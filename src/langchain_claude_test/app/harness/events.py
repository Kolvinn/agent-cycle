"""What a turn tells the outside as it happens.

The seam between the inner layer and any UI. The harness emits; a sink
receives. The TUI is one sink, a list is another, a JSONL file a third — and
because the sink is the only thing the harness knows about the outside, the
whole loop runs headless with a recording sink and is tested that way.

Events are small frozen records. They carry text and ids, never live objects,
so a sink can serialise them without thinking.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Protocol, Union

Kind = Literal["chat", "graph"]


@dataclass(frozen=True, slots=True)
class TurnStarted:
    label: str
    kind: Kind
    stage: str = ""
    cycle: int = 0


@dataclass(frozen=True, slots=True)
class TurnFinished:
    label: str
    ok: bool
    interrupted: bool = False
    subtype: str = ""
    terminal_reason: str = ""
    cost_usd: float | None = None
    session_id: str = ""


@dataclass(frozen=True, slots=True)
class SessionInfo:
    """From the ``init`` system message: what this conversation can do."""

    session_id: str
    model: str = ""
    tools: tuple[str, ...] = ()
    slash_commands: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ThinkingDelta:
    text: str


@dataclass(frozen=True, slots=True)
class ThinkingDone:
    text: str


@dataclass(frozen=True, slots=True)
class TextDelta:
    text: str


@dataclass(frozen=True, slots=True)
class TextDone:
    text: str


@dataclass(frozen=True, slots=True)
class ToolStarted:
    tool_use_id: str
    name: str


@dataclass(frozen=True, slots=True)
class ToolInputDelta:
    tool_use_id: str
    partial_json: str


@dataclass(frozen=True, slots=True)
class ToolCalled:
    """The complete call: name and input, once the block has closed."""

    tool_use_id: str
    name: str
    input: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ToolResult:
    tool_use_id: str
    text: str
    is_error: bool = False


@dataclass(frozen=True, slots=True)
class Priced:
    """A call the meter allowed, and what it left in the pool."""

    tool_use_id: str
    name: str
    call_class: str
    price: int
    pool: str
    remaining: int


@dataclass(frozen=True, slots=True)
class Refused:
    """A call the meter or the surface refused before it ran."""

    tool_use_id: str
    name: str
    reason: str


@dataclass(frozen=True, slots=True)
class ApprovalAsked:
    tool_use_id: str
    name: str
    input: dict[str, Any]
    title: str = ""
    #: What the call would do, as the handler's dry run described it.
    description: str = ""


@dataclass(frozen=True, slots=True)
class ApprovalAnswered:
    tool_use_id: str
    name: str
    approved: bool
    words: str = ""
    answered_by: str = "human"


@dataclass(frozen=True, slots=True)
class StageStarted:
    stage: str
    cycle: int


@dataclass(frozen=True, slots=True)
class StageFinished:
    stage: str
    cycle: int
    #: A short description of what the frame wrote.
    summary: str = ""


@dataclass(frozen=True, slots=True)
class StateSnapshot:
    """The graph as it stands after a frame committed — for a panel to draw."""

    stage: str
    cycle: int
    question: str
    #: (depth, node id, label) rows, from ``thought.outline``.
    outline: tuple[tuple[int, str, str], ...]
    #: (pool, spent, cap) for this cycle's pools.
    pools: tuple[tuple[str, int, int], ...]
    conversation: str = ""
    #: (id, kind, role, status, text) for every live node — the browser's rows.
    nodes: tuple[tuple[str, str, str, str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class Notice:
    """Something the user should see that is not part of the model's reply."""

    text: str
    level: Literal["info", "warning", "error"] = "info"


@dataclass(frozen=True, slots=True)
class ResultText:
    """The final text of a chat turn, as the CLI reports it."""

    text: str


HarnessEvent = Union[
    TurnStarted,
    TurnFinished,
    SessionInfo,
    ThinkingDelta,
    ThinkingDone,
    TextDelta,
    TextDone,
    ToolStarted,
    ToolInputDelta,
    ToolCalled,
    ToolResult,
    Priced,
    Refused,
    ApprovalAsked,
    ApprovalAnswered,
    StageStarted,
    StageFinished,
    StateSnapshot,
    Notice,
    ResultText,
]


class EventSink(Protocol):
    def emit(self, event: HarnessEvent) -> None: ...


class ListSink:
    """Records everything. What tests assert on."""

    def __init__(self) -> None:
        self.events: list[HarnessEvent] = []

    def emit(self, event: HarnessEvent) -> None:
        self.events.append(event)

    def of(self, kind: type) -> list[Any]:
        return [e for e in self.events if isinstance(e, kind)]

    def text(self) -> str:
        return "".join(e.text for e in self.events if isinstance(e, TextDelta))


class JsonlSink:
    """Appends one line per event. Open-append-close, so a crash loses nothing."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: HarnessEvent) -> None:
        line = {
            "at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "event": type(event).__name__,
            **asdict(event),
        }
        with self.path.open("a") as fh:
            fh.write(json.dumps(line, default=str) + "\n")


class FanoutSink:
    """One sink that feeds several."""

    def __init__(self, *sinks: EventSink) -> None:
        self.sinks: list[EventSink] = list(sinks)

    def emit(self, event: HarnessEvent) -> None:
        for s in self.sinks:
            s.emit(event)


@dataclass
class NullSink:
    emitted: int = field(default=0)

    def emit(self, event: HarnessEvent) -> None:
        self.emitted += 1
