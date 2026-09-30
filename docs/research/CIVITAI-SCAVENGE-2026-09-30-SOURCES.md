# SOURCES — Civitai week-delta 2026-09-30 (BST)

## Rules
- Public Civitai API only: `https://civitai.com/api/v1/models`
- User-Agent: `Mozilla/5.0 (compatible; LAS-scavenge/2026-09-30)`
- **No API tokens / secrets**
- **No weight downloads** (HF HEAD for size/etag only)
- List/search only — **avoided model-by-id** (CF 1015 risk)
- NSFW quarantine docs named EXPLICIT_* ; never SFW preset paths

## Scrape window
~23:44–23:47 BST 2026-09-30 (Europe/London, UTC+1) · follow-ups to ~23:47

## Prior packs read
- `/workspace/handoffs/nsfw-north-star-2026-09-27/` (PARKED_KREA2 · QUEUE · MODEL_SHORTLIST · COMPRESSED · SOURCES)
- `/workspace/handoffs/las-image-models-wave-2026-09-24/` (QUEUE · COMPRESSED · SOURCES · #934 Pruna park)
- `/workspace/handoffs/civitai-scavenge-2026-09-23/` + `…-2026-09-21/`
- `/workspace/handoffs/ming-image-design-2026-09-27/`
- Prior exclusion union → `raw/_prior_ids.txt` (**382** ids)

## GitHub context
- https://github.com/Chris0Jeky/local-asset-studio/issues/1176
- https://github.com/Chris0Jeky/local-asset-studio/issues/934 (Pruna parked 2026-09-27 comment)
- https://github.com/Chris0Jeky/local-asset-studio/issues/1174
- Draft PR prior pattern: #1177 / #936 docs under `docs/research/`

## Civitai queries (snapshots under `raw/`)

### Illustrious / Noob / Pony / SDXL
```
types=LORA&baseModels=Illustrious&sort=Highest%20Rated|Most%20Liked&period=Week|Month&limit=20
types=Checkpoint&baseModels=Illustrious&sort=Most%20Liked&period=Month|Week&limit=15
types=LORA&baseModels=NoobAI|Pony|SDXL%201.0&sort=Most%20Liked&period=Month&limit=20
types=Checkpoint&baseModels=Pony|NoobAI&sort=Most%20Liked&period=Month
types=LORA|Workflows&sort=Newest&period=Week&limit=20
```

### Qwen / Klein / Z-Image / Krea
```
query=Qwen%20Image%202.1&sort=Most%20Liked|Newest&period=Month|Week
query=Qwen%20Edit&sort=Most%20Liked&period=Month|Year
types=Workflows&query=Qwen&sort=Most%20Liked&period=Year|Month
query=2511%20lighting&sort=Most%20Liked&period=Year
query=Klein|FLUX.2%20Klein&sort=Most%20Liked&period=Month|Year
types=Workflows&query=Klein&sort=Most%20Liked&period=Month
query=Z-Image%20Turbo&sort=Most%20Liked&period=Year
types=Workflows&query=Z-Image&sort=Most%20Liked&period=Month
query=Krea&sort=Most%20Liked&period=Month|Week
query=Krea2%20Turbo|Realism%20Engine%20Krea|Realism%20Yogi%20Krea|TextFusion%20Krea
query=FinePorn|SNOFS|FineCorn → empty items (documented)
```

### Craft / NSFW quarantine / stack
```
types=LORA|Checkpoint&tag=nsfw&sort=Most%20Liked&period=Month&nsfw=true
query=WAI%20Illustrious|WAI-Mature|WAI%20FP8
types=LORA&baseModels=Illustrious&query=lighting|skin|hands|Smooth%20Detailer
query=NSFW%20Pose%20Wildcard|character%20sheet|Pixel%20Art%20XL|Xinsir|Animagine|RealVis|Pruna|Qwen%20GGUF|FP8%20Illustrious
types=Workflows&query=AMD&sort=Most%20Liked&period=Year
types=Controlnet&sort=Most%20Liked&period=Month
```

### Thin / empty (documented)
```
FinePorn / SNOFS / FineCorn → {"items":[],"metadata":{}}
Pixel Art XL · some Controlnet month · Qwen Edit Month → empty or tiny
```

## Hugging Face (no weight body)
- https://huggingface.co/PrunaAI/Pruna-Qwen-Image-2.1
- README cached: `raw/hf_pruna_README.md` (license_name: qwen-research)
- HEAD 8-step: `x-linked-size: 335606104` · etag `f0865d68…` (matches #934 smoke hash)

## Raw artifacts
- `raw/*.json` — list snapshots
- `raw/_prior_ids.txt` — exclusion
- `raw/_curated_new.json` — scored NEW pool
- `raw/hf_pruna_README.md`

## What was not done
- No weight downloads · no merges · no by-id CF hammering · no graphic binaries · no SFW preset flips · no secrets
