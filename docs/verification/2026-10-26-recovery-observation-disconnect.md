# Recovery observation response disconnect — 26 October 2026

Refs #393. This is a narrow HTTP response-cleanup correction. The broader
keyboard, focus and assistive-technology acceptance remains open.

## Observed hosted evidence

PR #1674 at `b4bd56b654c9c53d6c840d4962c1e66af28f4da8`, tree
`219aeb38b14c095aba40a44cf71aca6cf2a24577`, passed its browser checks.
[Lifecycle Windows job 121854953980](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40403426649/job/121854953980)
passed all nineteen LIFE checks, nineteen Python cases and the existing reload
and detail contracts. It also retained a request-thread
`ConnectionAbortedError: [WinError 10053]` while writing the observation response.

The exception follows LIFE-11's Escape check at 21:23:01.403 UTC and overlaps
LIFE-12 at 21:23:01.453. The traceback reaches
`asset_recovery_http.py:43` → the production `_json` writer → socket
`sendall`. It is a response-write failure, not a missing synthetic jobs owner.

The exact fixture holds one recovery-observation response, waits until it
reaches the server, presses Escape, opens another editor and changes its notes,
then releases the response. The lifecycle close listener calls
`observer.cancel()`, whose controller aborts the read. These source and timing
records identify the held-read close scenario; the request-thread exception
itself was not an expected or asserted success. The native job stays recorded
as passing, with this separate cleanup gap visible.

The same WinError diagnostic occurs in the earlier
[Library Windows job 121837397137](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40398210608/job/121837397137),
between its LIFE-11 and LIFE-12 checks. The fixture, lifecycle JavaScript and
HTTP owner are byte-identical between #1674 and its parent
`9dca741bcf2c86af34af7c3f1ad92ef25d846ad5`:

| Source | Git blob |
| --- | --- |
| `tests/asset_recovery_lifecycle_browser.py` | `e406281b11b0bad21ccf5097148094d24947e7ae` |
| `app/static/asset-recovery-lifecycle.js` | `dd80ec9a012470e0648c058847ab888a0747a535` |
| `studio_workflow/asset_recovery_http.py` | `3f077028203c55cf41e5b10e940c2ccdf88648ce` |

## Causal correction

The observation route already treats `BrokenPipeError` and
`ConnectionResetError` from its final JSON response as peer disconnection.
It omitted `ConnectionAbortedError`. The production change adds only that
specific exception to the existing response-write tuple. It does not catch
generic `OSError` or `ConnectionError`, retry the read or response, change
observation data, alter request authority, or modify browser behavior.

Two regressions in the existing `test_asset_recovery_observation.py` use a
disposable real SQLite Workspace and the real observation reader. A controlled
response writer reproduces the exact exception class at the recorded seam.

- On the unchanged source, the disconnect regression fails only for
  `ConnectionAbortedError`; the successful response, existing broken-pipe/reset
  cases and unrelated-error control behave as expected.
- Every response case asserts one route observation and one response attempt,
  exact target identity, `generation_submitted: false`, unchanged complete
  SQLite dump and unchanged source bytes.
- Unrelated `OSError`, generic `ConnectionError` and encoding `ValueError`
  still propagate as the original exception object.
- After the one-line correction, all **13 real-Workspace read-owner tests pass
  in 1.176 seconds, with no skips**. This includes the two new regressions and
  the unchanged bounds, lifecycle, snapshot and corruption checks.

The local proof replays the response-write fault deterministically; it is not
a fresh Windows network or browser execution. The existing real HTTP tests,
native Linux/Windows Lifecycle commands and full-suite gate remain unchanged
and require fresh qualification on the published correction. Earlier passing
jobs and their retained disconnect diagnostics are not relabeled as clean.
