# Workshop validation record

## Earlier Focus/Studio evidence

The original Focus and Studio delivery retained full suite, component-browser and actual-application evidence in its merged PRs. Those historical counts are not repeated as current-head proof.

## Immersive implementation: fresh local evidence

Executed against the exact local files prepared for this PR:

- `node --test tests/workshop_contracts.cjs`: **8 tests passed**. Coverage includes unknown/malformed preferences, v1 fallback, scoped v2 persistence, 3 layouts, 4 skins, 3 ambiences and the presentation-only DOM seams.
- `python tests/workshop_browser.py --output .runtime/workshop-component`: **8 check groups passed** with Chromium. The shared state sequence exercised all **36 layout × skin × ambience combinations** while preserving prompt and file-input identity and recording zero submissions.
- The component geometry matrix exercised **24 desktop/mobile layout × skin cases** at 1440×900 and 390×844. It checked horizontal overflow, in-viewport Generate geometry, local ambience visibility, full-width stacked Immersive panels and contextual guidance at the narrow viewport, and zero page exceptions.
- The default Focus fixture remained **1695 px** after the Problems disclosure was populated/opened; prompt and Generate stayed in the first 1440×900 viewport.
- Contextual guidance reproduced blocked, ready and output states. Its actions only revealed readiness, focused Generate or opened Recent runs; submission count remained unchanged.
- `python tests/workshop_prototype.py --output .runtime/workshop-prototype`: **9 checks passed**, including the Immersive + Retro Anime + Night Shift review default, embedded ambience art, guarded recipe replacement, local reference retention, non-generating setup preview, adapter feedback, offline route interception, read-only guidance and mobile geometry.
- The prototype/browser sessions recorded **zero HTTP/HTTPS/WebSocket requests and zero page exceptions**. The exporter embeds both production workshop styles, local ambience art and existing repository example images.

The source SVGs were inspected for scripts, `foreignObject` and external references. Production uses inert CSS data copies so SVG serving is not added to the application.

## Guidance contract accuracy follow-up

The #610 accuracy follow-up was developed regression-first. The new static contracts failed while `workshop.js` still read the unreachable `draftDirty` bridge, registered operation/conflict handlers that its capture could never emit, and the workshop documents still described the pre-integration tree.

After the bounded correction, the branch workflow completed all of these commands successfully against the exact published files:

- `node --check app/static/workshop.js`
- `node --test tests/workshop_contracts.cjs tests/reference_model.cjs`
- `python -m unittest tests.test_workshop_frontend tests.test_presentation_context -v`
- `python scripts/validate-repo.py`

The production adapter now registers only readiness review, source review, Generate focus and result opening. The wider pure-context vocabulary remains tested but is not presented as production-reachable without matching observations from an existing owner. Normal current-head `Workshop UI` and `Check studio` runs remain the hosted review gate before the stacked PR is marked ready.

## Hosted native browser gate

`Workshop UI` runs the component driver, lifecycle/handoff checks, `tests/workshop_application.py`, the prototype driver and exporter. The actual-application driver uses native HTTP/browser storage and the real frontend against the existing synthetic API. It must verify:

- Focus + Atelier + None remains the production default;
- v2 presentation preferences contain only layout/skin/ambience;
- all presentation combinations preserve real source lineage and controls;
- one explicit Generate reaches the original handler exactly once and is rejected by the fixture;
- desktop/mobile geometry has no additional submissions or page exceptions.

Current-head hosted results must be inspected before the PR is marked review-ready. A queued or older green run is not evidence for this head.

## Owner acceptance, not claimed by tests

Run one ordinary text-to-image and one reference continuation on the installed ComfyUI environment. Check tab order, long blockers, modal recovery, model-specific controls, real outputs and whether the fixed dock obscures useful review content at the owner's common display sizes.

Review Night Shift and Quiet Morning as optional atmosphere, not model-quality evidence. Confirm that the extra visual structure improves orientation without slowing normal Focus work. No browser fixture proves GPU performance, artistic acceptance, accessibility for every assistive setup, model compatibility or licence clearance.
