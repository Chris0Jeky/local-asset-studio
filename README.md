# Local Asset Studio

Your personal workshop for game art, pixel concepts, product imagery, website backgrounds, reference edits, and Blender-to-sprite experiments.

**On the configured PC: double-click the `Asset Studio` desktop shortcut.** Pick a preset, change the description, and press **Generate**. The launcher starts ComfyUI and opens the simpler studio interface. You do not need to learn nodes first.

![Three Lanternkeeper skins](examples/lanternkeeper/contact-sheet.png)

Start with the [first-image walkthrough](docs/START-HERE.md), then try the [five guided experiments](docs/EXPERIMENTS.md). The [current state](CURRENT_STATE.md) distinguishes completed tests from plans.

## What is here

| Folder | Purpose |
|---|---|
| `app/` | Local browser interface; Python standard library, no web build toolchain |
| `presets/` | Human-readable preset names and controls mapped to graph inputs |
| `workflows/api/` | 21 executable ComfyUI recipes |
| `workflows/comfyui/` | 20 visual node graphs for learning and deeper changes |
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
| Small reference changes | FLUX Klein edit | SDXL gentle variation, Qwen edit |
| Exact repeated views and motion | Blender example | Render, reduce palette, pack atlas |

NoobAI is retained for hobby experiments; its author terms exclude commercial generated products. WAI came from a Hugging Face mirror; matching hashes do not authenticate the creator or establish commercial rights. See [model notes](models/README.md).

The local graphs do not call hosted moderation services. Local execution, model capability, and usage rights are separate questions.

**New experiment:** [HiDream-O1 FP8 ran successfully in an isolated environment](docs/HIDREAM.md), producing a 2048px image on the Radeon. Its advanced API workflow is included; it is not yet part of the simplified preset picker.

## Run and develop

On the configured Windows PC, use `Start Studio.cmd` or the desktop shortcut. The app is at `http://127.0.0.1:8191`; advanced ComfyUI is at `http://127.0.0.1:8188`.

On another computer, copy `config/example.json` to `config/local.json`, point it to an installed ComfyUI and Python, install the required models/nodes separately, then run `python app/server.py`. The app itself needs only Python 3.12+. This repository is not a complete installer for a fresh machine.

```console
python -m unittest discover -s tests
python scripts/validate-repo.py
```

See [operations](docs/OPERATIONS.md) for troubleshooting, backup, and adding presets. [HUMAN_TODO.md](HUMAN_TODO.md) contains optional creative choices, not setup blockers.
