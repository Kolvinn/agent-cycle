"""The package — what one cycle hands the next.

Inside a cycle every frame continues one conversation, so no prompt re-renders
what the model already has. Across the boundary the conversation is thrown
away on purpose and the graph is injected in its place:

> "Now this is where the graph (after synth modification) is hard injected into
> the session content. So each full turn through to synthesis is extending the
> knowledge graph and effectively storing it in cache, and removing the
> unneeded stage tool output."

Rendered from the **applied** view (``thought.build``), so a merge, a move, a
verdict, a discard or a compression shows exactly as the user approved it: a
discarded node is gone, a compressed set renders as its summary, a superseded
claim is marked. Evidence hangs off nodes, so rendering a node renders its
evidence with it — which is what lets the raw tool output be discarded
without losing it.

**A neighbourhood, not the whole graph.** The facts, the summaries, and the
claims and entities within ``hops`` of the cycle's question (and of what the
question's words match) render in full; every other live node is one line,
and the free read tools fetch it. That is how a cycle reads a graph bigger
than a context window — the GraphRAG answer, with the user's facts as the
root.

Stable by construction: ordering is by id and cycle, never by recency, so the
text changes only when the graph does. That is what makes it worth caching.
"""

from __future__ import annotations

import networkx as nx

from . import thought
from . import vocabulary as v
from .store import Ledger

_EVIDENCE = "      - "


def _quote(text: str, limit: int = 240) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def _mark(a: dict) -> str:
    status = a.get("status", "")
    return f" [{status}]" if status and status != v.PROVISIONAL else ""


def _evidence_lines(g: nx.MultiDiGraph, nid: str) -> list[str]:
    out = []
    for f in thought.evidence_of(g, nid):
        fa = g.nodes[f]
        if fa.get("compressed"):
            continue
        out.append(f'{_EVIDENCE}[{f}] {fa.get("locator", "")} — "{_quote(fa["text"])}"')
    return out


def _one_line(g: nx.MultiDiGraph, nid: str) -> str:
    a = g.nodes[nid]
    name = f"{a['kind']}/{a['role']}" if a.get("role") else a["kind"]
    return f"  [{nid}] {name}: {_quote(a['text'], 100)}{_mark(a)}"


def seeds_for(g: nx.MultiDiGraph, ledger: Ledger, cycle: int, prompt: str) -> set[str]:
    """Where the neighbourhood grows from: the facts, this cycle's question
    (or the latest, before this cycle has one), and what the question's words
    match — so a new question reaches the part of the graph it is about."""
    seeds = set(thought.live_nodes(g, v.FACT))
    number = cycle if cycle in ledger.cycles else ledger.last_cycle
    if number:
        seeds.add(thought.question_id(number))
    text = prompt or ledger.question_of(number)
    seeds |= {nid for nid, _ in thought.search(g, text, limit=8)}
    return seeds


def _relation_lines(g: nx.MultiDiGraph, nid: str) -> list[str]:
    out = []
    for key, src, dst, a in thought.relational_edges(g, nid):
        if src == nid:
            why = f" ({_quote(a['why'], 120)})" if a.get("why") else ""
            out.append(f"      → {a['kind']} {dst}{why}  [{key}]")
    return out


def _visible(g: nx.MultiDiGraph, nid: str) -> bool:
    return thought.is_live(g, nid) and not g.nodes[nid].get("compressed")


def render(ledger: Ledger, view: nx.MultiDiGraph, *, cycle: int = 0, hops: int = 2, prompt: str = "") -> str:
    """The graph as the text a cycle opens with. Empty when there is nothing."""
    g = view
    inside = thought.neighbourhood(g, seeds_for(g, ledger, cycle, prompt), hops)
    blocks: list[str] = []

    facts = [n for n in thought.live_nodes(g, v.FACT)]
    if facts:
        lines = ["KNOWN — the user's own words, registered by them:"]
        for n in facts:
            grounds = [dst for dst, _, _ in thought.out_edges(g, n, v.GROUNDS)]
            lines.append(f'  [{n}] "{_quote(g.nodes[n]["text"])}"' + (f"  (grounds {', '.join(grounds)})" if grounds else ""))
        blocks.append("\n".join(lines))

    context = [line for q in thought.live_nodes(g, v.QUESTION) if q in inside for line in _evidence_lines(g, q)]
    if context:
        blocks.append("CONTEXT — what the surveys read and kept:\n" + "\n".join(context))

    entities = [n for n in thought.live_nodes(g, v.ENTITY) if _visible(g, n) and n in inside]
    if entities:
        lines = ["ENTITIES — things in the project the surveys named (provisional until you confirm, merge or discard them):"]
        for n in entities:
            a = g.nodes[n]
            lines.append(f"  [{n}] {_quote(a['text'])} ({a.get('role') or 'concept'}){_mark(a)}")
            lines += _relation_lines(g, n)
            lines += _evidence_lines(g, n)
        blocks.append("\n".join(lines))

    def claims(role: str) -> list[str]:
        return [n for n in thought.live_nodes(g, v.CLAIM) if g.nodes[n].get("role") == role and _visible(g, n) and n in inside]

    assumptions = claims("assumption")
    if assumptions:
        lines = ["ASSUMPTIONS MADE SO FAR, and what each rests on:"]
        for n in assumptions:
            a = g.nodes[n]
            lines.append(f"  [{n}] {_quote(a['text'])}{_mark(a)}")
            grounded = [src for src, _, _ in thought.in_edges(g, n, v.GROUNDS)]
            if grounded:
                lines.append(f"      hangs off {', '.join(grounded)}")
            if a.get("moved_by"):
                lines.append(f"      would be moved by: {_quote(a['moved_by'])}")
            cites = [dst for dst, _, _ in thought.out_edges(g, n, v.CITES)]
            if cites:
                lines.append(f"      rests on: {', '.join(cites)}")
            replaced = [dst for dst, _, _ in thought.out_edges(g, n, v.SUPERSEDES)]
            if replaced:
                lines.append(f"      supersedes: {', '.join(replaced)}")
            lines += _relation_lines(g, n)
            lines += _evidence_lines(g, n)
        blocks.append("\n".join(lines))

    counters = claims("counter")
    if counters:
        lines = ["AGAINST THEM — the rival found for each:"]
        for n in counters:
            a = g.nodes[n]
            targets = [dst for dst, _, _ in thought.out_edges(g, n, v.CONTENDS)]
            lines.append(f"  [{n}] contends with {', '.join(targets) or '?'}: {_quote(a['text'])}{_mark(a)}")
            lines += _relation_lines(g, n)
            lines += _evidence_lines(g, n)
        blocks.append("\n".join(lines))

    observations = claims("observation")
    if observations:
        lines = ["OBSERVATIONS — claims recorded along the way, provisional:"]
        for n in observations:
            a = g.nodes[n]
            lines.append(f"  [{n}] {_quote(a['text'])}{_mark(a)}")
            lines += _relation_lines(g, n)
            lines += _evidence_lines(g, n)
        blocks.append("\n".join(lines))

    summaries = thought.live_nodes(g, v.SUMMARY)
    if summaries:
        lines = ["COMPRESSED — summaries standing in for what they name; the members are kept, not shown:"]
        for n in summaries:
            members = [dst for dst, _, _ in thought.out_edges(g, n, v.SUMMARISES)]
            lines.append(f"  [{n}] {_quote(g.nodes[n]['text'])}  (stands for {', '.join(members)})")
        blocks.append("\n".join(lines))

    beyond = [n for n in thought.live_nodes(g, v.CLAIM, v.ENTITY) if _visible(g, n) and n not in inside]
    if beyond:
        lines = [
            f"ELSEWHERE IN THE GRAPH — {len(beyond)} node(s) further from this question, one line each; "
            "graph_neighbours(id) shows one in full, graph_search(text) finds by words:"
        ]
        lines += [_one_line(g, n) for n in beyond]
        blocks.append("\n".join(lines))

    refused = ledger.refused()
    if refused:
        lines = ["THE USER REFUSED THESE. Do not propose them again:"]
        for w in refused:
            said = ledger.decisions[w.id].words
            lines.append(
                f"  {w.write} {w.target_id or ''} — {_quote(w.argument)}".rstrip()
                + (f'\n      they said: "{_quote(said)}"' if said else "")
            )
        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


def opening(ledger: Ledger, view: nx.MultiDiGraph, prompt: str, *, hops: int = 2) -> str:
    """The first message of a cycle: the carried graph, then what is asked.

    The graph first because it is the stable part, worth caching; the question
    last because it is the only part that changes.
    """
    carried = render(ledger, view, hops=hops, prompt=prompt)
    if not carried:
        return prompt
    return (
        "This is what you already know. It was built with the user across earlier "
        "cycles and everything in it was either registered by them or found by "
        "you. The tool output that produced it is gone; this is what was kept.\n\n"
        f"{carried}\n\n"
        "---\n\n"
        f"{prompt}"
    )


# ---------------------------------------------------------------------------
# Reading one node, a neighbourhood, a search — the same text for the agent's
# read tools and the shell's /show
# ---------------------------------------------------------------------------


def describe_node(g: nx.MultiDiGraph, nid: str) -> str:
    """One node in full: text, status, why, every live edge, its evidence, its history."""
    if nid not in g:
        return f"{nid!r} is not a node in the graph."
    a = g.nodes[nid]
    lines = [thought.label(g, nid)]
    if a.get("authority"):
        lines.append(f"  authority: {a['authority']}; cycle {a.get('cycle', '?')}")
    if a.get("inferred_because"):
        lines.append(f"  why: {_quote(a['inferred_because'])}")
    if a.get("moved_by"):
        lines.append(f"  would be moved by: {_quote(a['moved_by'])}")
    if a.get("because"):
        lines.append(f"  the user said: {_quote(a['because'])}")
    if a.get("merged_into"):
        lines.append(f"  merged into {a['merged_into']}")
    for dst, key, ea in thought.out_edges(g, nid):
        tag = f" [{key}]" if ea.get("relational") else ""
        lines.append(f"  → {ea['kind']} {dst}{tag}" + (f" — {_quote(ea['why'], 100)}" if ea.get("why") else ""))
    for src, key, ea in thought.in_edges(g, nid):
        tag = f" [{key}]" if ea.get("relational") else ""
        lines.append(f"  ← {ea['kind']} {src}{tag}" + (f" — {_quote(ea['why'], 100)}" if ea.get("why") else ""))
    lines += _evidence_lines(g, nid)
    for h in a.get("history", []):
        lines.append(f"  was: \"{_quote(h['text'], 100)}\" ({h['kind']}/{h['role']}) until cycle {h['cycle']}: {_quote(h['because'], 80)}")
    return "\n".join(lines)


def describe_neighbours(g: nx.MultiDiGraph, nid: str, depth: int = 1) -> str:
    """A node in full, then every node within ``depth`` of it, one line each."""
    if nid not in g:
        return f"{nid!r} is not a node in the graph."
    around = sorted(thought.neighbourhood(g, [nid], depth) - {nid})
    lines = [describe_node(g, nid)]
    if around:
        lines.append(f"within {depth} hop(s):")
        lines += [_one_line(g, n) for n in around]
    else:
        lines.append("nothing else within reach.")
    return "\n".join(lines)


def describe_search(g: nx.MultiDiGraph, text: str, limit: int = 20) -> str:
    hits = thought.search(g, text, limit)
    if not hits:
        return f"no node matches {text!r}."
    return "\n".join(_one_line(g, nid) + f"  ({n} word(s) match)" for nid, n in hits)
