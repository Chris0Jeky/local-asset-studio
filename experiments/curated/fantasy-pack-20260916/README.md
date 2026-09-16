# Fantasy character pack, first four-step batch — 16 September 2026 (02:07-02:10)

The brief's first deliverable ([docs/FANTASY-CHARACTER-BRIEF.md](../../../docs/FANTASY-CHARACTER-BRIEF.md)) run once through the Studio's own
path (POST /api/jobs: prepare -> worker -> ComfyUI, the shape the page submits; `pack_lookb.py` next to this file, results in `pack_lookb.json`),
on the owner's chosen **look B**: `anima-v1-baseline` with slot 1 `nsfw_girls_anima.safetensors` at 1.0 (the other five slots at 0), seed
`2026091301`, 832x1216, 30 steps, CFG 4.5, euler/simple, the baseline's negative prompt; the character wording is the baseline's clothed
traveller with the brief's navy coat, brass details and teal accents named. Backend `primary` (ComfyUI 0.35.0 on 8188), receipts under the
configured receipts root (`experiments/runs/<job-id>/`: recipe, state with the exact submitted graph, workflow). The exact submitted recipes
(`/api/jobs/<id>/recipe`, graph included) are committed under `recipes/`. Sheet: `examples/fantasy-pack/first-batch.jpg`.

| Step | Job / prompt | s | Output | Inspected (agent's reading, not acceptance) |
| --- | --- | --- | --- | --- |
| 1 · three-quarter portrait, both hands on the lantern | `ca5c5082-7268-46cc-a99d-e88646b1b10e` / `f7c3e345-f15d-40a6-b9d4-64480217c08c` | 34.3 | `Studio/Anima-v1-Baseline_00004_.png` (Workspace asset `021731c057d955b4a2487395a37fadf6`) | navy double-breasted coat with brass buttons, teal scarf, long dark hair, earrings; calm, attentive face; both hands visible holding the lantern, the finger arrangement on the handle slightly odd (candidate defect for step 4); soft evening light on the platform, cinematic. The design reads. |
| 2 · full body, lantern at her side, satchel strap | `373d0b35-421c-4749-956f-377f19b98ce6` / `f42084d8-9883-46a5-a1f2-d3d9b2b6058c` | 18.2 | `Studio/Anima-v1-Baseline_00005_.png` (Workspace asset `025678cadf5750bf9a3bfa8ed62e6590`) | same coat, scarf and buttons, belted; lantern in the right hand, left hand on the satchel strap, brown lace-up boots, cuffed trousers; readable silhouette, coherent clothing, hands plausible; face and hair consistent with 1 in style, the face slightly different (a different framing of the same seed). |
| 3 · expression variation (warm surprised smile) | `053f6cf5-aa70-482f-aecb-3021235cd560` / `9dec5e14-60d2-4bd7-9174-0f380a1f75fc` | 18.2 | `Studio/Anima-v1-Baseline_00006_.png` (Workspace asset `60b1b58f87435dc48e5d32ca06c2ac92`) | the open-mouthed surprised smile with raised brows came through; coat, scarf and lantern kept; **the hair changed** (shorter, side-swept bangs instead of the centre-parted long hair of 1 and 2), so the design held but the face/hair identity drifted: the seed alone does not carry identity across prompts. |
| 4 · Anime Detail Fix (faces, then hands) on 1 | `009eddad-f90d-4435-bffb-8f5c98a3305d` / `8933d238-53e6-40f3-9397-b8c31d43564d` | 70.5 | `Studio/anime-detail-fix_00003_.png` (Workspace asset `97432e2fc7d25cc2a834267a66283c7f`) | the face pass (denoise 0.40) repainted the face: eyes turned grey-blue from brown, expression a touch softer; the hand pass (0.45) left the hands as they were, the odd finger arrangement included. So the pass changed what needed no change and left the candidate defect: not a useful correction as run; the original (job ca5c5082) is preserved as its own asset. |

Wording per step (the shared character sentence, then the step): see `STEPS` in `pack_lookb.py`; step 4 reused step 1's wording as the
detailer's positive prompt and staged step 1's output through POST /api/assets/reference, the way *Continue with this -> Repair* does.

## What this batch establishes and what it does not

- Established: the four artefacts the brief asks for exist as Studio jobs with retained prompt IDs, graphs and Workspace assets, at one
  seed, on the selected look, in 141 s of GPU time in all. The costume reads consistently across the three renders (coat, buttons, scarf,
  lantern, boots).
- Not established: character identity across prompts (the hair changed on the expression render; the face differs between 1 and 2);
  a useful correction (the detail pass changed the face's eye colour and left the hands); art acceptance of any image; licence
  clearance (Anima base v1.0 and the slot-1 adapter carry their own civitai terms, recorded in `models/library.json`).
- Timing note: step 1 (34.3 s) includes the Anima model load after the Klein 9B runs earlier in the session; steps 2 and 3 ran warm.

## Identity follow-up, the same night (02:55-03:00): a reference route instead of the seed

Two more jobs (`pack_identity.py`, results in `pack_identity.json`, recipes 5 and 6 under `recipes/`, sheet `examples/fantasy-pack/identity-followup.jpg`),
both fed from the batch's own outputs staged through POST /api/assets/reference the way *Continue with this* does:

| Step | Job / prompt | s | Output | Inspected (agent's reading, not acceptance) |
| --- | --- | --- | --- | --- |
| A · expression through *Change one thing* (`flux-edit`, FLUX.2 Klein 4B) on the portrait, fill "change her expression to a warm, surprised smile with raised eyebrows and the mouth slightly open" | `d0e8524e-173c-4a26-99bc-d5e4fdb80197` / `aac58ca7-f12b-4591-816b-2933f391fb82` | 64.5 | `Verified/FLUX-Edit_00010_.png` | **identity kept in full**: the same face, centre-parted hair, earrings, coat, scarf, lantern and hands; the expression became a broad toothy grin rather than the surprised half-open mouth asked for. This is the expression variation the seed could not give. |
| B · full body through the depth Combine (`combine-klein-9b-depth`, FLUX.2 Klein 9B): the portrait as the character (image 2), the batch's full-body render as the pose picture (image 1, read as a depth map) | `18a4f441-b504-44cf-9a1b-9baca4480fe0` / `a257dc56-5f1f-43f4-a6c2-b83b0a0fe05a` | 107.1 | `Combine/Klein-9B-depth_00005_.png` | the full-body pose, coat, scarf, belt, satchel, lantern and boots came through on a plain background, **but the face is lost**: closed-eye lines and no features, and the finish went flat vector-like instead of the portrait's painterly shading. At full-body scale the 9B depth route does not carry a face from a portrait-sized reference. |

What this settles for the pack: an edit route on a finished picture keeps identity (A), so expression and small-costume variations should be edits of the
reference portrait, not new seeds; a body-pose change from a portrait needs a route that keeps the face at that scale (Copy Pose with a
full-body character picture, or a face pass after the Combine), which is the next experiment, not this one.

## Full body that keeps the face: the replace-character LoRA (16 September 2026, 03:19-03:26)

The slice B could not give - the depth Combine carried the pose and the costume but lost the face - proved the same night, but **in
research, straight against ComfyUI** (`POST /prompt` on 8188), *not* through the Studio: `pack_replacechar.py` next to this file,
results in `pack_replacechar.json`, the three exact submitted graphs under `research-graphs/`. Sheet:
`examples/fantasy-pack/full-body-keeps-face.jpg`.

The pair is the pack's own: **image 1** is the batch's full-body render (step 2, `Studio/Anima-v1-Baseline_00005_.png`, staged in
ComfyUI's input folder as `9c880763...`) and **image 2** the batch's three-quarter portrait (step 1, `...Baseline_00004_.png`,
`aa93fb46...`). The graph is the shipped FLUX.2 Klein 9B two-reference Combine (`workflows/api/combine-klein-9b-api.json`) with one
node added: a `LoraLoaderModelOnly` on the pinned civitai adapter `replace_character_v1_klein.safetensors` at strength 1.0, model
only (node 40), feeding the CFGGuider's model input. 832x1216, 6 Euler steps on the Flux2 schedule at CFG 1.0, one image per seed,
backend `primary` (ComfyUI 0.35.0 on 8188). The same wording on all three seeds, the LoRA author's sentence with the costume named:

> Replace the woman in image 1 with the woman in image 2, while keeping the same pose, action, camera angle, composition, background
> and lighting as in image 1. The woman in image 2 has long centre-parted dark hair, brown eyes, a calm face and small gold earrings;
> keep her face, hair and expression exactly as in image 2. She wears image 1's clothes: a navy double-breasted travelling coat with
> brass buttons, a teal scarf, dark trousers, brown lace-up boots, holding a brass lantern, a leather satchel on a strap. Keep image
> 1's painterly rendering and its station platform. One figure only, nobody else in the picture.

| Seed | Prompt | s | Output | Inspected (agent's reading, not acceptance) |
| --- | --- | --- | --- | --- |
| 2026091301 | `6eaa00a9-083e-41e9-88c9-d2820b0b4487` | 116.1 | `Research/pack-replacechar_00001_.png` | the portrait's heavy centre-parted fringe low over the brows, its gold diamond earrings, its rounder face and calm half-lidded gaze - on image 1's body: the same standing pose, lantern in the right hand, left hand on the satchel strap, navy coat, belt, teal scarf, boots, platform, rails and evening light unchanged. |
| 2026091302 | `36312e34-4c09-477b-ab4b-bf33c544ff61` | 132.2 | `Research/pack-replacechar_00002_.png` | the same transfer; the eyes read a little more open and both earrings show. Pose, costume, framing and background again unchanged from image 1. |
| 2026091303 | `b6b1e704-b0aa-4e75-8330-21fdd909d35d` | 124.3 | `Research/pack-replacechar_00003_.png` | between the other two: the fringe covers one brow, the earrings are visible, the calm expression is kept; image 1's scene intact. |

**What held, 3 of 3 seeds:** the portrait's fringe, gold earrings, face shape and calm expression arrived in the full-body scene, and
image 1 kept everything else - pose, action, camera angle, composition, the navy double-breasted coat with brass buttons, the teal
scarf, the belt, the satchel, the brass lantern, the boots, the station platform and the evening light. One figure in each, nobody
added. 116-132 s per render.

**What this does NOT establish:** the recipe through the Studio - these are `POST /prompt` research renders, the prepare/worker path
is still owed and the catalog entry stays `verified: false` until it runs; any other character or pair (one pair, one look, one
costume - and because the portrait wears the same coat, this run is not a hard test of costume leaking from image 2); non-Anima or
photographic styles; that the face matches the portrait at portrait fidelity (at full-body scale the head is a small fraction of the
frame: the fringe, earrings, hair and expression read, the fine features are re-drawn); art acceptance by the owner (HUMAN_TODO
q-30); licence clearance - the 9B model is non-commercial and the adapter's civitai flags (Image/RentCivit/Rent, no Sell) are
recorded in `models/library.json`, not granted here.

The Studio recipe built from this run is **`combine-klein-9b-replace`** (`workflows/api/combine-klein-9b-replace-api.json` plus its
catalog entry): the same graph, with "Picture to put them in (image 1)" as the board slot, "Character to keep (image 2)" as the
picture you continue from, and three bracketed fills (image 1's pose and camera, who is in image 2, image 1's clothes and colours).

## Next slices this points at

1. Identity across prompts needs a reference, not a seed: done for the expression (A above, kept) and now for the full body - the
   replace-character LoRA carried the portrait's face into the batch's own full-body render on 3 of 3 seeds (the section above), and that
   run is the Studio recipe `combine-klein-9b-replace`. What is left on this slice: the Studio proving run for that recipe, and a face
   pass on one of the three renders if the owner wants the face at portrait fidelity.
2. A targeted hand correction: the detailer's hand pass at 0.45 did not change the lantern grip; a masked repair on the hand region
   (the repair programme, #243-#257) or a *Change one thing* Klein edit on step 1 is the next candidate, at the same seed, with the original kept.
3. The owner's review of the four assets in *Runs & review* decides which, if any, becomes the pack's reference (HUMAN_TODO q-30).
