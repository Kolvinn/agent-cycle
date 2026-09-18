"""The trace — the run's primary output, not a debugging aid.

The point of the first live runs is to watch how the agent extracts and
implies, so every step emits an event and nothing is reconstructed after the
fact. Two renderings: :meth:`Trace.to_jsonl` for assertions, and
:meth:`Trace.render` for reading.

One rule this module exists to hold: a gate decision records both what it
*would* have done and what actually happened. In ``observe`` mode those differ
by design — that gap is the friction measurement, and it is the thing a prior
attempt at this never collected before deciding the gate was too annoying.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

# --- event kinds -----------------------------------------------------------

TURN_STARTED = "turn_started"
USER_MESSAGE = "user_message"
THINKING = "thinking"
EXPLICIT_REGISTERED = "explicit_registered"
EXTRACTION_REJECTED = "extraction_rejected"
ASSUMPTION_FORMED = "assumption_formed"
ASSUMPTION_REJECTED = "assumption_rejected"
SIGNOFF_REQUESTED = "signoff_requested"
SIGNOFF_ANSWERED = "signoff_answered"
GATE_DECISION = "gate_decision"
TOOL_CALL = "tool_call"
TOOL_RESULT = "tool_result"
SOURCE_PROPOSED = "source_proposed"
SOURCE_APPLIED = "source_applied"
SOURCE_REJECTED = "source_rejected"
REPLY_SENT = "reply_sent"
COMPACTION = "compaction"

_GLYPH = {
    TURN_STARTED: "═",
    USER_MESSAGE: "👤",
    THINKING: "💭",
    EXPLICIT_REGISTERED: "🟢",
    EXTRACTION_REJECTED: "❌",
    ASSUMPTION_FORMED: "🟡",
    ASSUMPTION_REJECTED: "❌",
    SIGNOFF_REQUESTED: "🙋",
    SIGNOFF_ANSWERED: "✅",
    GATE_DECISION: "🛡️",
    TOOL_CALL: "⚙️",
    TOOL_RESULT: "📄",
    SOURCE_PROPOSED: "🔗",
    SOURCE_APPLIED: "🔗",
    SOURCE_REJECTED: "❌",
    REPLY_SENT: "💬",
    COMPACTION: "✂️",
}


@dataclass(frozen=True, slots=True)
class Event:
    seq: int
    turn: int
    kind: str
    at: str
    detail: dict[str, Any]


@dataclass
class Trace:
    events: list[Event] = field(default_factory=list)

    def emit(self, kind: str, *, turn: int, **detail: Any) -> Event:
        ev = Event(
            seq=len(self.events),
            turn=turn,
            kind=kind,
            at=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            detail=detail,
        )
        self.events.append(ev)
        return ev

    # --- queries used by tests ---------------------------------------------

    def of_kind(self, kind: str) -> tuple[Event, ...]:
        return tuple(e for e in self.events if e.kind == kind)

    def for_turn(self, turn: int) -> tuple[Event, ...]:
        return tuple(e for e in self.events if e.turn == turn)

    # --- output ------------------------------------------------------------

    def to_jsonl(self) -> str:
        return "\n".join(json.dumps(asdict(e), default=str) for e in self.events)

    def render(self, *, show_thinking: bool = True) -> str:
        out: list[str] = []
        for e in self.events:
            if e.kind == THINKING and not show_thinking:
                continue
            out.append(self._render_one(e))
        return "\n".join(out)

    def _render_one(self, e: Event) -> str:
        g = _GLYPH.get(e.kind, "·")
        d = e.detail

        if e.kind == TURN_STARTED:
            return f"\n{'═' * 72}\n  TURN {e.turn}\n{'═' * 72}"

        if e.kind == USER_MESSAGE:
            return f'{g} user: "{d.get("text", "")}"'

        if e.kind == THINKING:
            body = str(d.get("text", "")).strip().replace("\n", "\n     ")
            return f"{g} thinking:\n     {body}"

        if e.kind == EXPLICIT_REGISTERED:
            span = d.get("span")
            where = f" @{span[0]}..{span[1]}" if span else ""
            return f'{g} EXPLICIT {d.get("node_id", "")[:8]}{where} "{d.get("quote", "")}"'

        if e.kind == EXTRACTION_REJECTED:
            return f"{g} extraction rejected: {d.get('reason', '')}"

        if e.kind == ASSUMPTION_FORMED:
            return (
                f'{g} IMPLICIT {d.get("node_id", "")[:8]} '
                f'grounded in {d.get("grounded_in", "")[:8]}\n'
                f'     claim: "{d.get("claim", "")}"'
            )

        if e.kind == ASSUMPTION_REJECTED:
            return f"{g} assumption refused: {d.get('reason', '')}"

        if e.kind == SIGNOFF_REQUESTED:
            return f'{g} sign-off needed on {d.get("node_id", "")[:8]}: "{d.get("claim", "")}"'

        if e.kind == SIGNOFF_ANSWERED:
            by = d.get("answered_by", "?")
            warn = "  ⚠️ MACHINE-GENERATED, NOT A HUMAN" if by in ("auto", "scripted") else ""
            return f'{g} sign-off: {d.get("verdict", "")} (by: {by}){warn}'

        if e.kind == GATE_DECISION:
            would, did = d.get("would_be"), d.get("executed")
            shadow = "" if would == did else f"  ← observe mode: would have been {would!r}"
            return (
                f'{g} gate [{d.get("tier", "?")}] {d.get("tool", "?")} → {did}{shadow}\n'
                f'     why: {d.get("reason", "")}'
            )

        if e.kind == TOOL_CALL:
            return f'{g} call {d.get("tool", "?")}({json.dumps(d.get("args", {}))[:100]}) id={d.get("tool_call_id", "")}'

        if e.kind == TOOL_RESULT:
            body = str(d.get("text", ""))
            clipped = body if len(body) <= 200 else body[:199] + "…"
            return f"{g} result ({len(body)} chars):\n     " + clipped.replace("\n", "\n     ")

        if e.kind == SOURCE_PROPOSED:
            return f'{g} source proposed: {d.get("locator", "")} — "{d.get("excerpt", "")}"'

        if e.kind == SOURCE_APPLIED:
            return (
                f'{g} SOURCE APPLIED to edge {d.get("edge_id", "")[:8]}: {d.get("locator", "")}\n'
                f'     answers: "{d.get("answers", "")}"'
            )

        if e.kind == SOURCE_REJECTED:
            return f"{g} source rejected: {d.get('reason', '')}"

        if e.kind == REPLY_SENT:
            return f'{g} reply: "{d.get("text", "")}"'

        if e.kind == COMPACTION:
            return (
                f"{g} COMPACTION at round boundary\n"
                f'     before: {d.get("before_messages", "?")} messages, '
                f'{d.get("before_tool_entries", "?")} tool entries\n'
                f'     after:  {d.get("after_messages", "?")} messages, '
                f'{d.get("after_tool_entries", "?")} tool entries\n'
                f'     carried: {d.get("carried", "")}'
            )

        return f"{g} {e.kind}: {json.dumps(d, default=str)[:160]}"
