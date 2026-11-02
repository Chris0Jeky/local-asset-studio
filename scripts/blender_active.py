"""Render-space active testing: search camera, pose, shape-key and culling configurations for the one where two
revisions of an asset disagree most, instead of trusting a fixed set of views (research report #1).

Both revisions are rendered as deterministic Workbench clay on a shared camera sphere, framed from `before`. The
search runs a coarse grid over azimuth × elevation × animation frame × shape-key weight × backface culling, ranks the
configurations by changed pixels (largest channel > 8 levels, the render critic's gate), and refines around the top
few. A pass that finds nothing is evidence for those dimensions only; materials and textures stay with the fixed lit
views.

    python scripts/blender_active.py search --blender <exe> --before a.blend --after b.blend --out-dir <new-dir>
    python scripts/blender_active.py corpus --blender <exe> --corpus-dir <known-bad corpus> --out-dir <new-dir>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import blender_lab as lab
from blender_lab import require

LEVEL, MIN_PX = 8, 20
AZIMUTHS, ELEVATIONS = tuple(range(0, 360, 45)), (-20, 15, 50)


def plan_from(manifest, max_frames=3):
    """Shared camera sphere and search dimensions taken from the `before` manifest."""
    corners = [o["world_bbox"] for o in manifest["objects"] if o["type"] == "MESH" and o["visible"] and not o["hide_render"] and o["world_bbox"]]
    require(corners, "before has no visible mesh to frame")
    low = [min(c["min"][i] for c in corners) for i in range(3)]
    high = [max(c["max"][i] for c in corners) for i in range(3)]
    radius = sum((h - l) ** 2 for l, h in zip(low, high)) ** 0.5 / 2
    spec = {"target": [round((l + h) / 2, 5) for l, h in zip(low, high)], "ortho_scale": round(radius * 2.1, 5)}
    sampled = sorted({f for group in ("pose_samples", "object_samples") for s in manifest.get(group, {}).values() for f in s["frames"]})
    if len(sampled) > max_frames: sampled = [sampled[round(i * (len(sampled) - 1) / (max_frames - 1))] for i in range(max_frames)]
    frames = sampled or [manifest["scene"]["frame_range"][0]]
    weights = (0.0, 1.0) if any(m.get("shape_keys") for m in manifest["meshes"]) else (0.0,)
    return spec, frames, weights


def grid(frames, weights, azimuths=AZIMUTHS, elevations=ELEVATIONS):
    return [{"azimuth": az, "elevation": el, "frame": f, "shape_keys": w, "backface_culling": c}
            for az in azimuths for el in elevations for f in frames for w in weights for c in (False, True)]


def refine(config, step=15):
    return [dict(config, azimuth=(config["azimuth"] + da) % 360, elevation=max(-80, min(80, config["elevation"] + de)))
            for da in (-step, 0, step) for de in (-step, 0, step) if da or de]


def changed_px(a_path, b_path, level=LEVEL):
    from PIL import Image, ImageChops
    with Image.open(a_path) as a, Image.open(b_path) as b:
        require(a.size == b.size, f"render sizes differ: {a_path} vs {b_path}")  # Pillow would silently crop
        channels = ImageChops.difference(a.convert("RGBA"), b.convert("RGBA")).split()
    peak = channels[0]
    for channel in channels[1:]: peak = ImageChops.lighter(peak, channel)
    return peak.point(lambda v: 255 if v > level else 0).histogram()[255]


def render_set(exe, blend, spec, configs, out_dir, size, timeout):
    out_dir.mkdir(parents=True)
    plan = out_dir / "plan.json"
    plan.write_text(json.dumps({"camera_spec": spec, "configs": configs}, indent=1), encoding="utf-8", newline="\n")
    lab.run(exe, ["render-probe", "--blend", blend, "--plan", plan, "--out-dir", out_dir / "renders", "--size", size,
                  "--out", out_dir / "probe.json"], out_dir / "probe.log.json", timeout)
    return [out_dir / "renders" / f"{i:04d}.png" for i in range(len(configs))]


def search(blender_path, before, after, out_dir, size=96, top=3, timeout=900, before_cache=None):
    """Two-stage search for maximal disagreement. `before_cache` reuses the before renders of an earlier search over
    the same before asset and grid (the corpus control)."""
    exe = lab.executable(blender_path)
    target = Path(out_dir).expanduser().resolve()
    require(not target.exists(), "out_dir must be new")
    target.mkdir(parents=True)
    started = time.perf_counter()
    key = {"before_sha256": lab.file_sha(before), "blender": exe.as_posix(), "size": size}
    require(before_cache is None or before_cache.get("key") == key, "before_cache was made for another asset, Blender or size")
    if before_cache is None:
        manifest = lab.manifest(exe, before, target / "before-manifest.json")
        spec, frames, weights = plan_from(manifest)
        configs = grid(frames, weights)
        before_renders = render_set(exe, before, spec, configs, target / "before-grid", size, timeout)
        before_cache = {"key": key, "spec": spec, "configs": configs, "renders": before_renders}
    spec, configs = before_cache["spec"], before_cache["configs"]
    after_renders = render_set(exe, after, spec, configs, target / "after-grid", size, timeout)
    scored = sorted(({"config": c, "changed_px": changed_px(a, b)} for c, a, b in zip(configs, before_cache["renders"], after_renders)),
                    key=lambda r: -r["changed_px"])
    neighbours = [n for r in scored[:top] if r["changed_px"] > 0 for n in refine(r["config"])]
    refined = []
    if neighbours:
        a = render_set(exe, before, spec, neighbours, target / "before-refine", size, timeout)
        b = render_set(exe, after, spec, neighbours, target / "after-refine", size, timeout)
        refined = [{"config": c, "changed_px": changed_px(x, y)} for c, x, y in zip(neighbours, a, b)]
    ranked = sorted(scored + refined, key=lambda r: -r["changed_px"])
    best = ranked[0]
    def sensitivity(dimension):  # best disagreement when that dimension is held at its default
        default = {"frame": configs[0]["frame"], "shape_keys": 0.0, "backface_culling": False}[dimension]
        return max((r["changed_px"] for r in scored if r["config"][dimension] == default), default=0)
    result = {"before": Path(before).name, "after": Path(after).name, "camera_spec": spec, "size": size,
              "grid_renders": len(configs), "refine_renders": len(neighbours), "max_changed_px": best["changed_px"],
              "best": best["config"], "detected": best["changed_px"] >= MIN_PX, "gate": {"level": LEVEL, "min_px": MIN_PX},
              "top": ranked[:5], "best_with_default": {d: sensitivity(d) for d in ("frame", "shape_keys", "backface_culling")},
              "seconds": round(time.perf_counter() - started, 2)}
    (target / "active.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return result, before_cache


def corpus(blender_path, corpus_dir, out_dir, size=96):
    """Run the search for every corpus entry against its control and compare with the fixed-view baseline."""
    root = Path(corpus_dir).expanduser().resolve()
    index = json.loads((root / "corpus.json").read_text(encoding="utf-8"))
    target = Path(out_dir).expanduser().resolve()
    require(not target.exists(), "out_dir must be new")
    target.mkdir(parents=True)
    import re
    entries = {e["id"]: e for e in index["entries"]}
    def contained(entry):  # a crafted corpus must not reach outside its root or our output
        require(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", entry["id"]) is not None, f"bad corpus entry id {entry['id']!r}")
        blend = (root / entry["blend"]).resolve()
        require(blend.is_relative_to(root) and blend.suffix == ".blend", f"corpus blend escapes the corpus: {entry['blend']}")
        return blend
    require("control" in entries, "corpus has no control entry")
    blends = {entry_id: contained(entry) for entry_id, entry in entries.items()}  # all checked before any Blender run
    control = blends["control"]
    cache, rows = None, []
    for entry_id in sorted(entries, key=lambda k: (k != "control", k)):
        entry = entries[entry_id]
        result, cache = search(blender_path, control, blends[entry_id], target / entry_id, size, before_cache=cache)
        rows.append({"id": entry_id, "expected": entry["expected"], "fixed_views": entry["baseline"]["caught_by_renders"],
                     "manifest": entry["baseline"]["caught_by_manifest"], "active": result["detected"],
                     "max_changed_px": result["max_changed_px"], "best": result["best"],
                     "best_with_default": result["best_with_default"], "seconds": result["seconds"]})
    defects = [r for r in rows if r["expected"] == "defective"]
    summary = {"control_clean": not next(r for r in rows if r["id"] == "control")["active"],
               "fixed_views_caught": sorted(r["id"] for r in defects if r["fixed_views"]),
               "active_caught": sorted(r["id"] for r in defects if r["active"]),
               "found_beyond_fixed_views": sorted(r["id"] for r in defects if r["active"] and not r["fixed_views"]),
               "missed_by_both_render_paths": sorted(r["id"] for r in defects if not r["active"] and not r["fixed_views"])}
    report = {"schema": "las.blender-active-testing.v1", "corpus": str(root), "rows": rows, "summary": summary}
    (target / "active-corpus.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    one = commands.add_parser("search")
    one.add_argument("--blender", required=True); one.add_argument("--before", required=True)
    one.add_argument("--after", required=True); one.add_argument("--out-dir", required=True)
    many = commands.add_parser("corpus")
    many.add_argument("--blender", required=True); many.add_argument("--corpus-dir", required=True); many.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "search":
            result, _ = search(args.blender, args.before, args.after, args.out_dir)
            print(json.dumps({k: result[k] for k in ("detected", "max_changed_px", "best", "best_with_default", "seconds")}, indent=2))
        else:
            print(json.dumps(corpus(args.blender, args.corpus_dir, args.out_dir)["summary"], indent=2))
    except (lab.BlenderLabError, OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
