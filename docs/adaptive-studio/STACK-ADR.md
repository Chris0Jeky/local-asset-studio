# ADR: frontend modernization without replacing the local runtime

**Decision status: candidate default, not approved for a default switch.** The owner accepted the maintainer build step (option B, 23 Sep 2026) and answered **candidate default** after seeing the island on 27 Sep 2026 (`adaptive-island-trial`). The historical [spike results](#spike-results-27-sep-2026-907) remain below; the [current decision plan](#candidate-default-plan-1207) prepares the separate owner decision and implementation PR.

## Context

The inspected application uses Python's HTTP server and plain JavaScript under `app/static/`; normal launch has no package-manager or frontend build prerequisite. The shell dynamically loads specialist modules. The workbench and specialist tools expose useful existing contracts, but stateful DOM manipulation, asynchronous loading and cross-module focus ownership make broad UI changes expensive. A framework alone cannot repair those boundaries.

The desired task-aware workspaces, reusable source cards, stable guidance and presentation variants justify evaluating component tooling. They do not justify replacing Python, ComfyUI, the Workspace or the job coordinator.

## Options

| Option | What improves | Main cost / risk | Role here |
| --- | --- | --- | --- |
| A. ES modules, JSDoc/checkJs, native components | Smaller change, explicit types at seams, no mandatory runtime framework | Declarative state, lifecycle and complex widgets remain largely hand-built | Mandatory contract cleanup and viable fallback |
| B. Vue 3 + TypeScript + Vite islands | Declarative task panels, scoped component ownership, readable templates and component tests | Build discipline, generated assets and a temporary bridge need maintenance | Preferred experiment after A |
| C. Lit + TypeScript | Standards-based reusable elements and scoped composition, gradual adoption | Existing document selectors/focus behavior require care around component boundaries; still needs state ownership work | Alternative if tiny independent widgets dominate |
| D. React + TypeScript + Vite | Incremental roots and a broad component ecosystem; suitable when a specific graph/editor package is decisive | Different rendering model and the same bridge/build costs; switching alone gains no workflow semantics | Valid alternative, not chosen without a concrete component advantage |

The official Vue and React documentation both support incremental embedding; Lit is designed around web components; TypeScript supports checking JavaScript. These are documented possibilities, not comparative performance measurements. See [SOURCES.md](SOURCES.md), S02-S06.

## Recommended path

**Typed boundary first, Vue island second, wider ownership only after evidence.** Use TypeScript for new projection contracts and isolated components; use JSDoc/checkJs selectively around stable legacy seams. Do not mechanically convert dense existing files in a single PR. Keep pure projection and action descriptors framework-independent.

The first useful island is **task guidance plus recipe discovery summaries**, not the prompt editor or Generate handler. It reads an immutable snapshot and invokes existing reveal/navigation adapters. It cannot own the production draft. The second candidate is a source-board display, with edit commands still delegated until source/lineage parity is proved.

Only one modern framework is admitted. Do not add Vue, React and Lit to compare their appearance in production. The spike may have disposable alternatives, but its merge selects one or retains A.

## Runtime and build topology

```text
Maintainer / CI: frontend source -> pinned Node/toolchain + lockfile -> build manifest + static JS/CSS
Runtime PC:     Python server -> checked, packaged static output -> browser
                Existing API and ComfyUI endpoints stay unchanged
```

A developer build may use Vite, but the end user's normal launch must not run npm, fetch a CDN or need the internet. Initial development should use build-watch output served from the existing Python origin. Do not weaken Host/Origin protections to make a Vite proxy convenient. A later HMR development mode must be explicit, loopback-only and absent from the runtime configuration.

Proposed source location: `frontend/`; compiled payload: `app/static/ui-dist/`; generated manifest maps source entries to hashed output. Vite documents this backend-integration pattern (S03). Choose exact stable package and Node versions during the spike, record them in the lockfile/toolchain file and test Windows. This document intentionally does not pretend a currently untested version combination is pinned or qualified.

For this repository's clone-and-launch workflow, the initial proposal is to commit the small generated JS/CSS/manifest with source in the same PR, with a reproducibility check and a strict size budget. Exclude source maps and large media; retain the prior complete bundle until replacement is verified. If that creates unacceptable churn, use an explicitly installed signed/hashed release bundle instead. That alternative must preserve an offline first launch and cannot be silently selected by a runtime downloader.

## Component and dependency policy

Use semantic HTML, CSS variables/layers and narrow components before adding a full visual framework. Keep the skin token layer independent of Vue components. Start with native dialogs and existing keyboard semantics; introduce a headless widget dependency only for a named accessibility/interaction gap with tests. A node-editor library is a separate evaluation, not a prerequisite for task guidance. Do not put the workbench behind WebGL, a scene engine or a video canvas.

Use CSS/WAAPI for small transitions. GSAP or another timeline library becomes a measured exception for a genuinely complex showcase, not the default dependency for every panel. Avoid SSR frameworks, a new Node application server, Electron/Tauri repackaging and a UI-wide global store in this phase. A Vue store may own presentation state later, but it must not become a competing draft/job authority.

## Spike acceptance and rejection gates

Use one real task-guidance island against the existing browser fixture and the same captured recipe/draft/reference state. Measure both baseline and candidate on the same machine, build and data.

Accept only if the island preserves input identity and existing generation/recovery behavior; supports unmount/remount without duplicate listeners or polls; works with all network blocked except the local Studio; supports keyboard, 200% zoom, reduced motion and storage denial; and adds a bounded reproducible payload. Proposed budget: no more than 150 KiB gzip initial new JS plus CSS for the first island, measured and recorded, not asserted here.

Reject or revise if the implementation needs two-way DOM mirroring, mutation observers on the whole document, origin-check exceptions, runtime npm/CDN access, duplicated command ownership or a wholesale rewrite before it provides value. Feature-flag rollback must restore the previous presentation without losing the current draft or replaying a write.

## Migration sequence

1. Document and test the read-only snapshot plus semantic action adapter; no renderer change.
2. Introduce type-checking/build scaffolding with the first useful island, not an empty framework shell.
3. Trial guidance/discovery behind an explicit local flag; retain existing controls.
4. Qualify source-board and recipe-difference interactions before adopting their renderers.
5. Take over one complete editor surface only after parity tests and owner acceptance; remove old renderer/listeners in that same slice.
6. Consolidate guide/disclosure logic and retire the bridge when no legacy consumer needs it.

Each step has independent rollback. A default change is a separate decision from whether the code compiles. Nothing in this ADR authorizes changes to installed ComfyUI packages or claims a rendering-quality improvement.

## Spike results (27 Sep 2026, #907)

Measured on the owner's Windows 11 PC (Radeon host, Python 3.14.3, headless Chromium via Playwright 1.57), with ComfyUI unreachable from the test instance. One seed of evidence per claim; nothing here is a user study.

**What shipped.** One Vue island, `frontend/src/TaskGuide.vue`, mounted as a new `#uiIsland` section in the Create view's `guidance` grid area. It renders the workshop's existing projection (primary intent, up to two secondary intents, source line, "Why this?") and a recipe-discovery summary of `presets/recipes.json` from `GET /api/recipes`, with stills from the existing `/static/bundle-showcase.js` module and a no-preview variant. Buttons dispatch the workshop's existing `createActionAdapter` intents (reveal/focus only) or open the existing bundle explorer for inspection. It owns no draft, submits nothing, uploads nothing and adds no timer, poll or MutationObserver. Typed contracts with runtime validation live in `frontend/src/contracts.ts`; a snapshot claiming `authorizesSubmission` or carrying commands is rejected.

**Legacy seams added** (the whole bridge): `workshop.js` announces a frozen `{view, recipe}` once per context stamp (`studio:presentation` on `#createView`) and exposes `presentationSnapshot()`; `bundle-explorer.js` exposes `StudioBundleExplorer.open(id)` (opens and inspects, never applies); `studio-shell.js` loads `/static/ui-dist/island.{css,js}` only when the URL carries `?ui=island`. Rollback is removing the flag: the island unmounts, `body[data-ui-island]` goes away and the legacy aside returns.

**Enable it:** `http://127.0.0.1:8191/?ui=island#create`. No restart or npm is needed; the Python server reads static files per request.

| Measure | Result |
| --- | --- |
| Node / npm | Node 24.13.1 (`frontend/.nvmrc`, `engines >=24.13.1 <25`, `engine-strict`), npm 11.8.0 locally |
| Packages (exact, lockfile v3, 73 installed) | vue 3.5.43 · vite 8.3.1 (Rolldown) · @vitejs/plugin-vue 6.0.9 · typescript 6.0.3 · vue-tsc 3.3.11 · vitest 5.0.2 · happy-dom 20.14.5 |
| TypeScript choice | 6.0.3, not 7.0.2: 7 is the native port and vue-tsc needs the JavaScript language-service API |
| Build output | `island.js` 70,678 B (sha256 `564b73ef3c0c8c6c…`), `island.css` 2,987 B (`cda5d623c99479f8…`); lockfile sha256 `7e99d247bfd0222e…`; full hashes in `app/static/ui-dist/manifest.json` |
| Compressed payload | 27,441 B + 1,035 B = **28,476 B gzip (27.8 KiB)**, 19 % of the 150 KiB budget; the build fails above budget |
| Reproducibility (Windows) | Two consecutive builds and a clean `npm ci` rebuild were byte-identical to the committed output. CI (`ui-island.yml`, Ubuntu) rebuilds and requires `git diff --exit-code` on `ui-dist` |
| Build cost | `npm ci` 7 s warm / about 1 min cold, 99 MB `node_modules` (maintainer only, gitignored); `vite build` 0.6 s |
| Island tests | Vitest 26/26 in 2.9 s, one forked worker (MACHINE.md OOM guard); browser script `tests/ui_island_browser.py` 26/26 checks |
| Offline start | See below: zero requests outside the local origin, zero blocked, zero page errors, both flag states |
| Timing, 6 runs per arm | Workshop ready p50 256 ms (flag off) vs 281 ms (flag on); island cards rendered p50 303 ms; one long task in one run of each arm |

**Offline-start proof.** `app/server.py` has no `--port` flag and its Host/Origin guard accepts only `127.0.0.1:8191`/`localhost:8191`, while the owner's live Studio held 8191. The proof therefore ran the unchanged module's own `create_server(repo_root, port=18191)` from the worktree with a copied `config/local.json` whose `comfy_url` points at a closed port, observed with a request-recording wrapper around `parse_request` (no handler change), and Chromium's `--host-resolver-rules=MAP localhost:8191 127.0.0.1:18191`, so the page ran on the real `localhost:8191` origin with the real Host header. A Playwright route aborted every request that was not a GET/HEAD to that origin. A discriminator request (`/static/ui-dist/island.js` is 404 on main) confirmed the mapping before any page load. Results: server start 0.39 s with Python only; flag off 57 requests, flag on 65 (adds `island.css`, `island.js`, `/api/recipes`, `/static/bundle-showcase.js`); every recorded request reached the proof server and all were GET; `island.js` served as `application/javascript` (Windows registry via `mimetypes`; Linux 3.12 serves `text/javascript`, both valid module types). The live Studio and ComfyUI were not stopped or contacted by the page.

**Findings that shaped the topology.**

- The static handler serves only `.html`, `.js` and `.css`, so a runtime lookup of a JSON manifest or hashed chunk names would need a server change. The spike emits stable names (`island.js`, `island.css`), one module with no chunks or maps, and keeps `manifest.json` as a build/CI record that the server deliberately does not serve. The build refuses any other file type in `ui-dist`.
- `core.autocrlf=true` on this PC; `.gitattributes` forces LF for `*.ts`, `*.vue`, `*.mjs`, `.nvmrc`, `.npmrc` and `app/static/ui-dist/**` so Windows and Linux builds hash identically.
- The legacy guidance aside is `display:none` in Focus and Studio layouts, so the `guidance` grid row was empty there. The island fills it in every layout and hides the legacy aside (Immersive only) while `body[data-ui-island="active"]` is set.

**Against the acceptance gates.** Met: unmount/remount without duplicate listeners (unit + browser), prompt field identity and value kept across unmount/remount, network blocked except the local Studio, keyboard (native buttons, arrow/Home/End between recipe cards), OS reduced motion, storage denial (tab-only notice), error containment (a render or setup failure unmounts only the island and restores legacy guidance), bounded reproducible payload. Not triggered: two-way DOM mirroring, document-wide observers, origin exceptions, runtime npm/CDN, duplicated command ownership. **Not measured:** 200 % zoom, IME composition, the A7 paired comparison on the frozen fixture journey, a real generation or recovery run with the island mounted, and owner use.

**Recommendation: accept option B for the guidance island trial and keep it behind `?ui=island`, off by default.** The island met every gate the spike could exercise at under a fifth of its budget with two small, read-only legacy seams. Do not change the default or start the source-board island (A3) until the owner has used the trial and the 200 % zoom and A7 paired-fixture checks have run.

## Candidate-default plan (#1207)

Prepared 25 October 2026 against production source `1aa48338f0f2aedd545bad6fcec1c4865a862849`.
The owner's 27 September answer promotes the two panels to a **candidate**, not to a default.
This section supersedes the spike's recommendation to wait for owner trial feedback; it does
not supersede the historical measurements or authorize a switch. Refs #907.

### Keep Vue or port to plain JavaScript?

**Recommendation: retain the existing Vue island for these two panels.** It already has typed,
runtime-validated snapshots, isolated lifecycle/failure handling, a read-only action bridge,
component tests and committed offline assets. A port would have to recreate and prove those
contracts, disclosure preferences, recipe projection and keyboard handling in a second renderer.
It could avoid the Vue payload and the maintainer build, but there is no measured plain-JS port
whose size or load advantage can be claimed. The normal Create arm below is the existing page
without either candidate panel, not a plain-JS implementation of them.

| Choice | Concrete cost | Decision consequence |
| --- | --- | --- |
| Keep Vue | Two additional static bundle files; maintain source/lockfile/build parity | Smallest default-switch diff; retain the existing bridge and tests |
| Port both panels | New DOM/lifecycle/disclosure code and replacement parity tests; final payload unknown | Choose only if the owner rejects the measured payload or maintainer build cost; replace Vue completely for this surface |

For either choice, Python's runtime and APIs stay unchanged. The shipped page reads local assets;
normal launch requires no Node, npm, CDN, internet connection or change to installed ComfyUI.
The build remains a maintainer/CI operation. No second framework or production draft authority is needed.

### Current page-cost measurement

`python tests/ui_island_browser.py --output .runtime/issue-1207/island-verified` runs the same real frontend
against synthetic HTTP data, with all non-fixture-origin requests blocked. Six alternating runs
per arm use new Chromium contexts (Playwright 1.62.0, Python 3.14.3 on Windows) at 1440 x 900, empty browser storage and disabled browser cache
(Playwright routing); the OS file cache is not cold. Arms are normal `/#create`, opt-in
`/?ui=island#create`, and a candidate `/#create` whose **test-only response override** removes
only the loader's opt-in guard. The production file is never rewritten. The script refuses a
changed/missing guard instead of silently measuring a different implementation.

`load` is Navigation Timing's `loadEventEnd`; `workshop` is elapsed navigation time when the
browser driver first observes the workshop and selected recipe; `panels` additionally waits for
a rendered authored-setup card. These are separate milestones, not interchangeable definitions
of readiness. The 300 ms request-settling wait is excluded from these timings.

Measured 2026-10-25T20:03:18.604138+00:00; milliseconds, medians of six runs per arm.

| Arm | load p50 | workshop observed p50 | panels observed p50 |
| --- | ---: | ---: | ---: |
| normal | 624.5 | 652.3 | absent |
| opt-in | 658.4 | 708.1 | 743.3 |
| candidate-default | 592.2 | 624.0 | 685.6 |

The opt-in arm is the direct HTTP comparison for the island's page cost: **+33.9 ms** at the
load milestone in this sample. The candidate was 32.3 ms below normal, but its shell response
was fulfilled by Playwright instead of one fixture HTTP response. That confound and ordinary
run/order variation prevent treating the candidate row as a speedup or a precise prediction of
production-default latency. The final sample was taken after the journey browser runs finished;
the broad unit suite was still running. These are local synthetic loads, not a user study, network benchmark, generation-speed claim or
proof that Vue is faster. Six runs cannot establish a general latency ceiling. Raw samples and
payload hashes are retained in the ignored output directory's `result.json`; rerun on the target
host before the later implementation PR if the source or host changes.

Current committed payload, measured from the actual files rather than the September table:

| Additional bundle | Raw bytes served | gzip level 9, Python measurement | SHA-256 |
| --- | ---: | ---: | --- |
| `island.js` | 70,944 | 27,602 | `88975d7a64f9a4851771d69c695cb2696e489520d8f8f9410fa44123801e9487` |
| `island.css` | 2,987 | 1,037 | `cda5d623c99479f8af9133184733ed8a5147ca03fde52fb4fd185e3e4dbf56e0` |
| Total | **73,931 (72.2 KiB)** | **28,639 (28.0 KiB)** | |

The build manifest records 28,552 B gzip using its pinned Node/zlib toolchain; compressor versions
can differ, and the static tests verify the actual bundle hashes against that manifest. Both are
below 153,600 B (150 KiB). Python's static server serves uncompressed bytes: gzip is a payload
budget comparison, **not** the actual loopback transfer size. Recipe JSON, showcase-module and
local preview requests are additional to this bundle total; previews depend on the selected
recipe and viewport. The fixture does not model the owner's complete model/media inventory.
Normal mode still requests neither island bundle file and creates no island root.

### Fixture journeys and zoom

The normal baseline and candidate default at 100% each passed **25/25 journeys**. The final
candidate at 200%-equivalent reflow also passed **25/25**. All three had **zero generation
submissions and zero page exceptions**. The updated candidate runner additionally requires
mounted panels on each journey ending on the main page. The panel/browser script passed
**61 checks**.

```console
python tests/studio_use_cases.py --out .runtime/issue-1207/baseline-journeys.json --screenshots .runtime/issue-1207/baseline-shots
python tests/studio_use_cases.py --island-default --out .runtime/issue-1207/candidate-final.json --screenshots .runtime/issue-1207/candidate-final-shots
python tests/studio_use_cases.py --island-default --zoom 200 --out .runtime/issue-1207/candidate-zoom-verified.json --screenshots .runtime/issue-1207/candidate-zoom-verified-shots
python -m unittest discover -s tests -p "test_ui_island_static.py"
python -m unittest discover -s tests -p "test_use_case_matrix.py"
python scripts/validate-repo.py
```

Static serving/budget checks passed **5/5**, runner/scoring checks **68/68**; validation passed
93 preset graphs/bindings and 187 pinned assets. An additional full offline unit-suite attempt
was stopped after about 35 minutes on the shared host without a final verdict; it is **not pass
evidence**, and the full pre-publication gate remains for the coordinator. The new flagless-mount regression was run
before removing the opt-in guard from the fixture's response: the normal control passed and
the candidate check failed with `Timeout 5000ms exceeded` waiting for the island primary action.
It passed after the fixture override; no production code was changed to make that test pass.

The candidate switch is available only as `--island-default` in the fixture runner; combining it
with `--base-url` is refused before browser startup. No production preference, query string or
persisted default is changed. Each journey ending on the main page additionally requires the
island primary action and authored-setup cards to be mounted, so an inert override cannot
masquerade as coverage. Normal controls, typed wording, source handoffs, comparisons and recovery
remain the existing journey drivers' success conditions; the script never presses Generate.

The 200% test halves the CSS viewport and doubles pixel density (1536 x 1060 becomes 768 x 530
for journeys; 1440 x 900 becomes 720 x 450 for panel checks). This exercises equivalent reflow
and readable controls, **not Chromium's native toolbar zoom or an assistive-technology audit**.
The panel checks cover Focus, Studio and Immersive: no internal horizontal overflow, keyboard
opening of Why this?, and collapse/reopen of authored setups. The first journey now opens the
collapsed navigation through its menu button at that narrower viewport. The comparison driver
also uses Tab to leave the prompt before looking for the secondary run tools that the short
viewport deliberately hides while typing.

The existing fixture logs asset-family reads with `studio=None` and occasional connection aborts
when a context closes; these also occurred in the normal baseline. They are not production
recovery evidence. Journey success, page exceptions and generation-request counts are recorded
separately; existing measured dead ends remain in the matrices rather than being erased.

### What a future switch changes for someone who never opted in

- Ordinary Create gains **Next step**, its primary reveal/focus action, source/evidence wording
  and a closed **Why this?** disclosure. Existing secondary guidance links remain as currently
  rendered; the later PR must explicitly account for them rather than claim there is only one button.
- **Authored setups** shows up to four ideas for the selected recipe, or clearly labelled
  fallback recipe ideas when no authored setup matches. Inspect opens the existing bundle
  explorer; it neither applies a setup nor submits a generation. Run evidence, art acceptance
  and licence clearance remain distinct.
- Focus and Studio gain content in the guidance slot that was previously empty. In Immersive,
  the island hides the retained legacy guidance aside while active. This changes page height,
  scrolling and keyboard tab order, and adds collapsible-discovery preferences in browser storage;
  denied storage keeps the choice in the tab only.
- The existing main-page loader runs even when the initial route is Make or Assets. Simply
  removing its guard therefore adds bundle/data work to those visits too, although the panel
  lives in Create. This measured candidate simulates that exact behavior; a later Create-only
  lazy-load design would need its own proof.
- Failure or unmount restores legacy guidance without replacing prompt controls or replaying a
  write. A deliberate opt-out is needed: removing `?ui=island` would no longer disable a default.
  No generation, upload, retry, runtime switch, remote-media permission or model licence changes.

### Separate decision and implementation PR

The owner chooses **retain as opt-in**, **make the Vue panels default**, or **port the panels**,
using the costs and coverage above. The checked `adaptive-island-trial` answer in HUMAN_TODO.md
stays checked; the default-switch decision stays open. No unanswered preference is inferred here.

If the owner selects the Vue default, the next PR should:

1. Record that answer, change the loader default and provide a documented explicit opt-out
   (proposed `?ui=legacy`), preserving `?ui=island` links. Keep unmount/failure rollback intact.
2. Replace the trial heading with normal Task guide wording. Retain the same immutable snapshot,
   one primary next step, existing action adapter and inspect-only authored setups.
3. Rebuild and commit source plus bundle/manifest together with the pinned maintainer toolchain;
   update flag/default static tests and run component/build reproducibility checks.
4. Run normal-default and explicit-opt-out browser arms, all fixture journeys at 100% and 200%
   equivalent, offline containment, storage denial, keyboard, reduced motion and rollback.
   Confirm no automatic generation and no prompt identity/value loss.
5. Carry forward the limits: native browser zoom, IME, assistive technology, actual generation and
   live recovery with the panels are not proved by these inert fixtures. Owner workflow/art
   acceptance remains separate. Any port must meet the same gates before replacing Vue.

This completes the decision preparation requested by #1207. Activation and the owner's final
choice belong to the separate PR; the production default remains opt-in.
