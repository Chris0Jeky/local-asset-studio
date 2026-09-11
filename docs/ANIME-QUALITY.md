# Anime quality: compose, refine, repair

## Start in two clicks

Open **Asset Studio** from the desktop (http://127.0.0.1:8191), refresh the page, and select category **Anime quality**.

- **Anime WAI Portrait**: WAI v17, 832 x 1216, 30 steps, CFG 5, Euler ancestral / normal. A practical starting recipe, not a claim of defect-free results.
- **Anime Animagine Portrait**: Animagine XL 4.0 Opt, same composition, 28 steps, CFG 5. Its author documents these sampler/CFG/step defaults. Use this as an alternative aesthetic, not merely a fallback.
- **Anime Refine 1.5x**: upload your chosen image, paste its original prompt and negative prompt, then generate. Defaults to WAI and 0.22 denoise. For an Animagine source, use workflow 23 in ComfyUI and switch its checkpoint to Animagine first.

These are intended for clearly adult, non-explicit character art and costume exploration. All use your existing local models. No new generation was submitted while preparing them. The presets are deliberately marked not rendered; earlier versions of the base WAI and Animagine graphs have run successfully.

For deeper control, ComfyUI at http://127.0.0.1:8188 has saved workflows **21 through 24**. Find them in its Workflows sidebar. The same editable JSON files are in `workflows/comfyui/`; API JSON under `workflows/api/` is for scripts, not the ordinary canvas importer.

## A useful first prompt

The preset already contains a complete portrait prompt. Example subject tags you can substitute:

```
1girl, solo, adult woman, mature female, original character,
silver hair, blue eyes, looking at viewer, upper body,
elegant black evening dress, bare shoulders, relaxed pose,
soft lighting, simple background
```

Costume variations: `halter top, long skirt, gold jewelry`; `swimsuit, beach, sun hat`; `cropped jacket, high-waisted shorts, boots`; or `off-shoulder dress, embroidered fabric`. Replace the costume rather than appending mutually contradictory outfits. The token `1girl` is an anime subject-count convention; specify an adult subject separately.

For WAI, the preset adds `masterpiece, best quality`. For Animagine, it uses the author's quality suffix: `masterpiece, high score, great score, absurdres`. These are learned style/quality cues, not resolution controls or anatomical guarantees. Pony uses a different score-tag vocabulary; copying its tags into every other model is not a universal improvement.

A restrained negative prompt is already supplied. `bad hands`, extra-digit and malformed-eye terms are weak preferences, not an anatomical validator. Avoid long copied lists of contradictory terms and heavily weighted tags until you know what each changes.

## What each control actually does

| Control | Start here | What changing it does |
|---|---|---|
| Seed | Keep fixed while comparing settings | Changes the initial noise and therefore composition/details. A new seed can escape a bad hand layout. The same seed across different models does not guarantee the same pose. |
| Resolution | 832 x 1216 portrait; 1024 square | Allocates pixels and changes composition. Very small faces/hands have little detail budget. Generating directly at 2048 can introduce duplication and anatomy problems; use a second pass instead. |
| Steps | WAI 30; Animagine 28 | More denoising iterations, usually more time. Beyond a sensible range, benefits diminish; 80 steps will not reliably repair a malformed skeleton. |
| CFG | 5; compare 4, 5, 6 | Higher values push conditioning harder, sometimes increasing contrast, harsh contours, or artifacts. Lower values can soften the look but lose prompt details. It is not a quality percentage. |
| Sampler / scheduler | Euler ancestral / normal for the portraits | Changes the numerical denoising path and noise schedule. Alternatives can change texture and composition. These controls are on the ComfyUI KSampler node, not the simple Studio form. |
| Denoise for a new image | **1.0** | Start from noise. Lowering it on an empty latent is not the same as improving an existing image. |
| Denoise for refinement | **0.22**, explore 0.15–0.30 | Lower preserves more; higher redraws more and can change face, costume, or identity. Upscaling first provides a larger canvas, not new true detail by itself. |
| Denoise for masked repair | **0.40**, explore 0.25–0.55 | Lower makes subtle corrections; higher can reconstruct structure but depart from the original. These are starting ranges, not measured optima. |
| LoRA strength | None initially | Higher strength gives a stronger learned concept/style, potentially distorting anatomy or overpowering the checkpoint. Add one architecture-compatible LoRA at a time. |
| Batch | 1–4 in Studio | Produces separate candidates serially, with incremented seeds. It does not increase one image's quality. |

Do not add SDXL's generic refiner, a V-prediction switch, CLIP-skip hacks, or multiple detail LoRAs simply because an unrelated workflow used them. They change the model's expected processing. The new graphs load the checkpoint's own CLIP and VAE through **CheckpointLoaderSimple**.

## Eyes and hands: the finishing workflow

A good final image can involve selecting a strong base, local redrawing, detail refinement, and manual cleanup. A gallery shows selected outputs; it does not establish an author's failure rate or prove that every image was a one-pass generation. There is no evidence here for one universal secret model.

1. Start with one character and a readable pose. Use an upper-body composition when the face matters. Avoid tiny full-body figures during a face-quality comparison.
2. Choose a base for anatomy and composition, not only texture. If the entire pose is wrong, try a new seed or your existing pose workflow before investing in detail.
3. Open **24 - Anime Masked Repair** in ComfyUI. Select the checkpoint used for the original image. Upload the chosen PNG into **UPLOAD YOUR IMAGE AND PAINT MASK**. Replace the demo image before running.
4. Open that Load Image node's mask editor from its context menu. Paint the area to replace and save the mask back to the node. A plain opaque upload has an empty edit mask and will produce no visible correction. Use the editor's soft brush edge to blend the repair.
5. For eyes, mask the face with enough surrounding context, often both eyes together. For a hand, include the whole hand and wrist, not just an extra fingertip. Keep pose and lighting described in the prompt. Try one local correction at a time.
6. Run, compare, and save only a better result. If the region is extremely small, a full-image mask does not provide extra detail resolution: crop a working copy around the hand/face in Krita, enlarge it, repair that crop, and paste/blend it back. Keep the untouched original.
7. Use **23 - Anime Refine 1.5x** only after the anatomy is acceptable. Paste the source prompt. Its scale is in ImageScaleBy; the simple Studio form exposes denoise but not the scale multiplier.

The repair graph is **LoadImage -> VAEEncode -> SetLatentNoiseMask -> KSampler -> VAEDecode -> ImageCompositeMasked -> SaveImage**. The final composite restores the original where the mask is zero, instead of saving the full VAE reconstruction. Soft-mask boundaries blend source and repair. Use source dimensions divisible by 8; other sizes may be cropped internally by the VAE. Pixel preservation is a graph design property here, not a newly executed image-comparison test.

The repair workflow is ComfyUI-only because the simple Studio does not yet offer a mask painter. It deliberately uses installed core nodes: no detector downloads or environment upgrades are necessary. It is manual masked img2img, not a dedicated inpainting model and not an automatic hand anatomist.

## What about ADetailer / FaceDetailer?

Automatic detection plus cropped resampling is a real and useful workflow family. ADetailer belongs to the WebUI ecosystem; ComfyUI's Impact Pack provides detailers and related detector/segmentation tools. These can improve small faces by resampling a larger crop, but a detector finding a hand does not mean the model knows the correct fingers. They can also alter identity or miss stylized faces. They were researched but are **not installed or configured in this quick slice**. Manual repair is available now; an automatic detailer would be a separate tested addition.

The Animagine authors explicitly list complex hand poses and finger counting as limitations. A high-quality checkpoint is a starting point, not a guarantee.

## Downloads started for broader experiments

Pinned revisions, filenames, expected bytes and SHA-256 values are in `models/next-downloads.json`:

- **FLUX.2 dev 32B Q4_K_M**: 20.08 GB. A higher-memory, general image-generation/editing experiment. It will need offloading; successful loading/inference on this AMD setup is not established.
- **Mistral Small 3.2 24B Q4_K_M**: 14.33 GB. The companion text encoder linked by the FLUX GGUF model card, not a second image generator. Installed-node compatibility still needs a focused run.
- **Xinsir Union SDXL 1.0**: 2.51 GB. Additional multi-condition control for future depth/edge/pose experiments; this download is not wired into the new portrait graphs. Your existing OpenPose workflow already has its separate model.

Total approximately **34.4 GiB**, downloaded serially with checksum verification before installation. Existing FLUX.2 VAE is retained. The queue leaves a 20 GiB free-space reserve per file. These are downloads only: no model switches, generation jobs, package upgrades, or claims that the 32B stack is ready to run. HiDream is already installed; Qwen's slow preset needs testing, not another weight download. No redundant anime checkpoint was added just to increase the model count.

Local status and logs are kept outside Git, under the original workspace's `work/remaining-model-status.json` and `work/remaining-downloads.log`. The process can continue after this chat turn; this is not a scheduled monitor. Failed files remain marked failed and are not installed as usable weights.

## Sources and verification

- [Animagine author instructions and limitations](https://huggingface.co/cagliostrolab/animagine-xl-4.0): tag structure, 28 steps, CFG 5, Euler ancestral, native sizes and hand limitations.
- [Impact Pack project](https://github.com/ltdrdata/ComfyUI-Impact-Pack): detector/detailer workflow capabilities.
- [FLUX.2 GGUF model card](https://huggingface.co/city96/FLUX.2-dev-gguf): encoder/VAE dependencies and quantizations.
- [Xinsir Union model card](https://huggingface.co/xinsir/controlnet-union-sdxl-1.0): multi-condition model for future control workflows.

All four graphs were checked against the running ComfyUI node schemas, available checkpoint names, enum values and link types. The Studio catalog exposes all three new presets. Nine regression tests and the catalog validator passed. **No new images were generated or accepted for quality**, per your request to leave experiments to you. Download completion and inference are separate states.

[HUMAN_TODO.md](../HUMAN_TODO.md) still contains optional creative choices. Pick what looks best to you; successful execution is not subjective approval.
