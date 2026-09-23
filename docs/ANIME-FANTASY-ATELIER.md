# Anime & fantasy atelier

The practical guide to the anime and fantasy side of Studio: which recipe to open for which look, what
every installed LoRA does, the settings each model family actually wants, and how long a render really
takes on this machine. Written 12 September 2026.

Everything here is a starting recipe. A finished render is neither art acceptance nor licence
clearance; see [What "verified" means](#what-verified-means) and [Terms](#terms-and-territory).

## Pick a route

| You want | Open (category · preset id) | Why |
|---|---|---|
| Painterly anime character, the owner's target look | Anime flagship · `krea-anime-atelier`, recipe *painterly witch (NIJISIS)* | Krea 2 Turbo with the Niji/NIJISIS adapters; natural-language prompt |
| Same subject, faster audition | same preset, variant **Fast 8-step euler** or **4-step audition** | 8 steps is the distilled default; the 4-step LoRA is faster still |
| Illustration style study (watercolour, ink, oil, tarot…) | Anime flagship · `krea-style-lab` | Two style slots you mix; each fal/Comfy-Org LoRA has its own trigger |
| A retro-anime Krea starting point that already ran | Anime flagship · `krea-portrait` / `krea-environment` | Existing recipes, now with sampler/scheduler and a LoRA slot |
| Crisp tagged anime portrait | Anime quality · `anime-wai-quality` / `anime-animagine-quality` | Illustrious/Animagine grammar, Danbooru tags, fast |
| Hobby-only tagged anime with a different aesthetic | Experimental · `noob` | Licence excludes commercial products |
| Score-tag vocabulary and pose-heavy work | Characters · `pony`, `wai-pose` | Pony needs the `score_*` prefix and clip skip 2 |
| Fantasy scenery rather than a character | Variant **Fantasy environment** on the SDXL anime presets, or `krea-environment` | Danbooru lighting/composition vocabulary |
| Line art, screentone, manga studies | Manga & style · `lineani-portrait`, plus the screentone LoRA | See [anime detailing](ANIME-DETAILING.md) |
| A whole settings sweep instead of one image | **Experiments → Plan from settings library** | See [the planner](#the-planner) |

Start at the cheapest thing that answers your question. On Krea 2 that means 512×768 or the 4-step
LoRA; save 768×1152 at 15 steps for a shot you already like.

## The LoRA table

All files live in ComfyUI `models/loras/`. Strength columns are the author's documented range.
Checksums, byte sizes and full source URLs are pinned in [`models/library.json`](../models/library.json);
[`models/README.md`](../models/README.md) carries the provenance narrative.

### Krea 2 Turbo adapters

| File (`.safetensors`) | Trigger | Position | Strength | Source | Terms |
|---|---|---|---|---|---|
| `Krea2_TextFusion_Refusal_Reduction` | none | — | 1.0 | [civitai 2775340](https://civitai.com/models/2775340?modelVersionId=3125118), HF mirror `Quiho/Krea2_TextFusion_Refusal-Reduction_LoRA_v1.0_lora` | Krea 2 community licence per the listing; PDF not read |
| `Niji_Sweet_Spot_Krea2_v2A` | `@NJSW33T` | start of prompt | 0.8–1.5 | civitai (recorded in the registry) | third-party LoRA terms recorded, not cleared |
| `NIJISIS_KREA_2_krea2_3274861_epoch_8` | `@NIJISIS` | start of prompt | 1.0 | [civitai 2863875](https://civitai.com/models/2863875?modelVersionId=3302337) | civitai `allowCommercialUse: Image, RentCivit, Rent`; downloaded by the owner 2026-09-12 |
| `krea2_retroanime` | `purple retro anime style` | with the style phrase | 1.0 | Comfy-Org official LoRA set | Krea 2 community licence |
| `krea2_darkbrush` | `monochrome ink wash style` | " | 1.0 | Comfy-Org | " |
| `krea2_dotmatrix` | `monochrome stippling style` | " | 1.0 | Comfy-Org | " |
| `krea2_kidsdrawing` | `naive expressive sketch style` | " | 1.0 | Comfy-Org | " |
| `krea2_neondrip` | `textured abstract style` | " | 1.0 | Comfy-Org | " |
| `krea2_rainywindow` | `rainy window style` | " | 1.0 | Comfy-Org | " |
| `krea2_softwatercolor` | `art deco watercolor style` | " | 1.0 | Comfy-Org | " |
| `krea2_sunsetblur` | `ethereal motion blur style` | " | 1.0 | Comfy-Org | " |
| `krea2_vintagetarot` | `vintage tarot style` | " | 1.0 | Comfy-Org | " |
| `krea2_turbo_4step_rank_64_lora_comfyui` | none | — | 0.75–1.0 (use **4 steps**, cfg 1) | Comfy-Org distill | Krea 2 community licence |
| `fal-krea2-<name>` (19 files) | the name with spaces plus ` style` | **end** of a short prompt | 1.0–1.25 | fal style LoRA set | third-party terms recorded, not cleared |

The nineteen fal styles are `airy-anime-watercolor`, `amber-dusk-anime`, `azure-cel-shaded`,
`azure-manga-bloom`, `cel-shaded-daytime-anime`, `cobalt-sky-anime`, `chibi-watercolor-pastel-anime`,
`baroque-dreamscape-oil`, `amber-lit-fantasy-filmset`, `azure-sunlit-storybook`, `dark-fantasy-film`,
`crimson-blue-inkline-fantasy`, `emerald-fantasy-paperback`, `bold-impasto-sunlit`,
`dark-chiaroscuro-oil`, `cozy-storybook-gouache`, `detailed-manga-inkwork`, `aged-tempera-fable`,
`emerald-lamplight-oil`. Trigger example: `fal-krea2-airy-anime-watercolor` →
`airy anime watercolor style` at the end of the prompt.

**koukouya (Krea 2), installed 12 September 2026:** `krea2_koukouya_style_c1-st3000` (no trigger; the author
documents 1280×1856 or 1536×1536, weight 1.0, `er_sde`/`simple`, 8–10 steps). Fetched with
`scripts/civitai-fetch.py` once the owner's key was in `CIVITAI_API_TOKEN`; the receipt hash matches the
listing. The `krea-atelier-target-stack` recipe now carries all three adapters of the target image.

### Anima adapters (civitai, installed 12 September 2026)

Anima base v1.0 (`anima-base-v1.0.safetensors`) is the checkpoint behind the owner's second baseline,
[civitai image 139608451](https://civitai.com/images/139608451): no text prompt at all, six style adapters,
Euler a, `simple`, 30 steps, cfg 4, 1328×1776. The `anima-artist-stack` preset binds all six as slots at
exactly those strengths. `LoraLoaderModelOnly` loads the LyCORIS (LoCon) file like any LoRA.

| File | Trigger | Reference strength | Notes |
|---|---|---|---|
| `anima-xilmo-000020` | — | 0.7 | lead style of the reference stack |
| `anima-huashijw_v2_step10000` | `@hu45h11w` | 0.6 | artist style |
| `anima-koukouya_v2_step2500` | `@40u40uya` | 0.3 | Anima base also knows the plain `@koukouya` tag |
| `anima-ke-ta_style_v1` | — | 0.7 | |
| `anima-newanimastyle-v1` | — | 1.0 | civitai lists it as V1-390a; renamed on intake |
| `anima-kieed_v9_step6000` | `@k144d` | 0.5 | LyCORIS/LoCon |
| `anima-turbo-lora-v0.2` | — | 1.0 with 8 steps, cfg 1 | official accelerator (Hugging Face), not a style |

The adapter-free painterly look of [images 131843207–131843406](https://civitai.com/images/131843377)
needs no file at all: Anima base with `@synswt, @koukouya, @kyano \(kyanora3141\)` at the start of a tag
prompt, cfg 3, `dpmpp_2m_sde_gpu`, `simple`, 30 steps, 832×1216, negative
`worst quality, low quality, score_1, score_2, score_3, pink theme, cropped, out of frame`. That is the
"Artist tags, no adapters" variant and the `anima-painterly-artist-tags` recipe.


### SDXL adapters

| File | Trigger | Strength | Use |
|---|---|---|---|
| `pixel-art-xl` | — | 0.6–1.0 | pixel props; compare strengths on a fixed seed |
| `LineAniRedmondV2-Lineart-LineAniAF` | see the model card | 0.6–1.0 | line art |
| `manga-ink-screentone` | — | 0.4–0.8 | screentone texture |
| `cinematic lighting` | — | 0.3–0.8 | lighting push on any SDXL anime preset |
| `Hyper-SDXL-8steps-CFG-lora` | — | 1.0 with 8 steps | fast auditions |

## LoRA slots and pruning

`anima-artist-stack` exposes six adapter slots, `krea-anime-atelier` and `krea-refine` four, `krea-style-lab`
three, the SDXL anime presets two and the retro-anime pair one. Every slot is a pair of controls: a
strength (`lora` … `lora6`) and a filename (`lora_name`, `lora2_name`, …). The
filename select lists the LoRAs ComfyUI actually reports as installed.

- **Strength 0 means off.** Before submitting, Studio removes every LoRA node whose strength is 0 and
  rewires the graph around it, repeatedly, so chains collapse cleanly. You get the same graph you
  would have authored without that adapter — no "loaded at 0" placeholder.
- The authored graph always references installed files, because ComfyUI rejects an unknown
  `lora_name` with HTTP 400 *before* execution, even at strength 0.
- Keep at most three adapters active on Krea 2. Total strength above roughly 2.5 tends to fight itself; a
  sensible ladder when stacking is 1.0 / 0.8 / 0.6. Anima's reference stack is the exception: six adapters
  totalling 3.9, each a partial style, with the lead at 0.7.
- TextFusion and NIJISIS both edit the same text-fusion path. Stacking them is allowed and untested
  here; treat a combined result as an experiment, not a known-good recipe.
- The saved job recipe keeps strengths *and* filenames verbatim, so an evidence record names the
  exact stack.

## Per-family settings

### Krea 2 Turbo (`krea2_turbo_fp8_scaled`)

Loader chain is fixed: `CLIPLoader(type="krea2", qwen3vl_4b_fp8_scaled)` plus the Qwen image VAE, with
`ConditioningZeroOut` as the negative. **Do not add a ModelSampling\* node** — the loader already
applies shift 1.15. FreeU, PAG and RescaleCFG do nothing useful on this model. Turbo has no usable
negative prompt: leave it empty and say what you want instead of what you do not.

| Setting | Value |
|---|---|
| Steps | 8 default (distilled); 12 for more structure; 15 was the owner's target; 4 only with the 4-step LoRA |
| CFG | 1.0 |
| Sampler | `euler` (safe), `euler_ancestral` (target look), `er_sde` (koukouya-style cards), `res_multistep`, `dpmpp_2m` |
| Scheduler | `simple`, `beta`, `sgm_uniform`, `normal` — flow models do not take `karras`/`exponential` |
| Resolution | 768×1152, 832×1248, 1024×1024, 1152×768, 1024×1536; 1280×1856 is the koukouya card's suggestion |
| Denoise | 1.0 |

Prompt style is a **natural-language paragraph of 30–150 words**, ordered camera/framing → lighting →
subject → environment → expression → pose → style. No Danbooru quality soup, with one exception: Niji
Sweet Spot was trained on tag-ish prompts and accepts them. Put `@NJSW33T` or `@NIJISIS` at the
*start*; put a fal style trigger at the *end* of a short prompt.

### Anima base v1.0 (`anima-artist-stack`)

Loader chain: `UNETLoader(anima-base-v1.0)`, `CLIPLoader(qwen_3_06b_base, type="stable_diffusion")`, the Qwen
image VAE, a real negative prompt. This is the official ComfyUI "Anima base v1" template minus its subgraph.
The compact Qwen encoder reads sentences and tags alike; artist tags take an `@` prefix.

| Setting | Value |
|---|---|
| Steps | 30 (template and both references); 8 only with the official turbo LoRA at cfg 1 |
| CFG | 4 (template, six-adapter reference); 3 for the painterly artist-tag look |
| Sampler | `euler` (template), `euler_ancestral` (six-adapter reference), `dpmpp_2m_sde_gpu` (artist-tag references) |
| Scheduler | `simple` |
| Resolution | 832×1216, 1024×1024, 1248×1824, 1328×1776 (16-pixel grid) |
| Negative | `worst quality, low quality, score_1, score_2, score_3, blurry, jpeg artifacts, sepia` |

Executed 12 September 2026 on base v1.0: the authored six-adapter stack (24 s at 832×1216), the adapter-free artist-tag
variant (20 s) and the 1328×1776 reference (66 s), all clean; both artist-driven looks tend to hallucinate a small
signature glyph in a corner; crop it when it matters (`anime-detail-fix` only repaints detected faces and hands, so it
will not remove a corner mark).

### SDXL anime families

| Family | Prompt grammar | Negative | Sampler / scheduler | Steps | CFG | Resolution |
|---|---|---|---|---|---|---|
| **WAI v17 (Illustrious)** | tags, then tail `masterpiece, best quality, amazing quality` | `bad quality, worst quality, worst detail, sketch, censor` | `euler_ancestral` / `normal` | 15–30 | 5–7 | 1024×1024 minimum; 832×1216, 1024×1344 |
| **Animagine XL 4.0** | `1girl/1boy, <character>, <series>, <rating>, <everything else>, masterpiece, high score, great score, absurdres` | `lowres, bad anatomy, bad hands, text, error, missing finger, extra digits, fewer digits, cropped, worst quality, low quality, low score, bad score, average score, signature, watermark, username, blurry` | `euler_ancestral` / `normal` | 25–28 | 5–6 | 832×1216, 1024×1024, 1216×832 |
| **NoobAI XL 1.1** (epsilon file) | prefix `masterpiece, best quality, newest, absurdres, highres, safe,` then tags | `worst quality, low quality, worst aesthetic, lowres, bad anatomy, bad hands, text, error, missing fingers, extra digits, fewer digits, cropped, jpeg artifacts, signature, watermark, username, blurry, mammal, anthro, furry, ambiguous form, feral` | `euler_ancestral` / `normal` | 28 | 5–7 | 832×1216 |
| **Pony V6** | prefix `score_9, score_8_up, score_7_up, score_6_up, score_5_up, score_4_up, source_anime, rating_safe,` and clip skip 2 (`CLIPSetLastLayer -2`) | short; long negatives hurt | `euler_ancestral` / `normal` | 25–30 | 5–7 | 832×1216 |

These four may also use `karras`, `exponential`, `kl_optimal` and `ddim_uniform`. WAI's limb problems
usually respond to a 1.5× hires pass at denoise 0.35–0.5 rather than to more steps.

**Fantasy vocabulary** for all four is Danbooru lighting and composition tags: `backlighting`,
`light rays`, `dappled sunlight`, `chiaroscuro`, `rim lighting`, `volumetric lighting`, `glowing`,
`sparkle`, `dutch angle`, `from below`, `cowboy shot`, `wide shot`, `depth of field`, `scenery`,
`fantasy`, `magic circle`, `floating particles`. Do not paste these into a Krea 2 prompt; describe the
same thing in a sentence.

## Recipes

`presets/recipes.json` holds complete, named starting points — a preset plus every control, including
the LoRA stack and seed. In **Create**, the **Recipes** select is filtered to the current preset's
family; choosing one applies its controls exactly as a variant does, and shows its notes, sources and
status. `GET /api/recipes` returns the same list annotated with `available` and `missing` so a recipe
that needs a LoRA you do not have is flagged rather than silently failing at submission.

A recipe's `status` is `executed` only when a local prompt ID backs it; otherwise it is `unverified`
and the settings come from the model or LoRA card, not from a run on this machine.

## Wildcards

Any positive or negative prompt may contain wildcards; they expand server-side, per batch member,
deterministically from that member's seed — so a recipe and its seed reproduce the same expansion.

- `{a|b|c}` picks one option. Nesting one level of braces inside is fine.
- `__name__` picks a line from `presets/wildcards/name.txt` (one option per line, `#` comments).
  Unknown names are left literal. Recursion stops at depth 4.
- Available lists: `medium`, `lighting`, `palette`, `composition`, `fantasy_setting`,
  `fantasy_creature`, `anime_style`, `mood`, `time_of_day`, `weather`,
  `lazy_color_character` (Times Lazy adult-illustration character lines),
  `Breastsrandom` (nested size tags used by that pack).
- Create shows one chip per list under the prompt; clicking inserts `__name__`.
  Recipes **AniFox v2 - lazy color character study** and **Anima v1 - lazy color character study**
  already use the pack as a four-seed audition.

Example (SDXL): `1girl, solo, __fantasy_creature__, __lighting__, {forest|ruins|library}, scenery`.
Example (Krea): `… lit by __lighting__, standing in __fantasy_setting__ …`.

The submitted graph carries the expanded text — that is what evidence records — while the job's saved
controls keep the template, so you can rerun the same template with a new seed.

## The planner

**Experiments → Plan comparison** still takes one numeric axis. Two new buttons read the settings
knowledge base (`presets/settings-kb.json`, served at `GET /api/knowledge`) instead:

- **Plan from settings library** builds a grid over the KB axes that your preset actually binds
  (steps, sampler, scheduler, style strength…). Values for sampler and scheduler are intersected with
  the preset's own `choices`, so you cannot plan an impossible run. The first axis varies slowest, and
  the product is truncated to eight variants; remove variants with ✕ to fit your generation budget.
- **Remix LoRA weights** varies the strengths of the slots that are currently on, over the family's
  documented ladder, one slot per variant plus one "everything at the second rung" variant.

Each variant arrives with a label, a rationale and the source URLs the setting came from; the plan
records the KB checksum so a later reader knows which revision of the knowledge base produced it.
Planning reserves nothing — it submits only when you press **Start comparison**, and the existing
generation budget still applies. The narrative behind the knowledge base is in
[SETTINGS-KNOWLEDGE.md](SETTINGS-KNOWLEDGE.md).

## The owner's creative review (12 September 2026)

Recorded from the owner's message, not inferred (full wording in [HUMAN_TODO.md](../HUMAN_TODO.md)):
`krea-anime-atelier` "genuinely great"; every Krea witch probe with the target stack "very good" (er_sde,
15-step, 4-step) or "good" (baroque oil, airy watercolour); NIJISIS baseline "potential but imperfect", its
4-step run "very good"; `krea-style-lab` nice from afar but the foxes lose detail and their faces morph;
WAI okay-ish with imperfections; NoobAI has potential but six fingers; Pony "a complete mess". Almost every
image carries a small imperfection the owner would like corrected by a follow-up workflow.

## The correction pass

Four presets answer that. `anime-detail-fix` and `krea-refine` accept a reference upload or their authored example; `anime-masked-repair` and `sdxl-inpaint-fix` require their own real RGBA PNG with a transparent repair region.

From a gallery image or its Workspace details, choose **Fix hands & face** to open `anime-detail-fix`,
or **Refine image** to open `krea-refine`. The Studio attaches that image and retains its source asset
identity in saved setups and generated recipes. Review the prompt, denoise and other settings, then
press **Generate** explicitly. Opening either action does not start a render or approve its output.

- **`anime-detail-fix`** — the ADetailer pattern in ComfyUI: Impact Pack `FaceDetailer` twice, first with
  the `face_yolov8s` detector, then with `hand_yolov8n`, repainting only the detected crops with WAI v17 at
  denoise 0.4 (faces) / 0.45 (hands). Nothing outside the boxes changes. It is model-agnostic on the input
  side, so a Krea, Anima or SDXL image all go through the same pass; the repaint style is WAI's, which suits
  anime faces and hands. Only two settings have actually been measured on this machine. The repair that fixed
  the six-fingered NoobAI hand (job `14caa4fb`, 36.2 s, at the cost of a slight expression shift in the face
  crop) ran the **authored graph values, 0.4 face / 0.45 hand** — its recipe carries no `denoise` control. The
  Create UI now preserves that pair: **Denoise changes the face only**, while hands stay at **0.45**.
  **Lighter face (face 0.30 / hand 0.45)** and **Stronger face (face 0.55 / hand 0.45)**
  name both strengths. Neither new face-only variant has been rerun. Changing face Denoise to zero
  does not disable hand repainting; use a different workflow when hands must remain unchanged.
  To adjust hand strength independently, select **WAI Auto Hand Detail** (`anime-hand`) in Studio,
  or open the shipped [27 - WAI Auto Hand Detail](../workflows/comfyui/27%20-%20WAI%20Auto%20Hand%20Detail.json)
  in ComfyUI and adjust its `FaceDetailer` denoise. This is a separate **hand-only** pass, not the combined
  face/hand recipe; it does not inherit the combined repair's quality evidence.
  The earlier **Gentle (0.3 for both)** trial is historical, not the current Lighter face variant:
  it sharpened the face but left the extra digit (job `e4e49006`, 42.3 s,
  `target_defect_fixed: false`). Old coupled recipes keep their embedded graphs; Studio's exact-recipe
  check refuses to silently reinterpret them through the changed binding. See the
  [binding reconciliation](reconciliation/2026-09-14-detail-denoise.md) for the measured recipe and limits.
  *Correction, 23 September 2026 (agent review, full-resolution crop; [docs/quality/QUALITY-BACKLOG.md](quality/QUALITY-BACKLOG.md)):* after job `14caa4fb` the raised hand still has six digits (two tall fingers, a thumb across the palm, three fingers on the right), the same structure as the original. The pass redrew the hand (mean pixel change about 9 levels in its box) without fixing the count, so this is not a proven hand repair. A masked hand inpaint is the next thing to try.
- **`krea-refine`** — a global img2img polish for Krea 2 pictures: Qwen-VAE encode, re-sample at denoise
  0.35 for 4 steps with the distill LoRA and the target-stack adapters, decode. It tightens mushy small
  faces (the foxes) while keeping the composition; "Redraw" at 0.5 changes more.
  *Correction, 23 September 2026 (agent review; [docs/quality/QUALITY-BACKLOG.md](quality/QUALITY-BACKLOG.md)):* the fox faces did get eyes and snouts, but the run also turned three or four small foxes into two large ones and scattered white snow specks over the frame. Its prompt was the preset's example ("two red foxes ... on a snowy hill under a starry night sky"), not the shrine's. Give the source picture's own prompt when refining.
- **`anime-masked-repair`** — a manual local option when a detector crop is the wrong shape. Select it from
  **Anime quality**, then upload a real **RGBA PNG** with both dimensions divisible by 8: retain the image in RGB, leave every protected area
  opaque, and make only the broken hand or other repair area transparent. Prepare refuses JPG, WebP, RGB-only and fully opaque uploads before queueing; it does not pad or crop an unaligned source. The existing core `LoadImage` alpha
  output is grown by 12 px and feathered (a blurred edge), and that soft mask drives both the latent noise mask
  and the final composite, so the workflow re-samples the manual region with WAI v17 at its authored 0.6 denoise
  and blends it into the supplied source without a seam. Studio preserves the uploaded RGBA bytes when staging the
  input, but it has no mask painter or automatic hand-anatomy guarantee. Measured 23 September 2026 on the
  six-digit NoobAI hand (`experiments/curated/overnight-20260923/hand-inpaint/`, straight against ComfyUI with this
  preset's own submitted graphs): the old 0.4 default left the extra digit on 3 of 3 seeds, 0.6 gave five digits on
  3 of 3 with the gesture and painterly shading kept, and the old hard mask edge left a visible seam where it cut
  the background light streak, which the feathered mask removed. Proved through the Studio on 23 September 2026
  (job `1f9b3e11`, 27 s): five digits and no seam on the same hand at the new defaults.
- **`sdxl-inpaint-fix`** (**WAI • Fooocus inpaint repair**) — the same manual RGBA upload as
  `anime-masked-repair`, but the repaint runs through the **Fooocus inpaint patch** that is already installed,
  so the model is conditioned on the surrounding picture instead of re-imagining the hole from noise. That is
  what makes a fairly high denoise usable: a plain masked resample that high tends to invent a new subject,
  while the patched model redraws the region and keeps it attached to the art around it. The alpha mask is
  grown 8 px and the same grown mask drives both the encode and the final composite. For a hard-edged alpha
  the composited area and the regenerated area are the same region; a feathered edge is composited but only
  partly regenerated, because the sampler's noise mask keeps the fractional values while the composite blends
  them. Authored at **denoise 0.7**, with **Gentle (0.5)** as the first try and **Redraw (1.0)** when the
  region has to be rebuilt from nothing.

  One wiring detail is load-bearing and easy to get wrong. ComfyUI's core *VAE Encode (for Inpainting)*
  erases every masked pixel to 0.5 grey before encoding, so the pack's README states plainly that with it
  "denoise strength must be 1.0" — anything lower starts the sampler from a partly grey latent. The
  documented route for sub-1.0 denoise is the pack's own **VAE Encode & Inpaint Conditioning**
  (`INPAINT_VAEEncodeInpaintConditioning`): it keeps the real image in the sampled latent and puts the erased
  copy in the conditioning, exposing `latent_inpaint` for *Apply Fooocus Inpaint* and `latent_samples` for the
  sampler. This preset uses that node, which is what makes 0.5 and 0.7 legitimate here.

### Which correction to reach for

| Situation | Preset | Why |
| --- | --- | --- |
| A face or hand a YOLO detector can find, anywhere in the picture | `anime-detail-fix` | Fully automatic: it crops, repaints and pastes back. No mask to prepare. An undetected hand is an unfixable hand. |
| Detector fires but the crop is the wrong shape, or a hand needs its fingers redrawn in place | `anime-masked-repair` | Manual region, feathered edge, denoise 0.6: fixed a six-digit hand on 3 of 3 seeds without changing the gesture (23 Sep). |
| The region has to be genuinely redrawn — a mangled hand, a missing prop, a hole the detector crop cannot contain | `sdxl-inpaint-fix` | The Fooocus patch is what survives a high denoise without inventing a new subject. |
| The source is a Krea 2 Turbo, Anima Turbo or z_image_turbo render | none of these | The Fooocus patch does not work on distilled merges; see the note below. |
| The whole Krea 2 image is soft rather than locally broken | `krea-refine` | Global img2img polish; no mask. |

**`sdxl-inpaint-fix` is SDXL-only.** The Fooocus inpaint patch works on SDXL checkpoints — WAI v17, NoobAI,
Animagine, Pony, RealVisXL — and does **not** work on distilled merges: Krea 2 Turbo, Anima Turbo and
z_image_turbo are not supported by it. For those families the equivalent route is the native
`DifferentialDiffusion` node with a blurred mask; that is a mention here, not a preset in this repo yet.

**`sdxl-inpaint-fix` is unverified.** Nothing has been submitted through it: no prompt ID, no timing, no
inspected output. It stays `verified: false` until one deliberately submitted repair is run, inspected and
recorded in `experiments/curated/anime-fantasy-atelier/`. Its node classes, links and both patch filenames
(`fooocus_inpaint_head.pth`, `inpaint_v26.fooocus.patch`) were checked against ComfyUI's `/object_info`
schema, which is a read and proves nothing about the picture that comes out. The three denoise values are
read from the installed pack, not measured here: 0.7 is its refine example workflow, 1.0 is what its other
four example workflows use, and 0.5 is an interpolation inside the 1–100% range its README documents for the
refine workflow. Licence facts stay recorded and
uncleared: WAI's terms are unresolved, the Fooocus patch mirror carries no licence tag, and upstream Fooocus
is AGPL-3.0.

The recorded 12 September **Gentle (0.3)** trial sharpened the NoobAI portrait's face but retained its
extra digit. That run is preserved as an unsuccessful hand-repair candidate; lowering denoise alone
is not a verified cure for an extra finger. See the [exact trial evidence](../experiments/curated/anime-fantasy-atelier/anime-detail-fix-gentle-evidence.json).

None of them is a hires-fix; upscaling stays with the existing ESRGAN handoff. Execution results, when a pass has
been run, are in `experiments/curated/anime-fantasy-atelier/`.

## Timing reality

Measured on this PC (ComfyUI 0.35.0, ROCm 7.2.1, RX 9070 XT 16 GB, 32 GB RAM):

| Run | Time | Evidence |
|---|---|---|
| Krea 2 Turbo, 768×1152, 15 steps, NIJISIS @1.0 | **986.6 s** | ComfyUI prompt `09dadd6e-3e60-4c37-80d1-9244bb8e848d`, 12 Sep 2026 |
| Krea 2 Turbo, 768×1152, 15 steps, TextFusion @1.0 + Niji Sweet Spot @1.0 | **941.2 s** | prompt `412b3c9f-162b-434b-a2a6-e57635f82da1` |
| same stack + 4-step distill LoRA @0.85, 4 steps | **270.9 s** | prompt `d7bd3104-f348-46e6-811e-3b1d918c75c3`; quality on par with 15 steps |
| `krea-anime-atelier` "4-step audition" through a Studio job | **197.0 s** | job `db02f6b1-8346-4361-a432-7734fc72d2c2` |
| `wai` / `noob` / `anime` / `pony` fantasy portraits, 832×1216, 28–30 steps (Studio jobs) | **26–30 s** each | see `experiments/curated/anime-fantasy-atelier/` |
| Krea 2 retro-anime, 512×768, 8 steps | **188.7 s** | prompt `144048d4-d6ea-4142-87f5-bdf11d87031c` |
| Manga Line Art (SDXL), 512×768, 20 steps | **34.2 s** | prompt `6e37e90d-ef45-4e07-af31-045b4938fe53` |
| Anima Aesthetic (SDXL), 512×768, 24 steps | **20.0 s** | prompt `6d136e16-132f-4964-a07b-988a2a34b5ac` |

Read that honestly: **Krea 2 is one to two orders of magnitude slower than SDXL here.** The 986 s run
is a single observation and VRAM offload is the suspected cause, not a benchmark of the model. The
practical consequences:

- Audition on Krea at 512×768, or with the 4-step LoRA, before spending a 15-minute render.
- A four-variant Krea grid at 768×1152 is roughly an hour of wall clock. Plan it deliberately.
- Sweeps belong on SDXL; Krea gets the final frame.
- Never re-submit a job whose outcome is uncertain. Keep the prompt ID; a lost prompt ID is evidence
  lost, not a reason to run again.

## What "verified" means

`verified: true` on a preset means one real generation went through *this* preset and a human looked
at the output. It is not set by the schema validator, by `validate-live.py`, or by a successful run of
an earlier version of the graph. Every preset added or restructured in this pass ships
`verified: false` until someone runs it and records the prompt ID.

A recipe's `evidence` block, when present, names the prompt ID, the wall-clock seconds and what the
run actually was. The Krea probe above was submitted through the ComfyUI API before the preset
existed, so it proves the model/LoRA combination, not the preset's bindings.

Record, never infer. See [studio execution evidence](../.claude/skills/studio-execution-evidence/SKILL.md)
for the recording ritual and [EXPERIMENTS.md](EXPERIMENTS.md) for bounded comparisons.

## Terms and territory

- Krea 2 and its official LoRAs carry the Krea 2 community licence; the listing was read, the PDF was
  not.
- Third-party Krea LoRAs (Niji Sweet Spot, NIJISIS, the fal set, koukouya) have their own terms. They
  are **recorded** in `models/library.json`, not cleared for any particular use. NIJISIS's civitai
  metadata says `allowCommercialUse: Image, RentCivit, Rent`.
- NoobAI's Fair-AI Public License 1.0-SD excludes commercial products.
- WAI came from a Hugging Face mirror; matching hashes do not authenticate its creator.
- Hunyuan3D 2.1 and HY-Motion 1.0 exclude UK use.

A completed render is not licence clearance. Check [models/README.md](../models/README.md) before any
non-hobby use.
