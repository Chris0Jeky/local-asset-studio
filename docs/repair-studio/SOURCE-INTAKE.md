# Bounded repair-source intake

First implementation under #244 / #243; architecture is in PR #264. This slice creates a real, verifiable normalized source packet without touching the Studio server, existing extraction behavior, native applications or generation allowance.

## Run

Use Python 3.12+ and the repository's existing Pillow dependency. No ComfyUI is required.

```console
python scripts/repair_source.py capture --image original.png --out experiments/runs/repair-source-001
python scripts/repair_source.py verify experiments/runs/repair-source-001
```

Choose a **new directory**. Capture retains `source.png` byte-for-byte, writes `normalized.png`, and publishes `receipt.json` last. A failed or interrupted packet is retained without a trusted completion marker; inspect it, do not reuse or delete it as an automatic retry. Normalization is CPU-only; it does not repair anatomy, detect subjects, remove backgrounds or grant any art/usage approval.

`normalize_repair_png(encoded: bytes) -> (normalized_bytes, normalization_record)` is the pure API. `capture(Path, Path)` performs explicit bounded file IO; `verify(Path)` reconstructs expected pixels from the retained source and checks the entire evidence record. `load_packet(Path)` returns the same captured normalized bytes and receipt to downstream tools, avoiding a second path read after validation. All CLI success output is JSON; input/IO failure returns JSON with exit 2. Invalid CLI syntax retains argparse's exit-2 usage error.

## Supported contract

The initial input envelope is a **single-frame 8-bit RGB/RGBA PNG**, at most 20 MiB encoded and 24 million decoded pixels. A PNG wire scan checks chunk framing, checksums, sample depth, bounded counts, image-data ordering, and an aggregate 1 MiB metadata budget before Pillow decoding. Compressed zTXt/iTXt/iCCP payloads are bounded before expansion. This is a qualified intake subset, not a claim of implementing every PNG conformance rule.

All eight EXIF orientation/mirroring values are applied once to a new derivative. Geometry in the receipt distinguishes original encoded and normalized dimensions. PNG EXIF may occur after image data, so orientation is read after complete bounded decode. Invalid orientation is rejected rather than guessed.

The derivative is RGBA8. RGB+tRNS colour keys become real alpha; partial alpha and RGB hidden under zero alpha are retained. Transparency **does not** become permission to repair the background. No image is stretched, resized or cropped during normalization.

Text and EXIF are removed from the derivative and retained in the original. The receipt lists removed chunk types, not private text values. Supported `iCCP`, `gAMA`, `cHRM` and `sRGB` chunks are retained verbatim. No colour conversion, profile certification or untagged-to-sRGB inference occurs. The ICC payload hash identifies content; even a retained profile is not declared valid. Current neural adapters may still refuse transparent or colour-ambiguous input, as they should until their own support is implemented.

Animation, HDR colour declarations, grayscale/palette and 16-bit samples require separate explicit routes; no silent frame flattening, palette expansion or high-bit-depth loss. Unknown critical chunks and trailing/truncated data are refused. A 16-bit true-colour file is rejected before Pillow can reduce its samples to 8 bits.

## Source and publication integrity

Hash, byte count and decoded geometry all come from one bounded capture, not hash-then-reopen of a mutable path. This establishes a coherent retained capture, not an atomic snapshot of a hostile writer's in-place changes. The original path is never modified or hard-linked into the packet.

Packet creation atomically claims a new directory with `mkdir`, writes exclusive files and fsyncs their contents, then hard-links the complete pending receipt to its final name. Concurrent callers cannot replace a winning packet. Hard-link support is required (for example local NTFS); unsupported publication retains the partial packet and fails without an overwrite/rename fallback. This is not a universal power-loss or hostile-filesystem guarantee.

Verification rejects missing/partial markers, symlinked members, changed hashes, extra receipt fields, type confusion and mismatched pixels/colour metadata. It **reconstructs** the normalized pixels from `source.png`; editing a normalized image and merely updating its hash is insufficient. Lossless encoder byte differences across Pillow versions are permitted when the recorded digest, pixel content and metadata remain consistent. Complete malicious replacement of all sources and records is outside the single-user integrity model; hashes do not authenticate owner decisions.

## Integration decision

Keep normalization in a small `scripts/repair_source.py` module instead of extending the already mixed-purpose `character_media.py` with more state or changing its legacy contracts. The module has no database or queue and creates only explicit offline packets. The next panel slice consumes these verified bytes and supplies a legacy manifest for the existing extractor as well as instance-aware records. Actual mask scaling and protected candidate application remain #245; guided browser intake remains #251.

## Reconciliation and evidence

Inspected main `29135ff38647f88a06df1e382f8bab2da9054dc5`. PR #264 was open; no competing #244 implementation/comments were found. #240 campaign budgets and #226 native revision guards were already on main and are not repeated. Existing bounded reference capture/publication and source-aware recipe advice are separate owners. HUMAN_TODO's earlier choices remain answered and unchanged.

Local Python 3.13.5 / Pillow 12.3.0: **29 tests passed**. Tests first exercised an absent interface, then actual media logic; an adversarial receipt-type test reproduced Python's `False == 0` equality problem before canonical JSON comparison fixed it. Coverage includes all EXIF transforms with independent pixel orders, tRNS/hidden alpha, preserved colour, metadata bombs, non-RGB/16-bit rejection before decoder entry, corrupt/trailing PNGs, real capture replacement, concurrent packet creation, failed publication, rehashed wrong pixels and CLI subprocesses from another directory.

```console
python -m unittest discover -s tests -p "test_repair_source.py" -v
python -m unittest discover -s tests
python scripts/validate-repo.py
```

Full source checkout was unavailable in this container because GitHub DNS resolution failed. Local tests cover the new standalone implementation, not a claimed local full-repository run. The PR's hosted check runs the full suite and validator; the new path-filtered intake lane runs focused contracts on Linux and Windows. Their actual head-specific results belong to the PR record, not an inferred pass here.

#244 stays open: panel proposals/previews, guided UI, owner-reviewed real-sheet acceptance and broader formats are not delivered by normalization alone. No private artwork was published or inferred upon.

## Primary references

Pillow PNG transparency/EXIF/animation behavior: https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#png

Pillow orientation transforms: https://pillow.readthedocs.io/en/stable/reference/ImageOps.html#PIL.ImageOps.exif_transpose

These were reviewed 14 September 2026. Tests establish the selected implementation's behavior; documentation is not a substitute for actual pixel comparisons.
