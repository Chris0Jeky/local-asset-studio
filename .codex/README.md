# Codex workspace layer

The Codex-facing routing for Local Asset Studio. Canonical facts stay in `../CLAUDE.md`; the Codex
contract in `../AGENTS.md`; authority in `../.agent-harness/tier.json` (read live). This layer adds
only the Codex runtime config, the active gate, and skill adapters.

## Start here

1. `../AGENTS.md` (the Codex contract) and its shared facts in `../CLAUDE.md`.
2. `memories/00_ACTIVE.md` — the active gate: what is running, what is parked, what needs a human.
3. `../CURRENT_STATE.md` head for executed evidence; `../HUMAN_TODO.md` for human-only choices.
4. `skills/README.md` — pick the one Studio skill that matches; global skills cover the rest.

## What is here

| Path | Purpose |
| --- | --- |
| `config.toml` | project-scoped Codex settings: workspace-write sandbox, on-request approvals, the two MCP servers this repo uses. The Docker MCP gateway is declared once at user scope; never re-declare it here. |
| `memories/00_ACTIVE.md` | a pointer, not a record; edited on pivots only. |
| `skills/*` | Codex adapters of `../.claude/skills/*`: identical bodies, Codex frontmatter, `agents/openai.yaml`. `tests/test_agent_harness.py` fails on drift. |

The root deliberately has no `.codex/hooks.json`: the repo is declared floorless (`floor_wiring: none`).

## Development loop

1. Confirm the live state: `git status`, `../CURRENT_STATE.md` head, and whether the Studio or ComfyUI
   is already running (`http://127.0.0.1:8191/api/identity`, `http://127.0.0.1:8188/system_stats`).
2. Branch as `codex/<topic>`; keep one writer in this checkout; preserve `experiments/` and `.runtime/`.
3. Run the narrowest proving check from the `../CLAUDE.md` table, then the full suite before the PR.
4. Open the PR ready-for-review; triage review comments once by the global severity bar.
5. End with `studio-session-closeout` when anything was launched or generated.
