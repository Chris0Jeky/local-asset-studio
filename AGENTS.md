# AGENTS.md — Local Asset Studio (Codex adapter)

Shared facts — what the Studio is, how to run it, the per-seam proving checks, architecture, pitfalls,
tier and authority — live in **`CLAUDE.md`** and are not repeated here. Global working agreements reach
Codex through `~/.codex/AGENTS.md`. This file carries only the Codex-runtime delta and routing.

## Start here

1. `CLAUDE.md` — repo facts, proving checks, architecture, pitfalls.
2. `CURRENT_STATE.md` head — executed evidence versus plans; reconcile claims against code and `.runtime/`.
3. `HUMAN_TODO.md` — human-only creative choices; surface open items in every summary, never tick them.
4. `docs/PROJECT-OPERATING-MODEL.md` — issue type/readiness, three-line WIP limit, stack order and evidence placement.
5. `.codex/README.md` and `.codex/memories/00_ACTIVE.md` — Codex routing and the active gate.
6. Authority: `.agent-harness/tier.json` (T2, push free, merge free). Read it live; never infer it from prose.

## Hard rules (also in CLAUDE.md; listed here because Codex sessions submit generations)

- Keep one writer in this checkout. Preserve `experiments/`, `.runtime/` and any active ComfyUI queue.
- The server stays loopback-only. Never auto-submit generation on page load.
- Preserve full recipes and known prompt IDs; never repeat an uncertain submission.
- Successful generation, art acceptance and model licensing are three separate states. Record, never infer.
- Models and installed applications live outside Git; never edit installed ComfyUI or upgrade its packages.
  comfy-mcp (`comfy-local`) is read-only here: no update/install/download/launch/stop tools (`docs/AGENT-TOOLING.md`).
- Run `python -m unittest discover -s tests` and `python scripts/validate-repo.py` for app or catalog changes.

## Codex-specific facts

- Branches from Codex sessions are named `codex/<topic>`; PRs are opened ready-for-review, never draft.
- Project MCP config is `.codex/config.toml` (no Docker gateway here; it is declared once at user scope).
- Skills: `.codex/skills/` mirrors `.claude/skills/` body-for-body; `tests/test_agent_harness.py` fails on
  drift. Change the Claude tree first, then port the body verbatim in the same commit.
- Use native `rg` and `git` for repository search and state; `gh` for PRs and issues.
- Every Codex PR body states each issue disposition: `Closes #N`/`Fixes #N` only for a complete issue,
  otherwise `Refs #N` plus the remaining acceptance. List multiple closures individually, recheck
  the live issue state before and after merge, and never use a closing keyword as a non-closing example.

## Skill routing

| Situation | Skill |
| --- | --- |
| Add or change a preset, workflow graph, catalog binding or variant | `studio-preset-slice` |
| Run one generation or comparison and record it honestly | `studio-execution-evidence` |
| Krita, Blender, Godot or articulated-prop adapter work | `studio-native-adapter` |
| Backend environments, launchers, ports, model installs, licence terms | `studio-runtime-models` |
| End of session: stop owned processes, closeout note, state and handoff | `studio-session-closeout` |
| Orientation, implementation loop, review, handoff | global `resume-repo-work`, `small-safe-slice`, `review-and-ship`, `verify-and-handoff` |
