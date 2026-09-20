# Production audit — plan of attack and build log, 2026-09-20

Status: **answered 2026-09-20 (§4a); Cycle 0 running.** No code in the core has been changed by me; UI work runs on branch `ui-workflow`. This document is the
build log for the audit session; cycles are appended below §6 as they run, and the ledger in
§7 is compressed as they close.

Registers, as in the earlier design records, plus one:

| Marker | Meaning | Authority |
|---|---|---|
| **E** | Your words, verbatim, typos preserved. Numbering continues from E50 in `build-plan-2026-09-19.md`. | The only authority here. |
| **O** | Observed: a quotation from this repository, or a run, with a locator. Re-checkable. | None. A witness. |
| **A** | An assumption I hold. Each names what would settle it. | None. |
| **R** | The rival of an **A**: what would have to be true for the A to be wrong, and what decides between them. | None. |
| **Q** | A question only you can answer. My recommendation comes first. | Open until you close it. |
| **D** | A decision I have taken with its reason, to be agreed or overturned. | None until you agree. |

Nothing below closes a **Q** on your behalf, and no **A** or **R** is promoted because it reads
well. An **A** becomes an **O** when I go and look, and an **E** only when you say so.

---

## 0. What this build is for — your words, and my reading

### 0.1 Your words this session

| # | Their words |
|---|---|
| E51 | "the entire point of this build is to curb the premature stopping or invalid concluding of agents, or coming to the wrong conclusion by forcing context and evidence into a comprehensive and structured shape." |
| E52 | "I'm intentionally mimicing the graph rag style structure because it gives a good base to work from and extend such that we can be sure agentic flows remain consistently grounded in a proven shape, but that doesn't mean that this shape can't change" |
| E53 | "you should study from an anthithesis POV about all of your previous build considerations, assumptions, and conclusions. Look at, realistically, what you actually built for vs what this design is supposed to be used for." |
| E54 | "don't just consider one scenario, you need to follow just like the system that is being built. Survey your surroundings, orientate and disprove your own assumptions as you go." |
| E55 | "I should be able to copy and paste and do all the regular workflow operations." |
| E56 | "keep a track of your build log such that you mimic the projects structure you are checking." |
| E57 | "come back to me with a plan of attack for how you would approach this large session request, and anything you need from me to get you started, and you should also write down what you read the project's build pupose is and what that means for how you should approach your own interactions this session" |

### 0.2 My reading of the purpose — **A** until you confirm or correct it

The system exists to make an agent's route to a conclusion inspectable and correctable
*before* the conclusion is acted on. Read against E1–E50, it does that six ways:

1. **Interpretations become named, funded assumptions** (E2, E3, E17, E18) instead of staying
   implicit in the agent's head. An assumption is "a place information can land", so it can
   be checked.
2. **Every assumption goes through a separate adversarial pass** (E27a–c), because "an agent
   cannot think they are right and wrong in the same task".
3. **Evidence is literal.** The finding is the captured output of a fenced read, not the
   agent's paraphrase of it (`thought-graph-v2-options-2026-09-19.md` §2).
4. **Authority is yours alone**, exercised at explicit approval surfaces (E7, E9, E20, E28).
   Everything the agent authors is provisional and must render as provisional wherever it
   appears.
5. **Tool use is priced** so the agent goes wide before deep and stops at a forced report
   rather than at a self-declared conclusion (E5, E6, E8, E11). "It is not which way they go,
   it is when they stop and how they approach it."
6. **The graph outlives the session**, and only what you approved survives the cycle of
   growth, compression and reconciliation (E48).

The GraphRAG shape — entities, claims, evidence, summaries — is the scaffold that keeps the
flows "grounded in a proven shape" (E52). It is not itself the goal, and E52 says it may change.

The TUI is not decoration on this. It is the *approval surface* (E28) and the *control
surface* (E26), which means every place it fails to show authority, budget, stage or effect
is a place the discipline leaks.

### 0.3 What that means for how I work this session — **D**, overturnable

- **I am the kind of agent this system was built to constrain.** So every claim I make about
  the code is **A** until it carries a locator (**O**) or you confirm it (**E**). "Not
  production ready" is not a verdict I issue; I show what I found, where, and what it would
  take, and you close each item.
- **Each prior conclusion gets its rival.** The D-items and A-items of the previous build
  (`build-plan-2026-09-19.md` §4, `thought-graph-v2-options-2026-09-19.md`) are listed in
  §3 with an **R** each, and what would decide between them. Then I go and look.
- **Wide before deep.** §2 enumerates every flow before any is investigated. I do not
  disappear into the first bug.
- **Evidence is what I ran, not what I remember.** My memory file says the suite has 58
  tests; the build plan says 140. Neither counted until `pytest` ran (§1). Where a flow can
  be exercised headlessly (Textual `Pilot`, the scripted harness) a failing test *is* the
  finding, and it stays in `tests/` as the evidence.
- **Forced stop points.** Each cycle ends with a present-to-you section in this log (E21).
  Options I offer there are suggestions and may be wrong (E22); they are not decisions. Where
  a question does not block, I continue under a marked **A** rather than wait.
- **Your open questions stay open.** Q-A..Q-H of the proposal and Q1–Q10 of the options doc
  are not mine to close. I record what the code does today against each.
- **Every number I introduce is provisional** and marked (E33).
- **The scope is yours.** If I find that a part of the work should be smaller or larger than
  E55–E57 imply, I say so here and keep going on what was asked; I do not resize it myself.

---

## 1. What I have surveyed so far, and what I have not

**O** Read this session: `build-plan-2026-09-19.md` (all), `thought-graph-v2-options-2026-09-19.md`
(all), `thought-graph-proposal-2026-09-19.md` (all), `budgeted-flow-2026-09-17.md` (E1–E37 only);
after you allowed the code survey: every file under `app/tui/`, `runner.py`, `commands.py`,
`graph_driver.py`, `tests/app/test_tui.py`, `tests/app/test_prompt.py`, the selection and
clipboard code of the installed Textual 8.2.8, the cwd and provisional sections of `config.py`,
one stored session record, the devcontainer file. Findings are in **Cycle 0 (partial)** below.

**O** Not read: `harness/*` (13 files), `graph/*` (14 files), `chat.py`, `session.py`, the rest of
`config.py`, the other eight test files, the spikes, `framework-fit-2026-09-18.md`,
`eie-tree-turn-by-turn-example.md`, `updated-flow-2026-09-16.md`, `PLAN.md`, `app/README.md`.
Statements about those are **A**.

**O** `git status`: one uncommitted change, `.gitignore` gains `Harness/`. Branch
`orientate-absorbs-assume`, five commits ahead of what my memory recorded as "nothing committed".

**O** `uv run pytest tests -q` → **58 passed in 21s**. My memory said 58; the build plan's "140"
(G14) counted the old suites that G16 deleted.

---

## 2. The flows — the survey list, wide first

Every flow the app is supposed to carry, with how I will check it. *Method*: **read** = code
with locators · **pilot** = Textual `App.run_test()` headless · **scripted** = the scripted
harness end to end · **live** = a real Haiku turn (needs Q-P4) · **you** = only checkable in
your terminal; I give you the steps and record your answer as **E**.

| # | Flow | What the record says it does | Method |
|---|---|---|---|
| F1 | Launch and environment | entry point launches the TUI; CLI present and logged in is assumed | read, pilot, you |
| F2 | Chat mode | plain text to the focused mode's SDK connection; streaming thinking/text/tools; pass-through of `/compact` etc. | pilot, scripted, live |
| F3 | Graph cycle, happy path | `/graph <q>` → orientate → antithesis → synthesis text-first → your reply → gated calls | scripted, live |
| F4 | Approval surface | modal with dry-run effect; approve/refuse + your words; words ride back both ways (D6) | pilot, scripted |
| F5 | Interrupt | Esc / `/interrupt` at each frame, during a modal, during chat | pilot, scripted, live |
| F6 | Resume and abandon | `/graph` alone resumes from the frame owed; `/graph <q>` abandons "with a warning" | scripted, read |
| F7 | Sessions | `/new /sessions /resume /fork`; a fork shares the graph; what a session record carries | scripted, read |
| F8 | Modes | `modes.toml` tables as `/<name>`; prompt files; bad files | read, pilot |
| F9 | Pickers | `/model`, `/effort` from the CLI's model list; when the list fails | pilot, read |
| F10 | Budget and prices | `/budget`, `/prices`, `reset`; what the status bar shows and when it updates | pilot, scripted |
| F11 | Graph browser | panel views, select → `/show node`; `/show search`, `/show neighbours`; large graphs; authority visible | pilot, read |
| F12 | Prompt and keyboard | wrap, Enter/Shift+Enter, Tab, Ctrl+A; every binding vs terminal and tmux conflicts (ctrl+b is the tmux prefix) | pilot, read, you |
| F13 | Clipboard | copy out of the transcript (selection, OSC 52); paste into the prompt (bracketed, multi-line must not send) | pilot, read, you |
| F14 | Transcript operations | follow/unfollow, scroll, search, export, clear, history recall | pilot, read |
| F15 | Errors and failure surfacing | SDK errors, CLI missing/logged out, payload validation failure and retry, refused calls, executor refusals | pilot, scripted, read |
| F16 | Persistence and integrity | `ops.jsonl` torn line, `checkpoints.sqlite` locked, two processes, record schema change | scripted, read |
| F17 | Configuration | every provisional number, where it is set, whether the app says which were never chosen | read |
| F18 | Observability | run log for the new loop (build plan E3, unbuilt); where an error goes when the TUI is not looking | read |
| F19 | Packaging and platform | `uv run`, Python 3.14, empty root `README.md`, `agent_framework/` and `Harness/` gitignored | read |
| F20 | Tests vs flows | which flows above have a test; which are scripted-only; which have never run live | read |
| F21 | The executor as a shell | allow-list, cwd fence, timeout, cap; each refusal has a test; what cwd *is* | read, scripted |
| F22 | The design's target vs what was built | the frames suggest assumptions about *your intent*; the graph holds *entities and claims about the project*; the live checks ran on a five-file fixture with Haiku | read, live, Q-P8 |

---

## 3. The antithesis of the previous build — first pass, before reading code

Each row is a conclusion I recorded last time, its rival, and what decides it. These are
**A/R** pairs; Cycle 0 turns each into an **O**. Rows the partial survey has already settled
point at the O-line that settles them.

| Prior conclusion (locator) | **R** — the rival | Decides it |
|---|---|---|
| D1 Textual is the TUI, chosen for streaming + modal + panel (`build-plan` §4) | D1 weighed only *output*. Nothing considered input: terminal selection, clipboard, bracketed paste, prompt history. Textual owns the mouse, so native select-to-copy is gone unless widgets opt in. E55 is exactly this gap. | **partly settled → O2–O5**: Textual 8 selects and copies by default, but tool results and panel nodes opt out; no history; paste untested |
| One SDK client per frame turn, `resume=` (`build-plan` §5a) | Built for conversational correctness, not for latency or failure. Each frame spawns a CLI process; the gap between frames is visible and unexplained; a spawn that fails (CLI absent, logged out) has no designed surface. | time a cycle; launch without the CLI on PATH |
| D5 events are the seam, the TUI subscribes | The event union was drawn from the happy path. Errors, SDK failures and refusals may be emitted but not rendered, or rendered but not persisted. | **partly settled → O8**: 6 of 20 event kinds never reach the transcript; StageStarted is one |
| D7 interrupt aborts to the last checkpoint; "nothing resumes on its own" | True of the graph; not shown true of the screen. After an interrupt the partial stream, the open modal, the stage label and the budget shown may disagree with the checkpoint. Interrupt *during* a modal is its own case. | pilot: interrupt at each frame and inside the modal; compare with `/show state` |
| G10 "the TUI survives every terminal size" | Survival was measured as "does not crash". Silently hiding the panel and dropping the placeholder is survival, not usability. | pilot at 80×24 and 40×10 |
| G12 `/graph <query>` abandons an interrupted cycle "with a warning" | A warning *after* a destructive act is not a gate. The system gates the agent's destructive ops behind your approval and does not gate your own slip. | **settled → O9**: the warning and the abandon are the same call, no confirm |
| S-2 op log; "a file lock is enough" (`options` §6) | Two processes is one case. A crash between `open_cycle` and the frame's write, or a torn last line, is another; replay tolerance was never tested. | truncate the last line of a copied log and load it |
| Q-8 graph reads are free (`options` §7) | Free reads let the agent read the graph *instead of* the project and refill the window the package was designed to keep small. | count `graph_search` calls per frame in the spike log |
| G-2 growth ungated; "authority=agent must stay visible" (`options` §10) | Written about the *package* the model reads. Whether the panel, `/show node` and the transcript show authority was never stated as a requirement of §8. | read `panels.py`; pilot `/show node` |
| Fixture repo + Haiku is the live check (`build-plan` B3, G7) | The fixture is five small files. The 80-line evidence cap, `package_hops` and word-match seeding were never exercised at the scale the design targets. | one live cycle against this repository itself (Q-P4) |
| Q2 answer: plain text goes to the focused mode | The status bar is the only cue of where the next line goes. A reader mid-transcript has no persistent signal. | pilot: switch modes and inspect the prompt area |
| Build-plan closing note: assumptions are about *what you are asking* | The thought graph (§4 of the options) holds entities and claims about *the project*. Two kinds of node share one store and one word. Which one is "grounded in evidence"? | Q-P8 |
| "All approved steps of the v2 plan are built" (my memory) | "Built" meant the stage gate passed: tests plus one live spike each. Production readiness was never a gate criterion. What this audit finds is not regression; it is scope that was never in the plan. That is E53. | **sharpened → O11**: the store layer (G13–G15) has never been written by a live run in this checkout |
| The suite is the verification (memory: 58; plan: 140) | Tests under `tests/app` exercise the scripted path. Pilot tests cover what the commit message names. The count says nothing about which flows in §2 are covered. | pytest now; F20 map |

---

## 4. Questions — what I need from you

My recommendation first in each. Q-P3 and Q-P4 block the work after Cycle 0; the rest I can
proceed on under the marked **A** if you prefer to answer later.

| # | Question | My recommendation (**A** until answered) |
|---|---|---|
| Q-P1 | **Who is "production" for?** You alone, locally, on your own projects — or a tool others install? | You alone, locally. Then packaging, onboarding docs and multi-user concerns are noted but ranked last. |
| Q-P2 | **Where does the app run relative to the project it studies?** Launched *inside* the project (cwd is the project, sessions live in it) or *pointed at* one (`--project <path>`, sessions user-level)? This decides the executor's cwd fence, where `sessions/` and `modes.toml` resolve, and whether one graph is one project. | Inside the project, as today; add the pointed-at form only if you say so. |
| Q-P3 | **Audit first, or fix as I go?** | Cycle 0 is read-only. From Cycle 1, mechanical UI fixes you have already named (E55: copy, paste) are made with a test each; everything else is written up with a failing test as evidence and fixed only after you pick from the list. |
| Q-P4 | **May I spend live turns?** Some flows (interrupt, resume, real-scale evidence) cannot be scripted. The app runs on your subscription. | Scripted for everything that can be; one live Haiku run per flow that cannot, against this repo, and I record each run's reported cost here before the next. Say "no live" and I mark those flows as checked-by-reading only. |
| Q-P5 | **Which terminal(s) must it work in?** Clipboard (OSC 52) and key bindings differ by terminal and multiplexer. | VS Code integrated terminal in this devcontainer (from `.devcontainer/`, `.vscode/`); no tmux. If you use tmux or another terminal, name it. |
| Q-P6 | **"All the regular workflow operations" (E55)** — my reading of the list: copy text out of the transcript, paste multi-line into the prompt without sending, prompt history (up/down), clear the transcript, search it, export/save it, scroll with mouse and keys, cancel the in-flight turn, resize. | Strike or add. Anything not on the list is out of scope until you name it. |
| Q-P7 | **This log's place and shape.** | Here, `docs/design/production-audit-2026-09-20.md`, in the registers above, cycles appended. Alternative: also record findings into the app's own graph store by running the app on itself, which dogfoods F22 but mixes audit records into your project graph. I would not, unless you want it. |
| Q-P8 | **Assumptions about intent, or propositions about the project?** The build-plan closes on this. The frames were built to E2 (an assumption interprets the request); the thought graph was built to hold entities and claims about the project. Are both intended to coexist, or should orientate's suggestions become claims about the project that the entity layer grounds? This changes what F22 measures and what synthesis reconciles. | Both coexist, and the audit reports how they render side by side — but this is the one **Q** where a wrong guess makes the F22 finding useless, so I will not guess. |

---

### 4a. Your answers, 2026-09-20 — verbatim, and what each changes

| # | Q | Your words | What it changes |
|---|---|---|---|
| E58 | Q-P1 | "Yes, for me alone, so it needs to be smooth and versitile enought to not interrupt workflwo." | Single user, local. Packaging for others is out. Smoothness is in: anything that makes you wait or repeat yourself is a finding. |
| E59 | Q-P2 | "It should be bundleable meaning that I can install the flow somewhere whereever I have claude set up. You can see the Harness project, that is my work project that I want to be using this flow on for testing real life usage. For now, however, the easiest way is to make it standalone in a git repo that I can pull down into the harness and gitignore it there, so I can update THIS project and pullit into whatever project I'm using to act as the agent harness." | The target project is `Harness/` (a .NET tree). The install shape is this repo cloned into a subdirectory of the host project and gitignored there, studying the parent. So `sessions/`, `modes.toml` and the graph must live with the *install*, not be written into the host (O12 writes them into `--cwd`). F19 becomes a real flow: clone into `Harness/`, run, nothing lands in Harness's tree. |
| E60 | Q-P3 | "Audit first. However since the UI is simply a ui interactable checklist, I'm happy for you to hand that off to an opus/sonnet agent and not do it yourself, you should save your context for the heavy thinking." | I change nothing in the core until the audit presents. The UI checklist goes to an Opus subagent on its own branch (`ui-workflow`) in a worktree, in parallel with the audit. |
| E61 | Q-P4 | "yes. only test on haiku." | Live runs allowed, Haiku only. Each run's reported cost is logged here before the next. |
| E62 | Q-P5 | "yes, curretly, should be able to work in any terminal though." | VS Code now. No terminal-specific mechanism may be the only way to do a thing: a command beside OSC 52 for the clipboard, no binding only one terminal delivers. |
| E63 | Q-P6 | "As I said before, I'm happy with just a professional overview of changes that can be done independently of the audit. The audit and considerations of where we should go and how we do it is much more important than the UI, the UI is just something that should be done for a smooth workflow. You can consider from the perspective of something like claude cli - what's missing, lets add it. You dont have to work on the graph view at all, it's bad and will need rethinking, so just leave it for now." | The UI agent writes the overview first, measured against the Claude CLI's own shell, then builds it. The graph panel (F11) is frozen: "bad and will need rethinking" is your verdict, and the rethink is a post-audit item. My weight goes to F3–F7, F15, F16, F19, F21, F22. |
| E64 | Q-P7 | "Wherever, you should have the logs output individual stream tokens though, that's too much, just result messages." | Read as: the per-session `events.jsonl` must **not** log stream deltas; result-level events only (**A** on the missing "not"; the second half of the sentence settles it). Handed to the UI agent. This log stays where it is. |
| E65 | Q-P8 | "This is difficult because I need you to be autonomous, but I don't want you overassuming. Therefore, I give you permission to explore and implement avenues of potential to make this the best version of its self - as long as you are always framing based on my extracted words (as you ahve in that  doc). If you explore separate shapes of implementation (say completely differentn edge and node shapes, or a workflow that requires some different nodes) make a branch for each adn keep their works and ideas separate. And once again, this is fine to do because I'm allowing you to do it - but it shoudl always be rooted in the explicit requirements we've established for the REASON why I'm making this structure in the first place." | The licence for the post-audit work: explore and implement, every avenue framed on E-lines, one branch per distinct shape, E51 as the root test of each. Q-P8 itself stays open as the design question F22 must answer with evidence; any shape I try for it gets its own branch. |
| E66 | — | "you can have a look at this task folde rin the Harnes project /workspaces/langchain-claude-test/Harness/docs/tasks/agent-workflow-overhaul that inspired the start of this project (just for reference , not for basing design off)" | Read in Cycle 0 as context for what real use looks like. Not a design source. |

**D-P1 (order, revised).** Cycle 0 proper: the rest of `app/`, the tests, spikes 09 and 10, the
Harness task folder; one live Haiku cycle against this repository. Then F3–F7, F15, F16, F21,
F19 (the install shape), F22. F11 frozen. F12–F14 and the shell items of F1 handed off.

**D-P2 (the hand-off).** An Opus agent in its own worktree on branch `ui-workflow`. Deliverable:
`docs/design/ui-workflow-2026-09-20.md` (its overview and report) plus commits on that branch.
Nothing merges until you say. It does not touch `app/graph/`, the panel, or frame semantics.

**D-P3 (branches).** Any implementation shape I explore after the audit lives on its own branch
named for the shape; this branch and `main` are not touched by exploration.

---

## 5. Method — each flow is a cycle

Mirroring the system (E54, E56):

1. **Orientate** — survey the flow's code and tests with locators; keep what I read as **O**
   lines; suggest between one and five assumptions about where it falls short, each citing
   the O-lines it rests on.
2. **Antithesis** — one rival per assumption: the reading under which the flow is fine, or
   fails differently. Then run it (pilot, scripted, live, or ask you) so one side becomes
   **O**.
3. **Present** — a section here: what holds, what fails with locator and reproducing test,
   what I did not look at, what I don't know, and options (E21, E22). You reconcile: confirm,
   refute, or reprioritise. Nothing is fixed on a provisional finding unless Q-P3 says so.
4. **Compress** — the ledger in §7 gains one line per closed item; the cycle's detail stays.

Budget for my own reading, marked provisional: no more than **three** consecutive cycles
without a present-to-you section, and no fix without a test that failed first.

---

## 6. Order of work — **D**, overturnable

- **Cycle 0 — ground truth.** Read every file under `app/` and `tests/`; run the suite; run
  the app under Pilot once; run the two spikes only if Q-P4 allows. Turn every row of §3 into
  an **O**. No fixes.
- **Cycles 1–2 — F13, F12** (E55, your named ask: clipboard, prompt, keys).
- **Cycles 3–6 — F2, F3, F4, F5+F6** (the two entry points, the approval surface, interrupt
  and resume).
- **Cycles 7–9 — F7, F15, F16** (sessions, failure surfacing, integrity).
- **Cycles 10–12 — F11, F10, F14, F9, F8** (the browser and the controls).
- **Cycle 13 — F22** (the design's target vs what was built), informed by everything above.
- **Then** — F17–F21 as a written map rather than cycles, and the fix list in the order you
  choose.

---

## 7. Ledger — compressed findings

Filled at Present, 2026-09-20. L1–L18 are the forked session's (part 2, folded in below);
L19–L31 are this session's. One line each; the evidence column names the O-lines; the last
column is yours. ✔ marks a thing that *holds* and is listed so you know it was checked.

| # | Flow | Finding (one line) | Evidence | Your verdict |
|---|---|---|---|---|
| L1 | F16 | A crash after a frame's log append and before the checkpoint leaves a ghost cycle the next run duplicates | O37, simulated on a copy | |
| L2 | F16 | A frame that fails every re-author attempt refunds the points it spent | O39 | |
| L3 | F15 | Runner notices and runner-level errors never reach the session log | O43, live log: 0 notices | done on `ui-workflow` `eda6d2c` |
| L4 | F15 | A schema mismatch is corrected as a wrong count | O45 | |
| L5 | F21 | Dash-prefixed, relative and second-expression arguments are not fenced | O51–O54, by reading | |
| L6 | F17 | Provisional numbers are disclosed only by `/budget`; the provisional price class nowhere | O57–O59 | |
| L7 | F18 | The session log is three-quarters stream deltas and misses the shell's own lines | O61, O62 | done on `ui-workflow` `4c3caea` |
| L8 | F19 | Running against Harness wrote untracked state into Harness; you did this twice on 09-19 | O66, O67 | |
| L9 | F19 | The CLI keys conversations by the cwd string; a session moved across mounts cannot resume its cycle | O71, A13 | |
| L10 | F19 | `--cwd` conflates studied project, install and state; P-19a splits them | O68 | |
| L11 | F4 | The approval modal shows an id and a done-tense effect, not the node's text or the model's reason | O90–O92 | done on `ui-workflow` `46da48c` |
| L12 | F4 | The advertised approve key is swallowed by the words box; Tab+Enter works | O96, Pilot | done on `ui-workflow` `6ea96d7` |
| L13 | F4 | Parallel gated calls stack modals answered in reverse; the words for one reach none of the others | O95, O79 | serialised on `ui-workflow` `46da48c`; O79 (the model batching) stands |
| L14 | F4/F5 | Esc behind a modal interrupts the turn; answering the orphaned modal then crashes the shell | O88, O89, O97 | done on `ui-workflow` `e73ba5f`, `46da48c` |
| L15 | F4 | The next cycle reads every refusal as "never", including "not this cycle" | O99 | |
| L16 | F7 | Forking a thread interrupted in its first frame skips the owed frame and runs antithesis on cycle 0 | O104, scripted | |
| L17 | F7 | A fork shares the chat conversation id with its source | O103, A22 | |
| L18 | F21 | The survey frame used the free keep path zero times and the priced look path twelve; CONTEXT came out empty | O107–O109 | |
| L19 | F3/F22 | **The survey keeps nothing, on both real runs**; the next cycle inherits assumptions with no ground under them | O73, O107, O110 | |
| L20 | F22 | **Zero entities, zero claims**: the assumption layer absorbed the claim layer; Q-P8 answered as far as a question-shaped run can | O74, O111, O112 | |
| L21 | F22 | **Nothing consumes the graph but the next cycle**; no hand-off to the working session E12/E59 describe | O117, O119 | |
| L22 | F5/F6 | ✔ An interrupt during an open approval aborts on the wire in half a second, writes nothing, and the cycle resumes | O86, O87 | |
| L23 | F3 | From one sentence of yours the model proposed four closes, three in one message, one of them your own assumption on its rival's status; the gate caught three | O79, O80, O115 | |
| L24 | F3 | Your refusal words reach the model verbatim and its next proposal does not answer them | O93, O94, O116 | |
| L25 | F3/F11 | Kept findings render cut at 240 characters; three of five exceeded it | O23, O82 | |
| L26 | F0 | The system prompt describes four frames, "readings" and an `excerpt` argument, none of which exist; harmless on Haiku | O17, O85 | |
| L27 | F3 | Refusals by the meter are not recorded on the graph | O32 | |
| L28 | F3 | The survey walks the working tree, not the repository: gitignored trees are read and paid for | O75 | |
| L29 | F22 | Breadth is capped by count only; three assumptions were one topic and two rivals said the same thing | O113 | |
| L30 | F3 | ✔ Budget exhaustion arrives as a hook error and works: the model stops and reports | O76 | |
| L31 | F18 | Cost figures per turn are the CLI's cumulative totals; the status bar double-counts. **Backlogged at your instruction** | O72 correction | |

---

*Cycles are appended below this line.*

## Cycle 0 (partial) — the UI layer, surveyed 2026-09-20 before this plan was returned

You allowed the code survey mid-turn; this is what it found in the UI layer only. Every line
below is **O** (a locator) or **A/R** (a belief and the run that would settle it). Nothing here
is a verdict, and nothing has been changed.

### O — what the code does today

| # | Observation | Locator |
|---|---|---|
| O1 | The suite is 58 tests, all passing. | `uv run pytest tests -q` |
| O2 | **Copy out.** Textual 8.2.8 selects text by mouse on any widget with `ALLOW_SELECT` and copies it with ctrl+c through OSC 52. `Collapsible` and `Tree` set `ALLOW_SELECT = False`, so **tool results and the panel's node ids cannot be selected**. Tool results are also cut at 24 lines with no way to expand. | `textual/screen.py:272`, `app.py:1770`, `widgets/_collapsible.py:22`, `widgets/_tree.py:561`; `tui/transcript.py:15,67` |
| O3 | **Paste in.** A terminal paste arrives as one `Paste` event that `TextArea._on_paste` inserts whole; `PromptInput._on_key` never sees it, so a multi-line paste should not send. No test posts a `Paste`. ctrl+v pastes the *app's* clipboard, not the system's. | `textual/widgets/_text_area.py:1982,2661`; `tui/prompt.py:58-76`; `tests/app/test_prompt.py` |
| O4 | No prompt history: nothing recalls a previous entry. | `tui/prompt.py` |
| O5 | No transcript search, export or clear. `/clear` passes through to the SDK conversation; it does not touch the transcript. | `commands.py:55` |
| O6 | `escape` is an app-level **priority** binding for interrupt. `ChoiceScreen` binds escape to "leave" without priority; `ApprovalScreen` and `QuestionScreen` have no escape at all. | `tui/app.py:68`; `tui/screens.py:40,81,123` |
| O7 | Every `/` command — `/show`, `/panel`, `/sessions`, `/new` — waits in one FIFO queue behind any turn in flight. Only Esc and the key bindings act at once. | `runner.py:76-99,274`; `tui/app.py:135` |
| O8 | The transcript renders 14 of 20 event kinds. Never rendered: `StageStarted`, `ResultText`, `TurnFinished` unless interrupted, `SessionInfo` (status bar only), `StateSnapshot` (panel only). The panel's pools update only on `StateSnapshot`, which the driver emits **after** a frame ends, so the budget on screen is stale for the whole frame. | `harness/events.py:24-185` vs `tui/transcript.py:140-210`; `graph_driver.py:109-115` |
| O9 | `/graph <query>` with a cycle owed warns and abandons in the same call. No confirm. | `runner.py:294-300` |
| O10 | Two quit paths: `/quit` closes the clients then stops; ctrl+q is Textual's own `action_quit` and exits without `_close_clients`. | `runner.py:240-245`; `tui/app.py:69` |
| O11 | Every launch without a name creates a new timestamped session. Four such records exist, all from 2026-09-19 06:23–07:00. `sessions/graph/` does not exist: **the project op log (G13–G15) has never been written by a live run in this checkout** — the records predate those commits (12:38). | `runner.py:82-86`; `ls sessions/` |
| O12 | `--cwd` exists, and `AppConfig.default` puts `sessions/` and `modes.toml` under it. Pointing the app at another project writes `sessions/` into that project. | `tui/app.py:228`; `config.py:375-379` |
| O13 | A stored session record carries name, created, focus, mode, conversations, model, effort, forked_from. Budgets and prices are not in the record on disk. | `sessions/s-20260919-070059.json` |
| O14 | This is a VS Code devcontainer on the host network. `Harness/` (the uncommitted `.gitignore` line) is an unrelated .NET tree, not part of this app. | `.devcontainer/devcontainer.json`; `ls Harness` |
| O16 | Spike 09 runs against a `mkdtemp` sessions directory, so the store **has** run live once — against the five-file fixture, in a temp dir that is gone. Never in this project's own `sessions/`, and never on a real project. | `scripts/spikes/spike_09_live_cycle.py:40,46` |
| O15 | TUI tests cover: one scripted cycle rendered; panel hide/resize/drag; six terminal sizes without a crash; Enter, Shift+Enter, Tab, ctrl+a; follow/unfollow. Not covered: paste, selection and copy, the approval modal answered by keys with words end to end, interrupt, Esc inside a modal, `/sessions` `/resume` `/fork` through the TUI, an error notice, a picker's escape (`test_tui.py:170-174` presses it and asserts nothing). | `tests/app/test_tui.py`, `test_prompt.py` |

### A/R — what I now believe, and the run that would refute it

| # | **A** | **R** | Decides it |
|---|---|---|---|
| A1 | Multi-line paste inserts and does not send (O3). | The terminal or multiplexer strips bracketed paste and the newlines arrive as Enter keys, sending line one. | Pilot posts a `Paste`; you paste three lines in VS Code |
| A2 | Esc inside the approval modal fires the app's interrupt while the modal stays up with an unresolved future (O6; `screens.py:163-167`). | Textual delivers the screen's bindings first, or the interrupt cancels the awaiting task and the modal closes cleanly. | Pilot; then `hooks.py:169` and `sdk.py:202` read |
| A3 | Esc in the model/effort picker never reaches `action_leave` (O6). | The screen's binding outranks the app's priority binding. | Pilot: push `ChoiceScreen`, press escape, assert dismissed |
| A4 | In VS Code, copy works for your lines and the model's text, and not for tool results or panel nodes (O2). | OSC 52 is off in your terminal and nothing copies at all. | you |
| A5 | During a frame you have no signal of which frame runs or what it has spent (O8). | The previous frame's line plus "⋯ working" is enough in practice. | you, watching one live frame |
| A6 | ~~The store layer has only ever run under tests (O11).~~ **Refuted → O16.** | Spike 09 wrote a sessions directory elsewhere. | `scripts/spikes/spike_09_live_cycle.py:40,46` |

### Present

What holds: the widgets that were built do what their tests say. What is missing is the
input side of the UI (E55), the live-frame feedback, the gates on your own destructive
commands, and any live exercise of the store. What I did not look at: everything under
`harness/` and `graph/`. What I don't know: how an interrupt meets an awaited approval; where
budgets and prices are restored from when a session record lacks them.

Awaiting your answers to §4 before Cycle 0 proper.

## Cycle 0 — the core, read in full, 2026-09-20

Read: every file under `app/harness/` and `app/graph/`, `chat.py`, `session.py`, `config.py`,
`prompts/graph_system.md`, spikes 09 and 10, every test's name, the six Harness task-folder
documents (E66, reference only). Nothing changed. Each line is **O** with a locator, or **A/R**
with what would settle it.

### O — the core as it stands

| # | Observation | Locator |
|---|---|---|
| O17 | **The system prompt every graph frame opens with is stale.** It describes "four frames … orientate (go wide, name the readings worth testing), assume (fund one reading at a time …)" and tells the model to attach a finding "with the excerpt copied from what the tool returned". The assume frame was deleted (G1), "reading" became "assumption" (G5), and `attach_finding` runs the command itself (G11). G5 claimed the rename reached "every brief, tool description, package section"; it did not reach the system prompt. Every live cycle so far ran under this contradiction. | `prompts/graph_system.md:8,12`; `config.py:289` |
| O18 | **One CLI subprocess per frame turn.** `SdkHarness.run` connects, sends one message, drains, disconnects, inside one method; a retry is another subprocess on the same conversation. The gap between frames is unmeasured. | `harness/sdk.py:118-157` |
| O19 | **Interrupt is a request to the CLI, not a cancellation of the awaiting approval.** `interrupt()` calls `client.interrupt()`; `FrameInterrupted` is raised only when the result's `terminal_reason` starts with `aborted`. Nothing cancels a `can_use_tool` that is awaiting the approver, so the modal's future stays pending. What the CLI does with an interrupt while a permission request is outstanding was never measured: spike 10 interrupted a streaming chat turn, not an approval. | `harness/sdk.py:166,198,202-205`; `harness/hooks.py:169`; `scripts/spikes/spike_10_live_chat.py:153-161` |
| O20 | **The frame's log write and its checkpoint are two writes.** A frame appends its records to `ops.jsonl` and then returns; LangGraph commits the thread state after the return. A crash between the two leaves records in the graph for a cycle no thread knows about; on the next `/graph` the store sees the cycle has records and opens a fresh one. Nothing detects the orphan. | `graph/nodes/orientate.py:164-184`; `graph/store.py:315-337` |
| O21 | **Torn-line tolerance exists on the read side and is tested**: `_catch_up` applies only whole lines; `decode` skips a bad line. The write side appends every record of a frame in one `write()`. The untested case is O20, not a torn line. | `graph/store.py:253-281`; `tests/app/test_store.py:82` |
| O22 | **Text-first synthesis is enforced structurally, not by prompt.** On the opening exchange the gated tools are left off the MCP server and the hook refuses them with a "suggest it in text" reason. | `graph/nodes/synthesis.py:166`; `harness/tools.py:561-564`; `harness/hooks.py:58-67` |
| O23 | **Kept evidence is never re-readable in full.** A finding stores up to 80 lines / 6 KB, but every rendering of it — the package, `graph_neighbours`, `/show node` — cuts the text at 240 characters. The next cycle sees the command and the first 240 characters. The tool description promises "what the graph keeps"; what the graph *shows* is a stub. | `harness/evidence.py:41-42`; `graph/package.py:41-43,57,244` |
| O24 | **Authority renders in one place.** `describe_node` prints `authority:`; the package marks entities "provisional until you confirm"; the panel, the outline label and the assumptions section show status only. `authority=agent` versus `authority=user` on an edge is visible nowhere in the shell. | `graph/package.py:228-229,113`; `graph/thought.py:515-531`; `tui/panels.py:108-110` |
| O25 | **Assumptions are about the request; entities are about the project.** The payload schema says an assumption is "one checkable proposition about what is being asked"; `add_node` records "a thing in the project". Both land in one store under one word. | `graph/payloads.py:27,53`; `harness/tools.py:197-202` |
| O26 | **`StageStarted` is defined and never emitted.** No module constructs it. What *is* emitted at the start of every frame turn is `TurnStarted(kind="graph", stage, cycle)`. | `harness/events.py:141`; `harness/sdk.py:133`; `harness/scripted.py:102`; grep over `app/` |
| O27 | **Pools shown to the user come from the committed ledger**, so during a frame the spend is invisible; `Priced` events carry `remaining` per call and are rendered only on the tool block. | `graph_driver.py:28-38`; `harness/hooks.py:73-82` |
| O28 | **Every event, including every text and thinking delta, is written to the session's `events.jsonl`.** E64 is a description of current behaviour. | `harness/events.py:229-243`; `runner.py:122-123` |
| O29 | **Live approvals have never been exercised.** Spike 09 uses `AutoApprover`, which approves everything and stamps `answered_by="auto"`. The modal has answered a real gated call zero times outside Pilot. | `scripts/spikes/spike_09_live_cycle.py:43`; `harness/scripted.py:200-215` |
| O30 | **`AskUserQuestion` is not on any graph frame.** The build plan (Q3) named it for synthesis; `STAGE_BUILTINS` carries the five evidence tools only, and the graph gate has no branch for it. The chat gate does. | `graph/surface.py:76-82`; `harness/hooks.py:126-133,210-216`; `build-plan` §5 Q3 |
| O31 | **Chat mode does not pass `setting_sources`.** The graph harness passes `[]` for isolation on purpose. The chat driver passes nothing, so whether the default connection loads the user's `CLAUDE.md`, settings, hooks and MCP servers as the CLI would depends on the SDK's default (checked in the reply to this section). | `chat.py:54-67`; `harness/sdk.py:97` |
| O32 | **Refused calls are recorded on the meter but not on the graph.** `meter.refused` reaches `TurnResult.refused` and is dropped: no frame appends it, no record type holds it, the next cycle cannot see what the model tried and was refused (as distinct from what the user refused). | `harness/meter.py:65,86,95,105`; `harness/turn.py:146`; `graph/nodes/*.py` append lists |
| O33 | **`WebFetch` and `WebSearch` exist on every frame.** A survey of a codebase can leave the repository at 3 points a call. Nothing in the briefs says when that is wanted. | `config.py:45-57`; `graph/surface.py:76-82` |
| O36 | **Chat mode loads the user's settings as the CLI does**: the SDK's `setting_sources=None` means all sources. The graph frames alone are isolated (`[]`). O31 is answered. | `claude_agent_sdk/types.py:2243-2251` |
| O34 | **A session record without `budgets`/`prices` loads with defaults**: `from_json` keeps known keys and the dataclass fills the rest. O13's question is answered. | `session.py:55-58` |
| O35 | **Tests → flows.** Scripted end to end: F3, F4 (ScriptedApprover), F5 (`test_cycle:255`), F6 (`test_runner:257`), F7, F8, F9, F10, F11, F12 (partly), F14 (follow only), F16 (partly: two stores, same id, broken line), F21 (refusals, allowed, cap). **No test at all:** F1 launch paths, F13 clipboard, F15 failure surfacing (no test drives `HarnessUnavailable`, `OrientationFailed`, a payload retry to exhaustion, or a CLI absent), F17 provisional disclosure, F18, F19, F20 itself, F22. **Live once, on the fixture, auto-approved:** F2, F3, F5 (chat only). | `tests/app/*.py` test names; spikes 09, 10 |

### The §3 rivals, settled where the read could settle them

| Prior | Outcome |
|---|---|
| One client per frame turn | **O18**: true, and latency unmeasured → Cycle 1 |
| D5 events are the seam | **O8, O26, O27, O32**: six kinds never rendered, one never emitted, refusals never persisted |
| D7 interrupt aborts to last checkpoint | **O19**: true of the graph; the approval case is unmeasured → Cycle 2 |
| S-2 "a file lock is enough" | **O20, O21**: the lock and the torn line are fine; the log/checkpoint pair is the gap |
| Q-8 free graph reads | unmeasured → Cycle 1 counts them |
| G-2 authority visible | **O24**: in `/show node` only |
| Fixture + Haiku | **O29** sharpens it: fixture, Haiku, *and* auto-approved |
| Assumptions about intent | **O25**: both kinds coexist by construction → F22, Q-P8 |
| G5 rename reached everything | **refuted, O17** |
| Text-first is only prompted (my own R while reading) | **refuted, O22**: enforced |

### A/R carried into the live cycles

| # | **A** | **R** | Decides it |
|---|---|---|---|
| A7 | The stale system prompt (O17) makes Haiku try `attach_finding` with an `excerpt` argument or talk about "readings"; the tool schema has no `additionalProperties: false` so extras pass silently. | Haiku follows the brief (which is correct) over the system prompt, and nothing visible happens. | Cycle 1: grep the events log for `excerpt` and `reading` |
| A8 | On a real repository the survey's 12 findings × 240-char stubs do not carry what the next cycle needs, and the second cycle re-reads what the first kept (O23). | The locators are enough: the model re-runs the command when it needs the text. | Cycle 1: count re-reads of kept locators in cycle 2 |
| A9 | An interrupt while the approval modal is open leaves the CLI waiting on the permission reply and the turn never ends until the modal is answered (O19). | The CLI aborts the turn, the permission callback's task is cancelled, and the modal is orphaned. | Cycle 2: live, Haiku, scripted approver that blocks until told |
| A10 | ~~`setting_sources` unset in chat means the default connection is *not* the user's Claude Code (O31).~~ **Refuted → O36.** | The SDK default loads everything, as the CLI does. | `claude_agent_sdk/types.py:2243-2251`: "When ``None``, all sources are loaded (matches CLI defaults)" |

### Present

What holds: the surface, the meter, the gate and the store do what the design says, and the
scripted suite proves the scripted path. What is out of line with the record: the system prompt
(O17) contradicts three built steps; evidence is kept but never shown (O23); refusals by the
meter are lost (O32); nothing measures the two things the design most depends on live — an
approval answered by a human and an interrupt during one (O19, O29). What I did not look at:
the LangGraph checkpoint ordering under `astream(None)` beyond what `test_runner:257` proves.

Options for you, each a suggestion and possibly wrong: (i) treat O17 as the first fix after
the audit, since it is one file and it shapes every live turn; (ii) decide whether O23 is a
rendering cap to raise or the intended shape ("the package can never carry more than the
model did" cuts both ways); (iii) O32 is a small record type if you want "the model tried and
was refused" to survive a cycle. None of these is started.

---

## Cycle 1 — one live cycle against this repository, Haiku, 2026-09-20 04:50

Run: `scripts/spikes/spike_11_audit_cycle.py`, sessions under the job's temporary directory,
question *"Where does the app decide which tools a frame may call, and what happens when the
model calls one outside that set?"*, one reply in synthesis registering a fact and asking for
closes, a `ScriptedApprover` answering approve-with-words, approve-empty, refuse-with-words,
then refuse "not this cycle". Numbering continues from the forked session's part 2 (O71, A14).

Lens from here on, at your instruction after the fork: **product and efficiency of the flow**,
not adversarial probing.

### O — what one cycle costs and leaves

| # | Observation | Locator |
|---|---|---|
| O72 | **Wall clock 220 s, cost $1.21, four turns.** orientate 56 s / $0.115, antithesis 39 s / $0.230, synthesis opening 46 s / $0.346, synthesis reply 78 s / $0.514. Cost rises with every turn although the reply turn made fewer priced calls (0) than the survey (19 points): each frame resumes one CLI conversation, so every turn re-reads everything the earlier turns read. | `run.log` timeline; `events.jsonl` `TurnFinished.cost_usd` per label; `harness/sdk.py:104` (`resume=`) |
| O73 | **The survey kept nothing.** Orientate spent 19 of its 20 points on `Glob` ×3, `Read` ×8, `Grep` ×2 and never called `attach_finding`, which is free and is the only way a finding reaches the graph. Its stage summary: `0 finding(s), 3 assumption(s), 19 points spent`. Every one of the cycle's five findings was attached by antithesis, which spent 2 points. The assumptions the whole cycle then argued about are grounded on nothing the graph holds. | `events.jsonl` `ToolCalled` by label; `StageFinished orientate`; `graph_driver.py:138-141` |
| O74 | **Zero entities.** `add_node` and `add_edge` were never called in any frame. Against a real repository the GraphRAG "things" layer — the reason for the shape (E, your words: "grounded in a proven shape") — stayed empty; the graph after one cycle is one question, three assumptions, three rivals, five findings, one fact. | `ToolCalled` names: no `add_node`, no `add_edge`; `run.log` op log line |
| O75 | **The survey's reach is the working tree, not the repository.** `Glob **/*.py` returned files under `Harness/`, which is gitignored here. Priced reads can be spent on a tree the studied project does not own. Under the E59 install shape the same walk from the host would find the clone's own source inside it. | `ToolResult` for the `Glob` call; `.gitignore` |
| O76 | Budget exhaustion reaches the model as a hook error, `PreToolUse:Read hook error: BUDGET_EXHAUSTED: Read costs 2 and 1 is left in this pool. Nothing further can be bought here — report what you have.` It worked: the model stopped and answered, and treated the refusal as evidence for the question it was asked ("Perfect timing — I just experienced exactly what you asked about"). | `ToolResult` of the refused `Read`; `TextDone` in `orientate.0` |
| O77 | A `Read` of the project directory itself returned `EISDIR` and cost the same 2 points as a good read (charge on authorisation). A wasted call and a useful one are priced alike, and the model has no cheaper way to learn a path is a directory than to pay for it. | `ToolResult` `EISDIR`; `harness/meter.py` charge-before-run |
| O78 | The first `StructuredOutput` in orientate was rejected by the CLI as unparseable JSON and retried by the model inside the same turn. Our re-author loop never saw it; the fork's O47 records the same. Two of the cycle's five `StructuredOutput` calls were this one call. | `ToolResult` `InputValidationError` |
| O79 | **Gated calls arrive in batches, so your words on the first cannot inform the second.** The model issued `close_node x1.2` and `close_node x1.3` in one assistant message; both approvals were asked at 178.6 s. The scripted refusal of x1.2 ("a refuted rival is not the same as a wrong one; leave it open") was answered before x1.3 was, but x1.3 carried the identical reasoning and was already on the table. Only the fifth proposal (a1.1, at 205.8 s) came after the model had read any refusal. | `run.log` timeline; `ApprovalAsked` inputs for x1.2, x1.3 |
| O80 | **The user's fact grounded the rivals, not the assumptions.** `propose_fact … supports: [x1.1, x1.2, x1.3]`, then x1.1 confirmed, x1.2 and x1.3 refuted (two of the three by the same sentence), then a1.1 proposed as refuted "because its rival x1.1 is confirmed". Nothing in the tool stopped one sentence from settling three propositions in both directions; only the approver did. | `ApprovalAsked` inputs; `graph/store` proposals p1.1–p1.5 |
| O81 | The model made three free `graph_search` calls in the reply turn to find node ids that the brief had already given it, between "Now I'll close the assumptions" and "I see — I had it backwards". Free reads were measured at 3 per cycle (Q-8), all in synthesis. | `ToolCalled` `graph_search` ×3 in `synthesis.1.1`; `TextDone` |
| O82 | **Three of five kept findings exceed the 240-character render cap.** Sizes 188 / 470 / 278 / 32 / 401 chars; the package after the cycle is 3 835 chars / 28 lines. O23 is now observed rather than read: the next cycle sees the command and the first 240 characters of findings that are 470 and 401 characters long. | `run.log` finding sizes; `graph/package.py:41-43` |
| O83 | Antithesis attached its findings with `target: "1"`, `"2"`, `"3"` — ordinals — and the tool resolved them to x1.1–x1.3. The model reasons about "assumption 1", not "a1.1"; the ordinal path is the one it takes when offered. | `ToolCalled` `attach_finding` inputs |
| O84 | Approvals: 5 asked, 2 approved, 3 refused with words; `Decision.applied` true on the two approved only. The dry-run effect text shown at the ask reads as the *done* tense ("x1.2 is now refuted.") for a thing that has not happened. | `ApprovalAsked.description`; `harness/hooks.py:143-160` |
| O85 | **A7 is refuted.** Zero `excerpt` arguments in 33 tool calls and zero uses of "reading" in the model's text. Haiku followed the brief over the stale system prompt; O17 costs tokens, not behaviour, on this model. | `run.log` last lines |

### A/R from this cycle

| # | **A** | **R** | Decides it |
|---|---|---|---|
| A15 | The conversation transcript, not the package, is the carrier the design actually runs on: every turn pays for every file the survey read, and the cost of a reply turn (O72) is mostly cache-read input, not the model's own output. | The cost growth is the model's thinking and tool-input output growing with the task; input is a minor share. | The CLI's transcript for the conversation records per-message usage; read it. **Settled below.** |
| A16 | Orientate keeps nothing (O73) because its brief presents `attach_finding` as optional and the priced built-ins as the way to look, and the pool runs out before it thinks to keep anything. | Haiku's habit: it reads, it does not annotate; a stronger model keeps findings without being told. | Two runs, same question: (a) brief says "every assumption must cite at least one kept finding", (b) unchanged brief on Sonnet. (b) is off the table by E61 (Haiku only). (a) is a one-line prompt change and one Haiku run: proposed, not run. |
| A17 | Entities stay empty (O74) because nothing in the cycle *needs* one: assumptions and rivals can be closed without ever naming a thing in the project, so the GraphRAG layer is optional by construction and will stay empty on every question that is not explicitly "what are the parts". | The model would name entities if the payload schema asked for them, the way it names assumptions. | Same as A16: a schema field, one Haiku run. Proposed, not run. |
| A8 | carried, not measured: the second-cycle flag was not used. | | Cycle 2's resume run stays in synthesis, so A8 remains open. |

### Present

The machinery ran clean end to end on a real repository: four turns, no crash, every approval
recorded, the gate refusing on the user's word. What the run shows against the purpose (§0.2):
the frame that exists to *look* keeps none of what it saw (O73); the layer that exists to hold
*what the project is made of* is empty (O74); a single sentence of the user's was allowed to
settle three propositions both ways in one batch the user could not steer mid-way (O79, O80);
and what the graph keeps is shown cut (O82). None of these is a bug in the sense of a wrong
line; each is the built shape doing exactly what it was built to do, on a task the shape was
not tested against until now. The cost pattern (O72) says the conversation, not the graph, is
carrying the state between frames, which is the opposite of the design's thesis — A15 is
settled next.

**Backlog (your instruction 2026-09-20: cost accounting is not a priority).** O72's per-turn
dollar figures are the CLI's *cumulative* session totals (`cost-state` lines in its transcript
carry the same four numbers), so the cycle cost $0.51, not $1.21, and the status bar sums the
same cumulative figure. A15 is withdrawn; its premise was this misreading. Parked, not pursued.

---

## Cycle 2 — interrupt while an approval is open, then resume (A9; F5, F6 live), 2026-09-20

Runs: `scripts/spikes/spike_12_interrupt_during_approval.py` (Haiku, on a *copy* of the Cycle 1
session, one synthesis reply that provokes `propose_fact`, an approver that blocks, `interrupt()`
two seconds after the ask, then a plain reply) and `scripts/spikes/spike_13_orphaned_modal.py`
(headless Textual, no model: the real `ProvenanceApp`, the real `ApprovalScreen`).

### O

| # | Observation | Locator |
|---|---|---|
| O86 | **The CLI aborts the turn under an open approval and cancels the callback.** Ask at 11.2 s, `interrupt()` at 13.2 s, `TurnFinished` at 13.7 s with `subtype=error_during_execution`, `terminal_reason=aborted_tools`, `interrupted=True`. The approver's `await` was cancelled by the SDK (`CancelledError` inside `approve`). The events log holds one `ApprovalAsked` and no `ApprovalAnswered`. | `cycle2/run.log`; `harness/sdk.py:202-205` |
| O87 | **Nothing leaks into the graph and the conversation resumes.** Ledger delta after the abort: 0 lines, 0 proposals, 0 decisions. The thread owes `('synthesis',)`; a plain reply ten seconds later ran on the same conversation id and completed (`ok=True`, 10.1 s). F6 holds for the synthesis stage; the model carried on as if the aborted call had not happened, and no record says it was ever proposed. | `cycle2/run.log`; `graph_driver.py:87-90,116-118` |
| O88 | **Escape with the modal open interrupts the run underneath it.** `ApprovalScreen` binds `ctrl+y` and `ctrl+n` only; the app binds `escape` to `interrupt` with `priority=True`, so the key the user reaches for to leave a dialog aborts the model's turn instead. Headless: one `runner.interrupt()` call, modal still on top, `approve()` still awaiting. | `tui/screens.py:41`; `tui/app.py:68,141-142`; `spike_13` step 1 |
| O89 | **The orphaned modal crashes the app when answered.** After the cancellation the screen stays (stack depth 2). `ctrl+n` then calls `future.set_result` on a cancelled future: `InvalidStateError: invalid state`, the app exits with return code 1. So the whole sequence from the user's chair is: a proposal appears, they press Escape, the modal stays, they press refuse, the shell is gone. | `tui/screens.py:166`; `spike_13` steps 2–3 |
| O85b | A20 (fork): in Cycle 1 no later proposal's `because` quoted an earlier refusal's words; the one proposal made after a refusal (a1.1) reasoned from the confirmed rival, not from the user's sentence. A21 (does the CLI time out an unanswered request): not measured; the ask was answered within two seconds in every run. | Cycle 1 `ApprovalAsked` inputs |

### A/R

| # | **A** | **R** | Outcome |
|---|---|---|---|
| A9 | An interrupt while the approval modal is open leaves the CLI waiting on the permission reply and the turn never ends until the modal is answered. | The CLI aborts the turn, the permission callback's task is cancelled, and the modal is orphaned. | **A9 refuted, R confirmed (O86, O88, O89)**, and R is worse than either of us wrote: the orphan is not just left over, it takes the shell down. |
| A18 | The right shape is the one the fork's F4 pilot and this run both point at: the modal owns its own Escape (refuse, with the user's words), so the app's interrupt never fires under a dialog; and `TuiApprover.approve` dismisses the screen in a `finally` when its await is cancelled, so an abort from anywhere clears the dialog and a late answer has nowhere to land. | Keep Escape as the global interrupt and make the modal *survive* the abort, recording the user's late verdict as words on the interrupted turn. | Yours. A18 is smaller and matches E42 ("interrupts … as the claude cli already does"); R keeps a verdict the model will never see. Not built. |
| A19 | O87's silence is a gap in the record the design cares about: an aborted proposal is a thing the model wanted to do and the user did not answer. It should leave a `ProposedWrite` with `decision=aborted`, so the next cycle's package can show it. | An aborted turn is noise and nothing about it belongs in the graph. | Same question as the fork's Q-P9 (attempted vs committed). Listed, not decided. |

### Present

The design's core promise at this seam holds: an interrupt cannot leave a half-written graph, and
the cycle carries on afterwards. The shell in front of it does not hold: the one key a user
presses to back out of a dialog aborts the model's work and then crashes the shell on the
next keypress. Both are small fixes (a binding and a `finally`) and both belong on the
`ui-workflow` branch, not the core; they are listed for the UI agent's report, not made here.

---

## Cycle 10 — F22: what the design is for, against what was built (Q-P8), 2026-09-20

Method: your words (E1–E66) on one side; on the other, what one live cycle on this repository
(Cycle 1), your own two runs inside `Harness/` on 09-19 (fork, O66, O107), the interrupt run
(Cycle 2) and the read of the core (Cycle 0) show the built shape doing. Numbering continues
from the fork's O109 / A23. Each row is one place the two sides meet; the lens is product and
efficiency, as you asked after the fork.

### The purpose, in your words

> E51 "the entire point of this build is to curb the premature stopping or invalid concluding
> of agents, or coming to the wrong conclusion by forcing context and evidence into a
> comprehensive and structured shape."

> E12 "all tool calls are replaced in the session context with the output of the graph and the
> relevant pieces of the docs that are attached to them."

> E19 "The orientation in of itself is letting the agent reconcile the user input against the
> landscape of the project, and then assuming based on that."

> E2 "the assumption of an agent is always an interpretation of what the user is asking"

> E48 "a thought graph that is rooted in the user approval similar to how a graph rag works
> where it goes through cycles of growth, compression and reconcilation such that only the
> correct data is maintained across sessions"

> E59 "the Harness project, that is my work project that I want to be using this flow on for
> testing real life usage."

### O — where the built shape meets the purpose

| # | Observation | Locator |
|---|---|---|
| O110 | **The evidence the survey gathers is not forced into the shape; it stays in the transcript.** E51 and E12 say the graph is what carries context. Built: within a cycle the three frames resume one CLI conversation, so what orientate read (eight files, 56 k tokens of context by the reply turn) is carried by the *conversation*, and the graph receives only what the model chose to `attach_finding`. On this repo (O73) and on your Harness run (fork O107) that was zero for the survey frame, twice. Across cycles the conversation is dropped and the package (3.8 k chars) stands in; so the next cycle starts from assumptions with nothing under them. The pricing made the model look less (E11's first purpose); nothing made it keep more. | `harness/sdk.py:104`; `graph/nodes/orientate.py:52-58`; `package.py`; Cycle 1 `StageFinished orientate`; fork O107 |
| O111 | **Q-P8, with evidence: the two kinds do not coexist in practice; the assumption layer absorbed the claim layer and the entity layer stayed empty.** The schema says an assumption is "one checkable proposition about what is being asked" (E2). On the one live question every assumption was a proposition *about the project* ("the frame's tools are decided at the moment the SDK client opens", "`Meter.charge()` is the last-resort refusal"). No `claim` node was ever written by any frame, and no entity (O74). So the GraphRAG layer E48 names — things and claims about them, with evidence — was carried entirely by nodes called assumptions, and the things themselves were never named. | `graph/payloads.py:27`; `graph/thought.py` node kinds; Cycle 1 assumptions text (package render) |
| O112 | **The build cannot tell which kind of question it was given.** A "how does X work" question makes E2's interpretation collapse into a claim about the code (O111). A task-shaped request ("add the handler", the Harness kind of work, E66) would make an interpretation a genuinely different thing from a claim. `/graph <text>` carries no kind, the briefs are the same for both, and the package renders both under ASSUMPTIONS. Whether E2 and E48 separate on a task-shaped request is untested: both live runs asked questions. | `runner.py` `/graph` handling; `graph/nodes/orientate.py:35`; Cycle 1 and the 09-19 Harness question |
| O113 | **Breadth is asked for and not measured.** E11 ("go wide before going deep") and E14 ("breadth" is load-bearing) are enforced by a count ceiling and the word "distinct" in a schema description. The three live assumptions were three views of one mechanism (surface list, hook, meter), and two of the three rivals said the same thing ("the hook is the enforcer"). Nothing in the cycle notices that three assumptions are one topic. | `graph/payloads.py:53`; Cycle 1 assumptions and rivals |
| O114 | **The antithesis is the part that works as you described it.** One rival per assumption, in a separate turn, with base + N points (E27a–c), and it kept five findings against three assumptions on two points of spend. Because the survey kept nothing, the graph's evidence is one-sided by construction: the side that attacks holds all of it. | `graph/nodes/antithesis.py:30-70`; Cycle 1 antithesis tally |
| O115 | **Premature concluding reappears inside synthesis as premature closing.** From one sentence of yours the model proposed four closes in one reply turn, three of them in one message (O79, O80), one of them your own assumption on the strength of its rival being confirmed. E20 held at the gate — every close was asked — and only because the approver refused three of them. The brief invites it: "put it to them as changes to the graph", with `close_node` in the list. E31/E32 marked this stage "exploration required"; this is the first exploration data. | `graph/nodes/synthesis.py:36-60`; Cycle 1 `ApprovalAsked` ×5 |
| O116 | **Your words at a refusal go into the graph and not into the model's next move.** The words reach the model verbatim (fork O93) and the next proposal does not answer them (A20 confirmed, O85b). The next cycle's package then reads every refusal as "Do not propose them again" (fork O99), including "not this cycle". So the one channel the design gives you to steer mid-cycle (E28: approval is its own surface) is recorded faithfully and acted on weakly. | `graph/package.py:183-192`; Cycle 1 `because` texts |
| O117 | **Nothing consumes the graph except the next cycle.** E12 says the graph replaces tool calls in the session context; E59 says the flow is for real work in Harness. Built: chat mode is your own Claude Code with your settings (O36) and receives nothing from the graph; no command renders the package into a prompt, a file, or a CLAUDE.md for the working session. The loop produces a grounded graph and stops; the agent that does the work in Harness never sees it. | `chat.py:54-67`; `runner.py` commands; no export path in `app/` |
| O118 | **What the loop does well, measured.** On a real repository it ran end to end with no crash; every alteration was asked; an interrupt at the worst moment left the graph clean and the cycle resumable (O86, O87); the fenced keep path worked five times out of five (fork O109); the scripted suite covers the scripted path (O35). Time to first word from the model: about 140 s on Haiku, all three frames, before you can reply. | Cycles 1, 2; `tests/app/` |
| O119 | **Against the Harness catalogue.** The failure class at the top of your own retrospective there — "a repo document was treated as authoritative without checking it against the thing it describes" — is exactly what survey → assumption → antithesis-with-evidence addresses, and O114 shows that part working. The catalogue's other finding, "the rules exist and are not reached" (a retrieval problem), is the one O117 leaves open: the graph is the retrieval structure and nothing retrieves from it. | `Harness/docs/tasks/agent-workflow-overhaul/FAILURES-OBSERVED.md` §1; `INTERACTION-MAP.md` §1 (reference only, E66) |

### A/R — the shapes that follow, each a branch if tried (E65)

| # | **A** | **R** | Decides it |
|---|---|---|---|
| A24 | **Looking is keeping.** In the surveying frames a priced `Read`/`Grep` result *is* a finding: the PostToolUse hook already holds the output and records it on the question (or on an entity named from the path). `attach_finding` remains for keeping a range of something already seen. O110 and O111 close by construction: the survey keeps everything it paid for, and every read names the thing it read. This is E12 taken literally. | Keeping every read floods the graph with noise the model did not choose, and the package (already cut at 240 chars) gets worse, not better; the fix is the brief (fork P-8 ii: an assumption must cite a finding). | One Haiku run each on the same question, on separate branches: `looking-is-keeping` and `cite-or-retry`. Count findings kept, entities named, and what the next cycle's package carries. |
| A25 | **Two kinds of `/graph`.** A question gets the cycle as built (assumptions are claims about the project, attacked, closed by you). A task gets a cycle whose assumptions are interpretations of the request (E2), whose antithesis attacks the interpretation, and whose synthesis ends by rendering the package for the working session (O117). | One shape with a better brief covers both; the kind is the model's to infer from the text. | Branch `graph-task-kind`: one scripted run and one Haiku run on a task-shaped request against Harness. Not started; O112 says the data does not exist yet. |
| A26 | **The package is the hand-off.** A `/package` command (or the end of synthesis) writes the rendered graph — facts, open assumptions, kept evidence in full, refusals with their words and their scope — to a file the working session reads. Closes O117 with no change to the cycle. | The working session should *be* the synthesis stage: chat mode gains the graph as context and the gated tools, and there is no hand-off because there is no second agent. | Yours; the second is a bigger shape (chat and graph merge) and would be its own branch. |
| A27 | O115 is a brief problem: synthesis should propose *one* change per message and wait, and `close_node` should require a finding or a fact as `because`, not a rival's status. | It is a model problem (Haiku), and the gate is the right and sufficient place to catch it. | One Haiku run with the brief changed; if it still batches, R. |

### Present — the answer to "what you actually built for vs what this design is supposed to be used for"

What was built is a **question-answering loop with provenance**: it takes a question about a
project, surveys, names propositions, attacks them with kept evidence, and puts every change to
you. On that job the core does what your words say, and the antithesis frame in particular
does it well (O114, O118).

What the design is for, in your words, is **an agent that does not conclude early or wrongly
while doing real work** (E51, E59). Between the two there are three gaps, none of them a bug:

1. **The evidence is not in the shape.** The survey's reads live in the transcript, not the
   graph (O110). So the "comprehensive and structured shape" holds the attack and not the
   survey, and the next cycle inherits assumptions without their ground.
2. **The shape has one kind of node for two kinds of thing** (O111, O112). On questions,
   assumptions are claims and the entity/claim layer goes unused; on tasks, which is what
   Harness needs, the build has not been run at all.
3. **Nothing reads the graph but the graph** (O117, O119). The loop ends with a graph and the
   working agent never sees it.

The shell's failures (O88, O89, fork O95, O96) sit on top of this and are cheaper; they are on
the `ui-workflow` branch. Q-P8 is answered as far as evidence can answer it (O111); the part
that needs a task-shaped run is marked (O112, A25) rather than guessed.

---

## Present — 2026-09-20

The ledger in §7 is the compressed list; every line has its O-lines above. This section is what I
would do with it, in the order I would do it, each item a suggestion (E22) and possibly wrong.

### What holds

The core does what your words say on the scripted path and on one real repository: frames run
in order, every alteration is asked, an interrupt at the worst moment leaves the graph clean
and the cycle resumable, the fenced keep path works, the antithesis frame attacks with evidence.
Nothing in the core was changed this session; nothing was merged anywhere.

### The fix list, ordered by effect on your daily use (E58: "smooth … not interrupt workflow")

**Tier 1 — the shell, on `ui-workflow`, small, no shape change.** The UI agent has commits for
the paste/copy/recall/clear/expand set (E55, E62), the log without deltas (E64), Esc owned by
the modal (L14 first half), and "which frame is running" (A5). Still to do there from this audit:
the `finally` that dismisses an orphaned modal (L14 second half, O89); the approve key (L12);
one modal at a time in call order with "n more waiting" (L13); the node's text and the model's
`because` on the modal, effect phrased as "would" (L11); runner notices into the session log
(L3). A day's work, all with Pilot tests.

**Tier 2 — the core, one file each, no shape change.** In this order: the system prompt (L26);
the render cap, either raised or `/show node` showing the whole finding (L25); a scope on
refusals so "not this cycle" is not rendered as "never" (L15); meter refusals recorded (L27);
the fork seed from `pending()` (L16); a done-marker or post-commit append for the ghost cycle
(L1, needs **Q-P9**); the state-directory split and a README (L8, L10, **Q-P11**), which is the
one item that blocks real use in Harness because today it writes into the host.

**Tier 3 — the shape, one branch each (E65), rooted in E51.** These are the three gaps F22
names, and each is a run, not a fix:

| Branch | Gap | What it tries | What decides it |
|---|---|---|---|
| `looking-is-keeping` | L19, L20 | A priced read *is* a finding, recorded by the PostToolUse hook on the question or on an entity named from the path (A24; E12 literally). | One Haiku cycle, same question: findings kept, entities named, package size and content. |
| `cite-or-retry` | L19 | Unchanged shape; the survey's answer is refused unless each assumption cites a kept finding (A24's rival; fork P-8 ii). | Same run; compare with the branch above. |
| `graph-task-kind` | L20, O112 | `/graph` takes a kind: question (as built) or task, where assumptions are interpretations (E2) and synthesis ends by rendering the package for the working session (A25). | One task-shaped run against Harness, after the state split. |
| `package-handoff` | L21 | A `/package` that writes the graph — facts, open assumptions, evidence in full, refusals with words and scope — where the working session reads it (A26). | Does the working session's next turn cite it. |

I would run `looking-is-keeping` first: it is the smallest change that touches two of the
three gaps, and its result tells you whether the entity layer fills on its own once reads are
kept. `package-handoff` second, because it is what makes the loop useful for Harness work.

### Questions, compressed

| # | Question | My suggestion |
|---|---|---|
| Q-P9 | Is the log the trail of everything *attempted* or everything *committed*? (L1) | Attempted, with a done-marker. |
| Q-P10 | Who runs the Harness install? | You, from the README, once P-19a exists. |
| Q-P11 | State beside the install or in a dot-directory of the studied project? | The install. |
| Q-P12 | Both A24 branches, or one? | Both; they are cheap and they answer each other. |
| Q-P13 | Is the working session meant to *be* the synthesis stage (A26's rival), or a reader of its output? | Reader first; merging chat and graph is a larger shape and its own branch. |

### What I did not do, plainly

No live run on a task-shaped request (O112). A8 (re-reads in a second cycle), A13 (mount
mismatch), A21 (permission timeout) and A22 (fork chat interleave) are unmeasured. Cost
accounting is backlogged at your word (L31). The graph panel was not looked at (E63). The
executor was assessed by reading only and not probed further, at your word after the fork.
Two of my own assumptions were refuted by the runs (A7, A9) and one was withdrawn as a
misreading (A15); they stand in the log as written.

### Where the evidence lives

- This log, §7 and the cycles above; the fork's part 2 folded in below.
- `scripts/spikes/spike_11_audit_cycle.py`, `spike_12_interrupt_during_approval.py`,
  `spike_13_orphaned_modal.py` — reproducible; the run logs are in the job's temporary directory
  and are not kept.
- Branch `ui-workflow` (worktree `.claude/worktrees/agent-a05f27d14ce8ecc60`) — the UI agent's
  commits and its overview `docs/design/ui-workflow-2026-09-20.md` there.
- Nothing on `main` or `orientate-absorbs-assume` changed except this document and the three spikes.

---

# Part 2 — the forked session's cycles, folded in


Status: **written 2026-09-20 by the forked session; to be folded into
`production-audit-2026-09-20.md` by whoever holds it.** Same registers as that document (E your
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

---

## Addendum — the UI agent's report, 2026-09-20 05:45 (verified here)

Branch `ui-workflow`, 17 commits, worktree `.claude/worktrees/agent-a05f27d14ce8ecc60`, based
on `orientate-absorbs-assume` at `fa8f871`. Verified in this session: the suite there is
**72 passed** (58 before); `git diff --name-only fa8f871 ui-workflow` touches 13 files and none
under `app/graph/`, none of `harness/sdk.py`, `hooks.py`, `tools.py`, `evidence.py`, `turn.py`,
`graph_driver.py`; `GraphPanel` is unchanged. Its overview and report:
`docs/design/ui-workflow-2026-09-20.md` on that branch. Nothing merged.

Done there, from your list (E55, E58, E62, E64) and from this audit: multi-line paste inserts
and does not send; up/down recall; `/copy`, `/expand`, ctrl+o, `/wipe`, ctrl+l; the frame in
progress and the pool moving per call; the log without stream deltas; a read-only lane so
`/show` and friends answer beside a running turn; a nameless launch reopens the last session;
ctrl+q quits through the runner; Esc owned by each modal (approval refuses with the typed words);
the advertised approve key approving; a cancelled await removing its own modal; gated calls
asked one at a time in call order with "N more waiting"; the node's text and the model's
`because` on the modal; the shell's own lines in the session log.

**Four corrections it returns to this log, accepted:**

| # | Correction | Where |
|---|---|---|
| O2 | Misattributed and half refuted: `ALLOW_SELECT = False` belongs to `CollapsibleTitle`, not `Collapsible`; a tool *result* was always draggable, the *title row* was not. Its test drives a real drag. | Cycle 0 (partial), O2 |
| O6 | The cause is not missing bindings: Textual checks priority bindings App → screen → widget, so a screen's own `escape` could never win against the app's priority `escape`. The fix is in the action: each modal says what Esc means to it, and `action_interrupt` asks the top screen first. | Cycle 0 (partial), O6; Cycle 2, O88 |
| O26 | Agreed: `StageStarted` is dead code; it renders `TurnStarted(kind="graph")` instead and leaves `StageStarted` alone, since emitting it would mean predicting a cycle number the frame allocates from the op log. | Cycle 0, O26 |
| **O120** | **New, intermittent: orientate's `StageFinished` line can read the pre-frame checkpoint.** In its scripted run the line read `orientate · cycle 0 — 0 finding(s), 0 assumption(s), 0 points spent` while the panel in the same run read `orientation:1 5/20`. The driver reads the thread state back as the node's update streams and can get the checkpoint from before the frame. In my live run (Cycle 1) the same line read `3 assumption(s), 19 points spent`, so the order is not fixed. Not touched by either of us; its test documents it without asserting on it. | `graph_driver.py:112-115`; ledger **L32** |

It also notes that the read-only lane widens the S-2 window: `/show` now reads the shared op
log while a frame may be appending. The store's whole-line read (O21, O42) is what protects it.

| # | Flow | Finding (one line) | Evidence | Your verdict |
|---|---|---|---|---|
| L32 | F3/F10 | The frame-finished line can be computed from the checkpoint before the frame, intermittently, so it may say 0 while the panel says 3 | O120, UI agent's Pilot run; `graph_driver.py:112-115` | |
