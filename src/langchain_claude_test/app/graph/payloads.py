"""The structured answer each frame must return.

Crosses the SDK boundary as ``output_format`` (a JSON schema the CLI's
validator accepts — see ``harness/wire.py``); the graph keeps these types.

**No ids anywhere.** The graph assigns ids positionally. An id the model
invents is one more thing that can come back duplicated or drifted, and a
finding stamped to the wrong reading is a mistake nothing downstream could
detect. Position is the one handle both sides already agree on.

**Counts come back on the answer; findings come back as calls.** A count is a
property of the whole set — a per-call refusal can stop a fourth reading but
never produce a second — so the readings and the rivals arrive here and a wrong
count is a retry. A finding is individually checkable and unbounded in number,
so it arrives as ``attach_finding``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AuthoredAssumption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: str = Field(min_length=1, description="One checkable proposition about what is being asked.")
    grounded_in: str = Field(
        default="",
        description="The id of a KNOWN fact this reading hangs off, or empty if none applies.",
    )
    inferred_because: str = Field(min_length=1, description="Why you read the request this way.")
    moved_by: str = Field(
        min_length=1,
        description="The specific call whose result would change your belief about this claim.",
    )


class Orientation(BaseModel):
    """Frame ① — the landscape, and the readings worth exploring."""

    model_config = ConfigDict(extra="forbid")

    reading: str = Field(min_length=1, description="The landscape, against what was asked.")
    assumptions: list[AuthoredAssumption] = Field(
        description="The distinct readings of the request worth testing, in the order you would fund them."
    )


class Investigation(BaseModel):
    """Frame ② — one turn on one reading."""

    model_config = ConfigDict(extra="forbid")

    reasoning: str = Field(min_length=1, description="What you make of what you found for this reading.")
    nothing_further: bool = Field(
        default=False,
        description="True if nothing further is worth buying for this reading; its remaining points go unspent.",
    )


class AuthoredAntithesis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: str = Field(min_length=1, description="The rival reading of this assumption.")
    inferred_because: str = Field(min_length=1, description="What in the evidence or the request supports the rival.")
    moved_by: str = Field(
        min_length=1, description="The specific call whose result would change your belief about the rival."
    )


class Antitheses(BaseModel):
    """Frame ③ — one rival per reading, in reading order."""

    model_config = ConfigDict(extra="forbid")

    antitheses: list[AuthoredAntithesis] = Field(
        description="Exactly one rival per reading, in the same order the readings were named."
    )
    reasoning: str = Field(min_length=1, description="What you make of what you found against the case.")


class Exchange(BaseModel):
    """Frame ④ — one exchange of the conversation.

    No "am I finished" field: the stage ends when the user says so. The
    alterations are not here either — they are calls, answered as they are
    made.
    """

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, description="What you say to the user this turn.")


PAYLOADS: dict[str, type[BaseModel]] = {
    "orientate": Orientation,
    "assume": Investigation,
    "antithesis": Antitheses,
    "synthesis": Exchange,
}
