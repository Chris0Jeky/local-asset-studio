"""Render an orbit dataset of one GLB in NeRF-synthetic format for splat training (run inside Blender 5.4).

  blender -b --factory-startup --python scripts/splat_orbit_dataset.py -- <asset.glb> <out_dir> [n_train] [n_test] [res] [near]

Writes <out>/train/r_###.png, <out>/test/r_###.png (RGBA, transparent background) and transforms_train.json /
transforms_test.json with camera_angle_x and per-frame 4x4 camera-to-world matrices in Blender's camera convention
(-Z forward, +Y up), which is the NeRF-synthetic convention. Train cameras lie on a Fibonacci upper hemisphere; test
cameras sit on a separate ring between train elevations (held out: never seen in training). Cycles CPU, fixed seed.
`near` (e.g. 0.45) moves every other train camera to that fraction of the distance: a splat holds up only at distances
its training views covered (pier, 2 Nov: far-only 26.4 dB held out, with a 0.45 near orbit 35.4 dB). scene.json records
the light rig so live meshes can be relit to match the splat's baked lighting.
"""
import json, math, sys
from pathlib import Path
import bpy
from mathutils import Vector

a = sys.argv[sys.argv.index("--") + 1:]
glb, out = Path(a[0]), Path(a[1]); n_train = int(a[2]) if len(a) > 2 else 100; n_test = int(a[3]) if len(a) > 3 else 20
res = int(a[4]) if len(a) > 4 else 512
bpy.ops.wm.read_factory_settings(use_empty=True); sc = bpy.context.scene
bpy.ops.import_scene.gltf(filepath=str(glb))
for o in [o for o in bpy.data.objects if o.name.endswith(("-colonly", "-convcolonly"))]: bpy.data.objects.remove(o)
meshes = [o for o in bpy.data.objects if o.type == "MESH"]
pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
centre, radius = (lo + hi) / 2, (hi - lo).length / 2
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = 48; sc.cycles.use_denoising = True; sc.cycles.seed = 0
sc.render.resolution_x = sc.render.resolution_y = res; sc.render.film_transparent = True
sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"; sc.view_settings.view_transform = "Standard"
RIG = {"sun_rotation_deg": [45, 0, 35], "sun_energy": 3.0, "world_strength": 0.6}
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True; bg = w.node_tree.nodes["Background"]; bg.inputs[1].default_value = RIG["world_strength"]
RIG["world_color"] = list(bg.inputs[0].default_value)[:3]
bpy.ops.object.light_add(type="SUN", rotation=[math.radians(v) for v in RIG["sun_rotation_deg"]]); bpy.context.active_object.data.energy = RIG["sun_energy"]
bpy.ops.object.camera_add(); cam = bpy.context.active_object; sc.camera = cam; cam.data.lens = 40
tr = cam.constraints.new("TRACK_TO"); bpy.ops.object.empty_add(location=centre); tr.target = bpy.context.active_object
dist = radius / math.tan(cam.data.angle / 2) * 1.15


NEAR = float(a[5]) if len(a) > 5 else 0


def render(split, dirs):
    (out / split).mkdir(parents=True, exist_ok=True); frames = []
    for i, d in enumerate(dirs):
        k = NEAR if (NEAR and split == "train" and i % 2) else 1.0
        cam.location = centre + d * dist * k; bpy.context.view_layer.update()
        sc.render.filepath = str(out / split / f"r_{i:03d}.png"); bpy.ops.render.render(write_still=True)
        frames.append({"file_path": f"./{split}/r_{i:03d}", "transform_matrix": [list(r) for r in cam.matrix_world]})
    (out / f"transforms_{split}.json").write_text(json.dumps({"camera_angle_x": cam.data.angle_x, "frames": frames}, indent=1))


golden = math.pi * (3 - math.sqrt(5)); train = []
for i in range(n_train):  # Fibonacci points on the upper hemisphere, elevation 8-80 degrees
    z = math.sin(math.radians(8 + 72 * (i + 0.5) / n_train)); r = math.sqrt(1 - z * z); t = golden * i
    train.append(Vector((r * math.cos(t), r * math.sin(t), z)))
test = [Vector((math.cos(t) * math.cos(e), math.sin(t) * math.cos(e), math.sin(e)))
        for k in range(n_test) for t, e in [(2 * math.pi * (k + 0.37) / n_test, math.radians(27))]]
render("train", train); render("test", test)
(out / "scene.json").write_text(json.dumps({"glb": str(glb), "centre": list(centre), "radius": radius, "distance": dist, "res": res,
                                           "near": NEAR, "light": RIG}, indent=1))
print("DATASET", out, n_train, n_test)
