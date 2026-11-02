# Render critic: complete, loss-aware reference evidence

## What this changes

The existing critic remains the detector and optional model client. Reference mode now requires equal, unique view-label sets, observes decoded **RGBA**, and refuses image representations that would silently lose precision or temporal information. It retains actual candidate/reference dimensions and the raw pixel policy in each successful result. This is decoded-value comparison, **not** ICC-managed/linear-light equivalence, identity judgement or artistic acceptance.

Unsupported evidence returns `error`, `evidence_complete: false`, `changed: true`, and `model: null`. The conservative boolean protects older consumers; the existing scorer excludes error rows from all confusion counts. No vision-model fallback is allowed to convert missing evidence into a judgement. `pixel_diff()` raises `ReferenceEvidenceError` for these cases. Ordinary filesystem/decode failures still raise and are recorded by the existing evaluator.

Supported sample modes: `1`, `L`, `LA`, `P`, `RGB`, `RGBA`; one frame only. PNG sample depth is read from IHDR because RGB16/RGBA16 can be exposed as 8-bit modes by Pillow. Originals must remain unchanged; any deliberate 8-bit conversion is a separate copied artifact. The module does not convert high-bit source art in place. Hidden RGB is retained in the raw comparison even at zero alpha, so this is a conservative data-level check, not only a display-equivalence test.

A `view_front.png` label remains `front`. Other names retain their full stem: `view_front_001.png` and `view_front_002.png` are distinct frames, not duplicate front views. Reference order may differ; matches are by exact unique label.

## Why this precedes a noise-threshold change

Issue #1970 reports 26 critic-only pixels on an unchanged native chest. That is **one reported observation**, not a calibrated distribution. A raised global threshold could remove that alarm and also conceal a small real defect. This change therefore **does not raise `DIFF_MIN_PX=20` or `DIFF_LEVEL=8`**, change sentinel policy, invoke Blender, or claim the native chest issue is resolved.

`check(..., diff_only=True)` without references now refuses the request before HTTP. `view_sizes` and `pixel_policy` are additive result fields; existing per-view `pixel_diff` rows stay compatible. A future offline policy study can use those recorded denominators instead of inventing a capture resolution for old receipts.

## Evidence from this pass

Against exact upstream critic blob `b1962c0da3b3e59443638c871fd1c79af7873211` at main `4a1c1789b2d88efd985c014082b6339dd7c206cd`, owned fixtures reproduced:

- alpha-only and palette-transparency changes being cleared;
- a reference-only view disappearing from the comparison;
- duplicate/aliased labels being overwritten or counted as multiple views;
- 16-bit RGB/RGBA PNG low-bit differences and integer/float images being reduced by conversion;
- multi-frame evidence being judged from the first frame;
- an offline-only request entering the model path without references.

The new regression module has 21 tests. Its first run failed; after the repair it passes. The locally reconstructed existing critic test module adds 16 passing tests (37 total). Production source was blob-verified; the reconstructed test source was not byte-identical, so only the new tests and the changed production file are published. Hosted full-tree qualification remains a separate gate. No GPU/model execution or native Blender qualification was performed.

Run:

```console
python -m unittest discover -s tests -p "test_render_critic*.py" -v
```

## Research notes (checked 2 November 2026)

- [Pillow ImageChops documentation](https://pillow.readthedocs.io/en/stable/reference/ImageChops.html): most channel operations operate on 8-bit images. A successful conversion is not proof that source samples were preserved.
- [Pillow Image API](https://pillow.readthedocs.io/en/stable/reference/Image.html): conversions and alpha handling are explicit operations. The implementation reduces channel differences to a single-band mask before `getbbox`, rather than relying on an RGBA difference image's alpha-only bounding behaviour.
- [Blender sampling-pattern documentation](https://developer.blender.org/docs/features/cycles/sampling_patterns/): adaptive sampling takes different sample counts progressively. Controls must pin capture conditions and separate renderer noise from genuine asset change; this documentation does not calibrate a LAS tolerance.

## Remaining acceptance

Re-render the unchanged chest repeatedly on each configured executable, retain each view's PNG/dimensions/settings, and replay the defective corpus. Report false alarms and missed defects separately, using held-out scenes/poses. A nonzero review floor must be selected from that evidence, not silently inherited from this fix. #1970 stays open. Owner creative review, model terms and runtime promotion are unchanged.
