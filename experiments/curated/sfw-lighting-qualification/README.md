# SFW night lighting LoRA: WAI v17 comparison (25 September 2026)

**Result:** Five Studio jobs completed. The Illustrious build of Civitai model
[1711037](https://civitai.com/models/1711037?modelVersionId=1936270) darkened
the fixed night scene at both tested strengths. **0.6 is the useful trial
strength** on these two seeds: it kept the coat, adult subject, lantern and
bridge readable. At 1.0, much of the background and coat fell into near-black.
This is a small experiment, not a preset change, art acceptance or licence
clearance. The output PNGs remain in ComfyUI's local `output/Studio/`, outside
Git. Every output below was opened at full resolution (832 x 1216).

## Method

`run.py` submitted each job through Studio `POST /api/jobs` on the primary
ComfyUI backend, serially after a health, lease and queue check. It left a
submission marker before each POST and saved the Studio job, prompt ID, full
job response and `/recipe` after completion; it will not repeat any named run.
The `wai` preset, 832 x 1216, 30 steps, CFG 5.0, Euler ancestral / normal,
denoise 1.0, positive and negative prompts were fixed as in [PLAN.md](PLAN.md).
Only LoRA strength varied within a seed. The baseline's zero-strength LoRA
nodes were pruned in its saved recipe. Seed 2026092501 ran 0, 0.6 and 1.0;
seed 2026092502 repeated 0 and 0.6. The installed LoRA was 170,594,572 bytes,
SHA-256 `8bf1c001b1a6ecf463df812470008264ec94bd3a2b1952546eea789eeec4f27d`,
matching the listing and `.runtime/downloads/receipts.json`.

| Run | Seed | Strength | Studio job | ComfyUI prompt | Seconds in Studio | PNG | SHA-256 | Mean grayscale (0-255) |
| --- | ---: | ---: | --- | --- | ---: | --- | --- | ---: |
| Baseline | 2026092501 | 0 | `11c4fa44-e644-4e9e-b7e9-92d22a33bb55` | `74757156-fe16-40b9-8b57-2ceb7cf3908e` | 67.4 | `Studio/WAI-Illustration_00039_.png` | `8224f33b6a64643f08d4cd83ea37c3475fd19d4c32e5123df1b6dac73dc90a63` | 40.0 |
| Moderate | 2026092501 | 0.6 | `aede8fa2-59bf-46c8-ac66-289447798160` | `2370952c-c6b5-45ff-864c-628466678bcb` | 20.2 | `Studio/WAI-Illustration_00040_.png` | `ec3ebb3dcb44714a2abf5c2edf80cc3942cd85fb49924b1e0ace451eecabad78` | 28.4 |
| Strong | 2026092501 | 1.0 | `5c81ee83-8ac6-4545-b4f0-f0cca2165145` | `0b844c1e-0bdf-4040-a172-437e70572b7a` | 14.2 | `Studio/WAI-Illustration_00041_.png` | `773b31ddee3330262d4508223be16272dfd36c0397994fda436826beb68e793e` | 16.4 |
| Baseline 2 | 2026092502 | 0 | `c1194ca5-e9bf-47df-a6f0-8e5da2290106` | `1de840e9-a4de-43bd-8a92-3bc10fb2cab8` | 14.2 | `Studio/WAI-Illustration_00042_.png` | `65c4ff277359266b43343eff74527bd05bdd63e8dcf33277925fcac5e6eebb71` | 34.5 |
| Moderate 2 | 2026092502 | 0.6 | `4d695586-e9a7-456d-9b6a-4f07486c73c8` | `a4dc485f-1371-42be-a121-4231462420d8` | 16.2 | `Studio/WAI-Illustration_00043_.png` | `dffca90c82c90469208f057c150dfc33e8832037707df5259aecf61a5df34b7c` | 22.5 |

The first run included checkpoint load time; its 67.4 seconds is not a
LoRA-speed comparison. Mean grayscale was computed from each complete output
with Pillow and is only a simple brightness measure. No peak VRAM was
measured, so none is inferred.

## Visual inspection

All five images depict a fully clothed adult woman in a dark green coat with a
lantern against a river bridge at night. The lantern is held to the side,
although the prompt asked for it raised in the right hand; that mismatch is
already present in both baselines. Glove fingers are awkward in several images,
including the baselines. No explicit content or obvious wrong-base collapse
appeared. The fixed seed did not freeze composition: the LoRA moved the bridge,
subject and lantern somewhat.

- Seed 1: the baseline has a bright blue background (lighting 0 as control;
  preservation 2; artifacts 1 for the glove). At 0.6 the background and coat
  darken while face, lantern and clothing remain readable (lighting 1,
  preservation 2, artifacts 1). At 1.0 the lantern and face remain visible but
  the coat and bridge lose much detail (lighting 2, preservation 1, artifacts 1).
- Seed 2: the baseline is a brighter bridge scene (lighting 0, preservation 2,
  artifacts 1). At 0.6 the same night read is distinctly darker with the coat,
  face, bridge and lantern still visible (lighting 1, preservation 2,
  artifacts 1). No 1.0 run was planned for this seed.

**Recommendation:** keep the pin available for further SFW trials and prefer
0.6 over 1.0 for this WAI recipe. Do not mark the `wai` preset verified based
on this five-image comparison. The owner has not accepted these images as art.
The model's Civitai flags are recorded in `models/library.json`; they and the
WAI mirror do not establish creator authentication or commercial clearance.
