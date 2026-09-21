# Primary sources

Accessed 15 September 2026. Sources are inputs to reviewed route claims, not installation evidence. Later agents should preserve exact snapshots/revisions and record contradictions instead of replacing old claims silently.

## Models

- CircleStone Labs, Anima model card: https://huggingface.co/circlestone-labs/Anima
  - Base/Aesthetic/Turbo roles; native ComfyUI; generation and prompting guidance; LoRA training recommendations; model/output licence distinction.
- Cagliostro Research Lab, Animagine XL 4.0: https://huggingface.co/cagliostrolab/animagine-xl-4.0
  - SDXL lineage, ordered tag prompting, Opt variant and recommended baseline settings.
- Onoma AI Research, Illustrious XL v2 Stable: https://huggingface.co/OnomaAIResearch/Illustrious-XL-v2.0
  - Stable v2 checkpoint and OpenRAIL metadata.
- Laxhar Lab, NoobAI XL 1.1: https://huggingface.co/Laxhar/noobai-XL-1.1
  - Illustrious-derived tag model, recommended resolution/settings and base-specific terms.
- AstraliteHeart, Pony Diffusion V6 XL: https://huggingface.co/AstraliteHeart/pony-diffusion-v6-sdxl
  - Family baseline; an exact local derivative still requires its own card and graph.
- Qwen, Qwen Image Edit 2511: https://huggingface.co/Qwen/Qwen-Image-Edit-2511
  - 20B BF16, multiple image input, consistency/geometric editing claims and Apache 2.0.
- Black Forest Labs, FLUX.1 Kontext dev: https://huggingface.co/black-forest-labs/FLUX.1-Kontext-dev
  - 12B instruction editing, reference/iterative editing and non-commercial model terms.
- Gazingstars123, Anima 2.9B preview: https://huggingface.co/Gazingstars123/Anima-2.9B
  - Experimental community watchlist derivative; exact origin, preview status and inherited licence require revalidation before use.
- NewBie Image: pin the exact official model repository before promotion. Discovery/card claims remain unresolved in the route manifest until that identity is reviewed.

## Conditioning, geometry and masks

- Tencent AI Lab, IP-Adapter: https://github.com/tencent-ailab/IP-Adapter
- ComfyUI IPAdapter Plus: https://github.com/cubiq/ComfyUI_IPAdapter_plus
  - Exact IP-Adapter/base/CLIP vision pairing; several FaceID variants require their specific LoRA. Community workflows remain version-specific.
- IDEA Research, DWPose: https://github.com/IDEA-Research/DWPose
- ControlNet Auxiliary Preprocessors for ComfyUI: https://github.com/Fannovel16/comfyui_controlnet_aux
- Meta, SAM 2: https://github.com/facebookresearch/sam2
- ComfyUI documentation and source: https://docs.comfy.org/ and https://github.com/Comfy-Org/ComfyUI

These projects describe capabilities, not support in the installed Studio environment. Exact commits, model files, preprocessing and runtime compatibility remain qualification inputs.

## Prompt, tag and caption analysis

- SmilingWolf, WD SwinV2 Tagger v3: https://huggingface.co/SmilingWolf/wd-swinv2-tagger-v3
  - Anime ratings/character/general tag classifier; reviewed pinned tree exposes 10,861 classes plus ONNX, safetensors and `selected_tags.csv`. Scores remain model outputs, not calibrated truth or original-prompt recovery.
- FancyFeast, Llama JoyCaption beta-one: https://huggingface.co/fancyfeast/llama-joycaption-beta-one-hf-llava
  - Diffusion-training caption VLM with broad visual-domain coverage. Exact revision, runner, resources and semantic accuracy require qualification.
- Existing Prompt Lab model-dialect research: `docs/prompt-studio/MODEL-RESEARCH.md`.

## Source-provider provenance

- Hugging Face Hub documentation: https://huggingface.co/docs/huggingface_hub/
- Civitai developer docs, model versions: https://github.com/civitai/civitai-developer-docs/blob/main/site/reference/model-versions.md
  - Version lookup by ID and by file hash; provider records can expose model/version/file IDs, AIR and several hashes.
- Civitai CLI/public API client: https://github.com/civitai/cli
  - Useful reference for public read endpoints and hash lookup; the Studio should still use bounded provider adapters and existing acquisition authority.
- Civitai file scanning/hashing implementation notes: https://github.com/civitai/civitai/blob/main/docs/features/model-file-scanning.md

Provider APIs and pages are untrusted external inputs. A returned version or hash match does not establish terms, local compatibility, installation or promotion.

## Identity, style and adapter research watchlist

- WithAnyone, controllable and ID-consistent image generation: https://github.com/Doby-Xu/WithAnyone
  - ICLR 2026 project with code/checkpoints and community ComfyUI support; exact backbone, terms, anime fit and Radeon resources remain unresolved.
- AnimeAdapter, pose-aware zero-shot anime character generation: https://arxiv.org/abs/2605.20237
  - May 2026 paper; the paper states that code, weights and dataset will be released upon acceptance, so this is paper-only watchlist evidence.
- AnyStyle, image-guided style transfer: https://github.com/Yvan1001/AnyStyle
  - 2026 research route combining a style LoRA and structural guidance; exact local assets and comparative value remain unresolved.

## Training and finishing

- OneTrainer: https://github.com/Nerogar/OneTrainer
- kohya-ss sd-scripts: https://github.com/kohya-ss/sd-scripts
  - Current repository documents Anima support, Anima LoRA/LLLite work and `torch.compile` improvements. Pin a version and reproduce known validation/precision behavior before use.
- T-LoRA: https://github.com/ControlGenAI/T-LoRA
  - AAAI 2026 single-image personalization method with SDXL/FLUX and PEFT/multi-adapter work; official setup is Linux/NVIDIA-oriented and is not an Anima/Radeon result.
- Concept Sliders: https://arxiv.org/abs/2311.12092
- Real-ESRGAN: https://github.com/xinntao/Real-ESRGAN

Training recommendations are model- and runner-specific. Super-resolution can invent or remove detail and remains a separately reviewed derivative.

## AMD/runtime

- AMD Radeon Windows ROCm compatibility: https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/compatibility/compatibilityrad/windows/windows_compatibility.html
- AMD Radeon Linux compatibility: https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/compatibility/compatibilityrad/linux/linux_compatibility.html
- ComfyUI Desktop/runtime documentation: https://docs.comfy.org/installation/desktop

The Windows matrix lists RX 9070 XT support for the current PyTorch/ROCm combination while noting that the complete ROCm stack is not available on Windows. Treat each application and custom node separately.

## Existing repository evidence

Consult, in order:

- `CURRENT_STATE.md`;
- `docs/prompt-studio/`;
- `docs/workflow-studio/`;
- `docs/character-consistency/`;
- `docs/repair-studio/`;
- `experiments/curated/style-pose-matrix/`;
- live issues #9, #10, #14, #21, #35, #37, #38, #65, #66, #71, #72, #118–#123, #144, #178, #232, #243–#257, #302, #313, #343, #356, #357, #403–#413, #432 and #433.

Executed local evidence outranks a general source recommendation for the exact installed route. It does not generalise to another version, quantisation or graph.
