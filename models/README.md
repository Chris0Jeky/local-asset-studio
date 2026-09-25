# Model registry

`installed-manifest.json` records relative model paths, file sizes, SHA-256 values and available source revisions. The files were checksum-verified when originally downloaded. Presence and size can be checked quickly; rehashing every weight is deliberately not part of every launch.

No weights are stored in Git. They remain in the configured ComfyUI `models` directory. This registry does not install a fresh machine automatically.

`library.json` now pins **every file with a pinned suffix** (`.safetensors`, `.gguf`, `.pth`, `.pt`,
`.onnx`) installed under the ComfyUI `models` tree: the 22 Workflow Lab assets, the 34 anime/fantasy
adapters below, and the 45 previously unpinned files listed in
[Everything else installed](#everything-else-installed-45), each with its exact filename, destination
folder, source URL, size, SHA-256, model family and terms. Weights with any other suffix are outside
that set and are not pinned; see the note at the end of that section.
The first 22 were installed and checksum-verified on 11 September 2026. Use Studio's
**Models & folders** for presence, verification receipts, available storage and
explicit install/resume actions. The older manifest describes the original set;
the two manifests are complementary. The [Workflow Lab guide](../docs/WORKFLOW-LAB.md)
explains which split weights and adapters belong together.

- **WAI v17:** installed from [frankjoshua's Hugging Face mirror](https://huggingface.co/frankjoshua/waiIllustriousSDXL_v170). `wai-provenance.json` records agreement with another mirror. Original creator authentication/commercial terms remain unresolved. No VPN was needed for the copy installed here.
- **NoobAI XL 1.1:** [author model card](https://huggingface.co/Laxhar/noobai-XL-1.1) restricts commercial use including generated products; hobby/research preset only.
- **Pixel Art XL:** [LoRA source](https://huggingface.co/nerijs/pixel-art-xl), paired with SDXL. It is a style aid, not automatic production pixel cleanup.
- **FLUX.2 dev 32B:** its Q4 diffusion weight and matching Mistral Q4 encoder are installed and checksum-verified. Inference remains untested; `flux2-32b-candidates.json` preserves the source metadata. A concrete RAM/offload strategy is still needed.

Other installed options: SDXL base, FLUX Klein 4B FP8, RealVisXL V5 FP16, Animagine XL4 Opt, Pony V6, Z-Image Turbo BF16, Qwen Image Edit2511 Q4 with Lightning, and Xinsir OpenPose SDXL. Research documentation contains source links and measured limitations. A model being installed does not imply unrestricted rights over its weights, outputs, third-party characters, or references.

## Everything else installed (45)

On 12 September 2026 every file under the ComfyUI `models` tree with a `.safetensors`, `.gguf`,
`.pth`, `.pt` or `.onnx` suffix was enumerated and SHA-256 hashed from the installed bytes, then
compared with `library.json`. One hundred and seven files matched that suffix set; forty-five were
unpinned, and all forty-five are pinned below. Sizes and
hashes come from the installed files, not from a card. Where a receipt, `installed-manifest.json`
or `anime-detailing-install.json` already recorded a hash, it agreed — **no mismatches**. Thirty-seven
also match the Hugging Face LFS oid at the exact pinned revision; a hash match proves the bytes came
from that repository, never who made the model or what rights it carries.

Pinning added four model folders — `ipadapter`, `ultralytics`, `inpaint` and `vae_approx` — to the
Models view. Eleven of these files are not `.safetensors` (`.gguf` backbones, `.pth` heads and
upscalers, `.pt` detectors). Those are **pin only**: Studio reports presence and size, and the
installer refuses them with *"Automatic installation supports safetensors weights only"* rather than
writing a file it cannot verify through the download path. Copy them in by hand.

| File | Bytes | SHA-256 (first 12) | Source | Declared licence |
| --- | ---: | --- | --- | --- |
| `checkpoints/NoobAI-XL-v1.1.safetensors` | 7,105,349,958 | `6681e8e4b134` | [Laxhar/noobai-XL-1.1](https://huggingface.co/Laxhar/noobai-XL-1.1) | other |
| `checkpoints/RealVisXL_V5.0_fp16.safetensors` | 6,938,065,488 | `6a35a7855770` | [SG161222/RealVisXL_V5.0](https://huggingface.co/SG161222/RealVisXL_V5.0) | openrail++ |
| `checkpoints/animagine-xl-4.0-opt.safetensors` | 6,938,350,040 | `6327eca98bfb` | [cagliostrolab/animagine-xl-4.0](https://huggingface.co/cagliostrolab/animagine-xl-4.0) | openrail++ |
| `checkpoints/pony-diffusion-v6.safetensors` | 6,938,041,050 | `67ab2fd8ec43` | [AstraliteHeart/pony-diffusion-v6](https://huggingface.co/AstraliteHeart/pony-diffusion-v6) | creativeml-openrail-m |
| `checkpoints/sd_xl_base_1.0.safetensors` | 6,938,078,334 | `31e35c80fc48` | [stabilityai/stable-diffusion-xl-base-1.0](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0) | openrail++ |
| `checkpoints/waiIllustriousSDXL_v170.safetensors` | 6,938,040,682 | `f116b0c78ff4` | [frankjoshua/waiIllustriousSDXL_v170](https://huggingface.co/frankjoshua/waiIllustriousSDXL_v170) | none declared |
| `checkpoints/novaAnimeXL_ilV190.safetensors` | 6,939,105,596 | `fa486caafc33` | [civitai model 376130](https://civitai.com/models/376130) | civitai flags RentCivit/Image/Rent (no Sell) |
| `clip_vision/clip-vision_vit-h.safetensors` | 2,528,373,448 | `6ca9667da1ca` | [h94/IP-Adapter](https://huggingface.co/h94/IP-Adapter) | apache-2.0 |
| `controlnet/xinsir-openpose-sdxl.safetensors` | 2,502,139,104 | `b8524e557a7d` | [xinsir/controlnet-openpose-sdxl-1.0](https://huggingface.co/xinsir/controlnet-openpose-sdxl-1.0) | apache-2.0 |
| `controlnet/xinsir-union-sdxl-1.0.safetensors` | 2,512,030,408 | `a9e13fd61f31` | [xinsir/controlnet-union-sdxl-1.0](https://huggingface.co/xinsir/controlnet-union-sdxl-1.0) | apache-2.0 |
| `diffusion_models/flux-2-klein-4b-fp8.safetensors` | 4,070,624,520 | `97ed34fe0567` | [black-forest-labs/FLUX.2-klein-4b-fp8](https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8) | apache-2.0 |
| `diffusion_models/flux2-dev-Q4_K_M.gguf` | 20,082,414,560 | `fca680c7b221` | [city96/FLUX.2-dev-gguf](https://huggingface.co/city96/FLUX.2-dev-gguf) | other |
| `diffusion_models/qwen-image-edit-2511-Q4_K_M.gguf` | 13,244,758,624 | `8677bac90627` | [unsloth/Qwen-Image-Edit-2511-GGUF](https://huggingface.co/unsloth/Qwen-Image-Edit-2511-GGUF) | apache-2.0 |
| `diffusion_models/z_image_turbo_bf16.safetensors` | 12,309,866,400 | `2407613050b8` | [Comfy-Org/z_image_turbo](https://huggingface.co/Comfy-Org/z_image_turbo) | apache-2.0 |
| `inpaint/MAT_Places512_G_fp16.safetensors` | 125,280,278 | `309dd6ce6e04` | [Acly/MAT](https://huggingface.co/Acly/MAT) | cc-by-nc-4.0 |
| `inpaint/fooocus_inpaint_head.pth` | 52,602 | `32f7f838e0c6` | [lllyasviel/fooocus_inpaint](https://huggingface.co/lllyasviel/fooocus_inpaint) | openrail |
| `ipadapter/ip-adapter-plus-face_sdxl_vit-h.safetensors` | 847,517,512 | `677ad8860204` | [h94/IP-Adapter](https://huggingface.co/h94/IP-Adapter) | apache-2.0 |
| `ipadapter/ip-adapter-plus_sdxl_vit-h.safetensors` | 847,517,512 | `3f5062b8400c` | [h94/IP-Adapter](https://huggingface.co/h94/IP-Adapter) | apache-2.0 |
| `ipadapter/ip-adapter_sdxl_vit-h.safetensors` | 698,391,064 | `ebf05d918348` | [h94/IP-Adapter](https://huggingface.co/h94/IP-Adapter) | apache-2.0 |
| `loras/Hyper-SDXL-8steps-CFG-lora.safetensors` | 787,359,648 | `55b51334c850` | [ByteDance/Hyper-SD](https://huggingface.co/ByteDance/Hyper-SD) | none declared |
| `loras/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors` | 849,608,296 | `22226e8d05d3` | [lightx2v/Qwen-Image-Edit-2511-Lightning](https://huggingface.co/lightx2v/Qwen-Image-Edit-2511-Lightning) | apache-2.0 |
| `loras/flux-2-klein-4B-outpaint-lora.safetensors` | 76,038,936 | `b8a5142b40f2` | [fal/flux-2-klein-4B-outpaint-lora](https://huggingface.co/fal/flux-2-klein-4B-outpaint-lora) | apache-2.0 |
| `loras/pixel-art-xl.safetensors` | 170,543,052 | `4234637cb80c` | [nerijs/pixel-art-xl](https://huggingface.co/nerijs/pixel-art-xl) | creativeml-openrail-m |
| `loras/qwen-image-edit-2511-multiple-angles-lora.safetensors` | 295,140,688 | `42426ded4e25` | [fal/Qwen-Image-Edit-2511-Multiple-Angles-LoRA](https://huggingface.co/fal/Qwen-Image-Edit-2511-Multiple-Angles-LoRA) | apache-2.0 |
| `loras/ST_Mishima_Kurone_0R.safetensors` | 202,694,828 | `d1e424d0afda` | [civitai model 1523528](https://civitai.com/models/1523528) | civitai flags Image/RentCivit/Rent/Sell · trigger `mishimakurone` |
| `loras/glossy_anime_style_illustriousXL-000011.safetensors` | 228,464,188 | `c71fb57c4409` | [civitai model 1364837](https://civitai.com/models/1364837) | civitai flags Rent/RentCivit/Image (no Sell) · trigger `glossy_anime_style` |
| `loras/Konosuba_Fantastic_Days_v2.0.safetensors` | 456,521,740 | `6d20e168091d` | [civitai model 1610833](https://civitai.com/models/1610833) | civitai flags Image/RentCivit/Rent (no Sell) · trigger `KonosubaFantasticDays-Liver020` |
| `loras/Konosuba_Illustrious_SD8.safetensors` | 170,639,476 | `b2fecb129da4` | [civitai model 663943](https://civitai.com/models/663943) | civitai flags Image/RentCivit/Rent/Sell · trigger `—` |
| `loras/Detail_enhancer_IL_v2.safetensors` | 228,492,876 | `54a203f0a909` | [civitai model 1450571](https://civitai.com/models/1450571) | civitai flags RentCivit/Image/Rent (no Sell) · trigger `—` |
| `loras/ST_Momoko_Roshidere_0R.safetensors` | 202,694,260 | `d80eb6f9dcdc` | [civitai model 1516990](https://civitai.com/models/1516990) | civitai flags Image/RentCivit/Rent/Sell · trigger `momokoroshidere` |
| `loras/shiny_nai_ilxl_goofy_remade.safetensors` | 114,428,780 | `f6186b476517` | [civitai model 618752](https://civitai.com/models/618752) | civitai flags RentCivit/Rent (no Image, no Sell) · trigger `shiny skin` |
| `text_encoders/Mistral-Small-3.2-24B-Instruct-2506-Q4_K_M.gguf` | 14,333,922,848 | `a3cc56310807` | [unsloth/Mistral-Small-3.2-24B-Instruct-2506-GGUF](https://huggingface.co/unsloth/Mistral-Small-3.2-24B-Instruct-2506-GGUF) | apache-2.0 |
| `text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors` | 9,384,670,680 | `cb5636d852a0` | [Comfy-Org/Qwen-Image_ComfyUI](https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI) | apache-2.0 |
| `text_encoders/qwen_3_4b.safetensors` | 8,044,982,048 | `6c671498573a` | [Comfy-Org/z_image_turbo](https://huggingface.co/Comfy-Org/z_image_turbo) | apache-2.0 |
| `ultralytics/bbox/face_yolov8s.pt` | 22,507,707 | `c7237eff2578` | [Bingsu/adetailer](https://huggingface.co/Bingsu/adetailer) | apache-2.0 |
| `ultralytics/bbox/face_yolov9c.pt` | 51,648,019 | `d02fe493c31e` | [Bingsu/adetailer](https://huggingface.co/Bingsu/adetailer) | apache-2.0 |
| `ultralytics/bbox/hand_yolov8n.pt` | 6,237,883 | `3991202eb69e` | [Bingsu/adetailer](https://huggingface.co/Bingsu/adetailer) | apache-2.0 |
| `ultralytics/bbox/hand_yolov9c.pt` | 51,633,747 | `6f116f686ef5` | [Bingsu/adetailer](https://huggingface.co/Bingsu/adetailer) | apache-2.0 |
| `ultralytics/segm/person_yolov8m-seg.pt` | 54,827,683 | `c8ab26f51717` | [Bingsu/adetailer](https://huggingface.co/Bingsu/adetailer) | apache-2.0 |
| `upscale_models/4x_NMKD-Superscale-SP_178000_G.pth` | 66,958,607 | `1d1b0078fe71` | [gemasai/4x_NMKD-Superscale-SP_178000_G](https://huggingface.co/gemasai/4x_NMKD-Superscale-SP_178000_G) | none declared |
| `upscale_models/OmniSR_X2_DIV2K.safetensors` | 1,655,992 | `79408fc23203` | [Acly/Omni-SR](https://huggingface.co/Acly/Omni-SR) | apache-2.0 |
| `upscale_models/OmniSR_X3_DIV2K.safetensors` | 1,673,302 | `4fb0b68fc314` | [Acly/Omni-SR](https://huggingface.co/Acly/Omni-SR) | apache-2.0 |
| `upscale_models/OmniSR_X4_DIV2K.safetensors` | 1,697,536 | `dff25e4ed392` | [Acly/Omni-SR](https://huggingface.co/Acly/Omni-SR) | apache-2.0 |
| `upscale_models/RealESRGAN_x4plus_anime_6B.pth` | 17,938,799 | `f872d837d3c9` | [github.com](https://github.com/xinntao/Real-ESRGAN/releases/tag/v0.2.2.4) | none declared |
| `vae/ae.safetensors` | 335,304,388 | `afc8e28272cd` | [Comfy-Org/z_image_turbo](https://huggingface.co/Comfy-Org/z_image_turbo) | apache-2.0 |
| `vae/flux2-vae.safetensors` | 336,211,292 | `868fe7b343cc` | [huggingface.co](https://huggingface.co/black-forest-labs/FLUX.2-dev) | none declared |
| `vae/qwen_image_vae.safetensors` | 253,806,246 | `a70580f0213e` | [Comfy-Org/Qwen-Image_ComfyUI](https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI) | apache-2.0 |
| `vae_approx/taef1_decoder.safetensors` | 2,464,414 | `bb41500b646d` | not recorded | none declared |
| `vae_approx/taef1_encoder.safetensors` | 2,464,424 | `19f5a854ce57` | not recorded | none declared |
| `vae_approx/taesd_decoder.safetensors` | 2,450,590 | `d903e7cc3ae5` | not recorded | none declared |
| `vae_approx/taesd_encoder.safetensors` | 2,450,568 | `a6b8c0fda4aa` | not recorded | none declared |
| `vae_approx/taesdxl_decoder.safetensors` | 2,450,590 | `ae5256b046b0` | not recorded | none declared |
| `vae_approx/taesdxl_encoder.safetensors` | 2,450,568 | `3d7801328667` | not recorded | none declared |

Three groups carry less than a full provenance record, and their `terms` say so rather than guessing:

- **`vae/flux2-vae.safetensors`** — byte count and role match `ae.safetensors` in
  [black-forest-labs/FLUX.2-dev](https://huggingface.co/black-forest-labs/FLUX.2-dev), but that repo is
  gated and the unauthenticated API masks its LFS oid, so this is a size-and-name match, not a hash
  match. Licence of the installed copy unconfirmed; no install URL pinned.
- **`upscale_models/RealESRGAN_x4plus_anime_6B.pth`** — `anime-detailing-install.json` records the
  official [Real-ESRGAN v0.2.2.4](https://github.com/xinntao/Real-ESRGAN/releases/tag/v0.2.2.4) GitHub
  release and already carried this SHA-256. GitHub is not a curated install source, so `url` is empty.
- **The six `vae_approx` TAESD/TAEF1 previewers** — half the size of the `madebyollin/taesd` files, so
  they are FP16 conversions from an unrecorded origin. `source` is empty and `terms` reads
  *"provenance not recorded; pinned from the installed file on 2026-09-12"*.

Two further licence facts are recorded, not cleared: `Laxhar/noobai-XL-1.1` declares Fair-AI Public
License 1.0-SD (no commercial products, hobby and research only), and `Acly/MAT` is `cc-by-nc-4.0`
(non-commercial only). `lllyasviel/fooocus_inpaint` declares `openrail` in its repository card even
though upstream Fooocus itself is AGPL-3.0; both facts are in that entry's `terms`.

Two installed files fall outside the pinned suffix set and therefore have no entry, by design:

- **`inpaint/inpaint_v26.fooocus.patch`** (1,323,362,033 bytes, `lllyasviel/fooocus_inpaint`, LFS oid
  `f8657a025104`, evidence in PR #100) — the patch weight the pinned `fooocus_inpaint_head.pth` pairs
  with. `.patch` is not a suffix `SUFFIXES` recognises, so neither the pin nor the inventory list it.
- **`diffusion_models/krea2_turbo-Q5_K_M.gguf.part`** (2.96 GB) — the abandoned Krea 2 Q5 transfer.
  A `.part` file is by definition unfinished; it stays for inspection and is never pinned.

The CCIP identity model (`model_feat.onnx`, `deepghs/ccip_onnx`, licence `openrail`) downloaded the
same evening lives at `C:\AI\asset-tools\ccip\`, outside the ComfyUI model tree. It is a critic
tool, not a ComfyUI weight, so it is **not** a `library.json` asset; its receipt is the record.

## Local intake — 21 September 2026

Nine weights were copied from `Downloads/temp2` through `scripts/intake-downloads.py`. The owner obtained those files from civitai.red. AniFox v2 was already pinned; the copied SHA-256 matches `c07eadce03076d02…`. The Qwen Image VAE in that folder is byte-identical to the installed `vae/qwen_image_vae.safetensors` and was not copied again. `civitai.com` returned HTTP 451 until a VPN session; at 2026-09-21T01:30 its `/api/v1/models` and by-hash endpoints agreed with the civitai.red flags and SHA-256 values. Download origin remains civitai.red.

| File | Folder | Bytes | SHA-256 (first 12) |
| --- | --- | ---: | --- |
| `anifoxXLV20_anifoxV2.safetensors` | `checkpoints/` | 6,938,040,706 | `c07eadce0307` (existing pin) |
| `oneObsessionAnima_v20.safetensors` | `diffusion_models/` | 4,182,229,969 | `d1d4fa3de475` |
| `pearlyAnimaMix_v10.safetensors` | `diffusion_models/` | 4,436,052,094 | `52de310e0eea` |
| `realism_engine_krea2_v3.1.safetensors` | `loras/` | 1,562,410,296 | `a6712629445a` |
| `RealisticSnapshotKrea2.safetensors` | `loras/` | 228,587,720 | `dfd67eb881be` |
| `Ringeko.safetensors` | `loras/` | 228,486,116 | `b7edfa16d5c1` |
| `lenovo_krea2.safetensors` | `loras/` | 114,324,736 | `6967840059e5` |
| `pearly_esearu_style.safetensors` | `loras/` | 91,892,608 | `926cc59441dc` |
| `pearly_petiflow2.safetensors` | `loras/` | 91,863,712 | `1e5b64e9d23d` |
| `Robertlu1021_fluorite_arknights_v1.0_epoch_10.safetensors` | `loras/` | 57,435,028 | `9941b93e392a` |

The two Anima UNETs needed `--dest-folder diffusion_models`: their tensor keys match JANIMA (`model.diffusion_model.blocks…`) rather than the header classifier's `img_in`/`final_layer` backbone signature.

## Anime & Fantasy adapters

Thirty Krea 2 LoRAs were added on 12 September 2026 for the anime/fantasy atelier work. Every row below is
pinned in `library.json` with its byte count and SHA-256; the weights themselves stay in the ComfyUI
`models/loras` folder. **Strength** is the range the source card recommends, not a measured optimum — no
generation in this repository has yet proved any of these numbers on this machine.

Trigger position matters and differs per author: the fal styles want a short prompt with the trigger at the
**end**; `@NJSW33T` and `@NIJISIS` go at the **start**; the Comfy-Org official styles read as ordinary style
phrases anywhere in the prompt. `Krea2_TextFusion_Refusal_Reduction` and `NIJISIS` both edit the txtfusion
blocks — stacking them is untested here. The 4-step distill is a sampler change, not a style: use it with
steps 4 and cfg 1.

### Comfy-Org official Krea 2 styles and the 4-step distill (9)

Downloaded from the official [Comfy-Org/Krea-2](https://huggingface.co/Comfy-Org/Krea-2) repository and the
[4-step distill mirror](https://huggingface.co/lvladikov/Krea2-Turbo-Distill-4step-LoRA); both repo cards
state `krea-2-community-license`. The licence PDF itself has not been read.

| File | Trigger | Strength | Source |
| --- | --- | --- | --- |
| `krea2_darkbrush.safetensors` | `monochrome ink wash style` | 1.0 | [Comfy-Org/Krea-2](https://huggingface.co/Comfy-Org/Krea-2) |
| `krea2_dotmatrix.safetensors` | `monochrome stippling style` | 1.0 | [Comfy-Org/Krea-2](https://huggingface.co/Comfy-Org/Krea-2) |
| `krea2_kidsdrawing.safetensors` | `naive expressive sketch style` | 1.0 | [Comfy-Org/Krea-2](https://huggingface.co/Comfy-Org/Krea-2) |
| `krea2_neondrip.safetensors` | `textured abstract style` | 1.0 | [Comfy-Org/Krea-2](https://huggingface.co/Comfy-Org/Krea-2) |
| `krea2_rainywindow.safetensors` | `rainy window style` | 1.0 | [Comfy-Org/Krea-2](https://huggingface.co/Comfy-Org/Krea-2) |
| `krea2_softwatercolor.safetensors` | `art deco watercolor style` | 1.0 | [Comfy-Org/Krea-2](https://huggingface.co/Comfy-Org/Krea-2) |
| `krea2_sunsetblur.safetensors` | `ethereal motion blur style` | 1.0 | [Comfy-Org/Krea-2](https://huggingface.co/Comfy-Org/Krea-2) |
| `krea2_vintagetarot.safetensors` | `vintage tarot style` | 1.0 | [Comfy-Org/Krea-2](https://huggingface.co/Comfy-Org/Krea-2) |
| `krea2_turbo_4step_rank_64_lora_comfyui.safetensors` | none | 0.75-1.0 | [lvladikov/Krea2-Turbo-Distill-4step-LoRA](https://huggingface.co/lvladikov/Krea2-Turbo-Distill-4step-LoRA) |

`krea2_retroanime.safetensors` (`purple retro anime style`) was already pinned as `krea-retro`.

### fal style LoRAs (17)

All from [ilkerzgi/fal-Krea-2-Style-LoRAs](https://huggingface.co/ilkerzgi/fal-Krea-2-Style-LoRAs) (the
`comfy/` variant of each), licensed `krea-2-community-license` in that repo card. The trigger is the style
name in words followed by ` style`, placed at the end of a short prompt; the index recommends scale 1.0-1.25.

| File | Trigger | Strength |
| --- | --- | --- |
| `fal-krea2-aged-tempera-fable.safetensors` | `aged tempera fable style` | 1.0-1.25 |
| `fal-krea2-airy-anime-watercolor.safetensors` | `airy anime watercolor style` | 1.0-1.25 |
| `fal-krea2-amber-dusk-anime.safetensors` | `amber dusk anime style` | 1.0-1.25 |
| `fal-krea2-azure-cel-shaded.safetensors` | `azure cel shaded style` | 1.0-1.25 |
| `fal-krea2-azure-manga-bloom.safetensors` | `azure manga bloom style` | 1.0-1.25 |
| `fal-krea2-baroque-dreamscape-oil.safetensors` | `baroque dreamscape oil style` | 1.0-1.25 |
| `fal-krea2-bold-impasto-sunlit.safetensors` | `bold impasto sunlit style` | 1.0-1.25 |
| `fal-krea2-cel-shaded-daytime-anime.safetensors` | `cel shaded daytime anime style` | 1.0-1.25 |
| `fal-krea2-chibi-watercolor-pastel-anime.safetensors` | `chibi watercolor pastel anime style` | 1.0-1.25 |
| `fal-krea2-cobalt-sky-anime.safetensors` | `cobalt sky anime style` | 1.0-1.25 |
| `fal-krea2-cozy-storybook-gouache.safetensors` | `cozy storybook gouache style` | 1.0-1.25 |
| `fal-krea2-crimson-blue-inkline-fantasy.safetensors` | `crimson blue inkline fantasy style` | 1.0-1.25 |
| `fal-krea2-dark-chiaroscuro-oil.safetensors` | `dark chiaroscuro oil style` | 1.0-1.25 |
| `fal-krea2-dark-fantasy-film.safetensors` | `dark fantasy film style` | 1.0-1.25 |
| `fal-krea2-detailed-manga-inkwork.safetensors` | `detailed manga inkwork style` | 1.0-1.25 |
| `fal-krea2-emerald-fantasy-paperback.safetensors` | `emerald fantasy paperback style` | 1.0-1.25 |
| `fal-krea2-emerald-lamplight-oil.safetensors` | `emerald lamplight oil style` | 1.0-1.25 |

All nineteen fal styles are installed and pinned. Eighteen have a download receipt in
`.runtime/downloads/receipts.json`; `fal-krea2-emerald-lamplight-oil` has none, so its size and SHA-256 were
computed from the installed file on 12 September 2026 and its `terms` entry says so. `amber-lit-fantasy-filmset`
and `azure-sunlit-storybook` needed retried downloads the same day and were pinned once their hashes matched
the Hugging Face LFS metadata.

### civitai adapters (4)

civitai's metadata API answers without credentials, so names, file ids, sizes, SHA-256 values and the
permission flags below were read from `https://civitai.com/api/v1/model-versions/<id>` on 12 September 2026.
The **download** endpoint needs a personal API key: `scripts/civitai-fetch.py` reads it from the
`CIVITAI_API_TOKEN` environment variable only and never prints it. The flags are the listing's own; they are
not legal advice and the linked model page governs.

| File | Trigger | Strength | Source | civitai `allowCommercialUse` |
| --- | --- | --- | --- | --- |
| `Krea2_TextFusion_Refusal_Reduction.safetensors` | none | 1.0 | [model 2775340](https://civitai.com/models/2775340?modelVersionId=3125118) | Image, RentCivit, Rent, Sell; derivatives allowed; different licence not allowed |
| `Niji_Sweet_Spot_Krea2_v2A.safetensors` | `@NJSW33T` (start) | 0.8-1.5 | [model 2554999](https://civitai.com/models/2554999?modelVersionId=3210573) | Image, RentCivit, Rent (no Sell); derivatives **not** allowed |
| `NIJISIS_KREA_2_krea2_3274861_epoch_8.safetensors` | `@NIJISIS` (start) | 1.0 | [model 2863875](https://civitai.com/models/2863875?modelVersionId=3302337) | Image, RentCivit, Rent (no Sell); derivatives allowed |
| `krea2_koukouya_style_c1-st3000.safetensors` | none | 1.0 | [model 2844656](https://civitai.com/models/2844656?modelVersionId=3211621) | Image, RentCivit, Rent, Sell; derivatives allowed |

NIJISIS was downloaded by the owner on 12 September 2026 (the owner spent the Buzz); its SHA-256 was verified
against the installed file. **koukouya was installed on 12 September 2026** with the owner's civitai key (`CIVITAI_API_TOKEN`), receipt hash matching the listing; the `krea-atelier-target-stack` recipe names all three adapters.

### SDXL-family smoke LoRAs (11), 23 September 2026

These LoRAs were downloaded for the smokes in issues #757 (WAI v17 / Illustrious), #758 (NoobAI-XL 1.1) and #759
(Pony V6), using `scripts/civitai-fetch.py`. Every receipt's SHA-256 matches the civitai listing. The flags were
read from `https://civitai.com/api/v1/models/<id>` on 23 September 2026. They are the listing's own statements,
not licence clearance. NoobAI outputs stay hobby/non-commercial under the checkpoint's own terms, whatever a
LoRA's flags say. Results and the verdict for each LoRA: `experiments/curated/lora-smoke-20260923/README.md`.

**Base matching.** The installed `NoobAI-XL-v1.1` (Laxhar/noobai-XL-1.1) is epsilon-prediction. The NoobAI
builds of Flat Color (`1132089`) and MeMaXL (`269772`) are all v-pred, so neither was downloaded for NoobAI. The
Illustrious Flat Color build (Illustrious v0.1 is the parent of NoobAI eps) stood in for them.

| File | Base | Trigger | civitai version | civitai `allowCommercialUse` |
| --- | --- | --- | --- | --- |
| `illustriousXLv01_stabilizer_v1.198.safetensors` | Illustrious | none | [971952 / 2055853](https://civitai.com/models/971952?modelVersionId=2055853) | RentCivit only; derivatives **not** allowed |
| `detailed_hand_focus_style_illustriousXL_v1.1.safetensors` | Illustrious | none | [200255 / 2212079](https://civitai.com/models/200255?modelVersionId=2212079) | RentCivit only; derivatives **not** allowed |
| `illustrious_masterpieces_v3.safetensors` | Illustrious | `masterpiece, best quality, very aesthetic` | [929497 / 2247497](https://civitai.com/models/929497?modelVersionId=2247497) | Image, RentCivit, Rent (no Sell) |
| `AddMicroDetails_Illustrious_v7.safetensors` | Illustrious | `addmicrodetails` | [1377820 / 3206748](https://civitai.com/models/1377820?modelVersionId=3206748) | Image, RentCivit, Sell, Rent, SellMerge |
| `iLLC0lorL1nes.safetensors` | Illustrious | `C0lorL1nes` | [599757 / 2620790](https://civitai.com/models/599757?modelVersionId=2620790) | RentCivit, Image, Rent, Sell, SellMerge |
| `noobai_ep11_stabilizer_v0.205_fp16.safetensors` | NoobAI (eps 1.1) | none | [971952 / 1764869](https://civitai.com/models/971952?modelVersionId=1764869) | RentCivit only; derivatives **not** allowed |
| `illustrious_noobai_epsilon_pred_1_masterpieces_v1.safetensors` | NoobAI (eps 1.0) | `masterpiece, best quality, very aesthetic` | [929497 / 1070123](https://civitai.com/models/929497?modelVersionId=1070123) | Image, RentCivit, Rent (no Sell) |
| `illustrious_flat_color_v2.safetensors` | Illustrious | `flat color, no lineart` | [1132089 / 1311848](https://civitai.com/models/1132089?modelVersionId=1311848) | Image, RentCivit, Rent (no Sell) |
| `g0th1cPXL.safetensors` | Pony | `g0thicPXL, glowing, neon,` | [888231 / 398847](https://civitai.com/models/888231?modelVersionId=398847) | RentCivit only; derivatives **not** allowed |
| `S1_Dramatic_Lighting_v3.safetensors` | Pony | `s1_dram` | [661736 / 1280045](https://civitai.com/models/661736?modelVersionId=1280045) | RentCivit only |
| `Hand_pony_style_v1.safetensors` | Pony | none | [200255 / 1356581](https://civitai.com/models/200255?modelVersionId=1356581) | RentCivit only; derivatives **not** allowed |

The TextFusion "Refusal-Reduction" LoRA (`2775340`) was not downloaded again. It was already on disk; see
`docs/research/LORA-DISK-AUDIT-2026-09-23.md` (#762) for its hot-path recommendation.

### SFW lighting qualification candidate, 25 September 2026

`Dark_Illustrious_v1.safetensors` (Civitai [model 1711037, Illustrious version 1936270](https://civitai.com/models/1711037?modelVersionId=1936270)) was downloaded with `scripts/civitai-fetch.py`. The installed file is 170,594,572 bytes and its SHA-256 matches the listing: `8bf1c001b1a6ecf463df812470008264ec94bd3a2b1952546eea789eeec4f27d`. The receipt is in `.runtime/downloads/receipts.json`. The model-level listing flags allow Image and RentCivit commercial uses, require credit, disallow derivatives and different licensing; the version API carries no separate permission flags. These are recorded claims, not licence clearance. WAI v17's creator authentication and commercial terms also remain unresolved. The planned, unaccepted SFW lighting comparison is documented in `experiments/curated/sfw-lighting-qualification/`.

### Acquisition scripts

| Script | Use |
| --- | --- |
| `python scripts/fetch-hf.py --repo <owner/name> --path <file> [--dest-folder loras] [--name <file>] [--dry-run]` | Hugging Face file, verified against the LFS oid in the repository tree |
| `python scripts/civitai-fetch.py --version-id <id> [--file-id <id>] [--dry-run]` | civitai model version, verified against the listed SHA-256; token from `$CIVITAI_API_TOKEN` only |
| `python scripts/intake-downloads.py [--from <dir>] [--dest-folder <folder>] [--dry-run]` | Inspect model-role hints and copy reviewed browser downloads; retain originals |

The HF/Civitai acquisition scripts retain failed `.part` transfers, append receipts to
`.runtime/downloads/receipts.json` and print a `library.json` stub. Browser intake instead **copies, not
moves**: the original remains in place and each operation records its intent, staged hash and publication
state in `.runtime/downloads/intake/<operation-id>.json`. It reuses the pinned installer's lease and
no-clobber publisher; a racing destination and failed partial copy are preserved. The other acquisition
scripts are not made lease-aware by this change, so do not run competing writers.

Unknown header roles are skipped before copying. `--dest-folder` is an explicit whole-batch override,
not evidence of model identity or compatibility. Browser receipts retain `verified: false`,
`expected_sha256: null` and `runtime_compatible: null`; an observed local hash is not source verification.
Budget a full independent copy plus 20 GiB headroom. Inspect the per-operation journal after an interruption,
and handle source cleanup separately. See [the intake and recovery guide](../docs/MODEL-INTAKE.md).
