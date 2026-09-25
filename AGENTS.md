# AGENTS.md — Local Asset Studio (runtime adapters)

Shared facts — what the Studio is, how to run it, the per-seam proving checks, architecture, pitfalls,
tier and authority — live in **`CLAUDE.md`** and are not repeated here. Global working agreements reach
Codex through `~/.codex/AGENTS.md` and Grok through `~/.grok/rules/00-global-laws.md` (deployed copy of
claude-config `rules/laws.md`) plus `~/.grok/AGENTS.md`. `[compat.claude] agents` is off so `~/.claude/AGENTS.md`
(claude-config's project file) does not leak. This file is the Codex-runtime delta; Grok also loads
it, so the Grok section at the bottom overrides the Codex facts for Grok sessions.

## Start here

1. `CLAUDE.md` — repo facts, proving checks, architecture, pitfalls.
2. `CURRENT_STATE.md` head — executed evidence versus plans; reconcile claims against code and `.runtime/`.
3. `HUMAN_TODO.md` — owner decisions and actions; surface open items in every summary. Tick an item only on verified completion, or when the owner answered every part and its stated conditions hold, recording how and when; never infer a decision or art acceptance.
4. `docs/PROJECT-OPERATING-MODEL.md` — issue type/readiness, three-line WIP limit, stack order and evidence placement.
5. If you are Codex, read `.codex/README.md` and `.codex/memories/00_ACTIVE.md`. If you are Grok, read `.grok/README.md`.
6. Authority: `.agent-harness/tier.json` (T2, push free, merge free). Read it live; never infer it from prose.

## Hard rules (also in CLAUDE.md; listed here because sessions submit generations)

- Keep one writer in this checkout. Preserve `experiments/`, `.runtime/` and any active ComfyUI queue.
- The server stays loopback-only. Never auto-submit generation on page load.
- Preserve full recipes and known prompt IDs; never repeat an uncertain submission.
- Successful generation, art acceptance and model licensing are three separate states. Record, never infer.
- Models and installed applications live outside Git; never edit installed ComfyUI or upgrade its packages.
  comfy-mcp (`comfy-local`) is read-only here: no update/install/download/launch/stop tools (`docs/AGENT-TOOLING.md`).
- Run `python -m unittest discover -s tests` and `python scripts/validate-repo.py` for app or catalog changes.
- Use native `rg` and `git` for repository search and state; `gh` for PRs and issues.
- Every PR body states each issue disposition: `Closes #N`/`Fixes #N` only for a complete issue,
  otherwise `Refs #N` plus the remaining acceptance. List multiple closures individually, recheck
  the live issue state before and after merge, and never use a closing keyword as a non-closing example.

## Codex-specific facts

- Branches from Codex sessions are named `codex/<topic>`; PRs are opened ready-for-review, never draft.
- Project MCP config is `.codex/config.toml` (no Docker gateway here; it is declared once at user scope).
- Skills: `.codex/skills/` mirrors `.claude/skills/` body-for-body; `tests/test_agent_harness.py` fails on
  drift. Change the Claude tree first, then port the body verbatim in the same commit.

## Grok-specific facts

- Branches from Grok sessions are named `grok/<topic>`; PRs are opened ready-for-review, never draft.
- Project config is `.grok/config.toml` (permissions only). MCP stays user-scope in `~/.grok/config.toml`;
  do not redeclare `comfy-local` or `MCP_DOCKER` here.
- Skills come from `.claude/skills/` via Claude compatibility. Do not add `.grok/skills/` (a third copy
  would collide and `tests/test_agent_harness.py` fails).
- Muse Code delegation (reviews, bug hunts, tests, bounded fixes) goes through the estate wrapper
  `py -3 ~/.claude/tools/muse_exec.py` under this repository's effective policy (no `delegation.json`:
  strict defaults, `max_workers` 3); the overnight swarm is `~/.claude/prompts/OVERNIGHT_MUSE_SWARM.md`.
  Run the wrapper with `run_terminal_command` (`batch --detach` + `batch-wait` for a wave); never
  `spawn_subagent` per Muse job. Muse never merges, pushes or decides.
- Ignore the Codex-specific facts above (`.codex/` paths, `codex/<topic>` branches).

## Skill routing

| Situation | Skill |
| --- | --- |
| Add or change a preset, workflow graph, catalog binding or variant | `studio-preset-slice` |
| Run one generation or comparison and record it honestly | `studio-execution-evidence` |
| Krita, Blender, Godot or articulated-prop adapter work | `studio-native-adapter` |
| Backend environments, launchers, ports, model installs, licence terms | `studio-runtime-models` |
| End of session: stop owned processes, closeout note, state and handoff | `studio-session-closeout` |
| Orientation, implementation loop, review, handoff | global `resume-repo-work`, `small-safe-slice`, `review-and-ship`, `verify-and-handoff` |
