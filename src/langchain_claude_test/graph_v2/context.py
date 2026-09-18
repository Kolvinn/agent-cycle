"""Control values — set by the graph, read by the nodes, never written by either.

This file exists because of the rule that the agent never sets its own values:
*"the agent can never set their own values. These values are set inside the
graph flow. The agent can never manually refresh."* A node's only way to affect
the run is the delta it returns, so anything reachable from a delta is something
the agent can propose a change to. Caps and prices therefore live in **runtime
context** rather than in state — readable from every node, writable from none,
and never checkpointed. The agent cannot widen its own budget because there is
no channel on which to widen it.

The same rule puts control of the values in the wrapper over the top rather than
in this code: *"I would obviously want control over it, if we can bake that kind
of control into the custom gui wrapper over the top of the sdk, then that would
be good."* That is the shape a runtime context has — the driver builds one per
run and the graph reads it. Changing a price is a driver concern, never a graph
edit.

**Every number here is a default, not a decision.** The instruction that made it
so, verbatim:

> "All of the numbers will need to be tested and tweaked, and there is a
> reasonable case for a settings file upload for persona types, where some are
> heavy thinkers and others dont need that much. So in this sense, we can just
> pick defaults but make sure to not that they are not set."

So the loop runs on defaults, and :data:`PROVISIONAL` names every field whose
value is a placeholder chosen to let it run. :data:`SETTLED` names the two
that are not. Nothing distinguishes the two at run time except that list, which
is why the list is machine-readable rather than a comment: the settings layer
needs to be able to show which numbers are yours and which are filler.

The harness lives here too, for the same ownership reason and one more: a live
SDK connection is not serialisable, and state is. Keeping it in context means the
checkpointer never sees it and a fork never carries a stale one.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, replace
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:  # pragma: no cover - import cycle only matters to type checkers
    from .harness import Approver, StageHarness


def _nobody():
    """The refusing approver. Imported late, because `harness` imports this file."""
    from .harness import NobodyApproves

    return NobodyApproves()

#: Prices per class of call, in the user's own example values: *"Read tools
#: might be -2, survey skills might mb -1 (like ls, tree, etc.), webfetch = 3,
#: and so on."* Examples given in passing, so they are defaults like everything
#: else — and the mapping from a concrete tool onto a class is a separate
#: question, answered where the tools are built.
DEFAULT_PRICES: Mapping[str, int] = MappingProxyType(
    {
        "survey": 1,  # ls, tree, glob — cheap, and what going wide is made of
        "read": 2,
        "webfetch": 3,
    }
)

#: Charged when a call's class cannot be determined. Deliberately the most
#: expensive class rather than the cheapest: an unpriced call is the hole
#: through which a budget leaks, and guessing low is how it widens.
UNKNOWN_CALL_PRICE = 3


@dataclass(frozen=True, slots=True)
class Budgets:
    """Every cap in the cycle, in one place, owned by the graph.

    Read :data:`PROVISIONAL` before treating any of these as meaningful. Two
    are the user's; the rest are placeholders that exist so a base loop can run
    end to end, which is the stated priority: *"I'd like to see a working base
    loop before extending the finer details."*
    """

    #: Which persona's numbers these are. A heavy thinker and a light one want
    #: different budgets, and the intent is that a settings file supplies them.
    #: ``"default"`` means the values compiled in below, which belong to nobody.
    persona: str = "default"

    # --- the user's own numbers -------------------------------------------

    #: Five points per assumption. The user's number, twice over: the
    #: restriction is *"tool call restrictions per assumption"*, and the worked
    #: example reads *"if there are 3 assumptions, where each assumption has a
    #: budget of 5"*.
    per_assumption: int = 5

    #: The adversarial turn is funded at ``base + N``, and base is five:
    #: *"the budget has the base (5) + assumption N (3) = 8"*.
    antithesis_base: int = 5

    # --- placeholders, so the loop runs ----------------------------------

    #: Points for the synthesis conversation, for one cycle.
    #:
    #: **This was zero, on your answer, and your later instruction supersedes
    #: it.** The zero was right for the stage as it then was: *"delay for now,
    #: but no this is just a analyze and report stage at the moment."* It is no
    #: longer that stage. It is a conversation you are in, it carries evidence
    #: calls because you may ask it to go and look, and a frame that can look
    #: needs a pool or the restriction does not exist for it.
    #:
    #: One pool for the whole conversation, not one per exchange. So looking is
    #: bounded while talking is not: when it runs dry the agent can still argue,
    #: still propose alterations and still finish the package — it just cannot
    #: buy any more evidence, and going round the cycle is what opens a fresh
    #: one. ⚠️ Whether a lookup *you asked for* should cost the agent anything is
    #: a real question and is not answered here.
    synthesis_points: int = 5

    #: Points for the wide orientation pass, which spends from a pool tied to
    #: no reading because none exist yet. **Points, not a pool** — a pool is an
    #: identity and lives in `budget.py`, a cap is a number and lives here; the
    #: two used to share a name and that is a confusion worth one rename.
    #: Never assigned a value by the design.
    #: Set equal to :attr:`antithesis_base` only because a number was needed —
    #: whether the two are genuinely the same constant is an open question, and
    #: this default must not be read as having answered it.
    orientation_points: int = 5

    #: Ceiling on how many assumptions may be formed.
    #:
    #: **The limit is required, by the user's own instruction:** *"there should
    #: be a limit on the amount of assumptions produced."* So this is the one
    #: budget field whose *existence* is settled while its *value* is not — it
    #: appears in both :data:`REQUIRED` and :data:`PROVISIONAL`, and the two say
    #: different things. A run may report that nobody chose the number. It may
    #: not run without a ceiling.
    #:
    #: Why the ceiling cannot belong to the agent: the assume frame is funded at
    #: the per-reading rate times this count, and the rival at base plus this
    #: count. An agent free to choose the count would be choosing its own budget,
    #: which the "agent never sets its own values" rule forbids.
    #:
    #: **Enforced by the shape of the first frame's answer, not by a tool.** A
    #: count is a property of the whole set: a per-call refusal could stop a
    #: fourth reading but could never produce a second, and "too few" is the
    #: failure that matters more. So the readings come back on the answer, an
    #: answer outside the range is a retry, and :attr:`max_reauthor_attempts`
    #: bounds the retrying. The model is told the number, as a fact it needs to
    #: plan against — and nothing more, because the retry is the enforcer.
    #:
    #: Three is the count from the user's worked example, used as a ceiling
    #: rather than a target. It is a placeholder.
    max_assumptions: int = 3

    #: How many times the agent may re-author an inadmissible assumption, or an
    #: antithesis that fails to attack anything. Nothing in the design bounds
    #: this; a graph needs a bound or the loop is unbounded.
    max_reauthor_attempts: int = 2

    #: What an in-graph bookkeeping write costs. The instruction was that *"tool
    #: usage from claude registered to point values"*, but every priced example
    #: given was evidence gathering — a read, a survey, a web fetch. Writing an
    #: assumption into the graph is not evidence gathering. Zero keeps the
    #: question visible in one place instead of spreading an assumption about it.
    graph_write_price: int = 0

    #: Whether compressing or discarding graph material needs a human approval.
    #: It registers no fact, yet it decides what the next cycle can still see,
    #: which is a kind of authority. Defaulted to *yes* because that is the
    #: direction whose failure mode is friction rather than silent loss.
    compression_needs_approval: bool = True

    def with_persona(self, persona: str, **overrides: Any) -> Budgets:
        """A copy under another persona's name, with the given values changed."""
        return replace(self, persona=persona, **overrides)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any], *, persona: str = "default") -> Budgets:
        """Build from a settings file's parsed contents.

        The seam the persona idea needs, and only the seam. The expected shape
        is one block per persona::

            {"heavy": {"per_assumption": 9, "max_assumptions": 5},
             "light": {"per_assumption": 3, "max_assumptions": 2}}

        Anything a block omits keeps the default, so a persona file states only
        what it changes. **The file format is not decided** and neither are any
        persona's values — no persona but ``default`` is defined in code,
        deliberately, so that inventing numbers here cannot be mistaken for
        having chosen them.
        """
        block = data.get(persona)
        if block is None:
            raise BudgetNotSet(
                f"settings define no persona {persona!r} (found: {sorted(data) or 'none'})"
            )
        known = {f.name for f in fields(cls)} - {"persona"}
        unknown = sorted(set(block) - known)
        if unknown:
            raise BudgetNotSet(f"persona {persona!r} sets unknown budget(s): {unknown}")
        return cls(persona=persona, **{k: v for k, v in block.items()})


#: Fields whose value is a placeholder, not a decision. The settings layer
#: should show these differently from the rest — that is the whole reason this
#: is data rather than a docstring.
PROVISIONAL: frozenset[str] = frozenset(
    {
        "orientation_points",
        "synthesis_points",
        "max_assumptions",
        "max_reauthor_attempts",
        "graph_write_price",
        "compression_needs_approval",
    }
)

#: Fields the user set, and the only ones any run should be trusted to have
#: right without tuning.
SETTLED: frozenset[str] = frozenset({"per_assumption", "antithesis_base"})

#: Fields the user has ruled must *exist*, whatever their value. This overlaps
#: :data:`PROVISIONAL` on purpose: *"there should be a limit on the amount of
#: assumptions produced"* settles that there is a ceiling without settling what
#: it is. A run may disclose that the number is untested; it may not drop the
#: limit because the number is untested, and a settings file may not set it to
#: nothing.
REQUIRED: frozenset[str] = frozenset({"max_assumptions"})


def provisional_fields(budgets: Budgets) -> dict[str, Any]:
    """The placeholder values in force, for a run to disclose.

    Every number will be tested and tweaked, so a run that reports its findings
    without saying which of its limits were arbitrary is reporting on a
    configuration nobody chose. This is what makes that disclosable.
    """
    return {name: getattr(budgets, name) for name in sorted(PROVISIONAL)}


def unclassified_budget_fields() -> tuple[str, ...]:
    """Budget fields that are in neither :data:`PROVISIONAL` nor :data:`SETTLED`.

    Empty is the only correct answer. A new cap that lands in neither set is a
    number with no stated origin, which is the exact thing being guarded against.
    """
    named = PROVISIONAL | SETTLED | {"persona"}
    return tuple(sorted({f.name for f in fields(Budgets)} - named))


@dataclass(frozen=True, slots=True)
class ControlContext:
    """What the driver hands the graph for one run.

    Constructed outside the graph — by the wrapper that owns value control, or
    by a test — and passed as LangGraph's runtime context. Nodes reach it
    through ``runtime.context``.
    """

    #: The inner Agent SDK boundary. One harness, opened per node.
    harness: StageHarness

    #: Who answers a gated call, at the moment it is made. Lives here for the
    #: same two reasons the harness does: the driver owns it, and a live
    #: connection to a human is no more serialisable than a live connection to a
    #: model. The graph never checkpoints either.
    #:
    #: :class:`~.harness.NobodyApproves` is the default, and it refuses
    #: everything. A default that said yes would be a human-in-the-loop with no
    #: human in it, which this repository has shipped once before and caught.
    approver: "Approver" = field(default_factory=lambda: _nobody())

    budgets: Budgets = field(default_factory=Budgets)
    prices: Mapping[str, int] = DEFAULT_PRICES

    #: Spikes and phase calls are mechanical. Never inherit an ambient
    #: heavyweight default — that is how an expensive model gets spawned
    #: without anyone choosing it. Same reasoning as the built pipeline's
    #: model client.
    model: str = "claude-haiku-4-5-20251001"



class BudgetNotSet(RuntimeError):
    """A settings file asked for a persona or a cap that does not exist.

    No longer raised for a missing *value* — every cap now has a default, per
    the instruction to pick defaults and mark them. It survives for the case
    where a settings file is wrong, which is a typo rather than an open design
    question.
    """
