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

Read through the Hugging Face model API and tree API, which this pack already used as its method. These are summaries of the API responses, not saved raw JSON; the queries used only `expand[]=safetensors`, which returns only the listed properties, so `sha` and `lastModified` were **not requested** (their absence says nothing about the repos). A revision pin needs a re-query with `expand[]=sha&expand[]=lastModified`.

| Endpoint | What it returned |
|---|---|
| `huggingface.co/api/models/inclusionAI/Ming-Image-0.1-Design-Layer?expand[]=safetensors` | `safetensors.total` 6,154,908,736; parameters `{"F32": 6154908736}` |
| `huggingface.co/api/models/inclusionAI/Ming-Image-0.1-Design?expand[]=safetensors` | `safetensors.total` 6,154,901,056; parameters `{"BF16": 6154901056}` |
| `huggingface.co/api/models/Comfy-Org/Ming-Image?expand[]=safetensors` | no `safetensors` object (sha and `lastModified` not requested); per-file breakdown not available |
| `huggingface.co/api/models/Comfy-Org/Ming-Image/tree/main?recursive=true` (bytes) | `diffusion_models/ming_image_0.1_design_bf16.safetensors` 12,309,858,664; `diffusion_models/ming_image_0.1_design_int8_convrot.safetensors` 6,175,239,953; `diffusion_models/ming_image_0.1_design_layer_bf16.safetensors` 12,309,874,192; `diffusion_models/ming_image_0.1_design_layer_int8_convrot.safetensors` 6,175,255,481; `text_encoders/ming_image_0.1_ling_mini_2.0_layer_bf16.safetensors` 36,677,768,245; `text_encoders/ming_image_0.1_ling_mini_2.0_layer_int8_convrot.safetensors` 19,507,670,525 |

The tree API also returns a per-file LFS sha256 for each file. Those hashes are **not recorded here**: they came back through a summarizing fetch and have not been checked against the raw response, so they cannot be cited as audit evidence. The next step is to pull the raw tree JSON into a tracked file with its date and compare the hashes there.

Not established: the official Layer transformer's LFS hash (so no byte-identity claim between the Comfy and official Layer files); the Comfy file's safetensors header dtype; any revision pin.

## Related LAS issues / packs

- #739 Qwen-Image-2.1 Comfy qualify — https://github.com/Chris0Jeky/local-asset-studio/issues/739
- #760 Edit-2511 vs 2.1 split — https://github.com/Chris0Jeky/local-asset-studio/issues/760
- #934 Pruna / image-models wave — https://github.com/Chris0Jeky/local-asset-studio/issues/934
- #1028 QI-2.1 Pareto — https://github.com/Chris0Jeky/local-asset-studio/issues/1028
- Packs: `las-image-models-wave-2026-09-24/`, `qwen-image-2.1-las-2026-09-20/`, `qi21-quality-speed-pareto-2026-09-25/`, civitai 09-21/09-23
