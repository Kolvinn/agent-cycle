# Combined plan — the session graph as an extension of a project graph, 2026-09-20

Status: **APPROVED TO BUILD, 2026-09-20 (their words E76 in §7). Nothing is built yet; §7 is where to start.** Revised after one antithesis pass. The draft the pass
attacked is `combined-plan-2026-09-20-draft.md`; the pass itself (Opus, 830 lines, no live model
call, every runtime claim measured on the Cycle 1 op log or by direct handler invocation) is
`combined-plan-antithesis-2026-09-20.md`. Section 6 records, per element, the rival, the verdict,
and how it was settled here. Registers as the audit. Their constraints for this phase: product and
design lens, no security framing, Haiku only for anything live, nothing built or committed until
they choose.

---

## 0. The shape in one paragraph

Two graphs with opposite relationships to time. The **session graph** (this app) is episodic and
append-only: questions, assumptions, rivals, evidence, the user's answers, facts. The **project
graph** (future, E71) is current and refreshable: what the project is, its goals, its
implementations. They meet at two seams. **Reading down**: the project graph is another source to
read; what comes from it enters as evidence, never as truth (E72). **Writing up**: approved session
outcomes are promoted with their provenance (E72, D12). Inside a session, only what the user said
in that session is truth (D13); anything from an earlier session arrives as evidence and is
re-asked, "is this still true" (D14). Until a project graph exists, the shared op log across
sessions rehearses **D13, D14 and D16** — prior material in one store, distinguishable by origin,
overridable locally. It does **not** stand in for D15 (the parent's goals and implementations);
that needs the parent, and P5.1 is where the first task-shaped evidence comes from.

## 1. Roots

Unchanged from the draft: E51, E12, E19, E18, E11, E7/E9/E20/E28, E48, E58, E59, E65, E67–E70,
E71–E72, E73. Full text in the audit (§0) and the branch decisions (E67–E73).

---

## 2. The elements, revised

Each: **root** · **changes** (records, node kinds, edge kinds, tools, files) · **test** · **closes**.
A prerequisite the pass found that no element had budgeted for is now **P0.0**, first.

### Stage 0 — Ground

**P0.0 — Keep the envelope: `session` and `at` survive `decode`.** Root: H5 (every record needs a
stable id, a time and a provenance pointer); needed by P1.1 (a date on an answer) and P4.1 (origin).
- *Changes.* `encode` already writes `{"kind","session","at","data"}` per line; `decode`
  (`store.py:211-222`) keeps only `data`. Change `decode` to return the record **and** its envelope;
  `Ledger` gains `origin: dict[record id, (session, at)]` (and the same for records without ids,
  keyed by line). No record type changes. Nothing else in the plan works without this.
- *Files.* `graph/store.py:206-222`, `Ledger` (`store.py:101-123`).
- *Test.* A ledger loaded from a two-session log reports each record's session and time; an old
  line without an envelope decodes with empty origin.
- *Effort.* Half a day (pass).

**P0.1 — Split the three directories, and key the graph by the studied project.** Root: E59, E58;
audit P-19a **and P-19b** (the draft dropped P-19b; L9 and A13 with it).
- *Changes.* `AppConfig`: `sessions_dir` is renamed `state_dir` (a rename across seven call sites,
  not a new field) and gains `home` (the install). `cwd` stays the studied project and the executor's
  fence. **The graph lives under the install, keyed by the studied project's resolved real path**:
  `<state_dir>/<key>/graph/ops.jsonl`, so one clone driving two projects keeps two graphs and two
  cycle sequences, and one project reached by two mounts keeps one. A session record stores the
  `cwd` it was created under; `/resume` says so when the current one differs (L9, A13 made visible
  rather than silent). `modes.toml` resolves `state_dir` → `home` → the package. `--state` overrides.
  `README.md` gets the three-line install and the one rule.
- *Files.* `config.py:359-381`, `tui/app.py:228-231`, `runner.py` (store paths, `/resume`),
  `session.py`, `README.md`.
- *Test.* Scripted cycle with `--cwd <tmp project>`: nothing under the tmp project; graph under
  `<state_dir>/<key>/`; two cwd strings that resolve to one real path share one graph; `/resume`
  under a different cwd prints the warning.
- *Closes.* L8, L10, L9 (visible), A13 (visible). Answers Q-P11 as "the install, keyed by project".
- *Effort.* A day and a half (pass).

**P0.2 — The listing tool is ours; the ignore file is honoured; a frame cannot read its own state.**
Root: E11 ("not pollute their context by reading outdated and unnecessary files"), E59; audit
O75, O77, L28. **Cause, measured on the Cycle 1 events log:** of seven listing and search calls,
the one `Glob **/*.py` returned 21 files under the gitignored `Harness/`; the other two `Glob`
calls and all four `Grep` calls returned none. The CLI's `Grep` is ripgrep-backed and honours
`.gitignore`; the CLI's `Glob` does not. So the leak is one tool, and the model only ever reads an
ignored file after a listing named it.
- *Changes.*
  - **`Glob` comes off every frame's surface and is replaced by our own `glob(pattern, path=)`**,
    an MCP tool priced at the survey class, backed by the fenced executor running
    `rg --files -g <pattern>` (`rg` is already on the allow-list, `evidence.py:29`). ripgrep honours
    `.gitignore` natively (measured here: zero files under `Harness/`), and the fence adds
    `--glob !<home>` and `--glob !<state_dir>` so the install and its state never appear even when
    the clone sits inside the host. Output is one path per line, capped as evidence is.
  - The CLI's `Read` and `Grep` stay. **Belt and braces on `Read`:** in `pre_tool_use`, **before**
    `meter.charge` (so a refusal costs nothing, unlike O77), refuse a `Read` whose path is under
    `home`, under `state_dir`, or reported ignored by `git check-ignore` in the studied project, with
    a reason that says so.
- *Why not more.* Replacing `Read` too would rebuild something the SDK does well (E39); the read
  only goes wrong when the listing did. Replacing `Grep` is unnecessary: it already honours the
  ignore file. Cloning the tool beside the host rather than inside it (a sibling directory) is a
  zero-code mitigation for the install half, and is worth doing regardless, but does nothing for a
  .NET tree's `bin/` and `obj/`, which is the E11 cost on Harness.
- *Files.* `graph/surface.py:76-82` (`EVIDENCE_TOOLS`), `harness/tools.py` (one new tool beside
  `attach_finding`), `harness/evidence.py` (the two exclusion globs), `harness/hooks.py:52-68` (the
  `Read` check, placed before line 68), `config.py` (price class for `glob`).
- *Test.* Scripted: `glob("**/*.py")` in a tree with an ignored subdirectory lists none of it and
  none of `state_dir`; a `Read` of an ignored path → refused, pool unchanged; a `Read` of a host
  file → priced as before. Live (P0.6): the Harness run's listings name nothing under `bin/`, `obj/`
  or the clone.
- *Closes.* **L28.** Also removes the "post-hook must parse `tool_input`" difficulty for listings
  in P2.1, since a `glob` result is ours. A day.
- *Tension stated.* E39 says not to rebuild what the SDK does. This replaces one listing tool
  because the SDK's version defeats E11 on any real repository; the loop, `Read` and `Grep` are
  untouched. If you would rather keep the CLI's `Glob`, the `Read` check alone stops the reads and
  the listing still costs a point and shows the names.

**P0.3 — Rewrite the system prompt, once, last.** Root: O17. Measured harmless on Haiku (O85), and
Stages 1–4 add `answer` nodes, `store_evidence`, the grounding rule and PRIOR SESSIONS, so writing it
now means writing it twice. **Moved to the end of the `session-graph` work.** One file; one string
test that it names no removed concept. Closes L26. An hour.

**P0.4 — Store lossless, cap only at render.** Root: E12, H2; audit O23, O82, L25.
- *Changes.* The cut the audit blamed on `package._quote` (240) is also in `thought.label`
  (`thought.py:519-520`, 89 chars), which `describe_node` uses; measured, a 470-char finding renders
  at 245 chars through `/show node`. So: `describe_node` gets a finding branch that prints the
  excerpt whole; the outline `label` stays short; the package's `_evidence_lines` appends
  `(+N chars — /show node f1.2)` when it cuts. `Finding.excerpt` is already stored whole.
- *Files.* `graph/thought.py:515-531`, `graph/package.py:41-43,57`.
- *Test.* A 470-char finding: whole through `/show node`, capped-with-pointer in the package.
- *Closes.* L25. Half a day.

**P0.5 — Small core defects the draft forgot, each independent.** Root: the ledger.
- **L16** fork seeds from `pending()` (the frame it owes), not from `stage`. *Files.* `runner.py:506-508`.
- **L17** a fork's first chat message passes `fork_session=True`, mirroring the graph. *Files.* `chat.py:63`.
- **L32** the driver reads the state after the update is committed, not as it streams. *Files.* `graph_driver.py:112-115`.
- **L6** `/prices` marks the provisional class; the session record and the events log carry
  `provisional_fields()` once at open (E33 is not optional; `config.py:120-128` is built and unused).
- **L1** waits on **Q-P9** (below); not started.
- **L5** parked at their word, as L31 is.
- *Effort.* A day for the four.

### Stage 0½ — Evidence before the shape (was P5.1; moved here)

**P0.6 — One task-shaped live run, and A8, before any Stage 1 code.** Root: E54 ("disprove your
own assumptions as you go"), E2, E59; audit O112, A8.
- *Changes.* None to code. After Stage 0: one Haiku cycle against `Harness/`, task-shaped, in the
  vocabulary of its own task folder ("start on task X"), then **a second cycle on the same question**
  (A8: does kept evidence survive, or does cycle 2 re-read what cycle 1 kept). Record whether the
  model's assumptions are interpretations of the request or claims about the code; whether anything
  reaches a state worth promoting (L20 is measured here, not fixed); what the package carried into
  cycle 2. Write-up in the audit's registers.
- *Cost.* By Cycle 1's corrected measure, about $0.50 and four minutes per cycle, half a day to write up.
- *Gate.* `graph-task-kind` is not specified until this has run. Stage 1 does not start until A8 is
  measured, because A8 is the premise of Stage 2.

### Stage 1 — The user's answers are nodes

**P1.1 — An `Answer` record, written at the gate.** Root: E73 (D11), E28, E7; audit O99, L15; branch O-B1.
The draft derived answer nodes from `Decision` + `ProposedWrite`; the pass measured that the pair
carries no date, no sign, and a target that is empty or not a node id for four of the seven gated
tools. **R1.1 is taken: a record of its own, at the one place all of it is in hand.**
- *Changes.*
  - `Answer` record (`state.py`, and the checkpoint allowlist — "a decision", noted): `id` (prefix
    `u`, graph-assigned), `cycle`, `write` (the tool), `target` (a node id when the proposal named
    one, else empty and honest), `argument` (summary), `verdict`, `words`, `question` (the cycle's
    question id — Q-B6). `session` and `at` come from the envelope (P0.0). Written by
    `permission_gate` (`hooks.py:150-198`) beside the `Decision`; the frame appends it with its
    other records. Every refusal becomes an answer; an approval becomes one only when it carries words.
  - Node kind `answer`, `authority=user`, status empty at birth as a `fact`; added to `NODE_KINDS`,
    `live_ids` (`thought.py:85`) and `_WALKABLE` (`thought.py:204`) so it is targetable and reachable.
  - **One structural edge kind, `answers`, and it is neutral.** The pass showed the draft's `blocks`
    reads backwards: all three live refusals refused `close_node` — the user was *protecting*
    x1.2, x1.3, a1.1 — and a `blocks u→a1.1` edge says the opposite. So: `answers` from the answer
    to the target node when there is one, carrying `write` and `verdict` as attrs, and **always**
    `answers` from the answer to the cycle's question, so every answer is one hop from the question
    and the neighbourhood bounds it. The package renders the verb from write + verdict: *"u1.3 →
    a1.1: refused `close_node refuted` — 'not this cycle'"*. Never a bare "blocks".
  - `close_node` and `supersede` accept the `answer` kind (`tools.py:469,489`), and
    `apply(Supersession)` sets the winner's role to `assumption` only when the winner is a claim
    (`thought.py:416`, measured: today it would turn an answer into an assumption).
  - Package: "THE USER REFUSED THESE. Do not propose them again" is replaced by **ANSWERS**,
    bounded by the neighbourhood like every other block, each with cycle, date, verb, words, status.
    Brief: an answer is the user's word in this session; before proposing the same write on the
    same target again, ask.
- *Files.* `graph/state.py`, `graph/vocabulary.py`, `harness/hooks.py:150-198`, `harness/turn.py`,
  `graph/nodes/*.py` (append), `graph/thought.py:85,204,335,416`, `harness/tools.py:469,489`,
  `graph/package.py:183-192`, four briefs.
- *Test.* Scripted refusal of `close_node x1.2` with words → `u1.1`, edges `answers u1.1→x1.2`
  (write=close_node, verdict=refused) and `answers u1.1→q1`; package line reads as protecting x1.2
  with the words, cycle and date; scripted `propose_fact` approval with words → `u1.2` with no
  target and one edge to `q1`; in a later cycle `close_node u1.1 refuted` (approved) → rendered as
  no longer holding; `supersede u1.1→u1.3` keeps u1.3's kind.
- *Closes.* L15; O-B1; reframes L24. Three days (pass).

**P1.2 — What was tried and stopped, as a ledger line (surface and budget only).** Root: E51;
audit O32, L27.
- *Changes.* `Blocked` record: `call`, `reason_class ∈ {surface, budget, handler}`, `stage`, `cycle`,
  `tool_call_id`. `Meter.refused` gains the call id (`meter.py:84-103`); `Attempts.absorb` carries
  `result.refused` (`_common.py:52-58`, which drops it today); frames append. Not a node. One line
  per cycle in the package.
- *Not included.* `aborted`: an interrupted turn appends nothing by design (O87), and whether it
  should is **Q-P9**. A19 stays open until that is answered; this element does not decide it.
- *Files.* `graph/state.py`, `harness/meter.py`, `graph/nodes/_common.py`, `graph/package.py`.
- *Test.* Scripted off-surface call → `Blocked(surface)`; scripted budget refusal → `Blocked(budget)`; both render.
- *Closes.* L27. Two days.

### Stage 2 — Evidence comes from what was already read

**P2.1 — A reference on every priced read, scoped to the frame's attempts.** Root: E68 (D4), H3, H4;
E27a and the antithesis brief (`antithesis.py:52-54`).
- *Changes.* `post_tool_use` reads `tool_input` (it reads only `tool_response` today) and records a
  `Reference(call_id, source_kind ∈ {file, git, web, graph}, source_id, locator, read_at, version)`
  for a priced `Read` or `Grep` (not `Glob`); `version` is mtime and size, a content hash marked
  provisional. **Scope: the frame's attempts.** References and the recorded texts are carried on
  `Attempts` (`_common.py:34-58`) beside `findings` and `spend`, and handed into each attempt's
  `StageRequest`, so a re-author can cite what the first attempt read. **The frame boundary stays
  hard**: antithesis is funded to re-read the frame it attacks, by the brief and by E27a, and
  cycle-scoped references would let it skip that. Q-B1 was a false binary; this is the settlement.
  `source_kind=graph` is reserved here (the draft's P4.3, folded in).
- *Recorded text, once.* `turn.record` today concatenates two renderings of every result (the
  hook's raw `tool_response` and the stream's `ToolResultBlock`, `hooks.py:93` + `sdk.py:147`,
  `turn.py:126-129`). The raw hook rendering becomes canonical for slicing; the stream one is kept
  for `source_of` matching only.
- *Files.* `harness/turn.py`, `harness/hooks.py:90-103`, `graph/nodes/_common.py`, `harness/sdk.py:147`.
- *Test.* Scripted (the scripted harness does call `post_tool_use` with `tool_input`,
  `scripted.py:136`): after a priced `Read`, the reference holds path, read time, version; after a
  scripted re-author, the second attempt's request carries the first's references.
- *Effort.* Two days.

**P2.2 — `Finding` carries its citation, and its two dead fields come alive.** Root: E67 (D7), H3, H4.
- *Changes.* `Finding.tool_call_id` and `Finding.price` exist and are empty on every live finding
  (measured: all five `''`/`0`); `store_evidence` fills them from the reference. `Finding.source:
  Reference | None` is added (optional, so old lines decode; a nested record in the checkpoint — the
  allowlist decision is noted, not hidden). The evidence node renders its citation and a staleness
  mark by comparing `version` with the file now.
- *Files.* `graph/state.py:145-163`, `graph/thought.py` (`apply(Finding)` attrs), `graph/package.py`.
- *Test.* A finding with a source renders "sdk.py:91-104, read 04:50"; touching the file flips it to "changed since read".
- *Effort.* A day.

**P2.3 — `store_evidence`.** Root: E67–E69 (D1, D5–D9).
- *Changes.* A free tool beside `attach_finding` on the same frames: `store_evidence(target,
  call_id, lines="a-b" | match="text", replace=)`. `lines` are **file line numbers as the `Read`
  output shows them**; the slice is taken from the canonical recorded text with the CLI prefixes
  stripped; `match` is a substring. Presence is checked with `source_of` (called for the first time;
  the `Finding` docstring's promise enforced). `lines` or `match` is required when the recorded result
  exceeds the finding cap; a `Grep` result may be taken whole (Q-B3). Same per-frame cap and same-turn
  `replace` as `attach_finding` (D9). The finding is the only thing created (D5), with the graph's id (D6).
- *Files.* `harness/tools.py` (beside line 130), `graph/surface.py` tool sets, briefs.
- *Test.* Scripted `Read` then `store_evidence(lines="10-20")` → excerpt equals those lines, source
  filled, `tool_call_id` and `price` filled; an excerpt in no recorded result → refused; `replace`
  overwrites this frame's finding; a call id from another frame → refused.
- *Closes.* L18, L19 with P2.5. Three days.

**P2.4 — `attach_finding` stays**, for what the frame has not read. With P2.1's settlement a retry
can cite the first attempt's reads, so the pass's point that a retry *needs* `attach_finding` no
longer applies; the brief demotes it to "when you have not read it yet". No code.

**P2.5 — An assumption must cite its ground, softly.** Root: E18, E19; audit O73, O107, L19, L2, L4.
- *Changes.* In `orientate`: an assumption whose `evidence` names no finding of this frame's attempts
  **and** whose `grounded_in` names no live fact or answer is *ungrounded*. The check **resolves ids**
  against `node_ids` (passed on every request, `orientate.py:127`, and read by nothing today) plus
  this frame's findings; a sentence in `grounded_in` does not pass. **Soft path**: one correction
  naming the assumption and what would ground it; if the second answer is still ungrounded, the
  assumption is **accepted and marked** `ungrounded`, rendered "(no ground given)" in the package
  and the outline, and counted in the stage summary. It does **not** share `OrientationFailed` with
  the count: a frame is never lost to this rule (E58). The brief gains one sentence.
- *Folded in.* **L4**: the correction message names the actual fault — shape, count, or ground —
  instead of always "wrong count". **L2**: when a frame does fail every attempt, its spend is
  appended before the raise (A12: spend is spend, E8).
- *Files.* `graph/nodes/orientate.py:112-154`, `graph/payloads.py:30` (the `grounded_in`
  description; the draft's locator was wrong), `graph/package.py`, brief.
- *Test.* Scripted payload with `grounded_in="some sentence"` → correction; second attempt with a
  real finding id → accepted, unmarked; second attempt still ungrounded → accepted, marked, cycle
  continues; total failure → spend appended.
- *Closes.* L19 (with P2.3), L4, L2. Three days.

**P2.6 — dropped.** The draft's exact-match rule on `moved_by` would have fired zero times on the
case it cited (no two of Cycle 1's three matched), and it rewards paraphrase (against E18).
**L29 stays open.** The measurement E14 needs is similarity, which is the horizon's; no stand-in
is built. The pass's alternative (count distinct files named across `moved_by`) is recorded as an
option, not taken.

### Stage 3 — The hand-off, file form

**P3.1 — `/handoff`.** Root: E12, E59; audit O117, L21. Smaller than the draft said: `/show package`
already exists (`runner.py:457-475`); this is an **uncapped** renderer beside `render`, a command,
and a file under `<state_dir>/<key>/handoff/`. Contents: facts; open assumptions and rivals with
status; answers with verb, words, status, date; evidence whole with citations and staleness; what the
model was refused (P1.2); what was not looked at. Chat-mode auto-injection stays deferred (E28).
*Test.* Scripted cycle with a refusal and a long finding → the file holds them whole. Closes L21
(interim). A day and a half.

**P3.2 — One change at a time, and closes rest on ground of the right kind.** Root: E20, E51;
audit O79, O80, O115, L23, A27.
- *Changes.* Brief: propose one change per message and read the answer before the next.
  `close_node`'s dry run refuses a `because` that does not name a **live node of kind evidence, fact
  or answer**, and refuses one that rests on a **claim** — the live call p1.5 (`because="because its
  rival x1.1 is confirmed"`) names a claim id and is the exact case; "names an id" would have
  passed it.
- *Files.* `graph/nodes/synthesis.py:36-95`, `harness/tools.py` `close_node` dry run.
- *Test.* p1.5's real `because` → refused with the reason; `because` naming `f1.2` → asked.
- *Closes.* L23 (model side). A day.

### Stage 4 — Sessions as the truth source, rehearsed on the shared log

**P4.1 — Origin-aware package, with a bound and a re-ask that works.** Root: E73 (D13, D14, D16);
audit O106. A week, not a renderer change (pass); P0.0 is its prerequisite.
- *Changes.*
  - Origin from the envelope (P0.0), never derived from the cycle (a fork writes the source's cycle
    number under its own session — L16, L17 — so derivation mislabels forks).
  - Nodes from **this** session render as today; nodes from **other** sessions of the same graph
    render under **PRIOR SESSIONS — evidence, not truth**, with session and date.
  - **Bounded**: only prior-session facts, closed claims and answers whose words the question's
    words reach, using the existing search (`package.py:67-77`), and never more than a marked
    provisional number. Not everything (the E58 wall), not nothing (they would be invisible).
  - **The re-ask is a gated tool, `reaffirm(target, because)`**, on synthesis: target is a
    prior-session fact or answer; the user approves ("still true") or refuses with words; the result
    is an `Answer` in this session (P1.1) with `write=reaffirm` and the prior node as target. This is
    D14 as a call the user answers, and it needs no new node kind. `propose_fact` is left as it is:
    it requires the user's own words this cycle, which is right, and is why it could not serve D14.
  - A local override (D16) is an answer in this session that contradicts a prior one; both stand,
    each in its session, and the package shows both.
- *Files.* `graph/package.py:96-192`, `harness/tools.py` (one new gated tool), `graph/surface.py`, briefs.
- *Test.* Two scripted sessions on one graph: B's package shows A's fact under PRIOR SESSIONS only
  when the question's words reach it; B's `reaffirm` approved → an answer in B targeting A's fact;
  B's `reaffirm` refused with words → the same, rendered as no longer holding; A's package is unchanged.
- *Closes.* O106 (duplicates carry origin); embodies D13/D14/D16.

**P4.2 — dropped.** A dormant `promote` tool is five registrations for a refusal. The H5 gap it
was meant to reserve is the discarded timestamp, which P0.0 fixes. When a parent graph exists,
`promote` is one gated tool whose record cites the answer, the evidence and the decision by id —
all of which exist after Stage 1.

### Stage 5 — Vocabulary, only on evidence

**P5.1 — `graph-task-kind`, specified after P0.6.** A kind on the cycle; a second claim role;
separation by destination (project claims promotable, request interpretations episodic). Not
written until the task-shaped run says the distinction survives contact with a task.

---

## 3. Out of scope, on purpose

Vectors and similarity (horizon; L29 waits for them). Compression and the `summary` kind (later).
Auto-created nodes (D5). The graph panel (E63). Cost accounting (L31). Fact extraction (E34).
Executor fencing beyond P0.2 (L5, at their word). Security probing of any kind (their word).

## 4. Stages — product level, internals first, deploy last (2026-09-20, at their word)

Their two instructions: *"squash more of the build together into product level stages, testing can
happen once per big stage"*, and then: *"I don't really think there's much in the way of point of
having it deployable to harness and then changing the internal structures … the change that this
build is supposed to act is what I want to be testing anyway."* So: the graph changes are built and
tested **here**, on this repository, first; the install shape comes **last** and the Harness run
tests the finished shape on real work. One branch per stage; the suite plus one live Haiku run at
the end of each stage is the acceptance; scripted tests are batched at stage end.

What this gives up, stated: the antithesis pass wanted a task-shaped run *before* the graph work,
because the graph work was designed on one question-shaped cycle. That run now happens at deploy
time, on the finished shape. The elements of Stages 1 and 2 do not depend on the question/task
distinction (a refusal is a node either way; a reference is a reference either way), so the cost is
that Stage 4 waits until the end rather than being informed early. Accepted at their word.

| Stage | Branch | Elements | What you can do afterwards | Acceptance at the end |
|---|---|---|---|---|
| **1 — The graph holds your answers and the model's evidence** | `stage-1-graph` | P0.0 (envelope kept), P0.2 (listing tool, `Read` check), P0.4 (lossless render), P1.1, P1.2, P2.1, P2.2, P2.3, P2.4, P2.5, P3.2 | Refusals and approvals-with-words are nodes you can see, search and later revise; the model keeps what it read by pointing at it; listings honour the ignore file; findings show whole; an assumption without ground is marked; a close needs real ground; one proposal at a time. | Suite; then **two** Haiku cycles here on Cycle 1's question, compared against Cycle 1: findings kept by orientate, answers rendered, ungrounded count, proposals per message, and **A8** (does cycle 2 cite what cycle 1 kept, or re-read it). ~2 weeks. |
| **2 — The graph leaves the session** | `stage-2-handoff` | P3.1, P4.1, P0.3 | A hand-off file for the working session; a second session sees the first's conclusions as evidence and re-asks with `reaffirm` or overrides; the system prompt matches the build. | Suite; then a two-session Haiku run here: session two opens on a related question and re-affirms or overrides session one. ~1 week. |
| **3 — Runs on Harness** | `stage-3-install` | P0.1, P0.5 | Clone it into Harness, run the finished shape on real work; nothing lands in Harness; forks and frame lines behave; provisional numbers marked. | Suite; then **P0.6 on the finished shape**: one task-shaped Haiku cycle on Harness. This is the first real-work test and the evidence Stage 4 waits for. ~3 days + half a day of runs. |
| **4 — Task kind, only on evidence** | `graph-task-kind` | P5.1 | A session opens against a task rather than a question. | Specified only after Stage 3's run says the distinction survives contact with a task. |

Dependencies are linear: 2 needs 1's answers; 3 needs nothing from 1 or 2 but is pointless before
them (their point). Every number introduced is provisional and marked (E33).

## 4a. Before the go-ahead — what is open

| # | Open item | Proposed default, so it does not block |
|---|---|---|
| G1 | **Q-P9**: is the op log the trail of everything *attempted* or everything *committed*? Gates L1 (ghost cycle), the `aborted` half of P1.2, and what can be promoted. | **Attempted, with a done-marker** (the audit's own recommendation): a frame writes a `frame_done` line on success; `open_cycle` hands back a cycle whose last frame is not done; the package hides cycles no frame finished; an aborted proposal leaves a `Blocked(aborted)`. Lands in Stage 1 (P1.2) and the L1 fix in Stage 3 (P0.5). Say "committed" to overturn. |
| G2 | **Base branch and the UI branch.** The app lives on `orientate-absorbs-assume` (`main` is behind). `ui-workflow` (17 commits, unmerged) edits `runner.py`, `tui/app.py`, `screens.py`, `events.py`; Stage 1 edits none of those, so the overlap is now small. | **Merge `ui-workflow` into `orientate-absorbs-assume` first**, so there is one line of development; then branch Stage 1 from there. Or name the base you want. |
| G3 | **The nine settled-unless-overturned items in §5.** Q-C8 (task run before the graph work) and Q-C9 (separable branches) are superseded by this section, at their word. | **Silence is assent** on the remaining seven. Say the number to overturn one. |

Q-B5 (my reading of "no self referencing for now") no longer needs an answer: P2.1's frame-scoped
references and the single `answers` edge satisfy both readings.

## 5. Questions — settled here unless you overturn, and one that is yours alone

| # | Question | Settled as | Status |
|---|---|---|---|
| **Q-P9** | Is the op log the trail of everything **attempted** or everything **committed**? Gates L1 (the ghost cycle), the `aborted` half of P1.2 (A19), and what can be promoted (D12). | — | **Yours.** Unchanged since the audit; now load-bearing. |
| Q-C1 | What does a refusal relate to? | The **proposal**, not the target: the edge is neutral (`answers`), carries the write and verdict, and renders as the user protecting or declining what they actually answered. Your words "an assumption node was blocked by a user answer node" are honoured by the edge landing on the assumption, labelled by what was refused. | Settled; overturnable. |
| Q-C2 | Answer nodes: derived, or a record of their own? | A record, at the gate (R1.1). | Settled by measurement. |
| Q-C3 | How does a session re-establish a prior answer (D14)? | `reaffirm`, a gated call whose answer is an `Answer` in this session. Not `propose_fact`, which correctly wants your own words. | Settled; overturnable. |
| Q-C4 | How much of a prior session does a new session see? | Only what the question's words reach, capped by a marked number; not everything, not nothing. | Settled; overturnable. |
| Q-C5 | Reference scope? | The frame's attempts; hard between frames. | Settled by E27a and the antithesis brief. |
| Q-C6 | Breadth stand-in? | Dropped; L29 waits for similarity. | Settled; overturnable. |
| Q-C7 | The graph's key under the install (Q-P11 + P-19b)? | Under the install, keyed by the studied project's resolved real path. | Settled; overturnable. |
| Q-C8 | Order: the task-shaped run before Stage 1? | Yes (P0.6), with A8 in the same run. | Settled by E54/O112. |
| Q-C9 | One branch or several? | Several, as §4. | Settled by E65. |

---

## 6. The antithesis pass, recorded

Opus, in its own worktree, no live model call, baseline suite 58 passed. Every verdict below was
checked here against the code before being accepted; one correction to the pass is noted.

### Verdicts and settlements

| Element | Rival (one line) | Verdict | Settled here as |
|---|---|---|---|
| P0.1 | `sessions_dir` already exists; P-19b, L9, A13 dropped | PARTLY HOLDS | Rename, plus P-19b (graph keyed by real path) and the cwd warning. |
| P0.2 | O75's leak was a `Glob` rooted at cwd; charge order unspecified | HOLDS (part) | Cause measured: only the CLI's `Glob` ignores `.gitignore`; replaced by an `rg --files` tool of ours, plus a no-charge `Read` check. **L28 closes.** |
| P0.3 | Harmless on Haiku (O85); later stages rewrite what it describes | REFUTED as urgent; placement HOLDS | Moved to the end. |
| P0.4 | The cut is in `thought.label`, not only `_quote` | HOLDS (locator) | Both fixed; `describe_node` prints whole. |
| P1.1 | `blocks` reads backwards; 1 in 4 has no target; `close_node`/`supersede` refuse the kind; no date exists | **HOLDS** | `Answer` record at the gate; neutral `answers` edge to target and to question; tools widened; role mutation fixed; date from P0.0. |
| P1.2 | Two reason classes have no source; `aborted` is unreachable by design; it decides Q-P9 by a clause | HOLDS | Surface, budget, handler only; `aborted` waits for Q-P9. |
| P2.1 | Turn-vs-cycle is the wrong axis; the re-author attempt is the boundary | **HOLDS** | Scoped to the frame's attempts on `Attempts`; frame boundary hard. |
| P2.2 | `tool_call_id` and `price` are dead on every finding; a nested record is an allowlist decision | PARTLY HOLDS | Both filled by `store_evidence`; the allowlist decision stated. |
| P2.3 | `turn.records` holds each result twice with prefixes | HOLDS | One canonical rendering for slicing; `lines` are file line numbers. |
| P2.4 | Not a fallback; the only thing a retry can use | REFUTED after P2.1's settlement | A retry can now cite; demoted as planned. |
| P2.5 | Checks emptiness not validity; any sentence passes; shares a cycle-killing failure | HOLDS | Resolves ids against `node_ids`; soft path; ungrounded is marked, never fatal; L2 and L4 folded in. |
| P2.6 | Would have fired zero times on the case cited; rewards paraphrase | **HOLDS** | Dropped. |
| P3.1 | `/show package` exists; smaller than described | REFUTED / size HOLDS | Resized. |
| P3.2 | "Names an id" passes p1.5, the very call it exists to refuse | HOLDS | Kind-aware: evidence, fact or answer; never a claim. |
| P4.1 | "Every record carries session" is false; `propose_fact` refuses the re-ask; unbounded; fork-unsafe by derivation | **HOLDS** | P0.0 first; origin from the envelope; `reaffirm`; bounded by the question's reach. |
| P4.2 | "Dormant" is five registrations; the real H5 gap is the discarded timestamp | HOLDS | Dropped; P0.0 is the reservation. |
| P4.3 | An enum value with no consumer is not an element | HOLDS (mild) | Folded into P2.1. |
| P5.1 | Numbered last, needed second; Stages 1–4 built on the gap it closes | **HOLDS** | Moved to P0.6, with A8. |

### The seven conflicts, and where each is settled

1. P2.5 destroyed what P2.3 needs through P2.1's scope → P2.1 (frame's attempts).
2. P1.1 and P4.1 both needed a date and a session neither budgeted → P0.0.
3. P1.1's and P4.1's re-asks were each refused by the other's tool → `reaffirm` + widened `close_node`.
4. P0.3 and Stages 1–4 both owned the prompt → P0.3 last.
5. P0.4 and P1.1/P4.1 all edit `package.py` → sequenced by §4; the split is by shape, not by file.
6. P0.2's fence and P3.1's directory → no conflict while chat auto-injection stays deferred; noted.
7. P2.5 and P2.6 both added triggers to a frame that hard-fails → P2.6 dropped; P2.5 never fatal.

### False claims in the draft, corrected above

Ten tabled; all accepted: session not preserved (P0.0); `close_node`/`supersede` refuse the kind
(P1.1); no date (P0.0); the label cut (P0.4); P4.1 not a renderer change (P4.1); `Blocked`'s
sources (P1.2); the `payloads.py` locator (P2.5); `sessions_dir` exists (P0.1); the allowlist
(P2.2, P1.1, P1.2); the doubled record (P2.3).

**One correction to the pass.** It says the scripted harness "bypasses the hook path entirely"
for P2.1. It does not: `scripted.py` calls `pre_tool_use` and `post_tool_use` directly with
`tool_input` and `tool_response` (`scripted.py:110,136`); it also calls `turn.record` before the
post-hook, so the doubling exists there too. A scripted test **can** cover a reference; a live test
is still worth one run for the real payload shape.

### Their words the draft contradicted or ignored, and where each is now honoured

D14 → `reaffirm` (P4.1). E58 → the bound (P4.1) and the soft path (P2.5). E65 → §4. E54/O112 →
P0.6 first. Q-P9 → left open, named in §5, no element decides it. D15 → §0 corrected. E18 → P2.6
dropped; P2.5 resolves ids. E33 → P0.5 (L6).

### Ledger lines the draft forgot, placed

L9, A13 → P0.1. L1 → waits on Q-P9, named. L2, L4 → P2.5. L6 → P0.5. L16, L17, L32 → P0.5.
L20 → measured in P0.6, stated as reframed-not-fixed. L5 → parked at their word, stated. A8 →
P0.6. A21, A22 → unmeasured, stated.

### The pass's nine questions

Q1 → Q-C2. Q2 → Q-C1. Q3 → **Q-P9, yours**. Q4 → Q-C4. Q5 → Q-C3. Q6 → Q-C6. Q7 → Q-C7.
Q8 → Q-C8. Q9 → Q-C9.

---

## 7. Go-ahead — their decisions, and where to start

### Their words

| # | Their words |
|---|---|
| E74 | "Ideally, I'd like to squash more of the build together into product level stages, testing can happen once per big stage" |
| E75 | "I don't really think there's much in the way of point of havbin it deployable to harness and then changing the internal structures? Especially considering that the change that this build is supposed to act is what I want to be testing anyway. IOf we deploy to harness and then test, but we are not testing it on the result, then that's redundant" |
| E76 | "I'm happy with the defaults you have put for all of these. YOu should do the merge yourself and make sure the state of the doc is up to date so building can be done straight away. I will then trigger a compaction, so make sure that everything is recorded for the continuation" |

### Decisions

| # | Decision | From |
|---|---|---|
| D-G1 | **The op log is the trail of everything attempted.** A frame writes a `frame_done` line on success; `open_cycle` hands back a cycle whose last frame is not done; the package hides cycles no frame finished; an aborted proposal leaves `Blocked(aborted)`. Q-P9 closed. | E76 accepting the default |
| D-G2 | **`ui-workflow` merged first** into `orientate-absorbs-assume` (fast-forward to `a12751a`, 2026-09-20); every stage branches from there. | E76 |
| D-G3 | The seven settled items Q-C1–Q-C7 stand as written in §5. Q-C8 and Q-C9 are superseded by §4 (E74, E75). | E76 |
| D-G4 | Stages are product-level, internals first, install last (§4). Testing once per stage: scripted tests are written per element but batched and run at stage end, plus one live Haiku run as acceptance. | E74, E75 |

### Standing constraints for the build (unchanged)

- Live model calls: **Haiku only** (E61). Each run's reported cost is noted in the stage's write-up.
- Lens: product and design. **No security framing, no fence probing** (their word, 2026-09-20).
- Nothing merges into `orientate-absorbs-assume` or `main` without them. Each stage is a branch; they merge it.
- Every proposal and every commit message is framed on their E-lines. Every number introduced is provisional and marked (E33).
- The graph panel is not touched (E63). Cost accounting is backlogged (L31).
- Commit messages name the test and quote the failure it produced, as the UI branch's do.

### Start here — Stage 1, `stage-1-graph`

```
git checkout -b stage-1-graph orientate-absorbs-assume   # from a12751a
uv run pytest tests -q                                    # baseline: 72 passed
```

Order inside the stage (each element's spec is in §2; this is the build order, chosen so every
later element has what it needs):

| # | Element | Why here | Key files |
|---|---|---|---|
| 1 | **P0.0** envelope kept through `decode` | P1.1 needs the date; nothing else works without it | `graph/store.py:206-222`, `Ledger` |
| 2 | **D-G1** done-marker (`frame_done` line; `open_cycle` respects it; package hides unfinished cycles) | Closes L1 while the store is open | `graph/store.py:315-337`, `graph/nodes/_common.py`, `graph/package.py` |
| 3 | **P1.1** `Answer` record at the gate; `answer` kind; `answers` edge; tools widened; ANSWERS block | The centre of the stage | `graph/state.py`, `graph/vocabulary.py`, `harness/hooks.py:150-198`, `harness/turn.py`, `graph/thought.py:85,204,335,416`, `harness/tools.py:469,489`, `graph/package.py:183-192`, briefs |
| 4 | **P0.2** `glob` tool (rg-backed, ignore-honouring, install excluded); `Read` check before charge | Our listing result feeds P2.1's reference | `graph/surface.py:76-82`, `harness/tools.py`, `harness/evidence.py`, `harness/hooks.py:52-68`, `config.py` |
| 5 | **P2.1** `Reference` on priced reads, carried on `Attempts`; one canonical recorded text | P2.3 slices from it | `harness/turn.py`, `harness/hooks.py:90-103`, `graph/nodes/_common.py:34-58`, `harness/sdk.py:147` |
| 6 | **P2.2** `Finding.source`; `tool_call_id`/`price` filled; staleness mark | P2.3 writes it | `graph/state.py:145-163`, `graph/thought.py`, `graph/package.py` |
| 7 | **P2.3** `store_evidence` | The mechanism | `harness/tools.py` beside line 130, `graph/surface.py`, briefs |
| 8 | **P0.4** lossless render (`describe_node` whole; package pointer) | Evidence must be readable to be cited | `graph/thought.py:515-531`, `graph/package.py:41-57` |
| 9 | **P2.5** grounding check, soft; L4 correction names the fault; L2 spend appended on total failure | The pressure; needs 5–7 | `graph/nodes/orientate.py:112-154`, `graph/payloads.py:30`, brief |
| 10 | **P3.2** one change per message; `close_node` kind-aware ground | Small, independent | `graph/nodes/synthesis.py:36-95`, `harness/tools.py` `close_node` |
| 11 | **P1.2** `Blocked` (surface, budget, handler, aborted per D-G1) | Needs meter call ids | `graph/state.py`, `harness/meter.py:84-103`, `graph/nodes/_common.py:52-58`, `graph/package.py` |
| 12 | **P2.4** brief demotion of `attach_finding` | Text only | briefs |

**Acceptance for Stage 1.** `uv run pytest tests -q` green (72 + the stage's tests). Then two Haiku
cycles here on Cycle 1's question, using `scripts/spikes/spike_11_audit_cycle.py <dir> second-cycle`
(adapt it to count answers, references, `store_evidence` calls and ungrounded marks), compared
against Cycle 1 (`production-audit-2026-09-20.md`, Cycle 1): findings kept by orientate (was 0),
answers rendered (was 0 nodes), ungrounded count, proposals per message (was 3 in one), and **A8**:
does cycle 2 cite what cycle 1 kept, or re-read it. Write the comparison into the audit log as
"Stage 1 acceptance" in the same registers. Then present to them for the merge.

**Stage 2** (`stage-2-handoff`: P3.1, P4.1, P0.3) and **Stage 3** (`stage-3-install`: P0.1, P0.5,
then P0.6 on Harness) follow, each branching from `orientate-absorbs-assume` after the previous
stage is merged.
