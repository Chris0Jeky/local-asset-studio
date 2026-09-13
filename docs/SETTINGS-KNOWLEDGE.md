# Settings knowledge: what the numbers mean and where they came from

`presets/settings-kb.json` is the machine-readable version of this page. The Studio serves it at
`GET /api/knowledge` (file plus sha256), the sweep planner reads its axes, and `scripts/validate-repo.py`
checks its shape. This page is the narrative: per family, what prompt grammar the publisher documents, which
settings are worth sweeping, and which of them anything on this machine has actually rendered.

Three rules kept the file honest:

- **`sources` are URLs that document the setting.** A model card, a LoRA card, a ComfyUI tutorial. Not a forum
  memory, not a recollection.
- **`observed` is local evidence only.** It lists ComfyUI prompt IDs from runs on this PC. As of 12 September 2026 the
  Krea 2 Turbo `steps`, `sampler` and `style_strength` axes carry them; everything else is card-sourced.
- **A recommendation is not a measurement.** Every number below that is not marked observed is a card's claim
  about somebody else's hardware and taste.

## Locally measured Krea 2 runs

Twelve September 2026, RX 9070 XT, all at 768×1152 with seed 281715418 (full records in
`experiments/curated/anime-fantasy-atelier/execution-evidence.json`): NIJISIS @1.0 at 15 steps, 986.6 s;
TextFusion @1.0 + Niji Sweet Spot @1.0 at 15 steps, 941.2 s; the same stack with the 4-step distill LoRA @0.85
at 4 steps, 270.9 s, comparable quality; four further 4-step probes (NIJISIS with its trigger, a fal oil style
stacked on the target pair, a fal watercolor style alone, and `er_sde` in place of `euler_ancestral`) at
170–200 s each. The first of those runs is described below.

| Field | Value |
| --- | --- |
| Prompt ID | `09dadd6e-3e60-4c37-80d1-9244bb8e848d` |
| Stack | Krea 2 Turbo FP8 + `NIJISIS_KREA_2_krea2_3274861_epoch_8.safetensors` @ 1.0 |
| Controls | 768x1152, 15 steps, euler_ancestral / simple, cfg 1, seed 281715418 |
| Result | success, **986.6 s** wall for one image |
| Earlier evidence | 512x768 at 8 steps in 188.7 s |

That single number sets the economics of the whole Krea lane: a 15-step portrait is a commitment, a sweep is
not affordable at that size, and auditions belong at 512x768, at 4 steps with the distill LoRA, or both. The
recipe `krea-witch-nijisis` in `presets/recipes.json` reproduces it exactly, including the prompt text; it is
one of the nine recipes carrying `status: executed` on 13 September 2026 (the first to do so). Note what it does *not* prove: the `@NIJISIS` trigger was never in
that prompt, so the trigger itself is untested here.

## Krea 2 Turbo

Natural-language paragraphs, 30-150 words, in block order: camera and framing, lighting, subject, environment,
expression, pose, style. No negative prompt exists for Turbo - the Studio graphs route the positive
conditioning through `ConditioningZeroOut`, so negative text is ignored rather than weakly applied. No
`ModelSampling*` node belongs in these graphs (the loader applies shift 1.15 already), and FreeU, PAG and
RescaleCFG do nothing useful at cfg 1.

| Axis | Values | Why |
| --- | --- | --- |
| steps | 8, 12, 15 | Distilled for 8 and most LoRA cards quote 8; BArtstyle quotes 12; the owner's target image used 15. Observed locally at 15. |
| sampler | euler, euler_ancestral, er_sde | euler is the ComfyUI tutorial default; euler_ancestral is the Niji Sweet Spot and target-image setting; er_sde is quoted by the koukouya and Fantasy Impressions cards. |
| scheduler | simple, beta | Flow-matching family: only simple, beta, sgm_uniform, normal and linear_quadratic are offered. karras and friends belong to the eps families. |
| style_strength (`lora2`) | 0.6, 0.8, 1.0, 1.2 | fal cards say scale 1.0-1.25; the Niji card allows 0.8-1.5. Drop toward 0.6-0.8 once a second style adapter is on. |
| second_style (`lora3`) | 0, 0.6, 1.0 | The style-pair slot: prove one adapter, blend, or let the second lead. Unmeasured. |
| aspect (`height`) | 1152, 1248, 1536 | Portrait heights the LoRA cards illustrate; 1280x1856 is the koukouya card's own size. All multiples of 16. |

LoRA rules: at most 3 active, warn above 2.5 total strength, ladder 1.0 / 0.8 / 0.6. Order does not matter for
plain adapters chained through `LoraLoaderModelOnly`. A slot at strength 0 is pruned out of the submitted
graph, so an unused slot costs nothing - but the authored graph must still name an installed file, because
ComfyUI validates the combo before execution and rejects a missing filename with HTTP 400 even at strength 0.

Trigger placement follows the card, not a convention: `@NJSW33T` and `@NIJISIS` go at the START, fal style
phrases at the END of a short prompt, the official Comfy-Org style phrases anywhere.

### Installed Krea 2 adapters

| File | Trigger | Strength | Role |
| --- | --- | --- | --- |
| `Krea2_TextFusion_Refusal_Reduction.safetensors` | none | 1.0 | adherence (edits txtfusion, 26 MB) |
| `Niji_Sweet_Spot_Krea2_v2A.safetensors` | `@NJSW33T` (start) | 0.8-1.5 | style, tolerates danbooru tags |
| `NIJISIS_KREA_2_krea2_3274861_epoch_8.safetensors` | `@NIJISIS` (start) | 0.8-1.2 | style, NijiJourney V7 look |
| `krea2_retroanime` / `darkbrush` / `dotmatrix` / `kidsdrawing` / `neondrip` / `rainywindow` / `softwatercolor` / `sunsetblur` / `vintagetarot` | the card's style phrase | 1.0 | official Comfy-Org styles |
| `krea2_turbo_4step_rank_64_lora_comfyui.safetensors` | none | 0.75-1.0 | accelerator: set steps 4, cfg 1 |
| `fal-krea2-<style>.safetensors` (19 installed) | `<style words> style` (end) | 1.0-1.25 | fal style pack, short prompts |

All nineteen fal names are installed (the two that were partial on the morning of 2026-09-12 were re-fetched
and pinned the same day). `krea2_koukouya_style_c1-st3000` - the third adapter in the owner's target image - was
installed on 2026-09-12 with the owner's civitai key (`CIVITAI_API_TOKEN`), so the `krea-atelier-target-stack`
recipe now names all three adapters. A preset or recipe may only name a file that `models/library.json` pins.

## WAI v17 (Illustrious)

Danbooru tags: subject, appearance, clothing, action, setting, lighting and composition, and the quality tail
**last** (`masterpiece, best quality, amazing quality`). Short negative (`bad quality, worst quality, worst
detail, sketch, censor`). Defaults euler_ancestral / normal, 26 steps, cfg 6, 832x1216.

| Axis | Values | Why |
| --- | --- | --- |
| steps | 15, 22, 30 | The listing quotes 15-30; 30 is the authored value in `workflows/api/wai-api.json`. |
| cfg | 5, 6, 7 | Quoted band; above 7 colour burns, below 5 the tags stop landing. |
| sampler | euler_ancestral, dpmpp_2m, dpmpp_2m_sde | Family default plus the deterministic comparison. |
| scheduler | normal, karras | eps family, so karras is available. |

Below 1024 on the short side this family loses anatomy. The documented fix for broken limbs is a 1.5x hires
pass at denoise 0.35-0.5, not more steps. Provenance: installed from a Hugging Face mirror; two mirrors
advertise the same SHA-256, which is mirror agreement, not creator authentication, and the original commercial
terms are still unresolved. The civitai listing returned HTTP 451 from this machine.

## NoobAI XL 1.1

Quality words are a **prefix** here, and they include the year and rating tags: `masterpiece, best quality,
newest, absurdres, highres, safe,` then the tag list. The author's long negative is in the knowledge base
verbatim, furry/feral terms included. Defaults euler_ancestral / normal, 28 steps, cfg 5.5, 832x1216; axes
steps 22/28/32, cfg 5/5.5/7, sampler euler_ancestral or dpmpp_2m, scheduler normal or karras. The installed
file is the epsilon-prediction release, so ordinary CFG and eps schedulers apply - the separate V-pred release
would need different sampling. Licence: Fair-AI Public License 1.0-SD, which forbids commercialising the
generated products. Hobby and research only.

## Animagine XL 4.0

Tag **order** is the mechanism: `1girl/1boy, <character>, <series>, <rating: safe>, <everything else>` then
`masterpiece, high score, great score, absurdres`. For original characters the character and series slots stay
empty rather than borrowing a franchise. Publisher negative is recorded verbatim. Defaults euler_ancestral /
normal, 28 steps, cfg 5, 832x1216; axes steps 25/28, cfg 5/6, sampler euler_ancestral or dpmpp_2m, scheduler
normal or karras. The card documents these sampler, CFG and step values and its own hand-quality limitations.

## Pony V6

The score prefix (`score_9, score_8_up, ... source_anime, rating_safe,`) plus clip skip 2
(`CLIPSetLastLayer -2`) is how this checkpoint was conditioned; dropping either changes the model, not the
style. Keep the negative short. Defaults euler_ancestral / normal, 30 steps, cfg 6, 1024x1024; axes steps
25/30, cfg 6/7, sampler euler_ancestral or dpmpp_2m_sde, scheduler normal or karras. Pony LoRAs are their own
ecosystem: Illustrious and SDXL-base adapters do not transfer reliably.

## Anima (Anima Aesthetic 1.1)

Prose first, tags after: the compact Qwen encoder reads sentences. This family *does* take a negative prompt
(node 5 in the authored graphs). The authored graph is euler / simple, 30 steps, cfg 4.0 at 768x1152, and the
preset's own variants bracket it at 20 and 36 steps; cfg above 5 drifts toward plastic shading. No
Anima-compatible LoRA is installed, and the presets bind no LoRA slot. Weights are CircleStone Labs
Non-Commercial, with separate terms for outputs.

## SDXL, Z-Image Turbo, FLUX.2 Klein, Qwen Image Edit

These four are in the knowledge base so the planner has something to say about every anime-adjacent preset,
not because they are the anime lane.

| Family | Defaults | Axes | Note |
| --- | --- | --- | --- |
| SDXL | dpmpp_2m / karras, 25 steps, cfg 7, 1024x1024 | steps, cfg, sampler, scheduler, style_strength (`lora`) | Covers the LineAni, screentone, cinematic-lighting and pixel-art adapters; sliders read best below 1.0. |
| Z-Image Turbo | res_multistep / simple, 8 steps, cfg 1 | steps 6/8/12, sampler | Distilled; flow-family schedulers only. Apache-2.0. |
| FLUX.2 Klein | euler / simple, 20 steps, cfg 1 | steps 16/20/28 | Samples through `SamplerCustomAdvanced`, so sampler and scheduler are not Studio controls here. |
| Qwen Image Edit | euler / simple, 4 steps, cfg 1 | steps 4/8, denoise 0.6/0.8/1.0 | Edit strength is the interesting axis; the 4-step Lightning adapter is baked into the graph. |

## Family names and aliases

The knowledge base keys families by the exact `family` strings used in `presets/catalog.json` (`Anima`, `SDXL 1.0`, `Qwen Image Edit 2511`, `Krea 2 Turbo`, ...), so `settings_planner.axes_for()` finds a preset's family without aliasing; `family_aliases` only maps the registry spelling `Krea 2` to `Krea 2 Turbo`.

## Recipes and wildcards

`presets/recipes.json` holds 30 saved control sets (13 September 2026), served at `GET /api/recipes` with `available` and
`missing` annotations computed from the installed LoRA list. Each carries `status` (`executed` or
`unverified`), `notes`, `sources`, and - for the one executed recipe - an `evidence` block with the prompt ID
and wall time. Applying a recipe is exactly like applying a variant: it writes the controls, nothing else.

`presets/wildcards/*.txt` are the prompt lists: `medium`, `lighting`, `palette`, `composition`,
`fantasy_setting`, `fantasy_creature`, `anime_style`, `mood`, `time_of_day`, `weather`. One option per line,
`#` comments and blank lines ignored, trailing whitespace stripped. `{a|b|c}` picks one alternative and
`__name__` draws from the matching file; expansion happens per batch member with `random.Random(f"{seed}:{i}")`,
so a seed reproduces its text. The job keeps the template, the submitted graph carries the expanded text. The
entries are written to work in both worlds: danbooru-valid tags for the SDXL families that also read as plain
phrases inside a Krea paragraph. All entries are SFW and the characters are original, with no franchise names
or locations.

## Sources

Model and adapter cards:

- [ComfyUI Krea 2 tutorial](https://docs.comfy.org/tutorials/image/krea/krea-2)
- [Comfy-Org/Krea-2 (official style LoRA trigger table)](https://huggingface.co/Comfy-Org/Krea-2)
- [ilkerzgi/fal-Krea-2-Style-LoRAs](https://huggingface.co/ilkerzgi/fal-Krea-2-Style-LoRAs)
- [lvladikov/Krea2-Turbo-Distill-4step-LoRA](https://huggingface.co/lvladikov/Krea2-Turbo-Distill-4step-LoRA)
- [TextFusion refusal reduction (civitai 2775340)](https://civitai.com/models/2775340)
- [Niji Sweet Spot (civitai 2554999)](https://civitai.com/models/2554999)
- [NIJISIS (civitai 2863875, version 3302337)](https://civitai.com/models/2863875?modelVersionId=3302337)
- [koukouya style, installed 12 September 2026 with a hash receipt (civitai 2844656)](https://civitai.com/models/2844656)
- [Animagine XL 4.0](https://huggingface.co/cagliostrolab/animagine-xl-4.0)
- [NoobAI-XL 1.1](https://huggingface.co/Laxhar/noobai-XL-1.1)
- [WAI v17 mirror](https://huggingface.co/frankjoshua/waiIllustriousSDXL_v170) and
  [Illustrious XL v2.0](https://huggingface.co/OnomaAIResearch/Illustrious-XL-v2.0)
- [Pony Diffusion V6](https://huggingface.co/AstraliteHeart/pony-diffusion-v6)
- [Anima](https://huggingface.co/circlestone-labs/Anima)
- [SDXL base 1.0](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0),
  [LineAni Redmond V2](https://huggingface.co/artificialguybr/LineAniRedmond-LinearMangaSDXL-V2),
  [manga ink screentone](https://huggingface.co/strkyyy/manga-ink-screentone),
  [cinematic lighting slider](https://huggingface.co/ntc-ai/SDXL-LoRA-slider.cinematic-lighting),
  [Pixel Art XL](https://huggingface.co/nerijs/pixel-art-xl), [Hyper-SD](https://huggingface.co/ByteDance/Hyper-SD)
- [Z-Image Turbo](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo),
  [FLUX.2 Klein 4B](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B),
  [Qwen-Image-Edit-2511](https://huggingface.co/Qwen/Qwen-Image-Edit-2511)

Local evidence, in this repo: `models/library.json` (pinned hashes for the pre-existing adapters),
`.runtime/downloads/receipts.json` (verified hashes for the 2026-09-12 downloads, untracked),
`.runtime/probes/witch-nijisis-baseline-09dadd6e.json` (the one measured Krea 2 run, untracked).
Licences were read as far as the listings go; a render is never licence clearance and this page records terms
rather than clearing them.
