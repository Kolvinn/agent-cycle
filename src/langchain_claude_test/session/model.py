"""Model access, behind a protocol.

Same split as the UI, for the same reason: the runner depends on an interface,
so a whole round replays deterministically under :class:`FakeModel` with no
tokens spent and no network — and the parts that are genuinely about prompting
stay isolated in the one implementation that talks to a model.

Everything here is recorded. A call's request lands on disk *before* it runs,
so a hang, a crash or a safeguard refusal still leaves behind exactly what was
sent — which is the difference between a log you can debug from and one that
only describes successes.
"""

from __future__ import annotations

import json
import re
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from ..runlog import ModelCallRecord

T = TypeVar("T", bound=BaseModel)

#: Spikes and phase calls are mechanical, not reasoning-heavy. Never inherit
#: the ambient session default — that is how an expensive model gets spawned
#: without anyone choosing it.
DEFAULT_MODEL = "claude-haiku-4-5-20251001"

#: The raw SDK inherits the whole parent environment, and the CLI prefers an
#: API key when it finds one. Blanking these keeps the run on the subscription.
SUBSCRIPTION_ENV = {"ANTHROPIC_API_KEY": "", "ANTHROPIC_AUTH_TOKEN": ""}


class ModelUnavailable(RuntimeError):
    """The model could not be reached, or refused to answer."""


class ModelClient(Protocol):
    async def structured(
        self,
        *,
        label: str,
        system: str,
        prompt: str,
        schema: type[T],
        turn: int,
        record: ModelCallRecord | None = None,
    ) -> T:
        """One locked-schema call. Returns a validated model or raises.

        ``record`` is opened by the *caller*, not by the implementation — that
        is what keeps the on-disk trail identical whether a real model or a
        scripted one answered. An implementation may enrich it (thinking,
        usage) but must not depend on it being present.
        """
        ...


def _extract_json(text: str) -> dict[str, Any]:
    """Pull one JSON object out of a model reply.

    Tries the whole string first, since a correctly-configured structured call
    returns bare JSON. The fenced and embedded fallbacks exist because a model
    that wraps its answer in prose has still answered — refusing that would
    discard a good response over formatting.
    """
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))

    start, depth = text.find("{"), 0
    if start != -1:
        for i in range(start, len(text)):
            depth += (text[i] == "{") - (text[i] == "}")
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise ModelUnavailable(f"no JSON object in reply: {text[:200]!r}")


class FakeModel:
    """A scripted model for tests and replays.

    Responses are queued per label, so a test states what each phase returns
    without caring about call order. Running out is an error rather than a
    default — a pipeline that quietly invents a response is the exact failure
    mode this project exists to catch.
    """

    def __init__(self, responses: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self._queued = {k: list(v) for k, v in (responses or {}).items()}
        self.calls: list[tuple[str, str]] = []

    def queue(self, label: str, payload: dict[str, Any]) -> None:
        self._queued.setdefault(label, []).append(payload)

    async def structured(
        self,
        *,
        label: str,
        system: str,
        prompt: str,
        schema: type[T],
        turn: int,
        record: ModelCallRecord | None = None,
    ) -> T:
        self.calls.append((label, prompt))
        queue = self._queued.get(label)
        if not queue:
            raise AssertionError(
                f"FakeModel has no queued response for {label!r} "
                f"(queued labels: {sorted(self._queued)})"
            )
        return schema.model_validate(queue.pop(0))


class SdkModel:
    """The real client: one `claude` CLI subprocess per call, no built-in tools.

    Deliberately one-shot. These are locked-schema phase calls with no tool use
    of their own, so there is nothing to keep a session alive for — and a fresh
    subprocess means a phase can never inherit context from an earlier one it
    was not given explicitly.
    """

    def __init__(self, *, model: str = DEFAULT_MODEL) -> None:
        self.model = model

    async def structured(
        self,
        *,
        label: str,
        system: str,
        prompt: str,
        schema: type[T],
        turn: int,
        record: ModelCallRecord | None = None,
    ) -> T:
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            ResultMessage,
            TextBlock,
            ThinkingBlock,
            query,
        )

        json_schema = schema.model_json_schema()
        options = ClaudeAgentOptions(
            model=self.model,
            tools=[],  # allow-list: no built-ins. Deny-listing is bypassable.
            allowed_tools=[],
            permission_mode="default",
            system_prompt=system,
            output_format={"type": "json_schema", "schema": json_schema},
            env=SUBSCRIPTION_ENV,
        )

        texts: list[str] = []
        structured: Any = None
        result_text: str | None = None

        async for msg in query(prompt=prompt, options=options):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        texts.append(block.text)
                    elif isinstance(block, ThinkingBlock) and record is not None:
                        record.thinking.append(block.thinking)
            elif isinstance(msg, ResultMessage):
                # `output_format` delivers the answer on its own channel, not
                # as a TextBlock. Reading only the blocks yields an empty reply
                # even though the model answered — confirmed by a live run
                # whose usage showed 361 output tokens and no text.
                structured = getattr(msg, "structured_output", None)
                result_text = getattr(msg, "result", None)
                if record is not None:
                    record.usage = dict(getattr(msg, "usage", {}) or {})
                    record.error = "; ".join(getattr(msg, "errors", None) or []) or None
            if record is not None:
                record.raw_messages.append(type(msg).__name__)

        # Preferred order: the typed channel, then the CLI's result text, then
        # whatever the assistant said in the open.
        reply = result_text if result_text else "\n".join(texts)
        if record is not None:
            record.raw_reply = reply
            record.structured_output = structured

        if structured is not None:
            try:
                return schema.model_validate(structured)
            except ValidationError as exc:
                raise ModelUnavailable(
                    f"{label}: structured_output did not match schema — {exc}"
                ) from exc

        if not (reply or "").strip():
            raise ModelUnavailable(
                f"{label}: empty reply and no structured_output "
                f"(messages seen: {record.raw_messages if record else '?'})"
            )

        try:
            return schema.model_validate(_extract_json(reply))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise ModelUnavailable(f"{label}: reply did not match schema — {exc}") from exc
