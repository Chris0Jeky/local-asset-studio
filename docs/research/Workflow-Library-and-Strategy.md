> Migrated research snapshot from 11 September 2026. Use [Start here](../START-HERE.md) and [current state](../../CURRENT_STATE.md) for the new repository. Original workspace commands below are historical.

# Workflow library for games, products and websites

Updated 11 September 2026. Your priorities are a mix of pixel art, abstract and stylized assets, realistic promotion, website customization, and reference edits. Slow batch generation is acceptable. This library deliberately covers those different needs.

## Choose by deliverable

| Work | Start with saved ComfyUI workflow | Finish and acceptance check |
|---|---|---|
| Pixel props and inventory icons | 12 - SDXL Pixel Prop Concept | Reduce to the actual 32/64/128px target, unify palette, clean individual pixels in Pixelorama; a pixel-style 1024px image is not a finished pixel asset |
| Animated pickups, rotations, mechanically consistent sprites | Lanternkeeper Blender scene and render script | Transparent frames, fixed camera/pivot, shared palette, atlas and engine playback; this complete example already exists |
| Illustrated characters | 07 Animagine; 15 Pony | Approve one reference, then matching family LoRAs/reference conditioning; inspect costume, proportions and silhouette |
| Hobby character experiments | 14 NoobAI | This exact 1.1 release has explicit noncommercial terms covering generated products; keep it out of commercial deliverables |
| Explicit body poses | 08 Animagine Pose Control | Compare skeleton/limbs and identity separately; ControlNet is a conditioning tool, not a standalone image generator |
| Abstract decorative website artwork | 11 SDXL Abstract Website Art | Crop responsively, verify text contrast, export WebP and keep real text in HTML |
| Stylized inventory props | 13 SDXL Stylized Inventory Prop | Isolate alpha, normalize scale and lighting, export named files and atlas metadata |
| Realistic product concepts | 09 RealVis Product Photography or 05 Z-Image Turbo | Check geometry and reflections; for a real product use its actual reference/render rather than invented details |
| Realistic website photography | 10 RealVis Website Banner | Inspect the actual mobile/desktop crop, focal point and headline clearance |
| Fast concept exploration | 02 FLUX Klein Starter | Generate several independent seeds; select against the brief |
| Fast reference edits | 03 FLUX Image Edit | Compare against source; composite only the approved masked region when pixels outside it must remain exact |
| Gentle variants | 17 SDXL Gentle Reference Variation | Starts at denoise 0.30; raising it increases freedom and identity drift |
| Difficult instruction edits | 06 Qwen Edit 20B Q4 | Four-step Lightning is the tested feasibility path; slow on this machine |
| Longer quality experiment | 16 Qwen Slow Quality Edit | 40 steps, CFG 4, Lightning removed; prepared, not benchmarked. Do not estimate duration by multiplying the four-step timing: guidance changes compute too |

All numbered workflows are saved in ComfyUI and provided as visual and API JSON in Expanded-Workflows. Refresh the frontend model list after downloads. See Workflow-Verification.json for individual execution state, rather than assuming every preset has been rendered.

## Local control

These saved graphs contain local generation and image-processing nodes, with no hosted generation call or prompt/output moderation node. Their example prompts and negative prompts are ordinary editable text, not an enforcement layer. There is no blanket promise that any model can render every requested concept: training, checkpoint choice and conditioning still determine its capabilities. Model-use terms are separate from runtime filtering. This is a general creative workstation, not an Unstable Diffusion service integration.

## Sprite production workflow

Choose a target size and camera before generating. Approve a single clean design. Author distinct contact, down, passing and up poses; use pose guidance or a Blender rig for consistency. Generate/edit each frame separately, review the silhouette and clothing, then remove backgrounds and align ground-contact pivots. Preview the loop at final size before packing. Export frame durations, anchors and collision metadata with the PNG atlas.

A generated sheet can contain misleading labels, duplicate poses, variable scale and baked backgrounds. The supplied second sheet says eight walk frames but visibly contains nine. Both tested background-removal models failed on its tiny blue-on-blue crops. The extraction remains a review draft. Interpolation alone cannot supply missing anatomy or create correct gait mechanics.

## Practical batch recipes

Use run-batch.py with a named job folder. It saves the submitted graph and prompt ID before waiting, preserves history, and resumes existing IDs on a rerun. It submits one job at a time and waits for existing ComfyUI work. Example:

```powershell
py -3.13 'C:\Users\jekyt\Documents\Codex\2026-09-11\i\outputs\Expanded-Workflows\run-batch.py' --graph 'C:\Users\jekyt\Documents\Codex\2026-09-11\i\outputs\Expanded-Workflows\abstract-api.json' --out 'C:\Users\jekyt\Documents\Codex\2026-09-11\i\outputs\Batches\abstract-first' --count 4 --seed 4200
```

Use a different job folder when changing a prompt or graph. Start with four seeds for concepts, one for expensive edits. Run only one batch runner at a time; ComfyUI remains the GPU queue authority. Avoid concurrent Blender GPU rendering. All outputs are candidates until reviewed. A long job may continue on the server after the runner times out; rerun the same folder to resume, not a new folder to duplicate it.

## Assessment of the pasted shortlist

- WAI: official Civitai API returned HTTP 451. Following your suggestion, WAI v17 was selected from a Hugging Face mirror. Two mirror repositories advertise the same SHA-256; the installer verifies the downloaded bytes. This is mirror agreement, not independent creator authentication, and mirror license labels are not authoritative. Workflows 18 (illustration) and 19 (pose control) are prepared. See WAI-Mirror-Provenance.json and Workflow-Verification.json for current evidence. [Selected mirror](https://huggingface.co/frankjoshua/waiIllustriousSDXL_v170).
- NoobAI: the installed candidate is standard NoobAI-XL 1.1, not the separate V-pred release. The author's recommended Euler ancestral, 25–30 steps and CFG 5–6 are used. Its additional terms explicitly prohibit commercialization of model-generated products. [Author's card](https://huggingface.co/Laxhar/noobai-XL-1.1/raw/main/README.md).
- Pony: another SDXL ecosystem, useful for compatible character/style LoRAs. LoRAs for Pony, Illustrious, SDXL base, FLUX and Qwen are not freely interchangeable. [Author's weights](https://huggingface.co/AstraliteHeart/pony-diffusion-v6).
- RealVisXL: a dedicated photorealistic SDXL option, using the author's DPM++ SDE/Karras 30+ step recommendation. [Author's card](https://huggingface.co/SG161222/RealVisXL_V5.0).
- HiDream-O1 is an 8B unified model, distinct from the older 17B HiDream-I1. Its official instructions target CUDA, flag PyTorch 2.9.x issues, and recommend Flash Attention or a code change. The current working AMD runtime uses PyTorch 2.9.1, so this requires a separate compatibility experiment; it is not installed or declared impossible. [Official model](https://huggingface.co/HiDream-ai/HiDream-O1-Image).
- Ideogram 4 is a real open-weight release, but the documented NF4 path is CUDA-specific, weights are gated, and default CLI prompting and screening involve hosted services. The repo lists FP8 separately; Radeon feasibility is untested. Its weights have separate noncommercial terms. It is not the first addition for this local AMD production stack. [Official repository](https://github.com/ideogram-oss/ideogram4).
- The pasted numeric ratings and universal runtime-freedom stars are not measured results on this PC. Large parameter count and long sampling do not guarantee better sprites or accurate edits.

## Expansion priorities

1. Use the installed library to compare the same concrete brief across appropriate models, recording useful output rate and wall time.
2. Add reference-conditioned pose generation and masked repair to the strongest illustration candidate. A matching character LoRA is justified after a recurring design exists.
3. Build reusable material/lighting setups in Blender for consistent props, orthographic sprites and product mockups.
4. Add a verified tiling workflow, depth guidance and a dedicated upscaler when a real deliverable needs them. Seamless texture production is not yet verified.
5. Trial HiDream-O1 in a separate AMD-compatible environment without replacing the working ROCm installation. Ideogram and larger FLUX variants remain separate feasibility candidates.

The immediate bottleneck is consistency and finishing, as well as generation quality. This library provides multiple models and controllable workflows while keeping each result's verification status explicit.

## Runtime finding

A Qwen-to-SDXL transition produced a native access violation (0xC0000005). Restarting the server allowed subsequent SDXL and ControlNet renders to complete. For now, group long Qwen work together and restart ComfyUI between that group and SDXL work after the queue is empty. The cause and a permanent fix remain unverified.

A community HiDream-O1 ComfyUI implementation supports SDPA attention and FP8 loading and reports roughly 10–11GB VRAM for FP8. This gives a plausible AMD experiment, not a verified result on this machine; it also repeats the PyTorch 2.9.x warning. [Node author's documentation](https://github.com/Saganaki22/HiDream_O1-ComfyUI).

## Visual findings from the first samples

The SDXL abstract sample rendered in 18.69 seconds and makes useful decorative artwork, but did not keep the requested left side empty. The pixel-prop sample rendered in 14.057 seconds and reads as a treasure chest, but is high-resolution pixel-style illustration with uneven pixel scale, loose objects and a baked background. It requires deliberate reduction and cleanup. Neither is labelled ready for deployment solely because rendering succeeded.

The pose-guided Animagine sample changed the leg arrangement toward the authored bent-leg guide. It is taller and stylistically different from the supplied chibi sprites, so it demonstrates pose influence rather than a drop-in animation frame.

All 20 saved visual workflows are also collected in ComfyUI-Workflows for import/backup.

## Experiment guide

See Experimenting-and-Evaluating-Models.md for controlled comparisons, scorecards, specialist selection and the later FLUX.2 dev 32B trial. Workflow 20 adds the installed Pixel Art XL LoRA and a 128px export; its first generation and resumable batch execution passed.
