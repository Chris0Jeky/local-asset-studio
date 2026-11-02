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


def cameras_hash(data):
    """Identity of a dataset's held-out cameras: renders are only comparable with the transforms they were made from."""
    import hashlib; return hashlib.sha256((Path(data) / "transforms_test.json").read_bytes()).hexdigest()


def render(splat, data, out, engine):
    out = Path(out); out.mkdir(parents=True, exist_ok=True); (out / "rendered.json").unlink(missing_ok=True)  # first: a failed run leaves none
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
    import time; t = time.perf_counter()
    for i, f in enumerate(meta["frames"]):
        cam.matrix_world = Matrix(f["transform_matrix"]); sc.render.filepath = str(out / f"r_{i:03d}.png"); bpy.ops.render.render(write_still=True)
    names = [Path(f["file_path"]).name + ".png" for f in meta["frames"]]
    (out / "rendered.json").write_text(json.dumps({"splat": str(splat), "dataset": str(data), "views": names, "cameras": cameras_hash(data)}))
    print("RENDERED", len(meta["frames"]), round(time.perf_counter() - t, 2))


def score(data, out):
    from PIL import Image, ImageChops  # Pillow only: the CI test environment has no NumPy
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import render_critic as rc
    def white(p):
        im = Image.open(p).convert("RGBA"); return Image.alpha_composite(Image.new("RGBA", im.size, (255, 255, 255, 255)), im).convert("RGB")
    # Score exactly the held-out frames the dataset declares, and only renders whose run finished (render writes the
    # manifest last, after deleting any old one), so a missing, stale or partial view set fails instead of skewing the mean.
    views = [Path(f["file_path"]).name + ".png" for f in json.loads((Path(data) / "transforms_test.json").read_text())["frames"]]
    manifest = json.loads((Path(out) / "rendered.json").read_text())
    if manifest["views"] != views: raise ValueError(f"rendered views {len(manifest['views'])} do not match the dataset's {len(views)} held-out views")
    if manifest.get("cameras") != cameras_hash(data): raise ValueError("renders were made from another dataset's held-out cameras")
    rows = []
    for name in views:
        gt = Path(data) / "test" / name; g, r = white(gt), white(Path(out) / name)
        if g.size != r.size: raise ValueError(f"{name}: render {r.size} vs truth {g.size}")
        hist = ImageChops.difference(g, r).histogram()  # 3 x 256 bins of |difference| per channel
        mse = sum(n * (i % 256) ** 2 for i, n in enumerate(hist)) / (g.width * g.height * 3 * 255 ** 2)
        (Path(out) / "gt_white").mkdir(exist_ok=True); (Path(out) / "pr_white").mkdir(exist_ok=True)  # same names: the critic matches views by label
        g.save(Path(out) / "gt_white" / gt.name); r.save(Path(out) / "pr_white" / gt.name)
        px = rc.pixel_diff([Path(out) / "pr_white" / gt.name], [Path(out) / "gt_white" / gt.name])
        rows.append({"view": gt.name, "psnr": round(10 * math.log10(1 / max(mse, 1e-12)), 2), "changed_px": next(iter(px.values()))["changed_px"]})
    summary = {"mean_psnr": round(sum(r["psnr"] for r in rows) / len(rows), 2), "min_psnr": min(r["psnr"] for r in rows),
               "mean_changed_px": round(sum(r["changed_px"] for r in rows) / len(rows)), "views": rows}
    (Path(out) / "score.json").write_text(json.dumps(summary, indent=1)); print(json.dumps({k: v for k, v in summary.items() if k != "views"}))


if __name__ == "__main__":
    if "--" in sys.argv:
        a = sys.argv[sys.argv.index("--") + 1:]; render(a[0], a[1], a[2], a[3] if len(a) > 3 else "eevee")
    elif sys.argv[1] == "score": score(sys.argv[2], sys.argv[3])
