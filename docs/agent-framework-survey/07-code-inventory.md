# 07 — Code inventory: src, pipeline, tests, test-spike

## Scope covered

All code under `agent_framework/src/`, `agent_framework/pipeline/`,
`agent_framework/tests/`, `agent_framework/test-spike/`, and
`agent_framework/debug_import.py`. Read-only survey; nothing under
`agent_framework/` was edited, moved, run, or deleted. Domain plumbing
(RAG/BERTopic/Qdrant/Alembic/Docker internals) was skimmed for shape only,
per instructions; budget went to agent-control code.

## Map

**`src/agent_runtime/`** (working, thin plumbing, no gating). A "Dynamic
Agent Runtime" for containerized agents whose tools/skills/MCP connections
are supposed to be toggled at runtime by an upstream service.
`graph_assembly.py:15-39` builds an agent with **LangChain's `create_agent`**
(the LangGraph-backed unified agent API) plus a `MemorySaver` checkpointer —
no tool-call interception anywhere in the assembly path. `tools.py` has three
loader functions (`load_graph_tools`, `load_langchain_tools`,
`load_package_tools`) that dynamically import Python modules/files and
collect callables; failures are logged and swallowed, never raised.
`flox.py` and `prompt.py` are best-effort environment/prompt resolution,
unrelated to gating. `agent_state.py` is a LangGraph state schema
(`messages`, `available_tools`, `available_skills` — no provenance field).
Tested only for plumbing edge cases (`tests/agent_runtime/*`).

**`src/agents/memory_manager/`** (working, self-contained, deterministic).
A LangGraph 3-node ingestion pipeline (`graph.py:344-367`:
`validate_classify -> build_payload -> embed_ingest`) that classifies
free text against a taxonomy, either from caller-supplied fields (validated
directly) or via one LLM call with **exactly one retry on JSON-parse failure
only** (`graph.py:161-189` — semantic/taxonomy validation failures are *not*
retried, they just become `{"error": ...}` and the graph still reaches END).
`edge_validator.py` is a separate, pure-stdlib validator for a different
concern: legal `(source_label, relation, target_label)` triples against a
taxonomy-defined adjacency matrix, with wildcard (`"*"`) target support and
a runtime-registration escape hatch (`register_edge`). `classifier.py` is
an explicitly-labeled **mock** (regex heuristics, not an LLM).

**`src/local_mcp/`** (half-built / abandoned experiments — see dedicated
section below). Three unrelated MCP-server sketches plus one LangChain MCP
client experiment. No production server here.

**`pipeline/memory/agents/`** (the most mature agent-control code in the
whole slice). Four *generations* of the same idea — an LLM given
add/modify/delete tools over a concept/thought graph, with a pure-function
validator standing between the tool call and the commit:
1. `agents.py` (403 lines) — earliest, validation inline inside tool closures.
2. `concept_extractor_agent.py` (210 lines) — mid refactor, now dead: only
   data shapes and one helper (`_check_rel_type`) remain; the functions its
   own smoke test imports (`create_nodes`, `connect_nodes`, `delete_nodes`,
   `delete_relationships`, `_is_relationship_payload`) do not exist in this
   file (see Open threads).
3. `network_agent.py` + `../networkx/network.py` — the finished version
   (see next section). `pipeline/memory/networkx/comparison.md` is the
   author's own before/after audit of this rewrite and documents that the
   *old* hand-rolled validator had an empty-body self-loop check, an
   undefined `_is_relationship_payload` helper referenced 13+ times, a
   missing colon (syntax error) in `create_relationships`, and several
   stub functions that reference undefined variables — i.e. the "old"
   generation never actually ran.
4. `thought_graph.py` (737 lines) — a parallel, independently-validated
   variant for a "thought" DAG with dependency/blocking semantics
   (`can_expand_thought`, `can_resolve_thought`, transitive-cycle detection
   in `add_dependencies`). This one is the most thoroughly tested file in
   the entire slice (see Tests section).

**`pipeline/memory/networkx/`** — see dedicated section below.

**`pipeline/memory/` (rest)** — domain plumbing: `mermaidpy.py`,
`opencode_extract.py` (session/turn/chunk extraction with real
turn→chunk **data lineage**, not agent-action provenance — see Provenance
section), `prompts.py`, `vector_store`/`vector_engine.py`. Skimmed only.

**`tests/`** — see dedicated section below.

**`test-spike/`** (self-contained, working per its own README). A spike
validating `uv` + Flox + YAML config inheritance + package composition —
i.e. it validates the `PackageComposition`/`ToolImplRef` config model that
`src/agent_runtime` consumes. Its README documents 8 explicit
disambiguation decisions made where the design doc it was validating was
ambiguous (module-name hyphens, `extends:` filename matching, one-level-deep
dict merge, list concatenation order, etc.) — good example of "spike first,
resolve ambiguity, write it down" discipline, but it is packaging/config
plumbing, not agent-control.

## Gates, validators, and interceptors

**Yes — the single most relevant mechanism found is a working
propose→validate→retry loop, in two independent implementations, both using
pydantic-ai's `ModelRetry`:**

- **`pipeline/memory/networkx/network.py`** (pure validator library, no
  LLM/agent import) exposes `validate_relationship` (`network.py:120-182`),
  `create_nodes` (`network.py:190-214`), `create_relationships`
  (`network.py:222-265`), `delete_nodes` (`network.py:273-295`),
  `delete_relationships` (`network.py:303-346`). Every one of these takes
  the current `networkx.DiGraph`, validates, and returns a `GraphResult`
  (`networkx/models.py:180-189`) that is `False`-y on rejection and carries
  a human-readable `message` plus, for cycles, the actual cycle path
  (`format_cycle_path`, `network.py:58-68`).
- **`pipeline/memory/agents/network_agent.py`** is the caller: each
  `@agent.tool` (`create_new_nodes` at `network_agent.py:95-125`,
  `create_new_relationships` at `:128-168`, `delete_new_nodes` at
  `:171-185`, `delete_new_relationships` at `:188-201`) calls the matching
  library function; **on `result.success is False` it raises
  `pydantic_ai.ModelRetry(message)`** (e.g. `network_agent.py:122-123`).
  pydantic-ai catches `ModelRetry`, feeds the message back to the model as
  the next turn, and the model must re-propose. The retry budget is capped
  at the `Agent(..., retries=3)` construction site
  (`pipeline/memory/agents/models.py:67,96`) — after 3 failed retries the
  run raises, it does not loop forever.
  - Errors are **de-tokenized for the LLM**: `_mermaidify`
    (`network_agent.py:74-83`) rewrites full UUIDs in the error message back
    to the short Mermaid tokens the model last saw, so a rejection reads
    against the diagram the model is holding in context.
  - Validation checks actually enforced before commit: unknown
    source/target id, self-loop, duplicate edge (undirected-pair
    comparison so reversed duplicates are caught too), DAG-cycle
    introduction (via `networkx.is_directed_acyclic_graph` +
    `find_cycle`), and a closed `rel_type` allow-list
    (`ALLOWED_REL_TYPES`, `network_agent.py:25-38`, cross-checked against
    the same closed `Literal` enum in `networkx/models.py:24-35`). Input
    shape is additionally locked by Pydantic `extra="forbid"` on
    `NewConcept`/`NewRelationship` (`networkx/models.py:72,144`) so a
    hallucinated field is a validation error, not silently dropped.
  - State is committed **only** via `_commit_result`
    (`network_agent.py:61-71`), called only after `result.success`. There
    is no code path that mutates `AgentState.current_graph` on failure.
- **`pipeline/memory/agents/thought_graph.py`** independently reimplements
  the identical propose→validate→`ModelRetry`→retry pattern for a second
  domain (thought dependency graph: `expand_thought`, `resolve_thoughts`,
  `add_dependencies`, each raising `ModelRetry` with a specific reason,
  e.g. `thought_graph.py:374,378,417,419,463,465,469,471,473`).
- **A parallel, non-pydantic-ai interceptor exists for LangChain
  specifically**: `src/local_mcp/client2.py:64-93` defines
  `DynamicToolMiddleware(AgentMiddleware)` using **LangChain's own
  middleware system** (`langchain.agents.middleware.AgentMiddleware`,
  `ToolCallRequest`), overriding `awrap_tool_call` (`:80-93`) to intercept
  every proposed tool call before it executes, look it up against a
  permission-filtered tool list, and substitute/reroute it
  (`request.override(tool=tool)`). This is exploratory (half the file is
  commented out, the permission source is an MCP round-trip on every call)
  but it is real, running-shaped code that intercepts *between* a
  LangChain agent's tool-call proposal and its execution — directly
  relevant prior art for where the new project's `bind_tools`-wrapping
  gate would live, since it demonstrates the same interception point
  (`langchain.agents.middleware`) the `langchain-middleware` skill covers.
- **What does *not* gate anything, despite looking like it should:**
  `src/local_mcp/server2.py`'s `PermissionsMiddleware.on_call_tool`
  (`server2.py:59-64`) calls `call_next(context)` and returns the result
  unconditionally — it never calls `check_tool_permission`/
  `get_tools_by_id` (defined at `:36-44` but never invoked from the
  middleware). `on_list_tools` (`:48-58`) computes a `permissions` list and
  even filters+prints matching tool names, but then returns the
  **unfiltered** `tools` list (`:58`, `return tools`) — the filter result is
  discarded. And `user__ask` (`:143-147`), whose docstring claims to "halt
  execution flow to capture runtime Human-In-The-Loop clarification or
  approval," actually returns immediately with a hardcoded string ending
  `"Override feedback received: 'Approved, execute operation.'"` — i.e. a
  fake-HITL stub that always self-approves. This is concrete, damning
  evidence for PLAN.md item 7's claim that an MCP server cannot itself
  block/gate a caller's tool calls: even where this codebase *tried* to
  build gating into an MCP layer, the gate silently no-ops.

## The networkx mutator + validation contract

Full contract, `pipeline/memory/networkx/network.py` +
`pipeline/memory/networkx/models.py`:

- **Value objects**: `Concept`/`Relationship` (internal, frozen, carry
  allocated ids) vs. `NewConcept`/`NewRelationship` (LLM-facing tool-call
  input shape, no id, `frozen=True, extra="forbid"`, closed `Literal` enums
  for `concept_type` (4 values) and `rel_type` (10 values) — the JSON
  schema itself makes an invalid category/relation type unrepresentable,
  before any custom validation runs).
- **Single return type**: `GraphResult` (`success`, `message`, `graph`
  [unchanged on failure, post-state on success], `modified_payloads`,
  `cycle`) with `__bool__` delegating to `success`, so callers can
  `if not result: raise ModelRetry(result.message)`.
- **Four mutator primitives**, all atomic (validate everything, then
  mutate once): `create_nodes` (content/type non-empty), 
  `create_relationships` (allow-list check first, then per-relationship
  `validate_relationship` against current graph *and* the rest of the
  pending batch — so two edges in the same batch can't create a cycle or
  duplicate together), `delete_nodes` (cascades edge removal, rejects
  empty/duplicate/unknown ids), `delete_relationships` (rejects a deletion
  that would **orphan** an endpoint — every node must keep at least one
  edge after the batch).
- **DAG invariant**: enforced by building a copy of the graph with the
  candidate edge(s) added and calling
  `networkx.is_directed_acyclic_graph`; on failure, `nx.find_cycle` is used
  to report the actual offending path (`format_cycle_path`), not just
  "rejected."
- **Token indirection**: `build_token_map`/`nx_to_mermaid` let the agent
  address nodes by an 8-char Mermaid-safe short token instead of a full
  UUID; the *tool wrapper* (not the library) resolves short tokens back to
  full ids before calling the validator, so the validator itself never
  sees ambiguity.
- **What it explicitly does not do**: no persistence (caller owns
  Qdrant/DB writes), no LLM calls, no agent state — `network.py`'s own
  module docstring (`network.py:1-13`) states it is "state-agnostic."

This is a real, working, arguably production-quality instance of "an agent
proposes a change; code validates it before it lands; on rejection the
agent is told exactly why and must re-propose" — the same shape of problem
the provenance-ledger project is trying to solve for the *different* axis
of provenance-of-target rather than graph-well-formedness.

## Agent frameworks actually used

- **pydantic-ai** (`Agent`, `RunContext`, `ModelRetry`, `@agent.tool`,
  `@agent.system_prompt`) — the dominant framework across
  `pipeline/memory/agents/*` and used for every mutator/validator example
  above. Models are OpenAI-compatible endpoints (opencode's
  `deepseek-v4-flash` via `OpenAIChatModel`+`OpenAIProvider`) or local
  Ollama (`OllamaModel`+`OllamaProvider`), selected in
  `pipeline/memory/agents/models.py:53-97`. `retries=3` is set at the
  `Agent(...)` call site, capping the `ModelRetry` bounce loop.
- **LangChain + LangGraph** — `src/agent_runtime/graph_assembly.py` uses
  `langchain.agents.create_agent` (LangGraph-backed) with a `MemorySaver`
  checkpointer; `src/agents/memory_manager/graph.py` uses raw
  `langgraph.graph.StateGraph`/`START`/`END` with `litellm.completion`
  calls (no LangChain model wrapper at all — went straight to LiteLLM);
  `src/local_mcp/client2.py` uses `langchain.agents.create_agent` +
  `langchain.agents.middleware.AgentMiddleware` + `ChatOllama` +
  `langchain_mcp_adapters.MultiServerMCPClient`.
- **litellm** — used directly (not through LangChain) in
  `src/agents/memory_manager/graph.py` and `pipeline/agents.py`'s default
  model selection, for straight `completion()` calls with
  `response_format={"type": "json_object"}`.
- **FastMCP** — the three `src/local_mcp/*.py` server sketches.
- **No deep-agents, no raw `claude_agent_sdk`/`claude-agent-sdk` usage
  anywhere in this slice** (`grep` for both turned up nothing under
  `src/`, `pipeline/`, `tests/`, `test-spike/` — only one unrelated hit in
  `src/main/main.py`, confirmed to be a different `main.py` string, not an
  import).

**Reusability against LangChain's `bind_tools`:** the pydantic-ai
`ModelRetry` mechanism is conceptually reusable (propose → deterministic
validator → structured rejection message → forced re-propose) but not
directly portable — pydantic-ai's tool decorator intercepts *inside* the
agent loop, whereas the new project's plan is to gate the `tool_calls`
list `ChatClaudeCli` *returns* to caller code, i.e. one level further out.
The closer precedent is `client2.py`'s `AgentMiddleware.awrap_tool_call`,
since it operates on LangChain's own `ToolCallRequest` at exactly the
external interception point v1 needs — but it's throwaway/experimental
code, not something to import.

## What the tests actually cover

- **Agent-behaviour tests (real, deterministic, no LLM/service needed)**:
  `tests/memory/test_thought_graph.py` (660 lines, 53 `test_*` functions)
  is by far the most substantial test file in the slice. It exhaustively
  covers the validator contract from `thought_graph.py`: empty-batch
  rejection, duplicate-id rejection, unknown-id rejection, self-dependency
  rejection, direct- and **transitive**-cycle rejection
  (`test_add_dependencies_transitive_cycle_rejected`,
  `:505-520`), state-machine legality (`can_expand`/`can_resolve` against
  `open`/`blocked`/`resolved` states), idempotency of resolve/add-deps on
  already-settled state, Mermaid rendering, and even
  `test_build_thought_graph_agent_registers_four_tools` (verifies the
  pydantic-ai agent actually wires up all 4 tools). This file is the
  strongest evidence in the whole codebase that the validate-before-commit
  pattern was taken seriously and works.
  `pipeline/memory/test_primitives.py` is a **standalone, non-pytest**
  smoke test for the *old* `concept_extractor_agent.py` primitives — see
  Open threads, it's broken (imports functions that no longer exist).
- **Plumbing tests**: `tests/agent_runtime/test_tools.py`,
  `test_flox.py`, `test_prompt.py`, `test_skills.py` — unit tests for tool
  loading, Flox activation, prompt resolution, all mocked/isolated, no
  gating logic to test because `agent_runtime` has none.
  `tests/memory/test_04_agents.py`, `test_05_ingest.py`, `test_06_retrieval.py`
  etc. exercise the memory-manager pipeline nodes with mocked
  LLM/Qdrant/DB layers. `tests/test_mcp_server.py` and
  `tests/memory/test_07_mcp_server.py` test **input-shape validation**
  (`_validate_mcp_params` rejecting bad project names/agent keys/paths;
  `query_memory` rejecting a non-UUID `session_id` or empty query) for two
  *different* MCP servers than the ones in `src/local_mcp/` — neither
  tests any permission/gating behaviour, because (per the section above)
  none of the `src/local_mcp/` gating code is wired up enough to test.
  `tests/memory/probe_*.py` (adversarial/round2-5) look like manual
  exploratory probing scripts rather than pytest suites — not reviewed
  line-by-line given budget.
- **`test-spike/tests/`** (`test_composition.py`, `test_env.py`,
  `test_inheritance.py`, `test_packages.py`) test the YAML
  inheritance/composition spike itself — config plumbing, not agent
  behaviour.
- Overall: **no test anywhere in this slice exercises a
  provenance/depth/explicit-implicit concept.** The closest thing —
  graph-mutation legality — is thoroughly tested; action-provenance is not
  a concept that existed in this codebase's test suite.

## Provenance/lineage in the models

**No agent-action provenance/depth field exists anywhere in this slice.**
Specifically:
- No graph node/edge model (`Concept`, `Relationship`, `Thought`,
  `ConceptPayload`, `QdrantPayload`, etc.) carries a field recording
  *why* an agent proposed it, whether its source was user-stated vs.
  agent-discovered, or any depth/hop count.
- What *does* exist, and is worth distinguishing from what PLAN.md wants:
  - **Data lineage** (chunk-to-source tracing, not action-provenance):
    `pipeline/memory/opencode_extract.py`'s `ChunkProcessingRecord`
    (`:109-124`) explicitly carries `turn_index`/`chunk_index` back-links
    "so downstream consumers can map any chunk back to its source turn
    without rescanning" (`opencode_extract.py:422-423`); similarly
    `source_ref` fields in `src/local_mcp/qdrant_schema.py:50` and
    `src/vector_rag/chunk_graph.py:81,338`. This is standard RAG
    source-attribution, unrelated to gating tool calls.
  - **A "sent/seen" ledger for LLM context**, closest analog in spirit:
    `pipeline/memory/agents/chunk_explorer_agent.py`'s `ChunkExplorerDeps`
    (`:58-105`) tracks `sent_chunk_ids`, `sent_turn_ids`,
    `completed_turn_ids`, and a chronological `sent_log` — i.e. "what has
    this agent already been shown, and what has it marked resolved,"
    which excludes completed material from future search results
    (`chunk_explorer_agent.py:435`, `exclude_turns=deps.completed_turn_ids`).
    This is the same *shape* of bookkeeping the ledger's "reconcile" /
    "completion" idea needs (a session-scoped record of open vs. closed
    items), but it tracks exposure/completion, not provenance-depth.
  - **The term "explicit"/"implicit" is already used in this codebase**,
    but for a different axis: the concept-extraction prompts
    (`pipeline/memory/prompts.py:9-14,79,162,180`, duplicated in
    `pipeline/memory/agents/relation_concept_agent.py:10,102`) instruct the
    LLM to distinguish "explicit concepts" (user directly mentioned) from
    "implicit concepts" (an overarching category the LLM synthesizes from
    several mentioned concepts) when building the concept forest. This is
    the same author, in the same period, already reaching for
    explicit/implicit as a category for LLM output — but applied to *what
    a concept extraction produces*, not to *whether a tool-call target is
    gated*. Worth knowing as precedent/vocabulary reuse, not as
    implementation to reuse.

## Salvage rating

### Directly reusable for the provenance-ledger project
- **The propose→validate→`ModelRetry`→retry pattern**
  (`pipeline/memory/networkx/network.py` +
  `pipeline/memory/agents/network_agent.py`) is the cleanest worked example
  in this codebase of "reject a proposed agent action with a specific,
  addressable reason and force a bounded retry." Even though it validates
  graph well-formedness rather than action-provenance, the *mechanics* —
  pure-function validator returning a structured result, tool wrapper
  translating failure into a retryable message, a capped retry budget —
  are a directly applicable template for a "depth-2 rejection" message the
  new project would send back to the model (if it chooses to let the model
  retry rather than only asking the user).
- **`src/local_mcp/client2.py`'s `AgentMiddleware`/`awrap_tool_call`
  pattern** (`:64-93`) is the one piece of code in this slice that
  intercepts at the same layer the new project's plan targets — a
  LangChain agent's proposed tool call, before execution. Worth reading as
  a starting sketch for where a `bind_tools` gate could hook in, even
  though the code itself should not be copied as-is (it's incomplete and
  the permission source is a live MCP round-trip per call).
- **The MCP-gating anti-pattern in `src/local_mcp/server2.py`** is
  reusable as a cautionary/evidentiary artifact for PLAN.md item 7: real,
  concrete proof (not hypothetical) that an MCP middleware's `on_call_tool`
  hook can look like a gate, print like a gate, and still not gate
  anything — directly supports item 7's claim and is worth citing.

### Good thinking material / adaptable
- `thought_graph.py`'s state machine (`open`/`blocked`/`resolved`,
  dependency-gated `can_expand`/`can_resolve`, transitive-cycle detection)
  is a well-tested, self-contained example of enforcing a *process*
  invariant (you can't resolve something whose dependency isn't resolved)
  — structurally similar to enforcing "you can't act at depth 2 without
  reconciling," even though the domain differs.
- `pipeline/memory/networkx/comparison.md` itself is worth keeping as a
  model for how to document a validator rewrite: it names exactly which
  old checks were broken/missing and why the new ones are correct — good
  practice to emulate when this project's own gate logic evolves.
- The explicit/implicit concept-extraction prompts
  (`pipeline/memory/prompts.py`) are a reminder that this vocabulary has
  prior, different use in the author's own work — worth a one-line
  disambiguation note in the new project so "explicit/implicit" isn't
  confused across the two efforts if either is ever referenced together.

### Dead, superseded, or domain-specific noise
- `pipeline/memory/agents/concept_extractor_agent.py` — superseded by
  `network_agent.py`; contains dead code and a stale companion smoke test
  that imports functions no longer present.
- `pipeline/memory/agents/agents.py` — earliest generation, validation
  inline in tool closures; superseded by the networkx-based rewrite.
- `src/local_mcp/mcp-server.py`, `server2.py`, `take2.py`, `client2.py` —
  all four are exploratory/half-finished (commented-out mounts, a
  Pydantic-schema sketch unrelated to the servers around it, a permission
  check defined but never called, a middleware class file with syntax
  debris — `server2.py:82` has a stray `sddsd` token inside a
  triple-commented block). None is a working MCP server as shipped.
- `src/agent_runtime/*`, `src/agents/memory_manager/*` (minus
  `edge_validator.py`), `test-spike/*` — working but purely
  plumbing/domain code (tool loading, taxonomy classification, Qdrant
  ingestion, YAML config inheritance); no gating relevance.
- RAG/BERTopic/Qdrant/Alembic/Docker-adjacent code
  (`src/vector_rag/`, `src/db/`, `src/alembic/`, `src/models/docker/`,
  `pipeline/vector_store/`) — skimmed only per instructions, appears to be
  standard domain plumbing with no agent-control surface.

## Open threads & contradictions noticed

- `pipeline/memory/test_primitives.py` imports `connect_nodes`,
  `create_nodes`, `delete_nodes`, `delete_relationships`,
  `_is_relationship_payload` from
  `pipeline.memory.agents.concept_extractor_agent` — none of these names
  exist in that file today (confirmed via `grep -n "^def "` — only
  `_make_concept_payload`, `_make_rel_payload`, `_check_rel_type` remain).
  This test would fail on import if run; it's a fossil from before the
  networkx-based refactor moved/removed those functions and was never
  updated or deleted.
- `pipeline/memory/networkx/comparison.md` documents that the *predecessor*
  file it replaced had multiple non-functional code paths (empty-body
  validator, undefined-variable references, a missing colon). That old
  file does not appear to survive in the current tree under its original
  name/location — the comparison doc is the only remaining record of it,
  which itself is useful context (it tells you *not* to resurrect anything
  matching that description if it turns up under another name).
- `src/local_mcp/` contains three independent, non-integrating attempts at
  an MCP proxy/gateway (`mcp-server.py`, `server2.py`, and the schema-only
  `take2.py`) plus one LangChain-side client experiment (`client2.py`)
  that talks to a gateway on `localhost:8001` — none reference each other
  directly and it's not obvious which (if any) was ever run together with
  which. Treat as three sketches, not a pipeline.
- No `pyproject.toml`/lockfile issues were checked (out of scope — reading
  only), but the presence of commented-out imports and debug prints
  (`server2.py:51-52`, `print(type(tools))`) throughout `local_mcp/`
  suggests this code was being interactively iterated in a REPL-like loop
  rather than run as a service.

## Best pointers

- Validator/gate mechanism to study first:
  `pipeline/memory/networkx/network.py` (whole file, 347 lines) +
  `pipeline/memory/agents/network_agent.py:95-201` (the four `@agent.tool`
  wrappers) + `pipeline/memory/networkx/comparison.md` (why it looks the
  way it does).
- Best-tested proof the pattern works:
  `tests/memory/test_thought_graph.py` (all 53 tests, esp. cycle/duplicate/
  orphan rejection cases from `:280` onward).
- Closest LangChain-side interception precedent:
  `src/local_mcp/client2.py:64-93` (`DynamicToolMiddleware`).
- Concrete evidence for PLAN.md item 7 (MCP can't gate built-in/host tool
  calls, and here it didn't even gate its own):
  `src/local_mcp/server2.py:47-64` (`PermissionsMiddleware`, filter computed
  but discarded) and `:143-147` (`user__ask`, fake self-approving HITL stub).
- Data-lineage precedent (not action-provenance, but same instinct — always
  carry a back-link to origin): `pipeline/memory/opencode_extract.py:109-124,
  404-429` (`ChunkProcessingRecord`).
