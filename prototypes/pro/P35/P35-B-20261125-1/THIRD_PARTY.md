# Third-party terms and provenance

This package contains original Python/JSON/documentation, four exact graphs already in this repository, and authored proposals based on published node schemas. It vendors no external executable code, model weights, images or dataset. The test/calibration fixtures are authored synthetic numbers and non-image bytes. The pinned repository has no root LICENSE file; this work does not invent a new repository-wide licence.

The code uses Python's standard library only (Python Software Foundation License Version 2, with the standard distribution's notices). Existing Studio runtime dependencies are unchanged. Current graph nodes depend on the owner's separately installed ComfyUI (GNU GPL v3) and city96 ComfyUI-GGUF (Apache-2.0); those projects are not copied or installed here.

Terms below identify upstream declarations and gaps, not a determination of owner eligibility or cleared asset rights. Exact inventory hashes are in `routes.json`; the report's `route-components-existing.json` preserves historical source records. A content hash proves byte identity, not lawful provenance. Each reference image and generated asset retains separate rights evidence.

| Component | Named upstream terms | Qualification gap |
| --- | --- | --- |
| FLUX.2 Klein 4B weights | Apache-2.0 | Preserve the exact FP8 conversion's provenance and notices. |
| Qwen3 4B / 8B encoders | Apache-2.0 | Current Comfy repack identity is separate from the original model card. |
| FLUX.2 Klein 9B / Unsloth GGUF conversion | FLUX Non-Commercial License v2.1 for the model; output provisions are distinct | Quantization does not replace original terms. Some source revisions remain `main`. |
| FLUX.2 autoencoder | Official upstream autoencoder: Apache-2.0 | The installed-copy library record leaves provenance/licence unconfirmed; do not promote it from the upstream declaration. |
| Copy Pose `KleinBase9B_PoseTransfer` | Creator's Civitai non-commercial description and use flags, retained September source snapshot; no established SPDX identifier | Current source page could not be reverified. Base-trained adapter on a distilled backbone remains a compatibility question. |
| Qwen-Image-Edit-2511, Qwen2.5-VL encoder, Qwen image VAE | Apache-2.0 upstream declarations | Retain exact conversion/repack byte identities. |
| Exact 2511 Lightning four-step adapter | Apache-2.0 | Four-step adapter results do not establish the base model's 40-step quality. |
| Prospective Qwen-Image 2.1 generator / VAE | Qwen Research License Agreement | Do not inherit Apache-2.0 from older Qwen image models. Owner terms and exact new component bytes remain unresolved. |
| Prospective FLUX 3 Image Klein weights | FLUX Kommunity License v1.0 | Conditions and owner eligibility remain unresolved. Code/encoder/prompt-upsampler licences are separate. |
| FLUX 3 inference code, Qwen3-VL encoders / prompt upsampler as separately declared | Apache-2.0 | Not vendored; prospective runtime/schema/AMD feasibility remain unqualified. |

Research-only alternatives name their own terms in the report: IP-Adapter implementation GPL-3.0 versus weight Apache-2.0; LAION vision encoder MIT; Depth Anything V2 Large weights CC-BY-NC-4.0 versus Small Apache-2.0. None is added to this run's four-route portfolio. No third-party image dataset is used.

## Source locations

The complete dated source ledger is `docs/programmes/systems/research/pro/P35/P35-B-20261125-1/source-ledger.json` at repository root. Relevant primary locations include:

- [Python licence](https://docs.python.org/3/license.html)
- [ComfyUI licence](https://github.com/Comfy-Org/ComfyUI/blob/master/LICENSE)
- [ComfyUI-GGUF licence](https://github.com/city96/ComfyUI-GGUF/blob/main/LICENSE)
- [FLUX.2 Klein 4B](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B)
- [FLUX.2 Klein 9B](https://huggingface.co/black-forest-labs/FLUX.2-klein-9B)
- [FLUX.2 inference/autoencoder repository](https://github.com/black-forest-labs/flux2)
- [Qwen-Image-Edit-2511](https://huggingface.co/Qwen/Qwen-Image-Edit-2511)
- [Qwen Image Lightning](https://huggingface.co/lightx2v/Qwen-Image-Edit-2511-Lightning)
- [Qwen-Image 2.1](https://huggingface.co/Qwen/Qwen-Image-2.1)
- [FLUX 3 Image Klein](https://huggingface.co/black-forest-labs/flux-3-image-klein)

Web `main`/`master` records are dated research snapshots. Freeze actual resolved revisions, downloaded hashes, notices and installed node schema before a new runtime condition is adopted.
