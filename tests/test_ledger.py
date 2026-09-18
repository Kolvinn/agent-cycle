"""Layer A: the ledger's rules, exhaustively, with no model involved.

Every test here runs in milliseconds and costs nothing, which is the point —
most of this design's risk is in the rules rather than in the prompting, and
the rules can be settled before a single token is spent.

The running scenario is the webhook-signature walkthrough from
``docs/design/eie-tree-turn-by-turn-example.md``, so a failure here maps
directly onto a turn in that document.
"""

from __future__ import annotations

import pytest

from langchain_claude_test.ledger import (
    NewExplicit,
    NewImplicit,
    Source,
    apply_source,
    check_invariants,
    form_implicit,
    grounds_edge_for,
    new_ledger,
    node,
    open_explicits,
    register_explicit,
    set_status,
    to_digest,
    to_mermaid,
    unresolved_implicits,
)

TURN_1 = "Where do we validate the incoming webhook signature?"
GREP_RESULT = (
    "webhook/handlers.py:42:def verify_signature(payload: bytes, sig: str) -> bool:\n"
    "webhook/handlers.py:51:    if not verify_signature(body, header):\n"
)


@pytest.fixture
def explicit():
    """A ledger holding one depth-0 explicit from turn 1."""
    g = new_ledger()
    quote = "validate the incoming webhook signature"
    r = register_explicit(
        NewExplicit(quote=quote, start=TURN_1.index(quote)),
        current_graph=g,
        turn=1,
        message_text=TURN_1,
    )
    assert r, r.message
    return r.graph, r.node_ids[0]


@pytest.fixture
def approved(explicit):
    """One explicit, one implicit hanging off it, signed off by the user."""
    g, eid = explicit
    r = form_implicit(
        NewImplicit(claim="validation happens in handlers.py at verify_signature", grounded_in=eid),
        current_graph=g,
        turn=1,
    )
    assert r, r.message
    iid, edge_id = r.node_ids[0], r.edge_ids[0]
    r = set_status(iid, "approved", current_graph=r.graph, by_user=True)
    assert r, r.message
    return r.graph, eid, iid, edge_id


# --- registering explicits -------------------------------------------------


def test_verbatim_quote_registers(explicit):
    g, eid = explicit
    n = node(g, eid)
    assert n.kind == "explicit" and n.status == "open"
    assert n.text == "validate the incoming webhook signature"
    assert check_invariants(g) == []


def test_paraphrase_is_rejected():
    """The check that separates a quote from a paraphrase — and paraphrase is
    already inference."""
    g = new_ledger()
    r = register_explicit(
        NewExplicit(quote="check the webhook sig", start=9),
        current_graph=g,
        turn=1,
        message_text=TURN_1,
    )
    assert not r
    assert "not verbatim" in r.message
    assert r.graph.number_of_nodes() == 0


def test_quote_at_wrong_offset_is_rejected():
    """Right words, wrong place: still refused, because the offset is what
    makes the claim checkable."""
    g = new_ledger()
    quote = "webhook signature"
    r = register_explicit(
        NewExplicit(quote=quote, start=TURN_1.index(quote) + 3),
        current_graph=g,
        turn=1,
        message_text=TURN_1,
    )
    assert not r and "not verbatim" in r.message


# --- the central invariant -------------------------------------------------


def test_implicit_grounds_in_explicit(explicit):
    g, eid = explicit
    r = form_implicit(
        NewImplicit(claim="validation happens in handlers.py at verify_signature", grounded_in=eid),
        current_graph=g,
        turn=1,
    )
    assert r, r.message
    iid = r.node_ids[0]
    assert node(r.graph, iid).status == "pending"
    assert grounds_edge_for(r.graph, iid).source_id == eid
    assert check_invariants(r.graph) == []


def test_implicit_cannot_ground_in_implicit(approved):
    """Turn 3 of the walkthrough: the failure the whole design exists to catch.

    Note the parent here is ``approved`` — the strongest an implicit can ever
    be — and it is still refused. 'Basically confirmed' is not a carve-out.
    """
    g, _eid, iid, _edge = approved
    r = form_implicit(
        NewImplicit(claim="the other webhook handlers have the same gap", grounded_in=iid),
        current_graph=g,
        turn=3,
    )
    assert not r
    assert "always an explicit" in r.message
    assert r.graph.number_of_nodes() == 2, "the rejected node must not enter the tree"


def test_implicit_cannot_ground_in_unknown_node(explicit):
    g, _ = explicit
    r = form_implicit(
        NewImplicit(claim="something", grounded_in="not-a-real-id"),
        current_graph=g,
        turn=1,
    )
    assert not r and "not a known node" in r.message


# --- closure is the user's, always -----------------------------------------


def test_agent_cannot_promote_its_own_claim(explicit):
    """`PLAN.md` decision 10, enforced rather than trusted: self-report is not
    closure."""
    g, eid = explicit
    r = form_implicit(NewImplicit(claim="x is true", grounded_in=eid), current_graph=g, turn=1)
    iid = r.node_ids[0]

    denied = set_status(iid, "approved", current_graph=r.graph, by_user=False)
    assert not denied
    assert "Self-report is not closure" in denied.message
    assert node(denied.graph, iid).status == "pending"


@pytest.mark.parametrize("verdict", ["approved", "rejected", "parked"])
def test_user_verdicts_land(explicit, verdict):
    g, eid = explicit
    r = form_implicit(NewImplicit(claim="x is true", grounded_in=eid), current_graph=g, turn=1)
    out = set_status(r.node_ids[0], verdict, current_graph=r.graph, by_user=True)
    assert out, out.message
    assert node(out.graph, r.node_ids[0]).status == verdict


def test_settled_verdicts_are_terminal(approved):
    g, _eid, iid, _edge = approved
    r = set_status(iid, "rejected", current_graph=g, by_user=True)
    assert not r and "not a legal transition" in r.message


def test_parked_can_still_be_answered_later(explicit):
    """An unanswered ask is not a dead end — it just never resolves itself."""
    g, eid = explicit
    r = form_implicit(NewImplicit(claim="x", grounded_in=eid), current_graph=g, turn=1)
    iid = r.node_ids[0]
    r = set_status(iid, "parked", current_graph=r.graph, by_user=True)
    r = set_status(iid, "approved", current_graph=r.graph, by_user=True)
    assert r, r.message


def test_explicit_cannot_take_an_implicit_status(explicit):
    g, eid = explicit
    r = set_status(eid, "approved", current_graph=g, by_user=True)
    assert not r and "not a legal status for an explicit" in r.message


# --- the source lands on the link ------------------------------------------


def test_source_applies_to_the_edge(approved):
    g, eid, iid, edge_id = approved
    src = Source(
        locator="webhook/handlers.py:42",
        excerpt="def verify_signature(payload: bytes, sig: str) -> bool:",
        answers="validate the incoming webhook signature",
        tool_call_id="call_1",
    )
    r = apply_source(edge_id, src, current_graph=g, tool_results={"call_1": GREP_RESULT})
    assert r, r.message

    edge = grounds_edge_for(r.graph, iid)
    assert edge.source is not None and edge.source.locator == "webhook/handlers.py:42"
    assert node(r.graph, eid).text  # the nodes themselves are untouched
    assert check_invariants(r.graph) == []


def test_source_refused_on_a_pending_claim(explicit):
    """Evidence is gathered for a signed-off claim, not to justify a pending
    one — the ordering the flow settles on."""
    g, eid = explicit
    r = form_implicit(NewImplicit(claim="x", grounded_in=eid), current_graph=g, turn=1)
    src = Source(
        locator="webhook/handlers.py:42",
        excerpt="def verify_signature",
        answers="validate the incoming webhook signature",
        tool_call_id="call_1",
    )
    out = apply_source(r.edge_ids[0], src, current_graph=r.graph, tool_results={"call_1": GREP_RESULT})
    assert not out and "not 'approved'" in out.message


def test_invented_excerpt_is_refused(approved):
    """The agent does not get to be its own witness: the excerpt must really
    appear in the result of the call it names."""
    g, _eid, _iid, edge_id = approved
    src = Source(
        locator="webhook/handlers.py:42",
        excerpt="def verify_signature_v2(payload, sig, algo):",  # not in GREP_RESULT
        answers="validate the incoming webhook signature",
        tool_call_id="call_1",
    )
    r = apply_source(edge_id, src, current_graph=g, tool_results={"call_1": GREP_RESULT})
    assert not r and "does not appear in the result" in r.message


def test_excerpt_must_come_from_the_named_call(approved):
    """Right text, wrong call: still refused. The citation names a specific
    call, so that is the one checked."""
    g, _eid, _iid, edge_id = approved
    src = Source(
        locator="webhook/handlers.py:42",
        excerpt="def verify_signature(payload: bytes, sig: str) -> bool:",
        answers="validate the incoming webhook signature",
        tool_call_id="call_2",
    )
    r = apply_source(edge_id, src, current_graph=g, tool_results={"call_1": GREP_RESULT})
    assert not r and "no recorded tool result" in r.message


def test_source_must_answer_the_explicit_not_just_the_claim(approved):
    """This is the check that makes the source *directly relevant to the
    explicit entry* rather than merely relevant to the assumption."""
    g, _eid, _iid, edge_id = approved
    src = Source(
        locator="webhook/handlers.py:42",
        excerpt="def verify_signature(payload: bytes, sig: str) -> bool:",
        answers="retry the failed delivery",  # nowhere in the explicit
        tool_call_id="call_1",
    )
    r = apply_source(edge_id, src, current_graph=g, tool_results={"call_1": GREP_RESULT})
    assert not r and "not a verbatim span of the explicit" in r.message


def test_one_link_one_source(approved):
    g, _eid, _iid, edge_id = approved
    src = Source(
        locator="webhook/handlers.py:42",
        excerpt="def verify_signature(payload: bytes, sig: str) -> bool:",
        answers="validate the incoming webhook signature",
        tool_call_id="call_1",
    )
    r = apply_source(edge_id, src, current_graph=g, tool_results={"call_1": GREP_RESULT})
    again = apply_source(edge_id, src, current_graph=r.graph, tool_results={"call_1": GREP_RESULT})
    assert not again and "already carries a source" in again.message


# --- round bookkeeping -----------------------------------------------------


def test_open_explicits_drive_completion(explicit):
    g, eid = explicit
    assert len(open_explicits(g)) == 1
    r = set_status(eid, "addressed", current_graph=g, by_user=False)
    assert r, r.message
    assert open_explicits(r.graph) == ()


def test_unresolved_implicits_tracks_pending_and_parked(approved):
    g, eid, _iid, _edge = approved
    assert unresolved_implicits(g) == ()
    r = form_implicit(NewImplicit(claim="second claim", grounded_in=eid), current_graph=g, turn=2)
    assert len(unresolved_implicits(r.graph)) == 1


# --- renderings ------------------------------------------------------------


def test_digest_is_self_contained(approved):
    """The digest is what survives the round boundary, so it has to carry the
    whole story on its own."""
    g, _eid, _iid, edge_id = approved
    src = Source(
        locator="webhook/handlers.py:42",
        excerpt="def verify_signature(payload: bytes, sig: str) -> bool:",
        answers="validate the incoming webhook signature",
        tool_call_id="call_1",
    )
    g = apply_source(edge_id, src, current_graph=g, tool_results={"call_1": GREP_RESULT}).graph

    digest = to_digest(g, turn=1)
    assert "validate the incoming webhook signature" in digest
    assert "validation happens in handlers.py" in digest
    assert "approved" in digest
    assert "webhook/handlers.py:42" in digest


def test_digest_flags_an_unsourced_link(approved):
    g, _eid, _iid, _edge = approved
    assert "(none applied)" in to_digest(g)


def test_mermaid_renders_both_kinds(approved):
    g, _eid, _iid, _edge = approved
    out = to_mermaid(g, title="turn 1")
    assert "flowchart LR" in out
    assert "EXPLICIT" in out and "IMPLICIT" in out
    assert "grounds" in out


def test_empty_ledger_renders(explicit):
    assert to_digest(new_ledger()) == "LEDGER: empty"
    assert "empty ledger" in to_mermaid(new_ledger())
