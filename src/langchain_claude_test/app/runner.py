"""The shell — one task that owns the clients and executes what the user typed.

Everything the user types goes onto a queue and is handled here, in order, by
the one task that owns the SDK clients (a client must live in a single async
context). Commands are handled by name; plain text is routed by the session's
focus: the chat driver, or the graph's synthesis conversation. Results reach
the outside only as events, so the runner has no idea what is rendering them.

*"I should be able to exit and enter the graph flow as I wish whilst staying
in the same session or switching sessions."* — ``/graph`` and ``/chat`` move
the focus; ``/resume`` and ``/new`` move between sessions; the clients follow.

There is a **second lane** for the commands that answer out of what the shell
already holds (``commands.READ_ONLY``): ``/show``, ``/help``, ``/sessions``
and their kind run on their own task so that looking at something does not
wait behind a model turn. Nothing on that lane opens a client, runs a turn or
writes a session record, and the model-turn queue is untouched by it.
"""

from __future__ import annotations

import asyncio
from dataclasses import fields, replace
from typing import Any, Awaitable, Callable

from .chat import ChatDriver
from .commands import Command, CommandSet, is_read_only, parse
from .config import EFFORT_DESCRIPTIONS, EFFORT_LEVELS, FALLBACK_MODELS, PROVISIONAL, AppConfig, Budgets, Mode, ModelChoice
from .graph import ControlContext
from .graph.graph import sqlite_checkpointer
from .graph import package
from .graph.store import GraphStore
from .graph_driver import GraphDriver
from .harness.events import EventSink, JsonlSink, FanoutSink, Notice
from .harness.protocol import Approver
from .harness.sdk import SdkHarness
from .session import SessionRecord, SessionStore

QUIT = object()

_BUDGET_FIELDS: tuple[str, ...] = tuple(f.name for f in fields(Budgets))


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
        #: The project's graph, shared by every session: one op log.
        self.graph_store = GraphStore(self.store.graph_log)
        self.commands = CommandSet(config.modes)
        self.queue: asyncio.Queue[Any] = asyncio.Queue()
        #: The read-only lane: ``/show``, ``/help``, ``/sessions`` and the rest
        #: of :data:`commands.READ_ONLY`, drained by their own task so they
        #: answer while a turn is in flight. Nothing on this lane opens a
        #: client, runs a model turn or writes a session record.
        self.fast_queue: asyncio.Queue[Any] = asyncio.Queue()
        #: Held closed while a session is being swapped, so the read-only lane
        #: never reads a half-open session.
        self._session_ready = asyncio.Event()
        self.session: SessionRecord | None = None
        self.settings = config.settings
        self.budgets: Budgets = config.budgets
        self.prices: dict[str, int] = dict(config.prices)
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
        #: Handled by the shell's surface (the TUI), not here: command name -> handler.
        self.surface_commands: dict[str, Callable[[str], Awaitable[None] | None]] = {}
        self._catalog: list[ModelChoice] = []

    # --- lifecycle -----------------------------------------------------------

    def submit(self, text: str) -> None:
        """Route what was typed. A read-only command takes the second lane;
        everything else keeps its place in the one queue, in order, on the one
        task that owns the SDK clients."""
        command = parse(text)
        if command is not None and is_read_only(command):
            self.fast_queue.put_nowait(text)
        else:
            self.queue.put_nowait(text)

    async def run(self, initial_session: str | None = None) -> None:
        async with sqlite_checkpointer(self.store.checkpoints) as saver:
            self._checkpointer = saver
            await self._open_initial(initial_session)
            fast = asyncio.create_task(self._read_only_lane())
            try:
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
            finally:
                fast.cancel()
            await self._close_clients()

    async def _open_initial(self, initial_session: str | None) -> None:
        """A name opens it, or creates it. **No name reopens the last session**
        rather than starting a blank one — as ``claude --continue`` does.
        ``/new`` is how a fresh one is asked for."""
        if initial_session:
            if not self.store.exists(initial_session):
                self.store.create(initial_session, mode=self.config.modes.default)
            await self.open_session(initial_session)
            return
        last = self.store.latest()
        if last is None:
            last = self.store.create(None, mode=self.config.modes.default).name
        else:
            self.sink.emit(Notice(text=f"reopening {last}, the session last worked in — /new starts a fresh one"))
        await self.open_session(last)

    async def _read_only_lane(self) -> None:
        """The second lane. In order among themselves, and never in the way."""
        while True:
            item = await self.fast_queue.get()
            try:
                await self._session_ready.wait()
                await self.handle(str(item))
            except Exception as exc:
                self.sink.emit(Notice(text=f"{type(exc).__name__}: {exc}", level="error"))
            finally:
                self.fast_queue.task_done()

    async def idle(self) -> None:
        """Both lanes drained — what a test waits on instead of one queue."""
        await self.queue.join()
        await self.fast_queue.join()

    async def stop(self) -> None:
        self.queue.put_nowait(QUIT)

    async def quit(self) -> None:
        """The one way out — ``/quit`` and ctrl+q both come here.

        The clients close **first**. ``on_quit`` is the app's ``exit``, and
        this task does not survive the app's unwind, so a QUIT left on the
        queue to do the closing might never be read and the CLI processes
        would be left behind.
        """
        await self._close_clients()
        await self.stop()
        if self.on_quit:
            result = self.on_quit()
            if result is not None:
                await result

    @property
    def busy(self) -> bool:
        return self._busy

    # --- sessions --------------------------------------------------------------

    async def open_session(self, name: str) -> None:
        self._session_ready.clear()  # the read-only lane waits out the swap
        await self._close_clients()
        record = self.store.load(name)
        self.session = record
        self.settings = self.config.settings
        if record.model:
            self.settings = self.settings.with_model(record.model)
        if record.effort:
            self.settings = self.settings.with_effort(record.effort)
        self.budgets = self.config.budgets.with_(**{k: v for k, v in record.budgets.items() if k in _BUDGET_FIELDS})
        self.prices = {**dict(self.config.prices), **record.prices}
        log = JsonlSink(self.store.events_path(name))
        self._session_sink = FanoutSink(self.sink, log)
        self._graph = GraphDriver(
            thread_id=record.thread_id,
            checkpointer=self._checkpointer,
            ctx=ControlContext(
                harness=self._make_harness(),
                budgets=self.budgets,
                prices=self.prices,
                store=self.graph_store,
                session=record.thread_id,
            ),
            sink=self._session_sink,
        )
        self._session_ready.set()
        self.sink.emit(Notice(text=f"session {name} — focus /{record.focus}"))
        if self.on_session:
            self.on_session(record)
        state = await self._graph.state()
        if state is not None:
            self.sink.emit(self._graph.snapshot(state))

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
            budgets=self.budgets,
            prices=dict(self.prices),
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
            await self.quit()
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
        elif name == "effort":
            await self._set_effort(cmd.args)
        elif name == "budget":
            await self._set_budget(cmd.args)
        elif name == "prices":
            await self._set_price(cmd.args)
        elif name in self.surface_commands:
            result = self.surface_commands[name](cmd.args)
            if result is not None:
                await result
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
            owed = await self._graph.pending()
            if args:
                if owed:
                    self.sink.emit(Notice(text=f"abandoning the unfinished cycle at {', '.join(owed)}; a new one starts on: {args}", level="warning"))
                else:
                    self.sink.emit(Notice(text=f"cycle starting on: {args}"))
                await self._graph.start_cycle(args)
            elif owed:
                self.sink.emit(Notice(text=f"resuming the cycle at {', '.join(owed)} with the current caps and prices"))
                await self._graph.resume()
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

    # --- model and effort ------------------------------------------------------

    async def catalog(self) -> list[ModelChoice]:
        """The CLI's own model list, learned once from the default connection."""
        if not self._catalog and self.session is not None:
            try:
                driver = await self._chat(self.session.mode)
                self._catalog = list(await driver.catalog())
            except Exception as exc:
                self.sink.emit(Notice(text=f"could not list models from the CLI ({exc}); using the last known list", level="warning"))
        return self._catalog or list(FALLBACK_MODELS)

    def _choice(self, model: str) -> ModelChoice | None:
        for c in self._catalog or FALLBACK_MODELS:
            if model in (c.value, c.resolved):
                return c
        return None

    async def _set_model(self, model: str) -> None:
        assert self.session is not None
        if not model:
            options = [(c.value, f"{c.display} — {c.description}" if c.description else c.display) for c in await self.catalog()]
            picked = await self.approver.choose("Model", options, current=self.settings.model)
            if not picked:
                self.sink.emit(Notice(text=f"model: {self.settings.model}  effort: {self.settings.effort}"))
                return
            model = picked
        self.settings = self.settings.with_model(model)
        self.session.model = model
        self._save()
        for driver in self._chats.values():
            await driver.set_model(model)
        self._push_settings()
        choice = self._choice(model)
        if choice is not None and choice.efforts and self.settings.effort not in choice.efforts:
            self.sink.emit(Notice(text=f"{choice.display} accepts effort {', '.join(choice.efforts)}; current is {self.settings.effort}", level="warning"))
        elif choice is not None and not choice.efforts and self._catalog:
            self.sink.emit(Notice(text=f"{choice.display} takes no effort level; /effort has no effect on it", level="warning"))
        self.sink.emit(Notice(text=f"model set to {model} for new turns"))

    async def _set_effort(self, level: str) -> None:
        assert self.session is not None
        choice = self._choice(self.settings.model)
        levels = tuple(choice.efforts) if choice is not None and choice.efforts else EFFORT_LEVELS
        if not level:
            options = [(lvl, f"{lvl} — {EFFORT_DESCRIPTIONS.get(lvl, '')}") for lvl in levels]
            picked = await self.approver.choose("Effort", options, current=self.settings.effort)
            if not picked:
                self.sink.emit(Notice(text=f"effort: {self.settings.effort}"))
                return
            level = picked
        level = level.strip().lower()
        if level not in EFFORT_LEVELS:
            self.sink.emit(Notice(text=f"effort must be one of {', '.join(EFFORT_LEVELS)}", level="warning"))
            return
        if level not in levels:
            self.sink.emit(Notice(text=f"{self.settings.model} accepts {', '.join(levels)}; setting {level} anyway", level="warning"))
        self.settings = self.settings.with_effort(level)
        self.session.effort = level
        self._save()
        for driver in self._chats.values():
            await driver.set_effort(level)
        self._push_settings()
        self.sink.emit(Notice(text=f"effort set to {level} for new turns"))

    def _push_settings(self) -> None:
        if self._harness is not None and hasattr(self._harness, "settings"):
            self._harness.settings = self.settings

    # --- the cycle's numbers -----------------------------------------------

    def _budget_lines(self) -> str:
        defaults = self.config.budgets
        rows = []
        for f in fields(Budgets):
            value = getattr(self.budgets, f.name)
            default = getattr(defaults, f.name)
            note = "  (provisional)" if f.name in PROVISIONAL else ""
            changed = f"  [default {default}]" if value != default else ""
            rows.append(f"  {f.name} = {value}{changed}{note}")
        return "\n".join(rows)

    async def _set_budget(self, args: str) -> None:
        assert self.session is not None
        parts = args.split()
        if not parts:
            self.sink.emit(Notice(text="the cycle's caps (/budget <field> <n> sets one, /budget reset restores the defaults):\n" + self._budget_lines()))
            return
        if parts[0] == "reset":
            self.session.budgets = {}
            self.budgets = self.config.budgets
        else:
            if len(parts) != 2 or parts[0] not in _BUDGET_FIELDS or not parts[1].lstrip("-").isdigit():
                self.sink.emit(Notice(text=f"usage: /budget <field> <n>, where field is one of {', '.join(_BUDGET_FIELDS)}", level="warning"))
                return
            value = int(parts[1])
            if value < 0 or (parts[0] in ("max_assumptions",) and value < 1):
                self.sink.emit(Notice(text=f"{parts[0]} cannot be {value}", level="warning"))
                return
            self.session.budgets[parts[0]] = value
            self.budgets = self.budgets.with_(**{parts[0]: value})
        self._save()
        await self._push_numbers()
        self.sink.emit(Notice(text="caps for the next frame:\n" + self._budget_lines()))

    async def _set_price(self, args: str) -> None:
        assert self.session is not None
        parts = args.split()
        if not parts:
            lines = [f"  {k} = {v}" + (f"  [default {self.config.prices.get(k)}]" if self.config.prices.get(k) != v else "") for k, v in sorted(self.prices.items())]
            self.sink.emit(Notice(text="what a call costs, by class (/prices <class> <n> sets one, /prices reset restores):\n" + "\n".join(lines)))
            return
        if parts[0] == "reset":
            self.session.prices = {}
            self.prices = dict(self.config.prices)
        else:
            if len(parts) != 2 or parts[0] not in self.config.prices or not parts[1].isdigit():
                self.sink.emit(Notice(text=f"usage: /prices <class> <n>, where class is one of {', '.join(sorted(self.config.prices))}", level="warning"))
                return
            self.session.prices[parts[0]] = int(parts[1])
            self.prices[parts[0]] = int(parts[1])
        self._save()
        await self._push_numbers()
        self.sink.emit(Notice(text="prices for the next frame: " + ", ".join(f"{k} {v}" for k, v in sorted(self.prices.items()))))

    async def _push_numbers(self) -> None:
        """The graph and the harness read the new numbers from the next frame on;
        a frame in flight keeps the pool it opened with."""
        if self._graph is not None:
            self._graph.ctx = replace(self._graph.ctx, budgets=self.budgets, prices=self.prices)
            state = await self._graph.state()
            if state is not None:
                self.sink.emit(self._graph.snapshot(state))
        if self._harness is not None:
            if hasattr(self._harness, "budgets"):
                self._harness.budgets = self.budgets
            if hasattr(self._harness, "prices"):
                self._harness.prices = dict(self.prices)

    async def _show(self, what: str) -> None:
        assert self._graph is not None
        state = await self._graph.state()
        if state is None:
            self.sink.emit(Notice(text="the graph is empty"))
            return
        what, _, rest = (what or "graph").strip().partition(" ")
        what, rest = what.lower(), rest.strip()
        view = self._graph.ctx.store.view()
        if what == "package":
            self.sink.emit(Notice(text=self._graph.package_text(state) or "(empty package)"))
        elif what == "node":
            self.sink.emit(Notice(text=package.describe_node(view, rest) if rest else "/show node <id>"))
        elif what == "neighbours":
            nid, _, depth = rest.partition(" ")
            hops = int(depth) if depth.strip().isdigit() else 1
            self.sink.emit(Notice(text=package.describe_neighbours(view, nid, hops) if nid else "/show neighbours <id> [depth]"))
        elif what == "search":
            self.sink.emit(Notice(text=package.describe_search(view, rest) if rest else "/show search <text>"))
        elif what == "state":
            self.sink.emit(Notice(text=state.model_dump_json(indent=1)[:6000]))
        elif what == "budget":
            snap = self._graph.snapshot(state)
            self.sink.emit(Notice(text="\n".join(f"{p}: {s} of {c}" for p, s, c in snap.pools) or "no pools yet"))
        else:
            snap = self._graph.snapshot(state)
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
        record.effort = source.effort
        record.budgets = dict(source.budgets)
        record.prices = dict(source.prices)
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
