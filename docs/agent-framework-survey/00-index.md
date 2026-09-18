# Survey of `agent_framework/` — index

Captured 2026-09-16. Nine agents, read-only, across ~1,300 files / 116 commits
(2026-05-12 → 2026-07-03). Purpose: find what in the old repo is worth carrying into the
explicit/implicit provenance-ledger project described in `PLAN.md`.

The old repo was a topic-modelling / graph-RAG system (BERTopic, Qdrant, Memgraph, Docker,
Flox) built by a hand-rolled multi-agent protocol. **The domain content is not relevant to the
new project. The process and control material is.** Weight accordingly.

## The documents

| # | Document | Covers |
|---|---|---|
| 01 | `01-root-roles-and-config.md` | repo root, three agent persona prompts, config v1→v3, Docker |
| 02 | `02-agent-workspace-protocol.md` | the multi-agent operating protocol: rules, registry, entry/handoff/learning triad |
| 03 | `03-build-threads.md` | memory-build 8-spec decomposition, build stages, adversarial audits |
| 04 | `04-exploration-docs.md` | `middleware-tool-gating.md`, agent substrate conclusions |
| 05 | `05-learnings-audits-briefs.md` | the 28 `learnings/` files, audit loop, honest negative results |
| 06 | `06-mvp-specs-current.md` | MVP split, spec templates, **why runtime gating was abandoned** |
| 07 | `07-code-inventory.md` | src/pipeline/tests — the working validator, the no-op gates |
| 08 | `08-transcripts-thought-tree-research.md` | transcripts, correction moments, **the S11 provenance-edge design** |
| 09 | `09-installed-skills.md` | the 36 installed skills, `planning-with-files`, reinstall shortlist |

## Tier 1 — directly reusable

1. **The `learnings/` template**, used across all 28 files: *What I Was Asked / Key Decisions /
   What I Assumed / What I Was Uncertain About / What I'd Do Differently*. This is the ledger
   written by hand, as a retrospective. The ledger's contribution is moving it to write-time.
2. **`decisions.md`'s Source column** (`agent-workspace/memory-build/decisions.md`) — `# | Decision
   | Source`, where Source is a literal user quote or a tagged inference (`inferred from X`),
   split into Locked vs Open. Plus `session-log.md`'s "What I did / What I did NOT do" blocks.
3. **The propose→validate→retry loop** in `pipeline/memory/networkx/network.py` +
   `agents/network_agent.py`: pure validator, structured rejection, `ModelRetry` capped at 3,
   errors de-tokenized back into IDs the model saw, **state committed only on success**.
   Best-tested code in the repo (`tests/memory/test_thought_graph.py`, 53 tests).
4. **`wrap_tool_call` as the interception seam** — `docs/exploration/middleware-tool-gating.md`,
   with a working `AgentMiddleware` sketch at `src/local_mcp/client2.py:64-93`.
5. **`planning-with-files`** (`.agents/skills/`) — file-based session state + hook wiring +
   `check-complete.sh`. The nearest working substrate for the ledger's durable state.
6. **Stable-ID discipline** in specs/audits (`G1-1`, `AC-4.8`, `NF-5`) so later docs reference
   findings without re-describing them. Plus separate findings/resolutions docs where the
   resolutions doc presents options and never decides: *"Awaiting user review and gate decisions."*
7. **The 4-angle independent audit** — separate fresh spawns, none deferring to another's verdict.
   Returned FAIL 4/4 on stage-02, each grounded in reproduced bugs. And the two-pass variant
   (plumbing pass, then "adopt a USER's perspective" pass) which found 12 findings the first missed.
8. `bertopic-pipeline-auditor/entry.md`'s prime directive, near-liftable:
   *"You are an investigator, not a confirmer... A 'looks plausible' is not a stopping point."*
9. **`data/packages/base-commons/.../calculator.py`** — working sandboxed LangChain `@tool`,
   usable immediately as a `bind_tools` gating fixture.

## Tier 2 — thinking material

- The three persona prompts' skeleton: forced phases, a required "what isn't" section, explicit
  boundaries, calibration triggers. `architect.md:51`: *"if you find yourself unable to write the
  'what isn't' section, you do not yet understand the problem."*
- `context/agent-variations.md`'s read/write boundary table — provenance control by restricting
  what an agent may *read*, orthogonal to gating what it does.
- `thought_tree/`'s tagging notation (`VERIFY` / `!!` / `?` / `LEAF` / `CROSS-LINK`, always cite the
  confirming line).
- DAG/edge vocabulary in `SESSION_SUMMARY.md:158-176` (source=parent, target=child, forest not
  tree, multiple parents, hard no-cycles) — usable for the ledger's node/edge model.
- `spec-process-cli-rework.md:246` — flat human-readable file over a DB row for session state,
  with stated rationale. A precedent for `PLAN.md` Open item 3.

## Tier 3 — disposable

`docs/research/rag-algorithms/` (597 files, ~126 MB of OpenAlex dumps and paper PDFs), all
BERTopic/Qdrant/Memgraph/Flox/Docker infrastructure docs (the repo's own audits record much of it
as broken, not merely inapplicable), `debug_import.py`, `save.txt` / `renderer=neato` /
`my_graph.dot` / `er.gv` (four formats of one Graphviz tutorial example), `thing.json`,
stray root images, `concept_extractor_agent.py` (dead; its own smoke test imports functions that
no longer exist), `src/local_mcp/*` (three non-integrating sketches, no working server).

## What this survey found that `PLAN.md` must answer

### 1. You built this gate before, and it was deleted the day after it was verified working

- **May 16** — `CapabilityRegistryMiddleware` speced across 7 files, implemented as 4 real modules.
- **May 18** — an independent audit **code-verifies HITL as working**: `findings_may18.md:25`,
  *"PM-2 ... ✅ ... ✅ | `middleware.py:154-236` — before_agent() with interrupt()"*. The audit
  calls the project *"converging on architectural coherence"*, and its prescribed fix for the one
  real defect in that layer is *"generate the migration"* — not remove anything.
- **May 19** — `specs/radical-simplification-rebuild.md` deletes the entire capability/permission/
  gating layer. New Core Principle (`:134`): *"There is no runtime gating."*

The stated argument (§1.1, "Triple Representation Problem") is that capability data existed in
three drifting representations. That is a **data-modelling** argument. Deleting runtime
*enforcement* was bundled into it **without separate justification** for why consolidating three
representations required removing the gate rather than pointing one gate at the surviving one.

It was a considered decision — own line items, a "Non-Negotiable Constraint" — but it was **not
routed through the user-gate process the same document defines for smaller decisions** (§4.2 gates
Flox-vs-uv and package-registry storage; "remove all runtime gating" is asserted in §4.1 instead).
No document found shows the user discussing or approving this specific reversal. Every later doc
treats it as settled fact.

`learnings/radical-simplification/2026-05-19-full-session.md:20` records: *"the user explicitly
rejected HITL skill approval, symlink-based file gating, and permission derivation. The ONLY gate
is package registration (vesting)."* Those three named rejections are compatible with the user
never having approved deletion of the middleware itself — the two are not the same decision.

**Unresolved and for the user alone:** did you reject *runtime gating*, or did you reject *three
specific permission mechanisms*, with the middleware's deletion inferred from that and then
propagated as settled? This survey cannot tell. It is the same failure shape as the
`USER CONFIRMED` incident below, one level up.

### 2. Gates that are present and silently never fire — twice

- `src/local_mcp/server2.py:143-147`: `user__ask`, whose docstring claims to *"halt execution... for
  Human-In-The-Loop approval"*, returns immediately with a hardcoded
  `"Override feedback received: 'Approved, execute operation.'"` A self-approving HITL stub.
  Its `PermissionsMiddleware.on_call_tool` (`:59-64`) calls `call_next` unconditionally; the
  permission checks at `:36-44` are defined and never invoked; `on_list_tools` computes a filtered
  list and returns the unfiltered one.
- `specs/dynamic-agent-runtime/06-concurrency-errors.md:152`: *"`wrap_tool_call` runs BEFORE
  HITL... If you dispatch through the registry, HITL never fires for that tool."* Silent
  bypass-by-ordering, in the exact hook the new project plans to use.

**The risk to design against is not a gate that blocks wrongly. It is a gate that looks present
and always says yes.** Whatever v1 builds needs a test that the gate actually fired.

### 3. The ledger's direct ancestor already exists, unbuilt

`ses-test.md:8900-9620` — a design for three **epistemic provenance edges**: `INFORMED`
(Decision→Knowledge, with `confidence`, `extraction_method` = LLM-extracted vs. explicit,
`timestamp`), `SUPERSEDES`, `CONTRADICTS`. It explicitly worried about multi-hop chains and
cardinality blow-up.

Its motivating case (`:9141`) is the `USER CONFIRMED` incident: *"the audit finding where we
corrected 'USER CONFIRMED' because the S10 handoff didn't actually confirm — that's a case where a
conclusion... was based on a piece of knowledge... that turned out not to exist."*
`PLAN.md` reads as a deliberate simplification of this design: a one-hop cap and user confirmation
in place of multi-hop chains and confidence scoring.

### 4. A prior estimate bearing on Open item 2

`ses-test.md:9167`: *"Provenance requires the LLM to identify causal/counterfactual structure, not
just co-occurrence... Both are research-grade NLU tasks. We should expect ~70-85% accuracy
initially and design for human-in-the-loop correction."* Named failure mode at `:9052`:
*"Misattribute provenance (e.g., 'the decision was based on this' when actually it was based on
something else)."*

That is prior reasoning against the model-self-report option in Open item 2, and it argues any
self-report needs correction on top.

### 5. Evidence against item 5's "asking is cheap"

`task_plan_may18.md:105` records **5 user gates that were never answered**. Finding `NF-5` records
a required user gate *implicitly resolved by an implementer commit* without the user answering —
in a repo whose stated first rule was "no autonomous decisions". Asking is cheap for the asker;
unanswered questions accumulate and then get silently resolved by whoever is still moving.
"What happens when the depth-2 gate fires and nobody answers" is a case to design for.

### 6. No precedent for the 5-call cadence, and one data point against

Nothing in the old repo ever counted tool calls; every reconciliation was stage- or session-grained.
The closest comparison is `planning-with-files`, whose `PreToolUse` hook re-injects the plan before
**every** matched call — denser than every-5. Its `check-complete.sh` "always exits 0" and only
reports; `PLAN.md` item 6 is written as a completion condition, not a report.

### 7. Substrate conclusions that support the current direction

`create_agent()` over `create_deep_agent()`, confirmed independently three times —
`create_deep_agent()` has no `middleware=` parameter, so custom hooks are impossible. Pydantic AI
was tried as the main runtime and abandoned (*"pydantic-graph API instability... the ecosystem is
immature"*). MCP was only ever about tool discovery, never gating already-bound calls — which
independently confirms `PLAN.md` item 7's scoping. `interrupt_on` is static and cannot change
mid-run, so `HumanInTheLoopMiddleware`'s declarative form cannot serve the depth-2 gate;
`wrap_tool_call` can.

Framework churn (LangChain → LangGraph → Pydantic-AI) is recorded, but its stated driver was
*"Ollama structured output issues"* — Ollama-specific, and so does not transfer to a Claude stack.

### 8. The thesis, observed in the wild

- `learnings/audit/may18-second-pass-code-verify.md:39` — *"the git analysis treated the file's
  existence as evidence of a working validator"*, when the docstring said **"Empty validator."**
  Fixed structurally: a mandatory second pass that re-reads files instead of trusting commit
  messages. *"The git-only pass... missed 3 findings and generated 1 false positive."*
- A spec required real micro-cluster initialization from cold-start centroids; the implementation
  stored them in a parallel dict the clusterer never reads. Code shaped like the spec, verified by
  nothing.
- "63/63 tests pass" was false — a silent syntax error meant only 56 collected. Recorded lesson:
  any "all tests pass" claim must carry the exact invocation and line counts.
- `ses-test.md:4211`, the thesis in the user's own words before the plan existed: *"they really
  need to CHALLENGE the assumptions, don't assume themselves... If the auditor sees an assumption,
  a conclusion, a pivot. ask WHY — DIG DEEP... has the issue been verified against source code?"*

**Every audit catch in this repo happened after a full build cycle. Never during.** That is the gap
the ledger moves to tool-call time.

## Provenance of this survey

Practising the discipline the project describes.

**Verified at source by the main session, not taken on an agent's word:**
the S11 provenance edges (`ses-test.md:9141`, `:9154-9156`, `:9067`, `:9052`, `:9167`); the
location and wording of the runtime-gating rejection
(`learnings/radical-simplification/2026-05-19-full-session.md:20`,
`context/ARCH_REBUILD_HANDOFF.md:11-12`, `specs/radical-simplification-rebuild.md:54`, `:134`);
the repo tree, file counts and git timeline.

**Single-agent reported, not independently verified:** everything else, including all line
citations in slices 01, 02, 03, 05, 07, 09 and the May 16/18/19 timeline detail in slice 06.

**Corrected during the survey:** `extraction_method` is a two-way split (LLM-extracted vs.
explicit), not the three-value enum first reported. `session_no_tools_or_thinking.md` is not a
controlled A/B run — it is `session-full.md` re-exported with thinking blocks and tool JSON
stripped (17x compression, all user corrections still legible). Slice 07 filed the MCP no-op
findings as counter-evidence to `PLAN.md` item 7; they are not — item 7 concerns what MCP can
architecturally do, while that code simply was never wired up.

**Known gaps:** the nine canonical agent personas lived in a global
`~/.config/opencode/opencode.jsonc` that does not exist in this container; six of the nine are
lost, and only `architect.md`, `product_owner.md`, `senior_python_engineer.md` survive in-repo.
`docs/taxonomy/` and `docs/research/` were skimmed, not read. No code was executed.
