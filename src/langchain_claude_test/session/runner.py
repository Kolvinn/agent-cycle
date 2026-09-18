"""The round driver.

Headless: it talks to a :class:`~.ui.protocol.UI`, a
:class:`~.model.ModelClient` and the ledger, and to nothing else. No terminal
library, no SDK import. That is what lets a whole round replay under
``ScriptedUI`` + ``FakeModel`` with no tokens spent.

The order of phases is fixed here, in code. The model's only freedom is what to
put in each schema's fields — it never decides what happens next.

    user words
      -> extract explicits          (verbatim, or refused)
      -> orient                      FREE — forms no claim, costs no hop
      -> assume                      one claim per open explicit
      -> SIGN-OFF                    the user, always; never self-report
      -> evidence                    GATED — one look, scoped to the approved claim
      -> source                      lands on the link, checked three ways
      -> reply                       once no explicit is left open

Every step writes to the run log before moving on, so an abandoned run is still
a readable one.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..ledger import trace as tr
from ..ledger.graph import (
    apply_source,
    form_implicit,
    node,
    open_explicits,
    register_explicit,
    set_status,
)
from ..ledger.models import NewExplicit, NewImplicit, Source
from ..ledger.render import to_digest, to_mermaid
from ..runlog import RunLog
from . import phases as ph
from .gate import Gate, Policy
from .model import ModelClient, ModelUnavailable
from .state import SessionState
from .tools import ToolError, ToolSpec, call_tool, make_tools
from .ui.protocol import UI


@dataclass(frozen=True, slots=True)
class ToolOutcome:
    """What came back from one attempted tool call."""

    ran: bool
    text: str
    call_id: str


class Runner:
    """Drives rounds against one ledger."""

    def __init__(
        self,
        *,
        model: ModelClient,
        ui: UI,
        runlog: RunLog,
        fixture_root: Path,
        policy: Policy | None = None,
        state: SessionState | None = None,
    ) -> None:
        self.model = model
        self.ui = ui
        self.log = runlog
        self.state = state or SessionState()
        self.tools = make_tools(fixture_root)
        self.gate = Gate(self.state, policy=policy)

    # --- plumbing ----------------------------------------------------------

    async def _emit(self, kind: str, **detail: Any):
        ev = self.log.event(kind, turn=self.state.turn, **detail)
        await self.ui.show_event(ev)
        return ev

    async def _ask(self, label: str, system: str, prompt: str, schema: type):
        """One phase call, recorded whoever answers it.

        The record is opened here rather than inside the model client so that a
        scripted run and a live one leave the same trail on disk — a test path
        that logs differently from production is worse than one that does not
        log at all, because it looks covered.
        """
        with self.log.model_call(
            label,
            turn=self.state.turn,
            request={
                "label": label,
                "system": system,
                "prompt": prompt,
                "schema_name": schema.__name__,
                # the real JSON Schema, not just its name — a phase that
                # fails validation is only debuggable against what was sent
                "schema": schema.model_json_schema(),
            },
        ) as rec:
            out = await self.model.structured(
                label=label,
                system=system,
                prompt=prompt,
                schema=schema,
                turn=self.state.turn,
                record=rec,
            )
            rec.response = out.model_dump(mode="json")
            return out

    async def _call_tool(
        self, name: str, args: dict[str, Any], *, for_node_id: str | None = None
    ) -> ToolOutcome:
        """Put one call past the gate, then run it if allowed.

        A refusal is returned as *text* rather than raised. That is the whole
        gating mechanism: the model reads a refusal the same way it reads a
        result, so the same channel carries both.
        """
        spec: ToolSpec = self.tools[name]
        full_args = dict(args)
        if for_node_id:
            full_args["for_node_id"] = for_node_id

        decision = self.gate.decide(spec, full_args)

        with self.log.tool_call(name, turn=self.state.turn, args=full_args, tier=spec.tier) as rec:
            rec.would_be = decision.would_be
            rec.executed = decision.executed
            rec.reason = decision.reason
            rec.rule = decision.rule
            rec.for_node_id = decision.for_node_id

            await self._emit(
                tr.GATE_DECISION,
                tool=name,
                tier=spec.tier,
                args=full_args,
                tool_call_id=rec.call_id,
                would_be=decision.would_be,
                executed=decision.executed,
                reason=decision.reason,
                rule=decision.rule,
            )

            if not decision.runs:
                rec.result = f"REFUSED ({decision.rule}): {decision.reason}"
                return ToolOutcome(False, rec.result, rec.call_id)

            await self._emit(tr.TOOL_CALL, tool=name, args=full_args, tool_call_id=rec.call_id)
            try:
                text = call_tool(spec, full_args)
            except ToolError as exc:
                rec.error = str(exc)
                await self._emit(tr.TOOL_RESULT, tool_call_id=rec.call_id, text=f"ERROR: {exc}")
                return ToolOutcome(False, f"ERROR: {exc}", rec.call_id)

            rec.result = text
            self.state.record_result(rec.call_id, text)
            if decision.for_node_id and spec.tier == "gated":
                self.state.spend_evidence(decision.for_node_id)
            await self._emit(tr.TOOL_RESULT, tool_call_id=rec.call_id, text=text)
            return ToolOutcome(True, text, rec.call_id)

    # --- phases ------------------------------------------------------------

    async def _extract(self, message: str) -> list[str]:
        """Register the user's own words. Anything not found verbatim is refused."""
        out = await self._ask("extract", ph.EXTRACT_SYSTEM, ph.extract_prompt(message), ph.Extraction)
        self.state.user_named_paths.update(out.named_paths)

        registered: list[str] = []
        for quote in out.quotes:
            start = message.find(quote)
            if start < 0:
                await self._emit(
                    tr.EXTRACTION_REJECTED,
                    quote=quote,
                    reason="not a verbatim span of the message — paraphrase is already inference",
                )
                continue
            r = register_explicit(
                NewExplicit(quote=quote, start=start),
                current_graph=self.state.graph,
                turn=self.state.turn,
                message_text=message,
            )
            if not r:
                await self._emit(tr.EXTRACTION_REJECTED, quote=quote, reason=r.message)
                continue
            self.state.graph = r.graph
            registered.append(r.node_ids[0])
            await self._emit(
                tr.EXPLICIT_REGISTERED,
                node_id=r.node_ids[0],
                quote=quote,
                span=[start, start + len(quote)],
            )
        return registered

    async def _orient(self, explicit_texts: list[str]) -> str:
        out = await self._ask("orient", ph.ORIENT_SYSTEM, ph.orient_prompt(explicit_texts), ph.Orientation)
        outcome = await self._call_tool("list_dir", {"path": out.path})
        return outcome.text

    async def _assume(self, explicit_id: str, orientation: str) -> str | None:
        explicit = node(self.state.graph, explicit_id)
        assert explicit is not None
        out = await self._ask("assume", ph.ASSUME_SYSTEM, ph.assume_prompt(explicit.text, orientation), ph.Assumption)
        r = form_implicit(
            NewImplicit(claim=out.claim, grounded_in=explicit_id),
            current_graph=self.state.graph,
            turn=self.state.turn,
        )
        if not r:
            await self._emit(tr.ASSUMPTION_REJECTED, reason=r.message, claim=out.claim)
            return None
        self.state.graph = r.graph
        await self._emit(
            tr.ASSUMPTION_FORMED,
            node_id=r.node_ids[0],
            grounded_in=explicit_id,
            claim=out.claim,
            why=out.why,
        )
        return r.node_ids[0]

    async def _sign_off(self, implicit_id: str, explicit_id: str) -> str:
        """Put the claim to the user. The only way an implicit ever closes."""
        implicit = node(self.state.graph, implicit_id)
        explicit = node(self.state.graph, explicit_id)
        assert implicit is not None and explicit is not None

        await self._emit(tr.SIGNOFF_REQUESTED, node_id=implicit_id, claim=implicit.text)
        answer = await self.ui.ask_signoff(
            claim=implicit.text, node_id=implicit_id, grounded_in_text=explicit.text
        )
        await self._emit(
            tr.SIGNOFF_ANSWERED,
            node_id=implicit_id,
            verdict=answer.verdict,
            answered_by=answer.answered_by,
            correction=answer.correction,
        )

        status = "rejected" if answer.verdict == "corrected" else answer.verdict
        r = set_status(implicit_id, status, current_graph=self.state.graph, by_user=True)
        if r:
            self.state.graph = r.graph

        # A correction is the user's own words, so it enters as a new explicit
        # rather than as a revised guess of ours.
        if answer.verdict == "corrected" and answer.correction:
            c = register_explicit(
                NewExplicit(quote=answer.correction, start=0),
                current_graph=self.state.graph,
                turn=self.state.turn,
                message_text=answer.correction,
            )
            if c:
                self.state.graph = c.graph
                await self._emit(
                    tr.EXPLICIT_REGISTERED,
                    node_id=c.node_ids[0],
                    quote=answer.correction,
                    span=[0, len(answer.correction)],
                    note="user correction",
                )
        return status

    async def _source(self, implicit_id: str, explicit_id: str) -> bool:
        """One gated look, then the most relevant line onto the link."""
        implicit = node(self.state.graph, implicit_id)
        explicit = node(self.state.graph, explicit_id)
        assert implicit is not None and explicit is not None

        plan = await self._ask("evidence", ph.EVIDENCE_SYSTEM, ph.evidence_prompt(implicit.text, explicit.text), ph.EvidencePlan)
        outcome = await self._call_tool(
            "grep", {"pattern": plan.pattern}, for_node_id=implicit_id
        )
        if not outcome.ran:
            return False

        choice = await self._ask("source", ph.SOURCE_SYSTEM, ph.source_prompt(implicit.text, explicit.text, outcome.text), ph.SourceChoice)
        await self._emit(
            tr.SOURCE_PROPOSED, locator=choice.locator, excerpt=choice.excerpt, answers=choice.answers
        )

        edge = _grounds_edge_id(self.state.graph, implicit_id)
        r = apply_source(
            edge,
            Source(
                locator=choice.locator,
                excerpt=choice.excerpt,
                answers=choice.answers,
                tool_call_id=outcome.call_id,
            ),
            current_graph=self.state.graph,
            tool_results=self.state.tool_results,
        )
        if not r:
            await self._emit(tr.SOURCE_REJECTED, reason=r.message, locator=choice.locator)
            return False
        self.state.graph = r.graph
        await self._emit(
            tr.SOURCE_APPLIED, edge_id=edge, locator=choice.locator, answers=choice.answers
        )
        return True

    # --- the round ---------------------------------------------------------

    async def run_round(self, message: str) -> None:
        self.state.turn += 1
        self.state.current_message = message
        await self._emit(tr.TURN_STARTED)
        await self._emit(tr.USER_MESSAGE, text=message)

        explicit_ids = await self._extract(message)
        if not explicit_ids:
            await self.ui.show_reply(
                "I could not quote anything from that message verbatim, so nothing was "
                "registered. Could you restate what you want?"
            )
            self.log.snapshot(self.state.graph, turn=self.state.turn)
            return

        texts = [node(self.state.graph, e).text for e in explicit_ids]  # type: ignore[union-attr]
        orientation = await self._orient(texts)

        # One claim per open explicit; the round ends when none are left open.
        for explicit_id in explicit_ids:
            implicit_id = await self._assume(explicit_id, orientation)
            if implicit_id is None:
                continue
            verdict = await self._sign_off(implicit_id, explicit_id)
            if verdict == "approved":
                await self._source(implicit_id, explicit_id)
            r = set_status(explicit_id, "addressed", current_graph=self.state.graph, by_user=False)
            if r:
                self.state.graph = r.graph

        digest = to_digest(self.state.graph, turn=self.state.turn)
        try:
            findings = await self._ask("reply", ph.REPLY_SYSTEM, ph.reply_prompt(digest), ph.Findings)
            reply = findings.text
        except ModelUnavailable as exc:
            reply = f"(could not compose findings: {exc})"

        await self._emit(tr.REPLY_SENT, text=reply)
        await self.ui.show_reply(reply)
        await self.ui.show_panel("LEDGER", digest)
        await self.ui.show_panel("MERMAID", to_mermaid(self.state.graph, title=f"turn {self.state.turn}"))
        self.log.snapshot(self.state.graph, turn=self.state.turn)

        # The round is responsible for the explicits it opened. A correction
        # given during sign-off enters as a *new* explicit in the user's own
        # words, and that is not this round's to answer — it carries forward,
        # visibly, rather than being swept up or silently dropped.

        
        still_open = [n for n in open_explicits(self.state.graph) if n.id in explicit_ids]
        assert not still_open, f"round ended with {len(still_open)} of its own explicits open"

        carried = [n for n in open_explicits(self.state.graph) if n.id not in explicit_ids]
        if carried:
            await self._emit(
                "explicits_carried_forward", 
                node_ids=[n.id for n in carried],
                texts=[n.text for n in carried],
            )

    async def run(self) -> None:
        """Rounds until the user stops."""
        while True:
            message = await self.ui.get_input()
            if not message:
                return
            await self.run_round(message)


def _grounds_edge_id(graph, implicit_id: str) -> str:
    for _, _, d in graph.in_edges(implicit_id, data=True):
        if d["kind"] == "grounds":
            return d["edge_id"]
    raise AssertionError(f"implicit {implicit_id} has no grounds edge")
