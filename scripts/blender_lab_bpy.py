"""Blender-side half of the Blender lab: runs inside `blender --background`, never in the Studio's Python.

Capabilities are detected by feature tests (RNA properties, registered types, operators, or by doing the thing),
never by comparing version numbers. `bpy` is imported lazily so the pure helpers stay importable offline.

    blender --background --factory-startup --disable-autoexec --python blender_lab_bpy.py -- probe --out <file>
"""
import json
import sys

SCHEMA = "las.blender-lab.v1"


def _enum_ids(rna_type, prop):
    try: return sorted(item.identifier for item in rna_type.bl_rna.properties[prop].enum_items)
    except (KeyError, AttributeError): return None


def _attempt(fn):
    """Run one feature test; a failure is a recorded result, never a crash."""
    try: return {"ok": True, "detail": fn()}
    except Exception as exc: return {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:300]}


def _action_api():
    import bpy
    rna = bpy.types.Action.bl_rna.properties
    result = {"legacy_fcurves_property": "fcurves" in rna, "slots_property": "slots" in rna, "layers_property": "layers" in rna}
    mesh = bpy.data.meshes.new("_las_probe")
    obj = bpy.data.objects.new("_las_probe", mesh)
    bpy.context.scene.collection.objects.link(obj)
    try:
        obj.keyframe_insert("location", index=0, frame=1)
        action = obj.animation_data.action
        result["keyframe_insert"] = True
        result["assigned_slot"] = getattr(obj.animation_data, "action_slot", None) is not None
        if "layers" in rna and len(action.layers):
            strip = action.layers[0].strips[0]
            bag = strip.channelbag(obj.animation_data.action_slot)
            result["channelbag_fcurves"] = len(bag.fcurves)
        if "fcurves" in rna:
            result["legacy_fcurves"] = len(action.fcurves)
        result["fcurve_ensure_for_datablock"] = hasattr(action, "fcurve_ensure_for_datablock")
        bpy.data.actions.remove(action)
    finally:
        bpy.data.objects.remove(obj)
        bpy.data.meshes.remove(mesh)
    try:
        from bpy_extras import anim_utils
        result["anim_utils_action_get_channelbag_for_slot"] = hasattr(anim_utils, "action_get_channelbag_for_slot")
    except ImportError:
        result["anim_utils_action_get_channelbag_for_slot"] = False
    result["layered"] = bool(result.get("slots_property") and result.get("channelbag_fcurves"))
    return result


def _shader_nodes():
    import bpy
    names = sorted(name for name in dir(bpy.types)
                   if isinstance(getattr(bpy.types, name), type) and issubclass(getattr(bpy.types, name), bpy.types.ShaderNode))
    interesting = [name for name in names if any(key in name for key in ("Light", "Toon", "ShaderToRGB", "Npr", "NPR"))
                   and name not in ("ShaderNodeLightPath", "ShaderNodeLightFalloff", "ShaderNodeOutputLight")]
    material = bpy.data.materials.new("_las_probe")
    material.use_nodes = True
    instantiable = {}
    try:
        for name in interesting:
            try:
                node = material.node_tree.nodes.new(name)
                instantiable[name] = {"inputs": [s.name for s in node.inputs], "outputs": [s.name for s in node.outputs]}
            except RuntimeError as exc:
                instantiable[name] = {"error": str(exc)[:200]}
    finally:
        bpy.data.materials.remove(material)
    return {"count": len(names), "all": names, "lighting_or_npr_candidates": instantiable}


def _projects():
    import bpy
    return {"types": sorted(name for name in dir(bpy.types) if "Project" in name),
            "ops_category": "project" in dir(bpy.ops), "context_attribute": hasattr(bpy.context, "project"),
            "preferences_attributes": sorted(name for name in dir(bpy.context.preferences) if "project" in name.lower())}


def _point_clouds():
    import bpy
    imports = {}
    for category in ("wm", "import_scene", "import_mesh"):
        ops = getattr(bpy.ops, category, None)
        if ops is None: continue
        imports[category] = sorted(name for name in dir(ops) if "import" in name or name.endswith("_in"))
    flat = [name for names in imports.values() for name in names]
    datablock = None
    if hasattr(bpy.data, "pointclouds"):
        cloud = bpy.data.pointclouds.new("_las_probe")
        datablock = {"points": len(cloud.points), "attributes": sorted(a.name for a in cloud.attributes)}
        bpy.data.pointclouds.remove(cloud)
    return {"import_operators": imports,
            "splat_like": sorted(name for name in flat if any(key in name for key in ("splat", "gauss", "ply", "spz", "point"))),
            "pointcloud_datablock": datablock, "pointcloud_object_type": "POINTCLOUD" in (_enum_ids(bpy.types.Object, "type") or [])}


def _gltf_export():
    import addon_utils
    import bpy
    props = bpy.ops.export_scene.gltf.get_rna_type().properties
    options = {}
    for prop in props:
        if prop.identifier == "rna_type": continue
        entry = {"type": prop.type}
        if prop.type == "ENUM": entry["items"] = sorted(item.identifier for item in prop.enum_items)
        options[prop.identifier] = entry
    version = None
    for module in addon_utils.modules():
        if module.__name__ == "io_scene_gltf2": version = list(module.bl_info.get("version", ()))
    return {"addon_version": version, "option_count": len(options), "options": options}


def _gpu():
    import bpy
    result = {"preferences_gpu_backend": getattr(bpy.context.preferences.system, "gpu_backend", None),
              "preferences_gpu_backend_items": _enum_ids(bpy.types.PreferencesSystem, "gpu_backend")}
    try:
        import gpu
        result["gpu_init_function"] = hasattr(gpu, "init")
        if hasattr(gpu, "init"): gpu.init()
        result["active_backend"] = gpu.platform.backend_type_get()
        result["vendor"] = gpu.platform.vendor_get()
        result["renderer"] = gpu.platform.renderer_get()
        result["version"] = gpu.platform.version_get()
    except Exception as exc:
        result["active_backend_error"] = f"{type(exc).__name__}: {exc}"[:200]
    return result


def _cycles():
    import bpy
    addon = bpy.context.preferences.addons.get("cycles")
    if addon is None: return {"enabled": False}
    prefs = addon.preferences
    types = [item[0] for item in prefs.get_device_types(bpy.context)]
    devices = {}
    for kind in types:
        if kind == "NONE": continue
        try: devices[kind] = [{"name": d.name, "type": d.type} for d in prefs.get_devices_for_type(kind)]
        except Exception as exc: devices[kind] = {"error": str(exc)[:200]}
    return {"enabled": True, "compute_device_types": types, "devices": devices,
            "hiprt_property": hasattr(prefs, "use_hiprt"),
            "gpu_visible": sorted(kind for kind, found in devices.items() if isinstance(found, list) and any(d["type"] != "CPU" for d in found))}


def _render_engines():
    """Engines are a dynamic enum: try assigning each known or registered identifier."""
    import bpy
    render = bpy.context.scene.render
    candidates = set(_enum_ids(bpy.types.RenderSettings, "engine") or [])
    candidates |= {"BLENDER_WORKBENCH", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "CYCLES"}
    candidates |= {getattr(cls, "bl_idname", None) for cls in bpy.types.RenderEngine.__subclasses__()} - {None}
    found, original = [], render.engine
    for name in sorted(candidates):
        try: render.engine = name; found.append(name)
        except TypeError: pass
    render.engine = original
    return found


def probe():
    import platform
    import bpy
    bpy.ops.wm.read_factory_settings(use_empty=True)
    app = bpy.app
    return {
        "schema": SCHEMA, "kind": "capability-probe",
        "blender": {"version": list(app.version), "version_string": app.version_string, "version_cycle": app.version_cycle,
                    "build_hash": app.build_hash.decode(), "build_branch": app.build_branch.decode(),
                    "build_date": app.build_date.decode(), "build_platform": app.build_platform.decode(),
                    "background": app.background},
        "python": {"version": platform.python_version(), "implementation": platform.python_implementation()},
        "render_engines": _render_engines(),
        "features": {
            "action_api": _attempt(_action_api),
            "shader_nodes": _attempt(_shader_nodes),
            "blender_projects": _attempt(_projects),
            "point_cloud_and_splat_import": _attempt(_point_clouds),
            "gltf_export": _attempt(_gltf_export),
            "gpu_backend": _attempt(_gpu),
            "cycles_devices": _attempt(_cycles),
        },
    }


# ---- scene manifest -------------------------------------------------------------------------------------------------

DIGITS = 5
# Identity and file locations are recorded but kept out of the semantic checksum: the same scene opened in another
# Blender build or from another folder keeps its checksum.
NON_SEMANTIC = ("schema", "kind", "blender", "source", "runtime", "semantic_checksum")


def rnd(value):
    value = round(float(value), DIGITS)
    return 0.0 if value == 0 else value  # folds -0.0


def vec(values): return [rnd(v) for v in values]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def semantic_checksum(manifest):
    import hashlib
    return hashlib.sha256(canonical({k: v for k, v in manifest.items() if k not in NON_SEMANTIC}).encode()).hexdigest()


def _quantised_hash(*arrays):
    """Order-sensitive hash; floats are quantised to DIGITS so float noise below that does not count."""
    import hashlib
    import numpy as np
    digest = hashlib.sha256()
    for array in arrays:
        data = np.asarray(array)
        if data.dtype.kind == "f": data = np.rint(data.astype(np.float64) * 10 ** DIGITS)
        digest.update(np.ascontiguousarray(data, dtype="<i8").tobytes())
    return digest.hexdigest()


def _foreach(collection, attr, width, dtype):
    import numpy as np
    out = np.empty(len(collection) * width, dtype=dtype)
    collection.foreach_get(attr, out)
    return out


def _socket(node, name):
    socket = node.inputs.get(name)
    if socket is None: return None
    if socket.is_linked: return "linked:" + socket.links[0].from_node.bl_idname
    value = socket.default_value
    return vec(value) if hasattr(value, "__len__") else rnd(value)


def _walk_nodes(tree, seen):
    for node in tree.nodes:
        yield node
        group = getattr(node, "node_tree", None)
        if group is not None and group.name not in seen:
            seen.add(group.name)
            yield from _walk_nodes(group, seen)


def _material(mat):
    entry = {"name": mat.name, "diffuse_color": vec(mat.diffuse_color), "node_types": {}, "images": [], "principled": None}
    tree = mat.node_tree if getattr(mat, "use_nodes", True) else None
    if tree is not None:
        types, images = {}, set()
        for node in _walk_nodes(tree, set()):
            types[node.bl_idname] = types.get(node.bl_idname, 0) + 1
            if node.bl_idname == "ShaderNodeTexImage" and node.image is not None: images.add(node.image.name)
            if node.bl_idname == "ShaderNodeBsdfPrincipled" and entry["principled"] is None:
                entry["principled"] = {name.lower().replace(" ", "_"): _socket(node, name)
                                       for name in ("Base Color", "Metallic", "Roughness", "Alpha")}
        entry["node_types"], entry["images"] = types, sorted(images)
    return entry


def _image(image):
    import os
    import bpy
    path = bpy.path.abspath(image.filepath_raw, library=image.library) if image.filepath_raw else ""
    packed = image.packed_file is not None
    size = list(image.size)  # reading size loads the buffer; a missing file stays 0x0
    return {"name": image.name, "source": image.source, "file": os.path.basename(path.replace("\\", "/")) or None,
            "packed": packed, "size": size, "colorspace": image.colorspace_settings.name,
            "missing": image.source == "FILE" and (size == [0, 0] or (not packed and not os.path.isfile(path)))}


def _signed_volume(mesh, points):
    """Divergence-theorem volume of the triangulated surface: positive for a closed mesh with outward normals,
    negative when its faces are wound inward. Split-invariant, so it survives a GLB roundtrip."""
    import numpy as np
    mesh.calc_loop_triangles()
    if not len(mesh.loop_triangles) or not len(points): return 0.0
    tris = points[_foreach(mesh.loop_triangles, "vertices", 3, np.int32).reshape(-1, 3)].astype(np.float64)
    return rnd(np.einsum("ij,ij->i", tris[:, 0], np.cross(tris[:, 1], tris[:, 2])).sum() / 6.0)


def _closed(mesh, points):
    """Every triangle edge shared by exactly two triangles once vertices with bit-identical positions are welded, so
    the seam splits of a GLB roundtrip do not make a closed surface look open."""
    import numpy as np
    mesh.calc_loop_triangles()
    if not len(mesh.loop_triangles) or not len(points): return False
    _, weld = np.unique(points, axis=0, return_inverse=True)
    tris = weld.reshape(-1)[_foreach(mesh.loop_triangles, "vertices", 3, np.int32).reshape(-1, 3)]
    edges = np.sort(np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]]), axis=1)
    _, counts = np.unique(edges, axis=0, return_counts=True)
    return bool((counts == 2).all())


def _mesh(mesh):
    import numpy as np
    coords = _foreach(mesh.vertices, "co", 3, np.float32)
    loop_totals = _foreach(mesh.polygons, "loop_total", 1, np.int32)
    loop_verts = _foreach(mesh.loops, "vertex_index", 1, np.int32)
    edge_verts = _foreach(mesh.edges, "vertices", 2, np.int32)
    material_index = _foreach(mesh.polygons, "material_index", 1, np.int32)
    pts = coords.reshape(-1, 3)
    entry = {"name": mesh.name, "vertices": len(mesh.vertices), "edges": len(mesh.edges), "faces": len(mesh.polygons),
             "loops": len(mesh.loops), "triangles": int(np.maximum(loop_totals - 2, 0).sum()),
             "geometry_hash": _quantised_hash(coords, loop_totals, loop_verts, edge_verts),
             "signed_volume": _signed_volume(mesh, pts),
             "closed": _closed(mesh, coords.reshape(-1, 3)),
             "bbox": {"min": vec(pts.min(0)), "max": vec(pts.max(0))} if len(pts) else None,
             "uv_maps": [uv.name for uv in mesh.uv_layers],
             "color_attributes": sorted(a.name for a in mesh.color_attributes),
             "material_face_counts": [int(c) for c in np.bincount(material_index, minlength=max(len(mesh.materials), 1))],
             "shape_keys": None}
    keys = mesh.shape_keys
    if keys is not None:
        reference = _foreach(keys.reference_key.data, "co", 3, np.float32).reshape(-1, 3)

        def deltas(block):  # split-invariant summary: survives the vertex duplication a GLB roundtrip introduces
            co = _foreach(block.data, "co", 3, np.float32).reshape(-1, 3)
            delta = co - reference
            pairs = np.unique(np.hstack([reference, co]), axis=0)  # seam duplicates are bit-identical rows
            return {"delta_max": rnd(np.linalg.norm(delta, axis=1).max()) if len(delta) else 0.0,
                    "delta_bbox": {"min": vec(delta.min(0)), "max": vec(delta.max(0))} if len(delta) else None,
                    # basis is centred: a roundtrip may bake the object offset into mesh data (skinned glTF meshes do)
                    "moments": _moments(np.hstack([pairs[:, :3] - pairs[:, :3].astype(np.float64).mean(0),
                                                   pairs[:, 3:].astype(np.float64) - pairs[:, :3]]),
                                        float(np.abs(pairs).max()) if len(pairs) else 0.0)}

        entry["shape_keys"] = {"use_relative": keys.use_relative, "reference": keys.reference_key.name, "keys": [
            {"name": block.name, "relative_key": block.relative_key.name, "value": rnd(block.value), "mute": block.mute,
             "vertex_group": block.vertex_group or None, "range": [rnd(block.slider_min), rnd(block.slider_max)],
             "data_hash": _quantised_hash(_foreach(block.data, "co", 3, np.float32)), **deltas(block)}
            for block in keys.key_blocks]}
    return entry


def _vertex_weights(obj):
    groups = {group.index: group.name for group in obj.vertex_groups}
    if not groups or obj.type != "MESH": return None
    stats = {name: {"vertices": 0, "max": 0.0} for name in groups.values()}
    influences, unnormalised = {}, 0
    for vertex in obj.data.vertices:
        weights = [(groups[g.group], g.weight) for g in vertex.groups if g.group in groups and g.weight > 0]
        influences[len(weights)] = influences.get(len(weights), 0) + 1
        if weights and abs(sum(w for _, w in weights) - 1.0) > 1e-3: unnormalised += 1
        for name, weight in weights:
            stats[name]["vertices"] += 1; stats[name]["max"] = max(stats[name]["max"], weight)
    for value in stats.values(): value["max"] = rnd(value["max"])
    return {"groups": stats, "influence_histogram": {str(k): v for k, v in sorted(influences.items())},
            "max_influences": max(influences, default=0), "unweighted_vertices": influences.get(0, 0),
            "unnormalised_vertices": unnormalised}


def _object(obj, view_layer):
    from mathutils import Vector
    corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box] if obj.type in {"MESH", "CURVE", "SURFACE", "FONT", "META", "ARMATURE"} else []
    anim = obj.animation_data
    slot = getattr(anim, "action_slot", None) if anim else None
    return {"name": obj.name, "type": obj.type, "data": obj.data.name if obj.data else None,
            "parent": obj.parent.name if obj.parent else None, "parent_type": obj.parent_type,
            "parent_bone": obj.parent_bone or None, "collections": sorted(c.name for c in obj.users_collection),
            "matrix_world": [vec(row) for row in obj.matrix_world],
            "world_bbox": {"min": vec(min(c[i] for c in corners) for i in range(3)),
                           "max": vec(max(c[i] for c in corners) for i in range(3))} if corners else None,
            "hide_render": obj.hide_render, "visible": obj.visible_get(view_layer=view_layer),
            "material_slots": [{"material": s.material.name if s.material else None, "link": s.link} for s in obj.material_slots],
            "modifiers": [{"name": m.name, "type": m.type, "show_render": m.show_render, "show_viewport": m.show_viewport,
                           "object": m.object.name if getattr(m, "object", None) else None} for m in obj.modifiers],
            "constraints": [{"name": c.name, "type": c.type, "mute": c.mute} for c in obj.constraints],
            "vertex_groups": [g.name for g in obj.vertex_groups], "vertex_weights": _vertex_weights(obj),
            "animation": {"action": anim.action.name if anim.action else None,
                          "slot": slot.identifier if slot is not None else None} if anim else None}


def _armature(arm):
    bones = []
    for bone in arm.bones:
        depth, parent = 0, bone.parent
        while parent is not None: depth += 1; parent = parent.parent
        bones.append({"name": bone.name, "parent": bone.parent.name if bone.parent else None, "depth": depth,
                      "head": vec(bone.head_local), "tail": vec(bone.tail_local), "deform": bone.use_deform,
                      "connected": bone.use_connect})
    return {"name": arm.name, "bones": sorted(bones, key=lambda b: b["name"]), "bone_count": len(bones),
            "roots": sorted(b["name"] for b in bones if b["parent"] is None),
            "max_depth": max((b["depth"] for b in bones), default=0)}


EASING = ("CONSTANT", "LINEAR", "BEZIER", "SINE", "QUAD", "CUBIC", "QUART", "QUINT", "EXPO", "CIRC", "BACK", "BOUNCE", "ELASTIC")


def _fcurve(curve, slot=None):
    import numpy as np
    points = curve.keyframe_points
    return {"slot": slot, "data_path": curve.data_path, "index": curve.array_index, "keys": len(points),
            "keys_hash": _quantised_hash(_foreach(points, "co", 2, np.float32), _foreach(points, "handle_left", 2, np.float32),
                                         _foreach(points, "handle_right", 2, np.float32),
                                         [EASING.index(p.interpolation) if p.interpolation in EASING else -1 for p in points]),
            "interpolation": sorted({p.interpolation for p in points})}


def _action(action):
    curves, slots = [], None
    if hasattr(action, "slots"):
        slots = [{"identifier": s.identifier, "target_id_type": s.target_id_type} for s in action.slots]
        for layer in getattr(action, "layers", []):
            for strip in layer.strips:
                for slot in action.slots:
                    bag = strip.channelbag(slot)
                    if bag is not None: curves += [_fcurve(c, slot.identifier) for c in bag.fcurves]
    if not curves and "fcurves" in action.bl_rna.properties:  # legacy actions on builds that still expose them
        curves = [_fcurve(c) for c in action.fcurves]
    return {"name": action.name, "frame_range": vec(action.frame_range), "slots": slots,
            "fcurves": sorted(curves, key=lambda c: (c["slot"] or "", c["data_path"], c["index"]))}


def _moments(points, scale=None):
    """Order-free summary of a point set: count, column sums and the upper triangle of the product sums. Sums, not
    means, so one changed point moves them by its own change whatever the point count. `scale` is the largest raw
    float32 coordinate behind the points, which bounds their rounding error."""
    import numpy as np
    points = np.asarray(points, dtype=np.float64)
    if not len(points): return {"count": 0}
    products = points.T @ points
    return {"count": int(len(points)), "scale": rnd(np.abs(points).max() if scale is None else scale),
            "sum": [round(float(v), 9) + 0.0 for v in points.sum(0)],
            "products": [round(float(v), 9) + 0.0 for v in products[np.triu_indices(points.shape[1])]]}


def _deform_samples(scene, view_layer, poses):
    """Moments of each visible mesh's unique evaluated world positions at its rig's sampled frames. A GLB roundtrip
    duplicates seam vertices with bit-identical positions and weights, so deduplicating exact float32 rows makes this
    split-invariant, and lost bone rotation (which leaves bone heads in place) still moves the deformed points."""
    import bpy
    import numpy as np
    current, plan = scene.frame_current, {}
    for obj in sorted(_evidence_meshes(scene, view_layer), key=lambda o: o.name):
        rig = next((m.object for m in obj.modifiers if m.type == "ARMATURE" and m.object), None)
        plan[obj.name] = (poses.get(rig.name, {}).get("frames") if rig else None) or [scene.frame_start]
    samples = {name: {"frames": frames, "moments": []} for name, frames in plan.items()}
    # Sample what the LAS export writes: skinning only. It does not apply other modifiers (they are reported as
    # format losses), so evaluating them here would flag a clean roundtrip. Viewport flags are restored afterwards.
    toggled = [(m, m.show_viewport) for name in plan for m in scene.objects[name].modifiers]
    for modifier, _ in toggled: modifier.show_viewport = modifier.type == "ARMATURE"
    try:
        for frame in sorted({f for frames in plan.values() for f in frames}):
            scene.frame_set(frame)
            depsgraph = bpy.context.evaluated_depsgraph_get()
            for name, frames in plan.items():
                if frame not in frames: continue
                evaluated = scene.objects[name].evaluated_get(depsgraph)
                mesh = evaluated.to_mesh()
                local = np.unique(_foreach(mesh.vertices, "co", 3, np.float32).reshape(-1, 3), axis=0)
                evaluated.to_mesh_clear()
                matrix = np.array(evaluated.matrix_world, dtype=np.float64)
                world = local.astype(np.float64) @ matrix[:3, :3].T + matrix[:3, 3]
                samples[name]["moments"].append(_moments(world, max(float(np.abs(local).max()), float(np.abs(world).max())) if len(local) else 0.0))
    finally:
        for modifier, shown in toggled: modifier.show_viewport = shown
        scene.frame_set(current)
    return samples


def _object_samples(scene, cap=121):
    """World matrices of every object moved by its own or an ancestor's action, at every frame of that action's range
    (evenly thinned to `cap`), so lost, truncated or briefly flattened object-level animation shows without an
    armature, including a mesh carried by an animated parent Empty."""
    samples, current = {}, scene.frame_current
    for obj in sorted(scene.objects, key=lambda o: o.name):
        if any(m.type == "ARMATURE" and m.object for m in getattr(obj, "modifiers", [])):
            continue  # skinned: glTF stores it in armature space; deform_samples cover its world-space motion
        mover = obj
        while mover is not None and not (mover.animation_data and mover.animation_data.action): mover = mover.parent
        if mover is None: continue
        low, high = (int(round(v)) for v in mover.animation_data.action.frame_range)
        count = min(cap, high - low + 1)
        frames = sorted({int(round(low + (high - low) * i / max(count - 1, 1))) for i in range(count)})
        samples[obj.name] = {"frames": frames, "matrices": [], "driven_by": mover.name}
    for frame in sorted({f for sample in samples.values() for f in sample["frames"]}):
        scene.frame_set(frame)
        for name, sample in samples.items():
            if frame in sample["frames"]:
                sample["matrices"].append([vec(row) for row in scene.objects[name].matrix_world])
    scene.frame_set(current)
    return samples


def _pose_samples(scene, count=5):
    """World-space bone heads at evenly spaced frames over the action's range (rest frame without an action):
    evaluated motion that survives the curve resampling and channel renames of a GLB roundtrip, so lost or truncated
    animation shows. Tails are left out because glTF stores none and the importer guesses bone length."""
    samples, current = {}, scene.frame_current
    for obj in sorted((o for o in scene.objects if o.type == "ARMATURE"), key=lambda o: o.name):
        action = obj.animation_data.action if obj.animation_data else None
        low, high = action.frame_range if action is not None else (scene.frame_start, scene.frame_start)
        frames = sorted({int(round(low + (high - low) * i / (count - 1))) for i in range(count)})
        bones = {bone.name: [] for bone in obj.pose.bones}
        for frame in frames:
            scene.frame_set(frame)
            for bone in obj.pose.bones:
                bones[bone.name].append(vec(obj.matrix_world @ bone.head))
        samples[obj.name] = {"frames": frames, "bones": bones}
    scene.frame_set(current)
    return samples


def manifest(source_label=None):
    """Task-oriented summary of the open scene for planning and parity; not a serialisation of Blender."""
    import bpy
    scene, view_layer, data = bpy.context.scene, bpy.context.view_layer, bpy.data
    result = {
        "schema": SCHEMA, "kind": "scene-manifest",
        "blender": {"version_string": bpy.app.version_string, "build_hash": bpy.app.build_hash.decode()},
        "source": {"file": source_label},
        "scene": {"name": scene.name, "frame_range": [scene.frame_start, scene.frame_end],
                  "fps": rnd(scene.render.fps / scene.render.fps_base), "camera": scene.camera.name if scene.camera else None,
                  "unit_system": scene.unit_settings.system, "unit_scale": rnd(scene.unit_settings.scale_length)},
        "objects": sorted((_object(o, view_layer) for o in scene.objects), key=lambda o: o["name"]),
        "collections": sorted(({"name": c.name, "objects": sorted(o.name for o in c.objects),
                                "children": sorted(ch.name for ch in c.children), "hide_render": c.hide_render}
                               for c in data.collections), key=lambda c: c["name"]),
        "meshes": sorted((_mesh(m) for m in data.meshes if m.users), key=lambda m: m["name"]),
        "materials": sorted((_material(m) for m in data.materials if m.users), key=lambda m: m["name"]),
        "images": sorted((_image(i) for i in data.images if i.users and i.type == "IMAGE"), key=lambda i: i["name"]),
        "armatures": sorted((_armature(a) for a in data.armatures if a.users), key=lambda a: a["name"]),
        "actions": sorted((_action(a) for a in data.actions if a.users), key=lambda a: a["name"]),
        "cameras": sorted(({"name": c.name, "type": c.type, "lens": rnd(c.lens), "ortho_scale": rnd(c.ortho_scale)}
                           for c in data.cameras if c.users), key=lambda c: c["name"]),
        "lights": sorted(({"name": l.name, "type": l.type, "energy": rnd(l.energy), "color": vec(l.color)}
                          for l in data.lights if l.users), key=lambda l: l["name"]),
        "pose_samples": _pose_samples(scene),
        "object_samples": _object_samples(scene),
    }
    result["deform_samples"] = _deform_samples(scene, view_layer, result["pose_samples"])
    result["counts"] = {key: len(result[key]) for key in ("objects", "meshes", "materials", "images", "armatures", "actions")}
    result["counts"]["triangles"] = sum(m["triangles"] for m in result["meshes"])
    result["counts"]["missing_images"] = sum(1 for i in result["images"] if i["missing"])
    result["semantic_checksum"] = semantic_checksum(result)
    return result


def open_blend(path):
    import bpy
    bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False, use_scripts=False)


def make_fixture(out_dir):
    """Build the deterministic lab asset (textured body, coloured head and badge, 3-bone rig with weights, a shape key,
    an action) as <out_dir>/lab-asset.blend plus its external texture. Generated, never a real character."""
    import math
    import os
    import bpy
    bpy.ops.wm.read_factory_settings(use_empty=True)
    os.makedirs(out_dir, exist_ok=True)
    image = bpy.data.images.new("lab-checker", 64, 64)
    pixels = []
    for y in range(64):
        for x in range(64):
            pixels += [0.9, 0.75, 0.2, 1.0] if (x // 8 + y // 8) % 2 else [0.1, 0.35, 0.8, 1.0]
    image.pixels.foreach_set(pixels)
    image.filepath_raw = os.path.join(out_dir, "lab-checker.png")
    image.file_format = "PNG"
    image.save()

    def material(name, color=None, texture=None):
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        bsdf = next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
        bsdf.inputs["Roughness"].default_value = 0.6
        if color is not None:
            bsdf.inputs["Base Color"].default_value = (*color, 1.0); mat.diffuse_color = (*color, 1.0)
        if texture is not None:
            node = mat.node_tree.nodes.new("ShaderNodeTexImage"); node.image = texture
            mat.node_tree.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
        return mat

    def add(name, op, mat, **kwargs):
        op(**kwargs)
        obj = bpy.context.object
        obj.name = obj.data.name = name
        obj.data.materials.append(mat)
        return obj

    body = add("Body", bpy.ops.mesh.primitive_cube_add, material("BodyTextured", texture=image), size=1.0, location=(0, 0, 0.75))
    body.scale = (0.6, 0.35, 0.75); bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    # Explicit sphere: primitive_uv_sphere_add emits faces in a run-dependent order on 4.5.13.
    seg, rings, radius = 24, 12, 0.32
    verts = [(0, 0, radius)] + [(radius * math.sin(math.pi * r / rings) * math.cos(2 * math.pi * s / seg),
                                  radius * math.sin(math.pi * r / rings) * math.sin(2 * math.pi * s / seg),
                                  radius * math.cos(math.pi * r / rings)) for r in range(1, rings) for s in range(seg)]
    verts.append((0, 0, -radius))
    ring = lambda r, s: 1 + (r - 1) * seg + s % seg
    faces = [(0, ring(1, s), ring(1, s + 1)) for s in range(seg)]
    faces += [(ring(r, s), ring(r + 1, s), ring(r + 1, s + 1), ring(r, s + 1)) for r in range(1, rings - 1) for s in range(seg)]
    faces += [(len(verts) - 1, ring(rings - 1, s + 1), ring(rings - 1, s)) for s in range(seg)]
    head_mesh = bpy.data.meshes.new("Head")
    head_mesh.from_pydata(verts, [], faces)
    head = bpy.data.objects.new("Head", head_mesh)
    bpy.context.scene.collection.objects.link(head)
    head.location = (0, 0, 1.85)
    head_mesh.materials.append(material("HeadRed", color=(0.8, 0.08, 0.06)))
    badge = add("Badge", bpy.ops.mesh.primitive_cylinder_add, material("BadgeGreen", color=(0.1, 0.7, 0.2)),
                radius=0.14, depth=0.06, vertices=16, location=(0.22, -0.37, 1.05), rotation=(math.pi / 2, 0, 0))
    basis = head.shape_key_add(name="Basis")
    squash = head.shape_key_add(name="Squash")
    for point in squash.data: point.co.z *= 0.7
    basis.value = squash.value = 0.0  # new-key default differs: 0.0 on 4.5, 1.0 on 5.4 alpha
    bpy.ops.object.armature_add(location=(0, 0, 0))
    rig = bpy.context.object
    rig.name = rig.data.name = "Rig"
    bpy.ops.object.mode_set(mode="EDIT")
    bones = rig.data.edit_bones
    root = bones[0]; root.name = "Root"; root.head, root.tail = (0, 0, 0), (0, 0, 0.75)
    spine = bones.new("Spine"); spine.head, spine.tail, spine.parent, spine.use_connect = (0, 0, 0.75), (0, 0, 1.5), root, True
    neck = bones.new("Neck"); neck.head, neck.tail, neck.parent, neck.use_connect = (0, 0, 1.5), (0, 0, 1.85), spine, True
    bpy.ops.object.mode_set(mode="OBJECT")
    for obj, groups in ((body, ("Root", "Spine")), (head, ("Neck",)), (badge, ("Spine",))):
        obj.parent = rig
        obj.modifiers.new("Armature", "ARMATURE").object = rig
        made = [obj.vertex_groups.new(name=name) for name in groups]
        for vertex in obj.data.vertices:
            if len(made) == 1: made[0].add([vertex.index], 1.0, "REPLACE"); continue
            upper = min(max((obj.matrix_world @ vertex.co).z / 1.5, 0.0), 1.0)
            made[0].add([vertex.index], 1.0 - upper, "REPLACE"); made[1].add([vertex.index], upper, "REPLACE")
    pose = rig.pose.bones["Spine"]
    pose.rotation_mode = "XYZ"
    for frame, angle in ((1, 0.0), (12, 0.2), (24, 0.0)):
        pose.rotation_euler = (0, angle, 0)
        pose.keyframe_insert("rotation_euler", frame=frame)
    rig.animation_data.action.name = "LabSway"
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, 24
    scene.frame_set(1)
    path = os.path.join(out_dir, "lab-asset.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path, relative_remap=True)
    return path


# ---- evidence renders, GLB export and reimport ----------------------------------------------------------------------

VIEWS = {"front": (0.0, 0.0), "three_quarter": (45.0, 15.0), "profile": (90.0, 0.0), "back": (180.0, 0.0)}
PASSES = ("lit", "clay", "object_id", "material_id")
# The existing LAS export settings (scripts/articulated_prop.py); recorded verbatim in every export record.
LAS_GLTF_SETTINGS = {"export_format": "GLB", "export_materials": "EXPORT", "export_cameras": False, "export_lights": False,
                     "export_animations": True, "export_frame_range": True, "export_force_sampling": True,
                     "use_renderable": True}
SEEDED_DEFECTS = ("missing-texture", "omitted-mesh", "material-mismatch", "truncated-animation", "shape-key-damage",
                  "bone-twist-lost", "shape-key-interior-damage")


def id_colour(name):
    """Stable colour per name, so ID passes map back to object and material names."""
    import hashlib
    digest = hashlib.sha256(name.encode()).digest()
    return [round(0.15 + 0.7 * b / 255, 4) for b in digest[:3]]


def _evidence_meshes(scene, view_layer):
    return [o for o in scene.objects if o.type == "MESH" and not o.hide_render and o.visible_get(view_layer=view_layer)]


def camera_spec(scene, view_layer):
    """Fixed orthographic rig framed on the visible meshes; stored outside the asset and reused for the roundtrip."""
    import bpy
    from mathutils import Vector
    depsgraph = bpy.context.evaluated_depsgraph_get()
    points = []
    for obj in _evidence_meshes(scene, view_layer):
        evaluated = obj.evaluated_get(depsgraph)
        points += [evaluated.matrix_world @ Vector(c) for c in evaluated.bound_box]
    if not points: raise RuntimeError("No visible mesh to frame")
    low = [min(p[i] for p in points) for i in range(3)]
    high = [max(p[i] for p in points) for i in range(3)]
    centre = Vector([(a + b) / 2 for a, b in zip(low, high)])
    radius = max((p - centre).length for p in points)  # a bounding sphere frames every view direction uncropped
    return {"target": vec(centre), "ortho_scale": rnd(radius * 2.1),
            "views": VIEWS, "frame": scene.frame_start}


def _rig(scene, spec):
    """Add evidence cameras and lights in their own collection; authored cameras are never touched."""
    import math
    import bpy
    from mathutils import Vector
    collection = bpy.data.collections.new("_LAS_Evidence")
    scene.collection.children.link(collection)
    target, distance = Vector(spec["target"]), spec["ortho_scale"] * 4
    cameras = {}
    for name, (azimuth, elevation) in spec["views"].items():
        az, el = math.radians(azimuth), math.radians(elevation)
        data = bpy.data.cameras.new(f"_LAS_{name}")
        data.type, data.ortho_scale, data.clip_end = "ORTHO", spec["ortho_scale"], distance * 4
        camera = bpy.data.objects.new(f"_LAS_{name}", data)
        collection.objects.link(camera)
        camera.location = target + Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el))) * distance
        camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
        cameras[name] = camera
    for name, rotation, energy in (("key", (0.8, 0.0, 0.6), 3.0), ("fill", (1.1, 0.0, -2.4), 1.2)):
        data = bpy.data.lights.new(f"_LAS_{name}", "SUN"); data.energy = energy
        light = bpy.data.objects.new(f"_LAS_{name}", data); light.rotation_euler = rotation
        collection.objects.link(light)
    return cameras


def render_evidence(out_dir, spec=None, size=256, samples=16):
    """Render every view x pass with fixed settings; returns the evidence record including the camera spec used."""
    import os
    import bpy
    scene, view_layer = bpy.context.scene, bpy.context.view_layer
    # Evaluate bounds in the same pose that will be rendered, regardless of the saved frame.
    scene.frame_set(spec["frame"] if spec is not None else scene.frame_start)
    if spec is None:
        spec = camera_spec(scene, view_layer)
    for obj in scene.objects:  # authored lights would differ after a GLB roundtrip that excludes lights
        if obj.type == "LIGHT": obj.hide_render = True
    cameras = _rig(scene, spec)
    world = bpy.data.worlds.new("_LAS_World"); scene.world = world
    world.color = (0.05, 0.05, 0.05)
    if hasattr(world, "use_nodes"): world.use_nodes = False
    render = scene.render
    render.resolution_x = render.resolution_y = size
    render.resolution_percentage = 100
    render.use_border = render.use_crop_to_border = False
    render.pixel_aspect_x = render.pixel_aspect_y = 1.0  # the camera spec alone then defines the projection
    render.image_settings.color_depth = "8"  # strict PNG consumers require 8-bit samples
    render.film_transparent = True
    render.image_settings.file_format, render.image_settings.color_mode = "PNG", "RGBA"
    scene.view_settings.view_transform, scene.view_settings.look = "Standard", "None"
    palette = {"object": {}, "material": {}}
    for obj in _evidence_meshes(scene, view_layer):
        obj.color = (*id_colour(obj.name), 1.0); palette["object"][obj.name] = id_colour(obj.name)
    for mat in bpy.data.materials:
        mat.diffuse_color = (*id_colour(mat.name), 1.0); palette["material"][mat.name] = id_colour(mat.name)
    os.makedirs(out_dir, exist_ok=True)
    files, timings = [], {}
    import time
    for pass_name in PASSES:
        started = time.perf_counter()
        if pass_name == "lit":
            render.engine = "CYCLES"
            scene.cycles.device, scene.cycles.samples, scene.cycles.seed = "CPU", samples, 20261102
            scene.cycles.use_denoising = False
            render.threads_mode, render.threads = "FIXED", 4
        else:
            render.engine = "BLENDER_WORKBENCH"
            shading = scene.display.shading
            scene.display.render_aa = "OFF"
            shading.light = "STUDIO" if pass_name == "clay" else "FLAT"
            shading.color_type = {"clay": "SINGLE", "object_id": "OBJECT", "material_id": "MATERIAL"}[pass_name]
            shading.single_color = (0.8, 0.8, 0.8)
            shading.show_cavity = shading.show_shadows = shading.show_specular_highlight = False
            shading.show_object_outline = False
        for view, camera in cameras.items():
            scene.camera = camera
            render.filepath = os.path.join(out_dir, f"{view}.{pass_name}.png")
            bpy.ops.render.render(write_still=True)
            files.append(f"{view}.{pass_name}.png")
        timings[pass_name] = round(time.perf_counter() - started, 3)
    return {"timings": timings, "camera_spec": spec, "size": size, "lit": {"engine": "CYCLES", "device": "CPU", "samples": samples, "seed": 20261102},
            "id_passes": {"engine": "BLENDER_WORKBENCH", "aa": "OFF"}, "palette": palette, "files": files,
            "view_transform": "Standard"}


def seed_defect(kind):
    """Deliberately break the in-memory scene after the source evidence and before export (sentinel self-test only)."""
    import bpy
    scene, view_layer = bpy.context.scene, bpy.context.view_layer
    if kind not in SEEDED_DEFECTS: raise ValueError(f"Unknown seeded defect {kind}")
    if kind == "missing-texture":
        image = sorted((i for i in bpy.data.images if i.users and i.source == "FILE"), key=lambda i: i.name)[0]
        if image.packed_file is not None: image.unpack(method="REMOVE")
        image.filepath = "//_las_seeded_missing_texture.png"
        image.reload()
        return {"kind": kind, "image": image.name}
    meshes = sorted(_evidence_meshes(scene, view_layer), key=lambda o: (len(o.data.polygons), o.name))
    if kind == "truncated-animation":  # export_frame_range=True then clips the action to the scene range
        action = sorted((a for a in bpy.data.actions if a.users), key=lambda a: a.name)[0]
        scene.frame_end = int((action.frame_range[0] + action.frame_range[1]) // 2)
        return {"kind": kind, "action": action.name, "scene_frame_end": scene.frame_end}
    if kind == "shape-key-damage":
        mesh = sorted((m for m in bpy.data.meshes if m.users and m.shape_keys), key=lambda m: m.name)[0]
        block = mesh.shape_keys.key_blocks[-1]
        for point, base in zip(block.data, mesh.shape_keys.reference_key.data): point.co = base.co + (point.co - base.co) * 0.5
        return {"kind": kind, "mesh": mesh.name, "key": block.name}
    if kind == "bone-twist-lost":  # flatten rotation curves but keep their keys and range: bone heads do not move
        action = sorted((a for a in bpy.data.actions if a.users), key=lambda a: a.name)[0]
        curves = [c for layer in action.layers for strip in layer.strips for slot in action.slots
                  for c in (strip.channelbag(slot).fcurves if strip.channelbag(slot) else [])]
        flattened = []
        for curve in curves:
            if "rotation" not in curve.data_path: continue
            rest = curve.keyframe_points[0].co[1]
            for point in curve.keyframe_points: point.co[1] = point.handle_left[1] = point.handle_right[1] = rest
            flattened.append(f"{curve.data_path}[{curve.array_index}]")
        return {"kind": kind, "action": action.name, "flattened": flattened}
    if kind == "shape-key-interior-damage":  # zero one non-extreme vertex delta: extrema and max delta are unchanged
        mesh = sorted((m for m in bpy.data.meshes if m.users and m.shape_keys), key=lambda m: m.name)[0]
        block, base = mesh.shape_keys.key_blocks[-1], mesh.shape_keys.reference_key.data
        moved = sorted((((p.co - b.co).length, i) for i, (p, b) in enumerate(zip(block.data, base)) if (p.co - b.co).length > 1e-6))
        index = moved[len(moved) // 2][1]
        block.data[index].co = base[index].co
        return {"kind": kind, "mesh": mesh.name, "key": block.name, "vertex": index}
    if kind == "omitted-mesh":
        meshes[0].hide_render = True
        return {"kind": kind, "object": meshes[0].name}
    target = next(o for o in sorted(meshes, key=lambda o: o.name) if o.material_slots and o.material_slots[0].material)
    current = target.material_slots[0].material
    other = next(m for m in sorted(bpy.data.materials, key=lambda m: m.name) if m != current and m.users)
    target.material_slots[0].material = other
    return {"kind": kind, "object": target.name, "from": current.name, "to": other.name}


def export_glb(path):
    import bpy
    bpy.ops.export_scene.gltf(filepath=str(path), **LAS_GLTF_SETTINGS)
    return {"settings": LAS_GLTF_SETTINGS, "path": str(path)}


def import_glb(path):
    """Import into a factory-empty scene. With several glTF animations the importer activates only one and leaves the
    rest as NLA strips, so an object animated by another clip would look static; activate its first strip (and mute
    that track) and report every such step. Engines read all clips; this is not forgiving a loss."""
    import bpy
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(path))
    activated = []
    for obj in sorted(bpy.context.scene.objects, key=lambda o: o.name):
        anim = obj.animation_data
        if anim is None or anim.action is not None: continue
        strips = [(track, strip) for track in anim.nla_tracks for strip in track.strips if strip.action]
        if not strips: continue
        track, strip = strips[0]
        anim.action = strip.action
        track.mute = True
        activated.append({"object": obj.name, "action": strip.action.name})
    return activated


# ---- typed persistent worker ----------------------------------------------------------------------------------------

REPLY = "@@LAS@@ "
EDIT_OPS = ("location", "rotation_euler", "scale", "hide_render", "material", "shape_key")


class WorkerError(ValueError):
    """A worker request is outside the typed vocabulary or its preconditions."""


def _need(condition, message):
    if not condition: raise WorkerError(message)


def _finite(value, low, high):
    import math
    _need(type(value) in (int, float) and math.isfinite(value) and low <= value <= high, f"value must be a finite number in {low}..{high}")
    return float(value)


class Worker:
    """Long-lived background Blender with a closed command set. Reads are allowed anywhere; every write goes to a new
    path inside `root`. There is no command that evaluates caller-supplied code."""

    def __init__(self, root):
        import os
        import tempfile
        import time
        self.root = os.path.realpath(root)
        _need(os.path.isdir(self.root), "root must be an existing directory")
        self.scratch = tempfile.mkdtemp(prefix="las-worker-")
        self.started, self.calls, self.source, self.allowed = time.time(), 0, None, set()
        self.capabilities = probe()  # resets to factory-empty, so it runs before any file is opened

    def _out(self, value, suffix=None, directory=False):
        import os
        _need(isinstance(value, str) and value and "\0" not in value, "path must be a string")
        path = os.path.realpath(os.path.join(self.root, value))
        _need(os.path.commonpath([path, self.root]) == self.root and path != self.root, "path escapes the worker root")
        _need(not os.path.exists(path), "output path must be new")
        _need(suffix is None or path.lower().endswith(suffix), f"output must end with {suffix}")
        os.makedirs(path if directory else os.path.dirname(path), exist_ok=True)
        return path

    def _loaded(self):
        _need(self.source is not None, "open a .blend first")

    def ping(self):
        import os
        import time
        import bpy
        scene = bpy.context.scene
        return {"pong": True, "pid": os.getpid(), "uptime_s": round(time.time() - self.started, 3), "calls": self.calls,
                "source": self.source, "datablocks": {name: len(getattr(bpy.data, name)) for name in
                ("objects", "meshes", "materials", "images", "cameras", "lights", "worlds", "collections", "actions")},
                "state": {"frame": scene.frame_current, "engine": scene.render.engine, "camera": scene.camera.name if scene.camera else None,
                          "world": scene.world.name if scene.world else None,
                          "resolution": [scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage],
                          "view_transform": scene.view_settings.view_transform}}

    def caps(self):
        return self.capabilities

    def open(self, blend, allow_edit=()):
        import os
        self.source, self.allowed = None, set()  # any open attempt drops the previous scene's authority
        _need(isinstance(blend, str) and blend.lower().endswith(".blend") and os.path.isfile(blend), "blend must be an existing .blend")
        open_blend(blend)
        import bpy
        names = {o.name for o in bpy.context.scene.objects}
        _need(isinstance(allow_edit, (list, tuple)) and set(allow_edit) <= names, "allow_edit must name existing objects")
        self.source, self.allowed = os.path.realpath(blend), set(allow_edit)
        return {"opened": os.path.basename(blend), "allow_edit": sorted(self.allowed), "semantic_checksum": manifest()["semantic_checksum"]}

    def describe_scene(self):
        import os
        self._loaded()
        return manifest(os.path.basename(self.source))

    def render_views(self, out_dir, size=256, samples=16, cameras=None):
        import os
        self._loaded()
        size, samples = int(_finite(size, 64, 512)), int(_finite(samples, 1, 64))
        if cameras is not None:  # view names become file names: only the fixed rig's views are accepted
            _need(isinstance(cameras, dict) and set(cameras) == {"target", "ortho_scale", "views", "frame"}
                  and isinstance(cameras["views"], dict) and set(cameras["views"]) <= set(VIEWS), "cameras must be a camera spec over the fixed views")
            _need(isinstance(cameras["target"], list) and len(cameras["target"]) == 3, "cameras.target must be [x, y, z]")
            [_finite(v, -1e4, 1e4) for v in cameras["target"]]; _finite(cameras["ortho_scale"], 1e-3, 1e4)
            _need(type(cameras["frame"]) is int, "cameras.frame must be an integer")
            for pair in cameras["views"].values():
                _need(isinstance(pair, list) and len(pair) == 2, "views must map to [azimuth, elevation]")
                [_finite(v, -360, 360) for v in pair]
        target = self._out(out_dir, directory=True)
        import bpy
        # ponytail: snapshot/reload costs one save+open per render; a targeted restore if big scenes make that slow.
        snapshot = os.path.join(self.scratch, f"snapshot-{self.calls}.blend")
        bpy.ops.wm.save_as_mainfile(filepath=snapshot, copy=True, relative_remap=True)
        try:
            return render_evidence(target, cameras, size, samples)
        finally:
            open_blend(snapshot)
            os.remove(snapshot)

    def save_copy(self, path):
        import bpy
        self._loaded()
        target = self._out(path, ".blend")
        bpy.ops.wm.save_as_mainfile(filepath=target, copy=True, relative_remap=True)
        return {"path": target}

    def export(self, path):
        self._loaded()
        return export_glb(self._out(path, ".glb"))

    def apply_edit(self, object, op, value, expect_checksum):
        import bpy
        self._loaded()
        _need(object in self.allowed, f"{object!r} is not in this session's allow_edit list")
        _need(op in EDIT_OPS, f"op must be one of {EDIT_OPS}")
        before = manifest()["semantic_checksum"]
        _need(expect_checksum == before, "precondition failed: the scene changed since expect_checksum was read")
        obj = bpy.context.scene.objects[object]
        if op in ("location", "rotation_euler", "scale"):
            _need(isinstance(value, list) and len(value) == 3, "value must be [x, y, z]")
            setattr(obj, op, [_finite(v, 1e-4 if op == "scale" else -1e4, 1e4) for v in value])
        elif op == "hide_render":
            _need(type(value) is bool, "value must be a boolean"); obj.hide_render = value
        elif op == "material":
            _need(isinstance(value, dict) and set(value) == {"slot", "material"}, "value must be {slot, material}")
            _need(type(value["slot"]) is int and 0 <= value["slot"] < len(obj.material_slots), "slot out of range")
            _need(value["material"] in bpy.data.materials, "material must already exist")
            _need(obj.material_slots[value["slot"]].link == "OBJECT" or obj.data.users == 1,
                  "slot is linked to mesh data shared with other objects")
            obj.material_slots[value["slot"]].material = bpy.data.materials[value["material"]]
        else:
            keys = obj.data.shape_keys if obj.type == "MESH" else None
            _need(keys is not None and isinstance(value, dict) and set(value) == {"key", "value"} and value["key"] in keys.key_blocks,
                  "value must be {key, value} for an existing shape key")
            _need(obj.data.users == 1, "shape keys live on mesh data shared with other objects")
            block = keys.key_blocks[value["key"]]
            block.value = _finite(value["value"], block.slider_min, block.slider_max)
        bpy.context.view_layer.update()  # matrix_world is stale until the depsgraph re-evaluates
        return {"object": object, "op": op, "before": before, "after": manifest()["semantic_checksum"]}

    def handle(self, request):
        import time
        started = time.perf_counter()
        command, args = request.get("cmd"), request.get("args") or {}
        handlers = {"ping": self.ping, "caps": self.caps, "open": self.open, "describe_scene": self.describe_scene,
                    "render_views": self.render_views, "save_copy": self.save_copy, "export": self.export,
                    "apply_edit": self.apply_edit}
        try:
            _need(command in handlers, f"unknown command {command!r}")
            _need(isinstance(args, dict), "args must be an object")
            result = {"ok": True, "result": handlers[command](**args)}
        except (WorkerError, TypeError) as exc:
            result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:500]}
        except Exception as exc:  # a Blender failure is reported, and the worker stays alive for the next call
            result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:500]}
        self.calls += 1
        return {"id": request.get("id"), "ms": round((time.perf_counter() - started) * 1000, 2), **result}


def serve(root):
    """JSON lines on stdin; each reply is one stdout line prefixed REPLY, so Blender's own output is ignorable."""
    worker = Worker(root)
    sys.stdout.write(REPLY + json.dumps({"ready": True, "blender": worker.capabilities["blender"]["version_string"]}) + "\n")
    sys.stdout.flush()
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line: continue
            try: request = json.loads(line)
            except ValueError: request = {"cmd": None}
            if not isinstance(request, dict): request = {"cmd": None}
            if request.get("cmd") == "quit": break
            reply = worker.handle(request)
            sys.stdout.write(REPLY + json.dumps(reply, allow_nan=False) + "\n")
            sys.stdout.flush()
    finally:
        import shutil
        shutil.rmtree(worker.scratch, ignore_errors=True)  # snapshot scratch is private to this worker


# ---- known-bad corpus -----------------------------------------------------------------------------------------------

# Source-level defects for the benchmark corpus: each variant is the lab asset with exactly one labelled fault saved
# into the .blend. Kinds shared with the sentinel reuse seed_defect; the rest are corpus-only.
CORPUS_DEFECTS = {
    "flipped-normals": "Head faces wound inward (normals point into the sphere)",
    "missing-uvs": "Body loses its only UV map, so its checker texture samples one texel",
    "broken-weights": "Body's Spine group weights zeroed: upper vertices no longer follow the spine",
    "mesh-hole": "Body loses two faces: an open, non-manifold box",
    "transform-offset": "Head moved 0.12 up, off the neck",
    "duplicate-overlap": "Badge duplicated in place: coincident overlapping geometry",
    "missing-texture": "Body's external texture file path broken",
    "material-mismatch": "Badge shows Body's textured material",
    "omitted-mesh": "Body hidden from render",
    "shape-key-damage": "Head Squash key deltas halved",
    "shape-key-interior-damage": "one interior Squash vertex delta zeroed",
    "bone-twist-lost": "Spine twist keys flattened (keys and range kept)",
}


def corpus_defect(kind):
    import bpy
    if kind not in CORPUS_DEFECTS: raise ValueError(f"Unknown corpus defect {kind}")
    if kind in SEEDED_DEFECTS: return seed_defect(kind)
    objects = bpy.data.objects
    if kind == "flipped-normals":
        mesh = objects["Head"].data
        for polygon in mesh.polygons: polygon.flip()
        mesh.update()
        return {"kind": kind, "object": "Head"}
    if kind == "missing-uvs":
        mesh = objects["Body"].data
        while mesh.uv_layers: mesh.uv_layers.remove(mesh.uv_layers[0])
        return {"kind": kind, "object": "Body"}
    if kind == "broken-weights":
        body = objects["Body"]
        body.vertex_groups["Spine"].add([v.index for v in body.data.vertices], 0.0, "REPLACE")
        return {"kind": kind, "object": "Body", "group": "Spine"}
    if kind == "mesh-hole":
        import bmesh
        mesh = objects["Body"].data
        work = bmesh.new(); work.from_mesh(mesh); work.faces.ensure_lookup_table()
        bmesh.ops.delete(work, geom=[work.faces[0], work.faces[1]], context="FACES_ONLY")
        work.to_mesh(mesh); work.free(); mesh.update()
        return {"kind": kind, "object": "Body", "faces_removed": 2}
    if kind == "transform-offset":
        objects["Head"].location.z += 0.12
        return {"kind": kind, "object": "Head", "dz": 0.12}
    twin = objects["Badge"].copy(); twin.data = objects["Badge"].data.copy(); twin.name = "BadgeDuplicate"
    bpy.context.scene.collection.objects.link(twin)
    return {"kind": kind, "object": "BadgeDuplicate"}


def make_corpus_variant(clean_blend, kind, out_path):
    import bpy
    open_blend(clean_blend)
    label = corpus_defect(kind)
    bpy.ops.wm.save_as_mainfile(filepath=str(out_path), copy=True, relative_remap=True)
    return {"kind": "corpus-variant", "label": label, "blend": str(out_path)}


def _evidence(args):
    """manifest -> fixed-camera evidence -> (fresh reload -> optional seeded defect -> LAS GLB export)."""
    import os
    os.makedirs(args.out_dir, exist_ok=True)
    if args.export and not args.blend: raise ValueError("--export needs --blend")
    activated = open_blend(args.blend) if args.blend else import_glb(args.glb)
    label = os.path.basename(args.blend or args.glb)

    def write(name, value):
        with open(os.path.join(args.out_dir, name), "w", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(value, indent=2, sort_keys=True) + "\n")

    write("manifest.json", manifest(label))
    spec = json.load(open(args.cameras, encoding="utf-8")) if args.cameras else None
    evidence = render_evidence(os.path.join(args.out_dir, "renders"), spec)
    write("evidence.json", evidence)
    result = {"kind": "evidence", "source": label, "evidence": "evidence.json", "manifest": "manifest.json"}
    if args.glb: result["import_activated_clips"] = activated
    if args.export:
        open_blend(args.blend)  # export from the untouched file, not from the evidence-rigged scene
        result["seeded_defect"] = seed_defect(args.seed_defect) if args.seed_defect else None
        result["export"] = export_glb(args.export)
    return result


def _main(argv):
    import argparse
    parser = argparse.ArgumentParser(prog="blender_lab_bpy")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("probe").add_argument("--out", required=True)
    manifest_parser = commands.add_parser("manifest")
    manifest_parser.add_argument("--blend", required=True)
    manifest_parser.add_argument("--out", required=True)
    fixture_parser = commands.add_parser("make-fixture")
    fixture_parser.add_argument("--out-dir", required=True)
    fixture_parser.add_argument("--out", required=True)
    evidence_parser = commands.add_parser("evidence")
    source = evidence_parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--blend")
    source.add_argument("--glb")
    evidence_parser.add_argument("--out-dir", required=True)
    evidence_parser.add_argument("--out", required=True)
    evidence_parser.add_argument("--cameras")
    evidence_parser.add_argument("--export")
    evidence_parser.add_argument("--seed-defect", choices=SEEDED_DEFECTS)
    variant_parser = commands.add_parser("corpus-variant")
    variant_parser.add_argument("--blend", required=True)
    variant_parser.add_argument("--kind", required=True, choices=sorted(CORPUS_DEFECTS))
    variant_parser.add_argument("--out-blend", required=True)
    variant_parser.add_argument("--out", required=True)
    commands.add_parser("serve").add_argument("--root", required=True)
    scene_parser = commands.add_parser("scene-v1")  # exact studio.dcc-scene/v1 observation (blender_scene_probe)
    scene_parser.add_argument("--blend", required=True)
    scene_parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.command == "serve": return serve(args.root)
    if args.command == "scene-v1":
        import os
        import bpy
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import blender_scene_probe
        return blender_scene_probe.observe(bpy, args.blend, args.out)  # writes its own exclusive output
    if args.command == "probe": result = probe()
    elif args.command == "manifest":
        import os
        open_blend(args.blend); result = manifest(os.path.basename(args.blend))
    elif args.command == "evidence": result = _evidence(args)
    elif args.command == "corpus-variant": result = make_corpus_variant(args.blend, args.kind, args.out_blend)
    else: result = {"kind": "fixture", "blend": make_fixture(args.out_dir)}
    with open(args.out, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")


if __name__ == "__main__":
    _main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
