# Workshop Ambience Eligibility Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a pure local ambience policy and browser adapter that distinguishes the persisted ambience request from the effective static rendering decision without gaining generation authority.

**Architecture:** A standalone UMD-style policy module normalises bounded observations and returns an immutable `none | suspended | tokens | poster` projection. The existing workshop adapter supplies live presentation observations, and a small controller updates allow-listed DOM attributes and status text. Existing CSS art remains the only poster renderer; no media fetch, loop, framework, service worker, or backend change is introduced.

**Tech Stack:** Plain JavaScript, Node `node:test`, existing Python unittest discovery, existing Playwright workshop fixtures, CSS, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-18-workshop-ambience-policy-design.md`

## Global Constraints

- Production default remains `Focus + Atelier + None`.
- Normal Python startup remains offline and requires no Node, npm, CDN, or build step.
- No remote media, video, audio, autoplay, service worker, shader framework, provider credentials, or dynamic downloader.
- No prompt, recipe, source, job, queue, readiness, recovery, or Generate ownership moves into the policy.
- Policy output always has `authorizesExecution: false` and `commands: []`.
- Still rendering is the only delivered media mode; `motionEligible` remains false.
- Internet state and backend state must not gate an available local poster.

---

### Task 1: Specify the pure ambience policy

**Files:**
- Create: `tests/workshop_ambience_policy.cjs`
- Create: `tests/test_workshop_ambience_policy.py`
- Create: `app/static/workshop-ambience-policy.js`

**Interfaces:**
- Produces: `normalize(input) -> Observation`
- Produces: `project(input) -> Decision`
- Produces: exported frozen constants `REQUESTS`, `ASSET_STATES`, `RENDER_MODES`, `EXECUTION_STATES`
- Decision fields: `requested`, `renderMode`, `assetId`, `heroVisible`, `motionEligible`, `reason`, `status`, `authorizesExecution`, `commands`

- [ ] **Step 1: Write failing policy contracts**

Add Node contracts that assert:

```js
const offline = Policy.project({
  requested:'night-shift', assetState:'available', visibility:'visible',
  internetState:'offline', backendState:'ready'
});
const backendDown = Policy.project({
  requested:'night-shift', assetState:'available', visibility:'visible',
  internetState:'online', backendState:'down'
});
assert.equal(offline.renderMode, 'poster');
assert.equal(backendDown.renderMode, 'poster');
assert.deepEqual(
  {mode:offline.renderMode, asset:offline.assetId},
  {mode:backendDown.renderMode, asset:backendDown.assetId}
);
```

Also assert `none`, hidden, forced colours, missing/unknown asset, reduced motion, save data, user pause, active/uncertain execution, malformed input, immutable output, empty commands, and false authority.

- [ ] **Step 2: Run the Node contract and verify RED**

Run:

```bash
node --test tests/workshop_ambience_policy.cjs
```

Expected: FAIL because `app/static/workshop-ambience-policy.js` does not exist.

- [ ] **Step 3: Add the unittest discovery wrapper**

Create a Python test that runs the Node file with `subprocess.run(..., check=True, capture_output=True, text=True)` and reports stdout/stderr on failure.

- [ ] **Step 4: Implement the minimum pure policy**

Implement:

```js
function project(input = {}) {
  const observation = normalize(input);
  // exact precedence from the design spec
  return deepFreeze({
    requested: observation.requested,
    renderMode,
    assetId,
    heroVisible,
    motionEligible:false,
    reason,
    status,
    authorizesExecution:false,
    commands:[]
  });
}
```

Do not include DOM access in `project()`.

- [ ] **Step 5: Run focused tests GREEN**

Run:

```bash
node --check app/static/workshop-ambience-policy.js
node --test tests/workshop_ambience_policy.cjs
python -m unittest tests.test_workshop_ambience_policy -v
```

Expected: all pass with no warnings.

- [ ] **Step 6: Commit**

```bash
git add app/static/workshop-ambience-policy.js tests/workshop_ambience_policy.cjs tests/test_workshop_ambience_policy.py
git commit -m "feat(workshop): add local ambience eligibility policy"
```

### Task 2: Add the bounded browser controller

**Files:**
- Modify: `app/static/workshop-ambience-policy.js`
- Modify: `tests/workshop_ambience_policy.cjs`

**Interfaces:**
- Consumes: `project(input)` from Task 1
- Produces: `createController(window, options) -> {update, snapshot, destroy}`
- `update(patch)` accepts only `requested`, `assetState`, `executionState`, `internetState`, `backendState`, and `userPaused`

- [ ] **Step 1: Add failing controller tests**

Use small fake document/media-query/event objects and assert:

```js
const controller = Policy.createController(fakeWindow, {
  hero, create, status,
  initial:{requested:'night-shift', assetState:'available'}
});
assert.equal(body.dataset.workshopAmbienceRender, 'poster');
visibilityState = 'hidden';
document.dispatch('visibilitychange');
assert.equal(body.dataset.workshopAmbienceRender, 'suspended');
controller.destroy();
assert.equal(document.listenerCount('visibilitychange'), 0);
```

Also verify forced-colour and reduced-motion listeners, save-data observation, bounded update keys, and zero calls to fetch or service-worker APIs.

- [ ] **Step 2: Verify RED**

Run:

```bash
node --test tests/workshop_ambience_policy.cjs
```

Expected: FAIL because `createController` is absent.

- [ ] **Step 3: Implement controller**

Register `visibilitychange` plus media-query `change` listeners, render only allow-listed dataset values and plain text, and remove every listener in `destroy()`.

- [ ] **Step 4: Verify GREEN**

Run the Node and Python commands from Task 1.

- [ ] **Step 5: Commit**

```bash
git add app/static/workshop-ambience-policy.js tests/workshop_ambience_policy.cjs
git commit -m "feat(workshop): observe effective ambience safely"
```

### Task 3: Integrate policy into the production workshop

**Files:**
- Modify: `app/static/studio-shell.js`
- Modify: `app/static/workshop.js`
- Modify: `app/static/workshop-immersive-core.css`
- Modify: `tests/workshop_contracts.cjs`
- Modify: `tests/workshop_fixture.html`
- Modify: `docs/workshop/prototype.html`

**Interfaces:**
- Consumes: global/CommonJS `StudioWorkshopAmbiencePolicy`
- Produces: `create.__workshop.ambienceDecision()` for inspection only
- Produces: `#workshopAmbienceStatus` status text

- [ ] **Step 1: Add failing static integration contracts**

Require:

```js
assert.ok(shell.indexOf('/static/workshop-ambience-policy.js') < shell.indexOf('/static/workshop.js'));
assert.match(workshop, /createController/);
assert.match(workshop, /workshopAmbienceStatus/);
assert.doesNotMatch(workshop, /fetch\(|serviceWorker|\.click\(\)/);
```

The prototype and fixture must load the policy before `workshop.js`.

- [ ] **Step 2: Verify RED**

Run:

```bash
node --test tests/workshop_contracts.cjs
```

Expected: FAIL on missing policy load and controller integration.

- [ ] **Step 3: Load policy before workshop**

Add the script in the shell and static fixtures. Preserve progressive failure: `workshop.js` must still mount if the policy global is absent.

- [ ] **Step 4: Wire observations**

Create the controller after the hero/status nodes exist. Call `update()` from `applyPresentation()` and `sync()` using the current requested ambience and the existing execution observation. Do not add polling or another mutation observer.

- [ ] **Step 5: Add CSS effective-mode selectors**

Implement:

```css
body.workshop-active[data-workshop-ambience-render="tokens"] .wk-immersive-hero::after,
body.workshop-active[data-workshop-ambience-render="suspended"] .wk-immersive-hero::after {
  background-image:none;
}
```

Keep gradients, controls, and layout intact.

- [ ] **Step 6: Verify static contracts GREEN**

Run:

```bash
node --check app/static/studio-shell.js
node --check app/static/workshop.js
node --test tests/workshop_ambience_policy.cjs tests/workshop_contracts.cjs
python -m unittest tests.test_workshop_ambience_policy tests.test_workshop_frontend -v
```

- [ ] **Step 7: Commit**

```bash
git add app/static/studio-shell.js app/static/workshop.js app/static/workshop-immersive-core.css tests/workshop_contracts.cjs tests/workshop_fixture.html docs/workshop/prototype.html
git commit -m "feat(create): apply effective local ambience policy"
```

### Task 4: Qualify browser behaviour and document limits

**Files:**
- Modify: `tests/workshop_browser_core.py`
- Modify: `tests/workshop_prototype.py`
- Modify: `docs/workshop/README.md`
- Modify: `docs/workshop/VALIDATION.md`
- Modify: `docs/workshop/ASSETS.md`

**Interfaces:**
- Consumes: DOM inspection seam `create.__workshop.ambienceDecision()`
- Produces: browser evidence for policy changes with zero submissions and zero network/media work

- [ ] **Step 1: Add failing browser assertions**

Cover:

- visible local poster;
- hidden → suspended → visible restoration;
- forced colours → token fallback;
- local poster unchanged across internet/backend combinations;
- asset missing → tokens;
- reduced motion/save data/user pause/active or uncertain execution keeps static poster but motion ineligible;
- prompt and file-input identity unchanged;
- no additional submission, HTTP, HTTPS, WebSocket, service-worker, or media request.

- [ ] **Step 2: Run browser tests RED where integration is incomplete**

Run:

```bash
python tests/workshop_browser.py --output .runtime/workshop-ambience
python tests/workshop_prototype.py --output .runtime/workshop-ambience-prototype
```

- [ ] **Step 3: Make the smallest integration corrections**

Change only presentation policy, status copy, or test fixtures required by failing evidence. Do not alter generation, readiness, source, or storage owners.

- [ ] **Step 4: Run complete scoped verification**

```bash
node --test tests/presentation_context.cjs tests/workshop_ambience_policy.cjs tests/workshop_contracts.cjs
python -m unittest tests.test_presentation_context tests.test_workshop_ambience_policy tests.test_workshop_frontend -v
python tests/workshop_browser.py --output .runtime/workshop-ambience
python tests/workshop_application.py --output .runtime/workshop-ambience-application
python tests/workshop_prototype.py --output .runtime/workshop-ambience-prototype
python scripts/validate-repo.py
```

Expected: all pass; browser reports zero extra submissions and no optional network/media work.

- [ ] **Step 5: Update evidence documentation**

Record exact commands, counts, head SHA, hosted run IDs, claim boundaries, and owner acceptance still required. State explicitly that no loop, GPU/media performance, or artistic acceptance is proved.

- [ ] **Step 6: Commit**

```bash
git add tests/workshop_browser_core.py tests/workshop_prototype.py docs/workshop/README.md docs/workshop/VALIDATION.md docs/workshop/ASSETS.md
git commit -m "test(workshop): qualify local ambience fallback policy"
```

### Task 5: Review and submit

**Files:**
- No product files unless review identifies a reproduced defect

**Interfaces:**
- Produces: review-ready stacked PR against `codex/workshop-context-guidance`

- [ ] **Step 1: Inspect the complete diff and stack relationship**

Confirm only policy, presentation integration, tests, and workshop documentation differ from the parent.

- [ ] **Step 2: Run fresh final-head verification**

Run all Task 4 commands on the exact final tree. Do not reuse earlier output.

- [ ] **Step 3: Update the PR body with exact evidence**

Include the final SHA, TDD sequence, browser counts, current-head workflows, authority limits, and deferred loop/remote-media work.

- [ ] **Step 4: Mark ready and trigger Codex review**

Resolve every reproduced finding through a failing regression before implementation. Keep the PR stacked; do not merge it automatically.
