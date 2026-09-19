"""The app: a transcript, an input, a graph panel, a status line."""

from __future__ import annotations

import argparse
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.suggester import SuggestFromList
from textual.widgets import Input

from ..config import AppConfig
from ..harness import events as ev
from ..runner import Runner
from ..session import SessionRecord
from .panels import GraphPanel, StatusBar
from .screens import TuiApprover
from .transcript import Transcript


class HarnessEventMessage(Message):
    def __init__(self, event: ev.HarnessEvent) -> None:
        super().__init__()
        self.event = event


class TuiSink:
    """The :class:`EventSink` the runner emits into: posts to the app."""

    def __init__(self, app: "ProvenanceApp") -> None:
        self.app = app

    def emit(self, event: ev.HarnessEvent) -> None:
        self.app.post_message(HarnessEventMessage(event))


class ProvenanceApp(App[None]):
    TITLE = "provenance"
    CSS = """
    Screen { layout: vertical; }
    #body { height: 1fr; }
    #main { width: 1fr; }
    #transcript { height: 1fr; }
    #input { dock: bottom; }
    """
    BINDINGS = [
        Binding("escape", "interrupt", "Interrupt", priority=True),
        Binding("ctrl+q", "quit", "Quit", priority=True),
    ]

    def __init__(self, config: AppConfig, session: str | None = None) -> None:
        super().__init__()
        self.config = config
        self.initial_session = session
        self.sink = TuiSink(self)
        self.approver = TuiApprover(self)
        self.runner = Runner(config=config, sink=self.sink, approver=self.approver)
        self.runner.on_session = self._session_changed
        self.runner.on_quit = self.exit
        self.transcript = Transcript(id="transcript")
        self.panel = GraphPanel(id="panel")
        self.status = StatusBar(id="status")
        self.input = Input(
            placeholder="message, or /command  (/help)",
            suggester=SuggestFromList(self.runner.commands.suggestions(), case_sensitive=False),
            id="input",
        )

    def compose(self) -> ComposeResult:
        with Horizontal(id="body"):
            with Vertical(id="main"):
                yield self.transcript
                yield self.input
            yield self.panel
        yield self.status

    def on_mount(self) -> None:
        self.input.focus()
        self.status.set_busy(False)
        self.run_worker(self._run_runner(), exclusive=True, name="runner")
        self.set_interval(0.25, self._poll_busy)

    async def _run_runner(self) -> None:
        try:
            await self.runner.run(self.initial_session)
        except Exception as exc:  # the shell died; say so rather than vanish
            self.transcript.apply(ev.Notice(text=f"runner stopped: {type(exc).__name__}: {exc}", level="error"))

    def _poll_busy(self) -> None:
        self.status.set_busy(self.runner.busy)

    def _session_changed(self, record: SessionRecord | None) -> None:
        self.status.set_session(record)

    # --- input ----------------------------------------------------------------------

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        self.input.value = ""
        if not text:
            return
        self.transcript.user(text)
        self.runner.submit(text)

    async def action_interrupt(self) -> None:
        await self.runner.interrupt()

    # --- events ---------------------------------------------------------------------

    def on_harness_event_message(self, message: HarnessEventMessage) -> None:
        event = message.event
        if isinstance(event, ev.StateSnapshot):
            self.panel.apply(event)
        else:
            self.transcript.apply(event)
        self.status.apply(event)


def run(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="langchain-claude-test", description="A Claude shell with a provenance cycle behind /graph.")
    parser.add_argument("session", nargs="?", help="session to open or create")
    parser.add_argument("--cwd", default=None, help="the directory the model works in (default: here)")
    parser.add_argument("--model", default=None, help="model alias or id for new turns")
    args = parser.parse_args(argv)
    config = AppConfig.default(Path(args.cwd) if args.cwd else None)
    if args.model:
        config = AppConfig(
            cwd=config.cwd,
            sessions_dir=config.sessions_dir,
            modes=config.modes,
            settings=config.settings.with_model(args.model),
            budgets=config.budgets,
            prices=config.prices,
            extra_env=config.extra_env,
        )
    ProvenanceApp(config, args.session).run()
