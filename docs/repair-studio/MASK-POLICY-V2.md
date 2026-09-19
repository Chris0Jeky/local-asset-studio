# Explicit source-mask processing and strict candidate context

## Design and implementation plan (issue #245)

Keep `straight-rgba-bilinear-v1` byte-compatible. Add the explicitly requested
`straight-rgba-bilinear-v2` transform with required `coverage` fields
`dilate_px` (integer 0..8) and `feather_px` (integer 0..16), measured in normalized
source pixels. Boolean, fractional and unknown policy fields are errors.

The single existing compositor remains authoritative. Before its forward/inverse
bilinear sampling, apply square maximum dilation then finite-support box feathering.
Use zero extension outside the source canvas, retain the intermediate source mask,
and reject expanded support outside the context or intersecting protection. The
final effective mask, not the authored mask, still requires the external review pin.

The v2 candidate must preserve every RGBA sample outside positive sampler coverage,
including padding and RGB hidden under zero alpha. At least one unwriteable interior
context pixel is required. This detects altered context; it does not certify
registration or artistic correctness inside the editable region, and cannot prove
alignment against uniform/repeating anchors. Never auto-warp or patch a rejected
candidate to make it pass.

Implementation sequence:
1. Add failing public-kernel and real packet/CLI tests, including a scalar mask
   oracle, stale pins, tRNS normalization and no output publication on refusal.
2. Add bounded policy helper and integrate it into the existing prepare/render/
   apply paths, preserving the old version and all old receipts.
3. Run the original raster contracts, the new regression matrix and subprocess
   checks locally; compare v1 outputs to the original pinned implementation.
4. Review the actual diff, publish only the tested files, and retain exact source
   hashes and verification limitations below.

No model, native editor, installed runtime or private artwork is needed for these
software contracts. Actual neural registration and owner-approved repair remain
separate #245 acceptance, not inferred from these tests.

## Request and commands

Keep the existing source packet, externally hash-bound plan and request format.
Only the nested transform opts into the new behavior:

```json
{
  "version": "straight-rgba-bilinear-v2",
  "box": [0, 0, 1024, 1024],
  "scale": [3, 2],
  "padding": [4, 8, 4, 8],
  "alignment": 8,
  "coverage": {"dilate_px": 2, "feather_px": 4}
}
```

The original mask file is still `authored_write` in the request and the edit plan.
The packet adds `processed-write.png`: the source-space mask after dilation and
feathering, before resizing. `work-write.png` is sampler coverage after resizing;
`effective-write.png` is the final source-space write coverage after inverse
sampling. Do not substitute any of these identities for another.

Run the existing `repair_pixel_transforms.py prepare`, followed by
`repair_scope_review.py preview` with the same external plan/request and prepared
bundle. The review retains all seven full-resolution artifacts and labels mask
processing explicitly. It exports the same separate inverse-alpha Comfy mask
carrier, never the source alpha. After inspecting the final mask, use its SHA-256
as `apply --expected-effective-write-sha256`. The existing request-file and
candidate-file SHA-256 arguments remain mandatory. No command invokes a model.

A native candidate must preserve the prepared context outside positive sampler
coverage exactly, including padding. A VAE round trip that changes the whole
context is therefore not a conforming v2 candidate. Reject it; do not silently
paste the original context back merely to satisfy the check. The existing v1
route remains available with its explicitly weaker registration claim.

The result adds `candidate_context` with the number of interior anchor pixels,
zero changed anchor pixels, all-RGBA semantics and
`interior_registration_proven: false`. The existing `candidate_registration`
warning stays truthful. Context equality is not a semantic alignment oracle.

## Pixel conventions, bounds and compatibility

Square dilation is a maximum over `(2*dilate_px+1)^2` samples. Feathering is two
separable box averages of width `2*feather_px+1`, rounding to the nearest integer
at each pass. All operations use encoded L samples, not linear-light colour or
alpha premultiplication. A finite zero halo of dilation plus feather radius
makes canvas-edge behavior explicit; its area must fit the same 24-million-pixel
allocation bound before any mask processing. Very thin, large canvases can fail
that scratch bound even when their original area fits. Zero radii make a copy.

The existing integer-centre/half-pixel mapping, positive half-up dimension
rounding, straight-RGBA bilinear interpolation and scale bounds are unchanged.
Expansion is checked before cropping; processing cannot silently cut away a
context escape or protection conflict. The inverse-resampled effective support
is checked again. Feather quantization can remove weak coverage; empty effective
support is rejected. No source transparency is treated as write permission.

Both v1 kernels and v1 receipts retain their old fields, filenames and bytes.
V1 cannot accidentally accept v2 policy fields. Missing fields, unknown fields,
bool-as-int values and unsupported versions are rejected. Existing review packets
retain their original v1 output; only a declared coverage policy changes review
wording/evidence. No schema migration rewrites saved packets.

## Local verification, 19 September 2026

Pinned repository base: `67f995f245518b36fb0192a61da780d337d53028`.
Linux, Python 3.13.5, Pillow 12.3.0. Direct container access to GitHub was unavailable,
so the tested subset was fetched through the connector; each original file's Git
blob ID was checked before editing. Real full modules and subprocesses were used,
not AST-extracted kernels or mocked plan/source owners.

- Original raster suite: 10 tests pass before and after the change.
- New policy suite: 9 tests pass, including its parameterized scalar-oracle and
  five-scale matrices, actual prepare/apply CLI, tRNS normalization, review export
  and reconstruction, rejected padding/context/hidden-RGB edits, stale policy and
  effective-mask pins, stale source, protected scope, missing anchors and caps.
- Initial policy run failed (3 failures, 24 subtest errors) because v2 was absent.
  The separate review regression failed on missing coverage-policy disclosure.
  Both turned green with their production changes.
- Combined command: `python -m unittest discover -s tests -p 'test_repair_*.py' -v`:
  **19 tests passed, zero failures or skips** in the fetched subset.
- 500 seeded comparisons against the unmodified pinned v1 module: exact geometry,
  every prepared image, rendered pixels, delta masks and result-field parity.
  A real v1 prepare packet and receipt were byte-identical.
- `python -m compileall -q scripts tests` and `git diff --check` passed.

No Codex review or cloud Actions result was used. A direct self-review checked
version dispatch, mask expansion versus clipping, all-channel context checks,
external receipt authority, no-clobber refusal and legacy byte compatibility.

Not verified: the full repository lifetime suite or repository validator (only a
pinned source subset was available), Windows execution, native-editor/model
round trips, an installed Comfy mask route, full-canvas transformation chains,
parallel/non-overlapping patch dependency proofs, or a private owner-approved
anatomy repair. No creative acceptance, registration inside editable pixels,
colour-management qualification or generation permission is claimed. #245 stays
open for its remaining native and owner-run acceptance.
