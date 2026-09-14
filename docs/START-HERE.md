# Your first image

1. Double-click **Asset Studio** on the desktop. Give the launcher time to start ComfyUI. It opens the local studio page.
2. Choose **Pixel art • 128px prop**. The existing prompt already works. For your first run, change only the subject: for example, replace the treasure chest with a brass compass.
3. Leave the advanced settings alone and press **Generate** once. The job appears in the gallery when complete. First loads are slower than repeat generations.
4. Inspect both outputs: the detailed concept and the small 128px version. A pixel-style image is not automatically a finished game sprite: check edges, palette, scale, and transparency.
5. Save the recipe or download the image. Your job recipe and seed are also saved locally in `experiments/runs/`.

The default prompts are starting examples, not hidden rules. You can rewrite them. When switching between model families, first try each preset's own defaults: Pony/Animagine tags and Qwen/FLUX instructions are deliberately different.

## Four words that help immediately

**Prompt** describes the desired picture. Include subject, medium, framing, lighting, background, and useful exclusions. For game props, specify one object, full object visible, clear silhouette, and a simple background.

**Seed** selects the starting noise. Keep it fixed when comparing one change. Change it to explore alternatives. The same seed across different models does not make their output composition identical.

**Steps** controls sampling iterations. More steps usually take longer and are not always better. Four-step FLUX Klein/Qwen Lightning and eight-step Z-Image presets have model-specific defaults; do not blindly set all models to 40.

**CFG** controls how strongly guidance affects sampling. High values can damage images. Begin with the preset's value. **Denoise**, on image variations, controls how much freedom the model gets to change the original.

## Anime and fantasy in one click

Open the **Recipes** select in the create view. A recipe is a complete named starting point: preset,
prompt, size, sampler, seed and the whole LoRA stack. Pick one, press **Generate**, change nothing the
first time. The list shows each recipe's notes and sources, and warns when a recipe needs an adapter
file you do not have installed.

Three things worth knowing before you spend a long render:

- **LoRA slots.** How many a preset has varies (`krea-anime-atelier` and `krea-refine` four, `krea-style-lab`
  three, the retro-anime Krea pair one, the Anima stacks up to six). Strength `0` means off, and the adapter is
  removed from the graph entirely. Turn one on by giving it a strength (usually `1.0`) — and use its
  trigger word, because most style adapters do nothing without it.
- **Wildcards.** In any prompt, `{misty|stormy|golden}` picks one option and `__lighting__` picks a
  line from `presets/wildcards/lighting.txt`. The choice is derived from the seed, so the same recipe
  and seed reproduce the same prompt.
- **Krea 2 is slow here.** A 768×1152 image at 15 steps took 986 seconds on this PC; the same family
  at 512×768 and 8 steps took 189 seconds; SDXL anime portraits at 512×768 take 20–35 seconds.
  Audition small, then render large.

The full map — which recipe for which look, every LoRA with its trigger and terms, per-family settings
and the settings planner — is the [anime & fantasy atelier guide](ANIME-FANTASY-ATELIER.md).

## Edit an existing image

Choose **FLUX Klein • reference edit**. Upload an image, then describe a single change: “Change the teal enamel to purple; keep the brass frame, amber light, viewpoint and background.” Generate one image and compare it with the original.

For tighter preservation, try **SDXL • gentle reference variation**. For more complex instruction following, try **Qwen • instructed image edit**. Qwen can take minutes and use most available memory. Neither promises pixel-identical unedited areas; the masked-composite example demonstrates that requirement separately.

Pose presets expect a **coloured OpenPose skeleton**, not an ordinary character photograph. The included guide is a working example. Pose control controls structure; it does not lock face, costume, or identity.

## Learn ComfyUI only when useful

Use the **ComfyUI** link to open the advanced editor. Drag a JSON from `workflows/comfyui/` onto its canvas, or use ComfyUI's workflow-open control. API JSON from `workflows/api/` is for programs and should not be confused with a visual graph.

Follow the picture-making chain: **load model → encode prompt → sample → decode → save image**. Click the positive text node to edit the prompt, then run the workflow. Save your changed version under a new name. The studio's controls are shortcuts to these same inputs; they do not conceal a separate model.

## Find your work

- The studio gallery keeps job history across page reloads.
- `experiments/runs/<job-id>/` retains the settings and execution record locally.
- Full-resolution outputs remain in ComfyUI's `output` folder; the studio displays/downloads them.
- Named browser presets are convenience copies. Export a recipe for a durable backup.
- GitHub receives curated experiments only when deliberately copied into `experiments/curated/` and committed. It does not auto-upload every generation.

Next: [experiments and native finishing](EXPERIMENTS.md).
