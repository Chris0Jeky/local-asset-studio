# Procedural assets

The Studio's **More tools → Procedural assets** page connects the eight existing
Blender generators to saved Production plans and the Library. Open
`http://127.0.0.1:8191/procedural.html`, or search for “procedural”, “Blender”,
“pier” or “room” in **Jump to a tool**.

This is a procedural geometry workflow: dimensions and part counts produce a
model. It does not add a fluid, cloth or rigid-body simulation engine.

## Prepare, build, inspect

1. Name the asset and choose a generator. Numeric fields, defaults, limits and
   fit rules come directly from `scripts/procgen_generators.json`.
2. Choose **Check settings** to validate parameters and fit constraints. This
   works without Blender and creates no project or native process.
3. Choose whether to render a four-view inspection sheet and whether to check
   the full-detail GLB in Godot. **Prepare asset** saves the exact settings and
   source/runtime hashes. It creates a planned project; it does not build.
4. Choose **Open build plan**, then **Start build** in Comparisons. The normal
   Studio worker and lease admission own the execution. No ComfyUI prompt is
   submitted and no image-generation allowance is consumed.
5. Inspect the model, contact sheet and technical checks. The three GLB detail
   levels and optional sheet appear in the regular Library. **Download native
   source pack** includes the BLEND, GLBs, sheet when requested, recipe and
   factory report. Individual files and process diagnostics are under
   **Files & provenance**.

| Generator | What it builds |
| --- | --- |
| `room_kit` | Open-front bedroom with furniture |
| `prop` | Configurable stool, crate or potted plant |
| `shrine` | Steps, platform, torii gate and optional stone lanterns |
| `lighthouse_room` | Radial map room, stairs, table and shelves |
| `pier` | Harbour pier, piles, railings, lamps and bollards |
| `coastal_path` | Cliff, beach, path, fencing, grass and rocks |
| `tide_pools` | Rock shelf, pools, shore details and optional stairs |
| `market_street` | Houses, stalls, lanterns and optional stage |

The form exposes the existing generators' supported ranges; not every
in-range combination will pass geometry, export or native-engine checks.
Those checks remain part of an explicitly started build.

## Required tools

Configure absolute executable paths in `config/local.json`:

```json
{
  "blender": "C:/Apps/Blender-5.4/blender.exe",
  "node": "C:/Program Files/nodejs/node.exe",
  "godot": "C:/Apps/Godot/Godot.exe"
}
```

Merge these keys into your existing configuration. The paths above are
examples, not installed locations. **The procedural generators require
Blender 5.4** and use its typed Geometry Nodes modifier interface. The general
`config/example.json` currently names Blender 4.5.13; copying it does not
establish procedural compatibility. The shared `blender` setting also affects
other native workflows, so qualify those workflows when changing it.

Node must be explicitly configured; the Studio adapter never searches `PATH`.
Install the repository's pinned Khronos validator once from the repository root:

```sh
npm ci --prefix tools/gltf-validation --ignore-scripts
```

Godot is optional unless **Check import in configured Godot** is selected.
Discovery reports whether configured files and the pinned validator package
exist. It does **not** launch a version probe, prove application compatibility,
install tools, download models or start Blender. Preparing pins executable
file contents, generator/adapter source files and installed validator files;
Start rechecks those pins. An executable file alone is not native proof.

## What a result means

The adapter accepts only the existing factory's matching report, successful
Blender exit receipt, passing required gates and exact requested output set.
It verifies output hashes, self-contained GLB structure and the inspection
sheet's PNG format and dimensions before Library registration. The factory
retains dimensions, topology, UV, part, triangle-budget, LOD, naming, pivot,
overlap and Khronos checks. Optional triangle-budget detail fields from newer
reports are tolerated; they are not required to read older reports.

Without Godot, the build can complete while its report remains
**`incomplete`**: the GLBs and BLEND exist and requested checks passed, but
Godot import was not checked. With Godot selected, the existing factory checks
the full-detail GLB's import, collision shapes and bounding box. Passing those
checks is neither art acceptance nor evidence of every target engine or toon
shader. Library assets remain unreviewed.

Each native process has a bounded timeout: Blender 600 seconds, each Khronos
LOD check 60 seconds, and each Godot import/probe command 120 seconds. A stop
request before the attempt prevents execution; an already running native
command reaches its result or timeout. The UI's **Stop after current stage**
does not kill an independently installed application.

## Interrupted or failed builds

Each project owns one native attempt. Its plan, job identity and exclusive
attempt receipt are persisted before the factory starts. A native execution or
check failure keeps its files and logs; preparing a new plan is the explicit
way to retry that build.

A Library insertion or publication-receipt error instead leaves the project
**uncertain**, with every known registered asset ID retained. Registration is
checkpointed one output at a time. **Reconcile and resume** rechecks the retained
files and completes publication idempotently; it does not rebuild the asset or
duplicate a Library record. If the native receipt cannot be updated, the
separate job record retains the known IDs. A later failed file inspection keeps
those prior Library identities and refuses to publish the remaining outputs.

After a restart, **Reconcile and resume** inspects retained receipts and output
hashes. It never invokes the factory again if the attempt marker or output
directory exists. Complete retained output can finish Library publication
without rerunning Blender. Missing, changed or failed evidence stays uncertain
and is retained for inspection. A recorded failure is not overwritten by later
reconciliation errors. If a project was stopped before it acquired any native
attempt, resuming may start that first attempt.

If the preparation response is lost, inspect Comparisons before preparing
again. The page suppresses rapid duplicate clicks and makes no automatic
retry. An uncertain preparation can leave a planned project, but it cannot
start native work.

A failed **Check setup** request disables preparation until setup can be read
again. Your selected generator and typed settings survive that failure and the
next successful setup check.

## HTTP and CLI

The HTTP surface is regular-workspace only and uses the existing loopback Host
and same-origin mutation checks. Client-supplied executable paths, scripts,
output directories, unknown parameters and private-creation requests are
rejected.

| Request | Effect |
| --- | --- |
| `GET /api/procedural` | Read generator schemas and configured-file readiness |
| `POST /api/procedural/validate` | Validate typed intent; no project or native work |
| `POST /api/procedural` | Prepare and persist a Production project |
| `POST /api/production/{id}/start` | Explicitly queue the existing plan |
| `POST /api/production/{id}/resume` | Reconcile interrupted work under the one-attempt rule |
| `GET /api/production/{id}` | Inspect status, settings, check results and artifacts |
| `GET /api/production/{id}/files/{path}` | Read an allowlisted artifact; changed hashes are refused |

Example typed intent (numbers and booleans are JSON values, not strings):

```json
{
  "name": "Harbour crate",
  "generator": "prop",
  "params": {"kind": 1, "width": 0.7, "height": 0.6},
  "render": true,
  "verify_engine": false
}
```

Omitted parameters use the schema's defaults. `render` defaults to `true` and
`verify_engine` defaults to `false` in the Studio adapter. The existing
Every generator exposes `smooth` as an integer switch: `0` retains the original
flat style (the default); `1` interpolates normals across spheres and the sides
of cylinders and cones. Round caps, boxes and planar grids keep hard normals.
For the potted plant, use `kind=2, smooth=1` to soften foliage lighting without
raising `detail` or spending more triangles. Smooth normals do not change the
polygon silhouette; use `detail` when the outline itself needs more segments.
The schema supplies this setting and its help to both the app and `describe`.

`python scripts/procgen_factory.py describe` and factory CLI remain available;
direct CLI builds do not automatically create Studio plans or Library records.
Dedicated SDK/MCP wrappers are not part of this slice.

## Validation and remaining qualification

Software regressions use a real temporary filesystem, SQLite, Library and HTTP
server with an inert factory boundary. They cover preparation, pins, admission,
explicit execution, publication, restart, changed files, failure evidence and
no-repeat recovery. The Node contract driver exercises real page handlers and
Production rendering; its Python wrapper is part of the ordinary full suite.

```sh
python -m unittest discover -s tests -p 'test_procedural*.py'
python -m unittest discover -s tests -p 'test_production*.py'
python scripts/validate-repo.py
python tests/procedural_browser.py
```

The **UX use cases** workflow runs the Chromium driver and uploads
`.runtime/procedural-browser/` screenshots and its report. Its native files are
synthetic test fixtures, so those screenshots prove the page and Library
handoff only. The development container had no Blender, Godot or usable Chromium
runtime; browser qualification used hosted artifacts. Native Blender 5.4 runs
across all eight generators, Godot import evidence for those generated assets
and human visual review remain open under **#2026**.

Level assembly (`procgen_level.py`), labelled datasets (`procgen_dataset.py`)
and toon spring-bone proofs are separate existing tools and are not wired into
this page. They can build on this integration after their distinct artifact,
runtime and recovery contracts are specified. No existing creative choice in
`HUMAN_TODO.md` is resolved by these software checks.
