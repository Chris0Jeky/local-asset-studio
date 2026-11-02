"""Seeded-defect figure renders for calibrating a render critic. Runs inside Blender (4.5+), CPU Cycles only.

  blender --factory-startup -b --python scripts/critic_defect_scene.py -- <out_dir> <seed> <category>

Builds a small textured, rigged, posed figure from primitives, applies one seeded defect (or none for `clean`), renders
front/back/left/right views (`view_<name>.png`) and writes `truth.json` with the defect, part and side.
The same seed gives the same figure, pose, light and cameras in every category, so `clean` is the reference. Every material
mixes to transparent on back faces, as a game engine's back-face culling would show it, so flipped normals and holes
read as they would in-engine. The character faces -Y; its left is +X (image right in the front view).
"""
import json, math, random, sys
from pathlib import Path

CATEGORIES = ("clean", "missing_texture", "omitted_mesh", "material_swap", "flipped_normals", "broken_weights",
              "white_material", "asymmetry", "backside_hole")
VIEWS = {"front": 0, "left": 90, "back": 180, "right": 270}  # yaw of the camera around the figure; left = character's left
PALETTE = {"skin": [(0.93, 0.76, 0.64), (0.78, 0.57, 0.42), (0.55, 0.38, 0.26), (0.98, 0.85, 0.75)],
           "shirt": [(0.15, 0.35, 0.75), (0.75, 0.2, 0.2), (0.2, 0.6, 0.3), (0.85, 0.65, 0.15), (0.45, 0.25, 0.6)],
           "pants": [(0.12, 0.12, 0.18), (0.35, 0.25, 0.15), (0.25, 0.3, 0.4), (0.3, 0.3, 0.3)]}


def parts(rng):
    """(name, bone, material, primitive, location, scale, rotation_y_deg) with seeded proportions."""
    s = rng.uniform(0.92, 1.08); w = rng.uniform(0.9, 1.1); out = []
    out.append(("torso", "spine", "shirt", "sphere", (0, 0, 1.25), (0.34 * w, 0.24 * w, 0.48 * s), 0))
    out.append(("head", "head", "skin", "sphere", (0, 0, 1.98 * s), (0.24, 0.23, 0.26), 0))
    for side, x in (("L", 1), ("R", -1)):
        out.append((f"eye.{side}", "head", "eye", "sphere", (0.085 * x, -0.2, 2.02 * s), (0.04, 0.03, 0.05), 0))
        out.append((f"arm.{side}", f"arm.{side}", "shirt", "cylinder", (0.49 * w * x, 0, 1.23 * s), (0.075, 0.075, 0.37 * s), -9 * x))
        out.append((f"hand.{side}", f"arm.{side}", "skin", "sphere", (0.55 * w * x, 0, 0.86 * s), (0.09, 0.07, 0.1), 0))
        out.append((f"leg.{side}", f"leg.{side}", "pants", "cylinder", (0.16 * x, 0, 0.45), (0.1, 0.1, 0.42), 0))
        out.append((f"shoe.{side}", f"leg.{side}", "eye", "cube", (0.16 * x, -0.06, 0.04), (0.09, 0.15, 0.05), 0))
    return out, s, w


def build(rng, drng, out_dir, category):
    import bpy, numpy as np
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    tex_path = out_dir / "shirt_texture.png"
    # Shirt texture: seeded stripes plus a chest emblem, saved beside the renders so missing_texture can break the path.
    base = np.array(rng.choice(PALETTE["shirt"])); alt = np.clip(base * 0.45 + 0.55, 0, 1); n = 256
    yy, xx = np.mgrid[0:n, 0:n]; period = rng.choice([16, 24, 32])
    px = np.where(((yy // period) % 2 == 0)[..., None], base, alt)
    em = ((xx - n * 0.25) ** 2 + (yy - n * 0.55) ** 2) < (n * 0.07) ** 2
    px[em] = (0.95, 0.9, 0.2)
    img = bpy.data.images.new("shirt", n, n); img.pixels = np.concatenate([px, np.ones((n, n, 1))], -1).ravel()
    img.filepath_raw = str(tex_path); img.file_format = "PNG"; img.save()

    mats = {}
    for name in ("skin", "shirt", "pants", "eye"):
        m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nd = nt.nodes
        bsdf = nd["Principled BSDF"]; out = nd["Material Output"]
        col = {"skin": rng.choice(PALETTE["skin"]), "pants": rng.choice(PALETTE["pants"]), "eye": (0.03, 0.03, 0.04),
               "shirt": (1, 1, 1)}[name]
        bsdf.inputs["Base Color"].default_value = (*col, 1); bsdf.inputs["Roughness"].default_value = 0.6
        if name == "shirt":
            t = nd.new("ShaderNodeTexImage"); t.image = bpy.data.images.load(str(tex_path)); t.name = "shirt_tex"
            nt.links.new(t.outputs["Color"], bsdf.inputs["Base Color"])
        geo = nd.new("ShaderNodeNewGeometry"); tr = nd.new("ShaderNodeBsdfTransparent"); mix = nd.new("ShaderNodeMixShader")
        nt.links.new(geo.outputs["Backfacing"], mix.inputs[0]); nt.links.new(bsdf.outputs[0], mix.inputs[1])
        nt.links.new(tr.outputs[0], mix.inputs[2]); nt.links.new(mix.outputs[0], out.inputs["Surface"])
        mats[name] = m

    spec, s, w = parts(rng); objs = []
    for name, bone, mat, prim, loc, scale, roty in spec:
        if prim == "sphere": bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, location=loc)
        elif prim == "cylinder": bpy.ops.mesh.primitive_cylinder_add(vertices=24, location=loc)
        else: bpy.ops.mesh.primitive_cube_add(location=loc)
        o = bpy.context.active_object; o.scale = scale; o.rotation_euler = (0, math.radians(roty), 0)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        o.data.materials.append(mats[mat]); vg = o.vertex_groups.new(name=bone)
        vg.add(list(range(len(o.data.vertices))), 1.0, "REPLACE")
        o["part"] = name; objs.append(o)
    # Remember part membership per vertex before the join (an int attribute survives joining).
    for i, o in enumerate(objs):
        a = o.data.attributes.new("part_id", "INT", "POINT"); a.data.foreach_set("value", [i] * len(o.data.vertices))
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]; bpy.ops.object.join()
    fig = bpy.context.active_object; fig.name = "Figure"
    for p in fig.data.polygons: p.use_smooth = True
    names = [p[0] for p in spec]

    bpy.ops.object.armature_add(location=(0, 0, 0)); arm = bpy.context.active_object; arm.name = "Rig"
    bpy.ops.object.mode_set(mode="EDIT"); eb = arm.data.edit_bones; eb.remove(eb[0])
    def bone(name, h, t, parent=None):
        b = eb.new(name); b.head = h; b.tail = t
        if parent: b.parent = eb[parent]
    bone("root", (0, 0, 0.85), (0, 0, 0.95)); bone("spine", (0, 0, 0.95), (0, 0, 1.7), "root")
    bone("head", (0, 0, 1.74 * s), (0, 0, 2.2 * s), "spine")
    for side, x in (("L", 1), ("R", -1)):
        bone(f"arm.{side}", (0.43 * w * x, 0, 1.6 * s), (0.55 * w * x, 0, 0.86 * s), "spine")
        bone(f"leg.{side}", (0.16 * x, 0, 0.88), (0.16 * x, 0, 0.05), "root")
    bpy.ops.object.mode_set(mode="OBJECT")
    mod = fig.modifiers.new("Rig", "ARMATURE"); mod.object = arm
    pose = {"arm.L": (rng.uniform(-25, 25), 0, -rng.uniform(5, 40)), "arm.R": (rng.uniform(-25, 25), 0, rng.uniform(5, 40)),
            "head": (rng.uniform(-8, 8), 0, rng.uniform(-10, 10)), "leg.L": (rng.uniform(-15, 15), 0, 0),
            "leg.R": (rng.uniform(-15, 15), 0, 0)}
    for b, (rx, ry, rz) in pose.items():
        pb = arm.pose.bones[b]; pb.rotation_mode = "XYZ"; pb.rotation_euler = tuple(math.radians(v) for v in (rx, ry, rz))
    truth = apply_defect(drng, category, fig, mats, names, tex_path)
    return truth


def part_verts(fig, names, part):
    ids = [0] * len(fig.data.vertices); fig.data.attributes["part_id"].data.foreach_get("value", ids)
    k = names.index(part); return [i for i, v in enumerate(ids) if v == k]


def apply_defect(rng, category, fig, mats, names, tex_path):
    import bpy, bmesh
    side = rng.choice(["L", "R"]); truth = {"category": category, "part": None, "side": None, "views": list(VIEWS)}
    def bm_edit(fn):
        bm = bmesh.new(); bm.from_mesh(fig.data); bm.verts.ensure_lookup_table(); fn(bm); bm.to_mesh(fig.data); bm.free()
    if category == "missing_texture":
        mats["shirt"].node_tree.nodes["shirt_tex"].image.filepath = str(tex_path.with_name("shirt_texture_MISSING.png"))
        mats["shirt"].node_tree.nodes["shirt_tex"].image.reload(); truth.update(part="torso+arms")
    elif category == "omitted_mesh":
        part = rng.choice(["head", f"arm.{side}", f"leg.{side}", f"hand.{side}", f"eye.{side}"])
        drop = set(part_verts(fig, names, part))
        bm_edit(lambda bm: bmesh.ops.delete(bm, geom=[bm.verts[i] for i in drop], context="VERTS"))
        truth.update(part=part, side=None if part == "head" else side)
    elif category == "material_swap":
        pair = rng.choice([("shirt", "pants"), ("skin", "pants"), ("skin", "shirt")])
        slots = {m.name: i for i, m in enumerate(fig.data.materials)}
        a, b = slots[pair[0]], slots[pair[1]]
        for p in fig.data.polygons: p.material_index = b if p.material_index == a else a if p.material_index == b else p.material_index
        truth.update(part="+".join(pair))
    elif category == "flipped_normals":
        part = rng.choice(["head", "torso", f"arm.{side}", f"leg.{side}"]); vs = set(part_verts(fig, names, part))
        bm_edit(lambda bm: bmesh.ops.reverse_faces(bm, faces=[f for f in bm.faces if all(v.index in vs for v in f.verts)]))
        truth.update(part=part, side=None if part in ("head", "torso") else side)
    elif category == "broken_weights":
        # A share of one part's vertices is re-weighted to a far, posed bone: the classic stretched-spike explosion.
        part = rng.choice(["head", "torso", f"arm.{side}"]); vs = part_verts(fig, names, part)
        far = {"head": f"leg.{side}", "torso": f"arm.{'R' if side == 'L' else 'L'}", f"arm.{side}": f"leg.{side}"}[part]
        bad = rng.sample(vs, int(len(vs) * rng.uniform(0.2, 0.35)))
        for g in fig.vertex_groups: g.remove(bad)
        fig.vertex_groups[far].add(bad, 1.0, "REPLACE")
        rig = bpy.data.objects["Rig"]; pb = rig.pose.bones[far]; pb.rotation_euler[0] += math.radians(rng.choice([-1, 1]) * rng.uniform(35, 55))
        truth.update(part=part, side=None if part in ("head", "torso") else side)
    elif category == "white_material":
        target = rng.choice(["shirt", "pants", "skin"]); m = mats[target]; nd = m.node_tree.nodes
        for l in list(m.node_tree.links):
            if l.to_node.name == "Principled BSDF" and l.to_socket.name == "Base Color": m.node_tree.links.remove(l)
        nd["Principled BSDF"].inputs["Base Color"].default_value = (1, 1, 1, 1); nd["Principled BSDF"].inputs["Roughness"].default_value = 1
        truth.update(part=target)
    elif category == "asymmetry":
        part = rng.choice([f"arm.{side}", f"leg.{side}", f"eye.{side}", f"hand.{side}"]); vs = part_verts(fig, names, part)
        k = rng.choice([0.6, 1.45]); co = [fig.data.vertices[i].co.copy() for i in vs]
        c = sum(co, co[0] * 0) / len(co); top = max(v.z for v in co)
        for i, v in zip(vs, co):
            pivot = c.copy(); pivot.z = top if part.startswith(("arm", "leg")) else c.z
            fig.data.vertices[i].co = pivot + (v - pivot) * k
        truth.update(part=part, side=side, scale=k)
    elif category == "backside_hole":
        vs = set(part_verts(fig, names, "torso"))
        def hole(bm):
            kill = [f for f in bm.faces if all(v.index in vs for v in f.verts) and f.calc_center_median().y > 0.12
                    and abs(f.calc_center_median().z - 1.3) < 0.22]
            bmesh.ops.delete(bm, geom=kill, context="FACES")
        bm_edit(hole); truth.update(part="torso", views=["back"])
    return truth


def render(rng, out_dir, size=384):
    import bpy
    sc = bpy.context.scene; sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = 24
    sc.cycles.use_denoising = True; sc.render.resolution_x = sc.render.resolution_y = size
    sc.render.image_settings.file_format = "PNG"; sc.view_settings.view_transform = "Standard"
    world = bpy.data.worlds.new("w"); sc.world = world; world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.6, 0.66, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.8
    bpy.ops.mesh.primitive_plane_add(size=40); pm = bpy.data.materials.new("floor"); pm.use_nodes = True
    pm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.35, 0.35, 0.33, 1)
    pm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 1
    bpy.context.active_object.data.materials.append(pm)
    bpy.ops.object.light_add(type="SUN", rotation=(math.radians(rng.uniform(35, 55)), 0, math.radians(rng.uniform(-40, 40))))
    bpy.context.active_object.data.energy = 3.5
    bpy.ops.object.camera_add(); cam = bpy.context.active_object; sc.camera = cam; cam.data.lens = 50
    jitter = rng.uniform(-10, 10)
    for name, yaw in VIEWS.items():
        a = math.radians(yaw + jitter); d = 4.1
        # yaw 0 = camera on -Y looking at the front; positive yaw orbits toward +X (the character's left side).
        cam.location = (d * math.sin(a), -d * math.cos(a), 1.3); cam.rotation_euler = (math.radians(87), 0, a)
        sc.render.filepath = str(out_dir / f"view_{name}.png"); bpy.ops.render.render(write_still=True)


def main(argv):
    out_dir, seed, category = Path(argv[0]).resolve(), int(argv[1]), argv[2]
    if category not in CATEGORIES: raise SystemExit(f"unknown category {category}; one of {CATEGORIES}")
    out_dir.mkdir(parents=True, exist_ok=True)
    # The base figure, pose, light and cameras depend on the seed only, so clean-<seed> is the exact reference for every
    # defect of that seed; the defect draws from its own stream.
    rng = random.Random(seed); truth = build(rng, random.Random(f"{seed}:{category}"), out_dir, category); truth["seed"] = seed; render(rng, out_dir)
    (out_dir / "truth.json").write_text(json.dumps(truth, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
