"""The gate: how far is this call from the user's words, and may it run?

Every decision names the **rule** that produced it, not just the verdict. A
log saying "blocked" is an assertion; a log saying "blocked by
``gated.unapproved-claim``, because node 4bde3de0 is pending" is something you
can argue with — and arguing with it is the point of running in observe mode
first.

Provenance here is an *argument*, not an inference. A gated call must name the
ledger node it serves via ``for_node_id``, and that node is looked up in the
real graph. This deliberately sidesteps `PLAN.md` Open item 2 — text-matching
versus model self-report — rather than pretending to solve it: the model can
still name the wrong node, but it cannot name one that does not exist, and the
source check later refuses evidence that does not answer the explicit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..ledger.graph import node
from ..ledger.models import CallTier
from .state import SessionState
from .tools import ToolSpec

Outcome = Literal["allow", "propose", "ask", "block"]

Mode = Literal["observe", "enforce"]


@dataclass(frozen=True, slots=True)
class Decision:
    """What the policy resolved, what will actually happen, and why.

    ``would_be`` and ``executed`` differ only in observe mode, and that gap is
    the whole friction measurement — how often the gate *would* have fired,
    on what, and for which rule. A prior gating layer was deleted for being
    annoying without anyone ever having collected this.
    """

    would_be: Outcome
    executed: Outcome
    rule: str
    reason: str
    tier: CallTier
    for_node_id: str | None = None

    @property
    def diverged(self) -> bool:
        return self.would_be != self.executed

    @property
    def runs(self) -> bool:
        return self.executed == "allow"


@dataclass(frozen=True, slots=True)
class Policy:
    mode: Mode = "observe"
    #: Evidence calls allowed per approved claim. At 1 — the default — a second
    #: hop cannot arise, because there is no second look in which to find one.
    #: Raise this only once the depth computation is real.
    max_evidence_per_implicit: int = 1


class Gate:
    """Decides one call at a time against live ledger state."""

    def __init__(self, state: SessionState, *, policy: Policy | None = None) -> None:
        self.state = state
        self.policy = policy or Policy()

    def decide(self, spec: ToolSpec, args: dict[str, object]) -> Decision:
        would, rule, reason, node_id = self._resolve(spec, args)
        executed = "allow" if self.policy.mode == "observe" else would
        return Decision(
            would_be=would,
            executed=executed,
            rule=rule,
            reason=reason,
            tier=spec.tier,
            for_node_id=node_id,
        )

    # --- the rules ---------------------------------------------------------

    def _resolve(
        self, spec: ToolSpec, args: dict[str, object]
    ) -> tuple[Outcome, str, str, str | None]:
        if spec.tier == "free":
            return ("allow", "free.no-hop", "a survey forms no claim, so it costs no hop", None)

        path = str(args.get("path", "")) if "path" in args else None
        if path and path in self.state.user_named_paths:
            return (
                "allow",
                "depth0.user-named",
                f"the user named {path!r} in their own words — reading it infers nothing",
                None,
            )

        raw = args.get("for_node_id")
        node_id = str(raw) if raw else None
        if not node_id:
            return (
                "block",
                "gated.missing-provenance",
                "a gated call must name the ledger node it serves (for_node_id)",
                None,
            )

        n = node(self.state.graph, node_id)
        if n is None:
            return (
                "block",
                "gated.unknown-node",
                f"for_node_id {node_id!r} is not in the ledger",
                node_id,
            )

        if n.kind == "explicit":
            if n.status not in ("open", "addressed"):
                return ("block", "gated.bad-explicit", f"explicit is {n.status!r}", node_id)
            return (
                "allow",
                "depth0.explicit",
                f"serving explicit {node_id[:8]} — the user's own words",
                node_id,
            )

        if n.status != "approved":
            return (
                "block",
                "gated.unapproved-claim",
                (
                    f"implicit {node_id[:8]} is {n.status!r}. Evidence is gathered for a "
                    "signed-off claim, not to justify a pending one"
                ),
                node_id,
            )

        spent = self.state.evidence_spent(node_id)
        if spent >= self.policy.max_evidence_per_implicit:
            return (
                "ask",
                "depth1.budget-exhausted",
                (
                    f"implicit {node_id[:8]} has already had its {spent} evidence call(s). "
                    "A second look is where multi-hop starts, so it needs you"
                ),
                node_id,
            )

        return (
            "allow",
            "depth1.approved",
            f"depth 1, scoped to approved implicit {node_id[:8]}",
            node_id,
        )
