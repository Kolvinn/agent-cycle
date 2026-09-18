"""Headless UI for tests and replays. No TTY, no terminal library.

Messages and sign-offs are supplied up front, so a whole round is
deterministic and re-runnable. Everything rendered is captured rather than
printed, which is what lets a test assert on what the user *would* have seen.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable

from ...ledger.trace import Event
from .protocol import SignOff, Verdict


class ScriptedUI:
    """A UI whose answers are decided in advance.

    Running out of scripted input is an error rather than a default: a test
    that silently approves something it never meant to is exactly the failure
    this project exists to catch, so exhausting the script raises.
    """

    def __init__(
        self,
        *,
        messages: Iterable[str] = (),
        signoffs: Iterable[SignOff | Verdict] = (),
    ) -> None:
        self._messages: deque[str] = deque(messages)
        self._signoffs: deque[SignOff] = deque(
            s if isinstance(s, SignOff) else SignOff(verdict=s, answered_by="scripted")
            for s in signoffs
        )
        self.events: list[Event] = []
        self.replies: list[str] = []
        self.panels: list[tuple[str, str]] = []
        self.questions: list[str] = []

    async def get_input(self, prompt: str = "> ") -> str:
        return self._messages.popleft() if self._messages else ""

    async def ask_signoff(self, *, claim: str, node_id: str, grounded_in_text: str) -> SignOff:
        self.questions.append(claim)
        if not self._signoffs:
            raise AssertionError(
                f"scripted sign-offs exhausted; the runner asked about {claim!r}. "
                "Add the expected verdict to the script rather than letting it default."
            )
        return self._signoffs.popleft()

    async def show_event(self, event: Event) -> None:
        self.events.append(event)

    async def show_reply(self, text: str) -> None:
        self.replies.append(text)

    async def show_panel(self, title: str, body: str) -> None:
        self.panels.append((title, body))
