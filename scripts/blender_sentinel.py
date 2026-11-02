"""Asset Parity Sentinel v1: does a .blend survive the LAS GLB export and a reimport in a NEW Blender process?

source.blend -> manifest + fixed-camera evidence -> GLB (existing LAS settings) -> new process: import -> same
evidence with the same cameras -> structural diff + per-camera visual diff with changed-region boxes -> result.json.
The source file is opened without scripts, never saved, and its SHA-256 must be unchanged afterwards.

    python scripts/blender_sentinel.py --blender <blender.exe> --blend <asset.blend> --out-dir <new-dir> [--seed-defect K]

`--seed-defect` (missing-texture, omitted-mesh, material-mismatch) breaks the in-memory scene after the source evidence
and before export, to prove the sentinel catches that class of failure. It never touches the source file.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import blender_lab as lab
from blender_lab import require


# Measured on the unchanged control (docs/BLENDER-LAB.md): ID passes are exact up to +-1 dither; lit Cycles noise
# stays below these. A pixel "changed" when its largest channel difference exceeds `pixel`; a view warns when the
# changed fraction exceeds `fraction`.
THRESHOLDS = {"lit": {"pixel": 40, "fraction": 0.004}, "clay": {"pixel": 12, "fraction": 0.002},
              "object_id": {"pixel": 12, "fraction": 0.001}, "material_id": {"pixel": 12, "fraction": 0.001}}
TILE = 8
PRINCIPLED_TOLERANCE = 2e-3


def _visible_meshes(manifest):
    return {o["name"]: o for o in manifest["objects"] if o["type"] == "MESH" and o["visible"] and not o["hide_render"]}


def compare_manifests(source, roundtrip):
    """Separate expected exclusions and known format losses from unexpected structural changes."""
    failures, losses, exclusions = [], [], []
    src_meshes, rt_meshes = _visible_meshes(source), _visible_meshes(roundtrip)
    mesh_data = lambda manifest: {m["name"]: m for m in manifest["meshes"]}
    src_data, rt_data = mesh_data(source), mesh_data(roundtrip)
    materials = lambda manifest: {m["name"]: m for m in manifest["materials"]}
    src_mats, rt_mats = materials(source), materials(roundtrip)
    rt_images = {i["name"]: i for i in roundtrip["images"]}
    for obj in source["objects"]:
        if obj["name"] not in src_meshes and obj["type"] != "ARMATURE":
            exclusions.append(f"{obj['name']} ({obj['type']}{', hidden' if obj['hide_render'] or not obj['visible'] else ''}) is not exported by the LAS settings")
    for image in source["images"]:
        if image["missing"]: failures.append(f"source image {image['name']} is missing ({image['file']})")
    used = set()
    for name, obj in sorted(src_meshes.items()):
        if name not in rt_meshes:
            failures.append(f"visible mesh {name} is missing after the roundtrip"); continue
        other = rt_meshes[name]
        before, after = src_data.get(obj["data"], {}), rt_data.get(other["data"], {})
        if before.get("triangles") != after.get("triangles"):
            failures.append(f"{name}: triangles {before.get('triangles')} -> {after.get('triangles')}")
        slots, rt_slots = [s["material"] for s in obj["material_slots"]], [s["material"] for s in other["material_slots"]]
        if slots != rt_slots: failures.append(f"{name}: materials {slots} -> {rt_slots}")
        used.update(m for m in slots if m)
        keys = lambda mesh: [k["name"] for k in (mesh.get("shape_keys") or {"keys": []})["keys"]]
        if keys(before) != keys(after): failures.append(f"{name}: shape keys {keys(before)} -> {keys(after)}")
        for modifier in obj["modifiers"]:
            if modifier["type"] != "ARMATURE":
                losses.append(f"{name}: {modifier['type']} modifier {modifier['name']!r} is not applied by the LAS export settings")
        for constraint in obj["constraints"]:
            losses.append(f"{name}: constraint {constraint['name']!r} ({constraint['type']}) has no glTF equivalent")
    for name in sorted(set(rt_meshes) - set(src_meshes)):
        failures.append(f"unexpected visible mesh {name} after the roundtrip")
    for name in sorted(used):
        before, after = src_mats.get(name), rt_mats.get(name)
        if before is None or after is None: continue  # slot comparison already reported the mismatch
        if before["images"] and (len(after["images"]) < len(before["images"])
                                 or any(rt_images.get(i, {}).get("missing", True) for i in after["images"])):
            failures.append(f"material {name}: textures {before['images']} -> {after['images']}")
        for key, value in (before["principled"] or {}).items():
            new = (after["principled"] or {}).get(key)
            if isinstance(value, str) or isinstance(new, str):
                if (value if isinstance(value, str) else "value") != (new if isinstance(new, str) else "value"):
                    failures.append(f"material {name}: {key} {value} -> {new}")
            elif new is None or max(abs(a - b) for a, b in zip(value if isinstance(value, list) else [value],
                                                                new if isinstance(new, list) else [new])) > PRINCIPLED_TOLERANCE:
                failures.append(f"material {name}: {key} {value} -> {new}")
    bones = lambda manifest: {a["name"]: {b["name"]: b["parent"] for b in a["bones"]} for a in manifest["armatures"]}
    src_bones, rt_bones = bones(source), bones(roundtrip)
    for name, graph in sorted(src_bones.items()):
        if rt_bones.get(name) != graph: failures.append(f"armature {name}: bone graph changed")
    rt_actions = {a["name"] for a in roundtrip["actions"]}
    for action in source["actions"]:
        if action["name"] not in rt_actions: failures.append(f"action {action['name']} is missing after the roundtrip")
        else: losses.append(f"action {action['name']}: keys are resampled per frame (export_force_sampling)")
    return {"failures": failures, "format_losses": losses, "expected_exclusions": exclusions}


def _srgb(channel):
    return round(255 * (12.92 * channel if channel <= 0.0031308 else 1.055 * channel ** (1 / 2.4) - 0.055))


def _names_in(image, palette):
    """Names whose ID colour occurs in an RGBA crop (Workbench shows linear colours through the sRGB transform)."""
    targets = {name: [_srgb(c) for c in colour] for name, colour in palette.items()}
    found = set()
    for count, pixel in image.getcolors(image.width * image.height) or []:
        if pixel[3] < 128 or count < 2: continue
        best = min(targets.items(), key=lambda item: sum(abs(a - b) for a, b in zip(item[1], pixel[:3])), default=None)
        if best and sum(abs(a - b) for a, b in zip(best[1], pixel[:3])) <= 9: found.add(best[0])
    return sorted(found)


def regions(mask, tile=TILE, min_pixels=3):
    """Changed-region boxes: tiles with >= min_pixels changed pixels, merged by 8-connectivity."""
    grid = mask.reduce(tile)  # mean of the 0/255 mask per tile
    cols, rows = grid.size
    data = grid.tobytes()
    hot = {(x, y) for y in range(rows) for x in range(cols) if data[y * cols + x] * tile * tile / 255 >= min_pixels}
    boxes = []
    while hot:
        stack = [hot.pop()]; xs, ys = [], []
        while stack:
            x, y = stack.pop(); xs.append(x); ys.append(y)
            for nx in (x - 1, x, x + 1):
                for ny in (y - 1, y, y + 1):
                    if (nx, ny) in hot: hot.remove((nx, ny)); stack.append((nx, ny))
        boxes.append([min(xs) * tile, min(ys) * tile, min((max(xs) + 1) * tile, mask.width), min((max(ys) + 1) * tile, mask.height)])
    return sorted(boxes)


def compare_image(source_path, roundtrip_path, diff_path, pass_name, palette=None):
    from PIL import Image, ImageChops
    with Image.open(source_path) as a_raw, Image.open(roundtrip_path) as b_raw:
        a, b = a_raw.convert("RGBA"), b_raw.convert("RGBA")
    require(a.size == b.size, f"Render sizes differ: {source_path}")
    channels = ImageChops.difference(a, b).split()
    peak = channels[0]
    for channel in channels[1:]: peak = ImageChops.lighter(peak, channel)
    limits = THRESHOLDS[pass_name]
    mask = peak.point(lambda v: 255 if v > limits["pixel"] else 0)
    total = a.width * a.height
    histogram = peak.histogram()
    changed = mask.histogram()[255]
    peak.point(lambda v: min(255, v * 4)).save(diff_path)
    boxes = regions(mask)
    record = {"changed_fraction": round(changed / total, 6), "mean_abs_diff": round(sum(i * c for i, c in enumerate(histogram)) / total, 4),
              "max_abs_diff": max(i for i, c in enumerate(histogram) if c), "boxes": boxes,
              "warn": changed / total > limits["fraction"], "thresholds": limits}
    if palette and boxes:
        record["attribution"] = [{"box": box, "source": _names_in(a.crop(box), palette), "roundtrip": _names_in(b.crop(box), palette)}
                                 for box in boxes]
    if pass_name == "object_id":
        sa, sb = a.getchannel("A").point(lambda v: 255 if v >= 128 else 0), b.getchannel("A").point(lambda v: 255 if v >= 128 else 0)
        union = ImageChops.lighter(sa, sb).histogram()[255]
        record["silhouette_iou"] = round(ImageChops.darker(sa, sb).histogram()[255] / union, 6) if union else 1.0
    return record


def compare_renders(source_dir, roundtrip_dir, evidence, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    palettes = {"object_id": evidence["palette"]["object"], "material_id": evidence["palette"]["material"]}
    views, warnings = {}, []
    for name in evidence["files"]:
        view, pass_name, _ = name.split(".")
        record = compare_image(source_dir / name, roundtrip_dir / name, out_dir / f"{view}.{pass_name}.diff.png",
                               pass_name, palettes.get(pass_name))
        views.setdefault(view, {})[pass_name] = record
        if record["warn"]:
            blame = "; ".join(f"{a['source']} -> {a['roundtrip']} at {a['box']}" for a in record.get("attribution", []))
            warnings.append(f"{view}/{pass_name}: {record['changed_fraction']:.2%} of pixels changed"
                            f" in {len(record['boxes'])} region(s){': ' + blame if blame else ''}")
    return views, warnings


def sentinel(blender_path, blend_path, out_dir, seed_defect=None, timeout=600):
    exe = lab.executable(blender_path)
    blend = Path(blend_path).expanduser().resolve()
    require(blend.is_file() and blend.suffix.lower() == ".blend", "blend must be an existing .blend file")
    target = Path(out_dir).expanduser().resolve()
    require(not target.exists(), "out_dir must be new")
    require(seed_defect in (None, *lab.bpy_side.SEEDED_DEFECTS), "Unknown seeded defect")
    target.mkdir(parents=True)
    before = lab.file_sha(blend)
    glb = target / "export.glb"
    args = ["evidence", "--blend", blend, "--out-dir", target / "source", "--out", target / "source.json", "--export", glb]
    if seed_defect: args += ["--seed-defect", seed_defect]
    seconds_source = lab.run(exe, args, target / "source.log.json", timeout)
    require(lab.file_sha(blend) == before, "Source .blend changed during the sentinel run")
    require(glb.is_file() and glb.stat().st_size > 0, "GLB export is missing")
    source_record = json.loads((target / "source.json").read_text(encoding="utf-8"))
    evidence = json.loads((target / "source" / "evidence.json").read_text(encoding="utf-8"))
    cameras = target / "cameras.json"
    cameras.write_text(json.dumps(evidence["camera_spec"], indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    seconds_roundtrip = lab.run(exe, ["evidence", "--glb", glb, "--out-dir", target / "roundtrip", "--out", target / "roundtrip.json",
                                      "--cameras", cameras], target / "roundtrip.log.json", timeout)
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    src_manifest, rt_manifest = load(target / "source" / "manifest.json"), load(target / "roundtrip" / "manifest.json")
    rt_evidence = load(target / "roundtrip" / "evidence.json")
    require(sorted(rt_evidence["files"]) == sorted(evidence["files"]), "Roundtrip did not render the same evidence set")
    for name in evidence["files"]:
        require((target / "source" / "renders" / name).is_file() and (target / "roundtrip" / "renders" / name).is_file(),
                f"Missing render {name}")
    structure = compare_manifests(src_manifest, rt_manifest)
    views, warnings = compare_renders(target / "source" / "renders", target / "roundtrip" / "renders", evidence, target / "diff")
    result = {
        "schema": "las.asset-parity-sentinel.v1", "pass": not structure["failures"] and not warnings,
        "blender": {"executable": exe.as_posix(), "sha256": lab.file_sha(exe), "version_string": src_manifest["blender"]["version_string"],
                    "build_hash": src_manifest["blender"]["build_hash"]},
        "source": {"file": blend.name, "sha256": before, "unchanged": True, "semantic_checksum": src_manifest["semantic_checksum"],
                   "counts": src_manifest["counts"], "seconds": seconds_source},
        "seeded_defect": source_record.get("seeded_defect"),
        "export": {"settings": source_record["export"]["settings"], "glb_sha256": lab.file_sha(glb), "glb_bytes": glb.stat().st_size},
        "roundtrip": {"semantic_checksum": rt_manifest["semantic_checksum"], "counts": rt_manifest["counts"],
                      "seconds": seconds_roundtrip, "process": "new Blender process, factory-empty scene, glTF import"},
        "cameras": evidence["camera_spec"], "render": {k: evidence[k] for k in ("size", "lit", "id_passes", "view_transform")},
        "structural_failures": structure["failures"], "format_losses": structure["format_losses"],
        "expected_exclusions": structure["expected_exclusions"], "visual_warnings": warnings, "views": views,
        "artifacts": [{"path": p.relative_to(target).as_posix(), "sha256": lab.file_sha(p), "bytes": p.stat().st_size}
                      for p in sorted(target.rglob("*")) if p.is_file()],
    }
    (target / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", required=True)
    parser.add_argument("--blend", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--seed-defect", choices=lab.bpy_side.SEEDED_DEFECTS)
    args = parser.parse_args(argv)
    try:
        result = sentinel(args.blender, args.blend, args.out_dir, args.seed_defect)
    except (lab.BlenderLabError, OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps({"pass": result["pass"], "structural_failures": result["structural_failures"],
                      "visual_warnings": result["visual_warnings"]}, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
