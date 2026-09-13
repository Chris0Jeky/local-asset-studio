# Reduced native schema contracts

`object-info.json` is hand-projected from **ComfyUI v0.35.0 source**, inspected
13 September 2026. It is not an installed-node capture and contains no model bytes,
local filenames, credentials or runtime observations. Tooltips/display-only metadata
are omitted. `FixtureSources` is synthetic and never executed.

| Entry | Source and reduction |
| --- | --- |
| SaveVideo | [`nodes_video.py`](https://github.com/Comfy-Org/ComfyUI/blob/v0.35.0/comfy_extras/nodes_video.py), `_save_video_codec_input` and `SaveVideo.define_schema`. Preserve format branches, codec sets, optional encoding, re-encode CRF bounds and optional hidden flat codec. |
| SaveGLB | [`nodes_save_3d.py`](https://github.com/Comfy-Org/ComfyUI/blob/v0.35.0/comfy_extras/nodes_save_3d.py), `SaveGLB.define_schema`. Reduce the long MultiType union to `MESH,FILE_3D_GLB`; the fixture intentionally does not enumerate other formats. |
| ImageCropToMask | [`nodes_images.py`](https://github.com/Comfy-Org/ComfyUI/blob/v0.35.0/comfy_extras/nodes_images.py), `ImageCropToMask.define_schema`; scalar bounds and COLOR/background metadata retained. |
| FixtureSources | Inert, zero-input typed outputs VIDEO/MESH/IMAGE/MASK/FILE_3D_GLB, solely to test target-node boundaries without importing Torch or asserting upstream inference. |

V3 serialization/expansion reference:
[`comfy_api/latest/_io.py`](https://github.com/Comfy-Org/ComfyUI/blob/v0.35.0/comfy_api/latest/_io.py).
Socket relation reference:
[`comfy_execution/validation.py`](https://github.com/Comfy-Org/ComfyUI/blob/v0.35.0/comfy_execution/validation.py).

The complete-catalog tests use actual tracked graph nodes, replacing only incoming
links with these explicit inert source types. They are compatibility regressions for
the three affected node boundaries, not full-graph runtime proof. A separate coverage
test deliberately supplies an incomplete schema and requires a failure result for
every catalog row. It must not be presented as every graph passing a native snapshot.

The full per-backend installed/custom-node corpus remains a #97 acceptance task.
See [the runbook](../../../docs/GRAPH-VALIDATION.md) for commands and limits.
