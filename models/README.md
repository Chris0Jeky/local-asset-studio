# Model registry

`installed-manifest.json` records relative model paths, file sizes, SHA-256 values and available source revisions. The files were checksum-verified when originally downloaded. Presence and size can be checked quickly; rehashing every weight is deliberately not part of every launch.

No weights are stored in Git. They remain in the configured ComfyUI `models` directory. This registry does not install a fresh machine automatically.

`library.json` adds the 22 Workflow Lab assets plus the 30 anime/fantasy adapters
below with exact filenames, destination folders, pinned source URLs, sizes,
SHA-256 values, model families and terms.
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
| `krea2_koukouya_sytle_c1-st3000.safetensors` | none | 1.0 | [model 2844656](https://civitai.com/models/2844656?modelVersionId=3211621) | Image, RentCivit, Rent, Sell; derivatives allowed |

NIJISIS was downloaded by the owner on 12 September 2026 (the owner spent the Buzz); its SHA-256 was verified
against the installed file. **koukouya is not installed**: its size and SHA-256 come from the civitai version
metadata, not from a local file, so Studio's **Models & folders** will show it missing until someone fetches
it with an API key or the browser. That is a `HUMAN_TODO.md` item, not an agent decision.

### Acquisition scripts

| Script | Use |
| --- | --- |
| `python scripts/fetch-hf.py --repo <owner/name> --path <file> [--dest-folder loras] [--name <file>] [--dry-run]` | Hugging Face file, verified against the LFS oid in the repository tree |
| `python scripts/civitai-fetch.py --version-id <id> [--file-id <id>] [--dry-run]` | civitai model version, verified against the listed SHA-256; token from `$CIVITAI_API_TOKEN` only |
| `python scripts/intake-downloads.py [--from <dir>] [--dest-folder <folder>] [--dry-run]` | Sort finished browser downloads into the right model folder by safetensors header |

All three refuse to overwrite an existing destination, keep a failed transfer as a `.part` file, append a
receipt to `.runtime/downloads/receipts.json` and print a `library.json` stub to paste in. A moved browser
download has no source checksum, so its receipt records `verified: false` — fill in the provenance by hand.
