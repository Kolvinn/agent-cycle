# Combined plan — the session graph as an extension of a project graph, 2026-09-20

Status: **draft for antithesis, 2026-09-20.** Nothing here is built. Registers as the audit
(E their words, O observed, A/R assumption and rival, Q for them, P a plan element, D their
decision). Sources: `production-audit-2026-09-20.md` (ledger L1–L32), `branch-decisions-2026-09-20.md`
(D1–D16, H1–H5, Q-B1–Q-B9), the code as it stands on `orientate-absorbs-assume` at `fa8f871`.

Their instruction for this document: *"Propose a plan for combining the best of all branches such
that they are rooted in my goals, have tangible build paths (edges, nodes, etc.), and have gone
through at least one antithesis pass."* And: this is not a security review; the lens is product,
design and the original intent.

---

## 0. The shape in one paragraph

Two graphs with opposite relationships to time. The **session graph** (this app) is episodic and
append-only: questions, assumptions, rivals, evidence, the user's answers, facts. The **project
graph** (future, E71) is current and refreshable: what the project is, its goals, its
implementations. They meet at two seams. **Reading down**: the project graph is another source
to read; what comes from it enters as evidence, never as truth (E72). **Writing up**: approved
session outcomes are promoted with their provenance (E72, D12). Inside a session, only what the
user said in that session is truth (D13); anything from earlier sessions or the project graph
arrives as evidence and is re-asked, "is this still true" (D14). The plan builds the session graph
so both seams exist as slots today, with the shared op log across sessions standing in for the
project graph until one exists.

## 1. Roots — the words every element traces to

| # | Their words (abridged; full text in the audit and branch documents) |
|---|---|
| E51 | "curb the premature stopping or invalid concluding of agents … by forcing context and evidence into a comprehensive and structured shape" |
| E12 | "all tool calls are replaced in the session context with the output of the graph and the relevant pieces of the docs that are attached to them" |
| E19 | "orientation … letting the agent reconcile the user input against the landscape of the project, and then assuming based on that" |
| E18 | "we want assumptions to be avenues available for information to stick. There is no point in assuming something unprovable." |
| E11 | pricing is "to not polute their context by reading outdate and uncessary files" and "to make the agent go wide before going deep" |
| E7 / E9 / E20 / E28 | fact registration is HITL always; the agent never states fact; never closes in either direction; a message and an approval are different surfaces |
| E48 | "rooted in the user approval … cycles of growth, compression and reconcilation such that only the correct data is maintained across sessions" |
| E58 | "for me alone, so it needs to be smooth and versitile enought to not interrupt workflwo" |
| E59 | "standalone in a git repo that I can pull down into the harness and gitignore it there" |
| E65 | explore and implement, "always framing based on my extracted words", one branch per distinct shape |
| E67–E70 | `store_evidence`: filtering stays; no cache; the hook stores a reference; no auto nodes; agent-made evidence nodes with auto ids; same-turn amendment; no self-referencing for now |
| E71–E72 | a thought-graph extension of a larger project GraphRAG; the parent graph is "another thing to read"; sessions "push session graph changes to the larger graph" |
| E73 | answers as nodes; promotable; re-asked ("is this still true"); "each session is explicitly tasked with only having session provided answers being the truth source"; the parent graph "holds all of the graph information concerning the goals of the overall project and the implementations" |

---

## 2. The elements

Each element: **root** · **what changes** (records, node kinds, edge kinds, tools, files) ·
**test that proves it** · **ledger lines it closes** · **A/R already known**. Numbering is by
stage; stages are the order of work.

### Stage 0 — Ground: make it runnable on real work

**P0.1 — Split the three directories.** Root: E59, E58; audit O68, P-19a.
- *Changes.* `AppConfig` gains `home` (the install: this repo's root, default the package's parent) and `state_dir` (sessions, graph log, checkpoints, event logs; default `<home>/sessions`). `cwd` keeps its meaning: the studied project, the executor's fence. `modes.toml` resolves `state_dir`'s parent → `home` → the package. A `--state` flag overrides. `README.md` (empty today) gets the three-line install and the one rule: the clone is ignored by the host, the host is read by the clone.
- *Files.* `config.py:363-381`, `tui/app.py:228-231`, `runner.py` (SessionStore path), `README.md`.
- *Test.* Launch with `--cwd <tmp project>`: after a scripted cycle nothing exists under the tmp project; sessions and graph exist under `state_dir`. A `modes.toml` in `home` is found when the studied project has none.
- *Closes.* L8, L10. Answers Q-P11 as "the install" (their verdict pending).

**P0.2 — Fence the survey to the studied project.** Root: E11 (first purpose), E59; audit O75, L28.
- *Changes.* The PreToolUse hook refuses `Read`/`Grep`/`Glob` whose path argument resolves under `home` or `state_dir` when either lies inside `cwd` (the install shape puts the clone inside the host). The evidence executor's fence gets the same exclusion. Reason text says why. **A0.2:** honouring the host's `.gitignore` in full is a follow-up, not this element; the CLI's own `Glob` walked into a gitignored tree in Cycle 1 and we do not control its walk.
- *Files.* `harness/hooks.py:pre_tool_use`, `harness/evidence.py` fence.
- *Test.* A `Read` of `<state_dir>/graph/ops.jsonl` from a frame is refused; a `Read` of a host file is priced as before.
- *Closes.* L28 (part).

**P0.3 — Rewrite the system prompt.** Root: G5's claim that the rename reached everything (refuted, O17). Three frames, "assumption", no `excerpt`. *Files.* `prompts/graph_system.md`. *Test.* The prompt contains none of "four frames", "assume (", "reading", "excerpt copied". *Closes.* L26.

**P0.4 — Store lossless, cap only at render.** Root: E12, H2; audit O23, O82, L25.
- *Changes.* `Finding.excerpt` is already stored whole (80 lines / 6 KB). `/show node <finding>` renders it whole. The package keeps its width cap and appends `(+N chars — /show node f1.2)` so the model knows there is more. `_quote(limit=240)` stops being the only path.
- *Files.* `graph/package.py:41-43,57,244`, `runner.py` `/show`.
- *Test.* A 470-char finding: whole in `/show node`, capped-with-pointer in the package.
- *Closes.* L25.

### Stage 1 — The user's answers are nodes

**P1.1 — Answer nodes, derived from decisions.** Root: E73 (D11), E28, E7; audit O99, L15; branch O-B1.
- *Changes.*
  - Node kind `answer` (`vocabulary.NODE_KINDS`), prefix `u`, `authority=user`, status empty at birth exactly as a `fact` (closable later with `close_node`, supersedable with `supersede`; no new status).
  - Structural edges `blocks` (a refusal: answer → the proposal's target node) and `permits` (an approval with words: answer → target). Added to `STRUCTURAL`; never addable by name.
  - **No new record type.** `build()` derives an answer node from each `Decision` and its `ProposedWrite` (both already in the ledger, keyed by write id): text = the user's words, or the proposal summary when the words are empty; attrs `verdict`, `proposal` (write, target, argument), `cycle`, `session`. Rule: every refusal becomes a node; an approval becomes a node only when it carried words (an approval's effect is already its own record). **R1.1:** an `Answer` record of its own, if answers later need fields a decision cannot carry (promotion origin); not now.
  - Package: the section "THE USER REFUSED THESE. Do not propose them again" is replaced by **ANSWERS**, listing each answer node with what it blocks or permits, its cycle and date, its words, and its status. The brief says: an answer is the user's word in this session; a block stands until the user says otherwise; before proposing the same thing again, ask.
  - `/show node u1.2` works as for any node; `graph_search` finds answers by text.
- *Files.* `graph/vocabulary.py`, `graph/thought.py` (`build`, `apply`), `graph/package.py:183-192`, briefs in `graph/nodes/*.py`.
- *Test.* Scripted cycle with one refusal with words → node `u1.1`, edge `blocks u1.1→x1.2`, package ANSWERS section quotes the words with cycle and date; in a later scripted cycle `close_node u1.1 refuted` (approved) → the package shows it as no longer holding; the old heading text is absent.
- *Closes.* L15; O-B1; reframes L24 (answers render as nodes, not footnotes). Carries the question an answer answered (Q-B6) via the `proposal` attrs.

**P1.2 — What was tried and stopped, as a ledger line (not a node).** Root: E51 (the route to a conclusion must be inspectable); audit O32, L27, A19.
- *Changes.* A `Blocked` record: `call`, `reason_class` ∈ {surface, budget, handler, aborted}, `stage`, `cycle`, `tool_call_id`. Appended by the frames from `turn.meter.refused` and from an interrupted turn's pending proposal. **Not a node** (it is not an answer and carries no authority); rendered as one line per cycle in the package: "the model was refused: Read ×1 (budget), close_node ×1 (aborted)".
- *Files.* `graph/state.py`, `harness/turn.py:146`, `graph/nodes/*.py` append lists, `graph/package.py`.
- *Test.* Scripted off-surface call → `Blocked(surface)`; scripted interrupt during approval → `Blocked(aborted)`; both render.
- *Closes.* L27; A19. Answers Q-B8 as "records, not nodes".

### Stage 2 — Evidence comes from what was already read

**P2.1 — A reference on every priced read.** Root: E68 (D4), H3, H4.
- *Changes.* `post_tool_use` records, for a priced `Read` or `Grep` (not `Glob`: listing is not reading — Q-B2), a `Reference(call_id, source_kind ∈ {file, git, web, graph}, source_id, locator, read_at, version)`; for a file, `version` is mtime and size (a content hash is **A2.1**, cheap and strictly better; decide on cost). Held on `TurnContext.references`. **Scope (Q-B1):** the default is **turn-scoped** — `store_evidence` may cite only reads made this turn, matching D10's "no self referencing for now". **R2.1:** cycle-scoped, kept in memory on the driver across the cycle's frames, because the CLI conversation is cycle-scoped and the model in antithesis can still see orientate's reads; a turn-scoped rule makes the model re-read what it is looking at. The antithesis pass should weigh this one.
- *Files.* `harness/turn.py`, `harness/hooks.py:post_tool_use`.
- *Test.* After a scripted priced `Read`, `turn.references[call_id]` holds path, read time and version.

**P2.2 — `Finding` carries its citation.** Root: E67 (D7), H3, H4.
- *Changes.* `Finding` gains optional `source: Reference | None` (optional so old log lines decode). The evidence node renders "← sdk.py:91-104, read 04:50, unchanged since" or "**changed since read**" by comparing `version` with the file now.
- *Files.* `graph/state.py:145`, `graph/thought.py` (`apply(Finding)` attrs), `graph/package.py`.
- *Test.* A finding with a source renders its citation; touching the file flips it to "changed since read".
- *Closes.* Gives L25's storage half its provenance; makes the staleness in H4 visible.

**P2.3 — `store_evidence`.** Root: E67–E69 (D1, D5–D9).
- *Changes.* A new free tool on every frame that has `attach_finding`: `store_evidence(target, call_id | path, lines="a-b" | match="text", replace=)`. It slices the recorded result of that call (`turn.records`), checks presence with `source_of` (the never-called method: the excerpt must appear in a recorded result — the `Finding` docstring's promise, enforced for the first time), and appends a `Finding` with `source` from the reference. Same per-turn cap and same-turn `replace` as `attach_finding` (D9). **Granularity (Q-B3):** `lines` or `match` is required when the recorded result exceeds the finding cap; a `Grep` result may be taken whole. **No new node kind, no auto node** (D5): the finding is the only thing created, with the graph's own id.
- *Files.* `harness/tools.py` (beside `attach_finding`), `graph/surface.py` (tool sets), briefs.
- *Test.* Scripted: `Read` then `store_evidence(lines="10-20")` → finding excerpt equals those lines and carries the source; an excerpt not in any recorded result → refused with the reason; `replace` overwrites this turn's finding; citing a call from another turn → refused under the default scope.
- *Closes.* L18, L19 (with P2.5).

**P2.4 — `attach_finding` stays.** Root: Q-B4. For the case where the frame has nothing recorded to cite (pool spent, or a file not yet read). The brief demotes it: "when you have not read it yet". No code change beyond the brief.

**P2.5 — An assumption must cite its ground, or the answer is re-authored.** Root: E18, E19; audit O73, O107, L19.
- *Changes.* In `orientate`, an `Orientation` whose assumption has empty `evidence` **and** empty `grounded_in` is a re-author, like a wrong count today, with a correction naming the assumption. `grounded_in` accepts a fact id or **an answer id** (Q-B9: yes — an answer is the user's word, the strongest ground there is). The brief gains one sentence.
- *Files.* `graph/nodes/orientate.py:112-146`, `graph/payloads.py:35` description, brief.
- *Test.* Scripted payload with an ungrounded assumption → a second attempt is requested naming it; with evidence → accepted; exhausting attempts → `OrientationFailed` (existing).
- *Closes.* L18, L19 (with P2.3). This is the pressure; P2.3 is the mechanism. Neither alone: P2.3 is voluntary, P2.5 without P2.3 forces the model to re-run reads to keep them.

**P2.6 — A breadth check, provisional.** Root: E11, E14, E33; audit O113, L29.
- *Changes.* Two assumptions naming the same `moved_by` call are treated as one: re-author with "assumptions 1 and 3 would be moved by the same call; are they one assumption?". **Marked provisional (E33)**: the right measure is similarity (horizon), this is the cheap stand-in.
- *Files.* `graph/nodes/orientate.py` validation.
- *Test.* Scripted payload with identical `moved_by` on two assumptions → re-author; distinct → accepted.

### Stage 3 — The hand-off, file form

**P3.1 — `/handoff`.** Root: E12, E59; audit O117, L21; branch-decisions branch 4.
- *Changes.* `/handoff [path]` renders the graph **without the width cap**: facts; open assumptions and rivals with status; **answers** with words, status, date; evidence in full with citations and staleness; what the model was refused (P1.2); what was not looked at (the synthesis brief already demands this sentence). Written to `<state_dir>/handoff/<session>-c<cycle>.md` by default; the path is printed. **R3.1:** chat mode receives it automatically as the first message of the next chat turn. Not now: E28 keeps the surfaces distinct and the file is the cheapest way to learn whether the content is useful at all.
- *Files.* `runner.py` commands, `graph/package.py` (a full renderer beside the capped one).
- *Test.* Scripted cycle with a refusal and a long finding → the file holds the finding whole, the answer with its words, the facts.
- *Closes.* L21 (interim form).

**P3.2 — Synthesis proposes one change at a time and closes on ground.** Root: E20, E51; audit O79, O80, O115, L23, A27.
- *Changes.* Brief: propose one change per message and wait for the answer; read the answer before the next. `close_node`'s handler dry-run refuses a `because` that names no finding, fact or answer id ("a rival being confirmed is not ground for refuting the assumption; cite what shows it").
- *Files.* `graph/nodes/synthesis.py:36-95`, `harness/tools.py` `close_node`.
- *Test.* Scripted `close_node` with `because="its rival is confirmed"` → refused at dry-run with the reason; with `because` naming `f1.2` → asked.
- *Closes.* L23 (model side; the UI side is done on `ui-workflow`); A27 settled in favour of the brief plus the check.

### Stage 4 — Sessions as the truth source; the promotion seam, with the shared log standing in

**P4.1 — Origin-aware package.** Root: E73 (D13, D14, D16); audit O106.
- *Changes.* Every record already carries `session`. The package renders nodes whose session is **this** session under KNOWN / ASSUMPTIONS / ANSWERS as today, and nodes from **other** sessions of the same store under **PRIOR SESSIONS — evidence, not truth**: facts, closed claims and answers with their session and date. The brief: treat these as evidence; before relying on one, put it to the user in this session ("is this still true?") as `propose_fact` or `close_node`, and the answer becomes this session's. A local override (D16) is simply an answer in this session that contradicts a prior one; both stand, each in its session.
- *Files.* `graph/package.py:124-192`, briefs.
- *Test.* Two scripted sessions on one store: B's package shows A's fact under PRIOR SESSIONS and not under KNOWN; B's `propose_fact` of the same sentence → a fact in B; B's `close_node` of A's answer → refuted in the view with B's session on the closure.
- *Closes.* O106 (duplicates now carry their origin); embodies D13/D14 without a project graph.

**P4.2 — The promotion slot, dormant.** Root: E72, D12, H5.
- *Changes.* A `Promoted` record (`node_id`, `to` (the parent's id for it), `at`, `decision_id`) and a gated tool `promote(target)` on synthesis that, with no parent configured (`AppConfig.parent` absent), is refused at the dry-run with "no project graph is configured". **R4.2:** do not build a dormant tool; add the record and the config key only when a parent exists. The antithesis pass should weigh this one.
- *Files.* `graph/state.py`, `harness/tools.py`, `config.py`.
- *Test.* `promote` refused with the reason; the record type round-trips.

**P4.3 — The read-down slot.** Root: E72, H3. `Reference.source_kind` includes `graph` from P2.1. No code beyond the enum value; when a parent exists, a retrieval is a priced call whose reference has `source_kind=graph`, and its content is evidence like any other.

### Stage 5 — Evidence before vocabulary

**P5.1 — One task-shaped live run, then decide the role split.** Root: E2, E59; audit O112; branch-decisions branch 3.
- *Changes.* None to code. After Stage 0, one Haiku cycle against `Harness/` with a task-shaped prompt from its own task folder's vocabulary ("start on task X"). Record whether the model's assumptions are interpretations of the request or claims about the code, and whether it names anything worth promoting. **Only then** is `graph-task-kind` (a kind on the cycle; a second claim role; separation by destination) specified.
- *Test.* The run's write-up in the audit's registers.

---

## 3. Out of scope, on purpose

Vectors and similarity (horizon; P2.6 is the stand-in). Compression and the `summary` kind
(unfinished, later). Auto-created nodes of any kind (D5). The graph panel (E63). Cost
accounting (L31, their word). Security probing of any kind (their word). Fact extraction (E34).

## 4. Branches, per E65

| Branch | Elements | Why separate |
|---|---|---|
| `install-shape` | P0.1–P0.4 | Infrastructure, no change of shape; can merge first and alone. |
| `session-graph` | P1.1–P4.3 | One shape: the session graph with answers, cited evidence, the hand-off, and the two seams. |
| `graph-task-kind` | after P5.1 | Changes the vocabulary; needs evidence that does not exist yet. |

Tests first, in the repo's own style (each commit names the test and quotes the failure it
produced). Every number introduced is provisional and marked (E33).

## 5. What the antithesis pass is asked to break

Each element above, and in particular: the derivation of answer nodes from decisions rather than
a record of their own (P1.1); turn-scoped versus cycle-scoped references (P2.1); the breadth
stand-in (P2.6); the dormant promotion tool (P4.2); the claim that the shared log can stand in
for the project graph (P4.1); the order of stages; and anything from the ledger the plan forgets.

## 6. Antithesis pass — recorded here when it returns

*(pending)*
