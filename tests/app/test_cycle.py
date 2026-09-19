"""A whole cycle, end to end, through the real compiled graph and a real SQLite
checkpointer, with the model replaced by a script and the human by a script.

This is the test the architecture was shaped for. Everything except the
subprocess runs: the entry router, the four frames, the assume subgraph and
its two loops, the meter, the surface, the hooks, the gate, the tools, the
records, the package, persistence, and a second cycle opened on the carried
state. It also asserts on what the user *would have seen* through the sink.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from langchain_claude_test.app.config import Budgets
from langchain_claude_test.app.graph import ControlContext, compile_cycle, package, thought
from langchain_claude_test.app.graph.graph import sqlite_checkpointer
from langchain_claude_test.app.graph.state import GraphState
from langchain_claude_test.app.harness import events as ev
from langchain_claude_test.app.harness.protocol import FrameInterrupted
from langchain_claude_test.app.harness.scripted import Call, ScriptedApprover, ScriptedHarness, Turn

QUESTION = "Where do we validate the incoming webhook signature?"
FILE_A = "     1→def verify_signature(payload, sig):\n     2→    return hmac.compare_digest(sig, sign(payload))\n"
FILE_B = "     1→def handle(request):\n     2→    if not verify_signature(request.body, request.headers['X-Sig']):\n     3→        return 401\n"


def reading(n: int) -> dict:
    return {
        "claim": f"reading {n}",
        "inferred_because": "the request names a signature",
        "moved_by": "reading the handler",
    }


def script() -> dict[str, list[Turn]]:
    return {
        "orientate": [
            Turn(
                payload={"reading": "a small webhook service", "assumptions": [reading(1), reading(2)]},
                calls=(Call("Glob", {"pattern": "**/*.py"}, result="webhook/signature.py\nwebhook/handlers.py"),),
            )
        ],
        "assume": [
            # reading a1.1, turn 1: a read (2) and a finding; 3 left, so the loop goes round
            Turn(
                payload={"reasoning": "the signature module defines it", "nothing_further": False},
                calls=(
                    Call("Read", {"file_path": "webhook/signature.py"}, result=FILE_A),
                    Call("mcp__graph__attach_finding", {"target": "", "locator": "webhook/signature.py:1", "excerpt": "def verify_signature(payload, sig):"}),
                ),
            ),
            # reading a1.1, turn 2: another read (2), then nothing further; 1 left unspent
            Turn(
                payload={"reasoning": "and the handler calls it", "nothing_further": True},
                calls=(Call("Read", {"file_path": "webhook/handlers.py"}, result=FILE_B),),
            ),
            # reading a1.2, turn 1: a finding whose excerpt is NOT in any result → refused; then nothing further
            Turn(
                payload={"reasoning": "nothing here", "nothing_further": True},
                calls=(
                    Call("Read", {"file_path": "webhook/handlers.py"}, result=FILE_B),
                    Call("mcp__graph__attach_finding", {"target": "", "locator": "x", "excerpt": "this text was never returned"}),
                ),
            ),
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
                    Call("mcp__graph__attach_finding", {"target": "2", "locator": "webhook/handlers.py:3", "excerpt": "return 401"}),
                    # a Bash call does not exist in this frame: refused before pricing
                    Call("Bash", {"command": "rm -rf /"}, result="should never run"),
                ),
            )
        ],
        "synthesis": [
            Turn(payload={"text": "Here is what I found. I did not look at the tests."}),
        ],
    }


async def _run(graph, ctx, thread: str, **update):
    config = {"configurable": {"thread_id": thread}}
    return await graph.ainvoke(update, config, context=ctx)


@pytest.mark.asyncio
async def test_a_full_cycle_then_a_reply_then_a_second_cycle(tmp_path: Path):
    db = tmp_path / "checkpoints.sqlite"
    approver = ScriptedApprover()
    harness = ScriptedHarness(script=script(), approver=approver)
    ctx = ControlContext(harness=harness, budgets=Budgets())

    async with sqlite_checkpointer(db) as saver:
        graph = compile_cycle(saver)

        # --- cycle 1 -----------------------------------------------------------
        final = await _run(graph, ctx, "t1", prompt=QUESTION, advance=True)
        state = GraphState.model_validate(final)

        assert state.cycle == 1 and state.stage == "synthesis" and state.advance is False
        assert state.question == QUESTION and state.said == [QUESTION]
        assert [a.id for a in state.assumptions] == ["a1.1", "a1.2"]
        assert state.allocations == {"a1.1": 5, "a1.2": 5}
        # every frame continued the one conversation the first frame opened
        assert state.conversation == "scripted-1"
        assert all(r.conversation == "scripted-1" for r in harness.requests[1:])
        assert harness.requests[0].conversation == ""  # the cycle boundary opened fresh

        # the rivals: one per reading, in order, aimed at the right reading
        assert [(x.id, x.target) for x in state.antitheses] == [("x1.1", "a1.1"), ("x1.2", "a1.2")]

        # findings: the case's on a1.1, the rival's on x1.2; the bad excerpt refused
        assert [(f.id, f.node_id, f.price) for f in state.findings] == [("f1.1", "a1.1", 2), ("f1.2", "x1.2", 2)]
        assert state.findings[0].tool_call_id == "toolu_0002"

        # spend: 1 (glob) + 2 + 2 (a1.1) + 2 (a1.2) + 2 (antithesis read)
        by_pool: dict[str, int] = {}
        for e in state.spend:
            by_pool[e.pool] = by_pool.get(e.pool, 0) + e.price
        assert by_pool == {"orientation:1": 1, "assume:a1.1": 4, "assume:a1.2": 2, "antithesis:1": 2}
        assert set(state.budget_closed) == {"a1.1", "a1.2"}
        assert state.disposition.startswith("Here is what I found")

        # the surface refused the Bash call, and said so where the model reads it
        refused = [e for e in harness.sink.events if isinstance(e, ev.Refused)]
        assert any(r.name == "Bash" and r.reason.startswith("NOT_AVAILABLE") for r in refused)
        # the bad excerpt came back as an error result, not a finding
        errors = [e for e in harness.sink.events if isinstance(e, ev.ToolResult) and e.is_error]
        assert any("does not appear" in e.text for e in errors)
        # the running count rode on the priced calls
        assert any(isinstance(e, ev.Priced) and e.remaining == 3 for e in harness.sink.events)

        # the stages ran in order, every frame exactly as many turns as scripted
        assert [r.stage for r in harness.requests] == [
            "orientate", "assume", "assume", "assume", "antithesis", "synthesis",
        ]

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
        assert state.said == [QUESTION, reply]
        assert [e.quote for e in state.explicits] == ["the validation is in signature.py"]
        assert [(w.write, w.target_id) for w in state.proposed] == [("propose_fact", ""), ("close_node", "a1.1")]
        assert [(d.write_id, d.approved, d.applied) for d in state.decisions] == [("p1.1", True, True), ("p1.2", False, False)]
        assert state.decisions[1].words == "no — I have not decided that"
        assert approver.asked[1].name == "close_node"

        rendered = package.render(state)
        assert 'KNOWN' in rendered and "the validation is in signature.py" in rendered
        assert "REFUSED THESE" in rendered and "no — I have not decided that" in rendered
        assert "contends with a1.2" in rendered

        # the thought graph over these records is structurally clean
        g = thought.build(state)
        assert thought.invariants(g) == []
        assert g.nodes["x1.2"]["kind"] == "rival" and ("x1.2", "a1.2") in g.edges
        assert ("a1.1", "f1.1") in g.edges

    # --- the process "restarts": a fresh graph over the same file sees the state ---
    async with sqlite_checkpointer(db) as saver:
        graph = compile_cycle(saver)
        snapshot = await graph.aget_state({"configurable": {"thread_id": "t1"}})
        reloaded = GraphState.model_validate(snapshot.values)
        assert reloaded.explicits[0].quote == "the validation is in signature.py"
        assert reloaded.conversation == "scripted-1"

        # --- /graph again: the second cycle opens on the carried package ---------
        harness.queue(
            "orientate",
            Turn(payload={"reading": "second look", "assumptions": [reading(3)]}),
        )
        harness.queue("assume", Turn(payload={"reasoning": "r", "nothing_further": True}))
        harness.queue(
            "antithesis",
            Turn(payload={"antitheses": [{"claim": "r", "inferred_because": "b", "moved_by": "c"}], "reasoning": "x"}),
        )
        harness.queue("synthesis", Turn(payload={"text": "cycle two"}))
        final = await _run(graph, ctx, "t1", prompt="and where is it configured?", advance=True)
        state = GraphState.model_validate(final)

        assert state.cycle == 2 and [a.id for a in state.current_assumptions()] == ["a2.1"]
        opening = harness.requests[-4]
        assert opening.stage == "orientate" and opening.conversation == ""  # fresh conversation
        assert "This is what you already know" in opening.message
        assert "the validation is in signature.py" in opening.message
        assert state.conversation == "scripted-2"
        # the previous cycle's readings are still there, and not funded
        assert len(state.assumptions) == 3 and "a1.1" not in state.allocations
        # spend from cycle 1 survived and cycle 2's pools are named apart
        assert any(e.pool == "assume:a1.1" for e in state.spend)


@pytest.mark.asyncio
async def test_an_interrupt_stops_the_run_at_the_last_committed_checkpoint(tmp_path: Path):
    s = script()
    s["assume"] = [Turn(payload=None, interrupt=True)]
    harness = ScriptedHarness(script=s, approver=ScriptedApprover())
    ctx = ControlContext(harness=harness)

    async with sqlite_checkpointer(tmp_path / "c.sqlite") as saver:
        graph = compile_cycle(saver)
        with pytest.raises(FrameInterrupted):
            await _run(graph, ctx, "t2", prompt=QUESTION, advance=True)
        snapshot = await graph.aget_state({"configurable": {"thread_id": "t2"}})
        state = GraphState.model_validate(snapshot.values)
        # orientate committed; assume did not
        assert state.stage == "orientate" and len(state.assumptions) == 2 and state.findings == []
        assert snapshot.next == ("assume",)


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
