"""Value shapes for the explicit/implicit ledger.

Two families, same split the archived concept-graph used (``NewConcept`` vs
``Concept``): ``New*`` models are the *input* shapes handed to the library by
the driving loop, and carry no id — the library allocates. ``Ledger*`` models
are the *read-out* shapes projected back out of the graph.

The graph itself is the store. Node attributes hold kind/status/text; these
models never hold live state, so there is no second copy to drift.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Closed enums
# ---------------------------------------------------------------------------

NodeKind = Literal["explicit", "implicit"]

NodeStatus = Literal[
    "open",       # explicit: registered, not yet answered
    "addressed",  # explicit: answered in a reply to the user
    "pending",    # implicit: literalized, awaiting sign-off
    "approved",   # implicit: the user confirmed it
    "rejected",   # implicit: the user corrected or refused it
    "parked",     # implicit: asked, no answer — never self-resolves
]

#: Statuses an implicit may legally hold.
IMPLICIT_STATUSES: frozenset[str] = frozenset({"pending", "approved", "rejected", "parked"})
#: Statuses an explicit may legally hold.
EXPLICIT_STATUSES: frozenset[str] = frozenset({"open", "addressed"})

#: Only one edge kind exists, on purpose. ``supersedes`` (from the "when the
#: user is wrong" design) is deliberately NOT built yet — it is outside the
#: eight-step round-one flow, and declaring a kind nothing can create would be
#: surface that only looks present.
EdgeKind = Literal[
    "grounds",  # explicit -> implicit. The ONLY way an implicit enters the graph.
]

#: Provenance weight of a tool call's result.
#:
#: ``free`` calls are executed without asking, but their results are still
#: tagged — anything citing one inherits depth normally. Free to call is not
#: free of provenance; skipping the tag is how a discovered reference launders
#: itself into a depth-0 one.
CallTier = Literal["free", "gated"]


class NewExplicit(BaseModel):
    """An explicit node, sourced from the user's literal words.

    ``quote`` must be a verbatim substring of the turn it came from —
    :func:`~.graph.register_explicit` re-checks this against the message text
    rather than trusting the caller, because paraphrase is already inference.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    quote: str = Field(
        min_length=1,
        description="Verbatim span of the user's message. Not a paraphrase, not a summary.",
    )
    start: int = Field(
        ge=0,
        description="Character offset of the quote's first character in the user message.",
    )


class NewImplicit(BaseModel):
    """An assumption the agent formed, literalized into a checkable claim.

    Not a tool's output — the *claim made from* it. ``grounded_in`` names the
    explicit node this hangs off; there is no form of this model that can hang
    off another implicit.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    claim: str = Field(
        min_length=1,
        description=(
            "The assumption stated as a single checkable proposition — something a "
            "user can answer yes or no to. Not a question, not a plan, not a hedge."
        ),
        examples=["validation happens in handlers.py at verify_signature"],
    )
    grounded_in: str = Field(
        description="Node id of the explicit this claim is derived from. Must be an explicit.",
    )


class Source(BaseModel):
    """Evidence attached to a ``grounds`` edge.

    Attached to the *link*, not to either node: it is the justification for
    that specific derivation, so it has to answer both ends — where the
    evidence came from (``locator``/``excerpt``) and what about the explicit
    it actually speaks to (``answers``).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    locator: str = Field(
        min_length=1,
        description="Where the evidence lives, e.g. 'webhook/handlers.py:42'.",
    )
    excerpt: str = Field(
        min_length=1,
        description=(
            "Verbatim text from the evidence. Checked against the recorded tool "
            "results — an excerpt that appears in none of them is rejected."
        ),
    )
    answers: str = Field(
        min_length=1,
        description=(
            "Verbatim words from the EXPLICIT that this evidence speaks to. Checked "
            "as a substring of the explicit's text. This is what keeps the source "
            "relevant to the explicit entry rather than merely relevant to the claim."
        ),
    )
    tool_call_id: str = Field(
        description="Id of the evidence call that produced the excerpt.",
    )


class LedgerNode(BaseModel):
    """Read-out shape for one node."""

    model_config = ConfigDict(frozen=True)

    id: str
    kind: NodeKind
    status: NodeStatus
    text: str
    turn: int


class LedgerEdge(BaseModel):
    """Read-out shape for one edge."""

    model_config = ConfigDict(frozen=True)

    id: str
    kind: EdgeKind
    source_id: str
    target_id: str
    source: Source | None = None


# ---------------------------------------------------------------------------
# GraphResult — the single return type for every mutation
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GraphResult:
    """Outcome of one ledger mutation.

    Kept from the archived engine deliberately: a failure carries a *message*
    rather than raising, which is what lets a rejected operation be handed
    back to the model as text it can read and react to.

    ``graph`` is the post-state on success and the unchanged pre-state on
    failure — never a partially-applied graph.
    """

    success: bool
    message: str = ""
    graph: nx.DiGraph = field(default_factory=nx.DiGraph)
    node_ids: tuple[str, ...] = ()
    edge_ids: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return self.success
