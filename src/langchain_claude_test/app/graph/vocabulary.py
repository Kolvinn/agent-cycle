"""The closed vocabulary of the thought graph: node kinds, roles, statuses,
and the two edge vocabularies.

> "tools should be able to add relationship types into the networkx in such a
> way like graph rag does it (depends on, requires, etc.)"

**Structural** edges are the graph's own: the frames make them from what
they author, and no tool names them. **Relational** edges are the GraphRAG
part: the model proposes one, the user approves it at the call. The core is
closed; a relation outside it is proposed as ``relates_to`` with a
``proposed_kind``, and approving that adds the kind to the project's
vocabulary as a record (``RelationKind``), so it persists and is a decision.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

# --- node kinds -----------------------------------------------------------------

QUESTION = "question"
FACT = "fact"
CLAIM = "claim"
ENTITY = "entity"
EVIDENCE = "evidence"
SUMMARY = "summary"

NODE_KINDS: tuple[str, ...] = (QUESTION, FACT, CLAIM, ENTITY, EVIDENCE, SUMMARY)

#: What the model may add with ``add_node``.
ADDABLE_KINDS: tuple[str, ...] = (ENTITY, CLAIM)

CLAIM_ROLES: tuple[str, ...] = ("assumption", "counter", "observation")
ENTITY_ROLES: tuple[str, ...] = ("file", "module", "function", "service", "config", "concept")

#: Id prefix per kind (and per claim role, for the frames' own claims).
PREFIX: Mapping[str, str] = MappingProxyType(
    {
        QUESTION: "q",
        FACT: "e",
        "assumption": "a",
        "counter": "x",
        CLAIM: "c",
        ENTITY: "n",
        EVIDENCE: "f",
        SUMMARY: "s",
        "edge": "r",
    }
)

# --- status ---------------------------------------------------------------------

PROVISIONAL = "provisional"
CONFIRMED = "confirmed"
REFUTED = "refuted"
SUPERSEDED = "superseded"
DISCARDED = "discarded"

#: Set by the user, terminal once set.
VERDICTS: tuple[str, ...] = (CONFIRMED, REFUTED)
TERMINAL: frozenset[str] = frozenset({CONFIRMED, REFUTED, SUPERSEDED, DISCARDED})

USER = "user"
AGENT = "agent"

# --- edges ----------------------------------------------------------------------

ASKS = "asks"
CITES = "cites"
EVIDENCES = "evidences"
CONTENDS = "contends"
GROUNDS = "grounds"
SUMMARISES = "summarises"
SUPERSEDES = "supersedes"

STRUCTURAL: frozenset[str] = frozenset({ASKS, CITES, EVIDENCES, CONTENDS, GROUNDS, SUMMARISES, SUPERSEDES})

#: The escape hatch: any ends, ``why`` required, optionally carrying a
#: ``proposed_kind`` that approval adds to the vocabulary.
RELATES_TO = "relates_to"

#: relation -> (allowed source kinds, allowed target kinds); ``None`` is any.
RELATIONS: Mapping[str, tuple[tuple[str, ...] | None, tuple[str, ...] | None]] = MappingProxyType(
    {
        "depends_on": ((ENTITY,), (ENTITY,)),
        "requires": ((CLAIM,), (ENTITY, CLAIM)),
        "calls": ((ENTITY,), (ENTITY,)),
        "defines": ((ENTITY,), (ENTITY,)),
        "configures": ((ENTITY,), (ENTITY,)),
        "part_of": ((ENTITY,), (ENTITY,)),
        "supports": ((CLAIM, EVIDENCE), (CLAIM,)),
        "contradicts": ((CLAIM, EVIDENCE), (CLAIM,)),
        RELATES_TO: (None, None),
    }
)

RELATION_READINGS: Mapping[str, str] = MappingProxyType(
    {
        "depends_on": "A does not work without B",
        "requires": "A holds only if B",
        "calls": "A calls B",
        "defines": "A defines B",
        "configures": "A configures B",
        "part_of": "A is part of B",
        "supports": "A is an argument for B",
        "contradicts": "A is an argument against B",
        RELATES_TO: "A relates to B, and why is required",
    }
)


def relation_allowed(kind: str, src_kind: str, dst_kind: str, extra: frozenset[str] = frozenset()) -> str:
    """Empty when the relation may join these kinds; otherwise why not."""
    if kind in STRUCTURAL:
        return f"{kind} is a structural edge the frames make; it cannot be added by name."
    if kind in extra:
        return ""
    ends = RELATIONS.get(kind)
    if ends is None:
        return f"{kind!r} is not a relation in this project's vocabulary."
    sources, targets = ends
    if sources is not None and src_kind not in sources:
        return f"{kind} cannot start at a {src_kind}; it starts at {' or '.join(sources)}."
    if targets is not None and dst_kind not in targets:
        return f"{kind} cannot end at a {dst_kind}; it ends at {' or '.join(targets)}."
    return ""


def vocabulary_line(extra: frozenset[str] = frozenset()) -> str:
    """The relations, one line, for a brief."""
    core = ", ".join(f"{k} ({RELATION_READINGS[k]})" for k in RELATIONS)
    added = f"; added on this project: {', '.join(sorted(extra))}" if extra else ""
    return core + added
