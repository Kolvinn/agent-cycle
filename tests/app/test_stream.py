"""SDK messages become harness events, in the order a UI needs them."""

from __future__ import annotations

from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    StreamEvent,
    SystemMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from langchain_claude_test.app.harness import events as ev
from langchain_claude_test.app.harness.stream import StreamTranslator


def _se(event):
    return StreamEvent(uuid="u", session_id="s", event=event)


def test_text_and_thinking_deltas_then_the_finished_blocks():
    t = StreamTranslator()
    out = []
    out += t.translate(_se({"type": "content_block_start", "index": 0, "content_block": {"type": "thinking"}}))
    out += t.translate(_se({"type": "content_block_delta", "index": 0, "delta": {"type": "thinking_delta", "thinking": "hm"}}))
    out += t.translate(_se({"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": "Hel"}}))
    out += t.translate(_se({"type": "content_block_delta", "index": 1, "delta": {"type": "text_delta", "text": "lo"}}))
    out += t.translate(AssistantMessage(content=[TextBlock(text="Hello")], model="m"))
    assert [type(e).__name__ for e in out] == ["ThinkingDelta", "TextDelta", "TextDelta", "TextDone"]
    assert out[-1].text == "Hello"


def test_tool_calls_stream_and_then_complete_and_then_return():
    t = StreamTranslator()
    out = []
    out += t.translate(_se({"type": "content_block_start", "index": 2, "content_block": {"type": "tool_use", "id": "toolu_1", "name": "Read"}}))
    out += t.translate(_se({"type": "content_block_delta", "index": 2, "delta": {"type": "input_json_delta", "partial_json": '{"file_'}}))
    out += t.translate(AssistantMessage(content=[ToolUseBlock(id="toolu_1", name="Read", input={"file_path": "a.py"})], model="m"))
    out += t.translate(_se({"type": "content_block_stop", "index": 2}))
    out += t.translate(UserMessage(content=[ToolResultBlock(tool_use_id="toolu_1", content="1→x = 1")]))
    kinds = [type(e).__name__ for e in out]
    assert kinds == ["ToolStarted", "ToolInputDelta", "ToolCalled", "ToolResult"]
    assert out[2].input == {"file_path": "a.py"}
    assert out[3].text == "1→x = 1"


def test_init_and_result_messages():
    t = StreamTranslator()
    info = t.translate(SystemMessage(subtype="init", data={"session_id": "abc", "model": "m", "slash_commands": ["compact"], "tools": ["Read"]}))
    assert isinstance(info[0], ev.SessionInfo) and info[0].session_id == "abc" and info[0].slash_commands == ("compact",)
    res = t.translate(ResultMessage(subtype="success", duration_ms=1, duration_api_ms=1, is_error=False, num_turns=1, session_id="abc", result="done"))
    assert isinstance(res[0], ev.ResultText) and res[0].text == "done"
