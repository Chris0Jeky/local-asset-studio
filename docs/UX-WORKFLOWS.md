# Workflow-first Studio UX

Implemented 12 September 2026 against main `2b911092e889687cd5d247da106f9de0c8348d99`.
Reconciled with merged PR #79 at `451a68199d855d8dd860c575ae7b115b7b9dcbf8`.
This is a working presentation-layer rework, not a new executor, GPU benchmark, or redesign mockup.

## The problem this changes

The existing Studio had working specialist tools but exposed their implementation boundaries to the
user. Creation opened a long recipe/parameter form, model-environment controls occupied every session,
outputs offered six overlapping transfer buttons, and Prompt Lab, scenes, voice and review each had a
separate navigation context. A user could create something without knowing what to do with it next.

The revised organizing unit is the **next decision**, with a retained source and an explicit destination:

```
Brief → choose recipe → attach sources → review settings → explicitly run
                                                       ↓
                      reuse ← choose / reject / repair ← inspect results
                        ↓
              image edit / motion / mesh / scene / native finish
```

Three concepts must not collapse into one green badge: execution completed, the human accepts the
artwork, and the intended use satisfies the model/source terms. None of the new navigation or transfer
controls makes those approvals or spends a generation allowance.

## Information architecture and feature scope

| Surface | Owns | Connections and limits |
| --- | --- | --- |
| Overview | Saved-work summary, recent assets, next decisions | Reads Workspace, Production and Jobs. Missing data is unknown, not zero. Links directly to review or an existing tool; never resumes execution. |
| Create | Task selection, exact recipe, sources, draft, readiness | Keeps the existing catalog/compiler and Generate handler. Parameters and adapter controls are progressively disclosed, not removed. |
| Asset library | Import, collections, selection, notes, review state, reuse | The existing asset ID stays the source of truth. Images can be copied into a named reference slot or prepared for another image-input recipe. No new asset database. |
| Runs & review | Existing planned comparisons, reservations, status, review and export | Plan comparison and Start remain separate. Uncertain work is inspected rather than repeated. Existing review desk keeps its blind-review behavior. |
| Prompt Lab | Creative intent, profile-specific text compilation | Explicit **text-only** preview in Create. Compiler fields do not establish executable graph bindings, transfer references, or select a matching model automatically. |
| Scene editor | Timing, visual/audio source selection, crop and render planning | Reuses the AV source picker. Bulk handoff accepts registered PNG/MP4/WAV, requires a visual, and checks 16-visual/32-audio bounds. Actual bytes and WAV suitability are still validated by the editor/server. |
| Voice takes | Existing local voice plan and recovery controls | Shared navigation, not a new voice engine. The voice tool remains authoritative for availability and execution. |
| Models & setup | Environment, model availability, installation, storage | Environment switching is explicit here, not an incidental effect of navigation or selecting a destination. |
| Workflow guide | Recipes, native-tool explanation and operating guidance | Native editing, character canon, masks and export semantics remain in their existing services and documentation. This change does not add a fake painting canvas or a second scene engine. |

At the source/destination boundary, **reference role** describes what to borrow, **lineage** records the
source asset, and **write scope** belongs to the actual native edit contract. A style reference is not a
pose controller. A whole-image instruction is not a guarantee of protected pixels. Recipe descriptions,
runtime blocks and missing required slots remain visible at the destination.

## Delivered interactions

### Start from an outcome

Overview offers five task families: start with an idea, change an image, refine details, make motion,
and explore a 3D draft. The chosen task filters the real catalog and selects a ranked starting recipe;
search, category, modality filters and the complete recipe list remain available. These are curated
presentation rules, not claims that a preferred model is universally best.

Create separates the brief, sources and run decision. The selected recipe, batch count, environment,
missing prerequisites and remaining references are shown beside the existing execution control.
The original resolved-recipe preview, source guidance, native graph downloads, named setups and
comparison planning remain available. A browser draft is not a pinned executable recipe.

### Continue with an output

The former six gallery transfer actions become one **Continue with this** action. Compare, recipe and
download remain independent. Asset detail uses the same handoff. The dialog shows the source, destination
family, compatible recipe, environment, and whether additional references are still needed.

**Prepare in Create** calls the existing asset-reference endpoint, keeps the original asset unchanged,
retains its ID in recipe lineage and attaches its local copy. It does not call Jobs, switch a model,
start a comparison or approve the art. Text-to-video-only recipes are not offered when handing off an
image. A multi-reference destination fills Image 1 and leaves remaining requirements explicit.
Unsaved asset notes, title, tags or review changes block handoff and scene/recipe navigation until saved.

### Bring something in without losing context

**Pull from library** searches retained images and lets the user choose the exact reference slot,
including first/last frames where supported. The chosen slot's semantic role and contribution notes
remain in place. The library also provides a drop zone reusing the existing sequential image importer;
the native file-input path stays keyboard-operable. Import limits and server validation are retained.
This is not a URL downloader, arbitrary filesystem picker, audio importer or implicit model upload.

### Resume safely

Drafts are versioned, size-bounded JSON, namespaced by the server's workspace identity and recipe ID.
They contain prompt/control values, batch, reference metadata, source IDs and pending-file markers.
They never serialize File bytes or executable code. A clean startup does not overwrite a saved draft
with recipe defaults. Restoration is explicit and rechecks reference availability; missing saved
inputs block generation instead of falling back to the recipe's example image.

Role references use the existing asynchronous hash/availability check. Single-input restoration has a
selection epoch so an old check cannot modify a subsequently selected recipe. Browser storage errors
leave creation usable; use Export draft or a named setup. Import draft validates version, dimensions,
reference metadata and primitive controls before applying them. Server-side recipe validation remains
authoritative. Exporting a draft does not bundle its image files or guarantee reproducibility elsewhere.

A storage event from another tab pauses autosave. The user can export their version, restore the saved
one, or explicitly keep this tab. This is a conflict warning, not transactional collaboration: browser
localStorage is not an atomic compare-and-swap database. Drafts are one current snapshot per recipe,
not revision history. They are not encrypted, and clearing site data removes them.

### Move compiled text between tools

Prompt Lab exposes **Review text in Create** after a usable compilation. A workspace-scoped,
time-limited sessionStorage message carries only text. Create shows a second explicit apply step.
Positive and negative text are previewed; negative text is applied only to a recipe that supports that
field, otherwise the user is told it was not applied. References and sampling controls are never
silently approximated. On storage failure, the existing compilation export remains available.

### Navigate without learning five applications

All five HTML entry pages share the same grouped sidebar, breadcrumb and tool finder. Ctrl/Cmd+K opens
the finder, Enter follows a filtered result, and Escape closes it. Main-workspace hashes support direct
links and browser Back/Forward; specialist tools remain independently served pages. Mobile navigation
collapses, source/dialog layouts reflow, and reduced-motion preferences are respected. Native dialogs
supply modal focus containment. This is not a claim of full WCAG conformance or a completed screen-reader
audit; those require the manual checks below.

## Implementation and migration boundaries

No frontend framework, dependency install, build step, remote font, remote image or telemetry was added.
`studio.css` scopes the new tokens/layouts under `.studio-shell`; the original tool styles remain.
Each HTML page loads the additive layer after the scripts it depends on.

| File | Responsibility |
| --- | --- |
| `app/static/studio-core.js` | Pure route, intent, summary, readiness, scene and draft/transfer policy. UMD export for dependency-free Node tests. |
| `app/static/studio-shell.js` | Shared sidebar, route event, mobile menu, finder, focus and environment-control placement. |
| `app/static/studio-workbench.js` | Main-page composition, source picker, handoffs, drafts and overview. All interception of legacy functions is localized here. |
| `app/static/studio-prompt-bridge.js` | Explicit Prompt Lab text transfer only. |
| `app/static/studio.css` | Shared visual tokens, states, responsive layouts and motion/focus rules. |

The workbench adapter deliberately retains existing DOM IDs and backend contracts. Its seams are
`showView`, preset rendering/selection, readiness, asset rendering/detail, job-card rendering,
role-file uploads, saved recipes and named-setup loading. This is a migration boundary, not the desired
permanent component model. When converting a legacy component, export its state/actions explicitly and
remove the corresponding adapter hook in the same change. Do not scatter additional global wrappers
across tools. In particular, never replace Production reservations or submission handling with UI state.

Overview fetches independent snapshots with `Promise.allSettled`; one failed service does not erase the
other results. It refreshes every 12 seconds only while visible. It retains at most six recent previews
and a short work queue. The existing library still renders its full returned inventory: large-workspace
pagination/virtualization is a separate measured task, not a solved scalability claim.

## Verification and local review

Required existing checks:

```sh
python -m unittest discover -s tests
python scripts/validate-repo.py
node tests/studio_ux.cjs
```

The normal unittest suite discovers `test_studio_ux.py`: policy execution, JS parsing, shared-shell
wiring and checks against remote assets/eval in the new layer. Node policy cases cover current catalog
intent coverage, no catalog mutation, separate review/status counts, all readiness blockers, scene
limits, bounded drafts, prototype/markup-shaped payloads and text-only transfer.

For real DOM interactions, in a development environment with Playwright and Chromium installed:

```sh
python tests/studio_browser_smoke.py --screenshots /tmp/studio-ux
```

Optional environment variables: `CHROMIUM_PATH` selects a system Chromium executable;
`STUDIO_UX_TEST_PORT` fixes the loopback fixture port (otherwise ephemeral). Do not install browser-test
packages into the managed ComfyUI environment. The suite serves actual frontend files and catalog
bindings with explicitly synthetic Workspace/Jobs/Production/API records. It blocks unexpected writes,
records every POST and verifies that navigation/handoffs do not submit generation or change setup.
The vendored model-viewer module is excluded from this no-GPU fixture; WebGL/3D rendering is not tested.
Screenshots show repository example art with synthetic task names/counts, not this workstation's live work.

Browser coverage includes desktop/mobile layouts, default overview, keyboard finder, reference slots,
lineage, consolidated gallery actions, explicit handoff, unsaved asset edits, reload-safe draft recovery,
invalid draft import, missing input reattachment, cross-tab conflict, unavailable data, runtime offline,
scene format gating, Prompt Lab transfer and startup with browser storage disabled.

Before treating this as a measured usability improvement, perform the same three tasks on the old and
new UI: imported image → prepared edit; rejected result → controlled next pass; selected visuals →
planned scene. Record completion time, wrong destinations, lost context, help requests and unintended
submissions. Targets are fewer navigation decisions and no unintended execution; no percentages or speed
improvements are asserted from fixture tests. Also check Windows Edge/Chrome at 100/200% zoom, keyboard-only
use and a screen reader, disconnected/reconnected ComfyUI, actual multi-reference uploads and a large
library. GPU execution, render quality, native editor integration and art approval remain separate gates.

## Next integrated slices, not parallel applications

1. **Common handoff contract:** move the current image-reference adapters to a typed, server-described
   capability contract with required/optional slots, supported media, transforms, retained provenance and
   dry-run validation. Do not rank an unsupported engine as ready from a UI label.
2. **Native edit review:** extend the existing character/native bridge (#71 and related work), exposing
   canon revision, source/mask freshness, context versus write scope, candidate comparison and import as a
   new layer. Reuse Production and the native application; do not start a second editor/queue.
3. **Project-aware workspace:** retain a collection/brief context across pages, then add exact output→stage
   links and restoration of the selected existing project. This pass does not invent a general project
   store or claim full project-context persistence across every specialist tool.
4. **Broader media transfer:** introduce real import/validation/conversion flows for audio/video before
   enabling arbitrary drag/drop into scenes. Make conversion costs and output registrations explicit.
5. **Measured density and accessibility:** virtualize large inventories, add empty/error/loading component
   contracts, and run assisted keyboard/screen-reader checks before declaring conformance or measured speed.

Reference patterns consulted: [WAI modal dialog guidance](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/)
and [MDN Web Storage usage](https://developer.mozilla.org/en-US/docs/Web/API/Web_Storage_API/Using_the_Web_Storage_API).
Human creative decisions in `HUMAN_TODO.md` remain untouched.
