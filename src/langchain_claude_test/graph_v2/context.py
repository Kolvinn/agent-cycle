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
value is a placeholder chosen to let it run. :data:`SETTLED` names the three
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
    from .harness import StageHarness

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

    Read :data:`PROVISIONAL` before treating any of these as meaningful. Three
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

    #: **No budget.** The user's answer, verbatim: *"delay for now, but no this
    #: is just a analyze and report stage at the moment."* Zero is not a
    #: placeholder here — it is the answer, and the nodes enforce it by opening
    #: no pool at all, so the gate refuses any priced call rather than trusting
    #: a prompt to say "don't look things up". "At the moment" is the user's
    #: word, so expect this to be revisited; it is not permanent.
    present_pool: int = 0

    # --- placeholders, so the loop runs ----------------------------------

    #: The wide orientation pass, which spends from a pool tied to no
    #: assumption because none exist yet. Never assigned a value by the design.
    #: Set equal to :attr:`antithesis_base` only because a number was needed —
    #: whether the two are genuinely the same constant is an open question, and
    #: this default must not be read as having answered it.
    orientation_pool: int = 5

    #: The fact-extraction pass. Explicitly parked: *"I think we can put this to
    #: the side for now. The fact extraction has more nuance at the moment than
    #: i anticipated."* A small number so the stage can run; the stage's design
    #: is deferred, not just its price.
    extraction_pool: int = 3

    #: Ceiling on how many assumptions may be formed. There has to be one:
    #: the turn is funded at five times this count and the next at base plus
    #: this count, so an agent choosing it freely would be choosing its own
    #: budget — which the "agent never sets its own values" rule forbids. Three
    #: is the count from the user's worked example, used as a ceiling rather
    #: than a target.
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
        "orientation_pool",
        "extraction_pool",
        "max_assumptions",
        "max_reauthor_attempts",
        "graph_write_price",
        "compression_needs_approval",
    }
)

#: Fields the user set, and the only ones any run should be trusted to have
#: right without tuning.
SETTLED: frozenset[str] = frozenset({"per_assumption", "antithesis_base", "present_pool"})


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

    budgets: Budgets = field(default_factory=Budgets)
    prices: Mapping[str, int] = DEFAULT_PRICES

    #: Spikes and phase calls are mechanical. Never inherit an ambient
    #: heavyweight default — that is how an expensive model gets spawned
    #: without anyone choosing it. Same reasoning as the built pipeline's
    #: model client.
    model: str = "claude-haiku-4-5-20251001"

    #: An internal turn exhausts its budget, the graph refreshes it, and the
    #: next stage runs — with no user contact. A user turn presents. The
    #: adversarial turn is internal, because showing the affirming findings
    #: before anything has challenged them invites a reaction that ratifies the
    #: frame. Kept as a flag so the distinction is switchable rather than baked.
    internal_turns: frozenset[int] = frozenset({2})


class BudgetNotSet(RuntimeError):
    """A settings file asked for a persona or a cap that does not exist.

    No longer raised for a missing *value* — every cap now has a default, per
    the instruction to pick defaults and mark them. It survives for the case
    where a settings file is wrong, which is a typo rather than an open design
    question.
    """
