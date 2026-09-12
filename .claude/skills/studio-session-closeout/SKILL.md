---
name: studio-session-closeout
description: "Close a Local Asset Studio session: confirm no queued or partial Studio work, stop only Studio-owned processes, write the dated closeout note, reconcile CURRENT_STATE.md and HUMAN_TODO.md, and hand off with changed/verified/NOT verified/residual risk. Use at the end of any session that ran the Studio or ComfyUI."
---

# Studio session closeout

## Use when / Do NOT use when

Use before ending a session that started the Studio, ComfyUI, an isolated backend, Blender, Krita or
Godot, or that produced execution evidence. Do NOT use for a docs-only session (global
`verify-and-handoff` is enough) and do NOT use it to tick creative or licensing choices.

## Guardrails

- Stop only processes the Studio owns (`.runtime/server.pid`, the ComfyUI pidfile, isolated backends)
  and only after `/api/jobs` shows no queued, running, uncertain or partial job. A user-started
  ComfyUI with its own queue is not yours to stop.
- Preserve outputs: name the full-resolution files that stay in ComfyUI's `output/` folder.
- Never write "verified" for a path you did not run this session; list it under NOT verified.
- `HUMAN_TODO.md` items stay open unless the human stated the decision in this session.

## Workflow

1. Check work state: `git status`, open PRs, `GET /api/jobs` and `/api/production`, and any worktree
   under `.claude/worktrees/`. Finish or park each item explicitly.
2. Reconcile `CURRENT_STATE.md`: add dated results with prompt IDs and timings, keep plans separate,
   correct nothing by deletion. Update `docs/` only for what actually ran.
3. Write `.runtime/closeout-<YYYYMMDD>.md`: merged PRs and SHAs, check results with counts, review
   threads resolved, runtime PIDs stopped and ports free, preserved outputs, disk headroom, credits
   spent (normally none), open human choices. It is gitignored evidence; quote from it in the handoff.
4. Stop owned runtimes in order: Studio server, then isolated backends, then primary ComfyUI; confirm
   no listener on 8191, 8192, 8194, 8188 that you started.
5. Tear down finished worktrees (plain `git worktree remove`, never forced) and confirm `main` is clean.
6. Hand off: changed / verified / NOT verified / residual risk, open `HUMAN_TODO.md` items, and the
   next safe slice. If harness files changed, note the `~/.claude/ESTATE.md` row that must follow.

## Read first

The previous `.runtime/closeout-*.md`; `HUMAN_TODO.md`; `CURRENT_STATE.md` head.
