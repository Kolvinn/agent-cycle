"""The durable record.

These tests exist because the log is only worth having if it survives the
things worth logging. Two of them deliberately crash a run and then assert the
disk still explains what happened.
"""

from __future__ import annotations

import json

import pytest

from langchain_claude_test.ledger import (
    NewExplicit,
    NewImplicit,
    new_ledger,
    form_implicit,
    register_explicit,
)
from langchain_claude_test.runlog import RunLog

MSG = "Where do we validate the incoming webhook signature?"
QUOTE = "validate the incoming webhook signature"


@pytest.fixture
def log(tmp_path):
    return RunLog(root=tmp_path, run_id="testrun", config={"mode": "observe"})


@pytest.fixture
def graph():
    g = new_ledger()
    r = register_explicit(
        NewExplicit(quote=QUOTE, start=MSG.index(QUOTE)),
        current_graph=g, turn=1, message_text=MSG,
    )
    r = form_implicit(
        NewImplicit(claim="validation happens in handlers.py", grounded_in=r.node_ids[0]),
        current_graph=r.graph, turn=1,
    )
    return r.graph


def _lines(path):
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


# --- structure -------------------------------------------------------------


def test_run_directory_is_laid_out_up_front(log):
    for sub in ("model", "tools", "ledger"):
        assert (log.dir / sub).is_dir()
    assert (log.dir / "events.jsonl").exists()
    meta = json.loads((log.dir / "meta.json").read_text())
    assert meta["status"] == "running"
    assert meta["config"] == {"mode": "observe"}
    assert meta["env"]["python"]


def test_events_hit_disk_immediately(log):
    """Not on close — immediately. A run that dies mid-turn must still have
    every event up to the death readable."""
    log.event("assumption_formed", turn=1, node_id="abc", claim="x")
    rows = _lines(log.dir / "events.jsonl")
    assert len(rows) == 1
    assert rows[0]["kind"] == "assumption_formed"
    assert rows[0]["detail"]["claim"] == "x"
    assert rows[0]["at"]


def test_events_keep_order_and_sequence(log):
    for i in range(5):
        log.event("tool_call", turn=1, tool=f"t{i}")
    rows = _lines(log.dir / "events.jsonl")
    assert [r["seq"] for r in rows] == [0, 1, 2, 3, 4]


# --- model calls -----------------------------------------------------------


def test_request_is_written_before_the_call_runs(log):
    """So a hang or a kill still leaves behind exactly what was sent."""
    with log.model_call("extract", turn=1, request={"prompt": "hello"}) as rec:
        on_disk = json.loads((log.dir / "model" / "call-0001.json").read_text())
        assert on_disk["status"] == "in_flight"
        assert on_disk["request"] == {"prompt": "hello"}
        rec.response = {"ok": True}

    final = json.loads((log.dir / "model" / "call-0001.json").read_text())
    assert final["status"] == "ok"
    assert final["response"] == {"ok": True}
    assert final["duration_s"] >= 0


def test_a_failing_model_call_records_the_failure(log):
    with pytest.raises(RuntimeError):
        with log.model_call("extract", turn=1, request={"prompt": "x"}):
            raise RuntimeError("safeguards flagged this message")

    final = json.loads((log.dir / "model" / "call-0001.json").read_text())
    assert final["status"] == "error"
    assert "safeguards flagged" in final["error"]


def test_unserialisable_payloads_degrade_instead_of_exploding(log):
    """A logger that throws while recording a failure is worse than useless."""
    with log.model_call("extract", turn=1, request={"obj": object()}) as rec:
        rec.response = {"fn": lambda: 1}
    final = json.loads((log.dir / "model" / "call-0001.json").read_text())
    assert "object" in str(final["request"])


# --- tool calls ------------------------------------------------------------


def test_tool_call_records_the_gate_verdict_and_its_rule(log):
    with log.tool_call("grep", turn=1, args={"pattern": "x"}, tier="gated") as rec:
        rec.would_be, rec.executed = "ask", "allow"
        rec.reason = "observe mode — executed anyway"
        rec.rule = "depth1.read"
        rec.for_node_id = "node-1"
        rec.result = "one match"

    final = json.loads((log.dir / "tools" / "call-0001.json").read_text())
    assert (final["would_be"], final["executed"]) == ("ask", "allow")
    assert final["rule"] == "depth1.read"
    assert final["for_node_id"] == "node-1"
    assert final["tier"] == "gated"


def test_observe_mode_gap_is_recoverable_from_disk(log):
    """The friction measurement: how often the gate would have fired."""
    for would, did in (("allow", "allow"), ("ask", "allow"), ("block", "allow")):
        with log.tool_call("grep", turn=1, args={}) as rec:
            rec.would_be, rec.executed = would, did

    files = sorted((log.dir / "tools").glob("*.json"))
    verdicts = [json.loads(f.read_text()) for f in files]
    diverged = [v for v in verdicts if v["would_be"] != v["executed"]]
    assert len(diverged) == 2


# --- snapshots -------------------------------------------------------------


def test_snapshot_writes_all_three_forms(log, graph):
    log.snapshot(graph, turn=1)
    base = log.dir / "ledger"
    assert (base / "turn-001.json").exists()
    assert (base / "turn-001.digest").exists()
    assert (base / "turn-001.mmd").exists()

    data = json.loads((base / "turn-001.json").read_text())
    assert len(data["nodes"]) == 2
    assert len(data["edges"]) == 1
    assert data["edges"][0]["kind"] == "grounds"
    assert QUOTE in (base / "turn-001.digest").read_text()
    assert "flowchart LR" in (base / "turn-001.mmd").read_text()


def test_snapshot_records_whether_the_state_was_legal(log, graph):
    """A snapshot of a corrupt ledger must say so, not archive it as fine."""
    log.snapshot(graph, turn=1)
    data = json.loads((log.dir / "ledger" / "turn-001.json").read_text())
    assert data["invariants"] == []


def test_snapshots_are_kept_per_turn(log, graph):
    log.snapshot(graph, turn=1)
    log.snapshot(graph, turn=2)
    assert len(list((log.dir / "ledger").glob("*.json"))) == 2


# --- close -----------------------------------------------------------------


def test_close_writes_transcript_and_counts(log, graph):
    log.event("turn_started", turn=1)
    log.event("explicit_registered", turn=1, node_id="n", quote=QUOTE)
    with log.model_call("extract", turn=1, request={}):
        pass
    log.close()

    assert QUOTE in (log.dir / "transcript.txt").read_text()
    meta = json.loads((log.dir / "meta.json").read_text())
    assert meta["status"] == "ok"
    assert meta["counts"]["events"] == 2
    assert meta["counts"]["model_calls"] == 1
    assert meta["counts"]["by_kind"]["explicit_registered"] == 1
    assert meta["ended_at"]


def test_a_crashed_run_is_marked_and_explained(tmp_path):
    with pytest.raises(ValueError):
        with RunLog(root=tmp_path, run_id="boom") as log:
            log.event("turn_started", turn=1)
            raise ValueError("the wheels came off")

    meta = json.loads((tmp_path / "boom" / "meta.json").read_text())
    assert meta["status"] == "error"

    rows = _lines(tmp_path / "boom" / "events.jsonl")
    assert rows[-1]["kind"] == "run_failed"
    assert "wheels came off" in rows[-1]["detail"]["error"]
    assert (tmp_path / "boom" / "transcript.txt").exists()


def test_run_ids_do_not_collide(tmp_path):
    a = RunLog(root=tmp_path)
    b = RunLog(root=tmp_path, run_id=a.run_id + "-b")
    assert a.dir != b.dir
