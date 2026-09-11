"""Build and verify a bounded Godot asset project from Studio atlas/GLB inputs.

This adapter only starts a caller-selected Godot executable with fixed argument
arrays.  It never evaluates manifest text as code or runs a command supplied by
asset metadata.  Inputs are confined to ``input_root`` and each invocation owns
a previously nonexistent ``output_root``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

from game_asset_pipeline import file_sha, read_json


MAX_MANIFEST_BYTES = 4 * 1024 * 1024
FILTERS = {"nearest": 1, "linear": 2}


class GodotAdapterError(ValueError):
    """A bad adapter request or an engine result that misses the contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise GodotAdapterError(message)


def _absolute_directory(value: str | Path, label: str, exists: bool = True) -> Path:
    path = Path(value).expanduser()
    _require(path.is_absolute(), f"{label} must be an absolute path")
    path = path.resolve()
    if exists:
        _require(path.is_dir(), f"{label} is not a directory: {path}")
    return path


def _input_file(input_root: Path, value: str, label: str) -> Path:
    candidate = Path(value)
    _require(not candidate.is_absolute(), f"{label} must be relative to input_root")
    resolved = (input_root / candidate).resolve()
    _require(resolved.is_relative_to(input_root), f"{label} escapes input_root")
    _require(resolved.is_file(), f"{label} is missing: {value}")
    return resolved


def _finite_number(value: Any, label: str) -> float:
    _require(type(value) in (int, float), f"{label} must be a number")
    result = float(value)
    _require(result == result and abs(result) != float("inf"), f"{label} must be finite")
    return result


def _read_atlas_manifest(path: Path) -> dict[str, Any]:
    _require(path.stat().st_size <= MAX_MANIFEST_BYTES, "Atlas manifest exceeds 4 MiB")
    manifest = read_json(path)
    _require(isinstance(manifest, dict), "Atlas manifest must be an object")
    _require(manifest.get("schema_version") == 1 and manifest.get("kind") == "sprite_atlas",
             "Expected Studio sprite_atlas manifest schema 1")
    _require(isinstance(manifest.get("clip"), str) and manifest["clip"], "Atlas clip is required")
    _require(type(manifest.get("loop")) is bool, "Atlas loop must be boolean")
    canvas = manifest.get("logical_canvas")
    anchor = manifest.get("anchor")
    _require(isinstance(canvas, list) and len(canvas) == 2 and all(type(x) is int and 1 <= x <= 8192 for x in canvas),
             "logical_canvas must be [width,height] integers")
    _require(isinstance(anchor, list) and len(anchor) == 2 and all(type(x) is int for x in anchor),
             "anchor must be [x,y] integers")
    _require(0 <= anchor[0] <= canvas[0] and 0 <= anchor[1] <= canvas[1], "anchor lies outside logical_canvas")
    _require(manifest.get("filter", "nearest") in FILTERS, "filter must be nearest or linear")
    _require(isinstance(manifest.get("atlas"), str) and manifest["atlas"], "Atlas PNG path is required")
    _require(isinstance(manifest.get("atlas_sha256"), str) and len(manifest["atlas_sha256"]) == 64,
             "Atlas SHA-256 is required")
    frames = manifest.get("frames")
    _require(isinstance(frames, list) and 1 <= len(frames) <= 512, "Expected 1..512 atlas frames")
    identifiers: set[str] = set()
    for index, frame in enumerate(frames):
        _require(isinstance(frame, dict), f"Frame {index} must be an object")
        frame_id = frame.get("id")
        _require(isinstance(frame_id, str) and frame_id and frame_id not in identifiers,
                 f"Frame {index} has a missing or duplicate ID")
        identifiers.add(frame_id)
        region = frame.get("region")
        _require(isinstance(region, list) and len(region) == 4 and all(type(x) is int and x >= 0 for x in region),
                 f"Frame {frame_id} region must be [x,y,width,height]")
        _require(region[2] == canvas[0] and region[3] == canvas[1],
                 f"Frame {frame_id} differs from common logical canvas")
        _require(type(frame.get("duration_ms")) is int and 1 <= frame["duration_ms"] <= 60000,
                 f"Frame {frame_id} has invalid duration_ms")
    return manifest


def describe() -> dict[str, Any]:
    return {
        "adapter": "godot-asset-adapter", "schema_version": 1,
        "operations": ["preflight", "execute", "inspect", "export", "cancel_owned"],
        "input_contract": "Studio sprite_atlas manifest and optional GLB under an explicit input root",
        "output_contract": "new Godot project plus actual headless engine report",
        "unsupported": ["rig retargeting", "root motion acceptance", "collision acceptance", "art acceptance"],
    }


def preflight(godot_path: str | Path, timeout: float = 30) -> dict[str, Any]:
    executable = Path(godot_path).expanduser().resolve()
    _require(executable.is_file(), f"Godot executable is missing: {executable}")
    result = subprocess.run([str(executable), "--headless", "--version"], capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False)
    version = result.stdout.strip()
    _require(result.returncode == 0 and version.startswith("4."), "Godot 4 headless preflight failed")
    return {"operation_id": "godot-preflight", "state": "ready", "runtime": {
        "path": str(executable), "sha256": file_sha(executable), "version": version,
    }, "resolved_inputs": [], "output_paths": [], "warnings": [],
            "measurement_method": "Godot --headless --version"}


def _quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _project_tscn(manifest: dict[str, Any]) -> str:
    canvas = manifest["logical_canvas"]
    anchor = manifest["anchor"]
    atlas_textures: list[str] = []
    frames: list[str] = []
    for index, frame in enumerate(manifest["frames"]):
        sub_id = f"AtlasTexture_{index}"
        x, y, width, height = frame["region"]
        atlas_textures.extend([
            f'[sub_resource type="AtlasTexture" id="{sub_id}"]',
            'atlas = ExtResource("1_atlas")',
            f"region = Rect2({x}, {y}, {width}, {height})",
            "filter_clip = true",
            "",
        ])
        relative_duration = (frame["duration_ms"] / 1000.0) * 60.0
        frames.append("{\n\"duration\": %.12g,\n\"texture\": SubResource(\"%s\")\n}" %
                      (relative_duration, sub_id))
    loop_value = "true" if manifest["loop"] else "false"
    offset_x = canvas[0] / 2.0 - anchor[0]
    offset_y = canvas[1] / 2.0 - anchor[1]
    return "\n".join([
        f"[gd_scene load_steps={len(manifest['frames']) + 3} format=3]", "",
        '[ext_resource type="Texture2D" path="res://assets/atlas.png" id="1_atlas"]',
        '[ext_resource type="Script" path="res://verify.gd" id="2_verify"]', "",
        *atlas_textures,
        '[sub_resource type="SpriteFrames" id="SpriteFrames_adapter"]',
        "animations = [{",
        '"frames": [' + ",\n".join(frames) + "],",
        f'"loop": {loop_value},',
        f'"name": &"{manifest["clip"]}",',
        '"speed": 60.0',
        "}]", "",
        '[node name="Verification" type="Node"]',
        'script = ExtResource("2_verify")',
        f'metadata/asset_anchor = Vector2({anchor[0]}, {anchor[1]})',
        f'metadata/logical_canvas = Vector2({canvas[0]}, {canvas[1]})',
        f'metadata/atlas_filter = &"{manifest.get("filter", "nearest")}"',
        "",
        '[node name="SpritePlayback" type="AnimatedSprite2D" parent="."]',
        'sprite_frames = SubResource("SpriteFrames_adapter")',
        f'animation = &"{manifest["clip"]}"',
        f'autoplay = &"{manifest["clip"]}"',
        "centered = true",
        f"offset = Vector2({offset_x:.12g}, {offset_y:.12g})",
        f"texture_filter = {FILTERS[manifest.get('filter', 'nearest')]}",
        "",
    ])


VERIFY_GD = r'''extends Node

const GLB_PATH := "__GLB_PATH__"

func alpha_region(image: Image, region: Rect2i) -> Dictionary:
	var min_x := region.size.x
	var min_y := region.size.y
	var max_x := -1
	var max_y := -1
	var alpha_pixels := 0
	for y in range(region.size.y):
		for x in range(region.size.x):
			if image.get_pixel(region.position.x + x, region.position.y + y).a > 0.0:
				alpha_pixels += 1
				min_x = min(min_x, x)
				min_y = min(min_y, y)
				max_x = max(max_x, x)
				max_y = max(max_y, y)
	if max_x < 0:
		return {"alpha_pixels": 0, "bounds": []}
	return {"alpha_pixels": alpha_pixels, "bounds": [min_x, min_y, max_x + 1, max_y + 1]}

func inventory_glb() -> Dictionary:
	var inventory := {"requested": GLB_PATH, "loaded": false, "node_count": 0, "meshes": [], "materials": [], "animations": []}
	if GLB_PATH.is_empty():
		inventory["not_requested"] = true
		return inventory
	var packed := load(GLB_PATH)
	if not (packed is PackedScene):
		inventory["load_error"] = "Godot did not load GLB as PackedScene"
		return inventory
	var root := (packed as PackedScene).instantiate()
	inventory["loaded"] = true
	var stack := [root]
	var material_seen := {}
	while not stack.is_empty():
		var item = stack.pop_back() as Node
		inventory["node_count"] += 1
		if item is MeshInstance3D:
			var mesh_item := item as MeshInstance3D
			var surfaces := 0
			if mesh_item.mesh:
				surfaces = mesh_item.mesh.get_surface_count()
				for index in range(surfaces):
					var material := mesh_item.get_active_material(index)
					if material:
						var label := "%s:%s" % [material.get_class(), material.resource_name]
						material_seen[label] = true
			inventory["meshes"].append({"name": item.name, "surfaces": surfaces})
		if item is AnimationPlayer:
			for animation_name in (item as AnimationPlayer).get_animation_list():
				inventory["animations"].append(str(animation_name))
		for child in item.get_children():
			if child is Node:
				stack.append(child)
	for label in material_seen.keys():
		inventory["materials"].append(label)
	root.queue_free()
	return inventory

func _ready() -> void:
	var sprite := $SpritePlayback as AnimatedSprite2D
	var frames := sprite.sprite_frames
	var animation := sprite.animation
	var speed := frames.get_animation_speed(animation)
	var texture := load("res://assets/atlas.png") as Texture2D
	var image := texture.get_image()
	var report := {"report_kind": "godot_headless_import_playback", "engine": Engine.get_version_info(), "sprite": {
		"animation": str(animation), "frame_count": frames.get_frame_count(animation), "loop": frames.get_animation_loop(animation),
		"speed_fps": speed, "anchor": [get_meta("asset_anchor").x, get_meta("asset_anchor").y],
		"logical_canvas": [get_meta("logical_canvas").x, get_meta("logical_canvas").y],
		"filter": get_meta("atlas_filter"), "texture_filter": sprite.texture_filter,
		"anchor_world_error": [sprite.offset.x + get_meta("asset_anchor").x - get_meta("logical_canvas").x / 2.0, sprite.offset.y + get_meta("asset_anchor").y - get_meta("logical_canvas").y / 2.0],
		"frames": [], "total_duration_ms": 0.0}, "glb": inventory_glb()}
	for index in range(frames.get_frame_count(animation)):
		var atlas_texture := frames.get_frame_texture(animation, index) as AtlasTexture
		var region := Rect2i(atlas_texture.region.position, atlas_texture.region.size)
		var relative_duration := frames.get_frame_duration(animation, index)
		var duration_ms := relative_duration / speed * 1000.0
		report["sprite"]["total_duration_ms"] += duration_ms
		report["sprite"]["frames"].append({"index": index, "region": [region.position.x, region.position.y, region.size.x, region.size.y], "relative_duration": relative_duration, "duration_ms": duration_ms, "alpha": alpha_region(image, region)})
	var serialized := JSON.stringify(report)
	var output := FileAccess.open("user://engine-report.json", FileAccess.WRITE)
	output.store_string(serialized + "\n")
	output.close()
	print("GODOT_ADAPTER_REPORT=" + serialized)
	get_tree().quit(0)
'''


def package_project(input_root: str | Path, atlas_manifest: str, output_root: str | Path,
                    glb_path: str | None = None) -> dict[str, Any]:
    """Create an exclusive portable Godot project without starting the engine."""
    source_root = _absolute_directory(input_root, "input_root")
    target_root = _absolute_directory(output_root, "output_root", exists=False)
    _require(not target_root.exists(), f"output_root already exists: {target_root}")
    manifest_path = _input_file(source_root, atlas_manifest, "atlas_manifest")
    manifest = _read_atlas_manifest(manifest_path)
    atlas_path = _input_file(manifest_path.parent.resolve(), manifest["atlas"], "atlas PNG")
    _require(file_sha(atlas_path) == manifest["atlas_sha256"], "Atlas PNG SHA-256 mismatch")
    glb_source = _input_file(source_root, glb_path, "glb_path") if glb_path else None
    if glb_source:
        _require(glb_source.suffix.lower() == ".glb", "glb_path must name a .glb file")
    target_root.parent.mkdir(parents=True, exist_ok=True)
    target_root.mkdir()
    assets = target_root / "assets"
    assets.mkdir()
    shutil.copy2(atlas_path, assets / "atlas.png")
    if glb_source:
        shutil.copy2(glb_source, assets / "ember.glb")
    (target_root / "project.godot").write_text("; Generated by godot_asset_adapter.py\n[application]\nconfig/name=\"Studio Godot Asset Verification\"\nrun/main_scene=\"res://main.tscn\"\n[rendering]\nrenderer/rendering_method=\"gl_compatibility\"\n", encoding="utf-8", newline="\n")
    (target_root / "main.tscn").write_text(_project_tscn(manifest), encoding="utf-8", newline="\n")
    verifier = VERIFY_GD.replace("__GLB_PATH__", "res://assets/ember.glb" if glb_source else "")
    (target_root / "verify.gd").write_text(verifier, encoding="utf-8", newline="\n")
    return {"operation_id": "godot-package", "state": "packaged", "project_root": str(target_root),
            "manifest_sha256": file_sha(manifest_path), "atlas_sha256": file_sha(atlas_path),
            "glb_sha256": file_sha(glb_source) if glb_source else None,
            "frame_count": len(manifest["frames"]), "anchor": manifest["anchor"],
            "filter": manifest.get("filter", "nearest"), "clip": manifest["clip"]}


def _engine_report_from_stdout(stdout: str) -> dict[str, Any]:
    for line in stdout.splitlines():
        if line.startswith("GODOT_ADAPTER_REPORT="):
            value = json.loads(line.removeprefix("GODOT_ADAPTER_REPORT="))
            _require(isinstance(value, dict), "Godot report was not an object")
            return value
    raise GodotAdapterError("Godot finished without its engine report")


def _verify_report(report: dict[str, Any], manifest: dict[str, Any], wants_glb: bool) -> None:
    sprite = report.get("sprite")
    _require(isinstance(sprite, dict), "Engine report has no sprite section")
    _require(sprite.get("frame_count") == len(manifest["frames"]), "Godot frame count differs from manifest")
    _require(sprite.get("anchor") == manifest["anchor"], "Godot anchor differs from manifest")
    _require(sprite.get("loop") == manifest["loop"], "Godot loop differs from manifest")
    _require(sprite.get("filter") == manifest.get("filter", "nearest"), "Godot filter differs from manifest")
    _require(all(abs(_finite_number(value, "anchor_world_error")) < 0.0001 for value in sprite.get("anchor_world_error", [])),
             "Godot anchor is not placed at node origin")
    frames = sprite.get("frames")
    _require(isinstance(frames, list) and len(frames) == len(manifest["frames"]), "Godot did not report every frame")
    for actual, expected in zip(frames, manifest["frames"]):
        expected_relative = expected["duration_ms"] / 1000.0 * 60.0
        _require(abs(_finite_number(actual.get("relative_duration"), "relative_duration") - expected_relative) < 0.00001,
                 "Godot relative duration differs from duration_ms / 1000 * fps")
        _require(abs(_finite_number(actual.get("duration_ms"), "duration_ms") - expected["duration_ms"]) < 0.001,
                 "Godot playback duration differs from manifest")
        _require(isinstance(actual.get("alpha"), dict) and actual["alpha"].get("alpha_pixels", 0) > 0,
                 "Godot alpha inspection found an empty frame")
    expected_total = sum(frame["duration_ms"] for frame in manifest["frames"])
    _require(abs(_finite_number(sprite.get("total_duration_ms"), "total_duration_ms") - expected_total) < 0.001,
             "Godot cycle duration differs from manifest")
    if wants_glb:
        glb = report.get("glb")
        _require(isinstance(glb, dict) and glb.get("loaded") is True, "Godot did not import the requested GLB")


def execute(input_root: str | Path, atlas_manifest: str, output_root: str | Path, godot_path: str | Path,
            glb_path: str | None = None, timeout: float = 120) -> dict[str, Any]:
    """Package inputs, import them in Godot, and retain the engine-authored report."""
    runtime = preflight(godot_path)
    package = package_project(input_root, atlas_manifest, output_root, glb_path)
    project_root = Path(package["project_root"])
    manifest_path = _input_file(_absolute_directory(input_root, "input_root"), atlas_manifest, "atlas_manifest")
    manifest = _read_atlas_manifest(manifest_path)
    user_data = project_root / "user-data"
    commands = [
        [runtime["runtime"]["path"], "--headless", "--path", str(project_root), "--editor", "--quit"],
        [runtime["runtime"]["path"], "--headless", "--path", str(project_root), "--user-data-dir", str(user_data)],
    ]
    logs: list[dict[str, Any]] = []
    for command in commands:
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                   timeout=timeout, check=False)
        logs.append({"argv": command[1:], "returncode": completed.returncode, "stdout": completed.stdout,
                     "stderr": completed.stderr})
        _require(completed.returncode == 0, "Godot headless command failed")
    report = _engine_report_from_stdout(logs[-1]["stdout"])
    _verify_report(report, manifest, glb_path is not None)
    (project_root / "engine-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    (project_root / "engine-log.json").write_text(json.dumps(logs, indent=2) + "\n", encoding="utf-8", newline="\n")
    return {"operation_id": "godot-execute", "state": "verified", "runtime": runtime["runtime"],
            "resolved_inputs": {"atlas_manifest": str(manifest_path), "glb": glb_path},
            "output_paths": {"project": str(project_root), "report": str(project_root / "engine-report.json"),
                             "log": str(project_root / "engine-log.json")}, "report": report,
            "warnings": ["Engine import proves this package only; art, rig, collision, root motion and licence acceptance remain outside this adapter."],
            "measurement_method": "Godot headless editor import followed by Godot headless AnimatedSprite2D playback inspection"}


def inspect(project_root: str | Path) -> dict[str, Any]:
    root = _absolute_directory(project_root, "project_root")
    return read_json(root / "engine-report.json")


def export(project_root: str | Path) -> dict[str, Any]:
    root = _absolute_directory(project_root, "project_root")
    _require((root / "engine-report.json").is_file(), "Project has no verified engine report")
    return {"operation_id": "godot-export", "state": "portable_project", "project_root": str(root),
            "files": [str(root / name) for name in ("project.godot", "main.tscn", "engine-report.json")]}


def cancel_owned(_operation_id: str) -> dict[str, Any]:
    return {"operation_id": _operation_id, "state": "not_running", "warning": "The adapter starts only blocking child processes and owns no background work."}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("describe")
    preflight_parser = sub.add_parser("preflight")
    preflight_parser.add_argument("--godot", required=True)
    package_parser = sub.add_parser("package")
    run_parser = sub.add_parser("run")
    for child in (package_parser, run_parser):
        child.add_argument("--input-root", required=True)
        child.add_argument("--atlas-manifest", required=True, help="Path relative to input-root")
        child.add_argument("--output-root", required=True, help="New absolute project path")
        child.add_argument("--glb", help="Optional .glb path relative to input-root")
    run_parser.add_argument("--godot", required=True)
    inspect_parser = sub.add_parser("inspect")
    inspect_parser.add_argument("--project-root", required=True)
    export_parser = sub.add_parser("export")
    export_parser.add_argument("--project-root", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "describe": result = describe()
        elif args.command == "preflight": result = preflight(args.godot)
        elif args.command == "package": result = package_project(args.input_root, args.atlas_manifest, args.output_root, args.glb)
        elif args.command == "run": result = execute(args.input_root, args.atlas_manifest, args.output_root, args.godot, args.glb)
        elif args.command == "inspect": result = inspect(args.project_root)
        else: result = export(args.project_root)
        print(json.dumps(result, indent=2))
        return 0
    except (GodotAdapterError, OSError, ValueError, TypeError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
