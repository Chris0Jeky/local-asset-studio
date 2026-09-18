# Immersive Studio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship an optional Immersive Studio layout, Retro Anime skin and paired local ambience while preserving the existing Create workbench and execution authority.

**Architecture:** Extend the existing `StudioWorkshop` presentation adapter. Keep one set of live controls and add only presentation DOM, allow-listed preferences and read-only guidance derived from current UI state. Local SVG ambience is decorative and optional.

**Tech Stack:** Plain JavaScript, CSS, SVG, Python/Playwright browser tests, Node test runner.

**Spec:** `docs/superpowers/specs/2026-09-18-immersive-studio-design.md`

## Global Constraints

- Normal Python startup remains offline and requires no Node, npm, CDN or remote media.
- Existing prompt, reference, recipe, setup, readiness, output and Generate owners remain unchanged.
- Presentation switches submit zero jobs and preserve the exact prompt and file input nodes.
- Existing Focus, Studio, Atelier, Arcade and Sakura options remain supported.
- System fonts only; reduced-motion and forced-colour fallbacks are required.

---

### Task 1: Lock the preference and presentation contract

**Files:**
- Modify: `tests/workshop_contracts.cjs`
- Modify: `app/static/workshop.js`

**Interfaces:**
- Produces: `LEGACY_STORAGE_KEY`, `STORAGE_KEY`, `LAYOUTS`, `SKINS`, `AMBIENCES`, `preferences(value)`, `readPreferences(storage)`, `writePreferences(storage, value)`.

- [ ] **Step 1: Write failing contracts** for three layouts, four skins, three ambiences, v1 migration, v2 persistence and exclusion of prompt/model data.
- [ ] **Step 2: Run** `node --test tests/workshop_contracts.cjs` and confirm failures are caused by the missing v2 model.
- [ ] **Step 3: Implement the v2 allow-list** and legacy fallback in `workshop.js`.
- [ ] **Step 4: Run** `node --test tests/workshop_contracts.cjs` and confirm all contracts pass.
- [ ] **Step 5: Commit** `test/feat(workshop): add versioned immersive presentation preferences`.

### Task 2: Add the local visual environment and skin controls

**Files:**
- Create: `app/static/workshop-assets/night-shift.svg`
- Create: `app/static/workshop-assets/quiet-morning.svg`
- Modify: `app/static/workshop.js`
- Modify: `app/static/workshop.css`
- Modify: `docs/workshop/ASSETS.md`

**Interfaces:**
- Consumes: the Task 1 preference model.
- Produces: `#workshopAmbience`, `#workshopSkin`, `[data-workshop-skin-choice]`, `.wk-immersive-hero`, `body[data-workshop-ambience]`.

- [ ] **Step 1: Add browser assertions** that the native controls and visual skin buttons exist, agree and make zero submissions.
- [ ] **Step 2: Run the browser contract** and confirm the new selectors are absent.
- [ ] **Step 3: Add the local SVG pair**, hero markup, ambience selector and visual skin picker.
- [ ] **Step 4: Add Retro Anime tokens**, local background rules, None fallback, narrow viewport and forced-colour behaviour.
- [ ] **Step 5: Run Node and browser contracts** and confirm all presentation combinations preserve the same prompt/file nodes.
- [ ] **Step 6: Commit** `feat(workshop): add Retro Anime skin and local ambience`.

### Task 3: Add Immersive Studio and contextual rails

**Files:**
- Modify: `app/static/workshop.js`
- Modify: `app/static/workshop.css`
- Modify: `tests/workshop_browser.py`
- Modify: `tests/workshop_application.py`

**Interfaces:**
- Consumes: current readiness text, Generate disabled state, output count and existing `reveal()` helper.
- Produces: `.wk-setup-rail`, `.wk-guidance`, `#workshopGuidanceAction`, `#workshopGuidanceWhy`.

- [ ] **Step 1: Add failing browser cases** for wide three-column geometry, stacked mobile geometry, blocked/ready/output guidance and zero implicit submissions.
- [ ] **Step 2: Run the cases** and verify failure because the rails/layout do not exist.
- [ ] **Step 3: Create the rails** using existing recipe, review and result owners; guidance may only focus or reveal.
- [ ] **Step 4: Add the 3-column CSS** at wide widths and deterministic single-column fallback below the breakpoint.
- [ ] **Step 5: Run browser and actual-application fixture checks**, including all layout × skin × ambience combinations.
- [ ] **Step 6: Commit** `feat(workshop): add Immersive Studio context layout`.

### Task 4: Update the offline prototype and documentation

**Files:**
- Modify: `docs/workshop/prototype-data.js`
- Modify: `tests/workshop_prototype.py`
- Modify: `docs/workshop/README.md`
- Modify: `docs/workshop/DESIGN.md`
- Modify: `docs/workshop/VALIDATION.md`

**Interfaces:**
- Consumes: production workshop JS/CSS and the exporter’s existing `/static/` asset embedding.
- Produces: an offline preview that starts in Immersive Studio + Retro Anime + Night Shift and still performs no request or generation.

- [ ] **Step 1: Update prototype expectations first** for the new initial presentation, local SVG embedding and mobile fallback.
- [ ] **Step 2: Run** `python tests/workshop_prototype.py --output .runtime/workshop-prototype` and confirm the old prototype defaults fail.
- [ ] **Step 3: Set the prototype presentation defaults** without changing production defaults.
- [ ] **Step 4: Document the new options, provenance, boundaries and remaining owner/GPU acceptance.
- [ ] **Step 5: Re-run the prototype and documentation link checks.
- [ ] **Step 6: Commit** `docs(workshop): document immersive presentation and qualification`.

### Task 5: Final verification and PR readiness

**Files:**
- Review all changed files.

- [ ] **Step 1: Run** `node --test tests/workshop_contracts.cjs`.
- [ ] **Step 2: Run** `python tests/workshop_browser.py --output .runtime/workshop-component`.
- [ ] **Step 3: Run** `python tests/workshop_prototype.py --output .runtime/workshop-prototype`.
- [ ] **Step 4: Run targeted unittest discovery** for the workshop frontend wrapper and repository validation commands documented in `docs/workshop/VALIDATION.md`.
- [ ] **Step 5: Inspect the diff** for duplicated editors, extra submission handlers, remote URLs, prompt persistence and unlabelled synthetic claims.
- [ ] **Step 6: Update the PR body with exact evidence and remaining limits; mark ready for review only after current-head CI is inspected.
