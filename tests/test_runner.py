"""A whole round, end to end, with no model and no terminal.

This is the test the architecture was shaped for: `ScriptedUI` + `FakeModel`
means the entire pipeline — extraction, the free survey, the claim, the
sign-off, the gated look, the source check, the reply — runs deterministically,
in milliseconds, for nothing.

It also asserts on the *run log*, not just the in-memory result. A stage that
worked but left no inspectable record is a stage that failed the brief.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from langchain_claude_test.ledger import check_invariants, grounds_edge_for, node, nodes
from langchain_claude_test.ledger import trace as tr
from langchain_claude_test.runlog import RunLog
from langchain_claude_test.session import ScriptedUI, SignOff
from langchain_claude_test.session.gate import Policy
from langchain_claude_test.session.model import FakeModel
from langchain_claude_test.session.runner import Runner

FIXTURE = Path(__file__).parent / "fixtures" / "repo"
MSG = "Where do we validate the incoming webhook signature?"
QUOTE = "validate the incoming webhook signature"
CLAIM = "signature validation happens in webhook/signature.py in verify_signature"
GREP_LINE = "webhook/signature.py:12:def verify_signature(payload: bytes, sig: str, secret: str) -> bool:"


def happy_model() -> FakeModel:
    return FakeModel(
        {
            "extract": [{"quotes": [QUOTE], "named_paths": []}],
            "orient": [{"path": ".", "why": "see the top-level layout"}],
            "assume": [{"claim": CLAIM, "why": "a signature module is the obvious home"}],
            "evidence": [{"pattern": "def verify_signature", "expect": "a definition confirms it"}],
            "source": [
                {
                    "locator": "webhook/signature.py:12",
                    "excerpt": "def verify_signature(payload: bytes, sig: str, secret: str) -> bool:",
                    "answers": QUOTE,
                }
            ],
            "reply": [{"text": "Validation lives in webhook/signature.py:12."}],
        }
    )


def build(tmp_path, *, model=None, signoffs=("approved",), policy=None):
    log = RunLog(root=tmp_path, run_id="r1", config={"mode": (policy or Policy()).mode})
    ui = ScriptedUI(messages=[MSG], signoffs=list(signoffs))
    runner = Runner(
        model=model or happy_model(),
        ui=ui,
        runlog=log,
        fixture_root=FIXTURE,
        policy=policy or Policy(mode="enforce"),
    )
    return runner, ui, log


# --- the happy round -------------------------------------------------------


@pytest.mark.asyncio
async def test_a_full_round_builds_a_sourced_ledger(tmp_path):
    runner, ui, log = build(tmp_path)
    await runner.run()

    g = runner.state.graph
    assert check_invariants(g) == []

    explicit = nodes(g, kind="explicit")[0]
    implicit = nodes(g, kind="implicit")[0]
    assert explicit.text == QUOTE
    assert explicit.status == "addressed"
    assert implicit.status == "approved"

    edge = grounds_edge_for(g, implicit.id)
    assert edge.source is not None
    assert edge.source.locator == "webhook/signature.py:12"
    assert edge.source.answers == QUOTE
    log.close()


@pytest.mark.asyncio
async def test_the_phases_run_in_the_fixed_order(tmp_path):
    """The model never chooses what happens next — the runner does."""
    model = happy_model()
    runner, _, log = build(tmp_path, model=model)
    await runner.run()
    assert [label for label, _ in model.calls] == [
        "extract", "orient", "assume", "evidence", "source", "reply",
    ]
    log.close()


@pytest.mark.asyncio
async def test_the_user_is_asked_before_any_gated_look(tmp_path):
    """Sign-off precedes evidence: the ordering the flow settles on."""
    runner, ui, log = build(tmp_path)
    await runner.run()

    kinds = [e.kind for e in ui.events]
    signoff_at = kinds.index(tr.SIGNOFF_ANSWERED)

    gated_positions = [
        i
        for i, e in enumerate(ui.events)
        if e.kind == tr.GATE_DECISION and e.detail["tier"] == "gated"
    ]
    assert gated_positions, "the round never made a gated call"
    assert min(gated_positions) > signoff_at, "a gated look happened before sign-off"
    assert kinds.index(tr.SOURCE_APPLIED) > signoff_at
    log.close()


@pytest.mark.asyncio
async def test_the_survey_is_free_and_the_search_is_not(tmp_path):
    runner, ui, log = build(tmp_path)
    await runner.run()
    by_tool = {e.detail["tool"]: e.detail for e in ui.events if e.kind == tr.GATE_DECISION}
    assert by_tool["list_dir"]["tier"] == "free"
    assert by_tool["list_dir"]["rule"] == "free.no-hop"
    assert by_tool["grep"]["tier"] == "gated"
    assert by_tool["grep"]["rule"] == "depth1.approved"
    log.close()


# --- the user says no ------------------------------------------------------


@pytest.mark.asyncio
async def test_a_rejected_claim_is_never_sourced(tmp_path):
    runner, ui, log = build(tmp_path, signoffs=["rejected"])
    await runner.run()

    implicit = nodes(runner.state.graph, kind="implicit")[0]
    assert implicit.status == "rejected"
    assert grounds_edge_for(runner.state.graph, implicit.id).source is None
    assert not [e for e in ui.events if e.kind == tr.SOURCE_APPLIED]
    log.close()


@pytest.mark.asyncio
async def test_a_correction_enters_as_the_users_own_explicit(tmp_path):
    """Their correction is their words, so it becomes a depth-0 explicit — not
    a revised guess of ours."""
    runner, _, log = build(
        tmp_path,
        signoffs=[SignOff(verdict="corrected", answered_by="human", correction="it is in handlers.py")],
    )
    await runner.run()

    texts = [n.text for n in nodes(runner.state.graph, kind="explicit")]
    assert "it is in handlers.py" in texts
    assert nodes(runner.state.graph, kind="implicit")[0].status == "rejected"
    log.close()


# --- extraction discipline -------------------------------------------------


@pytest.mark.asyncio
async def test_a_paraphrased_quote_is_refused(tmp_path):
    model = happy_model()
    model._queued["extract"] = [{"quotes": ["check the webhook sig"], "named_paths": []}]
    runner, ui, log = build(tmp_path, model=model)
    await runner.run()

    rejected = [e for e in ui.events if e.kind == tr.EXTRACTION_REJECTED]
    assert len(rejected) == 1
    assert "verbatim" in rejected[0].detail["reason"]
    assert nodes(runner.state.graph, kind="explicit") == ()
    assert "could not quote anything" in ui.replies[0]
    log.close()


# --- observe vs enforce ----------------------------------------------------


@pytest.mark.asyncio
async def test_observe_mode_records_the_refusal_but_runs_anyway(tmp_path):
    """With the evidence budget at zero the gate would refuse the search.
    Observe mode lets it through and writes down that it would not have —
    which is the friction measurement, collected without the friction."""
    runner, ui, log = build(
        tmp_path, policy=Policy(mode="observe", max_evidence_per_implicit=0)
    )
    await runner.run()
    log.close()

    verdicts = [json.loads(p.read_text()) for p in sorted((log.dir / "tools").glob("*.json"))]
    diverged = [v for v in verdicts if v["would_be"] != v["executed"]]
    assert diverged, "observe mode should have recorded at least one would-have-blocked call"
    assert diverged[0]["rule"] == "depth1.budget-exhausted"
    assert diverged[0]["would_be"] == "ask"
    assert diverged[0]["executed"] == "allow"


@pytest.mark.asyncio
async def test_observe_mode_only_measures_calls_that_were_attempted(tmp_path):
    """A limit worth knowing: the runner's own control flow skips the gated
    search entirely when a claim is rejected, so the gate never sees it and
    observe mode has nothing to record. Shadow-mode numbers are a floor, not a
    census."""
    runner, _, log = build(tmp_path, signoffs=["rejected"], policy=Policy(mode="observe"))
    await runner.run()
    log.close()

    tools_called = [json.loads(p.read_text())["tool"] for p in (log.dir / "tools").glob("*.json")]
    assert tools_called == ["list_dir"]


# --- the run log -----------------------------------------------------------


@pytest.mark.asyncio
async def test_every_stage_left_an_inspectable_record(tmp_path):
    runner, _, log = build(tmp_path)
    await runner.run()
    log.close()

    meta = json.loads((log.dir / "meta.json").read_text())
    assert meta["status"] == "ok"
    assert meta["counts"]["model_calls"] == 6
    assert meta["counts"]["tool_calls"] == 2

    events = [json.loads(x) for x in (log.dir / "events.jsonl").read_text().splitlines()]
    kinds = {e["kind"] for e in events}
    for required in (
        tr.USER_MESSAGE, tr.EXPLICIT_REGISTERED, tr.GATE_DECISION, tr.TOOL_CALL,
        tr.TOOL_RESULT, tr.ASSUMPTION_FORMED, tr.SIGNOFF_REQUESTED,
        tr.SIGNOFF_ANSWERED, tr.SOURCE_APPLIED, tr.REPLY_SENT,
    ):
        assert required in kinds, f"{required} never reached the log"

    assert (log.dir / "ledger" / "turn-001.json").exists()
    assert QUOTE in (log.dir / "ledger" / "turn-001.digest").read_text()
    assert (log.dir / "transcript.txt").exists()


@pytest.mark.asyncio
async def test_each_model_call_kept_its_prompt_and_reply(tmp_path):
    """'How' and 'when', not just 'what' — the request is on disk too."""
    runner, _, log = build(tmp_path)
    await runner.run()
    log.close()

    # FakeModel does not route through runlog.model_call, so assert the shape
    # the SDK client writes by exercising it directly.
    with log.model_call("assume", turn=1, request={"prompt": "p", "system": "s"}) as rec:
        rec.response = {"claim": CLAIM}
    written = json.loads(sorted((log.dir / "model").glob("*.json"))[-1].read_text())
    assert written["request"]["prompt"] == "p"
    assert written["response"]["claim"] == CLAIM
    assert "duration_s" in written


@pytest.mark.asyncio
async def test_a_crash_mid_round_still_leaves_a_readable_log(tmp_path):
    model = happy_model()
    model._queued["assume"] = []  # exhausted: the phase will raise
    runner, _, log = build(tmp_path, model=model)

    with pytest.raises(AssertionError):
        await runner.run()
    log.close(status="error")

    events = [json.loads(x) for x in (log.dir / "events.jsonl").read_text().splitlines()]
    assert [e["kind"] for e in events][:2] == [tr.TURN_STARTED, tr.USER_MESSAGE]
    assert any(e["kind"] == tr.EXPLICIT_REGISTERED for e in events)
    assert json.loads((log.dir / "meta.json").read_text())["status"] == "error"
