> Migrated research snapshot from 11 September 2026. Use [Start here](../START-HERE.md) and [current state](../../CURRENT_STATE.md) for the new repository. Original workspace commands below are historical.

> Current broad-use workflow catalogue and newer model findings: see Workflow-Library-and-Strategy.md. Exact per-workflow runs: Workflow-Verification.json.

# Model options and local control

11 September 2026. This is a practical shortlist for an RX 9070 XT with 16GB VRAM and 32GB system RAM, not an exhaustive ranking of every published image model.

## More than Qwen

| Family | Approximate main model size | Assessment for this machine |
|---|---:|---|
| SDXL and specialized checkpoints | 2.6B | Already demonstrated. Strong starting point for illustration workflows and explicit pose/reference conditioning. Animagine XL 4.0 Opt was selected for the anime experiment. |
| Z-Image Turbo | 6B | Installed BF16 weights; measured execution state is in Expansion-Status.md. |
| SD3.5 Large | 8B | A different Stable Diffusion architecture. Quantized/offloaded configurations are candidates; not installed or AMD-tested here. |
| FLUX Klein 9B | 9B | A possible quality comparison, with different encoder requirements and gated model terms. Not installed. |
| FLUX.1 dev / schnell | 12B | Quantized ComfyUI configurations are plausible candidates; not tested here. Schnell and dev have different licenses and sampling tradeoffs. |
| HiDream-I1 | 17B | Another heavyweight generator. Additional text encoders increase the memory/setup burden; not installed. |
| Qwen Image / Image Edit | 20B | Generation and editing are different checkpoints. The installed Q4 experiment is Image Edit 2511, not the general text-to-image checkpoint. |
| FLUX.2 dev | 32B | Larger still. Aggressive quantization/offload and its encoder make this a difficult fit, especially with 32GB RAM. Not an everyday recommendation or a verified local capability. |

Sizes exclude auxiliary encoders and are not directly comparable to VRAM usage. The statement that an untested quantized model is a candidate is an engineering estimate, not a compatibility guarantee.

Quantization reduces weight storage but does not guarantee faster inference. Kernel support, dequantization, CPU/GPU transfers, image resolution and reference-image token counts all matter. Qwen Q4's first observed steps took approximately three minutes each on this setup. The four-step Lightning test trades some quality for fewer steps; it should not be interpreted as a comparison of each model at its maximum quality setting. Z-Image BF16 took 275.405 seconds in its first 1024² test, while the established FLUX 4B cached-prompt run took about four seconds. These different workflows are feasibility measurements, not a controlled quality ranking.

Primary references: [SD3.5 Large](https://huggingface.co/stabilityai/stable-diffusion-3.5-large), [FLUX.1 dev](https://huggingface.co/black-forest-labs/FLUX.1-dev), [FLUX.1 schnell](https://huggingface.co/black-forest-labs/FLUX.1-schnell), [FLUX.2 dev](https://huggingface.co/black-forest-labs/FLUX.2-dev), [HiDream-I1](https://huggingface.co/HiDream-ai/HiDream-I1-Full), [Qwen editor](https://huggingface.co/Qwen/Qwen-Image-Edit-2511).

## Which is highest quality?

There is no single winner independent of the job. Judge brief adherence, character identity, pose correctness, typography, surface detail, latency and cleanup time separately. A smaller specialized illustration model can be the better choice for anime art, while a larger editor can be more useful for a complex material change.

For the supplied character sheets, prioritize an anime SDXL checkpoint and pose/reference controls, plus an editor for local revisions. Animagine XL 4.0 Opt is based on SDXL and uses tag-oriented prompts. Its publisher recommends approximately 28 Euler ancestral steps and CFG 5; the model carries Open RAIL++ terms. It is not automatically a pixel-art model or a reliable animation generator. [Animagine model card](https://huggingface.co/cagliostrolab/animagine-xl-4.0).

Our FLUX passing-pose experiment preserved broad identity but failed the requested leg pose and changed the visual style. That is direct evidence that increasing output resolution or repeating the same prompt is not a sufficient animation strategy.

## What local control means

The saved local ComfyUI generation graphs have no separate content-filter node and do not submit prompts/images to a hosted image-generation service. API/cloud nodes are disabled in the server launch configuration. This differs from a hosted service that evaluates each request before generation.

Three distinctions still matter:

- **Pipeline filters:** optional executable filtering components around inference. The saved graphs do not include one.
- **Learned model behaviour:** training influences what a model can or tends to generate. Removing an external filter does not remove those learned tendencies or make every request achievable.
- **Terms and assistance:** model licenses apply independently of local execution, and the assistant's own safety limits still apply to assistance. Local installation is not a promise of unrestricted assistance or unrestricted licensing.

No safety-filter removal or “uncensoring” modification was made in this task. The ordinary local generation workflows are available for creative work. Do not infer that every model in the table has identical content behaviour or commercial terms.

FLUX dev-family model-use terms and output-use terms are distinct; its model card explicitly discusses commercial use of outputs under its license. Avoid treating a non-commercial model-license label as a complete explanation of output rights. HiDream's main weights and auxiliary encoders also carry different licenses. Read the exact selected component terms when moving from experimentation to distribution.
