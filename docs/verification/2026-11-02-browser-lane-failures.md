# Browser lane failure evidence — 2 November 2026

Refs #1901. This follow-up preserves the original failures and adds evidence;
it does not establish a historical root cause from a later green run.

## Exact failed and baseline runs

| Lane | Failure | Later baseline | What the artifacts establish |
| --- | --- | --- | --- |
| Spoken Brief Linux | [run 41344193414, job 124960390712](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/41344193414/job/124960390712), head `e85a1bcf86750cb9e8b3231a06639d89fef8b3e1` | [run 41346157674, job 124966306214](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/41346157674/job/124966306214), **changed head** `9aed14734b9032fa0625e4df82140e38d30b3ebe` | The lost-Start-reply test reloads the retained run, then times out in its existing condition wait. There are no page errors. Exactly one narration GET appears while the producer continues; HTTP status, response body and final status text were not retained. |
| Private creation Windows | [run 41346157721, attempt 1, job 124966306613](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/41346157721/job/124966306613), head `9aed14734b9032fa0625e4df82140e38d30b3ebe` | Same head and run, [attempt 2, job 124967978151](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/41346157721/job/124967978151) | The second tab fails with missing `catalog`; the page itself reports six missing-`$`, two missing-`esc` and one missing-`catalog` errors. Its document load has no server request for `app.js`, although dependent scripts are requested. Ten server `ConnectionAbortedError` entries lack route/errno detail. |

The original Windows run at `e85a1bc` was green. The Linux baseline is not an
unchanged-head retry. Neither distinction is erased by this follow-up.

Downloaded original artifacts were checked against their advertised SHA-256 and
ZIP integrity before inspection:

- Spoken artifact `13098324993`: `cc65eb11725b872dce9007ddb3af5b0b63c350efc0bf52b98162da17f9457817`.
- Private creation artifact `13099124001`: `faf48864ff86a31db255a51be0698b0bb37fe35210597870d506d352ba44870e`.

## Added evidence and unchanged behavior

Both fixtures now retain failed browser request URL identities and failure text,
script/narration/error response statuses, and server exception type, route,
errno and Windows error number. A separate bounded failure list survives ordinary
successful-request churn. Startup flags and a known narration-status category
can distinguish absent globals from a stopped observation. No headers, request
or response bodies, source/form text, URL credentials, query values or fragments
are added to this evidence.

The existing page-error assertions, readiness expressions, waits, budgets,
installation commands and exit status remain. Narration diagnostics are
registered before initial navigation so setup failure also leaves a receipt.
The guide fixture reuses the same URL redactor without changing its behavior.
Workflow changes only include the shared diagnostic helper in path filters.

Seven focused diagnostic tests pass, including failure retention, status
distinction, redaction and preservation of the original exception if the renderer
or screenshot fails. Syntax and diff checks pass. Actual Chromium qualification
of these additions remains for exact-head hosted CI; this cloud checkout has no
usable Chromium binary.

## Separate reproduced narration race

On the integrated source at `7fb6a02`, a controlled actual HTTP/coordinator probe
held the synthetic create reply, began a retained-state observation, then allowed
the ordinary coordinator to atomically replace `state.json` between the reader's
stat and open. The GET refused with HTTP 400, `File changed while opening`.
A subsequent GET returned HTTP 200 `completed`, with exactly one producer create
and one producer Start. No source changes or unsafe reads were needed to expose
this race. The page currently stops polling after the read error.

This is consistent with the historical single-GET artifact, but **does not prove
the historical response**. The Windows transport cause also remains unproven;
no server queue, MIME, script-order or timeout change is justified by these
artifacts. The unrelated image-source MIME correction does not address script
loading. #1901 remains open until the remaining acceptance is supported.
Owner runtime, art, licence and HUMAN_TODO acceptance remain separate and open.
