# Retained board availability after structural edits

Issue #715; continuation follow-up to #699, #345 and #606.

## Ownership contract

An upload or library copy writes to an exact destination: a structural board
edit still invalidates that pending write. An availability check instead reads
an exact record and its filename/hash. Reordering that record, or clearing a
different slot, must not waive its pending check or drop the resulting finding.

`references.js` retains active observation descriptors outside reference records.
On a clear/reorder it carries only a current-epoch check that still owns at least
one occupied record with the same bytes. It advances that check's epoch and
counts it once before rendering. It does not submit another request. Read results
match retained record identity, not an obsolete numeric index.

Clearing the final observed occupied record retires the check. An empty optional
slot is never a missing picture. New checks and committed attachments still
supersede old observation tokens even when filename/hash repeat. Failed writes do
not supersede observations of unchanged bytes. Recipe resets remain invalidating;
a retired check cannot decrement pending work belonging to a later epoch.

The canonical `reference-model.js` remains unchanged. Named `lastReference`
lineage remains independent from board `parent_asset` claims. Observation
descriptors are transient: no new persisted field, store, readiness projection,
HTTP route, automatic recheck, upload, retry or generation authority is added.

## Causal reproduction

On parent #699 at `ee797b740e1485c3abc172af739f14f9dbc14550`, the exact
`references.js` blob is `541ac5e6d08373a569feb996591b67f3b30a3694`.
Hold a saved board's availability response, then clear another occupied slot or
move a slot up/down. The old handler resets `referencePending` to zero and later
discards the response on epoch mismatch. Readiness therefore becomes true for
retained unchecked bytes, including files later reported missing or changed.
This demonstrates misleading readiness, not a bypass of server Prepare checks.

`tests/reference_structural_observations.cjs` uses the production clear/reorder
handler, renderer, parent-claim helpers and shared reference model with a minimal
DOM and deferred transport. Against the exact parent reference owner, 10 of its
15 cases fail and 5 pass. With the correction, all 15 pass.

Coverage includes available/missing/hash-mismatch/offline results; both reorder
directions; repeated reorders; last-file clear with an optional board; reset;
old upload cancellation; committed upload/library replacement with identical
bytes; failed replacement; overlapping checks; and pending-count isolation.
It asserts retained source lineage, live readiness, no extra requests and no
observation fields in the attached payload.

## Verification commands

```sh
node --test tests/reference_structural_observations.cjs
python -m unittest discover -s tests -p 'test_reference_structural_observations.py' -v
node --test tests/reference_restore_observations.cjs tests/reference_attachment_races.cjs tests/workbench_handoff_guards.cjs tests/workbench_board_source_recovery.cjs
python tests/check_full_suite_lifetime.py
python scripts/validate-repo.py
```

The Python wrapper requires all 15 cases to execute without skips. The existing
read-only Restyle workflow runs the new contracts alongside prior attachment and
restore contracts, then the native browser journey, on Ubuntu and Windows with
an explicit pull-request-head checkout. Full repository evidence belongs to the
new head, not a passing parent workflow.

Local reproduction used the supplied ZIP plus the exact, blob-verified parent
reference owner. Other parent PR files were not all present in that scaffold;
its focused checks are not represented as a complete local checkout of #699.
The published child is based on the exact remote parent tree, preserving every
untouched file. Hosted complete/native checks and their SHAs are recorded in the
PR discussion. No live model or subjective creative acceptance is claimed.

## Stack and remaining acceptance

Review #692, then #699, then this child. #695 (saved-lineage documentation and
contracts) and #709 (optional-board compiler) are independent. This slice does
not activate an optional board, change catalog defaults, qualify a Restyle route,
resolve HUMAN_TODO q-27(b), or complete the wider #343/#351/#357 programme.
