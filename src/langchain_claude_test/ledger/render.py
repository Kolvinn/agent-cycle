"""Two renderings of a ledger.

:func:`to_mermaid` is for looking at — it follows the shapes and colours the
design documents already use, so a rendered turn is directly comparable to the
hand-drawn diagrams.

:func:`to_digest` is load-bearing. It is *the applied graph notation* that
survives the round boundary: when the tool traffic is stripped out of the
session, this text is what carries forward. It therefore has to be complete
enough to stand alone — a reader who sees only the digest must be able to tell
what was asked, what was assumed, who confirmed it, and on what evidence.
"""

from __future__ import annotations

import networkx as nx

from .graph import edges, grounds_edge_for, nodes
from .models import LedgerNode

_STATUS_MARK = {
    "open": "open",
    "addressed": "addressed",
    "pending": "PENDING SIGN-OFF",
    "approved": "approved",
    "rejected": "rejected",
    "parked": "parked",
}


def _short(node_id: str) -> str:
    return node_id[:8]


def _label(n: LedgerNode) -> str:
    prefix = "E" if n.kind == "explicit" else "I"
    return f"{prefix}:{_short(n.id)}"


def to_digest(graph: nx.DiGraph, *, turn: int | None = None) -> str:
    """The compact, self-contained notation that crosses the round boundary."""
    if graph.number_of_nodes() == 0:
        return "LEDGER: empty"

    head = "LEDGER" if turn is None else f"LEDGER after turn {turn}"
    lines = [head]

    for e in nodes(graph, kind="explicit"):
        lines.append(f'{_label(e)} [{_STATUS_MARK[e.status]}] "{e.text}"')
        for _, child, data in graph.out_edges(e.id, data=True):
            if data["kind"] != "grounds":
                continue
            i = next(n for n in nodes(graph, kind="implicit") if n.id == child)
            lines.append(f'  grounds -> {_label(i)} [{_STATUS_MARK[i.status]}] "{i.text}"')
            src = data.get("source")
            if src is None:
                lines.append("    source: (none applied)")
            else:
                lines.append(f'    source: {src.locator} — "{src.excerpt}"')
                lines.append(f'    answers: "{src.answers}"')

    orphans = [n for n in nodes(graph, kind="implicit") if grounds_edge_for(graph, n.id) is None]
    for o in orphans:  # unreachable by construction; shown rather than hidden if it ever happens
        lines.append(f'{_label(o)} [UNPARENTED — INVARIANT VIOLATION] "{o.text}"')

    return "\n".join(lines)


def to_mermaid(graph: nx.DiGraph, *, title: str | None = None) -> str:
    """Render the ledger as a Mermaid flowchart, in the design docs' palette."""
    lines: list[str] = []
    if title:
        lines.append(f"---\ntitle: {title}\n---")
    lines.append("flowchart LR")

    if graph.number_of_nodes() == 0:
        lines.append('    empty["(empty ledger)"]')
        return "\n".join(lines) + "\n"

    ids: dict[str, str] = {}
    for n in nodes(graph):
        token = ("E_" if n.kind == "explicit" else "I_") + _short(n.id)
        ids[n.id] = token
        text = n.text.replace('"', "'").replace("\n", " ")
        if len(text) > 70:
            text = text[:69] + "…"
        badge = "EXPLICIT" if n.kind == "explicit" else "IMPLICIT"
        lines.append(f'    {token}["{badge} · {_STATUS_MARK[n.status]}<br/>{text}"]')

    for e in edges(graph):
        label = "grounds" if e.source is None else f"grounds<br/>src: {e.source.locator}"
        lines.append(f'    {ids[e.source_id]} -->|"{label}"| {ids[e.target_id]}')

    explicit = [ids[n.id] for n in nodes(graph, kind="explicit")]
    pending = [ids[n.id] for n in nodes(graph, kind="implicit") if n.status in ("pending", "parked")]
    settled = [ids[n.id] for n in nodes(graph, kind="implicit") if n.status == "approved"]
    refused = [ids[n.id] for n in nodes(graph, kind="implicit") if n.status == "rejected"]

    lines.append("")
    lines.append("    classDef explicit fill:#90EE90,stroke:#2E7D2E,stroke-width:2px,color:darkgreen")
    lines.append("    classDef pending fill:#F0D58C,stroke:#8a6d1d,stroke-width:3px,stroke-dasharray:5 3,color:black")
    lines.append("    classDef approved fill:#F0D58C,stroke:#8a6d1d,stroke-width:2px,color:black")
    lines.append("    classDef rejected fill:#8a2b2b,stroke:#5c1c1c,stroke-width:2px,color:#fff")
    for name, members in (
        ("explicit", explicit),
        ("pending", pending),
        ("approved", settled),
        ("rejected", refused),
    ):
        if members:
            lines.append(f"    class {','.join(members)} {name}")

    return "\n".join(lines) + "\n"
