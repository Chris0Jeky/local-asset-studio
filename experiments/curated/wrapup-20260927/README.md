# Wrap-up live proofs — 27 September 2026 (late, 23:05-23:22 local)

These runs came after #1236 (the wide seam band and the loosened Night Shift look) and #1240 (`wai-vary`) merged, followed by a
Studio restart per the ritual. Everything was driven through the real Studio page in headless Chromium, and every job was followed through the API.
All prompts are SFW. Timings come from the job receipts. The agent pre-reviews below are execution notes, not art acceptance: the owner judges
(HUMAN_TODO `seamless-tiles-1220` and `wai-vary-look-1202`).

## 1a. Make seamless, wide band (#1220)

The flat floor texture (source asset `0a9839a5`) was run again with **Seam band: wide (160 px)**:
Asset library -> the picture -> Make seamless -> Generate.

- The job was `974236b1-fa82-4420-8202-833627d3fc3b` (`zimage-seam-repair`), with one prompt, and took **187.9 s**.
- **Seam score 13.53 → 2.17** against the tile's own neighbour gradient of 1.22. The narrow 112 px band earlier today gave 13.53 → 1.93.
- The new tile is asset `a4158f9f` and its 3×3 preview is `e84e7a97` (hashes in `receipts/tiles-assets.json`).
- Host commit before Generate was 54.2 % (51.9 of 95.7 GiB).
- **Sheet:** `tiles-floor-band-sheet.jpg` shows the narrow 3×3 on the left and the wide one on the right.
- **Agent pre-review:** the plank-end row is softer with the wide band but still repeats. It reads as fixable, not solved.

## 1b. Loosened Night Shift look (#1224, #1236)

The scene was "a rain-soaked arcade entrance on a narrow street at night; at the right edge a glowing vending machine beside the entrance". The look was prepared on `zimage-fast` at 1344×768.

- **Quiet-wall box off:** job `e8246b79-1768-445d-b61d-ac6cd773a09c`. It made 2 pictures, seeds 2026092752 and 2026092753 (assets `de1f9777` and `1d83cf81`), and took **171.9 s**. Host commit was 63.9 %.
- **Quiet-wall box on:** job `0ef89646-b99d-4fec-a1cd-4d1544c34059`. It made 1 picture, seed 2026092752 (asset `ee54c563`), and took **151.9 s**. Host commit was 62.4 %.
  - The box adds the sentence "The left half and centre of the frame is a plain dark graphite wall..." to the prepared wording.
- **Sheet:** `look-v2-sheet.jpg`, in this order:
  1. before, from the #1238 run;
  2. box off, seed 752;
  3. box off, seed 753;
  4. box on, seed 752.
- **Agent pre-review:**
  - With the box off, the scene now carries: the entrance reads as glass doors under an awning, no longer a shutter. The arcade cabinets are still not visible (fixable in wording).
  - With the box on, the picture returns to a plain wall, as the box asks.

## 2. WAI Vary (`wai-vary`, #1202, #1240)

**Parent:** WAI job `eaf24185-1518-4057-a806-8284487ef36d`, asset `4571765f`, 16.2 s elapsed on the worker (`elapsed_seconds` in its local `state.json`; the recipe-thumbs receipt records 17.9 s wall), from the recipe-thumbs baseline. It used the noirpopwave LoRA at 1.0, euler_ancestral, 24 steps, and an SFW fantasy cartographer prompt.

The route was: Asset library -> the picture -> Vary subtle or Vary strong -> Generate.

- **Subtle (denoise 0.5):** job `5a0b5775-be7a-475f-91cd-593235a3ee1c` made 2 pictures (seeds 1876502875-76; assets `bf577900` and `ad85495c`) in **69.7 s**.
  - The page kept the round to 2 because "No timing on this PC yet".
  - Host commit was 64.8 %.
- **Strong (denoise 0.7):** job `fe6462d2-bedf-44eb-84f9-b4478caa91e5` made 4 pictures (seeds 1015797779-82; assets `bf2172bd`, `fc31f3a7`, `e0997b42` and `6c152730`) in **77.6 s**.
  - The page chose 4 because it had a timing by then ("about 35 s per picture here").
  - Host commit was 73.8 %, with 3.0 GiB of physical memory free.
- **What carried into both jobs:** the parent's checkpoint, `lora_name` noirpopwave at 1, sampler and steps, and the parent asset, which is recorded in `parent_assets` and `continuation`. The graph denoise was 0.5 and 0.7. There were no page errors and no dialogs.
- **Graph check:** `python scripts/validate-live.py --preset wai-vary` gave PASS against primary's `/object_info` (schema SHA-256 65491c42…), with no submissions.
- **Catalog:** `wai-vary` is now `verified: true` with an `execution_note`. Its strengths stay `starting-value` until the owner judges them.
- **Sheet:** `vary-wai-sheet.jpg` shows the parent, then subtle, then strong.
- **Agent pre-review:**
  - Subtle stays close to the parent and keeps the style.
  - Strong moves further and keeps the style.

## Downloads: Qwen-Image 2.1 FP8 (#1028), stopped unfinished

Both downloads were stopped cleanly after the runs: the `dl.py` driver and its `curl` child were killed, and no curl process remains. The partial files were left in place so they can resume.

| File | Partial bytes | Full bytes | Expected SHA-256 |
| --- | --- | --- | --- |
| `C:/AI/experiments/qwen-image-21/ComfyUI/models/diffusion_models/Qwen-Image-2.1-FP8.safetensors.part` | 4,942,104,462 | 7,122,877,560 | `70e151cfbedd37de7f4a11bda8f58180965c85f4960584c3d10acff599fcd205` |
| `C:/AI/experiments/qwen-image-21/ComfyUI/models/text_encoders/Qwen-Image-2.1-text_encoder-FP8.safetensors.part` | 16,617,472 | 9,394,530,592 | `0a1e217ea5a327c77cf4c58ee2ec4b15dabdd55cc4ffa6d999085865e70db3df` |

To resume, run one command per file. Then verify the SHA-256 and rename the file to drop `.part`:

```bash
curl -L -C - --fail --retry 3 -o "C:/AI/experiments/qwen-image-21/ComfyUI/models/diffusion_models/Qwen-Image-2.1-FP8.safetensors.part" https://huggingface.co/unsloth/Qwen-Image-2.1-FP8/resolve/main/Qwen-Image-2.1-FP8.safetensors
curl -L -C - --fail --retry 3 -o "C:/AI/experiments/qwen-image-21/ComfyUI/models/text_encoders/Qwen-Image-2.1-text_encoder-FP8.safetensors.part" https://huggingface.co/unsloth/Qwen-Image-2.1-FP8/resolve/main/Qwen-Image-2.1-text_encoder-FP8.safetensors
```

The local driver `python C:/Users/jekyt/AppData/Local/Temp/qi21-dl/dl.py 3 4` does both steps: it resumes, verifies the SHA-256 and renames the files into place. Neither file is pinned in `models/library.json`.

## Not verified

- **Art quality of any picture.** The pre-reviews above are the agent's reading only.
- **Whether the wide band or the loosened look is what the owner wanted.**
- **The WAI Vary strengths as final values.**
- **A 3×3 check of the band on other textures.**
- **Any Vary on a WAI picture with two LoRAs or with no LoRA.**
- **The FP8 files:** they are incomplete, so they are not verified and not pinned.

## Files

- `tiles-floor-band-sheet.jpg`, `look-v2-sheet.jpg`, `vary-wai-sheet.jpg`: the sheets for the owner.
- `receipts/`: the page events, the prepared wording, host commit before each Generate, the job records (prompt IDs, seeds, assets and elapsed time) and the tile asset hashes.
- `scripts/`: the as-run page drivers, kept as receipts. They import a local `drive.py` helper and hardcode local paths.

**Receipt note (added at review, 27 Sep 2026):** `scripts/tiles3x3.py` is the earlier live-proofs driver and only builds the narrow-band wall/floor sheet. `tiles-floor-band-sheet.jpg` was put together ad hoc from the Studio's own 3×3 preview assets: narrow band `9f546d90` (the earlier floor run) and wide band `e84e7a97` (tile `a4158f9f`); see `receipts/tiles-assets.json`, and no script for it is committed. The `validate-live` pass for `wai-vary` was read from the console; no receipt is committed for it.
