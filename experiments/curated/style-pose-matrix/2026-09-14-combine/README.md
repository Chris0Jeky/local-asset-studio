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
"leaning forwards": the words decide how far the figure bends.

## Through the page

`combine-klein` proving run: see the catalog `execution_note` and `CURRENT_STATE.md` (job `fb0eb95d-ba3f-4025-a77e-9c62165d250f`).
Not verified here: art acceptance (HUMAN_TODO q-27), licence clearance of the imported pictures, Klein 9B / AniEdit 9B (still downloading).
