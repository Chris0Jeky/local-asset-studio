# Game-asset frontier: controllable production rather than isolated generations

**Research snapshot: 11 September 2026.** Recommendations below are engineering judgments, not a leaderboard or claims of local execution. Sources are the linked creators, maintainers and official specifications; the machine-readable directory is [sources.json](../../research/game-assets/sources.json). The tested implementation boundaries are in [README](README.md).

## 1. Choose the deliverable before the generator

An agent asked for “a character with portraits and animations” should first choose the representation. The following routes have different economics and guarantees.

| Desired result | Recommended starting route | Why / main tradeoff |
|---|---|---|
| Portraits and expression variations | Role-separated reference editing, then masked repair and layered source | Good reuse of one identity; each expression still needs inspection. |
| Hand-drawn or pixel sprite action | Authored key poses, guided individual frames, shared canvas/palette and atlas export | Direct silhouette control; effort grows with poses and views. |
| Dialogue portrait with blinking/breathing | Layered 2D puppet, explicit joints and editable curves | Reusable motion; separation must include hidden overlaps and sensible pivots. |
| Eight-direction walk cycles or rotating props | A reviewed 3D rig/scene rendered to 2D | Camera, scale and motion stay deterministic; initial modelling effort is higher. |
| Static 3D prop | Approved base/procedural model or generated proposal, then topology/material/collision review | A turntable is insufficient evidence of a usable game object. |
| Animated 3D character | Mesh → deformation topology → rig/weights → retarget → contact/loop cleanup → engine proof | Each step can fail independently and needs a saved intermediate. |
| Terrain and tile sets | Adjacency grammar and material graph before visual variation | Tileability alone does not create an autotile system. |
| UI / effect pack | Deterministic grid/timing/blend contract, then imagery and actual runtime testing | Labels, nine-slice rules and effect dynamics should remain editable. |

These are the eight shipped route definitions. A useful agent can choose among them, explain the tradeoff and retain a branch when uncertain. It should not turn every request into one huge diffusion graph.

The recorded local machine is an RX 9070 XT 16GB with about 32GB host RAM, using a working Windows AMD Comfy runtime. Existing successful runs and crashes remain in CURRENT_STATE.md. Remeasure free RAM/storage: earlier values precede large downloads. NVIDIA VRAM figures, flash-attention recipes and CUDA-only training instructions are not Radeon feasibility evidence.

## 2. Reference-driven anime illustration

Use the installed anime/reference-editing stack first, with a formal distinction between **identity**, **pose**, **style**, **costume**, **composition**, **geometry** and **motion**. The detailed input recipes and actual three Qwen variants are in [REFERENCE-WORKFLOWS](REFERENCE-WORKFLOWS.md).

A flexible reference editor and a structural-control graph serve different needs. Qwen/FLUX-style multi-image editing is convenient for describing contributions from several images. A matching SDXL ControlNet path provides explicit pose/depth/line guidance; an appearance adapter supplies different information. [Xinsir Union](https://huggingface.co/xinsir/controlnet-union-sdxl-1.0) is a useful structural candidate already related to the installed library. [IPAdapter Plus](https://github.com/cubiq/ComfyUI_IPAdapter_plus) remains useful, but its maintainer marks it maintenance-only; treat it as a mature pinned component rather than an actively expanding flagship.

For difficult viewpoint changes, the creator-published [Qwen multiple-angle adapter](https://huggingface.co/justabigduck/Qwen-Image-Edit-2511-Multiple-Angles-LoRA) is worth a small same-character experiment. Generated rear views are design proposals, not measured geometry. Approve them before feeding them into a 3D or animation branch. [OmniGen2](https://github.com/VectorSpaceLab/OmniGen2) is an independent multi-reference candidate; compare it on the same identity/pose/style brief rather than unrelated showcase art.

For a recurring original character, keep a design specification: proportions, hairstyle, costume pieces, palette, asymmetric accessories, expressions, silhouette and forbidden drift. A character LoRA becomes useful when repeatable reference conditioning falls short, but it adds training-data, architecture and version-management work. Evaluate on held-out poses and costumes rather than reproducing a training sheet. Keep motion/control adapters separate from identity/style adapters; adding all at once makes failures difficult to diagnose.

## 3. A genuinely useful intermediary: editable layers

[Qwen-Image-Layered](https://huggingface.co/Qwen/Qwen-Image-Layered) decomposes an image into multiple RGBA layers and supports varying the layer count. The official example recommends its 640-resolution bucket. It is a sizeable separate model, not a switch in the existing edit graph. The attractive experiment is:

`approved illustration → layer proposal → human/agent inspection → hidden-area repaint → named layer stack → native editor source`

Do not equate the output with animation-ready body parts. A hand may remain merged with a sleeve; an arm lifted away from the torso exposes pixels that were never visible. Recomposition should be compared to the source, while hidden-region completion is reviewed as a new design decision. Keep original layers and a diagnostic overlay so changes are inspectable.

The delivered OpenRaster writer packages reviewed, full-canvas RGBA layers into an actual layered archive with a merged preview and thumbnail. [Krita supports this interchange](https://docs.krita.org/en/general_concepts/file_formats/file_ora.html). The archive does not contain a rig or timeline; preserve those in KRA or the chosen animation project. Its format/stack tests ran here; a real Krita import is still an explicit local test.

## 4. Animation frontier worth investigating

### Editable stroke inbetweening: LayerInbetween

[LayerInbetween](https://github.com/MarkMoHR/LayerInbetween), presented as SIGGRAPH 2026 work by its authors, is a particularly relevant lead. It operates on stroke correspondence and occlusion-aware layering, with vector-oriented outputs that remain editable. Input preparation includes raster keyframes and an SVG for the first keyframe; the pipeline uses forward/inverse correspondence and separate inbetweening stages. It is closer to a production intermediate than a finished opaque video.

The documented setup needs several external models and a separate SAM2 environment. Some checkpoints use pickle-like formats; inspect provenance/loading and isolate the runtime before any execution. GPL code and dependency/model terms need separate review. Proposed test: two short line-art poses with a crossing arm or prop occlusion, compare stroke continuity and manual correction effort against ordinary interpolation.

### Colored frame plus timed sketches: ToonComposer

[ToonComposer](https://github.com/TencentARC/ToonComposer) accepts a colored keyframe, sparse sketches at chosen times, text and optional motion masks. That makes it relevant for a planned cartoon shot instead of wholly unconstrained motion. Its README reports roughly **57GB VRAM for a 480p 61-frame example**; this is an experimental compatible-worker candidate, not a promise for the local 16GB card. Its [licence](https://raw.githubusercontent.com/TencentARC/ToonComposer/main/LICENSE) is MIT for the named release subject to third-party terms, illustrating why licences must be assessed per release, not per company.

[ToonCrafter](https://github.com/Doubiiu/ToonCrafter) is an older short cartoon-interpolation baseline worth keeping for comparisons. [UniAnimate-DiT](https://github.com/ali-vilab/UniAnimate-DiT) is a different reference/pose-driven video candidate. Neither produces an engine skeleton, guaranteed alpha, correct ground contact or a ready-to-loop sprite atlas by definition. Use model-generated motion as a candidate sequence, then inspect, redraw, align and package.

### Traditional animation under agent control

The community [OpenToonz Headless fork](https://github.com/limitz/opentoonz-headless) exposes JSON-RPC over stdin/stdout and is a promising automation research target. It is not an official stable API promise from OpenToonz. A small controlled experiment should create strokes/layers, save a native project, render frames, reopen and compare. Generic `eval` is broad code execution; do not expose it to an unauthenticated network or run downloaded instructions through it.

Aseprite's [documented batch interface](https://aseprite.org/docs/cli/) is immediately relevant to sprites: frame tags, sheets and metadata can be exported without inventing a new editor. Retain the appropriately licensed installation and native source. Pixel-style diffusion output still needs a deliberate logical pixel grid, palette and final-size cleanup.

## 5. 3D: structure, mechanics and motion

### Shape and part-aware generation

[TRELLIS.2](https://github.com/microsoft/TRELLIS.2) is a substantial image-to-3D/PBR candidate, but its official Linux/NVIDIA path targets at least 24GB VRAM. [TripoSG](https://github.com/VAST-AI-Research/TripoSG) provides an independent shape comparison. [SAM 3D Objects](https://github.com/facebookresearch/sam-3d-objects) is another reconstruction lead for observed objects. None removes the need for hidden-side, topology, UV, material and engine checks.

[PartCrafter](https://github.com/wgsxm/PartCrafter) is especially interesting for a game prop factory because it proposes parts rather than only a monolithic shape. A treasure chest can then be inspected as lid/body components, but hinge axes, clearances and collision are still authored tasks. Its optional Gemini-backed assistance must not be mistaken for an entirely offline default; use explicit part counts and audited local paths when appropriate. Review background-removal and other component terms separately.

Proposed benchmark: one original chest, a lantern and a door. Compare authored procedural geometry, a monolithic generative model and a part-aware candidate. Judge unseen views, time to a usable UV/material setup, functional hinges and engine collision. Report rejected objects as well as attractive turntables.

### Rigging and gameplay motion

[UniRig](https://github.com/VAST-AI-Research/UniRig) can propose a skeleton/skinning path. An agent must still inspect shoulders, elbows, hips, hands, attachments and extreme poses. Rigging a poor deformation mesh merely moves the defect downstream.

[DART / DartControl](https://github.com/zkf1997/DART) is relevant to text-driven action timelines, keyframe inbetweening and trajectory-guided motion. Its model/code terms do not erase separate SMPL/SMPL-X or motion-data obligations. Use licensed inputs and an isolated supported environment; then map source bones/rest poses/proportions to the actual character. Motion generation and retargeting are separate stages.

**Important correction to the earlier broad shortlist:** the standard [Hunyuan3D 2.1 agreement](https://raw.githubusercontent.com/Tencent-Hunyuan/Hunyuan3D-2.1/main/LICENSE) excludes the UK, EU and South Korea. [HY-Motion 1.0's grant](https://raw.githubusercontent.com/Tencent-Hunyuan/HY-Motion-1.0/master/License.txt) also excludes the UK. These should be research-only entries for this UK workflow unless separate permission is obtained. A remote GPU or VPN is not a substitute for an applicable licence. This is a source-terms flag, not legal clearance of the remaining models.

The [HY-Motion README](https://github.com/Tencent-Hunyuan/HY-Motion-1.0) separately states that seamless-loop and in-place generation are not supported. Even apart from the licence, a generated motion clip would need contact cleanup, root-motion conversion and loop/transition work. That lesson generalizes: animation duration, feet, displacement, velocity continuity and controller transitions belong in the output contract.

## 6. Agent-accessible applications

Use native APIs and deterministic files where they provide enough control. [Krita Python scripting](https://docs.krita.org/en/user_manual/python_scripting/introduction_to_python_scripting.html) runs inside Krita; it is not a fictional universal headless `import krita` interface. [Krita AI Diffusion](https://github.com/Acly/krita-ai-diffusion) already connects generation to painting. [BlenderLayer](https://github.com/Yuntokon/BlenderLayer) is a useful bridge to investigate when a 3D pose/reference needs to sit in a painting workflow.

The community [Krita MCP bridge](https://github.com/SanSaSane/krita-mcp) offers layer/drawing/export operations and canvas feedback. Its documented close-document instability matters: use disposable copies, save before risky lifecycle operations, and verify recovery. [Blender MCP](https://github.com/ahujasid/blender-mcp) offers broad application control; inspect privileged code execution and optional external behavior. Neither was installed or connected to the user's PC here. Directory discovery in this chat found no matching installed app tools; local-agent installation remains a separately reviewed task.

Design adapters to return **both structured state and screenshots**: layer names/bounds plus a canvas image; mesh/bone/clip counts plus stress-pose renders. A tool success response without visual feedback is not enough for an agent to decide that it drew or rigged the intended asset.

## 7. Export and acceptance are part of generation

For sprites, retain equal logical canvases, a common anchor, named clips, variable frame durations, alpha policy and source hashes. Independent cropping is a common source of visual jumping. The delivered atlas tool copies RGBA bytes, adds padding/extrusion and checks source-to-region equality. Duplicate frames are a warning, not automatically an error: holds can be intentional.

[Godot SpriteFrames](https://docs.godotengine.org/en/stable/classes/class_spriteframes.html) stores relative durations. An adapter must convert milliseconds using the selected animation FPS; treating milliseconds as the raw duration multiplier produces incorrect playback. UI origin/anchor behavior also needs an actual AnimatedSprite2D test. Unity and Unreal need their own import adapters rather than a false “universal engine-ready” badge.

For GLB, use [Khronos glTF Validator](https://github.com/KhronosGroup/glTF-Validator) for structural/buffer/animation checks, then import and play the result in the chosen engine. Check skeletons, clips, root motion, materials, bounds, units, collisions and transitions. Structural validation cannot judge whether a foot slides or a face deforms convincingly.

For textures, [Material Maker](https://github.com/RodZill4/material-maker) provides controllable procedural structure alongside generated appearance. Inspect a 3x3 repeat, transitions and material channels under changing light. For UI, keep typography and nine-slice boundaries deterministic. For VFX, define alpha/additive blending, frame timing, overdraw and target-device budget.

## 8. Local control and priorities

A local model, an offline inference graph, an open code licence, a permissive weight licence and commercial output rights are different properties. Check optional prompt rewriters, model downloads, telemetry, hosted helper calls and asset provenance separately. This research covers general-purpose local generation and non-explicit anime production; it does not provide pornography-specialized workflows or bypass instructions.

Recommended first milestone: one original character with a neutral reference, a small expression set, an idle clip, editable source, a correctly timed atlas and actual engine playback. Compare frame-by-frame, cutout and 3D-rendered routes on the same design. The second milestone is a functional articulated prop. Add the more demanding research models only when a bounded experiment demonstrates an improvement in accepted output or cleanup effort.

The longest-term opportunity is a **representation-aware asset compiler**: a structured brief chooses editable layers, vector strokes, meshes, rigs or frames as intermediate representations, then invokes the appropriate model/editor at each stage. The delivered planner is the first interface for that idea, not a claim that every external adapter already exists.
