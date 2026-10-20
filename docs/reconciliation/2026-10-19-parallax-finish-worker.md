# Parallax CPU finishing — 19 October 2026

Issue #1234, item 4: the single generation worker called `finish_after_run` from
both normal generation completion and resumed observation. That hook entered
registration, the ring fill and PNG encoding synchronously. The next queued
generation waited for those CPU operations.

The earlier required follow-ups are already delivered by #1285 (saved plans),
#1288 (EXIF orientation) and #1289 (stage-card recall). This change addresses the
remaining CPU queue behavior. The issue's optional stricter isolate wording is
unchanged; it is not an additional acceptance requirement. Owner creative
acceptance remains in `HUMAN_TODO.md` and is not inferred here.

## Result and limits

Each Studio owns one Parallax finisher. It starts a CPU thread only when a split
is admitted and retires that thread when its queue drains. The implementation
admits one active pair and two waiting pairs. These numbers are a resource bound,
not a measured throughput or latency claim. Waiting entries retain job and asset
identity, not decoded images. Explicit `finish()` callers share this same owner;
they cannot bypass its capacity or start a duplicate split of an admitted pair.

Both completion hooks reserve a pair and return to generation. Registration,
layer construction and PNG encoding run on the CPU owner without holding the
Studio lock. Final identity checks, file publication, indexing and job/link
saves retain the existing Studio serialization. This removes the CPU wait; it
does not claim that all storage operations are nonblocking.

The cards show queued/running split progress. A failed or saturated split keeps
the completed edits and an explicit **Split layers** action. That retry sends
the retained plate and isolate IDs when a pair is recorded. A completed result
whose stage-link save failed remains visible, together with the save error and
an explicit **Save split status** action.

## Ownership and recovery

- Admission snapshots the exact stage objects, claims, outputs, prompt receipts,
  controls and expected asset identity. A newer sibling completing while a pair
  waits does not change the selected pair.
- Before final output files are created, the finisher checks that the original
  jobs still occupy their IDs, that their identity fields match the snapshots,
  and that source and edit bytes still match their recorded digests. Removed or
  replaced jobs and changed claims, outputs or source bytes cannot publish.
- Stage links carry an attempt identity. Finishing an older pair cannot replace
  a newer queued/running pair's link. A cached result is returned only when its
  receipt belongs to the requested pair. Completed links derive their stage IDs
  and finish ID from that receipt; another pair's failed attempt metadata cannot
  retarget **Save split status**.
- Success and failure release task capacity. The finisher explicitly closes its
  decoded and returned Pillow images, including PNG-encoding failures. An
  abnormal worker exit settles its waiters and retires its pending ownership.
- HTTP creation registers the concrete Studio finisher. Shutdown closes that
  registered owner without probing execution capabilities on an injected
  read-only Studio facade. Close revokes active output
  publication, settles waiting work and joins for at most five seconds. A CPU
  operation already inside Pillow may finish later; it cannot publish then.
  Repeated close, late generation completion and late worker cleanup cannot
  rewrite a newer stage record.
- Restart never queues a generation or CPU split. An interrupted queued/running
  marker becomes a visible explicit retry, or reconnects to its matching saved
  completed receipt. Prompt IDs, submitted graphs and stage outcomes are retained.

The existing multi-file/Workspace publication boundary remains separate work
under #716. This change does not provide a cross-process transaction over PNG
files, SQLite indexing, the finished receipt and two stage records. A storage
failure can retain partial files or indexed assets for inspection. Such a
failure is visible, task capacity is released, and a completed saved receipt is
not discarded because a later stage-link save failed. It is not a benchmark,
GPU proof, art acceptance or model-licensing decision.

## Causal regressions

The baseline local source was `70e920ac8f355459643fd5f15fba9a48f7b5f3fa`, reconciled
by the coordinator with GitHub main `670ee927526e2811763fae27cbc7fd157ddb387c`.
The following failures were observed before their corresponding fixes:

| Regression | Observed failure |
| --- | --- |
| Next generation while a resumed split is blocked on an event | The real `_work` consumer did not reach the following inert `/prompt` request until CPU finishing was released. |
| Source bytes changed while CPU work was blocked | The old split still wrote final files and a completed receipt. |
| Stage object replaced while CPU work was blocked | The abandoned task still published a result. |
| Cached receipt from a different/malformed pair | A completed-looking record was returned without validating its pair receipt. |
| Stage-link save fault after completed publication | The saved result remained, but the public link did not expose the recording failure. |
| PNG failure cleanup | Context management closed image files but left decoded pixel buffers usable; explicit `Image.close()` was required. |
| Close followed by a newer saved stage record | Late cleanup, a repeated close and a late generation hook could overwrite the newer record. |
| Abnormal CPU worker exit | An explicit waiter returned `None` instead of a terminal split error. |
| Queued/running and save-failure cards | The shipped renderer lacked progress and the failed stage-link save notice. |

The queue regression now exercises both normal generation and resumed
observation through the real single consumer. It retains the original prompt
receipt and proves that the following inert generation progresses while the
layer split is held on an event. It does not replace generation admission with
a mock worker.

## Independent review corrections

Review of local candidate `c855946e6a635ee46adfd089e198bb48bfc9d76d` identified
two P2 findings. The correction preserves the original bounded-worker design.

First, a cached result for pair A could inherit a failed newer pair B's marker
when both pairs shared an isolate. A link-save fault then exposed B's stage IDs
on A's **Save split status** action, causing new CPU work for B. `_link` now
derives both stage IDs and the finish ID from its verified completed receipt,
retaining attempt metadata only when it belongs to that pair. The regression
uses completed A, an actual failed B, a cached relink with a save fault, and the
exact status-button request. Both completed markers agree with A's receipt,
the retry returns cached A, and `layers` is called zero times. The same test
checks that a cached A read leaves B's running marker untouched.

Second, shutdown dynamically looked up `parallax_finisher` on the injected
shortlist facade. Its existing read-only sentinel correctly rejected that
execution-capability probe, preventing normal HTTP cleanup. Hosted run
`39341039138` reproduced six teardown failures on both Linux and Windows.
Creation now registers the actual Studio's finisher on its HTTP server, and
shutdown closes that registered owner before normal HTTP cleanup. Focused tests
retain the unmodified shortlist sentinel and prove that later replacement of a
Studio's finisher cannot redirect the registered server's close operation.

The new regressions first failed on the reviewed candidate: the cached marker
retained B's finish ID, the facade raised its capability assertion, and shutdown
closed a replacement finisher instead of the registered owner. Their RED/GREEN
receipts are retained in `.runtime/parallax-review-cached-link-{red,green}.log`
and `.runtime/parallax-review-close-{red,green}.log`. The correction does not
change the separate #716 publication boundary or the native UI code.

## Verification

All test images and generation replies are synthetic fixtures. No installed
ComfyUI/model action or generation was performed. Scoped escalation was used
only because the default sandbox denied inert loopback sockets and the Node
child test runner. The browser used the already retained Playwright 1.55 runtime
and Chromium cache; nothing was installed.

The Parallax, server, shortlist and repository checks below were rerun after the
review corrections. Frontend handoff, direct Node, native browser, EXIF and media
results are retained evidence from the initial candidate; those files were not
changed by the correction. Corrected-head hosted CI and focused rereview remain
the coordinator's gates.

| Check | Outcome |
| --- | --- |
| `python -m unittest discover -s tests -p 'test_parallax*.py' -v` | 40 passed: 22 existing Parallax tests, 16 CPU ownership/lifecycle tests, and two stage recovery contracts. Receipt: `.runtime/parallax-review-parallax-green.log`. |
| `python -m unittest discover -s tests -p 'test_server.py'` | 163 passed. Expected invalid-config diagnostics were emitted by the corresponding tests. Receipt: `.runtime/parallax-review-server-green.log`. |
| `python -m unittest discover -s tests -p 'test_recipe_shortlist*.py' -v` | 126 discovered, 121 passed, five optional MCP SDK tests skipped. All six affected transport tests passed with normal teardown. Receipt: `.runtime/parallax-review-shortlist-green.log`. |
| `python -m unittest discover -s tests -p 'test_frontend_handoffs.py' -v` | 19 passed. |
| `node --test --test-reporter=tap tests/parallax_stage_recovery.cjs` | 19 passed. |
| `node --check app/static/app.js` | Passed. |
| Native `parallax_stage_recovery_browser.py` at 1440 and 390 pixels | 26 checks passed, no page errors, eight exact-pair CPU split/status-save requests, no generation request. |
| Existing EXIF and local-output media contracts | Eight EXIF tests and five local-output media tests passed. |
| `python scripts/validate-repo.py` and `git diff --check` | Passed: 93 graphs/bindings and 187 pinned assets; no whitespace errors. |

Native evidence is in `.runtime/parallax-finish-worker-native/report.json`, with
running/completed card and full-page screenshots at both widths. The existing
Parallax Windows/Linux workflow now runs the CPU ownership suite and the expanded
native browser journey. Published-head full CI and independent review are owned
by the coordinator; a local focused pass is not represented as that full gate.
