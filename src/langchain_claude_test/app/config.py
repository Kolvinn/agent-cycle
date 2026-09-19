"""Values the graph reads and never writes, and the modes the shell offers.

Two things live here, both set outside the graph and both readable everywhere:

**Budgets and prices.** *"the agent can never set their own values. These values
are set inside the graph flow. The agent can never manually refresh."* Caps and
prices are runtime context, never state, so there is no channel on which an
agent could widen its own budget. Every number is a default — *"we can just
pick defaults but make sure to note that they are not set"* — and
:data:`PROVISIONAL` names the ones nobody has chosen so a run can say so.

**Modes.** *"The / commands should be variable and adaptable."* A mode is a
focus the shell can switch to: a plain Claude connection with its own system
prompt and tool surface, or the provenance cycle. Modes are data, read from a
``modes.toml``, so adding ``/reviewer`` is a table in a file rather than code.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields, replace
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, Mapping

# ---------------------------------------------------------------------------
# Prices and budgets
# ---------------------------------------------------------------------------

#: Prices per class of call, in the user's own example values: *"Read tools
#: might be -2, survey skills might mb -1 (like ls, tree, etc.), webfetch = 3."*
DEFAULT_PRICES: Mapping[str, int] = MappingProxyType(
    {"survey": 1, "read": 2, "webfetch": 3}
)

#: Charged when a call's class cannot be determined. The most expensive class
#: rather than the cheapest: an unpriced call is the hole a budget leaks
#: through, and guessing low is how it widens.
UNKNOWN_CALL_PRICE = 3

#: The SDK's built-in tools that gather evidence, and the price class each
#: falls into. *"dont remake what we can just build around naturally"* — the
#: tools are the SDK's own; only the pricing is ours. ``Grep`` as a survey is a
#: placeholder (it surveys, but returns content), marked in :data:`PROVISIONAL`.
EVIDENCE_TOOL_CLASS: Mapping[str, str] = MappingProxyType(
    {
        "Read": "read",
        "Glob": "survey",
        "Grep": "survey",
        "WebFetch": "webfetch",
        "WebSearch": "webfetch",
    }
)

#: The built-in surface every research frame carries. An allow-list: ``Bash``
#: never exists, so a refused read has nowhere to route around to.
EVIDENCE_TOOLS: tuple[str, ...] = tuple(EVIDENCE_TOOL_CLASS)


@dataclass(frozen=True, slots=True)
class Budgets:
    """Every cap in the cycle, in one place, owned by the graph."""

    #: Five points per assumption — the user's number: *"if there are 3
    #: assumptions, where each assumption has a budget of 5"*. Since the survey
    #: and the assumptions are one frame, this funds the survey: the orientate
    #: pool is ``orientation_base + per_assumption * max_assumptions``.
    per_assumption: int = 5
    #: The rival pass is funded at ``base + N``, and base is five: *"the budget
    #: has the base (5) + assumption N (3) = 8"*.
    antithesis_base: int = 5
    #: The survey's own share of the orientate pool, on top of the per-assumption
    #: allowance. Never assigned by the design.
    orientation_base: int = 5
    #: Points for the whole synthesis conversation of one cycle, not per
    #: exchange: looking is bounded, talking is not.
    synthesis_points: int = 5
    #: Ceiling on assumptions per cycle. *"there should be a limit on the amount
    #: of assumptions produced"* — the limit is required, the number is not.
    max_assumptions: int = 3
    #: How many times a frame may re-author an answer of the wrong shape.
    max_reauthor_attempts: int = 2
    #: What an in-graph bookkeeping write costs. Every priced example the user
    #: gave was evidence gathering, so this stays visible in one field.
    graph_write_price: int = 0
    #: ``attach_finding`` is free — *"attach finding should be free, but have a
    #: hard limit"* — and this is the limit: findings one turn may create.
    #: Overwriting one the turn just created does not count again.
    max_findings: int = 12
    #: How far from the cycle's question and the facts the package renders in
    #: full; beyond that a node is one line and the read tools fetch it.
    package_hops: int = 2
    #: After how many cycles a provisional node nothing approved connects to
    #: is proposed for compression.
    stale_after: int = 2

    def with_(self, **overrides: Any) -> Budgets:
        return replace(self, **overrides)


#: Fields whose value is a placeholder, not a decision.
PROVISIONAL: frozenset[str] = frozenset(
    {
        "orientation_base",
        "synthesis_points",
        "max_assumptions",
        "max_reauthor_attempts",
        "graph_write_price",
        "max_findings",
        "package_hops",
        "stale_after",
        "Grep->survey",
    }
)

#: Fields the user set.
SETTLED: frozenset[str] = frozenset({"per_assumption", "antithesis_base"})


def provisional_fields(budgets: Budgets) -> dict[str, Any]:
    """The placeholder values in force, for a run to disclose."""
    named = {f.name for f in fields(Budgets)}
    return {n: getattr(budgets, n) for n in sorted(PROVISIONAL) if n in named}


def unclassified_budget_fields() -> tuple[str, ...]:
    """Budget fields in neither set. Empty is the only correct answer."""
    return tuple(sorted({f.name for f in fields(Budgets)} - PROVISIONAL - SETTLED))


# ---------------------------------------------------------------------------
# Model defaults — from the user's own streaming experiment (v3_test/test.py)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ModelSettings:
    model: str = "sonnet"
    thinking: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({"type": "adaptive", "display": "summarized"})
    )
    effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"

    def with_model(self, model: str) -> ModelSettings:
        return replace(self, model=model)

    def with_effort(self, effort: str) -> ModelSettings:
        return replace(self, effort=effort)  # type: ignore[arg-type]

    @property
    def sdk_model(self) -> str | None:
        """What goes on the wire: ``None`` lets the CLI pick its own default."""
        return None if self.model in ("", "default") else self.model


#: The levels the CLI's ``/effort`` offers, in order. What a given model
#: accepts comes from the CLI's model list (``ModelChoice.efforts``).
EFFORT_LEVELS: tuple[str, ...] = ("low", "medium", "high", "xhigh", "max")

EFFORT_DESCRIPTIONS: Mapping[str, str] = MappingProxyType(
    {
        "low": "fastest, least thinking",
        "medium": "moderate thinking",
        "high": "thorough",
        "xhigh": "extended reasoning depth",
        "max": "maximum effort",
    }
)


@dataclass(frozen=True, slots=True)
class ModelChoice:
    """One entry of the CLI's own model list, as its ``initialize`` reply gives it."""

    value: str
    display: str
    description: str = ""
    resolved: str = ""
    efforts: tuple[str, ...] = ()

    @classmethod
    def from_init(cls, raw: Mapping[str, Any]) -> ModelChoice:
        return cls(
            value=str(raw.get("value", "")),
            display=str(raw.get("displayName", raw.get("value", ""))),
            description=str(raw.get("description", "")),
            resolved=str(raw.get("resolvedModel", "")),
            efforts=tuple(str(e) for e in raw.get("supportedEffortLevels", []) or []),
        )


#: What the CLI listed on 2026-09-19 under a Max subscription; used only when
#: no live connection has answered yet. The live list always wins.
FALLBACK_MODELS: tuple[ModelChoice, ...] = (
    ModelChoice("default", "Default (recommended)", "the CLI's own default", "", EFFORT_LEVELS),
    ModelChoice("opus[1m]", "Opus (1M context)", "Opus 5 with 1M context", "claude-opus-5[1m]", EFFORT_LEVELS),
    ModelChoice("claude-fable-5-1[1m]", "Fable", "Fable 5.1", "claude-fable-5-1", EFFORT_LEVELS),
    ModelChoice("sonnet", "Sonnet", "Sonnet 5", "claude-sonnet-5", EFFORT_LEVELS),
    ModelChoice("haiku", "Haiku", "Haiku 4.5", "claude-haiku-4-5-20251001", ()),
)


#: Plumbing and tests never inherit a heavyweight default.
TEST_MODEL = "claude-haiku-4-5-20251001"

#: The CLI prefers an API key over OAuth when one is present, and the SDK
#: passes the parent environment through. Blanking these keeps every run on
#: the subscription. Measured once; not re-tested.
SUBSCRIPTION_ENV: Mapping[str, str] = MappingProxyType(
    {"ANTHROPIC_API_KEY": "", "ANTHROPIC_AUTH_TOKEN": ""}
)


# ---------------------------------------------------------------------------
# Modes — the / commands that switch focus
# ---------------------------------------------------------------------------

ModeKind = Literal["agent", "graph"]


@dataclass(frozen=True, slots=True)
class Mode:
    """One focus the shell can be in. ``/<name>`` switches to it.

    ``agent`` modes are a plain Claude connection with the given system prompt
    and tool surface. The ``graph`` mode is the provenance cycle. The system
    prompt shapes map onto the SDK's: a preset, a preset with an append, an
    inline string, or a file.
    """

    name: str
    kind: ModeKind = "agent"
    description: str = ""
    #: ``"preset"`` for Claude Code's own prompt; a string for a custom one;
    #: ``{"preset": "claude_code", "append": "..."}``; or ``{"file": "..."}``.
    system_prompt: str | Mapping[str, Any] | None = None
    #: ``None`` keeps the CLI's default tools; a list is an allow-list.
    tools: tuple[str, ...] | None = None
    #: Tools that never prompt in this mode (``allowed_tools``).
    allowed_tools: tuple[str, ...] = ()
    model: str | None = None

    #: Where this mode was defined: the directory of the ``modes.toml`` that
    #: declared it, or the package for a built-in. A prompt ``file`` is
    #: relative to this first, then to the package's own ``prompts/``.
    origin: Path | None = None

    def prompt_file(self, base_dir: Path) -> Path:
        """Resolve ``system_prompt = { file = ... }``: beside the modes file
        that declared the mode if it is there, else in the package."""
        name = Path(str(self.system_prompt["file"]))  # type: ignore[index]
        candidates = [name] if name.is_absolute() else [
            *([self.origin / name] if self.origin is not None else []),
            base_dir / name,
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate.resolve()
        return candidates[-1].resolve()

    def sdk_system_prompt(self, base_dir: Path) -> Any:
        """The ``ClaudeAgentOptions.system_prompt`` value for this mode."""
        sp = self.system_prompt
        if sp is None or sp == "preset":
            return {"type": "preset", "preset": "claude_code"}
        if isinstance(sp, str):
            return sp
        if "file" in sp:
            return {"type": "file", "path": str(self.prompt_file(base_dir))}
        if "preset" in sp:
            out: dict[str, Any] = {"type": "preset", "preset": sp["preset"]}
            if sp.get("append"):
                out["append"] = sp["append"]
            return out
        raise ValueError(f"mode {self.name!r}: unrecognised system_prompt {sp!r}")


DEFAULT_MODES: tuple[Mode, ...] = (
    Mode(
        name="chat",
        kind="agent",
        description="Plain Claude Code session — the default connection.",
        system_prompt="preset",
    ),
    Mode(
        name="graph",
        kind="graph",
        description="The provenance cycle: orientate, antithesis, synthesis.",
        system_prompt={"file": "prompts/graph_system.md"},
    ),
)


@dataclass(frozen=True, slots=True)
class Modes:
    modes: Mapping[str, Mode]
    base_dir: Path
    default: str = "chat"

    def __getitem__(self, name: str) -> Mode:
        return self.modes[name]

    def __contains__(self, name: str) -> bool:
        return name in self.modes

    def names(self) -> tuple[str, ...]:
        return tuple(self.modes)

    @property
    def graph(self) -> Mode:
        for m in self.modes.values():
            if m.kind == "graph":
                return m
        raise KeyError("no graph mode defined")


def builtin_modes(base_dir: Path) -> Modes:
    """The two modes that exist without any file."""
    return Modes(modes={m.name: m for m in DEFAULT_MODES}, base_dir=base_dir)


def load_modes(path: Path, *, base_dir: Path | None = None) -> Modes:
    """Read ``modes.toml``; the built-ins are the base and the file overrides.

    Format, one table per mode::

        [modes.reviewer]
        kind = "agent"
        description = "Review the diff"
        system_prompt = { preset = "claude_code", append = "You are reviewing." }
        tools = ["Read", "Glob", "Grep"]
    """
    base = base_dir or path.parent
    modes = dict(builtin_modes(base).modes)
    data = tomllib.loads(path.read_text()) if path.exists() else {}
    for name, block in (data.get("modes") or {}).items():
        known = {f.name for f in fields(Mode)} - {"name"}
        unknown = sorted(set(block) - known)
        if unknown:
            raise ValueError(f"mode {name!r} sets unknown key(s): {unknown}")
        kwargs = dict(block)
        if "tools" in kwargs and kwargs["tools"] is not None:
            kwargs["tools"] = tuple(kwargs["tools"])
        if "allowed_tools" in kwargs:
            kwargs["allowed_tools"] = tuple(kwargs["allowed_tools"])
        modes[name] = Mode(name=name, origin=path.parent.resolve(), **kwargs)
    default = (data.get("default") or "chat")
    if default not in modes:
        raise ValueError(f"default mode {default!r} is not defined")
    return Modes(modes=modes, base_dir=base, default=default)


# ---------------------------------------------------------------------------
# The whole configuration a shell runs with
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Everything the runner needs, built once by the entry point."""

    #: The working directory the SDK sessions run in (what the model reads).
    cwd: Path
    #: Where sessions, checkpoints and event logs live.
    sessions_dir: Path
    modes: Modes
    settings: ModelSettings = field(default_factory=ModelSettings)
    budgets: Budgets = field(default_factory=Budgets)
    prices: Mapping[str, int] = DEFAULT_PRICES
    #: Extra environment for every SDK subprocess (tests point this at Haiku).
    extra_env: Mapping[str, str] = field(default_factory=dict)

    @classmethod
    def default(cls, cwd: Path | None = None, **overrides: Any) -> AppConfig:
        root = Path(cwd or Path.cwd()).resolve()
        package_dir = Path(__file__).parent
        modes_file = root / "modes.toml"
        modes = load_modes(modes_file, base_dir=package_dir) if modes_file.exists() else builtin_modes(package_dir)
        kwargs: dict[str, Any] = {"cwd": root, "sessions_dir": root / "sessions", "modes": modes}
        kwargs.update(overrides)
        return cls(**kwargs)
