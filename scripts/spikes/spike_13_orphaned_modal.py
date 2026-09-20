"""Spike 13 — what the approval modal does when the turn behind it is aborted (audit Cycle 2).

Headless, no model. Two questions about the real TUI:
  1. Escape while the modal is open: does the app's priority binding interrupt the run
     underneath the modal (the modal has no escape binding of its own)?
  2. After the awaiting coroutine is cancelled (what spike 12 showed the CLI abort does),
     is the modal still on screen, and what happens when it is then answered?

    .venv/bin/python scripts/spikes/spike_13_orphaned_modal.py <tmp_sessions_dir>
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from langchain_claude_test.app.config import AppConfig, ModelSettings, builtin_modes  # noqa: E402
from langchain_claude_test.app.harness.protocol import ApprovalRequest  # noqa: E402
from langchain_claude_test.app.tui.app import ProvenanceApp  # noqa: E402
from langchain_claude_test.app.tui.screens import ApprovalScreen  # noqa: E402

REQUEST = ApprovalRequest(kind="alteration", tool_use_id="toolu_x", name="propose_fact",
                          input={"quote": "a sentence"}, title="propose_fact", description="Registered e1.9", stage="synthesis")


async def main(sessions_dir: Path) -> int:
    config = AppConfig(cwd=ROOT, sessions_dir=sessions_dir,
                       modes=builtin_modes(ROOT / "src" / "langchain_claude_test" / "app"), settings=ModelSettings())
    app = ProvenanceApp(config)
    interrupts: list[str] = []

    async def fake_interrupt() -> None:
        interrupts.append("interrupt")
    app.runner.interrupt = fake_interrupt  # type: ignore[method-assign]

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.5)
        # --- 1. Escape with the modal open ---
        task = asyncio.create_task(app.approver.approve(REQUEST))
        for _ in range(50):
            await pilot.pause(0.05)
            if isinstance(app.screen, ApprovalScreen):
                break
        print(f"[spike] modal on top: {isinstance(app.screen, ApprovalScreen)}")
        await pilot.press("escape")
        await pilot.pause(0.2)
        print(f"[spike] after Escape: runner.interrupt called {len(interrupts)}x; modal still on top: {isinstance(app.screen, ApprovalScreen)}; "
              f"approve() still awaiting: {not task.done()}")
        # --- 2. the abort cancels the awaiting coroutine (spike 12) ---
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            print("[spike] approve() coroutine cancelled (as the CLI abort does)")
        await pilot.pause(0.2)
        print(f"[spike] after cancel: modal still on top: {isinstance(app.screen, ApprovalScreen)}; screen stack depth {len(app.screen_stack)}")
        # --- 3. the user answers the orphaned modal ---
        try:
            await pilot.press("ctrl+n")
            await pilot.pause(0.5)
            print(f"[spike] after ctrl+n on the orphan: app running={app.is_running} return_code={app.return_code} "
                  f"exception={type(app._exception).__name__ if getattr(app, '_exception', None) else None}: {getattr(app, '_exception', '')}; "
                  f"modal on top: {isinstance(app.screen, ApprovalScreen)}")
        except Exception as exc:  # the press itself may surface it
            print(f"[spike] pressing ctrl+n raised {type(exc).__name__}: {exc}")
    print(f"[spike] after run_test exit: return_code={app.return_code}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main(Path(sys.argv[1]))))
    except Exception as exc:
        print(f"[spike] run_test context raised {type(exc).__name__}: {exc}")
        sys.exit(2)
