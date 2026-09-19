"""The thought graph — a networkx view over the project's op log.

*"the networkx graph as basically a thought graph that is rooted in the user
approval similar to how a graph rag works where it goes through cycles of
growth, compression and reconciliation such that only the correct data is
maintained across sessions."*

The records are the store; this is the view. It is rebuilt on demand from the
ledger, so it can never drift from what was saved and it never needs to be
serialised. Anything that wants to traverse builds it first.

Three layers (``vocabulary.py``)::

    things     entity ──depends_on/calls/part_of…──► entity        (relational, approved)
    claims     question ──asks──► claim(assumption) ◄──contends── claim(counter)
               fact ──grounds──► claim         claim ──requires/supports…──► claim|entity
    evidence   node ──evidences──► evidence     claim ──cites──► evidence
    summary    summary ──summarises──► node

**Building is base then ops.** The base is what the frames authored: cycles,
facts, assumptions, counters, findings. Then every operation in the log is
applied in order — ``apply`` — so an update, a merge, a move, a verdict or a
compression changes the view exactly as it was approved. The tools call the
same ``apply`` on their turn's copy, so a turn sees its own changes at once.

A ``MultiDiGraph``: two nodes may be joined by more than one edge (a counter
``contends`` with an assumption and later ``supersedes`` it). Every edge has
a key — its id for a relational edge, ``kind:src:dst`` for a structural one —
and a ``status``; a discarded edge stays in the graph, marked, so a merge's
history is readable, and everything that renders or checks looks at live ones.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterable, Iterator

import networkx as nx

from . import vocabulary as v
from .state import (
    Antithesis,
    Assumption,
    Closure,
    Compression,
    Cycle,
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

if TYPE_CHECKING:  # pragma: no cover — the store imports this module
    from .store import Ledger

LIVE = "live"


def question_id(cycle: int) -> str:
    return f"q{cycle}"


# ---------------------------------------------------------------------------
# Reading the view
# ---------------------------------------------------------------------------


def is_live(g: nx.MultiDiGraph, nid: str) -> bool:
    return nid in g and g.nodes[nid].get("status") != v.DISCARDED


def live_nodes(g: nx.MultiDiGraph, *kinds: str) -> list[str]:
    return [n for n, a in g.nodes(data=True) if a.get("status") != v.DISCARDED and (not kinds or a["kind"] in kinds)]


def live_ids(g: nx.MultiDiGraph) -> frozenset[str]:
    """Every id a finding or an alteration may point at: live claims, entities, facts."""
    return frozenset(live_nodes(g, v.CLAIM, v.ENTITY, v.FACT))


def out_edges(g: nx.MultiDiGraph, nid: str, kind: str | None = None) -> Iterator[tuple[str, str, dict]]:
    """Live out-edges as (dst, key, attrs)."""
    if nid not in g:
        return
    for _, dst, key, a in g.out_edges(nid, keys=True, data=True):
        if a.get("status") == LIVE and (kind is None or a["kind"] == kind):
            yield dst, key, a


def in_edges(g: nx.MultiDiGraph, nid: str, kind: str | None = None) -> Iterator[tuple[str, str, dict]]:
    """Live in-edges as (src, key, attrs)."""
    if nid not in g:
        return
    for src, _, key, a in g.in_edges(nid, keys=True, data=True):
        if a.get("status") == LIVE and (kind is None or a["kind"] == kind):
            yield src, key, a


def edge_kinds(g: nx.MultiDiGraph, src: str, dst: str) -> list[str]:
    """The kinds of the live edges from src to dst."""
    if not g.has_edge(src, dst):
        return []
    return [a["kind"] for a in g[src][dst].values() if a.get("status") == LIVE]


def edge_by_id(g: nx.MultiDiGraph, edge_id: str) -> tuple[str, str, dict] | None:
    for src, dst, key, a in g.edges(keys=True, data=True):
        if key == edge_id:
            return src, dst, a
    return None


def relational_edges(g: nx.MultiDiGraph, nid: str | None = None) -> list[tuple[str, str, str, dict]]:
    """Live relational edges as (id, src, dst, attrs), all or touching one node."""
    out = []
    for src, dst, key, a in g.edges(keys=True, data=True):
        if a.get("relational") and a.get("status") == LIVE and (nid is None or nid in (src, dst)):
            out.append((key, src, dst, a))
    return out


def evidence_of(g: nx.MultiDiGraph, nid: str) -> list[str]:
    return [dst for dst, _, _ in out_edges(g, nid, v.EVIDENCES)]


def attached(g: nx.MultiDiGraph, nid: str) -> tuple[list[str], list[str]]:
    """What keeps a node from being deleted: its evidence, its relational edges."""
    return evidence_of(g, nid), [key for key, _, _, _ in relational_edges(g, nid)]


def live_problem(g: nx.MultiDiGraph, nid: str, *kinds: str) -> str:
    """Empty if the node is live (and of one of the kinds); otherwise why not,
    as the sentence a tool result says."""
    if nid not in g:
        return f"{nid!r} is not a node in the graph."
    a = g.nodes[nid]
    if a.get("status") == v.DISCARDED:
        where = f" (merged into {a['merged_into']})" if a.get("merged_into") else ""
        return f"{nid} was discarded{where}."
    if kinds and a["kind"] not in kinds:
        return f"{nid} is a {a['kind']}, not {' or '.join(kinds)}."
    return ""


def supersedes_would_cycle(g: nx.MultiDiGraph, old: str, new: str) -> bool:
    """Whether ``new supersedes old`` closes a loop through existing supersessions."""
    seen, frontier = set(), [old]
    while frontier:
        n = frontier.pop()
        for dst, _, _ in out_edges(g, n, v.SUPERSEDES):
            if dst == new:
                return True
            if dst not in seen:
                seen.add(dst)
                frontier.append(dst)
    return False


# ---------------------------------------------------------------------------
# Retrieval — how a cycle reads a bigger graph
# ---------------------------------------------------------------------------

_STOP = frozenset(
    "a an the of in on at to for and or is are was were be been do does did we you i it this that "
    "these those with from by as what where when how why which who our your its into".split()
)


def words_of(text: str) -> set[str]:
    """The words worth matching on: lower-cased, three letters or more, no stop
    words. A path or a dotted name counts whole and by its parts, so
    "webhook" finds ``webhook/handlers.py``."""
    tokens = "".join(c.lower() if c.isalnum() or c in "_./-" else " " for c in text).split()
    out: set[str] = set()
    for t in tokens:
        out.add(t)
        out.update("".join(c if c.isalnum() else " " for c in t).split())
    return {w for w in out if len(w) >= 3 and w not in _STOP}


def search(g: nx.MultiDiGraph, text: str, limit: int = 20) -> list[tuple[str, int]]:
    """Live nodes whose text shares words with ``text``, best first, as (id, hits)."""
    wanted = words_of(text)
    if not wanted:
        return []
    scored = []
    for nid in live_nodes(g):
        hits = len(wanted & words_of(str(g.nodes[nid].get("text", ""))))
        if hits:
            scored.append((nid, hits))
    scored.sort(key=lambda p: (-p[1], p[0]))
    return scored[:limit]


#: The kinds a neighbourhood walks through. Evidence is a leaf; a summary is
#: rendered on its own.
_WALKABLE = frozenset({v.QUESTION, v.FACT, v.CLAIM, v.ENTITY})


def neighbourhood(g: nx.MultiDiGraph, seeds: Iterable[str], hops: int) -> set[str]:
    """The live claims, entities, facts and questions within ``hops`` of the
    seeds, over live edges in either direction."""
    inside = {s for s in seeds if is_live(g, s)}
    frontier = set(inside)
    for _ in range(max(0, hops)):
        nxt: set[str] = set()
        for nid in frontier:
            for dst, _, _ in out_edges(g, nid):
                if dst not in inside and is_live(g, dst) and g.nodes[dst]["kind"] in _WALKABLE:
                    nxt.add(dst)
            for src, _, _ in in_edges(g, nid):
                if src not in inside and is_live(g, src) and g.nodes[src]["kind"] in _WALKABLE:
                    nxt.add(src)
        inside |= nxt
        frontier = nxt
        if not frontier:
            break
    return inside


def compression_candidates(g: nx.MultiDiGraph, cycle: int, stale_after: int) -> list[tuple[str, str]]:
    """What compression should be proposed for this cycle: nodes the user
    closed in an earlier cycle, and provisional nodes older than
    ``stale_after`` cycles that nothing the user approved connects to."""
    out: list[tuple[str, str]] = []
    for nid in live_nodes(g, v.CLAIM, v.ENTITY):
        a = g.nodes[nid]
        if a.get("compressed") or a.get("cycle", 0) >= cycle:
            continue
        status = a.get("status", "")
        if status in v.TERMINAL:
            out.append((nid, f"{status} in cycle {a.get('cycle')}"))
        elif status == v.PROVISIONAL and cycle - a.get("cycle", 0) >= stale_after:
            approved = any(ea.get("authority") == v.USER for _, _, ea in in_edges(g, nid)) or any(
                ea.get("authority") == v.USER for _, _, ea in out_edges(g, nid)
            )
            if not approved:
                out.append((nid, f"provisional since cycle {a.get('cycle')}, nothing approved connects to it"))
    return out


# ---------------------------------------------------------------------------
# Building
# ---------------------------------------------------------------------------


def _node(g: nx.MultiDiGraph, nid: str, kind: str, text: str, **attrs: Any) -> None:
    status = attrs.pop("status", "")
    authority = attrs.pop("authority", v.AGENT)
    g.add_node(nid, kind=kind, text=text, status=status, authority=authority, compressed=False, history=[], **attrs)


def _edge(
    g: nx.MultiDiGraph,
    src: str,
    dst: str,
    kind: str,
    *,
    key: str = "",
    why: str = "",
    cycle: int = 0,
    relational: bool = False,
    authority: str = v.AGENT,
) -> str:
    key = key or f"{kind}:{src}:{dst}"
    g.add_edge(src, dst, key=key, kind=kind, why=why, cycle=cycle, relational=relational, authority=authority, status=LIVE)
    return key


def build(ledger: Ledger) -> nx.MultiDiGraph:
    """The view: every cycle's base records, then every operation in order."""
    g = nx.MultiDiGraph()

    for c in ledger.cycles.values():
        apply(g, c)
    for e in ledger.explicits.values():
        apply(g, e)
    for a in ledger.assumptions.values():
        apply(g, a)
    for x in ledger.antitheses.values():
        apply(g, x)
    for f in ledger.findings.values():
        apply(g, f)
    # cites and grounds edges need both ends in place
    for a in ledger.assumptions.values():
        for fid in a.evidence:
            if fid in g:
                _edge(g, a.id, fid, v.CITES, cycle=a.cycle)
    for e in ledger.explicits.values():
        for cid in e.supports:
            if cid in g and v.GROUNDS not in edge_kinds(g, e.id, cid):
                _edge(g, e.id, cid, v.GROUNDS, cycle=e.cycle, authority=v.USER)
    for op in ledger.ops:
        apply(g, op)
    return g


def apply(g: nx.MultiDiGraph, record: Any) -> None:
    """One record's effect on the view. Base records add; operations alter.

    Tolerant of a missing end: a record that names a node the view does not
    hold does nothing, so a broken line in the log costs one effect, not the
    whole view.
    """
    match record:
        case Cycle():
            _node(g, question_id(record.number), v.QUESTION, record.question, cycle=record.number, authority=v.USER)
        case Explicit():
            _node(g, record.id, v.FACT, record.quote, cycle=record.cycle, authority=v.USER)
            for cid in record.supports:
                if cid in g:
                    _edge(g, record.id, cid, v.GROUNDS, cycle=record.cycle, authority=v.USER)
        case Assumption():
            _node(
                g,
                record.id,
                v.CLAIM,
                record.claim,
                role="assumption",
                status=v.PROVISIONAL,
                cycle=record.cycle,
                moved_by=record.moved_by,
                inferred_because=record.inferred_because,
            )
            q = question_id(record.cycle)
            if q in g:
                _edge(g, q, record.id, v.ASKS, why=record.inferred_because, cycle=record.cycle)
            if record.grounded_in and record.grounded_in in g:
                _edge(g, record.grounded_in, record.id, v.GROUNDS, why=record.inferred_because, cycle=record.cycle, authority=v.USER)
        case Antithesis():
            _node(
                g,
                record.id,
                v.CLAIM,
                record.claim,
                role="counter",
                status=v.PROVISIONAL,
                cycle=record.cycle,
                moved_by=record.moved_by,
                inferred_because=record.inferred_because,
            )
            if record.target in g:
                _edge(g, record.id, record.target, v.CONTENDS, why=record.inferred_because, cycle=record.cycle)
        case Finding():
            _node(g, record.id, v.EVIDENCE, record.excerpt, locator=record.locator, cycle=record.cycle, price=record.price)
            if record.node_id in g:
                _edge(g, record.node_id, record.id, v.EVIDENCES, cycle=record.cycle)
        case NodeAdded():
            _node(g, record.id, record.kind, record.text, role=record.role, status=v.PROVISIONAL, cycle=record.cycle, inferred_because=record.why)
            if record.kind == v.CLAIM and record.role == "assumption":
                q = question_id(record.cycle)
                if q in g:
                    _edge(g, q, record.id, v.ASKS, why=record.why, cycle=record.cycle)
            if record.kind == v.CLAIM and record.role == "counter" and record.about in g:
                _edge(g, record.id, record.about, v.CONTENDS, why=record.why, cycle=record.cycle)
        case EdgeAdded():
            if record.src in g and record.dst in g:
                _edge(g, record.src, record.dst, record.kind, key=record.id, why=record.why, cycle=record.cycle, relational=True, authority=v.USER)
        case RelationKind():
            pass
        case NodeUpdated():
            if record.target in g:
                a = g.nodes[record.target]
                a["history"].append(
                    {"text": a["text"], "kind": a["kind"], "role": a.get("role", ""), "cycle": record.cycle, "because": record.because}
                )
                if record.text:
                    a["text"] = record.text
                if record.kind:
                    a["kind"] = record.kind
                if record.role:
                    a["role"] = record.role
        case EdgeUpdated():
            found = edge_by_id(g, record.target)
            if found is not None:
                _, _, a = found
                if record.kind:
                    a["kind"] = record.kind
                if record.why:
                    a["why"] = record.why
        case Tombstone():
            if record.target in g:
                a = g.nodes[record.target]
                a["status"] = v.DISCARDED
                a["because"] = record.because
                if record.merged_into:
                    a["merged_into"] = record.merged_into
                for *_, ea in list(g.out_edges(record.target, keys=True, data=True)) + list(g.in_edges(record.target, keys=True, data=True)):
                    ea["status"] = v.DISCARDED
            else:
                found = edge_by_id(g, record.target)
                if found is not None:
                    found[2]["status"] = v.DISCARDED
                    found[2]["because"] = record.because
        case Merge():
            _merge(g, record)
        case EvidenceMoved():
            if record.finding in g and record.to in g:
                for _, _, a in list(in_edges(g, record.finding, v.EVIDENCES)):
                    a["status"] = v.DISCARDED
                _edge(g, record.to, record.finding, v.EVIDENCES, cycle=record.cycle)
        case Closure():
            if record.target in g:
                g.nodes[record.target]["status"] = record.verdict
                g.nodes[record.target]["because"] = record.because
        case Supersession():
            if record.old in g and record.new in g:
                g.nodes[record.old]["status"] = v.SUPERSEDED
                g.nodes[record.new]["role"] = "assumption"
                _edge(g, record.new, record.old, v.SUPERSEDES, why=record.because, cycle=record.cycle, authority=v.USER)
                # the winner now answers whatever asked the loser
                for q, _, a in list(in_edges(g, record.old, v.ASKS)):
                    if v.ASKS not in edge_kinds(g, q, record.new):
                        _edge(g, q, record.new, v.ASKS, why=a["why"], cycle=record.cycle)
        case Compression():
            _node(g, record.id, v.SUMMARY, record.summary, cycle=record.cycle, authority=v.USER)
            for m in record.members:
                if m in g:
                    g.nodes[m]["compressed"] = True
                    _edge(g, record.id, m, v.SUMMARISES, cycle=record.cycle, authority=v.USER)


def _merge(g: nx.MultiDiGraph, record: Merge) -> None:
    """Everything moves; duplicates (same kind, same far end) collapse,
    keeping the target's earlier edge and its why."""
    s, t = record.source, record.target
    if s not in g or t not in g or s == t:
        return
    for _, dst, key, a in list(g.out_edges(s, keys=True, data=True)):
        if a["status"] != LIVE:
            continue
        a["status"] = v.DISCARDED
        if dst == t or a["kind"] in edge_kinds(g, t, dst):
            continue
        _edge(g, t, dst, a["kind"], key=key if a["relational"] else "", why=a["why"], cycle=a["cycle"], relational=a["relational"], authority=a["authority"])
    for src, _, key, a in list(g.in_edges(s, keys=True, data=True)):
        if a["status"] != LIVE:
            continue
        a["status"] = v.DISCARDED
        if src == t or a["kind"] in edge_kinds(g, src, t):
            continue
        _edge(g, src, t, a["kind"], key=key if a["relational"] else "", why=a["why"], cycle=a["cycle"], relational=a["relational"], authority=a["authority"])
    apply(g, Tombstone(target=s, cycle=record.cycle, because=record.because, merged_into=t))


# ---------------------------------------------------------------------------
# Invariants
# ---------------------------------------------------------------------------


def invariants(g: nx.MultiDiGraph) -> list[str]:
    """Every structural violation. Empty means clean."""
    problems: list[str] = []
    for nid, a in g.nodes(data=True):
        kind = a["kind"]
        if a.get("status") == v.DISCARDED:
            if any(ea["status"] == LIVE for _, _, ea in g.out_edges(nid, data=True)) or any(
                ea["status"] == LIVE for _, _, ea in g.in_edges(nid, data=True)
            ):
                problems.append(f"{nid}: discarded but still has live edges")
            continue
        if kind == v.CLAIM and a.get("role") == "assumption" and not any(
            ea["kind"] in (v.ASKS, v.GROUNDS) for _, _, ea in in_edges(g, nid)
        ):
            problems.append(f"{nid}: assumption hangs off nothing")
        if kind == v.EVIDENCE:
            parents = [src for src, _, _ in in_edges(g, nid, v.EVIDENCES)]
            if len(parents) != 1:
                problems.append(f"{nid}: evidence has {len(parents)} parents, must be 1")
            elif g.nodes[parents[0]]["kind"] not in (v.QUESTION, v.CLAIM, v.ENTITY):
                problems.append(f"{nid}: evidence hangs off a {g.nodes[parents[0]]['kind']}")
        if kind == v.CLAIM and a.get("role") == "counter":
            targets = [dst for dst, _, _ in out_edges(g, nid, v.CONTENDS)]
            if len(targets) != 1 or g.nodes[targets[0]]["kind"] != v.CLAIM:
                problems.append(f"{nid}: counter must contend with exactly one claim")
        if kind == v.SUMMARY and not any(True for _ in out_edges(g, nid, v.SUMMARISES)):
            problems.append(f"{nid}: summary summarises nothing")
    for key, src, dst, _ in relational_edges(g):
        if not is_live(g, src) or not is_live(g, dst):
            problems.append(f"{key}: relational edge with a discarded end")
    structural = nx.DiGraph()
    structural.add_nodes_from(g.nodes)
    supersedes = nx.DiGraph()
    for src, dst, a in g.edges(data=True):
        if a["status"] == LIVE and not a["relational"]:
            structural.add_edge(src, dst)
            if a["kind"] == v.SUPERSEDES:
                supersedes.add_edge(src, dst)
    if not nx.is_directed_acyclic_graph(structural):
        problems.append("structural graph is not acyclic")
    if supersedes.edges and not nx.is_directed_acyclic_graph(supersedes):
        problems.append("supersedes forms a cycle")
    return problems


# ---------------------------------------------------------------------------
# Outline
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Outline:
    """A flat, ordered rendering for a tree widget or a log line."""

    lines: tuple[tuple[int, str, str], ...]  # (depth, node id, label)


def label(g: nx.MultiDiGraph, nid: str) -> str:
    a = g.nodes[nid]
    kind = a["kind"]
    text = " ".join(str(a.get("text", "")).split())
    if len(text) > 90:
        text = text[:89] + "…"
    marks = ""
    if a.get("status") and a["status"] != v.PROVISIONAL:
        marks += f" [{a['status']}]"
    if a.get("compressed"):
        marks += " [compressed]"
    if kind == v.EVIDENCE:
        return f"{nid} {a.get('locator', '')} — \"{text}\""
    name = a.get("role") or kind
    if kind == v.ENTITY:
        name = f"entity/{a.get('role') or 'concept'}"
    return f"{name} {nid}: {text}{marks}"


def outline(g: nx.MultiDiGraph) -> Outline:
    lines: list[tuple[int, str, str]] = []

    def relations(nid: str, depth: int) -> None:
        for key, src, dst, a in relational_edges(g, nid):
            if src == nid:
                lines.append((depth, key, f"→ {a['kind']} {dst}"))

    def evidence(nid: str, depth: int) -> None:
        for f in evidence_of(g, nid):
            lines.append((depth, f, label(g, f)))

    for nid in live_nodes(g, v.QUESTION, v.FACT):
        lines.append((0, nid, label(g, nid)))
        evidence(nid, 1)
        for claim, _, _ in out_edges(g, nid):
            if g.nodes[claim]["kind"] != v.CLAIM or not is_live(g, claim):
                continue
            lines.append((1, claim, label(g, claim)))
            for f, _, _ in out_edges(g, claim, v.CITES):
                lines.append((2, f, "rests on " + label(g, f)))
            evidence(claim, 2)
            relations(claim, 2)
            for counter, _, _ in in_edges(g, claim, v.CONTENDS):
                if is_live(g, counter):
                    lines.append((2, counter, label(g, counter)))
                    evidence(counter, 3)
                    relations(counter, 3)
    for nid in live_nodes(g, v.ENTITY):
        lines.append((0, nid, label(g, nid)))
        evidence(nid, 1)
        relations(nid, 1)
    for nid in live_nodes(g, v.CLAIM):
        if g.nodes[nid].get("role") == "observation":
            lines.append((0, nid, label(g, nid)))
            evidence(nid, 1)
            relations(nid, 1)
    for nid in live_nodes(g, v.SUMMARY):
        lines.append((0, nid, label(g, nid)))
        for m, _, _ in out_edges(g, nid, v.SUMMARISES):
            lines.append((1, m, "stands for " + label(g, m)))
    return Outline(lines=tuple(lines))
