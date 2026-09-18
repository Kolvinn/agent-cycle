"""Spike 3 — one real round, on Haiku, against the fixture.

Everything below the model is already covered by the deterministic suite. What
this answers is the part only a live run can: does a real model, under locked
schemas, actually produce a verbatim quote, a checkable claim, and a source
that survives all three checks?

Sign-off is scripted so the run is repeatable and unattended — and the trace
stamps it MACHINE-GENERATED so it can never be misread later as a human.

Run:  .venv/bin/python scripts/spikes/spike_03_live_round.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from langchain_claude_test.ledger import check_invariants, to_digest  # noqa: E402
from langchain_claude_test.runlog import RunLog  # noqa: E402
from langchain_claude_test.session import ScriptedUI  # noqa: E402
from langchain_claude_test.session.gate import Policy  # noqa: E402
from langchain_claude_test.session.model import DEFAULT_MODEL, SdkModel  # noqa: E402
from langchain_claude_test.session.runner import Runner  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "repo"
MESSAGE = "Where do we validate the incoming webhook signature?"


async def main() -> int:
    log = RunLog(
        root=ROOT / "runs",
        config={"spike": "03_live_round", "model": DEFAULT_MODEL, "mode": "observe"},
    )
    ui = ScriptedUI(messages=[MESSAGE], signoffs=["approved"])
    runner = Runner(
        model=SdkModel(),
        ui=ui,
        runlog=log,
        fixture_root=FIXTURE,
        # Observe: record what the gate would have done, then run anyway. The
        # first live runs are for watching how it extracts and implies, and
        # blocking would confound that with friction.
        policy=Policy(mode="observe"),
    )

    print("=" * 72)
    print(f"  Spike 3 — live round on {DEFAULT_MODEL}")
    print(f"  run dir: {log.dir}")
    print("=" * 72)
    print(f'\n  user: "{MESSAGE}"\n')

    status = "ok"
    try:
        await runner.run()
    except Exception as exc:  # noqa: BLE001 — the spike reports and still closes the log
        status = "error"
        log.event("run_failed", turn=runner.state.turn, error=f"{type(exc).__name__}: {exc}")
        print(f"  RUN FAILED: {type(exc).__name__}: {exc}")
    finally:
        log.close(status=status)

    print(log.trace.render())
    print("\n" + "-" * 72)
    print(to_digest(runner.state.graph, turn=runner.state.turn))
    print("-" * 72)

    problems = check_invariants(runner.state.graph)
    print(f"\n  invariants : {'clean' if not problems else problems}")
    print(f"  model calls: {log._model_seq}   tool calls: {log._tool_seq}")
    print(f"  artefacts  : {log.dir}")
    return 0 if status == "ok" and not problems else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
