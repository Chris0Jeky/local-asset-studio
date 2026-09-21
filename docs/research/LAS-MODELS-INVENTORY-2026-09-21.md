# LAS / Comfy model inventory — 2026-09-21

**Studio:** `C:\Users\jekyt\source\local-asset-studio`  
**Comfy:** `C:\AI\ComfyUI_windows_portable\ComfyUI` (`config/local.json`)  
**GPU context:** RX 9070 XT 16 GB (VRAM arbitration vs Spoken Briefs / local LLM)

Weights are **not** in git; LAS `models/installed-manifest.json` is the curated registry. Live Comfy `models/` has additional downloads beyond that registry.

## Curated registry (manifest — all verified present on disk)

### Checkpoints (SDXL family)
| File | Notes |
|------|--------|
| sd_xl_base_1.0 | base |
| animagine-xl-4.0-opt | anime |
| NoobAI-XL-v1.1 | hobby/research; **non-commercial** per card |
| pony-diffusion-v6 | pony |
| RealVisXL_V5.0_fp16 | realistic |
| waiIllustriousSDXL_v170 | WAI Illustrious (HF mirror; commercial terms unresolved) |

### Also on disk (checkpoints, beyond curated note)
- novaAnimeXL_ilV190, yumefluxXLIllustrious_ilV10, cstatiANIMEV30XL_v30, anifoxXLV20_anifoxV2
- hunyuan_3d_v2.1 (~6.9 GB)
- Incomplete `.part` leftovers for anifox (cleanup candidate)

### Diffusion / DiT / video-ish
| File | Role |
|------|------|
| flux-2-klein-4b-fp8 | FLUX.2 Klein 4B |
| flux-2-klein-9b Q6/Q8 GGUF | Klein 9B |
| flux2-dev-Q4_K_M.gguf | FLUX.2 dev (~19 GB) — runtime unverified on this GPU |
| z_image_turbo_bf16 (+ fp8_scaled) | Z-Image Turbo |
| qwen-image-edit-2511-Q4_K_M.gguf | **Qwen Image Edit 2511** |
| krea2_turbo_fp8_scaled | Krea2 turbo |
| wan2.2_ti2v_5B_fp16 | Wan TI2V |
| minimax_h3_fl2va_pruned_int8_convrot | MiniMax H3 |
| trellis_2_int8_convrot | Trellis |
| anima / JANIMA / oneObsession / pearlyAnimaMix | Anima family |

### Text encoders / VAE
- qwen_3_4b, qwen_2.5_vl_7b_fp8_scaled, Mistral-Small-3.2-24B Q4_K_M
- flux2-vae, qwen_image_vae, z_image ae

### LoRAs (86 files — highlights)
- **Qwen:** Edit-2511 Lightning 4-step; qwen-image-edit-2511-multiple-angles
- **Speed:** Hyper-SDXL-8steps-CFG; krea2_turbo_4step; minimax H3 turbo 8-step
- **Edit/style:** AniEdit9B_v2, AniEdit-Klein4B; large **krea2_*** + **fal-krea2-*** style pack (~20+)
- **Other:** pixel-art-xl; anime_style_v1_zimage; Konosuba Fantastic Days; NIJISIS_KREA; realism_engine_krea2; nsfw_girls (flag)
- Incomplete: krea2_turbo-Q5_K_M.gguf.part

### Control / IP-Adapter / upscale / detail
- ControlNet: xinsir-openpose-sdxl, xinsir-union-sdxl-1.0
- IP-Adapter SDXL vit-h (+ plus / plus-face)
- Upscale: RealESRGAN_x4plus_anime_6B, 4x_NMKD-Superscale, OmniSR X2/X3/X4
- Anime detailing: Impact Pack nodes + face/hand yolov8 (adetailer)

## License / policy flags
- NoobAI: non-commercial including generated products
- WAI: commercial/auth terms unresolved
- Always treat NSFW LoRAs as explicit-queue only (align with local LLM Uncensored policy)

## Gaps vs seeded interest
- **Qwen-Image-2.1** not in Comfy yet — LAS #739 (have Edit-2511 + Lightning + angles LoRA)
- FLUX.2-dev Q4 present but “runtime inference remains unverified”
- Huge LoRA sprawl (esp. krea2) → good Civitai scavenger target: which combos actually pair with WAI/NoobAI/Pony/Animagine vs orphaned

## Related
- Civitai FINDINGS: `docs/research/CIVITAI-SCAVENGE-2026-09-21.md`
