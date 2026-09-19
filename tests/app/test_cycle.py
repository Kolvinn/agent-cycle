"""A whole cycle, end to end, through the real compiled graph and a real SQLite
checkpointer, with the model replaced by a script and the human by a script.

This is the test the architecture was shaped for. Everything except the
subprocess runs: the entry router, the three frames, the meter, the surface,
the hooks, the gate, the tools, the records, the op log, the package,
persistence, and a second cycle opened on the carried graph. It also asserts on
what the user *would have seen* through the sink.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from langchain_claude_test.app.config import Budgets
from langchain_claude_test.app.graph import ControlContext, compile_cycle, package, thought
from langchain_claude_test.app.graph.graph import sqlite_checkpointer
from langchain_claude_test.app.graph.state import GraphState
from langchain_claude_test.app.graph.store import GraphStore
from langchain_claude_test.app.graph.surface import GATED_TOOLS
from langchain_claude_test.app.harness import events as ev
from langchain_claude_test.app.harness.protocol import FrameInterrupted
from langchain_claude_test.app.harness.scripted import Call, ScriptedApprover, ScriptedHarness, Turn

QUESTION = "Where do we validate the incoming webhook signature?"
FILE_A = "     1→def verify_signature(payload, sig):\n     2→    return hmac.compare_digest(sig, sign(payload))\n"
FILE_B = "     1→def handle(request):\n     2→    if not verify_signature(request.body, request.headers['X-Sig']):\n     3→        return 401\n"


def assumption(n: int, evidence: list[str] | None = None) -> dict:
    return {
        "claim": f"assumption {n}",
        "inferred_because": "the request names a signature",
        "moved_by": "reading the handler",
        "evidence": evidence or [],
    }


def script() -> dict[str, list[Turn]]:
    return {
        "orientate": [
            # the survey: a glob (1), two reads (2 each), one finding kept on the
            # question, one refused because its excerpt was never returned; the
            # first assumption cites the kept finding, the second cites an id
            # that does not exist and loses it
            Turn(
                payload={
                    "overview": "a small webhook service",
                    "assumptions": [assumption(1, ["f1.1"]), assumption(2, ["f9.9"])],
                },
                calls=(
                    Call("Glob", {"pattern": "**/*.py"}, result="webhook/signature.py\nwebhook/handlers.py"),
                    Call("Read", {"file_path": "webhook/signature.py"}, result=FILE_A),
                    # attach_finding runs the command itself; the scripted result is its output
                    Call("mcp__graph__attach_finding", {"target": "", "run": "sed -n '1,1p' webhook/signature.py"}, result="def verify_signature(payload, sig):"),
                    # a mistake, overwritten in place: same id, new output
                    Call("mcp__graph__attach_finding", {"target": "", "run": "sed -n '1,2p' webhook/signature.py", "replace": "f1.1"}, result=FILE_A),
                    Call("Read", {"file_path": "webhook/handlers.py"}, result=FILE_B),
                    # a command the executor refuses records nothing
                    Call("mcp__graph__attach_finding", {"target": "", "run": "rm -rf webhook"}, result="REFUSED: 'rm' is not an allowed command."),
                    # overwriting a finding this turn did not create is refused
                    Call("mcp__graph__attach_finding", {"target": "", "run": "cat webhook/handlers.py", "replace": "f9.9"}, result=FILE_B),
                ),
            )
        ],
        "antithesis": [
            Turn(
                payload={
                    "antitheses": [
                        {"claim": "rival of 1", "inferred_because": "b", "moved_by": "c"},
                        {"claim": "rival of 2", "inferred_because": "b", "moved_by": "c"},
                    ],
                    "reasoning": "attacked both",
                },
                calls=(
                    Call("Read", {"file_path": "webhook/handlers.py"}, result=FILE_B),
                    Call("mcp__graph__attach_finding", {"target": "2", "run": "grep -n 401 webhook/handlers.py"}, result="3:        return 401"),
                    # a Bash call does not exist in this frame: refused before pricing
                    Call("Bash", {"command": "rm -rf /"}, result="should never run"),
                ),
            )
        ],
        "synthesis": [
            # the opening exchange is text: a gated call does not exist yet and is refused
            Turn(
                payload={"text": "Here is what I found. I did not look at the tests. I suggest closing a1.1."},
                calls=(Call("mcp__graph__close_node", {"target": "a1.1", "verdict": "confirmed", "because": "too soon"}),),
            ),
        ],
    }


async def _run(graph, ctx, thread: str, **update):
    config = {"configurable": {"thread_id": thread}}
    return await graph.ainvoke(update, config, context=ctx)


@pytest.mark.asyncio
async def test_a_full_cycle_then_a_reply_then_a_second_cycle(tmp_path: Path):
    db = tmp_path / "checkpoints.sqlite"
    log = tmp_path / "graph" / "ops.jsonl"
    approver = ScriptedApprover()
    harness = ScriptedHarness(script=script(), approver=approver)
    ctx = ControlContext(harness=harness, budgets=Budgets(), store=GraphStore(log), session="t1")

    async with sqlite_checkpointer(db) as saver:
        graph = compile_cycle(saver)

        # --- cycle 1 -----------------------------------------------------------
        final = await _run(graph, ctx, "t1", prompt=QUESTION, advance=True)
        state = GraphState.model_validate(final)

        ledger = ctx.store.ledger()

        assert state.cycle == 1 and state.stage == "synthesis" and state.advance is False
        assert state.question == QUESTION and state.said == [QUESTION]
        # the cycle is the graph's, opened by this session on this question
        assert ledger.cycles[1].session == "t1" and ledger.cycles[1].question == QUESTION
        assert list(ledger.assumptions) == ["a1.1", "a1.2"]
        assert ledger.assumptions["a1.1"].evidence == ("f1.1",) and ledger.assumptions["a1.2"].evidence == ()
        assert state.orientation == "a small webhook service"
        # every frame continued the one conversation the first frame opened
        assert state.conversation == "scripted-1"
        assert all(r.conversation == "scripted-1" for r in harness.requests[1:])
        assert harness.requests[0].conversation == ""  # the cycle boundary opened fresh

        # the rivals: one per assumption, in order, aimed at the right assumption
        assert [(x.id, x.target) for x in ledger.antitheses.values()] == [("x1.1", "a1.1"), ("x1.2", "a1.2")]

        # findings: the survey's on the question (overwritten once, same id), the rival's on x1.2; free
        assert [(f.id, f.node_id, f.price) for f in ledger.findings.values()] == [("f1.1", "q1", 0), ("f1.2", "x1.2", 0)]
        assert ledger.findings["f1.1"].locator == "sed -n '1,2p' webhook/signature.py" and ledger.findings["f1.1"].excerpt == FILE_A
        assert ledger.findings["f1.2"].excerpt == "3:        return 401"

        # spend: 1 (glob) + 2 + 2 (the survey's reads) of a 5 + 5·3 pool; 2 (antithesis read)
        by_pool: dict[str, int] = {}
        for e in ledger.spend:
            by_pool[e.pool] = by_pool.get(e.pool, 0) + e.price
        assert by_pool == {"orientation:1": 5, "antithesis:1": 2}
        assert state.disposition.startswith("Here is what I found")
        # the opening synthesis exchange withheld the gated tools: nothing was proposed or asked
        assert harness.requests[-1].withheld == GATED_TOOLS
        assert ledger.proposed == {} and approver.asked == []
        assert any(r.name == "mcp__graph__close_node" and "Suggest it in text" in r.reason for r in [e for e in harness.sink.events if isinstance(e, ev.Refused)])

        # the surface refused the Bash call, and said so where the model reads it
        refused = [e for e in harness.sink.events if isinstance(e, ev.Refused)]
        assert any(r.name == "Bash" and r.reason.startswith("NOT_AVAILABLE") for r in refused)
        # the refused command and the bad overwrite came back as error results, not findings
        errors = [e for e in harness.sink.events if isinstance(e, ev.ToolResult) and e.is_error]
        assert any("not an allowed command" in e.text for e in errors)
        assert any("not a finding you created this turn" in e.text for e in errors)
        # the kept output came back to the model
        assert any("Overwrote f1.1" in e.text and FILE_A in e.text for e in [e for e in harness.sink.events if isinstance(e, ev.ToolResult)])
        # the running count rode on the priced calls
        assert any(isinstance(e, ev.Priced) and e.remaining == 15 for e in harness.sink.events)

        # the stages ran in order, every frame exactly as many turns as scripted
        assert [r.stage for r in harness.requests] == ["orientate", "antithesis", "synthesis"]

        # --- a reply enters synthesis, proposes, and the user answers at the call ---
        approver.verdicts.extend(
            [
                ScriptedApprover.approving(1, words="yes, register that").verdicts[0],
                ScriptedApprover.refusing(1, words="no — I have not decided that").verdicts[0],
            ]
        )
        harness.queue(
            "synthesis",
            Turn(
                payload={"text": "Registered. I proposed closing a1.1 and you refused."},
                calls=(
                    Call("mcp__graph__propose_fact", {"quote": "the validation is in signature.py", "because": "you said so"}),
                    Call("mcp__graph__close_node", {"target": "a1.1", "verdict": "confirmed", "because": "it held"}),
                    # a paraphrase is refused by the tool even though the user approved the call
                ),
            ),
        )
        reply = "I think the validation is in signature.py and the handler just calls it"
        final = await _run(graph, ctx, "t1", prompt=reply)
        state = GraphState.model_validate(final)

        assert state.stage == "synthesis" and state.synthesis_turns == 2 and state.cycle == 1
        assert harness.requests[-1].withheld == frozenset()  # the reply admits the calls
        assert state.said == [QUESTION, reply]
        ledger = ctx.store.ledger()
        assert [e.quote for e in ledger.explicits.values()] == ["the validation is in signature.py"]
        assert [(w.write, w.target_id) for w in ledger.proposed.values()] == [("propose_fact", ""), ("close_node", "a1.1")]
        assert [(d.write_id, d.approved, d.applied) for d in ledger.decisions.values()] == [("p1.1", True, True), ("p1.2", False, False)]
        assert ledger.decisions["p1.2"].words == "no — I have not decided that"
        assert approver.asked[1].name == "close_node"

        rendered = package.render(ledger, thought.build(ledger))
        assert 'KNOWN' in rendered and "the validation is in signature.py" in rendered
        assert "REFUSED THESE" in rendered and "no — I have not decided that" in rendered
        assert "contends with a1.2" in rendered
        assert "CONTEXT" in rendered and "[f1.1] sed -n '1,2p' webhook/signature.py" in rendered
        assert "ASSUMPTIONS" in rendered and "rests on: f1.1" in rendered
        assert "READING" not in rendered

        # the thought graph over these records is structurally clean
        g = thought.build(ledger)
        assert thought.invariants(g) == []
        assert g.nodes["x1.2"]["kind"] == "claim" and g.nodes["x1.2"]["role"] == "counter" and g.has_edge("x1.2", "a1.2")
        assert g.nodes["a1.1"]["kind"] == "claim" and g.nodes["a1.1"]["role"] == "assumption"
        assert thought.edge_kinds(g, "q1", "f1.1") == ["evidences"] and thought.edge_kinds(g, "a1.1", "f1.1") == ["cites"]
        assert any(label.startswith("rests on f1.1") for _, _, label in thought.outline(g).lines)

    # --- the process "restarts": a fresh checkpointer and a fresh store over the same files ---
    ctx = ControlContext(harness=harness, budgets=Budgets(), store=GraphStore(log), session="t1")
    async with sqlite_checkpointer(db) as saver:
        graph = compile_cycle(saver)
        snapshot = await graph.aget_state({"configurable": {"thread_id": "t1"}})
        reloaded = GraphState.model_validate(snapshot.values)
        assert reloaded.conversation == "scripted-1" and reloaded.cycle == 1
        # the thread carries the working set only; the graph was replayed from the log
        assert "explicits" not in snapshot.values
        replayed = ctx.store.ledger()
        assert replayed.explicits["e1.1"].quote == "the validation is in signature.py"
        assert replayed.lines == len(log.read_text().splitlines()) and replayed.lines > 10
        assert package.render(replayed, thought.build(replayed)) == rendered

        # --- /graph again: the second cycle opens on the carried package ---------
        harness.queue(
            "orientate",
            Turn(payload={"overview": "second look", "assumptions": [assumption(3)]}),
        )
        harness.queue(
            "antithesis",
            Turn(payload={"antitheses": [{"claim": "r", "inferred_because": "b", "moved_by": "c"}], "reasoning": "x"}),
        )
        harness.queue("synthesis", Turn(payload={"text": "cycle two"}))
        final = await _run(graph, ctx, "t1", prompt="and where is it configured?", advance=True)
        state = GraphState.model_validate(final)

        ledger = ctx.store.ledger()
        assert state.cycle == 2 and [a.id for a in ledger.assumptions_of(2)] == ["a2.1"]
        opening = harness.requests[-3]
        assert opening.stage == "orientate" and opening.conversation == ""  # fresh conversation
        assert "This is what you already know" in opening.message
        assert "the validation is in signature.py" in opening.message
        assert state.conversation == "scripted-2"
        # the previous cycle's assumptions are still there; the new pool is named apart
        assert len(ledger.assumptions) == 3
        assert {e.pool for e in ledger.spend} >= {"orientation:1", "antithesis:1"}
        assert harness.requests[-3].pools == {"orientation:2": 20}
        # both cycles' questions are nodes, and every assumption hangs off its own
        g = thought.build(ledger)
        assert thought.invariants(g) == [] and g.has_edge("q2", "a2.1") and g.has_edge("q1", "a1.1")


@pytest.mark.asyncio
async def test_an_interrupt_stops_the_run_at_the_last_committed_checkpoint(tmp_path: Path):
    s = script()
    s["antithesis"] = [Turn(payload=None, interrupt=True)]
    harness = ScriptedHarness(script=s, approver=ScriptedApprover())
    store = GraphStore(None)
    ctx = ControlContext(harness=harness, store=store, session="t2")

    async with sqlite_checkpointer(tmp_path / "c.sqlite") as saver:
        graph = compile_cycle(saver)
        with pytest.raises(FrameInterrupted):
            await _run(graph, ctx, "t2", prompt=QUESTION, advance=True)
        snapshot = await graph.aget_state({"configurable": {"thread_id": "t2"}})
        state = GraphState.model_validate(snapshot.values)
        ledger = store.ledger()
        # orientate committed, with its survey finding; antithesis did not
        assert state.stage == "orientate" and len(ledger.assumptions) == 2 and list(ledger.findings) == ["f1.1"]
        assert ledger.antitheses == {}
        assert snapshot.next == ("antithesis",)

        # resume: the run carries on from the frame that was owed, with the context of *this* run
        harness.queue("antithesis", script()["antithesis"][0])
        harness.queue("synthesis", script()["synthesis"][0])
        resumed = ControlContext(harness=harness, budgets=Budgets(antithesis_base=9), store=store, session="t2")
        final = await graph.ainvoke(None, {"configurable": {"thread_id": "t2"}}, context=resumed)
        state = GraphState.model_validate(final)
        assert state.stage == "synthesis" and state.cycle == 1
        assert list(store.ledger().antitheses) == ["x1.1", "x1.2"]
        assert [r.stage for r in harness.requests] == ["orientate", "antithesis", "antithesis", "synthesis"]
        assert harness.requests[-2].pools == {"antithesis:1": 11}  # 9 + 2, the resumed run's numbers


@pytest.mark.asyncio
async def test_a_fork_flag_makes_the_next_frame_fork_the_conversation(tmp_path: Path):
    harness = ScriptedHarness(script=script(), approver=ScriptedApprover())
    ctx = ControlContext(harness=harness)
    async with sqlite_checkpointer(tmp_path / "c.sqlite") as saver:
        graph = compile_cycle(saver)
        await _run(graph, ctx, "t3", prompt=QUESTION, advance=True)
        config = {"configurable": {"thread_id": "t3"}}
        await graph.aupdate_state(config, {"fork_conversation": True})
        harness.queue("synthesis", Turn(payload={"text": "forked"}))
        final = await _run(graph, ctx, "t3", prompt="go on")
        state = GraphState.model_validate(final)
        assert harness.requests[-1].fork is True
        assert state.conversation == "scripted-2" and state.fork_conversation is False


@pytest.mark.asyncio
async def test_the_findings_limit_is_hard_and_overwrites_do_not_count(tmp_path: Path):
    s = script()
    s["orientate"] = [
        Turn(
            payload={"overview": "o", "assumptions": [assumption(1)]},
            calls=(
                Call("mcp__graph__attach_finding", {"target": "", "run": "cat a"}, result="A"),
                Call("mcp__graph__attach_finding", {"target": "", "run": "cat b"}, result="B"),
                Call("mcp__graph__attach_finding", {"target": "", "run": "cat c"}, result="C"),  # over the limit
                Call("mcp__graph__attach_finding", {"target": "", "run": "cat d", "replace": "f1.2"}, result="D"),  # allowed
            ),
        )
    ]
    s["antithesis"] = [Turn(payload={"antitheses": [{"claim": "r", "inferred_because": "b", "moved_by": "c"}], "reasoning": "x"})]
    harness = ScriptedHarness(script=s, approver=ScriptedApprover(), budgets=Budgets(max_findings=2))
    ctx = ControlContext(harness=harness, budgets=Budgets(max_findings=2))
    async with sqlite_checkpointer(tmp_path / "c.sqlite") as saver:
        graph = compile_cycle(saver)
        await _run(graph, ctx, "t4", prompt=QUESTION, advance=True)
        assert [(f.id, f.excerpt) for f in ctx.store.ledger().findings.values()] == [("f1.1", "A"), ("f1.2", "D")]
        errors = [e.text for e in harness.sink.events if isinstance(e, ev.ToolResult) and e.is_error]
        assert any("limit of 2 findings" in t for t in errors)
