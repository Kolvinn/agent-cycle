"""Spike 5 — can one turn spend priced tool calls AND return a typed payload?

The budgeted-flow stages need both at once: look things up under a quota, then
register what was found. If `output_format` and tool use were mutually
exclusive, the stage would have to split into two turns for a mechanical reason
rather than a design one.

They are not exclusive — and the *way* they coexist matters for pricing. The
CLI implements structured output as a synthetic tool named `StructuredOutput`,
which appears in the model's tool-use stream but is **not** shown to
`can_use_tool`. So it occupies a slot the model can see, it cannot be gated,
and it must not be charged.

Run:  .venv/bin/python scripts/spikes/spike_05_tools_and_structured_output.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    PermissionResultAllow,
    ResultMessage,
    ToolPermissionContext,
    ToolUseBlock,
    create_sdk_mcp_server,
    query,
    tool,
)
from pydantic import BaseModel, ConfigDict, Field

MODEL = "claude-haiku-4-5-20251001"
SUBSCRIPTION_ENV = {"ANTHROPIC_API_KEY": "", "ANTHROPIC_AUTH_TOKEN": ""}

#: What the gate was actually consulted about, so the assertion inspects facts.
GATE_SAW: list[str] = []


@tool("lookup_price", "Return the price of one named item.", {"item": str})
async def lookup_price(args: dict[str, Any]) -> dict[str, Any]:
    prices = {"apple": 3, "pear": 7}
    item = str(args.get("item", "")).lower()
    return {"content": [{"type": "text", "text": f"{item}={prices.get(item, 0)}"}]}


async def gate(
    name: str, tool_input: dict[str, Any], ctx: ToolPermissionContext
) -> PermissionResultAllow:
    GATE_SAW.append(name)
    return PermissionResultAllow()


class Report(BaseModel):
    model_config = ConfigDict(extra="forbid")

    apple: int = Field(description="the price the tool reported for apple")
    pear: int = Field(description="the price the tool reported for pear")
    tool_calls_made: int


async def main() -> int:
    print("=" * 78)
    print("  Spike 5 — priced tool calls and a typed payload in one turn")
    print("=" * 78)

    options = ClaudeAgentOptions(
        model=MODEL,
        tools=[],
        allowed_tools=[],  # nothing auto-approved, so the gate sees every call
        permission_mode="default",  # NOT bypassPermissions — it shadows the gate
        mcp_servers={
            "shop": create_sdk_mcp_server(
                name="shop", version="0.1.0", tools=[lookup_price]
            )
        },
        can_use_tool=gate,
        output_format={"type": "json_schema", "schema": Report.model_json_schema()},
        env=SUBSCRIPTION_ENV,
    )

    model_saw: list[str] = []
    structured: Any = None
    async for msg in query(
        prompt=(
            "Use lookup_price to get the price of apple and of pear, then report both."
        ),
        options=options,
    ):
        if isinstance(msg, AssistantMessage):
            model_saw += [b.name for b in msg.content if isinstance(b, ToolUseBlock)]
        elif isinstance(msg, ResultMessage):
            structured = msg.structured_output

    print(f"  tool calls in the model's stream : {model_saw}")
    print(f"  calls shown to can_use_tool      : {GATE_SAW}")
    print(f"  structured_output                : {json.dumps(structured) if structured else structured!r}")

    both = bool(model_saw) and bool(GATE_SAW) and structured is not None
    parsed = None
    if structured is not None:
        try:
            parsed = Report.model_validate(structured)
        except Exception as exc:  # noqa: BLE001
            print(f"  parse failed: {exc}")
            both = False

    # The pricing-relevant half: the synthetic call is visible to the model and
    # invisible to the gate. Charging it would bill the ledger for its own
    # bookkeeping; trying to gate it would never fire.
    synthetic_seen_by_model = any("StructuredOutput" in n for n in model_saw)
    synthetic_hidden_from_gate = not any("StructuredOutput" in n for n in GATE_SAW)

    print()
    print(f"  [{'PASS' if both else 'FAIL'}] both surfaces active in one turn"
          f"{f' -> {parsed!r}' if parsed else ''}")
    print(
        f"  [{'PASS' if synthetic_seen_by_model and synthetic_hidden_from_gate else 'FAIL'}]"
        " `StructuredOutput` is a tool the model calls and the gate never sees"
        f" (in stream: {synthetic_seen_by_model}, hidden from gate: {synthetic_hidden_from_gate})"
    )
    print()
    print("  Consequence: price only the calls `can_use_tool` is consulted about.")
    return 0 if (both and synthetic_hidden_from_gate) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
