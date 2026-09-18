"""The narrow surface the runner is allowed to know about.

Deliberately small. The round driver must stay headless — testable with no
TTY, no terminal library, and no model — so everything it wants from a human
or a screen goes through this protocol and nothing else.

That has two consequences worth naming, because both were requirements rather
than tidiness:

- the whole pipeline runs under :class:`~.scripted.ScriptedUI` for repeatable
  tests, with sign-offs supplied in advance;
- the interactive implementation is one swappable file, so a presentation
  library going stale costs one adapter rather than the project.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from ...ledger.trace import Event

#: What a human can do with a proposed assumption. ``correct`` carries
#: replacement text: the user rewriting the claim in their own words, which
#: makes their correction a depth-0 source rather than another agent guess.
Verdict = Literal["approved", "rejected", "corrected", "parked"]


@dataclass(frozen=True, slots=True)
class SignOff:
    """A human's answer on one pending implicit.

    ``answered_by`` is not decoration. A prior attempt at this shipped a
    human-in-the-loop stub that returned "Approved, execute operation." with no
    human present, and nothing in the log said so. Every implementation must
    set this honestly, and the trace surfaces anything that is not ``human``.
    """

    verdict: Verdict
    answered_by: Literal["human", "scripted", "auto"]
    correction: str | None = None

    def __post_init__(self) -> None:
        if self.verdict == "corrected" and not self.correction:
            raise ValueError("a 'corrected' verdict must carry the user's replacement text")


@runtime_checkable
class UI(Protocol):
    """Everything the runner may ask of the outside world."""

    async def get_input(self, prompt: str = "> ") -> str:
        """Next user message. Empty string means the session is over."""
        ...

    async def ask_signoff(self, *, claim: str, node_id: str, grounded_in_text: str) -> SignOff:
        """Put one pending implicit to the human and wait.

        ``grounded_in_text`` is passed so the question can show what the claim
        is hanging off — a user cannot judge a derivation they can't see the
        parent of.
        """
        ...

    async def show_event(self, event: Event) -> None:
        """Render one trace event as it happens."""
        ...

    async def show_reply(self, text: str) -> None:
        """Render the agent's round-end findings."""
        ...

    async def show_panel(self, title: str, body: str) -> None:
        """Render a block of pre-formatted text (a ledger digest, a diagram)."""
        ...
