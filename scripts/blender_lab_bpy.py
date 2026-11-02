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


def _main(argv):
    import argparse
    parser = argparse.ArgumentParser(prog="blender_lab_bpy")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("probe").add_argument("--out", required=True)
    args = parser.parse_args(argv)
    result = probe()
    with open(args.out, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")


if __name__ == "__main__":
    _main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
