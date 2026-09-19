"""Spike 10 — the default connection, live: streaming, a tool call, an interrupt
from another task, and a follow-up after it. On Haiku. Run:

    .venv/bin/python scripts/spikes/spike_10_live_chat.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from langchain_claude_test.app.chat import ChatDriver  # noqa: E402
from langchain_claude_test.app.config import TEST_MODEL, ModelSettings, builtin_modes  # noqa: E402
from langchain_claude_test.app.harness import events as ev  # noqa: E402
from langchain_claude_test.app.harness.console import ConsoleSink  # noqa: E402
from langchain_claude_test.app.harness.events import FanoutSink, ListSink  # noqa: E402
from langchain_claude_test.app.harness.scripted import AutoApprover  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "repo"
PKG = ROOT / "src" / "langchain_claude_test" / "app"


async def main() -> int:
    recorded = ListSink()
    sink = FanoutSink(ConsoleSink(), recorded)
    modes = builtin_modes(PKG)
    driver = ChatDriver(
        mode=modes["chat"],
        base_dir=PKG,
        settings=ModelSettings(model=TEST_MODEL),
        sink=sink,
        approver=AutoApprover(),
        cwd=FIXTURE,
    )
    ok = True
    try:
        sid = await driver.send("List the python files in this directory and read one of them. Answer in one sentence.")
        calls = [e.name for e in recorded.events if isinstance(e, ev.ToolCalled)]
        text = recorded.text()
        print(f"\n  session: {sid}\n  tools: {calls}\n  text length: {len(text)}")
        ok &= bool(sid) and bool(calls) and bool(text)

        # interrupt from another task while a slow turn streams
        recorded.events.clear()
        slow = asyncio.create_task(driver.send("Count from 1 to 300, one number per line, no commentary."))
        await asyncio.sleep(4)
        await driver.interrupt()
        await slow
        fin = [e for e in recorded.events if isinstance(e, ev.TurnFinished)]
        print(f"  interrupted turn: {fin[-1] if fin else None}")
        ok &= bool(fin) and fin[-1].interrupted

        recorded.events.clear()
        await driver.send("Just say hello.")
        print(f"  after interrupt: {recorded.text()!r}")
        ok &= "hello" in recorded.text().lower()
    finally:
        await driver.close()
    print(f"\n  [{'PASS' if ok else 'FAIL'}] chat: stream, tool call, interrupt, follow-up")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
