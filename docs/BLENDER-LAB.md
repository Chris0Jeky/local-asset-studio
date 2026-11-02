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
