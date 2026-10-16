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

## HEAD size evidence

See `raw/comfy-org-head-sizes.txt` and `raw/hf-*.json`.

## Related LAS issues / packs

- #739 Qwen-Image-2.1 Comfy qualify — https://github.com/Chris0Jeky/local-asset-studio/issues/739
- #760 Edit-2511 vs 2.1 split — https://github.com/Chris0Jeky/local-asset-studio/issues/760
- #934 Pruna / image-models wave — https://github.com/Chris0Jeky/local-asset-studio/issues/934
- #1028 QI-2.1 Pareto — https://github.com/Chris0Jeky/local-asset-studio/issues/1028
- Packs: `las-image-models-wave-2026-09-24/`, `qwen-image-2.1-las-2026-09-20/`, `qi21-quality-speed-pareto-2026-09-25/`, civitai 09-21/09-23
