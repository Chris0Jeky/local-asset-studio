# Godot asset adapter

`scripts/godot_asset_adapter.py` packages a Studio `sprite_atlas` manifest into a
new Godot 4 project. AtlasTexture regions, common anchor, individual durations,
loop policy and nearest/linear filtering are retained. Packaging submits nothing.

**Verification v2** now observes `frame_changed` and `animation_looped` or
`animation_finished` before accepting a sprite. The earlier adapter's 480 ms
report was calculated from imported SpriteFrames durations; it did not wait for
a full cycle. The new report retains that configured value and separately records
observed simulation timing at 240 fixed steps/second. It is not a rendering-speed
benchmark. Blank/hold frames are checked against the original alpha pixels, not
rejected simply for being empty.

GLB verification additionally requires the pinned Khronos tool and an explicit
Node executable. Install the tool deliberately, outside the ComfyUI environment:

```console
npm ci --prefix tools/gltf-validation --ignore-scripts --no-audit --no-fund
```

Set `node` to the absolute Node executable path in `config/local.json`, beside
your existing `godot` path. This is used by the current Studio native-export
route; no second queue or new UI is needed. CLI callers may pass `--node`.
Sprite-only verification and atlas/ORA packaging do not need Node.

```powershell
python scripts/godot_asset_adapter.py run `
  --input-root "$PWD/.runtime/approved-asset-inputs" `
  --atlas-manifest atlas/manifest.json `
  --glb model.glb `
  --output-root "$PWD/.runtime/godot-new-attempt" `
  --godot "C:/path/to/Godot.exe" `
  --node "C:/Program Files/nodejs/node.exe"
```

All inputs above must actually exist under the explicit input root. The command
does not discover/download them. The original files remain unchanged.

Read [Engine evidence](../../docs/ENGINE-EVIDENCE.md) for architecture, limits,
CI/local test commands, source pins, report semantics and failure recovery.
A successful format/import check is not art, licence, rig, collision, root-motion
or cross-platform gameplay acceptance. GLB pose samples are labelled samples,
not proof of complete temporal/visual quality.
