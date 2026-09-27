# How to iterate on pictures: a research brief for the Studio (27 September 2026)

You approved the Combine experiment-loop layout on 27 September 2026 and asked for research on how people who do this
well actually iterate, because you are not an image-generation expert. This brief answers that in five parts:

- how skilled people iterate (seven patterns, each with sources);
- what the Studio already covers;
- what is missing, ranked;
- a suggested default loop for your three kinds of work;
- five questions only you can answer.

**What this is:** web research from 27 September 2026 plus a reading of the Studio code on `main` (`8c37eb05`).
**What this is not:** no picture was generated or judged, and no recommendation here has been tried on this PC yet.
Several product help pages (Midjourney, Adobe Firefly) blocked direct reading. Facts from those pages come from search
snippets of the official page and are marked *(snippet)*. Refs #422.

## In one minute

1. Experts do **not** look for the perfect prompt first. They make several cheap pictures, **pick one**, then make
   small, controlled changes to that one. Every tool studied is built around that rhythm.
2. They change **one thing at a time** on a **fixed seed**, so they know what caused a difference.
3. They judge pictures **side by side, at the same size, against a short fixed checklist**, and write down why a
   picture failed.
4. For a series (a character pack, a set of backgrounds) they **lock a canonical reference early** and check every
   new picture against it.
5. The Studio already has most of the raw parts. What it lacks is mostly the **step after "keep"**:
   - "more like this one";
   - a checklist that fits the job;
   - a grid to see the results together;
   - a saved character or look to reuse;
   - a visible family tree of where a picture came from.

## 1. How skilled people iterate

### P1 · Explore wide and cheap, then narrow

Start with many quick, low-cost pictures: random seeds, small sizes, fast models or draft modes. Keep only the
direction that works. The slow, high-quality pass (upscale, second detail pass) comes after the choice, never before.
- Concept artists do the same by hand: 5-20 small, quick thumbnails judged on shape and value, then build up the
  best. [Thumb]
- The A1111 *hires fix* is a second pass you switch on once a picture is worth it. [A1111]
- A common practitioner cadence: random seeds first, then note the good seed and keep it fixed while you change words,
  then steps and guidance. [aituts]
- Midjourney's Draft mode is about ten times faster and meant for ideas, which you then vary or enhance
  *(snippet)*. [MJ-draft]
- Krea's realtime canvas has "no queue" and "no render button": you steer live, then upscale at the end. [Krea-rt]

### P2 · Pick one of a few, then vary it with a "how far" dial

The unit of decision is a small set, usually four. You pick the best one, and it becomes the parent of the next step.
Every tool then offers a single dial for how far a variation may stray from the parent:
- Midjourney: *Vary (Subtle)* keeps the composition, *Vary (Strong)* changes it a lot *(snippet)*. [MJ-vary]
- A1111: *variation seed* plus *variation strength*. [A1111]
- NovelAI: an Enhance *Magnitude* slider. [NAI-enh]
- Leonardo: *Creativity strength*. [Leo-rt]
- Adobe Firefly Boards: *More like this* *(snippet)*. [FF-vary]

### P3 · Change one thing at a time, on a fixed seed, and show it as a grid

To learn what a setting does, hold everything else (above all the seed) fixed. Vary one or two things and lay the
results out as a labelled grid.
- A1111 *X/Y/Z plot* makes rows and columns from one or two settings, including text swaps (*Prompt S/R*). [A1111]
- A1111 *Prompt matrix* renders every combination of prompt parts on the same seed. [A1111]
- ComfyUI Efficiency Nodes has an *XY Plot* node for the same job. [Eff-XY]
- The seed only means "the same picture" inside one model and graph. It does not make two different models
  comparable by itself (already noted in [Experimenting](Experimenting-and-Evaluating-Models.md)).

### P4 · Judge side by side, at the same size, against a short checklist

Photographers and editors choose from a **contact sheet**: every frame at the same size, then a pick. Tools make
that fast, and research favours choosing between two over scoring one.
- Lightroom flags a pick (P) or a reject (X), with Compare (two side by side) and Survey (several) views *(snippet)*.
  Photo Mechanic marks with one key and jumps to the next picture *(snippet)*. [LR] [PM]
- Culling in passes beats deciding everything at once: first reject the clearly bad, then pick, then rate, in short
  sprints (a vendor guide, *snippet*). [Cull]
- Choosing the better of two was the most consistent and time-efficient rating method in a 2012 comparison
  (*abstract snippet*). Pick-a-Pic collects preferences the same way. [Pairwise] [PickAPic]
- Checklists are short and concrete. A study of generated figures found hands the most error-prone region. [Anatomy]
  For game characters, readability from silhouette alone is the classic test (Valve, Team Fortress 2). [TF2]

### P5 · Keep the family tree, and recall parts of a recipe

Every mature tool records where a picture came from and lets you reuse *part* of its recipe.
- A1111 writes the settings into the PNG. [A1111]
- ComfyUI embeds the whole workflow in the file. [Comfy-meta]
- InvokeAI offers four recalls: *Remix* (everything except the seed), *Use Seed*, *Use Prompt* and *Use All*. It also
  has boards with an auto-add destination and a staging strip where you accept one result and discard the rest.
  [Invoke-gal] [Invoke-stage]
- NovelAI recalls "everything but the seed" or "seed only", and badges each thumbnail with the step that made it. Its
  history lasts only for the session, a warning against keeping lineage only in the browser. [NAI-hist]

### P6 · Lock a canonical reference early, for anything that must stay consistent

Artists fix a character on a **model sheet** (front, side, back, three-quarter, expressions) before drawing it
again, and keep a short **art bible** for the look of the whole game. [Sheet] [Bible] AI pipelines copy this:
- Style or character models are trained from about 10-20 curated pictures that share the look but vary angle, framing
  and background. Too many near-duplicates overfit (vendor guides). [Scen-style] [Scen-char]
- *The Chosen One* automates "generate many, keep the tightest cluster, train, repeat" for one consistent character. [Chosen]
- Reference routes (IP-Adapter FaceID, InstantID, PuLID) carry a face without training. The IP-Adapter FaceID
  README says its identity consistency is not perfect, and those models are for research use only. [FaceID]
- Edit models carry identity from a picture, but drift builds up over repeated edits. The FLUX.1 Kontext paper
  says so itself. [Kontext] Qwen-Image-Edit works best with 1-3 input pictures. [QwenEdit] With Klein multi-reference,
  practitioners see "outfit right, face changed". [Klein-ref]
- The practical rule: **go back to the canonical picture for each new one**, rather than editing an edit of an edit.
  Use the fewest references that work, because style references also leak content. [InstantStyle]

### P7 · Fix a region instead of rerolling the whole picture

When a picture is 90 % right, experts repair the wrong part and keep the rest.
- A1111 inpaint "only masked" works on the masked region alone and pastes it back. [A1111]
- Midjourney *Vary Region* regenerates a selected area *(snippet)*. [MJ-region]
- In InvokeAI the canvas bounding box decides whether the step is generate, img2img, inpaint or outpaint. [Invoke-bbox]

## 2. What the Studio already covers

| Pattern | Already in the Studio (code on `main`) | Missing piece |
| --- | --- | --- |
| P1 Explore then narrow | Create's **Variations** control runs 1-4 pictures per job at seed, seed+1, … (`batch_count`, `app/server.py`), and **New seed** picks a fresh seed. Create shows an expected time from this PC's history when it has one, and Combine's engine chips show time per picture. Wildcards `{a\|b}` and `__name__` vary wording (`app/prompting.py`). Upscale/Refine recipes exist under *Continue with this*. | No named "cheap draft → full quality" step. The fast recipe and the finishing recipe are separate journeys. |
| P2 Pick then vary | Result tiles on Combine offer Keep, Needs work, *Prepare same seed* and *Prepare new seed*. *Continue with this → Refine* runs img2img recipes with a `denoise` control (`krea-refine`, `anime-detail-fix`). | No one-press **Vary subtle / Vary strong** on a keeper. You must choose Refine, a recipe and a denoise number yourself. |
| P3 One change at a time | *Plan comparison* (`app/production.py`) varies one of seed, LoRA strength, guidance, steps or denoise. It also takes up to 8 labelled variants and a sourced settings grid or LoRA remix (`app/settings_planner.py`). Budget is shown before Start. The same pair on several engines with the same seeds is in open PRs #1184/#1193 (#1163). | Results show as candidate cards or seed tiles, **not as a rows × columns grid**. No wording A/B in the comparison dialog. |
| P4 Judge with a checklist | Library review keys K keeper · W needs work · X rejected · S skip, with seven reason tags (hands, face, style off, composition, anatomy, artifacts, crop; `app/static/workspace.js`), and group-by run/recipe/day with bulk marks. The Review desk has blind candidates, a synced crop, *Reveal* as a separate recorded step, a 1-5 preference and a contact-sheet export (`app/review_desk.py`). | The reason tags are the same for every job. Combine needs pose / face / outfit / style checks (already asked for in #422). Nothing counts which engine passes which check. |
| P5 Family tree | Each asset stores its source assets (`lineage`), and the asset panel lists direct sources and same-run siblings. Every job keeps its exact submitted graph and recipe. Recipes can be exported and imported. | Only one level is visible. There is no "family tree" from the first draft to the finished keeper, and no split recall ("this recipe, new seed" / "this seed, new words"). |
| P6 Canonical reference | Reference roles (identity, pose, style, costume, composition, …; `app/references.py`). Combine remembers the who / clothes answers per character, **in this browser only** (`localStorage`). An expert path imports a character-consistency study once you approve its canon (`character-import.js`, #65). | No everyday **character card** or **look card** you can pick in Create or Combine. No line-up view of a character's keepers next to the canon. |
| P7 Fix a region | Repair recipes (`anime-detail-fix`) and the *Repair* route, including a masked-repair route type (`app/continuation.py`). The Repair programme (#243) is tracked. | No brush/mask on screen (a deliberate non-goal until a real mask route exists). Not ranked here. |

## 3. Gaps, ranked by value for effort

Value means how much it shortens the pick-and-refine loop for your jobs. Effort is a rough size: S is a small frontend
slice, M needs a server change, L is several slices. Issues were opened for the top five.

| # | Gap | Proposed mechanic | Value | Effort | Issue |
| --- | --- | --- | --- | --- | --- |
| 1 | Nothing between "keep" and "try again" | **Vary subtle / Vary strong** on every result tile and asset: prepares the Refine recipe with this picture as source, the same words, a preset denoise (about 0.3 subtle, 0.55 strong; to be measured per recipe) and 4 seeds. Generate stays a separate press. | High | S | #1202 |
| 2 | One generic reason list | **Per-job checklist chips** on result tiles. Combine: Pose · Face · Outfit · Style · Clean. Character: Face · Outfit · Silhouette · Hands · Style. Background: Composition · Depth · Palette · Clean. Each is a yes/no stored with the review, and the engine chips show "pose 3/4 · face 1/4 on this PC". | High | M | #1203 |
| 3 | Plans and seeds are not seen together | **Grid view** for a plan or a pair: rows = engine or setting, columns = seed, same size, labels hidden until *Reveal* when blind; K/W/X work on the focused cell. | High | M | #1204 |
| 4 | Consistency lives in your head and one browser | **Character card and look card** saved in the Workspace: canonical picture(s), who/clothes words or look words, avoid-words, preferred recipe and seeds that worked. One press uses a card as Combine picture 2, as an identity/style reference, or to fill the words. A **line-up** shows the card's keepers at the same height. | Very high | L | #1205 |
| 5 | Lineage is one level deep | **Family tree strip** on each asset and result ("draft seed 42 → vary subtle → detail fix → upscale"), each step clickable. Plus split recall: *Same recipe, new seed* · *Same seed, edit words* · *Use as reference*. | Medium | S-M | #1206 |
| 6 | No wording A/B | "Try two wordings" in the comparison dialog, on the same seeds. The plan format already takes up to 8 labelled control sets, and those can include the words; the dialog does not offer it. | Medium | S | tracked here |
| 7 | Draft and finish are separate journeys | **Finish this** on a keeper: one prepared chain (detail fix, then 2× upscale) with its time shown. | Medium | M | tracked here |
| 8 | No keeper-to-LoRA path | Once a card has about 15-30 approved keepers, offer "train a character LoRA" as a planned, budgeted job. | High later | L | #411 |

Gaps 6-8 are listed so they are not lost. They are not opened as issues here: 6 and 7 can join the first two slices,
and 8 already has an issue.

## 4. A suggested default loop for your work

Each loop is a starting habit, not a rule. Times come from the recipe's chip on this PC; nothing here promises speed.

### A · Fantasy character pack (one character, many pictures)

1. **Design the character once.** In Create, pick a verified character recipe. Write who, clothes and colours in
   short phrases. Set **Variations** to 4 seeds. Keep one, or change one phrase and run 4 more. Stop after about 3
   rounds and take the best.
2. **Make it the canon.** Refine the keeper until face and outfit are right: *Continue → Refine*, then a detail fix.
   Save it as the character's canonical picture. Today that means a keeper plus a collection; with gap 4, a character
   card.
3. **Make the pack.** For each needed picture (portrait, action pose, expression), start from the canon through
   Combine or an identity reference. Never start from a random earlier picture: drift compounds.
4. **Judge against the canon, side by side.** Use the checklist (face, outfit, silhouette, hands, style). Keep, needs
   work, or reject, with a reason.
5. **Finish only keepers.** Detail fix, then upscale, then export.

### B · Combine: this character in that pose

1. Put the character (from the canon) and the pose picture side by side. Fill who / pose / clothes in a few words.
2. **Round 1, engines:** run the same pair on 2-3 engines with the same 2 seeds (the multi-engine plan, #1184/#1193).
   Judge pose first, then face: they fail independently.
3. **Round 2, seeds:** on the engine that got the pose, run 4 new seeds.
4. **Round 3, fix:** if the pose is right but the face drifted, try the *replace character* recipe or a Refine on the face rather
   than rerolling everything. If the pose is wrong on every engine, draw the pose (skeleton recipe) instead of adding
   words.
5. Stop after roughly 3 rounds or 12 pictures without a keeper. Note what failed; that is evidence for the recipe, not
   a waste.

### C · Game-asset backgrounds

1. **Look first.** Pick or make 1-3 pictures that define the look (palette, line, lighting). Keep them as the look's
   reference; with gap 4, a look card.
2. **Thumbnails.** Many small, fast pictures of the scene layout on a fast recipe, judged only on composition and
   depth (near / middle / far read clearly).
3. **Pick one and refine** at full size on the chosen environment recipe, with the look reference attached.
4. **Line up the set:** every background of the game side by side at the same size, to catch a palette or lighting
   that drifts.
5. **Finish:** upscale, and, if you need parallax, split the layers in Krita. The Studio does not split layers today.

## 5. Questions for you

1. **How much do you want to judge per picture?**
   - (a) Keep / Needs work / Reject only.
   - (b) Also 4-5 quick yes/no checks that fit the job (pose, face, outfit, style, clean).
   - (c) Also a 1-5 preference score.
   - If you don't answer: (b).
2. **What is a character's canon?**
   - (a) One chosen keeper picture.
   - (b) A front / side / back sheet you approve first.
   - (c) Start with (a), and train a character LoRA once about 20 keepers exist.
   - If you don't answer: (c).
3. **Should comparisons hide which engine or setting made each picture until you choose?**
   - (a) Always.
   - (b) Only in planned comparisons and multi-engine plans.
   - (c) Never.
   - If you don't answer: (b).
4. **How big should one round be?**
   - (a) Always 4 pictures.
   - (b) 4 on fast recipes (under a minute each), 2 on slow ones.
   - (c) 8 for exploring, 4 for refining.
   - If you don't answer: (b).
5. **What do your game backgrounds need to be?**
   - (a) One painted backdrop per scene.
   - (b) Parallax layers (sky, far, middle, near).
   - (c) Tileable pieces for a tile map.
   - (d) A mix.
   - This decides whether the background loop needs layer splitting or seamless tiling next.

## 6. Owner answers (27 September 2026, in chat)

1. **Judging:** add quick checks. Keep / Needs work / Reject stays, plus 4-5 one-tap yes/no checks that fit the job (pose, face, outfit, style, clean), counted per engine (#1203).
2. **Canon:** start with one chosen keeper portrait, and train a character LoRA once about 20 keepers exist (#1205, #411).
3. **Blind judging:** only in planned comparisons and multi-engine plans; normal runs show their labels (#1204).
4. **Round size:** 4 pictures on fast recipes (under a minute each), 2 on slow ones (#1202).
5. **Backgrounds:** "A mix, a very ambitious mix, with experimentation, this will allow me to push in the direction that I most desire". The background loop has to cover single backdrops, parallax layers and tileable pieces, each experimentally first.

These are workflow defaults, not art acceptance.

## Sources

Fetched or seen on 27 September 2026. *(snippet)* means only the official page's search snippet was readable.

| Label | Source |
| --- | --- |
| A1111 | AUTOMATIC1111 wiki, Features (X/Y/Z, prompt matrix, variations, hires fix, inpaint, PNG info): https://github.com/AUTOMATIC1111/stable-diffusion-webui/wiki/Features |
| aituts | Seed cadence: https://aituts.com/stable-diffusion-seed/ |
| Thumb | Thumbnail sketching: https://conceptartempire.com/intro-to-thumbnail-sketching/ |
| MJ-draft, MJ-vary, MJ-region | Midjourney docs *(snippet)*: https://docs.midjourney.com/hc/en-us/articles/35577175650957-Draft-Conversational-Modes · https://docs.midjourney.com/hc/en-us/articles/32692978437005-Variations · https://docs.midjourney.com/hc/en-us/articles/32794723105549-Vary-Region |
| Krea-rt | Krea realtime: https://www.krea.ai/docs/realtime |
| NAI-enh, NAI-hist | NovelAI docs: https://docs.novelai.net/en/image/enhance · https://docs.novelai.net/en/image/history |
| Leo-rt | Leonardo realtime canvas: https://intercom.help/leonardo-ai/en/articles/8658301-realtime-canvas |
| FF-vary | Firefly Boards variations *(snippet)*: https://helpx.adobe.com/firefly/web/create-mood-boards/firefly-boards/generate-image-variations.html |
| Eff-XY | Efficiency Nodes XY Plot: https://github.com/jags111/efficiency-nodes-comfyui |
| Comfy-meta | ComfyUI workflow metadata: https://docs.comfy.org/development/api-development/workflow-metadata |
| Invoke-gal, Invoke-stage, Invoke-bbox | InvokeAI: https://invoke.ai/features/gallery/ · https://invoke.ai/features/canvas/run-workflow/ · https://support.invoke.ai/support/solutions/articles/151000096702-inpainting-outpainting-and-bounding-box |
| LR, PM | Lightroom *(snippet)*: https://helpx.adobe.com/lightroom-classic/help/flag-label-rate-photos.html · Photo Mechanic *(snippet)*: https://home.camerabits.com/setting-up-photo-mechanic-quickstart-guide-to-preferences/ |
| Cull | Culling passes (vendor, *snippet*): https://imagen-ai.com/valuable-tips/decision-fatigue-culling-photos/ |
| Pairwise, PickAPic | Mantiuk et al. 2012 *(abstract snippet)*: https://www.cl.cam.ac.uk/~rkm38/pdfs/mantiuk12cfms.pdf · Pick-a-Pic *(snippet)*: https://arxiv.org/html/2305.01569 |
| Anatomy | Anatomy errors in generated figures: https://pmc.ncbi.nlm.nih.gov/articles/PMC11663238/ |
| TF2 | Valve, Illustrative Rendering in TF2: https://wiki.teamfortress.com/wiki/Illustrative_Rendering_in_Team_Fortress_2 |
| Sheet, Bible | Model sheets: https://www.clipstudio.net/how-to-draw/archives/164740 · Art bibles: https://www.gamedeveloper.com/design/who-needs-an-art-bible-game-art-direction-from-indie-to-aaa |
| Scen-style, Scen-char | Scenario help (vendor): https://help.scenario.com/en/articles/train-a-style-model/ · https://help.scenario.com/en/articles/train-a-consistent-character-model/ |
| Chosen | The Chosen One (SIGGRAPH 2024): https://arxiv.org/html/2311.10093v4 |
| FaceID | IP-Adapter FaceID: https://huggingface.co/h94/IP-Adapter-FaceID |
| Kontext, QwenEdit, Klein-ref | https://arxiv.org/abs/2506.15742 · https://huggingface.co/Qwen/Qwen-Image-Edit-2509 · https://myaiforce.com/improve-multi-reference-image-results-flux-2-klein/ (practitioner) |
| InstantStyle | Style references leak content: https://instantstyle.github.io/ |
| Tile, Parallax | Seamless tiling nodes *(snippet)*: https://github.com/spinagon/ComfyUI-seamless-tiling · Parallax layers *(snippet)*: https://blog.yarsalabs.com/parallax-effect-in-unity-2d/ |

No primary studio or GDC talk describing a concrete AI art pipeline was found; vendor productivity claims were left out.
