# Articulated prop study

`scripts/articulated_prop.py` creates an authored stylized treasure chest as a
new, exclusive output directory. It starts only the configured local Blender
executable with this fixed argument shape:

```text
blender.exe --background --factory-startup --disable-autoexec --python <generated-script> -- --config <generated-config>
```

The generated script is reviewed source from this adapter. It does not load a
caller-provided blend, script, command, asset, or geometry. It creates a chest
body and lid as separate meshes. The lid origin is the rear-edge X-axis hinge,
with 0.03 units of clearance by default. Its `ChestLidOpenHoldClose` action is
24fps: frame 1 closed, 20 open at 70 degrees, 40 hold, and 60 closed.

```console
python scripts/articulated_prop.py preflight
python scripts/articulated_prop.py execute --output-root C:\exports\chest-study --options-json "{\"render_size\":192,\"samples\":8}"
```

All options are bounded numeric controls: `width` (0.4–8), `depth` (0.3–5),
`body_height` (0.2–5), `lid_height` (0.15–3), `clearance` (0.005–0.2),
`render_size` (64–512), and CPU Cycles `samples` (1–32). The scene uses CPU
Cycles, a fixed seed, four CPU render threads, a small square RGBA render, and
deterministic closed/open/front/side camera views.

Outputs are `chest.blend`, animated `chest.glb`, `metadata.json`, the generated
config/script, and `views/{closed,open,front,side}.png`. Metadata records named
parts, mesh triangle counts and dimensions, materials, hinge axis and limits,
clip timing, observed hinge transforms, GLB reimport inventory, render settings,
and explicit limits. A failed owned run retains its generated script, config, and
`blender-log.json`/`failure.json` for diagnosis. `CollisionProxy` is a named
box only; engine collision, mechanical usability, art acceptance, segmentation,
automatic rigging, and licensing are outside this authored baseline.

## Production operation

`app/articulated.py` exposes `prepare(studio, payload)` and
`run(studio, project_id, plan)` for the Studio production coordinator. Configure
the exact local executable as `config/local.json`'s `blender` path. `prepare`
accepts only a 1–120 character name and the numeric controls above, verifies the
configured executable, and returns a JSON-safe plan pinned to the adapter version
and executable SHA-256. It does not create output or start Blender.

`run` accepts only a 32-lowercase-hex project ID and a hash-valid plan. It runs
once in `experiments/projects/<id>/articulated`, records a deterministic native
job with no ComfyUI prompt IDs, retains failure files, registers the animated GLB
and four render PNGs in `AssetWorkspace`, and writes `export.zip` containing the
BLEND, GLB, renders, metadata, and recipe. Returned artifact records use the
production file route and include immutable byte hashes.

Studio persists the deterministic job and attempt before Blender starts. After a
restart, Resume inspects the retained receipt, pinned recipe, successful Blender
exit log and outputs; it does not execute Blender again. Failed or unproven
attempts remain unresolved even if partial files look complete.

The visible GLB excludes the render-hidden `CollisionProxy`; that helper remains
in the editable BLEND. A fresh Studio build on 11 September 2026,
`44cfa4a0b29a43098d6c7c7609ca6831`, produced all four inspection views and a GLB
containing body, lid and two hinge pins plus `ChestLidOpenHoldClose`. Its browser
preview was inspected. This is an authored blockout with an animated hinge,
not a hollow mechanical chest, automatic part segmentation or an accepted game asset.
