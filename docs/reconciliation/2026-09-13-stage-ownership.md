# Chronological continuation: mixed-batch stage ownership

Inspected main: `28cfe3b54e221ce0f18b5dd8615dfc82dd6b49d3`, captured from GitHub
13 September 2026 at 22:12 UTC. The snapshot had 49 open issues and no open PRs.
PR #198 and its #95/#98/#110 fixes are merged; PR #224 and #187 mixed-batch
recovery are also merged/closed. Those implementations were retained.

## Oldest-open reconciliation

| Issue | Existing flow and remaining work |
| --- | --- |
| #2 | Explicit isolated-backend switching and recovery exist. Higher-step HiDream/native runtime acceptance remains; no workstation switch was made here. |
| #3 | Current state contains newer image baselines, native proofs and a visually rejected Wan control. Completed inference is not accepted artwork; controlled creative/native comparisons remain. |
| #9 | Intake/publication, exact loader readiness and resource guidance already exist. Complete provenance/bundle/runtime evidence remains; #97's backend-schema capture/replay is a separate, non-overlapping slice. |
| #10 | Shared plans, reservations, materialization, clocks, retained-prompt recovery and mixed-batch commands exist. This change addresses the concrete ownership follow-up reported after #224; accepted exports and broader creative demonstrations remain. |

#97 is not stale bookkeeping: its recorded primary pass still has the AniFox
failure and lacks six matching isolated-backend checks. #204's wider reload
acceptance also must not be inferred merely from its merged implementation PRs.
Newer native Krita work remains with its owner; none of its files are modified.

## Confirmed defect and correction (#228)

The normal Production writer creates a project-scoped attempt. But the reader
previously trusted a stored `attempts[stage].job_id` without checking its owner.
A deliberately mislinked stored attempt could borrow another project's disposed
mixed batch, offer reconciliation and mark the wrong project failed. This was a
reported local-data-integrity gap, not a demonstrated public-route exploit or
an automatic generation path.

The same ownership predicate now serves capability projection and the locked
local reconciliation path. It requires a valid plan fingerprint, canonical
in-range stage index, unique job association, matching job/attempt identity,
`job.project_id`, preset, backend URL and pinned graph. No new mandatory receipt
field or deterministic-ID migration is introduced for existing jobs.

An invalid association is **not dropped from the candidate set**: silently
ignoring it would let Resume fall through toward ordinary execution. Instead,
`can_reconcile_batch` is false, the read-only projection exposes
`batch_reconciliation_error` and an explanatory message, and Resume or a stale
Production dispatch refuses before admission, time accounting or a state write.
Existing receipt-integrity checks still decide whether a correctly associated
batch is actually disposed.

A valid local disposition remains non-executing: it keeps remote uncertainty,
original recipe/workflow/state evidence, outputs, reservations and prior stop
history. New work still needs an explicit separately budgeted repair branch.
This check is scoped to mixed-batch reconciliation; it is not a general migration
or tenant-security boundary over every historical job reference in Studio.

## Proving checks and red/green evidence

```console
python -m unittest discover -s tests -p test_mixed_batch_owner.py -v
python -m unittest discover -s tests -p "test_mixed_batch*.py" -v
python -m unittest discover -s tests
python scripts/validate-repo.py
```

Nine new methods run actual Production/Workspace fixtures and retained job
files. Before the fix, eight negative methods failed (12 failing subcases),
while the matching legacy control passed. They cover foreign/missing owner,
noncanonical/out-of-range stages, one job linked to two stages, changed graph,
preset or backend, a mapping alias, restart and valid idempotent legacy recovery.
All 49 mixed-batch tests pass with the correction. The pre-existing two-stage
fixture now uses the second stage's actual pinned graph rather than copying the
first stage's graph and pretending it belongs to both.

Refusals preserve the private project record, exact job files and in-memory job
records, queue, requests and budget. Direct Resume and stale dispatch are both
checked before worker, clock and bundle-preflight entry. The existing Production
storage CI already discovers `test_mixed_batch*.py` on Linux and Windows, so no
new workflow is needed for this slice.

The baseline full suite ran 1,674 tests with 16 skipped and passed. Final
integrated and hosted checks are recorded against their exact heads in the PR,
not inferred from this baseline. Test diagnostics/deprecation warnings are not
silently relabelled as a warning-free result.

## Boundaries and owner handoff

This session changed no model files, ComfyUI packages, user configuration,
workstation processes or generation queues. All loopback services exercised here
are inert test fixtures. No GPU, native-artwork or rights acceptance is claimed.
`HUMAN_TODO.md` q-1 through q-4 are already answered; no repeated decision or
restart is requested. The exhausted character pilot, uncertain portrait, parked
AniFox transfer and rejected Wan output remain untouched. Creative selection and
acceptance remain owner decisions.
