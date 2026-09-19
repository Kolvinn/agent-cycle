"""The project's operation log — where the graph lives.

> "the networkx graph as basically a thought graph that is rooted in the user
> approval ... such that only the correct data is maintained across sessions"

One append-only JSONL file per project, ``sessions/graph/ops.jsonl``. Every
record a frame authors is one line, stamped with the session that wrote it
and when. Every session of the project reads and writes the same file, so a
``/fork`` shares the graph (it forks the conversation and the cycle, nothing
else), and two processes are serialised by a file lock.

**The log is the store; the ledger is the materialised records; the view is
the graph.** :class:`Ledger` is what replaying the log produces: every record
kind keyed by its id, in the order first written, with a later line of the
same id replacing the earlier one. That last rule is what makes a re-run
frame harmless — a frame that appended and then failed to checkpoint re-runs
and writes the same ids again. The alterations (``state.OPERATIONS``) are
kept in log order and applied on top by ``thought.build``; the store caches
that built view and rebuilds it only when the log has grown.

**Nothing is ever removed from the file.** "Why is this here" is answerable
by reading it top to bottom.

The in-memory ledger is refreshed from the file's tail on every read, so a
line another process appended is seen on the next ``ledger()`` call without
re-reading the whole file.
"""

from __future__ import annotations

import fcntl
import json
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

import networkx as nx
from pydantic import BaseModel

from . import thought
from .state import (
    OPERATIONS,
    Antithesis,
    Assumption,
    Closure,
    Compression,
    Counts,
    Cycle,
    Decision,
    EdgeAdded,
    EdgeUpdated,
    EvidenceMoved,
    Explicit,
    Finding,
    Merge,
    NodeAdded,
    NodeUpdated,
    Parked,
    ProposedWrite,
    Reasoning,
    RelationKind,
    SpendEntry,
    Supersession,
    Tombstone,
)

#: Line kind -> record type. The name is what a reader of the file sees.
KINDS: dict[str, type[BaseModel]] = {
    "cycle": Cycle,
    "explicit": Explicit,
    "parked": Parked,
    "assumption": Assumption,
    "antithesis": Antithesis,
    "finding": Finding,
    "reasoning": Reasoning,
    "spend": SpendEntry,
    "proposed": ProposedWrite,
    "decision": Decision,
    "node_added": NodeAdded,
    "edge_added": EdgeAdded,
    "relation_kind": RelationKind,
    "node_updated": NodeUpdated,
    "edge_updated": EdgeUpdated,
    "tombstone": Tombstone,
    "merge": Merge,
    "evidence_moved": EvidenceMoved,
    "closure": Closure,
    "supersession": Supersession,
    "compression": Compression,
}
_KIND_OF: dict[type[BaseModel], str] = {t: k for k, t in KINDS.items()}
assert set(OPERATIONS) <= set(_KIND_OF), "every operation record needs a line kind"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Ledger:
    """Every record in the log, materialised. Keyed by id where the record has
    one, so a later line replaces an earlier; in write order otherwise."""

    cycles: dict[int, Cycle] = field(default_factory=dict)
    explicits: dict[str, Explicit] = field(default_factory=dict)
    assumptions: dict[str, Assumption] = field(default_factory=dict)
    antitheses: dict[str, Antithesis] = field(default_factory=dict)
    findings: dict[str, Finding] = field(default_factory=dict)
    proposed: dict[str, ProposedWrite] = field(default_factory=dict)
    #: By the write they answer.
    decisions: dict[str, Decision] = field(default_factory=dict)
    parked: list[Parked] = field(default_factory=list)
    reasoning: list[Reasoning] = field(default_factory=list)
    spend: list[SpendEntry] = field(default_factory=list)
    #: The graph's operations (``state.OPERATIONS``), in log order. Applied
    #: on top of the base records by ``thought.build``.
    ops: list[BaseModel] = field(default_factory=list)
    #: Relations added to this project's vocabulary, by name.
    relation_kinds: dict[str, RelationKind] = field(default_factory=dict)
    #: How many lines have been applied — the log's length as this ledger saw it.
    lines: int = 0

    def apply(self, record: BaseModel) -> None:
        match record:
            case Cycle():
                self.cycles[record.number] = record
            case Explicit():
                self.explicits[record.id] = record
            case Assumption():
                self.assumptions[record.id] = record
            case Antithesis():
                self.antitheses[record.id] = record
            case Finding():
                self.findings[record.id] = record
            case ProposedWrite():
                self.proposed[record.id] = record
            case Decision():
                self.decisions[record.write_id] = record
            case Parked():
                self.parked.append(record)
            case Reasoning():
                self.reasoning.append(record)
            case SpendEntry():
                self.spend.append(record)
            case RelationKind():
                self.relation_kinds[record.name] = record
                self.ops.append(record)
            case _ if isinstance(record, OPERATIONS):
                self.ops.append(record)
        self.lines += 1

    # --- selection ----------------------------------------------------------

    @property
    def last_cycle(self) -> int:
        return max(self.cycles) if self.cycles else 0

    def question_of(self, cycle: int) -> str:
        c = self.cycles.get(cycle)
        return c.question if c is not None else ""

    def assumptions_of(self, cycle: int) -> list[Assumption]:
        """One cycle's assumptions, in the order they were named."""
        return [a for a in self.assumptions.values() if a.cycle == cycle]

    def antitheses_of(self, cycle: int) -> list[Antithesis]:
        return [x for x in self.antitheses.values() if x.cycle == cycle]

    def findings_on(self, node_id: str) -> list[Finding]:
        return [f for f in self.findings.values() if f.node_id == node_id]

    def has_records_for(self, cycle: int) -> bool:
        """Whether any frame has written to this cycle yet."""
        authored: Iterable[BaseModel] = (
            *self.assumptions.values(),
            *self.antitheses.values(),
            *self.findings.values(),
            *self.reasoning,
            *self.ops,
        )
        return any(getattr(r, "cycle", None) == cycle for r in authored)

    def refused(self) -> list[ProposedWrite]:
        """Alterations the user said no to, across every cycle."""
        return [w for w in self.proposed.values() if (d := self.decisions.get(w.id)) is not None and not d.approved]

    def approved(self) -> list[ProposedWrite]:
        return [w for w in self.proposed.values() if (d := self.decisions.get(w.id)) is not None and d.approved]

    def counts(self, cycle: int) -> Counts:
        """This cycle's record counts, so a turn continues the id sequence."""
        ops = [o for o in self.ops if getattr(o, "cycle", None) == cycle]
        return Counts(
            findings=sum(1 for f in self.findings.values() if f.cycle == cycle),
            proposals=sum(1 for p in self.proposed.values() if p.cycle == cycle),
            explicits=sum(1 for e in self.explicits.values() if e.cycle == cycle),
            entities=sum(1 for o in ops if isinstance(o, NodeAdded) and o.kind == "entity"),
            claims=sum(1 for o in ops if isinstance(o, NodeAdded) and o.kind == "claim"),
            edges=sum(1 for o in ops if isinstance(o, EdgeAdded)),
            summaries=sum(1 for o in ops if isinstance(o, Compression)),
        )


def encode(record: BaseModel, session: str, at: str = "") -> str:
    kind = _KIND_OF[type(record)]
    return json.dumps({"kind": kind, "session": session, "at": at or _now(), "data": record.model_dump(mode="json")})


def decode(line: str) -> BaseModel | None:
    """One line as a record, or ``None`` for a blank, broken or unknown line —
    a log survives a bad line rather than refusing to load."""
    line = line.strip()
    if not line:
        return None
    try:
        obj = json.loads(line)
        model = KINDS[obj["kind"]]
        return model.model_validate(obj["data"])
    except Exception:
        return None


class GraphStore:
    """The op log. ``path=None`` keeps it in memory, for tests and rendering."""

    def __init__(self, path: Path | None) -> None:
        self.path = Path(path) if path is not None else None
        self._ledger = Ledger()
        self._offset = 0
        self._view: nx.MultiDiGraph | None = None
        self._view_lines = -1
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.touch()

    # --- the file ------------------------------------------------------------

    @contextmanager
    def _locked(self, exclusive: bool) -> Iterator[None]:
        if self.path is None:
            yield
            return
        lock = self.path.with_suffix(".lock")
        with open(lock, "a+") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
            try:
                yield
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)

    def _catch_up(self) -> None:
        """Apply whatever the file holds past what this ledger has seen."""
        if self.path is None:
            return
        size = self.path.stat().st_size
        if size < self._offset:  # truncated behind our back: start over
            self._ledger = Ledger()
            self._offset = 0
        if size == self._offset:
            return
        with open(self.path, "rb") as fh:
            fh.seek(self._offset)
            chunk = fh.read()
        # Only whole lines: a writer in another process may be mid-line.
        cut = chunk.rfind(b"\n") + 1
        for raw in chunk[:cut].splitlines():
            record = decode(raw.decode("utf-8", errors="replace"))
            if record is not None:
                self._ledger.apply(record)
        self._offset += cut

    def _write(self, lines: list[str]) -> None:
        """Append lines to the file. Called under the exclusive lock."""
        if self.path is None:
            return
        with open(self.path, "ab") as fh:
            fh.write(("\n".join(lines) + "\n").encode("utf-8"))
            fh.flush()
        self._offset += sum(len(line.encode("utf-8")) + 1 for line in lines)

    # --- reading -------------------------------------------------------------

    def ledger(self) -> Ledger:
        """The log as it stands now, this and every other session's lines."""
        with self._locked(exclusive=False):
            self._catch_up()
        return self._ledger

    def view(self) -> nx.MultiDiGraph:
        """The thought graph over the log as it stands. Cached until the log
        grows. **Shared**: a caller that wants to apply anything copies it."""
        ledger = self.ledger()
        if self._view is None or self._view_lines != ledger.lines:
            self._view = thought.build(ledger)
            self._view_lines = ledger.lines
        return self._view

    # --- writing -------------------------------------------------------------

    def append(self, session: str, records: Iterable[BaseModel]) -> int:
        """Append the records as one locked write. Returns how many."""
        records = list(records)
        if not records:
            return 0
        with self._locked(exclusive=True):
            self._catch_up()
            at = _now()
            self._write([encode(r, session, at) for r in records])
            for r in records:
                self._ledger.apply(r)
        return len(records)

    def open_cycle(self, session: str, question: str) -> int:
        """Allocate this session's next cycle number on the shared graph.

        A cycle this session opened on the same question that no frame has yet
        written to is handed back rather than opened again: that is a frame
        re-running after it opened the cycle and then failed or was
        interrupted, and it owns its reservation.
        """
        with self._locked(exclusive=True):
            self._catch_up()
            ledger = self._ledger
            last = ledger.cycles.get(ledger.last_cycle)
            if (
                last is not None
                and last.session == session
                and last.question == question
                and not ledger.has_records_for(last.number)
            ):
                return last.number
            record = Cycle(number=ledger.last_cycle + 1, session=session, question=question)
            self._write([encode(record, session)])
            ledger.apply(record)
            return record.number
