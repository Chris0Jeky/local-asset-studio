# 07 · Constraints designs must respect

Each constraint names its source. A design that breaks one of these cannot be built without changing an owner decision.

## Runtime and delivery

| # | Constraint | Consequence for design | Source |
| --- | --- | --- | --- |
| K1 | **Loopback only.** Server binds 127.0.0.1:8191 and rejects foreign Host/Origin | No sharing, no remote access, no "open on phone" QR; mobile layouts are for narrow windows, not remote devices | `app/server.py` Handler guards |
| K2 | **Offline first.** No CDN, no web fonts, no remote icons, no analytics, no remote images by default | System font stack or a font file committed to the repo; icons as inline SVG or a local sprite | STACK-ADR; AMBIENCE |
| K3 | **Python-only runtime.** Normal launch runs Python; no npm, no Node, no build at runtime | Designs must be buildable as static HTML/CSS/JS | CLAUDE.md; STACK-ADR |
| K4 | **Vue island path (approved option B, #907).** TypeScript + Vue 3 + Vite on the maintainer/CI side only; compiled static output committed to `app/static/ui-dist/` with a manifest; first island = task guidance + recipe discovery; ≤ ~150 KiB gzip for the first island (proposed budget) | Deliver designs as components with explicit states and props so they map to islands; the legacy plain-JS pages coexist for a long time, so the design system must also be expressible as plain CSS variables | HUMAN_TODO `adaptive-frontend-build`; STACK-ADR |
| K5 | **No framework-owned drafts or jobs.** The existing workbench owns drafts, file inputs and the Generate handler; islands read snapshots and dispatch named actions | A redesign can move and restyle, but the brief textarea, file inputs and Generate button keep their identity (no clone/replace mid-edit) | ARCHITECTURE; workshop DESIGN |
| K6 | **Vendored model-viewer** for GLB | 3D previews use `<model-viewer>`; no WebGL scene engine for the workbench | `app/static/vendor/` |
| K7 | Optional remote decorative media was allowed by the owner (option B) **only from reviewed sources, off by default**; none is reviewed yet | Designs may show an "Environment" media slot; must look complete with a local still or nothing | HUMAN_TODO `adaptive-remote-media` |

## Execution truth

| # | Constraint | Consequence | Source |
| --- | --- | --- | --- |
| K8 | **Never auto-submit.** No generation on page load, recipe choice, task/skin/layout change, handoff or reconnect | Every Generate/Start/Run is a distinct, labelled press; "Prepare" and "Start" are separate for plans | CLAUDE.md pitfalls; UX-SPEC |
| K9 | **Uncertain jobs are never retried.** An outcome that could not be observed keeps its prompt ID and recipe; the only actions are observe again, stop tracking (with reason), abandon (with acknowledgement where applicable), put away | No "Retry" or "Run again" on an uncertain item; "Open as new draft" is allowed only as a clearly new job | `app/server.py` job actions; GPU-LEASE-FAILURE-SEMANTICS |
| K10 | **No cancel for a running ComfyUI job today** (plans have "Stop after current stage"; voice takes have Cancel) | Don't draw a Cancel button on a single running job unless marked "needs backend work" | job endpoints |
| K11 | **Long jobs on 16 GB VRAM.** 16 s to 14+ min; first load slower; heavy jobs refused when host commit > ~55 %; one environment at a time; switching refused while work is active; GPU lease can block submissions | Show estimates with their source, elapsed time, and queue position; design for waiting (the user leaves and comes back); never block the UI while a job runs | START-HERE; host-memory notes; backends |
| K12 | **One active environment** (Main library 8188 · HiDream 8192 · H3 8194 · Qwen 2.1 8196); switching is explicit and lives in Models & setup | A recipe needing another environment shows a blocker with an explicit Switch path, never a silent switch | `app/backends.py` |
| K13 | **Estimates are measured, not promised.** "Expected: 42 s" comes from local timing history; may be unavailable | Show "no timing yet" honestly; never a fake progress bar | `/api/estimate` |
| K14 | **Readiness can be stale or unknown.** Missing data is unknown, not zero or green | Distinct "unknown/needs a fresh check" state for readiness and stats | UX-SPEC §5; Overview "—" |

## Human decisions shown truthfully

| # | Constraint | Consequence | Source |
| --- | --- | --- | --- |
| K15 | **Executed ≠ accepted ≠ licensed.** A completed render is not art acceptance; a Keeper mark is the owner's selection, not licence clearance | No "approved", "✓ ready to ship" or star rating derived from completion; licence notes shown as facts per model ("FLUX non-commercial", "excludes UK use") | CLAUDE.md pitfalls; STATUS.md |
| K16 | **Agents never judge art or open explicit content.** The library contains agent-lab outputs, some adult | Designs and prototypes use placeholder art; review UI must never auto-classify or auto-accept | adult-content judging policy (memory); HUMAN_TODO |
| K17 | Review decisions save one asset at a time with a revision guard; the queue advances only after a confirmed save; conflicts are shown, never overwritten | Review mode shows "saving…" per decision and handles "changed elsewhere" | `workspace.js`, `/api/assets/update` |
| K18 | Recovery of unconfirmed writes: exact request retained, "Check status" before "Retry exact request"; newer typing is never sent with the old request | Keep an unconfirmed-save state in the component set (can be compact) | `workspace.js`, collection/prompt-project recovery |

## Scope

| # | Constraint | Source |
| --- | --- | --- |
| K19 | No change to backend contracts, APIs, job store or ComfyUI to make a design work; new server capability (e.g. job cancel, thumbnails for recipes) must be listed as a dependency | CLAUDE.md; STACK-ADR |
| K20 | Windows desktop browser (Chromium/Edge) is primary; 1440×900 is the reference laptop viewport; 1920×1080+ common; 390×844 must work | #539 acceptance |
| K21 | Keep "Show all controls" / Expert access: nothing is removed, only disclosed later | UX-SPEC §2 |
| K22 | Recipe thumbnails: example images exist for some recipes (`examples/`), others have none; some examples are local-only and not in Git | Card design needs a no-thumbnail variant | `scripts/validate-repo.py` LOCAL_MEDIA |
