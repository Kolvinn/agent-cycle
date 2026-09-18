# 09 — The 36 installed skills

Survey of `agent_framework/.agents/skills/` (36 skill directories, 87 files) — the skills the
user installed into the OLD opencode-based repo. The NEW repo (`langchain-claude-test`)
installed only four of them (`langchain-middleware`, `langchain-dependencies`,
`langgraph-human-in-the-loop`, `claude-code-hooks`). This document reports what the other 32
contain, whether any of it is a working pattern the provenance ledger (see
`/workspaces/langchain-claude-test/PLAN.md`) can reuse, and what's dead weight now that the
stack is Claude Code + LangChain instead of opencode + Pydantic AI + Qdrant.

Read-only survey. Nothing under `agent_framework/` was modified.

## Scope covered

All 36 directories under `agent_framework/.agents/skills/`, read to the depth the task brief
specified: full read for the 8 priority items (`planning-with-files` in full including every
template/script; `critical-thinking-logical-reasoning`; `agent-development` +
`validate-agent.sh`; the three `deep-agents-*` skills; `langchain-middleware` diffed against the
new repo's copy; `langgraph-human-in-the-loop`; `opencode-primitives`; and a skim pass over
`find-skills`, `create-specification`, `refactor`, `python-code-review`,
`pragmatic-programmer`). The remaining 21 domain/stack skills were skimmed at frontmatter level
(name + description) only, per the brief — they are one-liners below, not analyzed further.

## Map

**Agent-control skills** (state, reasoning discipline, agent/skill authoring, orchestration):
- `planning-with-files/` — file-based session-state protocol with hooks and a completion check. See detailed section below.
- `critical-thinking-logical-reasoning/SKILL.md` — structured argument-critique method (fallacy-spotting, assumption-surfacing, burden-of-proof); reactive-only, not a background discipline.
- `agent-development/` — how to author a Claude Code subagent `.md` file (frontmatter + system prompt); `validate-agent.sh` lints structure only.
- `deep-agents-core/SKILL.md` — `create_deep_agent()` API reference: middleware menu, SKILL.md format, backend config.
- `deep-agents-orchestration/SKILL.md` — subagents via `task`, `write_todos` planning tool, `HumanInTheLoopMiddleware` interrupt/resume — all as a LangGraph-based deep-agents library API surface.
- `deep-agents-memory/SKILL.md` — StateBackend/StoreBackend/CompositeBackend persistence model for deep-agents filesystem tools.
- `find-skills/SKILL.md` — how to search/install skills via `npx skills`; a meta-skill for skill discovery, not agent behavior.
- `create-specification/SKILL.md` — template + convention for writing a `spec-*.md` requirements doc (REQ/CON/AC-numbered).
- `refactor/SKILL.md` — code-smell catalog and refactoring technique reference (JS/TS-flavored examples).
- `python-code-review/SKILL.md` — Python review checklist; references a `review-verification-protocol` skill and reference files (`clean-code`, `refactoring-patterns`) that **do not exist anywhere in this repo** — dangling cross-references from a shared skill pack.
- `pragmatic-programmer/SKILL.md` — Hunt & Thomas meta-principles (DRY, orthogonality, tracer bullets, design-by-contract, broken windows, reversibility, estimation) with a 0–10 scoring rubric.

**Stack/protocol skills** (LangChain/LangGraph — same domain as the new repo, worth comparing):
- `langchain-middleware/SKILL.md` — HITL middleware, custom `wrap_tool_call`/`before_model` hooks, Command-resume. Byte-identical in substance to the new repo's copy (see below).
- `langgraph-human-in-the-loop/SKILL.md` — `interrupt()`/`Command(resume=...)` mechanics, idempotency rules for pre-interrupt side effects, multi-interrupt resume-map pattern.
- `langchain-dependencies/SKILL.md`, `langchain-fundamentals/SKILL.md`, `langchain-architecture/SKILL.md`, `langchain-rag/SKILL.md`, `langgraph-fundamentals/SKILL.md`, `langgraph-persistence/SKILL.md` — general LangChain/LangGraph reference skills (agent construction, RAG pipeline, checkpointing). Same subject area as the new repo's stack but broader than v1 needs.
- `opencode-primitives/SKILL.md` — opencode's own skills/plugins/MCP/config system. Platform-specific, does not carry to Claude Code (see dedicated section below).

**Domain/stack skills** (skimmed only, one line each — not agent-control, not ledger-relevant):
- `architecture-designer/SKILL.md` — system design / ADR authoring / scalability planning.
- `architecture-patterns/SKILL.md` — Clean/Hexagonal/DDD backend architecture patterns.
- `async-python-patterns/SKILL.md` — asyncio/concurrency patterns for Python.
- `context7/SKILL.md` — fetch up-to-date library docs via the Context7 API.
- `fastapi-python/SKILL.md` — FastAPI best practices.
- `fastapi-templates/SKILL.md` — scaffolding production FastAPI projects.
- `mermaid-diagram-specialist/SKILL.md`, `mermaid-diagrams/SKILL.md` — Mermaid diagram authoring (two overlapping skills).
- `pydantic/SKILL.md` — Pydantic v2 validation.
- `pytest/SKILL.md`, `pytest-coverage/SKILL.md` — pytest usage and coverage-to-100% workflow.
- `python-expert/SKILL.md`, `python-patterns/SKILL.md` — general Python craftsmanship/decision-making.
- `qdrant/SKILL.md`, `qdrant-search-quality/SKILL.md`, `qdrant-vector-search/SKILL.md` — Qdrant vector-search setup, relevance diagnosis, production search. The new stack has no vector store at all.

## planning-with-files, in detail

This is the closest existing artifact in the whole `agent_framework/` slice to what PLAN.md's
ledger needs: durable session state plus an explicit completion criterion. It is **not** a
provenance tracker — it tracks task progress, not explicit/implicit source lineage — but its
file model, hook wiring, and completion check are a directly transplantable pattern.

**Files it is built out of** (`agent_framework/.agents/skills/planning-with-files/`):
`SKILL.md`, `reference.md` (Manus context-engineering principles it's based on), `examples.md`,
`templates/task_plan.md`, `templates/progress.md`, `templates/findings.md`,
`scripts/init-session.sh` (+ `.ps1`), `scripts/check-complete.sh` (+ `.ps1`),
`scripts/session-catchup.py`.

**State model — three files, one job each:**

| File | Role | Update trigger |
|---|---|---|
| `task_plan.md` | Phases, current phase, decisions, error table — "where am I / where am I going" | After each phase completes |
| `findings.md` | Research/discoveries, resources, visual/browser findings — "what have I learned" | After ANY discovery, mandatory every 2 view/search ops ("2-Action Rule") |
| `progress.md` | Chronological session log, test results, detailed error log — "what have I done" | Throughout the session |

The model is explicitly framed as `Context Window = RAM (volatile) / Filesystem = Disk
(persistent)` (`SKILL.md:81-85`) — anything that matters gets written to disk so it survives
context loss, and is pulled back into the attention window by re-reading the plan file before
decisions (the "recitation" principle from `reference.md:42-54`).

**Hooks wire the state model into the session automatically** (`SKILL.md:6-24`):
- `UserPromptSubmit` — if `task_plan.md` exists, dumps its head + `progress.md` tail into context before the turn starts, so an active plan survives a `/clear`.
- `PreToolUse` (matcher `Write|Edit|Bash|Read|Glob|Grep`) — cats the first 30 lines of `task_plan.md` before *every* matched tool call, i.e. the plan is force-refreshed into context on a per-call cadence, not just per-session.
- `PostToolUse` (matcher `Write|Edit`) — reminds the agent to update `progress.md` and flip phase status after any write.
- `Stop` — runs `check-complete.sh` and reports phase completion status as the session ends.

**`templates/task_plan.md`** — phase table with explicit status enum `pending → in_progress →
complete`, a `Key Questions` list, a `Decisions Made` table (`| Decision | Rationale |`), and an
`Errors Encountered` table (`| Error | Attempt | Resolution |`). Quoted structure:
```
## Phases
### Phase 1: Requirements & Discovery
- [ ] Understand user intent
- [ ] Identify constraints and requirements
- [ ] Document findings in findings.md
- **Status:** in_progress
```
**`templates/findings.md`** quoted:
```
## Research Findings
<!-- Key discoveries during exploration -->
-
## Technical Decisions
| Decision | Rationale |
|----------|-----------|
## Resources
<!-- URLs, file paths, API references -->
-
```
**`templates/progress.md`** quoted (5-Question Reboot Check, the session's own self-audit):
```
| Question | Answer |
|----------|--------|
| Where am I? | Phase X |
| Where am I going? | Remaining phases |
| What's the goal? | [goal statement] |
| What have I learned? | See findings.md |
| What have I done? | See above |
```

**What `check-complete.sh` actually enforces** (`scripts/check-complete.sh:1-47`): it is a
pure reporter, not a blocker — "Always exits 0 — uses stdout for status reporting" (line 3). It
counts `### Phase` headings as `TOTAL`, counts lines matching `**Status:** complete` /
`in_progress` / `pending` as `COMPLETE`/`IN_PROGRESS`/`PENDING` (falling back to an inline
`[complete]`/`[in_progress]`/`[pending]` format if the `**Status:**` form isn't found), and
prints `"ALL PHASES COMPLETE (C/T)"` only when `COMPLETE == TOTAL && TOTAL > 0`; otherwise it
prints `"Task in progress (C/T phases complete)"` plus a line per non-zero in-progress/pending
count. Because it always exits 0, it cannot itself stop the session — the `Stop` hook that
invokes it (`SKILL.md:21-24`) is designed to surface this text to the agent so *the agent*
decides whether to keep going; it is advisory, not enforced by the harness. `init-session.sh`
just scaffolds the three files with boilerplate phases if they don't already exist; it does no
validation.

**Direct relevance to the ledger's completion criterion.** PLAN.md's completion rule (item 6:
"every implicit node closed out into explicit") is structurally the same *shape* of check as
`check-complete.sh`'s phase-count comparison — a simple ratio/equality test over a markdown
file's own status markers, run from a `Stop` hook, reported as text rather than as a hard block.
The transplant is direct: replace "count `### Phase` headings, compare `complete` to `total`"
with "count implicit-node entries in a ledger file, compare `resolved` to `total`." The
`PreToolUse` re-injection pattern (cat the plan's head before every matched tool call) is also
directly reusable for keeping the ledger's open-implicit-count in the agent's attention window
between checkpoints, addressing PLAN.md's rolling-5-call reconcile (item 3/11) — though note
`planning-with-files`' hook fires the plan into context on *every* tool call, denser than the
ledger's every-5 cadence; the ledger would need a counter of its own (the skill has no per-N-call
counter primitive — its Stop-hook check-complete only fires at session end, not every 5 calls).

**What it does not give you.** No node/provenance model at all — `task_plan.md` tracks *task
phases*, not *where each fact or file reference came from*. No depth concept, no explicit/implicit
distinction, no hop-counting. The "Security Boundary" section (`SKILL.md:220-228`) is a useful
adjacent idea though: it explicitly separates untrusted external content (must go to
`findings.md` only) from the auto-injected `task_plan.md`, on the grounds that repeatedly-injected
content is a high-value prompt-injection target — this is the same class of risk-shaped thinking
the ledger's "no implicit self-promotion" rule addresses, applied to a different attack surface.

## critical-thinking-logical-reasoning

Full text at `agent_framework/.agents/skills/critical-thinking-logical-reasoning/SKILL.md`. It
is scoped narrowly: "when you are explicitly asked to critically analyse written content such as
articles, blogs, transcripts and reports **(not code)**" (line 3) — a reactive, user-invoked
critique skill, not an always-on reasoning discipline the agent applies to its own inferences.

It does impose real discipline once invoked: state the argument before critiquing it (line 14),
separate conclusions from supporting points (line 15), "surface hidden assumptions — what must
be true for this argument to hold?" (line 19), and "acknowledge uncertainty in your own analysis
— flag where your critique depends on assumptions" (line 49). The output structure forces a
"Questions to Probe" section (line 33) rather than letting an unresolved ambiguity pass silently.

**Relevance to PLAN.md Open item 1** (an agent overreaching from a single document with no
second tool call to gate): this skill's assumption-surfacing step is the right *shape* of
discipline for that gap, but it doesn't close it. It's triggered only for explicit
critique-an-argument requests on prose content, and it critiques *someone else's* argument, not
the agent's own chain of inference while doing unrelated work. It would need to become a
standing self-check ("what did I just assert that wasn't stated in what I read?") applied after
every read, not a skill invoked on request, to actually plug that hole. As installed, it does not
address item 1.

## Human-in-the-loop and middleware skills

**`langgraph-human-in-the-loop/SKILL.md`** is the most directly relevant piece of stack material
in this whole slice to PLAN.md's depth-2 gate. The mechanism: `interrupt(value)` pauses graph
execution and surfaces `value` to the caller under `result["__interrupt__"]`; `Command(resume=
value)` resumes, and the resume value becomes `interrupt()`'s return value inside the paused node
(lines 9-13, 27-30). Three hard requirements: a checkpointer, a consistent `thread_id`, and a
JSON-serializable interrupt payload (lines 17-24). Critically: **on resume, the node re-runs from
its beginning** — all code before `interrupt()` re-executes, so any side effect placed before it
must be idempotent (upsert, not insert) or moved after the interrupt (lines 31, 355-430). This
maps almost exactly onto PLAN.md's depth-2 gate (item 4: "the agent must return to the user...
needs explicit approval before continuing") — a depth-2 tool call is precisely a node that should
call `interrupt({"depth": 2, "proposed_call": ..., "chain": [...]})`, block until
`Command(resume={"approved": bool})` comes back, and route to either proceed (depth-1, logged) or
drop the thread (PLAN.md's diagram: `Ask -->|denied| Back["Drop this thread"]`). The multi-interrupt
resume-map pattern (lines 250-349) is relevant if depth-2 gates can fire on parallel branches.

The catch, already flagged correctly in PLAN.md item 8: this is a **LangGraph** primitive, not a
LangChain-`bind_tools`-via-`ChatClaudeCli` primitive. `langchain-claude-cli`'s model defers tool
execution to caller code without necessarily running inside a LangGraph `StateGraph` with a
checkpointer. If v1's gate wraps the returned `tool_calls` directly in plain caller code (as item
8 concludes), this skill's `interrupt()`/`Command` machinery doesn't apply unless the ledger's
gate logic is itself built as a LangGraph node — which would be a bigger architectural commitment
than "wrap the returned tool_calls." Read as a reference for *shape* (pause, surface state,
resume-with-decision, idempotent pre-pause effects), not as directly droppable code for v1.

**`langchain-middleware/SKILL.md`** covers the same interrupt/resume contract one layer up, via
`HumanInTheLoopMiddleware(interrupt_on={...})` on `create_agent()`, plus six custom middleware
hooks — `wrap_tool_call`/`wrap_model_call` (`(request, handler)`, call `handler(request)` to
proceed or return early to short-circuit) and `before_model`/`after_model`/`before_agent`/
`after_agent` (`(state, runtime)`, inspect/modify state) (`SKILL.md:229-317`). **This is the
shape v1's gate should take**: since PLAN.md item 8 already established the gate wraps
`bind_tools`' returned `tool_calls` in caller code, a `wrap_tool_call` middleware hook is the
natural seam — inspect `request.tool_call["name"]`/`args`, compute provenance depth, and either
call `handler(request)` (depth 0/1, proceed) or short-circuit with a rejection/pending-approval
message (depth 2). No LangGraph checkpointer/interrupt machinery is required for this path,
consistent with item 8's conclusion. Confirmed **byte-identical in substance** to the new repo's
copy at `/workspaces/langchain-claude-test/.agents/skills/langchain-middleware/SKILL.md` — a
line-by-line diff shows only 13 added blank lines in the new repo's version (one extra blank line
inserted after each "intro sentence before a code fence" throughout the file, e.g. after line 22,
49, 81...); zero content, wording, or example differences. Same version, cosmetic reflow only —
no drift to worry about.

## What does NOT carry over from opencode

`opencode-primitives/SKILL.md` documents opencode's own primitive system, all Claude-Code-
incompatible:
- **Skills**: opencode skills live at `.opencode/skills/<name>/SKILL.md` (project) or
  `~/.config/opencode/skills/<name>/SKILL.md` (global), discovered by walking up to the git
  worktree; frontmatter name must match the directory and satisfy
  `^[a-z0-9]+(-[a-z0-9]+)*$`; access is gated by `opencode.json`'s `permission.skill`
  allow/deny/ask (lines 16-22). Claude Code's skill discovery/permission model is different.
- **Plugins**: `.opencode/plugins/` (project) or `~/.config/opencode/plugins/` (global), or npm
  plugins listed in `opencode.json`'s `plugin` array and installed via Bun at startup (lines
  24-27) — no equivalent primitive in Claude Code as documented here.
- **MCP servers**: defined under `opencode.json`'s `mcp` key, `type: "local"`/`"remote"`, with
  OAuth auto-handled for remote servers (lines 29-34) — Claude Code's MCP config format differs.
- **Config precedence**: remote `.well-known/opencode` → global `~/.config/opencode/
  opencode.json` → custom path → project `opencode.json` → `.opencode/` dirs → inline env
  overrides (lines 37-38) — an opencode-specific cascade.

Also confirmed via `agent_framework/opencode.jsonc:1-13`: the canonical agent set
(`orchestrator, product_owner, architect, senior_engineer, skeptical_reviewer, security_auditor,
researcher, investigator, library_checker`) lived in the **global** `~/.config/opencode/
opencode.jsonc`, which does not exist in this container — those nine persona definitions are
lost; only `orchestrator`, `investigator`, and `implementer` appear to have working directories
under `agent_framework/agent-workspace/` (a different slice's territory, noted here only because
it's the direct evidence for the "lost persona" claim). Given the skill contents surveyed here,
the likely skill-to-lost-persona pairings were:
- `critical-thinking-logical-reasoning` ↔ **skeptical_reviewer** (argument critique, hidden-assumption surfacing).
- `agent-development`, `deep-agents-core/orchestration/memory`, `opencode-primitives` ↔ **orchestrator** / **architect** (agent/subagent design, harness config, platform primitives).
- `python-code-review`, `refactor`, `pragmatic-programmer` ↔ **senior_engineer** (code quality gates, craftsmanship rubric).
- `create-specification`, `architecture-designer`, `architecture-patterns` ↔ **architect** / **product_owner** (spec authoring, ADRs).
- `context7`, `find-skills` ↔ **library_checker** / **researcher** (external doc/skill lookup).
- The `qdrant-*` and `fastapi-*` skills ↔ **senior_engineer** on the old Pydantic-AI/Qdrant stack specifically.
- No skill in this slice maps cleanly to **security_auditor** — nothing security-specific was found here (the new repo's separately-installed `claude-code-hooks` and a possible `security-review` slash-command are outside this slice).

Practically: none of the *persona definitions* survived, only the skills some of them likely
invoked — and the skills are stack references or generic technique guides, not agent behavior
specs, so losing the personas mostly cost prompt/role framing, not irreplaceable logic.

## Answers to the key questions

**1. Does `planning-with-files` give us a working file-based session-state + completion-check
pattern the ledger could adopt or adapt?** Yes, as a pattern, not as a drop-in. Three flat
markdown files with a fixed schema (phase table + status enum, decisions table, error table),
hook-driven auto-refresh into context (`UserPromptSubmit`, `PreToolUse`, `PostToolUse`), and a
`Stop`-hook completion reporter that counts `**Status:**` markers and compares completed-count to
total-count, always exiting 0 (advisory, not a hard block). See the detailed section above for
the concrete transplant: swap "phase count" for "implicit-node resolved count." What it lacks is
any provenance/depth concept — that part has to be designed from scratch.

**2. Does any skill here already implement or describe assumption-flagging, source-citation, or
separating stated-from-inferred?** Partially, and only reactively. `critical-thinking-logical-
reasoning/SKILL.md:19` — "Surface hidden assumptions — what must be true for this argument to
hold?" — and line 49 — "Acknowledge uncertainty in your own analysis... flag where your critique
depends on assumptions" — are the clearest statements of this discipline anywhere in the slice.
But it's scoped to critiquing external prose/arguments on explicit request, not to the agent
auditing its own inferences mid-task, and it explicitly excludes code (line 3). No skill in this
slice implements source-citation for the agent's own claims or a stated-vs-inferred tagging
scheme. Plainly: nothing here does what PLAN.md's ledger does.

**3. Reinstall shortlist vs. dead weight?** See below.

## Salvage rating

### Directly reusable for the provenance-ledger project
- `planning-with-files/` — the file-schema + hook-wiring + advisory-completion-check pattern (`SKILL.md`, `scripts/check-complete.sh`, `templates/*`) is the closest thing to a working precedent for the ledger's durable-state and completion-criterion needs.
- `langchain-middleware/SKILL.md` — `wrap_tool_call` is the concrete mechanism to hang the v1 `bind_tools` gate on; already installed in the new repo, so this is really "already reused," confirmed identical.
- `langgraph-human-in-the-loop/SKILL.md` — reference shape for the depth-2 interrupt/resume/idempotency contract, useful if/when the ledger's scope grows past plain caller-code wrapping into an actual LangGraph node.

### Good thinking material / adaptable
- `critical-thinking-logical-reasoning/SKILL.md` — its assumption-surfacing structure is a good model for a possible future "gate at the point of assertion" mechanism (PLAN.md Open item 1), if that gets designed; would need to be inverted from reactive/on-request to standing self-audit.
- `deep-agents-orchestration/SKILL.md` + `deep-agents-memory/SKILL.md` — the `interrupt_on={tool: {"allowed_decisions": [...]}}` policy-per-tool config pattern is a reasonable shape for expressing per-tool-name gating policy if the ledger ever needs more than a binary depth check.
- `agent-development/SKILL.md` — useful if the project ever wants a dedicated "ledger-reconciler" subagent; the frontmatter/system-prompt template is generic and portable to Claude Code's actual subagent format (though `validate-agent.sh` checks structure/length only, not behavior — see below).
- `pragmatic-programmer/SKILL.md` (design-by-contract section, `references/contracts-assertions.md`) — "fail immediately and loudly when a contract is violated" is philosophically aligned with the ledger's hard-stop-at-depth-2 design; not code, just a compatible mental model.

### Dead weight under the new stack
- `opencode-primitives/SKILL.md` — entirely opencode-specific (`.opencode/` paths, `opencode.json` schema, opencode MCP config); zero applicability to Claude Code.
- `qdrant/`, `qdrant-search-quality/`, `qdrant-vector-search/` — no vector store in the new stack.
- `fastapi-python/`, `fastapi-templates/` — no FastAPI service in the new stack (v1 is a CLI/library gate, not a web API).
- `context7/` — MCP-based doc lookup tool skill; not wired to anything in the new repo and not requested.
- `mermaid-diagram-specialist/` + `mermaid-diagrams/` — redundant with each other; PLAN.md already writes its own mermaid diagrams by hand without a skill.
- `architecture-designer/`, `architecture-patterns/` — generic backend-architecture skills (ADRs, DDD, hexagonal); not scoped to this project's actual problem.
- `find-skills/`, `create-specification/` — meta-tooling (skill marketplace search, generic spec template) with no specific tie to the ledger work.
- `agent-development/scripts/validate-agent.sh` — validates only frontmatter shape/length (`AGENT_FILE` starts with `---`, has `name`/`description`/`model`/`color`, description length 10–5000 chars, system prompt 20–10000 chars) and does string-matches like "does the prompt contain the word 'output'" (`validate-agent.sh:200`) — it cannot validate that an agent actually behaves correctly; worth knowing before leaning on it as a quality gate.
- `python-code-review/SKILL.md` — references a `review-verification-protocol` skill and `clean-code`/`refactoring-patterns` reference files that don't exist anywhere in this repo; the skill as installed here is missing dependencies and would need repair before reuse.
- Remaining LangChain/LangGraph reference skills not already installed (`langchain-fundamentals`, `langchain-architecture`, `langchain-rag`, `langgraph-fundamentals`, `langgraph-persistence`) — legitimate stack docs but broader than v1's narrow `bind_tools`-gate scope; low urgency, not dead in principle, just not needed yet.
- `pydantic`, `pytest`, `pytest-coverage`, `python-expert`, `python-patterns`, `async-python-patterns` — generic Python/testing reference material, fine skills in the abstract but not specific to this project's open questions; the new repo can reach for these later if/when it needs a testing or typing deep-dive.

## Reinstall shortlist

Ranked by how directly each serves the provenance-ledger work:
1. **`planning-with-files`** — highest value; gives the ledger project itself a working session-state substrate to build on or crib from immediately.
2. **`critical-thinking-logical-reasoning`** — cheap to install, directly usable for a future "gate at assertion" mechanism, and generically useful for any reasoning-heavy design conversation.
3. **`agent-development`** — only if the project ends up wanting a dedicated ledger-reconciler or auditor subagent; otherwise skip.
4. **`langgraph-human-in-the-loop`** — not urgent for v1 (item 8 shows the v1 gate lives in caller code, not a graph), but worth having on hand for the day the ledger's scope grows into a LangGraph node with real interrupts.

Everything in "Dead weight" above should not be reinstalled; everything else in "Good thinking
material" is optional/low-priority and can be pulled in later on demand rather than reinstalled
now.

## Best pointers

- `agent_framework/.agents/skills/planning-with-files/SKILL.md:1-27` — hook wiring (`UserPromptSubmit`/`PreToolUse`/`PostToolUse`/`Stop`).
- `agent_framework/.agents/skills/planning-with-files/scripts/check-complete.sh:1-47` — the completion-check logic to model the ledger's own completion check on.
- `agent_framework/.agents/skills/planning-with-files/templates/task_plan.md:16-45` — phase/status schema.
- `agent_framework/.agents/skills/planning-with-files/SKILL.md:220-228` — "Security Boundary" section (untrusted-content isolation principle, adjacent to the ledger's own gating logic).
- `agent_framework/.agents/skills/critical-thinking-logical-reasoning/SKILL.md:14-19,49` — assumption-surfacing steps.
- `agent_framework/.agents/skills/langchain-middleware/SKILL.md:236-274` — `wrap_tool_call` hook signature, the concrete seam for v1's gate.
- `agent_framework/.agents/skills/langgraph-human-in-the-loop/SKILL.md:355-430` — idempotency rules for pre-interrupt side effects.
- `agent_framework/.agents/skills/opencode-primitives/SKILL.md:16-38` — everything that does not carry over.
- `agent_framework/.agents/skills/agent-development/scripts/validate-agent.sh:190-203` — evidence validate-agent.sh is a structural/string-match linter, not a behavioral validator.
- `agent_framework/opencode.jsonc:1-13` — confirms the nine-persona canonical agent set lived only in the missing global config.
