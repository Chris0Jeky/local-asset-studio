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
  - Experimental watchlist derivative; preview and inherited licence status.
- NewBie Image: pin the exact official model repository before promotion. Discovery/card claims remain unresolved in the route manifest until that identity is reviewed.

## Conditioning, geometry and masks

- Tencent AI Lab, IP-Adapter: https://github.com/tencent-ailab/IP-Adapter
- IDEA Research, DWPose: https://github.com/IDEA-Research/DWPose
- ControlNet Auxiliary Preprocessors for ComfyUI: https://github.com/Fannovel16/comfyui_controlnet_aux
- Meta, SAM 2: https://github.com/facebookresearch/sam2
- ComfyUI documentation and source: https://docs.comfy.org/ and https://github.com/Comfy-Org/ComfyUI
- ComfyUI IPAdapter Plus: https://github.com/cubiq/ComfyUI_IPAdapter_plus

These projects describe capabilities, not support in the installed Studio environment. Exact commits, model files, preprocessing and runtime compatibility remain qualification inputs.

## Training and finishing

- OneTrainer: https://github.com/Nerogar/OneTrainer
- kohya-ss sd-scripts: https://github.com/kohya-ss/sd-scripts
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
- live issues #9, #10, #14, #21, #35, #37, #38, #65, #66, #71, #72, #118–#123, #144, #178, #232, #243–#257, #302, #313, #343 and #357.

Executed local evidence outranks a general source recommendation for the exact installed route. It does not generalise to another version, quantisation or graph.
