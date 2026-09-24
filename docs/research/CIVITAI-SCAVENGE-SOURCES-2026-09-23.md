# SOURCES — Civitai scavenge 2026-09-23 (BST)

## Rules
- Public Civitai API only (`https://civitai.com/api/v1/models`)
- User-Agent: `Mozilla/5.0 (compatible; LAS-scavenge/2026-09-23)` / `LAS-scavenge` variants
- **No API tokens / secrets**
- **No weight downloads**
- List/search only (no reliable model-by-id; CF 1015 risk)

## Queries used (snapshots under `raw/`)

### Week / Month Illustrious LoRA
```
types=LORA&baseModels=Illustrious&sort=Highest%20Rated&period=Week&limit=20
types=LORA&baseModels=Illustrious&sort=Most%20Liked&period=Week&limit=20
types=LORA&baseModels=Illustrious&sort=Highest%20Rated&period=Month&limit=20
types=LORA&baseModels=Illustrious&sort=Most%20Liked&period=Month&limit=20
```
→ `ill_lora_hr_week.json`, `ill_lora_ml_week.json`, `ill_lora_hr_month.json`, `ill_lora_ml_month.json`

### Noob / Pony / SDXL Month
```
types=LORA&baseModels=NoobAI&sort=Most%20Liked&period=Month&limit=20
types=LORA&baseModels=Pony&sort=Most%20Liked&period=Month&limit=20
types=LORA&baseModels=SDXL%201.0&sort=Most%20Liked&period=Month&limit=20
types=Checkpoint&baseModels=Illustrious&sort=Most%20Liked&period=Month&limit=15
```

### Qwen / Klein / Z-Image / Krea (Year + Month + Newest Week)
```
query=Qwen-Image&sort=Most%20Liked&period=Year&limit=20
query=Qwen-Image-Edit&sort=Most%20Liked&period=Year&limit=20
types=Workflows&query=Qwen&sort=Most%20Liked&period=Year&limit=20
query=Qwen%20Image%202.1&sort=Most%20Liked&period=Month&limit=20
query=FLUX.2%20Klein&sort=Most%20Liked&period=Year&limit=20
types=Workflows&query=Klein&sort=Most%20Liked&period=Month&limit=20
query=Z-Image%20Turbo&sort=Most%20Liked&period=Year&limit=20
types=Workflows&query=Z-Image&sort=Most%20Liked&period=Month&limit=20
query=Krea&sort=Most%20Liked&period=Month&limit=20
types=Workflows&sort=Newest&period=Week&limit=20
types=LORA&sort=Newest&period=Week&limit=20
```

### Gap / sheet / consistency / creators
```
types=LORA&baseModels=Illustrious&query=lighting|skin|eyes&sort=Highest%20Rated&period=Year
query=character%20sheet|character%20design%20sheet&sort=Most%20Liked&period=Month|Year
query=consistency|multi%20reference|Multiple-Angles
query=Consistence%20Edit&sort=Most%20Liked&period=Year
query=Klein%20Qwen%20edit&sort=Most%20Liked&period=Year
username=zura_janai|Zoropaton|bakariso|lonecatone23|YeiYeiArt
types=Workflows&query=AMD&sort=Most%20Liked&period=Year
```

### Thin / empty (documented)
```
baseModels=SDXL%201.0&query=Animagine&period=Month → 0 items
query=RealVis&period=Month → 0 items
types=LORA&baseModels=Flux.2&period=Month → 0 items (use query=FLUX.2%20Klein instead)
```

## WebSearch (signals only; no weights)
- Civitai Illustrious Week / Qwen-Image-Edit / Klein dual WF pages
- ComfyUI Qwen-Image-Edit-2511 docs
- AMD ROCm ComfyUI FA backends · Comfy-Org#9910 gfx1201 `--use-pytorch-cross-attention`
- localaimaster ComfyUI AMD ROCm fixes (strip Sage/Triton guidance)

## Prior exclusion list
- 138 model ids from `/workspace/handoffs/civitai-scavenge-2026-09-21/FINDINGS.md` saved to scrape-time `/tmp/prior_ids.txt`

## Raw artifacts
- `raw/*.json` — API snapshots
- `raw/_primary_rows.json` — curated NEW rows for this wave
- `raw/_curated_new.json` — broader NEW pool
