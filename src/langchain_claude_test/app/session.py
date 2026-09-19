"""Sessions — *"stored as these inbuilt graphs"*.

A session is a name, a LangGraph thread of the same name in one SQLite
checkpoint file, and the SDK conversations the session has opened: one per
chat mode, plus the one the graph's open cycle is running in (that one lives in
the graph state, because it is forked and checkpointed with it).

Session metadata is one JSON file per session — flat and readable, so a
session can be inspected or repaired with a text editor. The checkpoint
database is shared and is LangGraph's. The graph is shared too, as one op log
under ``graph/`` (``graph/store.py``): a session holds its cycle, not the graph.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

CHECKPOINTS = "checkpoints.sqlite"
GRAPH_LOG = "graph/ops.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class SessionRecord:
    name: str
    created: str = field(default_factory=_now)
    #: ``"graph"`` while the user is inside the cycle; otherwise a chat mode name.
    focus: str = "chat"
    #: The chat mode to return to when leaving the graph.
    mode: str = "chat"
    #: Chat mode name -> SDK session id, so ``/reviewer`` resumes its own thread.
    conversations: dict[str, str] = field(default_factory=dict)
    model: str | None = None
    effort: str | None = None
    #: Graph caps and prices the user changed with ``/budget`` and ``/prices``,
    #: as overrides on the configured defaults.
    budgets: dict[str, int] = field(default_factory=dict)
    prices: dict[str, int] = field(default_factory=dict)
    #: The session this one was forked from, if any.
    forked_from: str = ""

    @property
    def thread_id(self) -> str:
        return self.name

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2) + "\n"

    @classmethod
    def from_json(cls, text: str) -> SessionRecord:
        data = json.loads(text)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class SessionStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @property
    def checkpoints(self) -> Path:
        return self.root / CHECKPOINTS

    @property
    def graph_log(self) -> Path:
        """The project's one graph: the op log every session appends to."""
        return self.root / GRAPH_LOG

    def _path(self, name: str) -> Path:
        return self.root / f"{name}.json"

    def events_path(self, name: str) -> Path:
        return self.root / name / "events.jsonl"

    def exists(self, name: str) -> bool:
        return self._path(name).exists()

    def names(self) -> list[str]:
        return sorted(p.stem for p in self.root.glob("*.json"))

    def list(self) -> list[SessionRecord]:
        return [self.load(n) for n in self.names()]

    def load(self, name: str) -> SessionRecord:
        path = self._path(name)
        if not path.exists():
            raise KeyError(f"no session named {name!r}")
        return SessionRecord.from_json(path.read_text())

    def save(self, record: SessionRecord) -> None:
        self._path(record.name).write_text(record.to_json())

    def create(self, name: str | None = None, *, mode: str = "chat") -> SessionRecord:
        if not name:
            name = datetime.now().strftime("s-%Y%m%d-%H%M%S")
            n = 1
            while self.exists(name):
                n += 1
                name = f"{name}-{n}" if n == 2 else name.rsplit("-", 1)[0] + f"-{n}"
        if self.exists(name):
            raise FileExistsError(f"session {name!r} already exists")
        valid = name.replace("-", "").replace("_", "").isalnum()
        if not valid:
            raise ValueError("a session name may only hold letters, digits, - and _")
        record = SessionRecord(name=name, focus=mode, mode=mode)
        self.save(record)
        return record
