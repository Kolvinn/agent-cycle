from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Literal, Mapping, Protocol

from pydantic import BaseModel

if TYPE_CHECKING:  # pragma: no cover
    from claude_agent_sdk import PermissionResult, ToolPermissionContext

#: The CLI prefers an API key over OAuth when one is present, and the SDK passes
#: the parent environment through verbatim. Blanking these is what keeps the run
#: on the subscription. Same constant, same reason, as `session/model.py:33`.
SUBSCRIPTION_ENV: Mapping[str, str] = {
    "ANTHROPIC_API_KEY": "",
    "ANTHROPIC_AUTH_TOKEN": "",
}

#: The synthetic tool call ``output_format`` arrives as. It appears in the
#: model's tool-use stream and is **never shown to ``can_use_tool``** (measured,
#: `spike_05_tools_and_structured_output.py`). Two consequences for a budget
#: that decrements per call:
#: price only what the gate is consulted about, and no invariant may claim that
#: every tool call passes the gate — for this one call it is false.
STRUCTURED_OUTPUT_TOOL = "StructuredOutput"

from claude_agent_sdk import TextBlock, ThinkingBlock, query, ClaudeAgentOptions
from claude_agent_sdk.types import (
    AssistantMessage,
    ConversationResetMessage,
    RateLimitEvent,
    ResultMessage,
    StreamEvent,
    SystemMessage,
    TaskNotificationMessage,
    TaskProgressMessage,
    TaskStartedMessage,
    UserMessage,
)
import asyncio


def build_options() -> Any:
    """Assemble ``ClaudeAgentOptions`` for one stage turn.

    Every field set here is load-bearing and the reason is on the line. The
    import is local for the same reason `session/model.py` does it: the module
    should be importable, and testable, without the SDK present.
    """

    return ClaudeAgentOptions(
        model="sonnet",
        thinking={"type": "adaptive", "display": "summarized"},
        # `thinking` takes a ThinkingConfig dict (e.g. {"type": "enabled", ...}),
        # not a level string. `effort` is the Literal["low"|"medium"|"high"|"xhigh"|"max"]
        # that controls thinking depth.
        effort="medium",
        include_partial_messages=True,
        # An allow-list. Deny-listing leaked under test, so there is no built-in
        # surface at all and every tool is in-graph.
        tools=[],
        # Nothing auto-approved, so the gate is consulted for every call. An
        # entry here allowing a whole tool would shadow it — including the
        # authority-bearing ones, which would approve them with nobody asked.
        allowed_tools=[],
        # NOT bypassPermissions — that approves before the gate is consulted.
        permission_mode="default",
        # system_prompt=request.system,
        # # The only structured-output mechanism the Claude Code surface has.
        # # There is no tool_choice forcing and no response_format.
        # output_format={"type": "json_schema", "schema": to_wire_schema(request.payload_schema)},
        # # The budget and the approval, behind one callback.
        # can_use_tool=gate.can_use_tool,
        # mcp_servers=mcp_servers,
        env=dict(SUBSCRIPTION_ENV),
    )


async def stream_response():
    options = build_options()
    # ClaudeAgentOptions(
    #
    #     allowed_tools=["Bash", "Read"],
    # )

    async for message in query(
        prompt="Write me a short but complex poem. You should think at least a little bit before replying",
        options=options,
    ):
        if isinstance(message, StreamEvent):
            event = message.event
            #print(event.get("delta", {}))
            # if event.get("type") == {} or event.get("type") is None:
            #     continue
            delta = event.get("delta", {})
            if delta.get("type") == "text_delta":
                print(delta.get("text", ""), end="", flush=True)
            elif delta.get("type") == "thinking_delta":
                print(delta.get("thinking", ""), end="", flush=True)
            continue
        # TaskStartedMessage/TaskProgressMessage/TaskNotificationMessage subclass
        # SystemMessage, so they must be checked before the SystemMessage branch.
        elif isinstance(message, TaskStartedMessage):
            continue
        elif isinstance(message, TaskProgressMessage):
            continue
        elif isinstance(message, TaskNotificationMessage):
            continue
        elif isinstance(message, SystemMessage):
            continue
        elif isinstance(message, RateLimitEvent):
            continue
        elif isinstance(message, ConversationResetMessage):
            continue
        elif isinstance(message, UserMessage):
            continue
        elif isinstance(message, AssistantMessage):

            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block)
                elif isinstance(block, ThinkingBlock):
                    print(block.thinking)
        elif isinstance(message, ResultMessage):
            continue


asyncio.run(stream_response())
