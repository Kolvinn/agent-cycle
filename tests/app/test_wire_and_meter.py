"""The wire-schema repairs and the meter, with no model involved."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from langchain_claude_test.app.graph.payloads import PAYLOADS
from langchain_claude_test.app.graph.state import SpendEntry
from langchain_claude_test.app.harness.meter import GRAPH_WRITE_CLASS, Meter, call_class
from langchain_claude_test.app.harness.wire import to_wire_schema


class Leg(BaseModel):
    kind: Literal["a"]
    v: int


class Leg2(BaseModel):
    kind: Literal["b"]
    v: int


class Discriminated(BaseModel):
    x: Annotated[Leg | Leg2, Field(discriminator="kind")]


class Tupled(BaseModel):
    pair: tuple[int, str]


class Tree(BaseModel):
    label: str
    kids: list["Tree"] = []


def _walk(node, key):
    if isinstance(node, dict):
        if key in node:
            return True
        return any(_walk(v, key) for v in node.values())
    if isinstance(node, list):
        return any(_walk(v, key) for v in node)
    return False


def test_discriminator_is_stripped_and_oneof_kept():
    js = to_wire_schema(Discriminated)
    assert not _walk(js, "discriminator")
    assert _walk(js, "oneOf")


def test_prefix_items_are_expanded():
    js = to_wire_schema(Tupled)
    assert not _walk(js, "prefixItems")
    pair = js["properties"]["pair"]
    assert pair["minItems"] == pair["maxItems"] == 2
    assert "anyOf" in pair["items"]


def test_bare_ref_root_is_inlined():
    js = to_wire_schema(Tree)
    assert js.get("type") == "object"
    assert "$defs" in js


def test_every_payload_has_an_object_root():
    for model in PAYLOADS.values():
        assert to_wire_schema(model)["type"] == "object"


# --- the meter --------------------------------------------------------------


def test_call_classes_map_builtins_and_alterations():
    assert call_class("Read") == "read"
    assert call_class("Glob") == "survey"
    assert call_class("WebFetch") == "webfetch"
    assert call_class("mcp__graph__attach_finding") == GRAPH_WRITE_CLASS
    assert call_class("Bash") is None


def test_meter_charges_before_the_call_and_refuses_when_exhausted():
    m = Meter(stage="orientate", pools={"orientation:1": 5}, prices={"read": 2, "survey": 1}, default_pool="orientation:1")
    assert m.charge("Read", "t1") == (None, 2, 3)
    assert m.charge("Read", "t2") == (None, 2, 1)
    refusal, price, left = m.charge("Read", "t3")
    assert refusal and refusal.startswith("BUDGET_EXHAUSTED") and price == 2 and left == 1
    assert m.charge("Glob", "t4") == (None, 1, 0)
    assert [e.tool_call_id for e in m.entries] == ["t1", "t2", "t4"]
    assert m.refused == ["Read: orientation:1 exhausted"]
    assert m.price_paid("t2") == 2 and m.price_paid("t3") == 0


def test_meter_derives_from_prior_spend():
    prior = (SpendEntry(pool="p", call="read", price=4, stage="orientate"),)
    m = Meter(stage="orientate", pools={"p": 5}, prices={"read": 2}, default_pool="p", prior_spend=prior)
    assert m.remaining() == 1
    assert m.charge("Read", "t")[0] is not None


def test_meter_without_a_pool_refuses_priced_calls_but_not_free_writes():
    m = Meter(stage="orientate", pools={}, prices={"read": 2}, default_pool="")
    assert m.charge("Read", "t")[0].startswith("NO_BUDGET")
    assert m.charge("mcp__graph__attach_finding", "t2") == (None, 0, 0)


def test_unknown_tool_is_refused_as_unavailable():
    m = Meter(stage="orientate", pools={"p": 5}, prices={}, default_pool="p")
    assert m.charge("Bash", "t")[0].startswith("NOT_AVAILABLE")
