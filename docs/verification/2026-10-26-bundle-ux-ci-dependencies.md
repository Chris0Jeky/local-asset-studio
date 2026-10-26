# Bundle, UX and Lifecycle browser dependency setup — 26 October 2026

## Measured callers

Library PR #1660 head `023503312bb87419a1d1f82136de6e6442873d6c` reached
[Bundle workflow run 40398210495, attempt 1, job 121836803718](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40398210495/job/121836803718).
Its existing Chromium dependency step ran from **20:44:17 to 20:54:18 UTC**
while downloading Ubuntu fonts and libraries from
`http://azure.archive.ubuntu.com/ubuntu`. The job was cancelled at its
ten-minute budget. All four application steps were skipped and no artifact
was produced. This attempt is failure evidence, not native Bundle proof.
An unchanged-head retry is separate execution evidence and does not erase it.

Recovery PR #1659 head `59a865cdaa35c1c4db5853c404124000976bd26a` reached
[UX use-cases run 40397309632, job 121833628321](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40397309632/job/121833628321).
Its dependency step took **14 minutes 17 seconds**, from 20:37:45 to
20:52:02 UTC, against the same ambient Azure archive. It eventually passed
the unchanged 25-case native fixture matrix and 295 pose-handoff assertions.
This is a measured setup delay, not a timeout or failed application check.

Refusal PR #1664 head `460603dcd1f94c5927e9d2d2e65ddacb175bafc3` reached
[Lifecycle run 40398224645, attempt 1, Linux job 121837339117](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40398224645/job/121837339117).
Its unchanged dependency step ran from **20:48:40 to 21:03:41 UTC** against
the Azure archive before cancellation. All three application/native steps
were skipped and no artifact was produced. The parallel
[Windows job 121837338553](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40398224645/job/121837338553)
passed. The Linux cancellation remains recorded separately from its bounded
unchanged-head retry.

## Bounded correction

These three Linux callers now use the existing
[Chromium dependency helper](../../scripts/ci-install-chromium.sh)
on Ubuntu 24.04. The five existing helper contracts run before setup, and
the installer has a four-minute step deadline. Changes to the helper or its
contract tests trigger each caller.

The helper remains unchanged: signed official Ubuntu HTTPS sources, bounded
dependency/browser subprocesses, and fail-closed status handling. Bundle and UX
are Linux-only. Lifecycle retains its Windows lane and its exact original
Windows installation command; only the Linux runner/setup changes. Package
specifications, application commands and their order, checkout behavior and
artifacts remain. The Bundle ten-minute, UX twenty-minute and Lifecycle
fifteen-minute job budgets are unchanged.

The UX workflow retains the already-corrected Pillow installation before the
real-owner offline contract gate. That separate dependency-order failure and
its correction are recorded in
[UX offline dependency evidence](2026-10-26-ux-offline-dependencies.md).

## Source and verification

The exact starting head is
`3060633539ada1ee79c6b13b30d89aeebbc95c83`, tree
`7fafdd05d18cd2a5d04b79dcf3a1a9c7b00df251`.

| Workflow | Original Git blob |
| --- | --- |
| Bundle | `14eed7e7aeffeb615761a9351fcde00249e0da72` |
| UX | `4ff6a51651fdab94fc17cc7ce92cf7b36c94a0f6` |
| Lifecycle | `33c6af323e457a2476cc58fa06c922bf9af32bc0` |

Reversing only the runner, two trigger paths, helper-contract step and
installer substitution reproduces each original workflow byte for byte.
The UX Pillow-before-contract ordering remains explicit in the corrected
workflow.

All **five existing helper tests passed in 0.747 seconds with no skips**.
They exercise controlled dependency/browser commands, timeout/failure
propagation, cleanup and real APT configuration selection without fetching or
installing local packages. No helper or contract-test source changed.

Fresh hosted runs must still qualify these three new Linux callers after publication.
The earlier UX pass and local helper checks do not establish hosted download
completion for the new workflow revision. The retained cancellation, any
unchanged-head retry, and the subsequent bounded-helper runs remain separate
records.
