# Fixed-canvas depth-guide erasure

Refs #427, #407, #445. Implements the deterministic preprocessing operation motivated by the measured lower-depth-map erasure in #431. It does not reproduce the neural experiment or automatically locate ankles, shoes or unwanted anatomy.

## Operation

Input is an **already computed** 8-bit L or RGB PNG, its expected SHA-256, and explicit pixel-edge rectangles `[left, top, right, bottom]`. Output is a new PNG of exactly the same dimensions and mode. Selected pixels become black; every stored pixel outside the rectangle union remains equal. Right and bottom edges are exclusive. Overlap is permitted and counted once; duplicate and empty rectangles are refused. An empty operation preserves the original bytes exactly.

This is not RGB cropping, rescaling, depth re-estimation, a foreground detector or a final-image repair mask. Black is an intentional removal of visual conditioning for this candidate route, not a universally neutral metric-depth value. An unwanted donor heel may be erased for an experiment; an intended foot orientation still needs appropriate replacement structure. No route compatibility or art acceptance follows from a successful erasure.

## Local command

Create a new `rectangles.json`, for example `[[0,200,256,256]]` for the lower band of an explicitly inspected **256 x 256** map. Do not reuse these example coordinates on another canvas without reviewing them.

Read the hash of the exact source bytes:

```console
python -c "import hashlib; from pathlib import Path; print(hashlib.sha256(Path('depth.png').read_bytes()).hexdigest())"
```

Replace the marker below with that hash. Choose a new output path:

```console
python scripts/depth_erasure.py depth.png --expected-sha256 REPLACE_WITH_SOURCE_HASH --rectangles rectangles.json --out depth-erased.png
```

The CLI writes only the named new image and prints a JSON receipt on stdout. Retain that receipt through the calling workflow/agent. It includes source/output SHA-256, operation version, mode/dimensions, canonical rectangles, union pixel count, actually changed pixel count and outside-region equality. It explicitly declares no generation, native qualification or neutral-depth claim. Receipt stdout is not a durable Workspace transaction; later staging owns durable evidence storage.

A changed source hash, existing output (including the source itself), unsupported image, invalid JSON or invalid rectangle fails with JSON on stderr and exit 2. Validation completes before output creation. An OS failure during a write can leave an incomplete new file; inspect it and choose a new path rather than overwrite or assume success.

## Bounds and data preservation

Input is at most 32 MiB; dimensions at most 8,192 each and at most 16,777,216 pixels; at most 64 rectangles. The rectangles JSON uses the bounded duplicate-key/nonfinite-rejecting reader introduced with pose artifacts. Coordinates must be integers, not booleans or rounded floats.

Only single-frame PNG in `L` or `RGB` mode is accepted. Palette, alpha, tRNS transparency, 16-bit/integer/float maps, other formats and animation are refused without conversion. The operation preserves decoded pixel samples, not ancillary PNG metadata or embedded colour-management semantics. Nonempty operations deliberately clear ancillary metadata; empty operations retain all source bytes. Re-encoded PNG hashes are environment-dependent, so retain Pillow/version and output hash for exact reproducibility.

The pure helper `studio_workflow.depth_erasure.erase_png(data, expected_sha256, rectangles)` returns `(output_bytes, receipt)` and never writes files. It computes changed pixels and checks the outside-region difference before returning. It cannot verify that the input represents meaningful depth or that the selected regions are appropriate.

## Verification and remaining work

```console
python -m unittest discover -s tests -p "test_depth_erasure.py" -v
python -m py_compile studio_workflow/depth_erasure.py scripts/depth_erasure.py
```

The tests decode real temporary PNGs and check every pixel of grayscale/RGB examples, overlapping and boundary rectangles, malformed input, unsupported modes/transparency/animation, source-hash mismatch, deterministic output, no-op bytes and CLI no-overwrite behavior. They contain no user artwork and make no network or GPU call.

Still required: #427's inspected UI control, exact post-depth/native-route binding under #445, staging through the existing Workspace/reference services, and bounded owner-reviewed comparison under #446. Do not automatically feed the erased map back through Depth Anything or a pose detector. Do not change HUMAN_TODO q-28 based on these software tests.
