# Try queue — LAS image models wave 2026-09-24

| # | name / id | type | base | VRAM fit | license | LAS Create | NSFW | try/skip/park | reason | URL |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **PrunaAI/Pruna-Qwen-Image-2.1 (8-step v0.1)** | Few-step LoRA | Qwen-Image-2.1 | **tight** (~320 MB LoRA + FP8/GGUF base; BF16 no) | **Qwen RESEARCH** | **maybe** (LoRA OK if Create loads QI-2.1; needs sigma/no-CFG path) | SFW | **try** | Default A/B: HF strength 1.0 + exact 8-step sigmas + no CFG vs OP strength 2 / 8 steps; compare vs base 40-step + 2511-lighting-8. Not a preset flip. | https://huggingface.co/PrunaAI/Pruna-Qwen-Image-2.1 |
| 2 | Same repo, 5-step v0.1 | Few-step LoRA | Qwen-Image-2.1 | tight | Qwen RESEARCH | maybe | SFW | **try** (secondary) | Max speed; HF says visibly worse than 8-step. | same |
| 3 | qwen3vl_8b_fp8_scaled TE | Text encoder | QI-2.1 | tight | unclear | maybe | SFW | **try** (with #1) | Reddit: best quality / less body horror with this TE. | community / HF zoos |
| 4 | Qwen-Edit-2511_LightingRemap `2305167` | LORA | Qwen | fit–tight | unclear | maybe | SFW | **try** (compare) | Closest Civitai “2511-lighting” signal for Pruna quality A/B. | https://civitai.com/models/2305167 |
| 5 | Qwen Image 2.1 Fix `2957332` | LORA | Qwen 2 | tight | unclear | maybe | soft | **try** | Week NEW quality/fix LoRA for QI-2.1 stack (#739/#760/#934). | https://civitai.com/models/2957332 |
| 6 | QI 2.1 Nvfp4 Q4 Q3 `2957912` | Checkpoint | Qwen 2 | **fit**/tight | unclear | maybe | soft | **try** | AMD 16GB-friendly quant path for base under Pruna. | https://civitai.com/models/2957912 |
| 7 | QI 2.1 Character Design Sheet Maker `2960750` | Workflows | Qwen 2.1 | tight | unclear | yes/maybe | **SFW** | **try** | Studio sheet gap on QI-2.1 (beyond evergreen `100435`). | https://civitai.com/models/2960750 |
| 8 | QI 2.1 Character Ref Sheet `2960890` | Workflows | Qwen 2 | tight | unclear | yes/maybe | **SFW** | **try** | Face+wardrobe+pose sheet; low thumbs, high LAS relevance. | https://civitai.com/models/2960890 |
| 9 | Lonecats QI 2.1 Fast WF `2960068` | Workflows | Qwen 2.1 | tight | unclear | maybe | soft | **try** (sanitize) | Fast path + upscalers; strip Sage/Triton/NVIDIA nodes before import. | https://civitai.com/models/2960068 |
| 10 | Qwen-Edit_Anime2Real `2110229` | LORA | Qwen | tight | unclear | maybe | soft | **try** | High-signal Edit style bridge (WAI↔real tests). | https://civitai.com/models/2110229 |
| 11 | anime2real-2511 `2287977` | LORA | Qwen | tight | unclear | maybe | soft | **try** | 2511-tagged anime→real; pairs with #10. | https://civitai.com/models/2287977 |
| 12 | qwen-edit-skin `2097058` | LORA | Qwen | tight | unclear | maybe | soft | **try** | Skin utility for Edit-2511 gallery quality. | https://civitai.com/models/2097058 |
| 13 | Qwen Edit Plus OpenPose 8 Steps `2030628` | Workflows | Qwen | tight | unclear | maybe | **SFW** | **try** | Pose bridge for Edit (Xinsir/OpenPose handoff); 2509-era — verify on 2511. | https://civitai.com/models/2030628 |
| 14 | Dark/Dim lighting `1711037` | LORA | Illustrious | **fit** | unclear | **yes** | soft | **try** | Night/low-key complement after Dramatic Lighting + `1280702` (not a replacement). | https://civitai.com/models/1711037 |
| 15 | Retro Neo Noir `1836542` | LORA | Illu/Krea2/ZIT/Flux | **fit** | unclear | **yes** | soft | **try** | Multi-base noir style; non-zura gap-fill. | https://civitai.com/models/1836542 |
| 16 | Klein IMG2IMG+Upscaler `2326676` | Workflows | Klein 9B | tight | unclear | maybe | **SFW** | **try** | Klein edit/upscale delta vs prior Ultimate/AIO set. | https://civitai.com/models/2326676 |
| 17 | Klein Inpaint Segment Ultimate `2331118` | Workflows | Klein 9B | tight | unclear | maybe | **SFW** | **try** | Segment/inpaint gap on Klein (#764 tree). | https://civitai.com/models/2331118 |
| 18 | Add Lighting 2511 Multi/Single `2291445` / `2291406` | Workflows | Qwen | tight | unclear | maybe | **SFW** | **park** | Low thumbs; keep as Pruna compare harness, not daily. | https://civitai.com/models/2291445 |
| 19 | QI 2.1 bf16 mirror `2953241` | Checkpoint | Qwen 2 | **no** | unclear | no | soft | **park** | BF16 too heavy for 16GB daily; use quants. | https://civitai.com/models/2953241 |
| 20 | Civitai Xinsir OpenPose `2943879` | Controlnet | SDXL | fit | unclear | no | soft | **skip** | Weak mirror; keep HF Xinsir. | https://civitai.com/models/2943879 |
| 21 | Mac DLSS Neural Re-Detailer `2925631` | Upscaler | — | n/a | unclear | no | soft | **skip** | DLSS/Mac lineage — not AMD Create path. | https://civitai.com/models/2925631 |
| 22 | KleiNova NSFW Klein `2547526` | Checkpoint | Klein 9B | tight | unclear | no | explicit | **skip** (SFW) | Quarantine → EXPLICIT.md | https://civitai.com/models/2547526 |
| 23 | Month Illustrious NSFW ckpt spam | Checkpoint | Illustrious | varies | unclear | no | explicit | **skip** | See EXPLICIT.md (One obsession, Harem, WAI-Mature, …) | — |
| 24 | QI 2.1 AIO Xiaozhi NSFW `2960228` | Workflows | Qwen 2.1 | tight | unclear | no | NSFW-lean | **skip** SFW | EXPLICIT / adult WF lane only | https://civitai.com/models/2960228 |

**Do not** flip LAS Create default presets until A/B wins on DESKTOP. Tracking: [#934](https://github.com/Chris0Jeky/local-asset-studio/issues/934).

**Reddit extract:** scored (rows 1–4 + TE). Seed files preserved.
