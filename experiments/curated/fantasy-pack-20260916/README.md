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

## Next slices this points at

1. Identity across prompts needs a reference, not a seed: run steps 2 and 3 through a reference-carrying route (the character-consistency
   study's canon, or a Combine/restyle continuation from step 1) and compare against these three.
2. A targeted hand correction: the detailer's hand pass at 0.45 did not change the lantern grip; a masked repair on the hand region
   (the repair programme, #243-#257) or a *Change one thing* Klein edit on step 1 is the next candidate, at the same seed, with the original kept.
3. The owner's review of the four assets in *Runs & review* decides which, if any, becomes the pack's reference (HUMAN_TODO q-30).
