"""The terminal adapter, over ``agentui`` (PyPI: ``agentic-tui``).

The only file in the project that imports a presentation library. Everything it
shows is a string produced elsewhere — the ledger renderers and the trace
formatter — so this module decides *placement*, never *content*.

One deliberate piece of styling: a gate refusal is rendered as the tool call's
own error block rather than as a line of prose. A denial is a thing that
happened to a specific call, and showing it attached to that call is the
difference between watching the gate work and reading a claim that it did.
"""

from __future__ import annotations

from types import TracebackType

from agentui import Session

from ...ledger import trace as tr
from ...ledger.trace import Event, Trace
from .protocol import SignOff

_SIGNOFF_OPTIONS = (
    "approve — that's right",
    "reject — that's wrong",
    "correct it — I'll give you the right claim",
    "park it — I'm not answering this now",
)
_VERDICTS = ("approved", "rejected", "corrected", "parked")

#: Events whose meaning is already carried by a tool-call block, so rendering
#: them again as prose would duplicate what the block says.
_ABSORBED_BY_BLOCKS = frozenset({tr.TOOL_CALL, tr.TOOL_RESULT})


def _md_safe(text: str) -> str:
    """Neutralise the markdown metacharacters that appear in trace lines.

    Node ids are hex and claims are free text, so underscores and asterisks
    turn up often enough to matter.
    """
    for ch in ("\\", "*", "_", "`", "#", "[", "]"):
        text = text.replace(ch, "\\" + ch)
    return text


class InteractiveUI:
    """Drives a real terminal. Satisfies :class:`~.protocol.UI`."""

    def __init__(self, *, width: int | None = None) -> None:
        self._session = Session(width=width, multiline_input=False)
        self._turn = None
        self._open_calls: dict[str, object] = {}
        self._pending_gate: dict[str, str] = {}
        # A private trace, used only to reuse the formatter's per-event layout.
        self._fmt = Trace()

    # --- lifecycle ---------------------------------------------------------

    async def __aenter__(self) -> InteractiveUI:
        await self._session.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self._close_turn()
        await self._session.__aexit__(exc_type, exc, tb)

    async def _open_turn(self):
        if self._turn is None:
            self._turn = self._session.assistant_turn()
            await self._turn.__aenter__()
        return self._turn

    async def _close_turn(self) -> None:
        """Finish the open turn, erroring any tool block left dangling.

        A block that never completed means the run died mid-call; leaving it
        rendered as 'running' forever would misreport that as still in flight.
        """
        for call_id, ctx in list(self._open_calls.items()):
            await ctx.error("call did not complete")  # type: ignore[attr-defined]
            await ctx.__aexit__(None, None, None)  # type: ignore[attr-defined]
        self._open_calls.clear()
        if self._turn is not None:
            await self._turn.__aexit__(None, None, None)
            self._turn = None

    # --- protocol ----------------------------------------------------------

    async def get_input(self, prompt: str = "> ") -> str:
        await self._close_turn()
        try:
            return (await self._session.prompt(prompt)).strip()
        except (EOFError, KeyboardInterrupt):
            return ""

    async def ask_signoff(self, *, claim: str, node_id: str, grounded_in_text: str) -> SignOff:
        await self._close_turn()
        self._session.print(f'\n  grounded in: "{grounded_in_text}"')
        self._session.print(f'  the claim  : "{claim}"\n')

        choice = await self._session.choose(
            f"Sign off on {node_id[:8]}?", _SIGNOFF_OPTIONS, default=0
        )
        verdict = _VERDICTS[choice]

        correction = None
        if verdict == "corrected":
            correction = (await self._session.input("Your version of the claim:")).strip()
            if not correction:
                # An empty correction is not a correction. Rejecting is the
                # honest reading, and it keeps the claim out of the graph.
                verdict = "rejected"

        return SignOff(verdict=verdict, answered_by="human", correction=correction)

    async def show_event(self, event: Event) -> None:
        if event.kind == tr.TURN_STARTED:
            await self._close_turn()
            self._session.print(f"\n{'─' * 60}")
            return

        if event.kind == tr.USER_MESSAGE:
            return  # the prompt already echoed it

        if event.kind == tr.GATE_DECISION:
            await self._on_gate(event)
            return

        if event.kind == tr.TOOL_CALL:
            await self._on_tool_call(event)
            return

        if event.kind == tr.TOOL_RESULT:
            await self._on_tool_result(event)
            return

        if event.kind in _ABSORBED_BY_BLOCKS:
            return

        turn = await self._open_turn()
        await turn.append_markdown(_md_safe(self._fmt._render_one(event)) + "\n\n")

    async def _on_gate(self, event: Event) -> None:
        call_id = event.detail.get("tool_call_id", "")
        executed = event.detail.get("executed")
        reason = event.detail.get("reason", "")
        would = event.detail.get("would_be")

        if executed in ("allow",):
            # Held until the call itself arrives, so the block can carry it.
            self._pending_gate[call_id] = reason
            if would != executed:
                turn = await self._open_turn()
                await turn.append_markdown(
                    _md_safe(f"observe mode — would have been {would}: {reason}") + "\n\n"
                )
            return

        # Refused: render it as the call's own failure.
        turn = await self._open_turn()
        ctx = turn.tool_call(event.detail.get("tool", "?"), event.detail.get("args", {}))
        await ctx.__aenter__()
        await ctx.error(f"{str(executed).upper()} — {reason}")
        await ctx.__aexit__(None, None, None)

    async def _on_tool_call(self, event: Event) -> None:
        call_id = event.detail.get("tool_call_id", "")
        turn = await self._open_turn()
        ctx = turn.tool_call(event.detail.get("tool", "?"), event.detail.get("args", {}))
        await ctx.__aenter__()
        self._open_calls[call_id] = ctx

    async def _on_tool_result(self, event: Event) -> None:
        call_id = event.detail.get("tool_call_id", "")
        ctx = self._open_calls.pop(call_id, None)
        if ctx is None:
            return
        gate_note = self._pending_gate.pop(call_id, "")
        body = str(event.detail.get("text", ""))
        if gate_note:
            body = f"[gate: {gate_note}]\n{body}"
        await ctx.complete(body)  # type: ignore[attr-defined]
        await ctx.__aexit__(None, None, None)  # type: ignore[attr-defined]

    async def show_reply(self, text: str) -> None:
        turn = await self._open_turn()
        await turn.append_markdown(text)
        await self._close_turn()

    async def show_panel(self, title: str, body: str) -> None:
        """Print pre-formatted text exactly as given.

        All three flags are load-bearing. ``markup=False`` stops rich reading
        the ledger's own ``[open]`` / ``[approved]`` status marks as style tags
        and deleting them; ``soft_wrap=True`` stops Mermaid source being
        hard-wrapped mid-token into something that no longer parses; and
        ``highlight=False`` stops paths and numbers being recoloured inside
        text meant to be copied out verbatim.
        """
        await self._close_turn()
        console = self._session.console
        console.print(f"\n{title}\n{'─' * len(title)}", markup=False, highlight=False)
        console.print(body, markup=False, highlight=False, soft_wrap=True)
        console.print("")
