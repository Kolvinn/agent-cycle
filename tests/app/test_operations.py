"""The thought graph's operations, end to end: growth in the surveys, every
gated alteration in a synthesis reply, the view they leave, the package that
renders it, and the log that replays it."""

from __future__ import annotations

from collections import deque
from pathlib import Path

import pytest

from langchain_claude_test.app.config import Budgets
from langchain_claude_test.app.graph import ControlContext, compile_cycle, package, thought
from langchain_claude_test.app.graph import vocabulary as v
from langchain_claude_test.app.graph.graph import sqlite_checkpointer
from langchain_claude_test.app.graph.state import EdgeAdded, Merge, NodeAdded, RelationKind
from langchain_claude_test.app.graph.store import GraphStore
from langchain_claude_test.app.harness import events as ev
from langchain_claude_test.app.harness.protocol import Verdict
from langchain_claude_test.app.harness.scripted import Call, ScriptedApprover, ScriptedHarness, Turn

QUESTION = "Where do we validate the incoming webhook signature?"
YES = Verdict(approved=True, answered_by="scripted", words="yes")
NO = Verdict(approved=False, answered_by="scripted", words="no, keep that edge")


def tool(name: str, **args) -> Call:
    return Call(f"mcp__graph__{name}", args, result=args.pop("_result", "") if "_result" in args else "")


def assumption(n: int) -> dict:
    return {"claim": f"assumption {n}", "inferred_because": "b", "moved_by": "m", "evidence": []}


def script() -> dict[str, list[Turn]]:
    return {
        "orientate": [
            Turn(
                payload={"overview": "a webhook service", "assumptions": [assumption(1), assumption(2)]},
                calls=(
                    Call("mcp__graph__attach_finding", {"target": "", "run": "sed -n '1,2p' webhook/signature.py"}, result="def verify_signature(payload, sig):"),
                    # growth: ungated, provisional
                    tool("add_node", kind="entity", role="file", text="webhook/handlers.py", why="the HTTP entry"),
                    tool("add_node", kind="entity", role="file", text="webhook/signature.py", why="does the HMAC"),
                    tool("add_node", kind="entity", text="hmac", why="the stdlib it leans on"),  # role defaults to concept
                    tool("add_node", kind="entity", role="file", text="webhook/handlers.py", why="dup"),  # refused: already there
                    tool("add_node", kind="entity", role="planet", text="mars", why="bad role"),  # refused
                    tool("add_node", kind="claim", role="assumption", text="a1 again", why="dup of the answer"),  # refused here
                    # relations: gated, approved here
                    tool("add_edge", src="n1.1", kind="depends_on", dst="n1.2", why="handlers imports verify_signature"),
                    tool("add_edge", src="n1.2", kind="depends_on", dst="n1.3", why="signature.py imports hmac"),
                    tool("add_edge", src="n1.1", kind="calls", dst="q1", why="nonsense"),  # refused: a question is not an entity
                    tool("add_edge", src="n1.1", kind="depends_on", dst="n1.2", why="again"),  # refused: duplicate
                    tool("add_edge", src="n1.1", kind="evidences", dst="n1.2", why="structural"),  # refused: structural
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
                calls=(Call("mcp__graph__attach_finding", {"target": "2", "run": "grep -n 401 webhook/handlers.py"}, result="3:        return 401"),),
            )
        ],
        "synthesis": [Turn(payload={"text": "Here is what I found. I suggest merging the two files' nodes."})],
    }


def reply_turn() -> Turn:
    return Turn(
        payload={"text": "Done as discussed."},
        calls=(
            tool("add_node", kind="claim", role="observation", text="the handler returns 401 on a bad signature", why="seen"),
            tool("add_node", kind="claim", role="counter", text="counter without about"),  # refused
            tool("add_edge", src="a1.1", kind="requires", dst="n1.2", why="the assumption needs the file"),
            # a relation outside the vocabulary, approved: the kind is added to the project
            tool("add_edge", src="n1.1", kind="relates_to", dst="n1.2", why="handlers is tested through signature", proposed_kind="tested_by"),
            tool("update_node", target="n1.2", text="webhook/signature.py (HMAC check)", because="clearer"),
            tool("update_edge", edge="r1.2", why="import at the top of the file", because="precision"),
            tool("delete_node", target="n1.2", because="dup"),  # refused: relations remain
            tool("move_evidence", finding="f1.1", to="n1.2", because="it is that file's code"),
            tool("delete_node", target="n1.2", because="dup"),  # refused: evidence remains
            tool("merge", source="n1.2", target="n1.1", because="one thing, two names"),
            tool("delete_edge", edge="r1.2", because="try to drop it"),  # the user refuses this one
            tool("supersede", old="a1.2", new="x1.2", because="the rival held"),
            tool("close_node", target="a1.2", verdict="refuted", because="too late"),  # refused: terminal
            tool("close_node", target="a1.1", verdict="confirmed", because="it held"),
            tool("compress", ids=["x1.1"], summary="the rival of 1 went nowhere"),
            tool("propose_fact", quote="the validation is in signature.py", because="you said so", supports=["a1.1"]),
            tool("delete_node", target="c1.1", because="not needed"),  # bare: allowed
        ),
    )


async def _run(graph, ctx, thread: str, **update):
    return await graph.ainvoke(update, {"configurable": {"thread_id": thread}}, context=ctx)


@pytest.mark.asyncio
async def test_growth_relations_edits_merge_verdicts_and_compression(tmp_path: Path):
    log = tmp_path / "graph" / "ops.jsonl"
    approver = ScriptedApprover(verdicts=deque([YES, YES]))  # the survey's two relations
    harness = ScriptedHarness(script=script(), approver=approver)
    ctx = ControlContext(harness=harness, budgets=Budgets(), store=GraphStore(log), session="t1")

    async with sqlite_checkpointer(tmp_path / "c.sqlite") as saver:
        graph = compile_cycle(saver)
        await _run(graph, ctx, "t1", prompt=QUESTION, advance=True)

        ledger = ctx.store.ledger()
        added = [o for o in ledger.ops if isinstance(o, NodeAdded)]
        assert [(o.id, o.role, o.text) for o in added] == [
            ("n1.1", "file", "webhook/handlers.py"),
            ("n1.2", "file", "webhook/signature.py"),
            ("n1.3", "concept", "hmac"),
        ]
        assert [(o.id, o.src, o.kind, o.dst) for o in ledger.ops if isinstance(o, EdgeAdded)] == [
            ("r1.1", "n1.1", "depends_on", "n1.2"),
            ("r1.2", "n1.2", "depends_on", "n1.3"),
        ]
        # add_node never asked; a malformed add_edge is refused before it reaches the user
        assert [a.name for a in approver.asked] == ["add_edge", "add_edge"]
        errors = [e.text for e in harness.sink.events if isinstance(e, ev.ToolResult) and e.is_error]
        assert any("already says that" in t for t in errors)
        assert any("role is one of" in t for t in errors)
        assert any("named in your answer, not as nodes" in t for t in errors)
        assert any("cannot end at a question" in t for t in errors)
        assert any("already depends_on" in t for t in errors)
        assert any("structural edge" in t for t in errors)

        g = thought.build(ledger)
        assert thought.invariants(g) == []
        assert g.nodes["n1.1"]["kind"] == v.ENTITY and g.nodes["n1.1"]["status"] == v.PROVISIONAL
        assert thought.edge_kinds(g, "n1.1", "n1.2") == ["depends_on"]

        # --- the reply: every alteration, answered at the call -------------------------
        # twelve well-formed gated calls reach the user; the seventh (delete_edge) is refused
        approver.verdicts.extend([YES] * 6 + [NO] + [YES] * 5)
        harness.queue("synthesis", reply_turn())
        await _run(graph, ctx, "t1", prompt="I think the validation is in signature.py")

        ledger = ctx.store.ledger()
        g = thought.build(ledger)
        assert thought.invariants(g) == []

        # the vocabulary grew by approval, and the edge carries the new kind
        assert list(ledger.relation_kinds) == ["tested_by"]
        assert any(isinstance(o, RelationKind) and o.name == "tested_by" for o in ledger.ops)

        # the merge: n1.2 is gone into n1.1; its relation to hmac and its evidence moved; self-loops collapsed
        assert g.nodes["n1.2"]["status"] == v.DISCARDED and g.nodes["n1.2"]["merged_into"] == "n1.1"
        assert thought.edge_kinds(g, "n1.1", "n1.3") == ["depends_on"]
        assert thought.evidence_of(g, "n1.1") == ["f1.1"] and thought.evidence_of(g, "q1") == []
        assert not any(src == dst for _, src, dst, _ in thought.relational_edges(g))
        assert thought.edge_kinds(g, "a1.1", "n1.1") == ["requires"]  # re-pointed from n1.2
        # the update happened before the merge and is in the discarded node's history
        assert g.nodes["n1.2"]["text"] == "webhook/signature.py (HMAC check)" and g.nodes["n1.2"]["history"][0]["text"] == "webhook/signature.py"
        # the edge update kept the edge and changed its why
        assert next(a for key, _, _, a in thought.relational_edges(g) if a["kind"] == "depends_on" and a["why"].startswith("import"))

        # verdicts and supersession
        assert g.nodes["a1.1"]["status"] == v.CONFIRMED
        assert g.nodes["a1.2"]["status"] == v.SUPERSEDED and g.nodes["x1.2"]["role"] == "assumption"
        assert thought.edge_kinds(g, "x1.2", "a1.2") == ["contends", "supersedes"]
        # compression and the bare delete
        assert g.nodes["x1.1"]["compressed"] and thought.edge_kinds(g, "s1.1", "x1.1") == ["summarises"]
        assert g.nodes["c1.1"]["status"] == v.DISCARDED
        # the fact grounds the claim it supports
        assert thought.edge_kinds(g, "e1.1", "a1.1") == ["grounds"]

        # refusals said why, and the refused delete_edge is on the record with the user's words
        errors = [e.text for e in harness.sink.events if isinstance(e, ev.ToolResult) and e.is_error]
        assert any("still has relational edges" in t for t in errors)
        assert any("still has evidence f1.1" in t for t in errors)
        assert any("already superseded; that is terminal" in t for t in errors)
        assert any("needs about=" in t for t in errors)
        assert [w.write for w in ledger.refused()] == ["delete_edge"]
        assert ledger.decisions["p1.7"].words == "no, keep that edge"
        assert len(approver.asked) == 2 + 12  # the calls the handler refused were never asked
        # an approved call that its handler refused is recorded as not applied
        applied = {w.write: ledger.decisions[w.id].applied for w in ledger.approved()}
        assert applied["merge"] is True and applied["close_node"] is True and applied["delete_node"] is True

        # the package renders the applied graph
        rendered = package.render(ledger, g)
        assert "ENTITIES" in rendered and "[n1.1] webhook/handlers.py (file)" in rendered
        assert "→ depends_on n1.3" in rendered and "n1.2" not in rendered.split("ENTITIES")[1].split("ASSUMPTIONS")[0]
        assert "[a1.1] assumption 1 [confirmed]" in rendered
        assert "[x1.2] rival of 2" in rendered and "supersedes: a1.2" in rendered
        assert "[a1.2] assumption 2 [superseded]" in rendered
        assert "COMPRESSED" in rendered and "stands for x1.1" in rendered
        assert "[x1.1]" not in rendered.split("COMPRESSED")[0]
        assert "(grounds a1.1)" in rendered
        assert "delete_edge r1.2" in rendered and "no, keep that edge" in rendered

    # --- replayed from the file by a fresh store, the view and the package are the same ---
    replayed = GraphStore(log).ledger()
    assert package.render(replayed, thought.build(replayed)) == rendered
    assert thought.invariants(thought.build(replayed)) == []
    assert sum(1 for o in replayed.ops if isinstance(o, Merge)) == 1


def test_the_outline_shows_entities_relations_and_summaries():
    store = GraphStore(None)
    store.open_cycle("s", QUESTION)
    from langchain_claude_test.app.graph.state import Assumption, Compression, Finding

    store.append(
        "s",
        [
            Assumption(id="a1.1", cycle=1, claim="c", inferred_because="b", moved_by="m"),
            Finding(id="f1.1", node_id="a1.1", cycle=1, locator="cat a", excerpt="A", price=0),
            NodeAdded(id="n1.1", cycle=1, kind="entity", role="file", text="a.py"),
            NodeAdded(id="n1.2", cycle=1, kind="entity", role="module", text="b"),
            EdgeAdded(id="r1.1", cycle=1, src="n1.1", kind="part_of", dst="n1.2", why="w"),
            Compression(id="s1.1", members=("a1.1",), summary="folded", cycle=1),
        ],
    )
    lines = thought.outline(thought.build(store.ledger())).lines
    assert (0, "n1.1", "entity/file n1.1: a.py") in lines
    assert (1, "r1.1", "→ part_of n1.2") in lines
    assert any(nid == "a1.1" and "[compressed]" in label for _, nid, label in lines)
    assert (1, "a1.1", "stands for assumption a1.1: c [compressed]") in lines
