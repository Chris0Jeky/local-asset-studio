"""Create a bounded authored articulated chest study with a fixed Blender script.

The adapter accepts numeric dimensions only. It never loads user Blender files,
executes caller-supplied code, or starts any command other than its configured
local Blender executable with a reviewed generated script.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys


DEFAULT_BLENDER = Path(r"C:\AI\blender-4.5.13-windows-x64\blender.exe")
VIEW_NAMES = ("closed", "open", "front", "side")


class ArticulatedPropError(ValueError):
    """A prop request, generated result, or configured Blender is invalid."""


def require(condition, message):
    if not condition:
        raise ArticulatedPropError(message)


def file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _absolute_new_directory(value):
    path = Path(value).expanduser()
    require(path.is_absolute(), "output_root must be absolute")
    path = path.resolve()
    require(not path.exists(), "output_root must be new")
    return path


def _number(value, name, low, high):
    require(type(value) in {int, float} and math.isfinite(float(value)) and low <= float(value) <= high,
            f"{name} must be a finite number from {low} to {high}")
    return float(value)


def normalize_options(options):
    require(isinstance(options, dict), "options must be an object")
    allowed = {"width", "depth", "body_height", "lid_height", "clearance", "render_size", "samples"}
    require(set(options) <= allowed, "Unknown articulated prop option")
    result = {
        "width": _number(options.get("width", 2.4), "width", 0.4, 8.0),
        "depth": _number(options.get("depth", 1.4), "depth", 0.3, 5.0),
        "body_height": _number(options.get("body_height", 1.0), "body_height", 0.2, 5.0),
        "lid_height": _number(options.get("lid_height", 0.65), "lid_height", 0.15, 3.0),
        "clearance": _number(options.get("clearance", 0.03), "clearance", 0.005, 0.2),
    }
    render_size = options.get("render_size", 192)
    samples = options.get("samples", 8)
    require(type(render_size) is int and 64 <= render_size <= 512, "render_size must be 64..512")
    require(type(samples) is int and 1 <= samples <= 32, "samples must be 1..32")
    require(result["clearance"] < result["lid_height"] / 2, "clearance must leave meaningful lid geometry")
    result.update(render_size=render_size, samples=samples, fps=24, open_degrees=70,
                  keyframes={"closed": 1, "open": 20, "hold": 40, "close": 60})
    return result


def describe():
    return {
        "adapter": "articulated-prop", "schema_version": 1,
        "operations": ["describe", "preflight", "execute", "inspect", "export"],
        "fixed_argv": ["--background", "--factory-startup", "--disable-autoexec", "--python", "<generated-script>", "--", "--config", "<generated-config>"],
        "asset": "authored stylized chest with rear X-axis lid hinge and a 0-70 degree open/hold/close clip",
        "outputs": ["chest.blend", "chest.glb", "views/closed.png", "views/open.png", "views/front.png", "views/side.png"],
        "limitations": ["No generation, automatic segmentation, or automatic rigging.", "Engine collision and animation acceptance remain separate checks."],
    }


def preflight(blender_path=DEFAULT_BLENDER):
    executable = Path(blender_path).expanduser()
    require(executable.is_absolute(), "blender_path must be absolute")
    executable = executable.resolve()
    require(executable.is_file() and executable.name.lower() == "blender.exe", "Configured Blender executable is missing")
    return {"path": str(executable), "sha256": file_sha(executable), "start_command_not_run": True,
            "required_argv": describe()["fixed_argv"]}


def _script():
    return r'''import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector


config_path = Path(sys.argv[sys.argv.index("--") + 2]).resolve()
config = json.loads(config_path.read_text(encoding="utf-8"))
output = Path(config["output_root"]).resolve()
if not bpy.app.background:
    raise RuntimeError("Background Blender required")
if not output.is_dir() or config_path.parent != output:
    raise RuntimeError("Config must live in the owned output directory")


def cube(name, dimensions, location, material, bevel=0.04):
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        modifier = obj.modifiers.new("Soft edges", "BEVEL")
        modifier.width = bevel
        modifier.segments = 2
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    obj.data.materials.append(material)
    return obj


def material(name, color, metallic=0.0):
    result = bpy.data.materials.new(name)
    result.diffuse_color = (*color, 1.0)
    result.metallic = metallic
    result.roughness = 0.42
    return result


def point_camera(camera, location, target):
    camera.location = location
    camera.rotation_euler = (Vector(target) - camera.location).to_track_quat("-Z", "Y").to_euler()


def mesh_record(obj):
    return {"name": obj.name, "triangles": sum(len(face.vertices) - 2 for face in obj.data.polygons),
            "dimensions": [round(value, 6) for value in obj.dimensions], "materials": [slot.name for slot in obj.data.materials]}


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = config["samples"]
scene.cycles.seed = 20260911
scene.render.threads_mode = "FIXED"
scene.render.threads = 4
scene.render.resolution_x = config["render_size"]
scene.render.resolution_y = config["render_size"]
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.render.film_transparent = True
scene.render.fps = config["fps"]
scene.frame_start = config["keyframes"]["closed"]
scene.frame_end = config["keyframes"]["close"]

wood = material("Chest wood", (0.22, 0.07, 0.025))
metal = material("Hinge brass", (0.34, 0.16, 0.025), 0.7)
width, depth = config["width"], config["depth"]
body_height, lid_height, clearance = config["body_height"], config["lid_height"], config["clearance"]
body = cube("ChestBody", (width, depth, body_height), (0, 0, body_height / 2), wood)
hinge = (0, depth / 2, body_height + clearance)
lid = cube("ChestLid", (width, depth, lid_height), hinge, wood)
for vertex in lid.data.vertices:
    vertex.co += Vector((0, -depth / 2, lid_height / 2))
lid.data.update()
lid["hinge_axis"] = "X"
lid["open_limit_degrees"] = config["open_degrees"]
lid["clearance"] = clearance
for sign in (-1, 1):
    bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.055, depth=width * 0.16,
                                        location=(sign * width * 0.36, depth / 2 + 0.02, body_height + clearance),
                                        rotation=(0, math.pi / 2, 0))
    pin = bpy.context.object
    pin.name = "HingePinLeft" if sign < 0 else "HingePinRight"
    pin.data.materials.append(metal)
collision = cube("CollisionProxy", (width * 1.02, depth * 1.02, body_height + lid_height),
                 (0, 0, (body_height + lid_height) / 2), metal, bevel=0.0)
collision.display_type = "WIRE"
collision.hide_render = True
collision["collision_proxy"] = True

lid.rotation_euler = (0, 0, 0)
for frame, angle in ((config["keyframes"]["closed"], 0), (config["keyframes"]["open"], -config["open_degrees"]),
                     (config["keyframes"]["hold"], -config["open_degrees"]), (config["keyframes"]["close"], 0)):
    lid.rotation_euler[0] = math.radians(angle)
    lid.keyframe_insert(data_path="rotation_euler", index=0, frame=frame)
action = lid.animation_data.action
action.name = "ChestLidOpenHoldClose"
for curve in action.fcurves:
    for point in curve.keyframe_points:
        point.interpolation = "LINEAR"

bpy.ops.object.camera_add()
camera = bpy.context.object
camera.name = "InspectionCamera"
scene.camera = camera
camera.data.lens = 52
for location, energy in (((3.6, -4.2, 4.0), 850), ((-3.0, -2.0, 3.4), 500)):
    bpy.ops.object.light_add(type="AREA", location=location)
    light = bpy.context.object
    light.data.energy = energy
    light.data.shape = "DISK"
    light.data.size = 4
    light.rotation_euler = (0.5, 0, 0)

views = {
    "closed": (config["keyframes"]["closed"], (3.6, -4.2, 3.0)),
    "open": (config["keyframes"]["open"], (3.6, -4.2, 3.0)),
    "front": (config["keyframes"]["closed"], (0, -5.4, 1.9)),
    "side": (config["keyframes"]["open"], (5.1, 0, 2.5)),
}
(output / "views").mkdir(exist_ok=False)
for name, (frame, location) in views.items():
    scene.frame_set(frame)
    point_camera(camera, location, (0, 0, body_height * 0.65))
    scene.render.filepath = str(output / "views" / f"{name}.png")
    bpy.ops.render.render(write_still=True)

scene.frame_set(config["keyframes"]["closed"])
bpy.ops.wm.save_as_mainfile(filepath=str(output / "chest.blend"))
bpy.ops.export_scene.gltf(filepath=str(output / "chest.glb"), export_format="GLB", export_materials="EXPORT",
                          export_cameras=False, export_lights=False, export_animations=True,
                          export_frame_range=True, export_force_sampling=True, use_renderable=True)
parts = [mesh_record(item) for item in bpy.context.scene.objects if item.type == "MESH"]
action_name = action.name
render_record = {"engine": scene.render.engine, "device": scene.cycles.device, "threads": scene.render.threads,
                 "samples": scene.cycles.samples, "size": [scene.render.resolution_x, scene.render.resolution_y],
                 "views": [f"views/{name}.png" for name in views]}
clip_range = [scene.frame_start, scene.frame_end]
scene.frame_set(config["keyframes"]["open"])
open_rotation_degrees = round(math.degrees(lid.rotation_euler.x), 6)
scene.frame_set(config["keyframes"]["closed"])
closed_rotation_degrees = round(math.degrees(lid.rotation_euler.x), 6)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(output / "chest.glb"))
reimported_meshes = sorted(item.name for item in bpy.context.scene.objects if item.type == "MESH")
reimported_actions = sorted(item.name for item in bpy.data.actions)
metadata = {
    "schema_version": 1, "asset": "authored-stylized-articulated-chest", "blender": bpy.app.version_string,
    "parts": parts, "materials": [item.name for item in bpy.data.materials],
    "hinge": {"axis": "X", "rear_edge": [0, depth / 2, body_height + clearance],
              "open_limit_degrees": config["open_degrees"], "clearance": clearance,
              "closed_rotation_degrees": closed_rotation_degrees, "open_rotation_degrees": open_rotation_degrees},
    "clip": {"name": action_name, "fps": config["fps"], "keyframes": config["keyframes"],
             "range": clip_range},
    "render": render_record,
    "glb_reimport": {"mesh_names": reimported_meshes, "actions": reimported_actions,
                     "lid_present": "ChestLid" in reimported_meshes},
    "limitations": ["Authored baseline only; no automatic segmentation or rigging.",
                    "Collision proxy remains in BLEND only; GLB excludes this hidden helper. Engine collision needs authoring and validation.",
                    "Rendered views inspect this baseline; they do not accept art, mechanics, or licensing."],
}
(output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
print("ARTICULATED_PROP_METADATA=" + json.dumps(metadata, separators=(",", ":")))
'''


def command_for(blender_path, script_path, config_path):
    return [str(blender_path), "--background", "--factory-startup", "--disable-autoexec", "--python", str(script_path),
            "--", "--config", str(config_path)]


def _artifacts(output_root):
    return [{"path": path.relative_to(output_root).as_posix(), "sha256": file_sha(path), "bytes": path.stat().st_size}
            for path in sorted(output_root.rglob("*")) if path.is_file()]


def _check_output(output_root):
    expected = [output_root / "chest.blend", output_root / "chest.glb", output_root / "metadata.json",
                *(output_root / "views" / f"{name}.png" for name in VIEW_NAMES)]
    require(all(path.is_file() and path.stat().st_size > 0 for path in expected), "Blender did not produce every required artifact")
    metadata = json.loads((output_root / "metadata.json").read_text(encoding="utf-8"))
    require(metadata.get("hinge", {}).get("axis") == "X" and metadata["hinge"].get("open_limit_degrees") == 70,
            "Metadata lacks the required rear X-axis 0-70 degree hinge")
    require(metadata.get("clip", {}).get("name") == "ChestLidOpenHoldClose", "Animation clip missing")
    require('CollisionProxy' not in metadata.get('glb_reimport', {}).get('mesh_names', []), 'Hidden collision helper leaked into visible GLB')
    require(metadata.get("render", {}).get("device") == "CPU", "Render did not report CPU device")
    require(metadata.get("render", {}).get("threads") == 4, "Render did not report the fixed CPU thread cap")
    require(metadata.get("render", {}).get("views") == [f"views/{name}.png" for name in VIEW_NAMES],
            "Metadata does not list the four required inspection views")
    require(metadata.get("hinge", {}).get("closed_rotation_degrees") == 0
            and metadata["hinge"].get("open_rotation_degrees") == -70, "Hinge transform evidence is incorrect")
    require(metadata.get("glb_reimport", {}).get("lid_present") is True, "GLB reimport did not preserve the lid mesh")
    return metadata


def execute(output_root, options=None, blender_path=DEFAULT_BLENDER, timeout=180):
    """Run the fixed local Blender study after validating bounded numeric options."""
    target = _absolute_new_directory(output_root)
    settings = normalize_options({} if options is None else options)
    runtime = preflight(blender_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.mkdir()
    try:
        script_path = target / "_articulated_prop.py"
        config_path = target / "config.json"
        script_path.write_text(_script(), encoding="utf-8", newline="\n")
        config_path.write_text(json.dumps({**settings, "output_root": str(target)}, indent=2) + "\n", encoding="utf-8", newline="\n")
        command = command_for(runtime["path"], script_path, config_path)
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                   timeout=timeout, check=False)
        (target / "blender-log.json").write_text(json.dumps({"argv": command[1:], "returncode": completed.returncode,
            "stdout": completed.stdout, "stderr": completed.stderr}, indent=2) + "\n", encoding="utf-8", newline="\n")
        require(completed.returncode == 0, "Blender articulated prop render failed")
        metadata = _check_output(target)
        return {"operation_id": "articulated-prop", "state": "completed", "runtime": runtime,
                "artifacts": _artifacts(target), "metadata": metadata,
                "measurement_method": "CPU Blender Cycles fixed-camera RGBA renders and exported animation metadata"}
    except Exception as exc:
        (target / "failure.json").write_text(json.dumps({"error": str(exc)}, indent=2) + "\n", encoding="utf-8", newline="\n")
        raise


def inspect(output_root):
    root = Path(output_root).expanduser().resolve()
    require(root.is_dir(), "output_root is missing")
    metadata = _check_output(root)
    return {"artifacts": _artifacts(root), "metadata": metadata}


def export(output_root):
    return inspect(output_root)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("describe")
    preflight_parser = commands.add_parser("preflight")
    preflight_parser.add_argument("--blender", default=str(DEFAULT_BLENDER))
    execute_parser = commands.add_parser("execute")
    execute_parser.add_argument("--output-root", required=True)
    execute_parser.add_argument("--options-json", default="{}")
    execute_parser.add_argument("--blender", default=str(DEFAULT_BLENDER))
    inspect_parser = commands.add_parser("inspect")
    inspect_parser.add_argument("--output-root", required=True)
    export_parser = commands.add_parser("export")
    export_parser.add_argument("--output-root", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "describe": result = describe()
        elif args.command == "preflight": result = preflight(args.blender)
        elif args.command == "execute": result = execute(args.output_root, json.loads(args.options_json), args.blender)
        elif args.command == "inspect": result = inspect(args.output_root)
        else: result = export(args.output_root)
        print(json.dumps(result, indent=2))
        return 0
    except (ArticulatedPropError, OSError, ValueError, TypeError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
