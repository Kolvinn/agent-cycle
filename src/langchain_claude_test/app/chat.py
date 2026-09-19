"""The default connection — a plain Claude session, held open.

*"plain text just enters whatever default connection to claude."* This is
Claude Code through the SDK: the preset system prompt (or the mode's own), the
CLI's default tools (or the mode's allow-list), permission prompts answered by
the user, and the same streaming the graph frames use. One client per chat
mode, held open across messages so interrupts and queued messages work as they
do in the CLI, and resumed by session id when the session is reopened.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, ResultMessage

from .config import SUBSCRIPTION_ENV, Mode, ModelSettings
from .harness.events import EventSink, Notice, TurnFinished, TurnStarted
from .harness.hooks import chat_gate
from .harness.protocol import Approver
from .harness.stream import StreamTranslator


class ChatDriver:
    def __init__(
        self,
        *,
        mode: Mode,
        base_dir: Path,
        settings: ModelSettings,
        sink: EventSink,
        approver: Approver,
        cwd: Path,
        resume: str = "",
        extra_env: dict[str, str] | None = None,
    ) -> None:
        self.mode = mode
        self.base_dir = base_dir
        self.settings = settings
        self.sink = sink
        self.approver = approver
        self.cwd = Path(cwd)
        self.resume = resume
        self.extra_env = dict(extra_env or {})
        self.session_id: str = resume
        self._client: ClaudeSDKClient | None = None
        self._turns = 0

    def options(self) -> ClaudeAgentOptions:
        kwargs: dict[str, Any] = {}
        if self.mode.tools is not None:
            kwargs["tools"] = list(self.mode.tools)
        return ClaudeAgentOptions(
            model=self.mode.model or self.settings.model,
            thinking=dict(self.settings.thinking),
            effort=self.settings.effort,
            include_partial_messages=True,
            system_prompt=self.mode.sdk_system_prompt(self.base_dir),
            allowed_tools=list(self.mode.allowed_tools),
            permission_mode="default",
            can_use_tool=chat_gate(self.sink, self.approver),
            resume=self.resume or None,
            cwd=self.cwd,
            env={**dict(SUBSCRIPTION_ENV), **self.extra_env},
            **kwargs,
        )

    @property
    def open(self) -> bool:
        return self._client is not None

    async def connect(self) -> None:
        if self._client is None:
            client = ClaudeSDKClient(self.options())
            await client.connect()
            self._client = client

    async def send(self, text: str) -> str:
        """One message in, the whole response streamed out. Returns the session id."""
        await self.connect()
        assert self._client is not None
        self._turns += 1
        label = f"{self.mode.name}.{self._turns}"
        self.sink.emit(TurnStarted(label=label, kind="chat"))
        translator = StreamTranslator()
        result: ResultMessage | None = None
        await self._client.query(text)
        async for msg in self._client.receive_response():
            for event in translator.translate(msg):
                self.sink.emit(event)
            if isinstance(msg, ResultMessage):
                result = msg
        if result is None:
            self.sink.emit(TurnFinished(label=label, ok=False, subtype="no_result"))
            return self.session_id
        self.session_id = result.session_id or self.session_id
        interrupted = str(result.terminal_reason or "").startswith("aborted")
        if result.is_error and not interrupted:
            self.sink.emit(Notice(text=f"turn ended with {result.subtype}: {result.result or ''}"[:300], level="error"))
        self.sink.emit(
            TurnFinished(
                label=label,
                ok=not result.is_error,
                interrupted=interrupted,
                subtype=result.subtype,
                terminal_reason=str(result.terminal_reason or ""),
                cost_usd=result.total_cost_usd,
                session_id=self.session_id,
            )
        )
        return self.session_id

    async def interrupt(self) -> None:
        if self._client is not None:
            await self._client.interrupt()

    async def set_model(self, model: str) -> None:
        self.settings = self.settings.with_model(model)
        if self._client is not None:
            await self._client.set_model(model)

    async def close(self) -> None:
        client, self._client = self._client, None
        if client is not None:
            await client.disconnect()
