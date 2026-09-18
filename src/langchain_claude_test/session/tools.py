"""The tools the agent may call, as plain functions.

Kept pure and MCP-free on purpose: the SDK wrapper is a separate, thin layer,
so every tool can be tested for correctness and for sandbox escapes without a
model or a subprocess anywhere near it.

Two tiers, and the split is not about cost:

- ``free`` — the call consumes no provenance hop. ``list_dir`` surveys without
  forming a claim; reading a path the user named is depth 0 because the user
  handed over the target.
- ``gated`` — the call targets something the agent worked out for itself.

Free still means logged and tagged. A free result is ordinary evidence, and
anything citing it inherits depth normally; skipping that is how a discovered
reference launders itself into one the user supposedly named.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..ledger.models import CallTier


class ToolError(Exception):
    """A tool refusing its own arguments — distinct from the gate refusing the
    call. Surfaced to the model as text either way, but logged differently."""


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    tier: CallTier
    description: str
    schema: dict[str, type]
    fn: Callable[..., str]


def _resolve(root: Path, path: str) -> Path:
    """Resolve ``path`` under ``root``, refusing anything that escapes.

    Checked with ``is_relative_to`` after full resolution, so symlinks and
    ``..`` are both caught — a sandbox that only string-matches ``..`` is not a
    sandbox.
    """
    root = root.resolve()
    # An absolute path is refused outright rather than reinterpreted relative
    # to the root. Quietly turning '/etc/passwd' into '<root>/etc/passwd' would
    # be safe but dishonest — the caller asked for something specific and would
    # be handed something else under the same name.
    if path.startswith("/"):
        raise ToolError(f"path {path!r} is absolute and escapes the fixture root")
    candidate = (root / path).resolve()
    if candidate != root and not candidate.is_relative_to(root):
        raise ToolError(f"path {path!r} escapes the fixture root")
    return candidate


def make_tools(root: Path) -> dict[str, ToolSpec]:
    """Build the toolset bound to one fixture root."""
    root = Path(root).resolve()

    def list_dir(path: str = ".") -> str:
        """FREE. Survey a directory. Forms no claim, so it costs no hop."""
        target = _resolve(root, path)
        if not target.is_dir():
            raise ToolError(f"{path!r} is not a directory")
        entries = sorted(
            (p.name + ("/" if p.is_dir() else "")) for p in target.iterdir() if not p.name.startswith(".")
        )
        return "\n".join(entries) if entries else "(empty)"

    def read_file(path: str) -> str:
        """Read a file, numbered. Tier depends on who named the path — the gate
        decides that, not this function."""
        target = _resolve(root, path)
        if not target.is_file():
            raise ToolError(f"{path!r} is not a file")
        lines = target.read_text().splitlines()
        return "\n".join(f"{i}:{line}" for i, line in enumerate(lines, 1))

    def grep(pattern: str) -> str:
        """GATED. Search the fixture. Output is sorted so a run is repeatable."""
        if not pattern.strip():
            raise ToolError("pattern is empty")
        hits: list[str] = []
        for file in sorted(root.rglob("*.py")):
            try:
                lines = file.read_text().splitlines()
            except (OSError, UnicodeDecodeError):
                continue
            for i, line in enumerate(lines, 1):
                if pattern in line:
                    hits.append(f"{file.relative_to(root)}:{i}:{line}")
        return "\n".join(hits) if hits else f"(no matches for {pattern!r})"

    specs = [
        ToolSpec(
            name="list_dir",
            tier="free",
            description=(
                "List a directory inside the project. Use this to get your bearings. "
                "Free: it forms no claim, so it costs no provenance hop."
            ),
            schema={"path": str},
            fn=list_dir,
        ),
        ToolSpec(
            name="read_file",
            tier="gated",
            description=(
                "Read a file, with line numbers. Free when the user named this exact "
                "path; otherwise it needs an approved claim to serve."
            ),
            schema={"path": str, "for_node_id": str},
            fn=read_file,
        ),
        ToolSpec(
            name="grep",
            tier="gated",
            description=(
                "Search the project for a literal string. Requires for_node_id: the "
                "approved claim this search is gathering evidence for."
            ),
            schema={"pattern": str, "for_node_id": str},
            fn=grep,
        ),
    ]
    return {s.name: s for s in specs}


#: Arguments the gate consumes and the tool functions never see.
GATE_ARGS = frozenset({"for_node_id"})


def call_tool(spec: ToolSpec, args: dict[str, Any]) -> str:
    """Invoke a tool with the gate's own arguments stripped out."""
    payload = {k: v for k, v in args.items() if k not in GATE_ARGS}
    return spec.fn(**payload)
