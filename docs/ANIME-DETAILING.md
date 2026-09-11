# Anime detailing and upscaling

## What is installed

The **Anime quality** category now includes these finishing workflows. ComfyUI has been restarted while idle, and all required nodes are active. Refresh Asset Studio to load the new presets. If a future installation reports a missing node, restart ComfyUI only after its queue is empty.

| Studio preset / ComfyUI workflow | Use |
|---|---|
| 25 - Anime ESRGAN 2x | Upload a chosen image. RealESRGAN's anime 4x model enlarges it, then Lanczos reduces it to a final 2x size. No prompt or diffusion step. |
| 26 - WAI Auto Face Detail | Upload a WAI image and paste its original prompt. Detect faces and resample enlarged crops at denoise 0.28. Saves image and mask. |
| 27 - WAI Auto Hand Detail | Upload a WAI image. Optional hand crop resampling at denoise 0.40; always inspect the result and mask. This is not guaranteed finger correction. |
| 28 - Animagine Auto Face Detail | Same face workflow using Animagine XL 4.0 Opt. Prefer this for an Animagine source to reduce style drift. |
| 29 - WAI Portrait Face and ESRGAN | Generates a base portrait, refines detected faces, then produces a 2x export. Saves base, face pass, final and mask separately. |

Do not feed the black-and-white mask image back into the refinement preset by accident. It is a diagnostic output. The original source image remains unchanged.

The standalone finishing presets use a placeholder lantern image only so the graph has a valid input on installation. **Upload your chosen anime image and replace the prompt with its original prompt before running.** There is no face/hand in the placeholder, so an unchanged image with an empty mask is expected, not a software failure. The combined workflow has a complete adult evening-dress portrait prompt already set.

For workflow 29, Studio's steps/CFG/denoise edit the **base** KSampler. The face pass has separate settings in ComfyUI's FaceDetailer node. The seed changes both passes, preserving reproducible batch recipes. Face/hand standalone presets expose their own steps/CFG/denoise directly. Pure ESRGAN has no seed or prompt because it does not sample diffusion noise.

## Settings worth understanding

- **Face denoise 0.28:** a restrained starting point. Lower toward 0.15-0.20 if identity changes; higher toward 0.35 if correction is too weak. These are starting suggestions, not measured optimal values.
- **Hand denoise 0.40:** gives more room to redraw structure. It can still invent fingers or change a prop. If repeated attempts fail, use the manual mask/crop workflow or a pose reference instead of repeatedly increasing strength.
- **Detection threshold 0.5:** how confident the detector must be. Lower can find missed faces/hands but admits false positives. It does not measure anatomical correctness.
- **Guide size 512 / max size 1024:** the detected crop is enlarged for resampling, capped at the maximum. Increasing these can help small details but costs memory and time. Guide size is not the whole image's export size.
- **Crop factor:** 3.0 for faces; 2.5 for hands. Includes surrounding context, which helps lighting and pose interpretation. A tight isolated fingertip provides poor context.
- **Mask dilation 8:** expands the detected edit area. **Feather 12** blends its boundary; excessive feather can spill edits into nearby features.
- **Noise mask enabled:** limits sampling to the region. No SAM model is required for these bbox-based workflows. Some SAM compatibility fields remain visible but have no connected SAM model.
- **Force inpaint enabled:** processes detections even when the original crop is already sufficiently large. **Cycle 1** avoids repeatedly reworking the same region.
- **ESRGAN output scale:** the learned model itself is fixed at 4x. The ImageScaleBy node's 0.5 setting makes final output 2x. Set 0.25 for original-size cleanup or 1.0 for a 4x export. The model can alter line texture and smooth pixel art; use nearest-neighbour for pixel-perfect sprites.

The face and hand detectors look for regions; the selected image checkpoint does the redraw. Neither detector is a hand-anatomy repair model. An empty mask means no region was accepted at the current threshold. Inspect masks before changing unrelated prompts.

## Gemini advice: what carries over, what changes

- **Useful:** model-specific tags, native-resolution base generation, selecting a good composition, cropped detail refinement, and a learned anime upscaler. These are now represented in saved workflows.
- **Interface correction:** ADetailer is a Stable Diffusion WebUI extension. For this ComfyUI installation, the equivalents are Impact Pack's detailer nodes plus Impact Subpack's Ultralytics detector provider. Installing ADetailer itself here would not supply those nodes.
- **Denoise correction:** 0.35-0.5 is not a promise of preserving composition. It can redraw identity, clothing and pose. Pure ESRGAN upscaling and diffusion-based high-resolution refinement are separate operations; the former has no denoise setting.
- **Prompt correction:** rating/content tags are not quality tags. Use the vocabulary of the exact checkpoint, rather than copying Pony, Animagine and WAI tags into one prompt. The installed Animagine 4.0 Opt preset uses its own documented quality suffix and settings; the cited 3.1 guide is for another version.
- **LoRA correction:** 0.5-0.8 is a starting range, not a compatibility rule or universal sweet spot. Choose a LoRA for the correct architecture and, ideally, the checkpoint family; follow its author instructions. A pose/concept LoRA biases output but does not enforce precise joints. Use ControlNet for spatial guidance.
- **Batch correction:** prefer Studio's serial batch count over increasing EmptyLatentImage's simultaneous batch_size. It provides candidate selection without multiplying the per-batch VRAM requirement.

No arbitrary artist, character or pose LoRA was downloaded just to fill a slot. Existing pixel-art LoRA workflows remain available. For a new anime LoRA: place the verified weight in `ComfyUI/models/loras`, refresh the model list, add **Load LoRA** between CheckpointLoaderSimple and the sampler/text encoders, and connect both its MODEL and CLIP outputs. Start with one adapter and compare strength 0 versus the author's recommended strength at the same seed. Workflow 20 is an installed example of the loader wiring, but its pixel-art adapter is not an anime anatomy fix.

## Installation and reproducibility

Impact Pack and Impact Subpack are pinned to exact Git commits in `models/anime-detailing-install.json`. Small detector weights are pinned to a Hugging Face commit with matching SHA-256. The anime upscaler comes from Real-ESRGAN's official release; its local checksum is recorded without claiming an independently published checksum comparison.

Added Python packages were installed with pinned versions and `--no-deps`, followed by a complete `pip check`, to avoid replacing the working ROCm Torch stack. SAM2 is optional and was not installed; the SAM package is required by Impact Pack's imports, but no SAM weights are needed by these workflows. The node installers' optional automatic model-download routines were not run. No detector whitelist exception was added.

The separate CPU smoke check completed small upscaling and detector loading/forward passes without running image-diffusion generation. Both detectors produced non-empty masks on the existing WAI example, and a 32px synthetic image became 128px. The probe was stopped after the test. Graph schema checks do not prove that face or hand resampling improves an image. See CURRENT_STATE.md for the final activation and verification status.

## Sources

- [ComfyUI upscaling guide](https://docs.comfy.org/tutorials/basic/upscale)
- [Real-ESRGAN anime model guide](https://github.com/xinntao/Real-ESRGAN/blob/master/docs/anime_model.md)
- [Impact Pack documentation and example workflows](https://github.com/ltdrdata/ComfyUI-Impact-Pack)
- [Impact Subpack](https://github.com/ltdrdata/ComfyUI-Impact-Subpack)
- [ADetailer documentation](https://github.com/Bing-su/adetailer)
- [Animagine 4.0 author instructions](https://huggingface.co/cagliostrolab/animagine-xl-4.0)

[HUMAN_TODO.md](../HUMAN_TODO.md) records optional art choices. No subjective quality acceptance has been inferred from successful installation.
