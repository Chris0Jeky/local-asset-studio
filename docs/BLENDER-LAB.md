# Blender lab: probe, manifest, parity

Observability tooling for agent-driven Blender work. It qualifies a Blender build by feature tests, never by version
number, before anything edits a scene.

- `scripts/blender_lab_bpy.py` runs inside `blender --background --factory-startup --disable-autoexec`. It never runs
  caller-supplied Python.
- `scripts/blender_lab.py` is the host CLI: it validates the executable path, starts it with a fixed argv and a timeout,
  and keeps argv, exit code, stdout and stderr in `<out>.log.json`.

An `OSError`, including an executable disappearing before launch, leaves a receipt with `returncode: "os-error"`,
elapsed time and an `error` containing the exception type and message (at most 1,000 characters). The CLI exits
with status 2 and does not retry. Existing receipts remain protected from replacement.

## Capability probe

```bash
python scripts/blender_lab.py probe --blender C:/AI/blender-4.5.13-windows-x64/blender.exe --out probe.json
```

It records version, build hash, Python, render engines (found by assigning each candidate), GPU backend, and Cycles
device visibility. It also runs feature tests for the action API, which keyframes a temporary object, Material
Lighting and NPR shader nodes, which are instantiated, the Blender Projects API, point-cloud and splat import
operators, and the full glTF exporter option list. A failing test is recorded, not raised.

Committed results are in `tests/fixtures/blender_lab/`. They were measured on 2 Nov 2026 on the RX 9070 XT:

| Capability | 4.5.13 LTS (`daeeeca98fb0`) | 5.4.0 alpha (`67c9bdddb88b`) |
| --- | --- | --- |
| Python | 3.11.15 | 3.13.13 |
| EEVEE engine id | `BLENDER_EEVEE_NEXT` | `BLENDER_EEVEE` |
| Legacy `Action.fcurves` | present | removed |
| Layered actions (slots, channelbags) | yes | yes |
| Material Lighting nodes | none | `ShaderNodeLightAccumulation`, `LightEvaluation`, `LightInfo`, `LightIterInternal*` |
| Blender Projects API | absent | `BlenderProject`, `bpy.ops.project` |
| Splat import | `ply_import` only | `ply_import`, `spz_import` |
| GPU backend in background | unavailable (no `gpu.init`) | `gpu.init()` succeeds: Vulkan, AMD driver 26.8.1 |
| Cycles HIP device | RX 9070 XT visible | RX 9070 XT visible |
| glTF exporter | 4.5.51, 108 options | 5.4.11, 115 options |

Live check: `LAS_BLENDER_LAB_EXE=<blender.exe> python -m unittest discover -s tests -p "test_blender_lab.py"`. Without
that variable, only the offline tests run against the fixtures.

## Scene manifest

```bash
python scripts/blender_lab.py make-fixture --blender <blender.exe> --out-dir <new-dir>
python scripts/blender_lab.py manifest --blender <blender.exe> --blend <new-dir>/lab-asset.blend --out manifest.json
```

The manifest is a task-oriented summary for planning and parity. It is not a dump of Blender. It covers objects
(parent, collections, world matrix and bounding box, visibility, material slots, modifiers, constraints, vertex-group
weight statistics, animation action and slot), meshes (counts, triangles, ordered geometry hash, UV maps,
per-slot face counts, shape keys with data hashes), materials (node-type histogram, Principled inputs, image
dependencies), images (file basename, size, packed or missing), armatures (bone graph with depth), actions
(slots and F-curves through channelbags, with the legacy API only where the build still has it), cameras and lights.

The source is opened with `use_scripts=False` and never saved. The host checks that the `.blend` bytes are unchanged.

`semantic_checksum` is SHA-256 over canonical JSON (sorted keys, floats rounded to 5 decimals, `-0.0` folded). It
excludes `schema`, `kind`, `blender`, `source` and `runtime`, so the same scene keeps its checksum across builds and
folders. Measured: the lab asset gives one checksum whether 4.5.13 or 5.4 alpha builds it, and whether either reads it.
It is not a hash of `.blend` bytes: those differ between builds and between saves.

Findings from building a deterministic asset:
- `primitive_uv_sphere_add` on 4.5.13 emits the same coordinates with faces in a different order on each run. The
  ordered geometry hash flags this correctly, so the lab asset builds its sphere from explicit data.
- `shape_key_add` creates keys at value 0.0 on 4.5 and 1.0 on 5.4 alpha. Set values explicitly.

## Asset Parity Sentinel v1

```bash
python scripts/blender_sentinel.py --blender <blender.exe> --blend <asset.blend> --out-dir <new-dir> [--seed-defect missing-texture|omitted-mesh|material-mismatch]
```

Process 1 opens the source without scripts and writes `source/manifest.json`. It then renders the evidence set and
writes `source/evidence.json` (camera spec, render settings, ID palette). It reloads the untouched file, applies the
optional seeded defect in memory, and exports `export.glb` with the existing LAS settings (`LAS_GLTF_SETTINGS`, the
same call as `articulated_prop.py`). Process 2 is a new Blender, factory-empty. It imports the GLB and renders the
same evidence with the source's `cameras.json`. The host then compares and writes `result.json`, which holds `pass`,
`structural_failures`, `format_losses`, `expected_exclusions`, `visual_warnings`, per-view metrics, export settings,
both semantic checksums, and every artifact with its SHA-256. The exit code is 0 for pass, 1 for fail and 2 for error.
The source SHA-256 must be unchanged at the end.

Evidence is 4 orthographic views (front, three-quarter, profile, back) × 4 passes at 256 px:
- `lit`: Cycles CPU, 16 samples, fixed seed, no denoise.
- `clay`: Workbench studio, single grey.
- `object_id`: Workbench flat, per-object colour from SHA-256 of the name.
- `material_id`: the same, per material.

The views use a fixed two-sun rig in a `_LAS_Evidence` collection. Authored lights are hidden, because the LAS export
excludes lights, and authored cameras are untouched. The silhouette is the `object_id` alpha, reported as IoU.

Each view and pass gets a ×4 diff PNG under `diff/`. It also gets the changed fraction (largest channel difference
over a per-pass pixel threshold) and changed-region boxes (8 px tiles, 8-connected). In ID passes, each box is
attributed to the object or material names present before and after.

Measured on 2 Nov 2026 with the generated lab asset, CPU only, about 7 s per run on 4.5 and 11 s on 5.4:

| Run | 4.5.13 | 5.4 alpha |
| --- | --- | --- |
| Unchanged control | pass. Noise: lit max \|Δ\| 1/255, ID passes exact, IoU 1.0 | pass. Noise: lit max \|Δ\| 13/255 on a few pixels, ID passes exact, IoU 1.0 |
| A missing texture | fail: texture lost, base colour unlinked, lit 5.6–10.1 % | same |
| B omitted mesh (`Body` hidden, dropped by `use_renderable`) | fail: mesh missing, 16 visual warnings attributed `Body` → none | same |
| C material mismatch (`Badge` gets `BodyTextured`) | fail: slot changed, material_id boxes attributed `BadgeGreen` → `BodyTextured` | same |
| D truncated animation (scene end halved, so `export_frame_range` clips the action) | fail: sampled frames `[1, 7, 12, 18, 24]` → `[1, 4, 6, 9, 12]`, no visual warning | same |
| E shape-key damage (deltas halved) | fail: `Squash` max delta 0.096 → 0.048, no visual warning | same |

Known gaps, tracked in #1918: `pose_samples` holds bone heads only, so a twist or a leaf-bone rotation is not caught
(the lab fixture's own sway is a twist). Shape-key checks hold extrema only, so damage to non-extreme vertex deltas
passes. A sentinel pass is evidence about what it measures, not acceptance.

D and E pass every render. Only the manifest catches them. It records `pose_samples` (world-space bone heads at 5
frames over each action's range; no tails, because glTF stores none) and split-invariant shape-key
`delta_max`/`delta_bbox` (they survive the vertex duplication of a roundtrip). The ortho scale comes from the bounding
sphere, so diagonal views are not cropped.

The importer adds a hidden `Icosphere` bone-shape object in a `glTF_not_exported` collection. The sentinel ignores it
because it is not visible. Thresholds are in `blender_sentinel.THRESHOLDS`. They come from this control, so a
smooth-shaded asset or one with custom normals needs its own control run before the thresholds can be trusted on it.

### Review corrections and offline evidence (2 Nov 2026)

The evidence renderer now sets the intended frame before evaluating mesh bounds. Source captures use
`frame_start`; roundtrip captures reuse the source camera specification and its frame. Render Region and Crop to
Render Region are disabled for every pass. These changes affect the temporary evidence scene, preserving authored
camera data and the original source bytes.

The host requires exactly one PNG for each of the four declared views and four passes in both evidence receipts.
It validates that complete set before joining receipt filenames to output paths, refusing missing, duplicate or
foreign names. It rechecks the source SHA-256 after both processes, image comparisons and artifact hashing,
immediately before writing `result.json`. A refusal retains partial artifacts and does not publish a passing receipt.

Verification against the reviewed `ac65a7e5c9c7de9925bd0a32c87207dacb92e727` base:

- Renderer fixtures reproduced evaluation at saved frame 37 instead of evidence frame 3, and inherited crop flags
  across all 16 passes. Both failed before the correction; supplied-camera and authored-data controls passed.
- Full host fixtures reproduced a passing receipt after a concurrent source save during the second worker or final
  artifact hashing, and a pass with zero image comparisons when both receipts listed no files. Those cases now refuse;
  a complete synthetic control still compares all 16 PNG pairs and preserves its source. Missing, duplicate and
  foreign names are also covered, with partial artifacts retained on refusal.
- With `LAS_BLENDER_LAB_EXE` unset, `python -m unittest discover -s tests -p "test_blender_*.py" -v` discovered 41 tests:
  38 passed and the three native Blender tests skipped. Renderer inputs use API-shaped scene fixtures; host checks
  use synthetic worker receipts and real PNG comparisons. No native Blender execution occurred in this review.

The earlier native measurements and the remaining rotation and shape-key limits above retain their original scope.

## Typed persistent worker

`scripts/blender_worker.py` keeps one background Blender alive and talks JSON lines over its stdin and stdout pipes.
Pipes rather than a socket mean no other process can connect. Replies are stdout lines prefixed `@@LAS@@ `, so
Blender's own output is ignored. The vocabulary is closed:

| Command | Effect |
| --- | --- |
| `ping` | pid, uptime, call count, datablock counts |
| `caps` | the capability probe, taken at start-up |
| `open {blend, allow_edit}` | opens a `.blend` without scripts and sets this session's editable objects |
| `describe_scene` | the scene manifest |
| `render_views {out_dir, size, samples, cameras}` | the sentinel evidence set; the scene is snapshotted and reloaded, so nothing leaks |
| `save_copy {path}` / `export {path}` | a `.blend` copy, or a GLB with the LAS settings |
| `apply_edit {object, op, value, expect_checksum}` | location, rotation, scale, render visibility, material slot or shape-key value; only on allow-listed objects, only when `expect_checksum` matches the current semantic checksum, values finite and bounded |
| `reimport_validate {out_dir}` (host side) | worker evidence and export, then the sentinel's reimport in a new process and its comparison |

Every write goes to a new path inside the worker root. No command evaluates caller-supplied code. A refused request
leaves the worker running. `fresh_call` is the one-process-per-call fallback.

```bash
python scripts/blender_worker.py bench --blender <blender.exe> --blend <asset.blend> --out-dir <new-dir> --calls 30
```

Measured on 2 Nov 2026 with the lab asset. The 30 calls were a mix of ping, describe, an edit and its revert, export,
128 px renders and save_copy:

| | 4.5.13 | 5.4 alpha |
| --- | --- | --- |
| Persistent: start-up, then 30 calls | 0.56 s + 0.96 s | 0.83 s + 2.28 s |
| Fresh process per call: 30 calls | 25.3 s | 42.6 s |
| Speed-up | 26× | 19× |
| Median `describe_scene`, persistent vs fresh | 3 ms vs 0.77 s | 3 ms vs 1.33 s |
| Median `render_views` (16 renders at 128 px), persistent vs fresh | 0.12 s vs 1.43 s | 0.51 s vs 1.82 s |
| State-leak checks | pass | pass |
| Worker RSS after 30 calls | 435 MB | 432 MB |

The state-leak checks are:
- the semantic checksum is unchanged across every render and export;
- the start checksum equals the end checksum after edit and revert pairs;
- the end checksum equals a fresh process reading the same file;
- the datablock counts are unchanged.

Fixed start-up cost dominates fresh calls; on 5.4 alpha it is about 1.3 s.

A rerun after the review fixes (state check now also covers frame, engine, camera, world, resolution and view
transform) ran while another lane held the GPU for a 27B VLM. It measured 4.07 s vs 32.0 s (7.9×) on 4.5, where one
cold first render took 2.5 s, and 3.02 s vs 54.0 s (17.9×) on 5.4. The leak checks passed on both. Read the speed-up as
8–26× depending on machine load.

## Which tool for what

Two stacks were built in parallel on 2 Nov 2026: this lab, and the offline DCC evidence work from #1911. They now
have one owner per seam and no parallel copies.

Status on 2 Nov 2026: the probe, manifest and `scene-v1` are on `main`. The sentinel, worker and MCP façade are in
open PRs #1916, #1924, #1931 and #1936.

| Seam | Canonical tool | Use it for |
| --- | --- | --- |
| Starting Blender | `blender_lab_bpy.py`, through the host runner `scripts/blender_lab.py` (fixed argv, log, timeout) or a `probe_intent` plan of the same argv | every native run, including the exact observation below |
| Capability qualification | `blender_lab.py probe` | feature tests per build, never version checks |
| Exact scene observation (`studio.dcc-scene/v1`) | `blender_lab.py scene-v1`, which runs the stdlib-only collector `scripts/blender_scene_probe.py` | strict same-build change detection: unchanged reruns, before/after an edit; float-exact, UV coordinates, weights, material links |
| Strict comparison and evidence receipts | `studio_workflow/dcc_evidence.py` (`compare_scenes`, `compare_bundles`, `probe_intent`) | exact equality and hardened PNG/receipt validation; no tolerance or GLB forgiveness |
| Planning summary and cross-build identity | `blender_lab.py manifest` (`semantic_checksum`) | what an agent may edit; the same scene on 4.5 and 5.4; worker preconditions |
| GLB export → reimport parity (plan Task 3) | `scripts/blender_sentinel.py` | target-aware structure (format losses, expected exclusions), tolerant renders with region boxes |
| Persistent session and agent façade | `scripts/blender_worker.py`, `scripts/blender_mcp.py` | many typed calls without per-call start-up |
| Offline synthetic corpus and research CLI | `studio_workflow/dcc_fixture.py`, `dcc_lab.py` | comparator protocol tests; no Blender |

There are two observation contracts on purpose. A quantised manifest cannot produce the exact observation without
weakening strict equality. Native qualification of `scene-v1` on the lab asset and the articulated chest found the
following:
- Unchanged reruns are exactly equal on both builds.
- The same file read by 4.5 and by 5.4 differs only in Principled BSDF input records, because 5.4 changed the socket
  list.
- The chest built on each build also differs in UV coordinates.
- The semantic checksum is identical in all of these cases.

So use the exact observation within one build, and the manifest across builds. Evidence:
`E:/local-asset-studio-labs/rnd-20261102/blender-worker/evidence/scene-v1-qualification-2026-11-02/`.
