# Qwen-Image 2.1: isolated backend on this PC

Qwen-Image 2.1 (released 20 September 2026) is one 7B checkpoint for text to image, instruction edits with up
to ten reference pictures, and **native RGBA**: the decoder has four output channels, so a transparent sprite
comes straight out of the model with no background removal. Issue #739.

The primary ComfyUI here is v0.35.0 (9 September 2026) and has no Qwen-Image 2.1 model class; support landed
upstream in `6bfaacc6` (19 September) and ships in v0.37.0. Upgrading the primary would upgrade the shared
Torch/ROCm environment's ComfyUI packages, which this repository forbids, so 2.1 runs on its own backend.

## Layout (22 September 2026)

| Piece | Where | Identity |
| --- | --- | --- |
| ComfyUI checkout | `C:\AI\experiments\qwen-image-21\ComfyUI` | tag `v0.37.0`, commit `73c9bad4d21e7addbe1d13bc92eee0f1431b017d`, shallow clone, no custom nodes |
| Package overlay | `…\ComfyUI\python_packages` | `pip install --no-deps --target`: comfy-kitchen 0.2.35, comfy-aimdo 0.5.5, comfyui-frontend-package 1.52.7; wheel SHA-256 in `C:\AI\experiments\qwen-image-21\wheels\SHA256SUMS` |
| Python and Torch | the portable `python_embeded` | shared, unchanged: Python 3.12.10, torch 2.9.1+rocm7.2.1, transformers 5.15.1 |
| Launcher | `scripts/qwen21-launch.py` | puts the overlay first on `sys.path`, listens on `127.0.0.1:8196`, `--reserve-vram 3 --disable-fast-disk --disable-pinned-memory` (every *Speed* row below ran through this launcher, so pinned memory was off in all of them) |
| Studio profile | `qwen21` in `app/backends.py` | *Qwen-Image 2.1 · isolated*; readiness checks the overlay and the three pack files (`app/backend_contracts.py`) |
| Weights | `…\ComfyUI\models\{diffusion_models,text_encoders,vae}` | Comfy-Org pack at revision `5dc5850e`, pinned in `models/library.json` |

The three packages the overlay carries are the only `requirements.txt` differences between v0.35.0 and v0.37.0
that affect inference (the other two, workflow templates and embedded docs, only change the ComfyUI browser page
and are left at the shared versions; the server logs a warning about them). The overlay's comfy-kitchen wheel
ships the HIP backend, so int8 matmuls run on the RX 9070 XT (gfx1201) as they do for TRELLIS.2 and H3 on the
primary. Triton is absent in both runtimes.

Weights (`int8_convrot` diffusion 7,256,783,064 bytes; Qwen3-VL 8B `int8_convrot` text encoder 9,350,798,360
bytes; bf16 RGBA VAE 675,509,688 bytes) were fetched with resumable `curl` from the pinned revision and each
SHA-256 compared with the Hugging Face LFS object ID. The bf16 diffusion file (14.2 GB), the w4a8 and bf16
text encoders and the two Qwen3.5 9B prompt-enhancer files were not downloaded.

## Licence

Qwen Research License Agreement, release date 20 September 2026: **non-commercial research or evaluation
only**; commercial use needs a separate licence from Qwen. Recorded from the model card's `LICENSE` on
22 September 2026, not legal advice. The recipes say *private experiments only*.

## Recipes

Built by `scripts/build-qwen21-recipes.py` from Comfy-Org's day-0 templates (`image_qwen_image_2_1_t2i`,
`image_qwen_image_2_1_image_edit`), flattened out of their subgraphs: 25 steps, CFG 1, euler / simple.

- **Qwen-Image 2.1 - Text to Image** (`qwen21-t2i`): a written brief; 832 × 1248 default, native 2K sizes as
  variants.
- **Qwen-Image 2.1 - Transparent sprite (RGBA)** (`qwen21-rgba`): your subject wrapped in the model card's
  transparent-image wording (*This is an RGBA image with transparency. … The image has alpha channel and the
  background is transparent.*); the PNG keeps the alpha channel.
- **Qwen-Image 2.1 - Edit one picture** (`qwen21-edit`): one picture plus an instruction; the output keeps the
  picture's aspect ratio at about 1 MP.

## Use it in Studio

Choose **Qwen-Image 2.1 · isolated** in the environment selector and press **Switch environment**. As with
HiDream, the Studio refuses while any queue is busy, stops only the exact idle configured process, and starts
this launcher. Return to **Main library** for every other family. Do not run both families on the GPU at once.

## Speed

Measured on 22-23 September 2026 by `experiments/curated/qwen-image-21-20260922/bench.py`: 832 × 1248, 8 steps, one cold
run and one warm run per launch configuration. The prompt IDs are in `bench.json`.

| Launch flags | Cold run | Warm run | Last s/step |
| --- | --- | --- | --- |
| v0.37 defaults, `--reserve-vram 0.6` | 313.6 s | 248.9 s | 17.7 |
| `--disable-fast-disk` | 217.4 s | 202.5 s | 12.5 |
| `--disable-fast-disk --disable-dynamic-vram` | 270.7 s | 226.8 s | 13.9 |
| **`--disable-fast-disk --reserve-vram 3`** (the launcher's setting) | **64.5-66.2 s** | 72.4 s | **0.68-1.0** |

With a 0.6 reserve, ComfyUI does not count the VRAM that other processes hold, so the 7B model spills into
shared memory and every step pages weights across PCIe (`docs/RUNTIME-PRECONDITIONS.md` section 8). A 3 GiB
reserve makes ComfyUI evict the text encoder before sampling, and the diffusion model then fits.

Host commit headroom fell to 2.1-6.5 GB during these runs, because the int8 text encoder alone is 9.35 GB. Start a
Qwen-Image 2.1 job only with at least 32 GiB of commit headroom, the same gate as the other large routes.
The 25-step default recipe took 686.6 s wall before this launcher change (prompt `a259a112`, `research.json`).
*Re-timed 23 September 2026:* 52.9 s through the Studio at the new setting (see *Studio proofs* below).

## Studio proofs (23 September 2026)

After #863 and #870 fixed the two things that had blocked every backend switch on this PC (a stopped-tracking record
counted as live work; Windows answering a closed loopback port only after about 2.05 s, past the 2 s probe), the
Studio switched from the primary to *Qwen-Image 2.1 · isolated* in about 40 s and back in about 40 s. Each recipe then
ran once through `POST /api/jobs` (`experiments/curated/qwen-image-21-20260922/prove_studio.py`; `prove_studio.json` and
the exported `recipe-<preset>.json` beside it), seed 2026092211, 25 steps, commit-headroom gate enforced:

| Recipe | Job / prompt | Time | Peak GPU (dedicated / shared) | Result (agent-inspected) |
| --- | --- | --- | --- | --- |
| `qwen21-t2i`, 832 × 1248 | `be94bd02` / `457eabb0` | 52.9 s | 14.4 / 3.0 GB (cold load) | the brief as written: adult sorceress, lit brass lantern, rainy bridge, blue hour |
| `qwen21-rgba`, 1024² | `b377572d` / `b0297f2a` | 28.2 s | 13.3 / 0.4 GB | potion icon with native alpha, no halo; *fixable* per the blind second judge (#877): alpha dust (1-31) over the background and a 1-12 % see-through body; threshold alpha before packing |
| `qwen21-edit`, 1024² | `dc8f18f8` / `027b8a22` | 78.6 s | 13.2 / 2.7 GB | the lantern cutout kept in shape and colour, redrawn with ink outlines and cel shading |

All three recipes are now `verified: true` (the route runs and returns the intended kind of output). The t2i and edit
PNGs are saved as RGBA with faint partial alpha on part of the frame; strip or threshold alpha before any step that
crops or packs by alpha. Generated and agent-inspected only: not art acceptance, and the Qwen
Research License keeps them non-commercial. Still open under #739: a 2048² text-to-image run, a 3-6 reference identity
edit, a text-heavy prompt, the LoRA status (the downloaded 2.1 Fix LoRA is untested), and a VRAM-arbitration note for
running beside a local LLM or Spoken Briefs.
