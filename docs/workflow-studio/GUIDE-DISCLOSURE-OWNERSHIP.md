# Guide disclosure ownership

15 September 2026. Reconciled against main `85dc151ea89fa730967dcee4920750411f0c14cd`.
Refs #118, #278 and the guide findings in #360; these broader issues remain open.

## Contract

A stage may reveal its first usable target once. After that, routine observations
only inspect visibility. Closing a panel is a user decision: unrelated clicks,
input events, recipe notifications, automatic evidence refreshes and Re-check must
not reopen it or move focus. **Show the control** explicitly permits reopening
collapsed ancestors and moving focus, never activating the control. A target that
has not yet appeared retains its one initial reveal when its feature becomes
available. Navigation to a new stage starts a new reveal allowance.

The shipped coach and shared target helpers retain their existing responsibilities:
`find()` owns the per-stage allowance; `peekTarget()` observes;
`visibleTarget()` prefers an already-visible candidate before trying reveal;
`revealTarget()` opens only eligible candidates and restores newly opened panels
when that candidate remains unusable. Hidden tools and CSS-hidden ancestors stay
hidden. First summaries and closed details elements themselves can still be targets.

The bug had two layers. `find()` called the mutating helper on every observation,
even after its focus allowance had been consumed. Separately, Chromium can return
layout boxes for descendants of a closed details element. Checking rectangles alone
therefore mistook hidden descendants for visible controls, including nested ones.
The helper now checks closed ancestors explicitly while preserving first-summary
visibility. Neither change adds HTTP actions, saves, execution authority or approval.

## Verification and boundaries

`tests/studio_guide_disclosure_browser.py` executes the unmodified shipped script
bytes against real Chromium DOM, details layout, focus and keyboard default actions.
The page is synthetic; location/history/manifest reads are injected in-memory seams.
This is deliberately not a full Studio page, native navigation test or GPU run.

```bash
python tests/studio_guide_disclosure_browser.py --out .runtime/guide-disclosure-proof -v
# An existing browser may be selected explicitly without installing anything:
python tests/studio_guide_disclosure_browser.py --browser-path /path/to/chromium -v
node --check app/static/studio-guide.js
node --check app/static/studio-guide-state.js
```

The initial nine-test regression run failed on the exact pinned source (including
false visibility, hidden-panel mutation and reopening). After the patch the expanded
12-test suite passed locally, including 390px and 200%-CSS-zoom cases, keyboard Show,
Pause, delayed targets, first summaries and fallback restoration. No fixture action
was activated, no unexpected network request occurred, and guide reads stayed GET-only.

The existing Guided journey browser CI lane now runs this fixture alongside the
unchanged full-page journey driver. Local browser navigation is policy-blocked and
only the touched source files were reconstructed locally with matching Git blob
hashes; the full repository suite, validator and full-page tests require hosted CI.
Do not infer their result from the isolated fixture. This patch makes no screen-reader
or owner-machine acceptance claim. #360's heading, recipe-summary and exception-import
findings are separate work; #118's specialist journey acceptance remains outstanding.
