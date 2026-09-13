# Asset-detail browser evidence maintenance

Fixes the three test-driver defects in #193. This is synthetic test infrastructure,
not a claim that the product's asset editor failed in these three ways.

## Reconciliation and scope

The original maintenance baseline was main `06bd93aed2f019cb978eb5795e9f116cfb7ff749`;
the supplied archive matched its complete Git tree. During implementation, #199
introduced conditional metadata saves and changed this same fixture. This branch
therefore builds on #199 at `735de3291c9af722236b67770f3a012cf8aa49b9`, not on an
outdated unconditional-write fixture. The downloaded tracked snapshot reproduced
Git tree `fa57225d1848af882ff3df739d3d407575e054ef` before applying this patch.

Preserved: request IDs, expected revisions, replay receipts, revision increments,
Origin in the explicit inert HTTP bridge, and the Favorite-only field assertion.
The workflow retains #199's independent real-storage metadata browser test and
its dependency/trigger paths. Merge #199 first; retarget this PR to main afterwards.
No application files, model settings, stored work or historical receipts change.

## Root causes and correction

**Baseline mode.** Previously `--baseline` could return zero after a JavaScript
exception. It now permits unmet expectations only; recorded page exceptions
always produce exit 1. `asset_detail_driver_probe.py` drives two complete browser
runs: an injected exception must fail, while intentionally excessive preview CSS
must produce unmet expectations without failing the baseline process. The probe
checks the receipt, complete scenario count and actual process exit separately.

**Timing.** Fixed 30/50/180 ms sleeps were not completion evidence. The driver now
waits for the actual dialog/asset identity, held requests reaching the synthetic
server, and unheld API promises plus editor/refresh state completing. A test-only
wrapper forwards the original API's arguments, return value and exceptions without
changing product scripts or sending additional requests. Missing completion hits a
bounded timeout; assertions are not relaxed. `--response-delay-ms 400` deliberately
delays synthetic diagnostic/mutation responses. It is fault injection, not a longer
settling sleep. The CI matrix runs native HTTP at both 0 and 400 ms.

**Encoding.** Injected HTML/JavaScript/CSS, HTTP reply decoding and output receipts
explicitly use UTF-8. A regression emulates CP1252 as `Path.read_text`'s default;
it verifies non-ASCII markup, CSS and scripts survive without requiring `-X utf8`.
Playwright imports remain lazy so ordinary driver-unit tests need no browser package.

## Recorded local evidence

Environment: Linux, Python 3.13.5, Node 22.16.0 and Chromium. Successful local browser
checks use the explicitly labelled **inert component mode** with synthetic HTTP
transport; they do not establish native browser origin/storage/media behavior.
Attempting native navigation failed with `ERR_BLOCKED_BY_ADMINISTRATOR`; no browser
policy bypass was attempted. Hosted native HTTP remains a separate CI gate.

| Check | Observed result |
| --- | --- |
| Original baseline + injected page exception | 29/30 expectations pass, exception recorded, incorrectly exits 0 |
| Original fixed-wait driver + 400 ms request delay | Fails before the mutation reaches the fixture (`IndexError`) |
| UTF-8 regression with original implicit decoding restored | Fails under the emulated CP1252 default |
| Revised driver on original main with 400 ms delayed responses | 30/30 pass, zero page exceptions |
| Revised driver on #199 with 400 ms delayed responses | 30/30 pass, zero page exceptions |
| #199 real-storage metadata browser with revised inert bridge | 21/21 pass, no generation/backend mutation or page exception |
| Repeatable baseline probes on #199 | Exception exits 1; two CSS expectation failures exit 0; each completes all 30 checks |
| Driver unit suite | 6 tests pass (five new methods plus existing JavaScript contract wrapper) |
| Full suite on original main + driver changes | 1,468 tests, 15 skipped; no failures |

The final stacked full-suite result is recorded in the PR with the tested tree.
Existing Pillow deprecation/socket ResourceWarnings were not hidden. Optional/live
skips are not executed evidence. Driver receipts retain source hashes and add the
driver hash and configured synthetic delay. The probe's deliberately failing
receipts are expected fault evidence, not ordinary successful product runs.

## Repeatable commands

```sh
python -m unittest discover -s tests -p 'test_asset_detail*.py' -v
python -m unittest discover -s tests
python scripts/validate-repo.py
python tests/asset_detail_browser.py --out .runtime/asset-detail-proof
python tests/asset_detail_browser.py --response-delay-ms 400 --out .runtime/asset-detail-slow
python tests/asset_detail_driver_probe.py --out .runtime/asset-detail-probes
python tests/asset_metadata_browser.py --out .runtime/asset-metadata-proof
```

In a policy-restricted test environment, add `--inert` to the two browser drivers;
label the resulting evidence accordingly. The fault probe is always explicitly
inert. It injects faults only into its child fixture process. The workflow uploads
normal/delayed receipts, screenshots, probe logs and the existing metadata proof.

## Other maintenance slices

#200 addresses healthy runtime schema-cache churn (#147). #203 fixes omitted model
resources and duplicate/class-specific bindings in advisory bundle guidance (#184).
They are independent PRs. Broader guidance, uncertain submissions, native creative
acceptance and setup lineage workstreams remain outside this maintenance pass.
No new duplicate backlog issues were opened for the three already tracked defects.
