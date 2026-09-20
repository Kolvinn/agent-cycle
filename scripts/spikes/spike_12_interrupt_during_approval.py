"""Spike 12 — interrupt while an approval is open, then resume (audit A9, F5, F6).

Resumes the Cycle 1 session from a *copy* of its state, sends a synthesis reply
that provokes a gated call, blocks the approver, and calls ``interrupt()`` while
the approval is pending. Measures what ends, what is orphaned, what the graph
owes, and whether the conversation resumes afterwards.

    .venv/bin/python scripts/spikes/spike_12_interrupt_during_approval.py <sessions_dir_copy>
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from langchain_claude_test.app.config import TEST_MODEL, AppConfig, ModelSettings, builtin_modes  # noqa: E402
from langchain_claude_test.app.harness import events as ev  # noqa: E402
from langchain_claude_test.app.harness.console import ConsoleSink  # noqa: E402
from langchain_claude_test.app.harness.events import FanoutSink, ListSink  # noqa: E402
from langchain_claude_test.app.harness.protocol import ApprovalRequest, Verdict  # noqa: E402
from langchain_claude_test.app.runner import Runner  # noqa: E402

REPLY = (
    "Register this sentence as a fact: 'The meter charges a call before it runs, inside the PreToolUse hook.' "
    "Then close whichever open rival it settles."
)
AFTER = "In one sentence, what stands on the graph now? Do not call any tool."


class BlockingApprover:
    """Records the ask, then waits until the spike releases it — or is cancelled."""

    def __init__(self) -> None:
        self.asked = asyncio.Event()
        self.release: asyncio.Future[Verdict] | None = None
        self.requests: list[ApprovalRequest] = []
        self.outcome = "never asked"

    async def approve(self, request: ApprovalRequest) -> Verdict:
        self.requests.append(request)
        self.release = asyncio.get_running_loop().create_future()
        self.asked.set()
        try:
            verdict = await self.release
        except asyncio.CancelledError:
            self.outcome = "cancelled"
            raise
        self.outcome = "answered"
        return verdict

    async def ask(self, questions):
        raise AssertionError("ask not expected")

    async def choose(self, title, options, current=""):
        return None


async def main(sessions_dir: Path) -> int:
    recorded = ListSink()
    sink = FanoutSink(ConsoleSink(deltas=False), recorded)
    approver = BlockingApprover()
    config = AppConfig(
        cwd=ROOT,
        sessions_dir=sessions_dir,
        modes=builtin_modes(ROOT / "src" / "langchain_claude_test" / "app"),
        settings=ModelSettings(model=TEST_MODEL),
    )
    runner = Runner(config=config, sink=sink, approver=approver)
    task = asyncio.create_task(runner.run("audit11"))
    while runner.session is None:
        await asyncio.sleep(0.1)
    before = runner.graph_store.ledger()
    print(f"[spike] resumed session {runner.session.name} focus={runner.session.focus}; ledger {before.lines} lines, "
          f"{len(before.proposed)} proposals, {len(before.decisions)} decisions, {len(before.explicits)} facts")
    state0 = await runner._graph.state()
    print(f"[spike] thread stands at cycle={state0.cycle} stage={state0.stage} conversation={state0.conversation}")

    t0 = time.monotonic()
    runner.submit(REPLY)
    try:
        await asyncio.wait_for(approver.asked.wait(), 240)
    except asyncio.TimeoutError:
        print("[spike] no approval was asked within 240 s; aborting")
        await runner.stop(); await task
        return 1
    t_asked = time.monotonic() - t0
    req = approver.requests[-1]
    print(f"[spike] approval asked at {t_asked:.1f}s: {req.name} {dict(req.input)}")
    await asyncio.sleep(2.0)  # the modal is "open"
    t_int = time.monotonic() - t0
    await runner.interrupt()
    print(f"[spike] interrupt() returned at {t_int:.1f}s")

    turn_ended = True
    try:
        await asyncio.wait_for(runner.queue.join(), 60)
    except asyncio.TimeoutError:
        turn_ended = False
    t_end = time.monotonic() - t0
    print(f"[spike] turn ended on its own after interrupt: {turn_ended} (at {t_end:.1f}s); approver outcome: {approver.outcome}; "
          f"release future pending: {approver.release is not None and not approver.release.done()}")
    if not turn_ended:
        print("[spike] answering the orphaned approval with a refusal to see whether the turn then ends")
        approver.release.set_result(Verdict(approved=False, answered_by="scripted", words="interrupted; not now"))
        try:
            await asyncio.wait_for(runner.queue.join(), 90)
            print(f"[spike] turn ended after the late answer at {time.monotonic() - t0:.1f}s")
        except asyncio.TimeoutError:
            print("[spike] turn STILL open 90 s after the late answer")

    finished = recorded.of(ev.TurnFinished)
    for f in finished:
        print(f"[spike] TurnFinished {f.label}: ok={f.ok} interrupted={f.interrupted} subtype={f.subtype} terminal={f.terminal_reason}")
    print(f"[spike] notices: {[n.text[:90] for n in recorded.of(ev.Notice)]}")
    print(f"[spike] approvals asked={len(recorded.of(ev.ApprovalAsked))} answered={len(recorded.of(ev.ApprovalAnswered))}")
    after = runner.graph_store.ledger()
    print(f"[spike] ledger delta: lines +{after.lines - before.lines}, proposals +{len(after.proposed) - len(before.proposed)}, "
          f"decisions +{len(after.decisions) - len(before.decisions)}, facts +{len(after.explicits) - len(before.explicits)}")
    owed = await runner._graph.pending()
    state1 = await runner._graph.state()
    print(f"[spike] graph owes: {owed}; thread at cycle={state1.cycle} stage={state1.stage} conversation={state1.conversation}")

    # F6: does the conversation carry on after the abort?
    n_before = len(recorded.of(ev.TurnFinished))
    t1 = time.monotonic()
    runner.submit(AFTER)
    try:
        await asyncio.wait_for(runner.queue.join(), 120)
        f = recorded.of(ev.TurnFinished)[n_before:]
        texts = [t.text[:200].replace("\n", " ") for t in recorded.of(ev.TextDone)][-1:]
        print(f"[spike] resume reply took {time.monotonic() - t1:.1f}s: {[(x.label, x.ok, x.interrupted, x.subtype) for x in f]}; model said: {texts}")
    except asyncio.TimeoutError:
        print("[spike] resume reply did not finish in 120 s")
    await runner.stop()
    await task
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(Path(sys.argv[1]))))
