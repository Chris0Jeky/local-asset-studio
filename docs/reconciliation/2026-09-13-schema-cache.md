# Healthy runtime schema-cache observations

Maintenance for issue #147, based on main `06bd93aed2f019cb978eb5795e9f116cfb7ff749`.
The supplied ZIP reproduced that commit's exact Git tree
`9561db4b2bf6bba7178f10554bcc95479f0d6a7d` before any edits.

## Reproduction and correction

A healthy endpoint first reports a readable process PID/create time. A later
observation cannot read the optional process metadata. Previously those two
hash shapes were compared as if they were different runtimes, clearing the
schema cache both when metadata disappeared and when it returned.

`RuntimeRecovery` now tracks the stable endpoint/build identity separately from
its last observed process identity. Missing metadata alone does not clear a
healthy cache. A later different observed PID/create time still clears it.
Every observed disconnect/reconnect, endpoint/build change, and initial monitor
observation still clears it. The cache's age is preserved, not refreshed, when
nothing relevant changed.

Historical process information is private, in-memory comparison evidence only.
The public snapshot continues to contain the currently observed identity, even
when that observation lacks process metadata. It does not claim the old process
is still alive. Recovery launch, busy-work, process ownership, and connection-
refusal interlocks are unchanged.

## Repeat the checks

Run from the repository root; these use synthetic endpoints/processes and do not
need a model installation:

```sh
python -m unittest discover -s tests -p 'test_runtime*.py'
python -m unittest discover -s tests -p 'test_backend*.py'
python -m unittest discover -s tests
python scripts/validate-repo.py
```

Recorded in a Linux sandbox with Python 3.13.5 and Node 22.16.0:

| Check | Result |
| --- | --- |
| Untouched main full suite | 1,463 tests, 15 skipped; no failures |
| New causality tests against unchanged code | 7 tests; 6 expected failing assertions/subtests |
| Recovery plus new identity tests after fix | 19 passed |
| Backend contracts/ownership tests | 58 passed |
| Full suite after fix | 1,470 tests, 15 skipped; no failures |
| Portable repository validation | 66 preset graphs, 121 pinned assets; passed |

The full suite emitted existing Pillow deprecation and socket ResourceWarnings;
these also appeared on the untouched baseline. They were not suppressed.

## Scope and rollback

This proves cache invalidation decisions, not lower GPU memory, shorter model
inference, or Windows crash recovery. No ComfyUI process, model, native editor,
launch profile or artistic approval was changed. The existing suite's skipped
cases remain unverified in this environment. Reverting this change restores the
previous cache behavior without a configuration or stored-state migration.
