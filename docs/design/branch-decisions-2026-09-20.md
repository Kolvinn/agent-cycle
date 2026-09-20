# Branch decisions — the shapes the audit proposed, settled one at a time

Status: **in progress, 2026-09-20.** Same registers as `production-audit-2026-09-20.md`
(E their words, O observed with a locator, A my assumption, R its rival, Q a question for them,
D a decision they took, P a proposal of mine). **Nothing here is built and no branch is cut.**

The audit's Present proposed four shapes. They are being taken one at a time: their words are
recorded verbatim, my reading is marked as a reading, and what is still undecided stays a Q.

---

## Branch 1 — `looking-is-keeping`, as amended into `store_evidence`

### Their words, verbatim

| # | Their words |
|---|---|
| E67 | "I think it has some good and bad. I agree that the agent shouldnt actually put whatever they viewed into the assumption as evidence without at least some kind of filtering. the point of the tool outout being stored is so that the agent doesnt have to re-out what they already have. A fix for this could be where you store the read files, rather than the explicit output, and the assumption agent runs an store_evidence (or similar) that would auto generate a edge which would be similar to "evidenced_by" or supported_by, etc. and then attaches the read date, matches the file, and pipes the read/grep value directly into the graph as an exercpt." |
| E68 | "the cache doesn't exist in terms of read. The place the raw read is 'cached' is in the session tool output. The read post tool hook stores the reference to what was read, and when, and maybe file last updated, etc. You should think of those like metadata you would store in a node (which is what this is) in a graph rag. Then, since the agent has read that file, they can add evidence along with this metadata that validates on what is being extracted from, and they can modify any other nodes they made that turn (incase they made it wrong)" |
| E69 | "no nodes should not be auto created. Im fine with the agent specifying creating their own evidience nodes (with auto gen id). Theres' no reason to make a node just because somethign was read" |
| E70 | "no self referencing for now on other nodes" |

### D — what they decided

| # | Decision | From |
|---|---|---|
| D1 | **Automatic keeping is rejected.** Whatever the agent viewed does not become evidence on its own; a filtering step stays. | E67 |
| D2 | **The purpose of storing the tool output is to stop the agent re-producing what it already has.** That is the problem being solved, not "the graph should hold everything". | E67 |
| D3 | **There is no read cache to build.** The raw read is already held in the session's tool output, which is the conversation the model carries. Nothing bulky becomes durable. | E68 |
| D4 | **The PostToolUse hook stores a reference, not content**: what was read, when it was read, and probably when the file was last changed. Bookkeeping on the turn, not graph content. | E68 |
| D5 | **No node is auto-created.** Being read is not a reason for a thing to exist in the graph. | E69 |
| D6 | **The agent creates its own evidence nodes, deliberately, with an auto-generated id.** Ids stay the graph's to assign, as they are today. | E69 |
| D7 | **The evidence node carries the read metadata**, which is what validates what the excerpt was extracted from, and the excerpt is piped from what was already read rather than re-run. | E67, E68 |
| D8 | **The edge from the evidence auto-generates.** | E67 |
| D9 | **Within the turn, the agent may amend nodes it made that turn**, in case it made one wrong. | E68 |
| D10 | **No self-referencing on other nodes, for now.** | E70 |

### What this changes in the backing objects

Much less than my first write-up claimed, because D5 removed the source-node layer I had invented.

| Object | Change |
|---|---|
| `Finding` (`graph/state.py:145`) | Gains the read metadata: the file, the read time, the file's last-changed time. It already carries `tool_call_id` and `price`, which exist for exactly this tie and are filled today by the tool running its own command. |
| The excerpt's origin | Comes from the recorded tool output of a call already made, not from a freshly executed command. |
| `TurnContext.source_of` (`harness/turn.py:131`) | Defined, called by nothing today. Becomes the validation: the excerpt must appear in a recorded result. The `Finding` docstring already promises this rule ("stops the agent being its own witness") and nothing enforces it. |
| `TurnContext` | Gains the reference table D4 describes, written by `post_tool_use`, discarded with the turn. |
| A new tool, `store_evidence` or similar | Names a read and what to take from it. |
| `evidences` edge | Unchanged: it already auto-generates from a `Finding` when the view is built. D8 is existing behaviour. |
| Node kinds and ids | **Unchanged.** D5 and D6 mean no new kind and no natural-key identity, so the rule that the model never invents an id survives. |
| Authority and status | **Unchanged.** An evidence node stays agent-authored and provisional exactly as now. |

### What this does **not** fix

**Ledger line L20 (zero entities, zero claims) is untouched by this branch.** I had argued the
strongest gain was that the things layer would fill without the model's cooperation; that was
entirely a property of auto-creation, which D5 rejects. Under this shape the entity layer stays
as empty as the audit found it. Whether the project map is wanted at all is a separate question
and is not settled here.

### Q — open

| # | Question | My suggestion, possibly wrong |
|---|---|---|
| Q-B1 | **Cross-turn citation.** The reference table is per turn; the conversation spans the cycle. In antithesis the model still has orientate's reads in its context and may try to cite one, which would fail validation. Scope the references to the cycle, or refuse a citation outside the current turn? | Refuse outside the turn, for now: it keeps the witness rule literal and matches D10's caution. |
| Q-B2 | **Which calls leave a reference.** A read of a file, clearly. A grep matching several files. A glob that returns paths without reading them. | A reference means content was actually seen, so glob leaves none. |
| Q-B3 | **Granularity.** Does `store_evidence` take the whole recorded result, or a range or match within it? A whole-file read piped entire brings back the noise D1 rejects. | Name the read plus a range or match within it; require the range when the source was a whole-file read. |
| Q-B4 | **Does `attach_finding` stay?** If evidence can only be cited from something already read, a frame that has spent its pool cannot keep anything new. | Keep it for that case; `store_evidence` becomes the default path. |
| Q-B5 | **My reading of E70 needs their correction.** I read "no self referencing for now on other nodes" as: an evidence node does not link to other nodes beyond the one it supports, and the cross-node referencing I raised is out of scope for now. The other reading is that it answers Q-B1 directly (no citing a read belonging to another turn). | I have taken the first reading and left Q-B1 open. Correct me if it was the second. |

---

## Branches 2, 3, 4 — awaiting their answers

Summarised to them 2026-09-20; their words will be recorded here as they arrive.

---

# Horizon — what the coming iterations want, 2026-09-20

Recorded at their instruction while settling branch 1. **None of this is to be built now.** It is
here so that the small decisions taken now are not dead ends. Where a near-term decision is
cheap now and expensive later, it is marked **[protect]**.

## Their words

| # | Their words |
|---|---|
| E71 | "In the future, not now, we will be using this as a thought graph extension from a larger project graph rag. Future extensions might involve vectorization and vector stores as well. So perhaps don't get bogged down in what the specifics are of this, but instead exapnd your horizons into what the coming iterations would want it to be" |
| E72 | "I don't think taht the mistaking cite sourcing or readings as fact would be an issue in this expanded scenario because you can still instruct the agent who is investigating to only treat the original graph rag as another thing to read. They wopuld therefore say attach evidence in the same way as another read of an actual file, but it just becomes another source . The actions dictated by the individual session are still the passing off of the user and the session graph. This would expand the amoutn of tools available (most liekly) to the end sesison agent wherein they oculd push session graph changes to the larger graph." |

## The shape

**Two graphs with opposite relationships to time.** The project GraphRAG is about the world: it
is rebuilt from the world, it goes stale when the code changes, and its truth condition is
whether it matches the repository now. The session thought graph is about episodes of reasoning:
append-only, historical, never stale, and its truth condition is whether that reasoning happened
on that evidence at that time. Neither can serve the other's condition, which is why they are
two stores and not two layers.

**Reading down.** E72 settles how the larger graph is consumed: it is *another source to read*.
Its content enters through the same path as a file read and becomes an evidence node, provisional
and sourced. No new authority path is created, so no new authority rule is needed. **My earlier
concern about authority laundering is withdrawn** — it assumed retrieval would bypass the evidence
mechanism, and there is no reason it would.

**Writing up.** E72 adds the direction I had not considered: approved session outcomes can be
pushed from the session graph into the larger one, as further gated tools. This is the more
important half. A machine-built GraphRAG knows what it believes and not why or on whose
authority; a promoted node arrives carrying a citation to the cycle, the evidence and the user's
approval. Promotion is the channel by which a historical episode updates the current-world view,
and it is the validation channel a GraphRAG otherwise entirely lacks.

**This resolves the entity-layer question (L20).** With promotion, the thought graph's entity
layer is neither a defect nor a competing map. It is a *staging area*: the session names a thing
provisionally, the user confirms it, and it is promoted. That is why it should exist and why it
should stay small. The audit's "zero entities" finding should be re-read in that light — the
question is not "why did the model not build a map" but "did anything reach the state where it
would be worth promoting".

## What to protect now

| # | Thing | Why |
|---|---|---|
| **[protect]** H1 | **The op log stays the only truth; every graph is a derived view.** Already true and the most future-proof decision in the build. A vector index, a project-graph join and the networkx view are all projections that can be rebuilt. None may become authoritative. | A rebuilt index is free; a lost log is not. |
| **[protect]** H2 | **Storage lossless, cap only at render.** Findings are cut at a fixed width when displayed (L25). If that cap ever migrated into storage, a future index would embed stubs. | Embeddings of truncated text are worse than useless. |
| **[protect]** H3 | **Write the read reference as a citation into a corpus, not as a filesystem fact**: source identifier, locator within it, retrieval time, version marker. The filesystem is one implementation of those four. | Swapping the corpus becomes a change of resolver, not of schema. Directly shapes D4/D7 of branch 1. |
| **[protect]** H4 | **Record the source's kind, and with it how far the material is from the world.** A file read returns primary material; a project-graph read returns something an earlier process authored. Both are evidence and both provisional, but a chain of derived summaries should not be indistinguishable from a direct read. This is the one part of the withdrawn concern worth keeping, and H3 gives it for free. | Provenance depth, not authority. |
| H5 | Every record needs a stable id, a time and a provenance pointer, so it can be cited from outside. Nearly true today. | Promotion has to be able to name what it came from. |

## Where vectors earn their place

Retrieval of evidence is the obvious use and the least interesting; a retrieval is just another
priced call. The three that answer findings already in the ledger:

- **Breadth measurement.** L29: three assumptions were one topic and two rivals said the same
  thing. Breadth is load-bearing (E11, E14) and is enforced today by a count alone. Similarity
  over a cycle's assumptions is the measurement that does not exist.
- **Duplicate cycles.** O106: two sessions asking the same question in different words open two
  cycles and both sets of provisional nodes render forever, unmarked.
- **Recall of prior reasoning.** The strongest move against premature concluding (E51) is *you
  looked at this before, here is what you concluded and what the user refused*. That needs an
  index over accumulated reasoning, not over the project.
- **Compression.** The `summary` kind and `summarises` edge are built and unused. They are the
  hook for the compression half of E48's growth / compression / reconciliation, and clustering
  makes it tractable at scale. Not dead code; unfinished.

## Open, for when it is time

| # | Question |
|---|---|
| Q-H1 | What is promotable upward? Registered facts and confirmed verdicts, clearly. Approved entities and relations, probably. Refusals are arguable: "the user said this relation is wrong" may be the most valuable thing the larger graph could learn. Provisional assumptions, rivals and the reasoning trace stay episode-local. |
| Q-H2 | Conflict on promotion: the larger graph already holds something the promotion contradicts. The vocabulary already has `supersede` with "the loser keeps its evidence", which generalises, but who wins is a rule to state rather than infer. |
| Q-H3 | The price model probably inverts when retrieval is cheap and full reads are expensive. E11's "go wide before deep" stops being the costly direction. Nothing to decide before there is a retrieval layer to price. |

---

## Refusals, and the answer node — 2026-09-20

### Their words

| # | Their words |
|---|---|
| E73 | "If these are stored in the session as node answers. Say an assumption node was blocked by a user answer node, or similar, that could also get filled into the project graph which would be a legitimate thing to do concerning this project. Another session might come along, find that node conclusions on the project graph, but because each session is explicitly tasked with only having session provided answers being the truth source, the agent could then just use that and write it does as evidence but it woudl also get raised as a question to the user . I.e., "is this still true". This woiuld also play into the fact that the parent graph is the one that holds allof the graph information concerning the goals of the overall project and the implementations,et c. So a new session could say, lets start on task X, whicih would pick up that blocked we just mentioned, but because its being overriden that session, it's all fine." |

### What it settles

**My proposal is withdrawn.** I had suggested a scope on the verdict (not now / not this way /
not ever), so a refusal could be classified at the moment it is given. E73 moves the burden from
write time to read time instead: promote the answer, and let the next session re-establish it
with the user. That is better for a reason I had missed — **at the moment of refusing, the user
often cannot know whether the refusal is principled or situational**, so asking them to declare
it is friction that would frequently be answered wrongly. At read time, in a new session with a
concrete task, "is this still true" is both answerable and task-relative, which is the right
frame for it.

| # | Decision | From |
|---|---|---|
| D11 | **A user answer is a node**, not an annotation on a proposal. An assumption blocked by a user answer is an edge between two nodes. | E73 |
| D12 | **Answer nodes are promotable** to the project graph; a conclusion about this project is a legitimate thing for the parent graph to hold. | E73 |
| D13 | **A promoted answer arrives in a new session as evidence, never as truth.** Only answers given inside the session are that session's truth source. | E73 |
| D14 | **A promoted answer is raised back to the user as a question** — "is this still true" — rather than being assumed to hold. | E73 |
| D15 | **The parent graph holds the project's goals and implementations**, so a session can open on "start task X" and pick up what bears on it. | E73 |
| D16 | **A session may override a promoted conclusion locally**, and that is fine because the override is session-local. | E73 |

### Why this is structurally right, and what it exposes in the current build

**Refusals are stuck in the least reusable place precisely because they are not nodes.** Today
`propose_fact` turns the user's sentence into a node of kind `fact` with `authority=user`, which
is durable, citable, closable and promotable. Refusing a proposal turns an equally authoritative
sentence into a string on a `Decision` record, which is none of those things. The same words from
the same person become a first-class node or an annotation depending only on which surface they
were said at. E28 says a user message and a user approval are different *surfaces*; it does not
say they should have different *durability*. **O-B1.**

**It needs no new vocabulary.** An answer node takes `status` like any other node, so "is this
still true" answered no is an ordinary `close_node` to refuted, and a replacement is an ordinary
`supersede` with the loser keeping its evidence. The scope field I proposed is unnecessary: status
plus the date it was given carries it.

**It dissolves L15.** The package's "THE USER REFUSED THESE. Do not propose them again" heading
exists because a refusal has nowhere else to live. As nodes with a status and a date, they render
as what they are, and a stale one surfaces as a question rather than a commandment.

### What it makes necessary

**The re-ask has to be selective, and this is the first concrete job for retrieval.** If every
promoted answer raises "is this still true", a session opening on a mature project meets a wall
of re-confirmation, which is exactly the workflow interruption E58 rules out. Something has to
decide which prior answers bear on *this* task. That is similarity over accumulated answers
against the task, which gives the vector store in the horizon section a definite job rather than
a general aspiration.

### Q — open

| # | Question |
|---|---|
| Q-B6 | **An answer node must carry the question it answered, or it is meaningless once promoted.** "Not this cycle" says nothing without the cycle. Does the promoted object therefore travel as a pair (the answer and what it was answering), or as one node whose text is composed at promotion time? |
| Q-B7 | Concurrent override: session A overrides a promoted answer and promotes the override while session B is still running on the original. Same shape as Q-H2, now reachable in normal use rather than only on conflict. |
| Q-B8 | Do machine refusals (off-surface, budget exhausted, stale id — L27) become answer nodes too? They are not answers and not authoritative, so probably not; but they are currently dropped entirely, and "the model tried this and was stopped" is still something the next cycle cannot see. |

---

# Reconciliation — the four branches after the discussions, 2026-09-20

Written at their request: *"lets touch base with the start of this session, what are the still
original 4 branches, and how has the recent discussions changed them… i want ot make sure we are
not forgetting things in the midst of these cahnges."* Checked against the audit's ledger
(L1–L32), its open **A** items and its **Q-P** questions, not from memory.

## The three gaps the branches existed to close (audit F22, unchanged)

1. **Evidence is not in the shape.** The survey's reads live in the conversation, not the graph.
2. **One node kind for two kinds of thing.** Assumptions absorbed claims; the entity layer is empty.
3. **Nothing reads the graph but the graph.** No hand-off to the working session.

The discussions have changed *how* each is closed. None of the three is closed yet.

## Branch by branch

### 1. `looking-is-keeping` → **`store_evidence`** — amended, and narrowed

| | |
|---|---|
| **Was** | The PostToolUse hook writes a `Finding` from every priced read, plus an entity node named from the path. Automatic. |
| **Now** | D1–D10. The hook writes a *reference* only (file, read time, file last-changed), held on the turn. The agent deliberately calls `store_evidence`, which creates an evidence node with an auto id, carrying that metadata, the excerpt piped from what was already read. The edge auto-generates, as it already does. |
| **Shaped further by** | H3 (write the reference as a citation into a corpus: source id, locator, retrieval time, version) and H4 (record the source's kind, so primary material is distinguishable from derived). |
| **No longer does** | **Anything about gap 2.** Automatic entity creation was the whole of that, and D5 rejects it. The original branch touched two gaps; this one touches one. |
| **Still true of it** | It is still a *voluntary* call. It makes keeping cheap; it does not make keeping happen. |
| **Open** | Q-B1 cross-turn citation · Q-B2 which calls leave a reference · Q-B3 granularity · Q-B4 does `attach_finding` stay · Q-B5 the reading of E70 |

### 2. `cite-or-retry` — undiscussed, but promoted in importance

| | |
|---|---|
| **Was** | The comparison arm: A24's rival, run against branch 1 to see which works. |
| **Now** | Unchanged in substance and **more load-bearing than when written**. Branch 1 was amended to stay voluntary, so this is now the only proposed mechanism that *forces* the survey to keep anything. The pairing logic that made it a mere comparison no longer holds. |
| **New question from the answer-node discussion** | `Assumption.grounded_in` already accepts a fact. With answer nodes (D11), should an assumption be groundable in a prior *answer* as well as a fact or a finding? **Q-B9.** |
| **Risk** | Being carried as "the other option" when it is now the primary instrument for gap 1. |

### 3. `graph-task-kind` — substantially relocated

| | |
|---|---|
| **Was** | `/graph` takes a kind, question or task. A task cycle's assumptions are interpretations (E2); a second role holds claims about the project. |
| **Now** | D15 moves the task itself upward: the parent graph holds the project's goals and implementations, and a session opens *against* a task that already exists there. So this is not a flag on a command, it is a session opening against an external node. |
| **And the role split is resolved differently** | Separation by *destination* rather than by role name: claims about the project are promotable upward, assumptions about the request stay local and episodic. The thought graph's entity layer becomes a **staging area** for promotion, which is why it should exist and stay small. |
| **Unchanged and unmet** | **O112: the build has never been run on a task-shaped request.** Every design move above was made without that evidence. |
| **Risk, stated plainly** | This is the branch being redesigned furthest from any data, and it is the exact failure mode this project exists to prevent. Nothing here should be built before one task-shaped live run. |

### 4. `package-handoff` — subsumed as an end state, still the only buildable form today

| | |
|---|---|
| **Was** | A `/package` command writes the rendered graph where the working session reads it. |
| **Now** | Promotion to the parent graph *is* the hand-off (D12–D15). The working session reads the parent graph and re-establishes what it needs (D13, D14), rather than reading a file. |
| **Q-P13 is answered, and by a third option** | Not "the working session reads a file" and not "chat mode becomes synthesis", but "a later session reads the parent graph and re-asks what bears on its task". |
| **But** | The parent graph does not exist. The file form remains the only version buildable now, and it is the cheapest way to find out whether the content is even useful before any of the promotion machinery is worth building. |

### 5. **New — `answer-nodes`**, which belongs to none of the four

D11–D16, arising entirely from discussion. A user answer becomes a node with an edge, not a
string on a `Decision`. Promotable. Re-asked at read time rather than scoped at write time.

It is arguably now the **first** thing to build, because: it is buildable today with no parent
graph; it needs no new vocabulary (status, `close_node` and `supersede` already carry it); it
dissolves **L15**; it reframes **L24**; it fixes **O-B1** (the same sentence from the user becomes
a node or a string depending only on which surface it was said at); and it is the prerequisite for
the entire promotion architecture that branches 3 and 4 now depend on.

## What is at risk of being forgotten

Checked line by line against the ledger. Nothing below is addressed by any of the five branches.

| # | Item | Why it matters now, more than when recorded |
|---|---|---|
| **1** | **L8, L10, Q-P11 — the state-directory split.** Running inside Harness writes state into Harness; `modes.toml` does not travel with the install. | **Prerequisite to everything.** Every branch needs validation on real work in Harness, and none can be validated until the app can run there without polluting it. Unglamorous and receiving no attention. |
| **2** | **L28 — the survey walks the working tree, gitignored directories included.** | **Worse than when recorded.** Under the E59 install shape the clone sits *inside* the host, so a survey of the host would read the tool's own source and pay for it. |
| **3** | **O112 — no task-shaped live run.** | Branch 3 is being designed around it. See above. |
| **4** | **L25 — findings render cut at 240 characters.** | **More important, not less.** `store_evidence` makes evidence the primary carrier, H2 says storage must stay lossless, and promoted or embedded evidence must not be a stub. |
| **5** | **L27 and A19 — machine refusals dropped; aborted proposals leave nothing.** | Answer nodes cover *user* refusals only. "The model tried and was stopped" and "the user never answered" remain invisible. **Q-B8** asks whether they are nodes too. |
| **6** | **L23 and A27 — the model batches proposals.** | The UI now serialises the *modals*, but the model still issues several closes in one message, so an answer to one cannot inform its siblings. Untouched on the model side. |
| **7** | **A8, A13, A21, A22 — unmeasured assumptions.** | A8 tests directly whether kept evidence survives into the next cycle, which is the premise of branch 1. A13 (mount mismatch) bears on the install shape. |
| **8** | **L1, L2, L4, L16, L32 — small core defects.** | Ghost cycle, refunded spend, a schema mismatch reported as a wrong count, a fork skipping its owed frame, a frame line read from the wrong checkpoint. None hard, none started. |
| **9** | **L26 — the stale system prompt.** | Trivial to fix and every live run still pays for it. |
| **10** | **Q-P9 — is the log the trail of everything attempted or everything committed?** | Unanswered, gates L1's fix, and now **more** consequential: if answers are nodes and nodes are promotable, what the log holds determines what can be promoted. |

## What the discussions have retired

| Item | Outcome |
|---|---|
| L15 (the renderer says never; you said not now) | **Dissolved** by answer nodes: status plus date carries it. |
| L20 (zero entities, zero claims) | **Reframed, not fixed.** Not a defect but a staging-area question; nothing yet makes it fill, and branch 1 no longer tries. |
| Q-P13 | **Answered**, by a third option neither of mine. |
| My scope-on-the-verdict proposal | **Withdrawn** (write time vs read time). |
| My authority-laundering concern | **Withdrawn** (a retrieval is a read; evidence is the only path in). |
| A15 (cost as the carrier) | **Withdrawn** earlier as a misreading; cost work backlogged at their word. |

## Revised order, for their verdict

1. **The state-directory split.** Prerequisite; nothing else can be validated on real work without it.
2. **`answer-nodes`.** Buildable now, no new vocabulary, dissolves a ledger line, and is the foundation branches 3 and 4 now rest on.
3. **`store_evidence` and `cite-or-retry` together.** Still mutually decisive, but with the roles reversed from the original write-up: the first makes keeping cheap, the second makes it happen.
4. **`package-handoff`, file form.** The cheapest way to learn whether the content is useful before promotion machinery is worth building.
5. **One task-shaped live run**, and only then any of `graph-task-kind`.

The Tier 2 core fixes (L26, L25, L27, L16, L1, L4, L32) are small and independent of all of this.

---

## Go-ahead, 2026-09-20

Their words E74–E76 and decisions D-G1–D-G4 are recorded in `combined-plan-2026-09-20.md` §7,
which is also the start-here for building. `ui-workflow` was merged (fast-forward) into
`orientate-absorbs-assume` at `a12751a` the same day. The design phase is closed; the next action
is `git checkout -b stage-1-graph orientate-absorbs-assume` and element 1 of the plan's §7 table.
