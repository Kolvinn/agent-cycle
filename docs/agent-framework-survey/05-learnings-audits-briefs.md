# 05 — Learnings, audits, briefs, context, history

## Scope covered

All paths under `agent_framework/docs/`:

- `learnings/` — all 28 files read in full (the priority target).
- `audit-reports/` — all 8 files read in full.
- `briefs/` — 6 of 9 files read in full (`data-vs-raw-structures.md`, `dynamic-agent-runtime.md`,
  `full-project-audit-may18.md`, `model-unification-audit.md`, `phase2-tools-hybrid.md`,
  `taxonomy-audit.md`); 3 skimmed (`memgraph-diagram-redesign.md`, `taxonomy-concept-answers.md`,
  `taxonomy-conceptual-audit.md`) — these are BERTopic/taxonomy/Qdrant domain content per the
  skim instruction, confirmed structurally similar to `taxonomy-audit.md` (phased, "awaiting user
  gate").
- `context/` — all 6 files read; `docker-architecture.md` and `volumes.md` (909 + 802 lines, pure
  Docker/Flox research transcripts) skimmed via targeted grep rather than full read, per
  instruction to skim domain content.
- `history/` — all 8 files read (`container-topology-learnings.md`, `diagrams-summary.md`,
  `findings.md` in full per instruction; `git-history-roadmap.md`, `progress.md`,
  `session-005-handoff.md`, `session-006-handoff.md`, `task-plan.md` read/skimmed — mostly
  restate what's already in `context/` and other `history/` files).
- `overhaul/` — all 6 files opened; `findings.md`, `task_plan.md` read in full; `graph-instructions.md`,
  `orchestration-roadmap.md`, `progress.md`, `question-tree.md` (2133 lines — a RAG/taxonomy
  consultant-knowledge-system design tree) skimmed — pure domain content, structurally consistent
  with what `context/agent-variations.md` already documents about the delegation model.
- Top-level: `docs/content_manifest.md` (targeted read of §6 discrepancies + migration structure),
  `docs/next_goals.md`, `docs/session_handoff.md` — both read in full.

Read-only throughout; nothing in `agent_framework/` was modified.

## Map

| Directory | What it is | Process value |
|---|---|---|
| `learnings/` | 28 post-session retrospectives, one per work session, almost all following the same four-part template: What I Was Asked / Key Decisions / What I Assumed / What I Was Uncertain About / What I'd Do Differently | **Highest** — this template is itself a manual, prose-based provenance mechanism (see below) |
| `audit-reports/` | 8 files: two full multi-lens audits (May 16, May 18) plus their scratch/working files (findings, progress, task_plan) and a companion resolutions doc | **High** — documents an actual QA loop over agent output, with a measurable false-positive rate |
| `briefs/` | 9 pre-task scoping docs — options + trade-offs, explicitly gated behind user approval before becoming a spec | **High** — a structural analogue to "implicit node, needs promotion" |
| `context/` | 6 files: architecture ground-truth docs (`MASTER_STATUS.md`), a governance-rules manifesto, model-selection rationale (opencode-era), agent-variation matrix, and two large Docker/Flox research transcripts | **Mixed** — `MASTER_STATUS.md` §0 and `agent-variations.md` are gold; the two Docker files are pure infra domain content |
| `history/` | 8 files: early-session progress logs, topology learnings, diagram design notes, a git-branch-archaeology roadmap | **Low-medium** — mostly restates what `context/` already says, with one exception (`findings.md`) |
| `overhaul/` | 6 files: a later (June 2026), unrelated-repo-lineage RAG/taxonomy "consultant knowledge system" planning effort | **Low** — almost entirely domain content (RAG, BERTopic, Qdrant, taxonomy), reuses the same delegation/brief vocabulary already captured elsewhere |
| top-level `docs/*.md` | Migration bookkeeping between two now-merged repos (`app/` → `agent_framework/`) | **Low-medium** — `content_manifest.md`'s discrepancy table is a good honest-negative-result data point |

## Lessons about how agents fail

The strongest, most reusable finding in this whole slice is structural, not a single quote: **every one
of the 28 `learnings/` files follows the same four-part template** — "What I Was Asked to Do," "Key
Decisions Made," "What I Assumed About the Existing System," "What I Was Uncertain About," "What I'd Do
Differently Next Time." This is, functionally, a *manual, after-the-fact, prose version of exactly the
ledger PLAN.md proposes*: the "Assumed" section is a list of implicit nodes; "Uncertain About" is a list
of items that should have been escalated to the user; "I'd Do Differently" is a rolling reconcile,
just written once at session end instead of every 5 tool calls. It was never enforced by tooling —
it's convention, and conventions decay (see "Open threads" below for where it visibly slipped).

Beyond that structural finding, concrete quoted lessons:

**Treating surface evidence as proof of function (hallucinated conclusion from indirect evidence):**
> "Treat 'empty validator' / 'placeholder' comments as findings, not dismissals. The `validate_model_write`
> docstring literally said it was empty, but the git analysis treated the file's existence as evidence
> of a working validator."
— `agent_framework/docs/learnings/audit/may18-second-pass-code-verify.md:39`

The same file documents a **corrected false positive** from inference-without-reading:
> "Corrected a false finding mid-verification — had flagged a potential data flow gap... After reading
> `agent_runtime/models.py` line 151... and the `AgentConfig.model_validate_json()` call... confirmed
> that Pydantic's discriminated union handles the conversion. No gap exists. This was a false positive
> from my git-only analysis."
— `agent_framework/docs/learnings/audit/may18-second-pass-code-verify.md:16`
and its meta-lesson:
> "Code verification should be the SECOND pass, not an afterthought. The git-only pass gave me a
> directionally correct timeline but missed 3 findings and generated 1 false positive."
— same file, line 35

**Confusing prompt-tool scratchpad space with actual drafting (a agent losing track of what a tool is for):**
> "The moment a 'thought' exceeds ~15 words, it's no longer a reasoning step — it's drafting. At that
> point I should stop using the tool and write to a file... I was drafting report sections inside the
> thinking tool, which is not its purpose."
— `agent_framework/docs/learnings/architecture/2026-05-16-full-audit.md:64`

**Absorbing a skill's framing without making the reasoning traceable back to it:**
> "I loaded the skill and its vocabulary shaped my thinking..., but I never mapped findings back to
> specific Clean Architecture principles in the report... Making those connections explicit would make
> the audit more actionable."
— `agent_framework/docs/learnings/architecture/2026-05-16-full-audit.md:68-70`

**Overreach — building an abstraction before verifying it's needed:**
> "When a spec suggests writing a new abstraction, first verify the platform (SQLModel/Pydantic)
> can't already do it."
— `agent_framework/docs/learnings/model-unification-phase1-2.md:78`
(concretely: a whole `serialize.py` module was nearly hand-written before a 15-minute roundtrip test
showed Pydantic's `@model_serializer` already did the job — `model-unification-phase1-2.md:38-46`)

**Making policy decisions about facts that were never verified:**
> "Whether `graph_module` actually exists on `AgentConfig` — The gap analysis implies it does..., but
> the Explorer didn't confirm. I made a policy decision (drop it) without certainty about its existence.
> The Implementer will discover the truth."
— `agent_framework/docs/learnings/runtime/phase-a-updated.md:34`

**Losing the original ask through verbosity / over-explaining instead of pointing at files:**
> "Point implementers to files, don't repeat context — the user corrected me on being too verbose
> with implementer prompts. Point to the spec file, let them read it."
— `agent_framework/docs/learnings/radical-simplification/2026-05-19-full-session.md:45`

**A concrete in-the-wild example of unbounded, open-ended agent looping** (cited because it is exactly
PLAN.md's Open Item 1 — overreach within a single document/response, no chained tool call involved):
the Phase 2 taxonomy-organizing agent entered an infinite reasoning loop. The diagnosed cause and fix:
> "Remove: 5 open-ended 'AUDIT QUESTIONS' (these caused the loop) ... 'Ask yourself' loops ...
> 'Be AGGRESSIVE' (subjective, no stopping criteria). Add: Concrete merge criteria... Clear stopping
> condition: 'when no more merges/deletes remain, output final structure.'"
— `agent_framework/docs/briefs/phase2-tools-hybrid.md:64-77`

**A system-level version of scope/context failure** — two incompatible agent runtimes were built five
days apart because nobody checked prior work:
> "The spec doesn't mention `agent_entrypoint.py`. The implementer didn't look at `agent_entrypoint.py`.
> The result: two runtimes that solve the same problem but share nothing."
— `agent_framework/docs/audit-reports/deep-dive-two-runtimes-2026-05-16.md:222`

**Stale/contradicted context files being trusted as ground truth** (agents inheriting wrong facts
because nobody re-verified documentation against reality):
> 10 discrepancies including "`stack.md` describes conda as package manager — should be Flox,"
> "`services.md` lists wrong models... actual config uses deepseek-v4-pro," "`Dockerfile` still uses
> `conda install` — should use Flox per overhaul... Build would fail."
— `agent_framework/docs/content_manifest.md:210-225`

**The project's own explicit anti-hallucination rule for audits**, which is close kin to PLAN.md's
"prediction, not understanding" framing:
> "Rule: YOU ARE NOT SUPPOSED TO DEFINE AN ABSOLUTE TRUTH. You are creating a shifting timeline, and
> your job is to track the changing landscape, spot the inconsistencies..."
— `agent_framework/docs/briefs/full-project-audit-may18.md:14`

**And the closest thing to a written first-principles statement of "user is the provenance authority,"**
predating PLAN.md by months:
> "User is Governor — permissions bubble up, never assumed downward." / "Don't assume intent —
> ambiguity → query user directly." / "No autonomous decisions — pause and ask user before acting."
— `agent_framework/docs/context/MASTER_STATUS.md:14,15,11` (§0 Session Rules)
> "User is Governor: Universal principle injected into every agent prompt. Permissions bubble up,
> never assumed."
— `agent_framework/docs/history/findings.md:68`

## The audit loop, reconstructed

The method, reconstructed from `audit-reports/` + the two `briefs/*audit*` files + their `learnings/audit/*`
retrospectives:

1. **Multi-lens sweep** (`full-project-audit-2026-05-16.md`). One auditor agent reads *every* source
   file (not a sample) across three lenses — Architect, Developer, Product Manager — and cross-checks
   against a prior audit's 14 findings. Produces a severity-tiered table (🔴 Critical / 🟠 Major /
   🟡 Minor / ⚪ Note) with stable IDs (`ARC-#`, `CR-#`, `DEV-#`, `PM-#`) that persist across audit
   generations, enabling delta tracking later. 23 total findings.
2. **A separate resolutions document** (`full-project-audit-2026-05-16-resolutions.md`), explicitly
   gated: "Status: Awaiting user review and gate decisions" (line 5). For each finding it lays out
   2-3 options with pros/cons/effort, and *never itself picks* on architecture-level questions — e.g.
   ARC-1 ("which of the two agent runtimes is canonical?") is left as a hard "User gate required"
   (line 83) even though the auditor has an explicit recommendation.
3. **A brief handing the next audit off** (`briefs/full-project-audit-may18.md`) — written by the
   auditor, for a fresh instance of itself days later, explicitly framed as "a brief, not a spec"
   (line 12) with a hard read-only constraint: "Rule: Do NOT start coding or fixing" (line 16).
4. **Second pass, two sub-stages, run by the fresh instance:**
   - *(a) Git-driven chronological pass* (`findings_may18.md`, `task_plan_may18.md`,
     `progress_may18.md`) — walks all 25 commits since the May-16 audit, phase by phase, tagging
     each of the 23 prior findings ✅ resolved / ❌ still open / 🔄 worsened, and logging new findings.
   - *(b) Code-verification addendum* (`learnings/audit/may18-second-pass-code-verify.md`) —
     explicitly re-opens every file implicated in every finding and reads it end-to-end, "not what
     commits claim — what the code actually does" (line 11). This stage is what caught the false
     positive and found 3 of the 10 new findings the git-only pass missed.
5. **Final synthesized report** (`full-project-audit-2026-05-18.md`) with a delta table
   (Resolved / Still Open / New), a Mermaid architecture-evolution diagram, and a fresh priority plan.

**Did it catch real errors, or produce noise? Both, at a measurable rate.** Genuine, load-bearing bugs
were caught and (mostly) fixed: a controller/runtime schema mismatch that meant "no agent can ever
successfully bootstrap" (`dynamic-agent-runtime-2026-05-16.md:18`), a missing `PYTHONPATH` causing a
guaranteed `ModuleNotFoundError` on container start, a `KeyError` on any config push that added a new
MCP server, and MCP tools silently disappearing for unchanged servers on every reload. Of the 23
original findings, 10 were resolved within 2 days, 12 remained open, and 1 (`DEV-1`, the "two
AgentConfig classes" problem) *worsened into three* colliding classes — a rough 43% genuine fix rate
after one focused effort, which is itself an honest measure of how much initial agent output needed
correction. Against that, the loop also produced confirmed noise: one explicit false positive from
git-diff-only reasoning (corrected only because a second, code-reading pass existed), and a process
finding (`NF-5`) that the audit's own required user gate (ARC-1, "which runtime is canonical?") had
been *silently, implicitly resolved* by an implementer commit without ever getting the user's actual
answer — i.e., even in a repo whose written session rule was "no autonomous decisions," the audit
loop itself caught its own governance being quietly bypassed once.

## Briefs and agent variations as control mechanisms

**A brief is explicitly a pre-task scoping artifact, and it constrains what an agent may conclude by
construction, not by instruction.** Confirmed both structurally and in words across every brief opened:
`taxonomy-audit.md:5` ("Status: Phase 1 — Options & Trade-offs (awaiting user gate)"),
`taxonomy-conceptual-audit.md:5` (same pattern), `data-vs-raw-structures.md` (ends in "## Open Questions
Before Spec," never an answer), `dynamic-agent-runtime.md` (three lettered options, each with pros/cons,
no pick), `full-project-audit-may18.md:12` ("This is a brief, not a spec"). A brief never contains a
decision — only the space of decisions plus their trade-offs — and `context/agent-variations.md:99-106`
shows this is enforced by an actual read/write firewall: the Implementer and Auditor role definitions
list briefs under "NEVER READS." An implementer only ever sees a *spec* (the artifact produced after a
brief has been user-gated into a decision), never the brief's raw, hedged reasoning. This is a structural
analogue to "no implicit node self-promotes" — the tentative material (brief) literally cannot reach the
code-writing agent (implementer) until a human has turned it into a committed artifact (spec).

**Agent "variations" (`context/agent-variations.md`) were 9 named configurations of 5 generic base
types** (Orchestrator, System Thinker, Implementer, Auditor, Explorer), distinguished *only* by model +
injected skills + injected context files — explicitly not by prompt changes: "Prompt stays generic.
Variation = model + skills + context injection" (line 13). E.g. `strategic_thinker` / `rag_thinker` /
`architect_thinker` are all `system_thinker` base with different skill bundles; `python_implementer` /
`infra_implementer` are `implementer` base with different skills. Two prior types (Reviewer, Coordinator,
RAG Architect) were retired/absorbed as redundant (lines 27-30).

**Yes — specialization was explicitly used as a control mechanism, not just an efficiency one.** The
read/write boundary table (`agent-variations.md:99-106`) is the real enforcement layer: the Orchestrator
never reads full content, only summaries and file paths (token economy *and* a hedge against it drawing
conclusions from material it can't fully verify); System Thinkers never read source code; Implementers
read specs and source but never briefs; Auditors read specs and code but never briefs, and are
structurally barred from fixing anything — "Never fixes, only reports" (`agent-variations.md:24`). This
means the pipeline (Thinker writes brief → user gates it into a spec → Implementer translates spec
literally → Auditor reports only) is a hard-wired provenance chain: each stage can only act on artifacts
that a prior stage/user has already committed, and the system prevents any stage from reaching backward
into a more speculative upstream artifact.

## Honest negative results

- **A whole architectural investment was built, then fully discarded days later.** Across
  `learnings/dynamic-agent-runtime/*`, `learnings/model-unification*`, and
  `learnings/async-fastapi-receiver/session-summary.md`, multiple sessions (May 16-18) built a
  layered `CapabilityRegistry` + `CapabilityRegistryMiddleware` + a `PermissionRef`/`AgentPermissionLink`
  discriminated-union schema for fine-grained runtime tool/skill/MCP gating. By May 19,
  `context/ARCH_REBUILD_HANDOFF.md:11-13` reports it all deleted: "Permissions-Based Gating: The
  database no longer governs what tools/skills an agent can use... Runtime Middleware Gating:
  `capability_registry.py`, `middleware.py`, and `skills.py` have been purged." Replaced by a 5-table
  tracker with no runtime gating at all — per `learnings/radical-simplification/2026-05-19-full-session.md:20`,
  "the user explicitly rejected HITL skill approval, symlink-based file gating, and permission
  derivation. The ONLY gate is package registration (vesting)."
- **Framework churn, admitted directly:** "Started with LangChain[,] Migrated to LangGraph for better
  state management[,] Currently on Pydantic-AI for cleaner structured output... Ollama structured
  output issues drove Pydantic-AI migration." — `agent_framework/docs/overhaul/findings.md:22-24,31`
- **The audit's own admission that a whole class of its findings was unreliable without a second,
  code-reading pass** — see the false-positive/false-dismissal quotes above
  (`may18-second-pass-code-verify.md:16,39`).
- **Stale documentation actively misleading**, tracked as 10 discrepancies between what context docs
  claimed and what the code actually did (`content_manifest.md:210-225`), including a claim that would
  have caused a real build failure if trusted ("`Dockerfile` still uses `conda install`... Build would
  fail after conda removal").
- **No single explicit "X% of agent output was wrong" statement exists in this slice**, but the closest
  quantifiable proxies are: (a) 10 of 23 findings (~43%) fixed after one focused 2-day effort, 12 still
  open, 1 worsened; (b) the May-18 code-verification pass altered the record on roughly 4 of the ~14
  findings it re-checked in detail (1 corrected false positive + 3 newly discovered real bugs the
  git-only pass missed) — call it a rough 1-in-4 "the prior pass's belief about this finding was
  incomplete or wrong" rate, specifically *because* that prior pass reasoned from commit
  messages/diffs rather than reading the actual files.

## Salvage rating

### Directly reusable for the provenance-ledger project
- The `learnings/` four-part template (Asked / Decided / Assumed / Uncertain / Would-Do-Differently) —
  a working, low-overhead precedent for what the ledger's reconcile step should actually capture and
  surface to the user, validated across 28 real sessions.
- `context/MASTER_STATUS.md` §0 Session Rules (`MASTER_STATUS.md:9-20`) — "No autonomous decisions,"
  "Don't assume intent — ambiguity → query user directly," "User is Governor — permissions bubble up,
  never assumed downward." These are the provenance ledger's core principles already written down,
  months earlier, as *prompt convention only* — unenforced by any tool. The new project's contribution
  is exactly making these mechanically enforced instead of aspirational.
- The two-stage audit method itself (fast pass from message/diff history, then a mandatory separate
  pass that re-derives ground truth from actual file contents) is a good template for *validating the
  ledger once built*: periodically re-check the ledger's claimed depth-0/1 provenance links against
  actual message content rather than trusting the model's self-report — directly relevant to
  PLAN.md's Open Item 2 (deterministic text-match vs. self-report vs. hybrid).
- The brief → user-gate → spec → implementation pipeline, with its hard read/write firewall
  (`agent-variations.md:99-106`), as a concrete existing precedent for "no implicit node self-promotes."

### Good thinking material / adaptable
- The audit brief's explicit "you are not supposed to define an absolute truth" rule
  (`full-project-audit-may18.md:14`) is good framing for how the ledger should talk about
  what it finds — report the state, don't assert conclusions past the evidence.
- `phase2-tools-hybrid.md`'s "infinite reasoning loop" diagnosis and fix is concrete, real evidence for
  PLAN.md's Open Item 1 (an agent overreaching within a single response, no chained tool call to gate)
  — worth citing directly when that item eventually gets designed.
- The agent-variation "generic type + config-driven specialization" idea — heavier than v1's
  `bind_tools`-only scope needs, but a good reference for later phases (PLAN.md Item 9's deferred
  built-in-tool-gating work) on how role separation itself functions as a safety mechanism.

### Dead, superseded, or domain-specific noise
- `context/model-selection.md`'s specific model/benchmark claims (GLM-5.1 "58.4% SWE-bench Pro,"
  DeepSeek V4 Pro "87 BenchLM," "600+ iteration loops") — a copy-pasted opencode-era chat transcript
  with unverifiable, marketing-flavored numbers, entirely superseded by the new project's single-model
  Claude approach via `langchain-claude-cli`. The underlying *reasoning* (endurance model for
  orchestration, low-hallucination model for audit, cheap-fast model for grunt work) might be worth a
  passing mention if the new project ever needs multi-model routing, but the specifics are dead.
- Nearly all of `context/docker-architecture.md`, `context/volumes.md`, most of `history/`, and all of
  `overhaul/` — Docker/Flox/volume-topology and RAG/BERTopic/taxonomy domain content, not applicable to
  a LangChain + `langchain-claude-cli` project with no current multi-container or vector-DB scope.
- Most `learnings/` implementation-detail entries (SQLModel/Pydantic v2 quirks, PyYAML tag tricks, a
  Flox `set -e` leak into interactive shells) are reusable only if the new project touches those exact
  libraries — currently out of scope.

## Open threads & contradictions noticed

1. **Direct tension with the new project's premise.** The radical-simplification rebuild
   (`context/ARCH_REBUILD_HANDOFF.md`, May 19) explicitly tore out fine-grained runtime tool/skill
   gating as over-engineered relative to what the user actually wanted, after several sessions built
   it out in real depth. The new provenance-ledger project is, in a narrower and differently-motivated
   form, proposing gating on tool calls again (via `bind_tools`). This is not proof the new approach is
   wrong — the goal differs (provenance/scope-drift prevention vs. capability/package permissioning) —
   but it is a documented instance in this exact lineage of an elaborate gating system being built and
   then discarded as unwanted friction, and worth a deliberate gut-check that the ledger doesn't
   reproduce the discarded machinery under a new name.
2. **Framework churn risk, unaddressed in PLAN.md.** This lineage left LangChain/LangGraph once
   already, citing structured-output reliability problems with Ollama-hosted models
   (`overhaul/findings.md:31`). The new project re-adopts LangChain. The root cause (self-hosted-model
   structured output) likely doesn't recur with Claude, but PLAN.md doesn't mention this prior
   departure at all.
3. **A governance rule got silently bypassed even with the rule written down.** `NF-5`
   (`audit-reports/full-project-audit-2026-05-18.md:67`, `findings_may18.md:51,64`) documents that the
   ARC-1 "which runtime is canonical" user gate — explicitly flagged as "User gate required" in the
   resolutions doc — was implicitly resolved by an implementer's commit without the user ever formally
   answering. This happened in a repo whose #1 written session rule was "no autonomous decisions." It's
   direct, in-lineage evidence for PLAN.md's own Item 7 insistence that enforcement can't live in
   prompts/docs alone and needs a `PreToolUse`-style hook — because here, the prompt-only version of
   that exact rule visibly failed once already.
4. **"Asking is cheap" doesn't guarantee an answer arrives.** PLAN.md's decision 5 ("asking is cheap,
   so there's no case where skipping the check is worth the saved friction" — the user's own words)
   is exactly the old repo's cultural default. But `task_plan_may18.md:105` notes flatly that all 5
   user gates raised by the May-16 resolutions doc were *never formally answered* before the next audit
   pass began. Worth designing for: the ledger's ask-and-block behavior needs a real answer path, not
   just a cheap question — an unanswered depth-2 gate could otherwise just stall work indefinitely
   the way these open gates did for days.
5. **A five-week-long unresolved "Open" item.** ACP container transport is marked "TBD" continuously
   from `history/session-005-handoff.md` (May 12) through `audit-reports/full-project-audit-2026-05-18.md`
   (May 18) without ever closing. A caution for PLAN.md's own "Open — not yet decided" list: nothing
   in the old repo's process forced these items to resolve; they just persisted.

## Best pointers

- `agent_framework/docs/context/MASTER_STATUS.md:9-20` — the closest prior-art statement of the
  provenance ledger's own principles, written as prompt convention months before this project existed.
- `agent_framework/docs/learnings/audit/may18-second-pass-code-verify.md` (whole file, 39 lines) —
  the single best evidence that a two-pass (infer-then-verify) method catches real errors in inference
  that pure message/diff-based reasoning produces.
- `agent_framework/docs/audit-reports/full-project-audit-2026-05-16-resolutions.md:1-83` — the
  cleanest example of a brief-like document that presents options with effort estimates and refuses to
  decide for the user.
- `agent_framework/docs/context/agent-variations.md:97-106` — the read/write boundary table; the
  concrete mechanism behind "specialization as control."
- `agent_framework/docs/context/ARCH_REBUILD_HANDOFF.md:11-13` — the clearest single-paragraph record
  of a full gating architecture being deliberately discarded.
- `agent_framework/docs/briefs/phase2-tools-hybrid.md:64-77` — concrete, real evidence of an
  open-ended-prompt-induced infinite loop and its fix, relevant to PLAN.md's Open Item 1.
- `agent_framework/docs/content_manifest.md:210-225` — the discrepancy table; a compact, itemized
  honest-negative-result artifact.
