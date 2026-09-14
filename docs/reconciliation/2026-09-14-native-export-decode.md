# Native-export image admission and buffer ownership

Issue #281; related stage/resource admission remains #178. Source inspected:
`20c46dd45044a6f9193b3e562df5bee4e5fc8912`, exact archived Git tree
`a428ce04dd5e4e6edd2121eadda55a6dc509cf06` (14 September 2026).

## Cause and correction

`NativeExports._images` loaded pixels before applying the adapter's 8192-pixel
side limit, cumulative 16 × 1024 × 1024 source-pixel limit and shared-canvas check.
A refused input could already have incurred the decode allocation. PNG/WebP
animation was also silently reduced to one frame in a still-image export.

Check format, dimensions, total pixels, shared canvas and frame count before
calling `load` or converting colour. Reject multiple frames with an instruction
to extract frames explicitly. Separate supplied still frames remain a supported
atlas/animation package input: this does not prohibit frame sequences with their
own durations.

The colour conversion already produces an owned image. Retain it directly rather
than copying it again. An `ExitStack` owns successful conversions while inputs
are being validated; ownership transfers only after every input succeeds.
`execute` closes that set in `finally`, including invalid options, output-directory
creation errors, packaging errors and success. File decoders retain their existing
context-manager ownership. No frame bytes, timing, ordering or RGBA/sRGB policy
change is intended for previously admissible still-image inputs.

The existing exclusive `target.mkdir()` remains outside the block that writes
failure evidence. An unsuccessful claim on a competing directory therefore cannot
write `failure.json` into somebody else's directory. Once an attempt owns its
output directory, existing partial sources and failure evidence remain retained.

## Why this boundary

Pillow's [Image documentation](https://pillow.readthedocs.io/en/stable/reference/Image.html)
(describing 12.3.0, inspected 14 September 2026) distinguishes lazy `Image.open`
from pixel-loading operations. Metadata admission before `load` is therefore the
appropriate boundary; lowering global Pillow bomb thresholds or catching memory
errors after allocation would not implement this adapter's cumulative limit.

No global Pillow setting, model/queue reservation, second exporter or source store
is introduced. An animated input is rejected rather than inventing frame timing,
flattening semantics or silently choosing a frame for the operator.

## Reproduction and proving checks

Eight new real-image tests initially produced ten assertion/subtest failures on
unchanged source. They record actual decoder `load` calls, lower the existing cap
for small deterministic boundary fixtures, and include a real 8193 × 1 PNG plus
real two-frame APNG/WebP files. The exact-boundary case asserts the conversion is
not redundantly copied. Other cases check prior-buffer cleanup, invalid options,
successful ORA packaging and an injected packaging failure with retained evidence.

```sh
python -m unittest discover -s tests -p 'test_native_export*.py' -v
python -m unittest discover -s tests
python scripts/validate-repo.py
```

The focused corrected group passed 11 tests (eight new, three existing). The
unchanged full baseline passed 1,904 tests with 18 environment-dependent skips.
Final full-suite/CI counts and exact published trees are retained on the PR and
in the maintenance bundle. Existing Pillow deprecation/socket warnings remain
visible; no skipped live case is counted as executed evidence. The existing
Windows runtime-safety lane now explicitly runs the native-export group.

## Limits and rollback

This prevents these explicit decode/conversion calls for rejected input and closes
owned buffers predictably. It does not bound all compressed-file parsing, hashing,
packaging allocations, RSS, filesystem latency or Pillow internals. There is no
measured GPU or whole-process memory reduction, atomic-source-capture guarantee,
engine launch, art approval or new power-loss durability guarantee.

Revert the adapter/test/CI changes to restore the prior behavior; no stored schema,
configuration or artifact migration is required. Existing packages are untouched.
