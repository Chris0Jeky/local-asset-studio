# Blender evidence integrity — 5 November 2026

## Scope and decisions

This maintenance pass addresses incomplete render-critic coverage (#1985) and
duplicate asset accounting in repair benchmarks (#1986). It changes how existing
evidence is checked, not rendering, generation, art acceptance or model licences.

The implementation plan is to reproduce each defect with a narrow regression,
fix the owner of the incorrect verdict, preserve the original evidence, then run
the affected suites and repository validation. Hosted CI supplies the full-suite
result for the published commit. The uploaded source was reconciled against main
`bcfc1ac67a99b1771841271617b9917c31e6519c`; its Git tree is
`0adf83117696e18bfcea9bb02a6ffa2a18a0f963`.

## Render critic coverage (#1985)

`critic_signal()` asks for front, three-quarter, profile and back lit renders.
Previously, a legacy reply with only `front.lit` and a zero pixel count could be
reported as available and agreeing with a quiet primary diff. A producer's
`evidence_complete: true` claim also failed to bind that verdict to the requested
views.

The consumer now requires the returned view labels to match all four requested
lit views. Missing, substituted or additional views make the second signal
unavailable, preserve the raw observation and explain the mismatch. They do not
add a change warning or report agreement. A complete legacy reply without the
completeness flag remains usable; existing pixel-count checks still apply.

The new partial-view regression failed on the original code with `True is not
False`. After the fix:

- `python -m unittest discover -s tests -p 'test_blender_sentinel*.py'`:
  41 tests, one native Blender skip, no failures.
- `python -m unittest discover -s tests -p 'test_render_critic*.py'`:
  85 tests, no failures.
- `python scripts/validate-repo.py`: passed 98 preset graphs and bindings,
  194 pinned assets and the checked Git payload.

These are offline consumer and evidence tests. No native Blender execution or
new visual-quality claim is made. The separate pixel-threshold qualification
issue #1970 remains open.

## Repair benchmark accounting (#1986)

Each run and combined report now retains the verified control manifest's semantic
checksum. Combination requires one asset and one agent. Aggregation rejects a
second report for the same content even if its directory was renamed, and keeps
distinct assets that happen to use the same directory name. Legacy reports can
recover identity only from their verified adjacent control manifest; a missing
identity produces a repair instruction instead of a directory-based guess.

The benchmark's POSIX timeout now terminates its owned process group, including
children holding output pipes. A real-process regression verifies both bounded
return and the exact child's exit. See
[the benchmark receipt](2026-11-05-benchmark-evidence-identity.md) for the red/green
results, migration rules and platform limits.

No benchmark was rerun on the owner's workstation during this session, and
historical repair-rate claims are not rewritten.

## Full-suite environment limit

The unchanged uploaded baseline ran 7,183 tests locally with seven failures,
64 errors and 75 skips. The failures and errors were in process-owner and backend
admission tests. A separate minimal probe reproduced the environment mismatch:
`os.getpid()` returned 5 while `psutil.Process()` immediately raised
`NoSuchProcess(pid=5)`. This container's process and `/proc` views do not agree.
Production process-ownership checks were not weakened to accommodate it.

The local full-suite run is therefore not a passing receipt. Exact-head GitHub
Actions supplies the full-suite and hosted-platform gates; those run links and
outcomes are recorded in the PR after completion. The benchmark child-exit test
uses a Linux pidfd captured while that child is alive, so its local assertion
does not depend on the incompatible `/proc` view.

## Hosted full-suite fixture correction

The first integrated [Check studio run](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/41947912963/job/126984796004)
for PR #2010 head `fb1787a104cb279e72ce34849a0a9571943a2fe2` checked out merge
`e7c49caf94da3dd9c8e830bc47995ba6edc3feba`, tree
`2d8f13020d01b99bd68b8fb7bb21a801f465eee9`. It ran 7,197 tests in 958.495 seconds:
7,084 passed, 112 skipped and one failed. Shutdown reported no retained non-daemon
thread or active child process. The repository-validator step was skipped after
the suite failure; this run is not a passing merge gate.

The failure was
`test_blender_critic_receipt.CriticReceiptTests.test_legacy_success_remains_compatible_but_not_replayable`.
Its positive legacy fixture contained only `front.lit`, so the new completeness
check correctly refused it. The fixture now supplies all four requested labels,
keeping the front count at 40 and the other counts at zero. The test asserts that
the original observation is retained unchanged and still cannot be replayed as a
policy decision because the legacy metadata is missing. Production completeness
checks are unchanged. Partial legacy refusal is already covered by
`SecondSignalTests.test_partial_or_wrong_views_never_become_an_agreeing_second_signal`.

The failure was reproduced locally before correcting the fixture. Afterward:

- `python -m unittest discover -s tests -p 'test_blender_critic*.py'`:
  13 tests passed.
- `python -m unittest discover -s tests -p 'test_blender_sentinel*.py'`:
  41 tests, one native Blender skip, no failures.
- `python -m unittest discover -s tests -p 'test_render_critic*.py'`:
  85 tests passed.
- `python -m unittest discover -s tests -p 'test_blender_repair_bench.py'`:
  24 tests, two native Blender skips, no failures.
- Repository validation passed 98 graph/binding checks, 194 pinned assets and
  4,874 tracked paths; `git diff --check` passed.

The initial head's Privacy and Archive workflows passed on Windows and Ubuntu.
A fresh exact-head full-suite result is still required after this correction;
the targeted results do not replace it. No native Blender execution, historical
benchmark rerun, owner art acceptance or licensing decision is inferred. Studio
art direction/replacement of the paused asset wave (#1923), parallax usability
(#1219), and the island default-switch decision remain open.
