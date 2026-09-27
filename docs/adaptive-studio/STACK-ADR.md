# ADR: frontend modernization without replacing the local runtime

**Decision status: proposed; owner accepted the maintainer build step (option B, 23 Sep 2026). The spike ran on 27 Sep 2026 (#907); see [Spike results](#spike-results-27-sep-2026-907). A default change remains a separate owner decision.**

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

