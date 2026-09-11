# Local Asset Studio

Your personal workshop for anime and manga, images, video, textured 3D, reference editing, and reproducible creative experiments.

**On the configured PC: double-click the `Asset Studio` desktop shortcut.** Pick a preset, change the description, and press **Generate**. The launcher starts ComfyUI and opens the simpler studio interface. You do not need to learn nodes first.

![Three Lanternkeeper skins](examples/lanternkeeper/contact-sheet.png)

Explore the [Workflow Lab guide](docs/WORKFLOW-LAB.md) for the new models, folder map, variants, and image-to-video/3D paths.

Use **Workspace** to collect, tag, favorite, compare and restore your outputs.
**Experiments** keeps bounded comparisons and native finishing plans together.
You can assign identity/pose/style references, switch to the isolated HiDream
environment, build an authored hinged prop, or export selected images to Krita
and a tested Godot sprite project. See [Workspace](docs/WORKSPACE.md),
[reference editing](docs/REFERENCE-ATELIER.md) and [native exports](docs/NATIVE-EXPORTS.md).

Start with the [first-image walkthrough](docs/START-HERE.md), then try the [five guided experiments](docs/EXPERIMENTS.md). The [current state](CURRENT_STATE.md) distinguishes completed tests from plans.

## What is here

| Folder | Purpose |
|---|---|
| `app/` | Local browser interface; Python standard library server; local model-viewer bundle; no build toolchain |
| `presets/` | Human-readable preset names and controls mapped to graph inputs |
| `workflows/api/` | 55 API graphs (54 Studio presets) |
| `workflows/comfyui/` | 54 visual node graphs for learning and deeper changes |
| `scripts/` | Launcher, batch generation, asset finishing, validation |
| `examples/lanternkeeper/` | Playable example, editable Blender files, GLBs, sprites, promotional artwork |
| `examples/gallery/` | Small, curated model samples for comparison |
| `examples/references/` | Starter lantern and pose guide |
| `experiments/curated/` | Selected findings and scorecard template |
| `experiments/runs/` | Your local recipes and results; deliberately ignored by Git |
| `models/` | Model checksums, provenance, and future candidates; no weights |
| `docs/` | Beginner instructions, operations, strategy, and migrated research |

## Models and starting points

| You want | Start here | Try next |
|---|---|---|
| Pixel item concepts | SDXL + Pixel Art XL LoRA | Compare LoRA strength with the same seed |
| Realistic promotional art | RealVisXL | FLUX Klein, Z-Image Turbo |
| Abstract website art | SDXL abstract preset | Change composition and colour vocabulary |
| Stylized characters | WAI / Animagine | Pony; pose-control variants |
| Manga and anime studies | LineAni / Anima Aesthetic | Screentone, cinematic lighting, free Krea retro anime |
| Animate a finished image | Wan 2.2 Animate Image | Short motion study, then longer shots |
| Generate a 3D draft | TRELLIS textured draft | Authored Blender parts, pivot and motion |
| Small reference changes | FLUX Klein edit | SDXL gentle variation, Qwen edit |
| Combine reference roles | Qwen Atelier | Identity, pose and style in separate slots |
| Native 2K anime concepts | HiDream O1 isolated environment | Reference restyle, then compare seeds |
| Exact repeated views and motion | Blender example | Render, reduce palette, pack atlas |

NoobAI is retained for hobby experiments; its author terms exclude commercial generated products. WAI came from a Hugging Face mirror; matching hashes do not authenticate the creator or establish commercial rights. See [model notes](models/README.md).

The local graphs do not call hosted moderation services. Local execution, model capability, and usage rights are separate questions.

See the [new local execution samples](experiments/curated/workflow-lab/README.md)
for three image styles, a short video and a geometry GLB with their exact recipes.
MiniMax H3's files are installed. Its isolated loader experiment bypasses the
encoder access violation, but full video still encounters a Windows memory
failure. It remains experimental; see the exact attempts in [current state](CURRENT_STATE.md).

**HiDream O1 is in the Studio picker:** [both concept and reference-edit recipes](docs/HIDREAM.md)
produced 2048-square images on the Radeon. Use **Model environment → HiDream O1 →
Switch environment** before starting either recipe.

## Run and develop

On the configured Windows PC, use `Start Studio.cmd` or the desktop shortcut. The app is at `http://127.0.0.1:8191`; advanced ComfyUI is at `http://127.0.0.1:8188`.

On another computer, copy `config/example.json` to `config/local.json`, point it to an installed ComfyUI and Python, install the required models/nodes separately, then run `python app/server.py`. The app needs Python 3.12+, Pillow for image validation/finishing and psutil for explicit environment switches. The configured ComfyUI runtime already contains these packages. This repository is not a complete installer for a fresh machine.

```console
python -m unittest discover -s tests
python scripts/validate-repo.py
```

See [operations](docs/OPERATIONS.md) for troubleshooting, backup, and adding presets. [HUMAN_TODO.md](HUMAN_TODO.md) contains optional creative choices, not setup blockers.

### Anime quality quick start

Open the **Anime quality** category for WAI and Animagine portraits or a 1.5x refinement pass. ComfyUI workflow 24 adds manual masked repair. Read the [parameter and anatomy guide](docs/ANIME-QUALITY.md) before turning up steps or resolution. These new presets were schema-checked; no generation was submitted by the agent for this slice.

The [anime detailing guide](docs/ANIME-DETAILING.md) covers installed ESRGAN, automatic face crops, optional hand crops and the combined finishing workflow.
