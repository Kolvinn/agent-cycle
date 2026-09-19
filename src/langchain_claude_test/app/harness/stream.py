"""SDK messages → harness events.

With partial messages enabled the SDK yields raw API stream events (deltas) as
well as the complete ``AssistantMessage`` for each block, in this order per
block: ``content_block_start`` → deltas → ``AssistantMessage`` →
``content_block_stop``. So a sink sees the deltas as they arrive and then the
finished block, which it uses to replace what it streamed. Tool results arrive
as ``UserMessage`` blocks after the tool ran.
"""

from __future__ import annotations

from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    RateLimitEvent,
    ResultMessage,
    StreamEvent,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from .events import (
    HarnessEvent,
    Notice,
    ResultText,
    SessionInfo,
    TextDelta,
    TextDone,
    ThinkingDelta,
    ThinkingDone,
    ToolCalled,
    ToolInputDelta,
    ToolResult,
    ToolStarted,
)


def tool_result_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict):
            if block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            else:
                parts.append(str(block))
        else:
            parts.append(str(block))
    return "\n".join(parts)


class StreamTranslator:
    """Stateful over one turn: remembers which block index is which tool."""

    def __init__(self) -> None:
        self._tools: dict[int, str] = {}

    def translate(self, msg: Any) -> list[HarnessEvent]:
        if isinstance(msg, StreamEvent):
            return self._stream(msg.event)
        if isinstance(msg, AssistantMessage):
            out: list[HarnessEvent] = []
            for block in msg.content:
                if isinstance(block, TextBlock):
                    out.append(TextDone(block.text))
                elif isinstance(block, ThinkingBlock):
                    out.append(ThinkingDone(block.thinking))
                elif isinstance(block, ToolUseBlock):
                    out.append(ToolCalled(tool_use_id=block.id, name=block.name, input=dict(block.input)))
            return out
        if isinstance(msg, UserMessage):
            out = []
            if isinstance(msg.content, list):
                for block in msg.content:
                    if isinstance(block, ToolResultBlock):
                        out.append(
                            ToolResult(
                                tool_use_id=block.tool_use_id,
                                text=tool_result_text(block.content),
                                is_error=bool(block.is_error),
                            )
                        )
            return out
        if isinstance(msg, SystemMessage):
            return self._system(msg)
        if isinstance(msg, RateLimitEvent):
            info = msg.rate_limit_info
            if info.status == "allowed":
                return []
            return [Notice(text=f"rate limit {info.status} ({info.rate_limit_type})", level="warning")]
        if isinstance(msg, ResultMessage):
            if msg.result:
                return [ResultText(msg.result)]
            return []
        return []

    def _stream(self, event: dict[str, Any]) -> list[HarnessEvent]:
        kind = event.get("type")
        index = int(event.get("index", -1))
        if kind == "content_block_start":
            block = event.get("content_block") or {}
            if block.get("type") == "tool_use":
                tool_id = str(block.get("id", ""))
                self._tools[index] = tool_id
                return [ToolStarted(tool_use_id=tool_id, name=str(block.get("name", "")))]
            return []
        if kind == "content_block_delta":
            delta = event.get("delta") or {}
            dtype = delta.get("type")
            if dtype == "text_delta":
                return [TextDelta(str(delta.get("text", "")))]
            if dtype == "thinking_delta":
                return [ThinkingDelta(str(delta.get("thinking", "")))]
            if dtype == "input_json_delta" and index in self._tools:
                return [ToolInputDelta(tool_use_id=self._tools[index], partial_json=str(delta.get("partial_json", "")))]
            return []
        if kind == "content_block_stop":
            self._tools.pop(index, None)
        return []

    def _system(self, msg: SystemMessage) -> list[HarnessEvent]:
        data = msg.data or {}
        if msg.subtype == "init":
            return [
                SessionInfo(
                    session_id=str(data.get("session_id", "")),
                    model=str(data.get("model", "")),
                    tools=tuple(str(t) for t in data.get("tools", []) or []),
                    slash_commands=tuple(str(c) for c in data.get("slash_commands", []) or []),
                )
            ]
        if msg.subtype == "compact_boundary":
            return [Notice(text="conversation compacted", level="info")]
        return []
