"""The thought graph — a networkx view over the state's records.

*"the networkx graph as basically a thought graph that is rooted in the user
approval similar to how a graph rag works where it goes through cycles of
growth, compression and reconciliation such that only the correct data is
maintained across sessions."*

The records are the store; this is the view. It is rebuilt on demand from a
checkpointed state, so it can never drift from what was saved and it never
needs to be serialised. Anything that wants to traverse builds it first.

Node kinds and the edges between them::

    question ──asks──► reading ──evidences──► finding
    explicit ──grounds─► reading
    rival ──contends──► reading
    rival ──evidences──► finding

⚠️ **What this module does not yet do.** The alteration semantics — how an
approved ``close_node``, ``supersede``, ``compress`` or ``discard`` changes the
view and the package — are under review before they are built. Until then the
view reflects the records as authored plus the approval record, and
``invariants()`` is the structural check.
"""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from .state import GraphState

QUESTION = "question"
EXPLICIT = "explicit"
READING = "reading"
RIVAL = "rival"
FINDING = "finding"


def question_id(cycle: int) -> str:
    return f"q{cycle}"


def build(state: GraphState) -> nx.DiGraph:
    """The view, from every cycle's records."""
    g = nx.DiGraph()

    if state.question:
        g.add_node(question_id(state.cycle), kind=QUESTION, text=state.question, cycle=state.cycle)

    for e in state.explicits:
        g.add_node(e.id, kind=EXPLICIT, text=e.quote, cycle=e.cycle)

    decided = {d.write_id: d for d in state.decisions}
    closed: dict[str, str] = {}
    for w in state.proposed:
        d = decided.get(w.id)
        if d is not None and d.approved and w.write == "close_node" and w.target_id:
            closed[w.target_id] = w.argument or "closed"

    for a in state.assumptions:
        g.add_node(
            a.id,
            kind=READING,
            text=a.claim,
            cycle=a.cycle,
            moved_by=a.moved_by,
            budget_closed=a.id in state.budget_closed,
            verdict=closed.get(a.id, ""),
        )
        q = question_id(a.cycle)
        if q in g:
            g.add_edge(q, a.id, kind="asks", why=a.inferred_because)
        if a.grounded_in and a.grounded_in in g:
            g.add_edge(a.grounded_in, a.id, kind="grounds", why=a.inferred_because)

    for x in state.antitheses:
        g.add_node(x.id, kind=RIVAL, text=x.claim, cycle=x.cycle, moved_by=x.moved_by, verdict=closed.get(x.id, ""))
        if x.target in g:
            g.add_edge(x.id, x.target, kind="contends", why=x.inferred_because)

    for f in state.findings:
        g.add_node(f.id, kind=FINDING, text=f.excerpt, locator=f.locator, cycle=f.cycle, price=f.price)
        if f.node_id in g:
            g.add_edge(f.node_id, f.id, kind="evidences")

    return g


def invariants(g: nx.DiGraph) -> list[str]:
    """Every structural violation. Empty means clean."""
    problems: list[str] = []
    for nid, a in g.nodes(data=True):
        kind = a.get("kind")
        ins = list(g.in_edges(nid, data=True))
        if kind == READING and not any(d["kind"] in ("asks", "grounds") for _, _, d in ins):
            problems.append(f"{nid}: reading hangs off nothing")
        if kind == FINDING:
            parents = [u for u, _, d in ins if d["kind"] == "evidences"]
            if len(parents) != 1:
                problems.append(f"{nid}: finding has {len(parents)} parents, must be 1")
            elif g.nodes[parents[0]]["kind"] not in (READING, RIVAL):
                problems.append(f"{nid}: finding hangs off a {g.nodes[parents[0]]['kind']}")
        if kind == RIVAL:
            targets = [v for _, v, d in g.out_edges(nid, data=True) if d["kind"] == "contends"]
            if len(targets) != 1 or g.nodes[targets[0]]["kind"] != READING:
                problems.append(f"{nid}: rival must contend with exactly one reading")
    if not nx.is_directed_acyclic_graph(g):
        problems.append("graph is not acyclic")
    return problems


@dataclass(frozen=True, slots=True)
class Outline:
    """A flat, ordered rendering for a tree widget or a log line."""

    lines: tuple[tuple[int, str, str], ...]  # (depth, node id, label)


def outline(state: GraphState) -> Outline:
    g = build(state)
    lines: list[tuple[int, str, str]] = []

    def label(nid: str) -> str:
        a = g.nodes[nid]
        kind = a["kind"]
        text = " ".join(str(a.get("text", "")).split())
        if len(text) > 90:
            text = text[:89] + "…"
        marks = ""
        if a.get("verdict"):
            marks += f" [{a['verdict']}]"
        if a.get("budget_closed"):
            marks += " [budget closed]"
        if kind == FINDING:
            return f"{a.get('locator', '')} — \"{text}\""
        return f"{kind} {nid}: {text}{marks}"

    for nid, a in g.nodes(data=True):
        if a["kind"] not in (QUESTION, EXPLICIT):
            continue
        lines.append((0, nid, label(nid)))
        for _, r, d in g.out_edges(nid, data=True):
            lines.append((1, r, label(r)))
            for _, f, d2 in g.out_edges(r, data=True):
                if d2["kind"] == "evidences":
                    lines.append((2, f, label(f)))
            for x, _, d3 in g.in_edges(r, data=True):
                if d3["kind"] == "contends":
                    lines.append((2, x, label(x)))
                    for _, f, d4 in g.out_edges(x, data=True):
                        if d4["kind"] == "evidences":
                            lines.append((3, f, label(f)))
    return Outline(lines=tuple(lines))
