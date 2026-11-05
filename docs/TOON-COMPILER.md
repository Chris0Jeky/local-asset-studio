# Toon material compiler: Blender 5.4 Material Lighting graphs to Godot `light()` shaders and VRM MToon

Built on 2 November 2026 (R&D night, mira-lab lane) so that a toon look authored once in Blender's light loop reaches
Godot and VRM without hand-porting. It translates the node graph itself, not a fixed shader with parameters, so any
graph made of the supported nodes compiles; unsupported features are named in the report. Tested on the anime toon kit's `ml`
materials on Suzu (`docs/ANIME-TOON-KIT.md`); parity is measured, not claimed (below).

| Tool | Runs in | Does |
| --- | --- | --- |
| `scripts/toon_compile_bpy.py` | Blender 5.4 | Dumps every material on visible meshes as JSON IR, saves its textures, compiles; optionally renders parity views in EEVEE and exports the GLB for Godot. Never saves the .blend |
| `scripts/toon_compile.py` | Python 3.12+, stdlib (`parity` needs Pillow) | IR to Godot spatial shaders, VRM MToon 1.0 parameters, the Godot light rig and cameras; `parity` measures two render sets |
| `tools/toon-compiler/render.gd` | Godot 4.7.2 | Loads the GLB at runtime, applies only `ok` compiled materials, lights and cameras, writes one PNG per camera |

## Run it

```bash
blender -b --factory-startup scene.blend --python scripts/toon_compile_bpy.py -- OUT --cameras views.json --render --glb --no-outline
godot --path tools/toon-compiler --script res://render.gd -- godot.json
python scripts/toon_compile.py parity OUT/blender OUT/godot OUT/parity "[0.78, 0.82, 0.88]"
python scripts/render_critic.py check OUT/godot/*.png --reference OUT/blender/*.png
```

`views.json` is `{"background": [r, g, b] (linear), "views": [{"name", "res": [w, h], "target": [x, y, z], "yaw",
"pitch", "dist", "fov" | "ortho"}]}`; both programs frame the same matrices. `godot.json` is `{"glb": "OUT/scene.glb",
"compiled": "OUT", "out": "OUT/godot", "background": [...], "shadow_max_distance": 6}`, with optional `shadow_bias`,
`shadow_normal_bias`, `msaa` and `taa` (on by default). `--no-outline` turns off
inverted-hull Solidify modifiers in the Blender renders, because outlines are geometry, not material. Re-running
only `toon_compile.py IR.json OUT` recompiles without Blender.

## How a graph maps

Blender evaluates every node that reads a light (Light Evaluation, Light Info, Shadow Raycast with LightIndex
unlinked) once per light and sums the result in Light Accumulation. Godot's `light()` is the same model, so:

- nodes downstream of a light node go into `light()`; all other nodes run once in `fragment()` and reach `light()`
  through varyings (textures are sampled once);
- Light Accumulation becomes `DIFFUSE_LIGHT += Diffuse Light x Diffuse Color` and `SPECULAR_LIGHT += Glossy Light x
  Glossy Color`, with `ALBEDO = 1`; Emission becomes `EMISSION`; Transparent BSDF becomes `ALPHA` (dithered surfaces
  get a 0.5 alpha scissor); `ambient_light_disabled`, because world light never enters Blender's loop. A material
  without Light Accumulation compiles `unshaded`;
- a light node read outside the loop gets Blender's default (Factor 1, Mask 1, Power 0, shadow 1) and a warning;
- vectors stay in Blender world axes in the shader (`b_world`), so Direction, Incoming, Normal and object-space
  transforms mean what they meant in Blender. Object space is Godot's `MODEL_MATRIX` with the glTF axis change;
- implicit socket conversions follow Blender: colour to float is luminance (0.2126, 0.7152, 0.0722), vector to float
  the average, float to vector a broadcast. Math keeps Blender's safe variants (divide by 0 is 0, sqrt of a negative 0).

Supported nodes: Math, Vector Math (common ops), Map Range (float: linear, stepped, smoothstep, smootherstep), Mix and
MixRGB (mix, add, subtract, multiply, screen, difference, darken, lighten), RGB to BW, Separate/Combine XYZ and Color
(RGB), Clamp, Invert, Color Ramp (constant, linear), Layer Weight, Fresnel, Geometry (normal, incoming, backfacing,
position), Texture Coordinate and UV Map (render UV), Image Texture, Vector Transform (world/object), Value, RGB,
groups, reroutes, muted nodes, and the four Material Lighting nodes. An unsupported node or sampler mode is reported
in `report.json` with the node's name and produces no shader. A graph with a known unsupported lighting contribution
can produce a `partial` shader for inspection; the Godot runner keeps the imported material for that graph.

### Image samplers and material selection

Image Texture interpolation and extension belong to each node. Uniforms are keyed by image, interpolation and
extension; sampling also keeps UVs and shader stage distinct. Nodes using the same image with identical settings
can share a uniform and sample, while different settings produce separate uniforms. The image file is still
exported once, and `report.json` retains the existing `uniform name -> image name` mapping. Old IR that lacks a
node setting falls back to its image-level setting, then to Blender's `Linear` / `REPEAT` defaults.

The supported interpolation modes are `Closest` and `Linear`; supported extension modes are `REPEAT` and `EXTEND`.
`Cubic`, `Smart`, `CLIP`, `MIRROR`, and invalid values are explicitly refused instead of being approximated with a
different sampler. Re-exporting with Blender preserves these node properties without copying them onto images.

The Godot runner replaces a material only when its report status is exactly `ok` and the compiled shader file is
readable and nonblank. `partial`, `unsupported`, unknown or missing status, and unavailable shaders leave the
imported material in place. Stdout records each retained material's reason and any unsupported-feature list. A
linked or nonblack constant `Transmission Light` contribution makes a material `partial`; its shader file remains
available for inspection. A black unlinked value contributes nothing and does not mark the material partial.

### Light convention

Godot's `light()` sees only `LIGHT_COLOR`, which is colour x energy x pi. The compiler's light rig (`lights.json`)
sets each Godot light's colour to the Blender colour and its energy to what Blender's Light Info reports as Power
(measured: strength / pi for a sun, power / (4 pi^2) for a point). In the shader Power is the brightest channel of
`LIGHT_COLOR / PI` and Color is the rest. Products such as Color x Power are exact; each alone is exact when the light
colour's brightest channel is 1, true of every light in the kit. Light Info Position, Light Evaluation
Distance for point lights (read as 1, exact for suns), and Transmission Light have no `light()` equivalent.

Shadow Raycast becomes `ATTENUATION`. For suns that is the shadow alone. For omni lights Godot folds its distance
falloff into `ATTENUATION`, while Blender's diffuse Factor carries 1/d^2 instead, so Factor x Shadow agrees but
either alone does not.

## VRM MToon (approximate)

`mtoon.json` holds `VRMC_materials_mtoon` 1.0 parameters read from the graph's recognisable parts, each with the node
it came from: the N.L step becomes `shadingShiftFactor = -centre` and `shadingToonyFactor = 1 - width / 2` (MToon steps
linearly on N.L + shift); base x constant shade colour becomes `shadeColorFactor` with the base as
`shadeMultiplyTexture`; a Layer Weight facing step becomes the parametric rim (lift puts 1 at the upper edge, the
Fresnel power puts 5 % at the lower edge, mixed with lighting). MToon cannot express an SDF face shadow, a glossy step
highlight or per-light colour logic; those are listed under `dropped`. This half has no parity proof; it is a starting
point for a VRM export, not a match.

## Measured

2 November 2026, Blender 5.4.0 alpha 67c9bdddb88b, Godot 4.7.2, on Suzu with the kit's `ml` materials (16 of 16
compile, none partial). The light-loop semantics were measured on an orthographic unit sphere under one sun (linear
EXR):

- Diffuse Light Evaluation Factor = clamped N.L (maximum error 0.0075).
- Glossy Light Evaluation Factor = GGX D (alpha = roughness^2) x N.L, with no geometry term and no 1 / (4 N.V). The
  relative RMS is 0.2 % at roughness 0.4; the best-fit scale is 0.99 at 0.4 and 0.94 at 0.22 (an undersampled peak).
  A Smith geometry term cannot be told apart at these angles.

Parity between Blender's EEVEE (64 samples, Standard view transform, outlines off) and Godot, inside the subject, in
8-bit levels:

| View | v1 mean | v2 mean | v2 share > 8 | v2 share > 24 |
| --- | --- | --- | --- | --- |
| body-front | 5.87 | 4.18 | 11.8 % | 4.4 % |
| body-34 | 5.26 | 4.09 | 11.3 % | 3.7 % |
| body-back | 8.54 | 7.31 | 38.5 % | 3.5 % |
| face-front | 10.23 | 8.35 | 24.4 % | 9.1 % |
| face-34 | 10.65 | 9.67 | 29.3 % | 12.0 % |
| face-side | 10.34 | 8.35 | 24.2 % | 8.8 % |

v1 used a glossy guess about 3x too low, which drew the hair highlight as rings, and Godot's noisy soft shadows,
which the toon ramps stepped into dither. v2 adds the fitted glossy and TAA in the runner. What remains, by eye:

- silhouette edges: Blender's 1.5 px reconstruction filter is softer than MSAA plus TAA;
- cast shadows that Godot misses, such as the head on the apron and hair on the face (shadow bias, untested; see
  `shadow_bias`);
- slightly larger hair highlights in Godot.

The shading bands, ramps, rim and highlight shapes match.

## Regression checks

`python -m unittest discover -s tests -p 'test_toon_compile*.py' -v` runs the offline compiler suite and the opt-in
native material-policy test. The offline tests execute generated shaders with sampler-aware callbacks, including
shared images across groups, each independently changed sampler setting, UV separation, and Color/Alpha reuse.
They also verify that partial transmission artifacts and the uniform-to-image report mapping survive serialization.

The native test requires an explicit `STUDIO_TEST_GODOT` executable. Without it the test is skipped. The existing
Native engine evidence workflow runs it on Linux and Windows with **Godot 4.5**, imports the original CPU-authored
`FixturePaint` GLB, and calls the production material-selection guard. It checks that rejected records preserve
the actual imported material, that only valid `ok` records replace it, and that unavailable or blank shader files
retain the original. When `STUDIO_ENGINE_EVIDENCE` is set, its `toon-material-policy/` folder retains the fixture,
project, source hashes and command, exit result, stdout/stderr, and a JSON receipt with the Godot version and each
case's material-selection checks. These are import and selection-policy checks, not GPU render or shader parity checks.
They do not rerun or extend the Godot **4.7.2** visual measurements above. See the
[5 November verification note](verification/2026-11-05-toon-material-integrity.md) for this change's local results
and pending native evidence.

## Limits

- One Blender alpha build (5.4.0 67c9bdddb88b) and Godot 4.7.2; Material Lighting nodes may change before 5.4 ships.
- The IR reads the render UV map; a second UV set is refused, not guessed.
- Godot's shadow maps are not Blender's Shadow Raycast; shadow edges and contact shadows differ.
- Outlines and other modifier geometry are outside the compiler.
