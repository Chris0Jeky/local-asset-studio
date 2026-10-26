# Asset family browser dependency setup — 26 October 2026

## Observed dependency delay

At Library head `777082d51e6236fb87d194f1a607a4d9dee230b5`,
[run 40368213733 / Ubuntu job 121731574507](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40368213733/job/121731574507)
has a **cancelled job conclusion**. Its dependency step ran from 17:29:15 to
17:41:09 UTC: **11 minutes 54 seconds** of a 12-minute job budget. The log shows
prolonged Azure HTTP APT downloads before official HTTPS downloads completed.

Unlike the earlier Asset detail timeout, all three family application steps and
artifact upload subsequently reported success before cleanup ended at 17:41:19.
The cancelled job conclusion remains recorded; application assertions are not
described as unrun, and the whole job is not promoted to a successful gate.
The Windows job `121731574941` completed successfully. No rerun was requested for
this observation.

## Correction

`.github/workflows/asset-family-browser.yml` now pins its Linux leg to Ubuntu
24.04 and uses the existing signed, official HTTPS dependency helper with its
four-minute step bound. Windows retains the original installation command.
The workflow also runs the existing five helper contracts on Linux and triggers
when the helper or those contracts change.

This is the ninth affected caller when combined with the already reviewed
Recipe shortlist, conflict-envelope, guided-journey, restyle, shelf, Asset detail,
Model readiness and Reference review migrations. The helper itself is unchanged.

The original 12-minute job budget, Python/Node/Playwright versions, three
application commands, exact-head checkout, permissions, concurrency and artifact
configuration are byte-for-byte preserved after normalizing only the runner,
added trigger paths and installation block. No deadline or assertion is relaxed.

## Verification and limits

- Five controlled helper tests passed in **0.716 seconds**, zero skips. They cover
  signed source selection, effective APT options, elevated setup versus normal-user
  browser installation, failure/timeout propagation and temporary-file cleanup.
  They do not perform an actual package installation.
- Normalized workflow reversal reconstructs original Git blob
  `343e81946307dc0c15b6961d8991ecd51fcc17fc` exactly.
- Corrected workflow Git blob: `3de4816e6762f502459c85f434c1b39a1c28063c`.
- Helper remains Git blob `39aa8f40f1f6bd658e52e9c9a134724556fe4ac4` and test blob
  `417339a3747ff0ac8a422527dded1afb6c0b3575`.
- Fresh hosted qualification is required on the published corrected head.

Complete cancelled-job logs, step metadata, normalized comparison, source hashes
and local helper results are retained in `final-fixes/shelf/evidence/`. This does
not change product behavior, installed applications or model assets.
