# ADR: frontend modernization without replacing the local runtime

**Decision status: proposed, gated by a spike and owner acceptance of a maintainer build step.**

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
