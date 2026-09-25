# Qwen Image Edit 2511: primary-backend stack

Issue #760. Companion to [QWEN-IMAGE-21.md](QWEN-IMAGE-21.md); the 2.1 backend issue is #739.

> Note on #760's premise: it assumes Qwen-Image 2.1 is not installed. That is stale.
> 2.1 runs on the isolated `qwen21` backend (ComfyUI v0.37.0, port 8196) with an
> installed int8 pack and 23 September Studio proofs — see [QWEN-IMAGE-21.md](QWEN-IMAGE-21.md).
> This page documents the Edit-2511 stack as it exists; the two must not be mixed (below).

Edit 2511 is the 20B instruction-edit model. It runs on the **primary** backend
(ComfyUI v0.35.0, port 8188) as a GGUF quantization, not on the isolated 2.1 backend.

## Recipes (repository)

| Preset | API graph | Visual graph |
| --- | --- | --- |
| `qwen` | `workflows/api/qwen-api.json` | `workflows/comfyui/06 - Qwen Edit 20B Q4.json` |
| `qwen-quality` | `workflows/api/qwen-quality-api.json` | `workflows/comfyui/16 - Qwen Slow Quality Edit.json` |
| `qwen-character` | `workflows/api/qwen-character-api.json` | No visual graph bound in the catalog |
| `qwen-1ref` | `workflows/api/qwen-1ref-api.json` | `workflows/comfyui/50 - Qwen Atelier - 1 Reference.json` |
| `qwen-2ref` | `workflows/api/qwen-2ref-api.json` | `workflows/comfyui/51 - Qwen Atelier - 2 References.json` |
| `qwen-3ref` | `workflows/api/qwen-3ref-api.json` | `workflows/comfyui/52 - Qwen Atelier - 3 References.json` |

Bindings live in `presets/catalog.json` (family `Qwen Image Edit 2511`). The atelier
recipes scale every reference to 1.0 MP (lanczos, aspect preserved) and set the canvas
explicitly (`EmptySD3LatentImage`, 832x1248 default); output size is independent of the
references. All three atelier presets carry `verified: false` in the catalog.
`qwen-quality` is a separate, unverified 40-step experiment **without** Lightning;
the four-step settings below describe the other listed recipes.

## Component identities (pinned in `models/library.json`)

| Piece | File | Pin |
| --- | --- | --- |
| Backbone | `diffusion_models/qwen-image-edit-2511-Q4_K_M.gguf` (13,244,758,624 B) | `unsloth/Qwen-Image-Edit-2511-GGUF` rev `0d33d969`, SHA-256 `8677bac9…` (`qwen-image-edit-2511-q4-gguf`) |
| Text encoder | `text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors` | `Comfy-Org/Qwen-Image_ComfyUI` rev `7beb7b64` (`qwen25-vl-7b-fp8-encoder`) |
| VAE | `vae/qwen_image_vae.safetensors` | loaded by `VAELoader` (node 3) in every atelier graph |
| Lightning 4-step LoRA | `loras/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors` (849,608,296 B) | `lightx2v/Qwen-Image-Edit-2511-Lightning` rev `d74eba14`, SHA-256 `22226e8d…` (`qwen-edit-2511-lightning-4step`), strength 1.0 |
| Multiple-Angles LoRA | `loras/qwen-image-edit-2511-multiple-angles-lora.safetensors` | `fal/...` rev `e3066224` — pinned but referenced by **no** preset, graph or recipe (`docs/research/LORA-DISK-AUDIT-2026-09-23.md`); its trigger/scale are unproved here |

## Loader order and Lightning settings (as authored)

Inspected in `workflows/api/qwen-2ref-api.json`; the other atelier graphs repeat the pattern:

1. `UnetLoaderGGUF` (node 1) loads the Q4 backbone.
2. `LoraLoaderModelOnly` (node 8) applies the Lightning LoRA at `strength_model` 1.0
   **to that backbone**, before sampling is configured.
3. `ModelSamplingAuraFlow` (node 9) sets `shift` 3.1 on the LoRA-patched model.
4. `KSampler` (node 11): **4 steps, CFG 1.0, euler / simple**, `denoise` 1.0.
5. Conditioning is `TextEncodeQwenImageEditPlus` (Qwen2.5-VL encoder + VAE plus
   reference latents) wrapped per side by `FluxKontextMultiReferenceLatentMethod`
   (`index_timestep_zero`).

## Recipe versus machine

The graphs, catalog bindings and pins above are repository recipes. The weights, the
primary ComfyUI install and ComfyUI-GGUF live on the configured PC outside Git.
GGUF support is a custom-node dependency of the installed backend
(`docs/research/Asset-Strategy-and-Findings.md`).

## Measured limits

- Resident backbone: **12,738.98 MB** in every loading log
  (`docs/RUNTIME-PRECONDITIONS.md` section 2).
- The `loaded completely … full load: True` exit line at `--reserve-vram 0.6` has
  **not been observed** (section 7): the one Qwen job since the change (12 September,
  `qwen-2ref`, two references) died on a host allocation before any load line.
- **Rule: 32 GiB of commit headroom before any Qwen job at 1 MP or above**, sampled
  during the run (section 3). Open: #77 (host allocation), #89 (access violations).
- Speed: one `qwen-1ref` run measured 672 s on 14 September 2026 (catalog
  description). One research `qwen-2ref` Q4_K_M + Lightning four-step render at
  832×1248 took **871.2 s** (prompt `659e4504-c868-4413-9a5e-d3c6e002cbf1`,
  [retained row](../experiments/curated/style-pose-matrix/2026-09-14-combine/README.md));
  `research-scripts/qwen_pose.py` loaded its graph with changed runtime inputs.
  This single render is not a Studio-route timing distribution. No completed
  timed `qwen-3ref` render is recorded.

## Run proof is not acceptance or clearance

A completed job is generation only. No owner art acceptance is recorded for this
stack, and licence clearance is separate: the cards declare apache-2.0 for the
backbone, Lightning adapter and encoder, but a hash match proves the bytes, not the
creator (`models/library.json` terms); the catalog says to review the exact Qwen
model and adapter terms before any commercial use.

## Compatibility boundary: do NOT mix with Qwen-Image 2.1

| | Edit 2511 (this page) | Qwen-Image 2.1 ([QWEN-IMAGE-21.md](QWEN-IMAGE-21.md)) |
| --- | --- | --- |
| Checkpoint | 20B GGUF Q4 (`qwen-image-edit-2511-Q4_K_M.gguf`) | 7B int8 safetensors (`qwen_image_2.1_int8_convrot.safetensors`) |
| Text encoder | Qwen2.5-VL 7B fp8 | Qwen3-VL 8B int8 |
| VAE | `qwen_image_vae` | bf16 RGBA decoder |
| Backend | primary, ComfyUI v0.35.0, port 8188 | isolated `qwen21`, ComfyUI v0.37.0, port 8196 |
| Few-step adapter | Lightning 4-step (installed, this stack only) | Pruna 8/5-step (research lead, not installed) / Fix LoRA (downloaded, **untested**) |

The primary v0.35.0 has no Qwen-Image 2.1 model class, and the 2.1 backend has no
Edit-2511 loader path. Do not load the Lightning LoRA (or the Multiple-Angles LoRA)
on a 2.1 graph, do not load any 2.1 LoRA on an Edit-2511 graph, and do not point
either graph at the other's weights. Research hygiene already states this
(`docs/research/LAS-IMAGE-MODELS-WAVE-FINDINGS-2026-09-24.md` section 3):
keep Edit-2511 adapters off 2.1 until evidence; Pruna adapters are 2.1-only.
Open 2.1 items (2048px, multi-reference, text, LoRA status, VRAM arbitration) stay
under #739. Do not treat the downloaded 2.1 Fix LoRA as qualified: it is untested.

## Unverified

- Full-load line at reserve 0.6; Studio-route `qwen-2ref` timing and any
  `qwen-3ref` timing; Multiple-Angles trigger and scale; no Studio proof behind
  the atelier `verified: false` flags.
