# Technique portfolio and research watchlist

This document expands the model shortlist into a role-based portfolio. The machine-readable companion is `research/adult-illustration/technique-candidates.json`. Every entry is non-executing and uninstalled until exact repository evidence proves otherwise.

## Selection rule

Promote a technique only when it solves a named control or reliability gap better than the current route after considering accepted-output yield, identity/pose/outfit leakage, resource cost, cleanup, terms and operating complexity.

A new paper, GitHub release or Comfy node is not automatically a new Studio capability.

## First-wave operational candidates

### IP-Adapter Plus

Proposed role: role-specific appearance, style, composition and qualified FaceID conditioning on compatible SD/SDXL routes.

Important constraints:

- exact IP-Adapter model and CLIP vision encoder must match the base architecture;
- FaceID variants may require their specific paired LoRA;
- crop/resize and reference weighting affect what is transferred;
- style/composition transfer is not pose geometry or pixel-write authority;
- averaging every reference is a baseline, not a general multi-role solution.

Qualification belongs under #408 with the existing style-board and Qwen baselines.

### DWPose and ControlNet Aux

Proposed role: editable pose, depth, normal, line, edge and segmentation artifacts.

The preprocessor, control model and target checkpoint are three separate compatibility decisions. Estimated keypoints from an occluded or defective source must be reviewed before use. Pose, depth and edge controls should be added only where they solve a measured geometry failure; excessive simultaneous control can make figures rigid or flatten material behavior.

### SAM 2 or another qualified segmenter

Proposed role: interactive subject/garment/region proposals. Its result remains editable and cannot become a write mask without explicit review. Anime line art, transparency, steam, hair, overlapping bodies and contact regions require dedicated held-out cases.

### WD SwinV2 Tagger v3

Proposed role: anime vocabulary suggestions with retained raw scores and exact taxonomy. The pinned source example records one published ONNX SHA-256 and Xet identity but selects no file and authorizes no download.

It should run as an optional analyzer, not a prompt restorer or acceptance critic.

### JoyCaption beta-one

Proposed role: richer caption and training-caption proposals. It may complement a tagger for relationships and garment/camera descriptions, but its resource use, inventions, schema adherence and Radeon runner remain unmeasured.

### Real-ESRGAN anime route

Proposed role: one illustration super-resolution comparator after base acceptance. Compare with deterministic resampling and low-denoise diffusion refinement. Review line quality, invented texture, seams, grain, colour and alpha at final size.

## Identity and multi-subject research

### WithAnyone

The official repository provides code/checkpoints and reports community ComfyUI support for controllable, ID-consistent and multi-ID generation. Treat it as a comparator, not an immediate dependency:

- pin the exact backbone/checkpoint/integration;
- inspect terms;
- qualify anime-domain identity and outfit separation;
- measure multi-subject contact and RX 9070 XT resources;
- compare it against current Qwen editing and role-specific SDXL controls.

### AnimeAdapter

The May 2026 paper proposes a compact pose-aware anime appearance adapter intended to separate appearance from layout. Its paper states that code, model weights and dataset will be released upon acceptance. Until those artifacts exist with usable terms, it remains paper-only watchlist research.

This is strategically relevant because it targets the precise failure Local Asset Studio needs to measure: character details leaking the reference pose/layout. It is not executable evidence.

## Training research

### T-LoRA

T-LoRA uses timestep-dependent rank and optional orthogonal parametrisation to reduce single-image overfitting. The official repository now includes SDXL and FLUX routes plus a PEFT branch with multi-adapter support. Its documented prerequisites remain Linux/NVIDIA-centric, and it does not establish an Anima/Radeon route.

Use it only as an isolated training comparator after a native/reference gap is demonstrated. Retain no-adapter and ordinary-LoRA baselines.

### sd-scripts

Current source documents support for Anima plus recent Anima LoRA/LLLite and `torch.compile` work. Version-specific issues have also been reported around validation and precision. Pin an exact release/commit and reproduce the intended training path in an isolated environment rather than updating the working Comfy runtime.

### OneTrainer

Keep as an independent local runner candidate for dataset, masked training and general experiment ergonomics. Exact target-family and AMD support must be verified from a pinned revision.

## Style control research

### AnyStyle

AnyStyle is a 2026 image-guided style-transfer research route that combines a style LoRA with training-free structural guidance. It is useful as a comparator for the principle “style from one source, structure from another.” Exact backbone, weights, terms and local workflow remain unresolved, and it must beat simpler IP-Adapter/style-LoRA routes on accepted assets before adoption.

## Qualification matrix

Every technique card should eventually report:

| Dimension | Required evidence |
| --- | --- |
| Identity | exact subject fidelity and drift across pose/outfit/style changes |
| Geometry | pose, silhouette, camera, depth and contact adherence |
| Appearance isolation | intended facet transfer plus ignored-facet leakage |
| Edit authority | whether pixels outside a reviewed write scope remain protected |
| Composition | subject count, spatial relationship and framing |
| Resources | cold/warm time, VRAM, host RAM/commit, spill and cleanup |
| Robustness | OOM, crash, missing node/model, stale source and response loss |
| Effort | attempts, user corrections and cleanup minutes |
| Terms | exact weight/code/output/service implications |
| Evidence state | source-reviewed through promoted, with no skipped stage |

## Portfolio discipline

Keep the active portfolio small:

- one fast draft route;
- one or two final anime generation routes;
- one native multi-reference editor;
- one SDXL-style geometry/appearance assembly route;
- one tagger and one caption/VLM helper at most;
- one qualified training runner;
- one deterministic and one reconstructive finishing route.

Other candidates stay discoverable in the watchlist until a measured gap justifies qualification.

## Agent handoff

A development agent should select one candidate and one evidence gate. It must:

1. verify source identity and issue ownership;
2. inspect overlap with active PRs and existing Studio capability;
3. add a failing offline or fake-backend test before behavior;
4. retain exact compatibility gaps;
5. prepare a zero-authority plan first;
6. stop rather than install or execute without the appropriate issue and approval;
7. publish accepted and failed evidence through existing owners.
