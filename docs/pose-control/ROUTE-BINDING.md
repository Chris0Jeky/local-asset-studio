# Pose source to native route binding

This contract turns one reviewed pose source into a deterministic, inspectable **binding proposal** for one
native route slot. It validates identities, image bytes, geometry provenance, renderer evidence, canvas
transforms and route semantics before any graph is prepared.

A successful binding is deliberately not executable. It does not call the Studio, Production, ComfyUI, a
model provider or a detector. It grants no allowance and does not qualify a route.

## The three route contracts

| Route ID | Accepted source | Native slot | Detector rule | Route-specific pins |
| --- | --- | --- | --- | --- |
| `klein-geometry` | opaque RGB precomputed-skeleton PNG tied to a pose artifact | `geometry-reference` | not applicable | renderer |
| `copy-pose` | RGB/RGBA PNG, JPEG or WebP donor | `pose-donor-image-2` | not applicable | LoRA |
| `sdxl-corrected-skeleton` | opaque RGB precomputed-skeleton PNG tied to a pose artifact | `control-image` | **bypass the detector** | ControlNet and renderer |

`studio_workflow/pose_route_contract.py` is the single source of truth for route ID, mechanism, source
representation, detector behavior, native slot, accepted formats, admitted backend IDs and route-specific
pins. Screening and binding consume projections of the same immutable contracts, so the same route identifier
cannot acquire two meanings again.

Every route also pins the model, encoder, VAE, graph, node set, runtime, reference transform and prompt
dialect. Route ID, mechanism, source kind, detector behavior and native slot are one indivisible contract. A
source cannot be relabelled into a different route. Backend IDs are checked against the canonical route
contract; a bounded typo such as `primry` is refused rather than preserved as valid-looking evidence.

A skeleton, RGB pose donor and depth map are distinct representations. This module accepts the first two
only. It never sends a rendered skeleton back through OpenPose or DWPose and never silently substitutes an
RGB donor for corrected geometry.

## Skeleton evidence

A precomputed-skeleton request binds:

- the validated `studio.pose-artifact/v1` identity;
- the exact opaque RGB PNG bytes, SHA-256, byte count, canvas and image mode;
- the renderer ID and renderer SHA-256, which must equal the route's renderer pin;
- the confidence threshold and exact ordered set of filtered joints;
- the deterministic source-to-target canvas transform.

The artifact must retain at least one drawable COCO-18 limb at the declared threshold. The PNG must be opaque
RGB, carry no transparency declaration and contain non-black pixels. This prevents hidden RGB values beneath
a zero-alpha plane from being accepted as visible guide evidence.

Two local renderers are recomputed byte for byte from the artifact: `studio.coco18-lines/v1`, the thin-line guide
the Klein skeleton recipe was proved with, and `studio.coco18-openpose-xinsir/v1`, the controlnet_aux OpenPose
drawing the SDXL route uses (next section). A renderer SHA-256 covers the Studio renderer implementation contract,
PNG encoder settings, Pillow version, and zlib compile/runtime versions; the OpenPose identity also carries the
pinned controlnet_aux reference. A Pillow or zlib change therefore produces an encoder-identity mismatch, not a
misleading tamper diagnosis. The exact renderer identity is retained in local-renderer binding diagnostics. Any
other installed auxiliary/native renderer can only be receipt-bound here: its bytes and opaque identity are
retained, but this helper does not claim that the renderer or route is qualified.

## OpenPose-convention renderer for SDXL (#445 item 3)

Xinsir's SDXL OpenPose ControlNet was trained on controlnet_aux-style drawings, and the thin-line guide is not one:
it colours each limb with its end joint at full intensity, in its own order, with strokes of `min(w, h) // 128`.
`studio_workflow/pose_raster.py` therefore has a second mode that reproduces `draw_bodypose` from the
comfyui_controlnet_aux copy installed beside ComfyUI (pyproject 1.1.5; the folder has no Git checkout of its own,
so the file is pinned instead: `src/custom_controlnet_aux/open_pose/util.py`, SHA-256 `763d2680…ac89a`), with
`xinsr_stick_scaling=True` as the Style + Pose graphs already run the preprocessor:

| Property | controlnet_aux 1.1.5, reproduced |
| --- | --- |
| Colour order | RGB; the same 18-entry list as the thin-line guide |
| Limb order and colour | its `limbSeq` (neck-right shoulder, neck-left shoulder, right arm, left arm, right leg, left leg, face); limb *i* takes colour *i* at 60 % |
| Limb shape | filled `cv2.ellipse2Poly` polygon between the two joints, half-width 4 × scale, reproduced exactly (OpenCV's float sine table, `cvRound`) |
| Stroke scaling | scale 1 below 500 px on the long side, else `min(2 + long_side // 1000, 7)`: 3 on 832×1216 and 1024×1536 |
| Joints | radius-4 filled dots at full colour, drawn after every limb, not scaled |
| Coordinates | the joint travels normalised (x / W) and back (x · W), then `int()`, exactly as controlnet_aux does |
| Canvas | the generation canvas; the editor draws at the recipe's width and height, so the transform is `identity` |

`scripts/pose_openpose_reference.py`, run with ComfyUI's embedded Python (cv2 5.0.0, numpy 2.5.2), executes the
installed `draw_bodypose` by source (torch is never imported) and compares. Measured on 22 September 2026: the
ellipse replica matched `cv2.ellipse2Poly` on 4,000 of 4,000 random cases; on four figures (standing and bent at
832×1216, standing at 1024×1536, bent at 448×448) 99.936–99.987 % of all pixels agree, every differing pixel lies on
a limb outline (Pillow's polygon fill rule against `cv2.fillConvexPoly`) and both drawings use the same colour set.
`tests/fixtures/pose-openpose/` keeps those aux renders; `tests/test_pose_raster.py` holds the agreement,
outline-only and colour-set checks, pins the thin-line guide's pixels and refuses unknown renderers.

## RGB donor evidence

Copy Pose binds the exact donor pixels directly to image slot 2. It accepts no pose artifact and no renderer
receipt. The declared format must match the actual decoded file, and the image must be one RGB/RGBA frame
within the 20 MiB and 16-megapixel limits. PNG, JPEG and WebP are covered. This donor contract deliberately
continues to permit alpha; the opaque requirement applies only to the precomputed skeleton representation.

All pose sources must have identity EXIF orientation. The binder fully decodes a PNG before reading EXIF, so
an `eXIf` chunk placed after `IDAT` cannot evade the check. Rotated or mirrored orientation metadata is
refused rather than silently normalizing bytes, dimensions or joint coordinates. An upstream intake may
materialize a visibly oriented derivative, but that derivative needs its own bytes, hash, canvas and transform.

## Transform policy

A request declares either:

- `identity`, requiring equal source and target canvases; or
- `contain-pad`, preserving aspect ratio, using deterministic integer dimensions and centring any odd padding
  remainder on the right or bottom.

The compiler recomputes the transform. Changed dimensions, scale or padding fail rather than being normalized
silently. Tests cover both aspect-ratio branches, including a tall source padded horizontally.

## Runnable synthetic example

The first command writes a deterministic synthetic pose artifact, its local-renderer PNG and a complete
request whose hashes and renderer identity match the current environment. It creates the destination
exclusively and submits no work.

```console
python scripts/pose_route_binding.py write-example .runtime/pose-route-binding-example

python scripts/pose_route_binding.py compile \
  .runtime/pose-route-binding-example/request.json \
  --source .runtime/pose-route-binding-example/source.png \
  --artifact .runtime/pose-route-binding-example/artifact.json \
  --out .runtime/pose-route-binding-example.binding.json

python scripts/pose_route_binding.py validate-binding \
  .runtime/pose-route-binding-example/request.json \
  .runtime/pose-route-binding-example.binding.json \
  --source .runtime/pose-route-binding-example/source.png \
  --artifact .runtime/pose-route-binding-example/artifact.json
```

For `copy-pose`, omit `--artifact`. Binding output creation is exclusive, so an existing binding is never
overwritten. Validation recompiles from the request, exact source bytes and optional artifact, then requires
full equality. `write-example` likewise refuses an existing output directory rather than changing its files.
Receipts and failures always report:

```json
{
  "ready_for_execution": false,
  "execution_authorized": false,
  "generation_submitted": false
}
```

The binding contains deterministic request and binding identities, route and source evidence, the exact native
slot, transform and diagnostics. `detector_invocations` remains zero, `graph_prepared` remains false and
`route_qualified` remains false.

## Boundary and remaining work for #445

This contract is still a structural preflight: `prepare` does not consume a binding JSON. The SDXL route
(`wai-skeleton`, 22 September 2026) reaches the same guarantees through the Studio's ordinary reference-slot path:
the pose editor draws the OpenPose-convention guide and attaches it to the preset's single `pose` slot, the graph
contains no detector (tests walk every node back from `SaveImage`), and the guide's `LoadImage` feeds only
`ControlNetApplyAdvanced.image`. Research renders and the exact settings are in
`experiments/curated/style-pose-matrix/2026-09-22-sdxl-skeleton/README.md`. Still open:

1. a Studio proving run of `wai-skeleton` (its catalog entry stays `verified: false` until then);
2. binding-JSON consumption by `prepare`, if a later route needs more than slot-level identity;
3. human visual review and the bounded comparison under #446.

No private pose or character bytes are committed by this contract. A valid hash proves content identity, not
rights clearance, geometry correctness, artistic acceptance or route promotion. HUMAN_TODO q-28 remains open.
