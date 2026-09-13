# Compact controls beside complete mode explanations

Maintenance for #213, based on inspected main
`22ec26dc549a4648a6e94f80f5d3c870f03c6520`. No preset bindings, field values,
readiness rules or generation actions are changed.

## Measured cause and layout

The shared `.controls` grid stretched each label to the height of its tallest
neighbour. Each label is itself a grid, so its auto-sized rows allocated spare
height to the numeric input. The actual full-shell component fixture measured:

| Viewport / mode | Original Seed height | Patched Seed height |
| --- | ---: | ---: |
| 1440px / Quick | 72.2px | 40.6px |
| 1440px / Quality | 155.9px | 40.6px |
| 390px / Quality | 258.1px | 40.6px |
| 390px / Canonical upstream | 286.0px | 40.6px |

Neighbouring select controls measured 41px. These measurements reproduce the
prior screenshot finding; they are not guessed from CSS alone.

Control labels now align to the start of their row, allow narrow grid sizing and
wrap long text. The I2V-mode label uses the full control row so the explanation
can use the available width instead of creating one long column beside an empty
one. The complete warning remains in the document. Textareas keep their existing
sizing; no fixed global input/textarea height is imposed.

## Browser checks

`tests/control_layout_browser.py` reuses the existing synthetic Studio HTTP
fixture and actual HTML/JS/CSS. Nine scenarios cover Quick, Quality and Canonical
modes at desktop/mobile widths plus a 200%-equivalent desktop reflow viewport.
Long multilingual and unbroken label strings are tested as text. Each scenario
checks compact measured boxes, full-width unclipped help, no horizontal overflow,
keyboard progression, a real Seed hit target, unchanged effective values and
textarea height, and the existing enabled/held readiness result. It also checks
zero generation/backend/asset mutations and zero page exceptions.

The 2x cases use a half-sized CSS viewport and double device scale to reproduce
responsive zoom layout. This is **reflow emulation, not a browser-chrome zoom
shortcut, assistive-technology audit or owner-PC acceptance**. Canonical mode's
intentional seed override is retained; the test compares the value after mode
application against the value after layout/keyboard interactions.

All six initial geometry cases failed on original CSS. Start alignment fixes the
height failures; a separate full-width-help assertion failed before the full-row
rule. All nine final component scenarios pass. Local native navigation returned
`ERR_BLOCKED_BY_ADMINISTRATOR`; local successful runs therefore use the explicit
`--inert` HTTP bridge and are labeled accordingly. No navigation-policy bypass
was attempted. The existing Preset model readiness CI runs the default native
HTTP mode and retains a separate source-hashed result and screenshots.

```sh
python tests/control_layout_browser.py --out .runtime/control-layout-browser
# Component-only fallback in a navigation-restricted test environment:
python tests/control_layout_browser.py --inert --out .runtime/control-layout-inert
python -m unittest discover -s tests
python scripts/validate-repo.py
```

Source manifests and before/after screenshots are in the maintenance download;
hosted native results are recorded separately on the PR. The visual source
change is confined to CSS and can be reverted without data migration. No model
inference, runtime/configuration changes or HUMAN_TODO decisions are involved.
