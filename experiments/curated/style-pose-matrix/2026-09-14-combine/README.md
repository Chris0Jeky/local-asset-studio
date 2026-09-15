# Combine two pictures with FLUX.2 Klein 4B — 14 September 2026 (late night)

Research renders straight against ComfyUI (`Research/next-*` outputs, prompt IDs below), all on the installed
`flux-2-klein-4b-fp8.safetensors` + `qwen_3_4b` + `flux2-vae`, 6 Euler steps on the Flux2 schedule at CFG 1.0, seed
2026091407, 1024×1536 canvas, every reference scaled to 1.0 megapixel and chained as `ReferenceLatent` nodes in the
order image 1 → image 2 (→ image 3). Exact graphs: `klein-4b-graphs/<name>.graph.json`. Sheet:
`examples/style-pose/combine-klein-research.jpg` (four rows, labelled).

Pictures: image 1 = the owner's throne witch (`e0e988933f3c…_Nova_00004_.png.png`, 832×1216); pose picture A = the
owner's imported Santa-outfit fan picture (`4e25744e…_yande.re_1249734…`, 1053×1500); picture B = the imported
crop-top fan picture with "SHARK" lettering (`147a3362…_yande.re_1252703…`, 1063×1500).

## What the owner hit

The owner took a Klein restyle output, opened *Continue with this → Restyle* again and typed "have the pose of the
second image, the face and expression of the third image" into the keep sentence (jobs `3ad01f31…` 20:40 and
`35b548fd…` 20:44, same seed 2026091401). That recipe carries one picture, its wording says to keep everything, and the
seed did not change, so the three renders were the input again (mean absolute pixel difference 2.3 between the two runs,
10 against the input). The imported pictures sat in the library with no route that could use them as a second picture.

## Renders

| Name | Refs | Wording | Prompt ID | s | Result |
| --- | --- | --- | --- | --- | --- |
| m-edit-hat | witch | "Replace the witch's hat with a red Santa hat … Keep everything else exactly as it is" | 4ec15ceb | 34.1 | Hat replaced, pose/face/robe/throne kept; whole picture warmed towards red |
| m-pose-2ref | witch + A | concrete: "Redraw the witch from image 1 in the pose of the girl in image 2: leaning forward…, hand on hip…" + keep the witch's hat/robe/style | be5ed943 | 28.0 | **Pose moved**, witch kept (hat, robe, face); white background from A |
| m-pose-2ref-half | witch + A | same, image 2 at 0.5 MP | 156bcd22 | 14.0 | Same result |
| m-pose-aniedit | witch + A | same + AniEdit-Klein4B LoRA 1.0 | 4f31f04e | 22.0 | Same pose, slightly cleaner anime finish |
| m-expr-3ref | witch + A + B | + "facial expression of the girl in image 3" | 94839ccb | 34.2 | Pose and expression moved, **B's pink shorts and lettering leaked** |
| m-style-2ref | witch + B | "Redraw image 1 in the art style of image 2 … keep everything" | 98030e70 | 62.1 | Flat cel look and white background transferred; **hair purple, throne orange** |
| m-style-aniedit | witch + B | same + AniEdit LoRA | 2109da26 | 20.0 | Same, purple hair |
| t-combine-pose | witch + A | abstract "the character from image 1 … in the pose of the person in image 2" + *Image 1 shows: …* (the source's tag description) | 816c461b | 34.7 | **Pose undone**: the description says "one knee raised, leaning back" and the model obeyed it |
| t-look-desc | witch + B | look wording + the source description | 722277e2 | 64.2 | Colours held, **look barely changed** |
| t-look-colours | witch + B | look wording + "Image 1's colours: black hair, a black hat, a black and red robe…" | 1a7bddbe | 28.1 | Colours held, moderate look shift (heavier lines, darker) — the shipped compromise |
| t-combine-nodesc | witch + A | abstract wording, no description, no pose words | 7fdd9dc7 | 86.1 | **Did not move** (still on the throne) |
| t-combine-words-santa | witch + A | abstract wording + pose words | 21f4c31a | 44.4 | **Base swapped**: A's person kept, a witch hat added |
| t-combine-words-shark | witch + B | abstract wording + pose words | 3cf441f7 | 44.0 | **Base swapped** the same way |
| t-c3-santa | witch + A | **shipped wording**: named subject ("the witch in the black and red robe with gold trim and the wide-brimmed witch hat") + pose words | 673d15a5 | 46.1 | **Pose moved, witch kept** |
| t-c3-shark | witch + B | shipped wording, B's pose | 521778bb | 44.0 | Pose moved, witch kept; **"SHARK" lettering leaked onto the robe** |

Times are ComfyUI wall time including queue and any model reload (the 60–86 s rows followed a LoRA swap or the Studio
loading another model); a warm run is 14–46 s.

## What decided the shipped recipes

- **Name the subject; abstract wording fails.** "The character from image 1" either left the witch where she was or
  kept the *second* picture's person and added a hat (three renders). "The witch in the black and red robe with gold
  trim and the wide-brimmed witch hat" moved her every time (four renders across two pose pictures). The shipped
  wording therefore carries two bracketed fills the user must replace: who is in image 1, and the pose in a few words.
- **Do not append the source description to a Combine.** It names the source's pose and the model obeyed it.
- **One pose picture.** A third picture leaked its costume; the board has two slots so a third can be tried, and the
  hint says what happens.
- **The look-from-a-picture route is a compromise.** Without any colour anchor the look transfers strongly and the
  palette drifts; with the full description the look is lost; a short colour sentence (a bracketed fill) is the middle
  ground and is what ships.
- **The edit recipe works and should lead the Edit route** (it did not: the 11-minute Qwen recipe greeted the user).

## The owner's first run and the wording fix

Job `aebf406f…` (22:54, through the page): image 1 = picture B (the "SHARK" crop-top), pose picture = a newly imported
bent-over maid fan picture (`6895e9e0…_yande.re_1250070…`), fills "Ellen Joe in pink shorts and top with attractive silhouette"
and "leaning forwards, seen from the back, one hand on the hip moving the shorts slightly", plus "not include the tail",
seeds 2026091411–14, 148.5 s for four. Sheet `examples/style-pose/combine-klein-owner-run.jpg`. Every seed wore a cap the
source does not have (the shipped keep sentence said "her hat") and seed 2026091414 drew two figures.

Fix rendered against ComfyUI with the catalog graph, same pictures, seeds and fills, keep sentence "Keep the face, the
hair, the outfit and its colours, and image 1's rendering style. One figure only, nobody else in the picture." and
"Leave out the tail." appended:

| Seed | Prompt ID | s | Result |
| --- | --- | --- | --- |
| 2026091411 | `a20e6df1-fa86-46cf-9113-bf0b836285d2` (`Research/combine-fix_00001_.png`) | 54.8 (model load) | single figure, no cap, tail gone, from behind, hands on hips |
| 2026091412 | `39e6ce34-c09d-4b26-8595-0ac148233985` (`Research/combine-fix_00002_.png`) | 21.0 | same |
| 2026091413 | `f73b9c0b-56fc-46f9-bbeb-91e5d8e08e7b` (`Research/combine-fix_00003_.png`) | 21.0 | same; the source's "?" speech bubble kept |
| 2026091414 | `a27ae00d-cf23-40b8-8e9a-ce328fa26a76` (`Research/combine-fix_00004_.png`) | 21.1 | same; speech bubble kept |

Sheet `examples/style-pose/combine-klein-owner-fix.jpg`. The lean stayed mild in both runs because the fill said
"leaning forwards". Stronger words, same pictures and seeds (`bent forward at the waist, seen from behind, both hands on
the hips, looking back over her shoulder`; prompts `9c2635a7-a13b-48c5-83c4-114ee7333eeb`, `4241c6f4-c9d5-43d0-a847-5a45e1acb2d1`,
`Research/combine-bend_0000[12]_.png`, sheet `examples/style-pose/combine-klein-owner-bend.jpg`): the look-back and the
hands were honoured, the deep waist bend of the pose picture still was not. The words decide what moves; an extreme
bend is beyond what 6 steps of the 4B model reproduced here.

## Strategy change, 15 September 2026 (01:00-01:30): pose first on FLUX.2 Klein 9B

The owner called the 4B results "incredibly bad" and asked for a baseline that proves the workflow. Same two pictures (image A = the
"SHARK" crop-top character, image B = the bent-over maid picture), research renders straight against ComfyUI, seeds 2026091411+,
exact wordings, graph edits and seeds in `research-scripts/matrix.py` (Klein variants), `structural.py` (OpenPose + IP-Adapter),
`qwen_pose.py`, `prove_fix.py` and `prove_bend.py` next to this file (they run straight against ComfyUI on 8188 from the repo's
graphs; the input file names are the owner's uploads). Sheets:
`examples/style-pose/combine-klein4b-matrix.jpg`, `combine-klein9b-matrix.jpg`, `combine-klein9b-pose-first.jpg`, `combine-qwen-2ref.jpg`,
`combine-openpose-ipadapter.jpg`.

| Variant | Seed | Prompt ID | s | Output | Result |
| --- | --- | --- | --- | --- | --- |
| 4b-swap | 2026091411 | `103dd463-3db5-4a1b-a96b-cd660f346ae7` | 48.1 | `Research/matrix-4b-swap_00001_.png` | character's own pose came back (image 2 dominated) |
| 4b-swap | 2026091412 | `46bae6ce-b2ce-4b33-b824-d0ceb6a6a8d7` | 48.1 | `Research/matrix-4b-swap_00002_.png` | character's own pose came back (image 2 dominated) |
| 4b-8steps | 2026091411 | `1257fa75-e506-4e01-a3e7-95c1f1d49f7a` | 45.1 | `Research/matrix-4b-8steps_00001_.png` | mild lean from behind, as at 6 steps |
| 4b-8steps | 2026091412 | `9a6b0876-2bdd-4fac-9bdc-81bb4cb1d427` | 45.1 | `Research/matrix-4b-8steps_00002_.png` | mild lean from behind, as at 6 steps |
| 4b-aniedit | 2026091411 | `c6b91708-5715-4269-92dc-ad601ecbaedb` | 42.2 | `Research/matrix-4b-aniedit_00001_.png` | mild lean, cleaner finish |
| 4b-aniedit | 2026091412 | `d9c4eaa2-a937-45a1-a57b-5fee848bf634` | 39.4 | `Research/matrix-4b-aniedit_00002_.png` | mild lean, cleaner finish |
| 4b-swap-aniedit | 2026091411 | `5604b352-021e-4ba1-8cf1-188c0c22df5d` | 48.6 | `Research/matrix-4b-swap-aniedit_00001_.png` | character's own pose came back |
| 4b-swap-aniedit | 2026091412 | `1c49e50d-fdf2-4201-8db8-4d6ee3db246d` | 42.1 | `Research/matrix-4b-swap-aniedit_00002_.png` | character's own pose came back |
| 9b-normal | 2026091411 | `92ccd805-e735-4bd9-8974-4ece1c9bb754` | 102.5 | `Research/matrix-9b-normal_00001_.png` | look-back and hands on hips, no deep bend; lettering moved to the back |
| 9b-normal | 2026091412 | `92d70035-909f-4dfc-a407-c63e0335a059` | 123.2 | `Research/matrix-9b-normal_00002_.png` | look-back and hands on hips, no deep bend; lettering moved to the back |
| 9b-swap | 2026091411 | `7d1f9352-5728-4d3f-b17b-b3f124a083c5` | 109.1 | `Research/matrix-9b-swap_00001_.png` | seed 1 standing in heels; seed 2 **deep bend kept**, black shorts and heels leaked from image 1 |
| 9b-swap | 2026091412 | `01521153-3cea-43e5-90f7-6d6efee18cfb` | 110.1 | `Research/matrix-9b-swap_00002_.png` | seed 1 standing in heels; seed 2 **deep bend kept**, black shorts and heels leaked from image 1 |
| 9b-swap-anime | 2026091411 | `be351666-db63-46c8-aa61-3d38236f2463` | 157.1 | `Research/matrix-9b-swap-anime_00001_.png` | character's own pose came back (LoRA weakened the swap) |
| 9b-swap-anime | 2026091412 | `bea5137b-f1c2-4e42-a293-d41095b4e748` | 145.4 | `Research/matrix-9b-swap-anime_00002_.png` | character's own pose came back (LoRA weakened the swap) |
| 9b-swap-colour | 2026091411 | `9d15369a-81eb-4fdd-8ed4-0d3865453f43` | 923.6 | `Research/matrix-9b-swap-colour_00001_.png` | **deep bend, face, hair, SHARK top and pink shorts kept; tail gone** (4/4); a shoe or stocking from image 1 ghosts in on 3 of 4 |
| 9b-swap-colour | 2026091412 | `8858a542-8204-49c9-9543-d6a562817c2d` | 210.3 | `Research/matrix-9b-swap-colour_00002_.png` | **deep bend, face, hair, SHARK top and pink shorts kept; tail gone** (4/4); a shoe or stocking from image 1 ghosts in on 3 of 4 |
| 9b-swap-colour | 2026091413 | `a03e893a-57c1-4d92-be72-83fd8469acff` | 183.4 | `Research/matrix-9b-swap-colour_00003_.png` | **deep bend, face, hair, SHARK top and pink shorts kept; tail gone** (4/4); a shoe or stocking from image 1 ghosts in on 3 of 4 |
| 9b-swap-colour | 2026091414 | `02475ec4-c076-4b83-bcf9-7deab721a664` | 132.7 | `Research/matrix-9b-swap-colour_00004_.png` | **deep bend, face, hair, SHARK top and pink shorts kept; tail gone** (4/4); a shoe or stocking from image 1 ghosts in on 3 of 4 |
| qwen-2ref (Q4_K_M, Lightning 4 steps, 832x1248) | 2026091411 | `659e4504-c868-4413-9a5e-d3c6e002cbf1` | 871.2 | `Research/qwen-pose_00001_.png` | bent forward, look-back, hands on hips, identity kept; not the deep bend; 14.5 min |
| structural cn-plus07 (OpenPose ControlNet + IP-Adapter Plus on WAI v17) | 2026091411 | `ba6d060f-49df-4a46-9157-aee0b5828da6` | 1002.6 | `Research/structural-cn-plus07_00001_.png` | pose followed by the skeleton, identity and finish are WAI's, the tail came back (adapter copied it); 0.5 weight lost the face |
| structural cn-plus05 (OpenPose ControlNet + IP-Adapter Plus on WAI v17) | 2026091411 | `1af983bf-6918-431f-a6b9-06892a9f9ac4` | 199.0 | `Research/structural-cn-plus05_00001_.png` | pose followed by the skeleton, identity and finish are WAI's, the tail came back (adapter copied it); 0.5 weight lost the face |
| structural cn-plus07-face (OpenPose ControlNet + IP-Adapter Plus on WAI v17) | 2026091411 | `60c329d9-0420-42e0-926e-1a7bcdc47f4b` | 128.2 | `Research/error: IPAdapter model not present in the pipeline. Please load the` | error: IPAdapter node needs the unified loader; not retried |

What decided it: the Klein models keep **image 1's structure**. Asking for the pose in words while the character is image 1 gives a mild
pose at best (4B and 9B alike); putting the **pose picture first** and swapping the character in keeps the pose, and on 9B the swap holds
once the wording names the character's clothes and colours (without them image 1's black shorts and heels leaked). 4B cannot do the
swap (image 2's pose wins). Qwen Image Edit 2511 follows the pose better than Klein-normal but not the deep bend, at 14.5 minutes. The
structural route (OpenPose skeleton + IP-Adapter) follows the pose exactly but the identity and finish are the SDXL checkpoint's and the
adapter copied the tail; it is the fallback when a pose is too extreme even for the 9B swap. What GPT-class image models do
"effortlessly" is this composition inside one large multimodal model; locally it is structure (the pose picture as image 1, or a skeleton)
plus explicit words for everything that must not leak.

Shipped as `combine-klein-9b` (**Put this character into another picture's pose (FLUX.2 Klein 9B, follows the pose)**): the pose picture on
Picture 1 (image 1), your character on Picture to keep (image 2), three bracketed fills (who, the pose, the clothes and colours). The 9B
model is non-commercial (HUMAN_TODO q-27 (f)).

## Through the page

`combine-klein` proving run: see the catalog `execution_note` and `CURRENT_STATE.md` (job `fb0eb95d-ba3f-4025-a77e-9c62165d250f`).
Not verified here: art acceptance (HUMAN_TODO q-27), licence clearance of the imported pictures, Klein 9B / AniEdit 9B (still downloading).
