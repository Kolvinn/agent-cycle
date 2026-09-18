# The Claude Agent SDK's actual control surface — Tier 3, opened up

Captured 2026-09-17. Continues `docs/design/updated-flow-2026-09-16.md` §"What we actually
control over the CLI", which left Tier 3 ("drive `claude_agent_sdk` directly") as one line: "Total
control ... at the cost of reimplementing MCP wiring, streaming and message conversion the plugin
already provides." This document opens that box.

**Method, same discipline as the rest of this project's docs**: read directly from the installed
`claude_agent_sdk` 0.2.153 package source (`types.py` 2492 lines, `client.py`, `query.py`,
`_internal/transport/subprocess_cli.py`), and executed the bundled CLI binary's own `--help` /
`auth --help` / `setup-token --help` (`claude` 2.1.273, at
`claude_agent_sdk/_bundled/claude`). Nothing here is recalled from training data or taken from an
intermediate summary.

## Executive summary

| Question | Answer |
|---|---|
| Does the SDK give more granular **flow** control than `langchain-claude-cli`? | Yes, substantially. Live mid-session `interrupt()`, `set_permission_mode()`, `set_model()`, `rewind_files()` (file checkpoint/undo), `toggle_mcp_server()` / `reconnect_mcp_server()`, `stop_task()`, `get_context_usage()`, `get_mcp_status()`, `get_server_info()` — plus surgical history control (`resume_session_at` / `resume_drops_turn` / `fork_session`) and a `SessionStore` / `Transport` you can fully replace with your own backend. |
| Can it gate Claude Code's **own built-in tools** (Read/Edit/Bash) — the thing `PLAN.md`/`updated-flow` explicitly deferred? | **Yes.** `can_use_tool` is a native `async def` Python callback invoked for every tool call that would otherwise hit an interactive permission prompt. `PreToolUse`/`PostToolUse` hooks are native async Python functions too (not shell scripts), and fire for every tool — built-in or not, including from subagents (tagged with `agent_id`). This is exactly the surface `langchain-claude-cli` doesn't expose (confirmed: it owns `options.hooks` itself and never sets `can_use_tool`). |
| What's still unreachable here, that the raw Messages API has? | `temperature` / `top_k` / `top_p`, `tool_choice` forcing, explicit `cache_control` breakpoints, and the context-editing beta (`clear_tool_uses` / `clear_thinking`) — **zero references anywhere** in the SDK source or the CLI's own `--help`. Categorically absent from the product, not gated by auth mode. |
| Does this tier keep you on subscription billing automatically, like `langchain-claude-cli` does? | **No — this is the opposite.** The raw SDK's subprocess transport inherits the *entire* parent process environment verbatim (`subprocess_cli.py:812`), with no `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN` neutralization. You must blank those yourself. |
| Are beta headers (arbitrary ones, not just the SDK's one typed value) reachable at all? | Only with a real API key. The CLI's own `--betas` flag is documented, verbatim, as **"(API key users only)."** Under OAuth/subscription this surface doesn't exist, full stop. |

---

## 1. Flow control: what `ClaudeSDKClient` adds over one-shot `query()` and over the wrapper

`client.py` — a single long-lived `ClaudeSDKClient` connection exposes, all mid-conversation:

| Method | What it does | In `langchain-claude-cli`? |
|---|---|---|
| `interrupt()` | Cancel the in-flight turn | Only via `persistent=True` |
| `set_permission_mode(mode)` | Hot-swap permission mode (`default`/`acceptEdits`/`plan`/`bypassPermissions`/`dontAsk`/`auto`) mid-session | No |
| `set_model(model)` | Hot-swap model mid-session (e.g. plan on Opus, execute on Sonnet) | Only via `persistent=True` |
| `rewind_files(user_message_id)` | Roll tracked files back to their state at a specific prior user message (needs `enable_file_checkpointing=True`) | No |
| `toggle_mcp_server(name, enabled)` / `reconnect_mcp_server(name)` | Live enable/disable/reconnect one MCP server without restarting the session | No |
| `stop_task(task_id)` | Cancel one specific background task | No |
| `get_context_usage()` | The exact per-category token breakdown behind the `/context` command — total, max, percentage, per-MCP-tool, per-CLAUDE.md-file, per-agent | No |
| `get_mcp_status()` | Live connection status of every configured MCP server | No |
| `get_server_info()` | Available commands, output styles, server capabilities | No |

Two of these are exposed by the wrapper (`persistent=True` → `interrupt()`/`set_model()`, per
`_options.py`'s own docstring), the rest are SDK-only.

**Surgical history control**, also SDK-only: `resume_session_at` (resume only up to one exact
transcript-entry UUID) + `resume_drops_turn` (validated at load time — refuses the resume if the
discarded range isn't cleanly one turn) + `fork_session` (branch to a new session ID instead of
continuing). This is a materially finer instrument than the wrapper's `history_mode`
(`auto`/`flatten`/`replay`), which operates on whole conversations, not a chosen message boundary.

**Fully pluggable persistence and transport**: `session_store: SessionStore` is a `Protocol` you
implement against any backend (Postgres, S3, whatever) — every transcript line gets mirrored to it
live, `"batched"` (once per turn / 500 entries / 1 MiB) or `"eager"` (near-real-time). `Transport`
is an ABC you can replace entirely, bypassing the subprocess model altogether. The wrapper's
`session_store` field only offers `"memory"` or `"file"` (a fixed JSON-on-disk backend) — the raw
SDK's version is a Protocol, i.e. arbitrary.

---

## 2. Built-in tool gating — the deferred-phase blocker, actually reopened

`updated-flow-2026-09-16.md`'s diagram 3 puts "Claude Code built-in tools (Read/Edit/Bash)" in a
box labeled **"OUT OF v1 SCOPE · deferred"**, reasoning that gating them "would need a `PreToolUse`
hook plus its own session-keyed state file." Reading the SDK source directly shows the mechanism
exists and is considerably better-shaped than that framing assumed:

**`CanUseTool`** (`types.py:278-280`):
```python
CanUseTool = Callable[[str, dict[str, Any], ToolPermissionContext], Awaitable[PermissionResult]]
```
A plain async Python function: `(tool_name, tool_input, context) -> PermissionResultAllow |
PermissionResultDeny`. `PermissionResultAllow(updated_input=...)` rewrites the call's arguments
before it runs (`types.py:258-264`); `PermissionResultDeny(message=..., interrupt=...)` refuses it,
optionally aborting the whole turn (`types.py:267-273`). `ToolPermissionContext` (`types.py:222-254`)
hands the callback `tool_use_id`, `agent_id` (which subagent, if any), `blocked_path`,
`decision_reason`, and ready-made prompt text (`title`/`display_name`/`description`).

**`PreToolUse`/`PostToolUse` hooks are the same story** — `HookCallback = Callable[[HookInput, str |
None, HookContext], Awaitable[HookJSONOutput]]` (`types.py:598-605`), registered via
`HookMatcher(matcher="Bash", hooks=[my_async_fn])` in `ClaudeAgentOptions.hooks`. This is the exact
same field-level capability (`updatedInput`, `updatedToolOutput`, `permissionDecision`) that
`docs/claude-code-hooks-and-control-surface.md` documented for Claude Code's shell-script hooks —
just delivered as a native async Python call instead of a subprocess reading JSON off stdin.

**This directly resolves `PLAN.md`'s Open item 3** ("whether a `PreToolUse` hook's input actually
carries enough information... likely requires the hook script to keep its own session-scoped
state... since each hook invocation is a stateless process"). That concern is real for Claude
Code's *shell-script* hooks (each one really is a fresh subprocess). It does not apply here: an SDK
hook or `can_use_tool` callback is an ordinary Python closure/bound method for the life of the
process — it can read and write a shared ledger object directly, no file-keyed-by-session-ID
workaround needed. **This only changes what's possible if the project drives `claude_agent_sdk`
directly for this phase — it does not change `langchain-claude-cli`'s own limitation**, which is
still real and documented in `updated-flow-2026-09-16.md` §9 (the wrapper owns `options.hooks` and
never sets `can_use_tool`).

**Precedence and shadowing, read from `types.py:1826-1928`** (not guessed — this is exactly the
kind of "gate that looks present and always says yes" trap `updated-flow`'s diagram 3 warns about):

- A `PreToolUse` hook's `allow` decision skips `can_use_tool` entirely for that call.
- `permission_mode="bypassPermissions"` auto-approves everything (except explicit deny rules)
  *before* `can_use_tool` is ever consulted — the SDK detects this and raises
  `CanUseToolShadowedWarning` at connect time, naming exactly which config caused it.
- An `allowed_tools` entry that allows a *whole* tool (`"Read"`, `"Read()"`, `"Read(*)"` — not a
  narrowed one like `"Bash(git *)"`) also shadows `can_use_tool` for that tool, with the same
  warning.
- `can_use_tool` and `permission_prompt_tool_name` are mutually exclusive — setting both raises
  `ValueError` at connect/query time (`_configure_can_use_tool`, `types.py:1917-1928`).
- Hooks on the same event dispatch **concurrently**, not in sequence (`ClaudeAgentOptions.hooks`
  docstring, `types.py:2159-2164`) — a correction to assume independence between matchers, not
  ordering.

**New hook events, not in the public Claude Code hooks reference this project already fetched**
(`docs/claude-code-hooks-and-control-surface.md` §1 lists `UserPromptSubmit`, `PreToolUse`,
`PostToolUse`, `Stop`/`SubagentStop`, `PreCompact`/`PostCompact`, `SessionStart`): the SDK's
`HookEvent` union (`types.py:284-295`) also has **`PostToolUseFailure`** (fires on a failed tool
call specifically, carrying the `error` string), **`SubagentStart`** (paired with the already-known
`SubagentStop`), and **`PermissionRequest`** (fires when a permission prompt would show, carrying
`permission_suggestions`, output is a raw `decision` dict). Flagged here as an SDK-specific
finding the prior doc's source (the public hooks page) didn't surface — worth re-checking whether
these are newer additions to Claude Code itself or SDK-only surface before relying on them.

---

## 3. What's categorically absent — confirmed by exhaustive grep, not inference

Searched `context_management`, `clear_tool_uses`, `clear_thinking`, `cache_control`,
`prompt_cach`, `temperature`, `top_p`, `top_k`, `tool_choice` across every `.py` file in the
installed package: **zero matches, for all of them.** Cross-checked against the bundled CLI's own
`--help` (full flag list read directly, 2.1.273): no matching flag either. This is not a
subscription-vs-API-key restriction — it's an absence from the Claude Code product surface
entirely, SDK included. If any of these specifically matter, the only route is the raw Messages
API (`anthropic` Python/TS SDK), off both the CLI and the Agent SDK.

**Structured output is the one exception that *is* fully present**: `ClaudeAgentOptions.output_format`
(`types.py:2334-2340`) takes the same shape as the Messages API's `output_config.format`
(`{"type": "json_schema", "schema": {...}}`), and the CLI has a matching `--json-schema` flag. This
is the mechanism `langchain-claude-cli`'s `with_structured_output` already threads through — now
confirmed as a first-class, documented `ClaudeAgentOptions` field in its own right, not a
wrapper-specific trick.

**CLI-only flags with no typed `ClaudeAgentOptions` field** (reachable from Python only via the
`extra_args: dict[str, str | None]` escape hatch, which passes raw `--flag value` straight through):

| Flag | What it does | Note |
|---|---|---|
| `--restricted` | Strips Bash/PowerShell/REPL/other code-running tools + WebFetch unless `--tools` names them; ignores user/project/local settings; confines file tools to working dirs; refuses `bypassPermissions` | A coarser, one-flag alternative to hand-building an allow-list |
| `--safe-mode` | Disables CLAUDE.md, skills, plugins, hooks, MCP servers, custom commands/agents, output styles, themes, keybindings — auth/model/tools/permissions still work | Useful for isolating a session from ambient project config |
| `--bare` | Skips hooks, LSP, plugin sync, auto-memory, CLAUDE.md discovery | **Forces API-key auth** — see §4, this actively breaks subscription billing |

`betas: list[SdkBeta]` is typed with exactly one literal value, `"context-1m-2025-08-07"` (the 1M
context window beta for Sonnet 4/4.5) — Python doesn't enforce `Literal` at runtime, but it doesn't
matter: the CLI's own `--betas` flag help text says plainly **"(API key users only)."** Under
OAuth/subscription auth, arbitrary beta headers — including the one typed value, and including
the context-editing beta if it existed here at all — are not reachable. `task_budget` is the one
exception: it triggers its own beta header (`task-budgets-2026-03-13`) automatically when set,
independent of the `betas` list or auth mode (unverified whether it too is API-key-gated — not
tested here).

---

## 4. The auth gotcha: this tier does not protect your subscription billing by default

`langchain-claude-cli`'s `_options.py` actively blanks `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN`
before spawning the CLI (`_AUTH_ENV_VARS`, confirmed in the prior session) specifically because,
per its own comment, "the CLI would otherwise prefer them and bill per token."

The raw SDK does **no such thing**. `_internal/transport/subprocess_cli.py:812`:

```python
inherited_env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
```

Every environment variable in your process — including a stray `ANTHROPIC_API_KEY` left over from
another tool, a devcontainer default, or a CI secret — flows straight into the CLI subprocess, and
the CLI prefers it over OAuth when present. Nothing in `ClaudeAgentOptions` warns about this or
opts you out of it automatically.

**If driving `claude_agent_sdk` directly and subscription billing matters**, replicate the
wrapper's guard yourself, either by scrubbing `os.environ` before constructing the client, or by
setting `ClaudeAgentOptions(env={"ANTHROPIC_API_KEY": "", "ANTHROPIC_AUTH_TOKEN": ""})` (`env` is
merged over the inherited environment, per the same transport code). Also relevant here:
`claude setup-token` — "Set up a long-lived authentication token (requires Claude subscription)" —
is the CLI's own mechanism for headless/automated subscription auth (e.g. for an SDK process with
no interactive browser available), as an alternative to interactive `claude auth login`. Not tested
in this session; flagged as the likely answer to "how do I authenticate a subscription headlessly"
if that comes up.

---

## 5. Net effect on this project's open items

- `updated-flow-2026-09-16.md` diagram 3's "OUT OF v1 SCOPE" box for built-in-tool gating is no
  longer architecturally blocked — it's a scoping choice now, not a hard wall. The blocker was
  specific to `langchain-claude-cli` owning the hooks slot, not to the underlying platform.
- `PLAN.md` Open item 3 (session-scoped state for hook-based gating) is resolved for this surface
  specifically: SDK-native hooks/`can_use_tool` don't need file-keyed state at all, since they're
  ordinary long-lived Python callables.
- Moving to this tier means re-implementing what the wrapper currently gives for free: MCP wiring
  (though `create_sdk_mcp_server`/`@tool` make in-process tool definition straightforward — no
  external server process, direct access to your app's own state), LangChain message conversion,
  and streaming plumbing. That cost is real and unquantified here — this document only establishes
  what capability is on offer, not what it costs to rebuild the wrapper's conveniences on top of it.

## Provenance

**Read directly from installed source, this session, 2026-09-17**: `claude_agent_sdk` 0.2.153 at
`.venv/lib/python3.14/site-packages/claude_agent_sdk/{__init__.py,types.py,client.py,query.py}` and
`_internal/transport/subprocess_cli.py:812`. All line numbers cited above were read, not
recalled.

**Executed directly, this session**: the bundled CLI binary at
`claude_agent_sdk/_bundled/claude` (`claude --version` → `2.1.273 (Claude Code)`), `claude --help`
(full flag list), `claude auth --help`, `claude setup-token --help`.

**Not independently verified**: whether `PostToolUseFailure`/`SubagentStart`/`PermissionRequest`
are recent additions to Claude Code generally (and simply postdate
`docs/claude-code-hooks-and-control-surface.md`'s 2026-09-16 fetch of the public hooks page) versus
SDK-exclusive surface never in that public doc at all. Whether `task_budget`'s beta header is
API-key-gated like the general `betas` list. Whether `claude setup-token` is in fact the correct
mechanism for headless subscription auth in an SDK context — named in the CLI's own command list,
but its actual behavior was not executed or tested here.
