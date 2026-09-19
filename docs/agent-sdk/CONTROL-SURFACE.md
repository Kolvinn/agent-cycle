# The Agent SDK control surface (Python)

What you can override, what you can't, and exactly where each lever lives.

Source: every page under `docs/agent-sdk/` (32 Agent SDK pages) plus `docs/agent-sdk/_support/`
(35 Claude Code reference pages). Fetched 2026-09-19 from `https://code.claude.com/docs/llms.txt`.

**Revision 2.** Every claim in revision 1 was re-tested against the corpus by constructing its
antithesis and looking for contradicting text. Twenty-five claims were challenged; eight were
wrong, nine were overstated, eight survived intact. See the [antithesis log](#appendix-b-antithesis-log)
for what changed and why. The corrections are load-bearing — revision 1 understated Python's reach
by a wide margin.

---

## 0. The one fact that explains everything

**By default, the Agent SDK is not a library that talks to the API. It is a supervisor for a
`claude` CLI subprocess.**

```
your python process                    subprocess                    network
┌─────────────────────┐   stdio    ┌──────────────────┐   HTTPS   ┌──────────────┐
│ claude_agent_sdk    │◄──JSONL───►│ bundled `claude` │──────────►│ api.anthropic│
│  - query()          │            │  - agent loop    │           └──────────────┘
│  - your hooks       │            │  - system prompt │
│  - your can_use_tool│            │  - tool impls    │
│  - your @tool fns   │            │  - permissions   │
│  - your SessionStore│            │  - compaction    │
└─────────────────────┘            │  - settings merge│
                                   └────────┬─────────┘
                                            │ writes
                                   ~/.claude/projects/<cwd>/*.jsonl
```

"By default" is doing real work: the `Transport` ABC lets you replace the subprocess channel
entirely (§10), and your in-process MCP tools run inside *your* process, not the CLI's. The
subprocess is the default topology, not a law of the SDK.

Consequences that follow:

- **Anything the CLI decides, you influence but do not implement.** The agent loop, compaction, the
  permission evaluation order, `Bash` AST parsing, retry policy — inside a binary pinned to the SDK
  package version. You get hook points *around* those, not *inside* them.
- **Anything that runs as a callback runs in your process.** Hooks, `can_use_tool`, `@tool`
  handlers, `SessionStore`. This is where your real leverage is.
- **Configuration crosses the boundary three ways, and the middle one is the one people miss:**
  typed options, **the `settings` JSON string (231 keys, outranking every filesystem tier)**, and
  env vars. `extra_args` is the escape hatch for untyped CLI flags.
- **Updating the CLI = updating the pip package** (unless you point `cli_path` at your own install,
  in which case you inherit *that* install's defaults, including which tools exist).

### 0.1 Version numbers do not line up — check, don't infer

TypeScript aligns: SDK `0.3.N` bundles Claude Code `2.1.N`. **Python does not.** Observed pairings:

| Python SDK | bundles Claude Code | offset |
|---|---|---|
| 0.2.137 | ≥ 2.1.223 | +86 |
| 0.2.150 | ≥ 2.1.257 | +107 |
| 0.2.153 | ≥ 2.1.265 | +112 |

The offset drifts. When a doc says "requires Claude Code v2.1.NNN", you **cannot** compute the
Python SDK version that satisfies it — find the sentence that names the Python version, or test.

---

## 1. The layer map

| # | Layer | Lives where | You own it? |
|---|-------|-------------|-------------|
| 1 | Managed policy settings | MDM plist / registry / managed settings file / server-fetched | **Endpoint-managed:** removable at the host, not from the SDK. **Server-managed:** an org Owner's call, not yours at all. |
| 2 | Programmatic options + **`settings=` JSON** | your code | **Yes.** The flag-settings tier — 231 keys. |
| 3 | Local settings | `<cwd>/.claude/settings.local.json` | Yes, via `setting_sources` |
| 4 | Project settings | `<cwd>/.claude/settings.json`, `.mcp.json`, `.claude/**` | Yes, via `setting_sources` |
| 5 | User settings | `~/.claude/settings.json`, `~/.claude/**` | Yes, via `setting_sources` |
| 6 | Env vars | `options.env` (merged over inherited, in Python) | Yes |
| 7 | Unconditional inputs | `~/.claude.json`, auto-memory, claude.ai connectors, sandbox credential rules | Each has its own opt-out — §2.2 |

Merge precedence, highest first:
`managed policy > programmatic options/settings > local > project > user`.

### 1.1 Settings precedence is not permission precedence — do not conflate them

This is the correction that matters most in this section. "Your code beats the filesystem" is true
of **settings merging** and false of **permission evaluation**.

- A project `settings.json` **deny** rule is *not* overridden by your `allowed_tools`. Deny is
  step 2 of the evaluation flow; allow is step 5. **Deny always wins**, regardless of which tier it
  came from (§4.1).
- Likewise an **ask** rule from a settings file routes to your callback even under
  `bypassPermissions`.

So a project you don't control can *restrict* your agent no matter what you pass programmatically.
It cannot *loosen* it: `permissions.defaultMode` set to `"auto"` or `"bypassPermissions"` in
`.claude/settings.json` or `.claude/settings.local.json` **does not take effect** — those two values
are only honoured from higher tiers.

Rule of thumb: **your code beats the filesystem for configuration; the filesystem can still veto
you on permissions.**

### 1.2 The `settings` string is Python's widest lever

```python
ClaudeAgentOptions(settings='{"autoCompactWindow": "500k", "outputStyle": "Explanatory"}')
# or a path: ClaudeAgentOptions(settings="/etc/myagent/settings.json")
```

231 documented keys, applied at a tier above user/project/local. Anything in
`_support/settings-reference.md` with no corresponding `ClaudeAgentOptions` field — `outputStyle`,
`autoCompactWindow`, `effortLevel`, `modelPricing`, `promptCacheTtl`, `autoMemoryEnabled`,
`disableClaudeAiConnectors`, the whole `permissions` and `hooks` blocks — is reachable this way.

Python accepts a **path or an inline JSON string**; TypeScript additionally accepts a dict. That is
an ergonomics difference, not a capability one.

---

## 2. Configuration loading

### 2.1 `setting_sources` is the master switch

```python
ClaudeAgentOptions(setting_sources=[])            # nothing from disk
ClaudeAgentOptions(setting_sources=["project"])   # only <cwd>/.claude
# omitted  →  ["user", "project", "local"]  (matches the CLI)
```

| Source | Loads |
|--------|-------|
| `project` | `<cwd>/.claude/settings.json`, hooks; `CLAUDE.md` + `.claude/rules/*.md` from `<cwd>` **and every parent**; skills/commands/subagents from `<cwd>` and parents **up to the repo root**, plus `.claude/{skills,commands,agents}/` of every `add_dirs` entry; `.mcp.json` |
| `user` | `~/.claude/settings.json`, `~/.claude/CLAUDE.md`, `~/.claude/rules/*.md`, `~/.claude/{skills,commands,agents}/` |
| `local` | `.claude/settings.local.json`, `CLAUDE.local.md` from `<cwd>` and parents |

Gotchas:

- **`cwd` is load-bearing.** It decides project settings, skill discovery, session storage
  location, and the `project_key` your `SessionStore` sees. There is **no SDK setter** — but do not
  assume it is frozen: a `CwdChanged` hook event exists, so the CLI can change the working directory
  mid-session. Treat `cwd` as "set at start, may drift", not "immutable".
- **Project `settings.json` and hooks load only from `<cwd>/.claude/`** — no parent fallback. But
  `CLAUDE.md`, rules, skills and agents *do* walk up. Asymmetric.
- **Python-only bug:** SDK ≤ 0.1.59 treated `setting_sources=[]` as omitted. An "isolated" agent on
  an old pin is not isolated.
- **Python-only default shift:** set `skills=` with `setting_sources` unset and only `user` +
  `project` load — `local` is silently dropped. Set it explicitly.
- Child-directory `CLAUDE.md` files load **lazily**, when the agent first reads a file in that
  subtree. Context grows mid-run without you acting.
- **No precedence between CLAUDE.md levels** — they concatenate. If user and project instructions
  conflict, the model arbitrates. State precedence explicitly in the more specific file.

### 2.2 The five things `setting_sources=[]` does *not* turn off

| Input | Disable with |
|-------|--------------|
| Managed policy settings | Remove from the host. **Server-managed settings cannot be disabled from the SDK at all** |
| `~/.claude.json` global config | `env={"CLAUDE_CONFIG_DIR": "/per/tenant/dir"}` |
| Auto-memory at `~/.claude/projects/<project>/memory/` — **injected into the system prompt** | `env={"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"}`, or `settings='{"autoMemoryEnabled": false}'` |
| claude.ai MCP connectors (when auth'd with a claude.ai login) | `strict_mcp_config=True`, `settings='{"disableClaudeAiConnectors": true}'`, or `env={"ENABLE_CLAUDEAI_MCP_SERVERS": "false"}`. **`mcp_servers={}` does not suppress them.** |
| `sandbox.credentials` deny/mask entries in `~/.claude/settings.json` | Delete them from the file |

**The multi-tenant recipe**, all four required:

```python
ClaudeAgentOptions(
    cwd=tenant_dir,
    setting_sources=[],
    env={"CLAUDE_CONFIG_DIR": config_dir, "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"},
)
```
…plus per-tenant egress rules at your proxy. Python **merges** `env` over the inherited environment
(TS *replaces* it), so `PATH` and `ANTHROPIC_API_KEY` survive for free.

---

## 3. The system prompt

### 3.1 Four starting points

| `system_prompt=` | Result |
|---|---|
| unset (**the default**) | **Minimal prompt.** Tool-calling scaffolding only. No safety instructions, no environment context, no coding guidance. Differs from `claude -p`. |
| `"a string"` | Exactly your string. |
| `{"type": "custom", "prompt": "...", "snapshot": False}` | Same, plus the `snapshot` knob. SDK ≥ 0.2.153. |
| `{"type": "file", "path": "..."}` | Same, read from disk. **Use for anything large.** |
| `{"type": "preset", "preset": "claude_code", "append": "..."}` | The Claude Code prompt, optionally extended. |

Agent SDK v0.1.0 **removed the preset as the default**. If you migrated from `claude-code-sdk` and
behaviour changed, this is why.

**On "a custom prompt means you own safety":** you own *prompt-level* safety guidance — the
comparison table lists "Built-in safety: must be added". You do **not** lose the harness guardrails.
The permission system, critical-path checks on `rm`/`rmdir`, protected paths, and `Bash` AST parsing
are enforced by the CLI regardless of what your system prompt says. A custom prompt makes the agent
less *well-advised*, not unguarded.

### 3.2 The preset is not opaque, and not append-only

Revision 1 claimed you could only append to the preset. That is wrong in three distinct ways:

1. **An output style removes a section.** A custom output style *leaves out* the preset's software
   engineering instructions and substitutes yours. `keep-coding-instructions: true` in the
   frontmatter keeps them instead. This is surgical removal of a named preset section.
2. **`CLAUDE_CODE_SIMPLE_SYSTEM_PROMPT=1` swaps the whole prompt** for a shorter one with
   abbreviated tool descriptions, on any model. Set `0`/`false`/`no`/`off` to force it off where a
   server experiment would enable it. Tools, hooks, MCP and CLAUDE.md discovery stay on.
   (Note: `keep-coding-instructions` has no effect in a short-prompt session — those instructions
   only exist in the full prompt.)
3. **`exclude_dynamic_sections: True` removes the dynamic block**, relocating cwd / git-repo flag /
   platform / shell / OS version / auto-memory paths into the first user message so a fleet across
   directories shares one cache entry. Trade-off: that context now carries user-message weight.
   Preset object form only — silently ignored on a custom prompt.

What remains genuinely locked: you cannot *read* the preset's text, reorder it, or edit a section
you have no named switch for.

One real behavioural fork hiding behind the prompt choice: **on Opus 5 with the preset, Claude Code
injects an anti-delegation line** telling Claude not to call the Agent tool unless asked. With a
custom prompt it does not, and you must add that instruction yourself.

Mechanical limit: the string form goes on the subprocess argv. >~128 KB fails at spawn on Linux
(`Argument list too long`); Windows caps the whole command line at ~32 KB. Use `{"type": "file"}`.
TS's `SYSTEM_PROMPT_DYNAMIC_BOUNDARY` array form has no Python equivalent.

### 3.3 The snapshot rule

**Claude Code records the system prompt on a session's first request and reuses that record until
the session is compacted.** Pass a different `append` on `resume` and Claude does not see it.

Workarounds, best first:
1. Put the instruction in your next **user message**.
2. Return `additionalContext` from a `UserPromptSubmit` or `PostToolUse` hook — inserted where the
   hook fired, recorded prompt untouched.
3. `snapshot: False` — rebuilds every request. **Don't ship it:** kills the session prompt cache,
   and where the API enforces preserved thinking, loses Claude's earlier thinking.

**Recording is the default, but not universally.** Bare mode (`--bare` via `extra_args`, or
`CLAUDE_CODE_SIMPLE=1`) leaves recording *off* unless you set `snapshot: True`. And before Claude
Code v2.1.268, sessions that don't fetch feature flags — including **Bedrock, Google Agent Platform
and Microsoft Foundry** — rebuilt the prompt every request and ignored `snapshot` entirely.

So the corollary is conditional: *on first-party API and current versions*, the system prompt is a
session-creation-time decision. On those three providers with an older CLI, it isn't. Don't build
an abstraction that assumes either behaviour without pinning.

### 3.4 Output styles are reachable from Python at runtime

Revision 1 said Python could only set an output style at startup. Wrong — there are four paths, and
three of them work mid-session:

| Path | Python? | Timing |
|---|---|---|
| `settings='{"outputStyle": "Explanatory"}'` | ✅ | startup |
| Edit `.claude/settings.local.json` on disk yourself | ✅ | **next message** (v2.1.251+; before that, needed `/clear` or a new session) |
| Send `/output-style concise` as a prompt | ✅ if the command is in `slash_commands` — requires v2.1.269+ | next message |
| `/config outputStyle=...` — the `key=value` form is documented to work in non-interactive `-p` mode | ✅ | next message |
| TS `updateSettings('localSettings', {...})` | ❌ | next request |

TS's `updateSettings()` is a convenience wrapper over path 2, not a unique capability. Python
reaches the same tier by writing the file.

Output styles still require `setting_sources` to include `user` or `project` to be discovered.

---

## 4. Permissions

### 4.1 The evaluation order

```
tool call
   │
   1. HOOKS ─────────────► deny wins immediately. `allow` does NOT skip steps 2–3.
   │                        Cannot approve rm/rmdir on a critical path.
   2. DENY RULES ────────► disallowed_tools + settings deny, from ANY tier. Wins even in bypassPermissions.
   │                        Bare names ("Bash") already removed the tool from context upstream.
   3. ASK RULES ─────────► settings `ask` rules → falls to can_use_tool even in bypassPermissions.
   4. PERMISSION MODE ───► bypassPermissions approves; acceptEdits approves file ops;
   │                        plan routes writes to the callback; others fall through.
   5. ALLOW RULES ───────► allowed_tools + settings allow, plus self-approving calls
   │                        (reads inside cwd, read-only Bash). Never approves critical-path rm.
   6. can_use_tool ──────► your callback. In dontAsk this step is SKIPPED and the call is denied.
```

### 4.2 `can_use_tool` is a prompt handler, not a gate

Anything approved at steps 4 or 5 never reaches it — **except the never-auto-approved set in §4.3,
which reaches it even when an allow rule matches.** With that exception stated, the rule holds:
`allowed_tools=["Read"]` means your callback never sees an ordinary `Read`;
`permission_mode="bypassPermissions"` means it sees almost nothing. The docs carry this warning in
three separate places.

**A check that must run on every tool call has to be a `PreToolUse` hook.** Hooks are step 1 — before
rules, before modes — and a hook `deny` holds even under `bypassPermissions`.

Availability vs. permission:

| Option | Availability (in context?) | Permission (approved?) |
|---|---|---|
| `tools=["Read","Grep"]` | ✅ removes every other built-in | – |
| `tools=[]` | ✅ removes all built-ins, MCP tools survive | – |
| `disallowed_tools=["Bash"]` (bare) | ✅ removes it | – |
| `disallowed_tools=["Bash(rm *)"]` (scoped) | – | ✅ denies matching calls in every mode |
| `allowed_tools=[...]` | ⚠️ **one exception, below** | ✅ auto-approves; does not restrict |

**The exception:** naming one of the task-tracking tools (`TodoWrite`, `TaskCreate`, `TaskGet`,
`TaskUpdate`, `TaskList`) in `allowed_tools` **opts the session in**, adding them to Claude's
context on models where they're otherwise absent (§6.3). So `allowed_tools` is an approval list
that can also *add availability* in exactly that one case. Everywhere else it never restricts:
`allowed_tools=["Read"]` with `bypassPermissions` still approves `Bash`, `Write`, everything.

### 4.3 Actions no mode auto-approves — six, not five

Even `bypassPermissions` routes these to your callback (or denies them in `dontAsk`):

1. Tools matched by an explicit **`ask` rule**
2. **Connector tools** your organization set to `ask`
3. **Tools requiring user interaction:** `AskUserQuestion`, and MCP tools marked
   `_meta["anthropic/requiresUserInteraction"]`
4. **`rm`/`rmdir` targeting a critical path** — no allow rule and no `PreToolUse` `"allow"` clears it
5. **Cross-session messaging safeguards**
6. **Reads outside the working directories** while
   `permissions.blockReadsOutsideWorkingDirectories` is on — recognized file-reading Bash commands
   prompt even in `auto` and `bypassPermissions`, as does any unsandboxed retry needing approval.
   A command the shell parser can't trace (multiple `cd`s, a subshell) prompts the same way even
   when it names no outside path. Requires v2.1.257+.

These are enforced in the CLI. You cannot turn them off.

### 4.4 Mid-session changes

```python
await client.set_permission_mode("acceptEdits")
await client.set_model("claude-opus-5")   # None resets to Claude Code's default, not your `model=`
```

**The requirement in Python is `ClaudeSDKClient`, not "pass an async generator".** `ClaudeSDKClient`
connects in streaming mode regardless of whether you hand `query()` a string or a generator — which
is why its documented example calls `client.query("Count from 1 to 100")` with a plain string and
then `interrupt()`. The standalone `query()` function is what lacks the setters.

Beyond those two setters, Python's runtime-mutation options are narrower than TS's
`applyFlagSettings()`, but not empty:
- Write `.claude/settings.local.json` yourself → applies next message (§3.4).
- Return `PermissionUpdate` objects from `can_use_tool` with `destination="localSettings"` →
  persists rules across sessions.
- Keep mutable state in your process and read it from a `PreToolUse` hook → for policy this is the
  better pattern anyway, since it also covers the calls `can_use_tool` never sees.

### 4.5 Persisting a user's "always allow"

```python
persist = [s for s in context.suggestions if s.destination == "localSettings"]
return PermissionResultAllow(updated_input=input_data, updated_permissions=persist)
```
Requires `claude-agent-sdk` ≥ 0.1.80.

---

## 5. Hooks

### 5.1 Python has 10 of 33 events — as *callbacks*. All 33 are reachable.

This is the correction that most changes the Python-vs-TypeScript story.

All 33 hook events are **CLI-level**, not SDK-level, and registrable from `.claude/settings.json`
with five handler types: `command`, `http`, `mcp_tool`, `prompt`, `agent`. Filesystem hooks and
programmatic hooks **run side by side**, and Python loads them via `setting_sources`.

**Python's 10 programmatic events:** `PreToolUse` · `PostToolUse` · `PostToolUseFailure` ·
`UserPromptSubmit` · `Stop` · `SubagentStart` · `SubagentStop` · `PreCompact` · `Notification` ·
`PermissionRequest`

**The other 23** — `SessionStart` · `SessionEnd` · `Setup` · `PostCompact` · `PostToolBatch` ·
`MessageDisplay` · `StopFailure` · `PreModelSwitch` · `PostModelSwitch` · `PermissionDenied` ·
`UserPromptExpansion` · `TaskCreated` · `TaskCompleted` · `Elicitation` · `ElicitationResult` ·
`ConfigChange` · `InstructionsLoaded` · `CwdChanged` · `FileChanged` · `DirectoryAdded` ·
`WorktreeCreate` · `WorktreeRemove` · `TeammateIdle` — fire fine in Python sessions. You just
register them in a settings file rather than passing a Python function.

What you actually lose, registering them that way:

| | Programmatic callback | Filesystem hook |
|---|---|---|
| Closes over your app state | ✅ | ❌ |
| Returns a Python object | ✅ | ❌ (JSON on stdout) |
| Latency | in-process | process spawn, or a network hop |
| Structured decisions | ✅ | ✅ (JSON output, same schema) |

**The `http` handler type is the good workaround nobody mentions:** run an endpoint in your own
application and register it for the missing events. You get in-process handling with a network hop
instead of a subprocess spawn — state sharing restored, latency mostly restored.

So: an **ergonomics and latency** gap, not a capability gap. Revision 1's "10 vs 30" framing was
misleading.

### 5.2 What a hook can do

```python
{
  "systemMessage": "shown to the user",          # top-level, any event
  "continue_": False,                            # underscore; becomes `continue` on the wire
  "stopReason": "...",
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow" | "deny" | "ask" | "defer",
    "permissionDecisionReason": "shown to the model",
    "updatedInput": {...},                       # rewrite the tool's arguments
    "additionalContext": "...",                  # inject into the conversation
  }
}
```
`PostToolUse` additionally takes `updatedToolOutput`, which **replaces what Claude sees** for any
tool in both SDKs (`updatedMCPToolOutput` is the deprecated MCP-only ancestor).

Fire-and-forget: `{"async_": True, "asyncTimeout": 30000}` — the loop doesn't wait, so you cannot
block, modify, or inject; side effects only.

### 5.3 Precedence, concurrency, matchers

- All matching hooks for an event run **in parallel**, completion order non-deterministic.
- Decision precedence: **`deny` > `defer` > `ask` > `allow`**. One `deny` blocks regardless.
- `updatedInput` + `"allow"` = rewrite and auto-approve. `updatedInput` with `"defer"` is
  **silently dropped**.
- **`matcher` does not always match tool names.** It matches a *different field per event type*:
  tool name for tool hooks, notification type for `Notification`, and **`Stop` ignores matchers
  entirely**. Within tool hooks it still never matches file paths or argument values — filter on
  `tool_input["file_path"]` in the body.

### 5.4 Timeouts differ per event

For Python's 10 programmatic events: **600s default, 30s for `UserPromptSubmit`.** If you register
the other 23 as filesystem hooks, their own defaults apply — notably 10s for `MessageDisplay`, 30s
for `PreModelSwitch`/`PostModelSwitch`, and a 1.5s shutdown budget for `SessionEnd`.

On timeout the callback is cancelled and its output discarded, then:

| Event | What happens |
|---|---|
| `PreToolUse` | Tool does **not** run; Claude gets a "hook didn't respond" result; turn continues |
| `PostToolUse` / `PostToolUseFailure` | Result kept, turn continues |
| `UserPromptSubmit` | **Prompt is blocked.** A timed-out policy gate never fails open. |
| `Stop` / `SubagentStop` | Counts as no decision → treated as allow; your other hooks' decisions still apply |
| Others | Logged, continue |

### 5.5 The `defer` escape hatch

`permissionDecision: "defer"` from `PreToolUse` **ends the query** with
`stop_reason: "tool_deferred"` and `deferred_tool_use` on the result carrying the pending tool's
id/name/input. Your process can exit, surface the request in your own UI, and resume later. Use
this whenever a human decision might outlive your process — `can_use_tool` pauses **indefinitely**
and permission prompts never time out.

### 5.6 The dummy-hook workaround is scoped to `query()`

```python
async def dummy_hook(input_data, tool_use_id, context):
    return {"continue_": True}
```

All three occurrences in the docs are in `query()` + `prompt_stream()` (async-generator) examples,
labelled "Required workaround: dummy hook keeps the stream open for `can_use_tool`". The
`ClaudeSDKClient` permission example uses `can_use_tool` with **no dummy hook at all**.

So: needed for streaming-generator `query()`, not for `ClaudeSDKClient`. If `can_use_tool` never
fires, check which of the two you're on before adding the workaround.

---

## 6. Tools

### 6.1 Built-ins: you can't change the code, but you can change almost everything about the call

`Read` `Write` `Edit` `NotebookEdit` · `Glob` `Grep` · `Bash` · `WebSearch` `WebFetch` ·
`ToolSearch` · `Agent` `Skill` `AskUserQuestion` `TaskCreate` `TaskUpdate` `TaskGet` `TaskList`
`TodoWrite` · `Monitor` `TaskOutput` `TaskStop` `ExitPlanMode` `ListMcpResources`
`ReadMcpResource`.

Implementations live in the CLI binary. You cannot patch them. You can:
- **remove** (`tools=[...]`, bare `disallowed_tools`)
- **scope** (`disallowed_tools=["Bash(rm *)"]`, `Edit(//secrets/**)`)
- **rewrite arguments** (`PreToolUse` → `updatedInput`, `can_use_tool` → `updated_input`)
- **rewrite output** (`PostToolUse` → `updatedToolOutput`)
- **alias away** — TS only. `toolAliases: {Bash: "mcp__workspace__bash"}` has no Python equivalent;
  in Python, `disallowed_tools=["Bash"]` plus your own MCP tool under a different name is
  functionally equivalent, cosmetically worse.

Between those, "you cannot patch built-ins" is technically true and practically soft.

### 6.2 The `Agent` / `Task` naming trap

The tool is `"Agent"` in `tool_use` blocks but reports as `"Task"` in the init message's `tools`
list. Before v2.1.63, `tool_use` blocks also said `"Task"`. **Match both strings.**

### 6.3 Task/todo tools are model-gated

Present by default **only** on Claude 3.x, Opus 4–4.7, Sonnet 4–4.6, Haiku 4.5. On anything newer —
or any unrecognized model ID — absent unless you opt in via `allowed_tools`, `tools`, or
`env={"CLAUDE_CODE_ENABLE_TODO_TOOLS": "1"}`. **A progress UI reading `TaskCreate`/`TaskUpdate` goes
blank on a model upgrade.** Opt in explicitly.

The streamed `tool_use.input` is the **raw shape the model emitted**. Claude Code repairs
`id`/`task_id` → `taskId` and `active_form` → `activeForm` before execution, but **the repair is not
reflected in the stream**:

```python
task_id = inp.get("taskId") or inp.get("id") or inp.get("task_id")
```

### 6.4 Your own tools: the in-process MCP server

```python
@tool("get_temperature", "Get current temperature", {"latitude": float, "longitude": float})
async def get_temperature(args): ...

server = create_sdk_mcp_server(name="weather", version="1.0.0", tools=[get_temperature])
options = ClaudeAgentOptions(
    mcp_servers={"weather": server},
    allowed_tools=["mcp__weather__get_temperature"],   # or "mcp__weather__*"
)
```
Wire name: `mcp__{server_key}__{tool_name}` — the key in `mcp_servers`, not the server's `name`.

| Capability | Python in-process | Reach it via |
|---|---|---|
| Optional parameters | not via the `{"name": type}` shorthand (every key is required) | **Pass a full JSON Schema dict** with your own `required` list — fully supported |
| Enums, ranges, nested objects | same | same — full JSON Schema |
| `structuredContent` | **dropped** (decorator forwards only `content` + `is_error`) | standalone MCP server process |
| `resource.blob` (binary) | **dropped**, warning logged | standalone server |
| `audio` blocks | **dropped**, warning logged (TS saves to disk) | – |
| `resource_link` → `resourceLinks` on the user message | **never produced** (flattened to text first) | standalone server |
| `alwaysLoad` | not on `tool()`/`create_sdk_mcp_server()` | set it on the server entry in `.mcp.json`/settings, or `ENABLE_TOOL_SEARCH=false` |
| Per-server tool timeout | not on `create_sdk_mcp_server()` | `env={"MCP_TOOL_TIMEOUT": "..."}` (global) |

So the honest reading: the *schema* limits are shorthand limits with a documented full-power escape
hatch; the *result-shape* limits (`structuredContent`, blobs, audio, resource links) are real, and
the workaround for all of them is the same — run the server out of process.

Errors: an uncaught exception is caught by the in-process server, converted to an error result with
the raw message, and **the loop continues**. Return `{"content": [...], "is_error": True}` to
compose what Claude reads. Python uses `is_error`; TS uses `isError`.

Parallelism: custom tools are **sequential by default**. `annotations=ToolAnnotations(readOnlyHint=True)`
lets Claude batch them. It's a hint — nothing stops a `readOnlyHint=True` tool from writing to disk.

### 6.5 Tool search is on by default

Definitions are **withheld**; Claude searches and loads up to 5 at a time. On unless: unsupported
model, non-first-party `ANTHROPIC_BASE_URL` (proxies drop `tool_reference` blocks), Azure-hosted
Foundry (server-side rejection, unoverridable), or pre-4.5 models on Google Agent Platform.

`env={"ENABLE_TOOL_SEARCH": ...}` — unset / `true` / `false` / `auto` (10% of context) / `auto:N`.
`CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS` forces it off and cannot be overridden.

With <10 tools, tool search is a net loss (extra round-trip). Small scoped agent →
`ENABLE_TOOL_SEARCH=false`.

---

## 7. Subagents

`agents={"name": AgentDefinition(...)}` overrides a same-named filesystem agent. Fields:
`description`, `prompt`, `tools`, `disallowedTools`, `model`, `skills`, `memory`, `mcpServers`,
`initialPrompt`, `maxTurns`, `background`, `effort`, `permissionMode`.

**Python's `AgentDefinition` uses camelCase** (`disallowedTools`, `permissionMode`, `maxTurns`) to
match the wire format — unlike `ClaudeAgentOptions`, which is snake_case. It's a dataclass, so a
snake_case kwarg raises `TypeError`. Missing in Python: `omitClaudeMd`,
`criticalSystemReminder_EXPERIMENTAL`.

### What a subagent inherits

| Receives | Does not receive |
|---|---|
| Its own `prompt` + the Agent tool's prompt string | The parent's conversation history or tool results |
| Project CLAUDE.md (via `setting_sources`) | The parent's system prompt |
| Tool definitions (parent's, or the `tools` subset) | Preloaded skills, unless listed in `skills` |
| The main session's extended-thinking config | – |
| A list of other named agents, if it has `SendMessage` | – |

**The only content *you pass* is the Agent tool's prompt string.** (The subagent still gets
CLAUDE.md, tools, and thinking config from configuration — the restriction is on dynamic parent
state.) Put file paths, error messages, and decisions in the prompt explicitly.

**Permission mode inheritance is locked:** a subagent runs in the parent's mode unless
`AgentDefinition.permissionMode` is set *and* the parent is in `default`/`dontAsk`/`plan`. Claude
Code **never** honours a `"bypassPermissions"` value from an AgentDefinition — a subagent is in
bypass only when the parent is. Conversely, a parent in bypass grants every subagent full
autonomous access.

**Subagent output is scanned** (v2.1.210+): `<system-reminder>`-style control tags get a backslash
inserted, `Human:`/`Assistant:` line starts get escaped, and a `[harness: ...]` marker line is
prepended on a match. Nothing is removed or reworded — but account for the marker if you parse
output.

### You have more control over spawning than "Claude decides"

Claude chooses when and how many to spawn, and subagents spawn subagents — but:

```python
ClaudeAgentOptions(
    env={
        "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "1",   # default 3; 1 = no nesting
        "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": "5",   # default 20
        "CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS": "1" # no built-in general-purpose
    },
    disallowed_tools=["Agent"],                         # or: no delegation at all
    max_budget_usd=5.0,                                 # counts subagent spend
)
```
`background: True` on a definition forces background execution regardless of what Claude requests.
Depth/concurrency are env-only; the caps need SDK ≥ 0.2.127.

**Resuming a subagent:** capture `session_id`, parse `agentId: <id>` from the Agent tool result
text, then `resume=session_id` naming the agent id in the prompt. Built-in `Explore` and `Plan` are
one-shot and return no `agentId`.

**`AskUserQuestion` is unavailable in subagents.** User input must happen on the main thread.

---

## 8. Skills, commands, plugins

> **No programmatic API for registering a skill.** Skills are `SKILL.md` files.

But **filesystem-only does not mean static.** Your Python process can write
`.claude/skills/<name>/SKILL.md` at runtime and start a session that discovers it. What Python
lacks is TS's `reloadSkills()`, so a skill created mid-session needs a **new session** to appear —
and a brand-new `.claude/skills/` *directory* needs a restart even in TS, since the watcher only
covers directories that existed at session start.

You control which are enabled:

```python
skills="all"           # every discovered skill
skills=["pdf","docx"]  # exact names only — no wildcards
skills=[]              # none
# omitted → discovered user+project skills enabled (CLI parity)
```
Invalid names (`docs:*`, empty, whitespace-padded, parens/commas) raise `ValueError` **before** the
subprocess starts (SDK ≥ 0.2.129).

Setting `skills` auto-adds `Skill` to `allowed_tools` — but if you also pass an explicit `tools`
list, include `"Skill"` yourself.

**Restricting `skills` does not restrict dispatch.** `/<name>` runs a user-invocable skill even when
it's not in your list. To make one genuinely unreachable it must not exist on disk, or carry
`user-invocable: false` (which hides it from `slash_commands` and the `skills` array while keeping
it model-invocable).

Commands share one namespace: built-ins, bundled skills, your skills, legacy
`.claude/commands/*.md`. Read the set from the init message's `slash_commands`. An unmatched
`/<name>` no longer errors (v2.1.274+) — it goes to the model as an ordinary message with a note,
**spending a model turn**.

Plugins: `plugins=[{"type": "local", "path": "./my-plugin"}]`. `"local"` is the only type. **Tilde
paths are not expanded**, and a nonexistent path is **silently skipped** — verify against the init
message's `plugins` list. Python's `SdkPluginConfig` has no `skipMcpDiscovery`.

---

## 9. Sessions and storage

| Want | Use |
|---|---|
| Multi-turn in one process | `ClaudeSDKClient` |
| Resume most recent in this dir | `continue_conversation=True` |
| Resume a specific session | `resume=session_id` |
| Branch, keep the original | `resume=id, fork_session=True` |
| Branch from an earlier point | `+ resume_session_at=<msg_uuid>` |
| Write nothing to disk | TS `persistSession: False`; **Python:** `env={"CLAUDE_CODE_SKIP_PROMPT_HISTORY": "1"}` |

Transcripts: `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`, where `<encoded-cwd>` is the
absolute path with non-alphanumerics → `-`, truncated at 200 chars + hash. `CLAUDE_CONFIG_DIR`
relocates; `CLAUDE_CODE_PROJECT_DIR_NAME` names the project dir (SDK ≥ 0.2.140).

### `SessionStore` — bring your own backend

```python
class SessionStore(Protocol):
    async def append(self, key: SessionKey, entries: list[SessionStoreEntry]) -> None: ...
    async def load(self, key: SessionKey) -> list[SessionStoreEntry] | None: ...
    # optional: list_sessions, list_session_summaries, delete, list_subkeys
```

What's locked:

- **It's a mirror, not a replacement.** The subprocess writes local disk first, then the SDK
  forwards to `append()`. No pre-write interception.
- **Which copy survives depends on how the run started.** Fresh → local transcript outlives the run,
  store gets a copy. **Resumed from the store** → the SDK materializes into a temp
  `CLAUDE_CONFIG_DIR` and **deletes the local copy at run end**; the store is then the only durable
  copy.
- **Mirror writes are best-effort.** 3 attempts max, timeouts not retried; on failure the batch is
  **dropped**, `{"type":"system","subtype":"mirror_error"}` is emitted, query continues. Retries can
  re-deliver — **deduplicate on `entry.uuid`**.
- **Mutually exclusive with `enable_file_checkpointing`.** Throws at startup.
- **Python's temp-dir seeding is thinner than TS's.** TS copies credentials, `.claude.json`, *and*
  user `settings.json`. Python copies **credentials and `.claude.json` only** — so an app
  authenticating via `apiKeyHelper` in `~/.claude/settings.json` fails with `Not logged in` on a
  store-resume. Set `ANTHROPIC_API_KEY` in `env`, or put `apiKeyHelper` in managed/project settings.
- `project_key` derives from the working directory — **resume from a matching `cwd`**.
- **The SDK never deletes from your store.** Retention is yours. (Local transcripts are swept
  separately by `cleanupPeriodDays`.)

Python's store-backed helpers are separate functions: `list_sessions_from_store()`,
`get_session_info_from_store()`, `get_session_messages_from_store()`, `list_subagents_from_store()`,
`get_subagent_messages_from_store()`, `rename_session_via_store()`, `tag_session_via_store()`,
`delete_session_via_store()`, `fork_session_via_store()`. The plain `list_sessions()` reads local
files. **`startup()` has no Python equivalent** — no subprocess pre-warm.

Conformance suite ships in the package:
```python
from claude_agent_sdk.testing import run_session_store_conformance
await run_session_store_conformance(MyRedisStore)
```

---

## 10. The agent loop

Not overridable:

- **Turn structure.** Claude emits → tools execute → results feed back → repeat until a tool-free
  response. Hooks are the only insertion mechanism, and they sit at the boundaries, not inside.
- **Parallel-vs-sequential dispatch.** Read-only tools may batch; `Edit`/`Write`/`Bash` serialize.
  Your only influence is `readOnlyHint` on your own tools.
- **Sampling parameters.** `temperature`, `top_p`, `max_tokens` have no option fields **and no
  settings keys** (verified against all 231). Use `effort` and `max_budget_usd`, or call the
  Messages API directly.
- **`Bash` command parsing.** AST-parsed and matched against rules; unparseable → approval required;
  `eval` always requires approval. A permission gate, not a sandbox — it does not infer danger from
  a command's effects.
- **Retry policy.** Tunable via env, not replaceable.

**Compaction is more tunable than revision 1 claimed.** You cannot supply the summarizer or the
algorithm. You *can* set the threshold, three ways:

| Lever | Python reach |
|---|---|
| `autoCompactWindow` settings key | `settings='{"autoCompactWindow": "500k"}'` |
| `CLAUDE_CODE_AUTO_COMPACT_WINDOW` env var | `env={...}` — **takes precedence over the setting and the flag** |
| `--autocompact` CLI flag | `extra_args={"autocompact": "500k"}` |

Claude Code caps the window at the model's actual context window. `auto` returns to the
model-tuned default. And you steer *what survives* by putting preservation instructions in
CLAUDE.md — the compactor reads it like any other context and matches on intent, so the header name
is free-form. `PreCompact` lets you archive first; a `compact_boundary` message reports the result.

Tunable loop knobs:

| Knob | Option | Default |
|---|---|---|
| Turn cap | `max_turns` | none; `0` = unlimited (vs `max_budget_usd`, where `0` is rejected at startup) |
| Spend cap | `max_budget_usd` | none |
| Reasoning depth | `effort` | model-dependent |
| Extended thinking | `thinking={"type": "adaptive"\|"enabled"\|"disabled", "budget_tokens": N, "display": ...}` | adaptive |
| API-side pacing | `task_budget={"total": N}` — *alpha* | none |
| Model + fallback chain | `model`, `fallback_model` (comma-separated) | CLI default |
| Structured result | `output_format={"type": "json_schema", "schema": {...}}` | none |

`effort` and extended thinking are **independent**. On Opus 4.7+ the API defaults `display` to
`"omitted"`; set `"summarized"` to receive `ThinkingBlock` text. Claude Code **doesn't send
`display` to Bedrock or Google Agent Platform**, so Opus 4.7+ returns empty ThinkingBlocks there
regardless.

**`Transport` ABC** (`connect`/`write`/`read_messages`/`close`/`is_ready`/`end_input`) plus
`query(transport=...)` lets you run the CLI elsewhere. Flagged **low-level internal API, interface
may change**.

---

## 11. Structured output

`output_format={"type": "json_schema", "schema": <JSON Schema draft-07>}`. Validated with
re-prompting; the result lands on `ResultMessage.structured_output`.

- **Draft-07.** Rejection triggers on a *declared* newer `$schema`. Pydantic v2's
  `.model_json_schema()` emits no `$schema` key, so it passes; Zod declares 2020-12 by default and
  needs `target: "draft-7"`. Know the mechanism, not just the rule.
- `"format": "email"` is an annotation, **not enforced**.
- An invalid schema **fails at startup** (v2.1.205+; before that it was silently ignored and you got
  plain text).
- **`subtype == "success"` does not imply output.** An unsatisfiable schema finishes successfully
  with `structured_output is None`. Check both:
  ```python
  if msg.subtype == "success" and msg.structured_output:
  ```
- `error_max_structured_output_retries` covers two causes: repeated validation failure, **or** a
  model fallback retracting a completed output with no successful retry. Read `ResultMessage.errors`
  before debugging your schema.
- **No streaming.** JSON appears only on the final result.

---

## 12. Input modes and the result contract

| | Single message (`prompt="..."`) | `ClaudeSDKClient` / streaming |
|---|---|---|
| Images | ❌ | ✅ |
| Queue / interrupt | ❌ | ✅ |
| `set_model` / `set_permission_mode` | ❌ | ✅ |
| Error behaviour | **raises** after yielding the error result | session stays alive |
| Caps | turn cap ends the call | turn count restarts per queued message; budget accumulates |

### The raise-after-yield contract

A single-shot `query()` **yields the final error result, then raises.** Both.

```python
try:
    async for message in query(prompt=..., options=...):
        if isinstance(message, ResultMessage):
            ...   # this branch DID run for the error result
except ResultError as e:                 # SDK >= 0.2.140; subclasses ProcessError
    if e.terminal_reason == "api_error": ...
```

**Check `terminal_reason` before `subtype`.** When the *final request* fails, Claude Code reports
`subtype="success"` with `is_error=True` and the cause in `terminal_reason`. Only limits *you* set
produce an `error_*` subtype. Genuinely inverted from intuition.

A few trailing system events (`prompt_suggestion`) arrive **after** the result — iterate to
completion rather than `break`ing, and note that `break`ing early in a `ClaudeSDKClient` loop causes
asyncio cleanup issues the docs call out explicitly.

### Token streaming

`include_partial_messages=True` yields `StreamEvent` with raw API events; you accumulate deltas.
**`parent_tool_use_id` is always `None`** — token deltas are main-session only. For subagent
attribution use complete messages, or `forward_subagent_text=True` (SDK ≥ 0.2.140).

Per block: `content_block_start` → deltas → **`AssistantMessage`** → `content_block_stop`. The
complete message arrives *before* the stop event.

---

## 13. Cost and usage

| Field | Scope |
|---|---|
| `usage` | **Main loop only.** Excludes subagents. Per-turn in streaming mode. |
| `model_usage` | **Whole query pipeline** — main loop + subagents + compaction + Workflow agents, per model. Excludes the permission classifier and token-counting calls. |
| `total_cost_usd` | Same coverage as `model_usage`, summed. |

**Use `model_usage`.** `usage` undercounts the moment a subagent runs.

- **Per-step `output_tokens` is a placeholder** — the count reported at `message_start`, before
  generation. Real output counts only on the result. Per-step *input* and *cache* tokens are
  accurate once deduped by `message_id` (parallel tool calls share one id).
- **Cost is a client-side estimate** from a build-time price table. Drifts on price changes,
  unrecognized models, unmodellable rules. Do not bill from it. (`modelPricing` in settings can
  supply your own table — another `settings=` key with no option field.)
- Streaming: totals are **cumulative across turns** — read the latest, don't sum. `/clear`,
  `/reset`, `/new` reset them (and `max_budget_usd`). To total a call with resets: last result
  before each `/clear` + the final result.
- After a crash the final `error_during_execution` result may carry **zeroed** totals. Recover from
  the previous turn's result, or sum per-message input/cache usage.
- `ENABLE_PROMPT_CACHING_1H` extends cache TTL (higher write cost). Finer:
  `CLAUDE_CODE_PROMPT_CACHE_TTL` (your turns) and `CLAUDE_CODE_SUBAGENT_PROMPT_CACHE_TTL`, each `5m`
  or `1h` — or the `promptCacheTtl` / `subagentPromptCacheTtl` settings keys.

---

## 14. Observability

The SDK produces **no telemetry of its own.** It passes env vars to the CLI, which exports OTLP.

```python
ClaudeAgentOptions(env={
    "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
    "CLAUDE_CODE_ENHANCED_TELEMETRY_BETA": "1",     # traces only
    "OTEL_TRACES_EXPORTER": "otlp",
    "OTEL_METRICS_EXPORTER": "otlp",
    "OTEL_LOGS_EXPORTER": "otlp",
    "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
    "OTEL_EXPORTER_OTLP_ENDPOINT": "http://collector:4318",
    "OTEL_SERVICE_NAME": "my-agent",
    "OTEL_RESOURCE_ATTRIBUTES": f"enduser.id={quote(uid)},tenant.id={quote(tid)}",
})
```

- **Never set the `console` exporter** — stdout is the SDK's message channel.
- Export failures are **silent**. `CLAUDE_CODE_OTEL_DIAG_STDERR=1` + a `stderr` callback surfaces
  them.
- Spans: `claude_code.interaction` → `claude_code.llm_request`, `claude_code.tool`
  (→ `.blocked_on_user`, `.execution`), `claude_code.hook`. Subagent spans nest under the parent's
  tool span — a delegation tree is one trace.
- **W3C trace context propagates automatically.** Call `query()` inside an active span and the CLI's
  `interaction` span becomes its child; `TRACEPARENT` also reaches every Bash command. Set
  `TRACEPARENT` in `env` yourself to pin a parent (auto-injection is then skipped).
- **Content is off by default.** `OTEL_LOG_USER_PROMPTS`, `OTEL_LOG_TOOL_DETAILS`,
  `OTEL_LOG_TOOL_CONTENT`, `OTEL_LOG_RAW_API_BODIES` opt in — the last includes the entire
  conversation history.
- Batching drops spans on short calls. Lower `OTEL_*_EXPORT_INTERVAL` to ~1000.
- Identity attributes come from **your service's credential**, not your end user's. Inject
  `enduser.id` / `tenant.id` yourself, percent-encoded.

---

## 15. File checkpointing

```python
ClaudeAgentOptions(
    enable_file_checkpointing=True,
    extra_args={"replay-user-messages": None},   # REQUIRED to get checkpoint UUIDs
)
```
Checkpoint IDs are `UserMessage.uuid` values. Then `await client.rewind_files(uuid)`.

Limits:
- **Only `Write`, `Edit`, `NotebookEdit`.** Bash `sed -i`, `>`, `mv` — untracked.
- **Subagent edits untracked** (except a `context: fork` skill in the foreground).
- Directory create/move/delete not undone.
- Symlinks, hard links, and files whose parent dir moved are **skipped** (counted in
  `skippedLinks`).
- Tied to the session that made them. **Incompatible with `session_store`.**
- `rewind_files()` after iteration finishes → `ProcessTransport is not ready for writing`. Resume
  with an empty prompt (`await client.query("")`) and rewind on the new connection.

For anything else, use git.

---

## 16. What is genuinely TypeScript-only

Revised. Sorted by whether the capability is reachable in Python at all.

**Unrecoverable — no Python path:**

| Capability | Cost |
|---|---|
| `interrupt()` receipt (`still_queued` / `cancelled`) | Python's `interrupt()` returns `None`. You cannot tell which queued messages survived, so resending risks double-delivery. A **correctness** hazard for queue-heavy UIs. |
| `startup()` / `WarmQuery` pre-warm | Spawn + initialize handshake is inline on first query. Bites ephemeral per-request architectures; a long-lived `ClaudeSDKClient` amortizes it. |
| `planModeInstructions` | Can't replace the plan-mode workflow body. |
| Host-supplied `managedSettings` | Matters only if you're an embedding host. |
| `SYSTEM_PROMPT_DYNAMIC_BOUNDARY` | Cache efficiency on custom prompts only. |
| `Workflow` tool | Script-orchestrated fan-out. Orchestrate from asyncio instead — arguably better in a general-purpose language. |
| `omitClaudeMd` on a subagent | Minor. |
| `context_usage` on assistant messages | Send `/context` as a prompt and parse markdown; costs a turn. |

**Reachable in Python by another route:**

| TS feature | Python route |
|---|---|
| 23 extra hook events as callbacks | Filesystem hooks (`command`/`http`/`mcp_tool`/`prompt`/`agent`) — §5.1 |
| `applyFlagSettings()` (runtime settings) | `settings=` at startup for all 231 keys; write `settings.local.json` for mid-session; `PreToolUse` reading your mutable state for policy |
| `updateSettings('localSettings', ...)` | Write the file yourself — applies next message |
| `getContextUsage()` | `/context` as a prompt |
| `toolAliases` | `disallowed_tools=["Bash"]` + your own MCP tool under a different name |
| `structuredContent` from in-process tools | Standalone MCP server |
| `alwaysLoad`, per-server timeout | `.mcp.json` entry; `MCP_TOOL_TIMEOUT` |
| `persistSession: false` | `CLAUDE_CODE_SKIP_PROMPT_HISTORY` |
| `permissionPrompts: 'none'` | `dontAsk` mode (close, not identical — `dontAsk` skips `can_use_tool` entirely) |
| `agentProgressSummaries`, `promptSuggestions` | – (cosmetic) |
| `title` at query time | `rename_session()` after the fact |

Python has one thing TS lacks: `SystemPromptFile` (`{"type": "file", "path": ...}`) — which exists
precisely *because* Python passes string prompts on argv.

**Why the gap exists:** the CLI is TypeScript, and the TS SDK is a thinner wrapper over the same
codebase, so new control-protocol surface lands there first. `forward_subagent_text` (Py 0.2.140),
`resume_session_at` (0.2.137), `ResultError` (0.2.140) are all TS features landing later. A release
lag, not a design decision.

---

## 17. Verdict

### Fully yours

- **Tools** — `@tool` + `create_sdk_mcp_server`, or external MCP. Full JSON Schema available.
- **Policy** — `PreToolUse` hooks are a true universal gate: every call, before every rule and mode,
  deny absolute.
- **Approval UX** — `can_use_tool` for prompts, `defer` for out-of-band decisions.
- **Persistence** — `SessionStore` on any backend, with a shipped conformance suite.
- **Subagent topology** — definitions, tools, models, effort, prompts, hard caps, or disable
  delegation outright.
- **Observability** — full OTLP, your own trace parent, end-user attribution.
- **Transport** — run the CLI elsewhere (at your own risk).
- **Output shape** — validated JSON Schema.
- **231 settings keys** via `settings=`, above every filesystem tier.

### Bendable

- **System prompt** — append, replace, or remove named sections via output style /
  `CLAUDE_CODE_SIMPLE_SYSTEM_PROMPT` / `exclude_dynamic_sections`. Contents unreadable; recorded at
  session start on current first-party setups.
- **Tool behaviour** — remove, scope, rewrite inputs, rewrite outputs. Not reimplement; not alias
  (in Python).
- **Configuration loading** — `setting_sources` covers most; five inputs leak through.
- **Compaction** — threshold yes (three ways), preservation steering yes (CLAUDE.md), summarizer no.
- **Model selection** — pick, chain fallbacks, per-subagent override, mid-session swap. No sampling
  params.

### Locked

- The loop's turn structure and tool-dispatch scheduling
- The preset prompt's *text* (its named sections are switchable)
- Built-in tool implementations
- `temperature` / `top_p` / `max_tokens` — no option, no setting
- The six-step permission evaluation order and the six actions no mode auto-approves
- `Bash` AST parsing, critical-path and protected-path checks
- Server-managed settings
- Subagent `bypassPermissions` inheritance
- The CLI version (moves with the pip package)

### The shape of a good abstraction

1. **One factory that builds options.** Put the multi-tenancy quartet behind it, and centralize the
   `env` block *and* the `settings` JSON — between them they carry more configuration than the typed
   options do.
2. **A `PreToolUse` hook as your only policy gate.** Don't spread authorization across
   `allowed_tools`, `disallowed_tools`, `can_use_tool` and settings files; you will get the
   evaluation order wrong. Use `allowed_tools` purely as "don't prompt for this".
3. **Treat the system prompt as immutable per session** on first-party setups, and don't assume it
   on Bedrock/Vertex/Foundry. "Change behaviour" = inject context or start a session.
4. **Wrap the three counterintuitive readings once:** cost from `model_usage`; outcome from
   `terminal_reason` *then* `subtype`; structured output from `subtype == "success" and
   structured_output`.
5. **Wrap the raise-after-yield contract once**, so callers get a result object rather than an
   exception firing after the data arrived.
6. **Decide the hook topology early.** If you need the 23 non-Python events, stand up an `http`
   hook endpoint in your app on day one rather than retrofitting `command` hooks later.
7. **Pin the SDK and read the changelog on minors.** Half the corpus is version-gated, the bundled
   CLI moves with the package, and Python's version number tells you nothing about which CLI you got.

---

## Appendix A: env vars that act like hidden options

No `ClaudeAgentOptions` field. All via `env=` (merged over inherited, in Python). Several also have
`settings=` equivalents, noted where they differ in precedence.

| Variable | Effect |
|---|---|
| `CLAUDE_CONFIG_DIR` | Relocate `~/.claude` entirely |
| `CLAUDE_CODE_PROJECT_DIR_NAME` | Name the transcript project dir |
| `CLAUDE_CODE_DISABLE_AUTO_MEMORY` | Stop auto-memory injection (also `autoMemoryEnabled` setting) |
| `CLAUDE_CODE_SKIP_PROMPT_HISTORY` | Python's `persistSession: false` |
| `CLAUDE_CODE_AUTO_COMPACT_WINDOW` | Compaction threshold — **outranks the setting and the flag** |
| `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` | Nesting depth (default 3) |
| `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` | Concurrency (default 20) |
| `CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS` | Remove the built-in `general-purpose` subagent |
| `CLAUDE_CODE_ENABLE_TODO_TOOLS` | Force Task/Todo tools on newer models |
| `CLAUDE_CODE_ENABLE_TASKS=0` | `TodoWrite` instead of the four Task tools |
| `CLAUDE_CODE_SIMPLE_SYSTEM_PROMPT` | Short system prompt + abbreviated tool descriptions (`0`/`false`/`no`/`off` to force off) |
| `CLAUDE_CODE_SIMPLE=1` | Bare mode — also leaves prompt recording off |
| `ENABLE_TOOL_SEARCH` | `true` / `false` / `auto` / `auto:N` |
| `ENABLE_CLAUDEAI_MCP_SERVERS=false` | Suppress claude.ai connectors |
| `MCP_TIMEOUT` / `MCP_TOOL_TIMEOUT` / `MCP_CONNECT_TIMEOUT_MS` / `MCP_CONNECTION_NONBLOCKING` | MCP connect & call timing |
| `CLAUDE_CODE_MCP_STARTUP_WAIT_MS` | First-turn wait for pending MCP servers (v2.1.274+) |
| `MAX_MCP_OUTPUT_TOKENS` | Raise the 25k-token MCP result cap |
| `API_TIMEOUT_MS` / `CLAUDE_CODE_MAX_RETRIES` / `CLAUDE_CODE_RETRY_WATCHDOG` | API timeout & retry |
| `CLAUDE_ENABLE_STREAM_WATCHDOG` / `CLAUDE_STREAM_IDLE_TIMEOUT_MS` | Stream stall detection |
| `CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS` | Subagent stall watchdog |
| `ENABLE_PROMPT_CACHING_1H` / `CLAUDE_CODE_PROMPT_CACHE_TTL` / `CLAUDE_CODE_SUBAGENT_PROMPT_CACHE_TTL` | Cache TTL |
| `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS` | Strips betas; forces tool search off |
| `CLAUDE_CODE_STARTUP_FAILURE_RESULTS=1` | Result message for every startup failure |
| `CLAUDE_CODE_ENABLE_SDK_FILE_CHECKPOINTING` | Only for driving `claude -p --rewind-files` yourself |
| `ANTHROPIC_BASE_URL` / `HTTP_PROXY` / `HTTPS_PROXY` | Route traffic (non-first-party base URL disables tool search) |
| `CLAUDE_CODE_USE_BEDROCK` / `_USE_VERTEX` / `_USE_FOUNDRY` / `_USE_ANTHROPIC_AWS` | Provider selection |
| `CLAUDE_AGENT_SDK_CLIENT_APP` | Identify your app in the User-Agent |
| `OTEL_*`, `CLAUDE_CODE_ENABLE_TELEMETRY`, `CLAUDE_CODE_ENHANCED_TELEMETRY_BETA` | Observability (§14) |

---

## Appendix B: antithesis log

Each revision-1 claim, its antithesis, the verdict, and where the fix landed.

### Wrong — claim reversed or materially corrected (8)

| # | R1 claim | Antithesis that won | Fix |
|---|---|---|---|
| 1 | "Python SDK 0.2.153 bundles Claude Code ~2.1.153" | Doc pairings show 0.2.137→2.1.223, 0.2.150→2.1.257, 0.2.153→2.1.265. Offset drifts +86…+112. TS aligns; **Python does not** | §0.1 (new) |
| 2 | "The preset is opaque; you can only append" | Output styles *remove* the coding-instructions section; `CLAUDE_CODE_SIMPLE_SYSTEM_PROMPT` swaps the whole prompt; `exclude_dynamic_sections` removes the dynamic block | §3.2 rewritten |
| 3 | "You cannot supply the compaction threshold" | `autoCompactWindow` setting, `--autocompact` flag, `CLAUDE_CODE_AUTO_COMPACT_WINDOW` env — all Python-reachable | §10 |
| 4 | "`allowed_tools` is an approval list, **never** a restriction list" | Naming a task-tracking tool there *opts the session in* — it adds availability | §4.2 |
| 5 | "Actions no mode auto-approves: five" | Six. Missing: cross-session messaging safeguards, and reads outside working dirs under `blockReadsOutsideWorkingDirectories` | §4.3 |
| 6 | "`matcher` matches tool names only" | Matches a different field per event; **`Stop` ignores matchers entirely** | §5.3 |
| 7 | "Python loses 20 hook events" | All 33 are CLI-level, registrable as filesystem hooks with 5 handler types incl. `http`. Python loses the *callback form*, not the events | §5.1 rewritten |
| 8 | "Output styles: startup-only in Python" | Editing `settings.local.json` applies next message (v2.1.251+); `/output-style` and `/config key=value` are dispatchable | §3.4 rewritten |

### Overstated — claim survived but needed scoping (9)

| # | R1 claim | Scoping applied | Fix |
|---|---|---|---|
| 9 | "The SDK **is** a subprocess supervisor" | Default topology only — `Transport` replaces it; in-process MCP runs in your process | §0 |
| 10 | "Your code beats the filesystem" | True for settings merge, **false for permissions** — a filesystem deny/ask rule vetoes you. Also project/local can't set `auto`/`bypassPermissions` | §1.1 (new) |
| 11 | "`cwd` has no setter" (implying frozen) | A `CwdChanged` event exists — the CLI can change it mid-session | §2.1 |
| 12 | "Custom prompt = you own safety" | You own *prompt-level* guidance; harness guardrails (permissions, critical paths, AST parsing) remain | §3.1 |
| 13 | "System prompt is a session-creation-time decision" | Conditional: bare mode defaults recording off; pre-2.1.268 Bedrock/Vertex/Foundry rebuilt every request | §3.3 |
| 14 | "`can_use_tool` never sees auto-approved calls" | The §4.3 set reaches it *even when an allow rule matches* — stated inline now | §4.2 |
| 15 | "Setters require streaming input mode" | In Python the requirement is `ClaudeSDKClient`, which is streaming whether you pass a string or a generator | §4.4 |
| 16 | "Dummy hook required for `can_use_tool`" | All three doc instances are `query()`+generator; the `ClaudeSDKClient` example needs none | §5.6 |
| 17 | "In-process tools: optional params ❌" | Not via the dict shorthand; **fully supported** via a full JSON Schema dict | §6.4 |

### Additional corrections found while testing (4)

| # | Finding | Fix |
|---|---|---|
| 18 | `settings=` reaches **231 settings keys** at a tier above user/project/local — the single widest Python lever, unmentioned in R1 | §1.2 (new), §16 |
| 19 | "Skills are filesystem-only" read as "static" — you can generate `SKILL.md` at runtime; Python just needs a new session (no `reloadSkills`) | §8 |
| 20 | "Claude decides subagent spawning" — you can also disable `Agent`, force `background`, and cap three ways | §7 |
| 21 | Draft-07 rejection triggers on a *declared* `$schema`; Pydantic v2 emits none, which is why it passes | §11 |

### Survived intact (8)

`can_use_tool` is a prompt handler not a gate (§4.2 core claim) · the six-step evaluation order ·
the snapshot rule itself · deny > defer > ask > allow · the three cost scopes and `usage`
undercounting · `SessionStore` mirror semantics and dual-write · raise-after-yield and
`terminal_reason`-before-`subtype` · sampling params genuinely absent (verified against all 231
settings keys, not just the options table).

### Net effect on the thesis

Revision 1 concluded Python was "near-parity with a real gap". Testing moved the line: the
configuration-reach gap was **an artifact of my not having read the settings surface**, and the hook
gap was **an artifact of conflating SDK events with CLI events**. What remains is narrower and
sharper — a **runtime-mutation and latency** gap, plus one genuine correctness hazard (the interrupt
receipt). The "locked" list in §17 is shorter than revision 1 claimed by two entries.
