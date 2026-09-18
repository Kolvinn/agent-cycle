"""Spike 4 — can a pydantic model be handed to the CLI as-is?

`output_format={"type": "json_schema", ...}` is the only structured-output
mechanism the Claude Code surface has (there is no `tool_choice` forcing and no
`response_format`), so the whole ledger depends on `model_json_schema()` being
acceptable to it. The answer is "mostly", and the exceptions are load-bearing:
the CLI validates with Ajv in **strict mode**, which rejects unknown keywords,
and the schema travels as a *tool's* `input_schema`, which requires a typed
object at the root.

Three parts:

  A. one realistic ledger-shaped schema, round-tripped and re-validated
  B. an acceptance matrix over the constructs pydantic actually emits
  C. the same rejected schemas after a three-rule transform, to show the
     constraint is worked around rather than lived with

Part B's rejections are quoted from the CLI, not inferred. Run:

    .venv/bin/python scripts/spikes/spike_04_structured_output.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated, Any, Literal
from uuid import UUID

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
from pydantic import AnyUrl, BaseModel, ConfigDict, Field, ValidationError

#: Plumbing, not reasoning. Never inherit the ambient session default.
MODEL = "claude-haiku-4-5-20251001"

#: The raw SDK inherits the whole parent environment and the CLI prefers an API
#: key when it finds one. Blanking these keeps the run on the subscription.
SUBSCRIPTION_ENV = {"ANTHROPIC_API_KEY": "", "ANTHROPIC_AUTH_TOKEN": ""}


# ---------------------------------------------------------------------------
# Part A — a schema shaped like something the ledger would really ask for
# ---------------------------------------------------------------------------


class Register(str, Enum):
    E = "E"
    O = "O"
    A = "A"
    X = "X"


class Locator(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(description="repo-relative path")
    line: int | None = Field(default=None, description="1-indexed line, or null")


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Named `reg` rather than `register`, which shadows a BaseModel attribute
    # and makes pydantic drop the field's default from the emitted schema.
    reg: Register = Field(description="provenance register: E, O, A or X")
    excerpt: str = Field(min_length=1, max_length=120)
    locator: Locator


class Payload(BaseModel):
    """Nesting ($defs/$ref), an enum, a Literal, anyOf-null, and bounds."""

    model_config = ConfigDict(extra="forbid")

    findings: list[Finding] = Field(min_length=2, max_length=2)
    verdict: Literal["confirmed", "contested"]
    spent: int = Field(ge=0, le=10)
    note: str | None = None


# ---------------------------------------------------------------------------
# Part B — one class per construct, so a rejection names exactly one thing
# ---------------------------------------------------------------------------


class Leg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["a"]
    v: int


class Leg2(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["b"]
    v: int


class Discriminated(BaseModel):
    """`Field(discriminator=...)` — how a tagged tool choice would be modelled."""

    x: Annotated[Leg | Leg2, Field(discriminator="kind")]


class PlainUnion(BaseModel):
    """The same choice untagged: pydantic emits `anyOf` with no `discriminator`."""

    x: Leg | Leg2


class Formats(BaseModel):
    url: AnyUrl
    when: datetime
    ident: UUID


class Money(BaseModel):
    amount: Decimal


class Tupled(BaseModel):
    pair: tuple[int, str]


class Mapping(BaseModel):
    counts: dict[str, int]


class Defaulted(BaseModel):
    """Defaults, i.e. not every property appears in `required`."""

    n: int = 1
    s: str = "x"


class Patterned(BaseModel):
    code: str = Field(pattern=r"^[A-Z]{2}$")


class Tree(BaseModel):
    """Self-referential, so the root is a bare `$ref` with no `type`."""

    label: str
    kids: list["Tree"] = []


class WrappedTree(BaseModel):
    """The same recursion behind an object root — the fix, stated as a case."""

    tree: Tree


CASES: list[tuple[str, type[BaseModel]]] = [
    ("nested $defs + enum + Literal + anyOf-null + bounds", Payload),
    ("untagged union (anyOf)", PlainUnion),
    ("formats: AnyUrl / datetime / UUID", Formats),
    ("Decimal", Money),
    ("dict[str, int] (additionalProperties schema)", Mapping),
    ("fields with defaults (partial `required`)", Defaulted),
    ("str with pattern", Patterned),
    ("recursion behind an object root", WrappedTree),
    ("tagged union — Field(discriminator=...)", Discriminated),
    ("tuple[int, str] (prefixItems)", Tupled),
    ("recursion at a bare `$ref` root", Tree),
]


def options_for(json_schema: dict[str, Any]) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        model=MODEL,
        tools=[],  # allow-list: no built-ins. Deny-listing is bypassable.
        allowed_tools=[],
        permission_mode="default",
        output_format={"type": "json_schema", "schema": json_schema},
        env=SUBSCRIPTION_ENV,
    )


class _CapturedStderr:
    """Capture the CLI subprocess's stderr at the file-descriptor level.

    `contextlib.redirect_stderr` is not enough: the CLI is a child process that
    inherits fd 2 directly, and `ProcessError.stderr` is only ever the literal
    string "Check stderr output for details". Without this the schema
    complaint — the entire point of part B — is lost to the terminal.
    """

    def __enter__(self) -> "_CapturedStderr":
        self._file = tempfile.TemporaryFile(mode="w+")
        self._saved = os.dup(2)
        os.dup2(self._file.fileno(), 2)
        return self

    def __exit__(self, *exc: object) -> None:
        os.dup2(self._saved, 2)
        os.close(self._saved)
        self._file.seek(0)
        self.text = self._file.read()
        self._file.close()


async def ask(
    schema: type[BaseModel], prompt: str, *, json_schema: dict[str, Any] | None = None
) -> tuple[Any, str]:
    """Return (structured_output, diagnosis). Never raises.

    `json_schema` overrides what is sent, so part C can ship a transformed
    schema while still validating the reply against the original model.
    """
    captured = _CapturedStderr()
    try:
        with captured:
            async for msg in query(
                prompt=prompt,
                options=options_for(
                    json_schema if json_schema is not None else schema.model_json_schema()
                ),
            ):
                if isinstance(msg, ResultMessage):
                    if msg.structured_output is not None:
                        return msg.structured_output, "ok"
                    return None, (
                        f"no structured_output; is_error={msg.is_error} "
                        f"api_error_status={msg.api_error_status} "
                        f"result={(msg.result or '')[:90]!r}"
                    )
    except Exception as exc:  # noqa: BLE001 — the spike reports, it does not handle
        for line in (getattr(captured, "text", "") + f" {exc}").splitlines():
            if "JSON Schema" in line or "strict mode" in line or "API Error" in line:
                return None, line.strip().removeprefix("Error: ")
        return None, f"{type(exc).__name__}: {str(exc)[:110]}"
    return None, "no ResultMessage"


# ---------------------------------------------------------------------------
# The transform — three rules, each answering one measured rejection
# ---------------------------------------------------------------------------


def _strip_discriminator(node: Any) -> Any:
    """Rule 1. `discriminator` is an OpenAPI keyword; Ajv strict refuses it.

    The `oneOf` beside it is left alone, and pydantic still applies the
    discriminated validator on the way back in — the keyword is a parsing hint
    for the reader of the schema, not a constraint the model needs.
    """
    if isinstance(node, dict):
        return {k: _strip_discriminator(v) for k, v in node.items() if k != "discriminator"}
    if isinstance(node, list):
        return [_strip_discriminator(v) for v in node]
    return node


def _expand_prefix_items(node: Any) -> Any:
    """Rule 2. `prefixItems` is 2020-12 only; this validator is on draft-07.

    Positional typing is genuinely lost here — a fixed-length array of a union
    is weaker than a tuple. Prefer not to put tuples in a wire schema at all;
    this exists so the failure is a downgrade rather than a crash.
    """
    if isinstance(node, dict):
        out = {k: _expand_prefix_items(v) for k, v in node.items() if k != "prefixItems"}
        if (prefix := node.get("prefixItems")) is not None:
            out["items"] = {"anyOf": [_expand_prefix_items(i) for i in prefix]}
            out["minItems"] = out["maxItems"] = len(prefix)
        return out
    if isinstance(node, list):
        return [_expand_prefix_items(v) for v in node]
    return node


def _inline_ref_root(schema: dict[str, Any]) -> dict[str, Any]:
    """Rule 3. The schema travels as a tool's `input_schema`, which needs a type.

    A self-referencing model emits a root that is only `{"$ref": ..., "$defs":
    {...}}`. Inlining the referenced definition at the root keeps `$defs`, so
    the recursion inside it still resolves.
    """
    ref = schema.get("$ref")
    if not ref or "type" in schema:
        return schema
    key = ref.rsplit("/", 1)[-1]
    target = dict(schema.get("$defs", {}).get(key, {}))
    if not target:
        return schema
    target["$defs"] = schema["$defs"]
    return target


def transform(schema: type[BaseModel]) -> dict[str, Any]:
    """`model_json_schema()` made acceptable to the CLI's validator."""
    js = _inline_ref_root(schema.model_json_schema())
    return _expand_prefix_items(_strip_discriminator(js))


async def part_a() -> bool:
    print("A. a realistic ledger-shaped schema, round-tripped")
    structured, why = await ask(
        Payload,
        "Invent exactly two findings about a file called README.md. Use register E "
        "for one and O for the other. Set verdict to contested and spent to 3. "
        "Leave note null.",
    )
    if structured is None:
        print(f"  [FAIL] {why}\n")
        return False
    print(f"  returned: {json.dumps(structured)[:220]}")
    try:
        obj = Payload.model_validate(structured)
    except ValidationError as exc:
        print(f"  [FAIL] pydantic rejected the reply: {exc}\n")
        return False
    print(f"  [PASS] validated: {len(obj.findings)} findings, verdict={obj.verdict}\n")
    return True


async def part_b() -> int:
    print("B. which pydantic constructs `--json-schema` accepts")
    width = max(len(name) for name, _ in CASES)
    accepted = 0
    for name, schema in CASES:
        structured, why = await ask(schema, "Fill it in with anything. Be terse.")
        ok = structured is not None
        accepted += ok
        print(f"  {'ACCEPT' if ok else 'REJECT'}  {name:<{width}}  {'' if ok else why}")
    print(f"\n  {accepted}/{len(CASES)} accepted")
    return accepted


async def part_c() -> int:
    print("C. the three rejected schemas, after transform()")
    repaired = 0
    for name, schema in (
        ("tagged union — discriminator stripped", Discriminated),
        ("tuple — prefixItems expanded", Tupled),
        ("recursion — $ref root inlined", Tree),
    ):
        js = transform(schema)
        structured, why = await ask(
            schema, "Fill it in with anything. Be terse.", json_schema=js
        )
        ok = structured is not None
        # The reply is validated against the ORIGINAL model, which is the point:
        # the transform changes the wire schema, not the type the ledger keeps.
        if ok:
            try:
                schema.model_validate(structured)
            except ValidationError as exc:
                ok, why = False, f"sent ok but original model rejected it: {exc}"
        repaired += ok
        print(f"  {'REPAIRED' if ok else 'STILL BROKEN'}  {name:<38}  "
              f"{json.dumps(structured)[:70] if ok else why}")
    print(f"\n  {repaired}/3 repaired")
    return repaired


async def main() -> int:
    print("=" * 78)
    print("  Spike 4 — pydantic schemas through the CLI's structured output")
    print("=" * 78)
    a_ok = await part_a()
    accepted = await part_b()
    print()
    repaired = await part_c()
    print()
    print("Expected, as measured 2026-09-18 against CLI 2.1.273:")
    print("  B: 8/11 accepted. The three rejections are:")
    print("    discriminator  -> strict mode: unknown keyword (Ajv strict)")
    print("    prefixItems    -> strict mode: unknown keyword (draft-07 vocabulary)")
    print("    bare $ref root -> API Error: 400 tools.0.custom.input_schema.type:")
    print("                      Field required (the schema travels as a tool)")
    print("  C: 3/3 repaired, and each reply still validates against the")
    print("     untransformed pydantic model.")
    return 0 if (a_ok and accepted >= 8 and repaired == 3) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
