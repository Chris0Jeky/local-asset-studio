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
- [x] Publish all changed files on a focused branch/PR, verify remote blob identities and inspect check status (successful CI remains a separate merge gate).

## Publication receipt

Published in [PR #1981](https://github.com/Chris0Jeky/local-asset-studio/pull/1981),
branch `codex/critic-observation-replay`. Implementation commit:
`41eb25edbfa6ab8f3dab74c023f98c688d159cef`; tree:
`8e6dfb1c93233193263d24a74548692223b44427`.

All 17 published file identities matched the tested local manifest. Recreating the
remote tree from those blob identities returned the same tree. The final local
rerun passed 83 focused tests (69 + 13 + 1), zero skips, with ResourceWarnings as
errors; local-snapshot validation and whitespace checks passed. The limitations in
`docs/verification/critic-observation-2026-11-02.json` still apply.

At the publication check, the implementation commit's Check studio, Private
creation boundaries and Reversible asset Archive workflows were in progress.
This is not a green full-tree result. This documentation-only receipt does not
promote a runtime, threshold, artistic baseline or merge. Exact-head hosted checks
and independent review remain required; consult the live PR rather than treating
this dated observation as its current status.
