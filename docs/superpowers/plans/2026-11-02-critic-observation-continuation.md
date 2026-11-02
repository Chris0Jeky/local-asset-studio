# Critic Observation Continuation Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans task by task; observe red/green tests and retain results.

**Goal:** Fix #1977 and make retained sentinel observations usable by the existing offline policy evaluator.
**Architecture:** Preserve detector output; validate it at the sentinel adapter. Add explicit input selection to the existing bounded replay rather than introducing another queue or comparator.
**Tech Stack:** Python standard library and existing Pillow; no additional runtime dependencies.
**Spec:** `docs/superpowers/specs/2026-11-02-critic-observation-continuation.md`.

## Global constraints

No production threshold changes, native/model execution, environment changes, private assets or inferred art acceptance.
Record original source identities; never overwrite concurrent remote work or existing evidence outputs.

## Review focus

- Failed/incomplete evidence must not agree with either warning or quiet primary evidence (task 1).
- Malformed booleans/counts must not discard an otherwise usable primary result (task 1).
- Legacy successful signals remain compatible, but absent metadata cannot qualify replay (tasks 1–2).
- Sentinel envelope/observation contradictions and wrong input selectors cannot become a clean score (task 2).
- The public evidence must be reproducible from exact scripts and contain only synthetic data (task 3).

## Task 1 — truthful sentinel adapter

Files: modify `scripts/blender_sentinel.py`; add `tests/test_blender_critic_receipt.py`.
Consumes `render_critic.check`; produces retained `second_signal.observation` and unavailable/error state.
- [x] Write real-image and malformed-result tests and run them against the exact base sentinel.
- [x] Preserve the observation, validate before summarising, and guard agreement.
- [x] Rerun focused tests; inspect the diff for unrelated changes.

## Task 2 — explicit saved-sentinel replay

Files: modify `scripts/render_critic_policy.py`; add `tests/test_render_critic_sentinel_replay.py`.
Consumes task 1 observation; extends `replay(..., input_kind='receipt')` with `'sentinel'`.
- [x] Write failing selector, consistency, missing-observation, exclusive-output and CLI tests.
- [x] Validate the declared sentinel schema and observation without following document paths.
- [x] Retain document byte hash and source selector; rerun policy and integration tests.

## Task 3 — retained experiment and handoff

Files: add `research/agentic-creation/critic-observations/` evidence and README; add a dated verification document.
- [x] Regenerate the owned 24-case study using exact implementation hashes.
- [x] Commit compact raw observations, outcomes and deterministic verification instructions; do not commit private/media archives.
- [x] Record executed versus unexecuted checks, review limitations and the remaining native acceptance.
- [ ] Publish all changed files on a focused branch/PR and verify remote blob identities and checks.
