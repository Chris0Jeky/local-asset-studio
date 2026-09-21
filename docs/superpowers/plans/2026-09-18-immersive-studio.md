# Immersive Studio Implementation Plan

> **For agentic workers:** Use regression-first implementation and preserve one owner for every editable surface.

**Goal:** Ship an optional Immersive Studio layout, Retro Anime skin and paired local ambience while preserving the existing Create workbench and execution authority.

**Architecture:** Extend the existing `StudioWorkshop` presentation adapter. Keep one set of live controls and add only presentation DOM, allow-listed preferences and read-only guidance derived from current UI state. Ambience is local, inert and optional.

**Tech Stack:** Plain JavaScript, CSS, SVG source masters, Python/Playwright browser tests, Node test runner.

**Spec:** `docs/superpowers/specs/2026-09-18-immersive-studio-design.md`

## Global constraints

- Normal Python startup remains offline and requires no Node, npm, CDN or remote media.
- Existing prompt, reference, recipe, setup, readiness, output and Generate owners remain unchanged.
- Presentation switches submit zero jobs and preserve exact prompt and file-input nodes.
- Existing Focus, Studio, Atelier, Arcade and Sakura options remain supported.
- System fonts only; reduced-motion and forced-colour fallbacks are required.

### Task 1: Lock the preference and presentation contract

- [x] Add failing contracts for three layouts, four skins, three ambiences, v1 fallback and v2 persistence scope.
- [x] Verify the expected RED state on the first branch commit.
- [x] Implement the v2 allow-list and legacy fallback in `workshop.js`.
- [x] Pass `node --test tests/workshop_contracts.cjs`.

### Task 2: Add the local visual environment and skin controls

- [x] Add browser assertions for native controls, the visual skin mirror and zero submissions.
- [x] Add Night Shift and Quiet Morning source SVGs.
- [x] Add the environment header, ambience selector and wide visual skin picker.
- [x] Add Retro Anime tokens, inert embedded art, None fallback, mobile and forced-colour behaviour.
- [x] Preserve the exact prompt/file nodes through all 36 presentation combinations.

### Task 3: Add Immersive Studio and contextual rails

- [x] Add failing browser cases for wide geometry and bounded guidance.
- [x] Add the setup rail, three-column layout and stacked fallback.
- [x] Derive guidance from existing blocker, Generate and output observations only.
- [x] Prove guidance reveals/focuses existing surfaces without submitting.
- [x] Extend component and actual-application test plans for layout × skin × ambience.

### Task 4: Update the offline prototype and documentation

- [x] Add the second production stylesheet to the prototype/exporter.
- [x] Start the review prototype in Immersive Studio + Retro Anime + Night Shift while production remains Focus + Atelier + None.
- [x] Embed ambience art and existing repository examples with zero network requests.
- [x] Document options, provenance, authority boundaries and remaining GPU/owner acceptance.
- [x] Pass the updated offline prototype checks.

### Task 5: Final verification and PR readiness

- [x] Run `node --test tests/workshop_contracts.cjs`.
- [x] Run `python tests/workshop_browser.py --output .runtime/workshop-component`.
- [x] Run `python tests/workshop_prototype.py --output .runtime/workshop-prototype`.
- [ ] Run hosted actual-application and repository checks on the published head.
- [ ] Inspect current-head review feedback and resolve actionable findings.
- [ ] Mark the PR ready only after current-head CI and review evidence are inspected.
