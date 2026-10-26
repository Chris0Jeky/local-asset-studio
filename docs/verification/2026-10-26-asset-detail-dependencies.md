# Asset-detail browser dependency setup — 26 October 2026

## Observed cancellation

Recovery PR #1659 head `2c144d936e1b62170468c08434c6e17950a40024` triggered
[run 40364539027](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40364539027).
Its [400 ms job 121718554600](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40364539027/job/121718554600)
checked out GitHub's merge `5b94bd420b67538714751daba44e11496d4c4e63`, containing
that head and main `b4515ca73e274e07b5642616d3f5e26289880432`.

The exact job log starts at 17:00:31 UTC. Its original
`python -m playwright install --with-deps chromium` step begins at 17:00:41 and
continues fetching Ubuntu fonts/libraries over
`http://azure.archive.ubuntu.com/ubuntu` until cancellation at 17:10:43. That
exhausts approximately the workflow's existing ten-minute job budget. Every
application test step is skipped; the artifact uploader reports no files.
This attempt supplies dependency-failure evidence only.

The parallel [0 ms job 121718555461](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40364539027/job/121718555461)
passed its executed assertions at the same merge. Its incidental synthetic
family-owner exceptions are recorded and corrected in the
[separate fixture qualification](2026-10-26-recovery-fixture-jobs.md). It does
not qualify the skipped 400 ms execution. The original cancellation remains
retained when assessing any subsequent unchanged-head retry.

## Bounded correction

This follow-up applies the already-reviewed
[`ci-install-chromium.sh`](../../scripts/ci-install-chromium.sh) helper to
`.github/workflows/asset-detail-browser.yml`. The Linux runner is pinned to
Ubuntu 24.04, the five helper contracts run first, and installation has a
four-minute step bound. Changes to the helper or its contracts now trigger
this workflow.

The response-delay matrix remains `[0, 400]`; the ten-minute job bound, all
existing application test commands and conditions, package pins, checkout
behavior and artifact configuration are byte-for-byte preserved. This workflow
has no Windows lane. The helper itself is unchanged: signed official Ubuntu
HTTPS sources, bounded dependency/browser subprocesses, and fail-closed exit
handling remain as qualified in the
[original helper evidence](2026-10-26-browser-ci-dependencies.md).

## Verification and pending gate

The five existing helper contracts pass locally with no skips. They use
controlled commands and real APT configuration inspection; this check does not
install local packages or download Chromium. Source SHA-256 values remain:

| Source | SHA-256 |
| --- | --- |
| `scripts/ci-install-chromium.sh` | `5da279e7bf9b58ccc603a405278a05fb6396a741a70e5fa2823794cf1032db64` |
| `tests/test_ci_browser_dependencies.py` | `fe9cfd33fd74b380fba9d9187e9a3e042f8235b3f0d9d33696f939101308b440` |

A byte-exact comparison against `deb6091a61b1a2e1bf38b8744fb685a94731ac00`
reverses only the runner, two trigger paths, helper-contract step and installer
substitution, then requires equality with the original workflow. It passes.
`python scripts/validate-repo.py` and `git diff --check` also pass.

The corrected caller still requires hosted execution of both response-delay
lanes and their unchanged assertions. Earlier test results and the controlled
helper contracts do not establish real dependency download completion on this
new head. Full-suite qualification remains a separate exact-head gate.
