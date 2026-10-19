# FINDINGS — Ming Image Design family (2026-09-27 BST)

**Audience:** Chris Local Asset Studio (LAS) → docs PR into `Chris0Jeky/local-asset-studio`
**GPU:** AMD RX 9070 XT **16GB** · 32GB system RAM · Comfy portable · LAS Create
**Tracking:** [#1174](https://github.com/Chris0Jeky/local-asset-studio/issues/1174) (cross-links #739 / #760 / #934 / #1028)
**Rule:** Page URLs + metadata + HEAD sizes only. **No weight downloads. No secrets. No merges. No cloud agents.**

**Delta vs prior packs:** New family — not a Civitai week-scavenge. Do **not** rehash Pruna / QI-2.1 / Illu / Klein rows from `las-image-models-wave-2026-09-24` or civitai 09-21/09-23.

---

## 0. Provenance and reconciliation (added 2026-10-19, issue #1324)

**Labels.** Unlabelled statements in sections 1–7 are **dated observations from 2026-09-27**. Items marked **[current 2026-10-19]** were read again on 2026-10-19 from the Hugging Face model API and tree API. The [current evidence directory](evidence/ming-image-2026-10-19/README.md) now retains nine raw responses, full revision pins and a dated URL/size/SHA-256 receipt manifest. Nothing here downloads weights. Historical wording is retained with explicit corrections; the missing September files are not reconstructed from current responses.

**Precision and parameter count (the open question on 2026-09-27).** **[current 2026-10-19]**

| Repo | API `safetensors` total params | API stored dtype | Tensor bytes implied by count/dtype | Current file bytes |
|---|---|---|---|---|
| `inclusionAI/Ming-Image-0.1-Design` | 6,154,901,056 | BF16 only | 12,309,802,112 | 12,309,858,144 across five transformer shards |
| `inclusionAI/Ming-Image-0.1-Design-Layer` | 6,154,908,736 | **F32 only** | 24,619,634,944 | 24,619,690,768 across nine transformer shards |
| `Comfy-Org/Ming-Image` `diffusion_models/ming_image_0.1_design_layer_bf16.safetensors` | not published per file | not independently read | not established from this file | 12,309,874,192 |

The [retained model and tree responses](evidence/ming-image-2026-10-19/README.md#revision-pins-and-retained-responses) pin Design to `c57c49689d12ef7d4e24a170014f1dc43d3ce258`, Layer to `ff1b22d2bdd0ae6597c0024a42cac7923b24cf92`, and Comfy to `93804ff3747517a318969c5f61b25a57daefe09f`. Official file totals exclude configuration/index files and every non-transformer component. Parameter counts/dtype come from the API summary, not a locally parsed header.

Reading of these numbers:

- The official Layer DiT is **F32 storage of about 6.15 billion parameters**. The 2026-09-27 "~12.31B" parameter figure for Layer was an arithmetic guess that assumed BF16 bytes; it is wrong. Layer's reported count is 7,680 above Design's; both are approximately 6.15 billion.
- The 24.62 GB size is correct as a size. The "BF16" label on it (TLDR item 3, section 2) is not the stored dtype. The model card recommends BF16 for inference, which is a runtime choice.
- The Comfy file `design_layer_bf16` is 12,309,874,192 bytes, 56,720 bytes above the official Layer count at two bytes per parameter. The 2026-09-27 "discrepancy" is therefore consistent with **dtype and packaging** (F32 official storage versus a BF16 repack). This is an **inference from byte sizes**: the Comfy file's own header was not read, and the retained Comfy API response supplies no per-file safetensors breakdown. The arithmetic does not prove the tensor inventory or numerical equivalence.
- The 2026-09-27 "65.20 GB" and "52.88 GB" totals are sums of the recorded component sizes, rounded to two decimals; they are not re-measured here.

**Not verified, and what this changes.**

- Not known: the Comfy Layer file's own dtype, parameter inventory or numerical equivalence to the official weights; its safetensors header and tensors were not read. Byte identity or equal LFS hashes would be the wrong test for a sharded F32 original versus a single-file BF16 conversion, because conversion and repackaging change bytes.
- Now retained: current full revisions and every file's advertised LFS identifier/size in the [raw tree responses](evidence/ming-image-2026-10-19/README.md). The Comfy Layer BF16 entry advertises SHA-256 `31c588e279f0dd461d3366ae7e21b4a0f6926fbc8b5a1f6580ab899a761be34a`; the nine official Layer shard identifiers are separately recorded. These are metadata identities, not locally verified weight hashes.
- Still unavailable: the historical raw HEAD/tree files that SOURCES named (`raw/comfy-org-head-sizes.txt`, `raw/hf-*.json`) and the operator handoffs pack. The September numbers remain dated observations. The new evidence supports current measurements only.
- Changed: the Layer footprint row "BF16 DiT alone 24.62 GB" was computed from the F32 size. If the Comfy Layer file really is the same parameters at BF16, a BF16 Layer DiT would be about 12.31 GB, not 24.62 GB. The fit row is therefore not re-decided here.
- **Unchanged: the Layer park verdict** (section 7). Its condition (a) still needs separately authorized tensor/header qualification; text-encoder residency, offload, consumer-GPU execution and art quality were not evaluated. Metadata does not satisfy those acceptance conditions.

## Executive TLDR

1. **Ming-Image-0.1-Design + Design-Layer** (inclusionAI / Ant Group) — MIT, HF + GitHub, design-first T2I + layer decompose. **Not** a general anime/photo replacement for WAI / Pony / RealVis / QI-2.1.
2. **"6B" is the DiT only.** Design package **52.88 GB** BF16; Layer **65.20 GB**. Multimodal TE (**~34 GB**) + connector (**~6.2 GB**) dominate disk and VRAM.
3. **"12GB / 24GB" shorthand** = Design DiT **12.31 GB** vs Layer DiT **24.62 GB** (BF16), **not** validated consumer VRAM. *Correction [current 2026-10-19, §0]: the 24.62 GB Layer DiT is F32 storage of ~6.15B parameters (the card's stored dtype); BF16 is the recommended inference precision.*
4. Official validate: **1× CUDA GPU ≥ 80 GiB**, BF16, 12 steps. Consumer BF16: **no** on 16/24/32/48 GB cards.
5. Comfy path exists: **ComfyUI PR [#16482](https://github.com/Comfy-Org/ComfyUI/pull/16482) MERGED 2026-09-24**; weights at `Comfy-Org/Ming-Image` (moved from `Kijai/Ming-Image-ComfyUI`).
6. Consumer quants today: **INT8 ConvRot** DiT ~**6.18 GB**; TE INT8 ~**19.5 GB** or **w4a8 ~12.8 GB**; VAE ~0.25 GB. Still needs **Dynamic VRAM / offload** on 16GB.
7. **vs Qwen-Image / Edit-2511:** Ming wins on UI/UX design Elo (open-weights arena ~1082) and MIT license; QI-2.1 remains the general T2I/edit daily. Layer-decomp reported stronger than open Qwen-Image-Layered on Crello.
8. **AMD risks:** INT8 ConvRot on **gfx1201** has had NaN/black-image and Triton/HIP issues historically; LAS rule prefers FP8/GGUF and stripping Triton — **Ming has no FP8/GGUF consumer story yet**.
9. **Verdict:** Design (12GB DiT) → **try** Comfy smoke only. Layer (24GB DiT) → **park**. Create-tab → **no** until smoke + AMD INT8 path proven.

---

## Scoring columns

| Field | Values |
|---|---|
| VRAM fit | `fit` · `tight` · `no` (16GB AMD practical) |
| License | `ok` · `hobby-NC` · `unclear` · `blocked` |
| LAS Create-tab | `yes` · `maybe` · `no` |
| NSFW | `SFW` · `soft` · `NSFW-capable` · `explicit` |
| Disposition | `try` · `skip` · `park` |

---

## 1. What it is

| Item | Detail |
|---|---|
| Org | inclusionAI (Ant Group / Bailing·Ming family) |
| Release | Weights quiet ~2026-09-17; public card/package ~2026-09-22/23 |
| License | **MIT** (HF card + LICENSE) |
| Design | Text → complete layouts (UI screens, dashboards, infographics, posters); native **RGBA** |
| Layer | Image + layer plan → **2–9** standalone RGBA PNGs (+ recompose) |
| Architecture notes | DiT ~30L / 3840-d / 16ch / 2×2 patch (community); Kijai: **Z-Image-derived DiT + new VL text encoder**; Ling-mini 2.0 TE in Comfy packs |
| Buckets | Design: 1024 / **2048** (recommended); Layer: 512 / **1024** working |
| Defaults | Design: 12 steps, CFG **1.0**; Layer: 12 steps, CFG **2.0** |
| PE | Official prompt rewrite via `Ling-3.0-flash-VL` or `qwen3.8-27B` |

**RGBA tip:** Prepend exactly one documented transparency phrase (same pattern as QI-2.1 transparency mode).

---

## 2. Disk / VRAM math (metadata HEAD + HF tree — no body download)

### Official inclusionAI trees

| Component | Design | Design-Layer |
|---|---|---|
| transformer (DiT) | **12.31 GB** (~6.15B) | **24.62 GB** (~12.31B as dated 2026-09-27; *corrected [current 2026-10-19, §0]: 6,154,908,736 parameters, stored F32*) |
| mllm (TE) | 34.02 GB (~17B) | 34.02 GB (shared) |
| connector | 6.17 GB (~3.09B) | 6.17 GB |
| vae | 0.25 GB | 0.25 GB |
| mlp | 0.12 GB | 0.12 GB |
| **Total** | **52.88 GB** | **65.20 GB** |

### Comfy-Org / Ming-Image single-file (HEAD)

| File | Size |
|---|---|
| `ming_image_0.1_design_bf16.safetensors` | 12.310 GB |
| `ming_image_0.1_design_int8_convrot.safetensors` | **6.175 GB** |
| `ming_image_0.1_design_layer_bf16.safetensors` | 12.310 GB ⚠️ |
| `ming_image_0.1_design_layer_int8_convrot.safetensors` | 6.175 GB ⚠️ |
| `ming_image_0.1_ling_mini_2.0_bf16.safetensors` | 36.678 GB |
| `ming_image_0.1_ling_mini_2.0_int8_convrot.safetensors` | **19.508 GB** |
| `ming_image_0.1_ling_mini_2.0_w4a8.safetensors` | **12.814 GB** |
| Layer TE bf16 / int8 | same 36.678 / 19.508 GB |
| `ming_image_vae_bf16.safetensors` | 0.254 GB |

⚠️ **Dated discrepancy wording:** Official Layer DiT is **24.62 GB**; Comfy-Org `design_layer_bf16` HEAD is **12.31 GB** (same rounded size as Design). *Correction [current 2026-10-19, §0]: the size is consistent with ~6.15B parameters stored at BF16 against official F32 storage. Current revision-pinned sizes and advertised LFS identities are retained. The Comfy header, tensor mapping and runtime remain unqualified; matching hashes between different storage representations is not required or expected.*

### Fit on RX 9070 XT 16GB

| Stack | Approx weights | Practical fit |
|---|---|---|
| Design BF16 full | ~53 GB | **no** |
| Design INT8 DiT + INT8 TE + VAE | ~6.2 + 19.5 + 0.25 ≈ **26 GB** | **no** fully resident; offload required |
| Design INT8 DiT + w4a8 TE + VAE | ~6.2 + 12.8 + 0.25 ≈ **19.3 GB** | **tight** — Dynamic VRAM + 32GB RAM offload only |
| Layer BF16 DiT alone | 24.62 GB | **no** |
| Official validate | 80 GB CUDA | n/a desktop |

*[current 2026-10-19, §0]: the "Layer BF16 DiT alone 24.62 GB" row is the F32-stored size. A BF16 Layer DiT of the same parameters would be about 12.31 GB, unmeasured; this row is not re-decided here.*

Community (NVIDIA RTX 4070 12GB) reports **training** LoRAs via AI-Toolkit INT8 + full layer offload — inference smoke on AMD 16GB is plausible but **unproven**.

---

## 3. Quality vs current LAS lanes

| Lane | Role today | Ming relation |
|---|---|---|
| WAI Illustrious v170 / NoobAI / Pony V6 / Animagine XL4 | Anime / illustration daily | **Orthogonal** — keep |
| RealVis V5 | Photo-real | **Orthogonal** |
| FLUX.2 Klein FP8 | Edit / general | Overlap on posters only; Klein stays edit daily |
| Z-Image Turbo | Fast general | Ming DiT described as Z-Image-derived — different TE + design training |
| **Qwen-Image-2.1** | General T2I + RGBA | **Peer but different**: QI general; Ming design-layout specialist; QI Research license vs Ming **MIT** |
| **Qwen-Image-Edit-2511** | Edit | Ming Design is gen-first; Layer is decompose, not multi-ref edit |
| Pixel Art XL | Pixel niche | No overlap |
| Pruna QI-2.1 few-step (#934) | Speed on QI | Unrelated; keep QI speed track separate |

**Arena signal (UI/UX Design open-weights slice, Artificial Analysis):** Ming Design ~**1082 Elo** (top at publish; wide CI). Measures layout/text — **not** general T2I.

**Layer vs Qwen layered (Crello, from secondary reporting):** Ming Layer (CLEAR-1024) ahead of open Qwen-Image-Layered; close to closed Crello-finetuned Qwen layered.

---

## 4. ComfyUI / workflow notes

- Core: ComfyUI **PR #16482 merged 2026-09-24** (`feat: ming-image support`) — need Comfy build **≥ that merge**.
- Weights: `https://huggingface.co/Comfy-Org/Ming-Image` (Kijai repo redirects here).
- Placement: `diffusion_models/` + `text_encoders/` + `vae/` as card lists.
- Early community: LCM smooth but soft; INT8 still has random text failures; bbox-style prompts help; Layer packaging historically delayed (extra TE/projector complexity).
- AMD launch flags: `--use-pytorch-cross-attention`; **do not** import Sage/DLSS/RTX VSR/Nunchaku nodes.
- **Triton tension:** LAS strip-Triton rule vs INT8 ConvRot needing HIP/Triton kernels on ROCm — document as smoke risk; prefer eager/HIP-native if available; black/NaN history on gfx1201 INT8 DiT paths.

---

## 5. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| TE dominates VRAM | High | w4a8 TE + Dynamic VRAM; never BF16 TE on desktop |
| No FP8/GGUF yet | High | Park daily; only INT8 ConvRot try |
| AMD INT8 ConvRot instability | High | Smoke small 1024; abort on NaN/black; no Create pin |
| Layer Comfy size ≠ official DiT | Medium | Park Layer until audit |
| Design ≠ character gen | Medium | Do not put in anime Create presets |
| Prompt enhancer extra VRAM | Medium | Skip PE on first smoke |
| Disk pressure (~20–53 GB) | Medium | Prefer INT8+w4a8 only; no Layer download |
| Cloud API temptation | Low | Local-first; skip OpenRouter for LAS |

---

## 6. Scored FINDINGS rows

| # | Item | VRAM | License | Create | NSFW | Disp |
|---|---|---|---|---|---|---|
| F1 | Design INT8 + w4a8/INT8 TE (12GB DiT lane) | tight | **ok (MIT)** | no | SFW | **try** |
| F2 | Design BF16 full | no | ok | no | SFW | **skip** |
| F3 | Design-Layer (24GB DiT lane) | no | ok | no | SFW | **park** |
| F4 | Comfy Layer INT8 (unverified size) | unclear | ok | no | SFW | **park** |
| F5 | Official CUDA infer / FA2 | no | ok | no | SFW | **skip** |
| F6 | AI-Toolkit LoRA train (NVIDIA 12GB report) | train-only | ok | no | SFW | **park** |

---

## 7. Clear recommendation for Chris

- **Try (Design / 12GB DiT):** After Comfy includes #16482, optional **metadata-only bookmark** of Comfy-Org INT8 DiT + w4a8 TE + VAE. Smoke 1024, CFG 1.0, 12 steps, pytorch-cross-attention, Dynamic VRAM on. Compare one UI-poster prompt vs QI-2.1 / Klein for layout text — **quality curiosity only**. No Create preset. No BF16.
- **Park (Layer / official F32 24GB DiT):** Dated conditions were (a) qualifying the Comfy Layer tensor inventory, (b) TE ≤~8–10GB quant or a strong offload recipe on gfx1201, or (c) dual-GPU availability. *[current 2026-10-19, §0]: the official count (~6.15B, F32), revision-pinned file sizes and advertised hashes are retained. The Comfy file's actual header/tensor mapping and consumer runtime remain unqualified, so the verdict stands; this metadata pass did not re-evaluate the other conditions.*
- **Do not** displace QI-2.1 / Edit-2511 / Illu daily lanes.
