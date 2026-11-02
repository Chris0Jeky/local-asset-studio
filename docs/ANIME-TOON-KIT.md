# Anime toon kit: VRM character to toon shading in Blender 5.4 and Godot 4.7

Built and measured on 2 November 2026 (R&D night, waifu-lab lane) by taking one original SFW character, Suzu, from
a written design to a rigged, toon-shaded model. Lab media stays outside Git; this page records the reusable tools and
what was measured with them. Renders were inspected by an agent for defects only. That is not art acceptance.

| Tool | Runs in | Does |
| --- | --- | --- |
| `scripts/vrm_toon.py` | Python 3.12+, stdlib; `face-sdf` also needs numpy and Pillow | VRoid material roles, SDF face-shadow thresholds, VRM 1.0 spring chains and colliders as JSON for Godot |
| `scripts/vrm_posmap_bpy.py` | Blender (bpy + numpy) | A world-position map per texel of every base texture, so a VRM can be repainted by 3D rules without reading its UVs |
| `scripts/vrm_toon_bpy.py` | Blender 5.4 EEVEE | Rebuilds every material as toon: `ml` (Material Lighting loop) or `classic` (Shader to RGB), adds inverted-hull outlines and a key/rim light rig |
| `tools/godot-toon/` | Godot 4.7.2 | Toon `light()` shader with the same SDF face map, hull outline pass, built-in `SpringBoneSimulator3D` fed from the VRM's springs, procedural idle |

## Run it

```bash
blender -b char.blend --python scripts/vrm_posmap_bpy.py -- OUT/posmap
python scripts/vrm_toon.py face-sdf OUT/posmap/Face_00_SKIN.npz OUT/face_sdf.png
blender -b char.blend --python scripts/vrm_toon_bpy.py -- ml OUT/face_sdf.png OUT/char-toon.blend
python scripts/vrm_toon.py springs char.vrm tools/godot-toon/springs.json
```

For Godot, copy the VRM in as `tools/godot-toon/model.glb` (a VRM 1.0 file is a GLB; Godot imports the core glTF
and ignores the VRM extensions), copy `face_sdf.png` beside it, import once with `--headless --import`, then run the
project. `--headless` renders nothing, so a pixel proof opens a window (`--write-movie frames/f.png --fixed-fps 30`).
The kit's inputs are gitignored there.

`char.blend` is a VRM imported with the VRM Add-on for Blender. Version 4.10.3's extension manifest says
`blender_version_max = "5.3.0"`, so Blender 5.4 refuses it. A local copy with the cap raised to 5.5.0, installed into
an isolated profile (`BLENDER_USER_RESOURCES=<dir> blender --command extension install-file -r user_default --enable`),
imported and exported VRM 1.0 cleanly on 5.4.0 alpha 67c9bdddb88b. That is one build and two models, not a support claim.

## Blender 5.4 Material Lighting nodes, measured

Probed on spheres with a white sun and a red point light, EEVEE, build 67c9bdddb88b:

- `Light Evaluation` (mode Diffuse or Glossy; Position and Normal are implicit; LightIndex left unlinked) returns a
  per-light **Factor**, a Lambert-like term **without shadows**. **Mask** read about 1 wherever the light reaches; it is
  not a shadow. **Direction** points from the surface to the light.
- `Shadow Raycast` returns the cast shadow as a colour. At softness 0.15 it is noisy on large shadowed areas.
- `Light Accumulation` multiplies `Diffuse Light` by `Diffuse Color` (and Glossy likewise) and **sums over every light
  automatically**. No zone node is needed; `LightIterInternalInput/Output` exist but are internal. Two lights drew two
  independent cel bands on one sphere.
- `Light Info.Color` is the light's colour without its power.
- World lighting does not enter the loop. Shader to RGB does integrate it: under a bright world the classic setup's
  glossy-step hair highlight fired everywhere and washed the hair out. The kit therefore gives both styles a
  camera-only world (Light Path, Is Camera Ray).

## What the toon kit does

Per light, in `ml`: lit = smoothstep around 0.18 of Factor x Shadow Raycast; rim = smoothstep of Layer Weight facing
(0.62 to 0.70) on the lit side only; hair adds a glossy Light Evaluation (roughness 0.22) stepped at 0.5 to 0.56. The face
replaces N.L with the SDF test: the light's direction in object space gives its angle from the face's forward axis,
and a texel is lit while that angle (as a fraction of pi) is below its threshold in the SDF map, choosing the R or G
channel by the side the light is on. An emission term carries base x shade colour, so a fully lit texel shows exactly
its base colour.

Verdict from an 8-angle key-light sweep on the same model: cloth and hair look alike in both styles. The face is where
`ml` wins: a clean half-face split at side light and no blotches at front light, where classic N.L leaves patches by
the nose and jaw at every angle.

The SDF map is procedural. Landmarks come from the face position map: eye height at 45 % of the face's height, the
nose tip as the most forward central point, widths per height over the front half. The terminator sweeps from the far
cheek to the near cheek, bows into a crescent above and below the eyes, and has a small lobe past the nose. On Suzu the
automatic map was within 2.8/255 on average of a hand-tuned one.

## Godot 4.7

`SpringBoneSimulator3D` is built in and takes VRM-style settings directly: root and end bone, stiffness, drag, gravity,
radius, plus sphere and capsule collision children. Fed from the VRM, the 33 chains and 13 colliders of the test model
loaded with no add-on. Collider offsets are read in VRM node space, which is why the proof imports the VRM file
itself rather than a separate Blender glTF export, whose bone frames can differ.

Godot's glTF import ignores `VRMC_node_constraint`. VRoid bases drive their sleeve, shoulder and twist helper bones
with aim and roll constraints (14 on the test model), so with the arms lowered the sleeves stayed horizontal. The proof
now evaluates them each frame before the spring step, in dependency order: aim turns the bone's rest axis toward the
source bone; rotation applies the source's rotation from its rest; roll carries that rotation into the destination's
rest frame and keeps only the twist about the axis, as in the specification's reference code. Each is blended by
weight. Ordering looks only at sources, not at constrained ancestors (#1928). `vrm_toon.py springs`
writes them into `springs.json`, together with the VRM's expressions (morph-target binds by node and target name);
the idle plays a blink every 3.1 s and the `happy` expression through the turn. Expressions follow the VRM 1.0 update
order: binary ones snap at 0.5, `overrideBlink`/`overrideMouth` damp the blink and mouth groups, and binds sum per
blend shape before they are applied.

Actions: `godot --path . -- --action=wave` raises the right arm and waves the forearm with the `happy` expression;
`--action=walk` plays an in-place procedural walk (1.1 s cycle, side camera) whose skirt and hair motion comes from the
springs. Both are procedural, not retargeted motion capture.

Lip sync: put a `voice.wav` and its Rhubarb Lip Sync cues (`rhubarb -f json -o cues.json --dialogFile line.txt
voice.wav`) beside the model, rerun `godot --headless --import` so the WAV is imported (the proof warns and stays silent
otherwise), and it becomes a talking portrait. Rhubarb's mouth shapes map to the VRM visemes
(B -> ih, C -> ee, D -> aa, E -> oh, F -> ou, G/H -> light ih/aa, A and X closed), eased over about 60 ms. Movie Maker
writes the audio beside the frames (`f.wav`), so `ffmpeg -i f%08d.png -i f.wav` muxes the clip. Measured on a 7.65 s
Kokoro line: Rhubarb 3.9 s for 45 cues.

The toon shader writes `EMISSION = albedo x shade` and `DIFFUSE_LIGHT += light x lit x (1 - shade + rim)`. Its ambient
source is disabled, so the result matches Blender's. `LIGHT_COLOR` already includes PI and is divided back out.

## Grounded locomotion (mocap gait + foot IK)

`python scripts/bvh_joints.py IN.bvh OUT.json` turns a BVH clip into per-frame joint world positions. Output is in metres,
Y up, the figure's left on +X, and a travelling clip's path straightened onto +Z so loops don't drift.
`tools/godot-toon/mocap_gait.gd` plays such clips on a VRoid-style skeleton, for a host built on `toon_proof.gd` that
moves itself (a CharacterBody3D, a path follower):

```gdscript
var gait = preload("res://mocap_gait.gd").new()
func _ready() -> void: super(); gait.setup(self)
func _process(delta: float) -> void: super(delta); gait.drive(self, delta, Vector3(body.velocity.x, 0, body.velocity.z))
```

It expects `res://mocap/walk.json` and `run.json`. Mocap data is not in Git; record its licence where you keep it.

- **Retarget.** At runtime it matches bone directions: each mapped bone swings from its rest direction onto the mocap
  bone's direction, and the hips and chest take full frames from two vectors. VRM rest rotations need not be world-aligned.
- **Gait.** The cycle advances by distance travelled divided by the clip's stride, so the feet match whatever speed the
  host moves at. Idle applies below 0.05 m/s; the run blends in from 1.7 to 2.3 m/s.
- **Feet.** `TwoBoneIK3D` targets come from downward rays onto the level's colliders, and a foot stays locked where it
  planted while its ankle is within 1.5 cm of rest height. Measure foot sliding after the modifiers have run (the
  skeleton's `skeleton_updated` signal); a pose read in `_process` is from before the IK.

Measured on 2 Nov 2026 on a VRoid model with Bandai Namco Research Motiondataset 1 clips (CC BY-NC 4.0). The test moved
the body like a game controller: idle, a 1.1 m/s walk, a 2.6 m/s run, then a stop. Mean stance-phase foot slide fell from
2.26 m/s with the old in-place procedural walk to 0.017 m/s with the gait (p95 from 4.21 to 0.003; the mean carries a few rare spikes). The retarget is
swing-only: limbs get no twist, and the hands and head keep the idle pose.

## Limits

- One model, one Blender alpha build, one Godot version. The VRM add-on cap raise is a local patch, not upstream support.
- Springs carry each chain's first-joint settings and its collider groups; per-joint settings, `gravityDir` and
  `center` are not exported yet, and position maps assume one mesh per material.
- Shadow Raycast noise shows as speckle on large self-shadowed cloth areas.
- The SDF map assumes a VRoid-like face facing -Y with Z up in the position map.
- Validator: the exported VRM and GLB passed glTF-Validator 2.0.0-dev.3.10 with 0 errors. The VRM had 19 warnings, 15 of them
  `MULTIPLE_EXTENSIONS`.
