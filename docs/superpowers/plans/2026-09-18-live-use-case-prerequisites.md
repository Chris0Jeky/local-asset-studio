# Deterministic Live Use-Case Prerequisites Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make live read-only UX journeys select real current Workspace evidence when available and report an explicit named skip when a prerequisite is absent or the success action would create state.

**Architecture:** Keep fixture mode byte-for-byte deterministic while adding a small live-prerequisite layer to `CaseRun`. Data-backed selectors resolve the fixture identifier when it exists, otherwise the first rendered live identifier, which is the current UI's newest-first order. A dedicated `LiveCaseSkip` outcome stops a journey before a missing-control record is fabricated. The matrix, table and summary distinguish PASS, FAIL and SKIP.

**Tech Stack:** Python 3 standard library, Playwright sync API, existing fixture/live UX matrix, `unittest`.

**Spec:** GitHub issue #486.

## Global Constraints

- Live mode remains loopback-only and read-only.
- Never click a control that creates server state merely to improve coverage.
- Fixture selectors and the 14 synthetic journeys remain unchanged in meaning.
- Missing live data is not success and not a UI dead end: it is a named environmental skip.
- Selector values read from the DOM must be safely escaped and bounded.
- Preserve zero generation submissions as a hard invariant.

---

### Task 1: Lock live prerequisite and skip semantics

**Files:**
- Create: `tests/test_live_use_case_prerequisites.py`

- [ ] **Step 1: Add failing pure and runner-level contracts**

Cover preferred-value retention, newest-rendered fallback, duplicate/blank removal, no-value handling, explicit `LiveCaseSkip`, zero-dead-end skip rows, and `SKIP` table rendering. Add source-boundary assertions that the affected asset/project/output drivers use the live prerequisite helpers rather than fixture-only identifiers.

- [ ] **Step 2: Run the focused test before implementation**

```console
PYTHONPATH=tests python -m unittest tests.test_live_use_case_prerequisites -v
```

Expected: fail because live prerequisite selection and skip outcome APIs do not exist.

### Task 2: Add bounded selector resolution and explicit skip accounting

**Files:**
- Modify: `tests/studio_use_cases.py`

**Interfaces:**
- Produce: `choose_live_value(values, preferred=None)`.
- Produce: `LiveCaseSkip`.
- Produce: `CaseRun.live_data_selector(...)`, `CaseRun.require_live(...)`, `CaseRun.skip(...)`.
- Extend matrix row: `skipped`, `skip_reason`.
- Extend top-level matrix: `skipped`.

- [ ] **Step 1: Implement pure selection and result labels**

Choose the preferred fixture identifier when rendered; otherwise choose the first unique non-empty DOM value. Return `None` when no candidate exists. Render skipped rows as `SKIP`, independently of pass/fail.

- [ ] **Step 2: Implement browser-bound prerequisite helpers**

Allow only `data-*` attributes with bounded safe names. Read visible DOM values in order, escape the selected CSS attribute value, and raise a named skip before calling `act()` when none exists. `require_live()` refuses absent, hidden or disabled prerequisites with the nearest available reason.

- [ ] **Step 3: Account for skipped journeys**

Catch only `LiveCaseSkip` in `run_case`. Preserve earlier measurements, set no failure, and do not manufacture a missing-control record. Add skipped totals to console and JSON output.

### Task 3: Migrate affected live journeys

**Files:**
- Modify: `tests/studio_use_cases.py`

- [ ] **Step 1: Resolve data-backed evidence dynamically**

Use current live values for library assets, pullable assets and review projects in:

- one-reference edit;
- three-reference edit;
- review-and-keep-winner;
- reuse-keeper-as-reference;
- frames-to-native-export.

- [ ] **Step 2: Stop before state creation with named reasons**

Restyle, Combine, drawn-pose, comparison preparation, review recording, handoff preparation, source attachment, workflow mutation and native-export preparation must report why live read-only mode stops instead of cascading into absent controls.

- [ ] **Step 3: Guard non-data prerequisites**

When the installed live Studio has no compatible recipe, completed output, reviewable study, loaded node catalog or exportable graph, report that specific prerequisite rather than `missing-control`.

### Task 4: Document and verify the live coverage contract

**Files:**
- Modify: `docs/UX-USE-CASE-MATRIX.md`

- [ ] **Step 1: Document PASS, FAIL and SKIP**

State that fixture mode remains the complete deterministic interface qualification. Live mode reaches whatever current local evidence supports, names unavailable prerequisites, and refuses state-creating completion steps.

- [ ] **Step 2: Run focused offline verification**

```console
PYTHONPATH=tests python -m unittest \
  tests.test_live_use_case_prerequisites \
  tests.test_use_case_matrix -v
```

- [ ] **Step 3: Run fixture browser verification**

```console
python tests/studio_use_cases.py --out .runtime/use-case-fixture-after-486.json
```

Expected: all fixture journeys pass, zero generation submissions, zero page errors.

- [ ] **Step 4: Require exact-head hosted CI**

Require the UX use-cases workflow and Check studio on the final clean head before marking the PR ready. Do not merge automatically.
