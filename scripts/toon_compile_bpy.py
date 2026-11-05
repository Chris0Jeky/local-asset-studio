"""Blender half of the toon material compiler: dump a scene's materials as JSON IR, compile them, optionally render the
parity views and export the GLB the Godot half loads. Never saves the .blend. See docs/TOON-COMPILER.md.

  blender -b --factory-startup scene.blend --python scripts/toon_compile_bpy.py -- OUT_DIR [--cameras views.json]
      [--materials A,B] [--render] [--glb] [--no-outline] [--samples 64]

Writes OUT_DIR/ir.json, OUT_DIR/textures/*, everything `toon_compile.py` writes, and with --render OUT_DIR/blender/*.png,
with --glb OUT_DIR/scene.glb. views.json: {"background": [r, g, b] (linear), "views": [{"name", "res": [w, h],
"target": [x, y, z], "yaw", "pitch", "dist", "fov" | "ortho"}]}.
"""
import json
import os
import shutil
import sys
from pathlib import Path

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import toon_compile  # noqa: E402

BL_TYPE = {"ShaderNodeLightEvaluation": "LIGHT_EVALUATION", "ShaderNodeLightInfo": "LIGHT_INFO",
           "ShaderNodeShadowRaycast": "SHADOW_RAYCAST", "ShaderNodeLightAccumulation": "LIGHT_ACCUMULATION"}
BASE_PROPS = {p.identifier for p in bpy.types.ShaderNode.bl_rna.properties}


def plain(v):
    if hasattr(v, "__len__") and not isinstance(v, str):
        return [float(c) for c in v]
    return v if isinstance(v, (str, bool)) else float(v)


def sockets(socks, links):
    out = {}
    for s in socks:
        if not getattr(s, "enabled", True) or getattr(s, "is_unavailable", False):
            continue
        d = {"name": s.name, "type": s.type}
        if hasattr(s, "default_value"):
            try:
                d["default"] = plain(s.default_value)
            except TypeError:
                pass
        if links is not None:
            lk = next((l for l in links.get(s.as_pointer(), []) if l.is_valid and not l.is_muted), None)
            d["link"] = [lk.from_node.name, lk.from_socket.identifier] if lk else None
        out[s.identifier] = d
    return out


def props(n):
    p = {}
    for prop in n.bl_rna.properties:
        k = prop.identifier
        if k in BASE_PROPS or k in ("rna_type", "inputs", "outputs", "internal_links", "texture_mapping", "color_mapping", "image_user"):
            continue
        if prop.type in ("ENUM", "BOOLEAN", "INT", "FLOAT", "STRING") and not getattr(prop, "is_array", False):
            p[k] = getattr(n, k)
    if n.type == "TEX_IMAGE" and n.image:
        p["image"] = n.image.name
    if n.type == "VALTORGB":
        r = n.color_ramp
        p["ramp"] = {"interpolation": r.interpolation, "elements": [{"position": e.position, "color": list(e.color)} for e in r.elements]}
    return p


def tree(nt, groups, images):
    links = {}
    for l in nt.links:
        links.setdefault(l.to_socket.as_pointer(), []).append(l)
    nodes = {}
    for n in nt.nodes:
        if n.type == "FRAME":
            continue
        t = BL_TYPE.get(n.bl_idname, n.type)
        d = {"type": t, "bl_idname": n.bl_idname, "props": props(n), "inputs": sockets(n.inputs, links), "outputs": sockets(n.outputs, None)}
        if n.mute:
            d["mute"] = True
            d["internal_links"] = [[l.from_socket.identifier, l.to_socket.identifier] for l in n.internal_links]
        if t in ("GROUP_OUTPUT", "OUTPUT_MATERIAL"):
            d["active"] = bool(n.is_active_output)
        if t == "GROUP" and n.node_tree:
            d["tree"] = n.node_tree.name
            if n.node_tree.name not in groups:
                groups[n.node_tree.name] = None  # placeholder against recursion
                groups[n.node_tree.name] = tree(n.node_tree, groups, images)
        if t == "TEX_IMAGE" and n.image:
            images.add(n.image)
        nodes[n.name] = d
    return {"nodes": nodes}


def save_image(im, folder, used):
    folder.mkdir(parents=True, exist_ok=True)
    src = bpy.path.abspath(im.filepath) if im.filepath else ""
    copyable = Path(src).suffix.lower() in (".png", ".jpg", ".jpeg") if src else False
    ext = Path(src).suffix.lower() if copyable else ".png"
    stem = base = toon_compile.safe_name(Path(im.name).stem)
    k = 0
    while (stem + ext).lower() in used:  # distinct images can sanitise to one name
        k += 1
        stem = f"{base}_{k}"
    used.add((stem + ext).lower())
    dst = folder / (stem + ext)
    if not im.packed_file and copyable and os.path.isfile(src):
        shutil.copyfile(src, dst)  # exact bytes
    else:
        im.save(filepath=str(dst))  # packed or generated: Blender writes its buffer
    return dst.name


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    out = Path(argv[0])
    opt = lambda k: argv[argv.index(k) + 1] if k in argv else None  # noqa: E731
    out.mkdir(parents=True, exist_ok=True)
    sc = bpy.context.scene
    meshes = [o for o in sc.objects if o.type == "MESH" and not o.hide_render]
    wanted = set(opt("--materials").split(",")) if opt("--materials") else None
    mats = {s.material for o in meshes for s in o.material_slots if s.material and s.material.node_tree}
    groups, images, ir_mats = {}, set(), {}
    for m in sorted(mats, key=lambda m: m.name):
        if wanted and m.name not in wanted:
            continue
        g = tree(m.node_tree, groups, images)
        outn = m.node_tree.get_output_node("EEVEE")
        g.update(output=outn.name if outn else None, backface_culling=bool(m.use_backface_culling),
                 blend=getattr(m, "surface_render_method", "DITHERED"))
        ir_mats[m.name] = g
    imgs, used = {}, set()
    for im in sorted(images, key=lambda i: i.name):
        imgs[im.name] = {"file": "textures/" + save_image(im, out / "textures", used), "colorspace": im.colorspace_settings.name,
                         "size": list(im.size)}
    lights = [{"name": o.name, "type": o.data.type, "color": list(o.data.color), "energy": o.data.energy,
               "angle": getattr(o.data, "angle", 0.0), "shadow": o.data.use_shadow, "matrix": [list(r) for r in o.matrix_world]}
              for o in sc.objects if o.type == "LIGHT" and not o.hide_render]
    views = json.loads(Path(opt("--cameras")).read_text(encoding="utf-8")) if opt("--cameras") else {"views": []}
    ir = {"version": 1, "blender": bpy.app.version_string, "materials": ir_mats, "groups": groups, "images": imgs,
          "lights": lights, "cameras": views["views"], "background": views.get("background")}
    (out / "ir.json").write_text(json.dumps(ir, indent=1), encoding="utf-8")
    doc = toon_compile.compile_ir(ir, out)
    print("TOONC", json.dumps(doc["summary"]), flush=True)
    if "--no-outline" in argv:
        for o in meshes:
            for md in o.modifiers:
                if md.type == "SOLIDIFY" and (md.use_flip_normals or md.name.lower().startswith("outline")):
                    md.show_render = md.show_viewport = False
    if "--glb" in argv:
        kw = dict(filepath=str(out / "scene.glb"), export_format="GLB", export_apply=False, export_animations=False, use_visible=True)
        try:
            bpy.ops.export_scene.gltf(export_image_format="NONE", **kw)
        except TypeError:
            bpy.ops.export_scene.gltf(**kw)
        print("TOONC glb", out / "scene.glb", flush=True)
    if "--render" in argv:
        (out / "blender").mkdir(exist_ok=True)
        sc.render.engine = "BLENDER_EEVEE"
        sc.view_settings.view_transform = "Standard"
        sc.view_settings.look = "None"
        sc.view_settings.exposure = 0.0
        sc.view_settings.gamma = 1.0
        sc.render.film_transparent = False
        sc.eevee.taa_render_samples = int(opt("--samples") or 64)
        sc.render.image_settings.file_format = "PNG"
        sc.render.image_settings.color_mode = "RGB"
        cam = bpy.data.objects.new("ToonCompileCam", bpy.data.cameras.new("ToonCompileCam"))
        sc.collection.objects.link(cam)
        sc.camera = cam
        from mathutils import Matrix
        for c in toon_compile.cameras(views["views"]):
            cam.matrix_world = Matrix(c["matrix"])
            cam.data.clip_start, cam.data.clip_end = c["near"], c["far"]
            if "ortho" in c:
                cam.data.type, cam.data.ortho_scale = "ORTHO", c["ortho"]
            else:
                import math
                cam.data.type, cam.data.sensor_fit, cam.data.angle = "PERSP", "AUTO", math.radians(c["fov"])
            sc.render.resolution_x, sc.render.resolution_y = c["res"]
            sc.render.resolution_percentage = 100
            sc.render.filepath = str(out / "blender" / f"{c['name']}.png")
            bpy.ops.render.render(write_still=True)
        print("TOONC rendered", len(views["views"]), flush=True)


main()
