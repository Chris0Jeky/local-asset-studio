# `.claude/` — Claude Code execution layer

Repo facts and proving checks live in `../CLAUDE.md`; the Codex adapter in `../AGENTS.md`; review and
tier doctrine in the global laws. Nothing is restated here.

| Path | Purpose |
| --- | --- |
| `settings.json` | attribution trailers off; allow rules for the proving checks, local Git (status/diff/add/commit/switch; push still prompts), `gh` read and PR subcommands (no bare `gh api`), `rg`. No `defaultMode` (a project-scope mode would outrank the user's own), no hooks, no deny list: the repo is declared floorless in `../.agent-harness/tier.json`. Rules are prefix rules (`:*` only wildcards at the end of the token). |
| `settings.local.json` | gitignored personal overrides. Since Claude Code 2.1.257 a project-scope file cannot grant `bypassPermissions` or `auto`. |
| `rules/` | path-scoped rules that auto-load: `catalog.md` for presets/workflows/models, `evidence-docs.md` for state and evidence docs. |
| `skills/` | canonical repo-local skills (`studio-*`); `../.codex/skills/` is the body-identical Codex adapter, enforced by `tests/test_agent_harness.py`. |
| `worktrees/` | Claude-managed worktrees, gitignored; do not read by default. |

Tier and authority are declared only in `../.agent-harness/tier.json`; read it live rather than copying values here.
