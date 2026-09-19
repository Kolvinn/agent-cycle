# The thought graph's alterations — a starting implementation, for review

Status: **proposal, not built.** Your instruction: *"propose to me what might be the best
starting implementations and I will review before you build."* Everything else in the app is
built and runs; the gated calls below are recorded and answered but change nothing yet, and
their tool result says so to the model.

The registers are as before: **E** your words; **P** what I propose; **Q** what only you can
settle. Every **P** is a starting point expected to be wrong in details — the point is that the
details are written down so they can be argued with.

---

## 1. What the graph is for

> E48 "the networkx graph as basically a thought graph that is rooted in the user approval
> similar to how a graph rag works where it goes through cycles of growth, compression and
> reconciliation such that only the correct data is maintained across sessions (saved state)"

So three things happen to it, in every cycle, and they are different kinds of change:

| Phase | Who | What enters or leaves |
|---|---|---|
| **Growth** | the research frames | readings, rivals, findings — agent-authored, no authority |
| **Reconciliation** | you, at the call, in synthesis | facts registered, verdicts on nodes, a rival replacing a reading |
| **Compression** | you, at the call, in synthesis | what the next cycle stops seeing |

The package the next cycle opens with is the *result* of all three. "Only the correct data is
maintained" is therefore a property of what the package renders, not of what the checkpoint
holds: the checkpoint keeps everything (it is the audit trail), and compression decides what
crosses.

---

## 2. The model — P

### Nodes

| kind | authored by | authority | id |
|---|---|---|---|
| `explicit` | you (verbatim) | **the only authority** | `e<cycle>.<n>` |
| `question` | you (the cycle's prompt) | context, not fact | `q<cycle>` |
| `reading` | the agent (orientate) | none | `a<cycle>.<n>` |
| `rival` | the agent (antithesis) | none | `x<cycle>.<n>` |
| `finding` | the agent, checked against a tool result | none — evidence | `f<cycle>.<n>` |

### Node status — readings and rivals

`open` → one of `confirmed` · `refuted` · `superseded` · `discarded`. Terminal once set by
you. Orthogonal to status: `compressed` (has a summary in place of its evidence).

### Edges

| edge | from → to | carries |
|---|---|---|
| `asks` | question → reading | why the agent read it so |
| `grounds` | explicit → reading or rival | which fact it hangs off |
| `evidences` | reading or rival → finding | — |
| `contends` | rival → reading | why the rival was authored |
| `supersedes` | winner → loser | your words |

Findings have no status of their own: they follow their node.

---

## 3. The operations — P

Each is a **record appended to the state** (never an in-place edit), applied at the moment
you approve the call, inside the turn. The view and the package derive from the records.

### 3.1 `attach_finding(target, locator, excerpt)` — built, ungated

A finding hangs off the funded reading (assume), the rival named by position (antithesis), or
the node id named (synthesis). The excerpt must appear in a tool result of the turn. **Q-G:**
in synthesis, may a finding attach to an explicit? *P: no — evidence hangs off claims, not
facts. A fact is yours and needs no evidence.*

### 3.2 `propose_fact(quote, because)` — built, gated

The quote must be a verbatim span of something you said this cycle. Approved → `explicit`.
Refused → nothing, your words on the record.

**P addition:** an optional `supports: [node ids]` argument, so approving also draws
`grounds` edges from the new fact to the readings it bears on. Approving the call approves the
binding — E28 — which is what makes the edge legitimate.

### 3.3 `close_node(target, verdict, because)` — gated

Your verdict on one reading or rival: `confirmed` or `refuted`. Record:
`Closure(node_id, verdict, words, cycle)`.

- A **confirmed reading stays a reading.** It does not become `explicit`: the claim is in the
  agent's words and E9 says fact is yours. The package renders it as
  `CONFIRMED BY THE USER — "<your words>"` under the reading, evidence kept.
- A **refuted** node renders as one line under `CLOSED` with your words, evidence dropped from
  the package (kept in history). One line, because the next cycle must not re-propose it.
- **No implicit effects.** Confirming a reading does not refute its rival, and refuting a
  reading does not confirm its rival. **Q-A:** *P: none, and the synthesis brief tells the
  agent to propose the rival's closure in the same breath, so you answer two calls rather than
  one call with a hidden second effect.*

### 3.4 `supersede(target, by, because)` — gated

A rival (or a later reading) replaces the reading it contends with. Record:
`Supersession(old, new, words, cycle)`.

- The loser's status becomes `superseded`; it renders as one line under the winner
  (`superseded a1.2: <claim>`), evidence dropped from the package.
- **The winner is promoted to the readings section** of the next package, keeping its id, with
  the note `replaced a1.2`. A rival that won is now the working reading. **Q-D:** *P: yes.*
- The winner's own evidence carries. Its `contends` edge is kept in history and no longer
  rendered.

### 3.5 `compress(target, summary)` — gated

Your approval of a one-line summary in place of a node's evidence. Record:
`Compression(node_id, summary, words, cycle)`. The node renders as
`[id] <claim> — summary: <summary>` with no finding lines; the findings stay in the
checkpoint. Allowed on any node, open or closed.

This is the only thing that stops the package growing, so **P:** the synthesis brief asks the
agent, every cycle, to propose compressing every node you closed. **Q-F:** per-node only for
now; a cycle-level compression (one summary for a whole cycle) later if the package still
grows too fast.

### 3.6 `discard(target, reason)` — gated

The node leaves the package except for one line under `DISCARDED` carrying your reason.
Record: `Discard(node_id, reason, words, cycle)`. Not allowed on an explicit. **Q-C:** one line
kept (P) or dropped entirely?

### 3.7 `promote_fact` — **P: remove from the surface for now**

It promotes a parked candidate, and nothing produces candidates while fact extraction is
parked (E34). A tool that can never succeed is surface that only looks present. **Q-E.**

---

## 4. What the next cycle opens with — P

The package, in this order, stable by id:

```
KNOWN — your words, registered by you            every explicit, always
READINGS                                         open + confirmed readings, and superseding rivals
  [a1.1] claim                                   CONFIRMED BY THE USER — "your words"
      would be moved by …
      - locator — "excerpt"                      unless compressed → "summary: …"
  [x1.2] claim  (replaced a1.2)
      superseded a1.2: claim
AGAINST THEM                                     open rivals only
CLOSED — refuted, one line each, your words
DISCARDED — one line each, your reason
YOU REFUSED THESE                                refused proposals, your words
BUDGET CLOSED
```

Readings from earlier cycles that are still `open` render but are not funded: allocations are
per cycle. If you want an old reading looked at again, `/graph` with a question that names it
is the way; the orientate frame sees it in the package.

---

## 5. A worked example

**Cycle 1.** Question: *"Where do we validate the incoming webhook signature?"* Orientate
names a1.1 (in `signature.py`), a1.2 (in the handlers), a1.3 (middleware). Assume attaches
f1.1 (the `verify_signature` def) to a1.1 and f1.2 (the missing-header docstring) to a1.1.
Antithesis authors x1.1–x1.3 and attaches f1.3 (`api/routes.py` "deliberately does not
verify") to x1.2. Synthesis presents.

You reply: *"the validation is in signature.py and the handler just calls it. The middleware
idea is dead."* The agent calls, and you answer:

| call | your answer | record | effect on the next package |
|---|---|---|---|
| `propose_fact("the validation is in signature.py and the handler just calls it", supports=[a1.1, a1.2])` | approve | e1.1 + two `grounds` edges | KNOWN gains e1.1; a1.1 and a1.2 show `hangs off e1.1` |
| `close_node(a1.1, confirmed)` | approve, "yes" | Closure | a1.1 renders CONFIRMED with evidence |
| `close_node(x1.1, refuted)` | approve | Closure | x1.1 moves to CLOSED, one line |
| `discard(a1.3, "no middleware here")` | approve | Discard | a1.3 and its rival x1.3 …

… and here the first overlooked detail shows itself: **discarding a reading leaves its rival
dangling.** *P: a rival whose reading is discarded or superseded is rendered under CLOSED as
`orphaned by a1.3` and is not funded; you can still close it.* **Q-H.**

| `compress(a1.1, "verify_signature in signature.py, HMAC compare; handlers call it only when the header is present")` | approve | Compression | a1.1 keeps one line, drops f1.1 and f1.2 from the package |

**Cycle 2** opens with KNOWN e1.1, a1.1 compressed and confirmed, a1.2 open with its evidence,
x1.2 open against it, and three one-liners. Orientate reads that and names a2.1 about the
missing-header gap. Nothing from cycle 1 is re-funded and nothing refused is re-proposed.

---

## 6. What building it involves

- `state.py`: four new records — `Closure`, `Supersession`, `Compression`, `Discard` — on
  accumulating channels; `propose_fact` gains `supports`.
- `thought.py`: status and `supersedes` / `grounds` edges derived from the records; a
  `carried(state)` selection that the package renders from.
- `package.py`: the sections in §4.
- `tools.py`: the five handlers apply their record instead of returning `PENDING_EFFECT`.
- `synthesis.py`: the brief asks for the rival's closure alongside a reading's, and for
  compression of closed nodes.
- Tests: one scripted cycle per operation asserting the record, the view, and the next
  package; the invariants extended (a superseding edge's ends are a rival and a reading; no
  node both confirmed and refuted; a compressed node has a summary).

---

## 7. Questions

| # | Question | P |
|---|---|---|
| Q-A | Does closing a reading act on its rival? | No implicit effects; the agent proposes both |
| Q-B | Does a confirmed reading become KNOWN? | No; only `propose_fact` makes KNOWN |
| Q-C | Refuted and discarded nodes: one line, or gone? | One line, so they are not re-proposed |
| Q-D | Does a superseding rival become a reading in the next package? | Yes, keeping its id |
| Q-E | Drop `promote_fact` until extraction exists? | Yes |
| Q-F | Compression per node only, for now? | Yes |
| Q-G | May a finding attach to an explicit? | No |
| Q-H | A rival whose reading is discarded or superseded? | Rendered as orphaned under CLOSED, not funded |
