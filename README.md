# Local Asset Studio

Your personal workshop for anime and manga, images, video, textured 3D, reference editing, and reproducible creative experiments.

**On the configured PC: double-click the `Asset Studio` desktop shortcut.** Pick a preset, change the description, and press **Generate**. The launcher starts ComfyUI and opens the simpler studio interface. You do not need to learn nodes first.

![Three Lanternkeeper skins](examples/lanternkeeper/contact-sheet.png)

Explore the [Workflow Lab guide](docs/WORKFLOW-LAB.md) for the new models, folder map, variants, and image-to-video/3D paths.

For anime and fantasy work, the [anime & fantasy atelier guide](docs/ANIME-FANTASY-ATELIER.md) is the
one page to read: which recipe produces which look, every installed LoRA with its trigger and terms,
the settings each model family wants, prompt wildcards, the settings planner, and honest timings
(Krea 2 at 768×1152 and 15 steps measured 986 s; the same family at 512×768 and 8 steps, 189 s;
SDXL anime portraits at 512×768, 20–35 s).

Use **Workspace** to collect, tag, favorite, compare and restore your outputs.
**Experiments** keeps bounded comparisons and native finishing plans together.
You can assign identity/pose/style references, switch to the isolated HiDream
environment, build an authored hinged prop, or export selected images to Krita
and a tested Godot sprite project. See [Workspace](docs/WORKSPACE.md),
[reference editing](docs/REFERENCE-ATELIER.md) and [native exports](docs/NATIVE-EXPORTS.md).

Start with the [first-image walkthrough](docs/START-HERE.md), then read [experiments and native finishing](docs/EXPERIMENTS.md) for bounded comparisons and export plans. The [current state](CURRENT_STATE.md) distinguishes completed tests from plans.

## What is here

| Folder | Purpose |
|---|---|
| `app/` | Local browser interface; Python standard library server; local model-viewer bundle; no build toolchain |
| `presets/` | Preset names and controls mapped to graph inputs; `recipes.json`, `settings-kb.json` and `wildcards/` |
| `workflows/api/` | API graphs, one per Studio preset plus a helper graph |
| `workflows/comfyui/` | Matching visual node graphs for learning and deeper changes |
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
| Stylized characters | WAI / Animagine | Pony; pose-control variants; [atelier guide](docs/ANIME-FANTASY-ATELIER.md) |
| Manga and anime studies | LineAni / Anima Aesthetic | Screentone, cinematic lighting, Krea 2 style lab |
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
MiniMax H3 now generates through the isolated loader: the tested quick audition
produced 1.625 seconds of 512×320 video with stereo audio in 6 minutes 38 seconds.
See [the working H3 setup](docs/H3-WINDOWS.md). Larger shots and Seed Hunter remain
experimental.

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

### Anime & fantasy atelier

The **Anime flagship** category now carries Krea 2 Turbo presets with LoRA slots (four on `krea-anime-atelier` and `krea-refine`, three on `krea-style-lab`, one on the retro-anime pair; the SDXL anime presets carry two and the Anima/JANIMA stacks up to six). A slot set
to strength 0 is removed from the submitted graph, so the same preset covers a plain render, a single
style adapter, or a stacked look. **Recipes** in the create view apply a complete named starting point
(preset, prompt, settings and LoRA stack) in one click; prompts accept `{a|b|c}` and `__wildcard__`
expansions; **Experiments** can plan a settings grid or a LoRA-weight remix from a sourced knowledge
base instead of a single numeric axis. Read [the atelier guide](docs/ANIME-FANTASY-ATELIER.md) first —
Krea 2 is minutes per image on this machine, not seconds.

**Correction (12 September 2026).** This section previously said the presets were "marked unverified; no
generation was submitted by the agent for this slice". That is wrong for the two Krea atelier presets:
`krea-anime-atelier` and `krea-style-lab` are `verified: true` in `presets/catalog.json` against recorded
Studio jobs — `db02f6b1` (197.0 s, 4-step audition), `7d589f47` (827.6 s, full target stack with koukouya)
and `f373ba3b` (207.1 s, `krea-style-lab` 4-step audition). Prompt IDs, submitted LoRA chains, output
SHA-256s and the reviewer's own inspection notes are in
[experiments/curated/anime-fantasy-atelier/execution-evidence.json](experiments/curated/anime-fantasy-atelier/execution-evidence.json).
`krea-environment` and the recipes marked `unverified` remain unverified. A completed job is generation
only: it is neither art acceptance nor licence clearance, and each stacked LoRA keeps its own terms.
