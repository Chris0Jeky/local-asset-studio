---
name: studio-native-adapter
description: Build or change a native export path in Local Asset Studio that drives Krita, Blender or Godot (native exports, articulated props, Krita roundtrip, Godot sprite projects). Use for app/native_exports.py, app/articulated.py and the matching scripts; not for ComfyUI graphs or generation.
---

# Studio native adapter

## Use when / Do NOT use when

Use for `app/native_exports.py`, `app/articulated.py`, `app/production.py` native jobs, and
`scripts/krita_roundtrip.py`, `scripts/godot_asset_adapter.py`, `scripts/articulated_prop.py`,
`scripts/finish-generated-mesh.py`. Do NOT use for ComfyUI graphs, presets, backend switches, or the
offline game-asset planner (`docs/game-assets/AGENT-CONTRACT.md` owns that).

## Guardrails

- External programs come only from `config/local.json` (`blender`, `krita`, `godot`, `asset_python`).
  Never hardcode a path and never search `PATH` at runtime.
- Launch with validated argument arrays; never interpolate asset names, metadata or prompts into a
  shell string. Reject paths that escape the experiments root (`inside()`).
- A native job persists its plan before the program starts; recovery reads the exit log and refuses
  recorded failure evidence instead of re-running. Keep that shape.
- Package supplied media only. The adapter does not submit generation, accept art, or judge licences.
- Do not claim engine behaviour from a build log: for Godot, import the project and read the retained
  evidence; for Blender, inspect renders and the GLB part list; for Krita, reopen the KRA.

## Workflow

1. Name the artifact contract: inputs (asset ids or frames), outputs (BLEND, GLB, KRA, PNG, project
   folder), retained evidence files, and the failure evidence that must survive.
2. Write the plan/job record and its fingerprint first; make the executable step idempotent on retry.
3. Drive the program headless with a literal argv list and a bounded timeout; capture stdout, stderr
   and exit code into the job folder.
4. Verify the result structurally in Python (Pillow for images, zip/JSON for KRA and project files,
   GLB header and part names) and record the check next to the output.
5. Prove with the adapter's tests: `python -m unittest tests.test_native_exports tests.test_krita_roundtrip
   tests.test_godot_asset_adapter tests.test_articulated_prop tests.test_articulated_operation`.
   Add a focused fault test when you touched recovery or evidence retention.
6. Record the executed project id and inspection notes in `CURRENT_STATE.md` when a real run happened.

## Read first

`docs/NATIVE-EXPORTS.md`, `docs/KRITA-ROUNDTRIP.md`, `docs/ARTICULATED-PROP.md`, `integrations/godot/README.md`,
and the existing tests for the adapter you are changing.
