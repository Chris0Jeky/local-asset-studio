# Focus validation record

Baseline source: `b8b1409d0f397b7562e67366e51629826ec0ae7d` (18 September 2026 session).

## Executed locally

- Full offline Python suite: **2925 tests, 20 skipped, 281.417 seconds, exit 0** on the first implementation snapshot. This precedes the later presentation refinements and the new Node-contract wrapper; do not mislabel it as final-head CI.
- `node --test tests/workshop_contracts.cjs`: 3 passed.
- `python -m unittest discover -s tests -p test_workshop_frontend.py`: 1 passed, invokes those real Node contracts.
- `python tests/workshop_browser.py`: original control identities, cancellation/acceptance, same-recipe preservation, focus return, disabled state, explicit original handler, 1440×900 and 390×844 geometry passed with system Chromium 144.
- Actual full application source was also rendered against the existing synthetic API fixture, using an offline document loader: default Focus document **1513 px** at 1440×900; recipe, prompt and Generate visible; no JS exceptions; no `/api/jobs` request. Its in-memory storage shim is **not** evidence of native storage/reload correctness.
- Baseline repository validation: 80 preset graphs/bindings and 136 pinned assets passed.

The component fixture explicitly labels itself non-generating. Actual-application fixture health and its 42-second estimate are synthetic data, not a measurement of Chris's PC. The wishlist's 3397 px figure belongs to its earlier QA; the two states are not a controlled A/B test.

## Hosted native browser gate

`Workshop UI` runs the component driver and `tests/workshop_application.py`, using real HTTP, browser storage, the actual frontend and the existing synthetic API. It exports screenshots and `report.json` files as `workshop-browser-evidence`. The application driver checks native reload/draft recovery, all shipped presentation combinations, lineage, control identity and exactly one explicit original `/api/jobs` request. The fixture rejects that request rather than fabricating an accepted generation.

The existing use-case driver now counts opening the recipe picker, negative disclosure, review details and recent runs as real actions. Readiness tests reveal collapsed sections before exercising their original actions.

## Owner acceptance, not claimed by tests

Run one ordinary text-to-image and one reference continuation on the installed ComfyUI environment after merging. Check useful tab order, recovery, long errors, model-specific controls and actual outputs. Choose the preferred layout/skin with the same recipe, prompt and sources. Measure time to ready-to-Generate, scroll depth and perceived clutter; faster submission is not itself better art. Existing HUMAN_TODO creative decisions remain open and untouched.
