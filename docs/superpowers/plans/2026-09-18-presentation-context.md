# Read-only Presentation Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use regression-first implementation. Preserve one owner for every editable surface and keep this PR stacked on `codex/immersive-studio-presentation`.

**Goal:** Add an immutable presentation-context projection and guarded semantic action boundary without changing production rendering or execution authority.

**Architecture:** A standalone UMD/CommonJS module normalizes allow-listed observations, projects bounded data-only intents, rejects stale or cross-workspace dispatch, and provides an A-B-A freshness gate. The normal Python suite invokes its Node contracts.

**Tech Stack:** Plain JavaScript, Node test runner, Python unittest wrapper.

**Spec:** `docs/superpowers/specs/2026-09-18-presentation-context-design.md`

## Global Constraints

- No production default or visible UI change in this slice.
- No network calls, polling loop, framework dependency, package manifest or build step.
- No prompt text, filesystem path, credentials, image bytes or arbitrary selectors in captured context.
- No submission, retry, recipe-selection or file-staging semantic action.
- Unknown evidence stays unknown.
- Every dispatched intent must match both workspace ID and current context stamp.

---

### Task 1: Specify the boundary before implementation

**Files:**
- Create: `tests/presentation_context.cjs`

**Interfaces:**
- Consumes: the intended public API documented in the design spec.
- Produces: executable contracts for `captureContext`, `project`, `createActionAdapter`, `createObservationGate`, `makeContextStamp` and `ACTIONS`.

- [x] Write contracts for allow-listing, immutability, unknown evidence, source identity, projection precedence, guarded dispatch, A-B-A freshness and deterministic hashing.
- [x] Run `node --test tests/presentation_context.cjs` before implementation.
- [x] Confirm the expected failure is `MODULE_NOT_FOUND` for `app/static/presentation-context.js`.
- [x] Commit the RED contract checkpoint.

### Task 2: Implement the pure context and projection module

**Files:**
- Create: `app/static/presentation-context.js`
- Test: `tests/presentation_context.cjs`

**Interfaces:**
- Produces: `StudioPresentationContext` in browsers and CommonJS exports under Node.
- Produces: frozen context/view data, closed `ACTIONS`, guarded `dispatch(intent)` and freshness tokens.

- [ ] Implement strict primitive normalization and recursive freezing.
- [ ] Implement known/unknown capability and execution observations.
- [ ] Implement exact source-slot projection with separate missing, pending and extra collections.
- [ ] Implement deterministic intent precedence and data-only output.
- [ ] Implement guarded semantic dispatch without arbitrary payload forwarding.
- [ ] Implement monotonic observation tokens and A-B-A rejection.
- [ ] Run `node --test tests/presentation_context.cjs` and confirm all contracts pass.
- [ ] Refactor only after the suite remains green.

### Task 3: Register the contracts in normal repository discovery

**Files:**
- Create: `tests/test_presentation_context.py`

**Interfaces:**
- Consumes: `tests/presentation_context.cjs`.
- Produces: one unittest-discoverable test that skips only when Node is unavailable.

- [ ] Add a bounded subprocess wrapper with captured output and a 30-second timeout.
- [ ] Run `python -m unittest tests.test_presentation_context -v`.
- [ ] Confirm Node failure output propagates through Python when a sentinel assertion is introduced, then restore the passing file.

### Task 4: Document usage and claim boundaries

**Files:**
- Create: `docs/workshop/PRESENTATION-CONTEXT.md`

**Interfaces:**
- Consumes: the implemented public API.
- Produces: integration guidance for the later workshop adapter slice.

- [ ] Document the normalized context, intent precedence and action adapter.
- [ ] Include a concrete safe integration example that maps semantic IDs to existing local reveal/focus handlers.
- [ ] State that the module is not loaded by production in this PR and does not prove frontend, backend or GPU behaviour.

### Task 5: Publish and qualify the stacked PR

**Files:**
- Modify only if evidence changes: this plan and the PR description.

- [ ] Run fresh local Node and Python contract commands.
- [ ] Create a draft PR targeting `codex/immersive-studio-presentation`.
- [ ] Inspect all current-head hosted workflows.
- [ ] Resolve actionable review findings with regression coverage.
- [ ] Mark ready for review only after current-head CI is green and the PR body distinguishes pure contract evidence from production integration.
