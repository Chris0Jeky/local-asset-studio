# Pixel LoRA export geometry

Refs #255: the graph correction is delivered; the requested current-runtime
validation and inspected generation remain outstanding. This change submits no
job and does not alter the owner's recorded compass-A direction choice.

Inspected source: `20c46dd45044a6f9193b3e562df5bee4e5fc8912`, exact archived tree
`a428ce04dd5e4e6edd2121eadda55a6dc509cf06`, 14 September 2026.

## User-visible contract

The preset produces the original detailed render and a nearest-neighbour derivative
at **one eighth of each requested dimension**. It no longer stretches every export
into a 128 × 128 square.

| Requested render | Derivative |
| --- | --- |
| 1024 × 1024 (unchanged default) | 128 × 128 |
| 832 × 1216 | 104 × 152 |
| 1216 × 832 | 152 × 104 |
| 1000 × 744 | 125 × 93 |
| 64 × 1536 (existing admitted boundary) | 8 × 192 |

The existing dimension range and multiple-of-eight rule are unchanged. At these
admitted dimensions, dividing by eight produces exact positive integers with the
same aspect ratio. This is nearest downsampling, not a claim that generated art
has a clean pixel grid or has been accepted as a game asset.

## Graph and compatibility decision

Change only the export scaler (node 9) from fixed-size `ImageScale` to
`ImageScaleBy`, with `scale_by: 0.125` and `upscale_method: nearest-exact`.
The API graph and native visual graph carry the same type, widgets and links.
Model, LoRA, prompt, sampler, seed, latent, decoder and raw-save nodes are unchanged.

A fixed-square warning would document the distortion but leave the useful
non-square path broken. A custom server-side width/height fan-out would duplicate
a native graph operation. The built-in scale-by node follows actual image shape
without adding a control or changing server authority.

[ComfyUI v0.35.0 `nodes.py`](https://github.com/Comfy-Org/ComfyUI/blob/v0.35.0/nodes.py)
(`ImageScaleBy.INPUT_TYPES` and `upscale`, inspected 14 September 2026) supplies the
source contract: dimensions are independently rounded after multiplying by the
scale and scaling uses the disabled-crop path. This is source-derived evidence,
not a capture from the owner's installed backend/frontend or a model run.

The raw prefix remains `Studio/Pixel-LoRA-Raw`. The derivative prefix becomes
`Studio/Pixel-LoRA-Export`, because non-square exports are no longer always 128 px.
The existing visual-file path containing “128px” remains valid for bookmarks and
migration records; its contents and displayed preset description define the new
geometry. Old gallery examples, curated measurements and original files are not
rewritten.

The changed preset is explicitly **unverified**. Its original 20.173-second
execution note is retained and qualified as the historical fixed-square graph,
not inherited by this revision. No later artistic or licensing decision is
inferred. The current picker consumes the existing experimental badge behavior.

The existing expected-template hash guard rejects tickets bound to the previous
graph instead of silently changing their executable input. Old UI setups without
such a pin follow the current preset as before; they see the updated description
and experimental status. No new rebase/retry or implicit dispatch is introduced.

## Proving checks

Six new tests load the actual catalogue/API/visual files and call real Studio
`catalog`/`prepare` on temporary paths, with workers disabled and backend HTTP
forbidden. They cover six shape pairs, full-width seeds, unchanged generation
nodes, visual link/widget parity, a reduced source-derived native schema,
verification wording and old/current template hashes. Geometry is a documented
node projection, not tensor/inference execution.

The final red run on unchanged product files had ten assertion/subtest failures;
the first draft also exposed a test-only import-path shadowing problem, corrected
before that run. The corrected focused group passes six tests.

```sh
python -m unittest discover -s tests -p test_graph_pixel_export.py -v
python -m unittest discover -s tests
python scripts/validate-repo.py
```

The existing Graph validation contracts lane now exercises these tests on Linux
and Windows and also watches the paired visual file. Full-suite/CI results are
recorded against the exact PR head. No current native-render pass is claimed.

## Remaining acceptance and rollback

A runtime owner must inspect the installed schema, then explicitly authorize one
bounded non-square proof using the current preset. Retain job/prompt IDs, exact
graph/model identities, raw/derivative dimensions and hashes, and a separate visual
review; do not blindly repeat an uncertain attempt. Only matching current evidence
may restore `verified: true`. #255 remains open for this acceptance.

Rollback restores node 9, node 10's old prefix, paired visual widgets and catalogue
wording. Existing exports do not need migration; changed derivatives legitimately
have different bytes and paths. No runtime packages or owner choices changed.
