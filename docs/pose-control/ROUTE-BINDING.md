# Pose source to native route binding

This contract turns one reviewed pose source into a deterministic, inspectable **binding proposal** for one
native route slot. It validates identities, image bytes, geometry provenance, renderer evidence, canvas
transforms and route semantics before any graph is prepared.

A successful binding is deliberately not executable. It does not call the Studio, Production, ComfyUI, a
model provider or a detector. It grants no allowance and does not qualify a route.

## The three route contracts

| Route ID | Accepted source | Native slot | Detector rule | Route-specific pins |
| --- | --- | --- | --- | --- |
| `klein-geometry` | precomputed skeleton PNG tied to a pose artifact | `geometry-reference` | not applicable | renderer |
| `copy-pose` | RGB/RGBA PNG, JPEG or WebP donor | `pose-donor-image-2` | not applicable | LoRA |
| `sdxl-corrected-skeleton` | precomputed skeleton PNG tied to a pose artifact | `control-image` | **bypass the detector** | ControlNet and renderer |

Every route also pins the model, encoder, VAE, graph, node set, runtime, reference transform and prompt
dialect. Route ID, mechanism, source kind, detector behavior and native slot are one indivisible contract. A
source cannot be relabelled into a different route.

A skeleton, RGB pose donor and depth map are distinct representations. This module accepts the first two
only. It never sends a rendered skeleton back through OpenPose or DWPose and never silently substitutes an
RGB donor for corrected geometry.

## Skeleton evidence

A precomputed-skeleton request binds:

- the validated `studio.pose-artifact/v1` identity;
- the exact PNG bytes, SHA-256, byte count, canvas and image mode;
- the renderer ID and renderer SHA-256, which must equal the route's renderer pin;
- the confidence threshold and exact ordered set of filtered joints;
- the deterministic source-to-target canvas transform.

The artifact must retain at least one drawable COCO-18 limb at the declared threshold, and the PNG must contain
non-black pixels. The local preview renderer, `studio.coco18-lines/v1`, is recomputed byte for byte from the
artifact. An installed auxiliary/native renderer can only be receipt-bound here: its bytes and identity are
retained, but this helper does not claim that the renderer or route is qualified.

## RGB donor evidence

Copy Pose binds the exact donor pixels directly to image slot 2. It accepts no pose artifact and no renderer
receipt. The declared format must match the actual decoded file, and the image must be one RGB/RGBA frame
within the 20 MiB and 16-megapixel limits.

## Transform policy

A request declares either:

- `identity`, requiring equal source and target canvases; or
- `contain-pad`, preserving aspect ratio, using deterministic integer dimensions and centring any odd padding
  remainder on the right or bottom.

The compiler recomputes the transform. Changed dimensions, scale or padding fail rather than being normalized
silently.

## Headless commands

```console
python scripts/pose_route_binding.py compile request.json \
  --source corrected-pose.png \
  --artifact corrected-pose.json \
  --out binding.json

python scripts/pose_route_binding.py validate-binding request.json binding.json \
  --source corrected-pose.png \
  --artifact corrected-pose.json
```

For `copy-pose`, omit `--artifact`. Output creation is exclusive, so an existing binding is never overwritten.
Validation recompiles from the request, exact source bytes and optional artifact, then requires full equality.
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

This slice supplies the structural preflight and tamper-evident handoff. It does not complete route
qualification. The remaining work is to:

1. record the exact installed model, graph, node, runtime, renderer and adapter hashes on the target machine;
2. add the reviewed handoff from a valid binding into the existing prepare/Production path without allowing
   the graph to reinterpret its source type;
3. inspect the prepared graph and prove that SDXL consumes the precomputed guide without detector re-entry;
4. run a separately authorized exact-route smoke, retaining runtime, memory, failures and output evidence;
5. perform human visual review and the bounded comparison under #446.

No private pose or character bytes are committed by this contract. A valid hash proves content identity, not
rights clearance, geometry correctness, artistic acceptance or route promotion. HUMAN_TODO q-28 remains open.
