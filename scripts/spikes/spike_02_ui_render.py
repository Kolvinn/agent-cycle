"""Spike 2 — does the UI layer render a whole round legibly?

No model, no tools: a canned trace is pushed through the real interactive
adapter so the *rendering* can be judged on its own. The round it replays is
the one from the design docs, including the turn-3 violation, so what shows up
here is directly comparable to the hand-drawn diagrams.

Run:  .venv/bin/python scripts/spikes/spike_02_ui_render.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from langchain_claude_test.ledger import (  # noqa: E402
    NewExplicit,
    NewImplicit,
    Source,
    Trace,
    apply_source,
    form_implicit,
    new_ledger,
    register_explicit,
    set_status,
    to_digest,
    to_mermaid,
)
from langchain_claude_test.ledger import trace as tr  # noqa: E402
from langchain_claude_test.session.ui import interactive_ui  # noqa: E402

MSG = "Where do we validate the incoming webhook signature?"
QUOTE = "validate the incoming webhook signature"
GREP = "webhook/handlers.py:42:def verify_signature(payload: bytes, sig: str) -> bool:"


async def main() -> int:
    t = Trace()
    g = new_ledger()

    async with interactive_ui(width=76) as ui:
        await ui.show_event(t.emit(tr.TURN_STARTED, turn=1))
        await ui.show_event(t.emit(tr.USER_MESSAGE, turn=1, text=MSG))

        r = register_explicit(
            NewExplicit(quote=QUOTE, start=MSG.index(QUOTE)),
            current_graph=g, turn=1, message_text=MSG,
        )
        g, eid = r.graph, r.node_ids[0]
        await ui.show_event(
            t.emit(tr.EXPLICIT_REGISTERED, turn=1, node_id=eid, quote=QUOTE,
                   span=[MSG.index(QUOTE), MSG.index(QUOTE) + len(QUOTE)])
        )

        # --- free tier: a survey, forming no claim, costing no hop ----------
        await ui.show_event(
            t.emit(tr.GATE_DECISION, turn=1, tool="list_dir", tier="free", tool_call_id="c0",
                   args={"path": "webhook/"}, would_be="allow", executed="allow",
                   reason="survey forms no claim — consumes no hop")
        )
        await ui.show_event(
            t.emit(tr.TOOL_CALL, turn=1, tool="list_dir", args={"path": "webhook/"}, tool_call_id="c0")
        )
        await ui.show_event(
            t.emit(tr.TOOL_RESULT, turn=1, tool_call_id="c0",
                   text="handlers.py\nsignature.py\n__init__.py")
        )

        # --- the assumption, and a gated call refused before sign-off -------
        r = form_implicit(
            NewImplicit(claim="validation happens in handlers.py at verify_signature", grounded_in=eid),
            current_graph=g, turn=1,
        )
        g, iid, edge = r.graph, r.node_ids[0], r.edge_ids[0]
        await ui.show_event(
            t.emit(tr.ASSUMPTION_FORMED, turn=1, node_id=iid, grounded_in=eid,
                   claim="validation happens in handlers.py at verify_signature")
        )
        await ui.show_event(
            t.emit(tr.GATE_DECISION, turn=1, tool="grep", tier="gated", tool_call_id="c1",
                   args={"pattern": "verify_signature"}, would_be="ask", executed="deny",
                   reason=f"implicit {iid[:8]} is pending — evidence follows sign-off, not the other way round")
        )

        # --- sign-off, then the same call succeeds -------------------------
        await ui.show_event(t.emit(tr.SIGNOFF_REQUESTED, turn=1, node_id=iid, claim=r.message))
        g = set_status(iid, "approved", current_graph=g, by_user=True).graph
        await ui.show_event(
            t.emit(tr.SIGNOFF_ANSWERED, turn=1, verdict="approved", answered_by="scripted")
        )
        await ui.show_event(
            t.emit(tr.GATE_DECISION, turn=1, tool="grep", tier="gated", tool_call_id="c2",
                   args={"pattern": "verify_signature"}, would_be="allow", executed="allow",
                   reason=f"depth 1, scoped to approved implicit {iid[:8]}")
        )
        await ui.show_event(
            t.emit(tr.TOOL_CALL, turn=1, tool="grep", args={"pattern": "verify_signature"}, tool_call_id="c2")
        )
        await ui.show_event(t.emit(tr.TOOL_RESULT, turn=1, tool_call_id="c2", text=GREP))

        # --- the source lands on the link ----------------------------------
        src = Source(
            locator="webhook/handlers.py:42",
            excerpt="def verify_signature(payload: bytes, sig: str) -> bool:",
            answers=QUOTE,
            tool_call_id="c2",
        )
        sr = apply_source(edge, src, current_graph=g, tool_results={"c2": GREP})
        g = sr.graph
        await ui.show_event(
            t.emit(tr.SOURCE_APPLIED, turn=1, edge_id=edge, locator=src.locator, answers=src.answers)
        )

        await ui.show_reply(
            "**Round 1.** Signature validation lives in `webhook/handlers.py:42`, "
            "in `verify_signature`. One assumption was raised and you confirmed it."
        )
        await ui.show_panel("LEDGER", to_digest(g, turn=1))
        await ui.show_panel("MERMAID", to_mermaid(g, title="turn 1"))

    print("\n[spike 2: rendered ok]")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
