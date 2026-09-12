---
name: studio-execution-evidence
description: Run one real generation, comparison or probe through Local Asset Studio or ComfyUI and record it honestly with prompt ID, backend, timing and inspected outputs. Use when proving a preset, curating an experiment or updating CURRENT_STATE; not for graph authoring or model installs.
---

# Studio execution evidence

## Use when / Do NOT use when

Use when a slice needs a real run: proving a preset, a Workflow Lab recipe, an H3 or HiDream attempt, a
bounded comparison, or refreshing `CURRENT_STATE.md`. Do NOT use to author graphs
(`studio-preset-slice`), to change environments (`studio-runtime-models`), or when the user asked for
schema checks only.

## Guardrails

- One deliberate submission. If the outcome is uncertain (timeout, lost connection, missing history),
  recover the prompt ID from `experiments/runs/<job>/` or ComfyUI `/history`; never resubmit to find out.
- Do not claim an output was inspected unless you opened it (frames decoded, image viewed, GLB loaded).
- Generated is not accepted and not licensed. Write all three states separately; art acceptance and
  licence decisions stay with the human in `HUMAN_TODO.md`.
- Never spend paid credits (Buzz, hosted APIs) or change paging/system settings to make a run pass.

## Workflow

1. Preflight: `GET /api/health` and `/api/backends` (or `.runtime/backend-state.json`); confirm the
   right backend is active, the queue is empty, and disk headroom is known. Note the machine state.
2. Submit once through the Studio UI or `POST /api/jobs` with the preset id and controls, or through
   `scripts/run-batch.py` for serial batches. Capture the job id and ComfyUI prompt ID immediately.
3. Wait on `/api/jobs/<id>`; on a stall, read `.runtime/*-out.log` and `*-error.log` before deciding.
4. Inspect every output visually and structurally (dimensions, frame count, audio, GLB parts). Write what
   you saw in plain words; a tool exit code is not a review.
5. Record: recipe JSON via `/api/jobs/<id>/recipe`, prompt ID, backend, wall time, peak memory if
   measured, and inspection notes, into `experiments/curated/<topic>/` (small files only) and a dated
   paragraph in `CURRENT_STATE.md` that keeps plans separate from results.
6. Flip `verified` in the catalog only for the exact preset and graph hash that ran. Surface open
   `HUMAN_TODO.md` choices in the summary.

## Read first

`CURRENT_STATE.md` head; `docs/EXPERIMENTS.md`; the matching `experiments/curated/*/README.md`; for H3 or
HiDream, `docs/H3-WINDOWS.md` or `docs/HIDREAM.md`.
