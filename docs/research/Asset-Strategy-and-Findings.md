> Migrated research snapshot from 11 September 2026. Use [Start here](../START-HERE.md) and [current state](../../CURRENT_STATE.md) for the new repository. Original workspace commands below are historical.

> Current broad-use workflow catalogue and newer model findings: see Workflow-Library-and-Strategy.md. Exact per-workflow runs: Workflow-Verification.json.

# Local asset studio: strategy and findings

Updated 11 September 2026. This document extends the earlier Game-and-Product-Asset-Pipeline report with a working production example and a larger-model experiment. See Expansion-Status.md for the final installation and test state of the new models.

## Recommendation

Use FLUX Klein 4B for rapid ideas and straightforward reference edits, Blender for anything whose shape must remain consistent, and deterministic image tools for delivery. Keep SDXL for its established control/LoRA ecosystem. Evaluate Z-Image Turbo as the photography-oriented alternative and Qwen Image Edit 20B Q4 as the slower specialist for difficult edits.

The useful target is an approved asset family that can be regenerated and integrated. Model parameter count alone does not measure that. A successful render also does not prove an image satisfies the brief.

## Current machine and demonstrated baseline

RX 9070 XT with 16GB VRAM; i5-13600K; approximately 32GB system RAM. About 168GiB disk space and 14GiB available RAM were observed before this expansion. ComfyUI uses the official Windows AMD portable runtime, Python 3.12 and PyTorch 2.9.1 / ROCm 7.2.1. No NVIDIA-only acceleration was added.

| Operation | Observed server execution | Finding |
|---|---:|---|
| SDXL 1024², 25 steps, initial load | 20.05s | Useful illustration/concept baseline |
| SDXL, new seed with cached model/prompt | 10.46s | Comfortable iterative use |
| FLUX Klein 4B 1024², 4 steps, initial load | 48.39s | Model/text encoder loading matters |
| FLUX, new seed with cached model/prompt | 4.01s | Fast sampling after loading |
| FLUX reference edit, purple lantern | 12.27s | Recolour succeeded visually |

These are individual observations, not statistical benchmarks. Cached-prompt runs are not the cost of entering a new prompt. Timing includes server execution but excludes browser interaction; no peak-VRAM telemetry was recorded for those original tests.

All original selected core and Krita support downloads completed. Krita's fresh startup log now lists SD XL and Flux 2 Klein 4B as supported workloads. Native UI capture failed with “foreground window did not report a process id”, so interactive Krita generation remains unverified. This is a tooling limitation, not evidence of model failure.

## The completed example: Lanternkeeper

Open the local preview at http://127.0.0.1:8190 while its server is running. The Lanternkeeper folder contains the complete package and its own README.

The brief: a warm, mysterious forest exploration game with reusable lantern pickups, plus a matching promotional page. Moss, amethyst and ember materials share brass construction and an amber core.

The pipeline produced an editable Blender scene, three animated GLBs, 96 transparent sprite frames, a shared palette, an atlas with frame coordinates, a locally generated forest hero, a square social card and an animated turntable. A small browser game uses the actual atlas for movement and collection. No external fonts, analytics or runtime asset CDN is required.

### What worked

- Geometry, camera directions and bob animation remain consistent because Blender renders every frame from the same object.
- FLUX produced a coherent wide forest environment suitable for the page's mood. Text remains ordinary HTML, so headings stay legible and editable.
- Rendering on Radeon HIP worked. Atlas crops round-trip to all 96 source sprites byte for byte. All three GLBs reimported into Blender with nine meshes each and changing animated transforms.
- Browser interaction demonstrated a collectible disappearing and the count increasing; animation pause also changed state correctly.

### What needed judgment or correction

- FLUX's earlier fox prompt asked for one fox and produced two. SDXL's earlier single-bottle icon produced two bottles. Count and composition need visual review even when inference succeeds.
- A successful colour edit still resynthesizes pixels. It cannot guarantee untouched logos, dimensions, text or background pixels. Use a mask and composite onto the original for exact preservation.
- 3D-to-pixel conversion provides alignment and consistency, but it is not hand-authored pixel art. The 64px set still benefits from artist cleanup of highlights and silhouettes. At 32px, simplify the geometry/materials before merely shrinking it.
- Browser testing exposed focus-induced scrolling that displaced the click target. The click handler now measures the canvas before focusing it and suppresses focus scrolling.
- The GLBs were reimported and their animated transforms tested in Blender; an import into the user's actual engine has not been tested. The all-six completion state was observed in the browser, but this is not a complete game QA pass.

## Expansion result measured so far

Z-Image Turbo BF16 completed a 1024², eight-step render in 275.405 seconds. The resulting fictional lantern looks photographic, but the requested seamless backdrop became an outdoor forest scene. This configuration is much slower than the earlier FLUX 4B tests. Five-second memory samples briefly reported only about 0.035GiB available RAM during the run; that establishes memory pressure, not a proven explanation for all of the latency. Peak usage may be higher than sampled observations.

The character-sheet experiments are documented in Character-Study/README.md. FLUX failed the requested passing pose; two automatic matte models failed on the second sheet. These failed candidates were retained as evidence rather than called production assets.

## Bigger models: a practical ceiling, not a promise

| Candidate | Why it belongs | Configuration / tradeoff |
|---|---|---|
| Z-Image Turbo 6B | Product-style photography, realistic promotion, fresh alternative to FLUX | BF16 diffusion weights about 12.31GB, reuses existing Qwen3 4B encoder; 1024², 8 steps, CFG 1; automatic offload and tiled VAE |
| Qwen Image Edit 2511, 20B | Material replacement, harder reference edits and multi-image composition | Unsloth Q4_K_M diffusion weights about 13.24GB plus 9.38GB FP8 text encoder; start 768², one image, 4-step Lightning LoRA, tiled decode |
| FLUX Klein 9B | Possible future quality comparison | Different non-commercial model license and gated access. Not selected as the default product-production upgrade |
| Very large BF16 image models | Research only on this configuration | Model, encoder and activations compete with 16GB VRAM and 32GB RAM; aggressive offload can turn a render into a paging workload |

Z-Image's publisher describes a 6B model and a 16GB consumer-GPU deployment target. That does not guarantee this exact AMD runtime or workload; local rendering is the acceptance check. [Z-Image model card](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo), [ComfyUI workflow](https://docs.comfy.org/tutorials/image/z-image/z-image-turbo).

Qwen's 20B editor focuses on consistency and editing. The selected third-party quantization reduces the weight file to approximately 13.2GB; this is file size, not total VRAM usage. Quantized weights, temporary dequantization, text encoding and VAE work still need headroom. [Qwen model card](https://huggingface.co/Qwen/Qwen-Image-Edit-2511), [Unsloth quantization](https://huggingface.co/unsloth/Qwen-Image-Edit-2511-GGUF), [ComfyUI editing workflow](https://docs.comfy.org/tutorials/image/qwen/qwen-image-edit-2511).

ComfyUI-GGUF is an additional custom node dependency, pinned in this installation to commit 6ea2651e7df66d7585f6ffee804b20e92fb38b8a. Its upstream describes quantization and LoRA support as evolving. Dependencies were installed under the existing ROCm constraints and pip check passed. [Upstream loader](https://github.com/city96/ComfyUI-GGUF).

FLUX Klein 9B is gated and uses the FLUX non-commercial license, unlike the selected 4B variant. Revisit access and the actual license before making it part of a commercial workflow. [Publisher model card](https://huggingface.co/black-forest-labs/FLUX.2-klein-9B).

## Operating configurations

**Everyday:** FLUX 4B or SDXL, batch size 1, around one megapixel. Keep the existing 2GB VRAM reserve. Reuse one loaded model across a batch, then unload before switching. Save prompt, seed, model hash and workflow with the output.

**Heavy editing:** start Qwen at 768² with one reference and tiled decode. Close other GPU-heavy applications if memory becomes tight. A second reference, higher resolution or a different LoRA is a new memory test. Do not run Blender GPU rendering and heavy inference simultaneously. “Fits after CPU offload” and “comfortable for iteration” are different outcomes.

**Sprite production:** render at a stable camera and framing; choose the final pixel grid before palette reduction; use nearest filtering, fixed pivots and explicit frame durations. Disable mipmaps for ordinary pixel sprites unless the game's camera requires them. Test atlas filtering in the actual engine.

**Product fidelity:** preserve the original photograph or model, exact label artwork, alpha and masks. Generate the environment separately, then composite. For a real sellable product, compare every visual feature against the real item; the Z-Image test depicts a fictional lantern.

## Next expansions, in order

1. **Finish editor acceptance.** One Krita selection edit, apply it to a new layer, save a KRA, reopen it and verify the original remains available. Compare the same edit in FLUX and Qwen. Success means the desired material changes with acceptable shape drift.
2. **Engine-specific delivery.** Choose the actual engine, import the GLBs and atlas, verify scale, pivots, filter settings, animation loops and collision footprint. Generate its native metadata only once the engine is known. The browser demo already proves one actual runtime integration.
3. **Controlled asset families.** Add a project style board, fixed camera/lighting and approved palette. Try existing reference conditioning before training a LoRA. Train only when repeated tests show a specific consistency problem and a curated dataset is available.
4. **Promotional motion.** First use Blender camera moves and conventional editing, which preserve product shape. Evaluate a short Wan 2.2 5B image-to-video test later for atmosphere. The official workflow is a starting point, not AMD compatibility proof. [ComfyUI Wan 2.2](https://docs.comfy.org/tutorials/video/wan/wan2_2).
5. **Image-to-3D experiment.** Evaluate Hunyuan3D in an isolated environment only after choosing an actual asset that benefits from it. Budget time for topology, UV and material cleanup; keep procedural Blender for simple props. Its renderer/build dependencies deserve a separate AMD compatibility test. [Hunyuan3D upstream](https://github.com/Tencent-Hunyuan/Hunyuan3D-2).

## Automation that is useful now

A project brief becomes a saved ComfyUI API graph. A script submits it to the local queue, records the returned prompt ID, checks its history and copies the successful output. Blender runs headlessly to produce geometry and animation frames. Pillow packs sprites and exports WebP/GIF. The browser preview consumes the resulting manifest.

Keep execution serial on the GPU. On an interrupted request, inspect the recorded prompt ID before submitting again. Name batches, keep raw candidates separate from accepted assets and never silently overwrite an original. Add a human visual-selection step before copying a candidate into a real product repository.

A useful next batch would be 8–12 deliberately chosen prompts across icons, product scenes, environments and exact edits, scored for brief adherence, identity preservation, cleanup time and end-to-end latency. One attractive sample does not establish a model winner. No fine-tuning service, recurring automation or external publication has been configured.
