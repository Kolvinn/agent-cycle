"""The structured answer each frame must return.

Crosses the SDK boundary as ``output_format`` (a JSON schema the CLI's
validator accepts — see ``harness/wire.py``); the graph keeps these types.

**No ids anywhere.** The graph assigns ids positionally. An id the model
invents is one more thing that can come back duplicated or drifted, and a
finding stamped to the wrong node is a mistake nothing downstream could
detect. Position is the one handle both sides already agree on. The one id the
model may quote back is a finding's, which the tool result gave it.

**Counts come back on the answer; findings come back as calls.** A count is a
property of the whole set — a per-call refusal can stop a fourth assumption but
never produce a second — so the assumptions and the rivals arrive here and a
wrong count is a retry. A finding is individually checkable and unbounded in number,
so it arrives as ``attach_finding``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AuthoredAssumption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: str = Field(min_length=1, description="One checkable proposition about what is being asked.")
    grounded_in: str = Field(
        default="",
        description="The id of a KNOWN fact this assumption hangs off, or empty if none applies.",
    )
    inferred_because: str = Field(min_length=1, description="Why this is worth assuming about the request.")
    moved_by: str = Field(
        min_length=1,
        description="The specific call whose result would change your belief about this claim.",
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="Ids of the findings you attached this stage that this assumption rests on (for example f1.2). Empty if none.",
    )


class Orientation(BaseModel):
    """Frame ① — the overview, and the assumptions worth testing."""

    model_config = ConfigDict(extra="forbid")

    overview: str = Field(
        min_length=1,
        description="The project's context and surface as they bear on what was asked: what is there, what is not, what you could not tell.",
    )
    assumptions: list[AuthoredAssumption] = Field(
        description="The distinct assumptions about the request worth testing, in the order you would test them."
    )


class AuthoredAntithesis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: str = Field(min_length=1, description="The rival of this assumption.")
    inferred_because: str = Field(min_length=1, description="What in the evidence or the request supports the rival.")
    moved_by: str = Field(
        min_length=1, description="The specific call whose result would change your belief about the rival."
    )


class Antitheses(BaseModel):
    """Frame ② — one rival per assumption, in assumption order."""

    model_config = ConfigDict(extra="forbid")

    antitheses: list[AuthoredAntithesis] = Field(
        description="Exactly one rival per assumption, in the same order the assumptions were named."
    )
    reasoning: str = Field(min_length=1, description="What you make of what you found against the case.")


class Exchange(BaseModel):
    """Frame ③ — one exchange of the conversation.

    No "am I finished" field: the stage ends when the user says so. The
    alterations are not here either — they are calls, answered as they are
    made.
    """

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, description="What you say to the user this turn.")


PAYLOADS: dict[str, type[BaseModel]] = {
    "orientate": Orientation,
    "antithesis": Antitheses,
    "synthesis": Exchange,
}
