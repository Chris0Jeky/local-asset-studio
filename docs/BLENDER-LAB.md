# Blender lab: probe, manifest, parity

Observability tooling for agent-driven Blender work. It qualifies a Blender build by feature tests, never by version
number, before anything edits a scene.

- `scripts/blender_lab_bpy.py` runs inside `blender --background --factory-startup --disable-autoexec`. It never runs
  caller-supplied Python.
- `scripts/blender_lab.py` is the host CLI: it validates the executable path, starts it with a fixed argv and a timeout,
  and keeps argv, exit code, stdout and stderr in `<out>.log.json`.

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
