# A drawn skeleton drives WAI v17 through Xinsir OpenPose — research, 22–23 September 2026 (#761, #445)

Question: which ControlNet strength and schedule let a **drawn, precomputed** COCO-18 skeleton hold the pose on
WAI v17 (Illustrious SDXL) without destroying its look, and does the guide's drawing convention, the Union
ControlNet or Animagine XL 4 change that. No detector runs anywhere: the skeleton PNG goes from `LoadImage`
straight to `ControlNetApplyAdvanced`.

All 63 pictures here were rendered **straight against ComfyUI** on 127.0.0.1:8188 (primary backend, ComfyUI 0.35.0,
RX 9070 XT, ROCm 7.2) by `research-scripts/run_grid.py`, one prompt at a time; the Studio's own path is recorded
separately under *Studio proof* below. Generated is not accepted: nothing here is art acceptance or licence
clearance.

## Setup

| Part | Value |
| --- | --- |
| Checkpoint | `waiIllustriousSDXL_v170.safetensors` (library pin `sdxl-wai-v170`); Animagine rows `animagine-xl-4.0-opt.safetensors` |
| ControlNet | `xinsir-openpose-sdxl.safetensors` (pin `controlnet-xinsir-openpose-sdxl`, Apache-2.0 card); Union rows `xinsir-union-sdxl-1.0.safetensors` + `SetUnionControlNetType` = `openpose` |
| Graph | `workflows/api/wai-pose-api.json` with checkpoint, prompts, canvas, seed, ControlNet and schedule set by `graph()` in `run_grid.py`; `start_percent` 0 throughout |
| Sampler | 28 steps, Euler ancestral, normal, CFG 5.0, 832×1216, denoise 1 |
| Seeds | 2026092201, 2026092202, 2026092203 (every cell) |
| Positive (WAI) | `1girl, solo, full body, dynamic pose, adventurer, silver hair, long ponytail, green eyes, brown leather jacket, white shirt, black trousers, brown boots, white background, simple background, masterpiece, best quality, amazing quality` |
| Negative (WAI) | `bad quality, worst quality, worst detail, sketch, censor, multiple views, text, watermark` |
| Animagine prompts | the same subject in Animagine's tag order with `original, safe` and its quality tail (`ANIMAGINE_POSITIVE` / `ANIMAGINE_NEGATIVE`) |

The prompt names the character and says only *dynamic pose*, so the pose comes from the ControlNet.

**Skeletons** (`research-scripts/make_skeletons.py`, joints in `research-scripts/skeletons.json`), both drawn by the
pose editor's own code path (`app/pose_guide.artifact` + `studio_workflow.pose_raster.render_png`) at 832×1216:

- `skeleton-action.*.png`: right arm raised overhead, left hand on the hip, left knee raised, standing on the right
  leg, facing the viewer;
- `skeleton-bent.*.png`: the editor's *Bent forward, looking back* starting figure (deep waist bend seen from behind,
  head low looking back, left arm raised behind, legs apart; right ear unknown).

Each exists twice: `.openpose.png` in the controlnet_aux convention Xinsir was trained on
(`studio.coco18-openpose-xinsir/v1`, see `docs/pose-control/ROUTE-BINDING.md`) and `.lines.png`, the same joints in
the thin-line guide the Klein skeleton recipe uses (`studio.coco18-lines/v1`).

## Prompts and timings

This ComfyUI reloaded the checkpoint for every prompt (about 42 s), so after the three single-image baselines each
prompt carried one group of cells behind shared loaders (one KSampler per cell; a KSampler's noise depends on its
own seed only, so every picture is the one a single-cell graph with that seed gives). Times are ComfyUI's own
`execution_start` → `execution_success` for the whole prompt.

| Prompt ID | Cells | Seconds |
| --- | --- | --- |
| `979937fc-82b9-45fa-9821-81c44ec9fd8e`, `f909de0d-6cad-42cc-a381-e534c972816c`, `281d4a47-b07c-425a-9267-86b1a1dac81d` | no-ControlNet baseline, one seed each | 103.0, 85.2, 66.8 |
| `8025c625-d917-47aa-a20d-4dd8ebd74553` | action: strength 0.6/0.8/1.0 × end 0.6/1.0, plus 0.9/0.85 (the `wai-pose` default), 3 seeds = 21 | 896.8 (≈43 s each) |
| `45e46dfb-8e53-4fb7-85db-6c47654b70ce` | bent: the same 21 | 611.4 (≈29 s each) |
| `38816951-c013-4ed1-9f5a-b526007b8056` / `70e85db8-84e6-42e6-981f-b1b0bd53e309` | thin-line guide at 0.8/1.0, action / bent | 140.4 / 99.5 |
| `88b6163b-cc27-4009-8b4d-4d2fac77cd00` / `7a889236-726a-47a2-a6eb-b71769ba6d7e` | Union ControlNet at 0.8/1.0, action / bent | 125.8 / 96.2 |
| `deaa646a-cb15-4be8-a829-84de74e9f69f` / `7ed5a372-199b-437e-8758-add3d0fe5e18` | Animagine XL 4 at 0.8/1.0, action / bent | 78.9 / 74.6 |

**Failed candidates:** the first Animagine prompts `43574d0b-19ba-4742-b3a5-cf0dab931a32` (23.8 s) and
`2fbfb9ff-ca05-44b6-a391-e7cf8610f57b` (46.0 s) ended in `execution_error` at `CheckpointLoaderSimple`:
`IndexError: list index out of range` in `model_management.free_memory`, the known first-checkpoint-swap fault. The
outcome was certain (nothing generated), so each was queued once more (`--retry-failed`) and both retries succeeded;
the failed records stay in `grid.json` under `failed_attempts`. One status poll also died on a Windows socket error
(`WinError 10013`); that prompt had finished and its history was read, not resubmitted.

## What I saw

Scores are mine, from the full-size PNGs. *Held* means every named feature of the skeleton is in the picture.
Background brightness is the mean of a 40-pixel strip at the left edge (255 = white, as the prompt asks).

**Action skeleton** (raised right arm, left hand on hip, left knee up):

| Setting | Seed 01 | Seed 02 | Seed 03 | Seed 03 background |
| --- | --- | --- | --- | --- |
| no ControlNet | random dynamic pose | random | random | 246 |
| 0.6, end 0.6 / 1.0 | arms out low: lost | knee up, no raised arm | side view, arms bent at the chest | 233 / 232 |
| **0.8, end 0.6 / 1.0** | held | held | arm and knee held, left hand at the head instead of the hip | 178 / 173 |
| 0.9, end 0.85 | held | held | held | 69 |
| 1.0, end 0.6 / 1.0 | held | held | held | 34 / 33 |

**Bent skeleton** (deep bend seen from behind, looking back):

| Setting | Seed 01 | Seed 02 | Seed 03 |
| --- | --- | --- | --- |
| 0.6, end 0.6 / 1.0 | upright jump: lost | forward bend seen from the side | forward bend from the front, black background |
| **0.8, end 0.6 / 1.0** | held, looking back under the arm | held | bends forward but faces the viewer; black background |
| 0.9, end 0.85 | held | held | as 0.8 |
| 1.0, end 0.6 / 1.0 | held | held | as 0.8 |

- **Strength** is the lever: 0.6 never raised the arm and never showed the bent figure from behind; 0.8 held 4 of the 6
  figure-seed pairs in full and got one thing wrong on the other two (the action figure's left hand on seed 03, the
  bent figure's view on seed 03); 0.9 and 1.0 fixed that hand (5 of 6) but not the view.
- **end_percent** did nothing measurable: the mean absolute difference between end 0.6 and end 1.0 at the same
  strength and seed was 1.2–5.5 grey levels of 255, invisible side by side.
- **Style:** the WAI rendering (clean lineart, cel shading, the named colours, face and hands) held in every
  ControlNet picture; hands were clean at 0.8. The one visible cost is the background on seed 03: it darkens with
  strength on the action figure (233 → 173 → 69 → 33) and is black on the bent figure at every strength, although
  the prompt asks for a white one. The skeleton's black canvas leaks into the composition on that seed; seeds 01 and
  02 stayed white (239–255) at every setting.
- **Drawing convention matters.** The same joints drawn as thin lines (the Klein guide) held the pose on 2 of 3
  action seeds (seed 03 dropped the raised arm) and **0 of 3** bent seeds (an upright figure with arms out, a mangled
  front-facing bend, a crouch). The controlnet_aux drawing at the same setting held 3 (one with the wrong hand) and 2.
- **Union ControlNet** (openpose type) held the bent figure from behind on 3 of 3 seeds (seed 03 still black) but lost
  the action figure's arms on 3 of 3 (knees held; one seed raised both arms). Mixed, so not adopted.
- **Animagine XL 4** at 0.8: arm raised on 2 of 3 action seeds, every bent seed turned towards the viewer, and it
  added speed lines, splashes and a blue sky against *simple background*. Not adopted as a new recipe; the existing
  *Animagine — pose guide* recipe stays as it was.

## Chosen defaults (shipped as `wai-skeleton`)

WAI v17 + Xinsir OpenPose, **strength 0.8 from 0 to 100 % of the steps**, the guide drawn in the controlnet_aux
convention at the generation canvas. Variants: *Pose firmer (1.0)* (fixed the one wrong limb here, darker background
on that seed) and *3-seed audition*. No preprocessor: the skeleton is already the preprocessed map, and running
OpenPose/DWPose on a stick figure is what this route exists to avoid. When a seed turns the background dark, try the
next seed before raising strength.

## Studio proof plan (22 September; done, see the proof section below)

`research-scripts/prove_wai_skeleton.py` submits one `wai-skeleton` job through POST /api/jobs with the guide drawn by
POST /api/pose/render. Not run yet at the time: the running Studio serves the main checkout, which does not contain this branch.
The catalog entry stays `verified: false` until that run is recorded here and in its `execution_note`.

## Files

- `research-scripts/make_skeletons.py`, `run_grid.py`, `contact_sheet.py`, `prove_wai_skeleton.py`
- `research-scripts/prove_wai_skeleton.json`, `prove_wai_skeleton.recipe.json`: the Studio proof's job record and exported recipe
- `research-scripts/grid.json`: every cell with seed, settings, prompt ID, ComfyUI status, time and output file
- `research-scripts/skeletons.json`, `skeleton-*.png`: the four guides
- `examples/style-pose/sdxl-skeleton-grid-action.jpg`, `sdxl-skeleton-grid-bent.jpg`, `sdxl-skeleton-compare.jpg`

The full-size renders stay in ComfyUI's `output/Research/sdxl-skeleton/` on this PC (not in Git).

## Studio proof — 23 September 2026 (02:41)

`research-scripts/prove_wai_skeleton.py --guide render` through the running Studio after the #843 merge and a
restart: the action skeleton drawn by `POST /api/pose/render` with `studio.coco18-openpose-xinsir/v1` (sha256
`17b2b72a…`, byte-identical to `skeleton-action.openpose.png`), then one `POST /api/jobs`. Job
`6a342bbf-995f-466e-9e51-2bf169b11460`, prompt `9f3bea4a-b7f4-4a68-b1e9-c766ab213816`, seed 2026092201, 832x1216,
36.4 s on the primary backend; `prove_wai_skeleton.json` and `prove_wai_skeleton.recipe.json` beside the script.
Inspected: the raised arm over the head, the hand on the hip, the straight standing leg and the bent raised knee
all follow the guide; WAI's clean finish on white is kept; hands and boots are clean. `wai-skeleton` is now
`verified: true`. Generated and inspected by an agent — not art acceptance or licence clearance.
