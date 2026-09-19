# Workshop validation record

## Earlier Focus, Studio and Immersive evidence

The merged presentation deliveries retain full-suite, component-browser and actual-application evidence in their PRs. Historical counts below describe the scoped workshop package and are not automatically current-head proof for every later stacked slice.

The original Immersive delivery established:

- 3 layouts, 4 skins and 3 ambience requests;
- all 36 layout × skin × ambience combinations preserving prompt and file-input identity with zero presentation-triggered submissions;
- 24 desktop/mobile layout × skin geometry cases at 1440×900 and 390×844, using `None` outside the Immersive layout;
- the Focus + Atelier + None production default;
- a 9-check offline prototype with no observed HTTP/HTTPS/WebSocket requests or page exceptions.

The later evidence-hardening slice expands the geometry matrix to **48 layout × skin × selected-ambience cases**: every Focus, Studio and Immersive combination is exercised at both viewports with both `None` and `Night Shift`. Request and page-error observers are attached to every browser page rather than only the first fixture page.

## Read-only context and guidance

The stacked context slice replaces direct guidance decisions with an immutable, allow-listed projection and semantic intent adapter. Its contracts cover unknown and stale evidence, missing and excess sources, uncertainty, draft conflicts, context-stamp changes and refusal of unsupported, cross-workspace or stale intents.

The latest parent correction is merged into this branch as ancestry. It mirrors the real readiness owner's source requirements instead of inventing required roles: slot-less references remain optional, and reference-board recipes use their board-level minimum rather than marking every slot required.

## Ambience eligibility: scoped local evidence

The ambience-policy slice separates persisted request from effective rendering without moving execution authority.

Fresh scoped commands run against a local copy of the current workshop review package with the exact changed policy, adapter, fixtures, tests and source-requirement correction applied:

```sh
node --check app/static/workshop-ambience-policy.js
node --check app/static/workshop-ambience.js
node --check app/static/studio-shell.js
node --check app/static/workshop.js
node --test tests/presentation_context.cjs tests/workshop_ambience_policy.cjs tests/workshop_contracts.cjs
python -m unittest tests.test_presentation_context tests.test_workshop_ambience_policy tests.test_workshop_frontend -v
STUDIO_BROWSER_EXECUTABLE=/usr/bin/chromium \
  python tests/workshop_ambience_browser.py --output .runtime/workshop-ambience
STUDIO_BROWSER_EXECUTABLE=/usr/bin/chromium \
  python tests/workshop_browser.py --output .runtime/workshop-component
STUDIO_BROWSER_EXECUTABLE=/usr/bin/chromium \
  python tests/workshop_prototype.py --output .runtime/workshop-prototype
python scripts/export-workshop-prototype.py --output .runtime/workshop-prototype/index.html
```

Observed results for the ambience-policy parent:

- **42 Node tests passed** across presentation context, ambience policy and workshop integration contracts.
- **7 Python unittest tests passed**, including normal discovery of both Node contract files and existing workshop frontend contracts.
- The dedicated Chromium ambience journey passed **6 check groups**: available local poster, missing-poster token fallback, offline independence, forced-colour fallback/restoration, None, and stylesheet readiness transitioning through unknown, missing and available states.
- That journey retained the original prompt and file-input DOM nodes, recorded **zero submissions**, **zero HTTP/HTTPS/WebSocket requests** and **zero page exceptions**.
- The standalone prototype passed **9 checks** and exported as one offline HTML document.

## Evidence-fidelity extension

The visual-evidence follow-up was developed test-first against issue #599.

Fresh local results for its exact changed files:

- `python -m unittest tests.test_workshop_evidence_hardening -v`: **4 tests passed** after initially failing on unresolved CSS imports and missing shared geometry/observer helpers.
- `python -m unittest tests.test_workshop_frontend -v`: **5 tests passed**. The ambience inertness contract now decodes the two base64 SVG renditions embedded in the production stylesheet and scans the bytes that actually ship, allowing only the standard SVG XML namespace URL.
- `STUDIO_BROWSER_EXECUTABLE=/usr/bin/chromium python tests/workshop_browser.py ...`: **9 browser check groups passed**.
- The component geometry report now contains **48 cases**: 2 viewports × 3 layouts × 4 skins × 2 ambience selections.
- All 48 geometry pages install both page-error and external-request observers. The run recorded **zero HTTP/HTTPS/WebSocket requests**, **zero page exceptions**, and zero geometry-triggered submissions.
- The core browser driver resolves `workshop-immersive.css` and its imported core itself. The wrapper no longer monkeypatches a different CSS loader, so direct and CI invocation exercise the same production CSS.

The local review package does not contain the complete Python application modules used by `workshop_application.py` and `workshop_handoffs.py`; those native-origin checks are therefore reserved for the hosted workflow rather than being represented as local passes. The application driver now consumes the same 48-case helper and attaches request/error observers to every page; current-head CI must execute that code before the PR is marked review-ready.

## Policy properties qualified by contracts

- `project()` accepts only bounded primitive observations and returns an immutable decision.
- Every decision has `authorizesExecution: false`, `commands: []` and `motionEligible: false`.
- An available local poster is independent from internet and backend reachability.
- hidden documents suspend optional art;
- forced-colour mode and missing/unknown assets use token fallback;
- the adapter treats an unresolved stylesheet as unknown, an error event as missing and a load event as available instead of assuming that requested art exists;
- reduced motion, data saving, user pause and active/uncertain execution retain an available static poster while motion remains ineligible;
- malformed values fail closed and cannot introduce provider URLs, private paths or commands;
- the controller and adapter remove their listeners/observers on destruction;
- policy-load failure still permits the ordinary workshop to mount.

## Guidance contract accuracy follow-up

The #610 accuracy follow-up was developed regression-first. The new static contracts failed while `workshop.js` still read the unreachable `draftDirty` bridge, registered operation/conflict handlers that its capture could never emit, and the workshop documents still described the pre-integration tree.

After the bounded correction, the branch workflow completed all of these commands successfully against the exact published files:

- `node --check app/static/workshop.js`
- `node --test tests/workshop_contracts.cjs tests/reference_model.cjs`
- `python -m unittest tests.test_workshop_frontend tests.test_presentation_context -v`
- `python scripts/validate-repo.py`

The production adapter now registers only readiness review, source review, Generate focus and result opening. The wider pure-context vocabulary remains tested but is not presented as production-reachable without matching observations from an existing owner. Normal current-head `Workshop UI` and `Check studio` runs remain the hosted review gate before the stacked PR is marked ready.

## Hosted native browser gate

`Workshop UI` runs:

1. presentation-context, ambience-policy, workshop and evidence-fidelity contracts;
2. the complete component presentation and 48-case geometry matrix;
3. the dedicated effective-ambience Chromium journey;
4. native disclosure lifecycle and nested-modal handoffs;
5. `tests/workshop_application.py` against native HTTP/browser storage and the real frontend with its synthetic API, including the shared 48-case matrix and external-request observation;
6. the offline prototype and exporter.

The current-head hosted result must be inspected before either stacked PR is marked review-ready. A queued, cancelled, superseded or parent-branch green run is not evidence for the final head. The application lane must continue proving that one explicit Generate reaches the original handler exactly once and that presentation/policy changes never create another submission path.

## Owner acceptance, not claimed by tests

Run one ordinary text-to-image and one reference continuation on the installed ComfyUI environment. Check tab order, long blockers, modal recovery, model-specific controls, real outputs and whether the fixed dock obscures useful review content at the owner's common display sizes.

Review Night Shift and Quiet Morning as optional atmosphere, not model-quality evidence. Confirm that the extra visual structure improves orientation without slowing normal Focus work. No browser fixture proves GPU or media performance, artistic acceptance, accessibility for every assistive setup, model compatibility or licence clearance. No loop, parallax, sound or remote-media permission is delivered here.
