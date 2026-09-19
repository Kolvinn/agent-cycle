"""Spike 9 — one real cycle through the app's shell, on Haiku, against the fixture.

Everything below the model is covered by the deterministic suite. This answers
what only a live run can: do the hooks fire and price the SDK's own tools, does
``attach_finding`` land, does each frame's ``output_format`` come back, and does
the conversation continue across frames by ``resume``.

Approvals are auto-answered and every record says so. Run:

    .venv/bin/python scripts/spikes/spike_09_live_cycle.py
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from langchain_claude_test.app.config import TEST_MODEL, AppConfig, ModelSettings, builtin_modes  # noqa: E402
from langchain_claude_test.app.harness import events as ev  # noqa: E402
from langchain_claude_test.app.harness.console import ConsoleSink  # noqa: E402
from langchain_claude_test.app.harness.events import FanoutSink, ListSink  # noqa: E402
from langchain_claude_test.app.harness.scripted import AutoApprover  # noqa: E402
from langchain_claude_test.app.runner import Runner  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "repo"
QUESTION = "Where do we validate the incoming webhook signature?"
REPLY = (
    "I think the validation is in signature.py and the handler just calls it. "
    "Register that as a fact, and propose closing whichever reading it confirms."
)


async def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="spike09-"))
    recorded = ListSink()
    sink = FanoutSink(ConsoleSink(), recorded)
    approver = AutoApprover()
    config = AppConfig(
        cwd=FIXTURE,
        sessions_dir=work / "sessions",
        modes=builtin_modes(ROOT / "src" / "langchain_claude_test" / "app"),
        settings=ModelSettings(model=TEST_MODEL),
    )
    runner = Runner(config=config, sink=sink, approver=approver)
    task = asyncio.create_task(runner.run("spike09"))
    ok = True
    try:
        runner.submit(f"/graph {QUESTION}")
        await runner.queue.join()
        runner.submit(REPLY)
        await runner.queue.join()
        runner.submit("/show package")
        await runner.queue.join()
    finally:
        await runner.stop()
        await task

    print("\n" + "=" * 78)
    stages = [e.stage for e in recorded.events if isinstance(e, ev.StageFinished)]
    priced = [e for e in recorded.events if isinstance(e, ev.Priced)]
    refused = [e for e in recorded.events if isinstance(e, ev.Refused)]
    calls = [e for e in recorded.events if isinstance(e, ev.ToolCalled)]
    asked = [e for e in recorded.events if isinstance(e, ev.ApprovalAsked)]
    finished = [e for e in recorded.events if isinstance(e, ev.TurnFinished)]
    sessions = {e.session_id for e in finished if e.session_id}
    cost = sum(e.cost_usd or 0 for e in finished)
    print(f"  stages finished     : {stages}")
    print(f"  tool calls seen     : {len(calls)}  priced: {len(priced)}  refused: {len(refused)}")
    print(f"  structured output   : {sum(1 for e in finished if e.ok)}/{len(finished)} turns returned a payload")
    print(f"  approvals asked     : {[a.name for a in asked]}")
    print(f"  sdk conversations   : {sorted(sessions)}")
    print(f"  cost (estimate)     : ${cost:.4f}")
    print(f"  events log          : {config.sessions_dir / 'spike09' / 'events.jsonl'}")

    checks = [
        ("all four frames finished", stages[:4] == ["orientate", "assume", "antithesis", "synthesis"]),
        ("the reply re-entered synthesis", stages.count("synthesis") >= 2),
        ("at least one call was priced", len(priced) >= 1),
        ("StructuredOutput was never priced", not any(p.name == "StructuredOutput" for p in priced)),
        ("one conversation carried every frame", len(sessions) == 1),
        ("every turn returned its payload", all(e.ok for e in finished if not e.interrupted)),
    ]
    for label, passed in checks:
        ok &= passed
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
    print("=" * 78)
    shutil.rmtree(work, ignore_errors=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
