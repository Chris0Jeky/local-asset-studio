# Asset-kit master candidates — 27 September 2026

Candidates for the adaptive-studio wishlist (`docs/adaptive-studio/assets/`):

- `retro-anime-master` (Night Shift, the proposed pilot)
- `atelier-master`
- `sakura-master`
- `minimal-pro-master`
- the helper states `state-blank` and `state-source-required`

The work stops at candidates. Derivatives (quiet, hero, poster, card, layers) need the owner to pick an anchor first. Every file here is **candidate-produced and agent-judged only**. None is art-accepted, source-reviewed, runtime-qualified or licence-cleared (DELIVERY-SPEC acceptance stages).

The briefing asked for this work. Note that `HUMAN_TODO.md` still records `adaptive-pilot-world` as "option B, defer artwork" (23 September). This run does not change that record, and no candidate is installed anywhere in the app.

## Which model (one seed per model, Night Shift brief, 1344x768)

Every route ran seed 2026092701 once. Three routes (Z-Image, Qwen-Image 2.1, the Krea atelier stack) got the identical Night Shift paragraph. Two did not (`receipts/model-comparison-studio-plan.json`):

- **Krea + retro LoRA**: the same paragraph with the LoRA trigger `purple retro anime style, ` prepended.
- **WAI**: a Danbooru-tag rewrite of the brief (`no humans, scenery, indoors, anime screencap, 1990s \(style\), ...`) with a negative prompt that excludes `1girl, 1boy, person`, text and watermarks.

The `notes` field in `receipts/model-comparison-judgements.jsonl` says "same Night Shift prompt"; for those two rows it is wrong, and this paragraph supersedes it.

| Model / route | Time | Agent verdict | What it did |
| --- | ---: | --- | --- |
| **Z-Image Turbo fp8** (`zimage-fast`, Studio) | 217.8 s (this one job) | keep | Cel-painted 1990s anime look, quiet left wall, rose/cyan train lights in the rain, CRT and lamp at right |
| Qwen-Image 2.1 INT8 (`qwen21` backend, direct) | 67.5 s exec (this one run) | keep | Strongest prompt following; a semi-real film look with little rose. See the people problem below |
| Krea 2 GGUF + retro-anime LoRA (`krea-portrait-gguf`) | 271 s | fixable | Very quiet wall, but a heavy purple cast from the LoRA trigger |
| Krea 2 GGUF atelier stack | 1244 s (ComfyUI slow state, 65-77 s/step) | fixable | Graphite and rose on palette and painterly, but the left wall is cluttered |
| WAI v17 (SDXL) | 42 s | reject | Symmetric twin desks and pictures on both walls, with no quiet side |

**One-seed preference: Z-Image.** On this single seed, its picture matched the cel-anime brief best (agent-judged keep: adherence 5, style 5) and kept the left wall quiet. Qwen-Image 2.1 was also judged keep (adherence 5, style 4, a semi-real look). One seed per model is not a ranking: the three Krea/WAI routes may do better on other seeds, and two of them had different wording. More seeds per route are needed before calling a winner.

Z-Image speed in the later master series (`receipts/studio-jobs.jsonl`, Studio `wall_s`): the first job of each world's new text took 126.6-186.9 s. 11 of the 12 further seeds with the same text took 9.1-14.9 s, but `minimal-pro-master-z4` took 190.2 s with the same text as z1-z3. Its cause is not recorded (its host commit started at 52.6 %, the lowest in the series). So a further seed with the same text was usually about 10 s here, not always.

Z-Image Turbo's base weights are Apache-2.0; Qwen-Image 2.1 is under a non-commercial research licence. That licence difference matters for app artwork, and it is the owner's call, not cleared here.

Qwen followed the prompt most literally on its one comparison seed. With both "seated height" and "no characters" in the wording, it drew a seated person in all 8 of the first retro/atelier candidates. The empty-room rewording fixed that (the `r` series), and those 8 are recorded as rejects.

## Candidates

The contact sheets show every non-rejected candidate, labelled `<world>-<series><n> [verdict]`. `q0`, `c` and `r` are Qwen-Image 2.1; `z` is Z-Image.

- `retro-anime-master-contact.jpg`, `atelier-master-contact.jpg`, `sakura-master-contact.jpg`, `minimal-pro-master-contact.jpg`: 1344x768 masters shown at 448x256.
- `states-contact.jpg`: the four RGBA helper-state candidates (Qwen-Image 2.1 `qwen21-rgba`, 1248x832, true alpha 0-255) on a light surface (top) and a dark one (bottom).
- `model-comparison-contact.jpg`: the five-model comparison.

**Agent shortlist for the owner (pre-review, not a pick):**

| World | Shortlist |
| --- | --- |
| Retro Anime | z1, z4, z2, r3 |
| Atelier | z4, z1, r2, r3 |
| Sakura | z2, z1, c2, z4 |
| Minimal Pro | c2, c4, z4, z1 |
| Helper states | `state-blank-c2` (keep); `state-source-required-c1` (fixable: the frame nearly fills the canvas) |

The Z-Image Minimal Pro rooms put the skylight at top centre, which pulls the eye to the middle. The Qwen c2/c4 keep the light at the right.

Known gaps against the brief:

- The masters are 1344x768, not the 3840x2160 target; any upscale is a later, recorded derive step.
- Z-Image drew the Atelier courtyard as a window, not an open doorway.
- The Retro rose accents are small.
- `state-blank-c1` has a grey matte smear visible on dark surfaces.

## Files and receipts

- `manifest.json`: every rendered item, with world, key, model, prompt ID, Studio job ID where there is one, source path (`primary:` or `qwen21:` output root), size, mode, SHA-256, verdict and worst defect. The four Studio comparison rows copy their verdict and worst defect from `receipts/model-comparison-judgements.jsonl`.
- `judgements.jsonl`: `docs/quality/JUDGING-RUBRIC.md` records for all 45 asset renders (not blind: one model per series). `receipts/model-comparison-judgements.jsonl` covers the five-model comparison.
- `receipts/`: world prompts, exact direct-ComfyUI graphs, Studio plans and job receipts, and direct-run logs with `exec_s` and host-commit peaks. The 25 Qwen direct runs (`qwen21-direct-runs.jsonl`) peaked at 76.6-88.8 % commit; all but `retro-anime-master-r1` (88.8 %) stayed between 76.6 and 79.2 %. The 24 Studio jobs peaked at 70.4-83.5 % (`cmp-krea-atelier` has no recorded peak).
- `receipts/studio-jobs/<key>/`: for each of the 24 Studio jobs, the Studio's own `recipe.json`, `state.json` (with the exact submitted graph under `submissions`) and `workflow.json`, copied from the local `experiments/runs/<job-id>/` folder with only line endings normalised to LF. `studio-jobs.jsonl` maps each key to its job ID. The Studio refused three RGBA jobs with its 32 GiB headroom gate until the qwen21 cache was released with `POST /free` between jobs.
- Full-size PNGs and an `index.html` gallery stay local: ComfyUI `output/Research/lab-20260927/asset-kit/` on the primary install. Masters, states and comparison images are copied there from both backends.

## Next (owner)

1. Pick one Retro Anime anchor, or reject the set.
2. Only then, derive `retro-anime-quiet`, `-hero`, `-poster` and `-card` from that exact file and its checksum.

The other worlds are P2 and stay candidates.
