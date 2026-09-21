# Reference Hold Observation Admission Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep retained reference-analysis resource holds blocking all new work while allowing bounded observation of already-known prompt IDs through a live Studio worker.

**Architecture:** Split worker liveness from new-work resource admission at the shared `Studio` boundary. `require_worker()` remains the full admission guard and delegates its liveness portion to a new `require_worker_observation()` method. Only known-prompt observation entry points use the liveness-only guard; Production's already-local terminal reconciliation stays before ordinary resume admission.

**Tech Stack:** Python 3 standard library, `unittest`, existing Studio worker/queue and mixed-batch recovery contracts.

**Spec:** GitHub issue #458 and its 17 September 2026 reconciliation comment.

## Global Constraints

- Do not weaken `reference_jobs.require_available()` for any path that can reserve, submit, render, resume inference or start analysis.
- Observation must still refuse a genuinely started-but-dead Studio worker.
- Observation must retain backend-switch, state, revision, history and ownership checks.
- Observation must never submit the unresolved mixed-batch POST or authorize later stages.
- No new queue, scheduler, store, retry path or runtime dependency.

---

### Task 1: Lock the admission boundary with failing regressions

**Files:**
- Create: `tests/test_reference_hold_observation_admission.py`

**Interfaces:**
- Consumes: `server.Studio.require_worker`, `server.Studio._resume_tracking`, `server.mixed_batch.command`, `server.Production.resume`, `server.Production._start`.
- Produces: executable contracts for `Studio.require_worker_observation()` and the exact observation call sites.

- [ ] **Step 1: Write the failing tests**

Add tests proving that a synthetic retained reference hold still fails `require_worker()`, but does not fail the new observation guard or mixed-batch known-receipt observation. Add a dead-worker case and source-level boundary assertions covering Studio observation, mixed-batch observation, Production reconciliation ordering and Production start admission.

- [ ] **Step 2: Run the focused test before production changes**

Run:

```console
python -m unittest tests.test_reference_hold_observation_admission -v
```

Expected: failure because `Studio.require_worker_observation` does not exist and both observation call sites still invoke `require_worker()`.

### Task 2: Add the liveness-only guard and move observation callers

**Files:**
- Modify: `app/server.py`
- Modify: `app/mixed_batch.py`

**Interfaces:**
- Produces: `Studio.require_worker_observation(self) -> None`.
- Preserves: `Studio.require_worker(self) -> None` as the full reference-hold plus liveness gate.

- [ ] **Step 1: Implement the minimal shared guard**

Add:

```python
def require_worker_observation(self):
    if not Studio.worker_available(self):
        raise StudioError('Studio worker is unavailable. Restart Studio; no work was queued or reserved.')
```

Keep `reference_jobs.require_available()` only in `require_worker()`, then delegate its liveness check to `require_worker_observation()`.

- [ ] **Step 2: Move only observation entry points**

Change `Studio._resume_tracking()` and mixed-batch `action == 'observe'` admission to call `require_worker_observation()`. Leave `Production._start`, ordinary Production resume after reconciliation, AV render, voice resume, reference-analysis create and normal Studio creation on `require_worker()`.

- [ ] **Step 3: Run the focused regression**

Run:

```console
python -m unittest tests.test_reference_hold_observation_admission -v
```

Expected: all tests pass.

### Task 3: Verify adjacent recovery and admission contracts

**Files:**
- No additional production files.

- [ ] **Step 1: Run focused neighbouring suites**

```console
python -m unittest \
  tests.test_reference_hold_observation_admission \
  tests.test_mixed_batch \
  tests.test_mixed_batch_owner \
  tests.test_production_terminal \
  tests.test_reference_jobs -v
```

Expected: zero failures and zero errors.

- [ ] **Step 2: Run repository validation and hosted CI**

```console
python scripts/validate-repo.py
```

Then require exact-head `Check studio`, Windows/runtime and relevant recovery workflows before marking the PR ready.

- [ ] **Step 3: Reconcile issue and PR state**

Document exact verification, leave the PR draft while CI is incomplete, and do not merge automatically.

## Implementation reconciliation

The production split is intentionally polymorphic: `require_worker()` calls `self.require_worker_observation()` after the reference-hold admission check. Duck-typed test doubles that delegate the full production method must therefore delegate the observation method as well. `StorageStudio` now exposes both delegates; production dispatch was not weakened to accommodate a partial fixture.

Temporary write-enabled development workflows have been removed from the branch. Ordinary exact-head repository CI remains the readiness gate.

Review reconciliation (Codex P1, confirmed independently and at runtime): moving `_resume_tracking()`
alone left the fix inert, because its only caller `_queue_observation()` still asked for full
new-work admission before dispatching. `_queue_observation()` now chooses the guard itself: the
liveness-only guard for a stopped, non-abandoned, `uncertain` job whose prompt IDs already pass
`_known_prompt_error()`, and `require_worker()` -- reference hold included -- for every other
resume, unknown job id or malformed state. `tests/test_reference_hold_observation_admission.py`
exercises `resume_job()` itself rather than the helper, in both the admitted and the refused
direction.
