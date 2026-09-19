"""The in-process tools — what the model calls to change the graph.

Every handler is thin: it validates against the turn's view, appends a record
to the turn's ledger and applies that record to the turn's copy of the view,
so the next call in the same turn sees it. The evidence tools are not here;
they are the SDK's built-ins, priced by the hooks.

Three classes of call (``graph/surface.py``):

- ``attach_finding`` — free, limited, overwritable; a finding claims nothing.
- ``add_node`` — ungated growth: an entity or a claim is born provisional and
  claims nothing until the user reconciles it.
- everything else — **gated**: run only after the user has answered. The
  gate (``hooks.permission_gate``) first runs the handler dry, so a call the
  handler would refuse is refused to the model without ever being put to the
  user — a malformed call is not a proposal. A well-formed one is recorded
  as a proposal with the decision and, on approval, the user's words are
  injected into the call's input as ``user_words`` so the handler can echo
  them into the result. A refused call never reaches its handler, so a
  record's existence *is* its approval.

Every record is a line in the project's op log; nothing is edited in place.
``delete_node`` refuses while evidence or relational edges remain — *"this
could be a merge where you choose one source and one target node and it
brings across the data"* — so nothing is orphaned by a deletion.
"""

from __future__ import annotations

from typing import Any, Callable

from claude_agent_sdk import SdkMcpTool, ToolAnnotations, create_sdk_mcp_server, tool

from ..graph import package, thought
from ..graph import vocabulary as v
from ..graph.state import (
    Closure,
    Compression,
    Decision,
    EdgeAdded,
    EdgeUpdated,
    EvidenceMoved,
    Explicit,
    Finding,
    Merge,
    NodeAdded,
    NodeUpdated,
    RelationKind,
    Supersession,
    Tombstone,
)
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


def _schema(props: dict[str, dict[str, Any]], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": required}


def _s(args: dict[str, Any], key: str) -> str:
    return str(args.get(key, "") or "").strip()


def _quote(text: str, limit: int = 60) -> str:
    flat = " ".join(str(text).split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def graph_tools(turn: TurnContext) -> list[SdkMcpTool[Any]]:
    """The handlers, closed over this turn's ledger and view."""

    g = turn.graph
    cycle = turn.request.cycle
    vocab_extra = turn.request.relation_kinds

    def refused(text: str) -> dict[str, Any]:
        if not turn.dry_run:
            _mark_last_decision(turn, applied=False)
        return _text("REFUSED: " + text, error=True)

    def done(args: dict[str, Any], text: str, gated: bool = True) -> dict[str, Any]:
        if gated and not turn.dry_run:
            _mark_last_decision(turn, applied=True)
            return _text(f"{_approved_note(args)} {text}")
        return _text(text)

    def live(nid: str, *kinds: str) -> str:
        return thought.live_problem(g, nid, *kinds)

    # --- reading the graph: free ----------------------------------------------------

    @tool(
        "graph_search",
        "Find nodes of the graph whose text shares words with yours: id, kind, status, one "
        "line each. Free. The package above renders only the neighbourhood of the question; "
        "this reaches the rest.",
        _schema({"text": {"type": "string"}}, ["text"]),
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def graph_search(args: dict[str, Any]) -> dict[str, Any]:
        return _text(package.describe_search(g, _s(args, "text")))

    @tool(
        "graph_neighbours",
        "One node in full — its text, status, every edge, its evidence, its history — and "
        "every node within depth hops of it, one line each. Free.",
        _schema({"id": {"type": "string"}, "depth": {"type": "integer", "minimum": 0, "maximum": 3}}, ["id"]),
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def graph_neighbours(args: dict[str, Any]) -> dict[str, Any]:
        depth = args.get("depth", 1)
        depth = int(depth) if isinstance(depth, (int, float, str)) and str(depth).isdigit() else 1
        return _text(package.describe_neighbours(g, _s(args, "id"), max(0, min(3, depth))))

    # --- growth: ungated --------------------------------------------------------

    @tool(
        "attach_finding",
        "Keep evidence on a node of the graph by RUNNING one read-only command and recording "
        "its output as the finding: cat, head, tail, sed -n 'a,bp', grep, rg, ls, find, wc, "
        "and read-only git (log, show, blame, diff, status, ls-files, grep). One command, no "
        "pipes or redirects, paths inside the working directory. The output comes back to you "
        "and is what the graph keeps (capped at 80 lines), so you never retype it. Free, with "
        "a hard limit per turn; to fix a mistake, pass replace=<finding id you created this "
        "turn> and it is overwritten in place, not counted again. target names the node it "
        "serves: the assumption's position in the antithesis frame, a node id (claim or "
        "entity) elsewhere; ignored in orientate, where every finding hangs off the question. "
        "A finding is evidence, not a fact.",
        _schema(
            {
                "target": {"type": "string", "description": "Which node this serves (position or id)."},
                "run": {"type": "string", "description": "The read-only command to run, e.g. sed -n '10,40p' src/app.py"},
                "replace": {"type": "string", "description": "Optional: id of a finding you created this turn, to overwrite."},
            },
            ["target", "run"],
        ),
        annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=False),
    )
    async def attach_finding(args: dict[str, Any]) -> dict[str, Any]:
        resolver = turn.request.finding_target
        node_id = resolver(_s(args, "target")) if resolver else None
        if node_id is None:
            return _text(f"REFUSED: target {args.get('target')!r} names no node this frame can attach to.", error=True)
        # A node the frame itself will author (a rival named by position) is not
        # in the view yet; one that is there must still be live.
        if node_id in g and (problem := live(node_id)):
            return _text("REFUSED: " + problem, error=True)
        replace = _s(args, "replace")
        existing = next((f for f in turn.findings if f.id == replace), None) if replace else None
        if replace and existing is None:
            return _text(f"REFUSED: {replace!r} is not a finding you created this turn; only those can be overwritten.", error=True)
        if existing is None and len(turn.findings) >= turn.max_findings:
            return _text(
                f"REFUSED: this turn has kept its limit of {turn.max_findings} findings. "
                "Overwrite one you created this turn with replace=<id>, or go on with what you have.",
                error=True,
            )
        command = _s(args, "run")
        if not command or turn.executor is None:
            return _text("REFUSED: run must be one read-only command.", error=True)
        output = turn.executor(command)
        if output.startswith("REFUSED"):
            return _text(output, error=True)
        if not output.strip():
            return _text("REFUSED: the command produced no output; nothing to keep.", error=True)
        finding = Finding(
            id=existing.id if existing is not None else turn.next_finding_id(),
            node_id=node_id,
            cycle=cycle,
            locator=command,
            excerpt=output,
            tool_call_id="",
            price=0,
        )
        if existing is not None:
            turn.findings[turn.findings.index(existing)] = finding
        else:
            turn.findings.append(finding)
        thought.apply(g, finding)
        verb = "Overwrote" if existing is not None else "Recorded"
        left = turn.max_findings - len(turn.findings)
        return _text(f"{verb} {finding.id} on {node_id} ({left} more this turn).\n\n{output}")

    @tool(
        "add_node",
        "Add a provisional node: an entity (a thing in the project: file, module, function, "
        "service, config, concept) or a claim (role observation, assumption or counter). It is "
        "born provisional with no authority — it claims nothing until the user confirms, "
        "merges or discards it — so this is not gated. Say why in one line. A counter must "
        "name the claim it contends with in about. Returns the id to use in later calls.",
        _schema(
            {
                "kind": {"type": "string", "enum": list(v.ADDABLE_KINDS)},
                "text": {"type": "string", "description": "The entity's name/path, or the claim as one proposition."},
                "role": {"type": "string", "description": f"entity: {'|'.join(v.ENTITY_ROLES)}; claim: {'|'.join(v.CLAIM_ROLES)}"},
                "why": {"type": "string", "description": "What you read that makes this worth a node."},
                "about": {"type": "string", "description": "For a counter: the claim id it contends with."},
            },
            ["kind", "text"],
        ),
    )
    async def add_node(args: dict[str, Any]) -> dict[str, Any]:
        kind, text, role, about = _s(args, "kind"), _s(args, "text"), _s(args, "role"), _s(args, "about")
        if kind not in v.ADDABLE_KINDS:
            return _text(f"REFUSED: kind must be one of {', '.join(v.ADDABLE_KINDS)}.", error=True)
        if not text:
            return _text("REFUSED: text is required.", error=True)
        roles = v.ENTITY_ROLES if kind == v.ENTITY else v.CLAIM_ROLES
        role = role or ("concept" if kind == v.ENTITY else "observation")
        if role not in roles:
            return _text(f"REFUSED: a {kind}'s role is one of {', '.join(roles)}.", error=True)
        if kind == v.CLAIM and role in ("assumption", "counter") and turn.request.stage != "synthesis":
            return _text(
                f"REFUSED: in this frame {role}s are named in your answer, not as nodes; the graph "
                "records them from your answer. add_node here takes entities and observations.",
                error=True,
            )
        if kind == v.CLAIM and role == "counter":
            problem = live(about, v.CLAIM) if about else "a counter needs about=<claim id it contends with>."
            if problem:
                return _text("REFUSED: " + problem, error=True)
        dup = next((n for n in thought.live_nodes(g, kind) if normalise(g.nodes[n]["text"]) == normalise(text)), None)
        if dup is not None:
            return _text(f"REFUSED: {dup} already says that; attach to it, or update_node it.", error=True)
        record = NodeAdded(id=turn.next_node_id(kind), cycle=cycle, kind=kind, role=role, text=text, why=_s(args, "why"), about=about)
        turn.keep(record)
        return _text(f"Added {record.id}: {kind}/{role} — {text}. Provisional; it claims nothing yet.")

    # --- relations: gated ---------------------------------------------------------

    @tool(
        "add_edge",
        "Propose a relation between two live nodes; the user answers this call. Kinds: "
        + v.vocabulary_line()
        + ". A relation outside the vocabulary is proposed as relates_to with proposed_kind, "
        "and approving it adds that kind to this project's vocabulary. why is required.",
        _schema(
            {
                "src": {"type": "string"},
                "kind": {"type": "string"},
                "dst": {"type": "string"},
                "why": {"type": "string"},
                "proposed_kind": {"type": "string", "description": "With kind=relates_to: a new relation name to add."},
                "because": {"type": "string"},
            },
            ["src", "kind", "dst", "why"],
        ),
    )
    async def add_edge(args: dict[str, Any]) -> dict[str, Any]:
        src, kind, dst, why, proposed = _s(args, "src"), _s(args, "kind"), _s(args, "dst"), _s(args, "why"), _s(args, "proposed_kind")
        for nid in (src, dst):
            if problem := live(nid):
                return refused(problem)
        if src == dst:
            return refused("an edge needs two different ends.")
        if not why:
            return refused("why is required on every relation.")
        extra = vocab_extra | {r.name for r in turn.graph_ops if isinstance(r, RelationKind)}
        if kind == v.RELATES_TO and proposed:
            if proposed in v.RELATIONS or proposed in v.STRUCTURAL:
                return refused(f"{proposed!r} already exists; use it as kind.")
            if proposed not in extra:
                turn.keep(RelationKind(name=proposed, cycle=cycle, because=why))
                extra = extra | {proposed}
            kind = proposed
        if problem := v.relation_allowed(kind, g.nodes[src]["kind"], g.nodes[dst]["kind"], extra):
            return refused(problem)
        if kind in thought.edge_kinds(g, src, dst):
            return refused(f"{src} already {kind} {dst}.")
        record = EdgeAdded(id=turn.next_edge_id(), cycle=cycle, src=src, kind=kind, dst=dst, why=why)
        turn.keep(record)
        return done(args, f"Added {record.id}: {src} {kind} {dst}.")

    @tool(
        "propose_fact",
        "Propose that a span of the user's OWN words in this conversation be registered as a "
        "known fact. The quote must be verbatim. The user answers this call; if they approve, "
        "the quote becomes a KNOWN node. supports may name the claims it grounds.",
        _schema(
            {
                "quote": {"type": "string", "description": "Verbatim span of something the user said."},
                "because": {"type": "string", "description": "Why this is worth registering."},
                "supports": {"type": "array", "items": {"type": "string"}, "description": "Claim ids this fact grounds."},
            },
            ["quote"],
        ),
    )
    async def propose_fact(args: dict[str, Any]) -> dict[str, Any]:
        quote = str(args.get("quote", ""))
        wanted = normalise(quote)
        if not wanted or not any(wanted in normalise(s) for s in turn.request.said):
            return refused("that quote is not a verbatim span of anything the user said this cycle. Paraphrase is already inference.")
        supports = tuple(str(x) for x in (args.get("supports") or []))
        for cid in supports:
            if problem := live(cid, v.CLAIM):
                return refused(problem)
        explicit = Explicit(id=turn.next_explicit_id(), quote=quote, cycle=cycle, supports=supports)
        turn.keep_explicit(explicit)
        return done(args, f'Registered {explicit.id}: "{quote}"' + (f" grounding {', '.join(supports)}" if supports else ""))

    # --- edits: gated -------------------------------------------------------------

    @tool(
        "update_node",
        "Ask the user to rename, reword or reclassify a node the agent made (entity, claim or "
        "summary). Give at least one of text, kind, role. The old text stays in the log.",
        _schema(
            {
                "target": {"type": "string"},
                "text": {"type": "string"},
                "kind": {"type": "string", "enum": list(v.ADDABLE_KINDS)},
                "role": {"type": "string"},
                "because": {"type": "string"},
            },
            ["target", "because"],
        ),
    )
    async def update_node(args: dict[str, Any]) -> dict[str, Any]:
        target, text, kind, role = _s(args, "target"), _s(args, "text"), _s(args, "kind"), _s(args, "role")
        if problem := live(target, v.CLAIM, v.ENTITY, v.SUMMARY):
            return refused(problem)
        if not (text or kind or role):
            return refused("give at least one of text, kind, role.")
        final_kind = kind or g.nodes[target]["kind"]
        if kind and g.nodes[target]["kind"] == v.SUMMARY:
            return refused("a summary cannot change kind.")
        if kind and kind != g.nodes[target]["kind"] and not role:
            return refused(f"changing {target} to a {kind} needs a role for it.")
        if role:
            roles = v.ENTITY_ROLES if final_kind == v.ENTITY else v.CLAIM_ROLES
            if role not in roles:
                return refused(f"a {final_kind}'s role is one of {', '.join(roles)}.")
        record = NodeUpdated(target=target, cycle=cycle, text=text, kind=kind, role=role, because=_s(args, "because"))
        turn.keep(record)
        return done(args, f"Updated {target}.")

    @tool(
        "update_edge",
        "Ask the user to change a relational edge's kind or why. Name it by id (r1.2).",
        _schema({"edge": {"type": "string"}, "kind": {"type": "string"}, "why": {"type": "string"}, "because": {"type": "string"}}, ["edge", "because"]),
    )
    async def update_edge(args: dict[str, Any]) -> dict[str, Any]:
        edge, kind, why = _s(args, "edge"), _s(args, "kind"), _s(args, "why")
        found = thought.edge_by_id(g, edge)
        if found is None or not found[2].get("relational"):
            return refused(f"{edge!r} is not a relational edge in the graph.")
        src, dst, a = found
        if a["status"] != thought.LIVE:
            return refused(f"{edge} was discarded.")
        if not (kind or why):
            return refused("give kind or why.")
        extra = vocab_extra | {r.name for r in turn.graph_ops if isinstance(r, RelationKind)}
        if kind and (problem := v.relation_allowed(kind, g.nodes[src]["kind"], g.nodes[dst]["kind"], extra)):
            return refused(problem)
        turn.keep(EdgeUpdated(target=edge, cycle=cycle, kind=kind, why=why, because=_s(args, "because")))
        return done(args, f"Updated {edge}: {src} {kind or a['kind']} {dst}.")

    @tool(
        "delete_node",
        "Ask the user to discard a node the agent made. Refused while evidence or relational "
        "edges remain on it — move_evidence or merge first, so nothing is lost by a deletion. "
        "The reason is kept.",
        _schema({"target": {"type": "string"}, "because": {"type": "string"}}, ["target", "because"]),
    )
    async def delete_node(args: dict[str, Any]) -> dict[str, Any]:
        target = _s(args, "target")
        if problem := live(target, v.CLAIM, v.ENTITY, v.SUMMARY):
            return refused(problem)
        evidence, edges = thought.attached(g, target)
        if evidence or edges:
            what = []
            if evidence:
                what.append(f"evidence {', '.join(evidence)}")
            if edges:
                what.append(f"relational edges {', '.join(edges)}")
            return refused(f"{target} still has {' and '.join(what)}. merge it into another node, or move_evidence / delete_edge first.")
        turn.keep(Tombstone(target=target, cycle=cycle, because=_s(args, "because")))
        return done(args, f"Discarded {target}.")

    @tool(
        "delete_edge",
        "Ask the user to discard a relational edge, by id.",
        _schema({"edge": {"type": "string"}, "because": {"type": "string"}}, ["edge", "because"]),
    )
    async def delete_edge(args: dict[str, Any]) -> dict[str, Any]:
        edge = _s(args, "edge")
        found = thought.edge_by_id(g, edge)
        if found is None or not found[2].get("relational") or found[2]["status"] != thought.LIVE:
            return refused(f"{edge!r} is not a live relational edge in the graph.")
        turn.keep(Tombstone(target=edge, cycle=cycle, because=_s(args, "because")))
        return done(args, f"Discarded {edge}.")

    @tool(
        "merge",
        "Ask the user to merge one node into another of the same kind: every edge and every "
        "piece of evidence of source moves to target, duplicates collapse, and source is "
        "discarded with a pointer to target. This is how two names for one thing become one.",
        _schema({"source": {"type": "string"}, "target": {"type": "string"}, "because": {"type": "string"}}, ["source", "target", "because"]),
    )
    async def merge(args: dict[str, Any]) -> dict[str, Any]:
        source, target = _s(args, "source"), _s(args, "target")
        for nid in (source, target):
            if problem := live(nid, v.CLAIM, v.ENTITY):
                return refused(problem)
        if source == target:
            return refused("source and target are the same node.")
        if g.nodes[source]["kind"] != g.nodes[target]["kind"]:
            return refused(f"{source} is a {g.nodes[source]['kind']} and {target} a {g.nodes[target]['kind']}; only like kinds merge.")
        evidence, edges = thought.attached(g, source)
        turn.keep(Merge(source=source, target=target, cycle=cycle, because=_s(args, "because")))
        moved = []
        if evidence:
            moved.append(f"evidence {', '.join(evidence)}")
        if edges:
            moved.append(f"relations {', '.join(edges)}")
        return done(
            args,
            f"Merges {source} ({_quote(g.nodes[source]['text'])}) into {target} ({_quote(g.nodes[target]['text'])}); "
            + (f"{' and '.join(moved)} move to {target}; " if moved else "nothing hangs off it; ")
            + f"{source} is discarded with a pointer to {target}.",
        )

    @tool(
        "move_evidence",
        "Ask the user to re-point one finding to another live node (a claim, an entity, or the "
        "cycle's question).",
        _schema({"finding": {"type": "string"}, "to": {"type": "string"}, "because": {"type": "string"}}, ["finding", "to", "because"]),
    )
    async def move_evidence(args: dict[str, Any]) -> dict[str, Any]:
        finding, to = _s(args, "finding"), _s(args, "to")
        if finding not in g or g.nodes[finding]["kind"] != v.EVIDENCE:
            return refused(f"{finding!r} is not a finding in the graph.")
        if problem := live(to, v.CLAIM, v.ENTITY, v.QUESTION):
            return refused(problem)
        if to in [src for src, _, _ in thought.in_edges(g, finding, v.EVIDENCES)]:
            return refused(f"{finding} is already on {to}.")
        turn.keep(EvidenceMoved(finding=finding, to=to, cycle=cycle, because=_s(args, "because")))
        return done(args, f"Moved {finding} to {to}.")

    # --- verdicts and compression: gated ----------------------------------------------

    @tool(
        "close_node",
        "Ask the user to close a claim or an entity with their verdict: confirmed or refuted. "
        "Only the user may close a node, in either direction, and it is terminal.",
        _schema(
            {
                "target": {"type": "string", "description": "Node id, e.g. a1.2 or x1.1 or n1.3."},
                "verdict": {"type": "string", "enum": list(v.VERDICTS)},
                "because": {"type": "string"},
            },
            ["target", "verdict"],
        ),
    )
    async def close_node(args: dict[str, Any]) -> dict[str, Any]:
        target, verdict = _s(args, "target"), _s(args, "verdict")
        if problem := live(target, v.CLAIM, v.ENTITY):
            return refused(problem)
        if verdict not in v.VERDICTS:
            return refused(f"verdict is one of {', '.join(v.VERDICTS)}.")
        status = g.nodes[target].get("status")
        if status in v.TERMINAL:
            return refused(f"{target} is already {status}; that is terminal.")
        turn.keep(Closure(target=target, verdict=verdict, cycle=cycle, because=_s(args, "because")))
        return done(args, f"{target} is now {verdict}.")

    @tool(
        "supersede",
        "Ask the user to let one claim replace another — typically a counter replacing the "
        "assumption it contends with. The old claim is marked superseded and keeps its "
        "evidence; the new one takes the assumption role.",
        _schema({"old": {"type": "string"}, "new": {"type": "string"}, "because": {"type": "string"}}, ["old", "new"]),
    )
    async def supersede(args: dict[str, Any]) -> dict[str, Any]:
        old, new = _s(args, "old"), _s(args, "new")
        for nid in (old, new):
            if problem := live(nid, v.CLAIM):
                return refused(problem)
        if old == new:
            return refused("old and new are the same claim.")
        if g.nodes[old].get("status") in v.TERMINAL:
            return refused(f"{old} is already {g.nodes[old]['status']}.")
        if thought.supersedes_would_cycle(g, old, new):
            return refused(f"{old} already supersedes {new}; that would be a cycle.")
        turn.keep(Supersession(old=old, new=new, cycle=cycle, because=_s(args, "because")))
        return done(args, f"{new} supersedes {old}; {new} is now an assumption and {old} is superseded.")

    @tool(
        "compress",
        "Ask the user to compress a set of nodes: a summary node stands in for them in what "
        "the next cycle sees. The members keep everything; they are just not rendered.",
        _schema(
            {
                "ids": {"type": "array", "items": {"type": "string"}, "description": "The nodes the summary stands for."},
                "summary": {"type": "string"},
            },
            ["ids", "summary"],
        ),
    )
    async def compress(args: dict[str, Any]) -> dict[str, Any]:
        ids = tuple(str(x).strip() for x in (args.get("ids") or []) if str(x).strip())
        summary = _s(args, "summary")
        if not ids:
            return refused("ids must name at least one node.")
        if not summary:
            return refused("summary is required.")
        for nid in ids:
            if problem := live(nid, v.CLAIM, v.ENTITY, v.EVIDENCE):
                return refused(problem)
            if g.nodes[nid].get("compressed"):
                return refused(f"{nid} is already compressed.")
        record = Compression(id=turn.next_summary_id(), members=ids, summary=summary, cycle=cycle)
        turn.keep(record)
        return done(args, f"Compressed {', '.join(ids)} into {record.id}.")

    return [
        graph_search,
        graph_neighbours,
        attach_finding,
        add_node,
        add_edge,
        propose_fact,
        update_node,
        update_edge,
        delete_node,
        delete_edge,
        merge,
        move_evidence,
        close_node,
        supersede,
        compress,
    ]


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
    """Exactly the frame's in-graph tools on this turn. Empty for a reader."""
    wanted = STAGE_GRAPH_TOOLS[stage] - turn.request.withheld
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
