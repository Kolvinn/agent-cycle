"""Spike 8 — the same four mechanisms under pydantic_graph, for a fair read.

Counterpart to spike 6. `pydantic_graph` is the graph layer that ships with
Pydantic AI, and it is genuinely well typed: steps declare their input and
output types, edges are checked, and `render()` emits mermaid. The two things it
does not have are the two the turn structure leans on.

`pydantic-ai-slim` is deliberately NOT a project dependency — this spike exists
to justify that. Run it out of project:

    uv run --with pydantic-ai-slim --no-project --python 3.14 \
        python scripts/spikes/spike_08_pydantic_graph_control.py
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field

from pydantic_graph import GraphBuilder

RESULTS: list[tuple[str, bool]] = []


def check(label: str, ok: bool, detail: str) -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    for line in detail.strip().splitlines():
        print(f"         {line}")
    print()
    RESULTS.append((label, ok))


@dataclass
class Flow:
    prompt: str = ""
    thesis_reasoning: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    spent: int = 0


@dataclass
class Crossing:
    """The typed edge payload — this is pydantic_graph's projection seam."""

    assumptions: list[str]
    spent: int


builder = GraphBuilder(state_type=Flow, input_type=str, output_type=list[str])

SEEN_BY_ANTITHESIS: dict[str, object] = {}


@builder.step
async def assume(ctx) -> Crossing:
    ctx.state.prompt = ctx.inputs
    ctx.state.assumptions.append("A: the runner owns the order")
    ctx.state.thesis_reasoning.append("I felt confident because phases.py says so")
    ctx.state.spent += 5
    return Crossing(assumptions=list(ctx.state.assumptions), spent=ctx.state.spent)


@builder.step
async def antithesis(ctx) -> list[str]:
    # The *input* is narrow. `ctx.state` is not: it is the whole Flow, so the
    # affirming transcript is one attribute access away. Recorded, not asserted.
    SEEN_BY_ANTITHESIS["input_type"] = type(ctx.inputs).__name__
    SEEN_BY_ANTITHESIS["state_exposes_transcript"] = hasattr(
        ctx.state, "thesis_reasoning"
    )
    ctx.state.assumptions.append("X: or the order is an artefact of the harness")
    return ctx.state.assumptions


builder.add_edge(builder.start_node, assume)
builder.add_edge(assume, antithesis)
builder.add_edge(antithesis, builder.end_node)
graph = builder.build()


async def main() -> int:
    print("=" * 78)
    print("  Spike 8 — the same primitives under pydantic_graph")
    print("=" * 78)

    state = Flow()
    await graph.run(inputs="why is the order fixed?", state=state)

    check(
        "A. typed state accumulates across steps",
        len(state.assumptions) == 2,
        f"assumptions={state.assumptions} spent={state.spent}\n"
        "(mutated in place — there is no reducer/channel concept)",
    )

    check(
        "B. a step can be denied part of the state",
        SEEN_BY_ANTITHESIS.get("state_exposes_transcript") is False,
        f"the step's input type was {SEEN_BY_ANTITHESIS.get('input_type')!r} (narrow),\n"
        f"but ctx.state exposes thesis_reasoning="
        f"{SEEN_BY_ANTITHESIS.get('state_exposes_transcript')}\n"
        "so the boundary is a convention the author keeps, not a wall",
    )

    stepped: list[str] = []
    async with graph.iter(inputs="second run", state=Flow()) as run:
        async for item in run:
            stepped.append(type(item).__name__)
            if len(stepped) > 8:
                break
    check(
        "C. suspend on a call and resume by value (as a primitive)",
        False,
        f"iter() yields {stepped}, and GraphRun.next()/override_next() let the\n"
        "caller drive one task at a time — but there is no interrupt()/resume\n"
        "primitive, so suspension and its persistence are the caller's to build",
    )

    import pydantic_graph

    exported = dir(pydantic_graph)
    persistence = [n for n in exported if "ersist" in n or "napshot" in n]
    check(
        "D. built-in persistence / resume from a stored point",
        bool(persistence),
        f"pydantic_graph exports {len(exported)} names, none matching "
        f"persist/snapshot\n"
        "state is a plain object the caller stores; durability comes from the\n"
        "temporal / dbos / prefect integrations in pydantic_ai.durable_exec",
    )

    passed = sum(ok for _, ok in RESULTS)
    print("=" * 78)
    print(f"  {passed}/{len(RESULTS)} mechanisms confirmed (spike 6 scores 5/5)")
    print("=" * 78)
    print()
    print("The graph does render itself, which is worth something here:")
    print(graph.render())
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
