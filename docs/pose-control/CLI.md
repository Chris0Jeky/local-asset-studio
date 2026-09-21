# Corrected pose artifacts: local commands

Implements the P0 software seam from #443. No running Studio, ComfyUI, detector, model or network is needed. Python 3.12+ and the repository's existing Pillow dependency are sufficient. These commands do not register assets, apply a setup, allocate generation, approve geometry or generate artwork.

## Try the synthetic fixture

Choose new output paths. From the repository root:

```console
python scripts/pose_artifact.py import examples/pose-control/coco18-synthetic.json --width 256 --height 256 --coordinate-space pixels --out pose.json
python scripts/pose_artifact.py inspect pose.json
python scripts/pose_artifact.py render pose.json --out pose.png
python scripts/pose_artifact.py export-json pose.json --out openpose.json
```

`inspect` prints the artifact, its ID, missing/filtered/manual joint lists and unreviewed status. Copy its `id` into the expected-ID argument below; the marker is an explicit user replacement, not a real hash:

```console
python scripts/pose_artifact.py revise pose.json --expected-id REPLACE_WITH_INSPECTED_ID --edits examples/pose-control/correction.json --out pose-v2.json
python scripts/pose_artifact.py render pose-v2.json --out pose-v2.png
```

The example changes the right wrist and marks the left ear unknown. Parent files remain unchanged. Every successful write reports an output SHA-256; failures return exit code 2 and JSON on stderr. Existing output files, including a source supplied as output, are refused. A write interrupted by an OS/storage failure may leave an incomplete new output: retain/inspect it and choose a new path rather than assume success or overwrite it.

## Input and coordinate contract

Input is one OpenPose-style JSON object with `people` and optional `version`, `canvas_width`, `canvas_height`. Each selected body has exactly 54 `pose_keypoints_2d` values (18 x/y/confidence triples in COCO-18 order). More than one person requires an explicit zero-based `--person-index`. This is not a batch-frame importer.

Declare `--coordinate-space pixels` or `normalized`; automatic guessing is prohibited. Internal coordinates are continuous pixel-edge units, 0..width and 0..height inclusive, y down. Normalized coordinates multiply by the declared canvas. Boundary points are clamped only when rasterized, not silently changed in stored geometry. Native coordinate conventions must still be qualified at route binding.

A positive-confidence point at x=0/y=0 is real; zero confidence becomes a missing joint. A correction is a JSON object mapping exact joint names to `[x,y]` or `null`; manual coordinates are pixel-edge units regardless of original input scale. Duplicate keys, invalid numbers, bounds violations and unknown joints refuse the complete batch. An edit to identical already-manual coordinates is a no-op. Replacing an estimated point with manual coordinates changes its provenance even when the position is identical.

Bounds: JSON 1 MiB, 32 nesting levels, 8,192 visited values/keys, 16,384-character strings, integer literals up to 20 characters; 1..32 people; dimensions 1..8,192 and at most 16,777,216 pixels. Nonempty hand/face/3D channels and other body layouts are refused instead of dropped. Missing coordinates are not reconstructed. The artifact hashes the exact imported keypoint JSON bytes, not the original pose image, and does not re-observe external source files on validation.

## Export limitations

The native JSON export is deliberately lossy with respect to provenance: missing or filtered points become zero triples; manually authored points carry confidence 1 only as a presence sentinel. Keep the original artifact for source identity and manual/estimated distinctions. Do not interpret the interchange sentinel as detector certainty or owner approval.

`--threshold` (0..1, default 0.3) filters estimated points at export without deleting them from the artifact. Manual joints are retained. A blank guide is valid for inspection but is not automatically acceptable for generation.

PNG renderer `studio.coco18-lines/v1` draws an RGB skeleton on black, using versioned line/joint choices. PNG bytes are stable within the same Pillow/renderer environment; pin that environment for external reproducibility. It is an experimental visual guide, not a pixel-equivalent copy of the native auxiliary renderer and not certified for Xinsir/ControlNet. #445 owns exact native-renderer and precomputed-guide routing. Do not feed a rendered skeleton through a pose detector. The user can inspect/export the PNG now; native graph staging is a later explicit operation.

## Verification

```console
python -m unittest discover -s tests -p "test_pose_artifact.py" -v
python -m py_compile studio_workflow/pose_artifact.py studio_workflow/pose_raster.py scripts/pose_artifact.py
```

Tests use synthetic keypoints and actual temporary JSON/PNG files, not user artwork or model responses. Browser editing, shared Workspace persistence, rich hand/camera/contact geometry and artistic qualification remain #444/#407/#445/#446.
