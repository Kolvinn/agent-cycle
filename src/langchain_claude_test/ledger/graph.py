"""The ledger engine — a NetworkX DiGraph with the explicit/implicit invariants
enforced mechanically.

Ported from the archived concept-graph engine in
``agent_framework/pipeline/memory/networkx/``. What survived: the
``GraphResult`` contract (a failure is a *message*, not an exception, so it can
be handed to a model as readable text), the DAG check, and the general shape of
returning a post-state graph rather than mutating in place.

What did not survive, and why:

- **Qdrant payloads, vectors, embeddings** — that engine was a memory store.
  This is a provenance ledger; nothing here is retrieved by similarity.
- **Ten relationship types** — collapsed to one. ``grounds`` is the only edge
  that carries authority, so it is the only edge worth having.
- **Delete operations** — a ledger is append-only with status transitions. The
  archived ``delete_relationships`` orphan check is actively wrong here: an
  implicit is *supposed* to have exactly one edge, so every legal deletion
  would trip it.
- **The duplicate-in-either-direction rule** — it forbade A->B when B->A
  existed, which conflated a symmetric "related_to" model with this one.

The invariant that matters most is enforced in one place, in
:func:`form_implicit`: an implicit's parent is always an explicit. There is no
other way to create an implicit and no public edge-adding API, so
implicit-to-implicit is unrepresentable rather than merely discouraged.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping

import networkx as nx

from .models import (
    EXPLICIT_STATUSES,
    IMPLICIT_STATUSES,
    GraphResult,
    LedgerEdge,
    LedgerNode,
    NewExplicit,
    NewImplicit,
    NodeStatus,
    Source,
)

# ---------------------------------------------------------------------------
# Legal status transitions
# ---------------------------------------------------------------------------

#: ``approved`` and ``rejected`` are terminal for implicits: once the user has
#: settled a claim, the agent may not re-open it on its own initiative.
#: ``parked`` is not terminal — an unanswered ask can still be answered later.
_TRANSITIONS: dict[str, frozenset[str]] = {
    "open": frozenset({"addressed"}),
    "addressed": frozenset(),
    "pending": frozenset({"approved", "rejected", "parked"}),
    "parked": frozenset({"approved", "rejected"}),
    "approved": frozenset(),
    "rejected": frozenset(),
}


def new_ledger() -> nx.DiGraph:
    """An empty ledger."""
    return nx.DiGraph()


# ---------------------------------------------------------------------------
# Projection helpers
# ---------------------------------------------------------------------------


def node(graph: nx.DiGraph, node_id: str) -> LedgerNode | None:
    if node_id not in graph:
        return None
    a = graph.nodes[node_id]
    return LedgerNode(
        id=node_id, kind=a["kind"], status=a["status"], text=a["text"], turn=a["turn"]
    )


def nodes(graph: nx.DiGraph, *, kind: str | None = None, status: str | None = None) -> tuple[LedgerNode, ...]:
    out = []
    for nid in graph.nodes:
        n = node(graph, nid)
        if n is None:
            continue
        if kind is not None and n.kind != kind:
            continue
        if status is not None and n.status != status:
            continue
        out.append(n)
    return tuple(sorted(out, key=lambda n: (n.turn, n.id)))


def edges(graph: nx.DiGraph) -> tuple[LedgerEdge, ...]:
    out = []
    for u, v, d in graph.edges(data=True):
        out.append(
            LedgerEdge(
                id=d["edge_id"], kind=d["kind"], source_id=u, target_id=v, source=d.get("source")
            )
        )
    return tuple(sorted(out, key=lambda e: e.id))


def grounds_edge_for(graph: nx.DiGraph, implicit_id: str) -> LedgerEdge | None:
    """The single ``grounds`` edge feeding an implicit, if any."""
    for u, v, d in graph.in_edges(implicit_id, data=True):
        if d["kind"] == "grounds":
            return LedgerEdge(id=d["edge_id"], kind="grounds", source_id=u, target_id=v, source=d.get("source"))
    return None


def open_explicits(graph: nx.DiGraph) -> tuple[LedgerNode, ...]:
    """Explicits not yet addressed. The round's completion condition is that
    this is empty."""
    return nodes(graph, kind="explicit", status="open")


def unresolved_implicits(graph: nx.DiGraph) -> tuple[LedgerNode, ...]:
    """Implicits still awaiting or lacking a user verdict."""
    return tuple(n for n in nodes(graph, kind="implicit") if n.status in ("pending", "parked"))


# ---------------------------------------------------------------------------
# register_explicit
# ---------------------------------------------------------------------------


def register_explicit(
    new: NewExplicit,
    *,
    current_graph: nx.DiGraph,
    turn: int,
    message_text: str,
) -> GraphResult:
    """Register a depth-0 node from the user's literal words.

    The quote is re-checked against ``message_text`` at the offset given. This
    is not defensive padding — it is the one mechanical check that separates a
    quote from a paraphrase, and paraphrase is already inference.
    """
    end = new.start + len(new.quote)
    actual = message_text[new.start : end]
    if actual != new.quote:
        return GraphResult(
            success=False,
            message=(
                f"register_explicit: quote is not verbatim at offset {new.start}. "
                f"claimed {new.quote!r}, message has {actual!r}"
            ),
            graph=current_graph,
        )

    node_id = str(uuid.uuid4())
    post = current_graph.copy()
    post.add_node(
        node_id,
        kind="explicit",
        status="open",
        text=new.quote,
        turn=turn,
        span=(new.start, end),
    )
    return GraphResult(
        success=True,
        message=f"register_explicit: registered {node_id[:8]}",
        graph=post,
        node_ids=(node_id,),
    )


# ---------------------------------------------------------------------------
# form_implicit — where the central invariant lives
# ---------------------------------------------------------------------------


def form_implicit(
    new: NewImplicit,
    *,
    current_graph: nx.DiGraph,
    turn: int,
) -> GraphResult:
    """Literalize an assumption and hang it off exactly one explicit.

    Creates the node and its single ``grounds`` edge together — they are one
    operation, so an implicit can never exist unparented, and the parent can
    never be anything but an explicit.
    """
    parent_id = new.grounded_in
    if parent_id not in current_graph:
        return GraphResult(
            success=False,
            message=f"form_implicit: grounded_in {parent_id!r} is not a known node",
            graph=current_graph,
        )

    parent_kind = current_graph.nodes[parent_id]["kind"]
    if parent_kind != "explicit":
        return GraphResult(
            success=False,
            message=(
                f"form_implicit: grounded_in {parent_id[:8]} is an {parent_kind}. "
                "An implicit's parent is always an explicit — this is the multi-hop "
                "failure, and it is refused whether or not the parent looks settled."
            ),
            graph=current_graph,
        )

    node_id = str(uuid.uuid4())
    edge_id = str(uuid.uuid4())
    post = current_graph.copy()
    post.add_node(node_id, kind="implicit", status="pending", text=new.claim, turn=turn, span=None)
    post.add_edge(parent_id, node_id, kind="grounds", edge_id=edge_id, source=None)

    if not nx.is_directed_acyclic_graph(post):
        return GraphResult(
            success=False,
            message=f"form_implicit: would introduce a cycle via {parent_id[:8]}",
            graph=current_graph,
        )

    return GraphResult(
        success=True,
        message=f"form_implicit: {node_id[:8]} grounded in {parent_id[:8]}",
        graph=post,
        node_ids=(node_id,),
        edge_ids=(edge_id,),
    )


# ---------------------------------------------------------------------------
# set_status
# ---------------------------------------------------------------------------


def set_status(
    node_id: str,
    status: NodeStatus,
    *,
    current_graph: nx.DiGraph,
    by_user: bool,
) -> GraphResult:
    """Move a node to a new status.

    ``by_user`` is required and checked, not decorative: an implicit's verdict
    may only ever come from a user turn. The agent cannot promote its own
    claim, however confident — that is the rule the whole ledger exists to
    hold, so it is enforced here rather than trusted to a caller's discipline.
    """
    if node_id not in current_graph:
        return GraphResult(success=False, message=f"set_status: {node_id!r} not found", graph=current_graph)

    attrs = current_graph.nodes[node_id]
    kind, current = attrs["kind"], attrs["status"]

    legal_for_kind = IMPLICIT_STATUSES if kind == "implicit" else EXPLICIT_STATUSES
    if status not in legal_for_kind:
        return GraphResult(
            success=False,
            message=f"set_status: {status!r} is not a legal status for an {kind}",
            graph=current_graph,
        )

    if status not in _TRANSITIONS[current]:
        return GraphResult(
            success=False,
            message=(
                f"set_status: {current!r} -> {status!r} is not a legal transition"
                + (" (settled verdicts are terminal)" if not _TRANSITIONS[current] else "")
            ),
            graph=current_graph,
        )

    if kind == "implicit" and not by_user:
        return GraphResult(
            success=False,
            message=(
                f"set_status: refusing to move implicit {node_id[:8]} to {status!r} without a "
                "user verdict. Self-report is not closure."
            ),
            graph=current_graph,
        )

    post = current_graph.copy()
    post.nodes[node_id]["status"] = status
    return GraphResult(
        success=True,
        message=f"set_status: {node_id[:8]} {current} -> {status}",
        graph=post,
        node_ids=(node_id,),
    )


# ---------------------------------------------------------------------------
# apply_source — the evidence lands on the link, not on either node
# ---------------------------------------------------------------------------


def apply_source(
    edge_id: str,
    source: Source,
    *,
    current_graph: nx.DiGraph,
    tool_results: Mapping[str, str],
) -> GraphResult:
    """Attach the most relevant source to a ``grounds`` edge.

    Three checks, all deterministic — none of them trusts the agent's account
    of its own evidence:

    1. the implicit must be ``approved`` (you do not source a claim nobody has
       signed off on);
    2. ``excerpt`` must appear verbatim in the result of the *specific* tool
       call named by ``tool_call_id``;
    3. ``answers`` must appear verbatim in the **explicit's** text — this is
       what makes the source relevant to the explicit entry, rather than merely
       relevant to the claim it happens to support.
    """
    match = [(u, v, d) for u, v, d in current_graph.edges(data=True) if d["edge_id"] == edge_id]
    if not match:
        return GraphResult(success=False, message=f"apply_source: edge {edge_id!r} not found", graph=current_graph)
    u, v, data = match[0]

    if data["kind"] != "grounds":
        return GraphResult(
            success=False,
            message=f"apply_source: edge {edge_id[:8]} is a {data['kind']!r} edge, not 'grounds'",
            graph=current_graph,
        )
    if data.get("source") is not None:
        return GraphResult(
            success=False,
            message=(
                f"apply_source: edge {edge_id[:8]} already carries a source "
                f"({data['source'].locator}). One link, one most-relevant source."
            ),
            graph=current_graph,
        )

    implicit_status = current_graph.nodes[v]["status"]
    if implicit_status != "approved":
        return GraphResult(
            success=False,
            message=(
                f"apply_source: implicit {v[:8]} is {implicit_status!r}, not 'approved'. "
                "Evidence is gathered for a signed-off claim, not to justify a pending one."
            ),
            graph=current_graph,
        )

    if source.tool_call_id not in tool_results:
        return GraphResult(
            success=False,
            message=f"apply_source: no recorded tool result for call {source.tool_call_id!r}",
            graph=current_graph,
        )
    if source.excerpt not in tool_results[source.tool_call_id]:
        return GraphResult(
            success=False,
            message=(
                f"apply_source: excerpt does not appear in the result of "
                f"{source.tool_call_id!r}. Claimed {source.excerpt[:60]!r}"
            ),
            graph=current_graph,
        )

    explicit_text = current_graph.nodes[u]["text"]
    if source.answers not in explicit_text:
        return GraphResult(
            success=False,
            message=(
                f"apply_source: 'answers' is not a verbatim span of the explicit. "
                f"Claimed {source.answers!r}, explicit reads {explicit_text!r}"
            ),
            graph=current_graph,
        )

    post = current_graph.copy()
    post.edges[u, v]["source"] = source
    return GraphResult(
        success=True,
        message=f"apply_source: {source.locator} -> edge {edge_id[:8]}",
        graph=post,
        edge_ids=(edge_id,),
    )


# ---------------------------------------------------------------------------
# check_invariants — a standing assertion, not a mutation
# ---------------------------------------------------------------------------


def to_jsonable(graph: nx.DiGraph) -> dict[str, object]:
    """Serialise the whole ledger for a snapshot.

    Includes ``invariants`` deliberately. A snapshot that recorded only the
    state, and not whether that state was legal, would let a corrupt ledger be
    archived as though it were fine — and the corruption is the thing worth
    catching after the fact.
    """
    return {
        "nodes": [
            {
                "id": nid,
                "kind": a["kind"],
                "status": a["status"],
                "text": a["text"],
                "turn": a["turn"],
                "span": list(a["span"]) if a.get("span") else None,
            }
            for nid, a in sorted(graph.nodes(data=True), key=lambda kv: (kv[1]["turn"], kv[0]))
        ],
        "edges": [
            {
                "id": d["edge_id"],
                "kind": d["kind"],
                "source_id": u,
                "target_id": v,
                "source": d["source"].model_dump(mode="json") if d.get("source") else None,
            }
            for u, v, d in sorted(graph.edges(data=True), key=lambda e: e[2]["edge_id"])
        ],
        "invariants": check_invariants(graph),
    }


def check_invariants(graph: nx.DiGraph) -> list[str]:
    """Return every invariant violation in the graph. Empty means clean.

    The mutation functions already make these unrepresentable, so this exists
    to catch a *future* API that forgets one — it is the test the engine runs
    against itself, not a runtime guard.
    """
    problems: list[str] = []

    for nid in graph.nodes:
        a = graph.nodes[nid]
        kind, status = a["kind"], a["status"]
        legal = IMPLICIT_STATUSES if kind == "implicit" else EXPLICIT_STATUSES
        if status not in legal:
            problems.append(f"{nid[:8]}: {kind} holds illegal status {status!r}")

        if kind == "implicit":
            parents = [(u, d) for u, _, d in graph.in_edges(nid, data=True) if d["kind"] == "grounds"]
            if len(parents) != 1:
                problems.append(f"{nid[:8]}: implicit has {len(parents)} grounds parents, must be exactly 1")
            for pid, _ in parents:
                if graph.nodes[pid]["kind"] != "explicit":
                    problems.append(f"{nid[:8]}: implicit is parented by an implicit ({pid[:8]})")

    for u, v, d in graph.edges(data=True):
        if d["kind"] == "grounds":
            if graph.nodes[u]["kind"] != "explicit":
                problems.append(f"edge {d['edge_id'][:8]}: grounds source is not an explicit")
            if graph.nodes[v]["kind"] != "implicit":
                problems.append(f"edge {d['edge_id'][:8]}: grounds target is not an implicit")

    if not nx.is_directed_acyclic_graph(graph):
        problems.append("graph is not acyclic")

    return problems
