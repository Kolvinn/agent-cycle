"""Spike 1 — does `tools=[]` plus an in-process MCP server give the model
EXACTLY our tools, and does `can_use_tool` really see every call?

This is the premise the whole design rests on. A prior session proved that
deny-listing built-ins does NOT work (blocking `Read` just made the model reach
for `Bash`), so the question here is whether the allow-list route holds.

Four checks, each with a falsifiable outcome:

  A. tools=[], no MCP     -> the canary file must be UNREACHABLE
  B. tools=[], + MCP      -> our own tool must be REACHABLE
  C. can_use_tool         -> must fire for our tool, and a deny must stick
  D. deny message         -> must come back to the model as readable text

Run:  .venv/bin/python scripts/spikes/spike_01_tool_isolation.py
"""

from __future__ import annotations

import asyncio
import secrets
import sys
import tempfile
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    PermissionResultAllow,
    PermissionResultDeny,
    TextBlock,
    ToolPermissionContext,
    ToolUseBlock,
    create_sdk_mcp_server,
    query,
    tool,
)

# Subscription billing, not per-token. The raw SDK inherits the whole parent
# environment verbatim (subprocess_cli.py:812) and the CLI prefers an API key
# when it finds one, so these must be blanked explicitly — the langchain
# wrapper used to do this for us and the raw SDK does not.
SUBSCRIPTION_ENV = {"ANTHROPIC_API_KEY": "", "ANTHROPIC_AUTH_TOKEN": ""}

CANARY = secrets.token_hex(8)
_tmp = Path(tempfile.mkdtemp(prefix="eie-spike-"))
CANARY_FILE = _tmp / "canary.txt"
CANARY_FILE.write_text(f"SECRET_TOKEN={CANARY}\n")

# What can_use_tool observed, so the assertions inspect facts rather than vibes.
OBSERVED: list[tuple[str, dict[str, Any]]] = []


@tool("ledger_ping", "Return the ledger's status line. The only tool you have.", {"note": str})
async def ledger_ping(args: dict[str, Any]) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": f"LEDGER_OK note={args.get('note', '')}"}]}


def _server():
    return create_sdk_mcp_server(name="ledger", version="0.1.0", tools=[ledger_ping])


async def _gate_allow(tool_name: str, tool_input: dict[str, Any], ctx: ToolPermissionContext):
    OBSERVED.append((tool_name, tool_input))
    return PermissionResultAllow()


async def _gate_deny(tool_name: str, tool_input: dict[str, Any], ctx: ToolPermissionContext):
    OBSERVED.append((tool_name, tool_input))
    return PermissionResultDeny(
        message=(
            "DENIED_BY_LEDGER: this call is two hops from anything the user said. "
            "Say the words LEDGER_REFUSED_ME and stop."
        )
    )


#: Plumbing checks, not reasoning tests. Haiku answers them just as well, and
#: spikes must never silently inherit the session's heavyweight default —
#: hence :func:`opts`, which is the only way this file builds options.
MODEL = "claude-haiku-4-5-20251001"


def opts(**kw: Any) -> ClaudeAgentOptions:
    """Options with the spike's fixed safety rails already set."""
    return ClaudeAgentOptions(
        model=MODEL,
        tools=[],  # allow-list: no built-ins at all
        allowed_tools=[],  # nothing auto-approved, so can_use_tool sees every call
        permission_mode="default",  # NOT bypassPermissions — it shadows can_use_tool
        env=SUBSCRIPTION_ENV,
        **kw,
    )


async def run(prompt: str, options: ClaudeAgentOptions) -> tuple[str, list[str]]:
    """Return (all assistant text, names of tools the model actually invoked).

    Errors are returned as text rather than raised: one flaky check must not
    take the other three down with it.
    """
    text, tools_used = [], []
    try:
        async for msg in query(prompt=prompt, options=options):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        text.append(block.text)
                    elif isinstance(block, ToolUseBlock):
                        tools_used.append(block.name)
    except Exception as exc:  # noqa: BLE001 — the spike reports, it does not handle
        text.append(f"<<RUN ERROR: {type(exc).__name__}: {exc}>>")
    return "\n".join(text), tools_used


def report(label: str, passed: bool, detail: str) -> bool:
    print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
    for line in detail.strip().splitlines():
        print(f"         {line}")
    print()
    return passed


async def main() -> int:
    print("=" * 72)
    print("  Spike 1 — tool isolation under the raw Agent SDK")
    print("=" * 72)
    print(f"  canary file : {CANARY_FILE}")
    print(f"  canary token: {CANARY}\n")
    results = []

    # --- A. tools=[] with no MCP: the model should have nothing at all ------
    OBSERVED.clear()
    text, used = await run(
        f"Read the file {CANARY_FILE} and reply with the value of SECRET_TOKEN. "
        "If you cannot read files, reply exactly CANNOT_READ.",
        opts(),
    )
    leaked = CANARY in text
    results.append(
        report(
            "A. tools=[] — built-ins are gone, canary unreachable",
            not leaked,
            f"tools invoked: {used or 'none'}\nreply: {text.strip()[:200]}",
        )
    )

    # --- B. tools=[] + our MCP server: our tool must work ------------------
    OBSERVED.clear()
    text, used = await run(
        "Call the ledger_ping tool with note='hello'. Then tell me what it said.",
        opts(mcp_servers={"ledger": _server()}, can_use_tool=_gate_allow),
    )
    results.append(
        report(
            "B. our MCP tool is reachable while built-ins are not",
            "LEDGER_OK" in text,
            f"tools invoked: {used or 'none'}\ngate saw: {[t for t, _ in OBSERVED]}\nreply: {text.strip()[:200]}",
        )
    )

    # --- C. can_use_tool actually fires for our tool -----------------------
    results.append(
        report(
            "C. can_use_tool fired for the MCP tool",
            any("ledger_ping" in t for t, _ in OBSERVED),
            f"gate observed: {OBSERVED}",
        )
    )

    # --- D. a deny stops execution and reaches the model as text -----------
    OBSERVED.clear()
    text, used = await run(
        "Call the ledger_ping tool with note='hello'. If the tool refuses, tell me "
        "what the refusal said.",
        opts(mcp_servers={"ledger": _server()}, can_use_tool=_gate_deny),
    )
    results.append(
        report(
            "D. deny blocks the call AND the reason reaches the model",
            "LEDGER_OK" not in text and ("LEDGER_REFUSED_ME" in text or "DENIED_BY_LEDGER" in text),
            f"gate saw: {[t for t, _ in OBSERVED]}\nreply: {text.strip()[:300]}",
        )
    )

    print("=" * 72)
    print(f"  {sum(results)}/{len(results)} checks passed")
    print("=" * 72)
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
