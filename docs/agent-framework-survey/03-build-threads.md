# 03 — Build threads: memory-build, build stages, diagram-agent, auditor

## Scope covered

Read in full: `memory-build/IMPLEMENTER_PROMPT.md`, `decisions.md`, `objectives.md`, `session-log.md`,
`spec.md`, `references.md`; `memory-build/audit/00-tracking.md`, `HANDOFF.md`, and findings
`00-green-claim-false.md`, `17-no-answer-provenance.md`, `26-mcp-tool-no-provenance.md`;
`build/stage-01-cold-start/{audit,verification}.md`; `build/stage-02-streaming-design/audit-{goal,architecture,coding,engineering}.md`;
`build/state-overview/overview.md`; `diagram-agent/{CHANGELOG,entry,session-summary,learning-summary}.md`;
`bertopic-pipeline-auditor/{entry,learning-summary}.md`; `shared/{investigation-handoff,mvp-thought-map,product-fit-summary,research-session-summary,research-synthesis}.md`.

Not read in full (scope-limited, low process value): the individual `spec-01..08-*.md` files
(their contents are summarized accurately by `spec.md`'s table and `IMPLEMENTER_PROMPT.md`'s
build order — reading all 8 would have been mostly domain schema detail); the 26 individual
files under `memory-build/audit/findings/` (sampled 3 representative ones); the 7 individual
report files under `bertopic-pipeline-auditor/output/` (covered via `learning-summary.md`'s
synopsis, which is itself a condensed digest written for exactly this purpose); the `.mmd`
diagram file contents and `diagram-agent/output/*.mmd`; `shared/bertopic-docs/` (skimmed
directory listing only, per instructions — pure BERTopic API reference, no process content);
the 13-paper research corpus under `shared/research-*` beyond the two synthesis/summary
documents. `docs/learnings/stage-02-fix-pass-2026-06-24.md` is referenced repeatedly by this
slice's files but sits outside `agent-workspace/` and outside this assignment.

## Map

- **`memory-build/`** — a complete, shipped build thread (an opencode-session memory pipeline:
  3 Qdrant collections + Postgres + FastMCP server). Has the richest bookkeeping of the four
  threads: a `decisions.md`/`objectives.md`/`session-log.md` triad kept in sync across ~10
  architecture pivots in one day, an 8-file spec decomposition, an `IMPLEMENTER_PROMPT.md`
  used to hand the build to a fresh implementer agent, and a two-pass adversarial `audit/`
  (26 findings) including a persistent probe harness.
- **`build/`** — an earlier, still-open build thread (RAG pipeline: BERTopic + River streaming
  topic model over a cold-start/streaming-ingest split). `stage-01-cold-start/` passed audit;
  `stage-02-streaming-design/` did not — its 4-angle audit (goal/architecture/coding/engineering,
  each independently run) unanimously returned FAIL. `state-overview/overview.md` is a
  cross-referenced snapshot of the whole `src/` + `agent-workspace/` state at that point in time.
- **`diagram-agent/`** — a narrow, disciplined sub-agent variation whose only job is producing
  Mermaid diagrams for the wider investigation. Five diagrams, one changelog, incremental
  convention-building (D1→D14), each diagram's open questions carried forward explicitly.
- **`bertopic-pipeline-auditor/`** — a third-order audit: an agent spawned specifically to
  *audit the auditors* (validate the 4 stage-02 audits against source, not against each
  other's word). Its `entry.md` is an unusually explicit adversarial-verification brief.
- **`shared/`** — cross-thread handoffs and a large literature-research side-thread (13 academic
  papers on topic modeling / graph RAG, cast across 4 research sessions). Mostly domain content;
  the process-relevant part is the orchestration discipline described in `investigation-handoff.md`
  and the co-evolution analysis method in `product-fit-summary.md`.

## Process & control techniques found

### 1. Spec decomposition as a scope-drift control (memory-build, `spec.md:62-77`)

The build is split into 8 numbered spec files (`spec-01-storage.md` … `spec-08-cli-tests.md`),
each mapped 1:1 to a fixed, named set of files to create, with an explicit dependency column
and a stated build order:
`/workspaces/langchain-claude-test/agent_framework/agent-workspace/memory-build/spec.md:62-77`.
`IMPLEMENTER_PROMPT.md:56-65` restates this as "Build order (each is independently testable)"
and `IMPLEMENTER_PROMPT.md:125-127` closes with an explicit gate: *"Begin with spec-01-storage
... Move to spec-02 only when 01's done criteria pass."* Each section has a **done criteria**
block (`IMPLEMENTER_PROMPT.md:116-123`): files exist, `pyrefly check` passes, `ruff check`
passes, the spec's acceptance criteria are met, the section's own tests pass. This is a
sequential-checkpoint pattern — an agent cannot silently drift into section 5's scope while
"still working on" section 2, because each section has an independent, file-scoped
verification gate before the next can start. Directly relevant to the new project's per-5-call
reconcile idea, just applied at spec-section granularity instead of tool-call granularity.

### 2. `IMPLEMENTER_PROMPT.md` as a single canonical orientation document

One file a fresh implementer agent reads first, structured as: read-order list → locked
decisions → **anti-patterns to avoid** → build order → coding standards → environment →
"what to verify against current docs" → "what to log" → "what to NOT do" → done criteria →
explicit start instruction. It exists because build threads in this repo get **resumed by a
different agent instance** mid-build (confirmed in `session-log.md:495-499`: *"Picked up the
build after a prior implementer agent had partially completed specs 01-07 ... The previous run
went off the rails (errant commands, partial state)"*). The orientation doc is the mechanism
that lets a fresh agent resume without re-deriving 40+ prior decisions from scratch, and without
inheriting the previous agent's drift.

### 3. Decision bookkeeping that traces every decision to its source (memory-build `decisions.md`)

Every row in `decisions.md` is `| # | Decision | Source |`, and **Source is not a
paraphrase — it is either a literal quote from the user, or an explicit tag that the claim
was inferred**: e.g. `decisions.md:9` — `user: "I changed to server opencode... didn't attach
to the agent_framework folder"`; `decisions.md:11` — `inferred from src/local_mcp/server2.py`;
`decisions.md:130` — `derived from "It shouldn't be ingested if there's no clear concept..."`.
The document is split into **Locked (committed)** vs **Open (need user input)** sections
(`decisions.md:105-116`), and even "Open" items carry a default plus an explicit acceptance
status (`**accepted** (user: "Those defaults are fine")`). This is the single strongest
precursor found in this slice to PLAN.md's explicit/implicit split — it is doing, by hand, at
the granularity of *design decisions*, almost exactly what the new project wants to do
automatically at the granularity of *tool-call targets*: tag every claim with whether it traces
to the user's literal words or to inference, and never silently blur the two.

A related discipline appears in `session-log.md`: every dated entry ends with both a **"What I
did"** and a **"What I did NOT do"** subsection (e.g. `session-log.md:39-42`, `:80-84`,
`:159-161`, `:193-206`, `:242-246`, `:278-282`, `:306-309`, `:565-572`). Explicitly recording
exclusions is a scope-drift guard: it forces the agent to state, in writing, every adjacent
thing it *chose not to touch* — which is the write-time analogue of the ledger's "close out
every implicit node" completion criterion.

### 4. The 4-angle independent audit (`build/stage-02-streaming-design/audit-{goal,architecture,coding,engineering}.md`)

Stage 02 was audited from **four separate, independently-run angles** — goal (does it serve the
user's actual need), architecture (module boundaries, data flow, load-bearing seams),
coding (library API correctness, runtime bugs), engineering (test coverage, deployment
readiness) — each producing its own PASS/FAIL verdict against a shared checklist of 10
"settled findings" (verified largely by `grep` for banned language like `intelligence|smart|
novel|state-of-the-art`, e.g. `audit-goal.md:104-106`, `audit-architecture.md:413-424`). All
four independently returned **FAIL** (`audit-goal.md:5`, `audit-architecture.md:5`,
`audit-coding.md:9`, `audit-engineering.md:5`), each citing concretely reproduced runtime bugs
(e.g. `audit-coding.md:74-114` gives exact repro code for an `IncrementalPCA` shape-mismatch
crash). This is a genuine adversarial audit pattern, not a rubber stamp — worth reusing as a
technique: **split "is this good?" into independently-scoped lenses that cannot see or defer to
each other's verdict**, each grounded in re-running the actual code rather than trusting a
prior claim.

### 5. Two-pass adversarial audit with a persistent probe harness (`memory-build/audit/`)

`audit/HANDOFF.md` records two audit passes on the same build. **Pass 1** ("plumbing"):
correctness/accuracy, 14 findings, severity rubric CRITICAL/HIGH/MEDIUM/LOW/INFO
(`audit/00-tracking.md:38-44`). **Pass 2** ("user-experience lens", `HANDOFF.md:248-389`):
explicitly re-audits the *same* code from a different vantage — "adopt a USER's perspective...
find gaps the previous audit missed by inspecting what the LLM actually sees" — and finds 12
*new* findings the first pass missed entirely, two of them CRITICAL (chat history never reaches
the retrieval LLM despite being persisted; no PII scrubbing). Both passes are backed by
runnable, non-pytest probe scripts committed to the repo (`audit/probes/user_feedback_loop.py`,
`audit/probes/inspect_prompts.py`, `audit/probes/user_experience_audit.py`) that simulate real
usage and print/write structured findings — an audit that leaves behind reusable, re-runnable
evidence, not just prose.

### 6. Catching a stale "all green" claim (`memory-build/audit/findings/00-green-claim-false.md`)

A prior session's `session-log.md` asserted "63/63 tests pass." The audit re-ran the suite cold
and found only 56 collected — a syntax error (`for chunk in result:Now`) was silently preventing
7 tests from collecting (`findings/00-green-claim-false.md:1-26`). The finding's own "Process
issue" section (`:47-48`) states the generalizable lesson: *"The 'final state' summary in
session-log does not show the command that was run. The implementer asserted the count without
re-running... Recommend: any 'all tests pass' claim must include the exact pytest invocation +
line counts in the log."* This is a concrete instance of an agent treating a **remembered
assertion as if it were a freshly-verified fact** — exactly the "prediction, not understanding"
failure mode PLAN.md opens with, just manifested as trusting one's own prior session's summary
instead of trusting an inference.

### 7. Explicit adversarial-verification brief (`bertopic-pipeline-auditor/entry.md:14-37`)

This is the most directly reusable artifact in the slice for the new project's purposes. Its
"Prime directive — challenge everything" section states: *"You are an investigator, not a
confirmer... On every assumption, conclusion, pivot, or claim you encounter, ask: (1) Has this
been verified against source code, or is it inferred from a doc or another agent's claim? If
inferred — chase the source."* Its "Stop condition" (`entry.md:26-31`) enumerates exactly what
does **not** count as having verified a claim: *"A 'looks plausible' is not a stopping point. A
'the spec says so' is not a stopping point. 'I read the audit and it didn't flag this' is not a
stopping point."* The worked examples (`entry.md:33-37`) are all instances of "an upstream
agent's claim propagated forward without being re-traced to its actual source" — the same shape
of failure the provenance ledger exists to gate.

### 8. The "USER CONFIRMED" mislabeling — a real incident of implicit self-promotion

This is the closest thing in the whole slice to a documented occurrence of the exact failure
PLAN.md's decision #10 (*"No implicit node self-promotes to explicit... every implicit requires
the user's own confirmation"*) is designed to prevent. The stage-02 spec tagged a decision
as user-confirmed: *"TextClust primary, DBSTREAM fallback (USER CONFIRMED)"*
(`audit-architecture.md:399`, `audit-goal.md:43`). The build then silently deviated from it
(hardcoded DBSTREAM only), and `audit-goal.md:43,179-187` flags this as a **spec violation of a
user's confirmed decision** — treating the "USER CONFIRMED" tag as ground truth. It took a
*third* audit pass (`bertopic-pipeline-auditor`, spawned specifically to challenge prior
claims rather than build on them) to trace the tag back to its actual origin and discover it was
never true: *"the fix-pass deviation is architecturally sound. The spec's 'USER CONFIRMED'
annotation ... is **incorrect** — the user has not actually confirmed TextClust primary. The
[handoff] lists this as an open OQ-1 awaiting user decision"*
(`bertopic-pipeline-auditor/learning-summary.md:14`). An inference got labeled "confirmed,"
propagated through a spec and two build passes as if it were explicit, and was only caught by an
agent whose entire mandate was to distrust labels and re-derive provenance. This is a strong,
concrete justification for PLAN.md's "no implicit node ever self-promotes" rule — it is not a
hypothetical failure mode, it happened in this codebase's own history.

### 9. Two more instances of code confidently asserting a false property about itself

- `pipeline/steps/stream_topics.py:103` (per `audit-architecture.md:146-163`): a code comment
  reads `# deterministic int from UUID` next to `hash(topic.id) % (2**31)` — but Python's
  `hash()` is process-salted by default, so the value is *not* deterministic across runs. The
  comment asserts a property the code does not have.
- `pipeline/llm.py:170-179` (per `stage-01-cold-start/audit.md:141-144`): a function's comment
  claims it "Map[s] numeric string indices back to actual topic ids," but the implementation
  maps indices to *names*, not ids, and the real mapping happens elsewhere. Dead code with a
  misleading self-description.

Both are the same shape of error as a chat agent narrating an inferred conclusion as if it were
established fact — just happening inside code comments instead of conversation turns. Worth
naming as a distinct anti-pattern class: **agent-authored artifacts (not just agent speech) can
carry unverified claims about their own behavior**, and nothing about being "just a comment"
makes it exempt from the same explicit/implicit discipline.

### 10. Numbered decision/question ledgers as a cross-session bookkeeping convention

Independently invented in at least three threads: `decisions.md` (41 locked decisions, numbered),
`diagram-agent/session-summary.md` (`D1`–`D14` decisions, `Q1`–`Q17` open questions, carried
forward diagram-to-diagram, e.g. `session-summary.md:287-292`), and `shared/mvp-thought-map.md`
(`D1`–`D15`, §13). All three use the same shape: a stable ID that outlives any single session,
survives being referenced by a *different* agent instance later, and is never silently
renumbered. `diagram-agent/CHANGELOG.md:10` states the rule outright: *"Diagram numbering is
stable once written — appending a new diagram gets the next number; never renumber."* This is a
cheap, low-tech precursor to a provenance ledger's node IDs: an identifier that different agents
across different sessions can cite unambiguously.

### 11. Cumulative "learning-summary" separate from raw session log

Both `diagram-agent/learning-summary.md` and `bertopic-pipeline-auditor/learning-summary.md`
exist specifically so a **fresh** agent spawn (no memory of prior sessions) can self-orient by
reading one condensed file instead of replaying the full chronological log
(`diagram-agent/entry.md:16` explicitly points a fresh spawn at it). The two files this thread
maintains per agent variation — a chronological log (append-only, full detail, e.g.
`session-log.md`, `CHANGELOG.md`) and a cumulative summary (overwritten each session, condensed,
e.g. `learning-summary.md`) — are structurally different documents serving different consumers:
the log is for audit/debugging, the summary is for bootstrapping a new agent cheaply.

### 12. Write-time sync invariant, fail-loud rollback (`shared/mvp-thought-map.md:199-224`)

Not about the ledger's gating, but a reusable engineering pattern: every write that must keep
two stores consistent (a chunk file and its graph node) is checked *at write time*, atomically,
and rolled back entirely on any partial failure — `mvp-thought-map.md:209-216`: *"Write-time,
atomic, fail-loud... On any failure: roll back... raise a loud error. No background
reconciliation in MVP."* Cheap and simple, and it means an inconsistency can never silently
persist past the operation that created it — the same "catch it before it's committed" instinct
the new project wants at the tool-call level.

### 13. Explicit sub-agent orchestration rules, stated once and passed verbatim into every spawn

`shared/investigation-handoff.md:35-75` and `diagram-agent/session-summary.md:10-23` both
maintain a standing "Operational Rules" block that is copy-pasted into every sub-agent spawn
rather than re-derived per spawn: no autonomous spawning without user gate
(`investigation-handoff.md:39`), lazy exploration — "build a MAP of the domain only... do not
read [files] in full" before working (`session-summary.md:19,42-61`), sub-agents write full
output to file and return only flags/concerns to the orchestrator, never full data dumps
(`investigation-handoff.md:73-75`), and a documented heuristic for when to respawn-with-context
vs fresh-spawn-for-unbiased-synthesis (`investigation-handoff.md:51-54`).

## Anti-patterns the user identified

Quoted directly from `IMPLEMENTER_PROMPT.md:43-52` ("What to AVOID (anti-patterns)"):

> - **LiteLLM.** The `litellm` Python library is broken with Pydantic AI. Do NOT use
>   `litellm.embedding()` or `langchain_litellm.LiteLLMEmbeddings`. Do NOT reuse
>   `vector_rag.qdrant_embed.Embedder` (it uses LiteLLM).
> - **`ModelRetry` after `run_sync()`.** The broken pattern at `pipeline/llm.py:134-138`. The
>   CORRECT pattern is inside `@agent.output_validator` (per `rag_handle2.py:262-312`).
> - **Falkor / any graph database.** Dropped entirely.
> - **Reusing `vector_rag.qdrant_embed.Embedder`.** It uses LiteLLM. Use
>   `langchain_ollama.OllamaEmbeddings` instead.
> - **3-vector Qdrant pattern (sparse + multi).** Backlog. MVP is dense only.
> - **Pydantic AI versions before 1.107.** Verify the current API; the v1.107+ API is what
>   works per the stage 01 verification.
> - **Hardcoding model names, URLs, or credentials.** Use env vars (per spec 01).
> - **Topic ingestion (RAG steps 5-9).** Out of scope for this build.

Most of these are library/dependency-specific (LiteLLM breakage, Falkor removal, embedding
backend choice) — domain noise for the new project. The one with lasting behavioral relevance
is **"`ModelRetry` after `run_sync()`"**: an agent implementing a retry-on-validation-failure
mechanism placed the check *after* the point where the framework can still act on it, producing
code that looks correct (imports `ModelRetry`, sets `retries=2`) but is silently a no-op — the
exception just propagates as a crash instead of triggering a retry. This exact bug was flagged
three separate times across the archive before being fixed for good: first in
`build/stage-01-cold-start/verification.md:47-79` ("Severity: Medium... `retries=2` is
effectively dead"), again in the stage-01 audit (`stage-01-cold-start/audit.md:116-137`,
"STILL OPEN"), and the fix was verified a third time in
`stage-02-streaming-design/audit-architecture.md:281-296`. The user's own words governing the
whole build thread (`session-log.md:11`) are also worth quoting as the master anti-pattern
directive: **"DO NOT CODE BEFORE YOU VERIFY WITH ME. NEVER ASSUME WHAT I WANT."**

Beyond the named list, the audits surfaced two more anti-pattern classes worth carrying into the
new project (documented in full under "Process & control techniques," items 8–9 above):
**an inference mislabeled as user-confirmed, then silently overridden and re-propagated as if
still confirmed** (the "USER CONFIRMED" TextClust incident), and **code comments/docstrings
asserting properties about their own behavior that are false** (the non-deterministic `hash()`
comment; the mismapping-but-claims-to-map dead code).

## Answers to the key questions

**1. Anti-patterns in `IMPLEMENTER_PROMPT.md`.** See "Anti-patterns the user identified" above
for exact quotes. Most are dependency-specific; the `ModelRetry`-outside-lifecycle pattern is
the one with general "looks correct, silently isn't" relevance, reinforced by three independent
audit catches.

**2. Bookkeeping format for keeping a build thread honest, and decided-vs-assumed separation.**
`decisions.md`'s `# | Decision | Source` table (quoting the user verbatim, or tagging
`inferred`/`derived`) plus its Locked/Open split, combined with `session-log.md`'s per-entry
"What I did" / "What I did NOT do" pairing, is the clearest precursor found. It is manual and
per-decision rather than automatic and per-tool-call, and it has no depth cap or hard-stop
gate — an inference, once written into `decisions.md`, could still be treated as settled by a
later reader without re-checking its Source column (which is exactly what happened with the
"USER CONFIRMED" TextClust decision — see item 8 above). That gap — nothing *forces* re-checking
the Source column before acting on a decision — is precisely the gap PLAN.md's automated,
gated ledger is meant to close.

**3. `audit/` under memory-build and stage-02's 4-angle audit.** See items 4 and 5 above. What
was audited: the memory-build audit covered correctness/accuracy of a built pipeline (pass 1)
then user-facing behavior (pass 2); the stage-02 4-angle audit covered goal-fit,
architecture, code correctness, and engineering readiness of a streaming topic-model build. What
failed: stage-02 failed on all four angles (runtime crashes, an unimplemented load-bearing
design decision, zero test coverage for the new modules, idempotency violations). What was
learned: adversarial, source-grounded, multi-angle audit reliably finds real bugs a single
"does it look done" pass misses — and even a two-pass audit of the *same* code from different
lenses (pass 1 vs pass 2 in memory-build) finds materially different, non-overlapping critical
issues.

**4. spec-01..08 decomposition principle.** Decomposed by *storage layer / pipeline stage*
(storage → Qdrant → embedder → agents → ingest → retrieval → MCP server → CLI+tests), with an
explicit dependency graph and enforced build order. Yes — this is explicitly a scope-drift
control technique: each section is independently testable and gated (`IMPLEMENTER_PROMPT.md:56-65,
116-127`), so an agent cannot silently carry unfinished work from section N into section N+1
without an intervening done-criteria check.

**5. `diagram-agent` iteration — what changed and why.** Five diagrams over two sessions. Session
1 established base conventions (dark theme, `flowchart TB`, subgraph-as-zone, shape vocabulary).
Session 2 (diagram 05, the "what-if" conceptual view) added two new conventions — a two-accent
palette (amber=selected, reddish=affected) and `classDef` over per-node `style` for diagrams with
15+ nodes — each justified in `CHANGELOG.md:33-51` and logged as `D13`/`D14`. Each diagram's
`CHANGELOG.md` entry documents Mermaid's hard limitations (no node-size-by-weight, no true
interactivity, no opacity/ghosting, no dynamic edge-thickness) and the workaround chosen for
each, plus explicit open questions carried into the next session. The iteration is genuine but
thin (five diagrams, incremental convention accretion) rather than a deep redesign loop.

## Salvage rating

### Directly reusable for the provenance-ledger project

- The `decisions.md` **Source-column discipline** (quote-or-tag-inferred, Locked vs Open) as a
  human-readable *companion view* onto the ledger — even once the ledger is automated, a
  rendered "Source" column per node is a good UX for the reconcile step.
- The **done-criteria-per-section gate** (`IMPLEMENTER_PROMPT.md:116-123`) as a template for what
  the ledger's rolling 5-call reconcile should actually check.
- `bertopic-pipeline-auditor/entry.md`'s **"Prime directive" verification checklist** — it is
  essentially a hand-written spec for "how do you tell if a claim is explicit or was silently
  promoted from inferred," directly transferable to writing the ledger's reconcile logic or to
  writing a test suite for it.
- The **"USER CONFIRMED" mislabeling incident** as a concrete regression-test scenario: write a
  test where an agent tags something as user-confirmed without a traceable quote, and assert the
  ledger (or a review pass) catches it.
- The **"What I did / What I did NOT do" per-turn pairing** as a lightweight discipline to adopt
  even before the ledger is built — cheap, and it already caught scope in this codebase.

### Good thinking material / adaptable

- The abandoned **two-log / event-sourced "compounding model"** (`session-log.md:169-256`): the
  user proposed tracking two logs — what the session-log agent *saw* vs what the memory-manager
  *considered but didn't surface* — reconciled by timestamp into an ordered event stream. This is
  thematically close to tracking implicit nodes that were touched but never promoted, though it
  was scoped for a completely different problem (retrieval quality) and was abandoned mid-design
  in favor of a simpler MVP before being built. Worth a skim if the ledger later needs a notion
  of "considered but not acted on."
- The **4-angle independent audit** structure (goal / architecture / coding / engineering) as a
  template for a periodic "provenance-ledger implementation" self-audit once that project has
  code to audit.
- **Numbered, never-renumbered decision/question IDs** (`D1`, `Q1`, …) as a convention for the
  new project's own design docs — PLAN.md already numbers its decisions 1–11 and its open
  questions 1–3; this pattern validates continuing that.
- The **cumulative learning-summary vs. append-only log split**, useful if/when this project
  spawns fresh sub-agents that need to self-orient cheaply.

### Dead, superseded, or domain-specific noise

- Everything BERTopic/River/Qdrant/Memgraph/topic-modeling-specific: the entire `shared/`
  research corpus (13 papers, 4 research sessions), `bertopic-pipeline-auditor`'s actual
  findings content (OQ-1 TextClust vs DBSTREAM, centroid-shift semantics), `build/stage-02`'s
  runtime bugs (IPCA shape mismatch, `OnlineCountVectorizer` incompatibility). None of this
  transfers to a LangChain `bind_tools`-gating project.
- The LiteLLM-is-broken / Ollama-embedding-backend decision thread in `memory-build` — pure
  dependency trivia for a now-superseded stack.
- The five `.mmd` diagram files' actual visual content — the *conventions* (item 10/13 above) are
  worth keeping, the diagrams themselves are about a topic/concept graph unrelated to this
  project.
- The "SaaS sprawl vs personal-use" product-fit analysis (`shared/product-fit-summary.md`) — a
  business-model exploration for the older project's job-seeking anchor, no technical carryover.

## Open threads & contradictions noticed

- **"Accepted" bulk defaults vs individually-confirmed decisions.** `decisions.md:109-117` marks
  8 open questions (Q1–Q8) as `**accepted**` on the strength of one user sentence — *"Those
  defaults are fine"* — applied to all 8 at once. Under PLAN.md's depth-0/1/2 model, is a single
  blanket sentence sufficient provenance to mark 8 separate defaults as depth-0 explicit, or
  does each need to be depth-0 individually with the blanket sentence merely evidence of consent?
  This exact scenario (a bundle acceptance) isn't addressed by PLAN.md's current open questions
  and is worth adding to them.
- **The two-log/compounding-model thread was abandoned without an explicit "we're dropping this"
  decision.** It simply stops being referenced once the MVP pivots to 3 Qdrant collections
  (`session-log.md:369-407`). Nothing in `decisions.md` marks it superseded; a reader who only
  skims `decisions.md` and not the full `session-log.md` chronology would not know it was ever
  proposed. This is itself an instance of an idea silently falling out of scope rather than being
  explicitly closed — the same failure mode PLAN.md's "session is done when every implicit node
  is closed out" completion criterion targets.
- **Audits disagree with each other's severity, not just their findings.** Stage-02's `coding`
  audit calls the OnlineCountVectorizer bug a collateral fix once IPCA is fixed
  (`audit-coding.md:137-141`), while `bertopic-pipeline-auditor/learning-summary.md:47` later
  flags this exact claim as "plausible but unverified at scale." Neither is wrong, but it shows
  that even adversarial audits can converge on an assumption without full verification if no one
  is specifically tasked with re-checking *that* claim — an argument for the ledger's
  no-self-promotion rule applying to audit conclusions too, not just chat-agent inferences.

## Best pointers

- `/workspaces/langchain-claude-test/agent_framework/agent-workspace/memory-build/decisions.md` —
  best worked example of a Source-traced decision ledger.
- `/workspaces/langchain-claude-test/agent_framework/agent-workspace/memory-build/IMPLEMENTER_PROMPT.md` —
  best worked example of a single-file build-orientation contract with anti-patterns baked in.
- `/workspaces/langchain-claude-test/agent_framework/agent-workspace/memory-build/session-log.md` —
  best worked example of the "did / did NOT do" scope-boundary discipline (read the full file;
  the pattern repeats at every dated entry).
- `/workspaces/langchain-claude-test/agent_framework/agent-workspace/bertopic-pipeline-auditor/entry.md` —
  best worked example of an adversarial-verification brief; directly portable to any "audit the
  ledger's own output" task.
- `/workspaces/langchain-claude-test/agent_framework/agent-workspace/memory-build/audit/HANDOFF.md` —
  best worked example of a two-pass audit that deliberately re-examines the same artifact from a
  different lens and finds new critical issues each time.
- `/workspaces/langchain-claude-test/agent_framework/agent-workspace/bertopic-pipeline-auditor/learning-summary.md:13-14` —
  the "USER CONFIRMED" mislabeling incident; the single best piece of evidence in this slice for
  why PLAN.md's no-self-promotion rule is necessary, not merely cautious.
- `/workspaces/langchain-claude-test/agent_framework/agent-workspace/build/stage-02-streaming-design/audit-goal.md` —
  best worked example of a FAIL verdict grounded in an actually-run reproduction, not inference.
