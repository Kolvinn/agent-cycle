# UI workflow — overview of changes, 2026-09-20

Status: **overview written, nothing implemented yet.** Branch `ui-workflow`, in a worktree off
`orientate-absorbs-assume` (fa8f871). Nothing merges until you say (audit D-P2).

This is the hand-off the audit made in `production-audit-2026-09-20.md` §4a, D-P2: the UI
checklist, measured against the Claude Code CLI's own shell (E63), written up before it is
built. The registers are the audit's:

| Marker | Meaning |
|---|---|
| **E** | Your words, verbatim, typos preserved. |
| **O** | Observed: a locator in this repository, or a run. Re-checkable. |
| **A** | An assumption I hold, with what would settle it. |
| **D** | A decision I took, with its reason, to be agreed or overturned. |

Locators are `file:line` against this branch at fa8f871. `app/` means
`src/langchain_claude_test/app/`.

---

## 0. The words this work answers

| # | Your words |
|---|---|
| E55 | "I should be able to copy and paste and do all the regular workflow operations." |
| E58 | "for me alone, so it needs to be smooth and versitile enought to not interrupt workflwo." |
| E62 | "should be able to work in any terminal though." |
| E63 | "You can consider from the perspective of something like claude cli - what's missing, lets add it. You dont have to work on the graph view at all, it's bad and will need rethinking, so just leave it for now." |
| E64 | "you should have the logs output individual stream tokens though, that's too much, just result messages." |

**Read of E64** (the audit's, carried here): the per-session `events.jsonl` must **not** log
stream deltas; result-level events only. `JsonlSink` is `app/harness/events.py:229-243`;
it is opened per session at `app/runner.py:122`, path from `app/session.py:78`.

**Read of E62**, which constrains every clipboard and key item below: no terminal-specific
mechanism may be the *only* way to do a thing. Textual copies out through OSC 52
(`App.copy_to_clipboard`, `textual/app.py:1770`), which some terminals and multiplexers drop.
So every copy/expand item gets **both** a key and a `/` command, and the transcript keeps the
text so a command can reach it.

---

## 1. What I measured against — the Claude Code CLI shell

**A (from use, not from its source — I cannot read the CLI here).** The shell operations the
Claude CLI gives that a user reaches for without thinking:

paste (bracketed, multi-line, does not send) · up/down history · Esc to stop the turn ·
Esc that means "leave this prompt" inside a dialog, not "stop everything" · ctrl+l to clear the
screen without clearing the conversation · ctrl+o to expand a truncated tool output ·
`/clear` for the conversation · select-and-copy with the mouse, and a copy that does not
depend on the terminal · typing while the model is working, with the queued line visible ·
`--continue` reopening the last conversation instead of starting a blank one · a status line
that says where you are (cwd, model) · a visible sign of *which* step is running · ctrl+c/ctrl+d
that close cleanly.

What this project has on top, and what the CLI has no equivalent of, is the frame/budget/approval
surface. Nothing below touches it.

---

## 2. What ours does today — O, with locators

| # | Observation | Locator |
|---|---|---|
| O-U1 | The suite is **58 passed** on this branch. | `uv run pytest tests -q` |
| O-U2 | The prompt handles `enter`, `shift+enter`/`ctrl+j`, `tab`, and defers everything else to `TextArea`. It has **no `up`/`down` handling and no history**. A paste is not a key: `TextArea._on_paste` inserts the whole text (`textual/widgets/_text_area.py:1982`), so `_on_key` never sees it. **No test posts a `Paste`.** | `app/tui/prompt.py:58-76`, `tests/app/test_prompt.py` |
| O-U3 | Tool results are cut at 24 lines with **no way to expand**, and the full text is thrown away — `result()` renders the truncated string and keeps nothing. | `app/tui/transcript.py:15,65-71` |
| O-U4 | `ToolBlock` extends `Collapsible`, which sets `ALLOW_SELECT = False` (`textual/widgets/_collapsible.py:22`). There is **no copy command at all**: `copy_to_clipboard` is never called anywhere in this repo. | `app/tui/transcript.py:24`; `grep -r copy_to_clipboard src` → nothing |
| O-U5 | `escape` is an **app-level priority** binding for interrupt. Textual checks priority bindings `reversed(screen._binding_chain)` — **App first, then the screen, then the focused widget** (`textual/app.py:3966-3986`, `textual/screen.py:408-455`). So a screen-level binding, priority or not, cannot outrank it. `ChoiceScreen` binds `escape` non-priority; `ApprovalScreen` and `QuestionScreen` bind nothing. | `app/tui/app.py:68`; `app/tui/screens.py:40,81,123` |
| O-U6 | Every `/` command goes on **one FIFO queue** and waits behind whatever turn is in flight. | `app/runner.py:55,76-77,87-99` |
| O-U7 | **Every launch without a name creates a new timestamped session**; the name is only reused when it was given and already exists. | `app/runner.py:82-86`, `app/session.py:99-108` |
| O-U8 | **`StageStarted` is defined and never emitted.** Nothing in the repo constructs it; the driver emits `StageFinished` + `StateSnapshot` only, *after* a frame ends. | `app/harness/events.py:140-144`; `grep -rn StageStarted --include=*.py` → only the definition and the union; `app/graph_driver.py:107-120` |
| O-U9 | What *is* emitted when a frame starts is `TurnStarted(label, kind="graph", stage=<frame>, cycle=<n>)`. The transcript's `TurnStarted` case only closes open blocks — **it draws nothing**. | `app/harness/sdk.py:133`, `app/harness/scripted.py:102`; `app/tui/transcript.py:141-142` |
| O-U10 | `Priced` carries `pool` and `remaining` per call. The status bar ignores it; the panel's pools come only from `StateSnapshot`, which arrives after the frame. So during a frame **nothing on screen moves except "⋯ working"**. | `app/harness/events.py:100-109`; `app/tui/panels.py:147-158`; `app/graph_driver.py:114-115` |
| O-U11 | `/clear` is in `PASSTHROUGH` and goes to the SDK conversation. There is **no transcript clear and no ctrl+l**. | `app/commands.py:55`; `app/tui/app.py:67-77` |
| O-U12 | `JsonlSink.emit` writes **every** event, deltas included. | `app/harness/events.py:236-243` |
| O-U13 | Two quit paths: `/quit` calls `on_quit` (= `App.exit`) **then** enqueues QUIT, so `_close_clients` runs only if the runner worker survives the app's exit; `ctrl+q` is Textual's own `action_quit` and never touches the runner at all. | `app/runner.py:240-245,100`; `app/tui/app.py:69,87` |
| O-U14 | Esc with nothing running calls `runner.interrupt()`, which returns silently when no driver is live. No feedback. | `app/tui/app.py:141-142`; `app/runner.py:219-228` |
| O-U15 | A line typed while a turn runs is drawn in the transcript immediately, indistinguishable from one that is being answered. | `app/tui/app.py:130-135`; `app/tui/transcript.py:100-103` |
| O-U16 | The status line shows session, focus, cycle/stage, model, effort, cost, busy. **Not the cwd** — and the cwd is what the executor is fenced to and what a bundled install points at (E59). | `app/tui/panels.py:160-165`; `app/config.py:374-379` |

### A — what the overview cannot settle by reading, and the test that will

| # | **A** | The test that settles it |
|---|---|---|
| A1 | A multi-line paste inserts into the prompt and does **not** send (audit A1). | Pilot posts `events.Paste("a\nb\nc")` to the prompt and asserts the text and that no `Submitted` fired. |
| A2 | Esc inside the approval modal fires the **app's** interrupt while the modal stays up with an unresolved future (audit A2). | Pilot: push `ApprovalScreen`, press escape, assert the screen is still on the stack and the harness recorded an interrupt. |
| A3 | Esc in the `/model` picker never reaches `action_leave` (audit A3). | Pilot: push `ChoiceScreen`, press escape, assert it is **not** dismissed. |
| A4 | Mouse select-and-copy over a tool result is blocked by `Collapsible.ALLOW_SELECT = False` (audit O2). | Only partly testable headlessly: a Pilot test can assert `ToolBlock.ALLOW_SELECT` and that `Screen.get_selected_text()` returns the result text after `text_select_all()`. Whether *your* terminal's drag reaches it is **you** (audit A4), which is exactly why E62 forces a command path as well. |
| A5 | A read-only `/show` that runs *beside* a live frame can read a torn last line of `graph/ops.jsonl` while a frame is appending to it. | Not settled here. It is the audit's own S-2 item. I note it below and keep `/show` on the fast lane because you named it; the rival is "the store's reader tolerates a torn line", which the audit must check. |

---

## 3. The changes — one commit each, test first

Each row: what the CLI gives that we do not · our locator · the change · the test that must
fail before it.

### a. Paste (E55)

- **CLI**: a bracketed multi-line paste lands in the prompt as text.
- **Ours**: O-U2 — untested, and the whole of E55's "paste" rests on an unverified A1.
- **Change**: whatever the test shows. If A1 holds, no production change — the finding *is* a
  regression test so that a later prompt change cannot silently break it. If A1 is refuted,
  `PromptInput` grows an `_on_paste` that inserts and stops the event.
- **Test**: `tests/app/test_prompt.py::test_a_multiline_paste_inserts_and_does_not_send` —
  `app.prompt.post_message(events.Paste("a\nb\nc"))`, assert `prompt.text == "a\nb\nc"`, assert
  `app.submitted == []`, assert the box grew to three lines.

### b. Copy out, without depending on the terminal (E55, E62)

- **CLI**: mouse selection copies; tool output expands with ctrl+o.
- **Ours**: O-U3 (cut at 24 lines, full text discarded), O-U4 (no copy path at all).
- **Change**, three parts:
  1. `ToolBlock` keeps the full result text; the truncation note names how to see the rest.
     `expand()` re-renders it whole and opens the block.
  2. `/expand [last|<n>]` and **ctrl+o** expand the last (or nth-from-last) tool result.
  3. `/copy [last|tool|user]` copies the last assistant message / last tool result in full /
     last user line through `App.copy_to_clipboard`. `last` is the default.
     The transcript keeps `last_assistant`, `last_user` and the tool blocks in order.
  4. `ToolBlock.ALLOW_SELECT = True`, overriding `Collapsible`, so the mouse path is not
     blocked where the terminal supports it (A4).
- **Test**: `tests/app/test_tui.py::test_a_tool_result_expands_and_copies_without_the_terminal`
  — apply a 30-line `ToolResult`; assert the body is cut and says so; `/expand`; assert the body
  holds all 30 lines; `/copy tool`; assert `app._clipboard` is the full 30 lines; `/copy user`
  and `/copy last` likewise; ctrl+o on a fresh block does the same as `/expand`.

### c. Prompt history (E55 "regular workflow operations")

- **CLI**: up/down recalls previous entries.
- **Ours**: O-U2 — nothing.
- **Change**: `PromptInput` keeps the entries it submitted. `up` on the **first** line recalls
  the previous entry, `down` on the **last** line walks back toward the draft, and on any other
  line both keys move the cursor as `TextArea` always did. The unsent draft is restored when you
  walk past the newest entry. Consecutive duplicates are not recorded.
- **D-U1 (persistence: per run, in memory).** The history lives on the prompt widget for the
  life of the launch and spans session switches. *Why*: it introduces no new on-disk format,
  nothing to corrupt or migrate, and nothing that leaks into a host project when this repo is
  cloned into one and gitignored (E59). *The rival*: the CLI persists history across restarts,
  and you may want that; it is one file (`sessions/<name>/history`) away, and I will add it if
  you say. Per-session-file history is the worse of the three, because `/new` and `/resume`
  would throw away a recall you were halfway through.
- **Test**: `tests/app/test_prompt.py::test_up_and_down_recall_history_without_fighting_multiline`
  — submit three lines; `up` three times walks back; `down` returns to the empty draft; then
  type a two-line message, put the cursor on the second line, press `up`, and assert the text is
  unchanged and only the cursor moved.

### d. Esc inside modals (E58 "not interrupt workflwo")

- **CLI**: Esc in a permission dialog answers the dialog; it does not also kill the session.
- **Ours**: O-U5. A2/A3 say Esc in *any* modal runs the app's interrupt instead.
- **Change**: leave the app binding priority (it must still work with the prompt focused, which
  is the whole reason it is priority) and make the **action** modal-aware. Each modal screen
  gains one method saying what Esc means to it; `action_interrupt` asks the top screen first.
  - `ChoiceScreen` (`/model`, `/effort`): leave, unchanged — `dismiss(None)`.
  - **D-U2: `ApprovalScreen` on Esc refuses the call**, with whatever words are typed, exactly
    as ctrl+n does. *Why*: the modal is a future the harness is blocked on
    (`app/tui/screens.py:163-167`); dismissing without a verdict hangs the turn, and refusing is
    the conservative answer — nothing happens to the graph, the model is told, and the words
    ride back (D6). It also matches the CLI, where Esc at a permission prompt rejects the call.
    *The rival*: Esc is a reflex and a stray press now refuses a call you meant to approve. If
    you prefer, Esc becomes a no-op with a hint line; say so and it is a one-line change.
  - **D-U3: `QuestionScreen` on Esc answers the question with an empty string**, which is what
    "I am not answering that" looks like to the caller. Same reason: a modal that dismisses
    without resolving hangs the frame.
  - In every case Esc **does not** reach the harness interrupt while a modal is up.
- **Test**: `tests/app/test_tui.py::test_escape_in_a_modal_leaves_the_modal_not_the_turn` — and
  it asserts A2/A3 **before** the change in the same file's history (the commit message records
  the failing run). After: push `ChoiceScreen`, escape, assert dismissed with `None` and the
  harness recorded no interrupt; push `ApprovalScreen`, type words, escape, assert the verdict
  is `approved=False, words=…, answered_by="human"` and no interrupt.

### e. Read-only commands must not wait behind a turn (E58)

- **CLI**: you can look at things while it works.
- **Ours**: O-U6 — one FIFO queue.
- **Change**: a second, **read-only lane**. `commands.py` names which commands answer from what
  is already in hand: `/show`, `/panel`, `/sessions`, `/help`, `/modes`, `/copy`, `/expand`,
  `/wipe`, and `/budget`/`/prices` **with no arguments**. `Runner.submit` routes those to a
  second queue drained by a second task; everything else keeps the one queue, in order, on the
  one task that owns the SDK clients. The fast lane never sets `busy`, never writes a session
  record, and never touches a client.
- **D-U4 (a second queue, not a task per command).** *Why*: it keeps the read-only commands in
  order among themselves, it cannot start an unbounded number of tasks, and it leaves the
  model-turn path byte-for-byte as it was. `Runner.idle()` joins both, so tests have one thing
  to await; the nine existing `queue.join()` call sites move to it.
- **D-U5 (`/budget` and `/prices` split by arity).** With no args they print; with args they
  write the session record and push numbers. Only the printing form goes on the fast lane, so
  budgets/prices semantics are untouched.
- **A**: `/show` reads the shared op log while a frame may be appending to it (A5 above). Noted
  for the audit, not solved here.
- **Test**: `tests/app/test_runner.py::test_read_only_commands_answer_while_a_turn_is_in_flight`
  — a chat driver that blocks on an `asyncio.Event`; submit a message, then `/help` and
  `/sessions`; assert both answered while the turn is still blocked; release it and assert the
  turn's own output came after.

### f. Launch reopens the last session (E58)

- **CLI**: `--continue` reopens the last conversation.
- **Ours**: O-U7 — four abandoned timestamped sessions is what the audit found.
- **Change**: with no name on the command line, open the most recently touched session if there
  is one; create only when there is none. `/new` still creates, and `<name>` still opens-or-creates.
- **D-U6 (most recently *written*, by the record file's mtime, falling back to `created`).**
  *Why*: the record is rewritten on every `/model`, `/effort`, `/budget`, `/prices` and focus
  change (`app/runner.py:190-194`), so mtime is "the one I was last working in", which is what
  you mean by "the last session". `created` is the fallback for a store restored from a copy
  that lost its timestamps. *The rival*: if you want a blank shell on every launch, that is
  `--new`, which I will add on a word.
- **Test**: `tests/app/test_runner.py::test_launch_reopens_the_most_recent_session` — run the
  runner once with no name (creates one), write to it, stop; run again with no name; assert the
  same session name and that no second record was written; then `/new` and assert a second one.

### g. Feedback during a frame (E58, audit A5)

- **CLI**: you always see which step is running.
- **Ours**: O-U8, O-U9, O-U10 — `StageStarted` is dead code, `TurnStarted` draws nothing, and
  the pools on screen are the previous frame's.
- **Change**, two parts, neither of which touches a frame or the panel:
  1. The transcript renders `TurnStarted(kind="graph")` as a running-frame line —
     `── orientate · cycle 1 ── running` — closed by the existing `StageFinished` line. A
     `TurnStarted(kind="chat")` still only closes blocks (the user's own line is already there).
  2. The status bar consumes `Priced`, so the pool and what is left of it move **per call**
     rather than per frame: `orientation:1 14 left`.
- **D-U7 (`StageStarted` stays unemitted and unrendered).** *Why*: emitting it would mean the
  driver predicting a cycle number that the frame itself allocates from the op log
  (`app/graph/nodes/orientate.py:100`), and the frames are yours (forbidden). `TurnStarted`
  already carries stage and cycle from inside the frame and is emitted by both the real and the
  scripted harness, so it is the true signal. **`StageStarted` is now documented dead code** —
  either the driver should emit it or it should go; that is the audit's call, not mine.
- **Test**: `tests/app/test_tui.py::test_the_transcript_says_which_frame_is_running` — run the
  scripted cycle, assert a `.stage` line reading `── orientate · cycle 1 ── running` appears
  before the `── orientate · cycle 1 ── …finding(s)` line, and that the status bar shows the
  pool after a `Priced`.

### h. Clear the transcript (E55)

- **CLI**: ctrl+l clears the screen; `/clear` clears the conversation.
- **Ours**: O-U11 — `/clear` goes to the SDK and must keep going (`app/commands.py:55`), and
  there is nothing that clears the screen.
- **Change**: **`/wipe`** and **ctrl+l** empty the transcript widget. Nothing else: no session
  file, no SDK conversation, no graph.
- **D-U8 (the name is `/wipe`).** *Why*: `/clear` is the CLI's and is passed through — taking it
  would silently change what your muscle memory does to the conversation. `/wipe` is in no CLI
  namespace, and the pairing with ctrl+l (which is the CLI's screen clear) gives the
  terminal-independent second path E62 asks for. A notice is printed after it so the transcript
  is never blank-and-unexplained.
- **Test**: `tests/app/test_tui.py::test_wipe_clears_the_transcript_and_clear_still_goes_to_the_conversation`
  — fill the transcript, `/wipe`, assert it is empty; then `/clear` and assert `FakeChat` was
  sent `/clear` and the transcript still holds the echo.

### i. Logging (E64)

- **Ours**: O-U12 — every delta on disk.
- **Change**: `JsonlSink` writes an explicit **allow-list of result-level events**: `TurnStarted`,
  `TurnFinished`, `SessionInfo`, `ThinkingDone`, `TextDone`, `ToolCalled`, `ToolResult`,
  `Priced`, `Refused`, `ApprovalAsked`, `ApprovalAnswered`, `StageStarted`, `StageFinished`,
  `StateSnapshot`, `Notice`. Dropped: `ThinkingDelta`, `TextDelta`, `ToolInputDelta` (E64's
  "individual stream tokens"), `ToolStarted` (the block opening; `ToolCalled` carries the whole
  call) and `ResultText` (the CLI's own copy of the final text, which `TextDone` already has —
  `app/harness/stream.py:102`).
- **D-U9 (allow-list, not deny-list, plus a completeness test).** *Why*: a deny-list would let a
  future delta type leak onto disk silently. The allow-list cannot, and a test asserts that
  every member of the `HarnessEvent` union is either on the list or on a named, short list of
  deliberate exclusions — so adding an event type fails loudly instead of being guessed at.
- **Test**: `tests/app/test_runner.py::test_the_session_log_holds_result_events_only` — run a
  scripted cycle through the runner, read `sessions/<name>/events.jsonl`, assert no
  `*Delta` line, assert `TextDone`/`ToolCalled`/`ToolResult`/`StageFinished` are present, and
  assert the union is fully classified.

### j. ctrl+q goes through the runner's quit path

- **Ours**: O-U13.
- **Change**: `Runner.quit()` closes the clients **first**, then stops the queue, then calls
  `on_quit`. Both `/quit` and `ctrl+q` call it; `ctrl+q` no longer uses Textual's `action_quit`.
- **D-U10 (close before exit, not after).** *Why*: today `on_quit` is `App.exit`, and the
  runner's worker is cancelled by the app's unwind, so the QUIT item that would have closed the
  clients may never be read. Closing first makes it deterministic and is testable without
  racing the app's shutdown.
- **Test**: `tests/app/test_tui.py::test_ctrl_q_closes_the_clients` — send a chat message so a
  `FakeChat` exists, press ctrl+q, assert `FakeChat.instances[0].closed`.

### k. Idle interrupt feedback

- **Ours**: O-U14.
- **Change**: Esc with nothing running prints `nothing is running` as a notice instead of doing
  nothing. Esc with a turn in flight is unchanged.
- **Test**: folded into the modal test above —
  `tests/app/test_tui.py::test_escape_when_idle_says_so`.

### l. The cheap rest (from the CLI comparison)

| Item | Ours | Doing it? |
|---|---|---|
| A **queued marker** on a user line waiting behind a turn | O-U15 | **Yes.** `Transcript.user(text, queued=True)` draws `› text  (queued)`; the runner calls `on_dequeue` as it takes each item off the queue and the oldest marker is cleared. FIFO-correct because the queue is FIFO. Test: submit two lines behind a blocked turn, assert both marked, release, assert the marks clear in order. |
| **ctrl+l redraw** | O-U11 | **Yes**, as item (h) — it is the same action. |
| A status line showing the **cwd** | O-U16 | **Yes.** The cwd's name is added to the status line. It is one line in `StatusBar.refresh_line` and it is the thing a bundled install (E59) most needs to show. |

---

## 4. Not building — and why

| Not built | Why |
|---|---|
| Anything in the graph browser / `GraphPanel` | E63: "it's bad and will need rethinking, so just leave it for now." |
| Transcript **search** (the audit's Q-P6 list) | A real search needs the transcript to own its text as a model rather than as mounted widgets; that is a rewrite of `transcript.py`, not a workflow fix. With `/copy` and `/expand` in, the common case (get it out of the TUI and into something that can search) is covered. Say the word and it becomes its own branch. |
| Transcript **export** to a file | `sessions/<name>/events.jsonl` already *is* the export, and after item (i) it is a readable, result-level record. A second exporter would be a second truth. If you want `/export <path>`, it is a rendering of that file, and I would build it there. |
| **Esc Esc to edit the previous message** (the CLI's rewind) | It means rewinding the *graph* thread, not just the screen: LangGraph checkpoint surgery on the frame pointer. That is a design question for the audit (it interacts with `/fork` and with what "nothing resumes on its own" means, D7), not a UI item. |
| **shift+tab permission modes** | Permission mode is `"default"` in `chat.py:61` and the whole approval discipline (E7, E9, E20, E28) rests on it. Changing it from the UI would let a keystroke turn the approval surface off. **Needs the audit.** |
| **`!` bash mode, `@` file mention, `#` memory** | These are CLI conveniences that write into a conversation this shell does not own the same way. `!` in particular would be a second executor beside the fenced one (`harness/tools.py`, forbidden). **Needs the audit.** |
| **Image paste** | Textual delivers a paste as text; an image needs the SDK's content-block path. **Needs the audit** (it is a `chat.py`/`sdk.py` change). |
| A `/resume` **picker** (the CLI's session list as a modal) | `ChoiceScreen` already exists and `/sessions` lists them, so this is cheap — but `/resume <name>` opens a session, which closes and reopens clients, so it is a model-turn-lane command and the picker would block the lane while it is open. Worth doing; out of this pass's scope. Listed so it is not lost. |
| **ctrl+c twice / ctrl+d to exit** | Textual binds ctrl+c to copy-selection (`textual/screen.py:272`) and warns on it (`app.py:3993`). Rebinding it would take the only mouse-copy key away, which E62 says I may not do. ctrl+q (item j) is the clean exit. |
| **Vim mode in the prompt** | Not asked for, and `TextArea` has no vim binding set in 8.2.8. |
| **A context-left meter** | The CLI shows context remaining; nothing in `harness/events.py` carries token counts, so it would need `sdk.py` (forbidden) to emit usage. **Needs the audit.** |
| Making the graph panel's `Tree` selectable (audit O2's other half) | `Tree.ALLOW_SELECT = False` is Textual's; overriding it is a `GraphPanel` change. Frozen by E63. |

---

## 5. Order of commits

1. this overview
2. (a) paste — test first, then whatever it shows
3. (d) Esc in modals — the A2/A3 verdicts, then the fix
4. (c) prompt history
5. (b) expand + copy
6. (h)+(l) `/wipe`, ctrl+l, cwd in the status line
7. (g) running-frame line + live pool
8. (i) the session log
9. (e) the read-only lane
10. (f) reopen the last session
11. (j) ctrl+q, (k) idle Esc
12. (l) the queued marker
13. the Report section of this file

Every commit carries a test that failed before it, and says so.
