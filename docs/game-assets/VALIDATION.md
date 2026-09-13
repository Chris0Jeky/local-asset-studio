# Validation record

## Native graph validation follow-up — 13 September 2026

`game_asset_pipeline.graph_check` now checks string union sockets, explicitly
selected V3 dynamic branches and declared socketless scalar widgets. The read-only
`validate-live.py` delegates to it and defaults to every catalog entry, with explicit
collection/backend/preset filters and offline saved-schema mode. See
[Graph validation](../GRAPH-VALIDATION.md) for the contracts, source-derived fixture
scope, per-preset reports, verification commands and remaining installed-schema proof.
No native inference or new creative acceptance is established by this follow-up.

## Initial offline delivery — 11 September 2026

11 September 2026. Chat execution environment: Python 3.13.5, Pillow 12.3.0, Linux. This is not the user's Windows/Radeon workstation.

## Performed

- 48 new unit tests passed with no skips in the local partial checkout.
- All eight routes produced hash-checked plans; every referenced capability resolves in the 23-entry capability catalog.
- One/two/three-reference Qwen graph static topology and regression checks passed. Model, encoder, VAE and sampler nodes remain unchanged from the pinned source recipe.
- Planner tests include changed references/artifacts, duplicate/foreign receipts, prerequisite enforcement, traversal/symlink escape, unsafe numeric input, no-overwrite behavior and synthetic node-schema checks.
- Media tests include RGBA pixel round-trip, padding/extrusion, anchors, variable timing, duplicate/empty frames, size/hash mismatches, ORA mimetype order/compression, topmost/hidden-layer compositing, XML escaping and unsupported blend rejection.
- The procedural demo command created frames, an atlas/manifest, an ORA, a brief and a plan. Atlas image visually inspected. It is deliberately a small geometric QA fixture, not generative art or an accepted character animation.
- JSON schema validation of the generated brief and strict UTF-8/JSON parsing completed locally.

## Not performed

- New GPU inference or a live Comfy `/object_info` validation for the derived reference graphs.
- Live Krita opening/saving, native layer editing or animation export.
- Blender model generation, rigging, rendering or retargeting in this chat environment.
- A real Godot/Unity/Unreal import/playback test or Khronos validator invocation.
- Installation/audit of the linked community MCP bridges or the research model environments.
- Full original-repository tests in the local partial checkout. The PR's normal CI can supply that evidence; do not infer it from these 48 tests.

The dedicated GitHub workflow runs the new tests with optional Pillow on Python 3.12 and exercises the demo plus ready-task output. The original repository workflow remains unchanged. Any remote results are reported in the PR after observation rather than guessed here.
