# Style-reference research: modern glossy anime / light-novel look on SDXL-family — 14 September 2026

Research report written by a read-only agent from the live civitai and Hugging Face APIs on 2026-09-14 (no downloads,
no generations). `bytes` = the API's `sizeKB` × 1024. "Login" = result of an unauthenticated
`GET https://civitai.com/api/download/models/<versionId>`: `307` redirects anonymously, `401` needs the owner's token.
Licence flags are recorded as the API states them; a LoRA's flags never lift the checkpoint's restriction, and a
completed render is not licence clearance.

## 1. Style LoRAs (Illustrious unless stated)

| Candidate | model / version | file | bytes | sha256 (prefix) | trigger | strength | commercial flags | login |
|---|---|---|---|---|---|---|---|---|
| Mishima Kurone — Konosuba Light Novel Style | 1523528 / 1723753 | `ST_Mishima_Kurone_0R.safetensors` | 202,694,828 | D1E424D0… | `mishimakurone` | not stated | Image, RentCivit, Rent, Sell; derivatives/differentLicense/noCredit true | no |
| Momoko — Roshidere Light Novel Style | 1516990 / 1716323 | `ST_Momoko_Roshidere_0R.safetensors` | 202,694,260 | D80EB6F9… | `momokoroshidere` | not stated | Image, RentCivit, Rent, Sell | no |
| Glossy Anime Style illustriousXL | 1364837 / 1541970 | `glossy_anime_style_illustriousXL-000011.safetensors` | 228,464,188 | C71FB57C… | `glossy_anime_style` | 1.0 | Rent, RentCivit, Image (no Sell) | no |
| Anime Shiny Skin Style | 2597738 / (latest two are Anima builds) | — | — | — | `@anime_shiny_skin` | 1 | RentCivit, Rent | yes |
| Shiny Nai style (Goofy AI) | 618752 / 2786889 | `shiny_nai_ilxl_goofy_remade.safetensors` | 114,428,780 | F6186B47… | `shiny skin, sweat` | 0.7–1.0 | RentCivit, Rent (no Image, no Sell) | yes |
| Glossy, oil-sheen skin [Illustrious] | 2143993 / 2425064 | `Glossy_oil-sheen_skin_Illustrious.safetensors` | 228,477,556 | 944751FC… | `<Glossyoilsheen>` + artist tags | not stated | Sell, Image, RentCivit, Rent | no |
| Konosuba — Fantastic Days STYLE | 1610833 / 1824928 | `Konosuba_Fantastic_Days_v2.0.safetensors` | 456,521,740 | 6D20E168… | `KonosubaFantasticDays-Liver020` (optional) | 1.0 (0.9 with trigger) | Image, RentCivit, Rent (no Sell) | yes |
| Konosuba Style (Synthdark8) | 663943 / 1369394 (Illustrious); 743036 (Pony) | `Konosuba_Illustrious_SD8.safetensors` | 170,639,476 | B2FECB12… | none | not stated | Image, RentCivit, Rent, Sell | no |
| Key style ILL-v2 | 1576278 / 1783696 | `Key style ILL-v2.safetensors` | 256,056,360 | 892E85A6… | `keystyle` | 1.2–1.4 | RentCivit, Rent | yes |
| Detail enhancer IL v2 | 1450571 / 1983243 | `Detail_enhancer_IL_v2.safetensors` | 228,492,876 | 54A203F0… | none | not stated (quality booster) | RentCivit, Image, Rent (no Sell) | yes |
| Gacha Splash Art | 2147789 / 2429263 | `GachaSplash.safetensors` | 114,470,468 | DAB75F10… | `g4ch4, white background, full body` | 0.8 | RentCivit, Rent | yes |
| Light Novel Cover [IL] | 1627370 / 1841876 | `Light_Novel_Cover_IL.safetensors` | 228,456,868 | 6D753CA7… | `lncover` | not stated | **none** (hobby-only in effect) | no |

Verified but not ranked: Konosuba anime-screencap style (1611085 / 1823233, `konosuba_3.safetensors`; wrong idiom, the
author calls it unnecessary), Date a Live LN style (1068447 / 1642422, `Date_a_live_illus.safetensors`, trigger `D4t3`).

## 2. Illustrious-family checkpoints to compare with WAI v17

WAI v17.0 (827184 / 2883731, published 2026-04-23) is still the newest WAI release; nothing newer to chase.

| Checkpoint | model / version | file | bytes | sha256 (prefix) | prediction | settings | commercial flags | login |
|---|---|---|---|---|---|---|---|---|
| Nova Anime XL — IL v19.0 | 376130 / 2940478 | `novaAnimeXL_ilV190.safetensors` | 6,939,105,596 | FA486CAA… | epsilon | Euler a, 20–30 steps, CFG 5–7, clip skip 1–2 | RentCivit, Image, Rent (no Sell) | no |
| iLustMix v11.1 | 1110783 / 2807896 | `ilustmix_v111.safetensors` | 7,105,357,284 | 038DAD76… | epsilon | Euler a, 25 steps | Image, RentCivit, Rent, Sell | yes |
| JANKU v7.77 | 1277670 / 2786084 | `JANKUTrainedChenkinNoobai_v777.safetensors` | 6,938,040,674 | 88177D22… | epsilon | 25–30 steps, CFG 3–5 | RentCivit, Image; **no derivatives, no different licence** | yes |
| Illustrious-XL v2.0-stable | 1489531 / 1684946 | `illustriousXLV20_v20Stable.safetensors` | 6,938,040,674 | C2A1A3EA… | epsilon | 28 steps, CFG 6.5 (recent implementations) | RentCivit, Image; no different licence | yes |
| NoobAI-XL V-Pred 1.0 | 833294 / 1190596 | `noobaiXLNAIXL_vPred10Version.safetensors` | 7,105,350,110 | EA349EEA… | **v-prediction**, Euler only | CFG 4–5, 28–35 steps | RentCivit only; **credit required** | yes |

## 3. Style-reference adapters beyond h94 IP-Adapter

- **NoobAI IP-Adapter Mark 1** — HF `subby2006/noob-ipa`, `noobIPAMARK1_mark1.safetensors`, 1,405,172,056 bytes, licence
  fair-ai-public-license-1.0-sd; mirrored at `r3gm/noob-ipa` under `model_G/`. Needs the **CLIP-ViT-bigG-14** image encoder
  (not installed). Loads through `IPAdapterModelLoader` → `IPAdapterAdvanced`.
- **Style IPAdapter for NoobAI-XL v1.0** — civitai 1233692 / 1390253, `styleIpadapterFor_v10.safetensors`, 702,585,376
  bytes, sha256 C07D3F30…; finetuned from Mark 1 for drawing-style transfer; needs a patched bigG at 448 px and the
  author's own node pack (not the stock cubiq nodes). RentCivit only. Login required.
- **kataragi NoobAI / Animagine IP-Adapters** — HF `kataragi/Noob_ipadapter`, `ip_adapter_Noobtest_800000.bin`
  (1,396,798,350 bytes) and `ip_adapter_test_400000.bin`; creativeml-openrail-m; author says ViT-H but the training
  lineage (h94 `ip-adapter_sdxl.bin`) suggests bigG; author calls it undertrained. `.bin` is not a pinnable suffix in this
  repo's model library.
- **InstantStyle weightings are already installed**: `IPAdapterAdvanced` `weight_type` `style transfer` / `strong style
  transfer` / `style transfer precise` / `composition` / `style and composition`, plus `IPAdapterStyleComposition`
  (`image_style` + `image_composition`, separate weights). Measured on this PC before this report: `style transfer`
  costs 260 s per run with ControlNet against 80 s for `linear` (see `experiments/curated/style-pose/`).
- No CSD style encoder for Illustrious/NoobAI was found.
- Adjacent: `Laxhar/noob_openpose` (`openpose_pre.safetensors`, 2,502,140,008 bytes, no licence declared), a NoobAI-native
  OpenPose ControlNet.

## 4. Multi-image style boards with ComfyUI_IPAdapter_plus

Two documented paths. Equal weight: `LoadImage` × N → `ImageBatch` chain → `IPAdapterAdvanced` (one global `weight`,
`combine_embeds` concat/add/average/norm average; the repo's `examples/ipadapter_combine_embeds.json`). Per-image weight:
one `IPAdapterEncoder` per picture (`weight` −1..3) → `IPAdapterCombineEmbeds` (`embed1` + up to four optional embeds,
method concat/add/subtract/average/norm average/max/min) → `IPAdapterEmbeds` (`weight`, `weight_type` linear family only,
`start_at`, `end_at`, `embeds_scaling`; the repo's `examples/ipadapter_weighted_embeds.json`, encoders at 1.5 and 0.6,
average, applied at 0.8 linear). The Studio's style board uses the encoder path.

## Ranked "install first"

1. Mishima Kurone — Konosuba Light Novel Style (1723753, 202 MB, no login).
2. Run the installed InstantStyle weight types before any adapter download (done: linear wins on time here).
3. Glossy Anime Style illustriousXL (1541970, 228 MB, no login, weight 1.0).
4. Nova Anime XL IL v19.0 (2940478, 6.94 GB, no login) as the same-seed A/B against WAI v17.
5. kataragi `ip_adapter_Noobtest_800000.bin` only if the installed adapter proves insufficient (and only if `.bin`
   becomes pinnable).

## Could not verify

Whether an Illustrious build of Anime Shiny Skin exists; creator strengths for six LoRAs (start 0.7–0.8); which encoder
kataragi's adapter really wants; SHA-256 for the Hugging Face files (no `lfs.oid` in the `?blobs=true` responses read);
licence text for `Laxhar/noob_openpose` and `r3gm/noob-ipa`; a civitai id for noobIPAMARK1; and, above all, whether any
of these produce the target look — nothing was generated.
