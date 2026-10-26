# MOSS-Image: isolated backend on this PC

MOSS-Image (OpenMOSS, released 16 October 2026) is a 5B single-stream DiT with a Qwen3.5-9B text encoder and the FLUX.2 VAE (small decoder). It makes text-to-image from natural language, booru tags or a JSON layout. The **local `moss-t2i` workflow has no edit input or ControlNet**; its pose control is prompt wording and layout boxes. Community edit and color/depth adapters are now listed by [Comfy-Org](https://huggingface.co/Comfy-Org/MOSS-Image) (checked 26 October); they are not installed or proven by this local recipe. OpenMOSS weights and code are Apache-2.0; adapters have separate terms.

The primary ComfyUI here is v0.35.0 and has neither the model class nor the `moss_image` text encoder type (both arrived in ComfyUI v0.42.0). Upgrading the primary would upgrade the shared Torch/ROCm environment's ComfyUI packages, which this repository forbids, so MOSS runs on its own backend, as Qwen-Image 2.1 does ([QWEN-IMAGE-21.md](QWEN-IMAGE-21.md)).

## Layout (19 October 2026)

| Piece | Where | Identity |
| --- | --- | --- |
| ComfyUI checkout | `C:\AI\experiments\moss-image\ComfyUI` | tag `v0.42.1`, commit `63be2f9b82ad0dac88a7ceaa28a9cf3154125a18`, shallow clone, no custom nodes |
| Package overlay | `...\ComfyUI\python_packages` | `pip install --no-deps --target`: comfy-kitchen 0.2.39, comfy-aimdo 0.5.6, comfyui-frontend-package 1.55.18 (the three `requirements.txt` differences from v0.35.0 that matter; SHA-256 of the wheels in `C:\AI\experiments\moss-image\wheels\SHA256SUMS`) |
| Model paths | `...\ComfyUI\extra_model_paths.yaml` | points at the main library (`C:\AI\ComfyUI_windows_portable\ComfyUI\models`) so weights and LoRAs are not duplicated |
| Python and Torch | the portable `python_embeded` | shared, unchanged: torch 2.9.1+rocm7.2.1 |
| Launcher | `scripts/moss-launch.py` | overlay first on `sys.path`, `127.0.0.1:8198`, `--reserve-vram 2 --disable-pinned-memory` |
| Studio profile | `moss` in `app/backends.py` | *MOSS-Image - isolated*; readiness checks the overlay, a nonempty `extra_model_paths.yaml`, the MOSS encoder implementation and three library files (`app/backend_contracts.py`, `MOSS_FILES`) |
| Preset | `moss-t2i` | `workflows/api/moss-t2i-api.json`: UNETLoader, CLIPLoader type `moss_image`, VAELoader, two LoRA slots, EmptyFlux2LatentImage, KSampler |

When `enforce_host_commit_headroom` is enabled, every MOSS canvas requires 32 GiB of known host-commit headroom,
including the 832x1248 choice below 1 MP. Readiness checks file presence only: the contents of `extra_model_paths.yaml`,
node compatibility and inference still need their separate validation.

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

The MOSS backend and preset are on `main` (PR #1575). Start Studio from an up-to-date checkout (`python app/server.py --repo-root <checkout>`); an older running server needs a restart while idle to load the Python backend integration.

## Results (agent-judged, one 9070 XT, shared PC; see [the receipts](looks/lab-2026-10-19-moss.receipts.json) and [judgements](looks/lab-2026-10-19-moss.judgements.jsonl))

Scope: SFW adult characters, the same three briefs as the round-7 look lab (sorceress on a castle balcony, kimono on a stone bridge, knight on a battlefield), seed `2026101901` unless a seed is named, 1024x1536, euler / sgm_uniform, 30 steps, CFG 3, empty negative, one job at a time through the Studio. 70 jobs (55 for the backend evaluation, 10 for the trained-LoRA on/off test and 5 SFT steps-and-flagship runs), all completed, none failed or repeated, 70 receipts and 70 judgement rows (one per picture): 66 keep, 2 fixable, 1 reject, 1 skipped. The counts quoted in the tables below are per test and refer to the first 55 unless stated. Verdicts are agent judgements with the [rubric](quality/JUDGING-RUBRIC.md), configuration-aware, not art acceptance; one picture (Nanmokaken) was skipped as youthful-reading. Hands were judged at contact-sheet scale except the staff hand of the first proof (crop clean); the free hand is often long and thin.

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
| Reverse 1999 (0.9) | none used in this test | matte layered colour, mature faces; see the author's trigger guidance below |
| Re:Zero (0.9) | none | bright violet palette; face at the young-adult end |
| Chainsaw Man (0.8) | `chainsty` | flat shading, covered hooded robe |
| **Nanmokaken v0.5 (0.8)** | `@nanmokaken` | round-eyed moe style that **reads youthful: skipped, not scored** |

### What to watch

- **Close-ups drift photographic.** The same adult face brief that Anima rendered as anime came out as a photographic portrait (style score 2, reject for an anime brief). Fixes that worked: booru tags `anime coloring, flat color, cel shading, clean lineart, illustration` (best), the sentence "2D anime illustration with cel shading and clean lineart, not photorealistic", or a style adapter (Reverse 1999, mikkoani).
- **Necklines and thighs.** "High collar" and "covered" were not always obeyed; the 4-step sorceress added lace and the 2K sorceress a garter strap. There is a negative field, but the model card advises a short or empty negative, so put the coverage words in the positive and re-roll.
- **Free hand.** The hand not holding a prop is often long and thin at contact scale; crop before keeping.
- **Memory.** The cold load and the 2K size are the expensive moments; the Studio's commit gate still applies.

The Studio's timed idle cache release currently runs only on the **primary** backend.
Changing its timer does not release an isolated MOSS cache. During the 26 October
study, a six-stage adapter batch left only 1–4 GiB of available physical RAM even
with ample commit headroom. After verifying every Studio job completed and the
ComfyUI queue was empty, cycling only the exactly identified, study-owned MOSS
process restored about 18–19 GiB before the next batch. Keep prompt IDs and
receipts; do not cycle a process with active, partial or uncertain work, and do not
assume a process belongs to Studio merely because it listens on 8198.

### Author guidance refreshed 26 October 2026

These are source recommendations, separate from the 19 October measurements above:

- [Reverse 1999 author metadata](https://civitai.com/api/v1/models/3005908): trigger **`reversesty`**, strength **1.0–1.4**, er_sde, CFG 5, 30 steps. The author reports only a few generations and warns that anime, realistic and lighting words change the effect. The earlier local test used 0.9 without the trigger; it did not test the author's full recipe.
- [mikkoani author metadata](https://civitai.com/api/v1/models/2470371): the MOSS version was trained on Base and tried by its author on SFT with an 8-step adapter. A fixed MOSS trigger is not specified. This is a compatibility claim, not a multi-seed local quality result.
- [Impasto author metadata](https://civitai.com/api/v1/models/2230912): start at 0.8, range 0.6–1.0. The hazy painterly finish intentionally softens contrast. Adding a small amount to another style is a separate experiment, not an author-validated combination.

The [26 October frozen study](../experiments/curated/moss-study-20261026/plan.json) holds prompt, seed, dimensions and sampling fixed while testing the Reverse trigger, its strength, and a mikkoani/Impasto pair. Its plan is not a result; completed receipts and visual judgements are recorded separately.

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
4. The Studio's runtime recovery can relaunch the main ComfyUI while an isolated backend is active. It happened here because a second, preview Studio (another agent, on another port, with its own recovery enabled) started the main ComfyUI four times during the session (08:50, 08:51, 10:01 and 10:03 local); any such start competes for the GPU and memory with a running MOSS job. Run a preview Studio with runtime recovery disabled, and check `/api/backends` (`online`) before assuming the GPU belongs to one family.


## LoRA training on this AMD PC: it works (19 October 2026)

kohya `sd-scripts` (dev, commit `04ca541`, 18 October) trains MOSS-Image LoRAs with `moss_image_train_network.py` from the ComfyUI int8 ConvRot **Base** file and the int8 text encoder, on the RX 9070 XT with the shared torch 2.9.1+rocm7.2.1 and no Triton. It is a separate environment, never the shared runtime: `C:\AI\experiments\moss-train` holds the clone, an overlay of pure-Python packages (`accelerate` 1.15.0, `diffusers` 0.40.0, `huggingface-hub` 1.32.0, `voluptuous`, `imagesize`, the optimizer packages) installed with `pip --no-deps --target python_packages`, and `run_train.py`, which puts the overlay first on `sys.path` and runs the script on the portable Python. The Base int8 file (SHA-256 `f601c1e1...d8e6f`, matches the Hugging Face LFS id) lives on `E:\moss-image-base\`.

**Three fixes the box needed** (all inside the overlay or the launcher, nothing in the shared runtime):

1. This Windows ROCm torch has no `torch.distributed` backend. `accelerate.utils.other.model_has_dtensor` raised `ModuleNotFoundError`; the overlay copy returns `False` when DTensor cannot be imported. `accelerate.state.destroy_process_group` raised `AttributeError: torch.distributed has no attribute is_initialized` after the last step; the overlay copy guards it with `hasattr`. (The final LoRA is saved before that line, so the crash costs nothing, but patch it for a clean exit.)
2. `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8` are required: the trainer prints Japanese strings and the Windows console code page raised `UnicodeEncodeError`.
3. The embedded Python ignores `PYTHONPATH`, so `run_train.py` inserts the overlay and the clone itself.

**Measured.** A 4-step smoke (10 pictures) ran about 20 s/it on the first steps (warm-up) and saved a 149 MB LoRA; the real run, **136 steps on 34 pictures (rank 16, alpha 16, 252 DiT modules, 768x1152 buckets, AdamW 1e-4 constant, bf16, gradient checkpointing, latents and text-encoder outputs cached to disk, batch 1, seed 2026101901), took 10 min 13 s (about 4.5 s/it), mean loss 0.39**, and saved `moss_anima_cel_v1.safetensors` (148,729,296 bytes, SHA-256 `7fdf6209...3afe`). The command (`C:\AI\experiments\moss-train	rain_cel.sh`):

```
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
python run_train.py moss_image_train_network.py  --pretrained_model_name_or_path=E:/moss-image-base/moss_image_base_int8_convrot.safetensors  --text_encoder=<models>/text_encoders/qwen3.5_9b_int8_convrot.safetensors --vae=<models>/vae/flux2-vae.safetensors  --dataset_config=anima-cel.toml --output_dir=out --output_name=moss_anima_cel_v1 --save_model_as=safetensors  --network_module=networks.lora_generic --network_dim=16 --network_alpha=16 --network_train_unet_only  --learning_rate=1e-4 --optimizer_type=AdamW --lr_scheduler=constant  --timestep_sampling=sigma --weighting_scheme=logit_normal --logit_mean=-1.09 --logit_std=0.95 --discrete_flow_shift=1.0  --max_train_epochs=1 --save_every_n_steps=68 --mixed_precision=bf16 --gradient_checkpointing  --cache_latents --cache_latents_to_disk --cache_text_encoder_outputs --cache_text_encoder_outputs_to_disk  --max_data_loader_n_workers=2 --seed=2026101901
```

Do not use `AdamW8bit` (bitsandbytes does not run here). Training blocks the GPU: stop the Studio's queue first and `/free` the running ComfyUI. Keep only the final LoRA (149 MB); intermediate checkpoints are the same size.

**The dataset and what it taught.** 34 adult, SFW pictures from this lab (costumes, kimono, knight from the Pearly and One Obsession Anima mixes, all judged keep), each captioned with its own prompt preceded by `anime illustration, flat cel shading, clean lineart.`, to cure MOSS's tendency to render close-ups photographic. These are model outputs, so a LoRA from them carries those models' terms (Anima non-commercial); it is a technique test, not a distributable adapter. Result on MOSS SFT int8 (same seed, LoRA off / 0.6 / 1.0, [receipts](looks/lab-2026-10-19-moss.receipts.json)): **the LoRA loads and changes every picture**, but **the caption prefix did most of the work**: with the prefix and no LoRA the adult close-up that had come out photographic was already a clean anime face; with the LoRA and **without** the prefix it was still semi-photographic (style 3). The LoRA adds flatter shading, crisper lines and stronger colour (on the kimono scene it turned the bridge red-lacquer), and it changes the composition for a fixed seed. So: write the prefix first; the LoRA is a modest extra push, not a cure.

The trained LoRA is `loras/moss-lab-anima-cel-v1.safetensors` in the main library (private experiment, not pinned in `models/library.json`).


## Kromoss (lodestones, 19 October 2026): not proven here

Kromoss is a full fine-tune of MOSS-Image **Base** by the Chroma author (Apache-2.0, 1024 px, aimed at Base's blur), a drop-in for the SFT diffusion model with the same Qwen3.5-9B encoder and small VAE; the card's settings are euler, 50 steps, CFG 3, `uncond_skip_layers=[22]` (not implemented in ComfyUI v0.42.1's MOSS code, so not applied here), or 8 steps, CFG 1, euler / simple with `8-steps-dmd-lora.safetensors`. At the moment of the owner's request the download of `diffusion_models/kromoss_int8_convrot.safetensors` (5,413,711,632 bytes) was started at about 1 MB/s and **stopped at 3,417,003,886 bytes (63 %)** when the owner asked to stop; the 1.19 GB DMD LoRA was not started. So nothing about Kromoss is verified: it was **not loaded**, no picture was made, no timing or SHA-256 exists, and whether the DMD LoRA loads on an int8 file and whether the cel-anime LoRA loads on a Base fine-tune are untested. The partial file is `models/diffusion_models/kromoss_int8_convrot.safetensors.part`; resume with `python scripts/fetch-hf.py --repo lodestones/Kromoss --path diffusion_models/kromoss_int8_convrot.safetensors --dest-folder diffusion_models --name kromoss_int8_convrot.safetensors --resume`. A draft `kromoss-t2i` preset (a copy of `moss-t2i` with the diffusion file swapped) and a same-seed A/B queue of 16 jobs against the SFT pictures already in the receipts (kimono, knight, sorceress, a flagship brief, 30 and 50 steps, the DMD 8-step LoRA, the cel LoRA) are kept in the ignored `.runtime/lab-20261019/` and were not committed.

The SFT side of that A/B exists in the receipts: 50-step runs tie the 30-step ones on the three briefs and the flagship brief ("ultra high-end anime key visual ... swordmaster ..."), the SFT 4-step adapter renders the flagship brief in 44 s.

### 26 October refresh: DMD2 verified on disk; checkpoint comparison not run

The [current card](https://huggingface.co/lodestones/Kromoss) now describes update
11000 and `8-steps-dmd2-lora.safetensors`. The source revision used for this study
is `a4fe97449297af2e3be7841e1c18e431f3b06031`. Its diffusion file is a different
identity from the 19 October partial above, so that historical partial was
preserved and a fresh target was used.

- `diffusion_models/kromoss-u11000-int8-convrot.safetensors`: expected
  5,413,698,958 bytes, SHA-256
  `cacff0dd25cd2cf531e1f5ddae7872c3d57a54dbf66f1a1279f2f118514e7905`.
  Three transfers ended short; the latest `.part` retains 2,587,306,298 bytes.
  **Not installed, not loaded, no Kromoss generation submitted.**
- `loras/kromoss-u11000-8steps-dmd2.safetensors`: downloaded and verified against
  the source LFS hash, 1,189,176,800 bytes, SHA-256
  `7683fe1fb51f73f5d690f24dd6b7f46f31ab9a9873729a854ac5c9a420ffe6f2`.
  This proves file identity, not compatibility or quality. The author's recipe is
  8 steps, CFG 1, Euler / simple, strength 1.

The new `kromoss-t2i` preset stays **unverified**. Its graph reuses the MOSS backend,
encoder, small VAE and two adapter slots; the model choice has its own pinned
filename. The [saved eight-image plan](../experiments/curated/moss-study-20261026/kromoss-plan.json)
is explicitly NOT RUN. [Issue #1662](https://github.com/Chris0Jeky/local-asset-studio/issues/1662)
holds the external transfer dependency. After a stable transfer is available,
resume only the current partial with the exact revision and target:

```console
python scripts/fetch-hf.py --repo lodestones/Kromoss --revision a4fe97449297af2e3be7841e1c18e431f3b06031 --path diffusion_models/kromoss_int8_convrot.safetensors --dest-folder diffusion_models --name kromoss-u11000-int8-convrot.safetensors --resume
```

That command is a future bounded transfer attempt, not an automatic retry in this
wave. Require complete size/hash verification and a live schema check before
starting the saved comparison; do not resume the old partial against moving `main`.

## Second training run: stopped, not verified

A 408-step, 3-epoch run (learning rate 1.5e-4) on the same 34 pictures was started to see whether a stronger LoRA cures the photographic drift by itself; it ran at about 5 s/it and was **stopped at step 121 of 408** (loss 0.395) when the owner asked to stop. Nothing was saved (the first checkpoint was due at step 200). The first run's result above stands: trained, loaded, changes pictures, prefix does most of the work.
