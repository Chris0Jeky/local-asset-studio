# Pixel fidelity at the local-agent boundary

Companion to [controlled editing](EDITING.md) and the [runbook](EDIT-RUNBOOK.md).
The context handed to another tool must faithfully represent the source, not just have a matching width and height. An outside-mask preservation check can pass even when a generator was shown the wrong transparency.

## Supported context encoding

The offline bridge accepts single-frame RGB/RGBA PNG sources with an explicit canvas contract. It rejects EXIF-bearing input rather than guessing orientation. Grayscale L edit masks contain coverage values: 0 preserves the source and 255 permits replacement. A separate protection mask is binary, with 255 forbidding editing.

True-colour PNG may store transparency in a tRNS colour-key chunk while Pillow reports mode RGB. Before building a context canvas, the bridge now materializes that key as RGBA alpha. Source files, decoded source RGB and metadata are not overwritten. Ordinary opaque RGB and existing RGBA contexts retain their established mode and padding behaviour.

For key-transparent or RGBA contexts, alignment padding is zero RGBA, hence transparent black. For opaque RGB contexts, the existing padding is black. The write mask is always zero in padding. Padding is explicit and never resamples the source crop. ICC bytes are retained; this is not a complete colour-managed native-document interchange contract.

Bundle validation compares mode, dimensions, raw channel bytes, decoded RGBA and ICC metadata. Recomputing a file hash and bundle hash after adding a transparency key does not bypass source reconstruction. This is local integrity checking, not authentication against someone replacing every source and plan.

## Recovery from earlier prepared bundles

A context previously prepared from an RGB+tRNS source may have lost transparency. Such an old bundle will now fail reconstruction. Keep it as historical evidence and run `prepare` again into a **new** directory using the unchanged source and plan. This is a CPU-only preparation step; do not automatically repeat a neural job or overwrite the old candidate. Assess any existing candidate against the corrected context before selecting or regenerating it under the study budget.

Opaque RGB and RGBA bundles are not intentionally invalidated by this fix. A new source or mask still requires the normal hash-bound plan revision.

## Regression checks

```console
python -m unittest discover -s tests -p "test_character_edit_transparency.py" -v
python -m unittest discover -s tests -p "test_character_edit*.py" -v
```

The twelve new checks cover colour-key normalization, save/reopen fidelity, transparent alignment padding, unused/black colour keys, unchanged input bytes, opaque-RGB compatibility, partial alpha and hidden RGB, ICC retention, no resampling, a full no-op round trip, exact outside-mask preservation and a rehashed transparency-only bundle modification. They use synthetic pixels, not model-generated artwork.

The continuation session reproduced five failures in the nine context-level tests on the original code, then nine passes after the fix. It executed exact extracted production functions because the private repository could not be cloned from that container (DNS unavailable). The other three tests exercise actual planner/preflight/apply imports through the full repository's normal CI. Those execution scopes must not be conflated. No new image inference or native-editor operation is asserted here.

## Primary reference

Pillow PNG format documentation, inspected 12 September 2026:
https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#png

Pillow documents transparency metadata for RGB and other PNG modes. The tests establish the behaviour of this bridge and the selected Pillow runtime; they do not certify arbitrary model encoders or native editor export settings.
