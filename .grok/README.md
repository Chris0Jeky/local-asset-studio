# Grok workspace layer

The Grok-facing routing for Local Asset Studio. Canonical facts stay in `../CLAUDE.md`; Codex
delta in `../AGENTS.md`; authority in `../.agent-harness/tier.json` (read live). This layer adds
only Grok runtime config. It does **not** copy skills: Grok loads `../.claude/skills/` via Claude
compatibility (`grok inspect` labels them `project [claude]`).

## Start here

1. `../CLAUDE.md` (canon) and the Grok section of `../AGENTS.md`.
2. `../CURRENT_STATE.md` head for executed evidence; `../HUMAN_TODO.md` for human-only choices.
3. `../.claude/skills/README.md` — pick the one Studio skill that matches (`studio-preset-slice`,
   `studio-execution-evidence`, `studio-native-adapter`, `studio-runtime-models`,
   `studio-session-closeout`); global skills cover the rest.

## What is here

| Path | Purpose |
| --- | --- |
| `config.toml` | project-scoped Grok settings: permission allow rules for proving checks. MCP stays at user scope in `~/.grok/config.toml`; never redeclare `comfy-local` or `MCP_DOCKER` here (one gateway per runtime). |
| `README.md` | this file. |

There is no `.grok/skills/` (a third copy would collide with `.claude/skills/` and fail `tests/test_agent_harness.py`). There is no `.grok/hooks/` : the repo is declared floorless (`floor_wiring: none`). Path rules live in `../.claude/rules/` and Grok already scans them.

## Development loop

1. Confirm the live state: `git status`, `../CURRENT_STATE.md` head, and whether the Studio or ComfyUI
   is already running (`http://127.0.0.1:8191/api/identity`, `http://127.0.0.1:8188/system_stats`).
2. Branch as `grok/<topic>`; keep one writer in this checkout; preserve `experiments/` and `.runtime/`.
3. Run the narrowest proving check from the `../CLAUDE.md` table, then the full suite before the PR.
4. Open the PR ready-for-review; triage review comments once by the global severity bar.
5. End with `studio-session-closeout` when anything was launched or generated.

## Muse swarm from this checkout

A Grok session here may coordinate Muse Code: `~/.claude/skills/delegate-to-muse/SKILL.md` is the
procedure, `py -3 ~/.claude/tools/muse_exec.py` the wrapper, `~/.claude/prompts/OVERNIGHT_MUSE_SWARM.md`
the overnight mission (paste it at this root). This folder is Grok-trusted, so `AGENTS.md`/`CLAUDE.md`
load. Run the wrapper yourself (`batch --detach --run-dir <dir>`, then `batch-wait --run-dir <dir>
--brief --min-severity high`); one `spawn_subagent` per Muse job costs a fresh Grok context each
(measured 2026-09-20). Draft PRs and stacked children are skipped by the prompt's filters; hosted CI
must be green at the exact head before any merge (law 1).
