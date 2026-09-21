# Adaptive experience delivery and qualification plan

> For an implementation session: read this plan with UX-SPEC, ARCHITECTURE and STACK-ADR. Use regression-first work, isolated branches and review checkpoints. These are proposed tasks, not completed product features.

**Goal:** make the existing Studio easier to operate through task-aware presentation and optional bounded ambience.

**Architecture:** existing domain owners provide immutable context to a deterministic presentation layer. New component islands initially own only their own DOM. Decorative media cannot issue domain commands.

**Stack:** existing Python/JavaScript first; TypeScript/Vue/Vite is a gated maintainer-tooling proposal.

## Dependency graph

```text
Foundation qualification (#539)
    -> A1 context/action boundary -> A2 guidance island -> A3 source/recipe ownership pilot
                                   |                    -> A6 broader workflow lenses
                                   -> A4 appearance policy -> A5 accepted asset pilot
A7 measurement and accessibility spans every slice
```

Review current main and #540/#541 before implementation. Do not cherry-pick stale snapshots just because this document names them. Issue numbers below are traceability, not closure instructions. Broader owner feedback remains separate from any automated test result.

## A1. Read-only context and semantic targets

Proposed files: `app/static/presentation-context.js`, `tests/presentation_context.cjs`; narrow adapters beside the current workbench/guide owners only after confirming their current API.

Consumes: existing `StudioSetupDraft.capture/stamp/busy`, exact catalog bindings, readiness and guide state. Produces proposed `captureContext()` and `project(context, preferences)` contracts from ARCHITECTURE. The action adapter resolves closed semantic IDs to current reveal/navigation owners.

- [ ] Write tests proving unknown readiness remains unknown and a task/skin change cannot produce a command.
- [ ] Test source overflow, required slot identity, a stale A-B-A observation and cross-workspace rejection.
- [ ] Implement the smallest pure projection and read-only adapter; avoid a second polling loop.
- [ ] Run existing frontend handoff tests and relevant real-frontend fixture journeys.
- [ ] Publish one PR with actual changed-owner diagrams and no production default change.

Example acceptance assertion for the future contract:

```js
const before = structuredClone(context);
const view = project(context, {task: 'pose', assistance: 'guided', skin: 'retro-anime'});
assert.deepEqual(context, before);
assert.equal(view.authorizesSubmission, false);
assert.equal(view.primaryAction.id, 'inspect-operation'); // uncertain context fixture
```

## A2. Useful framework spike, not an empty shell

Proposed files: `frontend/` toolchain/lockfile, context types, `TaskGuide.vue`, its tests, and the generated static manifest described in STACK-ADR. Build-watch files are served from the Python origin. The component receives snapshots and dispatches semantic navigation intents; it never imports a job client.

- [ ] Capture baseline timing, payload, DOM identity and request counts for one real fixture journey.
- [ ] Build the guidance/discovery island behind an explicit local flag.
- [ ] Test mount/unmount, storage denial, keyboard flow, network denial, error containment and OS reduced motion.
- [ ] Compare against the same fixture, not a synthetic prettier page with fewer responsibilities.
- [ ] Record the package versions, build hash, compressed payload and Windows launch proof. Accept or reject the ADR based on these findings.

Do not widen origin permissions, require runtime Node or duplicate prompt state to pass the spike.

## A3. Source board and recipe difference review

Proposed files: a source-display component and a replacement-difference component under the selected frontend stack; adapters remain with reference/setup owners. Test using `tests/recipe_shortlist_browser.py`, `tests/setup_apply_browser.py`, `tests/setup_lineage_browser.py` and the applicable workshop suite after its merge.

- [ ] Make required/missing/selected/checked/staged source states visible without changing their meaning.
- [ ] Add keyboard reorder and deliberate replace/remove using existing commands.
- [ ] Preview complete recipe changes: text, parameters, source order/capacity, backend and unsupported fields.
- [ ] Prove cancel leaves File objects and current values intact; prove successful apply restores the correct focus.
- [ ] Exercise unknown response recovery and source disappearance before calling the slice complete.

## A4. Appearance and ambience policy

Proposed files: pure `ambience-policy` module, a bounded media renderer and appearance preferences component, plus policy/browser tests. See AMBIENCE for precedence.

- [ ] First test internet-off/local-backend-ready and internet-on/backend-down as different cases.
- [ ] Test reduced motion, hidden tab, unknown/running execution, user pause and data saving.
- [ ] Add a static local poster slot before any video/parallax support.
- [ ] Introduce one local loop and request-epoch handling; test fallback on slow/error/obsolete loads.
- [ ] Measure while the real generation workload runs. Keep still mode as default until the owner chooses otherwise.

No remote downloader, service worker, shader framework or sound engine belongs in this first media slice.

## A5. Produce a coherent pilot pack

Use the companion asset production kit. Select one world, one scene anchor, one quiet counterpart, one workflow illustration family and the essential empty states. Approve master composition before generating derivatives. A future generation session must use the real tool, record output identity and return a receipt; this plan's asset list is not such a receipt.

Acceptance: stable IDs, honest provenance, local poster fallback, working crops at 390/1440 widths, no baked labels, no obstructed controls, acceptable loop seam and bounded payload. Do not acquire six complete worlds before testing one in the real UI.

## A6. Expand task lenses selectively

Prioritize W01/W03/W04/W15, then W10/W11/W12, then temporal/native/3D workflows. Each lens uses a named existing service or declares a missing prerequisite. One lens PR must show an end-to-end next-action path, a failure path and a preservation test. Do not count an unavailable action's decorative card as implemented capability.

## A7. Paired evaluation and owner decision

Retain the original wishlist's 1440x900 and 390x844 scenarios, and add 1280x800, 1920x1080 and 200% zoom. Freeze the same recipe, inputs, backend state and output fixture for a comparison. Separate fresh users from returning users; counterbalance layout order and allow a warm-up. A small owner trial is formative, not a statistically powered A/B result.

Measure task completion, time to first *intentional* action, wrong turns, unsupported-action confusion, scroll distance, successful recipe switch/continuation, recovery without duplicate commands, and optional calm/cluttered feedback. Generation click-through is not success if the user ran the wrong setup. Measure time waiting for models separately from time finding controls.

Performance targets to validate, not results: initial island <=150 KiB gzip JS+CSS; first decorative transfer <=350 KiB; no more than one decorative loop; no media work in hidden state; no sustained layout shift from image arrival; no detectable duplicate domain command. Report actual p50/p75 interaction timing and long tasks rather than declaring the app “fast”.

## Existing proof commands to preserve

```sh
python scripts/validate-repo.py
python -m unittest discover -s tests
python -m unittest discover -s tests -p 'test_frontend_handoffs.py'
python tests/studio_use_cases.py
python tests/recipe_shortlist_browser.py --out .runtime/adaptive-shortlist
python tests/setup_apply_browser.py --out .runtime/adaptive-setup
python tests/setup_lineage_browser.py --out .runtime/adaptive-lineage
```

The browser commands require the repository's documented dependencies and fixtures. They are not executed or claimed passing by this plan. Add narrow projection/ambience tests with the implementation. Keep native-origin, synthetic-transport, model execution and owner acceptance results separate.

## Release and rollback

Every slice records source/build identity, changed ownership, test scope and remaining gaps. Default-off trial flags must be user-visible. A rollback unloads the new renderer/media module and restores the previous UI without restoring an older domain draft or resubmitting anything. Retain the previous static bundle until the new manifest is verified. Remove superseded observers/listeners when ownership moves; do not leave permanent parallel editors.

## Review decisions

The strategy needs three owner choices before production commitments: accept a maintainer-only build step; choose the first art world; choose whether any remote decoration is permitted. Existing creative decisions in HUMAN_TODO and real-machine #539 remain open. Do not mass-create roadmap issues until existing relevant issues have been reconciled; the seven slices above are a reviewable backlog rather than a second task tracker.
