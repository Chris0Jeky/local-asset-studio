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
