# Known-prompt observation and resource admission (#608)

## Boundary

A reference-analysis resource hold prevents new resource-consuming work. It does
not prevent the existing worker from reading retained prompt IDs or reconciling
already-terminal receipts. `Studio.resume_job()` still requires worker liveness,
no backend switch, an inactive eligible job and a consistent non-empty one-to-one
mapping between `prompt_ids` and submission receipts. A `pending_submission` key,
even with an empty/null value, does not earn the observation-only path.

`Studio._observation_error()` is the common eligibility projection for ordinary
resume dispatch, stopped-tracking resume, and the public stopped-resume capability.
Stopped tracking requires an uncertain job with unresolved receipts. Ordinary
resume also supports terminal receipt reconciliation for an uncertain/partial
job; that path may complete entirely from local evidence. Other invalid states
retain the full admission guard before returning their refusal.

The command queues the existing `observe` operation. `_resume()` reads history
and materializes retained results; it does not submit a new `/prompt`, prepare a
replacement graph, refill an allowance or cancel remote work. Lost history keeps
the original prompt identity and uncertain outcome. Reads of remote history are
not authentication or a claim that an unknown submission never happened.

## Deliberately unchanged owners

- `Studio.prepare()` and job creation still require full admission.
- Production Start and ordinary project Resume still require full admission:
  Resume can continue never-started stages and is not universally observation.
- Voice resume can schedule unsynthesized lines; it remains guarded.
- AV rendering and reference-analysis creation remain guarded.
- Existing mixed-batch observation retains its separate revisioned command and
  its known/unknown split. The ordinary path never consumes a pending marker.
- No model, backend, filesystem-output policy or HUMAN_TODO decision changes.

## Reconciliation

Checked against main `f8fcc40f7388c23d13309c20c2776017a20004b2` and the owner ZIP.
The previous `fix/reference-hold-observation-admission` branch belongs to merged
#567. Searches found no active #608 implementation; #684 only recorded it as next
work. The active #656/#674/#679 resource stack and #689 shutdown diagnostics are
not duplicated. The #244/#245 transforms already shipped in #274/#279 and require
remaining-contract audit, not a replacement normalization/composition subsystem.

## Regression evidence

Before the correction, eight new public-entry-point test methods produced four
assertion failures and six subtest errors: ordinary resume hit the retained hold,
and the stopped-resume capability advertised ineligible states. After correction:

```console
python -m unittest discover -s tests -p 'test_ordinary_observation_admission.py' -v
python -m unittest discover -s tests -p 'test_reference_hold_observation_admission.py' -v
python -m unittest discover -s tests -p 'test_observation_new_work_gates.py' -v
python -m unittest discover -s tests -p 'test_server.py'
python tests/check_full_suite_lifetime.py
python scripts/validate-repo.py
```

Fixtures use temporary storage and inert backends. Behavioral coverage includes
uncertain/partial observation, terminal reconciliation, store reopen, history
failure, invalid/mismatched/duplicate identities, empty pending markers, dead
worker, backend switching and two concurrent clients with one queued observation.
Separate public Production/Voice/AV/Reference commands prove the new-work hold.
The AV test explicitly skips without configured FFmpeg/FFprobe. No GPU or native
creative acceptance is established by these software tests.

Full-suite/CI results are recorded on the PR for the exact published head, rather
than asserting that a historical green run covers later edits. Broader #458
acceptance remains separate from the bounded ordinary-resume correction.
