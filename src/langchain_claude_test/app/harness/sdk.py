"""The real harness — one frame turn over a ``ClaudeSDKClient``.

**One client per frame turn, continuing one conversation per cycle.** The
options a frame needs — which built-ins exist, which in-graph tools, the
payload's ``output_format`` — are per process, so each turn opens its own
client and continues the cycle's conversation with ``resume``. The first
frame of a cycle opens a fresh conversation; that is the cycle boundary. The
conversation lives on disk under the CLI's own session storage, which is what
makes a thread resumed later re-open the same one.

The client must live in a single async context for its whole life, and here it
does: connect, one query, drain, disconnect, all inside :meth:`run`.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    HookMatcher,
    ResultMessage,
    UserMessage,
    ToolResultBlock,
)

from ..config import EVIDENCE_TOOLS, SUBSCRIPTION_ENV, Budgets, ModelSettings
from ..graph.surface import GRAPH_SERVER, STAGE_BUILTINS
from .events import EventSink, Notice, TurnFinished, TurnStarted
from .hooks import permission_gate, post_tool_use, pre_tool_use
from .meter import Meter
from .protocol import Approver, FrameInterrupted, HarnessUnavailable, StageRequest, TurnResult
from .stream import StreamTranslator, tool_result_text
from .tools import graph_server
from .turn import TurnContext
from .wire import to_wire_schema, validate_payload


def compose(brief: str, message: str) -> str:
    if brief and message:
        return f"{brief}\n\n{message}"
    return brief or message or "(continue)"


class SdkHarness:
    def __init__(
        self,
        *,
        sink: EventSink,
        approver: Approver,
        settings: ModelSettings,
        system_prompt: Any,
        cwd: Path,
        budgets: Budgets,
        prices: dict[str, int],
        extra_env: dict[str, str] | None = None,
    ) -> None:
        self.sink = sink
        self.approver = approver
        self.settings = settings
        self.system_prompt = system_prompt
        self.cwd = Path(cwd)
        self.budgets = budgets
        self.prices = prices
        self.extra_env = dict(extra_env or {})
        self._live: ClaudeSDKClient | None = None

    # --- options -------------------------------------------------------------

    def options(self, request: StageRequest, turn: TurnContext) -> ClaudeAgentOptions:
        server = graph_server(turn, request.stage)
        return ClaudeAgentOptions(
            model=self.settings.model,
            thinking=dict(self.settings.thinking),
            effort=self.settings.effort,
            include_partial_messages=True,
            system_prompt=self.system_prompt,
            # An allow-list of built-ins. Bash never exists.
            tools=list(STAGE_BUILTINS[request.stage]),
            # Nothing auto-approved: the meter is a hook and sees everything.
            allowed_tools=[],
            permission_mode="default",
            mcp_servers={GRAPH_SERVER: server} if server is not None else {},
            strict_mcp_config=True,
            # Isolation: no filesystem settings, so no project deny rule can
            # veto the frame and no ambient hook runs inside it.
            setting_sources=[],
            output_format={"type": "json_schema", "schema": to_wire_schema(request.payload_schema)},
            can_use_tool=permission_gate(turn, self.sink, self.approver),
            hooks={
                "PreToolUse": [HookMatcher(hooks=[pre_tool_use(turn, self.sink)])],
                "PostToolUse": [HookMatcher(hooks=[post_tool_use(turn, self.sink)])],
            },
            resume=request.conversation or None,
            fork_session=bool(request.conversation and request.fork),
            cwd=self.cwd,
            env={
                **dict(SUBSCRIPTION_ENV),
                # Fewer than ten tools: tool search would only add a round-trip
                # before the model could see attach_finding's schema.
                "ENABLE_TOOL_SEARCH": "false",
                **self.extra_env,
            },
        )

    # --- the turn ------------------------------------------------------------

    async def run(self, request: StageRequest) -> TurnResult:
        turn = TurnContext(
            request=request,
            meter=Meter(
                stage=request.stage,
                pools=request.pools,
                prices=self.prices,
                default_pool=request.default_pool,
                prior_spend=request.prior_spend,
                graph_write_price=self.budgets.graph_write_price,
            ),
            conversation=request.conversation,
        )
        self.sink.emit(TurnStarted(label=request.label, kind="graph", stage=request.stage, cycle=request.cycle))
        translator = StreamTranslator()
        result_msg: ResultMessage | None = None
        client = ClaudeSDKClient(self.options(request, turn))
        self._live = client
        try:
            await client.connect()
            await client.query(compose(request.brief, request.message))
            async for msg in client.receive_response():
                for event in translator.translate(msg):
                    self.sink.emit(event)
                if isinstance(msg, UserMessage) and isinstance(msg.content, list):
                    for block in msg.content:
                        if isinstance(block, ToolResultBlock):
                            turn.record(block.tool_use_id, tool_result_text(block.content))
                if isinstance(msg, ResultMessage):
                    result_msg = msg
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # the SDK's own errors: process, connection, decode
            self.sink.emit(TurnFinished(label=request.label, ok=False, subtype=type(exc).__name__))
            raise HarnessUnavailable(f"{request.label}: {type(exc).__name__}: {exc}") from exc
        finally:
            self._live = None
            await client.disconnect()

        if result_msg is None:
            self.sink.emit(TurnFinished(label=request.label, ok=False, subtype="no_result"))
            raise HarnessUnavailable(f"{request.label}: the turn produced no result message")

        turn.conversation = result_msg.session_id or request.conversation
        turn.raw_reply = result_msg.result or ""
        turn.cost_usd = result_msg.total_cost_usd
        interrupted = str(result_msg.terminal_reason or "").startswith("aborted")

        payload = None
        if not interrupted and result_msg.structured_output is not None:
            try:
                payload = validate_payload(request.payload_schema, result_msg.structured_output)
            except Exception as exc:  # pydantic — the wire schema and the model disagree
                self.sink.emit(Notice(text=f"structured output did not validate: {exc}", level="warning"))
        elif not interrupted:
            self.sink.emit(
                Notice(
                    text=(
                        f"no structured output ({result_msg.subtype}"
                        + (f", {', '.join(result_msg.errors)}" if result_msg.errors else "")
                        + ")"
                    ),
                    level="warning",
                )
            )

        self.sink.emit(
            TurnFinished(
                label=request.label,
                ok=payload is not None,
                interrupted=interrupted,
                subtype=result_msg.subtype,
                terminal_reason=str(result_msg.terminal_reason or ""),
                cost_usd=result_msg.total_cost_usd,
                session_id=turn.conversation,
            )
        )
        result = turn.result(payload, interrupted=interrupted)
        if interrupted:
            raise FrameInterrupted(result)
        return result

    async def interrupt(self) -> None:
        live = self._live
        if live is not None:
            await live.interrupt()
