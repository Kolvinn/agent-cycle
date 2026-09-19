"""The package — what one cycle hands the next.

Inside a cycle every frame continues one conversation, so no prompt re-renders
what the model already has. Across the boundary the conversation is thrown
away on purpose and the graph is injected in its place:

> "Now this is where the graph (after synth modification) is hard injected into
> the session content. So each full turn through to synthesis is extending the
> knowledge graph and effectively storing it in cache, and removing the
> unneeded stage tool output."

Evidence hangs off nodes, so rendering a node renders its evidence with it —
which is what lets the raw tool output be discarded without losing it.

Stable by construction: ordering is by id and cycle, never by recency, so the
text changes only when the graph does. That is what makes it worth caching.

⚠️ Compaction is recorded and not yet applied: an approved ``compress`` or
``discard`` appears in the decisions but does not change what renders, pending
the review of the alteration semantics. Until then the package renders the
whole graph, which is the wrong end of the failure but the safe one.
"""

from __future__ import annotations

from .state import GraphState

_EVIDENCE = "      - "


def _quote(text: str, limit: int = 240) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def render(state: GraphState) -> str:
    """The graph as the text a cycle opens with. Empty when there is nothing."""
    evidence: dict[str, list[str]] = {}
    for f in state.findings:
        evidence.setdefault(f.node_id, []).append(f'{_EVIDENCE}{f.locator} — "{_quote(f.excerpt)}"')

    blocks: list[str] = []

    if state.explicits:
        lines = ["KNOWN — the user's own words, registered by them:"]
        lines += [f'  [{e.id}] "{_quote(e.quote)}"' for e in state.explicits]
        blocks.append("\n".join(lines))

    if state.assumptions:
        lines = ["READINGS TAKEN SO FAR, and what was found for each:"]
        for a in state.assumptions:
            lines.append(f"  [{a.id}] {_quote(a.claim)}")
            if a.grounded_in:
                lines.append(f"      hangs off {a.grounded_in}")
            lines.append(f"      would be moved by: {_quote(a.moved_by)}")
            lines += evidence.get(a.id, [])
        blocks.append("\n".join(lines))

    if state.antitheses:
        lines = ["AGAINST THEM — the rival reading found for each:"]
        for r in state.antitheses:
            lines.append(f"  [{r.id}] contends with {r.target}: {_quote(r.claim)}")
            lines += evidence.get(r.id, [])
        blocks.append("\n".join(lines))

    refused = state.refused()
    if refused:
        answers = {d.write_id: d for d in state.decisions}
        lines = ["THE USER REFUSED THESE. Do not propose them again:"]
        for w in refused:
            said = answers[w.id].words
            lines.append(
                f"  {w.write} {w.target_id or ''} — {_quote(w.argument)}".rstrip()
                + (f'\n      they said: "{_quote(said)}"' if said else "")
            )
        blocks.append("\n".join(lines))

    if state.budget_closed:
        blocks.append(
            "BUDGET CLOSED — these readings stopped buying, which says nothing "
            "about whether they are true:\n  " + ", ".join(state.budget_closed)
        )

    return "\n\n".join(blocks)


def opening(state: GraphState, prompt: str) -> str:
    """The first message of a cycle: the carried graph, then what is asked.

    The graph first because it is the stable part, worth caching; the question
    last because it is the only part that changes.
    """
    carried = render(state)
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
