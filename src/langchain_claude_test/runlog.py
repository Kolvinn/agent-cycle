"""Durable, inspectable record of a run. Every stage writes here.

The design rule: **nothing happens that the disk does not know about.** If a
run crashes halfway, everything up to the crash must still be readable, and the
crash itself must be in the log rather than inferred from its absence. So every
write is open-append-close rather than buffered — event volume is tens per
turn, so the cost is irrelevant next to being able to trust the record.

A run directory::

    runs/<run_id>/
      meta.json               config, versions, git sha, timings, final counts
      events.jsonl            the full trace, append-only, one event per line
      transcript.txt          human-readable render, written at close
      model/call-0001.json    every model call: request, response, usage, timing
      tools/call-0001.json    every tool call: args, tier, gate verdict, result
      ledger/turn-001.json    ledger snapshot, machine-readable
      ledger/turn-001.digest  the notation that crosses the round boundary
      ledger/turn-001.mmd     the same turn as a diagram

Three cross-referenced id spaces make "what happened, how, and when" traceable
in either direction: an event carries the ``model_call_id`` or ``tool_call_id``
it concerns, and each of those files carries the ``event_seq`` that announced
it. Given any artefact you can get to the others.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
import traceback
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .ledger.graph import to_jsonable
from .ledger.render import to_digest, to_mermaid
from .ledger.trace import Event, Trace

DEFAULT_ROOT = Path("runs")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5
        )
        return out.stdout.strip() or None
    except Exception:
        return None


def _jsonable(value: Any) -> Any:
    """Best-effort JSON coercion that never raises.

    A log that throws while recording a failure is worse than useless, so
    anything unserialisable degrades to its repr rather than taking the run
    down with it.
    """
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        if hasattr(value, "model_dump"):
            try:
                return value.model_dump(mode="json")
            except Exception:
                pass
        if isinstance(value, dict):
            return {str(k): _jsonable(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [_jsonable(v) for v in value]
        return repr(value)


@dataclass
class ModelCallRecord:
    """One model call, filled in by the caller and written out on exit."""

    call_id: str
    label: str
    turn: int
    request: dict[str, Any]
    response: Any = None
    raw_reply: str | None = None
    structured_output: Any = None
    thinking: list[str] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)
    raw_messages: list[Any] = field(default_factory=list)
    error: str | None = None
    event_seq: int | None = None


@dataclass
class ToolCallRecord:
    """One tool call, including the gate's verdict and why."""

    call_id: str
    tool: str
    turn: int
    args: dict[str, Any]
    tier: str = "gated"
    #: What the policy resolved, what actually ran, and which rule decided.
    #: In observe mode ``would_be`` and ``executed`` differ by design — that
    #: gap is the friction measurement.
    would_be: str | None = None
    executed: str | None = None
    reason: str = ""
    rule: str = ""
    for_node_id: str | None = None
    result: str | None = None
    error: str | None = None
    event_seq: int | None = None


class RunLog:
    """The run's durable record. One instance per run."""

    def __init__(
        self,
        *,
        root: Path | str = DEFAULT_ROOT,
        run_id: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-") + f"{os.getpid():05d}"
        self.dir = Path(root) / self.run_id
        (self.dir / "model").mkdir(parents=True, exist_ok=True)
        (self.dir / "tools").mkdir(parents=True, exist_ok=True)
        (self.dir / "ledger").mkdir(parents=True, exist_ok=True)

        self.trace = Trace()
        self._events_path = self.dir / "events.jsonl"
        self._events_path.touch()
        self._model_seq = 0
        self._tool_seq = 0
        self._started = time.monotonic()

        self.meta: dict[str, Any] = {
            "run_id": self.run_id,
            "started_at": _now(),
            "ended_at": None,
            "status": "running",
            "config": _jsonable(config or {}),
            "env": {
                "python": sys.version.split()[0],
                "platform": platform.platform(),
                "git_sha": _git_sha(),
                "cwd": str(Path.cwd()),
            },
        }
        self._write_meta()

    # --- internals ---------------------------------------------------------

    def _write_meta(self) -> None:
        (self.dir / "meta.json").write_text(json.dumps(self.meta, indent=2) + "\n")

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.write_text(json.dumps(_jsonable(payload), indent=2) + "\n")

    # --- events ------------------------------------------------------------

    def event(self, kind: str, *, turn: int, **detail: Any) -> Event:
        """Record one trace event, in memory and on disk, immediately."""
        ev = self.trace.emit(kind, turn=turn, **detail)
        line = json.dumps(
            {"seq": ev.seq, "turn": ev.turn, "kind": ev.kind, "at": ev.at, "detail": _jsonable(ev.detail)}
        )
        with self._events_path.open("a") as fh:
            fh.write(line + "\n")
            fh.flush()
        return ev

    # --- model calls -------------------------------------------------------

    @contextmanager
    def model_call(
        self, label: str, *, turn: int, request: dict[str, Any]
    ) -> Iterator[ModelCallRecord]:
        """Wrap one model call so the full request and response land on disk.

        The request is written *before* the call runs, so a hang or a crash
        still leaves behind exactly what was sent.
        """
        self._model_seq += 1
        rec = ModelCallRecord(
            call_id=f"m{self._model_seq:04d}", label=label, turn=turn, request=request
        )
        path = self.dir / "model" / f"call-{self._model_seq:04d}.json"
        started = time.monotonic()
        self._write_json(path, {"status": "in_flight", "started_at": _now(), **rec.__dict__})
        try:
            yield rec
        except BaseException as exc:
            rec.error = "".join(traceback.format_exception_only(type(exc), exc)).strip()
            raise
        finally:
            self._write_json(
                path,
                {
                    "status": "error" if rec.error else "ok",
                    "started_at": _now(),
                    "duration_s": round(time.monotonic() - started, 3),
                    **rec.__dict__,
                },
            )

    # --- tool calls --------------------------------------------------------

    @contextmanager
    def tool_call(
        self, tool: str, *, turn: int, args: dict[str, Any], tier: str = "gated"
    ) -> Iterator[ToolCallRecord]:
        """Wrap one tool call, gate verdict included."""
        self._tool_seq += 1
        rec = ToolCallRecord(
            call_id=f"t{self._tool_seq:04d}", tool=tool, turn=turn, args=args, tier=tier
        )
        path = self.dir / "tools" / f"call-{self._tool_seq:04d}.json"
        started = time.monotonic()
        self._write_json(path, {"status": "in_flight", "started_at": _now(), **rec.__dict__})
        try:
            yield rec
        except BaseException as exc:
            rec.error = "".join(traceback.format_exception_only(type(exc), exc)).strip()
            raise
        finally:
            self._write_json(
                path,
                {
                    "status": "error" if rec.error else "ok",
                    "started_at": _now(),
                    "duration_s": round(time.monotonic() - started, 3),
                    **rec.__dict__,
                },
            )

    # --- ledger snapshots --------------------------------------------------

    def snapshot(self, graph: Any, *, turn: int, label: str = "") -> Path:
        """Freeze the ledger after a turn, three ways.

        All three, not one: the JSON is what a test diffs, the digest is what
        actually crosses the round boundary, and the diagram is what a human
        reads. Keeping them together means a turn can be inspected in whichever
        form the question calls for.
        """
        stem = f"turn-{turn:03d}" + (f"-{label}" if label else "")
        base = self.dir / "ledger"
        self._write_json(base / f"{stem}.json", {"turn": turn, "at": _now(), **to_jsonable(graph)})
        (base / f"{stem}.digest").write_text(to_digest(graph, turn=turn) + "\n")
        (base / f"{stem}.mmd").write_text(to_mermaid(graph, title=f"turn {turn}"))
        return base / f"{stem}.json"

    # --- close -------------------------------------------------------------

    def close(self, *, status: str = "ok", **extra: Any) -> None:
        """Finalise the run: transcript, counts, status.

        Safe to call twice, and safe to call after a crash — which is the
        point, since the failed runs are the ones worth reading.
        """
        (self.dir / "transcript.txt").write_text(self.trace.render() + "\n")
        self.meta.update(
            {
                "ended_at": _now(),
                "status": status,
                "duration_s": round(time.monotonic() - self._started, 3),
                "counts": {
                    "events": len(self.trace.events),
                    "model_calls": self._model_seq,
                    "tool_calls": self._tool_seq,
                    "by_kind": _kind_counts(self.trace),
                },
                **_jsonable(extra),
            }
        )
        self._write_meta()

    def __enter__(self) -> RunLog:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc is not None:
            self.event(
                "run_failed",
                turn=-1,
                error="".join(traceback.format_exception_only(type(exc), exc)).strip(),
            )
        self.close(status="error" if exc is not None else "ok")


def _kind_counts(trace: Trace) -> dict[str, int]:
    out: dict[str, int] = {}
    for e in trace.events:
        out[e.kind] = out.get(e.kind, 0) + 1
    return dict(sorted(out.items()))
