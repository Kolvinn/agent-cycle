"""The app: a transcript, an input, a graph panel, a status line."""

from __future__ import annotations

import argparse
from pathlib import Path

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Static

from ..commands import parse
from ..config import AppConfig
from ..harness import events as ev
from ..runner import Runner
from ..session import SessionRecord
from .divider import Divider
from .panels import GraphPanel, StatusBar
from .prompt import PromptInput
from .screens import TuiApprover
from .transcript import Transcript

PANEL_MIN, PANEL_MAX, PANEL_STEP, PANEL_DEFAULT = 20, 100, 6, 40
#: The transcript and prompt never get narrower than this; the panel hides
#: itself first. Below it the widgets would be asked to wrap to nothing.
MAIN_MIN = 24


class Body(Horizontal):
    """The columns. The app itself is not told about terminal resizes, so the
    container that lays the columns out is what refits the panel."""

    def on_resize(self, event: events.Resize) -> None:
        self.app._fit_panel()  # type: ignore[attr-defined]


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
    #main { width: 1fr; min-width: 24; }
    #transcript { height: 1fr; }
    #hint { height: auto; color: $text-muted; padding: 0 2; }
    #hint.empty { display: none; }
    #panel { width: 40; }
    #panel.hidden { display: none; }
    """
    BINDINGS = [
        Binding("escape", "interrupt", "Interrupt", priority=True),
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("ctrl+g", "toggle_panel", "Graph panel", priority=True),
        Binding("ctrl+b", "cycle_view", "Browser view", priority=True),
        Binding("ctrl+left", "panel_wider", "Wider panel", priority=True),
        Binding("ctrl+right", "panel_narrower", "Narrower panel", priority=True),
        Binding("pageup", "page_up", "Scroll up", priority=True),
        Binding("pagedown", "page_down", "Scroll down", priority=True),
        Binding("ctrl+end", "follow", "Jump to end", priority=True),
        Binding("ctrl+o", "expand", "Expand the last tool result", priority=True),
        Binding("ctrl+l", "wipe", "Clear the screen", priority=True),
    ]

    #: What ``/copy`` can be asked for.
    COPY_KINDS = ("last", "tool", "user")

    def __init__(self, config: AppConfig, session: str | None = None) -> None:
        super().__init__()
        self.config = config
        self.initial_session = session
        self.sink = TuiSink(self)
        self.approver = TuiApprover(self)
        self.runner = Runner(config=config, sink=self.sink, approver=self.approver)
        self.runner.on_session = self._session_changed
        self.runner.on_quit = self.exit
        self.runner.surface_commands["panel"] = self._panel_command
        self.runner.surface_commands["copy"] = self._copy_command
        self.runner.surface_commands["expand"] = self._expand_command
        self.runner.surface_commands["wipe"] = self._wipe_command
        self.transcript = Transcript(id="transcript")
        self.panel = GraphPanel(id="panel")
        self.panel_width = PANEL_DEFAULT
        self.panel_wanted = True
        self.divider = Divider(self.resize_panel, id="divider")
        self.status = StatusBar(id="status")
        self.input = PromptInput(self.runner.commands.suggestions(), id="input")
        self.hint = Static("", id="hint", classes="empty")

    def compose(self) -> ComposeResult:
        with Body(id="body"):
            with Vertical(id="main"):
                yield self.transcript
                yield self.hint
                yield self.input
            yield self.divider
            yield self.panel
        yield self.status

    def on_mount(self) -> None:
        self._fit_panel()
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
        self.status.set_settings(self.runner.settings.model, self.runner.settings.effort)

    # --- input ----------------------------------------------------------------------

    def on_prompt_input_submitted(self, event: PromptInput.Submitted) -> None:
        text = event.text.strip()
        if not text:
            return
        self.transcript.user(text, command=parse(text) is not None)
        self.runner.submit(text)

    def on_prompt_input_hint_changed(self, event: PromptInput.HintChanged) -> None:
        self.hint.update("  ".join(event.matches))
        self.hint.set_class(not event.matches, "empty")

    async def action_interrupt(self) -> None:
        """Esc.

        Inside a modal it means *that modal's* escape and never the harness's
        interrupt. The binding is app-level and priority, and Textual checks
        priority bindings from the App down (``textual/app.py:3976``), so a
        screen's own escape binding can never outrank it — the screen has to
        be asked from here instead.
        """
        escape = getattr(self.screen, "escape", None)
        if callable(escape):
            escape()
            return
        await self.runner.interrupt()

    async def action_quit(self) -> None:
        """ctrl+q. Through the runner, so the clients close: Textual's own
        ``action_quit`` exits the app and leaves the CLI processes behind."""
        await self.runner.quit()

    def action_page_up(self) -> None:
        self.transcript.page_up()

    def action_page_down(self) -> None:
        self.transcript.page_down()

    def action_follow(self) -> None:
        self.transcript.follow()

    # --- getting text back out (E55, E62) --------------------------------------

    def action_expand(self) -> None:
        self._expand_command("")

    def action_wipe(self) -> None:
        self._wipe_command("")

    def _wipe_command(self, args: str) -> None:
        """``/wipe`` and ctrl+l — the screen, and only the screen.

        Not ``/clear``: that is the CLI's own command, it is passed through to
        the SDK conversation (``commands.py``), and taking the name would
        silently change what muscle memory does to the conversation.
        """
        self.transcript.clear_transcript()
        self.transcript.apply(ev.Notice(text="transcript cleared — the conversation is untouched (/clear does that)"))

    def _expand_command(self, args: str) -> None:
        """``/expand [n]`` — the nth tool result from the end, in full."""
        arg = args.strip().lower()
        if arg and arg != "last" and not arg.isdigit():
            self.transcript.apply(ev.Notice(text="usage: /expand [n] — n counts back from the last tool result", level="warning"))
            return
        nth = int(arg) if arg.isdigit() else 1
        if not self.transcript.expand_tool(nth):
            self.transcript.apply(ev.Notice(text="no tool result to expand", level="warning"))

    def _copy_command(self, args: str) -> None:
        """``/copy [last|tool|user]`` — the keyboard path to the clipboard.

        Textual copies over OSC 52, which some terminals drop, so this says
        how much it copied: if nothing lands in your clipboard, the terminal
        ate it and the text is still on screen to select by hand (E62).
        """
        kind = args.strip().lower() or "last"
        if kind not in self.COPY_KINDS:
            self.transcript.apply(ev.Notice(text=f"usage: /copy [{'|'.join(self.COPY_KINDS)}]", level="warning"))
            return
        text = self.transcript.last_text(kind)
        if text is None:
            self.transcript.apply(ev.Notice(text=f"nothing to copy: no {kind} in this transcript yet", level="warning"))
            return
        self.copy_to_clipboard(text)
        self.transcript.apply(ev.Notice(text=f"copied {len(text)} characters ({kind})"))

    # --- the graph panel ---------------------------------------------------------------

    @property
    def panel_visible(self) -> bool:
        return not self.panel.has_class("hidden")

    def show_panel(self, visible: bool) -> None:
        self.panel_wanted = visible
        self._fit_panel()

    def resize_panel(self, width: int) -> None:
        self.panel_width = max(PANEL_MIN, min(PANEL_MAX, width))
        self.panel_wanted = True
        self._fit_panel()

    def _fit_panel(self) -> None:
        """Show the panel at the wanted width only where the main column keeps
        its minimum; otherwise hide it until the terminal is wide enough."""
        room = self.size.width - MAIN_MIN - 1  # one column for the divider
        visible = self.panel_wanted and room >= PANEL_MIN
        if visible:
            self.panel.styles.width = min(self.panel_width, room)
        self.panel.set_class(not visible, "hidden")
        self.divider.set_class(not visible, "hidden")

    def action_toggle_panel(self) -> None:
        self.show_panel(not self.panel_visible)

    def action_panel_wider(self) -> None:
        self.resize_panel(self.panel_width + PANEL_STEP)

    def action_panel_narrower(self) -> None:
        self.resize_panel(self.panel_width - PANEL_STEP)

    def action_cycle_view(self) -> None:
        self.show_panel(True)
        self.panel.cycle_view()

    def _panel_command(self, args: str) -> None:
        arg = args.strip().lower()
        if arg in ("", "toggle"):
            self.action_toggle_panel()
        elif arg in ("show", "on"):
            self.show_panel(True)
        elif arg in ("hide", "off", "close"):
            self.show_panel(False)
        elif arg.isdigit():
            self.resize_panel(int(arg))
        elif arg.startswith("view"):
            wanted = arg.removeprefix("view").strip()
            if wanted and self.panel.set_view(wanted):
                self.show_panel(True)
            else:
                self.transcript.apply(ev.Notice(text="usage: /panel view outline|kind|status", level="warning"))
        else:
            self.transcript.apply(ev.Notice(text="usage: /panel [show|hide|<width>|view <outline|kind|status>]", level="warning"))

    def on_graph_panel_node_picked(self, message: GraphPanel.NodePicked) -> None:
        """A node selected in the browser is shown in full in the transcript."""
        self.runner.submit(f"/show node {message.node_id}")

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
