# Minimum-copy CPU implementation plan

Goal: remove two verified full-image temporary-allocation patterns without changing user-visible pixels, metadata contracts, generation settings or dependencies.

Architecture: preserve the existing `review_media.decode(data)` and `character_edit_pixels.changed_mask(a,b)` interfaces. Keep changes independent; each can be reviewed or reverted without the other. Detailed owner/lifetime design: [ARCHITECTURE.md](ARCHITECTURE.md). Stack: existing Python 3.12+, Pillow, unittest; no GPU imports or network in tests.

## Slice A — no-op orientation copy (#362)

Files: modify `app/review_media.py`; add `tests/test_review_decode_copies.py`; add a scoped benchmark/evidence note under `docs/performance/low-level/` and a reproducible CPU-only script if needed.

1. Preserve the original function as a test oracle. Construct small asymmetric pixels in every supported mode, EXIF 1–8, unknown/missing orientation, palette/RGB transparency and metadata-bearing PNGs. Assert pixels, mode, dimensions, transform and stripped metadata against that oracle.
2. Add the causal allocation test before implementation:

```python
with patch.object(ImageOps, 'exif_transpose', wraps=ImageOps.exif_transpose) as transpose:
    result, transform = review_media.decode(normal_orientation_png)
    self.assertEqual(transpose.call_count, 0)
    result.close()
```

Run `python -m unittest discover -s tests -p 'test_review_decode_copies.py'`. The baseline must fail the zero-call assertion, not a missing import.

3. Branch only at the existing orientation decision:

```python
if orientation in (2, 3, 4, 5, 6, 7, 8):
    with ImageOps.exif_transpose(source) as oriented:
        image = oriented.convert('RGBA')
else:
    image = source.convert('RGBA')
```

Keep `image.info.clear()` and the existing return/error/cap contracts unchanged.

4. Run the focused suite, existing review tests and C1 benchmark. Record genuine source/input/output identities and exact environment. Do not use speed assertions in ordinary CI.
5. Publish a ready-for-review PR with the causal failure, passing result, memory/timing evidence, remaining Windows limitation and issue disposition. Require the existing full offline suite and validator on the hosted candidate.

## Slice B — tiled all-channel difference (#363)

Files: add `scripts/pixel_diff.py` and `tests/test_pixel_diff.py`; modify only the import/wrapper in `scripts/character_edit_pixels.py`; add C2 benchmark/evidence.

Consumes: two Pillow images of equal dimensions. Produces: independent binary L mask, 255 iff any converted RGBA channel differs. Expose `changed_mask(a, b)` from the helper; the old public wrapper delegates to it. Keep the existing dimension error wording.

1. Test baseline equivalence and allocation shape before replacing the implementation. First land the helper with the original full-image algorithm or test the original callable directly, so the bounded-difference assertion demonstrably fails on actual full-image work:

```python
with patch.object(ImageChops, 'difference', wraps=ImageChops.difference) as diff:
    mask = changed_mask(a, b)
    self.assertTrue(all(call.args[0].width <= 512 and call.args[0].height <= 512
                        for call in diff.call_args_list))
    mask.close()
```

The test images must exceed both tile dimensions. Test all channels, alpha-zero hidden RGB, palette/tRNS, odd/wide/tall shapes, boundary changes, no-op inputs and dimension mismatch. Do not substitute a fake diff function for the real operation.

2. Implement nested x/y tile traversal. Allocate only the required output L mask at canvas size. For each tile: crop each input; convert each crop to RGBA; calculate RGBA difference; take the maximum over all four bands; threshold; paste; close every owned intermediate. On error close the output and re-raise; never close caller-owned images.
3. Replace the original wrapper body with delegation. Keep `_verify_bundle` and its exact/profile comparisons untouched.
4. Run `python -m unittest discover -s tests -p 'test_pixel_diff.py'`, then the existing protected-edit suites and C2 fresh-process benchmark. Include a real Pillow-operation fault and verify cleanup. Label full-input decoding and required output storage as remaining costs.
5. Publish separately with full CI and validator evidence. A caller/source integration failure blocks promotion even when the helper tests pass.

## Publication and handoff

Base every remote tree on the inspected commit tree, not an invented partial repository. Recheck open work/main before publishing and compare changed files to avoid unrelated replacements. Local focused tests may run against checksum-verified extracted modules when a full clone is unavailable; **that is not the full offline suite**. Hosted checks must run against the actual complete PR tree.

Record verification at the final head. Keep `Refs #362`/`Refs #363` until complete acceptance is observed; do not close the resource, gallery, native-edit or inference epics. All PRs remain reviewable, with no implicit runtime deployment. HUMAN_TODO is unchanged.
