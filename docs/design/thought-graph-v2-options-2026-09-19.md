# The thought graph, second shape — options for review

Status: **reviewed 2026-09-19; step 1 built.** Your answers, verbatim: *"1. I think attach
finding should be free, but have a hard limit. this allows mistakes to be overwritten. But the
only bits that can be overwritten in the orientation phase are the ones that have been just
created. 2. i think actually i take back what i said before on splitting it into a subgraph,
keep as is, keep changes consistent with the attach finding costs as well. 3. resume on the
same one. It should be able to restart specific to the saved graph state and updated tool
costs, so there should be no issues here if built right. 4. 5. closed. --- happy with your
takes on the others."* What that changed: §2 attach_finding is free with a hard limit
(`Budgets.max_findings`, provisional 12) and `replace=<id>` overwrites a finding the same
turn created; §3 is withdrawn — antithesis stays one pass, and attach_finding is free there
too; Q-3 is resume: `/graph` alone continues an interrupted cycle from the frame it owes,
with the caps and prices as they are now. Q-4 one `claim` kind; Q-5 closed vocabulary; the
rest as proposed. Steps 2–5 of §9 remain to build.

Registers as before: **E** your words, **P** what I
propose, **Q** what only you can settle. Every P is a starting point meant to be argued with.

Your message raised three things. The first two are fixes with a clear shape; the third is a
change of kind, and the fixes should be built in the shape the third will need.

1. **The excerpt refusal** in antithesis, fixed by a subgraph that shows one assumption per
   turn.
2. **`attach_finding` should run the read itself**, not have the agent retype it.
3. **The graph should become a thought graph** grounded in your facts, with typed
   relationships, node and edge edits, merges, and moving evidence — all gated.

---

## 1. Why the excerpt refusal happens

`attach_finding` checks the excerpt against the tool results *of the current harness turn*.
Antithesis is one turn that continues the conversation, so the model can see what orientate
read but the harness cannot: those results belong to an earlier turn's ledger. The model
quotes them, the check fails, and the message it gets back ("copy it from what actually came
back") is wrong in that case — it did.

Two things fix it and they compound:

- **§2 the finding is produced by the tool, not typed by the model.** Then there is nothing
  to check: the excerpt *is* the output.
- **§3 antithesis becomes one assumption per turn.** Each turn is small, the assumption and
  its evidence are in the message, and a finding attached in that turn is stamped to that
  assumption's rival without the model naming a target.

## 2. `attach_finding` runs the read — P

> E "the tool for requirement should be attach finding by piping a bash or read command
> into the tool. The tool would match against allowed tools and read files that session and
> then use the tool to extract the information and place it in the graph itself. This avoids
> having the agent retype everything. The attach finding tool should return the output from
> the piece of text they attached."

### 2.1 Shape

```
attach_finding(target, run)  →  runs `run`, records the output as the finding, returns it
```

`run` is one command. The tool splits it with `shlex`, checks `argv[0]` against an allow-list,
refuses pipes, redirects, `;`, `&&`, globs in the executable position and any path that
resolves outside `cwd`, and runs it with a timeout and an output cap. The finding's `locator`
is the command itself, its `excerpt` is the captured output, its `price` is the class of the
command.

| allowed | class | price today |
|---|---|---|
| `cat`, `head`, `tail`, `sed -n` (print only) | read | 2 |
| `grep`, `rg` | survey | 1 |
| `ls`, `find` (no `-exec`/`-delete`) | survey | 1 |
| `git log`, `git show`, `git blame` (read-only subcommands) | read | 2 |

Output cap: **P** 80 lines / 6 KB, then a marker `… N more lines not kept`. The finding
keeps only what the model saw, so the package can never carry more than the model did.

### 2.2 Options for the rest of the evidence surface

- **O-A keep `Read`/`Grep`/`Glob` as they are, add the executor to `attach_finding`.** Two ways
  to look at the same file, priced the same. The model looks with `Read` and keeps with
  `attach_finding`, paying twice if it does both. *P: this — it is the smallest change and it
  matches "match against allowed tools and read files that session".* Whether keeping should
  be cheaper than looking is **Q-1**.
- **O-B `attach_finding` is the only way to read.** Every read is kept. Simplest to reason
  about, and the graph fills with everything the model ever glanced at; compression (§5.6)
  becomes the whole problem.
- **O-C a structured form instead of a command:** `attach_finding(target, path, lines="10-40")`
  and `attach_finding(target, grep="pattern", path=...)`. No shell parsing at all, but every
  new kind of look is a schema change. Can sit alongside O-A later.

### 2.3 Price and budget

Charged in the PreToolUse hook like any priced call, by the class of `argv[0]`, before the
command runs. Refused when the pool is empty. A refused or failed command records nothing.

### 2.4 What changes in the code

`harness/tools.py` gains the executor (`harness/evidence.py`, pure: parse → allow →
resolve paths → run → cap). The verbatim check goes. `EVIDENCE_TOOL_CLASS` gains the command
classes. The scripted harness needs a way to script command output (it already scripts tool
results; the executor takes a `runner` callable that tests replace).

## 3. Antithesis as a subgraph — P

> E "having the sub graph usage for the antithesis turn. They would only get the starter
> prompt once and then another message with the antithesis. This means that only ever see
> assumption once per iteration. They return raw text, with a comment attached to the
> antithesis if required. This phase would therefore be finished when all assumptions in the
> list/queue have been iterated on."

```
antithesis
  ├─ next      pick the first assumption of this cycle not yet countered
  └─ counter   one harness turn on it; loop to `next` until none is left
```

- **The brief once**, on the first turn, as now.
- **Each turn's message** is one assumption: its id, its claim, what it would be moved by, and
  the findings it cites — the evidence lines themselves, not just ids, so the turn has the
  excerpts in front of it without re-reading.
- **The payload per turn** is `Counter(rival: str, comment: str = "")` — "raw text, with a
  comment attached if required". No count to retry on: one rival per turn by construction.
- **Findings attached in the turn** are stamped to that assumption's rival; `target` is
  ignored (the old assume frame's discipline).
- **Budget:** one pool for the pass, `base + N`, shared across the turns; the message carries
  what is left. **Q-2:** per-assumption pools instead (`per_assumption` each), which is
  fairer but means an early assumption cannot borrow from a later one.
- **State:** `countered: list[str]` (accumulating) and the loop reads the queue as "this
  cycle's assumptions minus countered". The subgraph is invoked inside the node and returns a
  delta, exactly as the deleted assume frame did (it is in git history: `git show
  faa5985:src/langchain_claude_test/app/graph/nodes/assume.py`).

An interrupt mid-pass leaves the pass at the last countered assumption; the next `/graph` of
the same query resumes the loop rather than restarting it, because the entry router sees
`stage == antithesis` with an unfinished queue. That is a small change to `entry()` — **Q-3**:
resume the pass, or restart the cycle?

## 4. What "a comprehensive thought graph" means — P

> E "expand it to be more of a comprehensive thought graph grounded in user fact, rather
> than just what is essentially a slightly more formatted research tool. So tools should be
> able to add relationship types into the networkx in such a way like graph rag does it
> (depends on, requires, etc.). As per usual, the graph modifications are hitl gated. This
> also means that nodes will need to be deleted/renamed/modified along with edges. This
> means that information attached (the greps and reads) will need to be shifted."

Today's graph is a **derivation**: five fixed node kinds, five fixed edges, all determined by
which frame authored what. It cannot hold "the webhook handler depends on `signature.py`"
because nothing in it is a thing in the project — only claims about your request. A thought
graph in the GraphRAG sense has three layers, and ours has one and a half:

| layer | GraphRAG | ours today | ours proposed |
|---|---|---|---|
| **things** | entities (people, systems, files) with typed relations | — | `entity` nodes: file, module, function, service, config, concept |
| **claims** | claims about entities, with confidence | assumptions, rivals | `claim` nodes with a role (assumption, counter, observation) and a status |
| **evidence** | source text units the claims cite | findings | `evidence` nodes, produced by the executor (§2) |
| **authority** | — | explicits | `fact` nodes: your words, the only authority |
| **compression** | community summaries | (proposed, unbuilt) | `summary` nodes standing in for a subgraph |

The rest of this section is the model; §5 is the operations; §6 where it lives; §7 how the
next cycle reads it; §8 the shell; §9 the order to build it in.

### 4.1 Nodes

Every node: `id`, `kind`, `text`, `status`, `authority` (`user` | `agent`), `cycle`, and a
`summary` once compressed. Ids stay positional and prefixed, as now: `e` fact, `q` question,
`a` assumption, `x` counter, `f` evidence, plus `n` entity, `c` other claim, `s` summary.

| kind | who makes it | gated? | status set |
|---|---|---|---|
| `fact` | you, via `propose_fact` | yes | — (a fact is not open or closed; it is yours) |
| `question` | the cycle | — | — |
| `entity` | the agent, from the survey | see §5.1 | provisional → confirmed / discarded |
| `claim` (assumption, counter, observation) | the agent | see §5.1 | provisional → confirmed / refuted / superseded / discarded |
| `evidence` | the executor | no | follows its node |
| `summary` | the agent, via `compress` | yes | — |

**Q-4:** are assumptions and counters two kinds or one kind with a role? *P: one `claim` kind
with `role`, so a counter that wins becomes an assumption by changing its role (the
supersession of the earlier proposal), and a cycle can also record plain observations.*

### 4.2 Edges

Every edge: `kind`, `why`, `authority`, `cycle`, and its own status (an edge can be refuted
without either end being).

Two vocabularies:

**Structural** (the graph's own; made by the frames, never by the model naming them):
`asks` question→claim · `cites` claim→evidence · `evidences` node→evidence ·
`contends` counter→assumption · `grounds` fact→claim · `summarises` summary→node.

**Relational** (the GraphRAG part; the model proposes them, you approve):

| relation | between | reading |
|---|---|---|
| `depends_on` | entity→entity | A does not work without B |
| `requires` | claim→entity, claim→claim | A holds only if B |
| `calls` / `defines` / `configures` / `part_of` | entity→entity | code structure |
| `supports` / `contradicts` | claim→claim, evidence→claim | argument |
| `supersedes` | claim→claim | replacement, with your words |
| `relates_to` | any | the escape hatch, with `why` required |

**Q-5:** closed vocabulary, or open with approval? *P: the table above is the closed core;
a relation not in it is proposed with `relates_to` plus a `proposed_kind`, and approving that
call adds the kind to this project's vocabulary (a record, so it persists). New kinds are
rare and each is a decision, which is what the gate is for.*

### 4.3 Status, as before

`provisional` → one of `confirmed` · `refuted` · `superseded` · `discarded`, terminal once you
set it; `compressed` orthogonal. Agent-authored nodes are born `provisional`. Everything the
earlier proposal said about closure, supersession and compression stands, with "reading"
read as "claim".

## 5. The operations — P

> E "As per usual, the graph modifications are hitl gated."

### 5.1 What is gated — the one question that shapes everything

Every write that **touches an existing node or edge, or asserts a relation**, is gated. The
open question is *growth*: the survey will surface twenty entities and thirty evidence nodes
in one turn.

- **G-1 everything gated.** Twenty modals per survey. Faithful to the sentence, unusable.
- **G-2 growth is ungated and provisional; reconciliation and compression are gated.** A
  new `entity`, a new `claim`, a new `evidence` node and their *structural* edges are born
  `provisional` with `authority=agent`, exactly as assumptions are today — they claim
  nothing. Every *relational* edge, every edit of an existing node or edge, every merge,
  delete, verdict and compression waits for you. *P: this.*
- **G-3 growth is batched:** the frame collects its proposed nodes and puts them to you once,
  at the end of the turn, as a list to tick. Fewer modals than G-1, but the turn cannot use a
  node until you have answered, which breaks the flow of a survey.

Under G-2 the graph is still "rooted in user approval": a provisional node that nothing you
approved connects to renders under `PROVISIONAL — not yet reconciled` and is the first thing
compression proposes to discard.

### 5.2 The tools

One tool per operation, each thin, each a record (never an in-place edit):

| tool | gated | record | effect |
|---|---|---|---|
| `attach_finding(target, run)` | no | `Finding` | §2 |
| `add_node(kind, text, role?, why)` | no (G-2) | `NodeAdded` | a provisional node |
| `add_edge(src, kind, dst, why)` | structural no, relational **yes** | `EdgeAdded` | |
| `propose_fact(quote, because, supports?)` | yes | `Explicit` (+ `grounds` edges) | as proposed before |
| `update_node(id, text?, kind?, role?, because)` | yes | `NodeUpdated` | rename / reword / reclassify; the old text stays in history |
| `update_edge(src, dst, kind?, why?)` | yes | `EdgeUpdated` | |
| `delete_node(id, because)` | yes | `Tombstone` | status `discarded`; **refused while evidence or relational edges remain** — move or merge first |
| `delete_edge(src, dst, because)` | yes | `Tombstone` | |
| `merge(source, target, because)` | yes | `Merge` | every edge and every evidence node of `source` re-pointed to `target`; `source` tombstoned with `merged_into` |
| `move_evidence(finding, to, because)` | yes | `EvidenceMoved` | one finding re-pointed |
| `close_node(id, verdict, because)` | yes | `Closure` | confirmed / refuted |
| `supersede(old, new, because)` | yes | `Supersession` | |
| `compress(ids, summary)` | yes | `Compression` | a `summary` node standing in for the set |

> E "this could be a merge where you choose one source and one target node and it brings
> across the data" — that is `merge`, and `delete_node` refusing while things hang off the
> node is what forces the choice to be made rather than lost.

**Q-6 batching.** With this many gated calls, synthesis will raise several per reply. Two
ways to keep that bearable:

- one modal per call, as now — simple, and each answer is one record;
- a `propose_changes(ops)` tool whose one modal lists every op with an accept/refuse toggle
  and one words box for the batch, recording one decision per op. *P: build the per-call
  tools first; add the batch tool and its modal when the count hurts.* Your text-first rule
  for synthesis (built today) already means the batch is discussed before it is asked.

### 5.3 What moves when a node changes

- **update**: nothing moves; edges and evidence keep pointing at the id.
- **merge**: everything moves; duplicate edges collapse (same kind, same far end), keeping
  the earlier `why`.
- **delete**: refused unless bare (§5.2), so nothing is ever orphaned; the tool result names
  what is still attached and suggests `merge` or `move_evidence`.
- **supersede**: the loser's evidence stays on the loser (it was evidence *for that claim*);
  the winner's role becomes `assumption`. Your earlier Q-D stands.
- **compress**: the members keep everything; the package renders the summary instead.

### 5.4 Invariants (extended)

Evidence has exactly one parent; a counter contends with exactly one assumption; a
relational edge's ends are live (not tombstoned); a summary summarises at least one node;
no node is both confirmed and refuted; a tombstoned node has no live edges; no cycles among
`supersedes`; the whole graph stays a DAG **except** relational edges, which may form cycles
(`A depends_on B depends_on A` is a real thing to record). So acyclicity is checked on the
structural subgraph only.

*Built 2026-09-19 (§4, §5).* Decisions taken in the build, each overturnable: the gate
runs the handler dry before asking, so a call the handler would refuse (a discarded end, a
duplicate relation, a delete with evidence still attached) is refused to the model and never
becomes a proposal. `add_edge` exists in the surveying frames too, gated as everywhere; the
briefs tell them to name only what the code shows plainly. A superseding claim inherits the
`asks` edge of the claim it replaces, so it is a proper assumption. A merge keeps the
target's earlier edge on a duplicate and drops what would become a self-loop. `update_edge`
and `delete_edge` name the edge by id (`r1.2`), which the package prints beside each
relation. Neither `promote_fact` nor a parked candidate exists any more: nothing produced
one. Relational edges are not checked for cycles; the structural subgraph and the
`supersedes` edges are.

## 6. Where the graph lives — the architectural choice

Today the graph is derived from the **per-thread LangGraph state**. That gives every session
its own graph, forks copy it, and nothing is shared between sessions.

> E (earlier) "such that only the correct data is maintained across sessions (saved state)"

- **S-1 stay in the thread state.** No new store; `/fork` copies; sessions do not share.
  Simplest, and it contradicts "across sessions" unless a session *is* the project.
- **S-2 a project-level operation log.** `sessions/graph/ops.jsonl` (or a table in the
  existing SQLite file): every record from §5.2 appended with its cycle, session and
  decision. The networkx view is materialised by replaying it, cached in memory, and the
  thread state keeps only the cycle's working set (question, which claims this cycle made,
  the pointer, the conversation). Every session reads and writes the same graph. *P: this.*
  Consequences to decide: a `/fork` forks the conversation and the cycle but **shares** the
  graph (**Q-7**: or copy-on-fork into a named graph); two sessions altering the graph at
  once are serialised by the log (append-only; the runner is one task per process, so the
  conflict is only across processes, and a file lock is enough).
- **S-3 networkx pickled per project.** Same sharing, no history. The op log is what makes
  "why is this here" answerable and the earlier proposal's audit trail real, so no.

Under S-2 the earlier design's "records + derived view" pattern is kept exactly; only the
channel the records accumulate in moves from the checkpoint to the log.

*Built 2026-09-19 (`graph/store.py`).* Decisions taken in the build, each overturnable:
the log is `sessions/graph/ops.jsonl`, one line per record with `kind`, `session`, `at`
and `data`; a frame appends everything it authored in one locked write when its turn is
over, so an interrupted turn leaves nothing behind. Cycle numbers are the log's, not the
thread's (`open_cycle` under the lock), which is what keeps ids unique across sessions; a
cycle a session opened and never wrote to is handed back on re-run, so a frame that fails
after opening does not leave an empty cycle behind. Replay keys every record by id, last
line wins, which makes a re-run frame harmless and is the seam the §5.2 `update_*` ops
will use. The ledger is refreshed from the file's tail on each read, so another process's
lines appear on the next call.

## 7. How a cycle reads a bigger graph

The package injects the whole graph today. With entities and evidence outputs of 80 lines,
a project graph will pass the context window within a few cycles. GraphRAG answers this with
retrieval and summaries; so should we.

- **P-1 the package carries the top of the graph only:** KNOWN facts, every `summary`, the
  claims and entities within *k* hops of the cycle's question and of the facts it grounds on
  (k = 2, provisional), and one line per node beyond that. Evidence text renders only for
  nodes inside the neighbourhood and not compressed.
- **P-2 the agent pulls the rest:** two ungated, unpriced read tools on the graph server —
  `graph_search(text)` (nodes whose text matches, with kind and status) and
  `graph_neighbours(id, depth=1)` (a node, its edges, its evidence). Reading the graph is
  free because it is *our* text, already paid for; **Q-8**: or a nominal price so the model
  does not read it in place of thinking.
- **P-3 compression is proposed every cycle** for nodes closed last cycle and for any
  provisional cluster older than *n* cycles, so the top of the graph stays small.

*Built 2026-09-19 (§7).* P-1 as written, with one addition: the seeds are the facts, the
cycle's question (the latest one before a new cycle has its own) **and the nodes whose text
shares words with the question**, so a new question reaches the part of the graph it is
about rather than only the previous question's. `package_hops` and `stale_after` are
provisional numbers in `config.Budgets`, settable with `/budget`. The read tools are free
(Q-8) and exist on every frame. Compression candidates are computed by
`thought.compression_candidates` and named in the synthesis brief; the model proposes them
in text on the opening turn and calls `compress` after the reply, like any other change.

## 8. The shell

- The panel becomes a graph browser: by kind, by status, or the neighbourhood of a selected
  node; selecting a node shows its edges and evidence in the transcript (`/show node a1.2`).
- The approval modal shows the *effect* of an op, not just its arguments: for `merge`, the
  edges and evidence that will move; for `delete_node`, why it is refused.
- `/graph` commands for the same reads the agent has: `/show search <text>`,
  `/show neighbours <id>`.
- If Q-6 goes to batching, a checklist modal.

*Built 2026-09-19 (§8).* The panel is a browser with three views (outline, by kind, by
status); selecting a node runs `/show node <id>`. The approval modal shows what the handler's
dry run said the call would do (for a merge: which evidence and relations move). No checklist
modal: Q-6 stays per call until the count hurts.

## 9. Order of work — P

1. **Fixes first, in the new shape:** the executor behind `attach_finding` (§2, evidence
   nodes keep the command and its output) and the antithesis subgraph (§3). These do not
   depend on §4–§7 and remove the failure you hit.
2. **The store (§6, S-2):** move the records to the project op log, materialise the view,
   thread state slims to the working set. No new tools yet; everything behaves as today.
3. **The model and the tools (§4, §5):** `entity` and `claim` kinds, relational edges with
   the closed vocabulary, `add_node`, `add_edge`, `update_*`, `delete_*`, `merge`,
   `move_evidence`; the earlier proposal's `close_node`, `supersede`, `compress` built
   against the same records. Invariants extended. Package sections for provisional nodes.
4. **Retrieval and compression (§7):** neighbourhood package, `graph_search`,
   `graph_neighbours`, compression proposed per cycle.
5. **The shell (§8)** alongside 3 and 4.

Each step ships with the scripted-cycle test extended and one live spike.

## 10. Attention

- **Evidence gets large** once it is command output. The cap (§2.1) and compression (§7)
  are what keep the package honest; without P-3 the graph will outgrow the window.
- **`authority=agent` must stay visible** everywhere a node renders. A relational edge the
  model proposed and you approved is yours; one it proposed and is still provisional is not,
  and the package must not let the next cycle mistake the second for the first.
- **The executor is a shell.** The allow-list, the cwd fence, no pipes or redirects, a
  timeout and an output cap are the whole of its safety; `Bash` itself stays off every
  frame's surface. Worth a test per refusal.
- **Ids across sessions.** Positional ids per cycle (`a3.2`) stay unique only if cycle
  numbers are project-wide, not per session. Under S-2 the cycle counter moves to the log.
- **The synthesis text-first rule** (built today) applies unchanged to the new tools: the
  opening exchange withholds every gated tool.
- **The old proposal's questions Q-A..Q-H** still need your answers; they are about status
  and rendering and carry over unchanged with "reading" read as "claim".

## 11. Questions

| # | Question | P |
|---|---|---|
| Q-1 | Should keeping (via `attach_finding`) cost less than looking (`Read`)? | Same price; revisit if the model stops keeping |
| Q-2 | Antithesis budget: one shared pool or per-assumption? | Shared, `base + N` |
| Q-3 | An interrupted antithesis pass: resume or restart on the next `/graph`? | Resume |
| Q-4 | Assumptions and counters: two kinds or one `claim` with a role? | One kind |
| Q-5 | Relation vocabulary: closed, or open with approval? | Closed core, new kinds approved once |
| Q-6 | One modal per gated call, or batched proposals? | Per call first; batch when it hurts |
| Q-7 | With a project-level graph, does `/fork` share it or copy it? | Share |
| Q-8 | Are the graph read tools free? | Free |
| Q-9 | Which of G-1/G-2/G-3 for growth? | G-2 |
| Q-10 | Which of S-1/S-2/S-3 for where the graph lives? | S-2 |
