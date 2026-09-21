# Workshop Context-Guidance Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use regression-first implementation. Keep this PR stacked on `codex/presentation-context-boundary` and preserve the original domain handlers.

**Goal:** Drive the existing Immersive Studio guidance rail from the read-only presentation-context boundary without adding execution authority or replacing editable controls.

**Architecture:** Load `presentation-context.js` before the workshop adapter, capture bounded observations during the existing `sync()` cycle, render immutable semantic intents, and dispatch them through a closed local action map with workspace/context-stamp checks.

**Tech Stack:** Plain JavaScript, existing DOM adapter, Node contracts, Playwright browser drivers, Python unittest and offline prototype exporter.

**Spec:** `docs/superpowers/specs/2026-09-18-workshop-context-guidance-design.md`

## Global Constraints

- Existing prompt, file inputs, recipe state, readiness logic, result gallery and Generate handler remain the only owners.
- No prompt text, path, image bytes, arbitrary selector or executable callback enters presentation context.
- No new observer, timer, polling loop, network request, package or build step.
- Guidance may reveal/focus only; it cannot submit, retry, select a recipe, stage a source or resolve a conflict.
- Missing context module fails closed to the underlying unenhanced Create interface.

---

### Task 1: Specify integration and loading contracts

**Files:**
- Modify: `tests/workshop_contracts.cjs`
- Modify: `tests/workshop_browser_core.py`
- Modify: `tests/workshop_prototype.py`

**Interfaces:**
- Consumes: `StudioPresentationContext` from #581.
- Produces: expected script ordering, semantic intent IDs, stale-intent rejection and original-node/submission invariants.

- [x] Add failing static contracts for context-before-workshop loading, `Context.project()`, `createActionAdapter()`, `presentationView()` and `dispatchIntent()`.
- [x] Add browser expectations for `data-intent`, frozen no-command projections, prompt-redacted inspection, source-review focus and stale-context rejection.
- [x] Run `node --test tests/workshop_contracts.cjs` and verify the three new contracts fail because integration is absent.

### Task 2: Load the context boundary before the workshop

**Files:**
- Modify: `app/static/studio-shell.js`
- Modify: `docs/workshop/prototype.html`
- Modify: `scripts/export-workshop-prototype.py`

**Interfaces:**
- Produces: deterministic script order and an offline export containing both modules.

- [x] Add a same-origin context script and create the workshop script only from its `onload` handler.
- [x] Leave the base Create application intact if context loading fails.
- [x] Add the context script before workshop in the prototype source.
- [x] Verify exporter source-order inlining and no external request.
- [x] Run static contracts until loading tests pass.

### Task 3: Capture bounded existing observations

**Files:**
- Modify: `app/static/workshop.js`

**Interfaces:**
- Consumes: existing selected recipe, reference records/current upload state, file inputs, readiness blockers, Generate disabled state and result gallery.
- Produces: one frozen `Context.captureContext()` snapshot per existing scheduled sync.

- [x] Inject the boundary into the UMD/CommonJS wrapper and refuse to mount without it.
- [x] Add bridge readers for exact reference-slot IDs, staged references and pending local-file count.
- [x] Maintain a local non-sensitive context revision through the existing schedule path.
- [x] Build capability, draft and execution observations without prompt text or paths.
- [x] Keep appearance preferences as projection metadata only.

### Task 4: Render and dispatch semantic guidance

**Files:**
- Modify: `app/static/workshop.js`

**Interfaces:**
- Produces: `presentationView(): Readonly<View>` and `dispatchIntent(intent): DispatchResult` on the existing workshop test/inspection API.

- [x] Map closed action IDs to existing reveal/focus functions.
- [x] Replace inline blocked/ready/results conditionals with `Context.project()` output.
- [x] Render title, label, description, reason and text-only secondary observations.
- [x] Store only the current semantic ID in `data-intent`.
- [x] Reject stale intents after an input/recipe/readiness/source/output change.

### Task 5: Qualify component, prototype and application behavior

**Files:**
- Modify: `tests/workshop_browser_core.py`
- Modify: `tests/workshop_prototype.py`
- Modify if evidence changes: `docs/workshop/VALIDATION.md`, `docs/workshop/README.md`

- [x] Run `node --test tests/presentation_context.cjs tests/workshop_contracts.cjs`.
- [x] Run `python -m unittest tests.test_presentation_context tests.test_workshop_frontend -v`.
- [x] Run `python tests/workshop_browser.py --output .runtime/workshop-context`.
- [x] Run `python tests/workshop_prototype.py --output .runtime/workshop-context-prototype`.
- [x] Run the actual-application driver and relevant repository validator.
- [x] Confirm zero implicit submissions, zero page exceptions, zero external requests and exact original-node identity.

### Task 6: Publish the stacked PR

- [x] Open a draft PR targeting `codex/presentation-context-boundary` from the RED checkpoint.
- [x] Update the PR body with final architecture, exact verification and remaining live-machine acceptance.
- [x] Inspect current-head hosted workflows and review threads.
- [x] Add regression coverage for every actionable review finding.
- [x] Mark ready only after current-head checks are green.

## Completion note

The integration was implemented and qualified in #582. Independent follow-up #626 moved reference readiness into one shared projection and corrected source focus, replacement confirmation and secondary blocker detail. The final accuracy follow-up removes unreachable production handlers and reconciles the delivered documentation. All implementation and publication gates above are complete.
