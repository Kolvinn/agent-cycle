"""Scripted stand-ins for replay tests — beside the real ones, same trail.

``ScriptedHarness`` runs the **same** inner machinery as the real harness —
the meter, the surface, the hooks, the gate, the tool handlers — with the
model's part replaced by a script. So a test of a whole cycle exercises every
line of the ledger except the subprocess, and exhausting the script is an
error rather than a default: a pipeline that quietly invents an answer is the
failure this project exists to catch.
"""

from __future__ import annotations

import itertools
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import jsonschema

from ..config import Budgets
from ..graph.surface import bare_name
from .events import EventSink, ListSink, TextDone, ToolCalled, ToolResult, TurnFinished, TurnStarted
from .hooks import permission_gate, post_tool_use, pre_tool_use
from .meter import Meter
from .protocol import ApprovalRequest, Approver, FrameInterrupted, StageRequest, TurnResult, Verdict
from .tools import handler_for, schema_for
from .turn import TurnContext
from .wire import validate_payload


@dataclass(frozen=True, slots=True)
class Call:
    """One tool call the scripted model makes, and what the tool returns
    (for evidence tools; in-graph tools compute their own result)."""

    name: str
    input: dict[str, Any]
    result: str = ""


@dataclass(frozen=True, slots=True)
class Turn:
    """What the scripted model does on one turn."""

    payload: dict[str, Any] | None
    calls: tuple[Call, ...] = ()
    text: str = ""
    interrupt: bool = False


@dataclass
class ScriptedHarness:
    """Answers per stage, in order. Runs the real hooks, gate and tools."""

    script: dict[str, list[Turn]]
    approver: Approver
    sink: EventSink = field(default_factory=ListSink)
    budgets: Budgets = field(default_factory=Budgets)
    prices: dict[str, int] = field(default_factory=lambda: {"survey": 1, "read": 2, "webfetch": 3})
    requests: list[StageRequest] = field(default_factory=list)
    _queues: dict[str, deque[Turn]] = field(default_factory=dict)
    _ids: itertools.count = field(default_factory=lambda: itertools.count(1))
    _sessions: itertools.count = field(default_factory=lambda: itertools.count(1))

    def __post_init__(self) -> None:
        self._queues = {stage: deque(turns) for stage, turns in self.script.items()}

    def queue(self, stage: str, turn: Turn) -> None:
        self._queues.setdefault(stage, deque()).append(turn)

    async def run(self, request: StageRequest) -> TurnResult:
        self.requests.append(request)
        q = self._queues.get(request.stage)
        if not q:
            raise AssertionError(
                f"script exhausted for stage {request.stage!r} at {request.label} "
                f"(stages scripted: {sorted(self._queues)})"
            )
        scripted = q.popleft()

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
        )
        if request.conversation and request.fork:
            turn.conversation = f"scripted-{next(self._sessions)}"
        elif request.conversation:
            turn.conversation = request.conversation
        else:
            turn.conversation = f"scripted-{next(self._sessions)}"

        self.sink.emit(TurnStarted(label=request.label, kind="graph", stage=request.stage, cycle=request.cycle))
        pre = pre_tool_use(turn, self.sink)
        post = post_tool_use(turn, self.sink)
        gate = permission_gate(turn, self.sink, self.approver)

        for call in scripted.calls:
            call_id = f"toolu_{next(self._ids):04d}"
            self.sink.emit(ToolCalled(tool_use_id=call_id, name=call.name, input=dict(call.input)))
            decision = await pre({"tool_name": call.name, "tool_input": call.input}, call_id, {})
            outcome = (decision.get("hookSpecificOutput") or {}).get("permissionDecision")
            if outcome == "deny":
                reason = decision["hookSpecificOutput"].get("permissionDecisionReason", "denied")
                self.sink.emit(ToolResult(tool_use_id=call_id, text=reason, is_error=True))
                continue
            tool_input = dict(call.input)
            if outcome != "allow":
                permission = await gate(call.name, tool_input, _Ctx(call_id))
                if getattr(permission, "behavior", "") == "deny":
                    self.sink.emit(ToolResult(tool_use_id=call_id, text=permission.message, is_error=True))
                    continue
                tool_input = permission.updated_input or tool_input
            handler = handler_for(turn, request.stage, bare_name(call.name))
            if handler is not None:
                schema = schema_for(turn, request.stage, bare_name(call.name))
                if schema is not None:
                    jsonschema.validate(instance=tool_input, schema=schema)
                produced = await handler(tool_input)
                text = "\n".join(b.get("text", "") for b in produced.get("content", []))
                is_error = bool(produced.get("is_error"))
            else:
                text, is_error = call.result, False
            self.sink.emit(ToolResult(tool_use_id=call_id, text=text, is_error=is_error))
            turn.record(call_id, text)
            extra = await post({"tool_name": call.name, "tool_input": tool_input, "tool_response": text}, call_id, {})
            context = (extra.get("hookSpecificOutput") or {}).get("additionalContext")
            if context:
                self.sink.emit(TextDone(context))

        if scripted.interrupt:
            self.sink.emit(TurnFinished(label=request.label, ok=False, interrupted=True))
            raise FrameInterrupted(turn.result(None, interrupted=True))

        payload = None
        if scripted.payload is not None:
            payload = validate_payload(request.payload_schema, scripted.payload)
        turn.raw_reply = scripted.text
        if scripted.text:
            self.sink.emit(TextDone(scripted.text))
        self.sink.emit(TurnFinished(label=request.label, ok=payload is not None, session_id=turn.conversation))
        return turn.result(payload)

    async def interrupt(self) -> None:
        return None


@dataclass(frozen=True, slots=True)
class _Ctx:
    tool_use_id: str
    title: str = ""
    description: str = ""


@dataclass
class ScriptedApprover:
    """Verdicts supplied in advance; running out raises rather than defaults."""

    verdicts: deque[Verdict] = field(default_factory=deque)
    answers: deque[dict[str, Any]] = field(default_factory=deque)
    choices: deque[str | None] = field(default_factory=deque)
    asked: list[ApprovalRequest] = field(default_factory=list)
    offered: list[tuple[str, tuple[tuple[str, str], ...], str]] = field(default_factory=list)

    @classmethod
    def approving(cls, n: int, words: str = "") -> ScriptedApprover:
        return cls(verdicts=deque(Verdict(approved=True, answered_by="scripted", words=words) for _ in range(n)))

    @classmethod
    def refusing(cls, n: int, words: str = "") -> ScriptedApprover:
        return cls(verdicts=deque(Verdict(approved=False, answered_by="scripted", words=words) for _ in range(n)))

    async def approve(self, request: ApprovalRequest) -> Verdict:
        self.asked.append(request)
        if not self.verdicts:
            raise AssertionError(f"scripted verdicts exhausted; asked about {request.name} {dict(request.input)}")
        return self.verdicts.popleft()

    async def ask(self, questions: list[dict[str, Any]]) -> dict[str, Any]:
        if not self.answers:
            raise AssertionError("scripted answers exhausted")
        return self.answers.popleft()

    async def choose(self, title: str, options: list[tuple[str, str]], current: str = "") -> str | None:
        """A scripted pick, or ``None`` (leave the setting) when none was scripted."""
        self.offered.append((title, tuple(options), current))
        return self.choices.popleft() if self.choices else None


class AutoApprover:
    """Approves everything and says so in every record. For spikes only."""

    def __init__(self, words: str = "auto-approved (no human present)") -> None:
        self.words = words
        self.asked: list[ApprovalRequest] = []

    async def approve(self, request: ApprovalRequest) -> Verdict:
        self.asked.append(request)
        return Verdict(approved=True, answered_by="auto", words=self.words)

    async def ask(self, questions: list[dict[str, Any]]) -> dict[str, Any]:
        return {q.get("question", ""): (q.get("options") or [{}])[0].get("label", "") for q in questions}

    async def choose(self, title: str, options: list[tuple[str, str]], current: str = "") -> str | None:
        return None
