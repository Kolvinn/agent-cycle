# Production audit, part 2 — persistence, failure surfacing, the executor, the install shape

Status: **written 2026-09-20 by the forked session; folded into
`production-audit-2026-09-20.md` the same day (its Part 2). This file is the fork's original and is kept for the record.** Same registers as that document (E your
words, O observed with a locator, A/R an assumption and its rival, Q a question for you, P a
proposal, D a decision I took). Numbering continues from O36 and A10 there. Nothing in the code
was changed; every experiment ran on a *copy* of the live run's state under this job's
temporary directory.

Why a second file: two sessions were running this audit against one checkout after a fork at
05:00. Rather than both writing one file, this one holds F15, F16, F17, F18, F19 and F21; the
first keeps Cycle 1 (the live run), the interrupt-during-approval run, F22 and the UI branch.

---

## Cycle 6 — F16 persistence integrity

### O

| # | Observation | Locator |
|---|---|---|
| O37 | **The log/checkpoint gap (O20) is real and its outcome is a ghost cycle.** On a copy of the live run's state: the thread stands at cycle 1, synthesis, 8 checkpoints; the log holds cycle 1 with 3 assumptions, 3 rivals, 5 findings. `open_cycle` for the same session and the same question returns **2**, because cycle 1 "has records". So a frame that appended and then failed before LangGraph committed leaves the thread owing that frame; `/graph` alone re-runs it, it opens cycle 2, and cycle 1's assumptions and rivals stay in the graph as provisional nodes no thread will ever reconcile, rendered under ASSUMPTIONS MADE SO FAR in every later package. | run on the copy: `open_cycle('audit11', <question>) -> 2`; `graph/store.py:315-337`; `graph/nodes/orientate.py:164-184` |
| O38 | The one interrupt test covers the *other* order: `FrameInterrupted` is raised before the append, so nothing is written and the resume is clean. No test raises after the append. | `tests/app/test_cycle.py:255`; `tests/app/test_runner.py:257` |
| O39 | **A failed re-author sequence refunds itself.** Spend from earlier attempts is held in `attempts.spend` and appended only when an attempt succeeds. When every attempt fails and `OrientationFailed` is raised, the calls those attempts bought are gone from the log; the next `/graph` opens the frame with a full pool. E25 ("the agent can never manually refresh") holds for the model and not for the machinery around it. | `graph/nodes/orientate.py:112-146,164-172`; `antithesis.py:107-159` |
| O40 | The log is appended with `flush()` and no `fsync`; the sqlite checkpointer has its own durability. A power loss can leave the log behind the checkpoint, which is the inverse of O37 and produces a thread pointing at a cycle the log never saw. Not tested, low likelihood, listed for completeness. | `graph/store.py:274-281` |
| O41 | Two processes on one sessions directory are serialised for the *log* by the file lock. Nothing serialises two processes running the *same thread* against one `checkpoints.sqlite`; the store test covers two stores on one file, not two graphs on one thread. | `graph/store.py:240-251`; `tests/app/test_store.py:15` |
| O42 | The read side is tolerant, and tested: whole lines only, a bad line skipped. | `graph/store.py:266-271,211-222`; `tests/app/test_store.py:82` |

### A/R

| # | A | R | Decides it |
|---|---|---|---|
| A11 | The right repair for O37 is a *reservation* line: the frame writes `cycle` (already) and, on success, a `frame_done` line; `open_cycle` hands back a cycle whose last frame is not done, and the package hides cycles no frame finished. | The right repair is on the other side: the frame appends to the log **after** the node returns, in a LangGraph post-commit step, so the checkpoint is the source of truth and the log follows it. | Which invariant you want: "the log never holds what a thread did not commit" (R) or "the log is the audit trail of everything attempted" (A, and closer to the options doc §6). **Q-P9.** |
| A12 | O39 should be closed by appending the spend of a failed attempt sequence before raising. | Failed attempts are noise and should not be charged: the model produced nothing. | E8 decides it: "it is not which way they go, it is when they stop". Spend is spend. **A11's shape settles where the append goes.** |

---

## Cycle 7 — F15 failure surfacing

### O

| # | Observation | Locator |
|---|---|---|
| O43 | **Runner-level errors reach the screen and never the log.** `Runner.run` catches every exception from a command and emits a `Notice(error)` on `self.sink`, which is the TUI sink alone; the session's `events.jsonl` is fed through `self._session_sink`, which only the drivers hold. Every notice the runner itself emits (session opened, help, budgets, "abandoning the unfinished cycle", the error line) is absent from the log. The live run's log has **0** Notice lines against at least four shown. | `runner.py:66,96,123,136,236-467`; events.jsonl of the live run: `Notice` count 0 |
| O44 | `OrientationFailed` and `AntithesisFailed` propagate out of the driver (which catches only `FrameInterrupted` and `HarnessUnavailable`) to O43's handler. The user sees one line: the exception's class and message. Nothing says which attempt did what, and O39 applies. | `graph_driver.py:107-120`; `runner.py:95-96` |
| O45 | **A schema mismatch is reported to the model as a count error.** When structured output fails pydantic validation the harness emits a warning and returns `payload=None`; the frame's correction then reads "That answer named 0 assumptions. Name between one and 3." The model is told its count was wrong when its shape was. | `harness/sdk.py:168-184`; `orientate.py:139-142`; `antithesis.py:132-135` |
| O46 | **CLI absent or logged out.** In a graph frame the SDK's own error is caught and re-raised as `HarnessUnavailable` with the raw exception text, logged and shown. In chat mode `connect()` is not wrapped, so the same failure reaches O43: one unlogged line, raw class name. Neither path says what to do. Not exercised live. | `harness/sdk.py:150-154`; `chat.py:73-77` |
| O47 | The live run showed a failure mode the code handles silently: the model's first `StructuredOutput` call was rejected by the CLI ("could not be parsed as JSON") and the model retried inside the same turn. The transcript shows it as an error tool block; nothing records that the answer took two tries. | live run log, `orientate.0`; `tui/transcript.py:65-71` |
| O48 | The gate's dry-run refusals are shown as `Refused` tool blocks and recorded on the meter, but a refusal *by the handler* (a stale id, a duplicate relation) is not a `SpendEntry`, not a `ProposedWrite`, and does not survive the turn (O32). | `harness/hooks.py:137-148`; `harness/turn.py:146` |
| O49 | The status bar's "⋯ working" is the only signal that a queued command has not started; a command typed during a 56-second orientate frame (measured) sits silently. | `tui/app.py:113,121-122`; `runner.py:87-99`; live run timeline |

### Present

Nothing here is a crash. What fails is *witnessing*: the session log, which E64 says is the
record, misses every runner notice and every runner-level error, and the model is corrected
for the wrong fault when the wire schema and its answer disagree. The cheapest change with the
widest effect is one line: route the runner's notices through the session sink once a session
is open. Not done.

---

## Cycle 8 — F21 the executor as a shell (by reading only)

The executor is the only path by which model-chosen text becomes a process. It runs with the
app's own privileges and the studied project as its working directory. What follows names the
classes of check it makes and does not make; it deliberately contains no commands.

| # | Observation | Locator |
|---|---|---|
| O50 | What the fence checks: shell metacharacters anywhere in the string; the executable's basename against an allow-list; `git` restricted to a subcommand list; `sed` to `-n` with at least one print-range script and no `-i`; `find` to a forbidden-flag list; and any argument that is absolute or contains `..`, resolved and required to be under the working directory. Timeout 20 s, cap 80 lines / 6 KB, stdin closed. | `harness/evidence.py:59-91,108-125` |
| O51 | **Arguments that begin with a dash are never fenced.** The path check skips them. Several allowed executables accept a file path attached to an option, so a path outside the working directory can travel inside an option without meeting the check. | `evidence.py:84-86` |
| O52 | **Relative paths are never resolved.** Only absolute paths and paths containing `..` are resolved and compared to the root. A relative path that is a symbolic link to somewhere outside the tree is passed through untouched. | `evidence.py:87-90` |
| O53 | **The sed check is satisfied by one expression and inspects no other.** It requires `-n` and *at least one* print-range script; further script expressions on the same command line are not examined, and sed's script language has commands that write. | `evidence.py:75-80` |
| O54 | **The git subcommand list is checked; each subcommand's own options are not.** Some read-only subcommands accept options that write their output to a path, or run external commands. | `evidence.py:72-74` |
| O55 | Every refusal class in O50 has a test; none of O51–O54 does. `Bash` is off every frame's surface, so this executor is the whole of the model's process access, as the options document says. | `tests/app/test_evidence.py:40-52`; `graph/surface.py:76-82` |
| O56 | The working directory the fence protects is `AppConfig.cwd`, the studied project. Under the install shape of F19 that is the host project, which is the right root. | `harness/sdk.py:130`; `config.py:363` |

**P-21.** Three changes close O51–O54 without changing the tool's shape: (i) resolve *every*
argument that names an existing path, dash or not, and fence it; (ii) for `sed`, accept
exactly one script expression and require it to be a print range; (iii) for `git`, an
allow-list of options per subcommand rather than a subcommand list alone. Each gets a test that
fails first. Until then the executor is safe against a model that is not trying, which is the
case the design assumes (E11), and not against one that is.

---

## Cycle 9 — F17 provisional numbers and F18 observability, as written maps

### F17

| # | Observation | Locator |
|---|---|---|
| O57 | E33 ("make sure to note that they are not set") is met in one place: `/budget` with no arguments prints "(provisional)" beside eight fields. | `runner.py:389-398` |
| O58 | `provisional_fields()` and `unclassified_budget_fields()` are defined for "a run to disclose" and called by nothing in the app. The events log, the session record, the package and the briefs carry no marker. | `config.py:120-128`; grep over `app/` |
| O59 | `Grep->survey` is in `PROVISIONAL` and is not a budget field, so `/budget` never prints it: the one provisional *price class* is disclosed nowhere. | `config.py:45-53,102-114` |
| O60 | The numbers the user set (E5, E27b) are `SETTLED`; `/prices` shows them with no marker either way, which is correct. | `config.py:117` |

### F18

| # | Observation | Locator |
|---|---|---|
| O61 | **The session log is 73 % stream deltas.** The live run's `events.jsonl`: 777 KB, 5 525 lines; `ThinkingDelta`, `TextDelta` and `ToolInputDelta` account for 5 346 lines and 570 KB. Result-level events are 179 lines. E64 names exactly this. The user's own run inside Harness on 2026-09-19 left a 655 KB log for one cycle. | live run log by event kind; `Harness/sessions/s-20260919-100109/events.jsonl` |
| O62 | The log carries no runner notices and no runner errors (O43). | `runner.py:96` |
| O63 | Cost is visible in one place, the status bar's running total from `TurnFinished`; it is not in the session record, not in the graph log, and per-cycle cost is not derivable without reading the events log. The live cycle cost $1.21 on Haiku across four turns. | `tui/panels.py:153-155`; `session.py:29-46` |
| O64 | There is no rotation, no size cap and no per-cycle file; one session's log grows for its life. | `harness/events.py:229-243` |
| O65 | Build-plan item E3 ("run log for the new loop") was never built; the events log is what exists in its place. | `build-plan-2026-09-19.md` §6 stage E |

---

## Cycle 10 — F19 the install shape (E59)

> E59 "make it standalone in a git repo that I can pull down into the harness and gitignore
> it there, so I can update THIS project and pullit into whatever project I'm using to act as
> the agent harness."

### O — what running against Harness does today

| # | Observation | Locator |
|---|---|---|
| O66 | **You already ran it against Harness, twice, on 2026-09-19** (07:12 and 10:01, both entering the graph; the second ran all three frames with 16 priced calls). Those runs predate the graph store, so no `graph/` directory exists there. | `Harness/sessions/s-20260919-*.json`; `s-20260919-100109/events.jsonl` |
| O67 | **That state landed inside Harness and is untracked, not ignored.** `git status` in Harness shows `?? sessions/`; Harness's `.gitignore` names neither `sessions/` nor anything of this app. A `git add -A` there would commit a 352 KB sqlite file and the event logs. | `Harness/.gitignore`; `git status --short` in `Harness/` |
| O68 | Three directories are conflated by `--cwd`: the *studied* project (what the model reads and the executor's fence), the *install* (this repo: `modes.toml`, `prompts/`), and the *state* (`sessions/`, the graph log, checkpoints, event logs). `AppConfig.default` puts `sessions/` and `modes.toml` under `cwd`; only `prompts/` resolves to the package. | `config.py:374-381`; `tui/app.py:228-231` |
| O69 | Harness has no `modes.toml`, so the `/reviewer` mode defined in this repo's file does not exist there. Modes travel with the studied project rather than with the install. | `ls Harness/modes.toml` → none; `config.py:377` |
| O70 | The entry point runs from outside the clone: `uv run --project <clone> langchain-claude-test --help` succeeds from an unrelated directory. Harness already carries `pyproject.toml` (Python ≥ 3.14) and `uv.lock`, so the toolchain is present on the host. | run this session; `Harness/pyproject.toml` |
| O71 | **The CLI keys its own transcripts by the working directory string.** Under `~/.claude/projects/` this machine holds `-home-jeremy-dev-Harness` and `-workspaces-Harness` and `-workspaces-langchain-claude-test-Harness` as three separate projects for what is one repository on three mounts. A session record stores SDK conversation ids; a graph cycle's `conversation` is checkpointed. Resumed from a different mount, `resume=` names a conversation the CLI cannot find under that key. | `ls ~/.claude/projects/`; `session.py:38`; `state.py:417`; `harness/sdk.py:104` |

### A/R

| # | A | R | Decides it |
|---|---|---|---|
| A13 | On a mount mismatch (O71) the frame fails with `HarnessUnavailable` and the cycle cannot continue; the session is effectively dead for the graph. | The CLI starts a fresh conversation silently when the id is unknown, and the cycle continues with the package only, having lost the in-cycle context. | One live run: open a session's cycle with `--cwd` pointing at the same tree through a different path. Cheap, Haiku. Not run this session. |
| A14 | The minimal install that satisfies E59 today is: clone this repo to `Harness/.provenance`, add `.provenance/` to Harness's `.gitignore`, run `uv run --project .provenance langchain-claude-test --cwd .` from Harness. Everything works except that state lands in `Harness/sessions` (O67). | The clone's own `.venv` and lock resolution under `uv run --project` fail on the host for a reason the devcontainer hides. | Run it once on the host. **Q-P10** below asks whether I may. |

### P — the shape, for your review, not built

- **P-19a.** Split the three directories in `AppConfig`: `cwd` = studied project (unchanged);
  `home` = the install (default: the package's parent repo); `state_dir` = where sessions,
  graph and logs live (default: `<home>/sessions`, so the clone's own `.gitignore` covers it
  and nothing lands in the host). `modes.toml` resolves from `state_dir`'s parent, then `home`,
  then the package. `--cwd` keeps its meaning; a `--state` flag overrides.
- **P-19b.** One graph per studied project, keyed by the studied project's *resolved real
  path* rather than its string, so O71 does not split one project's graph across mounts. The
  SDK conversation ids remain mount-bound (that is the CLI's key, not ours); the session
  record should store the cwd it was created under and the runner should say so when the
  strings differ.
- **P-19c.** A `README.md` at the repo root (it is empty today) with the three-line install
  above and the one rule: the clone is ignored by the host, the host is read by the clone.

### Q

| # | Question | P |
|---|---|---|
| Q-P9 | For the log/checkpoint gap (O37): is the log the audit trail of everything *attempted* (then hide unfinished cycles and add a done-marker), or of everything *committed* (then append after commit)? | Attempted, with a done-marker; it keeps "why is this here" answerable from the file alone. |
| Q-P10 | May I do the A14 install run inside `Harness/` (a clone under an ignored directory, nothing else touched), or do you want to do that one yourself? | You do it, from the README, so the README is tested by its reader. |
| Q-P11 | Should the state directory default to the install (`<clone>/sessions`) or to a dot-directory in the studied project (`<host>/.provenance/`)? The first needs nothing added to the host's `.gitignore` beyond the clone itself; the second keeps state beside the code it is about. | The install. One ignore line, and updating the clone never touches the state. |

---

## F20 — tests against flows, one line

O35 in the main log is the map. The one addition from this part: **no test drives an error
path** — not `HarnessUnavailable`, not a re-author sequence to exhaustion, not a schema mismatch,
not a crash after the log append (O38). Every failure-surfacing observation above (O43–O49) is
untested by construction.

---

## Ledger lines for §7 of the main log

| # | Flow | Finding (one line) | Evidence | Your verdict |
|---|---|---|---|---|
| L1 | F16 | A crash after a frame's log append and before the checkpoint leaves a ghost cycle the next run duplicates | O37, simulated on a copy | |
| L2 | F16 | A frame that fails every re-author attempt refunds the points it spent | O39 | |
| L3 | F15 | Runner notices and runner-level errors never reach the session log | O43, live log: 0 notices | |
| L4 | F15 | A schema mismatch is corrected as a wrong count | O45 | |
| L5 | F21 | Dash-prefixed, relative and second-expression arguments escape the executor's fence | O51–O54, by reading | |
| L6 | F17 | Provisional numbers are disclosed only by `/budget`; the provisional price class nowhere | O57–O59 | |
| L7 | F18 | The session log is three-quarters stream deltas and misses the shell's own lines | O61, O62 | |
| L8 | F19 | Running against Harness wrote untracked state into Harness; you did this twice on 09-19 | O66, O67 | |
| L9 | F19 | The CLI keys conversations by the cwd string; a session moved across mounts cannot resume its cycle | O71, A13 | |
| L10 | F19 | `--cwd` conflates studied project, install and state; P-19a splits them | O68 | |

---

## Cycle 11 — F4 the approval surface (reading, the Cycle 1 events, and Pilot)

The product questions, as the other session put them: what the user sees at the modal, whether
the refusal words reach the model in a form it can act on, and what happens on the screen while
five approvals arrive in one 78-second turn. Sources: the Cycle 1 events log (five gated calls in
the synthesis reply: two approved, three refused with words), the code, and three headless Pilot
runs against the real app with no model behind it. Numbering from O90 / A20 by agreement.

### O — what the modal shows

| # | Observation | Locator |
|---|---|---|
| O90 | The modal is: a header ("The agent proposes a change to the graph: close_node"), the request's `title`, the `description`, the whole tool input as a JSON dump, the words box (focused), two buttons. `title` is the CLI's title or `"<write> <target>"`; `description` is the handler's dry-run text. In the live run the five titles were `propose_fact` (no target, so it duplicates the header), `close_node x1.1`, `close_node x1.2`, `close_node x1.3`, `close_node a1.1`; the descriptions were `Registered e1.1: "…" grounding x1.1, x1.2, x1.3`, `x1.1 is now confirmed.`, `x1.2 is now refuted.`, … | `tui/screens.py:46-60`; `harness/hooks.py:150-178`; `harness/tools.py:311,477`; events log `ApprovalAsked` ×5 |
| O91 | **The node's text is not on the modal.** For `close_node x1.2` the user sees the id and "x1.2 is now refuted." and must remember what x1.2 claims. They cannot look it up: the modal captures input, the panel behind it is inert, and `/show node x1.2` would queue behind the turn in flight (O7). The one effect text that quotes node text is `merge`'s. | `tui/screens.py:50-55`; `harness/tools.py:428-433,467-477`; O7 |
| O92 | **The model's reason is the best line and the least visible.** `because` was substantive on every call ("The fact identifies surface.py as where the surface is decided; surface.py is read when SdkHarness.options() is called…") and appears only inside the JSON dump. The labelled description — "x1.2 is now refuted." — is written in the past tense of a thing that has not happened, because the dry run reuses the handler's completion message. | events log `ApprovalAsked.input.because`; `harness/tools.py:93-97,477` |
| O93 | **Words ride both ways, live (D6 holds).** Approved: the model's tool result was `Approved by the user. Their words, verbatim: "yes, that is where it lives" Registered e1.1: …`. Refused: `REFUSED BY THE USER. Their words, verbatim: no - a refuted rival is not the same as a wrong one; leave it open`. | events log `ToolResult` for the five calls; `harness/hooks.py:199-201`; `harness/tools.py:63-65` |
| O94 | **The words reached the model; its next proposal did not honour them.** Order in the turn: `propose_fact` → **three `close_node` calls in one assistant message** (x1.1 approved; x1.2 refused with the reason above; x1.3 refused "not this cycle") → three `graph_search` → `close_node a1.1 refuted` → refused "not this cycle" → final text. The reason given on x1.2 applied equally to the a1.1 proposal that followed it. The final text ("Understood. I've confirmed the one rival…") lists what closed and what "remains open pending further examination" and does not mention that three proposals were refused or why. | events log 04:52:51–04:53:50; final `TextDone` |
| O95 | **Parallel gated calls become stacked modals answered in reverse.** The SDK spawns a task per permission request, so three requests arrive together; the approver pushes one screen each. Pilot: stack `['Screen', 'close_node x1.1', 'close_node x1.2', 'close_node x1.3']`, the user sees **x1.3** first, and the answers resolve x1.3, x1.2, x1.1. The user's answer to one cannot inform the others because the model issued them together. This is the first measured instance of Q-6 ("per call first; batch when it hurts") hurting. | `claude_agent_sdk/_internal/query.py:303-312`; `tui/screens.py:163-167`; Pilot K2; events log 04:53:09.430–.450 |
| O96 | **The advertised approve key does not work.** The modal binds `ctrl+y` / `ctrl+n` and focuses the words box, a `TextArea`, which binds `ctrl+y` to redo; a focused widget's binding beats a non-priority screen binding. Pilot: `ctrl+y` with the box focused leaves the request pending; `ctrl+n` refuses. The keyboard path that works: one `Tab` to the Approve button, then `Enter`. | `tui/screens.py:39-40,62-63`; `textual/widgets/_text_area.py:417`; Pilot K1 and TAB |
| O97 | **Esc with a modal open fires the interrupt and leaves the modal up.** Pilot: `runner.interrupt` called once, the screen still the approval modal, its future pending. Live, that is `client.interrupt()` sent while the CLI's permission request is outstanding — what the CLI does then is the other session's Cycle 2 (A9). Esc when nothing is running also calls interrupt and shows nothing. | `tui/app.py:68,141-142`; `tui/screens.py:163-167`; Pilot ESC lines |
| O98 | **Time.** The reply turn took 78 s with instant scripted answers. Each modal adds the human's time on top; the SDK side awaits `can_use_tool` with no timeout. The transcript keeps streaming behind the modal (D6) but is dimmed and not scrollable while it is up. | events log timeline; `claude_agent_sdk/_internal/query.py:475-535` |
| O99 | **The refusal register has one meaning; the words have several.** The package renders every refused proposal under "THE USER REFUSED THESE. Do not propose them again" and quotes the words. Two of the three refusals said "not this cycle". The header overrides the words for the next cycle's reader. | `graph/package.py:183-192`; live package output |

### A/R

| # | A | R | Decides it |
|---|---|---|---|
| A20 | The model treats a refusal as terminal for *that node* and not as guidance for its next proposal (O94), because the refusal arrives as a tool result and the brief says "read them" but nothing makes the next call's `because` answer the last refusal. | One Haiku run; a second run or a stronger model honours the words. | The other session's live runs: does any later proposal's `because` quote the refusal? By reading the events log, no live spend needed beyond what is planned. |
| A21 | The CLI does not time out an outstanding permission request, so a modal left open holds the turn indefinitely and the subscription is not charged for the wait. | The CLI times out and the SDK receives an error, which the harness surfaces as `HarnessUnavailable` mid-turn. | Leave a live modal unanswered for a few minutes once (Haiku; other session). |

### Present

The surface works as designed on the wire: words reach the model both ways, the dry run stops
malformed proposals before they are asked. What fails is the *reading* end of the modal: the
user decides on an id without its text, the model's reason is buried, the effect line is
phrased as done, the approve key is dead, and three calls at once arrive as three modals in
reverse with the words for one applied to none of the others. Options, each possibly wrong:
(i) put the node's text and the model's `because` on the modal as labelled lines and phrase
the effect as "would"; (ii) fix the key by binding approve with priority or moving focus to
the buttons; (iii) for O95, either serialise the approver (one modal at a time, in call order,
the transcript line saying "2 more waiting") or build the batch modal Q-6 deferred. None
started.

---

## Cycle 12 — F7 sessions (reading and scripted)

### O

| # | Observation | Locator |
|---|---|---|
| O100 | A session record holds name, created, focus, mode, conversation ids, model, effort, budget and price overrides, forked_from. Not: the working directory (O71), cost, last activity, the cycle it stands at or the question it asked. `/sessions` prints name, focus, mode, created. To find "the one where I asked about the webhook" you resume each. | `session.py:29-46`; `runner.py:251-256` |
| O101 | Every unnamed launch creates a session and nothing deletes or renames one; the listing only grows. Four such records exist in this repo and two in Harness from single days of use. | `runner.py:82-86`; `commands.py:37-52`; `ls sessions/` |
| O102 | `/resume` wants the exact name; Tab completion covers commands only. | `tui/prompt.py:86-90`; `runner.py:257-263` |
| O103 | **A fork shares the chat conversation by reference and forks the graph conversation by flag.** `/fork` copies `conversations` (the chat modes' CLI session ids), so the fork and its source both `resume=` one CLI session for chat; the graph's conversation is forked on the next frame (`fork_conversation`), which is tested. The SDK's own docs say forking "branches the conversation history" and is what `fork_session=True` is for. | `runner.py:492`; `chat.py:63`; `tests/app/test_runner.py:134-166`; `docs/agent-sdk/sessions.md:291-312` |
| O104 | **Forking a session whose first frame was interrupted skips the frame it owes.** The fork is seeded with `as_node=state.stage`, and before any frame has run `stage` is its default, `orientate`. LangGraph then reads the seed as "orientate just ran" and the fork owes **antithesis** with `cycle=0` and no assumptions. Scripted: source owes `('orientate',)`; after `/fork branch` the fork owes `('antithesis',)`; `/graph` in the fork runs antithesis on cycle 0, which asks the model for exactly zero rivals and retries until it raises. The source is unaffected. | `runner.py:506-508`; `graph_driver.py:122-124`; `state.py:406-409`; scripted run `scripted_f7.py` this session |
| O105 | `/new` and `/resume` close every client; the next message reopens the chat by id and the next frame re-opens the cycle's conversation by id. Nothing else is lost by switching, and a switch cannot happen during a turn (O7). | `runner.py:111-141,181-188` |
| O106 | The graph is shared by every session of a state directory (Q-7, by design). Two sessions asking the same question open two cycles, and both sets of provisional nodes render in every later package; nothing marks the second as a duplicate of the first. | `graph/store.py:315-337`; `graph/package.py:124-143` |

### A/R

| # | A | R | Decides it |
|---|---|---|---|
| A22 | Two sessions resuming one CLI session id for chat (O103) interleave one transcript: whichever speaks second continues the other's last turn. | The CLI forks on resume when the transcript has moved on, so each gets its own branch. | One chat turn in a source and one in its fork, Haiku (other session), then inspect the CLI transcript directory for one file or two. |
| A23 | The second variant of O104: a session at synthesis of cycle N that runs `/graph <new question>` and is interrupted during orientate still has `stage == synthesis`; a fork seeds it `as_node=synthesis`, LangGraph routes synthesis→END, and the fork owes nothing — the pending `/graph` is silently dropped in the fork. | The seed's `advance=True` makes the entry router send it to orientate on the next run anyway. | Scripted, ten lines on the pattern of `scripted_f7.py`; not run this session because O104 already shows the seed is the wrong instrument. |

### Present

Sessions do what the tests say, and the tests do not cover a fork of an interrupted thread.
O104 is a defect with a clear cause: the seed names the last *completed* stage, and the runner
has no record of what the source *owes*. The fix is on the fork side (seed as the node
*before* the owed frame, which `pending()` already knows), not in LangGraph. The rest is
product: a listing that says what each session is about, completion of session names, a way
to remove one, and a decision on whether a fork's chat should branch (P: yes, `fork_session`
on the fork's first chat message, mirroring the graph).

---

## Cycle 8, addendum — the executor from the product side

Per the other session's relay of your framing: not how the fence could be defeated, but what
a survey needs the executor to do and where it gets in the way. From the Cycle 1 events.

| # | Observation | Locator |
|---|---|---|
| O107 | **The survey kept nothing.** Orientate — the frame whose brief says "keep what you read" as step 2 — made 12 priced calls for 19 of its 20 points (Glob ×3, Read ×8, Grep ×2) and called `attach_finding` **zero** times. Antithesis made 2 priced calls and kept 5 findings with `attach_finding`. So the package's CONTEXT section (what the surveys read and kept) is empty, and the next cycle inherits three assumptions with no evidence under the question. The free tool went unused in the frame built around it. | events log per-turn tally; `graph/nodes/orientate.py:52-58`; live package output (no CONTEXT block) |
| O108 | **Three of the twelve priced calls bought nothing.** A `Read` of the working directory itself (EISDIR), and two whole-file reads of design documents not about the question. Charging happens before the call runs (by design, `meter.py`), so an error costs the same as a result. E11's first purpose — "not pollute their context by reading outdated and unnecessary files" — was not served by the price alone. | events log `orientate.0`; `harness/meter.py:78-123` |
| O109 | **The kept path is the unfamiliar one.** `Read`/`Grep` take the arguments the model already knows; `attach_finding` asks it to compose a `sed -n 'a,bp' <path>` string and name a target. Where it was used (antithesis) it worked five times out of five with no refusal, so the executor is not what gets in the way; the choice between two ways to read is. | `harness/tools.py:129-150`; events log `antithesis.0` |

**P-8.** Two candidate shapes for F22 rather than fixes here: (i) in the surveying frames a
priced `Read` or `Grep` *is* the finding — the PostToolUse hook already holds the result and
could record it, so keeping is what looking does and `attach_finding` becomes the way to keep a
range of something already seen; (ii) leave two paths and make the brief's step 2 a requirement
the payload checks (an assumption must cite at least one finding). (i) matches "keep what you
read" literally and E12's "tool calls are replaced … with the output of the graph"; (ii) is one
line. Your call; neither started.

---

## Ledger lines, continued

| # | Flow | Finding (one line) | Evidence | Your verdict |
|---|---|---|---|---|
| L11 | F4 | The approval modal shows an id and a done-tense effect, not the node's text or the model's reason | O90–O92 | |
| L12 | F4 | The advertised approve key is swallowed by the words box; Tab+Enter works | O96, Pilot | |
| L13 | F4 | Parallel gated calls stack modals answered in reverse; the words for one reach none of the others | O95, Pilot, events | |
| L14 | F4 | Esc behind a modal fires the interrupt and leaves the modal up | O97, Pilot | |
| L15 | F4 | The next cycle reads every refusal as "never", including "not this cycle" | O99 | |
| L16 | F7 | Forking a thread interrupted in its first frame skips the owed frame and runs antithesis on cycle 0 | O104, scripted | |
| L17 | F7 | A fork shares the chat conversation id with its source | O103, A22 | |
| L18 | F21 | The survey frame used the free keep path zero times and the priced look path twelve; CONTEXT came out empty | O107–O109 | |

---

## Settled by the other session's live run (relayed 2026-09-20, recorded there as O86–O89, A18)

| Mine | Outcome |
|---|---|
| O97 (Esc behind a modal) | Continues into a crash: the CLI aborts the turn about half a second after the interrupt and cancels the approver's await (`error_during_execution`, `aborted_tools`); nothing lands in the graph; the conversation resumes on the same id. Headless, answering the orphaned modal afterwards raises `InvalidStateError` on the cancelled future and the app exits with return code 1. So L14 is not "modal left up" but "the next keypress crashes the app". |
| A20 | **Confirmed by reading.** No later proposal in Cycle 1 quoted a refusal's words; the one proposal made after a refusal reasoned from the confirmed rival instead. |
| A21 | Not measured; every ask in the live runs was answered within two seconds, and a timeout wait was judged not worth a live run. Stays **A**. |
