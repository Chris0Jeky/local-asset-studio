# Lanternkeeper — reproducible local asset study

A small exploration-game prototype and promotional asset package, created on this machine with Blender and local FLUX Klein 4B. The object is fictional.

## Try it

Run `scripts/Open-Lanternkeeper.ps1` from the repository. It opens http://127.0.0.1:8193. Use arrows/WASD while the canvas is focused, click a destination, or use the movement buttons. Collect six lanterns. Choose a material, pause animation or start a new clearing.

To restart the preview from PowerShell:

```powershell
python -m http.server 8193 --bind 127.0.0.1 --directory examples/lanternkeeper
```

The page requires HTTP to load its JSON atlas; double-clicking index.html is not the supported launch method. The server is local-only and can be stopped with Ctrl+C in the terminal that started it.

## Contents

| File | Purpose |
|---|---|
| index.html | Playable canvas example and promotional landing page |
| source-lantern.blend | Original editable source before expansion |
| lanternkeeper.blend | Editable model with bobbing rig; last rendered material is ember |
| moss.glb / amethyst.glb / ember.glb | Three mesh/material exports with bob animation |
| renders/ | 96 original transparent 128px renders |
| sprites/ | 96 palette-reduced 64px RGBA sprites |
| sprites.png / sprites.json | Atlas and named rectangles, centre pivots, 160ms preview frame durations |
| contact-sheet.png / turntable.gif | Direction/material overview and animated preview |
| forest-hero.png / forest-hero.webp | Local FLUX environment artwork |
| social-card.png | 1200px promotional card with deterministic typography |
| hero-workflow-api.json / hero-result.json | Exact graph and actual execution record |
| asset-manifest.json | File sizes, hashes and source summary |

## Rebuild the sprites

These commands replace generated outputs in this package. Copy the folder first if you want to retain an edited version.

```powershell
& 'C:\AI\blender-4.5.13-windows-x64\blender.exe' --background --python 'C:\Users\jekyt\Documents\Codex\2026-09-11\i\outputs\Lanternkeeper\lanternkeeper-blender.py'
& 'C:\AI\asset-tools\venv\Scripts\python.exe' 'C:\Users\jekyt\Documents\Codex\2026-09-11\i\outputs\Lanternkeeper\pack-sprites.py'
```

The Blender script uses the supplied source scene, changes three materials, adds a bobbing parent rig, renders eight camera directions at four phases and exports GLBs. It uses Radeon HIP. The packer applies one shared palette and binary alpha on a 64px grid, then places frames into a padded atlas. The preview intentionally uses a 160ms sprite cadence; the GLB's continuous bob has its own two-second timeline.

The hero API graph uses FLUX Klein 4B FP8, the installed Qwen3 encoder, four Euler steps, CFG 1 and seed 20260911. Its pixel dimensions are 1344 × 768. The portable `lanternkeeper-hero.py --out <new-experiment-folder>` runner delegates to the repository's resumable batch tool. It preserves the supplied hero rather than overwriting it.

## Verified

96 Radeon HIP renders finished; all atlas frame crops exactly match their corresponding sprite files. All three GLBs were reimported into Blender: each recovered nine meshes and a measured animated vertical displacement of approximately 0.077 units between sampled frames. The actual browser loaded the artwork/atlas, updated collection counters and reached the all-six completion state, and toggled animation pause. The desktop page and sprite contact sheet were visually inspected.

## NOT verified

No Godot/Unity/Unreal import, full mobile/browser matrix, complete game QA, or subjective production approval. GLB round-trip validation proves import and animated transforms in Blender, not another engine. Full-resolution Blender renders and 64px sprites are separate deliverables; palette reduction is not hand-authored pixel cleanup.

## Findings

The edit-comparison.png strip demonstrates an exact-preservation workflow: FLUX recolours the whole lantern, then a binary teal-material mask composites only allowed pixels back onto the original 256px image. The executable check found 7,926 changed pixels and all 57,610 protected pixels identical. The rough colour mask leaves some edge/highlight cleanup; it is a demonstrator, not an artist-approved selection. edit-original.png, edit-mask.png and edit-protected-result.png retain the reversible inputs and output.

Blender is the reliable source for repeated views and motion. Local generation is useful for the environment and art direction. Deterministic layout keeps text, grid alignment and exports under control. This division produced an integrated result without asking a diffusion model to invent an animation sheet.

The source model and scripts were created for this task. The forest uses local FLUX Klein 4B; consult the model's Apache 2.0 terms and your distribution platform's requirements before shipping. No third-party stock images were used. The asset manifest provides hashes for provenance, not a copyright or trademark clearance.
