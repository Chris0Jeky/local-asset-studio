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


## Pose round two, 15 September 2026 (02:00-03:10): the depth map carries the pose

The owner's verdict on the pose-first result: "so so" — a much bigger step, but not the complete pose change they meant; of all the
renders the first Qwen one (`qwen-pose_00001_.png`, above) most resembled the objective, and 14.5 minutes is too slow. Scripts next to this
file: `qwen_pose2.py` (Qwen Image Edit 2511 Q4_K_M + Lightning, references appended as `ReferenceLatent` at a chosen size), `klein_skeleton.py`
(FLUX.2 Klein 9B, the shipped 9B graph with an annotator or a blank canvas as image 1), `sheet_round2.py`, `prove_depth.py` (the Studio proving
run). Same two pictures, seeds 2026091411+. Sheet: `examples/style-pose/combine-pose-round2.jpg`.

**Why Qwen is slow here, measured.** The ComfyUI log for the first Qwen run shows the model fully loaded in 65 s and the four Lightning steps
taking 13 min. Halving both references (the stock `TextEncodeQwenImageEditPlus` node rescales every reference to ~1 MP for its latents, so
the script appends them itself) cut the run only from 14:29 to 12:52; the time is in the 20B model's weight path on this GPU (Q4_K GGUF
dequantised every step with 1-3 GB of VRAM headroom), not in the reference tokens. No Qwen render here took under 10 minutes.

**Both 2D skeleton detectors fail on this pose picture; the depth map does not.** OpenPose (body/hand/face, 1024 and 1536) and DWPose
(yolox_l + dw-ll_ucoco_384, downloaded tonight) both returned a scrambled fragment for the bent-over, foreshortened maid picture
(`qwen2-skeleton_00001_.png`, `probe-dwpose_00001_.png`, `probe-openpose1536_00001_.png`), so the "structural" route of round one was driven
by a wrong skeleton as well. Depth Anything V2 Large (`probe-depth_00001_.png`, downloaded tonight, cc-by-nc-4.0) gives the whole silhouette:
bend, crossed legs, heels, skirt, tail.

`s` is ComfyUI's own execution time for the prompt (`execution_start` to `execution_success` in `/history`, the same basis as the tables
above, including any model reload and the annotator); `round2_history.json` next to the scripts holds that number, the status, the
outputs and the exact submitted graph for every prompt below, read back from `/history`. The per-script JSONs (`qwen_pose2.json`,
`klein_skeleton.json`) record the script's own wait, which includes queueing behind other prompts, and two scripts running at once
overwrote each other's file, so they are partial; the history file is the record.

| Variant | Seed | Prompt ID | s | Output | Result |
| --- | --- | --- | --- | --- | --- |
| qwen ref05 (identity first, refs 0.5 MP) | 2026091411 | `8d71b5e4` | 772.7 | `Research/qwen2-ref05_00001_.png` | deeper bend than round one, face kept, lettering garbled; **the maid's tights and the tail leaked** |
| qwen skel05 (failed OpenPose skeleton as picture 2) | 2026091411 | `ace2a0bf-ec6f-480c-9264-f4d8b5e138f4` | 1121.7 (incl. 6.5 min reload) | `Research/qwen2-skel05_00001_.png` | clean identity, no leak, mild bend only (the skeleton carried nothing) |
| qwen depth05 (depth map as picture 2) | 2026091411 | `1233cf2b-f052-4459-9b3d-d0f73612315d` | 640 (10:40) | `Research/qwen2-depth05_00001_.png` | **the exact pose**, but every shape in the silhouette drawn: pink heels, a frilled skirt, the tail; face and lettering distorted |
| klein 9b-skel-first (failed skeleton as image 1) | 2026091411 | `4cce14a5-f46c-4453-bcd1-56b316cc1f70` | 99.4 | `Research/klein-9b-skel-first_00001_.png` | deep bend, bare feet, no tights, no tail, face and top kept; hands behind the back (the words did it: image 1 had no competing figure) |
| klein 9b-blank-first (black canvas as image 1) | 2026091411 | `7fc87b50-e96a-4c18-8a90-743abcbead57` | 90.0 | `Research/klein-9b-blank-first_00001_.png` | perfect identity, lettering and colours, hand on hip, look-back; **mild lean only** |
| klein 9b-blank-first | 2026091412 | `e6b5d737-8dcd-4930-982f-9b9cca5f5729` | 87.1 | `Research/klein-9b-blank-first_00002_.png` | same: standing, hands on hips; the words never bend her |
| **klein 9b-depth-first** (depth map as image 1) | 2026091411 | `185101f3-0f41-4db2-943d-4727a496787e` | 115.4 | `Research/klein-9b-depth-first_00001_.png` | **deep bend, crossed legs, bare feet, no tights, no tail, face and hair kept**, lettering partial, hands between the knees |
| **klein 9b-depth-first** | 2026091412 | `83c2046a-fda0-4864-a2d1-9a00e05a7825` | 113.9 | `Research/klein-9b-depth-first_00002_.png` | **deep bend, crossed legs, look-back, SHARK lettering intact, pink shorts, bare legs**; one foot shaped like a heel (the silhouette's heel) |
| klein 9b-depth-first | 2026091413 | `190422c8` | 440.0 (6.5 min of sampling straight after the Qwen run; seeds 11-12 sampled in ~1 min) | `Research/klein-9b-depth-first_00003_.png` | **moderate bend only**, bare feet, no leak, lettering lost, the character picture's "?" speech bubble came back |
| **klein 9b-depth-first** | 2026091414 | `5da5f797` | 460.4 (same slow state) | `Research/klein-9b-depth-first_00004_.png` | **deep bend, crossed legs, look-back, SHARK lettering intact, pink shorts, bare legs**; one foot heel-shaped |
| **Studio proving run, `combine-klein-9b-depth`** (`prove_depth.py`, POST /api/jobs) | 2026091441 | job `22ff6394-11ad-490a-bfea-6304e53f5d24`, prompt `9047dc60-a99e-4eb5-94f8-4615de1b90fe` | 446.6 (slow state; the Studio job's own elapsed time was 448.7 s) | `Combine/Klein-9B-depth_00001_.png` | **deep bend, crossed legs, look-back, lettering intact, pink shorts, bare feet**; one foot heel-shaped |

What decided it: **the structural image carries the pose, the words carry everything that must not leak.** A depth map of the pose picture as
image 1 gives Klein 9B the body position without the pose picture's clothes, and the character as image 2 with the clothes and colours named
gives the identity: 3 of 4 research seeds plus the proving run held the deep bend. Shipped as `combine-klein-9b-depth`, first on the Combine
route; `combine-klein-9b` (pose picture first, keeps its camera and background, shoes can ghost) is second; the 4B recipe third.

**A slow state to know about:** after the 10-minute Qwen run, every Klein 9B render sampled in 6-7 minutes instead of about one
(seeds 13, 14 and the proving run; `POST /free` with `unload_models` did not restore it; VRAM read 15.2 GB free between jobs). Round one saw
the same swing (the 9B swap-colour seed 1 at 923 s). Not diagnosed tonight; a ComfyUI restart is the next thing to try.

## Pose round three, 15 September 2026 (03:40-05:30): what stands in for the pose picture, and the words that move hands and camera

Same two pictures and seeds 2026091411-13, research renders straight against ComfyUI, scripts next to this file: `pose_sources.py` (a
different image 1 per variant: the depth map painted, a PIL-drawn skeleton, a PIL-drawn capsule mannequin; hand and camera words; 8 steps;
the Q8 GGUF), `lora_pose.py` (four civitai LoRAs for Klein 9B, downloaded and SHA-256-verified tonight, pinned in `models/library.json`),
`restart_probe.py` (the slow state), `twopass.py` (depth Combine then Change one thing as one Studio journey), `sheet_round3.py`. Prepared
images 1 (`pose3-*.png`) and exact graphs (`pose3-*.graph.json`) are next to the scripts. Sheet: `examples/style-pose/combine-pose-round3.jpg`.

**The slow state is a ComfyUI-process condition that only a restart clears (`restart_probe.json`).** The night's per-prompt log shows a healthy
Klein 9B render at 6.2-6.6 s/step (87-120 s) and the slow state at 53-63 s/step (377-460 s), with identical model-load lines; two of the three
Qwen runs were followed by fast Klein renders, the third by slow ones that survived a 20-minute idle gap. `POST /free` (unload_models +
free_memory) cut the process's private bytes from 17.0 to 6.2 GB and the next render was still 53.3 s/step (prompt `3c3c3ba9`, 377 s);
`C:/AI/Stop-ComfyUI.ps1` brought the same graph back to 95.2 s (prompt `49e5f4db`) on the process that replaced it. Who relaunched it: the
Studio's own backend recovery, 15 s after the stop (process 20392, parent = the Studio server, `.runtime/backends/20260915-035844-recovery-*.log`);
the probe's 45-second check saw no server only because ComfyUI takes longer than that to answer, and `Start-ComfyUI.ps1` then exited 0 on the
recovered server while its own child died on "Port 8188 is already in use" (`C:/AI/logs/20260915-035917-error.log`). Rule: a Klein render over
~3 minutes means stop ComfyUI on an idle queue and let the Studio's recovery (or the launcher) bring it back; run Qwen last.

| Variant (image 1) | Seed | Prompt ID | s | Output | Result |
| --- | --- | --- | --- | --- | --- |
| depth-feet: the depth map with everything below the ankles painted black (heels, floor band) | 2026091411 | `399c7b94` (cached sampler from the probe render `49e5f4db`, 95 s) | 5.0 | `Research/pose3-depth-feet_00002_.png` | **deep bend, bare feet, no heel shape**; head down, hands at the knees |
| depth-feet | 2026091412 | `df442f10` | 95.1 | `Research/pose3-depth-feet_00003_.png` | **deep bend, crossed legs, look-back, lettering, bare feet, no heel** |
| depth-feet | 2026091413 | `96cb2353` | 85.1 | `Research/pose3-depth-feet_00004_.png` | bend with bent knees, bare feet; the "?" speech bubble again |
| depth-painted: feet plus the tail and the skirt frill painted black | 2026091411 | `20f6383d` | 85.7 | `Research/pose3-depth-painted_00001_.png` | same figure as depth-feet within a few pixels: bend, bare feet |
| depth-painted | 2026091412 | `c4b86e9b` | 75.3 | `Research/pose3-depth-painted_00002_.png` | same as depth-feet seed 12 |
| depth-painted | 2026091413 | `90b911f0` | 75.4 | `Research/pose3-depth-painted_00003_.png` | same as depth-feet seed 13, speech bubble |
| hands-camera: the unpainted map, the pose fill names both hands and adds a camera sentence | 2026091411 | `e16a1a63` | 95.2 | `Research/pose3-hands-camera_00001_.png` | **lollipop hand at the lips, low camera from behind**, deep bend, bare feet, no heel |
| hands-camera | 2026091412 | `534a141d` | 95.4 | `Research/pose3-hands-camera_00002_.png` | **lollipop at the lips, other hand on the hip, low camera**, bend, crossed legs, bare feet |
| hands-camera | 2026091413 | `e0d5db92` | 96.6 | `Research/pose3-hands-camera_00003_.png` | **lollipop at the lips, hand on the hip, look-back**, bend, bare feet; speech bubble |
| skeleton-drawn: an OpenPose-style stick figure drawn with PIL from 17 hand-estimated keypoints (`pose3-skeleton-drawn.png`), shipped 9B graph, no depth node | 2026091411 | `64dd730c` | 75.8 | `Research/pose3-skeleton-drawn_00001_.png` | **the drawn pose: deep bend, legs as drawn (one straight, one crossing), the arm I drew raised is raised**, look-back, bare feet, lettering partial |
| skeleton-drawn | 2026091412 | `7c6d7971` | 75.3 | `Research/pose3-skeleton-drawn_00002_.png` | **same pose from the skeleton**, arms folded at the chest, look-back, bare feet |
| skeleton-drawn | 2026091413 | `3daae932` | 75.2 | `Research/pose3-skeleton-drawn_00003_.png` | **same pose**, hand behind the head as drawn, lettering intact, speech bubble |
| mannequin-drawn: grey capsule limbs and a ball head drawn with PIL from the same keypoints (`pose3-mannequin-drawn.png`), no depth node | 2026091411 | `b64ca00a` | 75.4 | `Research/pose3-mannequin-drawn_00001_.png` | body in the pose, but **the ball head is drawn as a blank sphere, no face, no hair**: identity lost |
| mannequin-drawn | 2026091412 | `514f1d1e` | 75.4 | `Research/pose3-mannequin-drawn_00002_.png` | same: grey sphere head and grey capsule arm drawn literally; a stray foot |
| mannequin-drawn | 2026091413 | `9ee8a5e4` | 75.4 | `Research/pose3-mannequin-drawn_00003_.png` | same: sphere head, grey arm, speech bubble |
| depth-8steps: the shipped depth graph (unpainted map) at 8 steps | 2026091411 | `a12392e3` | 105.6 | `Research/pose3-depth-8steps_00001_.png` | the 6-step figure again; a small heel shape on one foot |
| depth-8steps | 2026091412 | `de42d7f0` | 105.3 | `Research/pose3-depth-8steps_00002_.png` | the 6-step figure again, clean feet |
| depth-8steps | 2026091413 | `6554b1d9` | 100.3 | `Research/pose3-depth-8steps_00003_.png` | the 6-step figure again, speech bubble |
| copypose: **Copy Pose LoRA** (`KleinBase9B_PoseTransfer`, 1.0), character = image 1, pose picture = image 2, trigger + clothes named (`lora_pose.py`) | 2026091411 | `5d1d1179` | 75.1 | `Research/pose3-copypose_00001_.png` | **deep bend from behind, crossed legs, look-back; identity, lettering and the character's own white background kept; bare feet, no tights, no heels, no tail**; speech bubble kept |
| copypose | 2026091412 | `f9a7db6f` | 80.3 | `Research/pose3-copypose_00002_.png` | **same: the pose picture's bend with nothing of it leaking** |
| copypose | 2026091413 | `a7c311f6` | 80.4 | `Research/pose3-copypose_00003_.png` | same; speech bubble kept |
| copypose-depth: the same LoRA with the depth map as image 2 | 2026091411 | `f1481c1c` | 75.9 | `Research/pose3-copypose-depth_00001_.png` | bend followed, but **the map's black ground and a grey ghost figure are copied and a heel is drawn**: worse than the picture |
| copypose-depth | 2026091412 | `fb187a7b` | 75.2 | `Research/pose3-copypose-depth_00002_.png` | same: black ground, grey ghost |
| copypose-depth | 2026091413 | `efad6ab7` | 75.6 | `Research/pose3-copypose-depth_00003_.png` | same: black ground, grey ghost, speech bubble |
| replacechar: **replace-character LoRA** (`replace_character_v1_klein`, 1.0), pose picture = image 1, character = image 2, the author's prompt + clothes named | 2026091411 | `62ef11ee` | 80.1 | `Research/pose3-replacechar_00001_.png` | **the pose picture's exact pose, camera and framing**, face, hair and choker swapped in, lettering, pink shorts; **but image 1's shaded semi-realistic finish, its ground and its shark tail come along** |
| replacechar | 2026091412 | `8e383703` | 75.1 | `Research/pose3-replacechar_00002_.png` | same pose and camera; **image 1's black skirt kept** (the LoRA is trained to keep image 1's outfit), tail in the background |
| replacechar | 2026091413 | `41eb0f2e` | 75.2 | `Research/pose3-replacechar_00003_.png` | same pose and camera, pink shorts, tail and ground from image 1 |
| refcontrol-skel: **RefControl LoRA** (`refcontrol_v2_poses`, 1.0), the drawn skeleton = image 1, character = image 2, trigger + the skeleton wording | 2026091411 | `d542ed7b` | 75.3 | `Research/pose3-refcontrol-skel_00001_.png` | the skeleton's pose, as without the LoRA; lettering partial |
| refcontrol-skel | 2026091412 | `c271436b` | 75.2 | `Research/pose3-refcontrol-skel_00002_.png` | **indistinguishable from the no-LoRA skeleton render of the same seed** |
| refcontrol-skel | 2026091413 | `f25bd5d4` | 75.1 | `Research/pose3-refcontrol-skel_00003_.png` | same pose; lettering garbled, speech bubble |
| refcontrol-depth: the same LoRA with the depth map as image 1 | 2026091411 | `1ea84cd4` | 75.1 | `Research/pose3-refcontrol-depth_00001_.png` | the depth route's figure, hand behind the head; no visible gain over no LoRA |
| refcontrol-depth | 2026091412 | `5cbb69f4` | 75.4 | `Research/pose3-refcontrol-depth_00002_.png` | same; **the heel shape is back on one foot** (unpainted map) |
| refcontrol-depth | 2026091413 | `f0805e97` | 75.2 | `Research/pose3-refcontrol-depth_00003_.png` | same, speech bubble |
| mannequin-gen: **Mannequin LoRA** (`Mannequin_V1_F29B`, 1.0), the pose picture as the only reference, the author's prompt, 8 steps | 2026091411 | `ddd51f9c` | 68.2 | `Research/pose3-mannequin-gen_00001_.png` | **a clean white CGI mannequin in the exact pose: deep bend, look-back, hand on the hip, crossed legs, no clothes, no tail, no hair, black ground**; the feet keep the heeled shape |
| mannequin-combine: that mannequin picture as the pose picture of the shipped depth recipe (no LoRA) | 2026091411 | `aa98f658` | 90.1 | `Research/pose3-mannequin-combine_00001_.png` | **deep bend, look-back, hand on the hip (the mannequin carried it), identity kept**; heel-shaped foot (the mannequin's) |
| mannequin-combine | 2026091412 | `55fab498` | 85.8 | `Research/pose3-mannequin-combine_00002_.png` | same, hand on the hip; heel-shaped foot, a faint tail line |
| mannequin-combine | 2026091413 | `2bf5fcfe` | 86.0 | `Research/pose3-mannequin-combine_00003_.png` | same, hand on the hip; heel-shaped foot, speech bubble |

| depth-q8: the shipped depth graph with **`flux-2-klein-9b-Q8_0.gguf`** (9.98 GB, downloaded and SHA-256-verified tonight) | 2026091411 | `88c5c1c8` | 342.3 (first load) | `Research/pose3-depth-q8_00001_.png` | the Q6 figure again; **"loaded partially; 9538 MB loaded, 170 MB offloaded" beside the text encoder's 5171 MB residue, 40-45 s/step** |
| depth-q8 | 2026091412 | `99a2bd93` | 365.6 | `Research/pose3-depth-q8_00002_.png` | 6 steps in 3:58: **six minutes per render, not usable on 16 GB** |
| depth-q8 | 2026091413 | `d1edaa07` | 365.7 | `Research/pose3-depth-q8_00003_.png` | same |
| control: Q6_K again, fresh seed, straight after the Q8 runs (feet painted out) | 2026091414 | `0e72710a` | 85.1 | `Research/pose3-depth-feet_00005_.png` | 85 s: the process is healthy; the Q8 time is the model's VRAM fit, not the slow state |
| **Studio proving run, `combine-klein-9b-skeleton`** (`prove_skeleton.py`: POST /api/upload for the drawn skeleton, POST /api/jobs) | 2026091461 | job `26448d58-c1bb-41a5-a49f-74c4db4fec89`, prompt `977e450f-46ba-485f-a0f4-9a0a45204dc2` | 68.7 | `Combine/Klein-9B-skeleton_00001_.png` | **the drawn pose: deep bend, the raised arm, one leg straight and one crossing, look-back**, bare feet, face and hair kept; lettering garbled on this seed |

| **Studio two-pass journey, pass 1: `combine-klein-9b-depth`** with the hands-and-camera fill (`twopass.py`, POST /api/jobs) | 2026091451 | job `c31e7777-cf02-401e-8fda-aacd7fe13644`, prompt `503277a9-b692-47f6-944e-7a0a7058ce24` | 88.8 | `Combine/Klein-9B-depth_00002_.png` | **lollipop at the lips, hand on the knee, low camera from behind, deep bend**, lettering; one heel-shaped foot |
| **pass 2: `flux-edit` (Change one thing, Klein 4B) on pass 1's output**, staged through POST /api/assets/reference as Continue with this does; fill "redraw both feet as plain bare feet flat on the ground, with no high heel and no shoe shape" | 2026091451 | job `b92dae0c-e3b3-4586-909a-8f3f96b671f2`, prompt `b33b69f6-d4a4-4fe7-806f-00854674106c` | 44.3 | `Verified/FLUX-Edit_00009_.png` | **the heel became a bare foot; face, lollipop, lettering, shorts and pose unchanged**. Whole journey 135.7 s wall |

**The four LoRAs, in one line each.** *Copy Pose* (character = image 1, pose picture = image 2) is the second strong route: the character keeps
her own framing and background and takes the picture's pose with nothing of the picture leaking (3/3), but only with the real picture, not
a depth map. *replace-character* (pose picture kept as image 1) gives the most exact pose and camera and the best identity swap of the
pose-first family, at the price of image 1's finish, ground, tail and sometimes outfit: it is what the pose-first recipe should carry when the
pose picture's camera must stay. *RefControl* adds nothing visible over the base model with either a drawn skeleton or a depth map. The
*Mannequin* LoRA turns any pose picture into a clean mannequin in 68 s, and that mannequin works as the pose picture of the depth recipe
with the hand position carried (3/3); its heeled feet still need the ankle cut.

What decided it so far: **cutting the depth map at the ankles removes the heel-shaped foot (3 of 3 seeds, #427)**, and painting the tail
and skirt out as well changes nothing visible, so the minimal edit is the one worth wiring (a crop or a painted band below the ankles, not
a subject mask). **Hand and camera words move the hands and the camera on the depth route** (3 of 3: the lollipop hand, the hand on the hip,
the low camera from behind), which round two's blank-canvas test never managed for the bend: the depth map carries the body, the words carry
what the map does not fix. The hands-camera fill is now the wording the depth recipe's pose field suggests. **A drawn stick figure carries the
pose (3 of 3, arms included), a drawn capsule mannequin is copied literally**: thin lines are read as a pose, solid crude shapes as content;
shipped as `combine-klein-9b-skeleton` and proved through the Studio (job `26448d58`). **8 steps and the Q8_0 GGUF change nothing visible**
(the Q8 figures match the Q6 ones seed for seed) and Q8 costs six minutes a render because it only partially fits beside the text encoder.
**The two-pass journey works in the Studio as it stands** (136 s: depth Combine, then Change one thing on the output), which is the repair
loop the owner asked for until the ankle crop is a control.

## The ankle cut as a Studio control, 16 September 2026 (02:00-02:05)

`combine-klein-9b-depth` now carries the round-three edit inside the graph: **Cut the depth map below (%)** (`depth_cut`, PR #453) composites
a black source through a 100-row mask band starting at that row (SolidMask + MaskComposite + ImageCompositeMasked with `resize_source`,
applied to the ~1 MP map before the VAE encode); 100 cuts nothing, the variant *Cut below the ankles (86 %)* is the `paint_depth` rectangle
of `pose_sources.py` (`0.86 * h`). Proving run through the Studio (`prove_depthcut.py`, POST /api/jobs, `prove_depthcut.json`):

| Run | Seed | Job / prompt | s | Output | Result |
| --- | --- | --- | --- | --- | --- |
| the shipped depth recipe, `depth_cut` 86, same pair and fills as the 15 September proving run `22ff6394` (uncut, one heel-shaped foot) | 2026091441 | `b57c6f3f-0d12-430d-863e-02e0bd0ebaa0` / `7769c72d-602d-49cc-b4f0-41238d09fd03` | 122.9 (fresh ComfyUI, model load included) | `Combine/Klein-9B-depth_00003_.png` | **same bend, crossed legs and look-back; both feet bare on tiptoe, no heel**; face, hair, SHARK lettering, pink shorts kept; submitted graph node 33 `y` = 86 (`state.json` in the receipts root) |

| the same recipe at the default `depth_cut` 100 (no-op check, `prove_depthcut_noop.json`) | 2026091441 | `216239b8-981f-426a-9d50-b2b02ef8f7fb` / `6879ee82-cabe-4387-9580-ed8fa82ecc8a` | 90.5 | `Combine/Klein-9B-depth_00004_.png` | **byte-identical to the 15 September uncut output `Klein-9B-depth_00001_.png`** (PIL difference: bbox None, max 0): the composite is a no-op at 100 on the real runtime, so the recorded run stays reproducible |

Exact submitted recipes (`/api/jobs/<id>/recipe`, graph included): `prove_depthcut.recipe.json`, `prove_depthcut_noop.recipe.json`. Sheet: `examples/style-pose/combine-depth-cut-control.jpg` (uncut vs cut, same seed). Not verified: the control by clicking through the page
(the API run uses the page's prepare and worker path); any other pose picture; art acceptance (HUMAN_TODO q-28).

## Copy Pose as a recipe, 16 September 2026 (02:05)

`combine-klein-9b-copypose` (PR #452) ships the round-three `copypose` variant: the 9B graph with `LoraLoaderModelOnly`
`KleinBase9B_PoseTransfer.safetensors` at 1.0 ahead of the guider, the character as image 1 (`last_reference`, node 14) and the pose picture
as image 2 (the board slot, node 20); the wording leads with the LoRA's trigger sentence and carries three fills in reading order (who is in
image 1; image 1's clothes and colours; image 2's pose, hands and camera), subject-neutral outside the brackets. Second on the Combine
route, engine label *Klein 9B · Copy Pose*. Proving run through the Studio (`prove_copypose.py`, POST /api/jobs; `prove_copypose.json`;
exact recipe `prove_copypose.recipe.json`):

| Run | Seed | Job / prompt | s | Output | Result |
| --- | --- | --- | --- | --- | --- |
| the shipped recipe, the SHARK character on Picture to keep (image 1), the fan picture on Pose picture (image 2), fills replaced | 2026091471 | `61dd5375-aa6c-42ca-b1e0-12466689857e` / `1fbea73e-e37c-4753-b94c-039552b2640c` | 58.5 (warm) | `Combine/Klein-9B-copypose_00001_.png` | **the deep bend, crossed legs and look-back with the character's own light background and framing kept**, bare feet, no tights, heels or tail; face, hair and pink shorts kept, the lettering partly hidden by the bend, the character picture's speech bubble kept (as in research) |

Sheet: `examples/style-pose/combine-copypose-proving.jpg` (image 1, image 2, the output). Not verified: the recipe by clicking through the
page (the API run uses the page's prepare and worker path); the engine switch depth -> Copy Pose by clicking; any other pair; art acceptance
(HUMAN_TODO q-28 (e), which is now a choice between two shipped recipes).

## The pose editor's guide through the skeleton recipe, 16 September 2026 (04:10)

The *Draw the pose* panel (PR #466) renders its guide on the server (`POST /api/pose/render` -> `studio_workflow.pose_raster`, renderer
`studio.coco18-lines/v1`: stroke `min(w,h)//128` = 8 px at 1024x1536 against the 14 px of the hand-drawn research figure). Proving run
(`prove_pose_editor.py`: the panel's "Bent forward, looking back" starting figure, the `KP` list above with the right ear unknown, rendered by
the endpoint, then `combine-klein-9b-skeleton` through POST /api/jobs with that file on Pose skeleton and the same fills and seed as the
hand-drawn proving run `26448d58`; `prove_pose_editor.json`, exact recipe `prove_pose_editor.recipe.json`, the guide `pose-editor-drawn-pose.png`):

| Run | Seed | Job / prompt | s | Output | Result |
| --- | --- | --- | --- | --- | --- |
| the page-rendered guide (8 px strokes) on the shipped skeleton recipe | 2026091461 | `8b571dd4-ba0f-403b-9f3d-35019cb1e3a3` / `2a80b266-d1cd-46df-8ccd-32a8ed7a65e1` | 66.5 | `Combine/Klein-9B-skeleton_00002_.png` | **the drawn pose as with the hand-drawn figure: deep bend, the arm raised behind the head, one leg straight and one crossing, look-back, bare feet, face and hair kept**; the lettering hidden by the bend (garbled on the hand-drawn run of the same seed) |

Sheet: `examples/style-pose/pose-editor-proving.jpg` (guide, its output, the hand-drawn figure, its output). Thin 8 px lines carry the pose as
well as the 14 px ones on this seed. Not verified: drawing in the panel by hand in a browser and pressing *Use this pose* then Generate as one
journey (the use-case driver covers the panel up to the attached guide with zero generations; this run submitted the same request shape by
API); other seeds; art acceptance (HUMAN_TODO q-28 (d)).

## Night audition, 16 September 2026 (04:35-04:55): the cut sweep, the editor and Copy Pose at three seeds

Seven more Studio jobs (`audition_night.py`, results `audition_night.json`, exact recipes under `audition-recipes/`), same pair and fills as the
proving runs, so the single proving runs become small auditions and the new control gets its numbers. ComfyUI's model cache had been
released just before (see CURRENT_STATE, the RAM measurement), so the first run of each family includes its reload.

| Run | Job / prompt | s | Output | Result |
| --- | --- | --- | --- | --- |
| `combine-klein-9b-depth`, seed 2026091441, **depth_cut 80** | `f8c45ada-5549-42b9-a660-a5a4e3a7f928` / `822a47d8-d4bd-4710-8c78-c1660c9c9f05` | 121.2 | `Combine/Klein-9B-depth_00006_.png` | bare feet, the bend kept, head down; the figure sits lower in the frame (more of the map gone) |
| the same at **depth_cut 92** | `63f9ecaa-310b-4237-9d22-11c6264ce24c` / `c9263b40-1bbd-416b-abaa-0e9307438e1d` | 54.5 | `Combine/Klein-9B-depth_00007_.png` | **bare feet too**: the heel is already gone at 92; bend, crossed legs, look-back and lettering as in the 86 run |
| the same at 86 and 100 (recorded above) | `b57c6f3f…` / `216239b8…` | | | 86: bare feet; 100: one heel-shaped foot (the uncut map) |
| `combine-klein-9b-skeleton` with the page-rendered guide, seed 2026091462 | `bac76a97-098c-452d-a485-bccfd6b60282` / `b1a39482-abf5-4cab-914d-18b87aa6b6bc` | 93.1 | `Combine/Klein-9B-skeleton_00003_.png` | **the drawn pose held**: deep bend, the arm behind the head, one leg crossing, look-back with a smile, bare feet |
| the same, seed 2026091463 | `bf3d1c70-eb27-443c-9aad-53af07d6e970` / `bfa1a4d0-4c72-4e92-bf08-a60e46d57659` | 75.3 | `Combine/Klein-9B-skeleton_00004_.png` | **held again**: bend, arm behind the head, look-back, bare feet; lettering partly hidden |
| `combine-klein-9b-copypose`, seed 2026091472 | `572794b6-4681-4457-8a2f-9eec373fa387` / `37f19109-b8ef-4060-a451-70837585bc2c` | 132.9 | `Combine/Klein-9B-copypose_00002_.png` | **the picture's bend and look-back with the character's own light background kept**, both hands between the knees on this seed, bare feet, lettering intact |
| the same, seed 2026091473 | `069c5efe-e412-482d-83e6-4477b2633c4e` / `b3c4ff76-5bd3-4dff-9e29-b18e3626ed02` | 143.2 | `Combine/Klein-9B-copypose_00003_.png` | **held again**: bend from behind, a hand on the knee, face looking down in profile, bare feet, lettering intact |

Sheets: `examples/style-pose/combine-depth-cut-sweep.jpg` (80 / 86 / 92 / 100), `pose-editor-audition.jpg` (seeds 61-63), `combine-copypose-audition.jpg`
(seeds 71-73). What it settles: on this pair any cut between 80 and 92 removes the heel and 92 loses the least of the figure, so the recipe hint
now says 86-92; the page-rendered guide carried the pose on 3 of 3 seeds like the hand-drawn one; Copy Pose held on 3 of 3 seeds through the
Studio as it did in research. Not verified: other pairs; art acceptance (HUMAN_TODO q-28).

## Through the page

`combine-klein` proving run: see the catalog `execution_note` and `CURRENT_STATE.md` (job `fb0eb95d-ba3f-4025-a77e-9c62165d250f`).
Not verified here: art acceptance (HUMAN_TODO q-27), licence clearance of the imported pictures, Klein 9B / AniEdit 9B (still downloading).
