# 06 — MVP docs, specs, current working set, diagrams, taxonomy

## Scope covered

Everything under `agent_framework/docs/`: `MVP/` (orchestrator, shared, thinker_CLI, thinker_runtime — 30 files), `specs/` (36 files: three numbered spec sets plus standalone specs), `current/` (19 files: rules/scope/audits/handoffs), `diagrams/` (8 files), `taxonomy/` (39 files, skimmed per instructions). Read in full: both `rules.md` files, `scope.md`, all three sampled audit sections (01, 04, 06) plus `audit-summary.md`, `session-handoff.md`, `integration-test-plan.md`, `agent-entrypoint-strict-fixes.md`, `system-thinker-ingestion-findings.md` (current/), both `thinker_CLI/design-spec-mvp-path.md` and `thinker_runtime/agent-runtime-gap-analysis.md` in full, `orchestrator-summary.md`, `sequential-thinking-rules.md`, `usernotes.md`, `cross-domain-queries.md`, `phase12-audit.md`, `explorer-findings-langchain-and-verification.md`, `radical-simplification-rebuild.md`, `skills-loading.md`, all diagram files, `dynamic-agent-runtime/00-overview.md` + `IMPLEMENTER_PROMPT.md`, `model-unification/00-overview.md`, `runtime-unification/IMPLEMENTATION_HANDOFF.md`, `model-unification-schema-draft.md`. Headers/skims for the remaining spec/current files (`spec-type-fix-handoff.md`, `sections-05-06-07.md`, `agent-entrypoint.md`, `config-schema.md`) and taxonomy (grepped for provenance/lineage, read the hits in context).

I also read `agent_framework/agent-workspace/rules.md` (outside the nominal slice but directly requested by the task brief for comparison) — read-only, not edited.

## Map

- **`current/`** is a frozen snapshot of a session dated 2026-05-14 (the seven-section audit + its implementation) plus a later 2026-05-19 planning pass (`current/planning/*`) that was **superseded** by `MVP/orchestrator/*` — the two directories share file names (`findings.md`, `progress.md`, `task_plan.md`, `design-spec-mvp-path.md`) but differ in content; `MVP/` is the continuation (session 2, 2026-05-20+) after the project's directory convention changed (`docs/MVP/` became the mandated single source of truth per orchestrator rule O12). Treat `current/` as an archived earlier working set, not a competing design.
- **`specs/`** holds three parallel numbered spec series — `dynamic-agent-runtime/00-06` + `IMPLEMENTER_PROMPT.md`, `model-unification/00-07` + `IMPLEMENTER_PROMPT.md`/`IMPLEMENTATION_HANDOFF.md`, `runtime-unification/00-10` + the same pair — plus standalone one-off specs (`agent-entrypoint.md`, `config-schema.md`, `skills-loading.md`, `sections-05-06-07.md`, `model-unification-schema-draft.md`, `radical-simplification-rebuild.md`). The three series are sequential rewrites of the same system (dynamic runtime → DB unification → runtime unification → eventually superseded by `radical-simplification-rebuild.md`, the terminal document).
- **`MVP/`** is a two-domain-plus-coordination structure: `thinker_CLI/` (controller/Docker-SDK/CLI side), `thinker_runtime/` (in-container LangChain agent runtime side), `shared/` (the negotiated contract between them), `orchestrator/` (the human-facing governance layer — rules, session log, master handoff).
- **`diagrams/`** — all `.mmd`/`.md` mermaid diagrams share one theme block; `flowchart TD.mmd` is the unmodified mermaid.live starter template (confirmed noise, not project content).
- **`taxonomy/`** — a RAG knowledge-graph schema for indexing this same codebase's docs (Qdrant + Memgraph), independent of the controller/agent architecture. Confirmed out of scope for deep reading per brief; grepped for provenance/lineage (see dedicated section below).

## Rules, scope, and spec formats

### `current/rules.md` vs `agent-workspace/rules.md`

`docs/current/rules.md` (`agent_framework/docs/current/rules.md:1-19`) is a **short, frozen session-rules snippet** ("from MASTER_STATUS.md §0") — 10 numbered rules plus 4 environment rules (flox/uv/pyrefly). It is a point-in-time export, not a living document.

`agent-workspace/rules.md` (`agent_framework/agent-workspace/rules.md`) is the **evolved, full operating manual** for a later multi-agent-orchestrator iteration of this same project. It is far more mature: it has a "MANDATORY CHECKS" section ordered by lifecycle, a spawning protocol, a communication protocol per agent type, a numbered "Lessons Learned" log (17 entries, each tied to a specific past failure), and file conventions. Compared line-for-line, several `current/rules.md` items reappear verbatim or near-verbatim in `agent-workspace/rules.md` (e.g. "User is Governor" → "User is governor", "Context Economy" → "Context economy", the flox/uv/pyrefly block is reproduced exactly at `agent-workspace/rules.md:201-205`). This confirms `agent-workspace/rules.md` is the direct descendant of `current/rules.md`, not an unrelated document — the project kept accreting rules onto the same skeleton across sessions.

Reusable pattern for the new project: **"Lessons Learned" as a versioned, numbered, dated log tied to a specific incident** (`agent-workspace/rules.md:132-150`), not a vague style guide. Also directly relevant to the ledger's "no self-promotion" design: rule O11 in `orchestrator-summary.md` ("The Governor can be wrong... challenge user decisions with evidence") and the strict **agent role boundaries** ("Thinkers do NOT read source code... NEVER read briefs... NEVER write code") are a *role-based* gating scheme — an analogue one level up from PLAN.md's *provenance-based* gating scheme. Worth citing as a sibling design: this project gates by **who is allowed to touch what**, PLAN.md gates by **where a target came from**.

### `scope.md` — what it actually is

`docs/current/scope.md` (`agent_framework/docs/current/scope.md:1-150`) is **not** an analogue of PLAN.md's ledger. It is a conventional build-requirements/architecture spec — volume model, mount table, lifecycle CLI operations, a compose YAML example. It bounds *infrastructure* (which volumes, which mounts, which operations exist), not *what an agent may conclude or touch epistemically*. The one place it brushes against agent-action gating is a single line: "**Agents require human-in-the-loop validation to load any skill from the watched directory** — skills are visible for discovery but approval gates actual loading" (`scope.md:125`). That HITL-for-skill-loading line is the seed of a much larger effort (see `specs/skills-loading.md` and the Salvage section below) — and it was later **deleted entirely** in the project's own simplification pass (see "Open threads" below). So `scope.md` is a weaker structural analogue than the seven-angle audit or the cross-domain contract negotiation — it bounds infrastructure surface area, not inference.

### Spec format — yes, there is a consistent, reusable template

Two template families recur across nearly every substantial document in `specs/` and `current/`:

**1. The audit-section template** (seen in all of `audit-01` through `audit-07`, e.g. `current/audit-01-volumes.md:1-153`, `current/audit-04-agent-entrypoint.md`, `current/audit-06-validation.md`):
```
---
title / version / date_created / owner / tags (YAML frontmatter)
---
# Introduction
## 1. Purpose & Scope        (explicit "Out of scope" line)
## 2. Definitions            (term table)
## 3. Gap Analysis           (Current State / Target State / Gaps table with severity emoji + ID like G1-1)
## 4. Required Architectural Changes  (lettered subsections A, B, C...)
## 5. Interactions with Other Sections
## 6. Risks & Assumptions
## 7. Acceptance Criteria    (numbered AC-N.M, testable)
## 8. Unresolved Questions   (Q-N, only when present)
## 9. Related Specifications (links back to scope.md + sibling sections)
```
Every finding gets a stable ID (`G1-1`, `IV-001`, `AC-4.8`, `Q4-1`) that gets referenced by later documents (audits reference `Key Invariants IV-001..IV-006` from `audit-summary.md:57-62`; implementation summaries reference the `AC-*` IDs). **This ID discipline is the single most reusable artifact in the whole slice** — it lets a later document say "fixes G1-1" instead of re-describing the gap.

**2. The IMPLEMENTER_PROMPT template** (`specs/dynamic-agent-runtime/IMPLEMENTER_PROMPT.md`, `specs/runtime-unification/IMPLEMENTER_PROMPT.md`, `specs/model-unification/00-overview.md:122-247`):
```
## 1. What You're Building        (already-built vs you-are-building split)
## 2. Context Files (read in this order)   (tiered: Tier 1 must-read / Tier 2 selected sections / Tier 3 reference-only)
## 3. Skills to Load               (ordered, "order matters")
## 4. What You MUST NOT Do         (table: forbidden action | why)
## 5. Key Decisions from Prior Sessions
## 6. Environment Rules
## 7. Big Picture (ASCII diagram)
```
The "What You MUST NOT Do" table (`specs/dynamic-agent-runtime/IMPLEMENTER_PROMPT.md:64-77`) is directly quotable — e.g. "Expect HITL to gate registry tools | `wrap_tool_call` ... runs BEFORE HITL in the middleware stack. If the middleware short-circuits ... HITL never fires." That is exactly the kind of ordering trap the new project's ledger needs to document once its own middleware/hook order is decided.

**3. The session-handoff template** (`current/session-handoff.md`, referenced and reused as `orchestrator-summary.md`'s structure):
```
## What was accomplished this session   (table: section | file | status | tests)
## Key changes this session
## Context the next agent MUST read     (numbered, prioritized)
## Key architectural decisions already made (locked)
## Important files and their roles
## Open questions / known gaps
## How to run tests
## Recommended next steps
```
This is worth adopting verbatim for the new project's own session handoffs — it is the difference between a "diary" and a document a fresh agent can actually resume from.

**Was there a template file, or convention-by-repetition?** No single `TEMPLATE.md` was found; the structure is convention carried forward by imitation session over session (confirmed by the `agent-workspace/rules.md` skill reference to `create-specification` at `MVP/orchestrator/orchestrator-summary.md:44`, described as providing "consistent spec structure across all domains" — the actual skill file is not in this slice).

## The seven-angle audit method

`current/audit-summary.md` (`agent_framework/docs/current/audit-summary.md:1-63`) is the index for seven dependency-ordered audit documents (`audit-01-volumes.md` through `audit-07-observability.md`), each covering one architectural layer: volumes → compose → controller ops → agent entrypoint → skills → validation/safety (cross-cutting) → observability. The index states an explicit dependency graph (`audit-summary.md:27-45`) and a 5-phase execution sequence grouping sections that can run in parallel (Phase 2 = sections 3+4 in parallel) vs. sections that gate everything downstream (Phase 1 = sections 1+2, "nothing above works until the substrate is correct").

**Method, concretely** (verified by reading sections 1, 4, and 6 in full): each section is scoped to one subsystem with an explicit "Out of scope" boundary, inventories the *current* state from a prior structural-inventory document, states the *target* state from `scope.md`, and produces a gap table with severity markers. Critically, each section also has an "Interactions with Other Sections" table (`audit-01-volumes.md:123-131`, `audit-06-validation.md:166-174`) that cross-references gaps by ID across sections — e.g. Section 6 (validation) explicitly says its guardrails are "Enforced in Section 3" and "Gated by Section 4." This turns seven otherwise-independent documents into one coherent dependency graph without needing a monolithic single-pass audit.

**Did splitting into numbered angles stop skimming?** Evidence for yes: `audit-summary.md`'s "Key Invariants (Non-Negotiable)" (IV-001 through IV-006) shows synthesis actually happened across sections rather than each section operating in isolation — e.g. IV-004 ("Skills are RO-mounted... HITL validation gates agent loading") pulls from Section 4's and Section 5's content into one cross-cutting invariant. The later `session-handoff.md` (`current/session-handoff.md:5-17`) shows all seven sections were in fact separately implemented and separately tested (24/14/15/12 tests per section, 90 total) — meaning the split produced genuinely separable, independently verifiable units of work, not just cosmetic section headers. The method was reused later: `MVP/thinker_CLI/phase12-audit.md` uses the identical Blockers/Major/Minor/Observations severity tiering (not renumbered per-angle there, since it's a combined two-phase audit, but the same discipline of assigning stable IDs — M1-M4, m1-m7, O1-O6 — to every finding persisted).

**Caveat:** the "seven angles" were not independently commissioned/audited by different agents in parallel — the same audit style and voice runs through all seven files (same table conventions, same phrasing patterns like "🔴 Critical" / "🟡 Missing"), suggesting one continuous authoring pass organized by section rather than seven genuinely separate audit sub-agents catching different things. The gain was **structural decomposition forcing scope discipline** (each section has an explicit out-of-scope line), not independent-reviewer diversity.

## thinker_CLI vs thinker_runtime

This is **not** a CLI-subprocess-driven agent split (i.e. not analogous to `langchain-claude-cli`'s "delegate execution to a CLI subprocess" pattern). "thinker_CLI" names the **controller/Docker-orchestration side** — the `python src/cli.py` tool that manages Docker volumes, containers, and compose/SDK lifecycle (`MVP/thinker_CLI/design-spec-mvp-path.md`). "thinker_runtime" names the **in-container LangChain agent runtime side** — what boots inside each agent's own container once running: tool loading via `importlib`, `create_agent()` graph assembly, ACP exposure (`MVP/thinker_runtime/agent-runtime-gap-analysis.md`). The naming coincidence with `langchain-claude-cli` is superficial.

What **does** transfer, though it requires translation:

1. **The contract-file pattern.** The two domains never talk directly — they agree on a schema for `agent_spec.json` (formerly `manifest.json`, renamed independently and convergently by both thinkers — see `MVP/shared/cross-domain-queries.md:162-183` and `:268-284`) written by the controller, read by the runtime. `extra="forbid"` was adopted at this boundary specifically because a silent `extra="allow"` mismatch (`name` vs `agent_key`) caused a real production bug (`MVP/thinker_runtime/agent-runtime-gap-analysis.md:70-78`, confirmed fixed at `current/agent-entrypoint-strict-fixes.md:11-38`). **Direct lesson for the ledger:** any schema shared between the LangChain-space gate and whatever consumes ledger state should use `extra="forbid"` at that boundary from day one — this project learned that lesson the hard way, not proactively.
2. **The "define the shared schema before either side implements" discipline** (`cross-domain-queries.md:107-123`, Conflict C2, "chicken-egg on spec file schema" — resolution: "We both need the schema defined FIRST, before either of us writes code"). Directly applicable if the ledger's node schema and the `bind_tools` wrapper are ever split across two components.
3. **The middleware-ordering trap** cited above (`wrap_tool_call` short-circuiting before HITL ever fires) is a concrete precedent for a failure mode the ledger's own `PreToolUse`-hook-vs-`bind_tools`-wrapper split (PLAN.md items 7-8) should watch for: whichever gate runs first can silently make the second gate unreachable.
4. **Nothing reusable at the code level** — no LangChain agent code, tool-loading code, or ACP protocol detail in this slice is applicable to a `claude-agent-sdk`-backed CLI subprocess model; the runtime side is built entirely around `create_agent()`/`create_deep_agent()` and `importlib`-based dynamic tool loading from a Docker volume, which has no analogue in a CLI-subprocess architecture.

## Provenance/lineage in the data models

**Controller/runtime data models (`diagrams/current-data-model.mmd`, `proposed-data-model.md`, `data-model-comparison.md`, and the spec that supersedes both, `specs/radical-simplification-rebuild.md`): no provenance/lineage tracking.** These are relational (SQLModel) schemas for *infrastructure state* — Project, AgentService, AgentVariation, VolumeRef, ContainerRef, PermissionRef. The closest thing to provenance is `FileRef.source_volume` + `FileRef.approved`/`approved_at` in the *current* (pre-simplification) model (`diagrams/current-data-model.mmd:136-147`) — a record of which volume a file-access grant came from and whether/when a human approved it. This table, along with the entire `PermissionRef`/`AgentPermissionLink`/HITL-gating apparatus, was **explicitly deleted** in the project's own simplification pass (`specs/radical-simplification-rebuild.md:79`, `:502-504`; also shown as the red "DELETED" block in `diagrams/simplified-architecture-v1.md:99-107`, which lists "HITL gating logic" and "Symlink-based file gating" as things removed). So: this project *had* a rudimentary per-file provenance/approval field, and *removed* it as part of a "radical simplification" — see Open Threads below, this is the single most important finding for the new project to weigh.

**Taxonomy/RAG schemas: a weak, non-structural echo, not absent, but not PLAN.md-equivalent either.** Two things surfaced on grep for "provenance"/"lineage":
- The Qdrant payload schema treats "provenance" purely as a flat `tags` list value (e.g. `discovered` vs `experienced`), explicitly *not* a structured field or dimension (`taxonomy/schema-design/schema-field-decisions.md:73-79`, `taxonomy/schema-design/session-handoff.md:26-29`). It also defines two distinct confidence fields — `fit_confidence` (classifier's own confidence) vs `relevancy_confidence`/`certainty` ("source reliability... 1.0 = irrefutable user fact at a specific time," `taxonomy/schema-design/session-summary-v4.md:47-52`) — which is conceptually adjacent to explicit-vs-implicit (a fact's reliability is tracked separately from how confidently it was classified) but is a *scalar trust score*, not a *traceable link back to origin*.
- The Memgraph graph schema **does** define a real edge type for this: `(:Goal)-[:DERIVES_FROM]->(:Knowledge)` (`taxonomy/schema-design/cypher-example.md:103-111`, also `taxonomy/schema-design/memgraph-demo-v4.md:173,181,188`). This is a genuine one-hop lineage edge — a goal/objective node points back at the knowledge chunk it was derived from — structurally similar in *shape* (one hop, node points to its source) to PLAN.md's "every implicit node must link back to the explicit node(s) it was derived from." But it is scoped to indexing this codebase's own documents for retrieval, has no depth cap, no gating semantics, and no agent-action tie-in — it is a content-lineage graph for a RAG index, not an action/tool-call provenance ledger. Worth noting as the closest *structural* precedent found anywhere in this slice, even though the domain is unrelated.

**Conclusion for Q6: no, nothing in this slice implements anything resembling PLAN.md's explicit/implicit ledger, depth-cap, or multi-hop gate.** The closest analogues are (a) a deleted per-file approval/source field in the old permission model, and (b) a single-hop `DERIVES_FROM` graph edge in an unrelated RAG taxonomy schema.

## Why runtime gating was abandoned

**Confirmed: the reasoning lives in this slice, specifically in `specs/radical-simplification-rebuild.md`, and it is thin — a stated diagnosis for consolidating the *representation*, bundled with (but not separately argued for) the removal of runtime *enforcement*.** Below is everything found, with what is and is not directly cited.

### What was built, and when (the timeline is in-slice)

`radical-simplification-rebuild.md:10-21`'s own timeline table shows the gating middleware was not a paper design — it was implemented and audited before being torn out:

| Phase | Date | What Happened |
|---|---|---|
| Spec + Unification | May 16 | "Dynamic agent runtime spec (7 files), **implemented (4 modules)**, first audit (23 findings), pivotal fix (6 resolved in `1f1faba`)" |
| Capability Unification | May 18 | "PermissionRef table, AgentPermissionLink junction, PermissionUnion hierarchy, async config lock" |
| Audit + Diagrams | May 19 | "Full exploration (53 files, 247 items), architecture diagrams (7), test spike (29/29 passing)" — **this is the session that produced `radical-simplification-rebuild.md` itself, deciding to delete everything above** |

The `specs/dynamic-agent-runtime/` series (`00-overview.md` through `06-concurrency-errors.md`, `IMPLEMENTER_PROMPT.md`) is the spec for exactly the middleware the coordinator's other surveyor found reversed: `CapabilityRegistryMiddleware`, using LangChain's `wrap_model_call` (filters visible tools) and `wrap_tool_call` (dispatches/blocks execution) — see `specs/dynamic-agent-runtime/00-overview.md:166-174` and `specs/dynamic-agent-runtime/03-middleware.md:19,26,95-98`. This spec is detailed and implementation-ready (concurrency model, error tables, middleware stack position 7-of-11 documented at `00-overview.md:176-194`) — it is not a rough sketch. It was built, then a further `PermissionRef`/`AgentPermissionLink` unification was layered on top two days later, then the whole stack was deleted the day after that.

### The stated diagnosis: "Triple Representation Problem," not "gating doesn't work"

The document's own causal argument is in §1.1 (`radical-simplification-rebuild.md:60-70`): the concept "what capabilities an agent has" existed in **three parallel, slightly-different forms simultaneously** — SQLModel tables (`Tool, Skill, MCPConnection, FileRef, PermissionRef`), a Pydantic permission hierarchy (`ToolPermission, SkillPermission, MCPPermission, FilePermission`), and runtime defs (`ToolDef, SkillDef, MCPServerDef`). The stated conclusion: "**All three must be deleted** and replaced with a single canonical form: YAML config files + package registry." This is an argument about representational duplication and drift, not an argument that runtime gating itself was unsafe, slow, or unwanted.

Corroborating concrete defects cited elsewhere in the same doc (not about the middleware's *logic*, about its *data layer*):
- `radical-simplification-rebuild.md:33`: "**PermissionRef unification** (May 18): Collapsed separate tool/skill/MCP/file tables into a single table with JSON config. Correct concept, **wrong execution** — no Alembic migration, the old tables still exist, PermissionRef is invisible to Alembic."
- `radical-simplification-rebuild.md:46`: audit finding NF-2, "No Alembic migration for Permission tables" — resolved in the rebuild only by declaring it "**IRRELEVANT** — Permission tables are being deleted," i.e. the fix for a missing migration was to delete the table rather than write the migration.
- `radical-simplification-rebuild.md:53`: DEV-1, "Three `AgentConfig` representations" → "Rebuild resolves this — one canonical `AgentConfig`."

So the documented failure mode is **schema/representation drift and incomplete migrations**, not a runtime-behavior failure of the gate itself (no crash report, no latency complaint, no "the interrupt() never fired correctly" bug report tied to this decision anywhere in this slice).

### The explicit deletion, and the new principle

`radical-simplification-rebuild.md:88-90` (§1.2, "What Gets Deleted") lists, with terse one-line reasons:
```
src/agent_runtime/skills.py                                         | HITL gating removed
src/agent_runtime/capability_registry.py (permission derivation)    | Replaced by config composition engine
src/agent_runtime/middleware.py (before_agent, wrap_model_call gating) | Gating removed
```
`radical-simplification-rebuild.md:54` (§0.3, audit-findings-to-rebuild-impact table): "PM-2 | HITL for skills required by scope | **Removing HITL entirely** — no runtime gating." (PM-2 refers back to `current/scope.md:125`'s explicit requirement — "Agents require human-in-the-loop validation to load any skill" — so this line is a **direct, acknowledged reversal of a previously-written scope requirement**, not an update to an undecided question.)

The new governing principle, stated as a pull-quote (`radical-simplification-rebuild.md:134`): "**Agents are pure config. Packages are the unit of capability. The database tracks state, not permissions. There is no runtime gating.**" And as a "Non-Negotiable Constraint" (`radical-simplification-rebuild.md:365`): "**Package registration is the ONLY gate.** No runtime HITL. No symlink gating. No file permission checks at agent execution time. If a package is registered, any agent config can reference it."

### Was it a considered decision, or an incidental casualty?

**Both, in a specific sense worth flagging precisely.** It reads as *deliberate* — it gets its own line items, its own pull-quote, its own non-negotiable-constraint listing — not something quietly dropped in passing. But the document's *argument* is scoped to representational consolidation ("stop having three copies of the capability model"), and the removal of runtime *enforcement* is bundled into that conclusion without a separate justification for why deduplicating the representation requires deleting the enforcement mechanism entirely, rather than, say, keeping one enforcement point that reads from the now-single config representation. Those are logically separable moves (you can have one canonical config model *and* still gate on it at tool-call time), and the document does not argue for why it chose to drop enforcement rather than just consolidate its data source. In that sense it is a **considered decision bundled inside a broader simplification, with the enforcement-removal piece specifically under-argued relative to the representation-consolidation piece.**

**One process irregularity, worth flagging on its own:** the same document defines a formal "Design Decisions That Require User Gates" section (§4.2, `radical-simplification-rebuild.md:381-388`, items ENV-1/PKG-1/CONF-1/TOOL-1 — e.g. "Flox or uv for agent environments?") and ends with "*Specification complete. Proceed to user gates (§4.2) before Phase 0 execution.*" (`radical-simplification-rebuild.md:509`). The removal of runtime gating is **not** listed among those gated items — it is asserted directly in §4.1 as a "Non-Negotiable Constraint," i.e. the System Thinker author treated it as already-decided rather than something to route through the same approval process used for smaller questions like the env-strategy choice. No document anywhere else in this slice (`MVP/`, `current/`, `diagrams/`) shows the user discussing, approving, or contesting this specific reversal — every later MVP document (e.g. `MVP/thinker_runtime/agent-runtime-gap-analysis.md:301`, "Tools injected at construction time means no runtime gating") simply treats "no runtime gating" as settled background fact from this point forward. This is a **confirmed absence**, not a speculation: I searched all of `MVP/`, `current/`, and `specs/` for `HITL`, `PM-2`, `gating removed`, and `user gate` (see grep results) and found no document where the user is shown weighing in on this specific reversal — only the System Thinker's own unilateral framing.

### Was the gate ever exercised end-to-end before being dropped?

**Implemented and audited, but not evidenced as tested against a real running agent.** It was "implemented (4 modules)" and passed a "first audit (23 findings)" with a "pivotal fix (6 resolved)" on May 16 (`radical-simplification-rebuild.md:18`) — so it existed as working code and was reviewed, not just specced. But the one piece of empirical validation this slice documents by name — "test spike (29/29 passing)" (`radical-simplification-rebuild.md:21`, detailed in `diagrams/test-spike-plan.md`) — explicitly tests **config inheritance, package composition, and conflict detection** (`test-spike-plan.md:9-18`), not the `CapabilityRegistryMiddleware`/`wrap_tool_call` gating path. No test-spike hypothesis, no integration test, and no smoke test anywhere in this slice targets the gating middleware specifically. Separately, the gating design itself carried a known, self-documented ordering flaw that would have undermined its own guarantee: `specs/dynamic-agent-runtime/04-graph-assembly.md:129` and `specs/dynamic-agent-runtime/06-concurrency-errors.md:152` both flag that "`wrap_tool_call` runs BEFORE HITL... If you dispatch through the registry (returning a ToolMessage), HITL never fires for that tool" — meaning tools routed through the capability registry could bypass human approval entirely, silently. This is documented as an implementer caveat to work around, not cited anywhere as the reason for the later reversal — but it is a real, in-slice-documented flaw in the same subsystem that was deleted, and the new project should note it: it is essentially the same "which gate runs first wins, and the loser is silently skipped" failure mode PLAN.md's own hook-vs-`bind_tools` split needs to avoid (see the thinker_CLI/thinker_runtime section above).

### Outside the formal slice, but explicitly cited from within it — and decisive: `docs/audit-reports/`

`radical-simplification-rebuild.md`'s own author line ("based on 2 audit passes...") and `specs/model-unification/00-overview.md:234-235` both cite `docs/audit-reports/full-project-audit-2026-05-16.md` and `docs/audit-reports/deep-dive-two-runtimes-2026-05-16.md` by path — a directory not listed in my assigned paths (`MVP/`, `specs/`, `current/`, `diagrams/`, `taxonomy/`). Given this was the coordinator's specific follow-up priority, I checked it (read-only, `agent_framework/docs/audit-reports/`, 8 files). **This resolves the question, and the answer sharpens rather than confirms the "considered decision, thinly argued" read above — it makes the reversal look actively discontinuous with the project's own most recent self-assessment:**

`docs/audit-reports/full-project-audit-2026-05-18.md` — written **one day before** `radical-simplification-rebuild.md`, by "System Thinker agent (task_id: `audit-may18`)" — is a full second-pass audit of the same codebase. Its findings directly contradict "gating was a problem":

- **PM-2 (HITL for skills) is marked resolved and code-verified**, not merely claimed: `full-project-audit-2026-05-18.md:33,261` — "✅ Resolved | `before_agent()` hook with `interrupt()` in middleware" — and the working paper behind it is even more precise: `docs/audit-reports/findings_may18.md:25` — "PM-2 | HITL for skills missing from dynamic runtime | 🟠 | ✅ | ✅ | `middleware.py:154-236` — before_agent() with interrupt()" (the second ✅ column is literally labeled "Verified," meaning the auditor read the actual code, not just a claim).
- The audit's **Executive Summary** (`full-project-audit-2026-05-18.md:10-18`) reads: "The project has made significant progress... capability management is abstracted... **The project is converging on architectural coherence.** The runtime is unified, the data layer is normalized, and capability management is abstracted. The remaining open items (ACP transport, volume governance, Alembic cleanup) are well-scoped and actionable." Overall Pragmatic-Programmer score: **6.5/10**, trending up from the prior pass.
- The one real defect found in the capability/permission layer — **NF-2, "No Alembic migration for `PermissionRef`/`AgentPermissionLink` tables"** (`full-project-audit-2026-05-18.md:64,228`) — is given an explicit recommended fix in the same document's P0 action plan: "**Generate migration** for `PermissionRef` + `AgentPermissionLink`, update `env.py` imports, verify `alembic upgrade head` succeeds" (`full-project-audit-2026-05-18.md:228`). **The auditor's own prescription for the missing-migration bug was to write the migration, not delete the table.**
- Nowhere in this second-pass audit — across 10 resolved findings, 12 still-open findings, 7 new findings, a priority action plan, and a "Files Requiring Modification" table — is there any recommendation, suggestion, or hint to remove HITL, remove the capability registry, remove `wrap_tool_call`-based gating, or move to a package-registration-only model. The word "simplification" does not appear as a direction in this document; the direction throughout is "finish and clean up what's built."

**So the sequence, precisely dated:** May 16 — gating middleware speced (7 files) and implemented (4 modules), first audit finds 23 issues, 6 fixed same day including HITL. May 18 — second audit confirms HITL/gating code-verified working, scores the whole project 6.5/10 and "converging," recommends finishing the one remaining gap (the missing migration) via a one-line fix. May 19 — one day later, `radical-simplification-rebuild.md` deletes the entire capability/permission/gating layer, with the stated `PM-2` line reading "HITL for skills required by scope | **Removing HITL entirely** — no runtime gating" (`radical-simplification-rebuild.md:54`) — silently reversing a status its own predecessor document had marked ✅ Resolved and code-verified the day before, in favor of an argument (§1.1, "Triple Representation Problem") about a genuinely separate concern: too many parallel *data* representations, not a defect in the *gating behavior* itself. **This is the strongest evidence in either directory that the removal of runtime gating was not a response to the gate failing, misbehaving, or being judged not worth its cost by the project's own audit process — it was a same-day architectural preference asserted in a document that itself skipped the user-gate process it defines for smaller decisions**, one day after an independent audit pass had explicitly validated the thing it removed and recommended finishing it instead.

I did not find, in either my formal slice or `docs/audit-reports/`, any document showing the user requesting or endorsing this specific reversal, nor any performance/bug complaint about `wrap_tool_call`/`CapabilityRegistryMiddleware` behavior itself (the only self-documented flaw in the gating design is the HITL-ordering caveat noted above, which is a workaround note for implementers, not a stated failure). The other surveyor's `docs/exploration/architectural-decision-history.md` citation remains outside everything I have read; if a considered rationale exists beyond "we decided to consolidate representations and dropped enforcement along with it," it would have to be there, in `docs/context/` (the `docker-architecture.md`/`volumes.md` chat logs referenced at `progress_may18.md:22-23`), or in a verbal/unlogged decision — none of which I have access to or evidence of.

---

## Salvage rating

### Directly reusable for the provenance-ledger project

- **The audit-section template with stable finding IDs** (`current/audit-01-volumes.md` format) — adopt for any future gap analysis of the ledger's own gaps.
- **The session-handoff template** (`current/session-handoff.md`) — adopt verbatim for resumable session state.
- **The IMPLEMENTER_PROMPT "What You MUST NOT Do" table pattern** (`specs/dynamic-agent-runtime/IMPLEMENTER_PROMPT.md:64-77`) — directly useful once the ledger has an implementer-facing spec; the ordering-trap entry about HITL never firing is a concrete cautionary precedent for hook/wrapper ordering.
- **`extra="forbid"` at every contract boundary** — a hard-won lesson (`agent-entrypoint-strict-fixes.md`) directly applicable to the ledger node schema.
- **"Define the shared contract before either side implements it"** discipline from `cross-domain-queries.md` — applicable if ledger state and the `bind_tools` wrapper are ever built by separate passes/agents.

### Good thinking material / adaptable

- **`agent-workspace/rules.md`'s numbered, dated "Lessons Learned" log** and its strict agent-role boundary model (Thinkers/Implementers/Auditors/Explorers, each with a hard "NEVER" list) — not directly about provenance, but a mature, tested example of *role-based* gating that sits one level above what PLAN.md is designing; worth cross-referencing when PLAN.md's "Open" item 3 (built-in-tool provenance) gets designed, since this project already worked out a full agent-boundary enforcement scheme (`orchestrator-summary.md §0.4`).
- **`MVP/orchestrator/sequential-thinking-rules.md`** — "thoughts are atomic (max 2 sentences), branch at every fork, resolve branches fully before returning to main" — a lightweight discipline for forcing an agent to make its reasoning forks explicit rather than silently picking a path. Thematically close to PLAN.md's "every action is a prediction" diagnosis: this is a technique for catching the moment a prediction gets made.
- **The `radical-simplification-rebuild.md` "Where We Have Come From" timeline** (`specs/radical-simplification-rebuild.md:10-55`) — a good model for writing a decision-history section that survives rewrites; the pivotal-decisions table with a one-line "correct decision" / "wrong execution" verdict per entry is a reusable format for tracking a project's own design churn.
- **The "spike before rebuild" methodology** (`diagrams/test-spike-plan.md`) — hypothesis/test/pass-criteria table format, used to de-risk architecture before committing.

### Dead, superseded, or domain-specific noise

- **`diagrams/flowchart TD.mmd`** — confirmed literal mermaid.live boilerplate, zero content, not even project-related.
- **All `taxonomy/` content** — a RAG/GraphRAG indexing schema for this same codebase's own documentation; entirely domain-specific to that sub-project, no transferable architecture beyond the two provenance-adjacent items noted above.
- **`current/planning/*`** — superseded duplicates of `MVP/orchestrator/*` under the same filenames; keep the MVP versions, the current/planning versions are the earlier draft.
- **The bulk of `specs/model-unification/*` and `specs/runtime-unification/*`** — SQLModel/Alembic/Docker-volume/Flox implementation detail specific to the old Docker-controller architecture; superseded in turn by `radical-simplification-rebuild.md`, which is itself the terminal document (nothing in this slice postdates it).
- **`MVP/shared/usernotes.md`** — two one-line notes about a global Nix cache volume; pure implementation-detail noise.

## Open threads & contradictions noticed

**The single most important finding in this slice, flagged explicitly for the ledger design:** this older project *built* a fine-grained runtime permission/approval system almost identical in spirit to what PLAN.md is proposing — per-skill HITL gating via LangGraph `interrupt()` (`current/scope.md:125`, implemented per `current/session-handoff.md:28` "Agent-side HITL: `load_skill_with_hitl()` gates skill loading... Authorized skills trigger HITL interrupt... with graceful fallback"), plus a `FileRef` table tracking `approved`/`approved_at`/`source_volume` per file grant (`diagrams/current-data-model.mmd:136-147`), plus a `PermissionRef`/`AgentPermissionLink` unification layer. **All of it was subsequently torn out.** `specs/radical-simplification-rebuild.md` states the new governing principle in italics: "**Agents are pure config. Packages are the unit of capability. The database tracks state, not permissions. There is no runtime gating.**" (`radical-simplification-rebuild.md:134`), and lists "no HITL," "no symlink gating," and "no file permission checks at agent execution time" as non-negotiable constraints of the rebuild (`radical-simplification-rebuild.md:365`). The stated rationale threading through the audit findings and the rebuild spec is complexity cost outrunning value: the permission system had "no Alembic migration," was "invisible to Alembic," coexisted with dead legacy tables, and produced schema drift bugs (the `name`/`agent_key` mismatch) faster than it produced safety value.

This is a direct, first-party cautionary data point for the new project, not a hypothetical risk: **the same author, in the same codebase family, already tried fine-grained agent-action gating and abandoned it for a coarser "gate at registration time only, trust everything after" model** — explicitly because the fine-grained version accumulated inconsistency and dead code faster than it delivered value. PLAN.md's design differs in kind (provenance-of-target, not permission-of-capability) and is explicitly scoped much narrower (v1 = `bind_tools` calls only, item 9), which may sidestep the specific failure mode here (the old system tried to gate *capability loading*, broad and infrequent; PLAN.md gates *tool-call targets*, narrow and frequent — different cost/value shape). But the new project should have an explicit answer for *why this time is different*, given the precedent sits directly in its own project history. Recommend surfacing this in whatever synthesis document aggregates all seven survey slices.

**Secondary contradiction, lower stakes:** `current/rules.md` rule 1 ("No autonomous decisions — pause and ask user before acting") versus the later `agent-workspace/rules.md` rule O11 ("The Governor can be wrong... uncritical obedience is a failure mode") show the project's own philosophy evolving from strict deference toward the orchestrator being expected to push back — worth noting only because PLAN.md's "no exception for trace-shaped requests... asking is cheap" design (item 5) sits closer to the *earlier*, more deferential rule than the *later* one this same project arrived at through experience.

## Best pointers

- `agent_framework/docs/current/audit-01-volumes.md` (or any of `audit-02` through `audit-07`) — the cleanest example of the reusable audit-section template.
- `agent_framework/docs/current/session-handoff.md` — the cleanest example of the reusable handoff template.
- `agent_framework/docs/specs/dynamic-agent-runtime/IMPLEMENTER_PROMPT.md` — the cleanest example of the implementer-prompt template, including the "MUST NOT do" ordering-trap table.
- `agent_framework/docs/specs/radical-simplification-rebuild.md` — the terminal document of the old architecture; read this first if triaging the rest of `specs/`, since it supersedes most of what precedes it and states explicitly what was deleted and why.
- `agent_framework/docs/MVP/shared/cross-domain-queries.md` — the clearest example of two independent design threads negotiating a shared contract before implementation.
- `agent_framework/docs/MVP/orchestrator/orchestrator-summary.md` §0 — the fullest articulation of role-based agent gating in this codebase family; read alongside `agent_framework/agent-workspace/rules.md`.
- `agent_framework/docs/taxonomy/schema-design/cypher-example.md:103-111` — the one genuine lineage-edge (`DERIVES_FROM`) precedent found in the entire slice.
