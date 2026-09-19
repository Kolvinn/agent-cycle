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

    #: Five points per reading — the user's number: *"if there are 3
    #: assumptions, where each assumption has a budget of 5"*.
    per_assumption: int = 5
    #: The rival pass is funded at ``base + N``, and base is five: *"the budget
    #: has the base (5) + assumption N (3) = 8"*.
    antithesis_base: int = 5
    #: Points for the wide orientation pass. Never assigned by the design.
    orientation_points: int = 5
    #: Points for the whole synthesis conversation of one cycle, not per
    #: exchange: looking is bounded, talking is not.
    synthesis_points: int = 5
    #: Ceiling on readings per cycle. *"there should be a limit on the amount
    #: of assumptions produced"* — the limit is required, the number is not.
    max_assumptions: int = 3
    #: How many times a frame may re-author an answer of the wrong shape.
    max_reauthor_attempts: int = 2
    #: What an in-graph bookkeeping write costs. Every priced example the user
    #: gave was evidence gathering, so this stays visible in one field.
    graph_write_price: int = 0

    def with_(self, **overrides: Any) -> Budgets:
        return replace(self, **overrides)


#: Fields whose value is a placeholder, not a decision.
PROVISIONAL: frozenset[str] = frozenset(
    {
        "orientation_points",
        "synthesis_points",
        "max_assumptions",
        "max_reauthor_attempts",
        "graph_write_price",
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

    def sdk_system_prompt(self, base_dir: Path) -> Any:
        """The ``ClaudeAgentOptions.system_prompt`` value for this mode."""
        sp = self.system_prompt
        if sp is None or sp == "preset":
            return {"type": "preset", "preset": "claude_code"}
        if isinstance(sp, str):
            return sp
        if "file" in sp:
            return {"type": "file", "path": str((base_dir / sp["file"]).resolve())}
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
        description="The provenance cycle: orientate, assume, antithesis, synthesis.",
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
        modes[name] = Mode(name=name, **kwargs)
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
