"""The seams the graph and the shell depend on.

``StageHarness`` is narrow on purpose: the graph asks for one turn and gets a
result. ``Approver`` is who answers when a call needs a human. Both have a
scripted implementation beside the real one, so a whole cycle replays with no
model and no terminal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Mapping, Protocol

from pydantic import BaseModel

from ..graph.state import Decision, Explicit, Finding, Parked, ProposedWrite, SpendEntry
from ..graph.surface import Stage

# ---------------------------------------------------------------------------
# What a node asks for, and what it gets back
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Counts:
    """How many of each record this cycle already holds, so the ids the turn
    assigns continue the sequence rather than restart it."""

    findings: int = 0
    proposals: int = 0
    explicits: int = 0


@dataclass(frozen=True, slots=True)
class StageRequest:
    """One harness turn, as a frame describes it.

    One frame turn is one whole conversation turn with the model, not one tool
    call: it can spend several priced calls *and* return a typed payload.
    """

    label: str
    stage: Stage
    cycle: int
    #: The frame's instructions. Sent once, as the first message of the frame;
    #: the conversation continues, so nothing is re-sent after that.
    brief: str
    #: This turn's message. May be empty when the brief is the whole message.
    message: str
    #: The pydantic model the answer must validate against.
    payload_schema: type[BaseModel]
    #: The SDK session to continue. Empty opens a fresh conversation, which is
    #: the cycle boundary made mechanical.
    conversation: str = ""
    #: Continue as a fork — a new session id with the same history — because
    #: another branch of the thread also continues the original.
    fork: bool = False
    #: Pool name -> cap. One per turn in practice; empty means every priced
    #: call is refused before it is priced.
    pools: Mapping[str, int] = field(default_factory=dict)
    default_pool: str = ""
    prior_spend: tuple[SpendEntry, ...] = ()
    #: Every message the user has sent this cycle. A proposed fact must be a
    #: verbatim span of one of them.
    said: tuple[str, ...] = ()
    #: Ids an alteration may target.
    node_ids: frozenset[str] = frozenset()
    #: Resolves the model's ``target`` on ``attach_finding`` to a node id.
    #: ``None`` refuses the finding. The frame knows how to map; the harness
    #: does not.
    finding_target: Callable[[str], str | None] | None = None
    #: Renders the running count appended after every priced call.
    status: Callable[[int], str] | None = None
    existing: Counts = field(default_factory=Counts)


@dataclass(frozen=True, slots=True)
class TurnResult:
    """What one harness turn produced. Spend is returned, never applied."""

    payload: BaseModel | None
    #: The SDK session id after this turn — what the next frame continues.
    conversation: str = ""
    spend: tuple[SpendEntry, ...] = ()
    refused: tuple[str, ...] = ()
    findings: tuple[Finding, ...] = ()
    proposals: tuple[ProposedWrite, ...] = ()
    decisions: tuple[Decision, ...] = ()
    explicits: tuple[Explicit, ...] = ()
    parked: tuple[Parked, ...] = ()
    tool_results: Mapping[str, str] = field(default_factory=dict)
    raw_reply: str = ""
    interrupted: bool = False
    cost_usd: float | None = None


class FrameInterrupted(RuntimeError):
    """The user interrupted the turn. Carries what the turn had so far.

    The frame lets it propagate: the run stops at the last committed
    checkpoint and nothing resumes on its own.
    """

    def __init__(self, partial: TurnResult) -> None:
        super().__init__("frame interrupted by the user")
        self.partial = partial


class HarnessUnavailable(RuntimeError):
    """The model could not be reached, or returned no usable answer."""


class StageHarness(Protocol):
    async def run(self, request: StageRequest) -> TurnResult: ...

    async def interrupt(self) -> None:
        """Cancel the turn in flight, if any."""
        ...


# ---------------------------------------------------------------------------
# Approval — who answers when a call needs a human
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    """One call put to the user, inside a live turn."""

    kind: Literal["alteration", "tool"]
    tool_use_id: str
    name: str
    input: Mapping[str, Any]
    title: str = ""
    description: str = ""
    stage: str = ""


@dataclass(frozen=True, slots=True)
class Verdict:
    """The user's answer. ``words`` matter most — they go back to the model.

    ``answered_by`` is not decoration: an earlier attempt in this repository
    shipped a human-in-the-loop stub that returned "Approved" with no human
    present. Anything not ``human`` is meant to be visible.
    """

    approved: bool
    answered_by: Literal["human", "scripted", "auto"]
    words: str = ""


class Approver(Protocol):
    async def approve(self, request: ApprovalRequest) -> Verdict:
        """Put one call to whoever decides, and wait."""
        ...

    async def ask(self, questions: list[dict[str, Any]]) -> dict[str, Any]:
        """Answer the model's ``AskUserQuestion``: question text -> label(s)."""
        ...


class NoApprover(RuntimeError):
    """A call needed a human and nobody was wired up to answer."""


class NobodyApproves:
    """The default. Raises rather than deciding — a wiring mistake, so loud."""

    async def approve(self, request: ApprovalRequest) -> Verdict:
        raise NoApprover(f"{request.name} needs an answer and no approver is configured")

    async def ask(self, questions: list[dict[str, Any]]) -> dict[str, Any]:
        raise NoApprover("the model asked a question and no approver is configured")


def refused_by_user(verdict: Verdict) -> str:
    """What the model is shown when the user says no. Marked as the user speaking."""
    if not verdict.words:
        return "REFUSED BY THE USER. No reason was given."
    return f"REFUSED BY THE USER. Their words, verbatim: {verdict.words}"


def approved_by_user(verdict: Verdict) -> str:
    if not verdict.words:
        return "APPROVED BY THE USER."
    return f"APPROVED BY THE USER. Their words, verbatim: {verdict.words}"
