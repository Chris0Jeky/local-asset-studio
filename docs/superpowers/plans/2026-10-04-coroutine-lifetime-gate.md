# Coroutine Lifetime Gate Implementation Plan

**Goal:** Reject a passing offline suite that leaves unawaited-coroutine diagnostics, and preserve creation/fatal-error evidence for #1270.

**Architecture:** Retain the existing parent/worker boundary and hard lifetime deadline. The parent rejects narrowly recognized coroutine warnings after a real child exit. The dedicated worker records bounded creation origins before test discovery. No resource is forcibly closed and no garbage-collection policy is changed.

**Tech Stack:** Python standard library, unittest, real subprocess fixtures.

**Spec:** Issue #1270 and the existing resource-lifetime guard contract.

## Constraints and review focus

Keep default 600 seconds and hosted override 900 seconds, existing resource-warning and nonzero-exit policy, sharding, canonical entry point and actual shutdown wait. Preserve ordinary awaited/closed coroutine behavior. Check warnings during a test and atexit, suppressed ambient warning policy, diagnostics emitted on stderr without a stdout newline, and benign diagnostic text. This work does not establish the cause or resolution of the historical signal-11 crash.

## Task 1: Reproduce and reject coroutine-warning false success

- [x] Add real subprocess fixtures that execute the shipped parent and worker against a temporary test module.
- [x] Observe failing assertions for warnings during tests and finalization, plus creation-origin and fatal-dump coverage.
- [x] Add narrowly scoped warning recognition and bounded diagnostics. No synthesized CI data.
- [x] Re-run the seven new fixtures, Python compilation, diff validation and repository validation.
- [ ] Complete existing lifetime and canonical full-suite qualification, retaining any failures rather than bypassing them.

## Task 2: Publish verifiable source and handoff

- [x] Match changed preimages to immutable main blobs before building a connector commit.
- [x] Store implementation, regression tests, this plan and measured evidence in the publication tree.
- [ ] Reconcile final-head hosted checks and review before integration. Keep unverifiable checks separate from local evidence.

See `docs/maintenance/2026-10-04-coroutine-lifetime-gate.md` for exact source identities, measured local evidence and remaining gates.
