"""Everything consulted around a tool call, as SDK hooks and the permission gate.

Three callbacks, closed over the turn's ledger:

- **``PreToolUse`` — the meter and the surface.** Fires for every call before
  any rule or mode, which is what makes it the universal gate. It refuses a
  call outside the frame's surface, prices the rest, and refuses what the pool
  cannot afford. An evidence call it allows is *allowed*, so no built-in ever
  reaches a permission prompt. An authority-bearing call it lets through falls
  to the gate.
- **``PostToolUse`` — the record and the running count.** Keeps the result
  for the excerpt check and appends what is left in the pool, from the meter
  that is keeping it, at the moment the count changed.
- **``can_use_tool`` — the human gate.** Reached only by the in-graph
  authority-bearing calls (and, in chat mode, by whatever the CLI would have
  prompted for). Records the proposal and the decision, and puts the user's
  words back in the model's hands either way.

``StructuredOutput`` never reaches the gate (measured); the guard is kept
because a measured absence is a fact about one SDK version.
"""

from __future__ import annotations

from typing import Any

from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny

from ..graph.state import Decision, ProposedWrite
from ..graph.surface import available, bare_name, gated
from .events import ApprovalAnswered, ApprovalAsked, EventSink, Priced, Refused
from .meter import STRUCTURED_OUTPUT_TOOL
from .protocol import ApprovalRequest, Approver, refused_by_user
from .turn import TurnContext, response_text


def _deny(reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def _allow() -> dict[str, Any]:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow"}}


def pre_tool_use(turn: TurnContext, sink: EventSink):
    async def hook(input_data: dict[str, Any], tool_use_id: str | None, context: Any) -> dict[str, Any]:
        name = str(input_data.get("tool_name", ""))
        call_id = tool_use_id or str(input_data.get("tool_use_id", ""))
        if name == STRUCTURED_OUTPUT_TOOL:
            return {}
        if not available(turn.request.stage, name):
            reason = f"NOT_AVAILABLE: {bare_name(name)} does not exist in the {turn.request.stage} frame."
            turn.meter.refused.append(f"{name}: not in surface")
            sink.emit(Refused(tool_use_id=call_id, name=name, reason=reason))
            return _deny(reason)
        refusal, price, remaining = turn.meter.charge(name, call_id)
        if refusal:
            sink.emit(Refused(tool_use_id=call_id, name=name, reason=refusal))
            return _deny(refusal)
        if price:
            sink.emit(
                Priced(
                    tool_use_id=call_id,
                    name=name,
                    call_class=turn.meter.entries[-1].call,
                    price=price,
                    pool=turn.meter.default_pool,
                    remaining=remaining,
                )
            )
        if gated(name):
            return {}  # falls through to the human gate
        return _allow()

    return hook


def post_tool_use(turn: TurnContext, sink: EventSink):
    async def hook(input_data: dict[str, Any], tool_use_id: str | None, context: Any) -> dict[str, Any]:
        call_id = tool_use_id or str(input_data.get("tool_use_id", ""))
        turn.record(call_id, response_text(input_data.get("tool_response")))
        if turn.request.status is not None and turn.meter.price_paid(call_id) > 0:
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": turn.request.status(turn.meter.remaining()),
                }
            }
        return {}

    return hook


def _summarise(tool_input: dict[str, Any]) -> str:
    parts = [f"{k}={v!r}" for k, v in tool_input.items() if k not in ("because", "user_words")]
    return ", ".join(parts)[:400]


def permission_gate(turn: TurnContext, sink: EventSink, approver: Approver):
    """The ``can_use_tool`` callback for a graph frame."""

    async def can_use_tool(tool_name: str, tool_input: dict[str, Any], context: Any):
        if tool_name == STRUCTURED_OUTPUT_TOOL:
            return PermissionResultAllow(updated_input=tool_input)
        call_id = getattr(context, "tool_use_id", "") or ""
        if not gated(tool_name):
            # A built-in the CLI would have prompted for. The meter already
            # priced it in PreToolUse; it is evidence, never approval.
            return PermissionResultAllow(updated_input=tool_input)

        proposal = ProposedWrite(
            id=turn.next_proposal_id(),
            cycle=turn.request.cycle,
            write=bare_name(tool_name),
            stage=turn.request.stage,
            target_id=str(tool_input.get("target", "") or tool_input.get("candidate_id", "")),
            argument=_summarise(tool_input),
            because=str(tool_input.get("because", "")),
        )
        turn.proposals.append(proposal)
        sink.emit(
            ApprovalAsked(
                tool_use_id=call_id,
                name=proposal.write,
                input=dict(tool_input),
                title=getattr(context, "title", "") or f"{proposal.write} {proposal.target_id}".strip(),
            )
        )
        verdict = await approver.approve(
            ApprovalRequest(
                kind="alteration",
                tool_use_id=call_id,
                name=proposal.write,
                input=tool_input,
                title=getattr(context, "title", "") or "",
                description=getattr(context, "description", "") or "",
                stage=turn.request.stage,
            )
        )
        turn.verdicts[call_id] = verdict
        turn.decisions.append(
            Decision(
                write_id=proposal.id,
                approved=verdict.approved,
                answered_by=verdict.answered_by,
                cycle=turn.request.cycle,
                words=verdict.words,
            )
        )
        sink.emit(
            ApprovalAnswered(
                tool_use_id=call_id,
                name=proposal.write,
                approved=verdict.approved,
                words=verdict.words,
                answered_by=verdict.answered_by,
            )
        )
        if not verdict.approved:
            return PermissionResultDeny(message=refused_by_user(verdict))
        return PermissionResultAllow(updated_input={**tool_input, "user_words": verdict.words})

    return can_use_tool


def chat_gate(sink: EventSink, approver: Approver):
    """The ``can_use_tool`` callback for a plain chat: every prompt goes to the
    user, and the model's questions go to the user too."""

    async def can_use_tool(tool_name: str, tool_input: dict[str, Any], context: Any):
        call_id = getattr(context, "tool_use_id", "") or ""
        if tool_name == "AskUserQuestion":
            answers = await approver.ask(list(tool_input.get("questions", [])))
            return PermissionResultAllow(
                updated_input={"questions": tool_input.get("questions", []), "answers": answers}
            )
        title = getattr(context, "title", "") or f"Claude wants to use {tool_name}"
        sink.emit(ApprovalAsked(tool_use_id=call_id, name=tool_name, input=dict(tool_input), title=title))
        verdict = await approver.approve(
            ApprovalRequest(
                kind="tool",
                tool_use_id=call_id,
                name=tool_name,
                input=tool_input,
                title=title,
                description=getattr(context, "description", "") or "",
            )
        )
        sink.emit(
            ApprovalAnswered(
                tool_use_id=call_id,
                name=tool_name,
                approved=verdict.approved,
                words=verdict.words,
                answered_by=verdict.answered_by,
            )
        )
        if not verdict.approved:
            return PermissionResultDeny(message=refused_by_user(verdict))
        return PermissionResultAllow(updated_input=tool_input)

    return can_use_tool
