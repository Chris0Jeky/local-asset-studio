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

## Prompt Lab handoff placement

The Prompt Lab text handoff is owned by `studio-workbench.js` and remains the same direct child, buttons and application path. The presentation layer now reserves a named transfer row only while `#uxTransfer` is visible; hidden handoffs do not add an empty grid track or change ordinary Create spacing.

A regression-first Chromium journey reproduced the previous Focus failure before the CSS correction: the transfer started below the editor at approximately 899 px and its Apply action ended below a 900 px viewport. After the correction:

- `python tests/workshop_transfer_handoff.py --output .runtime/workshop-transfer`: **12 presentation cases passed**;
- coverage is 1440×900 and 390×844 across Focus, Studio and Immersive with both `None` and `Night Shift` ambience;
- Focus and Studio place the transfer immediately after the visible Create heading and before ambience or toolbar content;
- Immersive places it after the mode bar and before the presentation toolbar;
- the Apply action remains in the first viewport in every case, with a measured maximum bottom edge of approximately 614 px;
- the panel remains full-width with no horizontal overflow, page exceptions, network requests or execution surface.

The existing `node --test tests/workshop_contracts.cjs` and `python tests/workshop_browser.py` suites were rerun after the correction: **8 Node tests** and **8 browser check groups** passed. This isolated component evidence does not replace the hosted native-application gate.

## Hosted native browser gate

`Workshop UI` runs the component driver, lifecycle/handoff checks, `tests/workshop_application.py`, the focused Prompt Lab handoff journey, the prototype driver and exporter. The actual-application driver uses native HTTP/browser storage and the real frontend against the existing synthetic API. It must verify:

- Focus + Atelier + None remains the production default;
- v2 presentation preferences contain only layout/skin/ambience;
- all presentation combinations preserve real source lineage and controls;
- one explicit Generate reaches the original handler exactly once and is rejected by the fixture;
- desktop/mobile geometry has no additional submissions or page exceptions;
- the Prompt Lab handoff remains visible above the editor without altering its application authority.

Current-head hosted results must be inspected before the PR is marked review-ready. A queued or older green run is not evidence for this head.

## Owner acceptance, not claimed by tests

Run one ordinary text-to-image and one reference continuation on the installed ComfyUI environment. Check tab order, long blockers, modal recovery, model-specific controls, real outputs and whether the fixed dock obscures useful review content at the owner's common display sizes.

Review Night Shift and Quiet Morning as optional atmosphere, not model-quality evidence. Confirm that the extra visual structure improves orientation without slowing normal Focus work. No browser fixture proves GPU performance, artistic acceptance, accessibility for every assistive setup, model compatibility or licence clearance.
