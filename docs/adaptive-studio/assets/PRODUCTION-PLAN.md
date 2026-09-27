# Asset production plan

Written 27 September 2026, after the owner lifted the artwork deferral (`adaptive-pilot-world` in `HUMAN_TODO.md`). This plan
routes all 154 catalogue requests to one production route each, orders them into small waves and names the first one. It
adds no art. Art acceptance stays the owner's call at every stage; a route or a receipt is never acceptance.

**Assumption:** the pilot world is Retro Anime / Night Shift with a same-camera Quiet Morning still, as the kit proposes.
Reason: the owner lifted the deferral without naming a world, and every existing pilot document assumes this one.
Reversible by: naming another world under `asset-plan-2026-09-27` in `HUMAN_TODO.md`; only wave 1's environment rows change.

## Routes

| Route | Who runs it | What it is for |
| --- | --- | --- |
| `local-comfyui` | the GPU lab session, through the Studio | Scenes that need a 16:9 canvas, registration with an anchor, a seed and a prompt ID, or an honest "made by this Studio" claim |
| `chatgpt-image` | the owner, in ChatGPT (free for them) | Original illustrations and teaching pictures from [CHATGPT-PROMPT-PACK.md](CHATGPT-PROMPT-PACK.md); results come back through `inbox/` and `intake.py` |
| `code-vector` | a code session | Produced by code, not a model: deterministic crops/encodes of an approved anchor (can start as soon as the anchor is accepted), or SVG/CSS/HTML that waits for the Claude Design brief (`docs/design-handoff/`) |
| `free-download` | an agent | Permissively licensed files (CC0, MIT, OFL, Apache only) recorded in [acquired/MANIFEST.json](acquired/MANIFEST.json) |
| `capture` | an agent or the owner | Real UI recordings, only after the workflow shown is qualified |
| `defer` | nobody yet | Not worth making until a named precondition holds |

## Review of the kit

**Over-scoped.** Six worlds of ten requests each, 18 parallax layers and 6 loops are a lot of decoration for a one-user,
loopback-only tool; the kit's own rule of one world at a time already implies that the other five wait. Eight promotion
pieces assume a public release process that does not exist. Six sound cues and eight guide expressions have no current
consumer: the Studio is silent and its guide is text. The ten foundation rows are code design, which the Claude Design
handoff now owns; the kit should not specify them a second time. P0 alone held 25 requests.

**What the Studio actually needs now** (from `app/static/` and `app/server.py` on `8a41edaa`):

- *No icon system.* Controls use Unicode glyphs as icons (51 `→`, 25 `↗`, 11 `★/☆`, 5 `✕` in `app/static/*.js|html`) and there is one inline SVG. `foundation-icons` is a real need, and candidate SVGs are now local (see Acquisitions).
- *No favicon or app icon.* Every page load asks for `/favicon.ico`, and the static handler answers 404 because it only serves `.html`, `.js` and `.css` files.
- *No served route for theme art.* For the same reason, the four `app/static/workshop-assets/*.svg` files are review masters only; the ambience posters ship as base64 SVG inside `workshop-immersive-core.css` (docs/workshop/ASSETS.md). Raster art (scenes, vignettes) needs a new allow-listed local route or must go through `/api/examples/<folder>/` (png/jpg/webp/gif/glb). SVG can ship today inside CSS/JS, which is one reason the helper states moved to `code-vector`.
- *No recipe thumbnails.* The 89 presets in `presets/catalog.json` have no thumbnail field; recipe cards are text. There are 24 named model families (e.g. Krea 2 Turbo, FLUX.2 Klein 4B/9B, WAI v17, Anima, Qwen-Image 2.1) and no family badge.
- *Existing slots already filled:* the Night Shift and Quiet Morning ambience posters (geometric SVG), the three `examples/workflow-lab/*.png` pictures on the Create page and the model showcase in `bundle-showcase.js` (civitai and atelier examples). None of these is replaced by this plan.

**Missing from the catalogue** (proposed additions, not yet catalogue rows):

| Proposed ID | Route | Wave | Reason |
| --- | --- | --- | --- |
| `app-favicon` | code-vector | W2 | A small SVG mark from the Claude Design brand work (`promo-readme`), shipped as a data-URI `<link rel="icon">` so no server change is needed |
| `recipe-thumbnails` | local-comfyui | W4 | Each recipe renders its own thumbnail with one fixed neutral subject and seed, so the picture is true of that recipe by construction; start with the shortlist leaders. A thumbnail made in ChatGPT would misrepresent a local recipe. Needs a `thumbnail` field and a served folder |
| `family-badges` | code-vector | W2 | Typographic badges for the 24 families inside `foundation-badges`; never vendor logos (trademarks) |
| onboarding inputs | (covered) | W2-W3 | The reference and sample rows below are the first-run inputs; serve them from an `examples/` folder with a manifest |
| empty library | (covered) | W2 | Reuse `state-blank` with library-specific HTML copy; no separate art |

**Depends on Claude Design decisions:** all ten `foundation-*` rows, `reference-mask`, the fourteen `state-*` rows, five
motion rows, `promo-readme` and the two additions above. The illustration language of the ChatGPT vignettes should follow
the design brief if it lands first: add its reference image to the upload for `workflow-create`. The typeface and the icon
family are design decisions; the downloaded fonts and icons are candidates for that decision, not the decision.

## Route table

Every catalogue ID appears exactly once below (`test_brief.py` checks it). Waves: **W0** done in this change, **W1** first
wave, **W2**-**W5** later waves, **later** when the named precondition holds.

### Environments (60)

| IDs | Route | Wave | Reason |
| --- | --- | --- | --- |
| `retro-anime-master` | local-comfyui | W1 | Needs a true 16:9 canvas, a seed and a prompt ID; start from `krea-environment` (Krea 2 Turbo) with `anima-environment` as the alternative, upscale with `anime-esrgan`. The GPU lab runs it |
| `retro-anime-quiet` | local-comfyui | W1 | Must register pixel-for-pixel with the anchor for crossfades; `flux-edit` (FLUX.2 Klein 4B) keeps the input size, while a ChatGPT edit may change the canvas |
| `retro-anime-hero`, `retro-anime-poster`, `retro-anime-card` | code-vector | W1 | Crops and encodes of the accepted anchor (`derive`); record the crop box and focal point |
| `retro-anime-wall` | chatgpt-image | W1 | A 3:2 quiet adaptation (2400x1600 target) is a new composition, not a registered layer; ChatGPT's landscape canvas is 3:2 and it follows "keep the centre empty" well. Runs after the anchor is accepted |
| `atelier-master`, `arcade-master`, `sakura-master`, `minimal-pro-master`, `sci-fi-noir-master` | local-comfyui | W5 | One new world at a time after the pilot is accepted. The GPU lab may make exploratory candidates earlier; exploration is not acceptance |
| `atelier-quiet`, `arcade-quiet`, `sakura-quiet`, `minimal-pro-quiet`, `sci-fi-noir-quiet` | local-comfyui | W5 | Same registration reason as the pilot's quiet still |
| `atelier-hero`, `atelier-poster`, `atelier-card`, `arcade-hero`, `arcade-poster`, `arcade-card`, `sakura-hero`, `sakura-poster`, `sakura-card`, `minimal-pro-hero`, `minimal-pro-poster`, `minimal-pro-card`, `sci-fi-noir-hero`, `sci-fi-noir-poster`, `sci-fi-noir-card` | code-vector | W5 | Crops of each world's accepted anchor |
| `atelier-wall`, `arcade-wall`, `sakura-wall`, `minimal-pro-wall`, `sci-fi-noir-wall` | chatgpt-image | W5 | Same 3:2 quiet-adaptation reason as the pilot wall |
| `retro-anime-loop` | local-comfyui | W4 | Wan 2.2 5B image-to-video from the accepted still (`examples/workflow-lab/wan-retro-anime.mp4` shows the route exists); only after the still pack works in the editor |
| `atelier-loop`, `arcade-loop`, `sakura-loop`, `minimal-pro-loop`, `sci-fi-noir-loop` | defer | later | One loop is the budget (AMBIENCE); revisit when a second world is accepted and the pilot loop is qualified |
| `retro-anime-layer-far`, `retro-anime-layer-mid`, `retro-anime-layer-near`, `atelier-layer-far`, `atelier-layer-mid`, `atelier-layer-near`, `arcade-layer-far`, `arcade-layer-mid`, `arcade-layer-near`, `sakura-layer-far`, `sakura-layer-mid`, `sakura-layer-near`, `minimal-pro-layer-far`, `minimal-pro-layer-mid`, `minimal-pro-layer-near`, `sci-fi-noir-layer-far`, `sci-fi-noir-layer-mid`, `sci-fi-noir-layer-near` | defer | later | No reliable layer-extraction route with hidden-region repair exists here (Qwen-Image 2.1 RGBA leaves alpha dust, #878), and parallax waits for the still pack and `motion-parallax` |

### Workflow illustrations (16)

| IDs | Route | Wave | Reason |
| --- | --- | --- | --- |
| `workflow-create` | chatgpt-image | W1 | The style anchor for all sixteen: one frame/folio motif, line weight and accent set, then every other vignette uploads it |
| `workflow-combine`, `workflow-pose`, `workflow-recover` | chatgpt-image | W2 | The other P0 vignettes, made with the approved `workflow-create` uploaded |
| `workflow-edit`, `workflow-sheet`, `workflow-repair`, `workflow-upscale`, `workflow-animate`, `workflow-sequence`, `workflow-compare`, `workflow-review`, `workflow-export`, `workflow-workflow`, `workflow-model`, `workflow-voice-3d` | chatgpt-image | W3 | Same method; `workflow-sheet` also uploads the approved `reference-identity` so the explorer stays one character |

### Empty, error and recovery states (14)

| IDs | Route | Wave | Reason |
| --- | --- | --- | --- |
| `state-blank`, `state-source-required`, `state-backend-missing`, `state-uncertain`, `state-conflict` | code-vector | W2 | Quiet geometric forms that need true alpha, theme-replaceable accents and <=60 KiB; SVG does all three and ships today inside CSS/JS, while raster would need a new served route. Waits for the Claude Design motif language |
| `state-no-match`, `state-loading`, `state-internet-absent`, `state-api-unavailable`, `state-model-missing`, `state-adapter-missing`, `state-media-failed`, `state-complete`, `state-failure` | code-vector | W3 | Same family, same reason |

### Reference examples (8)

| IDs | Route | Wave | Reason |
| --- | --- | --- | --- |
| `reference-identity` | chatgpt-image | W1 | The adult explorer canon every character example reuses; approve it before any derivative |
| `reference-outfit` | chatgpt-image | W2 | The explorer's own coat on a dress form: upload the approved identity so the costume matches the canon |
| `reference-pose`, `reference-style`, `reference-composition`, `reference-lighting`, `reference-background` | chatgpt-image | W2 | Standalone teaching pictures (the pose is a jointed mannequin, so its geometry stays independent of any identity); square or 2:3 canvases match the profile |
| `reference-mask` | code-vector | W2 | Editable vector overlay by definition |

### UI foundations (10)

| IDs | Route | Wave | Reason |
| --- | --- | --- | --- |
| `foundation-icons`, `foundation-tokens`, `foundation-buttons`, `foundation-fields`, `foundation-cards`, `foundation-tabs`, `foundation-badges`, `foundation-dialogs`, `foundation-patterns`, `foundation-skeletons` | code-vector | W2 | Code design owned by the Claude Design handoff. Inputs ready now: 62 Tabler outline icons (MIT), Inter and JetBrains Mono (OFL), paper and fabric grain (CC0) in `acquired/` |

### Optional guide (8)

| IDs | Route | Wave | Reason |
| --- | --- | --- | --- |
| `guide-neutral`, `guide-welcome`, `guide-point`, `guide-think`, `guide-question`, `guide-review`, `guide-rest`, `guide-celebrate` | defer | later | Optional by design and the guide is text today; revisit only if the owner asks for a companion |

### Real tutorials (10)

| IDs | Route | Wave | Reason |
| --- | --- | --- | --- |
| `tutorial-first-run`, `tutorial-reference`, `tutorial-pose`, `tutorial-recipe-change`, `tutorial-adapters`, `tutorial-compare`, `tutorial-continue`, `tutorial-recover`, `tutorial-workflow`, `tutorial-export` | capture | later | Each waits for its workflow to be qualified (#539 for Create); record at an exact commit with the W2-W3 reference pictures as public inputs |

### Promotion and showcase (8)

| IDs | Route | Wave | Reason |
| --- | --- | --- | --- |
| `promo-readme` | code-vector | W2 | The small brand mark is also the favicon source; from the Claude Design brief |
| `promo-hero`, `promo-offline`, `promo-workflow`, `promo-skins`, `promo-social`, `promo-release`, `promo-showcase` | defer | later | No public release process or audience yet; `promo-skins` also needs at least two accepted worlds |

### Optional audio (6)

| IDs | Route | Wave | Reason |
| --- | --- | --- | --- |
| `audio-confirm`, `audio-complete`, `audio-attention`, `audio-navigate`, `audio-room`, `audio-rain` | defer | later | Silence is the default and nothing plays sound; if wanted later, CC0 sources exist |

### Motion specifications (6)

| IDs | Route | Wave | Reason |
| --- | --- | --- | --- |
| `motion-disclose`, `motion-crossfade`, `motion-focus`, `motion-load`, `motion-pause` | code-vector | W3 | CSS/WAAPI tokens after the design brief; the crossfade needs the W1 quiet still |
| `motion-parallax` | defer | later | Needs the deferred layers |

### Controlled sample sets (8)

| IDs | Route | Wave | Reason |
| --- | --- | --- | --- |
| `sample-material-board` | free-download | W0 | Done: walnut veneer and cotton fabric (Poly Haven, CC0), paper and brushed metal (ambientCG, CC0) in `acquired/textures/` |
| `sample-character-canon`, `sample-pose-pair`, `sample-outfit-study`, `sample-lighting-pair`, `sample-composition-pair`, `sample-sequence-strip` | chatgpt-image | W3 | Controlled input sets built by uploading the approved references; they are source packs, so ChatGPT's consistency with an upload is the useful property |
| `sample-repair-pair` | defer | later | An honest repair pair needs a real repair receipt; waits for the repair programme (#243) |

## Route counts

| Family | local-comfyui | chatgpt-image | code-vector | free-download | capture | defer | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Environments | 13 | 6 | 18 | 0 | 0 | 23 | 60 |
| Workflow illustrations | 0 | 16 | 0 | 0 | 0 | 0 | 16 |
| States | 0 | 0 | 14 | 0 | 0 | 0 | 14 |
| References | 0 | 7 | 1 | 0 | 0 | 0 | 8 |
| Foundations | 0 | 0 | 10 | 0 | 0 | 0 | 10 |
| Guide | 0 | 0 | 0 | 0 | 0 | 8 | 8 |
| Tutorials | 0 | 0 | 0 | 0 | 10 | 0 | 10 |
| Promotion | 0 | 0 | 1 | 0 | 0 | 7 | 8 |
| Audio | 0 | 0 | 0 | 0 | 0 | 6 | 6 |
| Motion | 0 | 0 | 5 | 0 | 0 | 1 | 6 |
| Samples | 0 | 6 | 0 | 1 | 0 | 1 | 8 |
| **Total** | **13** | **35** | **49** | **1** | **10** | **46** | **154** |

## Waves

**W0 (this change):** tooling and free acquisitions. `intake.py` (receipts for owner-made candidates; verify/fetch for
downloads), the prompt pack, and 71 CC0/MIT/OFL files (3.1 MB, local-only): 62 Tabler icons plus licence, Inter and
JetBrains Mono plus licences, four material textures (`sample-material-board`).

**W1, first wave (Night Shift anchor plus two style anchors), 8 IDs:**

1. GPU lab: `retro-anime-master` candidates (at most four, per SESSION-HANDOFF).
2. Owner, in parallel: `workflow-create` and `reference-identity` in ChatGPT (they do not depend on the scene).
3. Owner: accept one master candidate, or reject all. Nothing below starts before that.
4. GPU lab: `retro-anime-quiet` from the accepted master.
5. Code session: `retro-anime-hero`, `retro-anime-poster` and `retro-anime-card` crops.
6. Owner: `retro-anime-wall` in ChatGPT with the accepted master uploaded.

**W2 (helpers and foundations):** `workflow-combine`, `workflow-pose`, `workflow-recover`; `reference-outfit`,
`reference-pose`, `reference-style`, `reference-composition`, `reference-lighting`, `reference-background` (all
ChatGPT); then, after the Claude Design brief: the ten foundations, `reference-mask`, five P0 states, `promo-readme`,
`app-favicon` and `family-badges`.

**W3:** the other twelve vignettes and six sample sets (ChatGPT), nine further states and five motion tokens (code).

**W4:** `retro-anime-loop` and `recipe-thumbnails` (GPU lab), and tutorial captures as each workflow qualifies.

**W5:** the next world, one at a time, only after the pilot is accepted in the running editor.

## Queue for the GPU lab

In order: `retro-anime-master` (now); `retro-anime-quiet` (after the owner accepts a master); exploratory
`atelier-master`, `arcade-master`, `sakura-master`, `minimal-pro-master`, `sci-fi-noir-master` (spare capacity only,
lowest priority); `retro-anime-loop` and `recipe-thumbnails` (W4). The lab reads `brief.py show <id>` itself and keeps its
own prompt IDs and receipts. Its outputs stay outside Git until the owner selects them.

## Bringing results in

ChatGPT results land in `docs/adaptive-studio/assets/inbox/` (gitignored) and `python docs/adaptive-studio/assets/intake.py
receipts` writes one tracked receipt per file under `receipts/` (see the prompt pack). Downloads are listed in
`acquired/MANIFEST.json`; `intake.py verify` checks them and `intake.py fetch` restores them on another clone. Receipt
status stays `candidate-produced` until the owner records art review; source review, rendition checks and runtime
qualification remain separate stages (DELIVERY-SPEC).
