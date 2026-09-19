"""The in-process tools — what the model calls to change the store.

Every handler is thin: it validates against the turn's ledger and appends a
record. The evidence tools are not here; they are the SDK's built-ins, priced
by the hooks.

**Gated calls run only after the user has answered.** The gate
(``hooks.permission_gate``) records the proposal and the decision and, on
approval, injects the user's words into the call's input as ``user_words`` —
so the handler can echo them into the result the model reads. A refused call
never reaches its handler.

⚠️ ``close_node``, ``supersede``, ``compress``, ``discard`` and ``promote_fact``
record the approved call and apply **no effect** yet: their semantics are under
review. Their result says so, plainly, so the model does not report a change
that did not happen.
"""

from __future__ import annotations

from typing import Any, Callable

from claude_agent_sdk import SdkMcpTool, ToolAnnotations, create_sdk_mcp_server, tool

from ..graph.state import Decision, Explicit, Finding
from ..graph.surface import GRAPH_SERVER, STAGE_GRAPH_TOOLS, Stage
from .turn import TurnContext, normalise


def _text(text: str, *, error: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {"content": [{"type": "text", "text": text}]}
    if error:
        out["is_error"] = True
    return out


def _approved_note(args: dict[str, Any]) -> str:
    words = str(args.get("user_words", "")).strip()
    return f'Approved by the user. Their words, verbatim: "{words}"' if words else "Approved by the user."


PENDING_EFFECT = (
    " Recorded as a decision. Applying this change to the carried graph is not yet "
    "implemented; the decision is kept on the record and nothing in the graph has changed."
)


def _schema(props: dict[str, dict[str, Any]], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": required}


def graph_tools(turn: TurnContext) -> list[SdkMcpTool[Any]]:
    """The handlers, closed over this turn's ledger."""

    @tool(
        "attach_finding",
        "Attach sourced material to a node of the graph: where you looked (locator) and "
        "what it literally said (excerpt, copied verbatim from a tool result you received "
        "in this conversation). target names the node it serves — the reading position in "
        "the antithesis frame, a node id in synthesis; ignored while a single reading is funded. "
        "A finding is evidence, not a fact.",
        _schema(
            {
                "target": {"type": "string", "description": "Which node this serves (position or id)."},
                "locator": {"type": "string", "description": "Where it lives, e.g. src/app.py:42."},
                "excerpt": {"type": "string", "description": "Verbatim text from the tool result."},
            },
            ["target", "locator", "excerpt"],
        ),
        annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=False),
    )
    async def attach_finding(args: dict[str, Any]) -> dict[str, Any]:
        resolver = turn.request.finding_target
        node_id = resolver(str(args.get("target", ""))) if resolver else None
        if node_id is None:
            return _text(
                f"REFUSED: target {args.get('target')!r} names no node this frame can attach to.",
                error=True,
            )
        excerpt = str(args.get("excerpt", ""))
        source = turn.source_of(excerpt)
        if source is None:
            return _text(
                "REFUSED: the excerpt does not appear in any tool result you received this turn. "
                "Copy it from what actually came back.",
                error=True,
            )
        finding = Finding(
            id=turn.next_finding_id(),
            node_id=node_id,
            cycle=turn.request.cycle,
            locator=str(args.get("locator", "")).strip() or "(unknown)",
            excerpt=excerpt,
            tool_call_id=source,
            price=turn.meter.price_paid(source),
        )
        turn.findings.append(finding)
        return _text(f"Recorded {finding.id} on {node_id} (source call {source}).")

    @tool(
        "propose_fact",
        "Propose that a span of the user's OWN words in this conversation be registered as a "
        "known fact. The quote must be verbatim. The user answers this call; if they approve, "
        "the quote becomes a KNOWN node.",
        _schema(
            {
                "quote": {"type": "string", "description": "Verbatim span of something the user said."},
                "because": {"type": "string", "description": "Why this is worth registering."},
            },
            ["quote"],
        ),
    )
    async def propose_fact(args: dict[str, Any]) -> dict[str, Any]:
        quote = str(args.get("quote", ""))
        wanted = normalise(quote)
        if not wanted or not any(wanted in normalise(s) for s in turn.request.said):
            _mark_last_decision(turn, applied=False)
            return _text(
                "REFUSED: that quote is not a verbatim span of anything the user said this cycle. "
                "Paraphrase is already inference.",
                error=True,
            )
        explicit = Explicit(id=turn.next_explicit_id(), quote=quote, cycle=turn.request.cycle)
        turn.explicits.append(explicit)
        _mark_last_decision(turn, applied=True)
        return _text(f'{_approved_note(args)} Registered {explicit.id}: "{quote}"')

    @tool(
        "promote_fact",
        "Promote a parked candidate fact to a known fact. The user answers this call.",
        _schema({"candidate_id": {"type": "string"}, "because": {"type": "string"}}, ["candidate_id"]),
    )
    async def promote_fact(args: dict[str, Any]) -> dict[str, Any]:
        return _text(_approved_note(args) + PENDING_EFFECT)

    @tool(
        "close_node",
        "Ask the user to close a reading or rival with their verdict: confirmed or refuted. "
        "Only the user may close a node, in either direction.",
        _schema(
            {
                "target": {"type": "string", "description": "Node id, e.g. a1.2 or x1.1."},
                "verdict": {"type": "string", "enum": ["confirmed", "refuted"]},
                "because": {"type": "string"},
            },
            ["target", "verdict"],
        ),
    )
    async def close_node(args: dict[str, Any]) -> dict[str, Any]:
        if str(args.get("target", "")) not in turn.request.node_ids:
            return _text(f"REFUSED: {args.get('target')!r} is not a node in the graph.", error=True)
        return _text(_approved_note(args) + PENDING_EFFECT)

    @tool(
        "supersede",
        "Ask the user to let one node replace another — typically a rival replacing the "
        "reading it contends with.",
        _schema({"target": {"type": "string"}, "by": {"type": "string"}, "because": {"type": "string"}}, ["target", "by"]),
    )
    async def supersede(args: dict[str, Any]) -> dict[str, Any]:
        for key in ("target", "by"):
            if str(args.get(key, "")) not in turn.request.node_ids:
                return _text(f"REFUSED: {args.get(key)!r} is not a node in the graph.", error=True)
        return _text(_approved_note(args) + PENDING_EFFECT)

    @tool(
        "compress",
        "Ask the user to compress a node: keep a one-line summary and drop its evidence from "
        "what the next cycle sees.",
        _schema({"target": {"type": "string"}, "summary": {"type": "string"}}, ["target", "summary"]),
    )
    async def compress(args: dict[str, Any]) -> dict[str, Any]:
        if str(args.get("target", "")) not in turn.request.node_ids:
            return _text(f"REFUSED: {args.get('target')!r} is not a node in the graph.", error=True)
        return _text(_approved_note(args) + PENDING_EFFECT)

    @tool(
        "discard",
        "Ask the user to discard a node and its evidence from what the next cycle sees. The "
        "reason is kept so it is not proposed again.",
        _schema({"target": {"type": "string"}, "reason": {"type": "string"}}, ["target", "reason"]),
    )
    async def discard(args: dict[str, Any]) -> dict[str, Any]:
        if str(args.get("target", "")) not in turn.request.node_ids:
            return _text(f"REFUSED: {args.get('target')!r} is not a node in the graph.", error=True)
        return _text(_approved_note(args) + PENDING_EFFECT)

    return [attach_finding, propose_fact, promote_fact, close_node, supersede, compress, discard]


def _mark_last_decision(turn: TurnContext, *, applied: bool) -> None:
    if not turn.decisions:
        return
    last = turn.decisions[-1]
    turn.decisions[-1] = Decision(
        write_id=last.write_id,
        approved=last.approved,
        answered_by=last.answered_by,
        cycle=last.cycle,
        words=last.words,
        applied=applied,
    )


def tools_for(turn: TurnContext, stage: Stage) -> list[SdkMcpTool[Any]]:
    """Exactly the frame's in-graph tools. Empty for a reader."""
    wanted = STAGE_GRAPH_TOOLS[stage]
    return [t for t in graph_tools(turn) if t.name in wanted]


def graph_server(turn: TurnContext, stage: Stage):
    """The in-process MCP server carrying this frame's surface, or ``None``."""
    tools = tools_for(turn, stage)
    if not tools:
        return None
    return create_sdk_mcp_server(name=GRAPH_SERVER, version="0.1.0", tools=tools)


def handler_for(turn: TurnContext, stage: Stage, name: str) -> Callable[[dict[str, Any]], Any] | None:
    """A tool's handler by bare name, for the scripted harness to call directly."""
    for t in tools_for(turn, stage):
        if t.name == name:
            return t.handler
    return None


def schema_for(turn: TurnContext, stage: Stage, name: str) -> dict[str, Any] | None:
    for t in tools_for(turn, stage):
        if t.name == name:
            return t.input_schema if isinstance(t.input_schema, dict) else None
    return None
