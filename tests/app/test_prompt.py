"""The prompt widget and the transcript's follow behaviour, driven by a pilot."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from langchain_claude_test.app.harness import events as ev
from langchain_claude_test.app.tui.prompt import PromptInput
from langchain_claude_test.app.tui.transcript import Transcript


class PromptHarness(App[None]):
    def __init__(self) -> None:
        super().__init__()
        self.submitted: list[str] = []
        self.hints: list[tuple[str, ...]] = []
        self.prompt = PromptInput(("/chat", "/graph", "/model", "/modes"), id="p")

    def compose(self) -> ComposeResult:
        yield self.prompt

    def on_prompt_input_submitted(self, event: PromptInput.Submitted) -> None:
        self.submitted.append(event.text)

    def on_prompt_input_hint_changed(self, event: PromptInput.HintChanged) -> None:
        self.hints.append(event.matches)


@pytest.mark.asyncio
async def test_enter_sends_and_shift_enter_breaks_the_line():
    app = PromptHarness()
    async with app.run_test(size=(40, 12)) as pilot:
        app.prompt.focus()
        await pilot.press(*"hello")
        await pilot.press("shift+enter")
        await pilot.press(*"world")
        assert app.prompt.text == "hello\nworld"
        assert app.prompt.styles.height.value == 4  # two lines plus the border
        await pilot.press("enter")
        await pilot.pause()
        assert app.submitted == ["hello\nworld"]
        assert app.prompt.text == ""

        await pilot.press(*"a long line that must wrap inside a narrow box rather than run off")
        await pilot.pause()
        assert app.prompt.styles.height.value > 3
        await pilot.press("ctrl+j")
        assert app.prompt.text.endswith("\n")
        await pilot.press("ctrl+a")
        assert app.prompt.selected_text == app.prompt.text
        await pilot.press("x")
        assert app.prompt.text == "x"


@pytest.mark.asyncio
async def test_tab_completes_a_command_and_the_hint_lists_matches():
    app = PromptHarness()
    async with app.run_test(size=(40, 12)) as pilot:
        app.prompt.focus()
        await pilot.press("/", "m")
        await pilot.pause()
        assert app.hints[-1] == ("/model", "/modes")
        await pilot.press("tab")
        assert app.prompt.text == "/mode"  # the common prefix of /model and /modes
        await pilot.press("l", "tab")
        assert app.prompt.text == "/model "
        await pilot.press(*"sonnet")
        await pilot.pause()
        assert app.hints[-1] == ()
        await pilot.press("enter")
        await pilot.pause()
        assert app.submitted == ["/model sonnet"]


class TranscriptHarness(App[None]):
    CSS = "Transcript { height: 6; }"

    def __init__(self) -> None:
        super().__init__()
        self.transcript = Transcript(id="t")

    def compose(self) -> ComposeResult:
        yield self.transcript


@pytest.mark.asyncio
async def test_transcript_stops_following_when_the_reader_scrolls_up():
    app = TranscriptHarness()
    async with app.run_test(size=(40, 8)) as pilot:
        t = app.transcript
        for i in range(20):
            t.apply(ev.Notice(text=f"line {i}"))
        await pilot.pause()
        assert t.following and t.scroll_y == t.max_scroll_y

        t.page_up()
        await pilot.pause()
        assert not t.following
        held = t.scroll_y
        for i in range(20, 30):
            t.apply(ev.TextDelta(text=f"more {i}\n"))
        await pilot.pause()
        assert t.scroll_y == held  # new content did not drag the view down

        t.follow()
        await pilot.pause()
        assert t.following and t.scroll_y == t.max_scroll_y
        t.apply(ev.Notice(text="tail"))
        await pilot.pause()
        assert t.scroll_y == t.max_scroll_y
