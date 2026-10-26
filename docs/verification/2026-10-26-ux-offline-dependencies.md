# UX offline fixture dependencies — 26 October 2026

## Observed failure

Library PR #1660 head `88ee123e83f76d280e8fc539b45a691f1b9e2cc4` failed
[UX use-cases run 40397724457, job 121835106504](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40397724457/job/121835106504).
The offline contract gate ran **71 tests in 0.280 seconds with three errors**.

All three `FamilyFixtureReads` tests call the real fixture's `build_handler()`.
That imports `studio_prompt.http_extension`, then
`studio_workflow.addressable_figures`, which imports Pillow. The workflow's
existing Pillow installation step came after this gate, so setup failed with
`ModuleNotFoundError: No module named 'PIL'`. Browser measurement and pose
handoff checks were skipped; this run supplies failure evidence only.

## Correction

Move the existing `python -m pip install pillow playwright==1.57.0` step
immediately before the offline contract gate. It installs the same two packages
with the same pin. The test command, Chromium installation, native browser
commands, artifact configuration, triggers, runner, and twenty-minute job
budget are unchanged. No test is removed or skipped.

The exact base workflow blob is
`71c8a3bc772085cbf0d5cdb53a71e209da213838`.
Moving that one step back reproduces the original workflow byte for byte.
All workflow lines and commands are preserved, with the prerequisite now
preceding the test that needs it.

## Qualification

The old exact-head failure remains recorded above. A fresh hosted workflow
must pass the unchanged offline and native browser gates before the corrected
head is qualified; source-order verification alone does not establish that
hosted execution result.
