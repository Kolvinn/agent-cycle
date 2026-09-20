"""The shell, headless: commands, focus, sessions and forks, with the model
scripted and the chat faked."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from langchain_claude_test.app.config import AppConfig, builtin_modes
from langchain_claude_test.app.harness import events as ev
from langchain_claude_test.app.harness.events import ListSink, TextDone
from langchain_claude_test.app.harness.scripted import ScriptedApprover, ScriptedHarness, Turn
from langchain_claude_test.app.runner import Runner

from .test_cycle import QUESTION, script

PKG = Path(__file__).resolve().parents[2] / "src" / "langchain_claude_test" / "app"


class FakeChat:
    """Stands in for the SDK conversation: records what it was sent."""

    instances: list["FakeChat"] = []

    def __init__(self, runner, mode, resume):
        self.mode = mode
        self.resume = resume
        self.sent: list[str] = []
        self.sink = runner._session_sink
        self.closed = False
        self.session_id = resume or f"chat-{mode.name}-{len(FakeChat.instances) + 1}"
        FakeChat.instances.append(self)

    async def send(self, text: str) -> str:
        self.sent.append(text)
        self.sink.emit(TextDone(f"[{self.mode.name}] echo: {text}"))
        return self.session_id

    async def interrupt(self) -> None:
        pass

    async def set_model(self, model: str) -> None:
        self.model = model

    async def set_effort(self, effort: str) -> None:
        self.effort = effort
        self.closed = True  # the real driver drops its client and resumes on the next send

    async def catalog(self):
        from langchain_claude_test.app.config import ModelChoice

        return [
            ModelChoice("default", "Default (recommended)", "Opus 5", "claude-opus-5[1m]", ("low", "medium", "high", "xhigh", "max")),
            ModelChoice("haiku", "Haiku", "Haiku 4.5", "claude-haiku-4-5-20251001", ()),
        ]

    async def close(self) -> None:
        self.closed = True


def make_runner(tmp_path: Path, harness: ScriptedHarness) -> tuple[Runner, ListSink]:
    sink = ListSink()
    config = AppConfig(cwd=tmp_path, sessions_dir=tmp_path / "sessions", modes=builtin_modes(PKG))
    runner = Runner(
        config=config,
        sink=sink,
        approver=harness.approver,
        harness_factory=lambda r: harness,
        chat_factory=FakeChat,
    )
    harness.sink = sink
    return runner, sink


async def drive(runner: Runner, *lines: str) -> None:
    for line in lines:
        runner.submit(line)
    await runner.idle()


def notices(sink: ListSink) -> list[str]:
    return [e.text for e in sink.events if isinstance(e, ev.Notice)]


@pytest.mark.asyncio
async def test_focus_routes_plain_text_and_the_graph_runs_a_cycle(tmp_path: Path):
    FakeChat.instances.clear()
    harness = ScriptedHarness(script=script(), approver=ScriptedApprover())
    runner, sink = make_runner(tmp_path, harness)
    task = asyncio.create_task(runner.run("work"))
    try:
        await drive(runner, "hello there")
        assert FakeChat.instances[0].sent == ["hello there"]
        assert runner.session is not None and runner.session.conversations == {"chat": "chat-chat-1"}

        await drive(runner, "/graph")
        assert runner.session.focus == "graph"
        await drive(runner, "in the graph but no cycle")
        assert any("no conversation is open" in n for n in notices(sink))

        await drive(runner, f"/graph {QUESTION}")
        stages = [e.stage for e in sink.events if isinstance(e, ev.StageFinished)]
        assert stages == ["orientate", "antithesis", "synthesis"]
        snap = [e for e in sink.events if isinstance(e, ev.StateSnapshot)][-1]
        assert snap.cycle == 1 and snap.stage == "synthesis"
        assert any(pool == "orientation:1" and spent == 5 and cap == 20 for pool, spent, cap in snap.pools)

        harness.queue("synthesis", Turn(payload={"text": "reply handled"}))
        await drive(runner, "tell me more")
        assert harness.requests[-1].stage == "synthesis" and harness.requests[-1].message == "tell me more"

        await drive(runner, "/chat", "back in chat")
        assert runner.session.focus == "chat"
        assert FakeChat.instances[0].sent[-1] == "back in chat"

        await drive(runner, "/compact")
        assert FakeChat.instances[0].sent[-1] == "/compact"
        await drive(runner, "/graph", "/compact")
        assert any("leave the graph" in n for n in notices(sink))

        await drive(runner, "/show budget")
        assert any("orientation:1: 5 of 20" in n for n in notices(sink))
        await drive(runner, "/nonsense")
        assert any("unknown command /nonsense" in n for n in notices(sink))
    finally:
        await runner.stop()
        await task
    assert FakeChat.instances[0].closed


@pytest.mark.asyncio
async def test_sessions_fork_and_resume_carry_the_graph(tmp_path: Path):
    FakeChat.instances.clear()
    harness = ScriptedHarness(script=script(), approver=ScriptedApprover())
    runner, sink = make_runner(tmp_path, harness)
    task = asyncio.create_task(runner.run("one"))
    try:
        await drive(runner, f"/graph {QUESTION}")
        await drive(runner, "/fork two")
        assert runner.session is not None and runner.session.name == "two"
        assert runner.session.forked_from == "one" and runner.session.focus == "graph"
        state = await runner._graph.state()
        assert state is not None and state.cycle == 1 and state.fork_conversation is True
        # the fork shares the project's graph: same log, same cycle, same ids
        ledger = runner.graph_store.ledger()
        assert list(ledger.assumptions) == ["a1.1", "a1.2"] and ledger.cycles[1].session == "one"
        assert (tmp_path / "sessions" / "graph" / "ops.jsonl").exists()

        # the reads the agent has, from the prompt
        await drive(runner, "/show package", "/show node a1.1", "/show search webhook signature", "/show neighbours a1.1 1", "/show node nope")
        shown = notices(sink)
        assert any("ASSUMPTIONS MADE SO FAR" in n and "[f1.1]" in n for n in shown)
        assert any(n.startswith("assumption a1.1:") and "→ cites f1.1" in n for n in shown)
        assert any("[q1] question:" in n and "match)" in n for n in shown)
        assert any("within 1 hop(s):" in n and "[q1]" in n for n in shown)
        assert any("'nope' is not a node" in n for n in shown)

        # the fork's next exchange forks the SDK conversation; the original does not
        harness.queue("synthesis", Turn(payload={"text": "in the fork"}))
        await drive(runner, "go on")
        assert harness.requests[-1].fork is True
        await drive(runner, "/resume one")
        assert runner.session.name == "one"
        harness.queue("synthesis", Turn(payload={"text": "in the original"}))
        await drive(runner, "go on")
        assert harness.requests[-1].fork is False and harness.requests[-1].conversation == "scripted-1"

        await drive(runner, "/sessions")
        listing = notices(sink)[-1]
        assert "one" in listing and "two" in listing and "(current)" in listing
        await drive(runner, "/new three")
        assert runner.session.name == "three" and runner.session.focus == "chat"
    finally:
        await runner.stop()
        await task


@pytest.mark.asyncio
async def test_model_and_effort_pickers_offer_the_cli_list_and_persist(tmp_path: Path):
    FakeChat.instances.clear()
    harness = ScriptedHarness(script=script(), approver=ScriptedApprover())
    runner, sink = make_runner(tmp_path, harness)
    approver = harness.approver
    approver.choices.extend(["haiku", None, "high"])
    task = asyncio.create_task(runner.run("pick"))
    try:
        await drive(runner, "/model")  # scripted pick: haiku, from the fake CLI's list
        assert approver.offered[0][0] == "Model"
        assert [v for v, _ in approver.offered[0][1]] == ["default", "haiku"]
        assert runner.settings.model == "haiku"
        assert runner.store.load("pick").model == "haiku"
        assert any("takes no effort level" in n for n in notices(sink))

        await drive(runner, "/model")  # scripted: leave as is
        assert runner.settings.model == "haiku"

        await drive(runner, "/model default", "/effort")  # scripted pick: high
        assert approver.offered[2][0] == "Effort"
        assert [v for v, _ in approver.offered[2][1]] == ["low", "medium", "high", "xhigh", "max"]
        assert runner.settings.effort == "high"
        assert runner.settings.sdk_model is None
        assert FakeChat.instances[0].effort == "high" and FakeChat.instances[0].closed

        await drive(runner, "/effort silly")
        assert runner.settings.effort == "high"
        assert any("effort must be one of" in n for n in notices(sink))

        await drive(runner, "/new other")
        assert runner.settings.effort == "medium" and runner.settings.model == "sonnet"
        await drive(runner, "/resume pick")
        assert runner.settings.effort == "high" and runner.settings.model == "default"
        await drive(runner, "/fork picked")
        assert runner.store.load("picked").effort == "high"
    finally:
        await runner.stop()
        await task


@pytest.mark.asyncio
async def test_budget_and_prices_are_set_from_the_prompt_and_persist(tmp_path: Path):
    FakeChat.instances.clear()
    harness = ScriptedHarness(script=script(), approver=ScriptedApprover())
    runner, sink = make_runner(tmp_path, harness)
    task = asyncio.create_task(runner.run("caps"))
    try:
        await drive(runner, "/budget")
        assert any("per_assumption = 5" in n and "orientation_base = 5" in n for n in notices(sink))
        await drive(runner, "/budget per_assumption 2", "/budget max_assumptions 0", "/budget nonsense 3", "/prices read 4")
        assert runner.budgets.per_assumption == 2 and runner.budgets.max_assumptions == 3
        assert runner.prices["read"] == 4
        assert any("cannot be 0" in n for n in notices(sink)) and any("usage: /budget" in n for n in notices(sink))
        record = runner.store.load("caps")
        assert record.budgets == {"per_assumption": 2} and record.prices == {"read": 4}
        assert runner._graph is not None and runner._graph.ctx.budgets.per_assumption == 2
        assert harness.budgets.per_assumption == 2 and harness.prices["read"] == 4

        # the next cycle opens its pool at the new size: 5 + 2·3 = 11, and reads cost 4
        await drive(runner, f"/graph {QUESTION}")
        snap = [e for e in sink.events if isinstance(e, ev.StateSnapshot)][-1]
        assert any(pool == "orientation:1" and cap == 11 for pool, _, cap in snap.pools)
        assert any(isinstance(e, ev.Priced) and e.name == "Read" and e.price == 4 for e in sink.events)

        await drive(runner, "/new fresh")
        assert runner.budgets.per_assumption == 5 and runner.prices["read"] == 2
        await drive(runner, "/resume caps")
        assert runner.budgets.per_assumption == 2 and runner.prices["read"] == 4
        await drive(runner, "/budget reset", "/prices reset")
        assert runner.budgets == runner.config.budgets and runner.prices == dict(runner.config.prices)
    finally:
        await runner.stop()
        await task


@pytest.mark.asyncio
async def test_graph_alone_resumes_an_interrupted_cycle(tmp_path: Path):
    from langchain_claude_test.app.harness.scripted import Turn

    FakeChat.instances.clear()
    s = script()
    s["antithesis"] = [Turn(payload=None, interrupt=True)]
    harness = ScriptedHarness(script=s, approver=ScriptedApprover())
    runner, sink = make_runner(tmp_path, harness)
    task = asyncio.create_task(runner.run("stopped"))
    try:
        await drive(runner, f"/graph {QUESTION}")
        assert any("interrupted" in n for n in notices(sink))
        assert await runner._graph.pending() == ("antithesis",)
        harness.queue("antithesis", script()["antithesis"][0])
        harness.queue("synthesis", script()["synthesis"][0])
        await drive(runner, "/budget antithesis_base 9", "/graph")
        assert any("resuming the cycle at antithesis" in n for n in notices(sink))
        state = await runner._graph.state()
        assert state is not None and state.stage == "synthesis" and state.cycle == 1
        assert harness.requests[-2].pools == {"antithesis:1": 11}
        assert await runner._graph.pending() == ()
    finally:
        await runner.stop()
        await task


@pytest.mark.asyncio
async def test_the_session_log_holds_result_events_only(tmp_path: Path):
    """E64: "you should have the logs output individual stream tokens though,
    that's too much, just result messages." JsonlSink wrote every event it was
    handed, deltas included (O-U12)."""
    import json
    from typing import get_args

    # every event type is classified, so adding one fails here rather than
    # being silently written or silently dropped
    assert set(get_args(ev.HarnessEvent)) == set(ev.RESULT_EVENTS) | set(ev.NOT_LOGGED)
    assert not set(ev.RESULT_EVENTS) & set(ev.NOT_LOGGED)

    FakeChat.instances.clear()
    harness = ScriptedHarness(script=script(), approver=ScriptedApprover())
    runner, sink = make_runner(tmp_path, harness)
    task = asyncio.create_task(runner.run("logged"))
    try:
        await drive(runner, "/help")  # the session -- and its log -- is open by now
        harness.sink = runner._session_sink
        await drive(runner, f"/graph {QUESTION}")
        log = runner._session_sink
        log.emit(ev.TextDelta(text="tok"))
        log.emit(ev.ThinkingDelta(text="tok"))
        log.emit(ev.ToolInputDelta(tool_use_id="t1", partial_json="{"))
        log.emit(ev.ToolStarted(tool_use_id="t1", name="Read"))
        log.emit(ev.ResultText(text="the CLI's own copy"))
        log.emit(ev.TextDone(text="the answer"))

        lines = [json.loads(line) for line in runner.store.events_path("logged").read_text().splitlines()]
    finally:
        await runner.stop()
        await task

    kinds = {line["event"] for line in lines}
    assert kinds and not kinds & {t.__name__ for t in ev.NOT_LOGGED}
    assert kinds <= {t.__name__ for t in ev.RESULT_EVENTS}
    # the cycle's own record is all there
    assert {"TurnStarted", "TurnFinished", "ToolCalled", "ToolResult", "Priced", "StageFinished"} <= kinds
    assert any(line["event"] == "TextDone" and line["text"] == "the answer" for line in lines)


@pytest.mark.asyncio
async def test_read_only_commands_answer_while_a_turn_is_in_flight(tmp_path: Path):
    """E58: "it needs to be smooth and versitile enought to not interrupt
    workflwo." O-U6: every / command sat in the one FIFO queue behind whatever
    turn was running, so looking at the graph meant waiting for the model."""
    gate = asyncio.Event()

    class BlockingChat(FakeChat):
        async def send(self, text: str) -> str:
            await gate.wait()
            return await FakeChat.send(self, text)

    FakeChat.instances.clear()
    harness = ScriptedHarness(script=script(), approver=ScriptedApprover())
    sink = ListSink()
    config = AppConfig(cwd=tmp_path, sessions_dir=tmp_path / "sessions", modes=builtin_modes(PKG))
    runner = Runner(
        config=config,
        sink=sink,
        approver=harness.approver,
        harness_factory=lambda r: harness,
        chat_factory=BlockingChat,
    )
    harness.sink = sink
    task = asyncio.create_task(runner.run("fast"))
    try:
        await runner._session_ready.wait()
        runner.submit("a message that blocks")
        await asyncio.sleep(0.05)
        assert runner.busy and not sink.of(TextDone)

        for line in ("/help", "/sessions", "/budget", "/prices"):
            runner.submit(line)
        await runner.fast_queue.join()
        answered = notices(sink)
        assert any("Built-ins" in n for n in answered)
        assert any("focus=/chat" in n for n in answered)
        assert any("the cycle's caps" in n for n in answered)
        assert any("what a call costs" in n for n in answered)

        # the turn is still where it was: read-only means read-only
        assert runner.busy and not sink.of(TextDone)
        assert runner.queue.qsize() == 0  # and it did not queue behind it

        # a command that writes keeps its place in the one queue
        runner.submit("/budget antithesis_base 9")
        await asyncio.sleep(0.05)
        assert runner.budgets.antithesis_base != 9

        gate.set()
        await runner.idle()
        assert runner.budgets.antithesis_base == 9
        assert FakeChat.instances[0].sent == ["a message that blocks"]
        # and the model's reply landed after the read-only answers
        texts = [i for i, e in enumerate(sink.events) if isinstance(e, TextDone)]
        helps = [i for i, e in enumerate(sink.events) if isinstance(e, ev.Notice) and "Built-ins" in e.text]
        assert helps and texts and helps[0] < texts[0]
    finally:
        gate.set()
        await runner.stop()
        await task
