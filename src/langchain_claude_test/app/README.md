# app — the Claude shell with a provenance cycle behind `/graph`

**Status: built and running.** The four-frame cycle runs live over the Claude Agent SDK, the
plain Claude connection is the default, sessions persist and resume, interrupts work, and the
Textual UI streams thinking, text and tool calls. One thing is deliberately not built: the
effects of the gated graph alterations, which are proposed for review in
`docs/design/thought-graph-proposal-2026-09-19.md`.

This package supersedes `graph_v2/`, `session/` and `ledger/` and imports none of them.

## Run

```bash
uv run langchain-claude-test            # a new session in this directory
uv run langchain-claude-test mywork     # open or create the session "mywork"
uv run langchain-claude-test --cwd /path/to/repo --model sonnet
```

Plain text goes to the focused mode. `/graph <query>` starts a cycle; plain text while the
focus is the graph continues its synthesis conversation; `/chat` leaves it. `/help` lists the
rest. Modes come from `modes.toml` in the working directory: every table there is a `/<name>`
command with its own system prompt and tools.

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

## Layout

| Module | Owns |
|---|---|
| `config.py` | budgets and prices (every unchosen number is in `PROVISIONAL`), model defaults, modes, `AppConfig` |
| `graph/state.py` | the records and which channels accumulate; the checkpoint allowlist |
| `graph/budget.py` | pool names and spend arithmetic — pure |
| `graph/surface.py` | which built-ins and which in-graph tools exist per frame; which are gated |
| `graph/payloads.py` | the structured answer each frame must return |
| `graph/package.py` | the text a cycle opens with — the compaction |
| `graph/thought.py` | the networkx view over the records; invariants; an outline for the panel |
| `graph/nodes/` | the four frames: orientate, assume (a two-loop subgraph), antithesis (one rival per reading), synthesis |
| `graph/graph.py` | the edge list, the SQLite checkpointer, `check_topology()`, `render()` |
| `harness/protocol.py` | `StageRequest` / `TurnResult`, `Approver` / `Verdict`, `FrameInterrupted` |
| `harness/meter.py` | prices a call and charges before it runs |
| `harness/hooks.py` | `PreToolUse` = meter + surface; `PostToolUse` = record + running count; `can_use_tool` = the human gate |
| `harness/tools.py` | the in-process MCP tools: `attach_finding` and the gated alterations |
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
.venv/bin/python -m pytest tests/app -q                      # 23 tests, no model
.venv/bin/python scripts/spikes/spike_09_live_cycle.py       # one real cycle on Haiku
.venv/bin/python scripts/spikes/spike_10_live_chat.py        # chat, tool, interrupt, follow-up
```

Both spikes passed on 2026-09-19. Their event logs land under a temporary `sessions/`.

## What a run writes

`sessions/checkpoints.sqlite` holds every graph checkpoint; `sessions/<name>.json` is the
session record; `sessions/<name>/events.jsonl` is every event the session emitted. SDK
conversations stay where the CLI keeps them (`~/.claude/projects/<cwd>/`); the ids are in
the session record (chat) and the graph state (the open cycle).
