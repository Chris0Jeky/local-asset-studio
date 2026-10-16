# QUEUE — LAS Create stack week-delta 2026-09-30

Hardware: RX 9070 XT **16GB**. Prefer FP8/GGUF; strip Sage/Triton/DLSS/RTX VSR/Nunchaku; `--use-pytorch-cross-attention`. No weight fetch in this research step. **Do not** flip Create presets until Desktop A/B wins.

Tracking: [#934](https://github.com/Chris0Jeky/local-asset-studio/issues/934) · pack continuity from `las-image-models-wave-2026-09-24/`.

---

## TRY (priority)

| # | name / id | type | base | VRAM | Create | NSFW | why | strength / notes | URL |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **QI-2.1 Consistency LoRA** `2969143` | LORA | Qwen 2.1 | tight | maybe | SFW | Highest NEW signal on QI-2.1 week charts (th≈103); identity/consistency gap for sheets + Create | start **0.6–1.0**; same-seed A/B vs no LoRA | https://civitai.com/models/2969143 |
| 2 | **QI-2.1 Outpaint LoRA** `2967375` + WF `2964810` | LORA+WF | Qwen 2.1 | tight | maybe | SFW | Week NEW extend-any-side utility; pairs with Edit lane | LoRA **0.7–1.0**; sanitize WF nodes | https://civitai.com/models/2967375 · https://civitai.com/models/2964810 |
| 3 | **QI-2.1 Turbo 8-step** `2967979` | LORA | Qwen 2.1 | tight | maybe | soft | Community few-step; **compare only** — Pruna 8-step stays **parked** (#934 2026-09-27 smoke) | strength per card; A/B vs base25 + parked Pruna | https://civitai.com/models/2967979 |
| 4 | **WAI-illustrious-Mix-FP8** `2451718` | Checkpoint | Illustrious | **fit** | yes/maybe | soft | AMD-friendly FP8 WAI mix; stack-match WAI v170 / Illu | smoke vs on-disk WAI; no preset flip | https://civitai.com/models/2451718 |
| 5 | **Blender Light Transfer 2511** `2397289` | LORA | Qwen | tight | maybe | SFW | Edit-2511 lighting craft delta vs LightingRemap `2305167` | **0.5–1.0**; Pruna-compare harness only | https://civitai.com/models/2397289 |
| 6 | **Klein FinalCut FP8/INT8** `2712664` | Checkpoint | Klein 9B | tight | maybe | soft | Quant path for Klein lane (#764 tree); prefer over BF16 | FP8/INT8 ConvRot first; unload LLM | https://civitai.com/models/2712664 |
| 7 | **Klein 9B Outpaint WF** `2964128` | Workflows | Klein 9B | tight | maybe | SFW | Week NEW Klein edit gap | strip NVIDIA nodes before import | https://civitai.com/models/2964128 |
| 8 | **Smooth Rotation Slider** `2714697` | LORA | Anima/Illu | fit | yes | soft | Craft utility (yaw) after Smooth Detailer; non-smut | **±0.3–0.7** | https://civitai.com/models/2714697 |

### Secondary TRY
| # | id | note |
|---|---|---|
| 9 | QI-2.1 Edit WFs `2962616` / `2965021` / `2969862` / `2966883` | Sanitize SageAttention; AMD strip |
| 10 | QI-2.1 TE Qwen3-VL 8B `2960962` | **Careful:** card says uncensored — smoke in Create only if age/content filters hold; else Uncensored quarantine |
| 11 | Pose changer WF `2031587` | Edit-2509 consistent pose; verify on 2511 |
| 12 | Versatile photo poses LoRA `2182923` | Edit pose utility |
| 13 | Ming Poster retro WF `2975857` | Note on #1174 only — Create = **no** until Ming INT8 AMD proven |

---

## SKIP
| ID | Item | Reason |
|---|---|---|
| SKIP-01 | Age-ambiguous / school-cast / loli-shota | Hard bound |
| SKIP-02 | Month Illustrious NSFW ckpt spam → SFW Create | Wrong lane → EXPLICIT |
| SKIP-03 | Revive Pruna 8-step as Create default | Parked 2026-09-27 (#934); TE eviction kills wall-clock |
| SKIP-04 | NVFP4 QI-2.1 `2957912` as AMD daily | Unverified on RDNA4; prefer pinned int8 library |
| SKIP-05 | MiniMax H3 / mega Flux dual WFs as Create default | VRAM / CUDA |
| SKIP-06 | DLSS / Sage / Triton / Nunchaku WFs unstripped | AMD unfit |
| SKIP-07 | Civitai Xinsir OpenPose weak mirrors | Keep HF Xinsir |

---

## PARK
| ID | Item | Why |
|---|---|---|
| PARK-01 | Pruna HF + Civitai mirrors `2962344` / `2969889` | Catalog OK; re-test at v0.2 or TE-resident path |
| PARK-02 | Krea2 Turbo FP8 `2723583` + Raw INT8 `2724771` | Uncensored park lane only — see EXPLICIT + #1176 |
| PARK-03 | Realism Yogi Krea2 `2786499` | PARK-08 family; not Create |
| PARK-04 | WAI-ANIMA `2544636` / WAI-SHUFFLE-NOOB `989367` | Popular; smoke later vs WAI v170 — not this week's A/B |
| PARK-05 | Klein Style Selector WF `2394566` | Low urgency |
| PARK-06 | Ming Design Layer / BF16 | #1174 already parks |
| PARK-07 | Z-Image daily Create | Separate family; 16GB budget |

---

## Smoke protocol (Create)
1. One lever per cell; record Studio job id + Comfy prompt id.  
2. Same seed when A/B’ing LoRA/WF.  
3. Unload Spoken Briefs / LLM on tight stacks.  
4. No graphic binaries in GitHub.  
5. Mark try→keep/park after craft score (identity · light · pose · hands).
