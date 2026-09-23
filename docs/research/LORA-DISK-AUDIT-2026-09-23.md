# LoRA disk audit: on-disk LoRAs vs upstream pages (issue #762), 23 September 2026

**What was checked, and when (local time, BST).** Every `.safetensors` file in the primary ComfyUI LoRA folder
(`C:/AI/ComfyUI_windows_portable/ComfyUI/models/loras/`, 85 files, about 26 GB) was hashed with SHA-256 at
00:04-00:05. Each hash was then looked up with civitai's `GET /api/v1/model-versions/by-hash/<sha256>` at 00:07-00:08 and
compared with its pin in `models/library.json`. "Refs" counts the files under `presets/`, `workflows/api/`, `app/` and
`scripts/` that name the file (`git grep -F`). The scratch data (hash list, by-hash replies, generator) stayed in the
worker's gitignored `.runtime/lora-smoke/`.

**Nothing was moved, renamed or deleted.** Every status below is a recommendation. A hash match proves the bytes match
the listing. It does not prove who made the file, and it does not grant any licence.

## Findings

- **All 77 pinned files match their pins byte for byte** (SHA-256 and size). No file was corrupt or swapped, and no pin
  pointed at a missing file.
- **8 files are orphans**: on disk, with no `models/library.json` pin and no preset, graph or recipe naming them.
  civitai identified all 8 by hash: 4 FLUX.2 Klein LoRAs (A1 Anime, AniEdit 4B and 9B, Mrpopo Klein 9B anime) and
  4 Z-Image Turbo LoRAs. `z-image-anime-v1` is also nsfw-flagged. Recommendation: pin the ones a recipe will use, or
  remove them. Either way it is the owner's choice (HUMAN_TODO q-32).
- **1 file should leave the hot path: `Krea2_TextFusion_Refusal_Reduction.safetensors`** (civitai 2775340, the
  "policy-bypass" item on #762's list). The file is pinned and matches its hash. It is wired at strength 1.0 into the
  shipped `krea-anime-atelier` and `krea-refine` graphs and into five recipes. The owner's own target stack used it
  (HUMAN_TODO q-1 and the atelier notes). The recommendation is to put it at 0 by default, as an opt-in, not to delete it.
  That is an owner decision (q-32). No graph was changed here.
- **7 files are explicit-queue-only.** civitai flags the model as nsfw: `nsfw_girls`, `nsfw_girls_anima`, both
  `BunnySlop` files, `rapscallion…stylepush`, `realism_engine_krea2_v3.1` and `z-image-anime-v1`. Wherever a shipped
  graph names one of them (the `anifox`/`cstati`/`yumeflux`/`anima`/`janima`/`oneobsession`/`pearly` baselines), the slot
  already sits at strength 0. At non-zero strength, `nsfw_girls*` and `BunnySlop_Anima` appear in the explicit-lab
  recipes (`*-nsfw-*`), where they belong. Two recipes that are not explicit also use flagged files:
  `anima-screenshot-stack` (BunnySlop_Anima 0.9, unverified) and `krea-realism-engine` (realism_engine 0.7, executed,
  clothed prompt). civitai's model flag describes the listing's gallery, not what the adapter does. Whether these two
  stay is q-32.
- **2 pins have the wrong family.** `Robertlu1021_fluorite_arknights…` is pinned as `SDXL 1.0`, but civitai says
  `Illustrious`. `krea2_koukouya_style_c1-st3000` is pinned as `Krea 2 Turbo`, but civitai says `Krea 2`. The second is
  cosmetic because the Studio aliases `Krea 2` to `Krea 2 Turbo`. Neither pin was edited here.
- **4 pinned files have no preset, graph or recipe reference**: `flux-2-klein-4B-outpaint-lora`,
  `Mannequin_V1_F29B`, `qwen-image-edit-2511-multiple-angles-lora` and `refcontrol_v2_poses`. The research scripts
  under `experiments/curated/` used some of them. Keep them.

## #762's upstream "hot IDs" vs the disk

| civitai id | What | On disk? | Note |
|---:|---|---|---|
| 2726029 | Krea 2 Turbo checkpoint (int8 convrot) | no | The disk has the Comfy-Org Hugging Face `diffusion_models/krea2_turbo_fp8_scaled.safetensors` (pin `krea-turbo`). A stale `krea2_turbo-Q5_K_M.gguf.part` sits in `diffusion_models/` (cleanup candidate, not touched). |
| 2761113 | Krea 2 Identity Edit LoRA | no | Not downloaded. It is a candidate for the identity work, not needed on the hot path. |
| 2729908 | [KREA 2] Detail Slider | no | Not downloaded. |
| 2174309 | Krea2 + Qwen 2511 + Z-Image "Illustria" cross-stack LoRA | no | Not downloaded. It is experimental, so verify the base per version first. |
| 2775340 | Krea2 TextFusion Refusal-Reduction | **yes** | See "leave hot path" above. |
| 2738703 | Krea2 [SFW/NSFW] Uncensored workflow | no | A workflow, not a LoRA. It belongs to the explicit queue only (`CIVITAI-SCAVENGE-BATCH4-EXPLICIT-QUEUE-2026-09-21.md`). |

Krea 2 builds exist upstream for three LoRAs on the SDXL shortlists: Aesthetic Masterpiece `929497` v5.1 [krea2]
(version 3077110), Velvet's Mythic `599757` "Krea 2" (3135757) and Add Micro Details `1377820` v1.0_Krea2 (3298811).
None was downloaded. They are candidates if a Krea 2 smoke follows.

## Table: filename → upstream page → base → status

Statuses are **keep**, **orphan**, **mistagged**, **explicit-queue-only** and **leave hot path**. For files that came
from Hugging Face, the pin's repository is the upstream page. The civitai mirror is added when the hash is also listed there.

### Krea 2

| File | Upstream page | Base (civitai by-hash) | Disk vs pin | Refs | Status | Note |
|---|---|---|---|---:|---|---|
| `fal-krea2-aged-tempera-fable.safetensors` | https://huggingface.co/ilkerzgi/fal-Krea-2-Style-LoRAs | Krea 2 (pin; not on civitai by hash) | sha256 match | 1 | **keep** |  |
| `fal-krea2-airy-anime-watercolor.safetensors` | https://huggingface.co/ilkerzgi/fal-Krea-2-Style-LoRAs | Krea 2 (pin; not on civitai by hash) | sha256 match | 4 | **keep** |  |
| `fal-krea2-amber-dusk-anime.safetensors` | https://huggingface.co/ilkerzgi/fal-Krea-2-Style-LoRAs | Krea 2 (pin; not on civitai by hash) | sha256 match | 1 | **keep** |  |
| `fal-krea2-amber-lit-fantasy-filmset.safetensors` | https://huggingface.co/ilkerzgi/fal-Krea-2-Style-LoRAs | Krea 2 (pin; not on civitai by hash) | sha256 match | 1 | **keep** |  |
| `fal-krea2-azure-cel-shaded.safetensors` | https://huggingface.co/ilkerzgi/fal-Krea-2-Style-LoRAs | Krea 2 (pin; not on civitai by hash) | sha256 match | 1 | **keep** |  |
| `fal-krea2-azure-manga-bloom.safetensors` | https://huggingface.co/ilkerzgi/fal-Krea-2-Style-LoRAs | Krea 2 (pin; not on civitai by hash) | sha256 match | 1 | **keep** |  |
| `fal-krea2-azure-sunlit-storybook.safetensors` | https://huggingface.co/ilkerzgi/fal-Krea-2-Style-LoRAs | Krea 2 (pin; not on civitai by hash) | sha256 match | 1 | **keep** |  |
| `fal-krea2-baroque-dreamscape-oil.safetensors` | https://huggingface.co/ilkerzgi/fal-Krea-2-Style-LoRAs | Krea 2 (pin; not on civitai by hash) | sha256 match | 5 | **keep** |  |
| `fal-krea2-bold-impasto-sunlit.safetensors` | https://huggingface.co/ilkerzgi/fal-Krea-2-Style-LoRAs | Krea 2 (pin; not on civitai by hash) | sha256 match | 1 | **keep** |  |
| `fal-krea2-cel-shaded-daytime-anime.safetensors` | https://huggingface.co/ilkerzgi/fal-Krea-2-Style-LoRAs | Krea 2 (pin; not on civitai by hash) | sha256 match | 2 | **keep** |  |
| `fal-krea2-chibi-watercolor-pastel-anime.safetensors` | https://huggingface.co/ilkerzgi/fal-Krea-2-Style-LoRAs | Krea 2 (pin; not on civitai by hash) | sha256 match | 1 | **keep** |  |
| `fal-krea2-cobalt-sky-anime.safetensors` | https://huggingface.co/ilkerzgi/fal-Krea-2-Style-LoRAs | Krea 2 (pin; not on civitai by hash) | sha256 match | 1 | **keep** |  |
| `fal-krea2-cozy-storybook-gouache.safetensors` | https://huggingface.co/ilkerzgi/fal-Krea-2-Style-LoRAs | Krea 2 (pin; not on civitai by hash) | sha256 match | 2 | **keep** |  |
| `fal-krea2-crimson-blue-inkline-fantasy.safetensors` | https://huggingface.co/ilkerzgi/fal-Krea-2-Style-LoRAs | Krea 2 (pin; not on civitai by hash) | sha256 match | 1 | **keep** |  |
| `fal-krea2-dark-chiaroscuro-oil.safetensors` | https://huggingface.co/ilkerzgi/fal-Krea-2-Style-LoRAs | Krea 2 (pin; not on civitai by hash) | sha256 match | 1 | **keep** |  |
| `fal-krea2-dark-fantasy-film.safetensors` | https://huggingface.co/ilkerzgi/fal-Krea-2-Style-LoRAs | Krea 2 (pin; not on civitai by hash) | sha256 match | 2 | **keep** |  |
| `fal-krea2-detailed-manga-inkwork.safetensors` | https://huggingface.co/ilkerzgi/fal-Krea-2-Style-LoRAs | Krea 2 (pin; not on civitai by hash) | sha256 match | 2 | **keep** |  |
| `fal-krea2-emerald-fantasy-paperback.safetensors` | https://huggingface.co/ilkerzgi/fal-Krea-2-Style-LoRAs | Krea 2 (pin; not on civitai by hash) | sha256 match | 3 | **keep** |  |
| `fal-krea2-emerald-lamplight-oil.safetensors` | https://huggingface.co/ilkerzgi/fal-Krea-2-Style-LoRAs | Krea 2 (pin; not on civitai by hash) | sha256 match | 1 | **keep** |  |
| `krea2_darkbrush.safetensors` | https://huggingface.co/Comfy-Org/Krea-2 (also civitai 2726235/3064381) | Krea 2 | sha256 match | 3 | **keep** |  |
| `krea2_dotmatrix.safetensors` | https://huggingface.co/Comfy-Org/Krea-2 (also civitai 2726235/3064396) | Krea 2 | sha256 match | 1 | **keep** |  |
| `krea2_kidsdrawing.safetensors` | https://huggingface.co/Comfy-Org/Krea-2 (also civitai 2726235/3064417) | Krea 2 | sha256 match | 1 | **keep** |  |
| `krea2_koukouya_style_c1-st3000.safetensors` | https://civitai.com/models/2844656?modelVersionId=3211621 | Krea 2 | sha256 match | 2 | **mistagged** | pin family `Krea 2 Turbo`, civitai base `Krea 2` |
| `krea2_neondrip.safetensors` | https://huggingface.co/Comfy-Org/Krea-2 (also civitai 2726235/3064408) | Krea 2 | sha256 match | 1 | **keep** |  |
| `krea2_rainywindow.safetensors` | https://huggingface.co/Comfy-Org/Krea-2 (also civitai 2726235/3064366) | Krea 2 | sha256 match | 2 | **keep** |  |
| `krea2_retroanime.safetensors` | https://huggingface.co/Comfy-Org/Krea-2 (also civitai 2726235/3064322) | Krea 2 | sha256 match | 4 | **keep** |  |
| `krea2_softwatercolor.safetensors` | https://huggingface.co/Comfy-Org/Krea-2 (also civitai 2726235/3064426) | Krea 2 | sha256 match | 4 | **keep** |  |
| `krea2_sunsetblur.safetensors` | https://huggingface.co/Comfy-Org/Krea-2 (also civitai 2726235/3064334) | Krea 2 | sha256 match | 2 | **keep** |  |
| `Krea2_TextFusion_Refusal_Reduction.safetensors` | https://civitai.com/models/2775340?modelVersionId=3125118 | Krea 2 | sha256 match | 4 | **leave hot path** | policy-bypass LoRA wired at 1.0 in `krea-anime-atelier` and `krea-refine` graphs and five recipes |
| `krea2_turbo_4step_rank_64_lora_comfyui.safetensors` | https://huggingface.co/lvladikov/Krea2-Turbo-Distill-4step-LoRA | Krea 2 (pin; not on civitai by hash) | sha256 match | 5 | **keep** |  |
| `krea2_vintagetarot.safetensors` | https://huggingface.co/Comfy-Org/Krea-2 (also civitai 2726235/3064354) | Krea 2 | sha256 match | 3 | **keep** |  |
| `lenovo_krea2.safetensors` | https://civitai.com/models/1662740?modelVersionId=3075606 | Krea 2 | sha256 match | 1 | **keep** |  |
| `Niji_Sweet_Spot_Krea2_v2A.safetensors` | https://civitai.com/models/2554999?modelVersionId=3210573 | Krea 2 | sha256 match | 4 | **keep** |  |
| `NIJISIS_KREA_2_krea2_3274861_epoch_8.safetensors` | https://civitai.com/models/2863875?modelVersionId=3302337 | Krea 2 | sha256 match | 3 | **keep** |  |
| `realism_engine_krea2_v3.1.safetensors` | https://civitai.com/models/2688234?modelVersionId=3109006 | Krea 2 | sha256 match | 1 | **explicit-queue-only** | civitai model flagged nsfw |
| `RealisticSnapshotKrea2.safetensors` | https://civitai.com/models/2268008?modelVersionId=3084537 | Krea 2 | sha256 match | 1 | **keep** |  |

### SDXL family (Illustrious / SDXL)

| File | Upstream page | Base (civitai by-hash) | Disk vs pin | Refs | Status | Note |
|---|---|---|---|---:|---|---|
| `cinematic lighting.safetensors` | https://huggingface.co/ntc-ai/SDXL-LoRA-slider.cinematic-lighting | SDXL 1.0 (pin; not on civitai by hash) | sha256 match | 16 | **keep** |  |
| `Detail_enhancer_IL_v2.safetensors` | https://civitai.com/models/1450571?modelVersionId=1983243 | Illustrious | sha256 match | 2 | **keep** |  |
| `glossy_anime_style_illustriousXL-000011.safetensors` | https://civitai.com/models/1364837?modelVersionId=1541970 | Illustrious | sha256 match | 2 | **keep** |  |
| `Hyper-SDXL-8steps-CFG-lora.safetensors` | https://huggingface.co/ByteDance/Hyper-SD (also civitai 428790/477813) | SDXL Hyper | sha256 match | 1 | **keep** |  |
| `Konosuba_Fantastic_Days_v2.0.safetensors` | https://civitai.com/models/1610833?modelVersionId=1824928 | Illustrious | sha256 match | 1 | **keep** |  |
| `Konosuba_Illustrious_SD8.safetensors` | https://civitai.com/models/663943?modelVersionId=1369394 | Illustrious | sha256 match | 1 | **keep** |  |
| `LineAniRedmondV2-Lineart-LineAniAF.safetensors` | https://huggingface.co/artificialguybr/LineAniRedmond-LinearMangaSDXL-V2 (also civitai 127018/177544) | SDXL 1.0 | sha256 match | 4 | **keep** |  |
| `manga-ink-screentone.safetensors` | https://huggingface.co/strkyyy/manga-ink-screentone (also civitai 2664796/2992297) | SDXL 1.0 | sha256 match | 15 | **keep** |  |
| `noirpopwave.safetensors` | https://civitai.com/models/2398033?modelVersionId=2696276 | Illustrious | sha256 match | 5 | **keep** |  |
| `nsfw_girls.safetensors` | https://civitai.com/models/2822856?modelVersionId=3184370 | Illustrious | sha256 match | 5 | **explicit-queue-only** | civitai model flagged nsfw |
| `pixel-art-xl.safetensors` | https://huggingface.co/nerijs/pixel-art-xl (also civitai 120096/130580) | SDXL 1.0 | sha256 match | 2 | **keep** |  |
| `Ringeko.safetensors` | https://civitai.com/models/2387976?modelVersionId=2685156 | Illustrious | sha256 match | 1 | **keep** |  |
| `Robertlu1021_fluorite_arknights_v1.0_epoch_10.safetensors` | https://civitai.com/models/2478250?modelVersionId=2786316 | Illustrious | sha256 match | 1 | **mistagged** | pin family `SDXL 1.0`, civitai base `Illustrious` |
| `shiny_nai_ilxl_goofy_remade.safetensors` | https://civitai.com/models/618752?modelVersionId=2786889 | Illustrious | sha256 match | 2 | **keep** |  |
| `ST_Mishima_Kurone_0R.safetensors` | https://civitai.com/models/1523528?modelVersionId=1723753 | Illustrious | sha256 match | 2 | **keep** |  |
| `ST_Momoko_Roshidere_0R.safetensors` | https://civitai.com/models/1516990?modelVersionId=1716323 | Illustrious | sha256 match | 2 | **keep** |  |

### Anima

| File | Upstream page | Base (civitai by-hash) | Disk vs pin | Refs | Status | Note |
|---|---|---|---|---:|---|---|
| `anima-highres-aesthetic-boost.safetensors` | https://civitai.com/models/2540444?modelVersionId=2855073 | Anima | sha256 match | 2 | **keep** |  |
| `anima-huashijw_v2_step10000.safetensors` | https://civitai.com/models/2753686?modelVersionId=3098204 | Anima | sha256 match | 5 | **keep** |  |
| `anima-ke-ta_style_v1.safetensors` | https://civitai.com/models/2852885?modelVersionId=3221815 | Anima | sha256 match | 6 | **keep** |  |
| `anima-kieed_v9_step6000.safetensors` | https://civitai.com/models/2012383?modelVersionId=2972811 | Anima | sha256 match | 5 | **keep** |  |
| `anima-koukouya_v2_step2500.safetensors` | https://civitai.com/models/2696189?modelVersionId=3027537 | Anima | sha256 match | 4 | **keep** |  |
| `anima-newanimastyle-v1.safetensors` | https://civitai.com/models/2830377?modelVersionId=3193726 | Anima | sha256 match | 5 | **keep** |  |
| `anima-turbo-lora-v0.2.safetensors` | https://huggingface.co/circlestone-labs/Anima-Official-LoRAs (also civitai 2560840/2979642) | Anima | sha256 match | 2 | **keep** |  |
| `anima-xilmo-000020.safetensors` | https://civitai.com/models/2683021?modelVersionId=3012652 | Anima | sha256 match | 3 | **keep** |  |
| `BunnyMid_Ani_v1.safetensors` | https://civitai.com/models/2833471?modelVersionId=3197565 | Anima | sha256 match | 2 | **keep** |  |
| `BunnySlop_Ani_v5.56.safetensors` | https://civitai.com/models/2613391?modelVersionId=3174127 | Anima | sha256 match | 2 | **explicit-queue-only** | civitai model flagged nsfw |
| `BunnySlop_Anima.safetensors` | https://civitai.com/models/2613391?modelVersionId=2978487 | Anima | sha256 match | 1 | **explicit-queue-only** | civitai model flagged nsfw |
| `Failleaf_Anima_Base_lora.safetensors` | https://civitai.com/models/2648711?modelVersionId=2974201 | Anima | sha256 match | 1 | **keep** |  |
| `nsfw_girls_anima.safetensors` | https://civitai.com/models/2822856?modelVersionId=3225971 | Anima | sha256 match | 6 | **explicit-queue-only** | civitai model flagged nsfw |
| `pearly_esearu_style.safetensors` | https://civitai.com/models/2897464?modelVersionId=3275865 | Anima | sha256 match | 2 | **keep** |  |
| `pearly_petiflow2.safetensors` | https://civitai.com/models/2794834?modelVersionId=3151811 | Anima | sha256 match | 2 | **keep** |  |
| `rapscallion_cherrypick_min1024_prodigy_lr1_4000_stylepush.safetensors` | https://civitai.com/models/1130747?modelVersionId=3056000 | Anima | sha256 match | 2 | **explicit-queue-only** | civitai model flagged nsfw |
| `sky02Light.safetensors` | https://civitai.com/models/2652568?modelVersionId=2978471 | Anima | sha256 match | 1 | **keep** |  |

### Klein / Qwen / Z-Image / H3

| File | Upstream page | Base (civitai by-hash) | Disk vs pin | Refs | Status | Note |
|---|---|---|---|---:|---|---|
| `A1AnimeGirls_Klein9B.safetensors` | https://civitai.com/models/2497765?modelVersionId=2807775 | Flux.2 Klein 9B | no pin | 0 | **orphan** | civitai "A1 Anime style - Flux.2 Klein 9b"; on disk with no `models/library.json` pin and no preset/graph/recipe reference |
| `aimaginedworlds_turbo_zimage.safetensors` | https://civitai.com/models/2286065?modelVersionId=2572799 | ZImageTurbo | no pin | 0 | **orphan** | civitai "aimaginedworlds: Z-Image Turbo LoRA Guide (Best Version)"; on disk with no `models/library.json` pin and no preset/graph/recipe reference |
| `AniEdit-Klein4B.safetensors` | https://civitai.com/models/2332320?modelVersionId=2623552 | Flux.2 Klein 4B | no pin | 0 | **orphan** | civitai "AniEdit (Flux 2 Klein)"; on disk with no `models/library.json` pin and no preset/graph/recipe reference |
| `AniEdit9B_v2.safetensors` | https://civitai.com/models/2332320?modelVersionId=2642969 | Flux.2 Klein 9B | no pin | 0 | **orphan** | civitai "AniEdit (Flux 2 Klein)"; on disk with no `models/library.json` pin and no preset/graph/recipe reference |
| `anime_style_v1_zimage.safetensors` | https://civitai.com/models/2186181?modelVersionId=2461573 | ZImageTurbo | no pin | 0 | **orphan** | civitai "Anime Style Lora For Z-Image-Turbo"; on disk with no `models/library.json` pin and no preset/graph/recipe reference |
| `elusarca_anime_style_zimage.safetensors` | https://civitai.com/models/2176274?modelVersionId=2450720 | ZImageTurbo | no pin | 0 | **orphan** | civitai "Elusarca's Anime Style LoRA for Z-Image Turbo"; on disk with no `models/library.json` pin and no preset/graph/recipe reference |
| `flux-2-klein-4B-outpaint-lora.safetensors` | https://huggingface.co/fal/flux-2-klein-4B-outpaint-lora | FLUX.2 Klein 4B (pin; not on civitai by hash) | sha256 match | 0 | **keep** | pinned but no preset/graph/recipe reference |
| `Klein9B_Anime_V3_Refined.safetensors` | https://civitai.com/models/2432849?modelVersionId=2825584 | Flux.2 Klein 9B | no pin | 0 | **orphan** | civitai "Mrpopo's Flux.2 Klein 9B anime"; on disk with no `models/library.json` pin and no preset/graph/recipe reference |
| `KleinBase9B_PoseTransfer.safetensors` | https://civitai.com/models/2380153?modelVersionId=2701726 | Flux.2 Klein 9B-base | sha256 match | 1 | **keep** |  |
| `Mannequin_V1_F29B.safetensors` | https://civitai.com/models/2191265?modelVersionId=2689061 | Flux.2 Klein 9B-base | sha256 match | 0 | **keep** | pinned but no preset/graph/recipe reference |
| `minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors` | https://huggingface.co/Comfy-Org/MiniMax-H3 (also civitai 1063735/3213016) | MiniMax H3 | sha256 match | 5 | **keep** |  |
| `Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors` | https://huggingface.co/lightx2v/Qwen-Image-Edit-2511-Lightning (also civitai 2047657/2552889) | Qwen | sha256 match | 5 | **keep** |  |
| `qwen-image-edit-2511-multiple-angles-lora.safetensors` | https://huggingface.co/fal/Qwen-Image-Edit-2511-Multiple-Angles-LoRA (also civitai 2300308/2588352) | Qwen | sha256 match | 0 | **keep** | pinned but no preset/graph/recipe reference |
| `refcontrol_v2_poses.safetensors` | https://civitai.com/models/2732076?modelVersionId=3071631 | Flux.2 Klein 9B-base | sha256 match | 0 | **keep** | pinned but no preset/graph/recipe reference |
| `replace_character_v1_klein.safetensors` | https://civitai.com/models/2829085?modelVersionId=3192138 | Flux.2 Klein 9B | sha256 match | 1 | **keep** |  |
| `z-image-anime-v1.safetensors` | https://civitai.com/models/1994924?modelVersionId=2455794 | ZImageTurbo | no pin | 0 | **explicit-queue-only + orphan** | civitai model flagged nsfw; civitai "Illustrious Anime Collection"; on disk with no `models/library.json` pin and no preset/graph/recipe reference |
