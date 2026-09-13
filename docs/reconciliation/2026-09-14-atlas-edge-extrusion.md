# Preserve RGBA bytes in atlas borders

Issue #267. Inspected main `2f91421ecbe0e014cceef1074f4d79e4c57051df`;
tracked-source tree `25da90c8445bc5e94cc73fd814964563c256f102` was reproduced
before editing. This is a deterministic packaging correction under #24/#177,
not completion of engine integration or gallery/media scaling.

## Root cause

The atlas exporter correctly copies each logical RGBA frame without applying
its alpha twice. Its existing round-trip check covers that central region.
However, widening the one-pixel edge strips used `Image.resize` without an
explicit filter. Pillow defaults to BICUBIC; non-nearest RGBA resizing converts
through premultiplied alpha. Quantization can change retained RGB, especially
at very low alpha. A real one-pixel frame `(101, 50, 200, 1)` produced border
pixels `(0, 0, 255, 1)`. Fully transparent RGB can also become zero.

The four edge resizes now explicitly use `Image.Resampling.NEAREST`: each border
pixel copies its clamped source-edge coordinate, including all four channels.
Corner fills already copied exact bytes and are unchanged. There is no new
interpolation, source trim, canvas resize, alpha composite, output schema or
package dependency.

## Compatibility

Logical frame regions, anchor, duration, ordering, remaining transparent padding,
source hashes and warning semantics remain unchanged. Extrusion 0 and 1 retain
their pixel behavior. New exports with wider borders can have corrected PNG
bytes and therefore a different atlas hash; the existing manifest generator
records that actual hash. Previously generated packages are not rewritten.
This does not assert a measured improvement in a particular engine's renderer,
texture filtering or mipmaps, nor creative acceptance.

## Regression coverage

Three new tests decode the resulting PNGs and compare every cell pixel against
an independently clamped source coordinate. Coverage includes extrusion widths
0/1/2/3/8/16, alpha 0/1/2/64/127/128/254/255, four edges/corners, untouched padding,
adjacent cells, a partially filled final row, a 1x1 frame and repeatable exports.
They also retain original input bytes and manifest content.

On unchanged source these tests produce six expected assertion/subtest failures.
After the four-resize correction all three pass; the existing game-asset group
also passes. CI checks pixel bytes, not wall-clock speed or subjective quality.

```sh
python -m unittest discover -s tests -p test_game_asset_extrusion.py -v
python -m unittest discover -s tests -p 'test_game_asset_*.py'
python -m unittest discover -s tests
python scripts/validate-repo.py
```

The existing Game asset lab workflow discovers the new test without a new lane.
Full-suite/hosted outcomes are recorded on the PR with its source identity.
Optional/live skips are not engine evidence. Revert the four resampling arguments
to restore prior behavior; no stored-state migration is required.

No model generation, native engine/editor launch, owner-data mutation, runtime
change or HUMAN_TODO edit occurred. Existing human decisions remain unchanged.

Primary reference checked 14 September 2026:
[Pillow Image.resize implementation and documented filters](https://pillow.readthedocs.io/en/stable/_modules/PIL/Image.html#Image.resize).
