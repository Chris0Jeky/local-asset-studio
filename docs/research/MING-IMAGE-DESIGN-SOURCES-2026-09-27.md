# SOURCES — Ming Image Design 2026-09-27 (BST)

## Rules
- Public HF model API + tree API + **HEAD** for `X-Linked-Size` / Content-Length only
- Public GitHub PR/issue metadata via `gh`
- Public news / ComfyUI Wiki pages
- **No weight body downloads**
- **No API tokens / secrets**
- **No cloud agents**

## Scrape window
~15:05–15:10 BST 2026-09-27 (Europe/London, UTC+1)

## Primary (HF / GitHub)

| Source | URL |
|---|---|
| Design model | https://huggingface.co/inclusionAI/Ming-Image-0.1-Design |
| Design-Layer model | https://huggingface.co/inclusionAI/Ming-Image-0.1-Design-Layer |
| Code | https://github.com/inclusionAI/Ming-Image |
| Comfy weights | https://huggingface.co/Comfy-Org/Ming-Image |
| Kijai redirect | https://huggingface.co/Kijai/Ming-Image-ComfyUI |
| ComfyUI Ming PR | https://github.com/Comfy-Org/ComfyUI/pull/16482 (MERGED 2026-09-24T01:57:31Z) |

## Secondary analysis / news

| Source | URL |
|---|---|
| Disk vs 6B label deep-dive | https://www.creativeainews.com/articles/ming-image-0-1-design-6b-vram-requirements-2026/ |
| ComfyUI Wiki news | https://comfyui-wiki.com/en/news/2026-09-23-ming-image-design |
| ComfyUI Wiki model page | https://comfyui-wiki.com/en/models/ming-image |
| Cocoloop release note | https://news.cocoloop.cn/en/2026/09/ant-ming-image-design-layer/ |
| NVIDIA 12GB LoRA train guide | https://note.com/sepiablue/n/n89e59ce996d9 |

## AMD / INT8 ConvRot context (risk)

| Source | URL |
|---|---|
| gfx1201 INT8 ConvRot NaN | https://github.com/Comfy-Org/ComfyUI/issues/15084 |
| ROCm INT8 ConvRot / HIP notes | https://github.com/Comfy-Org/comfy-kitchen/issues/78 |
| ROCm Triton default PR | https://github.com/Comfy-Org/ComfyUI/pull/14862 |

## HEAD size evidence (dated 2026-09-27)

Cited in the 2026-09-27 pack as `raw/comfy-org-head-sizes.txt` and `raw/hf-*.json`. **Checked 2026-10-19: neither path exists in this repository, and the operator handoffs pack is not here either.** The 2026-09-27 sizes survive only as the tables in FINDINGS section 2. They are not audited from files in the repo.

## Current provenance (observed 2026-10-19, issue #1324)

The first 2026-10-19 reconciliation used summarized, unpinned responses with only `expand[]=safetensors`. Those summaries did not preserve `sha`, `lastModified` or raw responses. A subsequent metadata-only collection on the same date now retains the discovery response and **revision-pinned model/tree responses** for all three repositories in [evidence/ming-image-2026-10-19](evidence/ming-image-2026-10-19/README.md).

The [receipt manifest](evidence/ming-image-2026-10-19/receipts.json) records all nine requested/final URLs, UTC fetch timestamps, server dates, HTTP statuses, byte counts and response SHA-256 hashes. The response files are unmodified bytes. Discovery requests explicitly expanded `sha`, `lastModified` and `safetensors`; pinned requests then used the full selected revision. The model responses confirm that revision, and the tree responses have no next-page Link header. No weight or header-range request was made.

| Repository | Retained revision | Current evidence |
|---|---|---|
| `inclusionAI/Ming-Image-0.1-Design` | `c57c49689d12ef7d4e24a170014f1dc43d3ce258` | API count 6,154,901,056, BF16; five transformer shards total 12,309,858,144 bytes |
| `inclusionAI/Ming-Image-0.1-Design-Layer` | `ff1b22d2bdd0ae6597c0024a42cac7923b24cf92` | API count 6,154,908,736, F32; nine transformer shards total 24,619,690,768 bytes |
| `Comfy-Org/Ming-Image` | `93804ff3747517a318969c5f61b25a57daefe09f` | No `safetensors` object; Layer BF16-named file is 12,309,874,192 bytes; per-file LFS identities retained |

The following table preserves the earlier 2026-10-19 summaries for provenance. Their values can now be compared with the pinned responses; these are not newly recovered September receipts.

| Endpoint | What it returned |
|---|---|
| `huggingface.co/api/models/inclusionAI/Ming-Image-0.1-Design-Layer?expand[]=safetensors` | `safetensors.total` 6,154,908,736; parameters `{"F32": 6154908736}` |
| `huggingface.co/api/models/inclusionAI/Ming-Image-0.1-Design?expand[]=safetensors` | `safetensors.total` 6,154,901,056; parameters `{"BF16": 6154901056}` |
| `huggingface.co/api/models/Comfy-Org/Ming-Image?expand[]=safetensors` | no `safetensors` object (sha and `lastModified` not requested); per-file breakdown not available |
| `huggingface.co/api/models/Comfy-Org/Ming-Image/tree/main?recursive=true` (bytes) | `diffusion_models/ming_image_0.1_design_bf16.safetensors` 12,309,858,664; `diffusion_models/ming_image_0.1_design_int8_convrot.safetensors` 6,175,239,953; `diffusion_models/ming_image_0.1_design_layer_bf16.safetensors` 12,309,874,192; `diffusion_models/ming_image_0.1_design_layer_int8_convrot.safetensors` 6,175,255,481; `text_encoders/ming_image_0.1_ling_mini_2.0_layer_bf16.safetensors` 36,677,768,245; `text_encoders/ming_image_0.1_ling_mini_2.0_layer_int8_convrot.safetensors` 19,507,670,525 |

The current raw tree responses now preserve every advertised per-file LFS SHA-256 and size, including the official transformer's separate shards. The Comfy Layer BF16 entry advertises `31c588e279f0dd461d3366ae7e21b4a0f6926fbc8b5a1f6580ab899a761be34a`. These identifiers come directly from retained JSON; no downloaded weight was hashed locally.

Not established: the Comfy file's own header dtype/tensor inventory, numerical equivalence after conversion, or runtime/consumer-GPU behavior. Byte-identical files or matching hashes are not expected across F32-to-BF16 conversion and sharded-to-single-file repackaging. The [evidence README](evidence/ming-image-2026-10-19/README.md) distinguishes measured metadata from arithmetic inference and provides an offline receipt verification snippet.

The historical operator pack remains unavailable. None of these current receipts audits the missing September capture or changes the existing park/default, licence or art-acceptance decisions.

## Related LAS issues / packs

- #739 Qwen-Image-2.1 Comfy qualify — https://github.com/Chris0Jeky/local-asset-studio/issues/739
- #760 Edit-2511 vs 2.1 split — https://github.com/Chris0Jeky/local-asset-studio/issues/760
- #934 Pruna / image-models wave — https://github.com/Chris0Jeky/local-asset-studio/issues/934
- #1028 QI-2.1 Pareto — https://github.com/Chris0Jeky/local-asset-studio/issues/1028
- Packs: `las-image-models-wave-2026-09-24/`, `qwen-image-2.1-las-2026-09-20/`, `qi21-quality-speed-pareto-2026-09-25/`, civitai 09-21/09-23
