# Launcher fixture path aliases — 26 October 2026

The Windows runtime-safety job for Qwen PR #1667 at
`fc234d8197273e2ba18cc4322fe09ce604bd68b0` failed its complete-checkout launcher
control. The launcher correctly resolved the temporary checkout from the Windows
short path `C:/Users/RUNNER~1/...` to `C:/Users/runneradmin/...`; the test compared
the resulting cwd to the unexpanded input path. Missing and empty encoder cases
passed, as did all 53 backend-safety cases in the preceding step.

Failure evidence: [run 40398249108, job 121836946830](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40398249108/job/121836946830).
The decoded failure log is retained with the session qualification records. It is
a failed run, not qualification for any later revision.

The fixture still passes the original temporary path to the real launcher. Its
positive control now compares cwd and the exact main-path argument with the
resolved checkout, preserving all remaining arguments, input staging, and
existing-input assertions. The production launcher is byte-for-byte unchanged
at Git blob `f54cb4952f53333acfc52d12e83002dd88c0f702`.

## Bounded causal check

A disposable symlink supplied a raw alias path distinct from its resolved target
on Python 3.12.14/Linux. The original Qwen fixture, Git blob
`5212ea2eb09c5fe96b3f5d3632add5ce451c8241`, reproduced the cwd assertion failure.
The corrected Qwen cases passed while still receiving that raw alias. The same
probe also exposed the corresponding MOSS fixture expectations and a stat-error
injection whose raw-path comparison could miss the canonical encoder path; that
fixture correction is carried separately in PR #1672.

Across the three Qwen and four MOSS cases, the original aliased fixtures produced
four failure assertions: one Qwen positive control, both MOSS reserve-argument
subcases, and the MOSS stat-error refusal. The corrected fixtures passed **7 tests
in 0.653 seconds, no skips, exit 0**, with the alias, and **7 tests in 0.729 seconds,
no skips, exit 0**, with ordinary temporary paths. Both real launcher files were
unchanged between these fixture runs. All checkouts and main functions were inert
and disposable; no installed runtime, model, network listener, or GPU was used.

These local results establish the fixture correction. Fresh Windows and full
repository checks on the published head remain the hosted qualification gate.
