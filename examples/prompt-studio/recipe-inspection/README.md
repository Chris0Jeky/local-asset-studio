# Recipe provenance inspection fixture

This graph is **fabricated metadata**, not an execution record. The companion
8×8 PNG uses procedural colour ramps, not the model named in the graph. The
checkpoint name deliberately does not identify an installed model. Do not import
or execute this fixture as a workflow.

From the repository root:

```sh
python examples/prompt-studio/recipe-inspection/create_demo.py /tmp/recipe-demo
python scripts/studio_prompt.py inspect-media /tmp/recipe-demo/source.png --output-node final
python scripts/studio_prompt.py inspect-media /tmp/recipe-demo/source.png --sidecar /tmp/recipe-demo/source.sidecar.json
```

Choose a new output directory; an existing directory is refused. On Windows,
use a new directory under your chosen local experiment workspace instead of
`/tmp/recipe-demo`.

## What to inspect

`source-report.json` has two known outputs and no automatically selected output.
The `preview` depends on `base`; `final` depends on both `base` and `refine`.
Each sampler keeps its own positive/negative records. The unused spaceship
prompt stays visible but is not attributed to either output. The refinement
negative text has `zeroed_text_embeddings`; it is not presented as evidence that
those negative words influenced inference. Auxiliary conditioning and actual
runtime behaviour remain unverified.

`selected-report.json` records the explicit selection of `final`. It still does
not authenticate the graph or bind that output to the pixels.

`conflict-report.json` preserves the embedded graph and the different sidecar
graph. Their prompt records have different text hashes, their source hashes point
to different files, and `duplicate_records` reports `conflicting_claims`. The
sidecar matches the exact PNG hash but can still lie, as this fixture demonstrates.

`sidecar-only-report.json` cannot compare with an image and reports
`image_binding: not_checked`.

All six generated files are deterministic within the same Python/zlib runtime.
The PNG hash may differ across compression-library versions; the sidecar is
always bound to the bytes actually written. No output is accepted art, a model
benchmark, or a reproduction guarantee.
