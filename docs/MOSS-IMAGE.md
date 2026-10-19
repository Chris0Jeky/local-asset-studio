# MOSS-Image: isolated backend on this PC

MOSS-Image (OpenMOSS, released 16 October 2026) is a 5B single-stream DiT with a Qwen3.5-9B text encoder and the FLUX.2 VAE (small decoder). It makes text-to-image from natural language, booru tags or a JSON layout. This release has **no edit input and no ControlNet**; pose control is layout boxes only. Weights and code are Apache-2.0.

The primary ComfyUI here is v0.35.0 and has neither the model class nor the `moss_image` text encoder type (both arrived in ComfyUI v0.42.0). Upgrading the primary would upgrade the shared Torch/ROCm environment's ComfyUI packages, which this repository forbids, so MOSS runs on its own backend, as Qwen-Image 2.1 does ([QWEN-IMAGE-21.md](QWEN-IMAGE-21.md)).

## Layout (19 October 2026)

| Piece | Where | Identity |
| --- | --- | --- |
| ComfyUI checkout | `C:\AI\experiments\moss-image\ComfyUI` | tag `v0.42.1`, commit `63be2f9b82ad0dac88a7ceaa28a9cf3154125a18`, shallow clone, no custom nodes |
| Package overlay | `...\ComfyUI\python_packages` | `pip install --no-deps --target`: comfy-kitchen 0.2.39, comfy-aimdo 0.5.6, comfyui-frontend-package 1.55.18 (the three `requirements.txt` differences from v0.35.0 that matter; SHA-256 of the wheels in `C:\AI\experiments\moss-image\wheels\SHA256SUMS`) |
| Model paths | `...\ComfyUI\extra_model_paths.yaml` | points at the main library (`C:\AI\ComfyUI_windows_portable\ComfyUI\models`) so weights and LoRAs are not duplicated |
| Python and Torch | the portable `python_embeded` | shared, unchanged: torch 2.9.1+rocm7.2.1 |
| Launcher | `scripts/moss-launch.py` | overlay first on `sys.path`, `127.0.0.1:8198`, `--reserve-vram 2 --disable-pinned-memory` |
| Studio profile | `moss` in `app/backends.py` | *MOSS-Image - isolated*; readiness checks the overlay and three library files (`app/backend_contracts.py`, `MOSS_FILES`) |
| Preset | `moss-t2i` | `workflows/api/moss-t2i-api.json`: UNETLoader, CLIPLoader type `moss_image`, VAELoader, two LoRA slots, EmptyFlux2LatentImage, KSampler |

## Weights (all verified against the Hugging Face LFS SHA-256)

Source: `Comfy-Org/MOSS-Image` at revision `3284a1dbb351e3396d70f39f2a71cbf6ed2ef1bb`; pins in `models/library.json`.

| File | Bytes | Role |
| --- | ---: | --- |
| `diffusion_models/moss_image_sft_int8_convrot.safetensors` | 5,413,698,958 | SFT, for generation |
| `text_encoders/qwen3.5_9b_int8_convrot.safetensors` | 9,748,121,532 | text encoder |
| `vae/moss_image_flux2-vae_small.safetensors` | 249,521,340 | decoder (the `flux2-vae_small` file, renamed so it cannot be mistaken for the full FLUX.2 VAE already in the library) |
| `loras/moss_image_sft_4step_lora_v2.safetensors` | 327,078,952 | 4-step distillation adapter (Kijai experimental; no licence stated) |
| `loras/moss-*.safetensors` (seven) | 62-145 MB each | civitai style adapters, flags recorded per file |

MOSS-Image-**Base** int8 (5.41 GB) is for LoRA training research only (SFT is the generation checkpoint); it is stored on `E:\moss-image-base\` to keep C: free and is not in the library. The bf16 DiT (10.2 GB) and bf16 text encoder (19.3 GB) were not fetched. Speed of the downloads here was about 1.4-2 MB/s, so plan an evening, not minutes.

## Does int8 ConvRot work on this GPU? Yes.

The three open reports before the first run were a black image for int8 ConvRot on gfx1201 (ComfyUI #15084), very slow int8 loads (kitchen #188) and no MOSS-on-AMD report. On the RX 9070 XT (torch 2.9.1+rocm7.2.1, comfy-kitchen 0.2.39 HIP backend) the first job, 1024x1536, 30 steps, finished in **123.5 s cold** with a normal picture: no black or NaN output, no spill, host commit peak 63-76 % while the other agents were running. Warm timings and the full test set below.

## How to run it

1. Wait until the Studio queue is empty (no queued, running or partial work).
2. In the Studio's environment selector choose **MOSS-Image - isolated** and press **Switch environment** (or `POST /api/backends/switch {"id":"moss"}`). It stops the main ComfyUI and starts the launcher; about 50 s.
3. Make or run the `moss-t2i` preset. Return to **Main library** for every other family. Do not run two families on the GPU at once.

Until this branch is merged, the Studio must be started from this branch for the profile to exist (`python app/server.py --repo-root <checkout>`).

## Results (agent-judged, one 9070 XT, shared PC; see [the receipts](looks/lab-2026-10-19-moss.receipts.json) and [judgements](looks/lab-2026-10-19-moss.judgements.jsonl))

Scope: SFW adult characters, the same three briefs as the round-7 look lab (sorceress on a castle balcony, kimono on a stone bridge, knight on a battlefield), seed `2026101901` unless a seed is named, 1024x1536, euler / sgm_uniform, 30 steps, CFG 3, empty negative, one job at a time through the Studio. 55 jobs, all completed, none failed or repeated, 55 receipts and 55 judgement rows (one per picture): 52 keep, 1 fixable, 1 reject, 1 skipped. Verdicts are agent judgements with the [rubric](quality/JUDGING-RUBRIC.md), configuration-aware, not art acceptance; one picture (Nanmokaken) was skipped as youthful-reading. Hands were judged at contact-sheet scale except the staff hand of the first proof (crop clean); the free hand is often long and thin.

### Speed (Studio job seconds, shared PC)

| Job | Seconds |
| --- | ---: |
| first job after the switch (cold load, 30 steps) | 124 |
| 30 steps, warm | 53-106, median about 75 (53-57 on a quiet machine) |
| 20 steps / 50 steps | 44 / 79 |
| 4-step adapter at CFG 1 (4 / 8 steps) | 28-59 / 33 |
| 832x1248, 30 steps | 63 |
| 1536x2048 (3.1 MP), 30 steps | 166 and a host-commit peak of **90.9 %** |

For comparison on the same PC (round 7): Anima mixes 20-50 s, Krea 2 GGUF 262-331 s. 1024x1536 needs no care at 55-75 % commit; do the 2K size last, after a `/free`.

### What held

| Test | Result |
| --- | --- |
| Three scenes x three seeds (seed ...01 plus two more) | 9 of 9 keep: cranes, umbrella, bridge, plate armour, scar, longsword, crystal staff all present |
| Steps 20 / 30 / 50 | tie; 20 steps is enough |
| CFG 2 / 3 / 4 / 6 | tie, no burn at 6 |
| Samplers `er_sde`, `euler_ancestral`; scheduler `simple` | all clean; composition changes a little with the sampler |
| 832x1248 | tie |
| Prompt kinds | natural-language paragraph, booru tags with a quality head, and tags plus sentences all worked |
| **JSON layout** | followed: the character, staff and castle boxes of the sorceress and the character, umbrella and bridge boxes of the kimono scene were placed where drawn |
| **Text in the picture** | "MOON TEA HOUSE" on a signboard and the kanji 月茶屋 on a lantern both came out correct (1024x1024) |
| **4-step adapter** `moss_image_sft_4step_lora_v2` at 1.0, CFG 1, euler / simple, 4 or 8 steps | a clean bright render on all three scenes; its own look is cleaner and lighter than the 30-step one; works with `sgm_uniform` too |
| Ten costumes (maid, office suit, hanfu, techwear, witch, priestess, pirate, samurai, winter coat, ballroom gown) | 9 keep, 1 fixable (techwear: face small and dark in the rain; add framing words). Held props present; fabric and jewellery detail is the richest of the SDXL/Anima families; the winter-coat brief came out full body where the Anima mixes cropped it |

JSON layout recipe (the Studio's positive text is simply this string): `{"summary":{"caption":"..."},"items":[{"label":"character","caption":"...","bbox":[y0,x0,y1,x1]},{"label":"object",...}],"bbox_coord_space":"abs_centralized","bbox_format":"yxyx"}`. Boxes are pixels with the origin at the canvas centre: `y0 = top_px - height/2`, `x0 = left_px - width/2`, and so on. The core node *MOSS-Image Layout Prompt* builds the same string; compact separators (`,` and `:`) were used here. `label` is `character`, `object` or `text` (a `text` item also takes `text`).

### Adapters (civitai, one picture each on the sorceress brief, strength 0.8-1.0)

| Adapter | Trigger | Result |
| --- | --- | --- |
| Anireal v1.0 (0.9) | none | softer, more realistic proportions; photographic 2.5D on the kimono scene |
| mikkoani (1.0) | none | bold 90s ink lines, darker palette |
| Impasto 2.5D v0.8-beta (0.8) | none | painterly texture, fewer lines |
| Reverse 1999 (0.9) | none | matte layered colour, mature faces |
| Re:Zero (0.9) | none | bright violet palette; face at the young-adult end |
| Chainsaw Man (0.8) | `chainsty` | flat shading, covered hooded robe |
| **Nanmokaken v0.5 (0.8)** | `@nanmokaken` | round-eyed moe style that **reads youthful: skipped, not scored** |

### What to watch

- **Close-ups drift photographic.** The same adult face brief that Anima rendered as anime came out as a photographic portrait (style score 2, reject for an anime brief). Fixes that worked: booru tags `anime coloring, flat color, cel shading, clean lineart, illustration` (best), the sentence "2D anime illustration with cel shading and clean lineart, not photorealistic", or a style adapter (Reverse 1999, mikkoani).
- **Necklines and thighs.** "High collar" and "covered" were not always obeyed; the 4-step sorceress added lace and the 2K sorceress a garter strap. There is a negative field, but the model card advises a short or empty negative, so put the coverage words in the positive and re-roll.
- **Free hand.** The hand not holding a prop is often long and thin at contact scale; crop before keeping.
- **Memory.** The cold load and the 2K size are the expensive moments; the Studio's commit gate still applies.

### Against the current best looks (same briefs)

| | Pearly Anima mix | Krea 2 GGUF + Niji Sweet Spot | MOSS-Image SFT int8 |
| --- | --- | --- | --- |
| Finish | clean cel anime | richest painted anime | detailed painted illustration, semi-real shading |
| Adult close-up | reads youthful | reads mature | mature, but photographic unless told |
| Layout / text | no | no | boxes and lettering work |
| Edit / pose input | via Klein routes | none | none |
| Seconds per picture | 20-50 | 262-331 | 53-106 |
| Tested keep rate | 12 of 12 | 9 of 11 (painted trigger text) | 9 of 9 on three scenes x three seeds, 9 of 10 costumes |

This is a comparison of tested briefs, not a taste ranking; the finishes are different on purpose.

### Not done / open

- **LoRA training.** kohya `sd-scripts` has `moss_image_train_network.py`; the plan, the unverified ROCm questions and the result are in the section below.
- MOSS-Image-Base generation was not tried; the int8 Base file (E:) is for training only.
- No second judge, no hand crops on the full-body pictures, no owner acceptance, no licence clearance for the third-party style adapters (civitai flags are recorded in `models/library.json`, and Chainsaw Man, Re:Zero and Reverse 1999 imitate third-party works).
- The community edit route (`ostris/ComfyUI-MOSS-Image-Ostris-Edit` plus ai-toolkit edit LoRAs) was not installed: it is third-party node code.

### Mistakes met on the way (so they are not repeated)

1. A test fixture wrote `inert fixture` into the real `C:\AI\experiments\moss-image\ComfyUI\main.py` because the new profile's default path pointed at the real checkout. The fixtures in `tests/test_backend_safety.py` and `tests/test_jobs_snapshot.py` now pass a temporary `moss_root`; restore with `git checkout main.py` in that checkout if it ever recurs.
2. The download script had no retry and silently stopped at 05:17 with 3 GB of the text encoder done; resume with `scripts/fetch-hf.py --resume`.
3. `1536x2048` was rejected until it was added to the preset's authored resolution pairs; the Studio accepts only authored pairs.
4. The Studio's runtime recovery can relaunch the main ComfyUI while an isolated backend is active; check `/api/backends` (`online`) before assuming the GPU belongs to one family.


## LoRA training on this AMD PC (status at 09:30, 19 October 2026)

kohya `sd-scripts` (dev, commit `04ca541`, 18 October) trains MOSS-Image LoRAs with `moss_image_train_network.py` from the ComfyUI int8 ConvRot Base file and text encoder. It is a separate environment, never the shared runtime: `C:\AI\experiments\moss-train` holds the clone, an overlay of pure-Python packages (`accelerate` 1.15.0, `diffusers` 0.40.0, `huggingface-hub`, `voluptuous`, `imagesize`, the optimizers) installed with `pip --no-deps --target`, and `run_train.py`, which puts the overlay first on `sys.path` and runs the script on the portable Python (torch 2.9.1+rocm7.2.1 unchanged). The Base int8 file lives on `E:\moss-image-base\` (SHA-256 `f601c1e1...d8e6f` matches the Hugging Face LFS id).

What was needed to get as far as model load on this box, in order:

1. The Windows ROCm torch has no `torch.distributed` backend, so `accelerate.utils.other.model_has_dtensor` raised `ModuleNotFoundError`; the overlay copy now returns `False` when DTensor cannot be imported (an overlay edit, not a change to the shared runtime).
2. `PYTHONUTF8=1` is required: the trainer prints Japanese strings and the Windows console code page raised `UnicodeEncodeError`.
3. The embedded Python ignores `PYTHONPATH`, so the overlay is put on `sys.path` from `run_train.py`.

Dataset for the first smoke test: ten Krea 2 + Niji Sweet Spot pictures from this lab (those without the painted trigger text), captioned with their own prompts plus `krea niji style.`; 768x1152 buckets, rank 16, AdamW, constant 1e-4, bf16, gradient checkpointing, latents and text-encoder outputs cached to disk. These are model outputs, so any LoRA from them carries the Krea Community Licence terms and the Niji adapter's own terms; it is a technique test, not a distributable adapter.

The smoke run passed latent caching, text-encoder caching and LoRA creation (252 DiT modules) and is loading the int8 Base. Results (seconds per step, VRAM, whether the ConvRot int8 backward runs without Triton on gfx1201, a working LoRA or not) are appended here when they exist; until then training on this PC is **unverified**.
