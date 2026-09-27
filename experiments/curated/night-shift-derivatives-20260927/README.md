# Night Shift derivatives from the owner's anchor — 27 September 2026 (16:56-17:26 local)

**Owner decision (27 Sep 2026, in chat; recorded in PR #1179):** the anchor is `retro-anime-master-z2`, and Night Shift stays
the pilot world. That anchor is Z-Image Turbo fp8, Studio job `c69e6e18-4739-458d-b546-1dd6e8174e19`, prompt
`adfc94c4-0de0-44af-ae72-72b3133742f0`, 1344x768.

This run derives `retro-anime-quiet`, `-hero`, `-poster` and `-card`, plus the upscaled master, from that exact file. It
follows `docs/adaptive-studio/assets/` (PRODUCTION-PLAN W1, DELIVERY-SPEC, ART-DIRECTION, and `brief.py show <id>`).
`retro-anime-wall` is the owner's ChatGPT job and was not made. Every file here is **candidate-produced and agent-judged
only**. None is art-accepted, runtime-qualified or licence-cleared. The owner picks.

**Anchor check.** `sha256` of `output/Research/lab-20260927/asset-kit/retro-anime-master/retro-anime-master-z2.png` is
`c22b723c65198b896ff9e542b05745742a447b62e91a7e5cfb8c0f593df7dfa9`. That matches the value given, and it is byte-identical to its
source `primary:output/Studio/Z-Image-Fast_00004_.png`. It was uploaded once through the Studio's `POST /api/upload`, which
echoed the same sha256 (`receipts/anchor-upload.json`). Every derivative starts from that upload.

**Where the files are.** Full-size PNG/WebP/AVIF files stay local, in the DELIVERY-SPEC layout, under ComfyUI
`output/Research/nightshift-20260927/<asset-id>/{master,renditions,review,candidates}/`. Each asset has a
`receipt.json`, and the pack has a `pack-manifest.json`. Only the small contact sheets and the receipts are in Git.

## Results

| ID | Route actually used | Shortlist (agent) | Output |
| --- | --- | --- | --- |
| `retro-anime-master` (upscale) | `anime-esrgan` model (RealESRGAN x4plus anime 6B), raw 4x, Lanczos to 3840 wide, 17 px trimmed top and bottom | **MA** (raw 4x then down) keep; MB (Studio 2x then Lanczos up) keep, 2nd | 3840x2160 PNG; 1280x720 and 960x540 previews in WebP (48 / 32 KiB) and AVIF (53 / 36 KiB) |
| `retro-anime-quiet` | Studio `flux-edit` (FLUX.2 Klein 4B) on the anchor, 4 candidates + 1 refinement round of 2, then a recorded registration warp and the same upscale path | **r1-2** keep; r1-1 keep, 2nd; a1/a2/b1/b2 fixable | 3840x2160 PNG on the master's exact crop box; 1280x720 WebP poster (41 KiB) |
| `retro-anime-hero` | crop of master MA (box 0,360,3840,1960) | keep | 3840x1600 PNG; 1920x800 (68 KiB) and 960x400 (26 KiB) WebP; portrait crop plan (not produced) |
| `retro-anime-poster` | resize of master MA, full 16:9, no crop | keep | 1280x720 (48 KiB) and 640x360 (18 KiB) WebP |
| `retro-anime-card` | two square crops of master MA | **tight** (2240,300-3840,1900) keep; wide (1680,0-3840,2160) keep, 2nd | 1024 PNG each; 512 (34 / 26 KiB) and 256 (12.5 / 9.5 KiB) WebP |

Every rendition is within its brief's byte budget, at WebP/AVIF quality 90: master previews <=300 KiB, hero <=250,
poster <=220/<=90, card <=80/<=30. Contact sheets:
- `pack-contact.jpg`: the chosen set, plus the quiet review frames (50 % crossfade, master edges over quiet) and the cards at 96 px.
- `quiet-candidates-contact.jpg`: the anchor and all six quiet candidates, with verdicts.
- `upscale-compare.jpg`: 1:1 crops of plain Lanczos against MA and MB.

## What was run (times from receipts)

| Key | Route | Job / prompt | Time | Peak commit |
| --- | --- | --- | ---: | ---: |
| master-up-u1-studio2x | Studio `anime-esrgan` | `c057d94c` / `d9bc3757` | 455.3 s (16:56:43-17:04:19) | 70.9 % |
| master-up-u2-raw4x | direct ComfyUI, same graph with `ImageScaleBy` 1.0 | — / `f5d51a36` | 1.7 s (nodes 1-3 reused from ComfyUI's cache of u1) | — |
| quiet-a1 / a2 / b1 / b2 | Studio `flux-edit`, wording A or B, seed 2026092781 or 82 | `99fa529a`/`2e47d288`, `22d40c6c`/`d835fb84`, `c9a1ba4f`/`d783f1f2`, `1fdf076f`/`b74a4f48` | 62.5 / 30.4 / 28.4 / 32.3 s (17:11:39-17:14:16) | 75.6-76.4 % |
| quiet-r1-1 / r1-2 | Studio `flux-edit`, refinement wording (`receipts/r1-words.txt`), seeds 81 / 82 | `9d48b796`/`3bce25d6`, `a08efbc3`/`5702bc23` | 39.2 / 36.9 s (17:17:28-17:18:45) | 76.6 / 74.2 % |
| quiet-up-raw4x | direct ComfyUI raw 4x on the warped r1-2 | — / `5d725cb9` | 93.8 s exec (from 17:21:23) | — |

The Studio `anime-esrgan` job spilled 9.0 GB of GPU memory into system RAM (the Studio's own message), which explains its
455 s. The quiet upscale ran the same model pass in 93.8 s without a Studio sampler, so the two times do not compare
cleanly. Before the run, ComfyUI's cache was released with `POST /free` while its queue was idle: host commit went from
59.6 % to 55.4 %. Commit read 50.5-62.9 % before the jobs (`receipts/runs.jsonl`). A separate `style-pose-wai` proof for
PR #1179 ran between the upscale and the quiet edits (17:05-17:10); it is not part of this pack.

## Quiet Morning: what changed between rounds

- **Round 0** (4 candidates, two wordings × two seeds): the lamp stayed on, the monitor went dark, and the rain stopped. All
  four redrew the window, though. The dark mullioned frame became a white modern one, and the rail, train and poles view became
  apartment blocks, or a dusk skyline in b2. a2 also threw a bright diagonal light beam across the left wall. Verdicts: all
  **fixable** (control 3: the architecture changed).
- **Refinement round 1** (one targeted change: the keep list now names the dark window frame with its vertical divider, and the
  view with the rail line, poles and buildings): both seeds kept the frame, divider, poles, train and red sign, now in morning
  mist. **r1-2** has the quietest wall. r1-1 is brighter but has lighter blotches on the left wall and added overhead wires.
  The second refinement round the handoff allows was not needed.

**Registration.** Every Klein edit came back about 0.7 % larger and a few pixels off. Patch-wise edge NCC over 25 patches
measured a mean |shift| of 3.3 / 1.5 px (x / y, at 1344x768) for r1-2. A fitted affine warp (bicubic, edge-replicated border
of at most about 8 px at the right edge) brings it to 0.50 / 0.15 px (`receipts/align-quiet-r1-1-quiet-r1-2.json`). The warped
file then went through exactly the master's upscale, resize and crop, so the two 3840x2160 files share one pixel grid. The 50 %
crossfade frame shows no doubled furniture. Registration is measured on edges, and the window view legitimately differs
(rain and night become mist and day), so the view region scores low by construction.

## Agent pre-review (docs/quality/JUDGING-RUBRIC.md; `judgements.jsonl`)

`control` scores faithfulness to the anchor. `anatomy` is null (no figures).

- **Master MA** (5/–/5/4/5/5, keep). ESRGAN smooths the anchor's painterly plaster grain on the left wall into near-flat graphite:
  crop 400,600-1000,1100 at 3840. Lines at the CRT and train come out cleaner than a plain resize. Right-zone edge energy is
  7.98 for MA against 7.14 for MB. This is **not a native 4K generation**: it is an upscale of a 1344x768 original.
- **Quiet r1-2** (4/–/5/5/5/4, keep). The monitor's front buttons are simplified and its screen is black (crop 1040,210-1180,330 at
  1344). The heavy mist may read as overcast rather than morning. The owner decides whether it reads as "quiet", not "error".
- **Hero, poster** (keep). These are crops and resizes of MA. The hero trims the upper window and the chair base.
- **Card tight** (keep, 1st). At 96 px the lamp, CRT and window read clearly, and the train shows as a thin light strip.
  **Card wide** (keep, 2nd): a dark wall strip fills the left quarter.

## Not done or not verified

- **Not made:** `retro-anime-wall` (ChatGPT, the owner's job). Nor were the parked commitments (the guide companion, all sound,
  7 of 8 promotion pieces, all parallax layers, 5 of 6 loops), per the owner's deferral.
- **Not verified:**
  - No art acceptance. No runtime qualification: nothing was shown in the actual slots at 390x844, 1440x900 or 1920x1080, and
    nothing is wired into the app.
  - No decoded-memory test while inference runs.
  - Only the WebP and AVIF encoder byte counts were measured. They were not visually checked against the lossless masters
    beyond the contact-sheet view.
  - The hero's portrait crop is a plan in `asset-receipts/retro-anime-hero.composition.json`, not a file.
- **Licence:** Z-Image Turbo's base weights are Apache-2.0 (per the asset-kit README); FLUX.2 Klein 4B terms and Real-ESRGAN
  terms were not re-checked here. A render is not licence clearance.

## Next (owner)

1. Art-review the set in `pack-contact.jpg`, or the full files under ComfyUI `output/Research/nightshift-20260927/`.
   Pick quiet r1-2 or r1-1, the card framing, and master MA or MB (or reject).
2. Then `retro-anime-wall` in ChatGPT with the anchor uploaded. A later code session wires the accepted renditions in.

## Files

- `receipts/runs.jsonl`: one line per render, with job and prompt IDs, controls, input and output sha256, sizes and commit
  readings. Direct graphs are included.
- `receipts/studio-jobs/<key>/`: the Studio's own `recipe.json` and `state.json`, with the exact submitted graph.
- `receipts/asset-receipts/*.receipt.json`: one filled `receipt-template.json` per asset ID, plus the hero composition
  note. `receipts/pack-manifest.json` lists every local file with its sha256.
- `receipts/*.py`: as-run scripts with this machine's local paths. They are not portable reproductions.
