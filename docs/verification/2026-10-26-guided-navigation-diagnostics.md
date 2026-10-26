# Guided navigation failure evidence — 26 October 2026

## Retained failure and successful retry

At refusal head `460603dcd1f94c5927e9d2d2e65ddacb175bafc3`,
[Guided run 40398224868 attempt 1, job 121836854034](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40398224868/job/121836854034)
timed out during the first `page.goto(...,timeout=15000)`, waiting for `load`.
No native journey assertion had run. The Python checks and bounded dependency
setup passed, but no diagnostic artifact survived. Request inventory and page
errors stayed in memory, and the result receipt was only written on success.

The guide driver, workflow and HTTP server blobs were unchanged across the
earlier passing Library candidate and this candidate. Current Library and
refusal also shared the same real Workspace fixture. Inspection found no added
network/media request in the refusal annotations, but the available evidence
could not identify what held the load event.

One explicitly bounded unchanged-head retry,
[attempt 2, job 121843486612](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/40398224868/job/121843486612),
passed all native stages. The original failed log is retained. That successful
retry does not establish an infrastructure cause or prove the failure transient.

## Observation change

The synthetic fixture now writes `navigation.json` before Playwright and server
cleanup on failure. It records request starts, responses, finishes/failures,
DOMContentLoaded/load timestamps, pending request URL/resource types, page errors,
and the fixture's server-call inventory. Request and server-call URL fields omit credentials, query values and fragments.
Exception and page-error messages are capped and come only from the synthetic
fixture; no request/response bodies are recorded.
Limits are 200 recent events, 100 tracked pending requests, 20 page errors and 100
recent server calls, with bounded text fields, dropped-event counts, untracked
request-start counts and the total server-call count.

The receipt is written before an optional one-second screenshot attempt,
clipped to at most 960×640 pixels. Capture errors cannot replace the original
failed assertion or browser exception. A successful run also writes a receipt.
The existing artifact step already runs with `always()`; the focused probe's
output directory is added to its paths.

The wrapper forwards the original navigation arguments without retries.
The 15-second default-load wait, every application assertion and the existing
panel/selected/backend readiness checks remain unchanged. Reversing only the
observer integration reproduces the original guide driver byte for byte.

## Causal proof of the evidence gap

The focused native probe holds one synthetic image response behind an event.
The page's guide panel and application readiness values are already available,
and DOMContentLoaded fires, while the original 15-second `load` wait times out.
The response is not released until the evidence assertions finish.

With diagnostics disabled, this same load failure leaves no receipt and the
proof fails its missing-receipt assertion. With diagnostics enabled, the same
TimeoutError propagates and the receipt identifies the pending image, observed
DOMContentLoaded, absent load event and server request before cleanup. The
optional screenshot itself timed out after one second in this probe; the JSON
remained available. The ordinary successful-load control passed. This establishes
the diagnostic ordering; it does not reproduce the unknown cause of attempt 1.

Three offline contracts also pass: original exception identity and navigation
arguments, bounded inventories with normalized URLs, and preserving the original failure
when writing the receipt is impossible. Local proof used Python 3.12.14,
Playwright 1.56.0 and the already available Chromium 1194 cache. Hosted CI pins
Playwright 1.57.0 and must qualify the final integration separately.

Starting source: head `3060633539ada1ee79c6b13b30d89aeebbc95c83`,
tree `7fafdd05d18cd2a5d04b79dcf3a1a9c7b00df251`.
Original driver blob: `3abd68e301923c1cb5daf497e7af73c24267f0f3`.
Original workflow blob: `e1c4a84db627832f750eee5ad412b13d8087d2fd`.
No production, installed runtime, model or owner decision changed.
