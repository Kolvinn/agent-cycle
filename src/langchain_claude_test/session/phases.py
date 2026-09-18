"""The phases, each a locked-schema model call.

The runner calls these in a fixed order, so the model never chooses what
happens next — its only freedom is what to put in the fields. That is the
whole point of the driven pipeline: it measures how *well* each step is done,
which is a different and more answerable question than whether the model would
have done it unprompted.

One deliberate simplification: nothing here asks the model for a character
offset. Models are unreliable at counting characters, and they do not need to
be — the runner locates each quote with :meth:`str.find` and rejects anything
it cannot find. That still catches paraphrase, which is the thing the check
exists for, without making the model do arithmetic it is bad at.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Schemas — what each phase is allowed to return
# ---------------------------------------------------------------------------


class Extraction(BaseModel):
    """Phase 1 — the user's own words, quoted, never paraphrased."""

    model_config = ConfigDict(extra="forbid")

    quotes: list[str] = Field(
        description=(
            "Verbatim spans copied character-for-character out of the user's message. "
            "One per distinct thing they asked for. Copy, do not rewrite, do not tidy "
            "up grammar, do not expand abbreviations."
        ),
        min_length=1,
        max_length=5,
    )
    named_paths: list[str] = Field(
        default_factory=list,
        description=(
            "File paths the user named explicitly in this message, if any. Only paths "
            "they actually typed — never one you inferred or completed."
        ),
    )


class Orientation(BaseModel):
    """Phase 2 — a free survey. Forms no claim, so it costs no hop."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(
        default=".",
        description="Directory to list, relative to the project root. '.' for the top level.",
    )
    why: str = Field(description="One short sentence: what you expect this to tell you.")


class Assumption(BaseModel):
    """Phase 3 — the agent's own claim, literalized so it can be checked."""

    model_config = ConfigDict(extra="forbid")

    claim: str = Field(
        description=(
            "Your assumption, stated as ONE checkable proposition the user can answer "
            "yes or no to. Not a question. Not a plan. Not a list. If you are unsure, "
            "state the specific thing you are unsure about — a hedge is not a claim."
        ),
        examples=["signature validation happens in webhook/signature.py in verify_signature"],
    )
    why: str = Field(description="One sentence: what led you to this, given only what you have seen.")


class EvidencePlan(BaseModel):
    """Phase 4 — the single gated look that either supports or kills the claim."""

    model_config = ConfigDict(extra="forbid")

    pattern: str = Field(
        description=(
            "A literal string to search the project for. You get ONE search for this "
            "claim, so choose the string that would most directly confirm or refute it."
        )
    )
    expect: str = Field(
        description="What result would confirm the claim, and what result would refute it."
    )


class SourceChoice(BaseModel):
    """Phase 5 — the most relevant source, attached to the explicit→implicit link."""

    model_config = ConfigDict(extra="forbid")

    locator: str = Field(description="Where the evidence is, as 'path:line'.")
    excerpt: str = Field(
        description=(
            "The single most relevant line, copied VERBATIM from the search result. "
            "It is checked against the recorded result — an excerpt that does not "
            "appear there is rejected."
        )
    )
    answers: str = Field(
        description=(
            "Words copied VERBATIM from the USER'S OWN QUESTION that this evidence "
            "answers. Not from your claim — from their question. This is checked as a "
            "literal substring, and it is what keeps the source relevant to what they "
            "actually asked rather than to what you assumed."
        )
    )


class Findings(BaseModel):
    """Phase 6 — what the user gets back."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(
        description=(
            "Your findings for this round, in two or three sentences. State what you "
            "established and on what evidence. Do not claim anything the ledger does "
            "not hold."
        )
    )


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_DISCIPLINE = """\
You are the reasoning half of a system that tracks where its own conclusions came from.

Two kinds of thing exist:
- EXPLICIT — the user's literal words. Authority comes from them, never from you.
- IMPLICIT — something you worked out. It carries no authority until the user confirms it.

Rules that are enforced mechanically, not by your good intentions:
- You may never treat one of your own claims as if the user had confirmed it.
- A quote must be copied exactly. A paraphrase is rejected.
- Evidence is gathered AFTER a claim is signed off, to source it — never before, to justify it.

Answer with JSON matching the schema. Nothing else."""

EXTRACT_SYSTEM = _DISCIPLINE
ORIENT_SYSTEM = _DISCIPLINE
ASSUME_SYSTEM = _DISCIPLINE
EVIDENCE_SYSTEM = _DISCIPLINE
SOURCE_SYSTEM = _DISCIPLINE
REPLY_SYSTEM = _DISCIPLINE


def extract_prompt(message: str) -> str:
    return (
        "Here is the user's message, between the markers.\n\n"
        f"<<<MESSAGE\n{message}\nMESSAGE>>>\n\n"
        "Copy out the span(s) that say what they want. Character for character."
    )


def orient_prompt(explicits: list[str]) -> str:
    asked = "\n".join(f"- {q}" for q in explicits)
    return (
        f"The user asked for:\n{asked}\n\n"
        "Before assuming anything, get your bearings. Which directory should be listed "
        "first? This is a free survey — it forms no claim."
    )


def assume_prompt(explicit: str, orientation: str) -> str:
    return (
        f"The user asked: \"{explicit}\"\n\n"
        f"A directory listing gave you:\n{orientation}\n\n"
        "State the one assumption you are now working from. It will be put to the user "
        "for sign-off before you are allowed to look at anything else, so make it "
        "specific enough to be worth confirming."
    )


def evidence_prompt(claim: str, explicit: str) -> str:
    return (
        f"The user asked: \"{explicit}\"\n"
        f'The user has APPROVED this claim: "{claim}"\n\n'
        "You now get exactly one search to source it. What literal string do you search for?"
    )


def source_prompt(claim: str, explicit: str, result: str) -> str:
    return (
        f"The user asked: \"{explicit}\"\n"
        f'The approved claim: "{claim}"\n\n'
        f"Your search returned:\n<<<RESULT\n{result}\nRESULT>>>\n\n"
        "Pick the single most relevant line as the source for this claim, and quote the "
        "words from the USER'S QUESTION that it answers."
    )


def reply_prompt(digest: str) -> str:
    return (
        "This is the ledger for the round that just finished:\n\n"
        f"<<<LEDGER\n{digest}\nLEDGER>>>\n\n"
        "Report the findings to the user. Only what the ledger supports."
    )
