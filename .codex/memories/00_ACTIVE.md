# Active gate — Local Asset Studio

Last updated: 2026-09-12

This file is a pointer, not a record. Executed evidence lives in `../../CURRENT_STATE.md`; authority in
`../../.agent-harness/tier.json`; human choices in `../../HUMAN_TODO.md`. All three outrank this file.

## Current authority

- Tier T2 daily-driver, push free, merge free, floorless. Re-read `tier.json` live.
- Merge with a merge commit, never squash. Ready-for-review PRs only; two review rounds maximum.

## Standing constraints

- One writer in this checkout. The stale second checkout under the user's `source/` folder (at PR #7)
  is not a work location.
- Never auto-submit generation; never repeat an uncertain submission; keep prompt IDs.
- Generated, accepted and licensed are three separate states. Hunyuan3D 2.1 and HY-Motion 1.0 exclude
  UK use; NoobAI excludes commercial products.
- Models, ComfyUI, `config/local.json`, `experiments/runs|uploads|workspace|projects/` and `.runtime/`
  stay outside Git.

## Lanes

- Studio app and catalog: `.claude/skills/studio-preset-slice`, `studio-runtime-models`.
- Evidence and closeout: `studio-execution-evidence`, `studio-session-closeout`.
- Native tools: `studio-native-adapter`.
- Offline game-asset planner: `docs/game-assets/AGENT-CONTRACT.md` and `agent-skills/game-assets/SKILL.md`.

## Parked or human-only

- The three creative choices in `HUMAN_TODO.md`.
- Portability follow-ups recorded at the PR #39 closeout: launcher profile readiness, optional Godot
  path validation, incomplete H3 bundle detection, padded atlas limits, custom primary ports.
