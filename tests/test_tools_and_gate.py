"""The enforcement layer: what the tools do, and what the gate lets through.

The fixture has known ground truth — ``verify_signature`` is defined at
``webhook/signature.py:12`` and called at ``webhook/handlers.py:17`` and
``:28`` — so the evidence tests assert on exact locations rather than on
"something was found".
"""

from __future__ import annotations

from pathlib import Path

import pytest

from langchain_claude_test.ledger import (
    NewExplicit,
    NewImplicit,
    form_implicit,
    register_explicit,
    set_status,
)
from langchain_claude_test.session.gate import Gate, Policy
from langchain_claude_test.session.state import SessionState
from langchain_claude_test.session.tools import ToolError, call_tool, make_tools

FIXTURE = Path(__file__).parent / "fixtures" / "repo"
MSG = "Where do we validate the incoming webhook signature?"
QUOTE = "validate the incoming webhook signature"


@pytest.fixture
def tools():
    return make_tools(FIXTURE)


@pytest.fixture
def state():
    """State holding one explicit, one pending implicit under it."""
    s = SessionState(current_message=MSG, turn=1)
    r = register_explicit(
        NewExplicit(quote=QUOTE, start=MSG.index(QUOTE)),
        current_graph=s.graph, turn=1, message_text=MSG,
    )
    s.graph, s.explicit_id = r.graph, r.node_ids[0]
    r = form_implicit(
        NewImplicit(claim="validation happens in signature.py", grounded_in=s.explicit_id),
        current_graph=s.graph, turn=1,
    )
    s.graph, s.implicit_id = r.graph, r.node_ids[0]
    return s


def _approve(state):
    state.graph = set_status(state.implicit_id, "approved", current_graph=state.graph, by_user=True).graph
    return state


# --- tools -----------------------------------------------------------------


def test_list_dir_surveys_deterministically(tools):
    out = call_tool(tools["list_dir"], {"path": "."})
    assert out.splitlines() == ["api/", "webhook/"]


def test_list_dir_rejects_a_file(tools):
    with pytest.raises(ToolError, match="not a directory"):
        call_tool(tools["list_dir"], {"path": "webhook/handlers.py"})


def test_read_file_numbers_lines(tools):
    out = call_tool(tools["read_file"], {"path": "webhook/signature.py"})
    assert "12:def verify_signature(payload: bytes, sig: str, secret: str) -> bool:" in out


def test_grep_finds_the_known_ground_truth(tools):
    out = call_tool(tools["grep"], {"pattern": "def verify_signature"})
    assert out == "webhook/signature.py:12:def verify_signature(payload: bytes, sig: str, secret: str) -> bool:"


def test_grep_reports_the_definition_and_every_call_site(tools):
    """A literal search for ``verify_signature(`` hits the definition too — the
    fixture's ground truth is all three lines, not just the two call sites."""
    lines = call_tool(tools["grep"], {"pattern": "verify_signature("}).splitlines()
    assert [(ln.split(":")[0], ln.split(":")[1]) for ln in lines] == [
        ("webhook/handlers.py", "17"),
        ("webhook/handlers.py", "28"),
        ("webhook/signature.py", "12"),
    ]


def test_grep_says_so_when_nothing_matches(tools):
    assert "no matches" in call_tool(tools["grep"], {"pattern": "nonexistent_symbol_xyz"})


def test_empty_pattern_is_refused(tools):
    with pytest.raises(ToolError, match="empty"):
        call_tool(tools["grep"], {"pattern": "   "})


@pytest.mark.parametrize(
    "escape",
    ["../../../etc/passwd", "../../conftest.py", "/etc/passwd", "webhook/../../../etc/hosts"],
)
def test_sandbox_escapes_are_refused(tools, escape):
    """Checked after full resolution, so `..` and symlinks are both caught —
    a sandbox that only string-matches `..` is not a sandbox."""
    with pytest.raises(ToolError, match="escapes the fixture root"):
        call_tool(tools["read_file"], {"path": escape})


def test_gate_arguments_never_reach_the_tool(tools):
    """`for_node_id` is the gate's, not the tool's — passing it through would
    be a TypeError at every call site."""
    out = call_tool(tools["grep"], {"pattern": "def verify_signature", "for_node_id": "abc"})
    assert "signature.py:12" in out


# --- the gate --------------------------------------------------------------


def test_free_tier_costs_no_hop(tools, state):
    d = Gate(state).decide(tools["list_dir"], {"path": "."})
    assert d.would_be == "allow" and d.rule == "free.no-hop"


def test_gated_call_must_name_its_node(tools, state):
    d = Gate(state).decide(tools["grep"], {"pattern": "x"})
    assert d.would_be == "block" and d.rule == "gated.missing-provenance"


def test_gated_call_cannot_invent_a_node(tools, state):
    d = Gate(state).decide(tools["grep"], {"pattern": "x", "for_node_id": "made-up"})
    assert d.would_be == "block" and d.rule == "gated.unknown-node"


def test_evidence_before_signoff_is_refused(tools, state):
    """The ordering the flow settles on: sign-off, then evidence."""
    d = Gate(state).decide(tools["grep"], {"pattern": "x", "for_node_id": state.implicit_id})
    assert d.would_be == "block"
    assert d.rule == "gated.unapproved-claim"
    assert "pending" in d.reason


def test_evidence_after_signoff_is_allowed(tools, state):
    _approve(state)
    d = Gate(state).decide(tools["grep"], {"pattern": "x", "for_node_id": state.implicit_id})
    assert d.would_be == "allow" and d.rule == "depth1.approved"


def test_serving_an_explicit_directly_is_depth_zero(tools, state):
    d = Gate(state).decide(tools["grep"], {"pattern": "x", "for_node_id": state.explicit_id})
    assert d.would_be == "allow" and d.rule == "depth0.explicit"


def test_reading_a_path_the_user_named_is_free(tools, state):
    state.user_named_paths.add("webhook/handlers.py")
    d = Gate(state).decide(tools["read_file"], {"path": "webhook/handlers.py"})
    assert d.would_be == "allow" and d.rule == "depth0.user-named"


def test_a_second_look_is_where_multi_hop_starts(tools, state):
    """The cap is how depth 2 is made impossible rather than detected: one
    look per claim means there is no second result to hop from."""
    _approve(state)
    gate = Gate(state)
    first = gate.decide(tools["grep"], {"pattern": "x", "for_node_id": state.implicit_id})
    assert first.would_be == "allow"

    state.spend_evidence(state.implicit_id)
    second = gate.decide(tools["grep"], {"pattern": "y", "for_node_id": state.implicit_id})
    assert second.would_be == "ask" and second.rule == "depth1.budget-exhausted"


def test_raising_the_budget_permits_a_second_look(tools, state):
    _approve(state)
    gate = Gate(state, policy=Policy(max_evidence_per_implicit=2))
    state.spend_evidence(state.implicit_id)
    assert gate.decide(tools["grep"], {"pattern": "y", "for_node_id": state.implicit_id}).would_be == "allow"


# --- observe vs enforce ----------------------------------------------------


def test_observe_mode_records_the_refusal_and_runs_anyway(tools, state):
    """The friction measurement: what the gate would have done, without the
    friction confounding the thing being measured."""
    d = Gate(state, policy=Policy(mode="observe")).decide(tools["grep"], {"pattern": "x"})
    assert d.would_be == "block"
    assert d.executed == "allow"
    assert d.diverged and d.runs


def test_enforce_mode_actually_stops_it(tools, state):
    d = Gate(state, policy=Policy(mode="enforce")).decide(tools["grep"], {"pattern": "x"})
    assert d.would_be == d.executed == "block"
    assert not d.diverged and not d.runs


def test_every_decision_names_the_rule_that_made_it(tools, state):
    """A verdict on its own is an assertion; a verdict plus its rule is
    something you can argue with."""
    gate = Gate(state)
    for spec, args in (
        (tools["list_dir"], {"path": "."}),
        (tools["grep"], {"pattern": "x"}),
        (tools["grep"], {"pattern": "x", "for_node_id": state.implicit_id}),
        (tools["grep"], {"pattern": "x", "for_node_id": state.explicit_id}),
    ):
        d = gate.decide(spec, args)
        assert d.rule and "." in d.rule, f"decision for {args} has no rule"
        assert d.reason
