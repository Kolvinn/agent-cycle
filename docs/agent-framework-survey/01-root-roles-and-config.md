# 01 — Repo root, agent roles, and config

## Scope covered

All paths relative to `/workspaces/langchain-claude-test/agent_framework/`. 28 files read in full:

- `SESSION_SUMMARY.md`
- `architect.md`, `product_owner.md`, `senior_python_engineer.md`
- `config-example-v1.yaml`, `config-example-v2.yaml`, `config-example-v3.yaml`, `confit-example.yml`
- `opencode.jsonc`, `pyproject.toml`, `tach.toml`, `skills-lock.json`, `.env` (keys only), `.dockerignore`, `.python-version`
- `Dockerfile`, `Dockerfile.agent`, `Dockerfile.agent_runtime`, `docker-compose.yml`
- `data/agents/default.yaml`, `data/packages/base-commons/package.yaml`, `data/packages/base-commons/base_commons/__init__.py` (empty), `data/packages/base-commons/base_commons/tools/__init__.py` (empty), `data/packages/base-commons/base_commons/tools/calculator.py`
- `examples/minimal-project.yaml`
- `scripts/ingest_session.py`, `scripts/init-env.sh`, `scripts/init-user.sh`
- `spec/spec-process-cli-rework.md`
- `debug_import.py`, `save.txt`, `thing.json`, `renderer=neato`, `my_graph.dot`, `er.gv`

No files under `agent_framework/` were edited, moved, or deleted.

## Map

**Agent persona prompts (the crown jewels of this slice)**
- `architect.md` (19K) — "Systems Architect" system prompt: five-phase operating mode (frame in three views → diagnose goal gaps → decompose into decisions not tasks → choose tools/references → verify with four stakeholder lenses), plus standing execution standards and explicit boundary with the senior-developer persona.
- `product_owner.md` (21.7K) — "Product Owner" system prompt: same five-phase skeleton adapted to user/value framing, scope-cutting, and user-observable acceptance criteria. Explicit boundaries with architect and senior-developer personas.
- `senior_python_engineer.md` (14K) — "Senior Python Engineer" system prompt: five-phase reframe → decompose → tools → execute → verify, plus a long list of Python-specific craft rules (typing, dataclasses vs Pydantic, exception handling, async discipline, security checklist, testing rules).

**Config schema evolution (agent/tool/package composition DSL)**
- `config-example-v1.yaml` — packages defined at project level, agents reference by name; standalone `tools:`/`mcps:` blocks; `extends` for agent inheritance; `model: provider:model` string convention.
- `config-example-v2.yaml` — same agent set, but packages are declared *inline per-agent* instead of centrally, explicitly noted as mirroring the `test-spike/` pattern more closely.
- `confit-example.yml` — messier, same-day-later scratch note (typos "inherrits", shouting-case TODOs) exploring an alternate `ref: "./base-assistant.yaml"` external-file syntax and flagging an unresolved circular-reference validation need.
- `config-example-v3.yaml` — v1's packages/tools/mcps/agents blocks copied verbatim, but with a new `globalvol`/`rootvol`/`project.volumes` preamble describing Docker volume topology (per-agent `.flox`/skills/tools/project_dir binds, shared volumes with `mount_path`/`size`).

**Repo-root config/tooling**
- `opencode.jsonc` — project overlay on a global OpenCode config; documents a 9-role "canonical agent set" (orchestrator, product_owner, architect, senior_engineer, skeptical_reviewer, security_auditor, researcher, investigator, library_checker) of which only 3 personas exist as files in this slice.
- `pyproject.toml` — heavy, unrelated dependency stack (bertopic, qdrant-client, deepagents, langchain-community/experimental/litellm/mcp-adapters/ollama/openai, pydantic-ai, mermaid-py, trafilatura, transformers, typer, sqlmodel...). **`langchain-claude-cli` never appears** — confirms this repo is a separate lineage, not an ancestor of the new project's core dependency.
- `tach.toml` — module-boundary-checker config, currently empty (`interfaces = []`), `source_roots = ["src"]`.
- `skills-lock.json` — lockfile for `bunx skills add`-installed skills (architecture-designer, architecture-patterns, fastapi-python, fastapi-templates, pragmatic-programmer, refactor) — same mechanism PLAN.md's build-scoping follow-up used to install `langchain-middleware` etc.
- `.env` — 4 keys, no secrets: `PROJ_DIR`, `PROJ_CONFIG`, `PACKAGES`, `NIX_GLOBAL_VOL`.
- `.dockerignore` — deny-by-default then explicit allowlist (`.opencode`, `.agents`, `docs`, `src`, `.python-version`, `pyproject.toml`, `.flox`).
- `.python-version` — `3.14`.

**Docker / process infra**
- `Dockerfile` — Flox-based dev container, non-idempotent user creation (`groupadd`/`useradd` will fail on rebuild if UID 1000 already exists).
- `Dockerfile.agent` — explicitly a stub: "Does NOT run agent_entrypoint.py... proves volume mounts, subpaths, compose generation, and container lifecycle work."
- `Dockerfile.agent_runtime` — real per-agent runtime image: `uv sync`, `/workspace` volume "Controller writes manifest.json here before starting container," `/health` HEALTHCHECK.
- `docker-compose.yml` — single `mcp-controller` service, external network, named volume. Minimal, mostly commented-out build block.

**Data / package examples**
- `data/agents/default.yaml` — one agent instance: `agent_key`, `type`, `model: unknown:unknown` (placeholder), `system_prompt_file` pointing at a `.md` file, `graph_module: agents.orchestrator.graph` (config declares *which Python module* implements the orchestration graph), `skills: [planning-with-files]`.
- `data/packages/base-commons/package.yaml` — package manifest declaring `exports: {tools: [calculator], skills: []}`.
- `data/packages/base-commons/base_commons/tools/calculator.py` — the one real, working piece of code in this slice: a LangChain `@tool`-decorated `calculator` using `ast.parse` + manual node-walking to safely evaluate arithmetic, rejecting `Call`/`Name`/`Attribute` nodes.
- Two `__init__.py` files under `base_commons/` are empty.

**Examples / scripts**
- `examples/minimal-project.yaml` — 5-line stub, barely a fixture.
- `scripts/ingest_session.py` — CLI (argparse + asyncio) that ingests a session-export markdown into a memory pipeline (chunker → concept tree → relationships → Qdrant + Postgres); careful input validation (path exists/non-empty, UUID validation), clean error→exit-code mapping.
- `scripts/init-env.sh` — one-line `PYTHONPATH` export snippet.
- `scripts/init-user.sh` — idempotent version of the Dockerfile's user-creation logic (handles pre-existing UID/GID 1000 via `groupmod`/`usermod` instead of failing).

**Spec**
- `spec/spec-process-cli-rework.md` (23K) — full requirements-numbered spec (REQ/CON/GUD/AC) for replacing broken `bootstrap`/`create_proj`/`new_proj` CLI commands with a three-command `init`/`up`/`switch` model over Docker Compose, with PyYAML `SafeLoader` custom-constructor config loading and a plain-text active-project state file.

**Scratch / junk**
- `SESSION_SUMMARY.md` — real content but scoped to a different sub-project (a Mermaid-diagram renderer for a Qdrant concept-tree memory store), not the ledger.
- `debug_import.py` — 9-line scratch script testing `sys.path`/import resolution. Dead.
- `save.txt`, `renderer=neato`, `my_graph.dot`, `er.gv` — all the same textbook Graphviz "student/course/institute" ER-diagram tutorial example (ASCII art, `.gv`, `.dot`, neato-specific variants), almost certainly produced while comparing Graphviz vs. Mermaid before SESSION_SUMMARY.md's mermaidpy work settled on Mermaid. Pure scratch, unrelated to any named entity in this project.
- `thing.json` — not actually valid JSON; a mangled paste of a Python `str(messages)` LangChain trace (Ollama `llama3.1:8b`, a `calculate_tip` tool call). Confirms the `HumanMessage → AIMessage(tool_calls=[...]) → ToolMessage → AIMessage` shape empirically, but it's broken/unparseable scratch output, not reusable.

## Substance

**1. The three persona prompts are a deliberately engineered "constrain by procedure, not by vibes" system.** All three (`architect.md`, `product_owner.md`, `senior_python_engineer.md`) share one skeleton:

- A **mandatory five-phase operating mode** run "internally and visibly" before any output — e.g. senior-engineer Phase 1 requires restating the job in one sentence, naming the success criterion as an observable/test, and asking rather than assuming when unclear (`senior_python_engineer.md:21-32`).
- **Explicit non-goals as a required artifact.** All three insist on writing down what is *not* being done. Architect: "If you find yourself unable to write the 'what isn't' section, you do not yet understand the problem well enough to design" (`architect.md:51`). Product owner: "Name what is not in this release... Writing them down is the cheapest insurance against scope creep" (`product_owner.md:109`).
- **Mutual role boundaries stated as text, not just implied.** Each file has a "Boundaries with adjacent personas" section spelling out exactly what the other two personas own and the rule "if X pushes back, treat it as a signal you're missing something, not an obstacle" (`architect.md:142-160`, `product_owner.md:135-155`).
- **Calibration heuristics as trailing guardrails** — a numbered list of "if you notice X, that means Y is wrong, do Z" checks, e.g. senior-engineer: "If the runtime prompt contains the word 'just'... it is almost certainly underspecified. Probe once, then proceed" (`senior_python_engineer.md:155`).
- **Verification is a named phase with a required negative disclosure**: "State what you did *not* test and why... 'Should be fine' is not [a useful disclosure]" (`senior_python_engineer.md:68`).

The mechanism these prompts use to constrain behavior is entirely **structural/procedural**: forced phases, forced artifacts (three-view framing, ADRs, acceptance criteria), forced negative space (what isn't built, what wasn't tested), and forced escalation triggers (ask vs. proceed heuristics). None of them touch *provenance* — they never ask "where did this requirement/file/fact come from" or track a source chain. They're the closest thing in this slice to "process discipline for agents" but attack a different failure mode than the ledger project: they combat scope drift and premature code-before-thought, not hallucinated/self-promoted inference chains. Still, the "ask vs. proceed" calibration heuristics and the "write down what you did NOT verify" phase are conceptually adjacent to the ledger's "no implicit node self-promotes" rule — both are refusals to let fluency substitute for confirmation.

**2. The config-schema experiments (v1→v3) are about tool/package *composition*, not provenance.** The four files chart a real design debate: centralized package registry with agents referencing by name (v1) vs. decentralized per-agent inline package declarations (v2, explicitly chosen to mirror a validated `test-spike/` pattern) vs. an external-file-`ref` + `inherrits` inheritance syntax with an unresolved circular-reference-validation TODO (`confit-example.yml:7,14,18`) vs., three days later after "successful agent/client integration for both MCP and tool permissions" (commit `2aca1b0`), a version that prepends Docker volume topology (`globalvol`/`rootvol`/per-agent `.flox`/skills/tools mounts) ahead of the same agents/packages/tools/mcps blocks, unchanged (`config-example-v3.yaml:1-41` is byte-identical to v1's corresponding section). The v1→v3 evolution is really "we started needing to describe infrastructure (volumes) around the same declarative agent config, not just capabilities" — an infra concern, not a provenance concern.

Notably, commit `2aca1b0`'s message says the older project *did* reach "tool permissions" integration for LangChain and FastMCP — that's the single most promising adjacent-prior-art lead in this slice, but the actual code isn't in the files assigned here (only the config-file side-effect is). Worth flagging to whichever survey slice covers `src/` — search for MCP/tool-permission middleware code near that commit.

**3. `data/packages/base-commons/.../calculator.py` is a genuine, complete, directly usable LangChain `@tool`.** It safely evaluates arithmetic via `ast.parse` + explicit node-type whitelisting (`BinOp`, `UnaryOp`, `Constant` only; rejects `Call`/`Name`/`Attribute`) — `data/packages/base-commons/base_commons/tools/calculator.py:24-57`. This is a ready-made, zero-dependency, safe toy tool that could be bound via `bind_tools` as a test fixture for the ledger's gating logic (the ledger needs *some* real bound tool to gate calls against; this is a clean one).

**4. `scripts/ingest_session.py` + the "Relationship naming convention" documented in `SESSION_SUMMARY.md:158-176` describe a DAG-provenance model that is structurally close to the ledger's explicit/implicit node graph**, even though it was built for an unrelated purpose (turning a session transcript into a Qdrant concept tree). The convention: `source_id` = parent (more general), `target_id` = child (more specific), `rel_type` named from the source's perspective ("A contains B", never "B part_of A"), forest not single tree (0+ roots), DAG not strict tree (1+ parents allowed), **no cycles**. This is a validated, previously-implemented vocabulary for "directed node graph with a parent→child derivation relationship and a hard non-cycle constraint" — exactly the shape PLAN.md's ledger needs (explicit node → implicit node, depth-capped, no implicit citing another implicit as parent = no cycles beyond depth 1). It's not code the ledger can import, but it's validated design vocabulary the ledger project could reuse almost verbatim when specifying its own node/edge model.

**5. `spec/spec-process-cli-rework.md` demonstrates a validated real-world answer to PLAN.md's own Open item 3** (how to persist state across stateless invocations). The spec chooses a flat, human-readable, single-line text file (`$ACTIVE_PROJECT_DIR/active`) over a DB row specifically because "(a) it avoids a DB query for something the CLI needs on every call, (b) it's human-readable and trivially debuggable, (c) it follows the 'config compose heavy' principle — state is in files, not DB tables" (`spec/spec-process-cli-rework.md:246`). PLAN.md's Open item 3 speculates a hook script would need "its own session-scoped state (e.g. a local file keyed by session ID)" — this spec is precedent that the same author already made and justified that exact choice in a different but structurally similar stateless-process problem (CLI subcommands that don't share memory across invocations, same as PreToolUse hook processes).

**6. `opencode.jsonc` reveals a 9-role agent roster** of which this slice only contains 3 prompt files (architect, product_owner, senior_engineer). The other 6 named roles — `orchestrator`, `skeptical_reviewer`, `security_auditor`, `researcher`, `investigator`, `library_checker` — are referenced (`opencode.jsonc:4-5`) but their prompt files are not in this slice. `skeptical_reviewer` in particular sounds directly relevant to the ledger's "don't self-promote / don't trust fluency" theme and should be hunted for in another surveyor's slice (likely under `.opencode/` or `.agents/`, both outside this assignment).

## Salvage rating

### Directly reusable for the provenance-ledger project
- `data/packages/base-commons/base_commons/tools/calculator.py:1-57` — complete, safe, dependency-free LangChain `@tool`. Usable as-is as a test fixture for exercising `bind_tools` gating logic.
- The relationship-naming convention in `SESSION_SUMMARY.md:158-176` (source=parent, target=child, DAG not tree, no cycles) — directly reusable *as design vocabulary* for specifying the ledger's own explicit→implicit edge model, even though no code carries over.

### Good thinking material / adaptable
- All three persona prompts (`architect.md`, `product_owner.md`, `senior_python_engineer.md`) — not reusable for the ledger's mechanism, but the "forced negative-space artifact" and "ask vs. proceed calibration heuristic" patterns are a proven template for writing the ledger's own future operating rules/hook prompts.
- `spec/spec-process-cli-rework.md`'s plain-text state-file rationale (`:246`) — directly informs PLAN.md Open item 3 (hook session state).
- `spec/spec-process-cli-rework.md`'s REQ/CON/GUD/AC numbered spec format — a usable template if/when the ledger moves from brainstorm (current PLAN.md status) to an actual spec.
- The config v1↔v2 centralized-vs-per-agent composition debate and the `confit-example.yml` circular-reference TODO — mildly relevant if the ledger's own "explicit node" registration ever needs a similar centralized-vs-inline registry decision, but this is a stretch; rate as low-value adjacent thinking, not load-bearing.
- `tach.toml`'s module-boundary-enforcement intent — worth considering once the new project's `src/` grows enough modules that "ledger core must not import LangChain-specific code" becomes worth enforcing mechanically.
- Docker/manifest-file pattern in `Dockerfile.agent_runtime:19-21` ("Controller writes manifest.json here before starting container") — a second data point (alongside the CLI spec's state file) for "how do you hand state to a process that can't share memory," relevant to any future built-in-tool-gating hook design (PLAN.md Open item 3).

### Dead, superseded, or scratch noise
- `debug_import.py`, `save.txt`, `renderer=neato`, `my_graph.dot`, `er.gv` — confirmed scratch/tutorial-example output, no salvageable content. Say so plainly: this is trash left in the repo root.
- `thing.json` — malformed, non-parseable pasted trace; the one fact it confirms (tool_calls message shape) is already known from PLAN.md's own verified reading of the library source.
- `examples/minimal-project.yaml` — too trivial to be a usable fixture on its own (5 lines, no tools/packages).
- `config-example-v1/v2/v3.yaml`, `confit-example.yml` as *code* — none of these are consumed by any parser in this slice (no loader script was in-scope to confirm they're even valid against a real schema); treat as design sketches, not working config.
- `docker-compose.yml`, `Dockerfile`, `Dockerfile.agent` (self-described stub), `Dockerfile.agent_runtime` — infra for a different, container-per-agent architecture that has no bearing on the ledger's v1 scope (a LangChain-space wrapper around `bind_tools`, no Docker required per PLAN.md item 8).
- `scripts/init-env.sh` — one line, trivial.

## Open threads & contradictions noticed

1. **`Dockerfile:22-26` vs. `scripts/init-user.sh`** — both create a `dev` user at UID/GID 1000, but the Dockerfile version (`groupadd`/`useradd`) is not idempotent and will fail if the base image already has UID 1000 taken, while `init-user.sh` explicitly guards against that with `getent`/`groupmod`/`usermod`. The script looks like the *fix* for a problem the Dockerfile still has — they were never reconciled.
2. **`opencode.jsonc` names 9 canonical agent roles; this slice only contains 3 of the prompt files.** `orchestrator`, `skeptical_reviewer`, `security_auditor`, `researcher`, `investigator`, `library_checker` are referenced but absent from the assigned paths — likely live under `.opencode/` or `.agents/` (both explicitly out of this slice's scope). Worth another surveyor confirming whether they exist at all or are aspirational.
3. **Commit `2aca1b0` claims "successful agent/client integration for both MCP and tool permissions"** for LangChain and FastMCP, but none of the actual integration code is in this slice — only `config-example-v3.yaml`'s volume-topology preamble, which doesn't reference permissions at all. This is a real lead for the `src/`-covering slice to chase, since "tool permissions" is close kin to the ledger's gating problem.
4. **`pyproject.toml` never depends on `langchain-claude-cli` or `claude-agent-sdk`.** The old repo used `langchain-community`/`langchain-openai`/`langchain-ollama`/`litellm`/`pydantic-ai` instead — a different model-abstraction lineage entirely. This confirms (per the task framing) that `agent_framework/` is not a direct ancestor of the new project's core library choice; any "reuse" here is at the idea level, never at the import level.
5. **The config-schema files (v1/v2/v3/confit) were never validated against a parser in this slice** — no `load_project_config()`-equivalent script was assigned to read. `spec/spec-process-cli-rework.md:71-72` references `load_project_config()` and a `config/resolver.py` that aren't in this slice, so it's unclear whether v3's new `globalvol`/`rootvol` block was ever actually consumed by code or is aspirational/sketch-only.

## Best pointers

- `agent_framework/data/packages/base-commons/base_commons/tools/calculator.py:1-57` → complete, safe `@tool` usable today as a `bind_tools` test fixture for the ledger's gating logic.
- `agent_framework/SESSION_SUMMARY.md:158-176` → validated DAG/provenance vocabulary (parent/child direction, no-cycle rule) directly analogous to the ledger's explicit→implicit edge model.
- `agent_framework/spec/spec-process-cli-rework.md:246` → real-world precedent and stated rationale for "session/process state lives in a plain text file, not a DB," answering PLAN.md's Open item 3 by example.
- `agent_framework/architect.md:51`, `agent_framework/product_owner.md:109`, `agent_framework/senior_python_engineer.md:68` → the "forced negative-space artifact" pattern (what isn't built / what wasn't tested) as a transferable prompt-engineering technique for future ledger-related agent instructions.
- `agent_framework/config-example-v3.yaml` commit `2aca1b0` message ("successful agent/client integration for both MCP and tool permissions... langchain and fastmcp") → a lead, not a finding — the actual permission-integration code is outside this slice and should be chased by whoever covers `src/`.
- `agent_framework/opencode.jsonc:4-5` → names 6 agent personas not present in this slice (`skeptical_reviewer` especially worth finding, given its thematic closeness to the ledger's "don't self-promote" rule).
