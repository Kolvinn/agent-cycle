"""A plain-text sink for spikes and debugging: one line per event, deltas inline."""

from __future__ import annotations

import sys
from typing import TextIO

from . import events as ev


class ConsoleSink:
    def __init__(self, out: TextIO = sys.stdout, *, deltas: bool = True) -> None:
        self.out = out
        self.deltas = deltas
        self._streaming = False

    def _line(self, text: str) -> None:
        if self._streaming:
            self.out.write("\n")
            self._streaming = False
        self.out.write(text + "\n")
        self.out.flush()

    def emit(self, event: ev.HarnessEvent) -> None:
        match event:
            case ev.TextDelta(text=t) | ev.ThinkingDelta(text=t):
                if self.deltas:
                    self.out.write(t if isinstance(event, ev.TextDelta) else f"\x1b[2m{t}\x1b[0m")
                    self.out.flush()
                    self._streaming = True
            case ev.TextDone():
                if self._streaming:
                    self.out.write("\n")
                    self._streaming = False
            case ev.ThinkingDone():
                if self._streaming:
                    self.out.write("\n")
                    self._streaming = False
            case ev.TurnStarted(label=label, kind=kind, stage=stage):
                self._line(f"=== turn {label} ({kind}{' ' + stage if stage else ''}) ===")
            case ev.TurnFinished(label=label, ok=ok, interrupted=i, subtype=st, terminal_reason=tr, cost_usd=c):
                self._line(f"=== end {label}: ok={ok} interrupted={i} {st} {tr} cost={c} ===")
            case ev.ToolCalled(name=name, input=inp):
                self._line(f"  ⚙ {name} {str(inp)[:160]}")
            case ev.ToolResult(text=text, is_error=err):
                first = text.splitlines()[0] if text else ""
                self._line(f"  {'✗' if err else '↳'} {first[:160]}")
            case ev.Priced(name=name, price=price, remaining=left, pool=pool):
                self._line(f"  $ {name} −{price} → {left} left in {pool}")
            case ev.Refused(name=name, reason=reason):
                self._line(f"  ⛔ {name}: {reason[:160]}")
            case ev.ApprovalAsked(name=name, title=title):
                self._line(f"  ? {name}: {title}")
            case ev.ApprovalAnswered(name=name, approved=a, words=w, answered_by=by):
                self._line(f"  {'✓' if a else '✗'} {name} by {by}: {w}")
            case ev.StageFinished(stage=stage, cycle=cycle, summary=summary):
                self._line(f"── {stage} (cycle {cycle}) — {summary}")
            case ev.Notice(text=text, level=level):
                self._line(f"[{level}] {text}")
            case ev.SessionInfo(session_id=sid, model=model):
                self._line(f"  session {sid} model={model}")
            case _:
                pass
