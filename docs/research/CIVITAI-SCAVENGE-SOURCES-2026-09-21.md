# SOURCES — Civitai scavenge 2026-09-21 (BST)

## Civitai public API (curl + jq on box)

Base: `https://civitai.com/api/v1/models`  
User-Agent: `LAS-scavenge/1.0`  
No auth. No weight downloads.

### LoRA sweeps (Highest Rated, period=Year, limit=40)
```
types=LORA&baseModels=Illustrious&sort=Highest%20Rated&period=Year&limit=40
types=LORA&baseModels=Pony&sort=Highest%20Rated&period=Year&limit=40
types=LORA&baseModels=NoobAI&sort=Highest%20Rated&period=Year&limit=40
types=LORA&baseModels=SDXL%201.0&sort=Highest%20Rated&period=Year&limit=40
types=LORA&baseModels=Flux.1%20D&sort=Highest%20Rated&period=Year&limit=40
```
Raw: `raw/lora_illustrious.json`, `lora_pony.json`, `lora_noobai.json`, `lora_sdxl.json`, `lora_flux.json`

### Checkpoint / query sweeps
```
types=Checkpoint&sort=Highest%20Rated&period=Year&limit=40&query=WAI%20Illustrious
…query=NoobAI | Pony | Animagine | FLUX | Qwen
query=RealVisXL%20V5&sort=Most%20Liked
query=NoobAI-XL&types=Checkpoint&sort=Most%20Liked
query=Animagine%20XL%204.0&sort=Most%20Liked
query=WAI-Illustrious&sort=Most%20Liked&period=Year
query=z-image&sort=Most%20Liked&period=Year
query=qwen-image | Qwen-Image | Qwen-Image-Edit-2511-Lightning
query=Krea2 | krea (LoRA)
query=controlnet%20union%20sdxl | xinsir
query=ipadapter | IP%20Adapter%20SDXL
query=lightning | pixel%20art
```

### ControlNet / Workflows / Articles
```
types=Controlnet&sort=Most%20Liked&period=AllTime&limit=40
types=Workflows&sort=Highest%20Rated&period=Year&limit=30
GET /api/v1/articles?limit=20&sort=Most%20Bookmarks
types=LORA&baseModels=Pony|NoobAI&sort=Most%20Liked&period=Month&limit=30
```

### Direct model id (partial — Cloudflare 1015 on some)
```
GET /api/v1/models/827184  → 1015 at scrape time
GET /api/v1/models/257749  → OK (Pony V6)
Others mixed; stats primarily from list/search payloads.
```

## civitai.red
- `GET https://civitai.red/` — featured hub reachable (WebFetch)
- `GET https://civitai.red/api/v1/models?types=LORA&baseModels=Illustrious&sort=Highest%20Rated&period=Year&limit=10` → `raw/red_lora.json` (10 items)
- `GET https://civitai.red/models/827184` — WAI v17 HTML; confirmed CFG 5–7, Euler a, quality tags (`raw/red_wai.html`)

## WebSearch / external guides (tips only)
- https://huggingface.co/xinsir/controlnet-union-sdxl-1.0
- https://huggingface.co/xinsir/controlnet-openpose-sdxl-1.0
- https://www.thundercompute.com/blog/qwen-image-edit-comfyui
- https://www.stablediffusiontutorials.com/2025/12/qwen-image-edit-2511.html
- https://myaiforce.com/qie-2511/
- https://wiki.monai.art/en/models/wai_illustrious_15
- https://civitai.com/articles/4248 (Pony score_9)
- https://civitai.com/articles/23210 (Illustrious prompt guide)
- https://civitai.com/articles/7484 (samplers)
- https://civitai.com/articles/6555 (Pony tips)

## Local raw snapshots
Directory: `/workspace/handoffs/civitai-scavenge-2026-09-21/raw/`  
Includes: LoRA/ckpt dumps, workflows, articles, krea2, ipa2, creators_agg.json, ratio samples, zimage, qwen*, controlnet*, red_*.

## Explicitly not done
- No safetensors / GGUF / CKPT downloads
- No login / scraping of private endpoints

## Batch 2 queries (~01:27–01:35 BST 2026-09-21)

UA: `LAS-scavenge/1.0`. Base: `https://civitai.com/api/v1/models`. No auth. No weight downloads. List/search only (avoid direct id 1015).

### FLUX.2 / Klein
```
types=LORA&query=Klein&sort=Highest%20Rated&period=Year&limit=40
types=LORA&query=FLUX.2|Flux.2&sort=Highest%20Rated|Most%20Liked&period=Year
types=LORA&query=Klein&sort=Most%20Liked&period=Month
types=LORA&query=Klein%20anatomy|Klein%20detail&sort=Most%20Liked&period=Year
query=Klein%20GGUF&sort=Most%20Liked&period=Year
baseModels=Flux.2 | Flux.2%20Klein  → empty (API rejects / no match)
```
Manual filter: keep versions whose `baseModel` contains Klein / Flux.2 / FLUX.2; reject pure Flux.1 D unless Klein also listed.

### Z-Image
```
query=z-image|Z%20Image%20Turbo&sort=Most%20Liked&period=Year
types=LORA&query=Z-Image&sort=Highest%20Rated&period=Year
types=Workflows&query=Z-Image&sort=Most%20Liked&period=Year
types=Checkpoint&query=Z-Image&sort=Most%20Liked&period=Year
types=Workflows&query=Z-Image%20low%20VRAM|low%20VRAM&sort=Most%20Liked&period=Year
```

### Animagine XL 4
```
types=LORA&query=Animagine&sort=Highest%20Rated&period=Year  → empty page1 (cursor=40)
types=LORA&query=Animagine&sort=Most%20Liked&period=AllTime&limit=40
types=LORA&query=Animagine%20XL%204.0&sort=Most%20Liked&period=AllTime
types=Workflows&query=Animagine&sort=Most%20Liked&period=Year
baseModels=Animagine → empty
```

### RealVis
```
types=LORA&query=RealVis|RealVisXL → ~1 item (portrait)
types=LORA&baseModels=SDXL%201.0&query=cinematic|skin%20detail|photorealistic&sort=Highest%20Rated|Most%20Liked
```

### Qwen-Image-2.1
```
types=LORA&query=Qwen-Image-2.1|Qwen%202.1|Qwen2.1
types=Workflows&query=Qwen-Image-2.1|Qwen2.1|Qwen%20GGUF
query=Qwen%202.1&sort=Most%20Liked&period=Year
```
Keep only name/base suggesting 2.1 / `Qwen 2`; reject pure 2511.

### Pixel art
```
types=LORA&query=pixel%20art&sort=Highest%20Rated|Most%20Liked&period=Year
query=pixel%20Z-Image|pixel%20Qwen|Pixel%20Art%20Refiner
```

### Creators (`username=` supported)
```
username=EauDeNoire|VelvetS|motimalu|YeiYeiArt|reakaakasky
&sort=Most%20Liked&period=AllTime&limit=20
```

### AMD-safe workflows
```
types=Workflows&query=GGUF|FP8%20low%20VRAM|Klein%20GGUF|Z-Image%20low%20VRAM|Qwen%20GGUF|low%20VRAM
```

### Raw snapshots
`raw/batch2_*.json` (50+ files) + `raw/batch2/flux2_klein_lora.json` early partial.

## Batch 3 queries (~01:32–01:45 BST 2026-09-21)

UA: `LAS-scavenge/1.0`. No weight downloads. List/search + article-by-id.

### Articles
```
GET /api/v1/articles?limit=50&sort=Most%20Bookmarks
GET /api/v1/articles/{23210,4248,6555,7484,7972,10242,5102,3296,3527,7036,8547,1250,5545,19251,…}
```
Article `query=` filters returned empty/unusable; relied on Most Bookmarks + known ids + WebSearch.

### Wildcards / workflows / LoRAs
```
types=Wildcards&sort=Most Liked|Highest Rated&period=AllTime|Year
types=Wildcards&query=SFW|fantasy|lighting|artist|wildcard|Dynamic Prompts
types=Workflows&query=character sheet|multi angle|outfit|Illustrious
types=LORA&query=character sheet|fantasy|armor|magic|lighting|Velvet Mythic|multi angle|outfit change
baseModels=Illustrious where noted
username not required (Velvet via query)
```

### Explicit quarantine
```
types=Wildcards&query=NSFW pose
types=LORA&baseModels=NoobAI&sort=Most Liked&period=Month
civitai.red /api/v1/models?query=WAI-illustrious
```

### WebSearch / external
- Illustrious / Danbooru tag order (SeaArt, Tensor.Art, WhatLab, Arctenox 23210)
- WAI rating tags (MonAI, lilting.ch v17 review)
- Animagine XL 4 Opt (CagliostroLab + HF README)
- NoobAI XL 1.1 (HF Laxhar README)

### Raw
`raw/batch3/` — articles_*.json, article_*.json, wildcards_*.json, wf_*.json, lora_*.json, explicit_*.json, red_wai_api.json, summary_batch3.json

## Batch 4 queries (~01:38–01:50 BST 2026-09-21)

UA: `LAS-scavenge/1.0`. Base: `https://civitai.com/api/v1/models` + `/articles`. No auth. No weight downloads. List/search only (`--data-urlencode`). Note: `types=Wildcard` is **invalid** on API (ZodError) — use `query=wildcard|…`.

### Wildcards / prompts
```
query=wildcard|Dynamic Prompts|wildcard Illustrious|wildcard Pony|artist wildcard|SFW prompt|danbooru wildcard|clothing/outfit/lighting/hair wildcard|tag list|Random SFW|fantasy core
```

### Workflows
```
types=Workflows&query=Illustrious|Animagine|Pony|NoobAI|character sheet|RealVis|SDXL photoreal|NSFW workflow
```

### RealVis / Animagine / stack
```
query=RealVisXL|RealVis|photorealistic SDXL|skin detail|cinematic lighting SDXL
query=Animagine XL 4|Animagine XL 4.0 Opt|Animagine stabilizer
types=LORA&baseModels=Illustrious|NoobAI|Pony + query=hands|anatomy|detail|style|artist|lighting|pose
types=LORA&baseModels=Illustrious|Pony|NoobAI&sort=Most Liked&period=Month
types=TextualInversion&query=negative
```

### Articles
```
GET /api/v1/articles?sort=Most Bookmarks&limit=30
query=prompt|Illustrious|wildcard|negative prompt|Animagine|realistic prompt
GET /api/v1/articles/{11432,2054,3527,17080,1250,23210}
```

### Explicit quarantine
```
query=NSFW wildcard|hentai pose|NSFW pose|NSFW prompt|NSFW MASTER|undress|ahegao
types=LORA&baseModels=NoobAI&period=Month
civitai.red … Illustrious|Pony|NoobAI&period=Month
```

### External HTML snapshots
MonAI WAI · HF Animagine XL 4.0 · Cagliostro Opt post · HF NoobAI 1.1 · RealVis model page

### Raw
`raw/batch4/` — wildcards_*.json, wf_*.json, articles_*.json, article_*.json, realvis_*.json, animagine_*.json, illu_*.json, noob_*.json, pony_*.json, explicit_*.json, red_*.json, summary_batch4.json
