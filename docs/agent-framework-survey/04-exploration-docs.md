# 04 — docs/exploration

Slice: `agent_framework/docs/exploration/` (39 markdown files). Read-only survey; nothing in
`agent_framework/` was modified. All paths below are relative to
`/workspaces/langchain-claude-test/agent_framework/docs/exploration/` unless given in full.

## Scope covered

All 39 files were opened. 15 were read in full (the priority list plus `repo-overview-and-
timeline.md`, used for orientation): `middleware-tool-gating.md`, `mcp-and-tool-servers.md`,
`deep-agents-viability.md`, `deep-agents-graph-internals.md`, `agent-architecture-
comprehensive.md`, `agent-runtime-layer.md`, `agent-runtime-models.md`, `agent-runtime-models-
analysis.md`, `dynamic-runtime-capabilities.md`, `architectural-decision-history.md`, `overhaul-
and-thought-tree-map.md`, `folder-structure-pressure-test.md`, `investigation-requirements.md`,
`repo-overview-and-timeline.md`, `pydantic-ai-rag-pipeline-analysis.md`. The remaining 24 were
skimmed (headers + first ~15 lines each) to confirm subject and route them into the map below.

## Map

**Agent-control docs** (agent orchestration, tool gating, middleware, multi-agent hierarchy —
the closest prior art to the provenance-ledger project):
- `middleware-tool-gating.md` — LangChain `wrap_tool_call`/`wrap_model_call` dynamic tool gating research. The single most relevant file in the slice; detailed below.
- `mcp-and-tool-servers.md` — MCP client/server layering in the LangChain ecosystem (tool exposure, not tool gating).
- `deep-agents-viability.md` — Can `create_deep_agent()` host custom middleware? (No.)
- `deep-agents-graph-internals.md` — Deep Agents' internal middleware stack and graph-compilation internals.
- `agent-architecture-comprehensive.md` — A 5-type multi-agent hierarchy (orchestrator/thinker/implementer/auditor/explorer) with read/write boundaries and approval gates.
- `dynamic-runtime-capabilities.md` — Runtime reconfiguration mechanisms (graph factories, configurable headers, PATCH APIs) for tools/skills/MCP.
- `architectural-decision-history.md` — Cross-document audit of ~20 sessions of decisions, timelines, and unresolved issues.
- `overhaul-and-thought-tree-map.md` — Orientation map of a large paused RAG-architecture design effort (mostly domain, some agent-workspace-structure methodology).
- `folder-structure-pressure-test.md` — A methodological pressure-test of a proposed multi-agent workspace folder layout; contains the closest thing to a provenance/lineage schema in the slice.
- `investigation-requirements.md` — Requirements digest for a RAG drift-handling investigation (mostly domain; has one transferable epistemic pattern, see Salvage).

**Runtime & substrate docs** (concrete, already-implemented code in the old repo's
`agent_runtime/` and controller — a working sibling implementation of "middleware gates tools"):
- `agent-runtime-layer.md` — Full function map of `src/agent_runtime/` (11 files, 42 functions), including `CapabilityRegistryMiddleware`.
- `agent-runtime-models.md`, `agent-runtime-models-analysis.md` — Pydantic model definitions (`ToolDef`, `ToolImplRef`, `AgentConfig`, etc.) and their validation/serialization patterns.
- `controller-model-definitions.md`, `controller-operations-layer.md`, `data-model-audit.md`, `config-model-map.md`, `field-inventory-models.md`, `manifest-serialization-chain.md`, `models-db-layer.md`, `operations-analysis.md`, `structural-inventory.md`, `project-structure-summary.md`, `db-alembic-infrastructure.md` — controller/CLI/Docker/DB plumbing that generates and delivers the manifest the runtime consumes. Container-orchestration infrastructure, not agent-reasoning logic.
- `flox-activate-exit-on-error.md`, `flox-manifest-summary.md` — Flox environment-activation mechanics, unrelated to gating.
- `repo-overview-and-timeline.md` — Git/branch/folder orientation map for the whole old repo (used here for context, not itself agent-control content).

**Domain (RAG, graph, DB, topic-modeling) docs** — not relevant to the provenance-ledger project,
skimmed hard per instructions:
- `bertopic-integration.md`, `pydantic-ai-rag-pipeline-analysis.md`, `memory-alembic-layer.md`, `memory-manager-pipeline-map.md`, `postgres-topic-centroid-analysis.md`, `qdrant-graphrag-analysis.md`, `graphrag-schema-falkordb-analysis.md`, `graph-schema-prior-work.md`, `topic-to-concept-prior-reasoning.md`, `vector-rag-pipeline-map.md`, `folder-pipeline-mapping-verification.md`, `folder-pipeline-mirror-design.md`.
- One-line notes on each are in the "Remaining files" pass below.

### One-liners on the skimmed/remaining files

| File | One-liner |
|---|---|
| `bertopic-integration.md` | BERTopic topic-modeling pipeline inventory (Ollama embedder, paragraph chunking). Pure RAG domain. |
| `config-model-map.md` | Cross-cutting YAML/JSON config file map (`defaults.json`, docker-compose). Controller plumbing. |
| `controller-model-definitions.md` | Full structural map of `src/schema.py`/`validators.py`/`registry.py` Pydantic models. Controller plumbing. |
| `controller-operations-layer.md` | Function map of FastAPI app + operations layer (79 functions across 12 files). Controller plumbing. |
| `data-model-audit.md` | DB-migration field inventory across registry/schema/runtime models. Controller plumbing. |
| `db-alembic-infrastructure.md` | Alembic/SQLite migration infrastructure audit. Unrelated to gating. |
| `field-inventory-models.md` | Field-by-field table of `agent_runtime/models.py`. Duplicate/adjacent to `agent-runtime-models.md`. |
| `flox-activate-exit-on-error.md` | Debug note on `flox activate` exiting on non-zero exit code. Unrelated. |
| `flox-manifest-summary.md` | Condensed reference for Flox `manifest.toml` syntax. Unrelated. |
| `folder-pipeline-mapping-verification.md` | Verifies a workspace folder structure mirrors pipeline *schema*, not pipeline *state*. RAG-workspace domain. |
| `folder-pipeline-mirror-design.md` | Proposes mapping the agent-workspace folder layout onto the RAG pipeline's output format. RAG-workspace domain. |
| `graph-schema-prior-work.md` | Digest of a Memgraph/EdgeType graph-schema implementation (38 bootstrap edge types). RAG domain. |
| `graphrag-schema-falkordb-analysis.md` | Confirms Memgraph (not FalkorDB/Neo4j) was the selected graph DB. RAG domain. |
| `manifest-serialization-chain.md` | Traces `write_manifest`/`generate_manifest` signatures end-to-end. Controller plumbing. |
| `memory-alembic-layer.md` | Function map of memory-manager + Alembic + MCP server (63 functions, 13 files). RAG domain. |
| `memory-manager-pipeline-map.md` | Documents two parallel, divergent memory-manager ingestion pipelines. RAG domain. |
| `models-db-layer.md` | Function map of `src/models/`, `src/db/` (17 files). Controller plumbing. |
| `operations-analysis.md` | Import/dependency map of `src/operations.py`. Controller plumbing. |
| `postgres-topic-centroid-analysis.md` | Confirms Postgres is a half-integrated secondary DB for topic-centroid tracking. RAG domain. |
| `project-structure-summary.md` | Whole-project layout/dependency/testing overview. Orientation only. |
| `qdrant-graphrag-analysis.md` | Two divergent Qdrant integration paths documented. RAG domain. |
| `structural-inventory.md` | Line-by-line inventory of the original 10-file controller bootstrap system. Controller plumbing (earliest version). |
| `topic-to-concept-prior-reasoning.md` | Consolidated digest of topic→concept design reasoning across 7+ prior files. RAG domain. |
| `vector-rag-pipeline-map.md` | Full DAG map of the V8 multi-pass tree-builder RAG pipeline. RAG domain. |

## middleware-tool-gating.md, in detail

Dated 2026-05-16, sourced from a direct fetch-and-grep of `docs.langchain.com` (LangChain,
LangGraph, Deep Agents, LangSmith docs), not recalled from training data — the same discipline
PLAN.md itself insists on. This is a **capability survey of what LangChain middleware can do**,
not a design document for a provenance ledger — it never uses the words "provenance,"
"lineage," or "explicit/implicit." But its subject (dynamically gating a tool call before it
executes) is exactly the mechanism surface the new project needs, and it nails down the correct
interception point precisely.

**The core mechanism it settles on, `wrap_tool_call`** (middleware-tool-gating.md:22–48):

> "`wrap_tool_call` is the most powerful hook for dynamic gating. It wraps **every** tool
> invocation and lets you:
> 1. **Short-circuit (zero handler calls)** — Return a `ToolMessage` directly without executing
>    the tool
> 2. **Modify (one or more handler calls)** — Edit args before passing to the handler
> 3. **Conditionally block** — Check external state (env var, Redis, API, config) and decide"

```python
from langchain.agents.middleware import wrap_tool_call
from langchain.messages import ToolMessage
from langchain.tools.tool_node import ToolCallRequest
from langgraph.types import Command

@wrap_tool_call
def dynamic_gate(
    request: ToolCallRequest,
    handler: Callable[[ToolCallRequest], ToolMessage | Command],
) -> ToolMessage | Command:
    tool_name = request.tool_call["name"]
    if not is_tool_allowed(tool_name):  # external config check
        return ToolMessage(
            content=f"Tool '{tool_name}' is disabled by policy.",
            tool_call_id=request.tool_call["id"],
        )
    return handler(request)  # normal execution
```

The document surveys five gating strategies (env-var, Redis/external config, agent-state/role-
based, graph-factory rebuild, and `HumanInTheLoopMiddleware`), all variations on the same
`wrap_tool_call` short-circuit. Its **recommended approach** (middleware-tool-gating.md:339–393)
is a `ConfigGatingMiddleware(AgentMiddleware)` class whose `wrap_tool_call` checks an
`_is_tool_enabled(name)` helper (env var → Redis fallback → default-enabled) before calling
`handler(request)`. Structurally this is a direct skeleton for a `ProvenanceLedgerMiddleware`:
swap `_is_tool_enabled(name)` for a ledger lookup keyed on `request.tool_call["args"]` against
the explicit/implicit node graph, and swap the "disabled by policy" `ToolMessage` for the
depth-2 hard-stop message PLAN.md specifies.

**What was tried and rejected, explicitly.** The Limitations table (middleware-tool-
gating.md:302–313) is the most load-bearing part of the file for this project:

| Limitation | Detail |
|---|---|
| `interrupt_on` is **static** | "Configured at middleware construction time. Cannot be changed mid-run... Use `wrap_tool_call` for dynamic gating instead." |
| Short-circuited tools still count as "tool calls" | "`wrap_tool_call` returning a ToolMessage means the agent thinks a tool ran. If you want the model to retry without the tool, use the response message strategically." |
| No built-in middleware registry | "There's no central 'tool registry' for gating — each middleware must do its own config lookups." |
| Middleware order matters | "Middleware is applied in list order. Outer middleware wraps inner. **Gating middleware should be outermost** to catch all calls." |
| Cannot add/remove middleware at runtime | "The middleware list is frozen at `create_agent()` time... Use wrap-style hooks with shared mutable state to work around this." |

Two of these bite directly on PLAN.md's open items: (1) the "short-circuited tools still count
as tool calls" note matters for the ledger's own bookkeeping-call exemption (item 11 in
PLAN.md) — a ledger-check call that short-circuits still shows up in the transcript as a tool
call and needs to be distinguished from a real one if the 5-call counter reads the message
history rather than an explicit counter; (2) the "interrupt_on is static" limitation directly
rules out using `HumanInTheLoopMiddleware`'s declarative `interrupt_on` dict for the depth-2
"ask the user" gate — PLAN.md's gate is dynamic (fires conditionally per-call based on
computed depth), so it must be hand-rolled via `wrap_tool_call` + `langgraph.types.interrupt()`,
confirmed working elsewhere in this slice at `agent_runtime/skills.py`'s
`load_skill_with_hitl()` (see agent-runtime-layer.md:183–187).

**Decision flowchart** (middleware-tool-gating.md:403–417) confirms `wrap_tool_call` +
external/shared state is the right general shape when gating needs to react to something
outside the model's own tool-list, which a provenance ledger is.

**Does it answer PLAN.md's Open item 2 ("how does a tool call's depth actually get
computed")? No — it doesn't even ask the question.** Every gating strategy surveyed here
checks a *pre-existing, externally-sourced* boolean or role (env var, Redis flag, agent-state
role) — never a *computed* property of the tool call's own arguments relative to conversation
history. There is no text-matching, no self-report, no hybrid approach discussed anywhere in
this file or elsewhere in the slice. The document answers **where** the gate check must live
(`wrap_tool_call`, outermost middleware, before `handler(request)`) but says nothing about
**what** the check should compute. PLAN.md's Open item 2 is a genuinely open question this
prior work never approached.

## Agent substrate conclusions

**LangChain `create_agent()` — confirmed correct substrate.** Multiple documents converge on
the same verdict from different angles:

- `deep-agents-viability.md:18–41` and `deep-agents-graph-internals.md:20-41` both confirm
  `create_deep_agent()` has **no `middleware=` parameter** for custom `wrap_model_call`/
  `wrap_tool_call` hooks — the middleware stack (`TodoList → Skills → Filesystem → SubAgent →
  Summarization → PatchToolCalls → [your middleware] → HarnessProfile extras →
  AnthropicPromptCaching → Memory → HumanInTheLoop`) is fixed by `create_deep_agent()` itself
  (deep-agents-graph-internals.md:98–134), with user middleware only insertable in the middle
  of that stack, never as the outermost wrapper the tool-gating doc says gating middleware
  needs to be.
- `deep-agents-viability.md`'s final recommendation (deep-agents-viability.md:458–462):
  *"Use Option A (spec as-is)"* — i.e., `create_agent()` directly, not `create_deep_agent()` —
  *"The dynamic runtime needs full control over middleware and tool dispatch — which
  `create_agent()` provides and `create_deep_agent()` does not."*
- The old repo's own already-built runtime (`agent-runtime-layer.md`, `graph_assembly.py`)
  independently reached the same conclusion in production code: it offers **two graph-assembly
  variants**, "LangChain manual graph (A)" via `create_agent()` and "Deep Agents (B)" via
  `create_deep_agent()`, "sharing `CapabilityRegistryMiddleware`" (agent-runtime-layer.md:107–
  109) — i.e. even when Deep Agents is used, the gating middleware is injected the same way,
  and `create_agent()` is the variant with full control.

**MCP — orthogonal to bind_tools gating, not a gating mechanism itself.**
`mcp-and-tool-servers.md` surveys four MCP integration layers (`langchain-mcp-adapters`,
LangSmith Tool Server, Agent Server `/mcp` endpoint, LangSmith's own remote MCP), and
`dynamic-runtime-capabilities.md` covers the same ground from the "how do I dynamically
enable/disable tools" angle. Neither ever discusses gating already-bound tool calls; MCP in
this ecosystem is about *how tools get discovered and loaded*, not about *intercepting a call
once the model has already decided to make it*. This confirms PLAN.md's own scoping instinct
(item 9: v1 = `bind_tools` calls only) — MCP tool loading and provenance gating are separate
concerns that don't need to intersect for v1.

**Pydantic AI — tried and explicitly abandoned in favor of LangChain, for reasons that support
the new project's choice.** `pydantic-ai-rag-pipeline-analysis.md` is written from the vantage
point of "preparing to switch from pydantic-ai/pydantic-graph back to LangChain + LangGraph"
(pydantic-ai-rag-pipeline-analysis.md:5). Its "Problematic" table (pydantic-ai-rag-pipeline-
analysis.md:387–397) says plainly: *"`pydantic-graph API instability` — `rag_handle2.py`
imports from `pydantic_graph` but the API surface is less stable than LangGraph... the
ecosystem is immature."* The file's closing "Key insight" (pydantic-ai-rag-pipeline-
analysis.md:453) states the production pipeline already lived in LangChain/LangGraph
(`chunk_graph.py`, `tree_builder.py`) and pydantic-ai was only ever a parallel prototype for
structured-output labeling — never the main agent runtime.

**Net effect on the new project's direction:** nothing in this slice discusses
`langchain-claude-cli` specifically (the old repo predates it), but everything the old repo
tried and converged on — `create_agent()` over `create_deep_agent()`, LangChain/LangGraph over
Pydantic AI, `wrap_tool_call` as the interception point — argues *for* the shape of the new
project's direction, not against it.

## Any prior provenance/lineage thinking

**No prior notion of tracking *where a tool call's target came from* (the PLAN.md sense —
explicit vs. implicit, depth-of-hop from the user's own words) exists anywhere in this slice.**
Searched deliberately across all 39 files; the closest analogues are about *data* provenance
and *artifact* provenance, not *action* provenance, and are worth recording because they show
the user's past self circling the same instinct from a different domain:

1. **Data-classification provenance** (`agent-architecture-comprehensive.md:244`, citing
   `docs/briefs/taxonomy-audit.md`, outside this slice): *"`learning/constraint` vs
   `knowledge/rule` — Provenance IS the category."* This is about a RAG taxonomy schema: whether
   a piece of content is filed as a "learning" (discovered during work) or a "rule" (stated
   upfront) is decided entirely by where it came from. It is a real precursor to "provenance as
   a first-class axis," but it classifies stored *knowledge chunks*, not agent *actions*.

2. **Artifact/session provenance headers** (`folder-structure-pressure-test.md:194`, its
   Recommended Modification #4): a proposed per-file header with *"at minimum: `goal`, `task`,
   `spawn_id`, `session_id`, `parents` (cross-goal edges), `in_scope_constraints`... This is the
   minimum provenance that is machine-readable."* This is structurally the closest thing to a
   ledger-node schema anywhere in the slice — an artifact with an explicit `parents` link back
   to what produced it, exactly the shape of PLAN.md's "every implicit node must link back to
   the explicit node(s) it was derived from" (PLAN.md:22–23). But it is scoped to multi-agent
   *work-product* lineage (which spawn/session wrote this markdown file), not to a single
   agent's *tool-call* lineage within one session.

3. **Graph-edge provenance** (`architectural-decision-history.md`'s Relationship Key Map,
   §5): a `DERIVES_FROM` edge type (Goal→Knowledge) that records *this goal's reasoning derives
   from this knowledge chunk* — again data lineage in a Memgraph schema, not action gating.

4. **A direct, unresolved contradiction with runtime gating as a concept**
   (`architectural-decision-history.md:270–272, 349–351`): the old repo's own "5-Layer
   Architecture" spec states as a Core Principle: *"Agents are pure config. Packages are the
   unit of capability. The database tracks state, not permissions. **There is no runtime
   gating.**"* And later: *"No runtime gating — only gate is package registration (vesting)."*
   This is the old repo's own past self **explicitly rejecting** the runtime-gating approach
   that `CapabilityRegistryMiddleware` had already been built to do, in favor of gating only at
   config/registration time. See "Open threads & contradictions" below — this is worth the
   user's attention since PLAN.md's entire premise is runtime, per-call gating.

**Conclusion for key question 2: no, this slice contains no prior provenance-of-action
thinking. It contains prior provenance-of-data-and-artifact thinking, and it contains a
documented, unresolved internal disagreement about whether runtime gating is even the right
layer to gate at.**

## Answers to the key questions

**1. What exactly was the gating mechanism in `middleware-tool-gating.md`? Open problems? Does
it answer Open item 2?**
The mechanism is LangChain's `wrap_tool_call` middleware hook (an `AgentMiddleware` subclass or
`@wrap_tool_call`-decorated function), used as an interceptor that either calls
`handler(request)` to proceed or returns a `ToolMessage`/`Command` to short-circuit — not a
wrapper class around the LLM, not an MCP interceptor, not a Claude Code hook. Open problems
found: `interrupt_on` is static (can't be used for dynamic per-call gating);
short-circuited calls still appear as completed tool calls in the transcript; no built-in
registry — every gating middleware rolls its own state lookup; middleware order is significant
(gating middleware must be outermost); the whole middleware list is frozen at `create_agent()`
time (work around with mutable shared state, not by adding middleware later). **It does not
answer Open item 2** — it establishes *where* a depth/provenance check must be wired in, not
*how* depth gets computed. That computation question (text-match vs. self-report vs. hybrid) is
untouched by this document and by everything else in the slice.

**2. Was there prior provenance/lineage tracking, in agent control or data/graph models?**
In agent control: no, none, anywhere in this slice. In data/graph models: yes, but for content
classification and artifact/session lineage, not agent-action gating — see above. The one
explicit design position on *runtime gating as a concept* found in the slice is a rejection of
it ("no runtime gating — only gate is package registration"), which directly conflicts with
PLAN.md's approach and should be treated as a known internal contradiction, not new information
overlooked by PLAN.md's author.

**3. Deep-agents / LangGraph / Pydantic AI conclusions — for or against `langchain-claude-
cli`?** LangGraph/LangChain's `create_agent()` (not `create_deep_agent()`) is the repeatedly
confirmed correct substrate for custom tool-call interception — confirmed independently by a
docs-research file (`deep-agents-viability.md`), a source-code-reading file
(`deep-agents-graph-internals.md`), and the old repo's own shipped code
(`agent-runtime-layer.md`/`graph_assembly.py`). Pydantic AI was tried as the main agent runtime
and abandoned back to LangChain/LangGraph specifically because `pydantic_graph`'s API was
judged less stable/mature than LangGraph's. Nothing in this slice discusses
`langchain-claude-cli` by name (it postdates this old repo), but every substrate conclusion
reached here is consistent with, and lends independent support to, the new project's choice of
LangChain + `langchain-claude-cli` for `bind_tools` gating via middleware.

**4. What does `architectural-decision-history.md` record, and does its format separate
decided from assumed?** It records a cross-document audit — a timeline of ~20 named sessions
(2026-05-07 → 2026-06-17) each with a one-line focus and key output, a framework-migration
history (OpenCode → LangChain/LangGraph → container/controller → concurrent RAG track), a
Critical/Medium/Low-priority open-issues table, and a table of prior formally-numbered ADRs
(ADR-006 through ADR-023) that live *outside* this slice. Its format is **decisions vs. open
questions**, similar in spirit to PLAN.md's own "Decisions settled" / "Open" split, but it has
**no equivalent of PLAN.md's dedicated "Assumptions made while writing this plan" section** —
nothing in it flags a claim as "this was inferred by the author of this document and never
confirmed by the user," the exact discipline PLAN.md applies to itself. It is an audit of
decisions recorded elsewhere, not itself a decision log with the assumption-tracking rigor
PLAN.md introduces.

## Salvage rating

### Directly reusable for the provenance-ledger project
- The `wrap_tool_call` short-circuit pattern and the `ConfigGatingMiddleware` skeleton in
  `middleware-tool-gating.md:353–393` — swap the config-lookup body for a ledger-depth check.
  This is a near-literal starting point for a `ProvenanceLedgerMiddleware`.
- The Limitations table (`middleware-tool-gating.md:302–313`), specifically: gating middleware
  must be registered outermost; `interrupt_on` cannot be used for the dynamic depth-2 ask-gate,
  so `wrap_tool_call` + `langgraph.types.interrupt()` must be hand-rolled instead.
- `agent_runtime/skills.py`'s `load_skill_with_hitl()` (documented in `agent-runtime-
  layer.md:173–188`) — a working, already-implemented example of exactly that hand-rolled
  `interrupt()` pattern, including an "auto-approve if outside graph context" fallback, which is
  directly relevant to how PLAN.md's depth-2 hard stop should degrade gracefully outside a
  LangGraph-checkpointed run.
- `CapabilityRegistryMiddleware` (`agent-runtime-layer.md` §6, `middleware.py`) as a structural
  template: `wrap_model_call` filters the tool list, `awrap_tool_call` looks up a request
  against a registry and dispatches or falls through to `handler`. A ledger middleware needs
  the identical two-hook shape (filter what's visible / gate what executes), just keyed on
  provenance depth instead of role.
- The Pydantic validation patterns in `agent-runtime-models.md`/`agent-runtime-models-
  analysis.md` (`model_validator(mode="after")` for cross-field checks, `extra="forbid"` by
  default with one deliberate `extra="allow"` exception for runtime-mutated fields) — a solid,
  already-battle-tested template for defining the ledger's own node/config schema.
- The definitive `create_agent()` (not `create_deep_agent()`) verdict — settles a question the
  new project would otherwise have to re-derive.

### Good thinking material / adaptable
- `folder-structure-pressure-test.md`'s pressure-test methodology itself (10 concrete stress
  scenarios run against a proposed design, each scored HOLDS/BREAKS/PARTIALLY with a specific
  failure mode and a specific fix) — a strong template for stress-testing PLAN.md's own design
  (e.g., pressure-test "depth cap of one" and "reconcile every 5 calls" against concrete
  multi-hop scenarios the way this document did for folder layout).
- The proposed artifact header schema (`goal`, `task`, `spawn_id`, `session_id`, `parents`,
  `in_scope_constraints`) — not directly portable, but the shape (every unit has an explicit
  parent-link and explicit constraints) is a useful cross-check against the ledger's own
  node schema design.
- `investigation-requirements.md`'s "capability vs. structure" framing (§2: does this
  architecture add real capability, or just organization/traceability that a simpler approach
  would also give you?) — worth deliberately applying to the ledger design itself as a gut
  check, independent of its RAG-specific content.
- "Provenance IS the category" as a collapsing rule (`agent-architecture-
  comprehensive.md:244`) — a reusable epistemic principle (if a distinction can be carried as a
  tag/attribute rather than promoted to a structural type, collapse it) that's relevant when
  deciding whether "depth" needs to be a first-class node type versus a field on a single node
  schema.
- `architectural-decision-history.md`'s decision/timeline/open-issues format as a rough
  template for a future ADR-style log for the new project — useful shape, missing the
  assumption-tracking rigor PLAN.md already has, so adopt the shape and keep PLAN.md's
  discipline on top of it rather than reverting to this document's looser version.

### Dead, superseded, or domain-specific noise
- All BERTopic/topic-modeling/streaming-drift content (`bertopic-integration.md`,
  `postgres-topic-centroid-analysis.md`, `topic-to-concept-prior-reasoning.md`,
  `investigation-requirements.md`'s drift-management sections, `overhaul-and-thought-tree-
  map.md`'s pipeline architecture) — a different domain entirely, explicitly "mid-flight,
  paused" (overhaul-and-thought-tree-map.md §8) with zero shipped code.
- All Qdrant/Memgraph/graph-schema content (`qdrant-graphrag-analysis.md`,
  `graphrag-schema-falkordb-analysis.md`, `graph-schema-prior-work.md`) — RAG data-layer design,
  no bearing on tool-call gating.
- The full pydantic-ai/pydantic-graph RAG pipeline (`pydantic-ai-rag-pipeline-analysis.md`) —
  useful only for its negative conclusion (see substrate section); its actual pipeline content
  (tree builder, multi-pass prompts) is irrelevant to this project.
- Nearly all controller/CLI/Docker/DB/Flox infrastructure docs (`controller-model-
  definitions.md`, `controller-operations-layer.md`, `data-model-audit.md`, `db-alembic-
  infrastructure.md`, `models-db-layer.md`, `operations-analysis.md`, `manifest-serialization-
  chain.md`, `structural-inventory.md`, `project-structure-summary.md`, `config-model-map.md`,
  `field-inventory-models.md`, `flox-activate-exit-on-error.md`, `flox-manifest-summary.md`) —
  this describes a multi-container Docker/Flox agent-hosting platform with a manifest-push
  control plane. `architectural-decision-history.md` §7 records this layer as never fully
  working ("ARC-1: two incompatible agent runtimes... never reconciled"; "Manifest never
  written by controller... agent exits at startup"; "Agent runtime doesn't load tools —
  `loaded_tools = []` always"). None of it applies to a single-process LangChain app, and even
  within its own scope it was documented as broken, not just inapplicable.
- The 5-type multi-agent hierarchy in `agent-architecture-comprehensive.md` (orchestrator /
  system thinker / implementer / auditor / explorer, with skill-based variation and file-based
  handoff gates) — interesting prior thinking about read/write boundaries and "user is
  governor" but scoped to a different, heavier multi-agent orchestration system than v1's
  single-agent `bind_tools` gate. Worth a re-read only if the project later grows into
  multi-agent territory.

## Open threads & contradictions noticed

1. **The old repo already tried runtime tool gating, then explicitly reversed course.**
   `agent_runtime/middleware.py`'s `CapabilityRegistryMiddleware` (fully built, per `agent-
   runtime-layer.md`) implements exactly the `wrap_model_call`/`wrap_tool_call` runtime-gating
   pattern PLAN.md wants. But a later spec in the same repo's history
   (`docs/specs/radical-simplification-rebuild.md`, summarized in `architectural-decision-
   history.md:257–272, 349–351`) states as a Core Principle: *"There is no runtime gating... only
   gate is package registration (vesting)."* This is a direct, documented reversal — the old
   repo built runtime gating, then a later design phase rejected the concept in favor of
   gating only at config/registration time. The reasoning behind that reversal is not captured
   in this slice (it likely lives in `docs/specs/radical-simplification-rebuild.md` or
   `docs/learnings/radical-simplification/`, outside `docs/exploration/`). This is worth
   surfacing to the user directly: a past version of this same effort considered runtime
   gating and walked away from it, for reasons not visible from this slice alone.

2. **The gating middleware was possibly never exercised end-to-end.** The "ARC-1 two
   incompatible agent runtimes" blocker (`architectural-decision-history.md:234`) plus "Manifest
   never written by controller — agent exits at startup" (same table) mean it's unclear whether
   `CapabilityRegistryMiddleware`'s `wrap_tool_call` gating logic was ever actually invoked by a
   running agent in this codebase, versus written and never load-bearing. Treat the pattern as
   structurally sound (it matches upstream LangChain docs) but not empirically validated by this
   repo's own runtime history.

3. **API drift risk.** `middleware-tool-gating.md` (2026-05-16) and `deep-agents-viability.md`
   / `deep-agents-graph-internals.md` (same date) were fetched against docs.langchain.com as of
   four months before today (2026-09-16). PLAN.md's own discipline ("verified against the
   current... reference, not recalled") should be applied here too: re-verify `ToolCallRequest`,
   `wrap_tool_call`, and `AgentMiddleware` against whatever `langchain` version this new project
   actually installs before relying on the exact signatures quoted in this slice.

4. **No file in this slice ever uses PLAN.md's specific framing** (explicit/implicit nodes,
   depth-of-hop, "every action is a prediction not an understanding"). This is confirmed novel
   framing relative to everything the old repo produced — not an oversight on PLAN.md's part.

## Best pointers

- `agent_framework/docs/exploration/middleware-tool-gating.md` — read in full before writing
  any middleware code; §1–2 (wrap_tool_call mechanism), §4 (Limitations table), §5 (recommended
  `ConfigGatingMiddleware` skeleton + decision flowchart).
- `agent_framework/docs/exploration/agent-runtime-layer.md` §6 (`middleware.py` function map)
  together with `agent_framework/docs/exploration/agent-runtime-models.md` — the closest thing
  to a working sibling implementation of a gating middleware plus its config schema.
- `agent_framework/docs/exploration/deep-agents-viability.md` — settles `create_agent()` vs.
  `create_deep_agent()` definitively; skip re-deriving this.
- `agent_framework/docs/exploration/architectural-decision-history.md` §7 (Critical Unresolved
  Issues) and §10 (Evolution Patterns & Lessons Learned) — for the runtime-gating-abandoned
  thread and for a decision-log format template.
- `agent_framework/docs/exploration/folder-structure-pressure-test.md` §5 point 4 (proposed
  artifact header schema) and its overall pressure-test methodology (§2, 10 stress scenarios) —
  nearest analogue to a provenance-node schema, and a reusable stress-testing method for
  PLAN.md's own design.
