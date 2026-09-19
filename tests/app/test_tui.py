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
        assert [s.split(" · ")[0] for s in stages] == ["── orientate", "── assume", "── antithesis", "── synthesis"]
        blocks = list(app.transcript.query(ToolBlock))
        assert any("Read" in b.title for b in blocks)
        assert any("refused" in b.title for b in blocks)  # the Bash call
        assert app.panel.graph_tree.root.label.plain.startswith("cycle 1")
        assert "assume:a1.1: 4/5" in plain(app.panel.pools)
        assert "cycle 1" in plain(app.status)

        app.input.value = "/chat"
        await pilot.press("enter")
        app.input.value = "hi"
        await pilot.press("enter")
        await app.runner.queue.join()
        await pilot.pause(0.2)
        assert FakeChat.instances[0].sent == ["hi"]
        assistant = [plain(w) for w in app.transcript.query(".assistant")]
        assert any("echo: hi" in a for a in assistant)
