"""The Textual app mounts, takes a command, and renders what the runner said —
with the model scripted and the chat faked, through the app's own runner."""

from __future__ import annotations

from pathlib import Path

import pytest

from langchain_claude_test.app.config import AppConfig, builtin_modes
from langchain_claude_test.app.harness.scripted import ScriptedApprover, ScriptedHarness
from langchain_claude_test.app.tui.app import ProvenanceApp
from langchain_claude_test.app.tui.transcript import ToolBlock

from .test_cycle import QUESTION, script
from .test_runner import PKG, FakeChat


def plain(widget) -> str:
    """The text a Static holds, whether it is rich Text or rich Markdown."""
    content = widget.content
    return getattr(content, "plain", None) or getattr(content, "markup", None) or str(content)


@pytest.mark.asyncio
async def test_app_runs_a_scripted_cycle_and_draws_it(tmp_path: Path):
    FakeChat.instances.clear()
    config = AppConfig(cwd=tmp_path, sessions_dir=tmp_path / "sessions", modes=builtin_modes(PKG))
    app = ProvenanceApp(config, "pilot")
    harness = ScriptedHarness(script=script(), approver=ScriptedApprover())
    app.runner._harness_factory = lambda r: harness
    app.runner._chat_factory = FakeChat

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.2)
        harness.sink = app.runner._session_sink  # the runner opened the session; record through it

        app.input.value = "/help"
        await pilot.press("enter")
        await app.runner.queue.join()
        await pilot.pause(0.2)
        notices = [w for w in app.transcript.query(".notice")]
        assert any("Built-ins" in plain(w) for w in notices)

        app.input.value = f"/graph {QUESTION}"
        await pilot.press("enter")
        await app.runner.queue.join()
        await pilot.pause(0.3)
        stages = [plain(w) for w in app.transcript.query(".stage")]
        assert [s.split(" · ")[0] for s in stages] == ["── orientate", "── antithesis", "── synthesis"]
        blocks = list(app.transcript.query(ToolBlock))
        assert any("Read" in b.title for b in blocks)
        assert any("refused" in b.title for b in blocks)  # the Bash call
        assert app.panel.graph_tree.root.label.plain.startswith("cycle 1")
        assert "orientation:1: 5/20" in plain(app.panel.pools)
        assert "cycle 1" in plain(app.status)

        # the browser: three views of the same snapshot, and a picked node shown in full
        await pilot.press("ctrl+b")
        assert "by kind" in app.panel.graph_tree.root.label.plain
        branches = [str(n.label) for n in app.panel.graph_tree.root.children]
        assert any(b.startswith("claim/assumption (2)") for b in branches) and any(b.startswith("evidence (") for b in branches)
        app.input.value = "/panel view status"
        await pilot.press("enter")
        await app.runner.queue.join()
        await pilot.pause(0.2)
        assert "by status" in app.panel.graph_tree.root.label.plain
        assert any(str(n.label).startswith("provisional (") for n in app.panel.graph_tree.root.children)
        app.panel.pick("a1.1")
        await pilot.pause(0.2)
        await app.runner.queue.join()
        await pilot.pause(0.2)
        shown = [plain(w) for w in app.transcript.query(".notice")]
        assert any(t.startswith("assumption a1.1:") and "← asks q1" in t for t in shown)
        app.input.value = "/panel view outline"
        await pilot.press("enter")
        await app.runner.queue.join()
        await pilot.pause(0.2)
        assert "by outline" in app.panel.graph_tree.root.label.plain

        app.input.value = "/chat"
        await pilot.press("enter")
        app.input.value = "hi"
        await pilot.press("enter")
        await app.runner.queue.join()
        await pilot.pause(0.2)
        assert FakeChat.instances[0].sent == ["hi"]
        assistant = [plain(w) for w in app.transcript.query(".assistant")]
        assert any("echo: hi" in a for a in assistant)


@pytest.mark.asyncio
async def test_panel_can_be_hidden_resized_and_shown(tmp_path: Path):
    FakeChat.instances.clear()
    config = AppConfig(cwd=tmp_path, sessions_dir=tmp_path / "sessions", modes=builtin_modes(PKG))
    app = ProvenanceApp(config, "panel")
    app.runner._harness_factory = lambda r: ScriptedHarness(script=script(), approver=ScriptedApprover())
    app.runner._chat_factory = FakeChat
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.2)
        assert app.panel_visible and app.panel.styles.width.value == 40
        await pilot.press("ctrl+g")
        assert not app.panel_visible
        await pilot.press("ctrl+left")
        assert app.panel_visible and app.panel.styles.width.value == 46
        app.input.value = "/panel 30"
        await pilot.press("enter")
        await app.runner.queue.join()
        await pilot.pause(0.1)
        assert app.panel.styles.width.value == 30
        app.input.value = "/panel hide"
        await pilot.press("enter")
        await app.runner.queue.join()
        await pilot.pause(0.1)
        assert not app.panel_visible
        assert "sonnet · medium" in plain(app.status)


@pytest.mark.asyncio
async def test_dragging_the_divider_resizes_the_panel(tmp_path: Path):
    FakeChat.instances.clear()
    config = AppConfig(cwd=tmp_path, sessions_dir=tmp_path / "sessions", modes=builtin_modes(PKG))
    app = ProvenanceApp(config, "drag")
    app.runner._harness_factory = lambda r: ScriptedHarness(script=script(), approver=ScriptedApprover())
    app.runner._chat_factory = FakeChat
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.2)
        assert app.divider.region.x == 120 - 40 - 1
        await pilot.mouse_down(app.divider, offset=(0, 5))
        await pilot.hover(offset=(59, 5))  # screen coordinates: 20 columns left of the divider
        await pilot.mouse_up(offset=(59, 5))
        await pilot.pause(0.1)
        assert app.panel.styles.width.value == 60
        assert app.divider.region.x == 120 - 60 - 1
        await pilot.press("ctrl+g")
        assert not app.divider.display


@pytest.mark.asyncio
async def test_every_terminal_size_renders_and_resizes_without_crashing(tmp_path: Path):
    """The panel hides itself before the main column can reach zero width, and
    the prompt drops its placeholder when there is no room to wrap it."""
    from langchain_claude_test.app.harness import events as ev
    from langchain_claude_test.app.harness.protocol import ApprovalRequest
    from langchain_claude_test.app.tui.screens import ApprovalScreen, ChoiceScreen

    FakeChat.instances.clear()
    config = AppConfig(cwd=tmp_path, sessions_dir=tmp_path / "sessions", modes=builtin_modes(PKG))
    for size in [(120, 40), (41, 10), (30, 8), (12, 6), (4, 3), (1, 1)]:
        app = ProvenanceApp(config, f"size{size[0]}x{size[1]}")
        app.runner._harness_factory = lambda r: ScriptedHarness(script=script(), approver=ScriptedApprover())
        app.runner._chat_factory = FakeChat
        async with app.run_test(size=size) as pilot:
            await pilot.pause(0.1)
            app.transcript.apply(ev.Notice(text="a notice " * 20))
            app.transcript.apply(ev.ToolStarted(tool_use_id="t1", name="Read"))
            app.transcript.apply(ev.ToolCalled(tool_use_id="t1", name="Read", input={"file_path": "x" * 80}))
            app.transcript.apply(ev.ToolResult(tool_use_id="t1", text="line\n" * 30, is_error=False))
            app.transcript.apply(ev.TextDelta(text="streaming " * 30))
            app.input.value = "typed text that is longer than any narrow terminal could hold on one line"
            for width, height in [(200, 50), (30, 8), (10, 4), (2, 2), (1, 1), (80, 24)]:
                await pilot.resize_terminal(width, height)
                await pilot.pause(0.05)
                assert app.size.width - (app.panel.size.width if app.panel_visible else 0) >= min(app.size.width, 24)
            app.push_screen(ApprovalScreen(ApprovalRequest(kind="alteration", tool_use_id="t9", name="close_node", input={"target": "a1.1"}, title="close a1.1", description="d")))
            await pilot.pause(0.05)
            await pilot.resize_terminal(3, 3)
            await pilot.pause(0.05)
            await pilot.press("ctrl+n")
            app.push_screen(ChoiceScreen("Model", [("a", "A"), ("b", "B")], current="a"))
            await pilot.pause(0.05)
            await pilot.resize_terminal(2, 2)
            await pilot.pause(0.05)
            await pilot.press("escape")
            await pilot.resize_terminal(100, 30)
            await pilot.pause(0.05)
            assert app.panel_visible
        assert app.return_code in (None, 0)


@pytest.mark.asyncio
async def test_a_tool_result_expands_and_copies_without_the_terminal(tmp_path: Path):
    """E55 "copy", E62 "any terminal". Textual copies out over OSC 52, which
    some terminals and multiplexers drop, and a tool result was cut at 24
    lines with the rest thrown away (tui/transcript.py:15,65-71). So the text
    is kept, `/expand` and ctrl+o show it whole, and `/copy` puts it on the
    clipboard from the keyboard — beside the mouse path, never instead of it.
    """
    from langchain_claude_test.app.harness import events as ev

    FakeChat.instances.clear()
    config = AppConfig(cwd=tmp_path, sessions_dir=tmp_path / "sessions", modes=builtin_modes(PKG))
    app = ProvenanceApp(config, "copy")
    app.runner._harness_factory = lambda r: ScriptedHarness(script=script(), approver=ScriptedApprover())
    app.runner._chat_factory = FakeChat

    body = "\n".join(f"line {i}" for i in range(30))
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause(0.2)
        app.input.value = "a message of mine"
        await pilot.press("enter")
        await app.runner.queue.join()
        await pilot.pause(0.2)

        app.transcript.apply(ev.ToolStarted(tool_use_id="t1", name="Read"))
        app.transcript.apply(ev.ToolCalled(tool_use_id="t1", name="Read", input={"file_path": "a.py"}))
        app.transcript.apply(ev.ToolResult(tool_use_id="t1", text=body, is_error=False))
        await pilot.pause(0.1)
        block = list(app.transcript.query(ToolBlock))[-1]
        assert "line 23" in plain(block._body) and "line 24" not in plain(block._body)
        assert "6 more lines" in plain(block._body)

        # /expand shows the whole of it and opens the block
        app.input.value = "/expand"
        await pilot.press("enter")
        await app.runner.queue.join()
        await pilot.pause(0.2)
        assert "line 29" in plain(block._body) and "more lines" not in plain(block._body)
        assert not block.collapsed

        # /copy tool copies the result in full, not the 24 lines that were drawn
        app.input.value = "/copy tool"
        await pilot.press("enter")
        await app.runner.queue.join()
        await pilot.pause(0.2)
        assert app._clipboard == body

        # /copy last is the model's last message; /copy user is mine, and the
        # /commands I typed to get here are not messages
        app.input.value = "/copy last"
        await pilot.press("enter")
        await app.runner.queue.join()
        await pilot.pause(0.2)
        assert app._clipboard == "[chat] echo: a message of mine"
        app.input.value = "/copy user"
        await pilot.press("enter")
        await app.runner.queue.join()
        await pilot.pause(0.2)
        assert app._clipboard == "a message of mine"

        # ctrl+o is the same thing without a command, for a second block
        app.transcript.apply(ev.ToolStarted(tool_use_id="t2", name="Grep"))
        app.transcript.apply(ev.ToolResult(tool_use_id="t2", text=body, is_error=False))
        await pilot.pause(0.1)
        second = list(app.transcript.query(ToolBlock))[-1]
        assert "6 more lines" in plain(second._body)
        await pilot.press("ctrl+o")
        await pilot.pause(0.1)
        assert "line 29" in plain(second._body)

        # the mouse path, checked rather than assumed. The audit read
        # ALLOW_SELECT = False at textual/widgets/_collapsible.py:22 as
        # Collapsible's; it is CollapsibleTitle's. A drag lands on the
        # innermost widget, which over the body is the result Static, so the
        # result always could be dragged over -- the *title* row (name, input,
        # price) is what cannot. That is the half /copy answers.
        from textual.widgets._collapsible import Collapsible, CollapsibleTitle

        assert CollapsibleTitle.ALLOW_SELECT is False
        assert "ALLOW_SELECT" not in vars(Collapsible)
        await pilot.mouse_down(second._body, offset=(0, 0))
        await pilot.hover(second._body, offset=(6, 3))
        await pilot.mouse_up(second._body, offset=(6, 3))
        await pilot.pause(0.1)
        assert (app.screen.get_selected_text() or "").startswith("line 0")


@pytest.mark.asyncio
async def test_escape_in_a_modal_leaves_the_modal_not_the_turn(tmp_path: Path):
    """Audit A2/A3 -> O. ``escape`` is an app-level *priority* binding
    (``tui/app.py:68``), and Textual checks priority bindings from the App
    down -- ``reversed(screen._binding_chain)``, ``textual/app.py:3976-3986``
    -- so no screen binding, priority or not, can outrank it. Before this
    change Esc inside any modal ran the app's interrupt while the modal stayed
    up, and ``ChoiceScreen``'s own escape binding (``tui/screens.py:123``) was
    never reached.
    """
    from textual.widgets import TextArea

    from langchain_claude_test.app.harness.protocol import ApprovalRequest, Verdict
    from langchain_claude_test.app.tui.screens import ApprovalScreen, ChoiceScreen, QuestionScreen

    FakeChat.instances.clear()
    config = AppConfig(cwd=tmp_path, sessions_dir=tmp_path / "sessions", modes=builtin_modes(PKG))
    app = ProvenanceApp(config, "esc")
    app.runner._harness_factory = lambda r: ScriptedHarness(script=script(), approver=ScriptedApprover())
    app.runner._chat_factory = FakeChat

    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause(0.2)
        interrupts: list[int] = []
        original = app.runner.interrupt

        async def spy() -> None:
            interrupts.append(1)
            await original()

        app.runner.interrupt = spy  # type: ignore[method-assign]

        # A3: the picker. Esc leaves it as it is and never reaches the harness.
        picked: list[str | None] = []
        app.push_screen(ChoiceScreen("Model", [("a", "A"), ("b", "B")], current="a"), lambda v: picked.append(v))
        await pilot.pause(0.1)
        assert isinstance(app.screen, ChoiceScreen)
        await pilot.press("escape")
        await pilot.pause(0.1)
        assert not isinstance(app.screen, ChoiceScreen), "Esc did not leave the picker"
        assert picked == [None]
        assert interrupts == [], "Esc in the picker interrupted the harness"

        # A2: the approval modal. Esc answers it -- a refusal, carrying the
        # words -- and does not interrupt the turn the modal is blocking.
        verdicts: list[Verdict] = []
        request = ApprovalRequest(kind="alteration", tool_use_id="t1", name="close_node", input={"target": "a1.1"}, title="close a1.1")
        app.push_screen(ApprovalScreen(request), lambda v: verdicts.append(v))
        await pilot.pause(0.1)
        app.screen.query_one("#words", TextArea).load_text("not this one")
        await pilot.press("escape")
        await pilot.pause(0.1)
        assert not isinstance(app.screen, ApprovalScreen), "Esc left the approval modal up"
        assert verdicts == [Verdict(approved=False, answered_by="human", words="not this one")]
        assert interrupts == [], "Esc in the approval modal interrupted the harness"

        # the model's question: Esc leaves it unanswered rather than hanging the frame
        answers: list[str] = []
        app.push_screen(QuestionScreen({"header": "h", "question": "q?", "options": []}), lambda v: answers.append(v))
        await pilot.pause(0.1)
        await pilot.press("escape")
        await pilot.pause(0.1)
        assert not isinstance(app.screen, QuestionScreen)
        assert answers == [""]
        assert interrupts == []

        # with no modal up, Esc still reaches the runner
        app.runner._busy = True
        await pilot.press("escape")
        await pilot.pause(0.1)
        assert interrupts == [1]
