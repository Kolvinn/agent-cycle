"""The package — what one cycle hands the next.

**Why anything is rendered at all.** Every earlier rule in this design said not
to re-render state into a prompt: the conversation already held it, so writing
it out again was paying tokens to repeat the model to itself. That rule held for
the frames *inside* a cycle, and it still does. It does not hold here, because
the cycle boundary throws the conversation away on purpose:

> "Now this is where the graph (after synth modification) is hard injected into
> the session content. So each full tuyrn thorugh to synthesis is extending the
> knowledge graph and effectively storing it in cache, and removing the uneeded
> stage tool output."

So the graph is not a restatement of the session. It *is* the session's carried
state, and the raw tool output that produced it is deliberately not carried. A
cycle is therefore a compaction: what survives is what was worth registering,
and what was scaffolding is dropped.

**Which is only safe because evidence hangs off nodes.** A finding is attached
to the node it speaks to, so rendering a node renders its evidence with it. That
is what lets the underlying tool output be discarded without losing it:

> "the agents need to be able to register tool output to certain nodes on the
> graph such that it can be reinjected into the context."

**Stable by construction.** Ordering is by id and by cycle, never by recency or
by anything derived from a set, so the text of a package changes only when the
graph does. That is what makes it worth caching as a prefix: it is identical on
every turn of a cycle and changes once, at the boundary.

⚠️ **Compaction is not applied here.** ``compress`` and ``discard`` are how you
and the agent decide what the next cycle stops seeing, and nothing yet carries
out an approved one — the store has no mutation layer. Until it does, this
renders the whole graph, which is the wrong end of the failure: it grows.
"""

from __future__ import annotations

from .state import GraphState

#: What a node's evidence is indented under it as. Not markdown — the package is
#: read by a model as context, and a heading level is a claim about structure
#: that plain indentation does not make.
_EVIDENCE = "      - "


def _quote(text: str, limit: int = 240) -> str:
    """One line, bounded. A package that grows without limit is not a compaction."""
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def render(state: GraphState) -> str:
    """The graph as the text a cycle opens with.

    Empty when there is nothing yet, which is the first cycle: there is no
    package before a conversation has produced one, and an empty heading would
    be the model's first impression of a graph that does not exist.
    """
    evidence: dict[str, list[str]] = {}
    for f in state.findings:
        evidence.setdefault(f.assumption_id, []).append(
            f'{_EVIDENCE}{f.locator} — "{_quote(f.excerpt)}"'
        )

    blocks: list[str] = []

    if state.explicits:
        lines = ["KNOWN — your own words, registered by you:"]
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
        lines = ["AGAINST THEM — the rival reading each set was found to miss:"]
        for r in state.antitheses:
            lines.append(f"  [{r.id}] {_quote(r.claim)}")
            if r.targets:
                lines.append(f"      contends with {', '.join(r.targets)}")
            lines += evidence.get(r.id, [])
        blocks.append("\n".join(lines))

    refused = state.refused()
    if refused:
        answers = {d.write_id: d for d in state.decisions}
        lines = ["YOU REFUSED THESE. Do not propose them again:"]
        for w in refused:
            said = answers[w.id].words
            lines.append(
                f"  {w.write} {w.target_id or ''} — {_quote(w.argument)}".rstrip()
                + (f'\n      you said: "{_quote(said)}"' if said else "")
            )
        blocks.append("\n".join(lines))

    if state.budget_closed:
        blocks.append(
            "BUDGET CLOSED — these readings stopped buying, which says nothing "
            "about whether they are true:\n  " + ", ".join(state.budget_closed)
        )

    return "\n\n".join(blocks)


def opening(state: GraphState, prompt: str) -> str:
    """The first message of a cycle: the carried graph, then what is being asked.

    In that order, and not the other way round. The graph is the stable part —
    identical for every turn of the cycle, and the thing worth having cached —
    so it goes first and the question, which is the only part that changes, goes
    last. The first cycle has no graph, and then this is just the question.
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
