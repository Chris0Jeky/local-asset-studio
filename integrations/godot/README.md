# Godot asset adapter

`scripts/godot_asset_adapter.py` packages a Studio `sprite_atlas` manifest into a new Godot 4 project. It creates `AtlasTexture` entries and one `SpriteFrames` animation, with `relative_duration = duration_ms / 1000 * 60`. The `AnimatedSprite2D` offset keeps the shared manifest anchor at node origin; nearest or linear filtering and loop policy are retained.

The adapter takes only root-confined input paths and a caller-selected Godot executable. It launches Godot with fixed argument arrays, never runs manifest text as code, and refuses an existing output root. `run` performs a headless import, runs the generated verification scene, and retains Godot's own frame/timing/anchor/alpha-region report. An optional GLB is copied read-only and loaded by Godot for scene, mesh, material, and animation inventory.

```powershell
python scripts/game_asset_demo.py --out .runtime/godot-fixture
python scripts/godot_asset_adapter.py run `
  --input-root "$PWD/.runtime/godot-fixture" `
  --atlas-manifest atlas/manifest.json `
  --glb examples/lanternkeeper/ember.glb `
  --output-root "$PWD/.runtime/godot-project" `
  --godot C:/AI/asset-tools/godot/Godot_v4.7.2-stable_win64.exe
```

`engine-report.json` proves only the imported package's headless behavior. Visual art acceptance, licence approval, rig quality, collision, root motion, and runtime platform coverage still need their own gates.
