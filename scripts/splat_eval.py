"""Render a trained splat from a dataset's held-out cameras (inside Blender 5.4), then score it on the host.

  blender -b --factory-startup --python scripts/splat_eval.py -- <splat.ply|.spz> <dataset_dir> <out_dir> [eevee|cycles]
  python scripts/splat_eval.py score <dataset_dir> <out_dir>

The dataset comes from scripts/splat_orbit_dataset.py; a trainer such as Brush turns its train split into the splat.

Render: imports the splat, places the camera at every transforms_test.json matrix with the dataset's camera_angle_x,
transparent film. Score: composites ground truth and render over white and reports per-view PSNR, the mean, and the
render critic's pixel-diff count (level > 8) per view.
"""
import json, math, sys
from pathlib import Path


def render(splat, data, out, engine):
    import bpy
    from mathutils import Matrix
    bpy.ops.wm.read_factory_settings(use_empty=True); sc = bpy.context.scene
    (bpy.ops.wm.spz_import if splat.endswith(".spz") else bpy.ops.wm.ply_import)(filepath=splat)
    o = bpy.context.selected_objects[0]; print("SPLAT", o.type, getattr(o.data, "type", None), len(o.data.points) if o.type == "POINTCLOUD" else len(o.data.vertices))
    meta = json.loads((Path(data) / "transforms_test.json").read_text()); res = json.loads((Path(data) / "scene.json").read_text())["res"]
    bpy.ops.object.camera_add(); cam = bpy.context.active_object; sc.camera = cam
    cam.data.sensor_fit = "HORIZONTAL"; cam.data.angle_x = meta["camera_angle_x"]
    sc.render.resolution_x = sc.render.resolution_y = res; sc.render.film_transparent = True; sc.view_settings.view_transform = "Standard"
    sc.render.image_settings.color_mode = "RGBA"
    if engine == "cycles": sc.render.engine = "CYCLES"; sc.cycles.samples = 64; sc.cycles.use_denoising = False
    else: sc.render.engine = "BLENDER_EEVEE"; sc.eevee.taa_render_samples = 64
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    import time; t = time.perf_counter()
    for i, f in enumerate(meta["frames"]):
        cam.matrix_world = Matrix(f["transform_matrix"]); sc.render.filepath = str(out / f"r_{i:03d}.png"); bpy.ops.render.render(write_still=True)
    print("RENDERED", len(meta["frames"]), round(time.perf_counter() - t, 2))


def score(data, out):
    import numpy as np
    from PIL import Image
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import render_critic as rc
    def white(p):
        a = np.asarray(Image.open(p).convert("RGBA"), dtype=np.float64) / 255; return a[..., :3] * a[..., 3:] + (1 - a[..., 3:])
    rows = []
    for gt in sorted((Path(data) / "test").glob("r_*.png")):
        pr = Path(out) / gt.name; g, r = white(gt), white(pr); mse = float(((g - r) ** 2).mean())
        (Path(out) / "gt_white").mkdir(exist_ok=True); (Path(out) / "pr_white").mkdir(exist_ok=True)  # same names: the critic matches views by label
        Image.fromarray((g * 255).astype("uint8")).save(Path(out) / "gt_white" / gt.name); Image.fromarray((r * 255).astype("uint8")).save(Path(out) / "pr_white" / gt.name)
        px = rc.pixel_diff([Path(out) / "pr_white" / gt.name], [Path(out) / "gt_white" / gt.name])
        rows.append({"view": gt.name, "psnr": round(10 * math.log10(1 / max(mse, 1e-12)), 2), "changed_px": next(iter(px.values()))["changed_px"]})
    summary = {"mean_psnr": round(sum(r["psnr"] for r in rows) / len(rows), 2), "min_psnr": min(r["psnr"] for r in rows),
               "mean_changed_px": round(sum(r["changed_px"] for r in rows) / len(rows)), "views": rows}
    (Path(out) / "score.json").write_text(json.dumps(summary, indent=1)); print(json.dumps({k: v for k, v in summary.items() if k != "views"}))


if __name__ == "__main__":
    if "--" in sys.argv:
        a = sys.argv[sys.argv.index("--") + 1:]; render(a[0], a[1], a[2], a[3] if len(a) > 3 else "eevee")
    elif sys.argv[1] == "score": score(sys.argv[2], sys.argv[3])
