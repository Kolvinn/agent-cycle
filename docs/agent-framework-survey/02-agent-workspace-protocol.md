# 02 — The agent-workspace operating protocol

> Survey of `/workspaces/langchain-claude-test/agent_framework/agent-workspace/`. Read-only pass;
> nothing under `agent_framework/` was modified. All paths below are relative to that directory
> unless given in full.

## Scope covered

- `rules.md`, `registry.md` (full)
- `orchestrator/entry.md` + `session-handoff-s3.md`, `-s6.md`, `-s7.md`, `-s8.md`, `-s9.md`, `-s10.md` (full)
- `system-thinker-build/entry.md`, `deprecated.md`, `learning-summary.md`, `handoff-for-next-system-thinker.md`, `handoff-build-folder-rundown.md` (~lines 1–441 of 614; the tail covers stage-02 fix-priority detail already summarized upstream in the file), `handoff-memory-build-rundown.md`, `handoff-pipeline-memory-rundown.md` (full)
- `system-thinker-bertopic/`, `system-thinker-cobweb/`, `system-thinker-recombination/`: `entry.md` + `learning-summary.md` full; `output/` skimmed via directory listing + the learning-summaries' own descriptions of each output file (not opened individually — their content is domain research, out of scope for this slice's questions)
- `implementer/entry.md`, `investigator/entry.md` (full)
- `pydanticAI.txt` — characterised, not read in full (see below)

Not opened in this pass (out of assigned slice): `diagram-agent/`, `bertopic-pipeline-auditor/`, `build/graph-rag-design/protocol/*` contents beyond the rundown's description, `memory-build/spec-*.md` and `audit/findings/*` contents beyond the rundown's description, `shared/*`. Where these are relevant to an answer below, I cite them as reported by the rundown documents I did read, not as directly verified — flagged inline.

## Map

```
agent-workspace/
├── rules.md              — the operating manual (206 lines): mandatory checks, spawn rules,
│                            communication protocol, 17 lessons, environment rules
├── registry.md            — task-ID ledger for every agent spawn across ~11 sessions
├── orchestrator/
│   ├── entry.md            — the ONE evergreen doc; rewritten every session to reflect current
│   │                          state (goals, settled findings, open gates, "what to do next")
│   └── session-handoff-s{3,6,7,8,9,10}.md
│                            — append-only, per-session narrative record (why, not just what)
├── system-thinker-build/   — the "build thread" specialist; deepest protocol instrumentation
│   ├── entry.md             — grounding frame (goal-evolution phases 1–4, scope, "the whys")
│   ├── learning-summary.md  — cumulative knowledge state, Session 1 through Session 11
│   ├── deprecated.md        — superseded-code log (date | file:line | reason | delete-stage)
│   └── handoff-for-next-system-thinker.md, handoff-build-folder-rundown.md,
│       handoff-memory-build-rundown.md, handoff-pipeline-memory-rundown.md
│                            — peer-to-peer (same-variation) handoffs + file-search rundowns
├── system-thinker-{bertopic,cobweb,recombination}/
│                            — domain-expert variations; entry.md + learning-summary.md +
│                              output/ (research artefacts — content is domain-specific,
│                              not protocol-relevant)
├── implementer/entry.md    — code-writer role definition (never became "active" in the sense
│                              of getting its own learning-summary.md — it's spawned fresh
│                              each time from a spec, so it doesn't accumulate persistent state)
├── investigator/entry.md   — ephemeral survey/read role (renamed from "explorer" — see below)
└── pydanticAI.txt           — a 211-line link index into pydantic.dev's docs tree, nothing more
```

The protocol has two visible "eras": a **research/investigation era** (Sessions 1–7, RAG-algorithm
literature review, CobwebTM vs BERTopic comparison, what-if mechanism analysis) and a
**build era** (Sessions 8–11, iterative pipeline construction: cold-start → streaming ingest →
memory/concept-extraction sub-pipeline). The scaffolding (`rules.md`, `registry.md`, the
entry/learning-summary/handoff triad) was invented during the research era and *hardened* during
the build era, where the cost of an ungoverned agent (broken builds, false-green tests, silently
deviated specs) became concrete and expensive.

## The protocol, reconstructed

### `entry.md` (per-variation)

**What it is:** a fixed identity card for one agent variation — its domain, the skills it must
load, an ordered reading list ("read these first" / "your own work" / "other agents' work" /
"the investigation context"), an explicit **role boundary** ("What You Do" / "What You Don't Do"),
and a communication protocol (what goes to a file, what comes back to the orchestrator).

**Failure it prevents:** role bleed. Concretely: a system-thinker writing code
(`implementer/entry.md:44-46`: "You do NOT make architectural decisions... You do NOT challenge
the spec's design... you flag concerns, but you implement as specified"), an investigator doing
synthesis (`investigator/entry.md:33-36`: "You do NOT do analysis or synthesis... You do NOT
make architectural recommendations — you report what you find, not what should be done"), or an
orchestrator doing file-level work itself (`rules.md:47`: "You do not design, code, explore, or
review. You pass responsibility to agents"). It also prevents context blow-up: the entry file's
reading list is deliberately curated ("point to files for framing context — don't re-inject
everything," `rules.md:27,71`), so a fresh spawn self-orients from a handful of named files
instead of the orchestrator pasting everything into the prompt.

### `learning-summary.md` (per-variation)

**What it is:** the agent's own cumulative internal state — "what it knows, what it's figured
out, what it's uncertain about, what it should focus on next" (`rules.md:96-99`) — explicitly
distinguished from a session summary living in `docs/`. It is *appended to*, not rewritten,
across the life of a variation (`system-thinker-build/learning-summary.md` runs from a
"Session 3" pressure-test update through a "Session 11 Final Update," each section left in place
with `SUPERSEDED` markers where a later pass overrode an earlier one, e.g.
`system-thinker-build/learning-summary.md:312`: "> **SUPERSEDED** by 'Session 11 Final Update'
below... The final session update below is the source of truth.").

**Failure it prevents:** the loss of accumulated domain reasoning every time the underlying agent
session ends. This is the single most load-bearing piece of the whole protocol, because the
project's own operating model made the *cheaper* option (fresh-spawn) the *default*: "Fresh-spawn
over respawn for system thinkers... 'the old sessions are getting bogged down' — respawning with
the same task_id carries heavy context. Fresh-spawn with self-orientation via the entry.md is
cleaner" (`session-handoff-s10.md:213`; codified as a rule at
`orchestrator/entry.md:43-45`, "Spawn methodology (user's rule from S9)"). Without
`learning-summary.md`, fresh-spawn-as-default would mean re-deriving weeks of domain analysis
every session. With it, a fresh spawn reads one file and picks up where the last one left off
(`rules.md:99`: "A fresh spawn reads the learning summary to self-orient without orchestrator
re-injection").

### Handoffs — two distinct kinds, doing two distinct jobs

1. **Orchestrator-to-orchestrator, per-session** (`session-handoff-s{3,6,7,8,9,10}.md`). This is
   the *only* continuity mechanism across sessions at the top level — the orchestrator is
   explicitly "not respawned — it is the persistent entry point. The next orchestrator reads
   `agent-workspace/orchestrator/entry.md` first" (`registry.md:23`). Each handoff carries a
   fixed shape that visibly hardened over time: Session 3's handoff (`session-handoff-s3.md`) is
   mostly an executive summary and a file table; by Session 6 it has grown a
   "MANDATORY READ FOR NEXT ORCHESTRATOR" block of numbered top-priority instructions
   (`session-handoff-s6.md:12-29`); by Session 7 it adds "The Conceptual Shifts (MUST
   internalize)" as a named section; by Session 9/10 it has a full "What I Learned (Orchestrator
   Self-Assessment)" retrospective with "What went well / What I missed / What I improved"
   (`session-handoff-s7.md:224-236`). The **failure it prevents**: a fresh orchestrator either
   silently re-opening settled questions (explicitly warned against — "Do not re-open design
   questions that are settled. Don't re-derive the workflow," `orchestrator/entry.md:245`) or
   missing a hard constraint the user stated once, weeks earlier, that never got written into a
   living spec (e.g. `session-handoff-s3.md:184`, "Do not re-couple tier into the state graph.
   This is the load-bearing separation").

2. **Peer-to-peer, same-variation** (`system-thinker-build/handoff-for-next-system-thinker.md`).
   A finer-grained instance of the same idea, invented specifically for the build thread's
   highest-complexity handoff (from the agent that shipped the "mutator agent" to whichever
   instance designs the next stage). It front-loads exactly the things a generic
   `learning-summary.md` doesn't capture well: precisely which skills to load and which *not* to
   load and why (`handoff-for-next-system-thinker.md:13-29`), a numbered "Behavior contract,"
   and — notably — a first-person log of **corrections the user made to the author's own design**
   in-session, generalised into a rule for the successor
   (`handoff-for-next-system-thinker.md:122-131`: "The user corrected me four times on the
   mutator design before I got it right... Generalise: for the live test, the extractor agent
   should be given a similar role split"). This is the protocol's closest thing to a structured
   self-correction record — but it's ad hoc prose, not a queryable ledger (see Key Question 2).

### `registry.md`

**What it tracks:** every agent spawn's task ID, keyed by variation, with a one-line description
of what that spawn did or found, organised into "Active Agents" (currently-respawnable, with
task_id + domain + skills), "Ephemeral Agents" (investigator — never respawned), "Available but
Not Yet Active" (implementer), and a chronological "Spawn History" table per session
(Sessions 7–11, `registry.md:52-113`).

**Why:** (1) it is the *only* way to decide respawn-with-context vs fresh-spawn-with-entry-file
(`rules.md:60-64`, "Respawn when... Fresh spawn when..."); (2) it prevents duplicate or
conflicting concurrent work (`rules.md:20`: "Check `agent-workspace/registry.md` for existing
task IDs (respawn vs fresh-spawn decision)"); (3) it is a project-history audit trail that
substitutes for conversational memory the orchestrator itself doesn't have across sessions — e.g.
`registry.md:14`, "Spawn was cancelled — user pivoted to v2 design mid-flight" is the *only*
surviving record of that abandonment; nothing else in the repo notes it.

### `rules.md`

The operating manual, read by every agent before doing anything (`rules.md:3-4`). Structurally it
is: (0) an ordered "mandatory checks" checklist (life-cycle-ordered: before starting work → before
spawning → in every spawn prompt → after every spawn → the validation cycle), (1) purpose,
(2) orchestrator rules, (3) spawning rules, (4) communication protocol per agent type,
(5) 17 numbered lessons learned, (6) agent types/variations, (7) file conventions,
(8) environment rules. It is the single document every other document in the folder assumes has
already been read.

## Answers to the key questions

### 1. What is the entry/learning-summary/handoff triad actually FOR?

Three different memory horizons for three different failure modes:

| Artefact | Horizon | Failure it guards against |
|---|---|---|
| `entry.md` | Static (per-variation identity) | Role bleed; context over-injection; wrong output shape (code from a thinker, opinions from an investigator) |
| `learning-summary.md` | Rolling (within one variation, across many spawns) | Losing accumulated domain reasoning every time a session ends, especially now that fresh-spawn is the *default*, not the exception |
| `session-handoff-sN.md` / peer handoff | Point-in-time snapshot (one per session boundary) | The next *orchestrator* — who has no other continuity mechanism at all — re-opening settled questions, missing load-bearing constraints, or repeating a named mistake |

None of the three overlaps with the others in practice: entry.md never changes once written
(except to append a lesson), learning-summary.md is append-only within a variation's lifetime,
and the handoff is a one-shot artefact written at a session's end and never edited again (a new
one is written next session; old ones stay as historical record — `orchestrator/entry.md` itself,
by contrast, *is* rewritten each session, e.g. `registry.md`'s modified-files lists at
`session-handoff-s8.md:137` and `session-handoff-s9.md:224`, "rewritten for next session").

### 2. Does `rules.md` resemble provenance tracking, assumption-flagging, explicit/implicit separation, or checkpointing?

**Partially, and in one specific place, strikingly.** Nothing in `agent-workspace/` uses the
words "explicit" or "implicit" in the provenance-ledger sense — this is not a literal ancestor of
`PLAN.md`'s design. But several independently-arrived-at mechanisms rhyme with it closely enough
to be worth citing as prior art:

- **Assumption-flagging (general form).** `rules.md:13`: "if you cannot verify, flag it and ask
  the user rather than assuming... do NOT rely on stale knowledge for implementation-critical
  decisions." And `rules.md:53`: "The user AND agents are fallible. Be rigorous, attentive to
  detail. Challenge assumptions in ALL conclusions (agents and users)." This is scoped to library
  API knowledge and general rigor, not to the provenance of a specific tool-call target — but the
  underlying ethic ("if unverified, don't assert it as fact — ask") is the same one `PLAN.md`
  generalises into a structural gate.

- **No self-promotion of the unconfirmed / upward-only permission flow.** `rules.md:48`: "No
  autonomous spawns. Every spawn must be gated on user approval. No autonomous pipelines.
  Permissions flow upward, never assumed downward." This is structurally the same shape as
  `PLAN.md` item 10 ("No implicit node self-promotes... every implicit requires the user's own
  confirmation") — applied to *agent actions* (spawning) rather than to *information* (ledger
  nodes), but the same refusal to let anything proceed on an unconfirmed basis.

- **Checkpointing — present, but coarse-grained, never tool-call-counted.** The closest analogues
  to `PLAN.md`'s "reconcile every 5 tool calls" are all *stage*- or *session*-grained, not
  *call*-grained: "Track concept drift. Periodically check that you and the user are on the right
  track" (`rules.md:51`); "No massive builds... Gate each stage on user approval"
  (`rules.md:35`); the four-angle audit run after every build stage
  (`orchestrator/entry.md:36-38`). There is no mechanism anywhere in this slice that reconciles
  state after a fixed count of actions. This is a genuine gap relative to `PLAN.md`'s design, not
  a near-miss.

- **The closest concrete precursor — a "Source" column on locked decisions.** In
  `system-thinker-build/learning-summary.md:320-334` ("Session 11 Update: Live Test Concept
  Extraction"), the 13 user-locked decisions are recorded as a table with an explicit `Source`
  column, and — critically — one entry cites *another decision* as its source, one hop removed
  from the user:
  ```
  | D6 | New Qdrant collections: `live_test_concepts_v1` and `live_test_relationships_v1`
        (additive, doesn't touch existing) — was v1: `concepts_live` / `relationships_live`
        | Derived from D3 (revised) |
  ```
  and the escalation rule attached to it:
  ```
  | Dev4 | If implementer wants to refactor/delete something not in scope, they MUST stop and
          bubble up. The bubble-up process involves me + user + another system thinker to assess
          system impact, then approve/disapprove | User D3 caveat |
  ```
  (`system-thinker-build/learning-summary.md:334`). This is a working, if informal and
  one-off, prototype of exactly the ledger `PLAN.md` proposes: each decision node names whether
  it traces to the user directly (depth 0) or to another decision (depth 1, "Derived from D3"),
  and anything that would go a hop further than that — an implementer wanting to act outside the
  locked scope — hits a hard stop requiring multi-party sign-off before it can continue
  (`Dev4`). I did not find this "Source column" convention used consistently elsewhere in the
  repo (e.g. I did not verify whether `memory-build/decisions.md`'s "41 locked decisions" carry
  the same column — out of this slice's reading list); treat it as a single strong data point,
  not a repo-wide convention.

- **What's absent.** There is no tracked distinction between "the user said this" and "an agent
  inferred this and it's now being treated as settled" anywhere at the level of ordinary prose
  claims — only at the level of formally tabled decisions in one file, in one late session. The
  "10 settled findings" in `orchestrator/entry.md:83-94` and the "8 open gates" at
  `orchestrator/entry.md:98-111` are the closest repo-wide analogue to an explicit/pending split,
  but they don't record *why* something is settled (user directive vs. thinker-derived
  conclusion vs. audit consensus) — they're a flat list, not a ledger with provenance edges.

### 3. What does `registry.md` track and why?

Answered above under "The protocol, reconstructed." In one line: it tracks *agent invocations*
(who was spawned, with what task ID, doing what, with what outcome) — an audit trail of activity,
not of information provenance. It is the mechanism that makes respawn-vs-fresh-spawn a real
choice rather than a guess, and it is the only persistent record of spawns that were cancelled or
superseded mid-flight.

### 4. What did the learning summaries actually learn? (concrete agent-failure lessons)

See the dedicated section below — there's enough material to warrant its own treatment rather
than folding it in here.

### 5. Did this protocol work?

Yes, with real cost, and with real catches. See "Did it work?" below.

## Lessons recorded about agent failure modes

`rules.md:134-150` is the canonical, protocol-level list (17 items, each traceable to a specific
incident). Grouped by failure category, with the sharpest ones quoted:

**Scope drift / over-claiming.**
- "we are getting carried away with investigations into deep topics" → produce the plain view
  *before* the mechanism-level detail (`rules.md:134`).
- "I like weighted connections" inflated by the orchestrator into "a weighted-probabilistic-
  connection architecture" — the user had to correct it back down. "Keep ideas at the level the
  user states them" (`rules.md:135`, also narrated in full at `session-handoff-s7.md:233`).
- "Structure, not capability" as a standing discipline against agents (and the orchestrator)
  letting documentation/code claim more than was actually built
  (`system-thinker-build/entry.md:26`, reinforced at `session-handoff-s9.md:249`).

**Context-economy violations (the orchestrator doing agents' work).**
- "Spawna system thinker to do this work, this is in direct violation of your content window
  maintenance" — the user's own words, verbatim, after an orchestrator read JSON files and ran
  curl itself instead of delegating (`session-handoff-s6.md:26`, codified at `rules.md:139`).

**Stale/unverified technical knowledge treated as fact.**
- "Agents have a horrible habit of relying on outdated training data and outdated skills to
  perform their work" — the up-to-date-verification directive that must appear in *every* spawn
  prompt (`rules.md:150`, `orchestrator/entry.md:25`). This is the protocol's most direct
  statement of `PLAN.md`'s core thesis ("every action... is a prediction, not an understanding")
  applied specifically to library-API knowledge.

**Identity/tooling confusion.**
- The custom `explorer` agent collided with a built-in `explore` agent; a prior orchestrator
  spawned the wrong one. Renamed to `investigator` across every config file and folder
  (`rules.md:19,146`; full incident narrated at `session-handoff-s8.md:18-22`).

**Premature closure / asking the wrong question at the wrong time.**
- Asking a scale-dependent question before the product was scoped got "no clue" as an answer —
  "the question doesn't apply yet" (`rules.md:141`, incident at `session-handoff-s6.md:227`).
- Presenting two hypotheses as separate when the user's own thinking had already converged them
  (`rules.md:140`, `session-handoff-s6.md:228`).

**Format violations.**
- Thinkers producing pseudocode instead of design rationale — corrected explicitly, then baked
  into every spawn prompt as "NO PSEUDOCODE — design rationale only"
  (`rules.md:149`, `orchestrator/entry.md:26`).

**Production evidence of "prediction, not verification" (not in rules.md, but the sharpest
concrete illustrations in the whole survey).** Two build-stage bugs are close to a textbook case
of an agent producing output *shaped like* the specification without verifying it actually
satisfied it:
- The stage-02 spec mandated the River clusterer be initialised with cold-start centroids as
  real micro-clusters plus a working `topic_mapper`. The implementer's build instead stored the
  centroids in a parallel dict the clusterer never reads — code that superficially matches the
  spec's shape but does nothing the spec required. Caught only by a dedicated architecture audit,
  not by the 26 passing unit tests (`handoff-build-folder-rundown.md:204`, "the 'extend' pattern
  is silently broken").
- The same spec mandated 768-dimensional centroid embeddings for cross-run topic identity
  (explicitly because Python's `hash()` is non-deterministic across runs). The implementation
  used `hash(topic.id) % (2**31)` anyway — the exact failure mode the spec existed to prevent,
  reintroduced silently (`handoff-build-folder-rundown.md:205`).
- Separately, in `memory-build`, a test suite reported "63/63 green" while a stray token (`Now`)
  silently prevented 7 tests from being *collected* at all — a false success claim that stood
  until a dedicated audit pass caught it (`handoff-memory-build-rundown.md:11,111`).

## Did it work?

**The gates caught real, serious problems** — this is the strongest evidence the protocol has
teeth, not just paperwork:
- The 4-angle audit (architecture / goal / coding / engineering, each a fresh, independent spawn
  against the same build) returned **FAIL on all four** for the stage-02 streaming build, and
  the four independent audits converged on the same root causes (IncrementalPCA crash, the
  pre-seeding no-op, zero test coverage on 75% of new code, a violated user-confirmed decision) —
  `handoff-build-folder-rundown.md:199-268`. Rules.md's own retrospective calls this out as a
  positive: "the 4-angle audit is valuable... The convergent FAIL verdicts... are robust"
  (`session-handoff-s10.md:215`).
- The `memory-build` audit found **5 CRITICAL bugs** in code that had shipped as "MVP built and
  verified, 63/63 tests pass," including a live PII/secret leak (`OPENAI_API_KEY=sk-...` stored
  verbatim and returned to the user in plain text — `handoff-memory-build-rundown.md:127,222-232`)
  and chat history that was persisted but never actually read by the retrieval path
  (`handoff-memory-build-rundown.md:125`). None of these were caught by the green test suite;
  all were caught by a dedicated adversarial "user-experience" audit pass built specifically
  because the plumbing-level audit alone wasn't judged sufficient.

**But the protocol also shows heavy, repeated churn, and some things it explicitly punted on
never got fixed:**
- `system-thinker-build/deprecated.md` is a literal deprecation ledger. Its second section
  records an entire schema redesign (v1 → v2) because "llama3.1:8b could not produce valid output
  even after 3 retries" against the original nested-schema design — a full rebuild, not a patch
  (`deprecated.md:13-26`).
- `system-thinker-build/learning-summary.md` contains a section explicitly marked
  `> **SUPERSEDED**` by a later section written the same session (`learning-summary.md:312`) —
  the protocol's own "locked" decisions got re-locked within hours.
- T3 (the tier-classification approach) was **fully reversed** after being treated as settled,
  when the user surfaced a cyclic-dependency bug the original design had missed
  (`learning-summary.md:21-36`; the agent's own retrospective: "My original T3 missed a
  structural problem... Approaches that 'resolve' cycles by smuggling them are not resolutions").
- An entire prior multi-session thread (the MVP/overhaul design, `session-handoff-s3.md`) was
  explicitly **paused and never resumed** two sessions later: "Do not spawn `architect_thinker`
  for state graph topology... The user explicitly said this thread 'goes technical too quickly'
  and 'assumes building is around the corner. Which it isn't'" (`session-handoff-s6.md:14`).
- A folder-restructuring side-quest consumed most of Session 9 before the user called it
  circular: "I believe thinking about this too much is us going around in circles"
  (`session-handoff-s9.md:245`) — an entire design thread abandoned mid-flight, not because it
  was wrong, but because the process had stopped converging.
- `pipeline/memory/models.py` stayed broken (`import Enum` instead of `from enum import Enum`,
  duplicate class definitions, an undefined `Concept` referenced elsewhere, `DataChunk`
  commented out) across at least three separate build efforts, each of which explicitly worked
  around it rather than fixing it — "Do NOT try to fix `models.py` as part of this stage"
  (`handoff-for-next-system-thinker.md:310`; full inventory of the breakage at
  `handoff-pipeline-memory-rundown.md:357-368`). The protocol's scope discipline (don't fix what
  you weren't asked to fix) is defensible in isolation, but the cumulative effect across sessions
  was persistent, load-bearing rot that every new agent had to independently rediscover and
  route around.
- Repeated, avoidable operational friction: the live-test failed **7 times in a row** for the
  same reason (an Ollama model not pulled) before anyone added a pre-flight check
  (`handoff-memory-build-rundown.md:146,238-244`), and the same missing-model failure mode is
  independently re-documented as a lesson in a *different* folder's handoff
  (`handoff-for-next-system-thinker.md:324-331`) — evidence that a documented lesson in one
  variation's files doesn't automatically propagate to another variation.
- The original 7-session research bet (a novel streaming-topic-model + supervised-meta-layer
  architecture, benchmarked as CobwebTM vs BERTopic) concluded "adds structure, not capability"
  and was, in effect, quietly set aside: the surviving build (`pipeline/`) uses plain
  BERTopic + River with no Cobweb code at all. The investigation wasn't wasted — it produced the
  honesty discipline ("structure not capability") that governs the later build — but the
  specific architecture it spent seven sessions evaluating did not ship.

**Net assessment:** the protocol did what governance protocols do — it didn't prevent mistakes,
it made them visible, bounded, and recoverable. The audit-gate mechanism specifically earned its
keep (catching a false "all green" claim and a live secrets leak are not small wins). But the
protocol never stopped an agent from confidently building the wrong thing in the first place;
every catch documented above happened *after* a full spec→build cycle, at the audit gate, not
before or during construction. That is exactly the gap `PLAN.md` is trying to close by moving the
gate earlier — to the point where a tool call's target is chosen, not to the point where a
finished artefact is reviewed.

## Salvage rating

### Directly reusable for the provenance-ledger project

- **The entry.md / learning-summary.md pattern**, as a template for any per-component onboarding
  doc the new project builds (e.g. per-module CLAUDE.md files): identity + explicit role boundary
  ("what you do" / "what you don't do") + curated reading list + communication contract. Proven
  through ~11 sessions of real multi-agent use.
- **The "Source" column / one-hop derivation citation pattern** at
  `system-thinker-build/learning-summary.md:320-334` — the closest thing in this codebase to a
  working ledger-entry schema (`{decision, source: "user" | "derived from <parent>"}`). Worth
  lifting as a concrete precedent when designing the ledger's node schema.
- **The "bubble up" hard-stop protocol** (`learning-summary.md:334`, Dev4/D3-caveat): "if you
  want to act outside the locked scope, STOP — don't act, don't guess, escalate for multi-party
  sign-off first." Structurally identical to `PLAN.md`'s depth-2 hard stop, independently
  invented for a different reason (scope creep, not reference chains) — good corroborating
  evidence the pattern generalises.
- **`rules.md`'s up-to-date-verification directive** (`rules.md:13`) — copy-adaptable text for a
  ledger "flag if unverifiable" clause: "if you cannot verify, flag it and ask the user rather
  than assuming."
- **The 4-angle parallel-audit pattern** (architecture / goal / coding / engineering, fresh
  independent spawns against the same artefact) — a reusable QA technique independent of the
  ledger idea, empirically proven to catch bugs unit tests missed
  (`handoff-build-folder-rundown.md:199-268`).
- **`registry.md`'s task-ID ledger shape** — a reusable model for logging agent invocations with
  enough metadata to support later audit, if the new project ever needs multi-agent orchestration
  on top of the ledger.

### Good thinking material / adaptable

- `handoff-for-next-system-thinker.md`'s full shape (one-paragraph summary → what I did →
  corrections I received, generalised → behavior contract → the new task → prioritised reading
  list → gotchas → open questions → recommended next steps) is good raw material for designing
  what a ledger "checkpoint reconcile" artefact should contain.
- "Structure, not capability" as a standing documentation discipline pairs naturally with the
  ledger's "don't let an unverified assumption pass as settled fact" ethic — worth carrying as a
  stylistic norm even without any code reuse.
- The convergent 4-way audit result (`session-handoff-s10.md:215`) is empirical support for the
  "double-run divergence" idea `PLAN.md` floats and explicitly leaves undecided (`PLAN.md`,
  Assumptions section) — cite this as a real-world data point if that idea gets revisited.
- The session-handoff's own visible hardening from S3 (thin summary) to S10 (mandatory-checks
  front matter + full retrospective) is a useful case study in how much process scaffolding is
  actually needed — the answer here was "grows organically as failures accumulate," not
  "front-load everything on day one."

### Dead, superseded, or scratch noise

- All CobwebTM / BERTopic / River / graph-RAG domain content — a different problem domain
  entirely (streaming topic modeling for a RAG knowledge pipeline), not reusable for
  tool-call-gating.
- `pipeline/memory/graphing.py` (an unrelated Graphviz course/student demo left in the tree),
  the syntax-broken `mermaidpy.py`, the duplicate class definitions in `models.py`, and the
  orphaned `probe_*.py` scripts in `tests/memory/` — explicitly flagged as dead/broken in the
  audits themselves (`handoff-pipeline-memory-rundown.md:370-384`).
- Most of the stage-01/stage-02 pipeline specifics (the 6-table Postgres schema, the Qdrant
  collection layout, the River-algorithm choice) — tied to the old RAG pipeline's domain, not
  transferable.
- `pydanticAI.txt` — a 211-line index of links into pydantic.dev's documentation tree, nothing
  more. Zero standalone content value; it was a fetch-list for `context7`-style lookups, not
  reference material in itself.

## Open threads & contradictions noticed

1. **"No autonomous spawns" (letter) vs. observed practice.** `rules.md:48` states every spawn
   must be individually gated on user approval, but the registry's spawn-history tables show long
   runs of same-session respawns; the more plausible reading is that approval was granted
   per-stage, not per-spawn. The documents don't reconcile this explicitly.
2. **Did "structure, not capability" actually change the build, or just get intellectually
   filed away?** The finding is treated as load-bearing throughout Sessions 6–10, but the
   surviving pipeline is a straightforward BERTopic+River build with no visible trace of the
   CobwebTM/meta-layer machinery the finding was originally about. Whether the seven-session
   investigation materially shaped the final design, or was largely superseded by the pivot to
   "internal daily-utility tool," is not resolved in the documents I read.
3. **Two parallel "settled" registries with different granularity.** `orchestrator/entry.md`'s
   "10 settled findings" and `system-thinker-build/learning-summary.md`'s "T1–T8 tensions" cover
   overlapping ground with different numbering and no explicit cross-reference — a minor but real
   inconsistency in how "locked" state was tracked.
4. **The Source-column provenance pattern is a single data point, not a convention.** I found it
   in exactly one file (`system-thinker-build/learning-summary.md:320-334`, Session 11). I did
   not verify whether other decision tables in the repo (e.g. `memory-build/decisions.md`'s "41
   locked decisions," out of this slice's reading list) use the same convention. Treat the
   parallel to `PLAN.md`'s ledger as suggestive, not as evidence of a repo-wide practice.
5. **No analogue anywhere to a fixed-cadence checkpoint.** Every reconciliation point in this
   protocol is stage- or session-grained; nothing counts actions. If the new project wants
   evidence that "checkpoint every 5 tool calls" is workable, this repo doesn't supply it either
   way — it simply never tried anything at that grain.

## Best pointers

- `agent-workspace/rules.md` — read in full before anything else; it's the one document every
  other artefact assumes has already been read.
- `agent-workspace/system-thinker-build/learning-summary.md:320-334` — the "Source" column /
  bubble-up precedent; the single most directly relevant few lines in the whole slice to the
  provenance-ledger project.
- `agent-workspace/system-thinker-build/handoff-for-next-system-thinker.md` — the richest example
  of the peer-handoff format, including the self-correction log at lines 122–131.
- `agent-workspace/orchestrator/session-handoff-s6.md` and `-s7.md` — read together, they show
  the handoff format's format hardening in real time and contain the sharpest quoted user
  corrections (`session-handoff-s6.md:26`, `session-handoff-s7.md:233`).
- `agent-workspace/system-thinker-build/handoff-build-folder-rundown.md:199-268` — the fullest
  concrete case study of the audit gate working (4/4 FAIL, convergent root causes) and of the
  "prediction, not verification" failure mode `PLAN.md` is designed around (the pre-seeding
  no-op, the non-deterministic `hash()` substitution).
- `agent-workspace/system-thinker-build/deprecated.md` — short, concrete evidence of real design
  churn (a full schema rebuild after 3 failed LLM retries).
