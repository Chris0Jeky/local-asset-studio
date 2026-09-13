# Hosted guide acceptance: PR #197

Recorded 13 September 2026, after the context fixes described in
[GUIDE-CONTEXT.md](GUIDE-CONTEXT.md). Tested code/test revision:
`8929c7051cef8dbbb9edc3c1eca5b21fafc6101c`; Git tree
`890d68f80f7cbdece64aa070245faf35699bbaaa`.

## Native browser result

[Guided journey browser run 34772468674](https://github.com/Chris0Jeky/local-asset-studio/actions/runs/34772468674)
passed **78 assertions** using the actual Studio pages, Chromium and native HTTP,
storage and history. Data is synthetic; no ComfyUI, GPU execution or artistic
acceptance is implied. The local container could not navigate to its test server;
this result comes from the hosted job, not a substitute local browser.

Coverage includes all seven paths, programmatic recipe/setup/import invalidation,
delayed readiness, reference staging versus file selection, specific-run output
and review evidence, current graph-check receipts, retained editor drafts, history,
keyboard focus, Pause/Resume, 390px width and 200% zoom. There were **zero page
exceptions and zero generation, installation, switching or asset-mutation calls**.
Desktop/mobile coach screenshots were opened and inspected after downloading.

The downloaded `guide-browser-proof` artifact (ID `10321848433`) matched its
reported SHA-256:
`b937d23266570df1e9dc4e663d9c852dcdcc7d8bad2880f38e894bb35c432907`.
It contains `result.json`, `history.json`, `guide-desktop.png` and
`guide-mobile.png`. CI artifact retention is seven days; rerun the checked-in test
to produce fresh evidence rather than treating this dated record as current state.

## A test failure that improved the coverage

The first hosted attempt incorrectly required hashchange when traversing between
stages that also changed query parameters. Chromium emitted popstate only. Its
[DocumentLoader implementation](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/third_party/blink/renderer/core/loader/document_loader.cc)
checks URL equality excluding the fragment before queuing hashchange. Checking the
new panel alone would not prove that the paired event was tested either.

The corrected suite preserves both cases instead of weakening the history test:

| Actual native navigation | Observed events | Expected and observed state |
| --- | --- | --- |
| Back to comparison budget; query changes | popstate | manual |
| Forward to comparison inspection; query changes | popstate | manual |
| Workbench fragment navigation; query retained | popstate, hashchange | manual |
| Fragment Back | popstate, hashchange | manual |
| Fragment Forward | popstate, hashchange | manual |

Every recorded event has `isTrusted=true`. Paired cases assert event order;
subsequent real input edits must invalidate again. No event is manufactured with
`dispatchEvent`, no timer suppresses application events, and manual classification
is not a restored success, an approval or evidence of being in the correct tool.
The test writes bounded history diagnostics even if its event wait fails.

## Other gates at the tested revision

All six workflows passed: Check studio, Guided journey browser, Preset model
readiness, Asset detail workflow QA, Production storage safety and Windows runtime
safety. The local 1,464-test result (15 skipped), nine regression scenarios and
baseline failure proof are recorded in [GUIDE-CONTEXT.md](GUIDE-CONTEXT.md).

The remaining original workstreams and live acceptance requirements are unchanged;
see [ROADMAP.md](ROADMAP.md) and [AGENT-QUICKSTART.md](AGENT-QUICKSTART.md).
