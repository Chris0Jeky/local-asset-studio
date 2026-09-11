> Migrated research snapshot from 11 September 2026. Use [Start here](../START-HERE.md) and [current state](../../CURRENT_STATE.md) for the new repository. Original workspace commands below are historical.

> September 11 expansion update: the original downloads and FLUX tests completed. See [Asset-Strategy-and-Findings.md](Asset-Strategy-and-Findings.md), [Expansion-Status.md](Expansion-Status.md), and [the Lanternkeeper example](Lanternkeeper/README.md) for the current state. Any pending-download text below describes the earlier installation checkpoint.

# A local asset pipeline for games and products

Research date: 11 September 2026. Tailored to your RX 9070 XT (16 GB VRAM), 32 GB RAM, Windows 11, and your mix of pixel-art games, stylized/abstract assets, and realistic promotional imagery.

**My recommendation:** combine ComfyUI for generation and model workflows, Krita for visual editing, small deterministic export scripts for asset preparation, and Blender for geometry, lighting, and repeatable animation. Build one useful asset pack before adding more models or a larger automation system.

The separate installation guide records actual installation and test results. Following your authorization, Blender 4.5 LTS and Pixelorama have been installed, and the AI Diffusion plugin has been added to your existing Krita. Pixelorama supplies the free pixel-art editing and animation lane; Aseprite remains an optional alternative.

## Choose the tool by the asset

| Your task | Suggested approach | Deliverable |
|---|---|---|
| Pixel-art pickups, props, portraits | SDXL style exploration, then palette and pixel cleanup | RGBA PNG at the actual game resolution |
| Pixel-art character animation | Draw/rig key poses; optionally render a Blender rig; finish at the target pixel grid | Frames, animation tags, common pivots, sprite atlas |
| Stylized inventory icons | Consistent reference and lighting, SDXL or FLUX Klein, then background removal and normalization | Matching transparent icons |
| Abstract website backgrounds | SDXL or Klein, with planned empty space for text | Several responsive crops, optimized WebP/AVIF |
| Exact UI icons and logos | Vector drawing or SVG/code; use generated images for exploration | Editable SVG and raster exports |
| Realistic promotional scenes | Klein or a selected SDXL checkpoint; real screenshots/product renders composited afterward | Accurate product imagery in several layouts |
| Small image changes | Krita selection + inpainting, or Klein edit + a final compositing mask | Original, editable layers, exported revision |
| Sprite-sheet slicing | Grid/rectangle crop script or Aseprite export | Precisely cropped frames and metadata |
| Isometric props and turnarounds | Blender camera/lighting/material template | Repeatable directional PNG renders |
| Textures | Generated concept followed by seam, lighting, and material checks | Texture maps tested on a mesh |

These assignments are my production recommendations, not claims that every generated candidate will be ready to ship.

## The model shortlist

**SDXL: the versatile baseline.** Start with the base checkpoint already selected for installation, then evaluate one style-specific checkpoint or LoRA against your own assets. SDXL's base can run without the optional refiner. I would use it for stylized illustrations, icon concepts, environments, and controlled variations. A pixel-art LoRA can help establish an aesthetic, but the final pixel grid and palette still need checking. [SDXL model card](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0)

**FLUX.2 Klein 4B distilled: the compact generation-and-editing workhorse.** It supports text-to-image and reference-image editing with the same model. The official ComfyUI workflow uses four steps for the distilled version. We selected FP8 weights to reduce memory use; this trades some precision for capacity and must be judged on actual outputs. The 4B model has an Apache-2.0 license. [BFL model overview](https://github.com/black-forest-labs/flux2), [ComfyUI Klein guide](https://docs.comfy.org/tutorials/flux/flux-2-klein)

**Z-Image-Turbo: a later candidate for fast realistic imagery.** Its developer describes a 6B model designed to fit 16 GB consumer GPUs, with eight model evaluations. That makes it worth comparing for promotion and website imagery once the baseline works. Vendor speed figures on other GPUs do not predict your AMD timing. Its model card identifies Apache-2.0 licensing. [Official model card](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo)

**Qwen-Image-Edit-2511: an optional heavier editor.** The developer emphasizes reduced image drift, character consistency, material changes, and industrial-design uses. It is a 20B model, so on your card I would investigate a supported quantized/offloaded configuration only after Klein has shown a specific editing limitation. It is not part of the starter installation. [Official model card](https://huggingface.co/Qwen/Qwen-Image-Edit-2511)

I would postpone large FLUX.2 dev, local video models, and model training. Your first useful improvement is likely better control and asset finishing. More weights alone will not solve sprite alignment, transparency, or consistent animation.

## Small modifications without disturbing everything else

There are three different operations worth keeping distinct:

1. **Exact transformations:** crop, resize, palette swap, recolor through an existing mask, add a real logo, or adjust brightness. Use conventional editing tools or scripts.
2. **Inventive local changes:** replace a sword, repair an object, extend a background. Use inpainting with a selected area and enough surrounding context.
3. **Semantic edits:** change weather, clothing, material, or scene style. Try Klein with an explicit instruction and a reference image.

Krita's AI Diffusion plugin supports selections for fill, expansion, object addition/removal, and background replacement. It also processes blend and denoising masks, so the effective changed region can be wider than the initial selection. [Krita selection documentation](https://docs.interstice.cloud/selections/)

For a strict local edit, my proposed workflow is: retain the original, generate a candidate using context around the mask, then paste the candidate through a final mask onto the untouched original. A pixel comparison outside that final mask can prove that those pixels did not change. Feathering should be an intentional border region. Asking a model to “keep everything else unchanged” is useful guidance, but compositing is how we enforce the boundary.

For a product screenshot, preserve the actual screenshot and its text. Generate a surrounding background or scene, then composite the real interface into it. This keeps shipped UI and product claims accurate and makes later copy changes easy.

Krita can connect to a custom ComfyUI server, but its plugin needs additional tooling nodes and selected supporting models. Its current handbook marks Klein and Qwen edit support experimental. I would connect it to the existing server in a separate, tested setup step, avoiding a second complete model collection. [Custom server setup](https://docs.interstice.cloud/comfyui-setup/), [edit-model support](https://docs.interstice.cloud/edit-models/)

## Pixel art, cutting sprites, and animation

For small games, decide the actual output contract early: for example 32×32 or 64×64 cells, a limited palette, transparent background, common ground line, and a consistent light direction. A detailed 1024-pixel image with a pixel-art appearance is not automatically a clean 32-pixel sprite.

My proposed pixel-art process is: explore a silhouette and design, choose a candidate, reduce it to the intended grid, constrain the palette, clean edge clusters and isolated pixels, then inspect it at 1× and integer zoom. Use nearest-neighbor scaling for the finished pixel asset; avoid a generative upscaler that changes its pixel structure. Pillow exposes cropping, resizing, palette quantization, and compositing for the mechanical steps. [Pillow image API](https://pillow.readthedocs.io/en/stable/reference/Image.html)

For an existing sheet with regular cells, slicing is straightforward. For an irregular transparent sheet, connected components can propose bounding boxes, followed by a preview for detached accessories and overlapping parts. Preserve each frame's original offset or place it on a shared canvas. Independently trimming every frame without storing offsets creates animation jitter.

Aseprite supports batch export, grid splitting, layer/tag exports, atlas packing, padding, edge extrusion, and JSON metadata. This can become a reproducible export step if you choose to use Aseprite. A smaller Python script can handle fixed grids without adding another editor. [Aseprite CLI](https://www.aseprite.org/docs/cli/)

Cutting up an image extracts the poses already present; it does not create the missing in-between poses or reveal parts hidden behind other objects. For animated characters, choose among:

- **Hand-finished keyframes:** good for small pixel-art games and intentional motion.
- **Layered cutout animation:** separate limbs/accessories, place pivots, rig, then render frames.
- **Blender rig to sprites:** use consistent camera, lighting, frame timing, and directions, then apply controlled pixel finishing.
- **Generative frame experiments:** useful for exploration and effects; inspect for changes in anatomy, silhouette, clothing, and frame timing before treating them as game assets.

Sprite-sheet delivery needs more than a PNG: frame order, durations, animation names, and pivots matter. The exact importer should follow your engine once selected. Godot, for example, supports both individual frames and sheets through AnimatedSprite2D, and sheet animation with Sprite2D/AnimationPlayer. [Godot sprite animation](https://docs.godotengine.org/en/stable/tutorials/2d/2d_sprite_animation.html)

## Consistent sets of assets

Create a small style reference containing palette, outline width, camera angle, lighting, texture/detail level, padding, and a few accepted examples. Keep the chosen model, adapters, resolution, and sampling settings fixed across a batch. Start with a contact sheet of a few candidates before generating dozens.

Use reference conditioning for appearance and control images for structure. ControlNet-style workflows can use edges, depth, or pose to guide composition; the control model must match the base architecture. Krita's control layers expose several of these ideas visually. They guide the result and still require inspection. [ComfyUI ControlNet guide](https://docs.comfy.org/tutorials/controlnet/controlnet), [Krita control layers](https://docs.interstice.cloud/control-layers/)

A fixed seed helps repeat an experiment; it is not a character identity lock. For repeated characters, begin with a reference sheet and controlled poses. Consider a character/style LoRA only when repeated production shows that references are insufficient. Use a curated set of images with known provenance for any later training project.

## Blender through Codex

Yes: a practical local route is for Codex to write a Blender Python script, run Blender in background mode, save a `.blend` file, render previews, inspect them, and revise the script. Blender documents background rendering and Python automation. An MCP bridge is optional for this route; it is not required to produce scripted scenes. [Blender command-line rendering](https://docs.blender.org/manual/en/dev/advanced/command_line/render.html), [Blender Python automation](https://docs.blender.org/api/main/info_advanced_blender_as_bpy.html)

Good initial Blender tasks include isometric props, consistent item icons, abstract 3D website compositions, product mockups with exact geometry, material variants, eight-direction character renders, and simple turntable animations. Keep editable geometry and materials in the `.blend` output alongside exported images.

For sprite production, use an orthographic render camera, fixed framing, transparent output, and a stable ground/pivot convention. Blender supports orthographic render cameras independently of the viewport projection. [Blender camera projection](https://docs.blender.org/manual/en/4.2/editors/3dview/navigate/projections.html)

The useful hybrid is: create rough geometry and lighting in Blender, render a reference or depth/edge guidance, use generation where surface appearance needs exploration, and retain the original render for compositing and alignment. For smooth, coherent animation, a rigged source gives us explicit control over motion.

Image-to-3D systems such as Hunyuan3D are another research direction. Their official implementations have their own GPU dependencies and separate shape/texture stages; we have not validated those on this AMD Windows setup. Treat generated meshes as starting material that may need topology, UV, material, scale, rigging, and collision cleanup. [Hunyuan3D repository](https://github.com/Tencent-Hunyuan/Hunyuan3D-2)

## Configuration for this machine

| Workflow | Starting point | What to tune after observing results |
|---|---|---|
| SDXL generation | 1024×1024, batch 1, 25 steps, CFG 7, DPM++ 2M/Karras | Compare fewer steps and checkpoint-specific recommendations |
| SDXL image-to-image | Same base model, fixed input and seed | Sweep denoise around 0.2, 0.35, 0.5 as experiments; stronger values permit larger changes |
| Klein 4B distilled | 1024×1024, batch 1, 4 steps, CFG 1, Euler/Flux2 schedule | Compare prompts/references first; keep the distilled recipe coherent |
| Local edits | One change and a cropped context region | Mask size, context, and blend width |
| Pixel-art finishing | Actual target cell dimensions and palette | Silhouette readability and edge cleanup at 1× |
| Promotional exports | Retain a full-resolution master | Check desktop/mobile composition before optimizing files |

The denoise sweep is my suggested experiment, not a universal preset. Instruction-based edit models often use full strength, so do not transplant SDXL image-to-image settings onto Klein. The Krita handbook explains this difference. [Edit-model parameters](https://docs.interstice.cloud/edit-models/)

Keep one expensive GPU workload active at a time initially. Queue Blender GPU rendering and model inference sequentially. Start with CPU background removal if using rembg, whose documented GPU installation targets NVIDIA/CUDA; the fact that PyTorch ROCm works does not establish GPU support for every companion tool. [rembg installation](https://github.com/danielgatis/rembg)

## Automation worth building first

ComfyUI already supplies the main integration points: submit a saved API graph through `POST /prompt`, track its returned ID through WebSocket events or `/history/{prompt_id}`, then retrieve outputs. Codex can drive this through a local script, without clicking every node. The API graph is distinct from the visual editor's layout JSON. [ComfyUI server routes](https://docs.comfy.org/development/comfyui-server/comms_routes)

A small asset job can specify the source/reference, prompt, seed, workflow, variants, output dimensions, and export format. The initial automation should:

1. Generate a small candidate batch from an explicit asset list.
2. Build a contact sheet for selection.
3. Apply approved masks or exact transformations.
4. Normalize canvas sizes and pivots; export frames/atlases or responsive website images.
5. Check dimensions, alpha, file size, palette, frame counts, and unchanged regions where required.
6. Save a compact record of the source, model/LoRA hashes, workflow/settings, and output paths.

Examples of useful requests this could support:

- “Create four variants of these twelve inventory items using this style reference; show a contact sheet.”
- “Change only the cloth on this character to teal; preserve the unselected pixels.”
- “Split this 8×4 sprite sheet into 64×64 frames, preserve the common pivot, and export a preview animation.”
- “Render this Blender prop from eight directions with the same camera and lighting.”
- “Create mobile and desktop crops of this hero background, keeping the left side clear for real HTML text.”

Use immutable originals and separate generated candidates from selected exports. For distribution, record the exact checkpoint and adapter license; a shared model-family name does not establish identical terms for every variant. Keep generated text out of exact UI labels and product screenshots.

## A useful first milestone

After the starter installation is proven, I would build a small demonstration pack: six stylized inventory icons, one strictly masked edit, one correctly sliced animation sheet, and one promotional background with desktop/mobile crops. That exercises most of your needs before we add Blender or more models.

Then add a Blender prop/turntable example and choose the game-engine export format. Connect Krita's plugin when interactive selection-based editing becomes the next priority. The major unknowns to resolve with samples are your preferred visual style, acceptable cleanup effort, exact engine import conventions, and performance of the additional editing/control workloads on this AMD runtime.


## Observations from this machine

The tested SDXL base model generated two 1024 x 1024 images successfully on the Radeon. Server execution times were approximately 20.1 seconds for the first image and 10.5 seconds for a new seed immediately afterward. A separate image variation ran through both the API and the saved ComfyUI interface preset. These are individual measurements with 25 steps, CFG 7 and DPM++ 2M / Karras.

The example contact sheet is in `asset-demo/examples-contact-sheet.jpg`. The actual outputs show useful limitations: the inventory prompt requested one bottle but produced two; the pixel-art prompt requested a plain background but produced scenery. The forest photograph request also leaned toward illustration. Treat these as concepts to direct and finish, not guaranteed production-ready outputs.

The Blender example is deterministic geometry with eight camera directions, a common target and alpha output. Both CPU Cycles and Radeon HIP completed a render; the GPU device preference is configured. Its original scene, PNGs, atlas JSON, GIF and MP4 are retained.

Pixelorama opens locally. The finishing scripts passed exact pixel checks for slicing/repacking and masked preservation. CPU background removal and H.264 video encoding also completed. FLUX and Krita's additional support models were still downloading at this checkpoint; `Setup-Progress.md` reports their later completion and automated test results separately.
