# Claude Code hooks & control surface — what actually constrains the model

Captured 2026-09-16. Answers four specific questions: can you force output schemas (à la
LangChain's `with_structured_output`), restrict/block responses, modify or remove context sent
back to the model (like tool output), and whether any of that affects Claude's prompt cache for
the parts that weren't touched.

**Scope.** Claude Code's hook system, plus the Claude API mechanics hooks sit on top of. Where
this project's own `langchain-claude-cli` / `claude-agent-sdk` testing
(`docs/design/updated-flow-2026-09-16.md`) bears directly on a question, it's cited rather than
re-derived — that document has execution-verified findings this one doesn't repeat.

## Executive summary

| Question | Answer |
|---|---|
| **Force an output schema** on the model's own final answer, like `with_structured_output`? | Not via hooks — hooks act on tool calls and turns, never on the shape of Claude's drafted text. The real mechanism is one layer down, in the Claude API: `output_config.format` (JSON-schema-constrained final response) and `strict: true` on a tool's `input_schema` (schema-valid tool arguments). This project's `langchain-claude-cli` wrapper reaches that same mechanism through a native CLI `output_format` passthrough (§7). |
| **Restrict / block a response**? | Yes, extensively — always at a tool-call or turn boundary, never by editing Claude's drafted text in place. `PreToolUse` can allow/deny/ask/defer a tool call and rewrite its arguments before it runs. `Stop` can refuse to let a turn end. `UserPromptSubmit` can refuse to let a prompt reach Claude at all. |
| **Modify or remove context sent back** to the model (tool output)? | Yes — `PostToolUse` can literally replace a tool's result via `updatedToolOutput` before Claude sees it (the real-world action already happened; this only changes what gets *reported*). `PreToolUse` can rewrite a tool's *input* before it executes, which does prevent the real action. |
| **Does that affect caching** for the untouched parts? | No — caching is strictly prefix-based. Content *before* the point a hook edits is an unchanged, still-valid prefix and keeps being read from cache. Content *at and after* that point can't match the old cache entry, gets rewritten once (paying the write cost), and becomes the new stable prefix from then on. |

---

## 1. The hook event surface

Claude Code fires hooks at defined points in a session. Source: `code.claude.com/docs/en/hooks`,
fetched and read directly (raw markdown, not a summarized rendering) on 2026-09-16. The events
relevant to the four questions above:

| Event | Fires | Can block? | Can rewrite content before Claude sees it? |
|---|---|---|---|
| `UserPromptSubmit` | before Claude processes a submitted prompt | yes — `decision: "block"` **erases the prompt from context entirely** | no — can only add `additionalContext` alongside the prompt, never replace its text |
| `PreToolUse` | after Claude builds tool arguments, before the tool runs | yes — `hookSpecificOutput.permissionDecision`: `allow` / `deny` / `ask` / `defer` | yes — `updatedInput` replaces the entire input object before execution |
| `PostToolUse` | immediately after a tool call succeeds | can end the turn with a warning (not a true block — the tool already ran) | yes — `updatedToolOutput` / `updatedMCPToolOutput` replaces the tool's result before Claude sees it |
| `Stop` / `SubagentStop` | the agent is about to finish responding | yes — `decision: "block"` forces continuation | no direct edit of the drafted reply; it can only add `hookSpecificOutput.additionalContext` as the next instruction, which restarts generation |
| `PreCompact` / `PostCompact` | before/after `/compact` or auto-compact | `PreCompact` can block the compaction; `PostCompact` cannot | no — neither can alter what compaction produces, only observe or (for `PreCompact`) refuse it |
| `SessionStart` | session begins/resumes | cannot block at all | can inject `additionalContext` at the start of the conversation |

Two structural notes worth internalizing before the rest of this document:

- **PreToolUse decisions precede permission-mode checks.** A hook's `deny` blocks a tool call
  even under `bypassPermissions`; conversely a hook's `allow` does **not** override an explicit
  deny rule in settings or an MCP tool marked `requiresUserInteraction`. When several `PreToolUse`
  hooks disagree, precedence is `deny` > `defer` > `ask` > `allow`.
- **`PreToolUse` used to use top-level `decision`/`reason` fields; that's now deprecated for this
  event specifically** (`"approve"`/`"block"` map to `"allow"`/`"deny"`). Every *other* event that
  supports blocking (`PostToolUse`, `Stop`, `SubagentStop`, `UserPromptSubmit`, `PreCompact`, …)
  still uses the plain top-level `decision`/`reason` pair. Worth knowing before copying an example
  from one event to another.

---

## 2. Forcing schema-constrained output

**Hooks cannot do this.** There is no hook field, on any event, that validates or reshapes
Claude's own final response text against a schema. The closest a hook gets is `Stop` blocking the
turn and asking Claude to redo it with a written reason — a retry, not a schema constraint, and
it costs a full generation cycle each time.

The real mechanism lives in the Claude API itself, one layer beneath Claude Code:

| Mechanism | Field | What it guarantees |
|---|---|---|
| **Structured outputs** | `output_config: {format: {...}}` on `messages.create()` (or `client.messages.parse()`, which validates automatically) | Claude's final response is constrained to a JSON Schema you supply — this is the direct equivalent of `with_structured_output` |
| **Strict tool use** | `strict: true` on a tool definition (alongside `name`/`input_schema`) | `tool_use.input` is guaranteed to validate against that tool's schema exactly |
| **Forced tool choice** | `tool_choice: {"type": "tool", "name": "..."}` (also `{"type": "any"}` — must call *some* tool, `{"type": "none"}` — cannot call any) | Forces a specific tool call, which is how JSON extraction was traditionally forced before structured outputs existed |

Supported models for structured outputs: Claude Fable 5/5.1, Mythos 5/5.1, Opus 5, Opus 4.8,
Sonnet 5, Haiku 4.5 (and legacy Opus 4.5/4.1). JSON Schema support is real but not complete —
no recursive schemas, no `minimum`/`maximum`/`multipleOf`, no string length constraints, and
`additionalProperties` must be `false`. **Claude Fable 5.1 / Mythos 5.1 reject forced
`tool_choice`** (`{"type": "any"}` / `{"type": "tool", ...}` return HTTP 400) — on those models
use `{"type": "auto"}` with an explicit prompt instruction, `strict: true` for schema-valid
arguments, or structured outputs if the forced call only existed to get JSON back.
Source: this session's `claude-api` skill, `shared/tool-use-concepts.md` §Tool Choice Options and
§Structured Outputs (read in full, not summarized).

**This project's own finding is directly relevant here.** `docs/design/updated-flow-2026-09-16.md`
records, verified by reading the installed `langchain-claude-cli` 1.2.1 package: `ChatClaudeCli`
implements `with_structured_output(schema, method="json_schema")` via "native CLI `output_format`"
— i.e. the wrapper threads a schema through to the same underlying mechanism, not something
hooks provide. That's a different, lower surface than Claude Code's hook system; it's reached
through the model-call layer (the Agent SDK / CLI request), not through `.claude/settings.json`
hooks.

---

## 3. Restricting / blocking a response

Every blocking mechanism operates on a *tool call* or a *turn boundary* — never a live edit of
text Claude has already drafted.

**`PreToolUse`** is the workhorse. `hookSpecificOutput.permissionDecision` takes four values:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "Database writes are not allowed"
  }
}
```

- `"allow"` — skips the permission prompt (with exceptions: actions no mode auto-approves, and
  `AskUserQuestion`/`ExitPlanMode`, which need `updatedInput` paired with it)
- `"deny"` — blocks the call; Claude sees the reason and can try something else
- `"ask"` — forces the interactive permission prompt, labeled by hook source (`[settings]`,
  `[plugin:name]`, `[skill]`)
- `"defer"` — pauses the tool call for an external process to resume later (non-interactive `-p`
  mode only; how the Agent SDK implements human-in-the-loop approval for `AskUserQuestion`)

**`Stop` / `SubagentStop`** block the *turn from ending*, not a specific response's content:

```json
{ "decision": "block", "reason": "Must be provided when Claude is blocked from stopping" }
```

Loop safety is explicit and bounded: the hook input carries `stop_hook_active` (true when this
continuation is itself the result of a prior block — check it to avoid an infinite demand), and
Claude Code hard-overrides the hook after **8 consecutive blocks**. `additionalContext` on `Stop`
is the softer sibling — same loop protections, but shown as "Stop hook feedback" rather than a
hook error.

**`UserPromptSubmit`** blocks the prompt from ever reaching Claude:

```json
{ "decision": "block", "reason": "Explanation for decision", "hookSpecificOutput": {...} }
```

`decision: "block"` here "prevents the prompt from being processed **and erases it from
context**" — the strongest of the block mechanisms, since the prompt never becomes part of the
conversation at all (compare to `PostToolUse`, where a "blocked" result still leaves the original
tool output visible unless separately replaced).

**LLM-judged gates exist too.** `type: "prompt"` hooks send the hook's JSON input to a fast model
(Haiku by default) and expect back `{"ok": true|false, "reason": "...", "impossible": true|false}`;
`type: "agent"` hooks spawn a full subagent with tool access (up to 50 turns) to verify a
condition — e.g. "did the test suite actually pass" — before allowing a `Stop`. This is a
genuinely different control shape from the deterministic JSON-field hooks above: it delegates the
decision to another model call rather than a script.

**What none of this does:** no hook fires on Claude's own current-turn output *except* `Stop`
(and even there, blocking discards the whole turn and asks for a redo — it can't surgically edit
one sentence of what was drafted). Every other event, including `UserPromptSubmit` — which sounds
like a plausible place to police "what gets said" — only ever sees the **user's** input.

---

## 4. Modifying / removing context sent back to the model

This is the question with the most nuance, because the first-pass research on it (a quick
WebFetch summarized by an intermediate small model) got it **wrong** — worth stating plainly
since it's exactly the failure mode this project's other docs are built around catching. That
pass concluded "`PostToolUse` cannot modify tool output, only add context." The primary source,
fetched as raw markdown and read directly, says the opposite:

> `updatedToolOutput` — Replaces the tool's output with the provided value before it is sent to
> Claude. The value must match the tool's output shape.

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "Additional information for Claude",
    "updatedToolOutput": {
      "stdout": "[redacted]",
      "stderr": "",
      "interrupted": false,
      "isImage": false
    }
  }
}
```

So redaction genuinely works — a `Bash` command's captured secret, a file's sensitive contents,
whatever a tool returned can be swapped out before it enters Claude's context. The documented
caveat matters as much as the capability:

> `updatedToolOutput` only changes what Claude sees. The tool has already run by the time the
> hook fires, so any files written, commands executed, or network requests sent have already
> taken effect. ... For built-in tools, a value that doesn't match the tool's output schema is
> ignored and the original output is used. ... Stripping error details that Claude needs can
> cause it to proceed on a false assumption.

In other words: `PostToolUse` redacts what's *reported*, not what *happened*. If the goal is to
actually prevent an action (not just hide its result), that's `PreToolUse`'s `updatedInput`,
which rewrites the tool's arguments before it ever executes — the only one of the two that can
stop something from occurring at all, as opposed to hiding that it occurred.

| Mechanism | Event | Changes reality or just what Claude sees? |
|---|---|---|
| `updatedInput` | `PreToolUse` | Changes what actually runs — the tool receives the rewritten arguments |
| `updatedToolOutput` / `updatedMCPToolOutput` | `PostToolUse` | Cosmetic to the model only — the real action already happened |
| `additionalContext` | most events | Pure addition — never removes or edits anything already there |

What's explicitly **not** possible with hooks: editing an arbitrary *earlier* point in the
transcript after the fact (there's no "go back three turns and redact that" mechanism), and
`UserPromptSubmit` cannot touch the prompt's own text — only block it outright or add alongside
it. `PreCompact`/`PostCompact` can observe or (for `PreCompact`) refuse a compaction, but neither
can shape what the compacted summary actually contains.

**A related mechanism one layer down, not a Claude Code hook.** The Claude API has a beta
*context editing* feature (`context_management`, beta header `context-management-2025-06-27`)
that server-side-clears old tool results (`clear_tool_uses_20250919`) or old thinking blocks
(`clear_thinking_20251015`) once a token threshold is crossed — a programmatic, rule-based
cousin of what a `PostToolUse` hook does by hand, but operating on the whole history rather than
one call, and available only if you're driving the Messages API or Agent SDK directly rather than
using Claude Code's own hook system. *(This item came from the research subagent's report,
consistent with known Anthropic API surface, but not independently re-verified against raw docs
in this session the way the hooks material above was — treat its exact field names as
directionally right, not quote-verified.)*

---

## 5. Caching mechanics, and what an edit does to it

Source: this session's `claude-api` skill, `shared/prompt-caching.md`, read in full.

**The one invariant everything follows from:**

> Prompt caching is a prefix match. Any change anywhere in the prefix invalidates everything
> after it. The cache key is derived from the exact bytes of the rendered prompt up to each
> `cache_control` breakpoint.

Render order is `tools` → `system` → `messages`. So concretely, for a hook that injects
`additionalContext` or replaces a tool's output at some position N in the conversation:

- **Everything before position N is untouched** — same bytes as the previous request, so it
  remains a valid prefix and keeps being served from cache (`cache_read_input_tokens` still
  covers it).
- **Position N onward differs** from whatever was cached before, so it can't match — that segment
  is written fresh (`cache_creation_input_tokens`) at the ~1.25× write cost, once.
- On the **next** turn, that injected/replaced content is no longer new — it's just part of the
  history — so it becomes part of the stable prefix and gets read from cache like everything else
  before it, *provided it doesn't change again*. The docs confirm hook-injected text is durable
  across resumes: "Claude Code saves the injected text in the session transcript... when you
  resume with `--continue` or `--resume`, Claude Code replays the saved text rather than
  re-running the hook for past turns" — meaning a value like a timestamp injected once becomes
  frozen, stale, and stable, not re-computed and re-invalidating on every resume.

This directly answers the caching question as asked: **no, editing or injecting content at one
point does not affect the cache validity of the unmodified parts before that point** — prefix
caching is precisely the property that isolates them. It only costs a rewrite of the tail from
the edit point forward, once.

Supporting mechanics, for completeness:

- **Max 4 `cache_control` breakpoints per request.** Minimum cacheable prefix is model-dependent
  (512 tokens on Opus 5/Fable 5/Fable 5.1/Mythos 5/5.1, up to 4096 on Opus 4.6/4.5 and Haiku 4.5) —
  shorter content silently never caches, no error.
- **Not everything invalidates everything.** The API has three cache tiers (tools / system /
  messages), and a change only invalidates its own tier and below:

  | Change | Tools cache | System cache | Messages cache |
  |---|:---:|:---:|:---:|
  | Tool definitions (add/remove/reorder) | invalidated | invalidated | invalidated |
  | Model switch | invalidated | invalidated | invalidated |
  | `tool_choice`, images | invalidated | invalidated | intact |
  | Message content (this is what a hook edits) | intact | intact | invalidated from that point |

  So a `PostToolUse` rewrite or an injected `additionalContext` — both message content — never
  touches the tools or system prompt cache at all; only the messages tier pays the cost, and only
  from the edit point forward.
- **20-block lookback window**: each breakpoint walks back at most 20 positions looking for a
  prior cache entry (parallel tool-call runs collapse to one position each; long sequential runs
  don't) — a turn that exceeds that window can silently miss a cache it should have hit,
  unrelated to any hook editing.

---

## 6. Other control knobs worth knowing about

- **Permission rules** (`settings.json` `permissions.allow`/`permissions.deny`, e.g.
  `"Bash(git *)"`, `"Edit(*.md)"`) and **permission modes** (interactive default, `acceptEdits`,
  `plan`, `bypassPermissions`) sit below hooks in precedence for denies, above for some allows —
  see the PreToolUse precedence note in §1.
- **Subagent tool restriction** via `tools:`/`disallowedTools:` frontmatter on an agent
  definition — an allow-list or deny-list of tool names, including MCP tool name patterns.
- Prompt- and agent-based hooks (§3) are worth remembering as a distinct category: they're a
  model call deciding, not a deterministic script — useful when the gate condition ("did the
  tests actually pass," "is this a genuine multi-hop reference") isn't mechanically checkable,
  which is exactly the kind of condition `PLAN.md`'s provenance ledger design in this repo cares
  about.

---

## 7. What this project already found, specific to `langchain-claude-cli`

`docs/design/updated-flow-2026-09-16.md` §"What we actually control over the CLI" has
execution-verified (not just documented) findings that sharpen §2–3 above for this project's
actual stack:

- **Deny-listing built-in tools doesn't work.** Blocking `Read` via `disallowed_tools` didn't
  stop a canary-token read — the model just switched to `Bash` and read the file that way
  (`tool_use: Read` → `tool_use: Bash` → leaked). **Allow-listing does work**: `builtin_tools`
  defaults to `None` (no built-in tools, no filesystem at all), and naming exactly the tools you
  want is the only control that actually holds. This is a concrete, measured instance of §3's
  restriction mechanisms failing when misapplied — the gate fired, and the model routed around it.
- **The hooks slot is owned by the plugin.** `langchain-claude-cli` assigns `options.hooks` itself
  whenever tools are bound via `bind_tools`; there's no passthrough for registering your own
  `PreToolUse` hook alongside it. So everything in §1–§4 above is reachable through this project's
  stack only by going around the wrapper (driving `claude_agent_sdk` directly), not through it.
- **Structured output is real and working** in this stack specifically — confirms §2's claim that
  the mechanism exists one layer below hooks, reached via the CLI/SDK request layer rather than
  `.claude/settings.json`.

---

## Provenance

**Read directly from primary sources this session** (raw markdown fetched via `curl`, not an
intermediate model's summary): the full Claude Code hooks reference at `code.claude.com/docs/en/hooks`
(§1, §3, §4's `updatedToolOutput` quote, §5's replay-on-resume quote); this session's `claude-api`
skill's `shared/prompt-caching.md` and `shared/tool-use-concepts.md`, read in full (§2, §5).

**From this project's own prior execution-verified testing**, not re-verified here:
`docs/design/updated-flow-2026-09-16.md`'s CLI-control table and canary-token test (§7).

**From a research subagent (`claude-code-guide`), single-report, not independently re-verified**:
the context-editing beta description in §4's closing paragraph, flagged inline. That same
subagent's report is also the concrete example of why this section exists: its first-pass answer
claimed `PostToolUse` "can only inject additionalContext, not modify tool output," which directly
contradicts the primary source quoted in §4. The correction was only possible because the raw doc
was fetched and read a second time rather than trusting the first summary — the same discipline
`docs/agent-framework-survey/00-index.md` documents from the prior project's survey.

**Not independently verified, taken as generally reliable background**: the tool_choice values,
structured-outputs model list, and JSON Schema limitation list in §2, sourced from the bundled
`claude-api` skill rather than fetched fresh this session.
