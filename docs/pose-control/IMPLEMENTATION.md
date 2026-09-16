# Correctable pose inputs: implementation plan

**Goal:** provide a usable local correction/export seam before neural or UI expansion.
**Architecture:** pure helpers in the existing `studio_workflow` package, explicit local CLI, existing Workspace/setup/Production integration in later slices. No new service or persistence owner.
**Stack:** Python 3.12+, standard library; existing Pillow only for raster operations.
**Spec:** [README.md](README.md). Work inline in an isolated source checkout; test-first and verify exact published blobs. A partial checkout must never be reported as a full repository test.

## Global constraints

No network, model execution, package changes, automatic backend recovery, source overwrite, owner database mutation, generation allowance or approval. JSON inputs are byte-bounded and reject duplicate keys/non-finite values. Every output path is explicit and exclusive-create. Preserve imported bytes by identity; do not pretend that the source image was checked when only keypoint JSON was read.

## Task 1 — P0 import and immutable correction (#443)

Create `studio_workflow/pose_artifact.py` and `tests/test_pose_artifact.py`.

Public functions: `loads(data: bytes) -> object`, `import_openpose(data: bytes, *, width: int, height: int, coordinate_space: str, person_index: int | None = None) -> dict`, `validate(artifact: dict) -> dict`, `revise(artifact: dict, expected_id: str, edits: dict) -> dict`, `export_openpose(artifact: dict, threshold: float = 0.3) -> dict`.

- [ ] Write tests first for explicit coordinate scales, x=0, missing confidence, exact body length and ambiguous people.
- [ ] Confirm the missing module fails, then implement bounded COCO-18 import and canonical identity.
- [ ] Add adversarial cases for booleans, nonfinite values, changed content/ID, unknown fields, unsupported populated channels and oversized input.
- [ ] Implement expected-ID edit batches with null for unknown joints, manual provenance and no mutation of input.
- [ ] Prove a valid first edit plus invalid second edit leaves the parent unchanged; prove no-op revision returns the same identity.
- [ ] Re-run `python -m unittest discover -s tests -p 'test_pose_artifact.py' -v`.

Representative acceptance:

```python
before = json.dumps(artifact, sort_keys=True)
with self.assertRaises(ValueError):
    revise(artifact, artifact['id'], {'nose': [12, 20], 'unknown_joint': [1, 2]})
self.assertEqual(json.dumps(artifact, sort_keys=True), before)
```

The first contract is single-person body-only. Native OpenPose export uses a positive presence sentinel for manual joints and zero triples for missing/filtered joints; the original artifact preserves manual/estimated provenance. Do not re-import the lossy interchange file as if it preserved review/provenance.

## Task 2 — P0 raster export and actual CLI (#443)

Create `studio_workflow/pose_raster.py`, `scripts/pose_artifact.py`, and CLI/raster tests alongside the artifact tests. Add a synthetic input under `examples/pose-control/`.

- [ ] Test actual black-background PNG dimensions/pixels, absent limbs when either endpoint is missing, confidence filtering and stable output bytes within the same renderer/Pillow environment.
- [ ] Implement `render_png(artifact: dict, threshold: float = 0.3) -> bytes` using explicit COCO-18 order and versioned colors/stroke choices. Do not claim upstream raster equivalence.
- [ ] Implement `import`, `inspect`, `revise`, `export-json` and `render` subcommands. JSON errors go to stderr; no hidden network/default config imports.
- [ ] Test from a different working directory; verify existing output refusal, invalid-input no-output, changed ID refusal and explicit expected-ID edit behavior.
- [ ] Exercise the synthetic import -> correction -> PNG -> exported keypoints round trip and inspect the PNG.

The CLI help and runbook must show exact invocation syntax and clarify that rendering a guide is not generating art, uploading a reference, binding a native graph or approving geometry.

## Task 3 — P0d post-depth erasure (#427)

Create a separate focused helper/CLI and tests; keep it independent of the pose module so review and merge can be separate.

- [ ] Use synthetic grayscale and RGB depth images. Supply explicit integer pixel-edge rectangles and expected source SHA-256.
- [ ] Test bounds, overlap, duplicate/unknown fields, unsupported modes/frames, changed bytes, source=output refusal and actual outside-region equality.
- [ ] Implement black erasure on the existing map without crop, rescale or re-estimation. Preserve shape and all pixels outside the union of rectangles.
- [ ] Export exact operation metadata and source/output hashes; label the mask as conditioning erasure, never final-image write authority or neutral metric depth.
- [ ] Run the local CLI on synthetic files. Leave real heel/anatomy acceptance with the owner.

## Task 4 — independent integration gates

- [ ] Compile new Python, run focused tests and whitespace checks, and inspect actual generated synthetic guides.
- [ ] Compare local file blob hashes to GitHub publication. Leave PRs ready-for-review and unmerged.
- [ ] Read hosted CI for the exact published head. Report pending/failing gates and preserve logs; never substitute focused passes for full integration.
- [ ] Reconcile main and overlapping PRs again before any merge. Add issue handoffs for browser/native/live evidence still required.

## Subsequent independently reviewable work

#444: existing Combine overlay and Workspace command integration; test real browser, stale imports, shared revisions and zero generation.
#445: source/guide/native-route binding, renderer qualification and inspected live smoke.
#446: exact eight-case screening; actual evidence collection and owner decisions.
#407/#249: neutral proxy/camera/contact and richer layouts only where retained failures justify them.
#245/#248/#257: scoped repair with protected-pixel proofs and accepted final assets.
