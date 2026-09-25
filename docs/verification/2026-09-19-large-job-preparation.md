# Verification: measured owned-resource cleanup

Date: 2026-09-19

Base: `chatgpt/178-stage-aware-admission` at
`f822fba06d34c901e9ed878d837875e99d9530b4`.

## Deterministic checks

The focused suite is intentionally inert: fake queue, process and counter adapters are
used; no ComfyUI request, process termination, generation or cloud action occurs.

```text
PYTHONPATH=/tmp/las306:/tmp/las306/app:/tmp/las306/tests python -m unittest discover -s /tmp/las306/tests -v
24 tests passed

python -m py_compile \
  app/large_job_prep_common.py \
  app/large_job_prep_flow.py \
  app/large_job_prep_actions.py \
  app/large_job_prep_journal.py \
  app/large_job_prep_runtime.py \
  app/large_job_prep_lifecycle.py \
  app/large_job_preparation.py \
  studio_prompt/resource_cleanup_http.py \
  studio_prompt/reference_job_http.py \
  tests/large_job_prep_test_support.py \
  tests/test_large_job_preparation_policy.py \
  tests/test_large_job_preparation_lifecycle.py \
  tests/test_large_job_preparation_http.py
passed
```

Covered failures include unknown counters, missing exact profiles, active/uncertain
work, queue changes before and after `/free`, PID reuse, process-inspection denial,
HTTP success with no measured relief, dropped `/free` response, interrupted durable
intent, restart startup failure, newly online unrelated listeners and dropped launch
return reconciliation without a second launch.

The HTTP seam is composed through the existing reference-job extension chain and is
separately exercised for same-origin JSON dispatch, cross-origin and media-type refusal,
and bounded validation errors. Two mutation checks also proved that
the dry-run branch and PID/creation-identity recheck tests fail when those gates are
removed, then return to green after restoration.

## Deliberately unclaimed

- no full-repository suite;
- no GitHub Actions or Codex review evidence;
- no live Windows `/free`, termination or restart;
- no GPU generation, throughput improvement or universal memory threshold;
- no owner-approved proof receipt.

Those environment-dependent claims remain part of issue #306's local acceptance, not
something deterministic fixtures can manufacture.

## Revival on main (2026-09-25)

The 19 Sep commit was cherry-picked onto `main` at `005df118`, after #656 (stage-aware
admission, #178) had merged. It supersedes draft PR #679. Against the merged code, its
focused suite failed: 14 failures and 1 error. The causes were:

- the fixture never registered its profile where `resource_admission.profile_for` reads
  it (`resource_admission_profiles`, keyed by the exact identity), so every run stopped at
  `profile_unknown`;
- `_evaluate` restored aggregate reservations as an unsigned record, which the merged
  `ReservationLedger.restore` rejects (it validates schema, owner and receipt hash);
- the fixture only imported when another test module had already put `app/` on the path.

The revival also adds these review fixes:

- a workflow bound to a backend other than the selected one is refused;
- `backends.busy` is held from the restart's terminate intent until the relaunched backend
  is ready or has failed, so `Studio.prepare`, `switch`, reference jobs and runtime
  recovery cannot start alongside it;
- a receipt with any attempted action reports `unknown`, never `refused`.

Tracked, not fixed here: #956, covering the `prepare()` host-commit preflight ordering and
journal rotation at 32 records.

```text
python -m unittest discover -s tests -p "test_large_job_preparation*.py"   30 tests OK
python -m unittest discover -s tests -p "test_resource_admission*.py"      21 tests OK
python -m unittest discover -s tests -p "test_server.py"                   76 tests OK
python scripts/validate-repo.py                                             PASS
python -m unittest discover -s tests   (at b2194480)                       4628 tests OK, 102 skipped, 909 s
```

Mutation checks: removing the `busy` claim fails the gate test, and removing the
unknown-after-action rule fails three tests. Nothing was run against the live Studio or
ComfyUI; the live acceptance described above is still owed.

## Live proof finding (25 Sep 2026)

The coordinator ran the owner-approved live proof on the configured PC. The command refused
every request, including `dry_run: true`, with "Active, partial or uncertain Studio work
blocks resource cleanup". The ComfyUI queue was empty and nothing was running. The blockers
were five Studio jobs from 12 and 23 Sep in `uncertain`, each with one `observing`
submission ("Restarted while remote job state was unknown; use Resume observation..."), and
production plans in `planned`, `awaiting_review`, `interrupted` and `uncertain`. The old
gate blocked every job in `uncertain`/`partial`, every unresolved submission and every plan
outside `completed`/`failed`/`abandoned`/`not_submitted`. A real library always holds such
records, so the command could never run.

The gate now classifies each record by what each action can harm:

| Class | Records | Blocks |
| --- | --- | --- |
| In-flight | job `queued`/`waiting`/`submitting`/`running`; job `pending_submission` (unless `abandoned`); an open submission that is not `observing` on an `uncertain`/`partial`/`interrupted` job; an unrecognized or missing job status; plan `queued`/`running`/`observing` or `pending_submission`; an unrecognized plan status; a busy reference job; a non-idle ComfyUI queue | every action, dry run included |
| Unresolved at rest | job `uncertain`/`partial`/`interrupted`, or with `observing` submissions; plan `uncertain`/`interrupted`. Each counts only while it retains an open prompt ID that the selected backend may still hold in `/history` | backend restart only (phase `restart_blocked_by_unresolved_work`) |
| At rest | plan `planned`/`awaiting_review`/`reviewed`/`published`/`stopped`/`completed`/`failed`/`abandoned`/`not_submitted`/`cancelled`; job `completed`/`failed`/`abandoned`/`not_submitted`/`cancelled`; an unresolved record with no open prompt ID | nothing |

A restart discards ComfyUI `/history`, which a later Resume observation needs (#864).
`/free` leaves history alone, so release stays allowed.

**History check.** Before a restart, and in a dry run that asks for one, the command checks
each unresolved record's open prompt IDs against the selected backend:

- **Which prompt IDs count:** retained `prompt_ids` and open submission receipts, minus
  receipts already `completed` or `failed`. For a plan, its attempts' jobs, or the attempt's
  own prompt IDs.
- **How it asks:** a read-only `GET /history/<prompt_id>` through the backend manager's
  loopback request path, with a 3-second timeout.
- **What the answer means:**
  - A mapping without the ID means the history is already gone, so the record does not block.
  - A mapping that contains the ID keeps the block.
  - So does any error, timeout, non-mapping answer or unreadable prompt list.
- **Bounds:** at most 20 records and 50 distinct prompt IDs are checked. Anything beyond the
  bounds stays blocking.
- **Receipt:** `blockers.history_checks` records each check as `{kind,id,prompt_ids,result}`,
  where `result` is `history_present`, `history_absent` or `unknown`.
- **Under the switch lock:** the recheck makes no network call. It lets through only records
  already proved absent with the same prompt IDs. Anything new blocks.
- **Refusal text:** "Open the job and use Resume observation to collect its result first;
  the restart would erase ComfyUI's record of it."

Every receipt carries `blockers`: the counts plus at most 20 `{kind,id,status,blocks}` items,
with in-flight blockers listed first. It also carries `history_checked`, which is false when
restart-level counts were not checked against history. Refusals list the blockers too.

**Dry run.** A dry run with unresolved work whose history may remain drops the restart from
`planned_actions` and sets `restart_blocked_by_unresolved_work`.

**Rechecks.** The rechecks before and after `/free` use the in-flight classification. The
pre-restart check and the recheck under the switch lock add the unresolved class. The check
after the restart uses the in-flight classification only, because the history is already gone
by then. The `backends.busy` hold and the `unknown` state after any attempted action are
unchanged.

```text
python -m unittest discover -s tests -p "test_large_job_preparation*.py"   46 tests OK
python -m unittest discover -s tests -p "test_resource_admission*.py"      21 tests OK
python -m unittest discover -s tests -p "test_server.py"                   83 tests OK
python scripts/validate-repo.py                                             PASS
```

Mutation checks each failed the new tests, and the tests passed again after restoration:

- restoring the old all-blocking rule;
- ignoring unresolved work before a restart;
- treating a submitting receipt as observing;
- dropping the recheck before `/free`;
- disabling the in-flight plan rule;
- treating absent history as blocking;
- treating a history request error as absent;
- removing the record bound;
- fetching history under the switch lock;
- dropping `cancelled` from the at-rest plans;
- letting an unknown job status through;
- using the restart level after the restart.

The live proof is re-owed on this classification. Nothing here called the live Studio or
ComfyUI.
