"""The shell — one task that owns the clients and executes what the user typed.

Everything the user types goes onto a queue and is handled here, in order, by
the one task that owns the SDK clients (a client must live in a single async
context). Commands are handled by name; plain text is routed by the session's
focus: the chat driver, or the graph's synthesis conversation. Results reach
the outside only as events, so the runner has no idea what is rendering them.

*"I should be able to exit and enter the graph flow as I wish whilst staying
in the same session or switching sessions."* — ``/graph`` and ``/chat`` move
the focus; ``/resume`` and ``/new`` move between sessions; the clients follow.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Awaitable, Callable

from .chat import ChatDriver
from .commands import Command, CommandSet, parse
from .config import AppConfig, Mode
from .graph import ControlContext
from .graph.graph import sqlite_checkpointer
from .graph_driver import GraphDriver, snapshot
from .harness.events import EventSink, JsonlSink, FanoutSink, Notice, StateSnapshot
from .harness.protocol import Approver
from .harness.sdk import SdkHarness
from .session import SessionRecord, SessionStore

QUIT = object()


class Runner:
    def __init__(
        self,
        *,
        config: AppConfig,
        sink: EventSink,
        approver: Approver,
        harness_factory: Callable[..., Any] | None = None,
        chat_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.config = config
        self.sink = sink
        self.approver = approver
        self.store = SessionStore(config.sessions_dir)
        self.commands = CommandSet(config.modes)
        self.queue: asyncio.Queue[Any] = asyncio.Queue()
        self.session: SessionRecord | None = None
        self.settings = config.settings
        self._harness_factory = harness_factory or self._default_harness
        self._chat_factory = chat_factory or self._default_chat
        self._chats: dict[str, ChatDriver] = {}
        self._graph: GraphDriver | None = None
        self._harness: Any = None
        self._checkpointer: Any = None
        self._session_sink: EventSink = sink
        self._busy = False
        self.on_session: Callable[[SessionRecord | None], None] | None = None
        self.on_quit: Callable[[], Awaitable[None] | None] | None = None

    # --- lifecycle -----------------------------------------------------------

    def submit(self, text: str) -> None:
        self.queue.put_nowait(text)

    async def run(self, initial_session: str | None = None) -> None:
        async with sqlite_checkpointer(self.store.checkpoints) as saver:
            self._checkpointer = saver
            if initial_session and self.store.exists(initial_session):
                await self.open_session(initial_session)
            else:
                record = self.store.create(initial_session, mode=self.config.modes.default)
                await self.open_session(record.name)
            while True:
                item = await self.queue.get()
                if item is QUIT:
                    self.queue.task_done()
                    break
                try:
                    self._busy = True
                    await self.handle(str(item))
                except Exception as exc:  # the shell survives a failed turn; the user sees why
                    self.sink.emit(Notice(text=f"{type(exc).__name__}: {exc}", level="error"))
                finally:
                    self._busy = False
                    self.queue.task_done()
            await self._close_clients()

    async def stop(self) -> None:
        self.queue.put_nowait(QUIT)

    @property
    def busy(self) -> bool:
        return self._busy

    # --- sessions --------------------------------------------------------------

    async def open_session(self, name: str) -> None:
        await self._close_clients()
        record = self.store.load(name)
        self.session = record
        if record.model:
            self.settings = self.settings.with_model(record.model)
        log = JsonlSink(self.store.events_path(name))
        self._session_sink = FanoutSink(self.sink, log)
        self._graph = GraphDriver(
            thread_id=record.thread_id,
            checkpointer=self._checkpointer,
            ctx=ControlContext(harness=self._make_harness(), budgets=self.config.budgets, prices=self.config.prices),
            sink=self._session_sink,
        )
        self.sink.emit(Notice(text=f"session {name} — focus /{record.focus}"))
        if self.on_session:
            self.on_session(record)
        state = await self._graph.state()
        if state is not None:
            self.sink.emit(snapshot(state, self.config.budgets))

    def _make_harness(self) -> Any:
        self._harness = self._harness_factory(self)
        return self._harness

    def _default_harness(self, runner: "Runner") -> SdkHarness:
        graph_mode = self.config.modes.graph
        return SdkHarness(
            sink=self._session_sink,
            approver=self.approver,
            settings=self.settings,
            system_prompt=graph_mode.sdk_system_prompt(self.config.modes.base_dir),
            cwd=self.config.cwd,
            budgets=self.config.budgets,
            prices=dict(self.config.prices),
            extra_env=dict(self.config.extra_env),
        )

    def _default_chat(self, runner: "Runner", mode: Mode, resume: str) -> ChatDriver:
        return ChatDriver(
            mode=mode,
            base_dir=self.config.modes.base_dir,
            settings=self.settings,
            sink=self._session_sink,
            approver=self.approver,
            cwd=self.config.cwd,
            resume=resume,
            extra_env=dict(self.config.extra_env),
        )

    async def _chat(self, mode_name: str) -> ChatDriver:
        assert self.session is not None
        driver = self._chats.get(mode_name)
        if driver is None:
            mode = self.config.modes[mode_name]
            driver = self._chat_factory(self, mode, self.session.conversations.get(mode_name, ""))
            self._chats[mode_name] = driver
        return driver

    async def _close_clients(self) -> None:
        for driver in self._chats.values():
            try:
                await driver.close()
            except Exception:
                pass
        self._chats.clear()
        self._graph = None

    def _save(self) -> None:
        if self.session is not None:
            self.store.save(self.session)
            if self.on_session:
                self.on_session(self.session)

    # --- dispatch ----------------------------------------------------------------

    async def handle(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        command = parse(text)
        if command is None:
            await self._plain(text)
        else:
            await self._command(command)

    async def _plain(self, text: str) -> None:
        assert self.session is not None and self._graph is not None
        if self.session.focus == "graph":
            await self._graph.exchange(text)
            return
        driver = await self._chat(self.session.mode)
        session_id = await driver.send(text)
        if session_id and self.session.conversations.get(self.session.mode) != session_id:
            self.session.conversations[self.session.mode] = session_id
            self._save()

    async def interrupt(self) -> None:
        if self.session is None:
            return
        if self.session.focus == "graph":
            if self._harness is not None:
                await self._harness.interrupt()
        else:
            driver = self._chats.get(self.session.mode)
            if driver is not None:
                await driver.interrupt()

    async def _command(self, cmd: Command) -> None:
        assert self.session is not None
        name = cmd.name
        if self.commands.is_mode(name):
            await self._switch_mode(name, cmd.args)
        elif name == "help":
            self.sink.emit(Notice(text=self.commands.help_text()))
        elif name == "modes":
            lines = [f"/{n} — {self.config.modes[n].kind}: {self.config.modes[n].description}" for n in self.config.modes.names()]
            self.sink.emit(Notice(text="\n".join(lines)))
        elif name == "quit":
            if self.on_quit:
                result = self.on_quit()
                if result is not None:
                    await result
            await self.stop()
        elif name == "interrupt":
            await self.interrupt()
        elif name == "new":
            record = self.store.create(cmd.args or None, mode=self.config.modes.default)
            await self.open_session(record.name)
        elif name == "sessions":
            rows = [
                f"{r.name}  focus=/{r.focus}  mode=/{r.mode}  created={r.created}" + ("  (current)" if self.session and r.name == self.session.name else "")
                for r in self.store.list()
            ]
            self.sink.emit(Notice(text="\n".join(rows) or "no sessions yet"))
        elif name == "resume":
            if not cmd.args:
                self.sink.emit(Notice(text="usage: /resume <name>", level="warning"))
            elif not self.store.exists(cmd.args):
                self.sink.emit(Notice(text=f"no session named {cmd.args!r}", level="warning"))
            else:
                await self.open_session(cmd.args)
        elif name == "fork":
            await self._fork(cmd.args or None)
        elif name == "model":
            await self._set_model(cmd.args)
        elif name == "show":
            await self._show(cmd.args)
        elif self.commands.is_passthrough(name):
            if self.session.focus == "graph":
                self.sink.emit(Notice(text=f"/{name} is a conversation command; leave the graph with /chat first", level="warning"))
            else:
                await self._plain(cmd.raw)
        else:
            self.sink.emit(Notice(text=f"unknown command /{name} — /help lists them", level="warning"))

    async def _switch_mode(self, name: str, args: str) -> None:
        assert self.session is not None and self._graph is not None
        mode = self.config.modes[name]
        if mode.kind == "graph":
            self.session.focus = "graph"
            self._save()
            if args:
                self.sink.emit(Notice(text=f"cycle starting on: {args}"))
                await self._graph.start_cycle(args)
            else:
                state = await self._graph.state()
                if state is None or state.cycle == 0:
                    self.sink.emit(Notice(text="in the graph. Start a cycle with /graph <query>."))
                else:
                    self.sink.emit(Notice(text=f"in the graph at cycle {state.cycle}, {state.stage}. Plain text continues the conversation."))
            return
        self.session.focus = name
        self.session.mode = name
        self._save()
        self.sink.emit(Notice(text=f"focus /{name}" + (f" — {mode.description}" if mode.description else "")))
        if args:
            await self._plain(args)

    async def _set_model(self, model: str) -> None:
        assert self.session is not None
        if not model:
            self.sink.emit(Notice(text=f"model: {self.settings.model}"))
            return
        self.settings = self.settings.with_model(model)
        self.session.model = model
        self._save()
        for driver in self._chats.values():
            await driver.set_model(model)
        if self._harness is not None and hasattr(self._harness, "settings"):
            self._harness.settings = self.settings
        self.sink.emit(Notice(text=f"model set to {model} for new turns"))

    async def _show(self, what: str) -> None:
        assert self._graph is not None
        state = await self._graph.state()
        if state is None:
            self.sink.emit(Notice(text="the graph is empty"))
            return
        what = (what or "graph").strip().lower()
        if what == "package":
            self.sink.emit(Notice(text=(await self._graph.package_text()) or "(empty package)"))
        elif what == "state":
            self.sink.emit(Notice(text=state.model_dump_json(indent=1)[:6000]))
        elif what == "budget":
            snap = snapshot(state, self.config.budgets)
            self.sink.emit(Notice(text="\n".join(f"{p}: {s} of {c}" for p, s, c in snap.pools) or "no pools yet"))
        else:
            snap = snapshot(state, self.config.budgets)
            self.sink.emit(snap)
            self.sink.emit(Notice(text="\n".join("  " * d + label for d, _, label in snap.outline) or "(no nodes)"))

    async def _fork(self, name: str | None) -> None:
        assert self.session is not None and self._graph is not None
        source = self.session
        state = await self._graph.state()
        record = self.store.create(name, mode=source.mode)
        record.focus = source.focus
        record.conversations = dict(source.conversations)
        record.model = source.model
        record.forked_from = source.name
        self.store.save(record)
        if state is not None:
            target = GraphDriver(
                thread_id=record.thread_id,
                checkpointer=self._checkpointer,
                ctx=self._graph.ctx,
                sink=self._session_sink,
            )
            values = state.model_dump()
            values["fork_conversation"] = bool(state.conversation)
            await target.seed(values, as_node=state.stage)
        await self.open_session(record.name)
        self.sink.emit(Notice(text=f"forked {source.name} into {record.name}"))
