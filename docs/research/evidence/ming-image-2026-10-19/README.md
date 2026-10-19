# Ming metadata receipts — 2026-10-19 UTC

Current evidence for [#1324](https://github.com/Chris0Jeky/local-asset-studio/issues/1324). This directory retains nine public Hugging Face JSON responses exactly as received, plus a [receipt manifest](receipts.json). The manifest records requested/final URLs, fetch time, server date, HTTP status, response size and SHA-256. It also records the pagination Link header; none of these tree responses advertises another page.

These are **current observations**, not a reconstruction of the missing 2026-09-27 HEAD/API pack. No weights, safetensors headers, runtime installation or inference were fetched or run. This evidence does not grant model, licence, preset or artistic acceptance.

## Revision pins and retained responses

For each repository, a discovery request selected a commit; subsequent model and recursive-tree requests used that full commit in their URL. The pinned model response's `sha` matches the requested revision. The three discovery responses are also retained so the selection can be audited.

| Repository | Immutable revision | Pinned model API | Pinned tree API |
|---|---|---|---|
| inclusionAI/Ming-Image-0.1-Design | `c57c49689d12ef7d4e24a170014f1dc43d3ce258` | [model](design-model-c57c49689d12ef7d4e24a170014f1dc43d3ce258.json) | [44 entries](design-tree-c57c49689d12ef7d4e24a170014f1dc43d3ce258.json) |
| inclusionAI/Ming-Image-0.1-Design-Layer | `ff1b22d2bdd0ae6597c0024a42cac7923b24cf92` | [model](layer-model-ff1b22d2bdd0ae6597c0024a42cac7923b24cf92.json) | [48 entries](layer-tree-ff1b22d2bdd0ae6597c0024a42cac7923b24cf92.json) |
| Comfy-Org/Ming-Image | `93804ff3747517a318969c5f61b25a57daefe09f` | [model](comfy-model-93804ff3747517a318969c5f61b25a57daefe09f.json) | [15 entries](comfy-tree-93804ff3747517a318969c5f61b25a57daefe09f.json) |

The model requests explicitly expand `sha`, `lastModified` and `safetensors`. Their reported last modifications are October 14 for both inclusionAI repositories and October 10 for Comfy-Org. Those timestamps describe the repositories; the manifest's fetch timestamps describe this evidence collection.

## What the metadata supports

Sizes below are decimal bytes. Official file totals sum only `.safetensors` entries under `transformer/`; they exclude the index, config, text encoder and other components. Parameter counts and dtype are the model API's `safetensors` summary, not a locally parsed tensor header.

| Evidence | Design | Design-Layer |
|---|---:|---:|
| API parameter total | 6,154,901,056 | 6,154,908,736 |
| API stored dtype | BF16 | F32 |
| Tensor bytes implied by that count/dtype | 12,309,802,112 | 24,619,634,944 |
| Official transformer shard count | 5 | 9 |
| Official transformer file bytes | 12,309,858,144 | 24,619,690,768 |
| File bytes beyond implied tensor storage | 56,032 | 55,824 |

Layer has 7,680 more reported parameters than Design; both are approximately 6.15 billion. The official Layer storage is F32. BF16 inference recommended by its model card is a separate runtime choice.

The Comfy tree reports `diffusion_models/ming_image_0.1_design_layer_bf16.safetensors` at **12,309,874,192 bytes**, with LFS SHA-256 **`31c588e279f0dd461d3366ae7e21b4a0f6926fbc8b5a1f6580ab899a761be34a`**. Each official shard's separate LFS identifier and byte size are retained in its tree response. These identify the advertised files; weight bytes were not downloaded to verify their hashes.

At two bytes per parameter, the official Layer count would occupy 12,309,817,472 tensor bytes. The Comfy file is 56,720 bytes larger, consistent with a BF16 repack plus header/metadata. **That is a size-based inference.** The Comfy API provides no per-file safetensors summary here; the filename and size do not independently prove its dtype, tensor inventory, numerical equivalence or successful loading.

Byte identity between a sharded F32 original and a single-file BF16 repack is not an appropriate acceptance test: precision conversion and repackaging change bytes and hashes. A future, separately authorized tensor/header and runtime qualification would have to establish the intended mapping and conversion. A matching file size or an LFS identifier alone cannot do that.

## Rechecking the receipt files

Run from this directory; this checks only the retained response bytes against their manifest and performs no network access:

```python
from pathlib import Path
import hashlib
import json

root = Path('.')
manifest = json.loads((root / 'receipts.json').read_text())
for receipt in manifest['responses']:
    raw = (root / receipt['file']).read_bytes()
    assert len(raw) == receipt['bytes']
    assert hashlib.sha256(raw).hexdigest() == receipt['sha256']
    json.loads(raw)
print('Verified', len(manifest['responses']), 'retained JSON responses')
```

The original September sizes and recommendations remain dated observations in the parent findings. This collection resolves access to current metadata and its revision provenance; it does not recover historical receipts or qualify a consumer GPU workflow.
