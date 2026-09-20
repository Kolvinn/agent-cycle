"""Spike 11 — one real cycle against THIS repository, on Haiku, for the audit.

Unlike spike 09 this runs on the project itself rather than the five-file
fixture, answers gated calls with a *scripted* approver (approve, approve,
refuse-with-words) rather than an auto-approver, and measures what the audit
needs: frame latency, findings kept and their sizes, package size, free graph
reads, refusals, and cost. Sessions go to a directory given on the command
line so nothing lands in the project's own ``sessions/``.

    .venv/bin/python scripts/spikes/spike_11_audit_cycle.py <sessions_dir> [second-cycle]
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from langchain_claude_test.app.config import TEST_MODEL, AppConfig, ModelSettings, builtin_modes  # noqa: E402
from langchain_claude_test.app.harness import events as ev  # noqa: E402
from langchain_claude_test.app.harness.console import ConsoleSink  # noqa: E402
from langchain_claude_test.app.harness.events import FanoutSink, ListSink  # noqa: E402
from langchain_claude_test.app.harness.protocol import Verdict  # noqa: E402
from langchain_claude_test.app.harness.scripted import ScriptedApprover  # noqa: E402
from langchain_claude_test.app.runner import Runner  # noqa: E402

QUESTION = "Where does the app decide which tools a frame may call, and what happens when the model calls one outside that set?"
REPLY = (
    "The surface is decided in graph/surface.py and the PreToolUse hook in harness/hooks.py refuses the rest. "
    "Register that sentence as a fact. Close whichever assumption it confirms, and refute the rival of that one."
)
SECOND = "What does a refused call leave behind in the graph, if anything?"


class Timeline(ListSink):
    def __init__(self) -> None:
        super().__init__()
        self.stamps: list[tuple[float, str]] = []

    def emit(self, event):  # type: ignore[override]
        super().emit(event)
        if isinstance(event, (ev.TurnStarted, ev.TurnFinished, ev.StageFinished, ev.ApprovalAsked, ev.ApprovalAnswered)):
            self.stamps.append((time.monotonic(), f"{type(event).__name__} {getattr(event, 'label', getattr(event, 'stage', ''))}"))


async def main(sessions_dir: Path, second: bool) -> int:
    recorded = Timeline()
    sink = FanoutSink(ConsoleSink(deltas=False), recorded)
    approver = ScriptedApprover(
        verdicts=deque(
            [
                Verdict(approved=True, answered_by="scripted", words="yes, that is where it lives"),
                Verdict(approved=True, answered_by="scripted", words=""),
                Verdict(approved=False, answered_by="scripted", words="no - a refuted rival is not the same as a wrong one; leave it open"),
            ]
            + [Verdict(approved=False, answered_by="scripted", words="not this cycle")] * 10
        )
    )
    config = AppConfig(
        cwd=ROOT,
        sessions_dir=sessions_dir,
        modes=builtin_modes(ROOT / "src" / "langchain_claude_test" / "app"),
        settings=ModelSettings(model=TEST_MODEL),
    )
    runner = Runner(config=config, sink=sink, approver=approver)
    task = asyncio.create_task(runner.run("audit11"))
    t0 = time.monotonic()
    try:
        runner.submit(f"/graph {QUESTION}")
        await runner.queue.join()
        runner.submit(REPLY)
        await runner.queue.join()
        if second:
            runner.submit(f"/graph {SECOND}")
            await runner.queue.join()
        runner.submit("/show package")
        await runner.queue.join()
    finally:
        await runner.stop()
        await task

    print("\n" + "=" * 78)
    finished = recorded.of(ev.TurnFinished)
    started = recorded.of(ev.TurnStarted)
    print("  frame timeline (s from start):")
    for t, what in recorded.stamps:
        print(f"    {t - t0:7.1f}  {what}")
    calls = recorded.of(ev.ToolCalled)
    by_name: dict[str, int] = {}
    for c in calls:
        by_name[c.name] = by_name.get(c.name, 0) + 1
    print(f"  tool calls by name  : {dict(sorted(by_name.items()))}")
    print(f"  priced              : {len(recorded.of(ev.Priced))}   refused: {[ (r.name, r.reason[:60]) for r in recorded.of(ev.Refused)]}")
    print(f"  approvals           : {[(a.name, a.title[:50]) for a in recorded.of(ev.ApprovalAsked)]}")
    print(f"  answered            : {[(a.name, a.approved, a.words[:30]) for a in recorded.of(ev.ApprovalAnswered)]}")
    print(f"  payload ok          : {sum(1 for e in finished if e.ok)}/{len(finished)}   interrupted: {sum(1 for e in finished if e.interrupted)}")
    cost = sum(e.cost_usd or 0 for e in finished)
    print(f"  cost (estimate)     : ${cost:.4f}")
    ledger = runner.graph_store.ledger()
    sizes = [len(f.excerpt) for f in ledger.findings.values()]
    lines = [f.excerpt.count(chr(10)) + 1 for f in ledger.findings.values()]
    print(f"  op log              : {ledger.lines} lines, cycles {sorted(ledger.cycles)}, {len(ledger.findings)} findings "
          f"(chars {sizes}; lines {lines}), {len(ledger.assumptions)} assumptions, {len(ledger.antitheses)} rivals, "
          f"{len(ledger.explicits)} facts, {len(ledger.ops)} ops, {len(ledger.proposed)} proposals, {len(ledger.decisions)} decisions")
    for w in ledger.proposed.values():
        d = ledger.decisions.get(w.id)
        print(f"    proposal {w.id}: {w.write} {w.target_id} -> {'approved' if d and d.approved else 'refused'} applied={getattr(d, 'applied', None)}")
    for f in ledger.findings.values():
        print(f"    finding {f.id} on {f.node_id}: {f.locator[:70]}")
    notices = [n.text for n in recorded.of(ev.Notice)]
    pkg = next((n for n in notices if n.startswith(("KNOWN", "CONTEXT", "ENTITIES", "ASSUMPTIONS"))), "")
    print(f"  package             : {len(pkg)} chars, {pkg.count(chr(10)) + 1} lines")
    log = sessions_dir / "audit11" / "events.jsonl"
    text = log.read_text() if log.exists() else ""
    print(f"  events log          : {log} ({len(text.splitlines())} lines, {len(text)} bytes)")
    print(f"  'excerpt' in model tool inputs: {sum(1 for c in calls if 'excerpt' in c.input)}   'reading' in model text: "
          f"{sum(1 for e in recorded.of(ev.TextDone) if 'reading' in e.text.lower())}")
    warnings = [n for n in notices if 'structured output' in n or 'no structured' in n]
    print(f"  payload warnings    : {warnings}")
    (sessions_dir / "summary.json").write_text(json.dumps({
        "cost": cost, "turns": len(finished), "calls": by_name, "findings": len(ledger.findings),
        "sizes": sizes, "package_chars": len(pkg), "stamps": [(round(t - t0, 1), w) for t, w in recorded.stamps],
    }, indent=1))
    print("=" * 78)
    return 0


if __name__ == "__main__":
    where = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/spike11")
    sys.exit(asyncio.run(main(where, "second-cycle" in sys.argv)))
