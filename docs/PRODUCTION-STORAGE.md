# Production project storage and recovery

Checkpoint: 13 September 2026, inspected main `a8eacdb108531c8c12a36c93f5a4f8a793e2fb74`.
Fixes the concrete publication defect in now-closed #96 through merged PR #153, advancing the
older Experiment Lab workstream #10. The live PR/issue map is in the [GitHub reconciliation](reconciliation/2026-09-13-github.md).
This is implementation/test evidence, not deployment or GPU/creative evidence.

## Reconciliation and scope

The oldest open issues still begin #2, #3, #9 and #10. #2/#3 retain real workstation
comparison and creative-acceptance requirements. #137, #142, #149 and #153 are merged;
#149 covers the scoped #140 browser-publication follow-up, while #9's broader provenance
and hardware scope remains open, so this pass does not duplicate it. Open
bundle UX and workflow-lineage PRs likewise keep their own stores and contracts.

At this main, `_create`, `native` and `articulated` committed their project/budget rows
before `mkdir` and `plan.json` publication. A filesystem failure left a `planned` row
that could reserve work and run despite incomplete project storage. The original
47,144-byte `production.py` was reconstructed and matched Git blob
`ddeee87ede7dc2c25afa8e8c4013dfcdd662d629` before modification.

The existing AV creation path already writes a plan and incomplete marker before
its transaction. This change applies that ordering to **comparison, native export
and articulated prop** projects, including character comparisons via `_create`.
AV and voice retain their separate storage/execution contracts. No new executor,
SQLite database, job queue, schema migration, generation route or model dependency is added.

## Publication protocol

```text
existing input/graph/editor preflight
  -> existing writer transaction and budget/duplicate checks
  -> exclusive project directory + .incomplete-create marker
  -> atomic plan.json write, file flush and content/fingerprint readback
  -> insert project row and commit budget/project transaction
  -> recheck plan and remove the incomplete marker
  -> return the planned project (still no queue or generation)
```

`app/project_storage.py` owns only filesystem publication and inspection.
`Production._insert_materialized` joins it to the existing transaction. A deterministic
character case already in SQLite is rejected before touching its directory; existing
shared budget allowances and reservations survive duplicate or failed child creation.

A directory collision is never adopted or overwritten. Partial directories, plans
and incomplete markers remain evidence. No compensation routine deletes files or
resets budgets. Only metadata writes (up to **16 MiB per serialized plan**) are inside
the transaction; graph preparation, node/network checks and tools remain outside.
The bounded writer-lock duration is a deliberate trade-off for straightforward
visibility and rollback, not a claim that files and SQLite share an atomic commit.

| Failure boundary | Result |
| --- | --- |
| Directory creation | No new committed project/budget; an existing colliding directory stays untouched. |
| Marker, plan write, flush or readback | SQLite rolls back; any created files remain. A marker-write failure may leave only an empty unregistered directory. |
| SQL insert or commit | Created files and marker stay; the transaction's new rows roll back, including a newly created root budget. |
| Process exit before commit | SQLite recovery removes the uncommitted rows; retained filesystem materialization is not auto-imported. |
| Process exit or marker removal failure after commit | The row exists but the marker blocks admission. Inspect it; do not blindly repeat creation. |
| Lost successful create response | Inspect existing rows/files first. Generic comparison creation is not an exactly-once API and this change does not add idempotency keys. |

File fsync/readback and SQLite rollback are exercised. Sudden power loss, storage
hardware failure and arbitrary external filesystem mutation are not made atomic.

## Existing rows and execution admission

On startup, each affected project receives a read-only storage inspection. Missing,
non-regular, linked, oversized, unreadable or changed `plan.json` files, a directory
link/junction, an invalid retained fingerprint, or a retained incomplete marker are
reported as `state.storage_issue` with a timestamp. The project stays listable and
the public message labels this as a **startup** observation, not fresh live status.
The normal queued/running restart-to-interrupted behavior remains unchanged;
this new inspection does not rewrite uncertain/terminal/review statuses, attempts,
artifacts, prompt IDs, graphs, stop-tracking authorizations or root reservations.

Fresh checks also run before Start reserves/enqueues work, before Resume changes
continuation consent, at worker entry, per comparison stage, after late preparation
and immediately before dispatching a queued stage. A cached restart diagnosis is
never the admission authority. A failure authorizes neither generation nor automatic
native-tool work. A reservation already made before later file loss remains retained;
it is not a refund or evidence that nothing ran.

A new failure propagated through the existing worker error path can still produce
a failed project, but no observed missing-plan condition licenses a new dispatch.
Manual deletion after the last check can still race a running process; these are
bounded observations, not an operating-system-wide lock. Outputs already in Workspace
and Gallery's independent known-prompt observation remain intact.

## Operator recovery

Do not delete the row, reset a budget or rerun a generation to repair project storage.
Use the configured `experiments_root/projects/<project-id>` and its existing
`projects.sqlite3`, not an empty folder in a different checkout.

First inspect the database plan, `plan.json`, any `.incomplete-create` marker and
retained attempts/jobs. A directory without a row is an interrupted creation, not a
startable project. A row with an incomplete marker needs explicit reconciliation;
automatic startup never removes the marker or reconstructs the directory.

Restore only the exact retained plan from a trusted backup or the matching database
record after inspecting the interrupted operation. Do not substitute today's preset
or fabricate a different fingerprint. Removing a retained marker is appropriate only
after confirming the row/plan identity and that no writer is still creating it.
Keep unrelated and partial files. These are operator actions, not automatic repair.

Starting Studio again refreshes the startup diagnosis without enqueuing work. Every
explicit Start/Resume rechecks files even without a restart. Restored files alone do
not start or resume anything. For uncertain known prompts, use Gallery observation
rather than generating a replacement; Production continuation remains a separate
explicit action. A previously failed comparison may need an explicit branch after
review, consistent with its existing status policy.

## Verification and limits

`tests/test_production_storage.py` has **27 tests** using actual Production, SQLite
transactions and temporary files, with Studio preparation/editor boundaries inert.
It includes real deferred-constraint commit failure, an independent SQLite reader,
and real child processes exiting before and after commit. Other cases cover all
three creators, partial writes, failed readback, collisions, parent budgets,
deterministic duplicates, legacy rows, altered/oversized plans, symlinks, queued/late
dispatch, unchanged review evidence, and explicit restore without automatic work.

`tests/test_production_storage_integration.py` adds **four full-Studio tests** for
actual creation/queue persistence, legacy restart refusal, native-export planning,
and retained-prompt recovery after explicit restoration. Comfy replies are synthetic;
no GPU inference is implied by a simulated successful response.

Local focused result: **31 discovered, 27 passed, four full-checkout skips**. GitHub
could not be resolved from the source container, so it is a partial workspace, not
a full clone. Local peer imports (settings/prompt helpers, review/AV initialization,
native planning adapters) use inactive test stubs outside Git. Committed tests import
real repository modules and mock only their documented seams; hosted CI must establish
the integration/full-suite results. All four published implementation/test blobs match
the locally tested files. Re-running against the original Production class exposes
startable rows after filesystem failure and the missing admission/reconciliation gates.

```sh
python -m unittest discover -s tests -p test_production_storage.py -v
python -m unittest discover -s tests -p test_production_storage_integration.py -v
python -m unittest discover -s tests -p test_production.py -v
python -m unittest discover -s tests
python scripts/validate-repo.py
```

The dedicated Python 3.12 CI matrix runs the new and existing Production suites on
Linux and Windows; normal CI remains the full-suite/validator gate. Test results do
not certify a Windows workstation deployment, live ComfyUI, native editor execution,
model feasibility, artistic acceptance or licensing.

`HUMAN_TODO.md` is untouched. Its creative decisions remain answered. The owner-controlled
Windows restart must respect the active downloads/saved-work gate recorded in the current
closeout; this change neither requests nor performs that restart.

## Primary technical references

- [SQLite transactions](https://www2.sqlite.org/lang_transaction.html): writer transactions,
  visibility and commit failure semantics. Files outside the database are not part of that transaction.
- [Python sqlite3 connection context manager](https://docs.python.org/3.12/library/sqlite3.html#how-to-use-the-connection-context-manager):
  rollback when the body or commit fails; connections still need explicit closure.

These references informed the publication ordering and real commit-failure tests;
they do not replace tests against the Studio's own code.
