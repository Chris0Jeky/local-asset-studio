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
from contextlib import nullcontext
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


SHAPE_TOLERANCE = 1e-3
POSE_TOLERANCE = 1e-3


def _flat(value, *keys):
    """Numbers of a nested JSON value (optionally only some keys), in a stable order."""
    if keys: value = [value.get(k) for k in keys]
    if isinstance(value, dict): return [n for k in sorted(value) for n in _flat(value[k])]
    if isinstance(value, list): return [n for item in value for n in _flat(item)]
    return [] if value is None else [value]


def _drift(a, b):
    a, b = _flat(a), _flat(b)
    return float("inf") if len(a) != len(b) else max((abs(x - y) for x, y in zip(a, b)), default=0.0)


FLOAT32_ULP = 1.2e-7  # relative spacing of float32 values


def _moments_differ(a, b):
    """Point-set sums from the manifest. Random float32 noise grows with sqrt(count). Rounding at a baked-in offset
    (skinned glTF meshes move the object offset into the vertices) is systematic, up to two ulps of the largest
    coordinate per point. A real change moves the sums by its own size."""
    if a is None or b is None: return a is not b
    if a["count"] != b["count"]: return True
    if not a["count"]: return False
    n, scale = a["count"], max(a.get("scale", 0.0), b.get("scale", 0.0))
    return any(abs(x - y) > 1e-6 * n ** 0.5 * (1 + abs(x) / n) + 2 * n * FLOAT32_ULP * scale * (1 + scale)
               for x, y in zip(_flat(a, "sum", "products"), _flat(b, "sum", "products")))


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
            reason = ("is not exported by the LAS settings" if obj["type"] in ("LIGHT", "CAMERA") or obj["type"] == "MESH"
                      else "is not compared (only visible meshes and armatures are)")
            exclusions.append(f"{obj['name']} ({obj['type']}{', hidden' if obj['hide_render'] or not obj['visible'] else ''}) {reason}")
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
        if before.get("closed") and after.get("closed") is False:
            failures.append(f"{name}: closed surface became open")
        volume, new_volume = before.get("signed_volume"), after.get("signed_volume")
        # Signed volume means something only for closed surfaces: an open one's value moves with translation.
        if before.get("closed") and after.get("closed") and volume is not None and new_volume is not None:
            if volume * new_volume < 0:
                failures.append(f"{name}: signed volume {volume} -> {new_volume} (normals flipped)")
            elif abs(volume - new_volume) > 1e-3 * max(abs(volume), abs(new_volume)) + 1e-9:
                failures.append(f"{name}: signed volume {volume} -> {new_volume}")
        slots, rt_slots = [s["material"] for s in obj["material_slots"]], [s["material"] for s in other["material_slots"]]
        if slots != rt_slots: failures.append(f"{name}: materials {slots} -> {rt_slots}")
        used.update(m for m in slots if m)
        keys = lambda mesh: {k["name"]: k for k in (mesh.get("shape_keys") or {"keys": []})["keys"]}
        if list(keys(before)) != list(keys(after)): failures.append(f"{name}: shape keys {list(keys(before))} -> {list(keys(after))}")
        for key_name, key in keys(before).items():
            other_key = keys(after).get(key_name)
            if other_key and (_drift(_flat(key, "delta_max", "delta_bbox"), _flat(other_key, "delta_max", "delta_bbox")) > SHAPE_TOLERANCE
                              or _moments_differ(key.get("moments"), other_key.get("moments"))):
                failures.append(f"{name}: shape key {key_name} deformation changed (max delta {key.get('delta_max')} -> {other_key.get('delta_max')})")
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
    rt_deform = roundtrip.get("deform_samples", {})
    for name, sample in sorted(source.get("deform_samples", {}).items()):
        other = rt_deform.get(name)
        if other is None: continue  # a missing visible mesh is already a failure
        if other["frames"] != sample["frames"]:
            failures.append(f"{name}: deform frames {sample['frames']} -> {other['frames']}"); continue
        for frame, a, b in zip(sample["frames"], sample["moments"], other["moments"]):
            if _moments_differ(a, b):
                failures.append(f"{name}: deformed shape differs at frame {frame}"); break
    rt_objects, exported = roundtrip.get("object_samples", {}), set(src_meshes) | {a["name"] for a in source["objects"] if a["type"] == "ARMATURE"}
    for name, sample in sorted(source.get("object_samples", {}).items()):
        if name not in exported: continue  # excluded helpers carry no export obligation
        other = rt_objects.get(name)
        if other is None or other["frames"] != sample["frames"]:
            failures.append(f"{name}: object animation frames {sample['frames']} -> {other and other['frames']}"); continue
        for frame, a, b in zip(sample["frames"], sample["matrices"], other["matrices"]):
            if _drift(a, b) > POSE_TOLERANCE:
                failures.append(f"{name}: object transform differs at frame {frame}"); break
    rt_poses = roundtrip.get("pose_samples", {})
    for name, sample in sorted(source.get("pose_samples", {}).items()):
        other = rt_poses.get(name)
        if other is None or other["frames"] != sample["frames"]:
            failures.append(f"armature {name}: sampled frames {sample['frames']} -> {other and other['frames']}"); continue
        for bone, track in sorted(sample["bones"].items()):
            if bone not in other["bones"]: continue  # bone graph comparison already reported it
            for frame, a, b in zip(sample["frames"], track, other["bones"][bone]):
                if _drift(a, b) > POSE_TOLERANCE:
                    failures.append(f"armature {name}: bone {bone} moved at frame {frame}"); break
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


def _evidence_files(evidence, label):
    """Accept only the complete fixed capture contract, before joining any receipt-provided paths."""
    expected = {f"{view}.{pass_name}.png" for view in lab.bpy_side.VIEWS for pass_name in lab.bpy_side.PASSES}
    files = evidence.get("files") if isinstance(evidence, dict) else None
    require(isinstance(files, list) and len(files) == len(expected)
            and all(isinstance(name, str) for name in files) and set(files) == expected,
            f"{label} must contain the complete unique evidence set (four views x four passes)")
    return sorted(expected)


def compare_renders(source_dir, roundtrip_dir, evidence, out_dir):
    files = _evidence_files(evidence, "Source")
    out_dir.mkdir(parents=True, exist_ok=True)
    palettes = {"object_id": evidence["palette"]["object"], "material_id": evidence["palette"]["material"]}
    views, warnings = {}, []
    for name in files:
        view, pass_name, _ = name.split(".")
        record = compare_image(source_dir / name, roundtrip_dir / name, out_dir / f"{view}.{pass_name}.diff.png",
                               pass_name, palettes.get(pass_name))
        views.setdefault(view, {})[pass_name] = record
        if record["warn"]:
            blame = "; ".join(f"{a['source']} -> {a['roundtrip']} at {a['box']}" for a in record.get("attribution", []))
            warnings.append(f"{view}/{pass_name}: {record['changed_fraction']:.2%} of pixels changed"
                            f" in {len(record['boxes'])} region(s){': ' + blame if blame else ''}")
    return views, warnings


def _shares(image, mask, palette, minimum=0.05):
    """Names whose ID colour covers at least `minimum` of the masked pixels."""
    from PIL import Image
    masked = Image.composite(image, Image.new("RGBA", image.size, (0, 0, 0, 0)), mask)
    total = mask.histogram()[255]
    if not total: return []
    targets = {name: [_srgb(c) for c in colour] for name, colour in palette.items()}
    if not targets: return []  # a scene with no materials (or objects) has nothing to name
    counts = {}
    for count, pixel in masked.getcolors(image.width * image.height) or []:
        if pixel[3] < 128: continue
        name, colour = min(targets.items(), key=lambda item: sum(abs(a - b) for a, b in zip(item[1], pixel[:3])))
        if sum(abs(a - b) for a, b in zip(colour, pixel[:3])) <= 9: counts[name] = counts.get(name, 0) + count
    return sorted(name for name, count in counts.items() if count >= minimum * total)


def _namer(palette):
    """Pixel -> name by nearest ID colour within tolerance (cached per colour)."""
    targets = {name: [_srgb(c) for c in colour] for name, colour in palette.items()}
    cache = {}
    def name(pixel):
        if pixel not in cache:
            best = min(targets.items(), key=lambda item: sum(abs(a - b) for a, b in zip(item[1], pixel[:3])), default=None)
            cache[pixel] = best[0] if best and pixel[3] >= 128 and sum(abs(a - b) for a, b in zip(best[1], pixel[:3])) <= 9 else None
        return cache[pixel]
    return name


def _material_transitions(ref_mat, cand_mat, ref_obj, mask, ref_pal, cand_pal, min_px):
    """Group changed pixels by (material before, material after, mesh) so reciprocal swaps are not cancelled out."""
    before, after, mesh = _namer(ref_pal["material"]), _namer(cand_pal["material"]), _namer(ref_pal["object"])
    counts = {}
    for keep, a, b, o in zip(mask.getdata(), ref_mat.getdata(), cand_mat.getdata(), ref_obj.getdata()):
        if not keep: continue
        key = (before(a), after(b), mesh(o))
        if key[0] != key[1]: counts[key] = counts.get(key, 0) + 1
    return sorted(key for key, count in counts.items() if count >= min_px)


def _change_mask(a, b, level):
    from PIL import ImageChops
    channels = ImageChops.difference(a, b).split()
    peak = channels[0]
    for channel in channels[1:]: peak = ImageChops.lighter(peak, channel)
    return peak.point(lambda v: 255 if v > level else 0)


def localise(views, reference_dir, candidate_dir, evidence, candidate_evidence=None, min_px=20):
    """Turn changed pixels into statements about objects and materials. The object-ID mask names what vanished,
    appeared, was revealed or moved; a material swap is claimed only where the object ID did not change (so occlusion
    is not a swap); lit and clay changes outside both ID masks are attributed to the objects covering them. Reference
    pixels are read with the reference palette, candidate pixels with the candidate's own."""
    from PIL import Image, ImageChops
    ref_pal = evidence["palette"]
    cand_pal = (candidate_evidence or evidence)["palette"]
    found = {}

    def note(text, view):
        entry = found.setdefault(text, {"statement": text, "views": []})
        if view not in entry["views"]: entry["views"].append(view)

    def load(root, view, pass_name):
        with Image.open(Path(root) / f"{view}.{pass_name}.png") as image: return image.convert("RGBA")

    count = lambda mask: mask.histogram()[255]
    for view, passes in sorted(views.items()):
        ref_obj, cand_obj = load(reference_dir, view, "object_id"), load(candidate_dir, view, "object_id")
        on = lambda mask: ", ".join(sorted(set(_shares(ref_obj, mask, ref_pal["object"])) | set(_shares(cand_obj, mask, cand_pal["object"])))) or "unknown mesh"
        obj_mask = _change_mask(ref_obj, cand_obj, THRESHOLDS["object_id"]["pixel"])
        explained = obj_mask
        if (passes.get("object_id") or {}).get("warn"):
            before, after = set(_shares(ref_obj, obj_mask, ref_pal["object"])), set(_shares(cand_obj, obj_mask, cand_pal["object"]))
            visible_before = set(_shares(ref_obj, Image.new("L", ref_obj.size, 255), ref_pal["object"], minimum=0.0))
            for name in sorted(before - after): note(f"object {name} is missing or hidden here", view)
            for name in sorted(after - before):
                note(f"object {name} revealed (was covered here)" if name in visible_before else f"object {name} appeared", view)
            if before & after: note(f"geometry of {', '.join(sorted(before & after))} moved or changed", view)
        if (passes.get("material_id") or {}).get("warn"):
            ref_mat, cand_mat = load(reference_dir, view, "material_id"), load(candidate_dir, view, "material_id")
            mat_mask = _change_mask(ref_mat, cand_mat, THRESHOLDS["material_id"]["pixel"])
            same_object = ImageChops.subtract(mat_mask, obj_mask)  # a swap is a material change on an unchanged object
            explained = ImageChops.lighter(explained, mat_mask)
            if count(same_object) >= min_px:
                for old, new, mesh in _material_transitions(ref_mat, cand_mat, ref_obj, same_object, ref_pal, cand_pal, min_px):
                    note(f"material {old or 'unknown'} -> {new or 'unknown'} on {mesh or 'unknown mesh'}", view)
        from PIL import ImageFilter
        halo = explained.filter(ImageFilter.MaxFilter(7))  # anti-aliased edges around an ID change belong to it
        for pass_name in ("lit", "clay"):
            if not (passes.get(pass_name) or {}).get("warn"): continue
            mask = _change_mask(load(reference_dir, view, pass_name), load(candidate_dir, view, pass_name), THRESHOLDS[pass_name]["pixel"])
            residual = ImageChops.subtract(mask, halo)  # independent of what the ID passes already explain
            # The residual must itself clear the pass's warning bar, so shadows and bounce light beside an ID change stay quiet.
            if count(residual) >= max(min_px, THRESHOLDS[pass_name]["fraction"] * mask.width * mask.height) and on(residual) != "unknown mesh":
                note(f"{'shading' if pass_name == 'lit' else 'surface shape'} changed on {on(residual)} ({pass_name} pass; IDs unchanged there)", view)
    return sorted(found.values(), key=lambda e: (-len(e["views"]), e["statement"]))


def critic_signal(reference_dir, candidate_dir, server=None):
    """Independent second visual signal: frontier-lab's render critic (`scripts/render_critic.py`, #1956) in reference
    mode on the four lit views. Its pixel gate only, unless a vision-model server is given to name what changed.
    Reported as unavailable when the critic is not installed; the primary diff never depends on it."""
    try:
        import render_critic
    except ImportError:
        return {"available": False}
    names = [f"{view}.lit.png" for view in lab.bpy_side.VIEWS]
    options = {"diff_only": server is None, **({"server": server} if server else {})}
    try:
        result = render_critic.check([str(candidate_dir / n) for n in names], reference=[str(reference_dir / n) for n in names], **options)
        require(isinstance(result, dict), "Invalid render critic result")
        if "error" in result or result.get("evidence_complete", True) is not True:
            return {"available": False, "evidence_complete": False, "observation": result,
                    "error": str(result.get("error") or "Render critic evidence is incomplete")[:300]}
        require(type(result.get("changed")) is bool and isinstance(result.get("pixel_diff"), dict),
                "Invalid render critic verdict")
        counts = [v.get("changed_px") if isinstance(v, dict) else None for v in result["pixel_diff"].values()]
        require(counts and all(type(n) is int and n >= 0 for n in counts), "Invalid render critic pixel counts")
        return {"available": True, "tool": "render_critic", "mode": "pixel gate" if server is None else "pixel gate + vision model",
                "changed": result["changed"], "changed_px": sum(counts), "defects": result.get("defects", []),
                "observation": result}
    except Exception as exc:  # a failing critic (unreachable model server, bad image) never discards the primary result
        return {"available": False, "error": f"{type(exc).__name__}: {exc}"[:300]}


def second_opinion(critic, warnings):
    """Agreement between the primary diff and the critic; a change only the critic sees becomes a visual warning."""
    if (critic.get("available") is not True or "error" in critic
            or critic.get("evidence_complete", True) is not True): return None
    agree = critic["changed"] == bool(warnings)
    if critic["changed"] and not warnings:
        warnings.append(f"independent render critic sees a change the primary diff did not ({critic['changed_px']} px over the lit views)")
    return agree


def roundtrip_and_compare(exe, target, timeout=600, critic_server=None):
    """Given <target>/source/{manifest,evidence}.json, renders and <target>/export.glb: reimport in a NEW Blender
    process with the source cameras and compare both sides."""
    load = lambda path: json.loads(path.read_text(encoding="utf-8"))
    evidence = load(target / "source" / "evidence.json")
    files = _evidence_files(evidence, "Source")
    cameras = target / "cameras.json"
    cameras.write_text(json.dumps(evidence["camera_spec"], indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    seconds = lab.run(exe, ["evidence", "--glb", target / "export.glb", "--out-dir", target / "roundtrip", "--out",
                            target / "roundtrip.json", "--cameras", cameras], target / "roundtrip.log.json", timeout)
    src_manifest, rt_manifest = load(target / "source" / "manifest.json"), load(target / "roundtrip" / "manifest.json")
    _evidence_files(load(target / "roundtrip" / "evidence.json"), "Roundtrip")
    for name in files:
        require((target / "source" / "renders" / name).is_file() and (target / "roundtrip" / "renders" / name).is_file(),
                f"Missing render {name}")
    structure = compare_manifests(src_manifest, rt_manifest)
    views, warnings = compare_renders(target / "source" / "renders", target / "roundtrip" / "renders", evidence, target / "diff")
    structure["localisation"] = localise(views, target / "source" / "renders", target / "roundtrip" / "renders", evidence,
                                         load(target / "roundtrip" / "evidence.json"))
    critic = critic_signal(target / "source" / "renders", target / "roundtrip" / "renders", critic_server)
    critic["agrees_with_primary"] = second_opinion(critic, warnings)
    return src_manifest, rt_manifest, evidence, structure, views, warnings, seconds, critic


def sentinel(blender_path, blend_path, out_dir, seed_defect=None, timeout=600, studio_lease=None, critic_server=None):
    exe = lab.executable(blender_path)
    blend = Path(blend_path).expanduser().resolve()
    require(blend.is_file() and blend.suffix.lower() == ".blend", "blend must be an existing .blend file")
    target = Path(out_dir).expanduser().resolve()
    require(not target.exists(), "out_dir must be new")
    require(seed_defect in (None, *lab.bpy_side.SEEDED_DEFECTS), "Unknown seeded defect")
    # Validate before any file or process exists; the TTL covers both Blender processes at their timeouts.
    lease = lab.StudioGpuLease(studio_lease, ttl_seconds=min(4 * 3600, 2 * timeout + 300)) if studio_lease else None
    target.mkdir(parents=True)
    before = lab.file_sha(blend)
    glb = target / "export.glb"
    args = ["evidence", "--blend", blend, "--out-dir", target / "source", "--out", target / "source.json", "--export", glb]
    if seed_defect: args += ["--seed-defect", seed_defect]
    with lease or nullcontext() as grant:  # a refused lease raises before Blender starts
        seconds_source = lab.run(exe, args, target / "source.log.json", timeout)
        require(lab.file_sha(blend) == before, "Source .blend changed during the sentinel run")
        require(glb.is_file() and glb.stat().st_size > 0, "GLB export is missing")
        source_record = json.loads((target / "source.json").read_text(encoding="utf-8"))
        src_manifest, rt_manifest, evidence, structure, views, warnings, seconds_roundtrip, critic = roundtrip_and_compare(
            exe, target, timeout, critic_server)
    rt_evidence = json.loads((target / "roundtrip" / "evidence.json").read_text(encoding="utf-8"))
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
        "gpu_cost": lab.gpu_cost(evidence, rt_evidence), "second_signal": critic,
        "studio_lease": None if lease is None else {"holder": lease.holder, "granted": bool(grant and grant.get("granted")),
                                                    "released": bool(getattr(lease, "released", {}).get("released"))},
        "structural_failures": structure["failures"], "format_losses": structure["format_losses"],
        "expected_exclusions": structure["expected_exclusions"], "visual_warnings": warnings, "views": views,
        "localisation": structure["localisation"],
        "artifacts": [{"path": p.relative_to(target).as_posix(), "sha256": lab.file_sha(p), "bytes": p.stat().st_size}
                      for p in sorted(target.rglob("*")) if p.is_file()],
    }
    # Recheck after both workers, image comparison and artifact hashing, immediately before publication.
    require(lab.file_sha(blend) == before, "Source .blend changed during the sentinel run")
    (target / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", required=True)
    parser.add_argument("--blend", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--seed-defect", choices=lab.bpy_side.SEEDED_DEFECTS)
    parser.add_argument("--studio-lease", metavar="URL",
                        help="hold the Studio GPU lease (pauses its ComfyUI) for the run, e.g. http://127.0.0.1:8191; "
                             "only for heavy GPU work, see result.gpu_cost")
    parser.add_argument("--critic-server", metavar="URL", help="vision-model server for the render critic's labels (pixel gate only without it)")
    args = parser.parse_args(argv)
    try:
        result = sentinel(args.blender, args.blend, args.out_dir, args.seed_defect, studio_lease=args.studio_lease,
                          critic_server=args.critic_server)
    except (lab.BlenderLabError, OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps({"pass": result["pass"], "structural_failures": result["structural_failures"],
                      "visual_warnings": result["visual_warnings"]}, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
