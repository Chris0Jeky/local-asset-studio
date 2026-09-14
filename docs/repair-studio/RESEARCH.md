# Repair techniques: evidence and implications

Primary sources checked 14 September 2026. This is capability research, not an installed-model inventory or a workstation benchmark. Live URLs may change; a qualified adapter must record exact revisions and weights in the existing registry. No weights or node packages were installed by this research.

## 1. Three different inverse problems

Restoration estimates cleaner/high-resolution content from a degraded observation. Anatomical correction changes an incorrect structure. Completion invents content absent through occlusion or cropping. One model may participate in several tasks, but successful upscaling does not demonstrate correct finger count, and a convincing completion is not recovery of uniquely known original pixels.

The perception-distortion tradeoff [S16] is a useful theoretical warning: perceptual plausibility and fidelity are not interchangeable objectives in restoration. It does not prove that a particular malformed limb is unrecoverable or prescribe this architecture. Our engineering inference is to retain separate repair, remaster and reconstruction contracts instead of one undifferentiated quality score.

## 2. Technique matrix

| Technique | Useful contribution | Limitation and resulting decision |
|---|---|---|
| Exact crop/resize/pad | Allocate working pixels and preserve panel provenance | Cropping retains contaminants; coordinate transforms must be recorded, not guessed [S17] |
| Real-ESRGAN anime restoration | Sharpen/enlarge anime-oriented imagery | Not a skeleton/hand validator; compare against conservative resizing after structural repair [S1] |
| Impact detector/detailer | Find and redraw enlarged local face/hand regions | Detector confidence locates a region, not a defect; inspect mask and avoid repainting an already-correct face [S2] |
| CropAndStitch | Separate context from edited area, enlarge a working crop and return a patch | Exact node version and mask/resize semantics matter; final Studio compositor remains authoritative [S3] |
| Matched-family masked img2img/inpaint | Local reconstruction while retaining a familiar style | Low strength can preserve the defect; higher strength can drift identity. Patch/model/encoder compatibility is exact, not generic |
| Qwen Image Edit 2511 | Instruction-driven and multi-reference editing | Author-reported consistency improvements are not an anatomy success rate or hard pixel lock [S4] |
| FLUX.2 Klein 4B | Compact multi-reference generation/editing alternative | Model card limitations still apply; advertised NVIDIA resource figures are not AMD measurements [S5] |
| ControlNet pose/depth/edge | Spatial guidance beyond prompt words | An estimated guide from malformed source may reinforce the error. Inspect or author it; use the correct family [S6] |
| HandRefiner-style geometry | Conditional repair guided by reconstructed hand shape | Original code uses SD1.5 dependencies; severely unrecognizable hands can defeat fitting; input PNG family is separate from weight compatibility [S7] |
| SAM2/SAM3 segmentation | Point/box/exemplar-based target selection | Concept matching may find several identical instances; review instance-specific results, especially on stylized art [S8,S9] |
| ViTMatte/trimap matting | Fractional edges for hair/translucency | Matting is not segmentation or anatomy reconstruction; inspect foreground colour contamination and halos [S10] |
| Qwen Image Layered | Generative layered RGBA decomposition | Proposed layers are not guaranteed original author layers, true unseen geometry or a ready rig [S11] |
| CCSR restoration | A content-consistency-oriented restoration experiment | Research objective/results do not establish anime hand repair; qualify only after the simpler baseline [S12] |
| Native paint / authored 3D proxy | Precise structural intent and reversible finishing | Costs manual effort; count it, but retain it as a dependable escape path rather than hiding it |

The matched-family row is a proposed baseline using existing Studio routes, not a comparative benchmark result. No universal denoise/CFG/step setting is specified. Use model-specific defaults as an audition, then compare bounded variants at fixed source, mask and references.

## 3. Detailed consequences

**Context is helpful and dangerous in different ways.** Selection-fill documentation separates useful context from edit selection [S13]. A chair can explain a seated pose; another face may contaminate identity. A protection mask prevents writes, not semantic influence. Keep context variants reviewable and use clean canonical references.

**Masks do not solve geometry alone.** A correct mask ensures where a patch may enter, not whether the wrist lines up or the hand holds the intended prop. Pose/depth guidance and explicit contacts constrain a different part of the problem. A hand proxy that fits the wrong silhouette should not be trusted because its renderer produced a valid depth image [S6,S7].

**Multi-subject and repeated panels are different tasks.** Independent sheet panels can share canon while being repaired separately. Physically interacting subjects need joint contact review. Regional conditioning can associate attributes with areas but its documentation explicitly distinguishes it from geometry control [S14]. Do not extrapolate three semantic reference slots into an arbitrary many-actor controller.

**Transparency requires an adapter decision.** A matte, an alpha-bearing image and an inverse-alpha edit mask are different representations. Maintain canonical coverage/protection masks separately. Normalizing orientation also changes coordinates; `contain`, `fit` and `pad` have different crop/resize meanings [S17]. Native preprocessing must be measured, not assumed from output dimensions.

**Models and runtime are not interchangeable.** Quantization and distilled/Lightning schedules create different effective configurations. The same seed is useful for a bounded comparison within a frozen setup, but does not guarantee identical output across software, hardware or release versions [S18]. Store actual artifacts and all effective settings.

**Recovery belongs outside the model graph.** Comfy documents queue, history, prompt and WebSocket interfaces [S15]. Those interfaces do not establish a cross-system exactly-once transaction with Studio. Existing durable intent/prompt tracking is therefore retained; unknown replies must not start a fresh graph automatically.

## 4. Research order and experimental discipline

Start with manual scope plus the currently registered anime repair and existing Qwen bridge. Measure whether failures arise from poor masks, small working crops, wrong framing, incompatible styles or insufficient semantic change. Add authored geometry where structure repeatedly fails. Add segmentation only where it reduces selection effort, and matting only where binary edges are inadequate.

An additional model should earn a place through a defect-class improvement under the same total budget, not a favourable showcase. Compare accepted task yield and total cleanup effort, retain no-op/occluded controls and publish negative results. The full-model, accelerated and quantized variants are separate rows in the evidence table. Installation/schema/inference/visual acceptance/terms each remain separate statuses.

Do not install every source below. Sources describing CUDA examples, research notebooks or a particular framework are capability evidence, not proof that their nodes run within the established Windows ROCm environment. Use isolated feasibility experiments with explicit resource and provenance checks.

## Sources

- **S1 — Real-ESRGAN anime model guide:** https://github.com/xinntao/Real-ESRGAN/blob/master/docs/anime_model.md
- **S2 — ComfyUI Impact Pack:** https://github.com/ltdrdata/ComfyUI-Impact-Pack
- **S3 — ComfyUI Inpaint CropAndStitch:** https://github.com/lquesada/ComfyUI-Inpaint-CropAndStitch
- **S4 — ComfyUI Qwen Image Edit 2511 guide:** https://docs.comfy.org/tutorials/image/qwen/qwen-image-edit-2511
- **S5 — FLUX.2 Klein 4B model card:** https://huggingface.co/black-forest-labs/FLUX.2-klein-4B
- **S6 — ControlNet author repository:** https://github.com/lllyasviel/ControlNet
- **S7 — HandRefiner author repository:** https://github.com/wenquanlu/HandRefiner
- **S8 — Meta SAM2:** https://github.com/facebookresearch/sam2
- **S9 — Meta SAM3:** https://github.com/facebookresearch/sam3
- **S10 — ViTMatte author repository:** https://github.com/hustvl/ViTMatte
- **S11 — Qwen Image Layered model card:** https://huggingface.co/Qwen/Qwen-Image-Layered
- **S12 — CCSR author repository:** https://github.com/csslc/CCSR
- **S13 — Krita AI Diffusion selection fill:** https://docs.interstice.cloud/selections/
- **S14 — Krita AI Diffusion regions:** https://docs.interstice.cloud/regions/
- **S15 — ComfyUI server routes:** https://docs.comfy.org/development/comfyui-server/comms_routes
- **S16 — Blau and Michaeli, The Perception-Distortion Tradeoff:** https://arxiv.org/abs/1711.06077
- **S17 — Pillow ImageOps:** https://pillow.readthedocs.io/en/stable/reference/ImageOps.html
- **S18 — PyTorch reproducibility:** https://docs.pytorch.org/docs/stable/notes/randomness.html

The project-specific foundations are the current `ANIME-QUALITY.md`, `ANIME-DETAILING.md`, `REFERENCE-ATELIER.md`, `character-consistency/STUDIO-BRIDGE.md`, `CAMPAIGN-BUDGETS.md`, `EDIT-PIXEL-CONTRACT.md` and `KRITA-DOCUMENT-SESSION.md`. They document different slices and dates; reconcile broad older not-implemented prose against current source and CURRENT_STATE before making a claim.
