# Antithesis pass on `combined-plan-2026-09-20.md`, 2026-09-20

Method: for each element, state the rival, then go and check it against the code at
`orientate-absorbs-assume` `fa8f871`, the recorded words (E/D/Q numbers), and where a claim turns
on behaviour, against the surviving artefacts of the audit's own live Cycle 1
(`/root/.claude/jobs/44a3082f/tmp/cycle1/sessions/graph/ops.jsonl`). Test suite run once as a
baseline: **58 passed** (`uv run pytest tests -q`). Throwaway verification code was written in the
worktree and removed. **No live model call was made** — everything that needed runtime evidence was
settled from the Cycle 1 op log, direct handler invocation, or a read of the code. Lens throughout
is product and design, not security.

---

## Verdict table

| Element | Rival (one line) | Verdict | Evidence |
|---|---|---|---|
| P0.1 Split the directories | `sessions_dir` already exists, and the audit's P-19b (one graph per studied project) is silently dropped with L9 | RIVAL PARTLY HOLDS | `config.py:359-381`; part2 P-19b; L9 |
| P0.2 Fence the survey | Refuses a path argument under `home`, but O75's leak was a `Glob` rooted at `cwd`; and the check's position relative to `meter.charge` is unspecified | RIVAL HOLDS (in part) | `hooks.py:52-87`; O75; O77 |
| P0.3 Rewrite the prompt | Measured harmless (O85), and Stages 1–4 change what it must describe | RIVAL REFUTED on the element, HOLDS on placement | `prompts/graph_system.md`; O85 |
| P0.4 Lossless store, cap at render | The truncation the test asserts on is in a file the element does not name | RIVAL HOLDS (locator) | measured: `/show node f1.2` = 245 chars for a 470-char finding; `thought.py:515-531` |
| P1.1 Answer nodes from decisions | `blocks` is sign-inverted; 1 in 4 answers has no target; `close_node`/`supersede` refuse the kind; there is no date | RIVAL HOLDS | measured on Cycle 1; `tools.py:469,489`; `thought.py:85,204,416`; `store.py:211-222` |
| P1.2 `Blocked` ledger line | Two of its four reason classes have no source; `aborted` is unreachable; decides open Q-P9 | RIVAL HOLDS | `meter.py:84,93,103`; `hooks.py:147`; `_common.py:52-58`; `graph_driver.py:116-117`; O87 |
| P2.1 Reference on every priced read | Turn-vs-cycle is the wrong axis; the boundary that bites is the re-author attempt | RIVAL HOLDS | `sdk.py:118`; `scripted.py:81`; `orientate.py:112-135`; `antithesis.py:52-54` |
| P2.2 `Finding` carries its citation | Two existing fields for this job are dead; a nested record is a checkpoint decision the element does not flag | RIVAL PARTLY HOLDS | measured: all 5 Cycle 1 findings `tool_call_id=''`, `price=0`; `state.py:162-163,453-470` |
| P2.3 `store_evidence` | `turn.records` holds each result **twice**, with CLI line prefixes — `lines="a-b"` is not lines of the file | RIVAL HOLDS | measured; `hooks.py:93` + `sdk.py:147` both call `turn.record`; `turn.py:126-129` |
| P2.4 `attach_finding` stays | It is not the fallback — it is the only thing that works on a retry and in antithesis's funded re-read | RIVAL REFUTED; element understates itself | `antithesis.py:52-54`; `orientate.py:112-135` |
| P2.5 Assumption must cite its ground | Checks emptiness, not validity; a sentence in the field passes; hard-fails the frame | RIVAL HOLDS | `thought.py:335`; `orientate.py:144,154`; measured: 3/3 live assumptions re-author on 1 of 20 points left |
| P2.6 Breadth stand-in | Would have fired **zero** times on the case it cites, and rewards paraphrase | RIVAL HOLDS — drop it | measured: no two Cycle 1 `moved_by` strings match; `state.py:117` |
| P3.1 `/handoff` | `/show package` already exists; the element is smaller than described | RIVAL REFUTED on the element, HOLDS on size | `commands.py` BUILTINS; `runner.py:457-475` |
| P3.2 One change, close on ground | An "names an id" check passes the exact call it exists to refuse | RIVAL HOLDS on the check's strength | measured: p1.5 `because` = "because its rival x1.1 is confirmed" |
| P4.1 Origin-aware package | "Every record already carries `session`" is **false**; `propose_fact` refuses the re-ask it prescribes; unbounded against E58 | RIVAL HOLDS | measured; `store.py:206-222`; `tools.py:300-305`; `runner.py:486-509` |
| P4.2 Dormant promotion tool | "Dormant" costs five registrations; the real H5 gap is the discarded timestamp | RIVAL HOLDS — drop, do the decode fix | `store.py:70-92`; `state.py:456`; `surface.py:47`; `graph/graph.py:104` |
| P4.3 Read-down slot | An enum value with no consumer is not an element | RIVAL HOLDS (mildly) — fold into P2.1 | plan §2, P4.3 |
| P5.1 Task-shaped live run | Numbered last, scheduled second; Stages 1–4 are built on the gap it exists to close | RIVAL HOLDS on the order | O112; branch-decisions branch 3; plan P5.1's own text |
| Order of stages | P5.1 and A8 belong before P1.1, by the plan's own words | RIVAL HOLDS | see above |

---

## Element by element

### P0.1 — Split the three directories

**Rival in full.** Three things. First, `AppConfig` does not "gain `state_dir`" — it already has an
independent `sessions_dir` field, so this is a rename plus one new field, and the rename touches
seven call sites. Second, the audit's install-shape proposal had three parts and the plan takes two:
**P-19b is dropped without a word**, and with it ledger line **L9** and assumption **A13**. Third,
`state_dir = <home>/sessions` gives **one graph per install**, which is not the same thing as
P-19b's "one graph per studied project, keyed by the studied project's resolved real path"; with
`--cwd` still free to point anywhere, two studied projects driven from one clone share a graph and
a cycle sequence.

**What I did.** Read `config.py:359-381` — `cwd: Path` and `sessions_dir: Path` are already separate
fields, defaulted `root` and `root / "sessions"`. Traced `sessions_dir` to `runner.py:51`,
`tui/app.py:235`, `spike_09_live_cycle.py:46,79`, and five test constructions in
`tests/app/test_runner.py:65` and `tests/app/test_tui.py:28,95,122,148`. Read the audit's P-19a/b/c
(`production-audit-2026-09-20-part2.md` §"P — the shape"). L9 appears in the ledger of both
documents and in no element of the plan.

Also checked the element's test. *"Launch with `--cwd <tmp project>`: after a scripted cycle nothing
exists under the tmp project"* — the scripted harness never launches the CLI subprocess
(`scripted.py` has no `ClaudeSDKClient`), so the test passes trivially and proves nothing about the
case O66/O67 recorded. The state that actually lands outside `state_dir` in a live run is the CLI's
own, keyed by the cwd string under `~/.claude/projects/` (O71), which no `--state` flag reaches.

**Verdict: RIVAL PARTLY HOLDS.** The element's substance is right and well rooted (E59, E58, Q-P11
answered as "the install"). Three changes: say it renames `sessions_dir`; say whether P-19b is
deferred or abandoned (L9 is a ledger line and the plan claims to close L8 and L10 from the same
cycle); and either make the test live or drop the "nothing exists under the tmp project" claim.

---

### P0.2 — Fence the survey to the studied project

**Rival in full.** The element does not do what its root describes. O75 is: *"`Glob **/*.py`
returned files under `Harness/`, which is gitignored here."* The element refuses calls *"whose path
argument resolves under `home` or `state_dir`"*. A `Glob` with `pattern="**/*.py"` and no `path`
resolves to `cwd`, which is not under `home` — so the element refuses nothing about the call that
produced the finding. The plan half-admits this in **A0.2** but still lists "Closes L28 (part)".

**What I did.** Read `hooks.py:52-87`. `pre_tool_use` reads `tool_name` and nothing else; it never
touches `tool_input`. So a path check is genuinely new code, not a tightening. Read the ordering:
`turn.meter.charge(name, call_id)` is at line 68, and a refusal placed after it charges the pool for
a call that never ran — which is exactly O77 ("A `Read` of the project directory itself returned
`EISDIR` and cost the same 2 points as a good read"). The element does not say where in the hook the
check goes, and that placement is what decides whether the fence costs the user points.

**Verdict: RIVAL HOLDS in part.** As a narrow fix — a frame cannot `Read` its own op log — the
element is correct, cheap, and worth having under the E59 install shape where the clone sits inside
the host. It does not close the observed leak, and L28 should be marked open, not "(part)". Add one
sentence: the check runs **before** `meter.charge`.

---

### P0.3 — Rewrite the system prompt

**Rival in full.** The audit measured this as costing tokens and not behaviour, so it is the
cheapest element in the plan and also the least consequential; and putting it in Stage 0 means
writing it twice, because Stages 1–4 add `answer` nodes, `store_evidence`, a citation rule and a
grounding rule the prompt will have to describe.

**What I did.** Read `prompts/graph_system.md` in full: it does say "four frames", "assume (fund one
reading at a time…)", "readings", and "the excerpt copied from what the tool returned". L26 stands.
O85 is the measurement: *"A7 is refuted. Zero `excerpt` arguments in 33 tool calls and zero uses of
'reading' in the model's text. Haiku followed the brief over the stale system prompt."*

**Verdict: RIVAL REFUTED on the element, HOLDS on its placement.** The rewrite is right and takes an
hour. Move it to the end of the work, or write it once with the finished vocabulary in hand. One
note on the test: the substring `"reading"` catches `"readings"`, which is what is actually there —
fine, but say so, because a reader will check for the plural and not find it.

---

### P0.4 — Store lossless, cap only at render

**Rival in full.** The element's own test does not pass against the files the element names. `/show
node <finding>` does not go through `package._quote(240)`; it goes through `thought.label`, which
cuts at 89 characters.

**What I did.** Ran the element's test against the real Cycle 1 finding `f1.2` (470 characters, the
one O82 names). Result: `package.describe_node(g, "f1.2")` returns **245 characters total**, and
`f1.2`'s excerpt is not contained whole. The cut happens at `thought.py:519-520`:

```python
text = " ".join(str(a.get("text", "")).split())
if len(text) > 90:
    text = text[:89] + "…"
```

and `describe_node` opens with `lines = [thought.label(g, nid)]` (`package.py:227`). The element's
file list — `graph/package.py:41-43,57,244`, `runner.py` `/show` — omits `thought.label` entirely.
The storage half of the claim checks out: `Finding.excerpt` is stored whole and the executor's cap
is `MAX_LINES = 80` / `MAX_BYTES = 6000` (`evidence.py:41-42`), exactly as stated.

**Verdict: RIVAL HOLDS (locator, not intent).** The element is right and is the strongest of the
Stage 0 four (H2 is a `[protect]`, and P2.3 makes evidence the primary carrier). It needs
`thought.label` in its file list, and `describe_node` needs a full-text branch for an evidence node
rather than relying on the one-line label.

---

### P1.1 — Answer nodes, derived from decisions

This is the element §5 names first and it is the one that breaks in the most places. Six rivals; five
hold.

**Rival (a) — the edge is sign-inverted, and it recreates the line it claims to reframe.**
Measured on Cycle 1: all three refusals were refusals of `close_node`.

```
refusal -> close_node | target_id: 'x1.2' | words: 'no - a refuted rival is not the same as a wrong one; leave it open'
refusal -> close_node | target_id: 'x1.3' | words: 'not this cycle'
refusal -> close_node | target_id: 'a1.1' | words: 'not this cycle'
```

Under P1.1 these become `blocks u→x1.2`, `blocks u→x1.3`, `blocks u→a1.1`. But the user did not
block `a1.1` — the user refused *closing* `a1.1` and said "leave it open". The refusal **protects**
the target. The rendered edge says the opposite. That is L24/O116 ("the next cycle reads every
refusal as 'never'") in a new form, and L24 is the line P1.1 claims to reframe. A refusal blocks the
**proposal**, not the proposal's target; the edge needs to hang off something that represents the
write.

**Rival (b) — one answer in four has no target at all.** Measured: the one approval-with-words on
the live run was `propose_fact`, and `_target_of` (`hooks.py:107-115`) has no key that
`propose_fact` supplies (`quote`, `because`, `supports`):

```
approval -> propose_fact | target_id: '' | words: 'yes, that is where it lives'
```

So the single most authority-laden surface in the system — E7, "a fact isn't a fact until it is
explicitly registered via a user" — produces an answer node whose `permits` edge points at nothing.

**Rival (c) — `target_id` is frequently not a node id.** Ran `_target_of` over each gated tool's
real argument shape:

| tool | `target_id` |
|---|---|
| `propose_fact` | `''` |
| `close_node` | `'x1.2'` ✔ |
| `add_edge` | `'n1.1'` (the **src**; the refusal was about the edge) |
| `compress` | `'a1.1, a1.2, a1.3'` (a comma-joined string) |
| `merge` | `'n1.2'` (the merge's **target**, not its source — `_TARGET_KEYS` puts `target` first) |
| `supersede` | `'a1.1'` ✔ |
| `move_evidence` | `'f1.2'` ✔ |

`thought.apply` is tolerant of a missing end, so a `blocks` edge to `'a1.1, a1.2, a1.3'` would be
silently dropped and the answer would render with no edge and no error.

**Rival (d) — "closable with `close_node`, supersedable with `supersede`; no new status" is false
against the code.** I built an `answer`-kind node in a real view and called the real handlers:

```
close_node(u1.1, refuted)   -> REFUSED: u1.1 is a answer, not claim or entity.   (tools.py:469)
supersede(u1.1 -> u1.2)     -> REFUSED: u1.1 is a answer, not claim.             (tools.py:489)
after apply(Supersession):  u1.2 role -> 'assumption'                            (thought.py:416)
```

So both tools refuse the kind, and if `supersede` were widened, `thought.apply(Supersession)` sets
`g.nodes[record.new]["role"] = "assumption"` — superseding one answer with another **turns the
winner into an assumption**. P1.1's file list is `vocabulary.py`, `thought.py`, `package.py:183-192`,
briefs. `harness/tools.py` is not in it.

**Rival (e) — the node is invisible to the graph's own machinery.** Measured on a hand-built answer
node: `live_ids()` excludes it (`thought.py:85` selects `CLAIM, ENTITY, FACT`), so no alteration can
target it and `synthesis`'s `finding_target` resolver rejects it. `_WALKABLE` excludes it
(`thought.py:204`), so `neighbourhood` never reaches it and `package.render` does not mention it.
Both are extra file-list entries.

**Rival (f) — there is no date.** P1.1's test requires the ANSWERS section to quote the words *"with
cycle and date"*. Measured: `encode` (`store.py:206-208`) writes `{"kind", "session", "at", "data"}`
and `decode` (`store.py:211-222`) returns `model.model_validate(obj["data"])` — **`session` and `at`
are discarded at load**. `Decision` and `ProposedWrite` carry no timestamp of their own. The date
does not exist anywhere the renderer can reach it.

**Rival (g) — unbounded, unlike every other block.** `ledger.refused()` is across every cycle
(`store.py:185-187`), and P1.1's ANSWERS block adds approvals-with-words on top. `render` bounds
every other block by `neighbourhood` (`package.py:96`, used at 107, 111, 122, 174). ANSWERS has no
bound. On the live run that is 4 answers per cycle; the branch doc's own worry about a "wall of
re-confirmation" (E58) starts here, not at P4.1.

**Verdict: RIVAL HOLDS.** The *decision* — D11, a user answer is a node — is right, well rooted, and
fixes a real asymmetry (O-B1: the same sentence from the same person becomes a node or a string
depending on which surface it was said at). What breaks is **the derivation**. A `Decision` plus a
`ProposedWrite` does not carry a node-shaped target, a sign, or a time, and three of those four are
in hand at `hooks.py:150-198` where the gate runs. **R1.1 is the cheaper path, not the deferred
one.** An `Answer` record written at the gate can carry `target` (resolved, or empty and honest),
`verdict`, `write`, `question` (Q-B6), `at` and `session`, and needs no reverse-engineering of
`_TARGET_KEYS`. Then widen `close_node`, `supersede`, `live_ids` and `_WALKABLE`, and fix the
`Supersession` role mutation, and say so in the file list.

---

### P1.2 — What was tried and stopped, as a ledger line

**Rival in full.** The two sources the element names cannot produce two of its four reason classes,
and the one place the fourth could come from is not in the file list.

**What I did.**
- `reason_class=surface`: `hooks.py:65` appends `f"{name}: not in surface"` to `turn.meter.refused`. ✔
- `reason_class=budget`: `meter.py:103` appends `f"{tool_name}: {pool} exhausted"`. ✔
- `reason_class=handler`: the dry-run refusal at `hooks.py:147-148` emits a `Refused` **event** and
  returns `PermissionResultDeny`. It never touches `turn.meter.refused`. **No source.**
- `reason_class=aborted`: on an interrupt `sdk.py:199` raises `FrameInterrupted(result)`, and
  `graph_driver.py:116-117` catches it and emits a Notice. The frame node never returns, so its
  `ctx.store.append(...)` never runs. This is exactly O87 as measured: *"Ledger delta after the
  abort: 0 lines, 0 proposals, 0 decisions."* **Unreachable from the frames.** The change would have
  to go in `graph_driver.py`, which the file list omits.
- `tool_call_id`: `meter.refused` is `list[str]` with no call id (`meter.py:84,93,103`). The Meter
  must change; not named.
- The carry: `Attempts.absorb` (`_common.py:52-58`) extends `spend`, `findings`, `ops` and
  `relation_kinds` and **drops `result.refused`**. So even the two working classes do not reach the
  append today. `_common.py` is not in the file list.

And the larger point: appending an aborted proposal **answers Q-P9** ("is the log the trail of
everything attempted or everything committed?") in favour of *attempted*. The branch-decisions doc
lists Q-P9 as open, as gating L1's fix, and — in its own words — as *"now more consequential: if
answers are nodes and nodes are promotable, what the log holds determines what can be promoted."*
The plan decides it in one clause of one element.

**Verdict: RIVAL HOLDS.** L27 and A19 are real and the element is worth having. As specified it can
deliver `surface` and `budget` only; `handler` needs the gate to record, and `aborted` needs Q-P9
answered and a change in `graph_driver.py`. Split it: ship surface+budget now, and put `aborted`
behind Q-P9 with the question stated to the user.

---

### P2.1 — A reference on every priced read

**Rival in full.** The plan frames the scope as turn vs cycle and asks the antithesis pass to weigh
it. Both are wrong, and the boundary that actually bites is neither: it is the **re-author attempt**
inside one frame.

**What I did.** `TurnContext` — which holds `records` and would hold `references` — is constructed
fresh on every `harness.run` call: `sdk.py:118` and `scripted.py:81`. Orientate calls
`ctx.harness.run` once per attempt inside its re-author loop (`orientate.py:112-135`) while carrying
`prior_spend=tuple(ledger.spend) + tuple(attempts.spend)` forward (`orientate.py:125`). So **a
re-author keeps the spend and loses the records**. Under the turn-scoped default, the re-author that
P2.5 triggers destroys exactly the references P2.3 needs to satisfy P2.5.

Measured on the live run: all three assumptions have `grounded_in=''` and `evidence=()`, so P2.5
would re-author all three, and orientate had spent **19 of 20 points**, so on the retry a `Read`
(cost 2) is refused with `BUDGET_EXHAUSTED`. The retry runs on the same conversation
(`conversation=conversation` after attempt 0), so the model can *see* its reads in context and
cannot cite them.

Counter-evidence that **supports** turn scope across frames, which the plan does not cite: the
antithesis brief orders the re-read explicitly (`nodes/antithesis.py:52-54`):

> RE-READ WHAT YOU ALREADY READ. The findings you kept are quotable by anyone; *which* excerpts you
> kept was a decision made inside the frame you are now attacking. **Part of this budget is funded
> for that and nothing else.**

E27a is the root: *"an agent cannot think they are right and wrong in the same task."* Cycle-scoped
references would let antithesis cite the frame it is attacking without the re-read the design funds,
which weakens the one part the audit found working (O114).

Second, smaller rival: `post_tool_use` (`hooks.py:90-103`) reads only `tool_response`. To record a
path it must read `tool_input`. That field is in the PostToolUse payload, but nothing here exercises
it, and the scripted harness bypasses the hook path entirely (`scripted.py:135` calls `turn.record`
directly), so a scripted test will not catch a wrong key.

**Verdict: RIVAL HOLDS, and the plan's binary is the wrong question.** The right scope is **the
frame's attempts**: carry the references on `Attempts` (`_common.py:34-58`) alongside `findings` and
`spend`, and keep the frame boundary hard. That refutes R2.1's "makes the model re-read what it is
looking at" for the case that matters (a retry) while preserving the re-read antithesis is funded
for. Q-B1 as posed is a false choice.

---

### P2.2 — `Finding` carries its citation

**Rival in full.** `Finding` already has two fields for exactly this tie, both dead, and the element
adds a nested record beside them without saying that a nested record is a checkpoint decision.

**What I did.** `state.py:162-163`: `tool_call_id: str = ""` and `price: int = Field(ge=0,
description="What the call that produced this cost.")`. Measured on all five Cycle 1 findings:
`tool_call_id=''`, `price=0`, every one — because `attach_finding` hard-codes them
(`tools.py:176-184`). Note that the branch-decisions D7 note says these *"are filled today by the
tool running its own command"* — that claim is false, though the plan does not repeat it.

`RECORD_TYPES` (`state.py:456`) is the checkpoint allowlist, and its own docstring says *"adding a
type to the checkpoint is a decision."* `unlisted_record_types()` is checked by
`graph/graph.py:104`, so a `Reference` defined in `state.py` and not listed trips the compiled-graph
guard.

The "changed since read" render (comparing `version` with the file now) is genuinely new, well
rooted in H4, and is the part of the element with no substitute.

**Verdict: RIVAL PARTLY HOLDS.** Keep the staleness render. Fill `tool_call_id` and `price` from the
reference rather than leaving two fields dead beside a new nested record, and say in the element that
`Reference` joins `RECORD_TYPES`. Smaller and it removes an inconsistency the code already carries.

---

### P2.3 — `store_evidence`

**Rival in full.** The buffer the element slices is not what `lines=` promises.

**What I did.** Traced `turn.record`. It is called from **two** places for the same `tool_use_id` in
the live path: `hooks.py:93` (`post_tool_use`) and `sdk.py:147` (the stream's `ToolResultBlock`).
`turn.record` concatenates rather than replaces (`turn.py:126-129`):

```python
prior = self.records.get(tool_use_id)
self.records[tool_use_id] = text if prior is None else prior + "\n" + text
```

Measured: a three-line file result becomes a seven-line record holding the result twice, with the
CLI's `NNN→` line prefixes intact (`normalise` strips those only for the *comparison*,
`turn.py:26-31`). So `lines="10-20"` over `turn.records[call_id]` means "lines 10–20 of a doubled,
prefixed buffer", not lines 10–20 of the file, and a `match=` slice can return two copies. The
scripted harness records once (`scripted.py:135`), so the element's scripted test passes while the
live behaviour differs — the same blind spot as P2.1.

**Claims that hold.** `source_of` (`turn.py:131-139`) is called by nothing in `src/`, `tests/` or
`scripts/` — grep confirms. ✔ One nuance: the `Finding` docstring's promise is not *unenforced*
today, it is satisfied by construction — `attach_finding` runs the command itself, so the excerpt is
the executor's output. What is new is enforcement for excerpts the model **types**, which is the real
gain. "Enforced for the first time" slightly overstates it.

**Two mechanical notes.** `graph_write_price = 0` (`config.py:85`), so adding `store_evidence` to
`ALTERATION_TOOLS` makes it free automatically. Putting it in `FINDING_TOOLS` instead gives it
`attach_finding`'s per-turn cap for free, which is what D9 asks for. The element says "same per-turn
cap" but does not say which set.

**Verdict: RIVAL HOLDS on the mechanism.** The element is the right shape and the best-rooted new
tool in the plan (D1–D9 map onto it almost line for line). Either record each result once, keyed and
un-prefixed, or say plainly in the tool description that `lines` means lines of the recorded result.
Do not ship it with a scripted-only test.

---

### P2.4 — `attach_finding` stays

**Rival in full.** The element is right and one sentence too small. It frames `attach_finding` as
the case "where the frame has nothing recorded to cite (pool spent, or a file not yet read)" and
demotes it in the brief to "when you have not read it yet."

**What I did.** Two places where it is not the fallback but the only thing that works: (1) a
re-author attempt, where `turn.records` is empty by construction (`sdk.py:118`) and the pool may be
spent (measured: 1 point of 20 left on the live run); (2) antithesis, where the brief explicitly
funds the re-read (`antithesis.py:52-54`) and all five Cycle 1 findings came through
`attach_finding`, not through anything else.

**Verdict: RIVAL REFUTED on the element (Q-B4 is answered right), but the brief change is wrong.**
"When you have not read it yet" tells the model the wrong thing in the frame that produced 5 of the
cycle's 5 findings. Demote it in orientate's brief only.

---

### P2.5 — An assumption must cite its ground

**Rival in full.** Four parts.

**(a) It checks emptiness, not validity.** `grounded_in` is never resolved. `thought.apply` silently
drops it when it is not a node: `if record.grounded_in and record.grounded_in in g:`
(`thought.py:335`). Orientate copies it straight through from the payload with no check
(`orientate.py:154`). So "empty `grounded_in`" is satisfied by typing any sentence into the field,
and the model's cheapest compliance is exactly that. The check must resolve against
`thought.live_ids` (and, with P1.1, answers). `node_ids` is already passed on every `StageRequest`
(`orientate.py:127`, `antithesis.py:122`, `synthesis.py:160`) and — I checked — **read by nothing**;
it is the field this check should use.

**(b) The locator is wrong.** The element names `graph/payloads.py:35`. Line 35 is `moved_by`'s
description (*"The specific call whose result would change your belief about this claim"*).
`grounded_in`'s description is line 30.

**(c) Measured consequence.** On the one live cycle all three assumptions have `grounded_in=''` and
`evidence=()`, so all three re-author; orientate had 1 point of 20 left, so a `Read` is refused; and
under P2.1's turn-scope the retry has no records either. The escape is `attach_finding`, which is
free and re-runs the command. So P2.5's practical effect on the observed run is **"make orientate
run its reads twice"**, not "make orientate keep what it read" — and re-running reads is what the
plan's own R2.1 objects to.

**(d) It shares a hard-failure path.** `max_reauthor_attempts = 2` (`config.py:82`), so three
failures raise `OrientationFailed` (`orientate.py:144`). Nothing in `graph_driver._run` catches it
(`graph_driver.py:108-120` catches `FrameInterrupted` and `HarnessUnavailable` only); it reaches the
shell's outer `except Exception` (`runner.py:95`) and the cycle is lost. Today that path fires only
on a count violation, which is trivially satisfiable. P2.5 adds a second, semantically much harder
trigger to the same hard failure — against E58 ("smooth … not interrupt workflow") and against
O118's already-140-second time to first word.

**Verdict: RIVAL HOLDS.** The pressure is the plan's best-rooted idea (L19 is the audit's strongest
finding, and the plan is right that P2.3 without P2.5 is voluntary). But as specified it is a
paraphrase check with a cycle-killing tail. Three changes: resolve the id against `node_ids`; fix the
locator; and give it a **soft** correction path (a brief line plus one re-ask) rather than sharing
`OrientationFailed` with the count.

---

### P2.6 — A breadth check, provisional

**Rival in full.** It would have fired zero times on the one case it cites as its root, and it
rewards the behaviour its roots forbid.

**What I did.** Read the three Cycle 1 assumptions' `moved_by` fields:

```
a1.1  "Reading SdkHarness.options() to see if the allow-list is dynamic per call or set once per frame"
a1.2  "Reading ClaudeAgentOptions documentation to confirm that tools= is a hard boundary and …"
a1.3  "Reading meter.py:78-100 to understand the full decision tree and whether it also enforces …"
```

Measured: **no two are identical** (all three pairwise comparisons false). O113's finding was that
the three assumptions were *one topic* — the surface list, the hook, the meter, three views of one
mechanism — which is a semantic relation that exact string equality on a free-text field cannot see.
`moved_by` is `str = Field(min_length=1, …)` (`state.py:117`) and its schema description asks for a
sentence, not a structured call (`payloads.py:33-36`).

Worse than useless: a de-duplication rule over model-authored free text teaches the model that
rewording passes the gate. That is the opposite of E18 (*"we want assumptions to be avenues
available for information to stick"*) and of E51.

**Verdict: RIVAL HOLDS — drop the element, do not build it provisionally.** The plan's §3 already
puts similarity out of scope; this stand-in does not approximate what it stands in for, adds a third
re-author trigger to a frame that already has two, and points the incentive the wrong way. L29 stays
open, which is the honest record. If something must be built, count **distinct files named across
the assumptions' `moved_by`** — cheap, mechanical, and it would have fired on the live case.

---

### P3.1 — `/handoff`

**Rival in full.** The element is smaller than it is described as, because half of it exists.

**What I did.** `/show package` is already a built-in (`commands.py` `BUILTINS["show"]`,
`runner.py:457-475`) and calls `driver.package_text(state)` → `package.render(...)`. So `/handoff`
is "the existing renderer, uncapped, written to a file". The element does say "a full renderer beside
the capped one", so the code claim is honest; the framing is not.

Second rival, checked and not a conflict: the file lands under `<state_dir>/handoff/`, which is the
directory P0.2 fences frames out of. The working session is not a frame, and chat mode uses
`chat_gate` (`hooks.py:206-242`), not `pre_tool_use`, so no fence applies. But R3.1 ("chat mode
receives it automatically") would need an exception if the fence ever covers chat, and that is worth
one sentence.

Everything else holds: E12, E59, O117, L21, Q-P13 answered by a third option, and the branch doc's
*"the cheapest way to find out whether the content is even useful before promotion machinery is worth
building."*

**Verdict: RIVAL REFUTED on the element, HOLDS on its size.** Build it. Say it reuses `/show
package`'s renderer, and note the fence interaction for R3.1.

---

### P3.2 — Synthesis proposes one change at a time and closes on ground

**Rival in full.** The check as worded passes the exact call the element exists to refuse.

**What I did.** The element says `close_node`'s dry run should refuse *"a `because` that names no
finding, fact or answer id"*, and its test uses `because="its rival is confirmed"` — no id at all.
But the call that actually happened on the live run was:

```
p1.5  close_node a1.1 refuted   because = "because its rival x1.1 is confirmed"
```

`x1.1` **is** a live node id. An "names an id" check passes it. The element's own quoted refusal
reason — *"a rival being confirmed is not ground for refuting the assumption; cite what shows it"* —
requires knowing the **kind** of the named node, not merely that one is named. So the check must be:
the `because` must name a live node of kind `evidence` or `fact` (or, with P1.1, `answer`), and must
not rest on a `claim`. The element's substance says "finding, fact or answer id", which is right; the
wording and the test are the weak form.

The brief half is sound. O115 and O79 are real (three closes in one message, the words on the first
reaching neither of the others), and A27 is fairly settled in favour of "brief plus check" —
the check catches what the brief misses. `graph/nodes/synthesis.py:36-95` is the right locator
(verified: the brief's "changes you can put to the user" list and the "discussion first" numbering
are in that range).

**Verdict: RIVAL HOLDS on the check's strength; element otherwise stands.** Rewrite the test to use
p1.5's real `because` — that is the case with evidence behind it.

---

### P4.1 — Origin-aware package

§5 asks whether the shared op log can stand in for the project graph. Five rivals; four hold.

**Rival (a) — "Every record already carries `session`" is false, and the element is not a renderer
change.** Measured. `encode` (`store.py:206-208`) writes `{"kind", "session", "at", "data"}` into
each line. `decode` (`store.py:211-222`) returns `model.model_validate(obj["data"])` — **the
envelope's `session` and `at` are thrown away.** Only `Cycle` has a `session` field of its own
(`state.py:49`). `Ledger` (`store.py:101-123`) has no field for either. So P4.1's file list
(`graph/package.py:124-192`, briefs) is wrong: the store's decode path and the `Ledger` shape both
have to change, and that is the load-bearing part of the element.

**Rival (b) — the one derivation available is wrong for forks.** `cycle → ledger.cycles[cycle].session`
looks sound, but `/fork` (`runner.py:486-509`) creates a **new** session record and seeds the same
`cycle` and `stage` into the new thread. So a fork's synthesis records are written under the fork's
session id into a cycle stamped with the source's. L17 already records that a fork shares the
conversation id; this adds that it would share the origin label, which is exactly the thing PRIOR
SESSIONS is supposed to distinguish.

**Rival (c) — the re-ask it prescribes is refused by the tool it names.** The brief says *"before
relying on one, put it to the user in this session … as `propose_fact` or `close_node`."* Measured:

```
propose_fact("the retry limit is three")  -> REFUSED: that quote is not a verbatim span of
                                             anything the user said this cycle. …
propose_fact("q?")                        -> Registered e1.1
```

`propose_fact` checks `turn.request.said` (`tools.py:300-305`), and `said` is this session's
messages (`orientate.py:128`, `synthesis.py:159`; the `operator.add` reducer accumulates within a
thread and never across threads). A prior session's sentence is refused by construction. And
`close_node` on a prior session's **answer** is refused by kind (see P1.1(d)). So **D14's "is this
still true" has no working tool on either path.** This is the single most consequential gap in the
element.

**Rival (d) — it builds the wall the branch doc identified.** The branch doc, on D14:

> *"If every promoted answer raises 'is this still true', a session opening on a mature project meets
> a wall of re-confirmation, which is exactly the workflow interruption E58 rules out. Something has
> to decide which prior answers bear on **this** task. That is similarity over accumulated answers…"*

P4.1 renders **every** prior-session fact, closed claim and answer under PRIOR SESSIONS with no
selection, and the plan's §3 puts similarity out of scope. Every other block in `render` is bounded
by `neighbourhood` (`package.py:96`, used at 107, 111, 122, 174); PRIOR SESSIONS and ANSWERS are the
only two that are not. So the element defers the only mechanism identified as taking the wall down
and builds the wall first.

**Rival (e) — on §5's question directly.** For D13/D14/D16 the op log is a faithful rehearsal: prior
material is in one store, it is distinguishable in principle, and a local override is just an answer
in this session. For **D15** it cannot stand in at all — the parent graph *"holds all of the graph
information concerning the goals of the overall project and the implementations"*, and the op log
holds one project's episodes and no goals. The plan's §0 sentence ("the shared op log across sessions
standing in for the project graph") overstates what P4.1 delivers. P5.1 is honest about this (the
task text comes from the user's own task folder), so the two sections disagree.

**Verdict: RIVAL HOLDS.** Direction right, costing wrong. The element is a week, not a renderer
change: decode must preserve `session` and `at`, `Ledger` must hold them, `propose_fact` needs a
path for "the user assented to a prior answer this cycle", and PRIOR SESSIONS needs a bound.

---

### P4.2 — The promotion slot, dormant

**Rival in full.** The plan states R4.2 itself ("do not build a dormant tool") and asks the
antithesis pass to weigh it. It holds, for a reason the plan does not give.

**What I did.** Costed "dormant". A `Promoted` record needs an entry in `store.KINDS`
(`store.py:70-92`), a decision about `OPERATIONS`, and an entry in `RECORD_TYPES` (`state.py:456`) or
`unlisted_record_types()` trips the compiled-graph guard (`graph/graph.py:104`). A gated `promote`
tool needs entries in `GATED_TOOLS` (`surface.py:47`) and `STAGE_GRAPH_TOOLS['synthesis']`, a handler
in `tools.py`, registration in `tools_for`/`handler_for`, and a price class (`meter.call_class`
routes `ALTERATION_TOOLS` to `graph_write`, currently 0). That is five registrations and a test for a
tool whose only behaviour is to refuse — and all five get revisited when a parent exists and the
real shape is known.

**And the real gap is elsewhere.** H5 says *"Every record needs a stable id, a time and a provenance
pointer, so it can be cited from outside. **Nearly true today.**"* The part that is not true is the
**time** — and P4.1(a) shows why: `at` is written to the log and discarded at decode
(`store.py:211-222`). A promoted node that cannot say *when* it was concluded is not citable from
outside, which is the whole of H5's purpose.

**Verdict: RIVAL HOLDS — drop P4.2 and do the decode fix instead.** Preserving `session` and `at`
through `decode` into the `Ledger` is half a day, serves H5, P4.1 and P1.1's "cycle and date" at
once, adds no surface the model can call and be refused by, and leaves the promotion tool to be
designed against a real parent.

---

### P4.3 — The read-down slot

**Rival in full.** An enum value with no consumer is not an element. The element's own text is *"No
code beyond the enum value"*, and that value is already inside P2.1's `Reference(source_kind ∈ {file,
git, web, graph})`.

**Verdict: RIVAL HOLDS, mildly.** H4 genuinely wants the field (*"a chain of derived summaries should
not be indistinguishable from a direct read"*), and P2.1 already provides it. Listing it as a
separate element inflates the plan's apparent scope and suggests the read-down seam exists as a slot
when it is one word in an enum. Fold it into P2.1 as a sentence.

---

### P5.1 — One task-shaped live run, then decide the role split

**Rival in full.** The element is numbered last and scheduled second, and the plan builds Stages 1–4
on top of the gap this element exists to close.

**What I did.** The element's own text says *"After Stage 0, one Haiku cycle against `Harness/`."* The
plan numbers it P5.1, after P4.3. O112 is unambiguous: *"the build has never been run on a
task-shaped request … Whether E2 and E48 separate on a task-shaped request is untested: both live
runs asked questions."* The branch-decisions doc, on branch 3: *"This is the branch being redesigned
furthest from any data, and it is the exact failure mode this project exists to prevent. **Nothing
here should be built before one task-shaped live run.**"*

P1.1's answer nodes, P4.1's PRIOR SESSIONS and P2.5's grounding rule are all shaped by the one
question-shaped run (Cycle 1), and all sit in branch `session-graph`, before P5.1. So the plan
repeats, at its own scale, the failure E51 names.

**And a second unmeasured premise the plan carries.** The branch doc's risk item 7 names **A8**:
*"A8 tests directly whether kept evidence survives into the next cycle, **which is the premise of
branch 1**."* A8 is still open (Cycle 1: *"carried, not measured"*). P2.3 and P2.5 are branch 1's
successors and the plan schedules A8 nowhere.

**Verdict: RIVAL HOLDS on the order.** P5.1 and A8 belong immediately after Stage 0 and before P1.1 —
which is what the element's own sentence says and what the plan's stage numbering contradicts. Cost
by Cycle 1's measure: about $0.50 and four minutes of wall clock, against a week of build that
assumes the answer.

---

## Conflicts between elements

1. **P2.5 destroys what P2.3 needs, through P2.1.** P2.5 triggers a re-author; a re-author is a new
   `harness.run` call with a fresh `TurnContext` (`sdk.py:118`, `orientate.py:112-135`), so the
   turn's `records` and `references` are empty while the spend carries forward
   (`orientate.py:125`). Under P2.1's turn-scoped default the retry can neither cite what it read
   nor afford to read again (measured: 1 of 20 points left on the live run). The only escape is
   `attach_finding`, which re-runs the command — the behaviour R2.1 objects to. **Fix: scope
   references to the frame's attempts, on `Attempts` (`_common.py`).**

2. **P1.1 and P4.1 both need what neither element budgets for.** Both need `session` and `at`
   preserved through `decode` into the `Ledger` (`store.py:211-222`). P1.1 assumes the date exists;
   P4.1 asserts the session already does. Neither is true. One shared prerequisite, listed in
   neither.

3. **P1.1's re-ask and P4.1's re-ask are blocked by different tools.** P4.1 prescribes
   `propose_fact` for the re-ask; it refuses anything not said this cycle (`tools.py:300-305`). P1.1
   prescribes `close_node`/`supersede` on answers; both refuse the kind (`tools.py:469,489`). So the
   two elements each assume the other's surface works.

4. **P0.3 and Stages 1–4 both own the system prompt.** P0.3 rewrites it in Stage 0 to describe three
   frames and "assumption"; P1.1 adds `answer` nodes, P2.3 adds `store_evidence`, P2.5 adds a
   grounding rule, P4.1 adds PRIOR SESSIONS. Writing it twice is the larger cost.

5. **P0.4 and P1.1/P4.1 collide in `package.py`.** The branch split (§4) merges `install-shape`
   (P0.1–P0.4) first and `session-graph` (P1.1–P4.3) second, and both edit the renderer — P0.4 at
   `_quote`/`_evidence_lines`, P1.1 at the refused block (183-192), P4.1 at 124-192. Sequenceable,
   but the split is not as clean as "infrastructure, no change of shape" claims.

6. **P0.2's fence and P3.1's output directory.** `/handoff` writes to `<state_dir>/handoff/`, which
   P0.2 makes unreadable from a frame. No conflict today (the working session and chat mode do not
   go through `pre_tool_use`), but R3.1 as written would need an exception.

7. **P2.5 and P2.6 both add a re-author trigger to a frame that already hard-fails after three
   attempts** (`config.py:82`, `orientate.py:144`), and `OrientationFailed` is caught only by the
   shell's outer handler (`runner.py:95`). Three triggers, one cliff, against E58.

---

## False claims about the code

| # | Claim | Where | What is true |
|---|---|---|---|
| 1 | *"Every record already carries `session`."* | P4.1 | `encode` writes it to the line envelope; `decode` (`store.py:220`) discards it. Only `Cycle` has a `session` field (`state.py:49`). `Ledger` has no field for it. Measured. |
| 2 | An answer node is *"closable later with `close_node`, supersedable with `supersede`."* | P1.1 | Both refuse a non-claim kind (`tools.py:469,489`). Measured: `REFUSED: u1.1 is a answer, not claim or entity`. And `thought.apply(Supersession)` sets the winner's role to `"assumption"` (`thought.py:416`). |
| 3 | P1.1's test requires the ANSWERS block to show *"cycle and date"*. | P1.1 | No date exists in the ledger. `Decision`/`ProposedWrite` have no timestamp; the envelope's `at` is discarded at decode. Measured. |
| 4 | `/show node <finding>` renders it whole once `package.py:41-43,57,244` and `runner.py` change. | P0.4 | The cut is in `thought.label` (`thought.py:519-520`, 89 chars), not in `package._quote` (240). Measured: 470-char `f1.2` → 245 chars total, excerpt not whole. |
| 5 | P4.1 is *"no code change beyond the package renderer"* (implied by its file list). | P4.1 | Requires `store.decode` and the `Ledger` shape to change. |
| 6 | `Blocked` is *"appended by the frames from `turn.meter.refused` and from an interrupted turn's pending proposal."* | P1.2 | `meter.refused` is `list[str]` with no call id and no handler refusals (`meter.py:84,93,103`; `hooks.py:147`). `Attempts.absorb` drops `result.refused` (`_common.py:52-58`). An interrupted turn's frame never appends — `graph_driver.py:116-117` catches and continues (O87: 0 lines). |
| 7 | P2.5's locator `graph/payloads.py:35`. | P2.5 | Line 35 is `moved_by`'s description; `grounded_in`'s is line 30. |
| 8 | `AppConfig` *"gains … `state_dir`"*. | P0.1 | `sessions_dir` already exists as an independent field (`config.py:365`), used in 7 places. This is a rename. |
| 9 | *"`Finding` gains optional `source`"* with no mention of the allowlist. | P2.2 | `RECORD_TYPES` (`state.py:456`) is guarded by `unlisted_record_types()` at `graph/graph.py:104`; the docstring calls adding a type "a decision". Same for `Blocked` (P1.2) and `Promoted` (P4.2). |
| 10 | *"`store_evidence` … slices the recorded result of that call (`turn.records`)"* as if `lines` means file lines. | P2.3 | `turn.records[call_id]` holds each result **twice** (`hooks.py:93` + `sdk.py:147`, concatenated by `turn.py:126-129`) with CLI line prefixes. Measured. |

**Claims that check out and are worth recording as refuted rivals:** `source_of` is genuinely called
by nothing (grep across `src/`, `tests/`, `scripts/`). `Finding.excerpt` is genuinely stored whole at
80 lines / 6 KB (`evidence.py:41-42`). The system prompt genuinely still says "four frames",
"assume (", "readings" and "excerpt copied". `config.py:363-381`, `package.py:41-43,57,183-192`,
`state.py:145`, `orientate.py:112-146`, `synthesis.py:36-95` are all correct locators. Structural
edges genuinely cannot be added by name (`vocabulary.py:113-116`), so P1.1's `blocks`/`permits` in
`STRUCTURAL` is right.

---

## User words contradicted or ignored

| # | Word | How |
|---|---|---|
| 1 | **D14** — *"A promoted answer is raised back to the user as a question — 'is this still true'"* | P4.1 prescribes `propose_fact` and `close_node` for the re-ask. Measured: `propose_fact` refuses any quote not said this cycle (`tools.py:300-305`); `close_node` refuses an answer's kind. **Neither tool can perform D14.** |
| 2 | **E58** — *"smooth and versitile enought to not interrupt workflwo"* | P4.1 renders every prior-session fact, closed claim and answer with no selection — the wall the branch doc identified for exactly this reason — while §3 defers the only named remedy. P2.5 and P2.6 add two re-author triggers to a frame already at ~140 s to first word (O118), sharing a cliff that loses the cycle (`orientate.py:144` → `runner.py:95`). |
| 3 | **E65** — *"one branch per distinct shape"* | The `session-graph` branch (§4) carries P1.1 (answers), P2.1–P2.6 (cited evidence), P3.1–P3.2 (the hand-off), P4.1 (origin), P4.2 (promotion) and P4.3. The branch doc treats `answer-nodes`, `store_evidence`, `cite-or-retry` and `package-handoff` as **four** separate shapes, and says of two of them that they are *"mutually decisive"* — which only works if they are separable. One branch makes the comparison impossible. |
| 4 | **E54** — *"Survey your surroundings, orientate and disprove your own assumptions as you go"* / **O112** | Stages 1–4 are designed on one question-shaped run and scheduled ahead of the task-shaped run (P5.1) that the branch doc says must come first. **A8**, named there as *"the premise of branch 1"*, is scheduled nowhere. |
| 5 | **Q-P9** — the user's open question, unanswered | P1.2 answers it as "attempted" in one clause, for machine refusals and aborted proposals, while L1 (which Q-P9 gates) stays unfixed. The branch doc says the question is *"now more consequential: if answers are nodes and nodes are promotable, what the log holds determines what can be promoted."* |
| 6 | **D15** — *"the parent graph holds the project's goals and implementations"* | §0 says the shared op log stands in for the project graph. It holds one project's episodes and no goals, so it cannot stand in for D15. P5.1 is honest about this; §0 is not. The two disagree. |
| 7 | **E18** — *"assumptions to be avenues available for information to stick"* | P2.6's exact-match rule on a free-text field rewards paraphrase, which is the opposite incentive. P2.5's emptiness check does the same on `grounded_in`. |
| 8 | **E33** — *"Every number … must be marked as unset"* | §4 asserts it, but **L6** ("provisional numbers are disclosed only by `/budget`; the provisional price class nowhere") is a ledger line the plan neither closes nor lists. E33's marking is not optional. |

**Not contradicted, worth recording:** E63 (the graph panel) is correctly out of scope. E34 (fact
extraction) is correctly out of scope. E31/L31 (cost accounting) is correctly backlogged at the
user's word. E61 (Haiku only) is honoured by P5.1. E28 (message and approval are different surfaces)
is honoured by R3.1's deferral.

---

## Ledger lines the plan forgets

The plan's source line says "ledger L1–L32". Checked line by line.

**Closed or named:** L8, L10 (P0.1) · L15, L24, O-B1 (P1.1) · L18, L19 (P2.3+P2.5) · L21 (P3.1) ·
L23 model side (P3.2) · L25 (P0.4) · L26 (P0.3) · L27, A19 (P1.2) · L28 part (P0.2) · L29
provisionally (P2.6) · L31 backlogged at the user's word · L22, L30 are ✔ lines · O106 (P4.1).

**Forgotten — no element, no §3 entry, no mention:**

| # | Line | Why it matters here |
|---|---|---|
| **L9** | The CLI keys conversations by the cwd string; a session moved across mounts cannot resume its cycle | The audit's own install-shape proposal had **P-19b** for this. The plan takes P-19a and P-19c and drops P-19b. Under the E59 shape the audit lists *three* mount strings for one Harness repo, so this gets worse, not better, with P0.1. **A13** goes with it. |
| **L1** | Ghost cycle: a crash after a frame's append and before the checkpoint leaves a cycle the next run duplicates | The branch doc's "Tier 2 core fixes" list names it, and P1.2 touches the very question that gates it (Q-P9) without fixing it. |
| **L2** | A frame that fails every re-author attempt refunds the points it spent | **P2.5 makes this reachable.** It adds a new re-author trigger to the frame; on total failure the spend is refunded, so a frame can burn 19 points, fail P2.5 three times, and hand the points back. Named in the branch doc's Tier 2; absent from the plan. |
| **L4** | A schema mismatch is corrected as a wrong count | Directly adjacent to P2.5, which adds a second correction to the same loop; a correction that names the wrong problem is what L4 is. |
| **L16** | Forking a thread interrupted in its first frame skips the owed frame and runs antithesis on cycle 0 | Named in the branch doc's Tier 2. Also bears on P4.1(b), since a fork is where the session/cycle attribution breaks. |
| **L17** | A fork shares the chat conversation id with its source | Bears directly on P4.1's session partition. |
| **L20** | Zero entities, zero claims | The branch doc calls it *"reframed, not fixed … a staging-area question; nothing yet makes it fill, and branch 1 no longer tries."* The plan does not name it even in §3, and P5.1's "whether it names anything worth promoting" depends on it. |
| **L32** | The frame-finished line can be computed from the checkpoint before the frame | Named in the branch doc's Tier 2 list; absent from the plan. |
| **L6** | Provisional numbers disclosed only by `/budget`; the provisional price class nowhere | §4 asserts E33 compliance for *new* numbers while the existing breach stands. |
| **L5** | Executor argument fencing | The user ruled security probing out; but L5 also has a product face (a model's relative path silently escaping the fence is a wrong-answer risk, not only a safety one). Worth a line saying it is parked at the user's word, as L31 is. |

**Assumptions the branch doc flagged and the plan schedules nowhere:** **A8** (does kept evidence
survive into the next cycle — *"the premise of branch 1"*), **A13** (mount mismatch), **A21**, **A22**.

---

## Choices only the user can make

1. **Answer nodes: derived or their own record?** P1.1 derives from `Decision` + `ProposedWrite`; I
   measured that the pair carries no date, no sign, and a target that is empty or non-node-shaped in
   4 of 7 gated tools. Do you want an `Answer` record written at the gate (R1.1, now the cheaper
   path), accepting one more record type in the checkpoint allowlist?

2. **What does a refusal block?** The user's three live refusals were refusals of `close_node`,
   i.e. *"leave this node open"*. Should the edge point at the **proposal** (a refusal declines a
   write) or at the **target node** (which renders as the user rejecting the node they meant to
   protect)? P1.1 chooses the second; the live data says it reads backwards.

3. **Q-P9, unchanged and now load-bearing:** is the op log the trail of everything **attempted** or
   everything **committed**? P1.2 needs it answered to record an aborted proposal, L1's fix needs it,
   and D12's promotion needs it (only what the log holds can be promoted).

4. **How much of a prior session does a new session see?** P4.1 shows every prior fact, closed claim
   and answer. The branch doc says that is the wall E58 rules out and that selection needs
   similarity, which §3 defers. Do you want (a) everything, unbounded; (b) only what the question's
   words reach, using the existing `neighbourhood`/`search` (`package.py:67-77`); or (c) nothing
   until similarity exists?

5. **How does a session re-establish a prior answer?** Today `propose_fact` requires a verbatim span
   of what you said **this cycle** (`tools.py:300-305`). Do you want a new path ("the user assented
   to prior answer u3.1 this cycle" becomes a fact in this session), or should a prior answer be
   re-established only by you saying it again in your own words?

6. **P2.6: build the exact-match stand-in, drop it, or replace it?** It would have fired zero times
   on the case it cites. The cheap alternative that *would* have fired is counting distinct files
   named across the assumptions' `moved_by`. Which?

7. **Q-P11 / the graph's key.** The plan puts the graph under the install (`<home>/sessions/graph`),
   so one clone driving two studied projects shares one graph and one cycle sequence. The audit's
   P-19b said one graph per studied project, keyed by resolved real path. Which, and is P-19b
   deferred or abandoned?

8. **The stage order.** P5.1's own text schedules the task-shaped run right after Stage 0; the plan
   numbers it last. Does the run (plus A8) come before P1.1, as the branch doc says it must?

9. **The branch split.** §4 puts P1.1 through P4.3 on one `session-graph` branch. The branch doc
   treats them as four shapes and calls two of them *"mutually decisive"*. Do you want them
   separable, per E65?

---

## Effort estimates

Sized from the code: files touched, whether tests exist for the path, and whether a schema or a
record type moves.

| Element | Effort | Why |
|---|---|---|
| P0.3 rewrite the prompt | **1 hour** | One markdown file; `tests/app/test_prompt.py` does not assert on it today, so add one string test. |
| P4.2 → **the decode fix instead** | **half a day** | `store.decode` + two `Ledger` fields + one test. Replaces P4.2 and unblocks P1.1(f) and P4.1(a). |
| P0.2 fence | **half a day** | One branch in `pre_tool_use`, placed before `meter.charge`; the path resolution is ten lines. |
| P0.4 lossless render | **half a day** | Once `thought.label` is in scope: a finding branch in `describe_node`, a `(+N chars)` suffix in `_evidence_lines`. |
| P0.1 directory split | **1 day**, +**half a day** if P-19b is in | Rename across 7 call sites incl. 5 test constructions, one new field, one flag, `README.md`. A live install test is another half day. |
| P2.2 citation on `Finding` | **1 day** | Fill the two dead fields, add the staleness compare, one allowlist entry. |
| P3.2 one-change + ground check | **1 day** | Brief edit plus a kind-aware check in `close_node`'s dry run; the gate already runs handlers dry (`hooks.py:138-148`), so the hook exists. |
| P2.5 grounding check | **1 day** for the check, **+2 days** for the re-author interaction | The check is ten lines against `node_ids`; making it a soft correction rather than sharing `OrientationFailed` is the work. |
| P2.1 references | **2 days** | New dataclass, `post_tool_use` reads `tool_input`, carry on `Attempts`, and a **live** test (the scripted path does not exercise the hook). |
| P1.2 `Blocked` (surface + budget only) | **2 days** | Record + allowlist + `Meter` carries call ids + `Attempts` carries refusals + renderer. The `aborted` half is blocked on Q-P9. |
| P3.1 `/handoff` | **1–2 days** | An uncapped renderer beside `render`, a command, a directory, a test. |
| P2.3 `store_evidence` | **3 days** | New tool + schema + surface sets + slicing + `source_of` wiring, and the doubled-record problem has to be solved or documented first. |
| P1.1 answer nodes | **3 days** with an `Answer` record; **a week** deriving | Derivation costs: `_TARGET_KEYS` rework, a sign decision, a date source, plus `tools.py` (2 handlers), `thought.py` (`live_ids`, `_WALKABLE`, `Supersession` role), `vocabulary.py`, `package.py`, four briefs. |
| P4.1 origin-aware package | **a week** | `decode`/`Ledger` change, a fork-safe origin, a re-ask path through `propose_fact`, a bound on PRIOR SESSIONS, two briefs, a two-session test. Not the renderer change the file list implies. |
| P2.6 breadth stand-in | **half a day** — and should not be spent | See the element. |
| P4.3 read-down slot | **0** | One word inside P2.1. |
| P5.1 task-shaped run | **~$0.50, 4 min wall clock, half a day to write up** | By Cycle 1's measure (O72 corrected: the cycle cost $0.51, 220 s). The cheapest element in the plan and the one the rest depends on. |

**Stage 0 as a whole: about 3 days.** **Stages 1–4 as written: about 3 weeks**, of which roughly a
week is P1.1's derivation and P4.1's under-costed store change — both avoidable by taking R1.1 and
doing the decode fix first.
