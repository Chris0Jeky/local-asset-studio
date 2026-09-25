# SOURCES — LAS image-models wave 2026-09-24 (BST)

## Rules
- Public Civitai API only (`https://civitai.com/api/v1/models`)
- User-Agent: `Mozilla/5.0 (compatible; LAS-scavenge/2026-09-24)`
- **No API tokens / secrets**
- **No weight downloads** (HF HEAD for `X-Linked-Size` / Content-Length only)
- List/search only (no model-by-id; CF 1015 risk)
- HF model API rate-limited this run; README raw + HEAD used for Pruna

## Scrape window
~23:05–23:12 BST 2026-09-24 (Europe/London, UTC+1)

## Reddit / HF seed
- Reddit: https://www.reddit.com/r/StableDiffusion/comments/1wp6la7/new_fewstep_lora_adapters_for_qwenimage21_5x/
- Shortlink: https://www.reddit.com/r/StableDiffusion/s/IBu4z0DXSt
- HF Pruna: https://huggingface.co/PrunaAI/Pruna-Qwen-Image-2.1
- Base: https://huggingface.co/Qwen/Qwen-Image-2.1
- Pack extract: `reddit-extract.md`
- Tracking issue: https://github.com/Chris0Jeky/local-asset-studio/issues/934

### Pruna file sizes (HEAD, no body)
- `p_qwen_image_2.1_8step_v0.1.safetensors` → 335606104 bytes (~320.1 MB)
- `p_qwen_image_2.1_5step_v0.1.safetensors` → 335606144 bytes (~320.1 MB)
- License frontmatter: `license_name: qwen-research`

## Civitai queries (snapshots under `raw/`)

### Illustrious Week/Month
```
types=LORA&baseModels=Illustrious&sort=Highest%20Rated&period=Week|Month&limit=20
types=LORA&baseModels=Illustrious&sort=Most%20Liked&period=Week|Month&limit=20
types=Checkpoint&baseModels=Illustrious&sort=Most%20Liked&period=Month&limit=15
```

### Noob / Pony / SDXL Month
```
types=LORA&baseModels=NoobAI|Pony|SDXL%201.0&sort=Most%20Liked&period=Month&limit=20
```

### Newest Week
```
types=LORA|Workflows&sort=Newest&period=Week&limit=20
```

### Qwen / Klein / Z-Image / Krea
```
query=Qwen%20Image%202.1&sort=Most%20Liked|Newest&period=Month|Week
query=Qwen%20Edit&sort=Most%20Liked&period=Year
types=Workflows&query=Qwen&sort=Most%20Liked&period=Year
query=FLUX.2%20Klein|Klein&sort=Most%20Liked&period=Year|Month
query=Z-Image%20Turbo&sort=Most%20Liked&period=Year
types=Workflows&query=Z-Image&sort=Most%20Liked&period=Month
query=Krea&sort=Most%20Liked&period=Month
query=2511%20lighting&sort=Most%20Liked&period=Year
```

### Thin / empty (documented — API returned items:[], nextCursor present)
```
query=Qwen-Image-Edit&period=Month → empty (use Year / Qwen Edit)
types=Workflows&query=Qwen&period=Month → empty
query=FLUX.2%20Klein&types=LORA&period=Month → empty (use Year / query=Klein)
query=Z-Image&types=LORA&period=Month → empty
types=LORA&query=lighting&baseModels=Illustrious&period=Month → empty (Year works for known sliders)
query=IP-Adapter&period=Month → empty
```

## Prior exclusion
- 218+ ids from 09-21 / 09-23 FINDINGS → `raw/_prior_ids.txt`
- Brief evergreen skip list applied in curation

## Raw artifacts
- `raw/*.json` — Civitai list snapshots
- `raw/hf_pruna_qwen21_README.md` — Pruna card
- `raw/hf_qwen_image_21_README.md` — QI-2.1 card frontmatter
- `raw/_curated_new.json` — NEW interesting pool
- `raw/_prior_ids.txt`
