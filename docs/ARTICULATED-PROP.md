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
