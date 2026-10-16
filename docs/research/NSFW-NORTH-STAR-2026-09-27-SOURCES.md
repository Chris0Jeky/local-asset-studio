# SOURCES — NSFW north-star research 2026-09-27 (BST)

## Prior LAS quarantine / measured craft
- `handoffs/civitai-scavenge-2026-09-21/BATCH3_EXPLICIT.md`, `BATCH4_EXPLICIT.md`, `SOURCES.md`
- `handoffs/las-image-models-wave-2026-09-24/EXPLICIT.md`
- `handoffs/las-pose-control-research-2026-09-21/` (#761 OpenPose/Union)
- Repo: `docs/research/CIVITAI-SCAVENGE-BATCH3-EXPLICIT-QUEUE-2026-09-21.md` (+ BATCH4 EXPLICIT)
- Repo: `experiments/curated/nsfw-lab-20260921/`, `nsfw-lab-20260923/` (TECHNIQUES, FINDINGS, INDEX, ORCHESTRATOR)
- Related issues: #756 era scavenges, #786, #988, #934/#936 EXPLICIT summary pattern, #761

## Civitai public list API (box curl 2026-09-27)
Base: `https://civitai.com/api/v1/models` · `.../images` · `.../articles`
UA: `LAS-Scavenger/1.0` · **nsfw=true / nsfw=X** · sort Most Liked / Most Reactions / Most Comments
**Avoided** model-by-id endpoints (CF 1015).
**Note:** image list responses returned IDs + reaction stats **without** generation `meta` on this date — recipes from model cards, articles, prior packs, lab.

Cached under `raw/`:
- `illu_ckpt_ml_month.json`, `illu_lora_ml_month.json`
- `pony_ckpt_ml_month.json`, `pony_lora_ml_month.json`
- `tag_nsfw_ckpt_ml.json`, `tag_nsfw_lora_ml.json`
- `images_most_react_month.json`, `images_most_react_year.json`, `images_most_comments_month.json`
- `wf_nsfw_ml.json`, `illu_lighting_lora.json`, `illu_pose_lora.json`, `detailer_hands.json`, `noob_ckpt_ml.json`
- `articles_nsfw_prompt.json`, `pose_wildcard.json`, `illu_skin_lora.json`, `wai_search.json`
- `top_images_index.json` (compact page index)

Mirrors: https://civitai.red/models/{id} when main blurs.

## Articles / guides
- Civitai articles `8547`, `4248`, `6555`, `23210`, `22181`, `17080`
- Pro Grade WF pages `2282970`, `2189190`
- Community ControlNet weight guides (OpenPose+Depth conservative weights, 2026 roundups)
- Illustrious prompting user guides (Euler a, Clip Skip 2, quality-tag order)
- Reddit r/StableDiffusion: ADetailer+Pony face-only prompt tip; Illustrious OpenPose quirks; AMD ADetailer notes

## What was not done
- No weight downloads · no merges · no cloud agents · no auto-publish · no secrets
- No model-by-id CF hammering
- No graphic binaries in pack
