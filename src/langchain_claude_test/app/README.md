# app — the Claude shell with a provenance cycle behind `/graph`

**Status: built and running.** The three-frame cycle runs live over the Claude Agent SDK, the
plain Claude connection is the default, sessions persist and resume, interrupts work, and the
Textual UI streams thinking, text and tool calls. The thought graph is a project-level op log
with entities, claims, evidence and approved relations; every alteration the user approves
takes effect in the graph, the package and the panel. The design is in
`docs/design/thought-graph-v2-options-2026-09-19.md`.

## Run

```bash
uv run langchain-claude-test            # a new session in this directory
uv run langchain-claude-test mywork     # open or create the session "mywork"
uv run langchain-claude-test --cwd /path/to/repo --model sonnet
```

Plain text goes to the focused mode. `/graph <query>` starts a cycle; plain text while the
focus is the graph continues its synthesis conversation; `/chat` leaves it. `/help` lists the
rest. Modes come from `modes.toml` in the working directory: every table there is a `/<name>`
command with its own system prompt and tools. `/graph` alone resumes a cycle that was
interrupted, from the frame it owes, with the caps and prices as they are now.

| Key or command | Does |
|---|---|
| `Enter` / `Shift+Enter` (or `Ctrl+J`) | send / new line; the prompt wraps and grows to ten lines |
| `Tab` | complete a `/` command; the line above the prompt lists the matches |
| `Ctrl+A` | select all in the prompt (and in the approval modal's words box; approve there is `Ctrl+Y`, refuse `Ctrl+N`) |
| `Esc` | interrupt the turn in flight |
| `PageUp` / `PageDown` / `Ctrl+End` | scroll the transcript; scrolling up stops it following new output until you return to the end or send a message |
| `Ctrl+G`, `Ctrl+Left`, `Ctrl+Right`, `/panel [show\|hide\|<width>]` , or drag the divider | hide, show and resize the graph panel |
| `/model` | pick from the CLI's own model list (with its per-model effort levels); `/model <alias>` sets one directly |
| `/effort` | pick the effort level; `/effort <level>` sets it. Chat reopens the same conversation at the new level |

Model and effort are saved on the session and restored by `/resume`; a fork inherits them.

The cycle's numbers are settable from the prompt and saved on the session the same way:
`/budget` lists every cap with its default, `/budget per_assumption 8` sets one for the next
frame on, `/budget reset` restores the defaults; `/prices` does the same for what a call
costs by class (`/prices read 3`). A frame already in flight keeps the pool it opened with.

## Layout

| Module | Owns |
|---|---|
| `config.py` | budgets and prices (every unchosen number is in `PROVISIONAL`), model defaults, modes, `AppConfig` |
| `graph/state.py` | the record types, and the thread's working set (cycle, pointer, conversation, what was said) |
| `graph/vocabulary.py` | the closed vocabulary: node kinds (question, fact, claim, entity, evidence, summary), roles, statuses, structural vs relational edges |
| `graph/store.py` | the project's op log (`sessions/graph/ops.jsonl`): every record appended with its session; replayed into a `Ledger`, shared by every session |
| `graph/budget.py` | pool names and spend arithmetic — pure |
| `graph/surface.py` | which built-ins and which in-graph tools exist per frame; which are gated |
| `graph/payloads.py` | the structured answer each frame must return |
| `graph/package.py` | the text a cycle opens with — the compaction |
| `graph/thought.py` | the networkx view over the ledger: base records, then every operation applied in log order (`apply`); invariants; an outline for the panel |
| `graph/nodes/` | the three frames: orientate (survey, findings on the question, suggested assumptions), antithesis (one rival per assumption), synthesis |
| `graph/graph.py` | the edge list, the SQLite checkpointer, `check_topology()`, `render()` |
| `harness/protocol.py` | `StageRequest` / `TurnResult`, `Approver` / `Verdict`, `FrameInterrupted` |
| `harness/meter.py` | prices a call and charges before it runs |
| `harness/hooks.py` | `PreToolUse` = meter + surface; `PostToolUse` = record + running count; `can_use_tool` = the human gate |
| `harness/evidence.py` | the fenced executor behind `attach_finding`: allow-list, no shell, cwd fence, output cap |
| `harness/tools.py` | the in-process MCP tools: `attach_finding` and `add_node` (ungated, provisional growth); gated `add_edge`, `propose_fact`, `update_node/edge`, `delete_node/edge`, `merge`, `move_evidence`, `close_node`, `supersede`, `compress` |
| `harness/stream.py` | SDK messages → events |
| `harness/sdk.py` | the real harness: one client per frame turn, `resume` per cycle |
| `harness/scripted.py` | the scripted harness and approver that tests replay with |
| `harness/events.py` | the event types and sinks (list, JSONL, fanout) |
| `chat.py` | the default connection, held open |
| `graph_driver.py` | one session's thread: start a cycle, exchange, snapshot, seed a fork |
| `session.py` | session records and the store (`sessions/`) |
| `commands.py` | parsing and the command set: modes + built-ins + pass-through |
| `runner.py` | the one task that owns the clients and executes what was typed |
| `tui/` | Textual: transcript, approval and question modals, graph panel, status |

## Verify

```bash
.venv/bin/python -m pytest tests -q                          # 58 tests, no model
.venv/bin/python scripts/spikes/spike_09_live_cycle.py       # one real cycle on Haiku
.venv/bin/python scripts/spikes/spike_10_live_chat.py        # chat, tool, interrupt, follow-up
```

Both spikes passed on 2026-09-19. Their event logs land under a temporary `sessions/`.

## What a run writes

`sessions/checkpoints.sqlite` holds every graph checkpoint; `sessions/<name>.json` is the
session record; `sessions/<name>/events.jsonl` is every event the session emitted.
`sessions/graph/ops.jsonl` is the graph itself — one append-only log the whole project
shares. A session's checkpoint carries only its working set (which cycle, which frame, which
conversation, what was said); every finding, assumption, rival, fact, proposal, decision and
spend entry is a line in the log, stamped with the session that wrote it. Cycle numbers are
allocated from the log, so ids are unique across sessions, and a `/fork` shares the graph.
A later line with the same id replaces the earlier one; nothing is ever removed from the file.

The graph has three layers. Things: `entity` nodes (file, module, function, service, config,
concept) the surveys name with `add_node`, free and provisional. Claims: assumptions, counters
and observations, one `claim` kind with a role. Evidence: findings, each hanging off one node.
Facts are the user's words and the only authority. Relations between nodes (`depends_on`,
`requires`, `calls`, `defines`, `configures`, `part_of`, `supports`, `contradicts`, or
`relates_to` with a proposed new kind) are put to the user at the call, as is every edit,
merge, move, delete, verdict, supersession and compression. A gated call is dry-run first, so
one the handler would refuse never reaches the user, and what the dry run says it would do is
what the approval modal shows. `delete_node` refuses while evidence or relations remain;
`merge` moves them. The package renders the applied graph: a merged node is gone, a compressed
set is its summary, a superseded claim is marked.

The package is a neighbourhood, not the whole graph: the facts, the summaries, and the claims
and entities within `package_hops` (2) of the cycle's question and of what its words match
render in full; every other live node is one line under ELSEWHERE. Two free tools reach the
rest: `graph_search(text)` and `graph_neighbours(id, depth)`. The synthesis brief names what is
due for compression each cycle — nodes the user closed earlier, and provisional nodes older
than `stale_after` (2) cycles that nothing approved connects to.

The side panel is a graph browser: `ctrl+b` or `/panel view outline|kind|status` switches the
view, and selecting a node shows it in full in the transcript, as `/show node <id>` does;
`/show neighbours <id> [depth]` and `/show search <text>` are the same reads the agent has. SDK
conversations stay where the CLI keeps them (`~/.claude/projects/<cwd>/`); the ids are in
the session record (chat) and the graph state (the open cycle).
