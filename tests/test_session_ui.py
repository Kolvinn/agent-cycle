"""The headless UI path — the one the round driver is tested through.

These are cheap tests of a thin adapter, but two of them guard real failure
modes rather than coverage: a sign-off that defaults when nobody answered, and
a "correction" that carries no correction.
"""

from __future__ import annotations

import pytest

from langchain_claude_test.ledger import Trace
from langchain_claude_test.ledger import trace as tr
from langchain_claude_test.session import ScriptedUI, SignOff


@pytest.mark.asyncio
async def test_messages_are_replayed_in_order():
    ui = ScriptedUI(messages=["first", "second"])
    assert await ui.get_input() == "first"
    assert await ui.get_input() == "second"


@pytest.mark.asyncio
async def test_exhausted_messages_end_the_session():
    ui = ScriptedUI(messages=[])
    assert await ui.get_input() == ""


@pytest.mark.asyncio
async def test_exhausted_signoffs_raise_rather_than_default():
    """The failure this guards is specific and has happened before: a stub
    approving something because nobody was there to say no."""
    ui = ScriptedUI(signoffs=[])
    with pytest.raises(AssertionError, match="exhausted"):
        await ui.ask_signoff(claim="x is true", node_id="abc123", grounded_in_text="y")


@pytest.mark.asyncio
async def test_bare_verdicts_are_marked_as_scripted():
    """A shorthand verdict must still be attributable — it is not a human."""
    ui = ScriptedUI(signoffs=["approved"])
    out = await ui.ask_signoff(claim="x", node_id="abc", grounded_in_text="y")
    assert out.verdict == "approved"
    assert out.answered_by == "scripted"


def test_correction_without_text_is_refused():
    with pytest.raises(ValueError, match="replacement text"):
        SignOff(verdict="corrected", answered_by="human")


@pytest.mark.asyncio
async def test_everything_shown_is_captured():
    ui = ScriptedUI()
    t = Trace()
    await ui.show_event(t.emit(tr.EXPLICIT_REGISTERED, turn=1, node_id="n1", quote="q"))
    await ui.show_reply("findings")
    await ui.show_panel("LEDGER", "body")

    assert [e.kind for e in ui.events] == [tr.EXPLICIT_REGISTERED]
    assert ui.replies == ["findings"]
    assert ui.panels == [("LEDGER", "body")]


@pytest.mark.asyncio
async def test_questions_are_recorded_for_assertion():
    ui = ScriptedUI(signoffs=["rejected", "approved"])
    await ui.ask_signoff(claim="first claim", node_id="a", grounded_in_text="e")
    await ui.ask_signoff(claim="second claim", node_id="b", grounded_in_text="e")
    assert ui.questions == ["first claim", "second claim"]


def test_scripted_ui_satisfies_the_protocol():
    """The runner depends on the protocol, not the class — so this is the
    check that the two adapters stay interchangeable."""
    from langchain_claude_test.session.ui.protocol import UI

    assert isinstance(ScriptedUI(), UI)
