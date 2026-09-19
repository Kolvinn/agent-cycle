"""The op log: one file every session shares, replayed into a ledger."""

from __future__ import annotations

from pathlib import Path

from langchain_claude_test.app.graph.state import Assumption, Decision, Finding, ProposedWrite
from langchain_claude_test.app.graph.store import GraphStore, decode


def assumption(id: str, cycle: int, claim: str = "c") -> Assumption:
    return Assumption(id=id, cycle=cycle, claim=claim, inferred_because="b", moved_by="m")


def test_two_stores_on_one_file_see_each_others_lines(tmp_path: Path):
    log = tmp_path / "graph" / "ops.jsonl"
    one, two = GraphStore(log), GraphStore(log)

    # session one opens cycle 1 and writes; session two opens the next cycle
    assert one.open_cycle("one", "q?") == 1
    one.append("one", [assumption("a1.1", 1)])
    assert two.open_cycle("two", "r?") == 2
    two.append("two", [assumption("a2.1", 2)])

    # each sees the other's lines on its next read, without a restart
    assert list(one.ledger().assumptions) == ["a1.1", "a2.1"]
    assert list(two.ledger().assumptions) == ["a1.1", "a2.1"]
    assert one.ledger().cycles[2].session == "two"

    # a third store, opened later, replays the whole file
    fresh = GraphStore(log).ledger()
    assert fresh.assumptions_of(1)[0].id == "a1.1" and fresh.last_cycle == 2
    assert fresh.lines == 4
    # every line says who wrote it
    assert [line.split('"session": "')[1].split('"')[0] for line in log.read_text().splitlines()] == ["one", "one", "two", "two"]


def test_a_later_line_with_the_same_id_replaces_the_earlier(tmp_path: Path):
    store = GraphStore(tmp_path / "ops.jsonl")
    store.open_cycle("s", "q")
    store.append("s", [assumption("a1.1", 1, "first"), assumption("a1.2", 1)])
    store.append("s", [assumption("a1.1", 1, "second")])
    ledger = store.ledger()
    assert [a.claim for a in ledger.assumptions.values()] == ["second", "c"]  # position kept, text replaced
    assert ledger.lines == 4  # nothing removed from the file


def test_a_cycle_this_session_opened_and_never_wrote_to_is_handed_back(tmp_path: Path):
    store = GraphStore(tmp_path / "ops.jsonl")
    assert store.open_cycle("s", "q") == 1
    # the frame re-runs: same session, same question, nothing written — same cycle
    assert store.open_cycle("s", "q") == 1
    # a different question is a new cycle
    assert store.open_cycle("s", "other") == 2
    # another session never inherits a reservation
    assert store.open_cycle("t", "other") == 3
    # once written to, the cycle is taken
    store.append("s", [assumption("a3.1", 3)])
    assert store.open_cycle("t", "other") == 4


def test_the_ledger_selects_by_cycle_and_by_decision():
    store = GraphStore(None)
    store.open_cycle("s", "q")
    store.append(
        "s",
        [
            assumption("a1.1", 1),
            Finding(id="f1.1", node_id="q1", cycle=1, locator="cat a", excerpt="A", price=0),
            ProposedWrite(id="p1.1", cycle=1, write="close_node", target_id="a1.1"),
            Decision(write_id="p1.1", approved=False, words="no"),
            ProposedWrite(id="p1.2", cycle=1, write="propose_fact"),
            Decision(write_id="p1.2", approved=True),
        ],
    )
    ledger = store.ledger()
    assert [w.id for w in ledger.refused()] == ["p1.1"] and [w.id for w in ledger.approved()] == ["p1.2"]
    assert ledger.counts(1).findings == 1 and ledger.counts(1).proposals == 2 and ledger.counts(2).findings == 0
    assert ledger.findings_on("q1")[0].excerpt == "A" and ledger.has_records_for(1) and not ledger.has_records_for(2)


def test_a_broken_line_is_skipped_not_fatal(tmp_path: Path):
    log = tmp_path / "ops.jsonl"
    store = GraphStore(log)
    store.open_cycle("s", "q")
    with open(log, "a") as fh:
        fh.write("{not json\n")
        fh.write('{"kind": "martian", "session": "s", "at": "", "data": {}}\n')
    store.append("s", [assumption("a1.1", 1)])
    assert decode("{not json") is None
    ledger = GraphStore(log).ledger()
    assert list(ledger.assumptions) == ["a1.1"] and ledger.lines == 2
