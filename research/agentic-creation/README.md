# Agentic creation: research → experiments → evidence

**Snapshot: 2 November 2026.** Additive to the [frontier workbench](../frontier/README.md), not a replacement for its model catalogue or LAS's runtime owners.

Read the [architecture, decisions and phased roadmap](../../docs/AGENTIC-CREATION.md), [implemented boundary and verification](../../docs/AGENTIC-EVIDENCE-VERIFICATION.md), and [next native implementation plan](../../docs/superpowers/plans/2026-11-02-dcc-native-parity.md). `programme.json` contains **10 falsifiable experiment cards and 24 ranked opportunities** across 2D, 3D, motion, procedural production, reconstruction and research. Scores are planning judgments, not measured probabilities.

## Working commands

Run from the LAS root, in the ordinary LAS Python environment. These commands do not start Blender, touch ComfyUI, download models, browse sources or reserve GPU resources.

```powershell
python -m studio_workflow.dcc_lab validate
python -m studio_workflow.dcc_lab seeded-study --out .runtime/dcc-seeded-study-001
python -m studio_workflow.dcc_lab plan-experiment scene-baseline --out .runtime/scene-baseline-intent.json
python -m studio_workflow.dcc_lab import-report "C:\private-research\report-export.json" --out "C:\private-research\archive-a"
python -m studio_workflow.dcc_lab verify-archive "C:\private-research\archive-a"
python -m studio_workflow.dcc_lab plan-probe --config config/local.json --source "C:\private-lab\copies\subject.blend" --out "C:\private-lab\runs\probe-001"
python -m studio_workflow.dcc_lab compare "C:\private-lab\before" "C:\private-lab\after" --required front profile --holdout profile --out "C:\private-lab\comparison-001.json"
```

Choose existing parent directories and **new** output names. The examples are paths to replace, not claims those files exist. `plan-probe` reads only the configured `blender` executable; it does not search PATH. It hashes the source, executable and fixed probe script, writes an intent, and stops. The resulting argv is a native adapter input, not admission or an execution receipt. A native runner must recheck pins, enforce the declared timeout/resource policy and retain process logs.

`compare` exits 0 only for `within_declared_tolerance`, 1 for different/incomplete/incomparable observations, and 2 for refused inputs. Even exit 0 never promotes a baseline or declares artistic acceptance, visual parity, native execution or distribution permission.

## Reproducible seeded study

`seeded-study` writes an owned synthetic control plus seven deliberate defects: changed pixels, same-count connectivity, weight drift, omitted part, missing hold-out, shifted camera contract and tampered file. It retains all bundles and comparison reports. These fixtures test evidence mechanics, not real Blender rendering or asset quality. The final `study.json` binds implementation hashes and the Python/Pillow versions. No GPU is used.

## Source preservation and confidentiality

The two supplied reports contain private project details. Their complete originals are intentionally **not committed to public LAS**. The importer creates `source.json` (exact bytes), `report.original.md` (exact report text), `report.md` (derived source-linked reading copy), `sources.json`, and `manifest.json` (hashes plus unresolved-reference inventory). The original research brief remains a separate source, not an invented web link. Each member is bounded to 1 MiB; larger future exports require a separately reviewed streaming intake change.

The private companion handoff and downloadable complete private archive preserve the project-specific material. Do not copy those archives into this public directory. Imported reports and linked webpages are data, not instructions; importing citations does not independently verify their claims. Hashes identify bytes, not licensing, accuracy or authorship. An intact self-contained archive is not an external authenticity signature.

## Evidence bundle contract

A directory contains `evidence.json`, a `scene.json` observation, and single-frame 8-bit RGB/RGBA PNGs. Paths are relative, canonical, non-symlink paths. Each artifact is bound by SHA-256. Scene JSON follows `studio.dcc-scene/v1`; the standalone probe writes that format. Images are limited to 1,048,576 pixels and 16 MiB each; at most 16 views are accepted.

```json
{
  "format": "studio.dcc-evidence/v1",
  "scope": "native_capture_unaccepted",
  "capture_contract": {
    "view_ids": ["front", "profile"],
    "resolution": [256, 256],
    "camera_rig_sha256": "<64 lowercase hex characters>",
    "render_settings": {
      "engine": "<observed engine>",
      "frame": 1,
      "settings_record": "<fixed settings, color management, lights and seed>"
    }
  },
  "scene": {"path": "scene.json", "sha256": "<actual file SHA-256>"},
  "views": {
    "front": {"path": "views/front.png", "sha256": "<actual file SHA-256>"},
    "profile": {"path": "views/profile.png", "sha256": "<actual file SHA-256>"}
  }
}
```

This is illustrative JSON, not a runnable fixture: placeholders must be replaced with actual hashes. Retain the full camera/light/pose record whose digest becomes `camera_rig_sha256`. A declaration cannot prove a renderer followed it. The next native adapter must generate these records from actual settings, not agent-authored recollection.

The caller independently specifies required and hold-out views. A missing hold-out is incomplete; differing camera/render contracts are incomparable. Comparison does not resize, realign or normalize a candidate. Exact RGBA comparison includes RGB beneath transparent alpha; it is a conservative byte-level diagnostic, not a perceptual aesthetic score.

## Current implementation limits

Read-only probe source exists and has offline API-fixture tests. **It has not been run on the owner's Blender/Windows/AMD stack by this implementation pass.** It observes base mesh connectivity/positions, UVs, weights, shape keys, rest bones, material socket defaults, links/ramps, image presence and layered/legacy actions. It intentionally does not call mutating animation `ensure` APIs.

It does not evaluate modifiers or posed geometry, fully serialize constraints/nested shader graphs, hash texture pixels, generate controlled renders, map GLB identities, or inspect motion. `complete: true` means the declared observation scope finished, not that every Blender feature was serialized. Exact object/library names are used; intentional GLB renaming or triangulation needs a target-aware mapping, not a blanket ignore rule. The native parity renderer, native resource bridge, private artifact registration and live app/MCP routes are **planned, not implemented**.

## Tests

```powershell
python -m unittest discover -s tests -p test_research_intake.py -v
python -m unittest discover -s tests -p test_dcc_evidence.py -v
python -m unittest discover -s tests -p test_blender_scene_probe.py -v
python -m unittest discover -s tests -p test_dcc_lab.py -v
python -m unittest discover -s tests -p test_dcc_fixture.py -v
python scripts/validate-repo.py
```

No new runtime dependency is introduced: offline image checks use existing Pillow. Blender's probe uses only its bundled Python and `bpy`. There is no import of Torch/ROCm or installation into either environment.
