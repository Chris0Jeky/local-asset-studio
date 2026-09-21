# Bind comparison diagnostics to their captured source bytes

Follow-up to #435 and #433, after #693's bounded input consumption.

## One capture, one digest, one interpretation

The planner selected technique records and retained their manifest digest, then
the facade read that same file again to check immutable revisions. A concurrent
edit between those reads could add or remove a compatibility gap while all the
reported input hashes stayed unchanged. A deleted file also caused an unnecessary
second-read failure after its evidence had already been captured.

Technique revision diagnostics now run in the existing selected-record loop,
using the very rows whose bytes produced `input_manifests.techniques`. The facade
no longer rereads techniques or hashes the plan twice. Each of the five catalogues
used by a plan is captured once, including empty optional selections so their
existing manifest bindings remain intact. No cross-call cache or mutable snapshot
registry is introduced.

For unchanged input bytes, output schema, compatibility gaps, canonical ordering
and `plan_id` remain unchanged. Missing, blank and moving technique revisions
remain unresolved. A later call reads changed bytes afresh and obtains a different
identity; nested calls cannot replace an outer call's captured rows.

## Capture is not a current-state or execution claim

A plan describes the bytes it captured, not necessarily the current files when
it returns. It explicitly remains stale when any input manifest changes. A file
deleted after capture does not invalidate those already-read historical bytes,
but the next planning call refuses the missing input. This does not add a writer
lock, an atomic multi-file snapshot, or protection against all filesystem races.

Provider claims, terms review, graph executability, vocabulary acceptance and
runtime authorization retain their separate owners. Authority is still `none`,
the authorized candidate cap is zero, and all execution/download/install/training
and generation flags remain false. No provider, model, image, subprocess or
workstation access is added. HUMAN_TODO q-29 is unchanged.

## Regression evidence

The regression suite rewrites and removes real temporary manifests immediately
after the real reader returns captured bytes. It covers both directions of
revision change, nested independent planning, one read per catalogue, unchanged
plan identities, new-call staleness and zero authority. The read hook schedules
the mutation; it does not fabricate parsed rows or hashes.

```sh
python -m unittest tests.test_adult_illustration_research_capture -v
python -m unittest discover -s tests -p 'test_adult_illustration*.py'
python tests/check_full_suite_lifetime.py
python scripts/validate-repo.py
```
