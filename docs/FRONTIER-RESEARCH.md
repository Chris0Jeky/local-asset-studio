# Frontier atlas: a studio that investigates, composes and finishes

**As of 11 September 2026.** This research was conducted against `6bd4e5ba36c3df22011727772754b6e9b3d13c70`. Sources are the linked model authors, project maintainers and official documentation. The [45-entry catalog](../research/frontier/catalog.json) is a reference directory, not a quality ranking or installed-model inventory. [Fourteen blueprints](../research/frontier/recipes.json) describe proposed pipelines; none is being passed off as a newly executed ComfyUI graph.

## 1. The useful change in direction

The next substantial improvement should be a **creative experiment system around ComfyUI**. A larger dropdown will not answer the important questions: which pipeline fits this brief, what can run on this hardware, which stage needs changing, and whether extra compute produces an asset worth keeping.

Build three connected workspaces: an **Atelier** for illustration, reference edits and layered repair; a **Shot Lab** for controlled motion, keyframes, continuation and audio; and an **Asset Foundry** for geometry, materials, sprites and engine-ready packaging. Share model intake, experiment records and source provenance across them. These are proposed product boundaries, not three new processes that should all compete for the GPU.

The repository already records a useful foundation: SDXL-family illustrations, WAI/Animagine controls, reference edits, finishing nodes, a working Blender-to-sprite example, and an isolated HiDream-O1 feasibility run. It also records large downloaded-but-unrun components and native process crashes. Preserve those distinctions. See [current state](../CURRENT_STATE.md), [operations](OPERATIONS.md) and the historical hardware snapshot in [existing findings](research/Asset-Strategy-and-Findings.md).

### Hardware-aware priorities

The recorded machine is an **RX 9070 XT with 16GB VRAM, roughly 32GB system RAM, Windows, and the AMD portable ComfyUI runtime**. This is not equivalent to a 16GB CUDA setup. Historical free-disk and free-RAM figures are stale after subsequent downloads; remeasure before provisioning.

My recommended order is: improve usable output from the installed image stack; establish one isolated H3 baseline; compare an independent video family; then investigate a compatible 3D worker. Retain a portable SDXL/Blender path throughout. A CUDA-only experimental package should not trigger a repair cascade in the working ROCm environment.

## 2. What your downloaded H3 file actually is

The recognized file name belongs under:

```text
<ComfyUI root>/models/diffusion_models/
    minimax_h3_fl2va_pruned_int8_convrot.safetensors
```

It is the diffusion component, not a whole self-contained checkpoint. The [Comfy-Org H3 pack](https://huggingface.co/Comfy-Org/MiniMax-H3) also lists a matching Qwen3VL text encoder in `models/text_encoders` and separate video/audio VAEs in `models/vae`. Optional Turbo adapters go in `models/loras`; the supplied Fun ControlNet patch uses `models/model_patches`. FL2VA and REF2VA are different bundles, not two friendly names for the same file.

The pack recommends INT8-convrot with a cu130 runtime. That is **not evidence that this precise quantization path works on Radeon**. Inspect the installed loader, backend capabilities and upstream requirements first. FP8 or another supported representation may be an alternative, but its feasibility must also be measured. Do not download a second enormous bundle just to guess. The included header inspector makes a folder suggestion without executing or relocating anything.

[Native H3 documentation](https://docs.comfy.org/tutorials/video/minimax/minimax-h3) covers first/last-frame generation, multimodal references, multiframe guidance and control-video workflows. It also identifies a separate commercial-license requirement for locally generated commercial outputs. Record that before using outputs in DeliveraSoft or a commercial game; this pass purchases or activates nothing.

### The two supplied Civitai links

The supplied [image](https://civitai.red/images/141483065) and [Seed Hunter workflow](https://civitai.red/models/2881362/minimax-seed-hunter-workflow-latent-upscaler-seamless-video-continuation-speedups) could not be inspected here. Attempts against the corresponding .com surface and model API did not yield the graph. A creator video surfaced, but that is not a substitute for inspecting the workflow bytes. Consequently, this package does **not** claim to have audited that graph, reproduced its example or verified its performance.

The local authenticated agent can export the graph and metadata through its available access. Intake should retain model/version/file IDs, creator identity, source URL, published/updated dates, file hashes, base family, trigger words, required custom nodes, resource files and terms. Treat promotional images as motivation, then reproduce a small claim before adopting the graph. Do not infer that a mirror's license label authenticates the original creator. The [Civitai API reference](https://github.com/civitai/civitai/wiki/REST-API-Reference) is the appropriate contract to consult rather than inventing endpoints.

## 3. Image and anime: more control before more checkpoints

### A useful baseline panel

Use **Animagine XL 4.0 / the installed WAI family** for anime, **RealVisXL** for a realistic SDXL specialist, the installed **Klein** setup for rapid variation, and the existing **Qwen/HiDream** lanes for harder edits or comparison. Add an upstream **Illustrious XL v2.0** comparison only where it answers a specific question. These are proposed task assignments, not claims of universal superiority. Sources: [Animagine](https://huggingface.co/cagliostrolab/animagine-xl-4.0), [Illustrious](https://huggingface.co/OnomaAIResearch/Illustrious-XL-v2.0), [RealVis](https://huggingface.co/SG161222/RealVisXL_V5.0), [Klein 4B](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B).

Useful newer comparisons include [Z-Image base](https://huggingface.co/Tongyi-MAI/Z-Image), [Qwen-Image-2512](https://huggingface.co/Qwen/Qwen-Image-2512) and [Qwen-Image-Edit-2511](https://huggingface.co/Qwen/Qwen-Image-Edit-2511). Resolve the exact currently installed variants before downloading near-duplicates. Finish the repo's existing FLUX.2 dev Q4 and HiDream experiments rather than treating another model announcement as evidence that they are obsolete.

### The character atelier

A proposed high-value chain is:

```text
character specification + accepted reference
  -> pose/depth/line-art preparation
  -> matching reference adapter + controlled base generation
  -> human composition/identity selection
  -> local masked repair
  -> optional appearance-preserving upscale
  -> target-size proof + layered source + metadata
```

[Xinsir Union](https://huggingface.co/xinsir/controlnet-union-sdxl-1.0) provides a particularly useful control research target: evaluate one hint first, then a complementary pair such as pose plus depth. Its ProMax variant should be recorded separately from standard Union. [IPAdapter Plus](https://github.com/cubiq/ComfyUI_IPAdapter_plus) is a reference-conditioning tool; [ControlNet auxiliary preprocessors](https://github.com/Fannovel16/comfyui_controlnet_aux) produce guidance maps. A preprocessor and a control model are different dependencies.

Use [Krita AI Diffusion](https://github.com/Acly/krita-ai-diffusion) for painting, layers and masks rather than rebuilding a canvas inside the studio. Keep the existing automatic face/hand detector passes optional. A detector tells you where to inspect, not that redrawing the region is beneficial. Compare original and repaired crops, including costume seams, fingers contacting props and small facial features.

### A disciplined LoRA portfolio

Organize adapters by **identity**, **visual medium**, **environment/material**, **camera/composition**, and **acceleration/control**. For this studio, useful non-explicit research themes include cel shading, ink linework, screentones, watercolor fantasy, painterly environments, hard-surface props, isometric scenes and pixel-style concepts. These are discovery briefs, not fabricated model recommendations.

Two inspectable examples are [Pixel Art XL](https://huggingface.co/nerijs/pixel-art-xl), an SDXL adapter already relevant to the studio, and [Watercolor Strokes](https://huggingface.co/gokaygokay/Flux-Watercolor-Strokes-LoRA), whose card targets FLUX.1-dev and gives the `WTRCLR, watercolor` trigger. The latter is **not** a FLUX.2 Klein adapter. Its modest research value is a controlled style trial; no claim of frontier quality or training-data clearance is made.

Every candidate should carry a compatibility tuple: architecture, exact base lineage, prediction type, adapter format, text-encoder assumptions, trigger tokens and intended strength range. Tensor-shape compatibility is necessary but does not prove useful behavior. Avoid blindly stacking character, style, detail, pose and speed adapters, then trying to diagnose all five at once.

Proposed experiment: hold prompt and references fixed; compare no adapter, one low-strength adapter and one moderate-strength adapter using several seeds. Only after it helps should you add a second adapter. Prefer a model card's strength guidance; absent guidance, choose conservative values and label them exploratory. Do not use a universal slider default across every family.

For recurring original characters, [AI Toolkit](https://github.com/ostris/ai-toolkit) and [Musubi Tuner](https://github.com/kohya-ss/musubi-tuner) are training references. First show that prompting and reference conditioning are insufficient. Then train in an isolated supported environment, keep held-out poses/costumes/backgrounds, and measure whether the adapter improves generalization rather than memorizing a sheet.

### Manga, game sprites and exact products need different finishing

For manga, generate controlled panels independently, then compose the page and typeset editable balloons. For sprites, prefer deterministic geometry/rig/camera when repeated views and motion matter; the existing Lanternkeeper is a better engineering foundation than a visually impressive but inconsistent generated sheet. For an exact product, protect source geometry and logos with masks and compositing. These are proposed production techniques, not additional model capabilities.

## 4. Video: three distinct research lanes

### A. H3 as a staged shot laboratory

Start from [official templates](https://github.com/Comfy-Org/workflow_templates), reproduce one small native shot, and preserve its graph. Only then study the community stages below.

| Source | Why investigate it | Test before adoption |
|---|---|---|
| [LightX2V H3 Turbo](https://huggingface.co/lightx2v/Minimax-h3-Turbo) | Matching short-schedule adapters for preview exploration | Variant/schedule agreement and whether preview ranking predicts final usefulness |
| [LBH learned H3 upscaler](https://github.com/LBH-123-AI/Comfyui_Minimax_h3_latent_Upscaler) | Learned spatial latent enlargement, including 2D/3D variants | Temporal seams, detail fidelity and peak memory; author does not promise automatic VRAM savings |
| [FL MiniMaxH3](https://github.com/filliptm/ComfyUI-FL-MiniMaxH3) | Timeline conditioning, temporal reshots and shot assembly | Audio preservation and rebuilding size-dependent conditioning after resizing |
| [H3 caching experiments](https://github.com/pepikir/minimax-h3-speedup) | Separating conditioning, sampling and decode | Complete context preservation, invalidation and serialization audit |
| [H3 Fun ControlNet](https://huggingface.co/alibaba-pai/MiniMax-H3-Fun-Controlnet-Union) | Authored control video and targeted edits | Control/frame alignment and actual additional memory cost |

The proposed seed-lab architecture is **encode once → bounded previews → select → final generation → optional refinement → export**. Cache exact reusable inputs before trying approximate attention or model acceleration. A reference-heavy encoder can dominate repeated experiments, but measure this rather than borrowing another GPU's timings.

Do not load third-party pickle/`torch.save` caches. They are not passive image files. A future persistent cache should use locally generated, validated tensor data and explicit JSON metadata where possible; preserve all reference/keyframe/audio conditioning, not just a convenient tensor subset. A partial cache can create a plausible-looking but semantically incorrect result.

Continuation should be an editorial branch with overlap handles, protected prefix context and visible seam review. Do not concatenate the last frame into a new independent generation and call that guaranteed seamless continuation. Compare a direct cut, constrained continuation and a short bridging shot; the simplest acceptable edit may beat the most elaborate graph.

### B. LTX-2.5, not a stale LTX shortlist

[LTX-2.5](https://huggingface.co/Lightricks/LTX-2.5) is a current candidate with connected-shot and fidelity-rendering workflows. Its split pack includes a new Gemma4-based encoder; the distilled transformer uses a fixed eight-step, CFG-one baseline. Treat it as a complete dependency bundle, not a one-file replacement for an older installation. Its documented CUDA paths do not establish Windows/Radeon feasibility. Access consent and custom license terms remain explicit human decisions.

My proposed trial compares a short single shot, several independently assembled shots and native multishot using the same story brief. Add expensive rendering stages only after the motion and continuity work. Record how many usable seconds survive review, not merely nominal output resolution.

### C. Wan and VACE for authored control

[Wan2.2 I2V A14B](https://huggingface.co/Wan-AI/Wan2.2-I2V-A14B) is a separate comparison lane. Keep its noise-stage components matched. The original [VACE](https://github.com/ali-vilab/VACE) release explicitly includes Wan2.1-based editing models; do not relabel them Wan2.2 or assume every community combination is supported. Start from an actually documented VACE graph, then evaluate any newer integration independently.

[Kijai's WanVideoWrapper](https://github.com/kijai/ComfyUI-WanVideoWrapper) is valuable for example workflows and experimental control features. Its author advises using native ComfyUI where equivalent functionality exists. That is a useful default: wrappers should buy a capability, not merely make a graph look more advanced.

Use a Blender proxy clip with known camera motion and object contact as the shared input across control families. A generated scene can then be judged against an intended movement rather than against unrelated promotional examples.

### Finishing is its own experiment

[VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite) supports the media-I/O side; [SeedVR2's Comfy integration](https://github.com/numz/ComfyUI-SeedVR2_VideoUpscaler) is a restoration candidate to compare against native latent refinement. Test the same accepted clip at the same output size, including temporal crops and original audio. Frame interpolation, restoration and generative continuation solve different problems; none certifies missing anatomy or correct motion.

## 5. 3D: pursue usable objects rather than attractive previews

[TRELLIS.2](https://github.com/microsoft/TRELLIS.2) is a compelling image-to-3D/PBR candidate, but its official setup targets Linux and NVIDIA hardware with at least 24GB VRAM. That is not a drop-in recipe for this PC. Treat a compatible isolated worker as a research option; do not provision paid compute without an explicit decision. [Hunyuan3D 2.1](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1) and [TripoSG](https://github.com/VAST-AI-Research/TripoSG) provide useful alternative investigations. Check shape and texture requirements separately.

The proposed factory is:

```text
approved image / geometric brief
 -> shape proposal -> hidden-view inspection -> topology and UV cleanup
 -> material authoring / generated texture proposal -> light-rotation review
 -> scale / pivot / collision / LODs -> GLB -> engine round-trip
```

For characters, [UniRig](https://github.com/VAST-AI-Research/UniRig) is an automatic rigging research option, not proof that the result deforms acceptably. Test bent elbows, shoulders, hips, attachments and foot contact. A neutral pose can hide serious skinning failures.

[Material Maker](https://github.com/RodZill4/material-maker) is especially attractive here because controllable procedural structure complements generated appearance. Keep tileability, physical scale, albedo and lighting assumptions explicit. A plausible normal or roughness map inferred from an image is not a measurement of the source material.

Extend the existing Blender/sprite pipeline before replacing it: fixed cameras and pivots, shared palettes, declared frame durations, transparent exports and actual engine playback are useful guarantees that independent generations do not automatically provide.

## 6. More useful combinations

**Editable video and campaign assembly.** Use accepted clips as ingredients in HyperFrames HTML/GSAP compositions in Codex. Keep captions, titles, logos and transitions editable; define a project `DESIGN.md` first. HyperFrames' installed skill documents this workflow; this pass does not claim it was installed or rendered on the user's PC. [ACE-Step 1.5](https://github.com/ace-step/ACE-Step-1.5) is an optional music research lane, with output review and rights tracked separately.

**State-controlled worlds.** [H3-World](https://arxiv.org/abs/2609.01560), [SolarWM](https://arxiv.org/abs/2609.02886) and [Code World Model](https://arxiv.org/abs/2608.25927) are recent research leads, not ready-made Studio features verified here. The particularly interesting design direction is authoritative scene state in code, proxy rendering for camera/geometry, and generative appearance layered over it. Keep game rules and object state deterministic even when imagery is synthesized.

**Do not rebuild ComfyUI wholesale.** [App Mode](https://docs.comfy.org/interface/app-mode), [subgraphs](https://docs.comfy.org/interface/features/subgraph) and [partial execution](https://docs.comfy.org/interface/features/partial-execution) already address simplified controls and graph organization. Studio can concentrate on project assets, discovery, hardware-aware selection, experiment comparison and export contracts. Put painting in Krita and deterministic geometry in Blender.

## 7. What should count as a flagship configuration?

Promote a bundle only after it wins a reproducible, task-specific test. Suggested initial briefs: a recurring fantasy character holding a prop; a three-panel conversation; an observatory interior with a fixed camera; a product-background edit with protected text; a short door-opening shot; and a directional sprite pack.

Record cold load time, warm sampling time, encoding/decode time, failed attempts, peak memory where actually measured, useful output rate, cleanup time and export acceptance. Keep hard failures separate from aesthetics. Equal step counts across architectures are not equal compute, and identical integer seeds across unrelated models are not equivalent noise.

A sensible frontier portfolio has a fast baseline, a quality candidate and a controlled experimental branch for each valuable task. Choose the configuration that reduces total effort per accepted asset. “Trending,” parameter count, graph size and a beautiful cherry-picked example are discovery signals—not evidence that a workflow belongs in the default studio.
