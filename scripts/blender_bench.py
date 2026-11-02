"""Blender render benchmark: one Blender build, engine and device per run; cold render, warm-ups and timed repeats apart.

  python scripts/blender_bench.py --blender <blender.exe> --engine cycles --device HIPRT --out bench.jsonl
  python scripts/blender_bench.py --blender <blender.exe> --engine eevee --gpu-backend vulkan --out bench.jsonl

Each run starts a fresh Blender, builds a deterministic generated scene (or opens `--blend`), renders once cold (kernel
load/compile, BVH and shader compilation included), then `--warmup` untimed and `--repeats` timed renders, and appends
one JSON line: per-render seconds, median/min/max, peak process RSS and private bytes, peak dedicated VRAM over the
pre-run baseline (Windows `GPU Adapter Memory` counter, so the GPU must be otherwise idle), and the sha256 of every
output's decoded pixels. `--table bench.jsonl` prints a Markdown summary. Cycles devices: CPU, HIP (HIP RT off), HIPRT (HIP RT on).
"""
import argparse, hashlib, json, os, statistics, subprocess, sys, threading, time
from pathlib import Path

INNER_FLAG = "--blender-bench-inner"


# ---------------------------------------------------------------- inside Blender
def build_scene(engine, res, samples):
    """Deterministic stress scene: ~1.6 M triangles of instanced subdivided monkeys, glass/metal/diffuse, area lights."""
    import bpy, math, random
    bpy.ops.wm.read_factory_settings(use_empty=True); sc = bpy.context.scene; rng = random.Random(7)
    def mat(name, **kw):
        m = bpy.data.materials.new(name); m.use_nodes = True; b = m.node_tree.nodes["Principled BSDF"]
        for k, v in kw.items(): b.inputs[k].default_value = v
        return m
    mats = [mat("diffuse", **{"Base Color": (0.8, 0.3, 0.2, 1), "Roughness": 0.7}),
            mat("metal", **{"Base Color": (0.9, 0.85, 0.7, 1), "Metallic": 1.0, "Roughness": 0.2}),
            mat("glass", **{"Base Color": (0.9, 0.95, 1, 1), "Transmission Weight": 1.0, "Roughness": 0.02, "IOR": 1.45})]
    bpy.ops.mesh.primitive_monkey_add(); src = bpy.context.active_object
    src.modifiers.new("s", "SUBSURF").levels = 2; bpy.ops.object.modifier_apply(modifier="s")  # ~7.9 k faces, ~15.7 k tris
    src.hide_render = src.hide_viewport = True; src.data.materials.append(None)
    for i in range(100):  # linked duplicates share one mesh; the material sits on each object's slot
        o = src.copy(); o.hide_render = o.hide_viewport = False; sc.collection.objects.link(o)
        o.location = (rng.uniform(-9, 9), rng.uniform(-6, 12), rng.uniform(0.6, 2.5)); o.rotation_euler = (0, 0, rng.uniform(0, 6.3))
        o.scale = (rng.uniform(0.5, 1.2),) * 3; o.material_slots[0].link = "OBJECT"; o.material_slots[0].material = mats[i % 3]
    bpy.ops.mesh.primitive_plane_add(size=60); bpy.context.active_object.data.materials.append(mat("floor", **{"Base Color": (0.5, 0.5, 0.5, 1), "Roughness": 0.4}))
    for loc, e in (((0, -4, 8), 2500), ((-8, 6, 5), 1500)):
        bpy.ops.object.light_add(type="AREA", location=loc); l = bpy.context.active_object; l.data.energy = e; l.data.size = 4
    bpy.ops.object.camera_add(location=(0, -16, 6), rotation=(math.radians(72), 0, 0)); sc.camera = bpy.context.active_object
    w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True; w.node_tree.nodes["Background"].inputs[1].default_value = 0.3
    sc.render.resolution_x, sc.render.resolution_y = res; sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"; sc.view_settings.view_transform = "Standard"
    return sc


def configure(sc, engine, device, samples):
    import bpy
    if engine == "cycles":
        sc.render.engine = "CYCLES"; c = sc.cycles; c.samples = samples; c.use_adaptive_sampling = False
        c.use_denoising = False; c.seed = 0
        if device == "CPU": c.device = "CPU"; return {"devices": ["CPU"]}
        p = bpy.context.preferences.addons["cycles"].preferences; p.compute_device_type = "HIP"; p.get_devices()
        if hasattr(p, "use_hiprt"): p.use_hiprt = device == "HIPRT"
        elif device == "HIPRT": raise SystemExit("this build has no use_hiprt preference")
        on = []
        for d in p.devices:
            d.use = d.type == "HIP"; on += [d.name] if d.use else []
        if not on: raise SystemExit("no HIP device visible")
        c.device = "GPU"; return {"devices": on, "use_hiprt": getattr(p, "use_hiprt", None)}
    # Engine identifiers moved between releases; feature-test the enum instead of reading the version.
    ids = {i.identifier for i in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in ids else "BLENDER_EEVEE"
    sc.eevee.taa_render_samples = samples
    if hasattr(sc.eevee, "use_raytracing"): sc.eevee.use_raytracing = True
    import gpu
    return {"gpu_backend": gpu.platform.backend_type_get(), "gpu_device": gpu.platform.renderer_get()}


def inner(cfg):
    import bpy
    t0 = time.perf_counter()
    if cfg["blend"]: bpy.ops.wm.open_mainfile(filepath=cfg["blend"]); sc = bpy.context.scene
    else: sc = build_scene(cfg["engine"], cfg["res"], cfg["samples"])
    info = configure(sc, cfg["engine"], cfg["device"], cfg["samples"]); setup_s = time.perf_counter() - t0
    out = Path(cfg["out_dir"]); out.mkdir(parents=True, exist_ok=True); times = []
    for i in range(1 + cfg["warmup"] + cfg["repeats"]):
        sc.render.filepath = str(out / f"r{i:02d}.png"); t = time.perf_counter()
        bpy.ops.render.render(write_still=True); times.append(round(time.perf_counter() - t, 4))
    print("BENCH_RESULT " + json.dumps({"setup_s": round(setup_s, 3), "times": times, "info": info,
                                        "blender": bpy.app.version_string, "build_hash": bpy.app.build_hash.decode()}), flush=True)


# ---------------------------------------------------------------- host
def vram_bytes():
    """Max dedicated usage over GPU adapters (the discrete card dominates), or None off Windows."""
    try:
        out = subprocess.run(["typeperf", r"\GPU Adapter Memory(*)\Dedicated Usage", "-sc", "1"], capture_output=True,
                             text=True, timeout=20).stdout.splitlines()
        row = next(l for l in out if l.startswith('"') and not l.startswith('"(PDH'))
        return max(float(v.strip('"')) for v in row.split(",")[1:] if v.strip('"'))
    except Exception: return None


class Peaks(threading.Thread):
    def __init__(self, pid):
        super().__init__(daemon=True); self.pid, self.stop, self.rss, self.private, self.vram = pid, threading.Event(), 0, 0, 0
    def run(self):
        import psutil
        p = psutil.Process(self.pid); n = 0
        while not self.stop.is_set():
            try:
                procs = [p] + p.children(recursive=True)
                m = [q.memory_info() for q in procs]
                self.rss = max(self.rss, sum(x.rss for x in m)); self.private = max(self.private, sum(getattr(x, "private", 0) for x in m))
            except Exception: pass
            if n % 8 == 0: v = vram_bytes(); self.vram = max(self.vram, v or 0)
            n += 1; self.stop.wait(0.25)


def run(a):
    cfg = {"engine": a.engine, "device": a.device, "samples": a.samples or (128 if a.engine == "cycles" else 64),
           "res": [a.width, a.height], "warmup": a.warmup, "repeats": a.repeats, "blend": a.blend,
           "out_dir": str(Path(a.out).with_suffix("") / f"{Path(a.blender).parent.name}-{a.engine}-{a.device or a.gpu_backend}")}
    argv = [a.blender, "--factory-startup", "-b"] + (["--gpu-backend", a.gpu_backend] if a.gpu_backend else []) + \
           ["--python", __file__, "--", INNER_FLAG, json.dumps(cfg)]
    base = vram_bytes(); t = time.perf_counter()
    proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True)
    peaks = Peaks(proc.pid); peaks.start(); lines = proc.stdout.readlines(); proc.wait(); peaks.stop.set(); peaks.join()
    rec = {"blender_exe": a.blender, "engine": a.engine, "device": a.device, "gpu_backend": a.gpu_backend, "config": cfg,
           "exit_code": proc.returncode, "process_wall_s": round(time.perf_counter() - t, 2),
           "peak_rss_mb": round(peaks.rss / 2**20), "peak_private_mb": round(peaks.private / 2**20),
           "vram_baseline_mb": round(base / 2**20) if base else None, "vram_peak_mb": round(peaks.vram / 2**20) if peaks.vram else None,
           "vram_peak_over_baseline_mb": round((peaks.vram - base) / 2**20) if base and peaks.vram else None,
           "started": time.strftime("%Y-%m-%d %H:%M:%S")}
    res = next((json.loads(l.split(" ", 1)[1]) for l in lines if l.startswith("BENCH_RESULT ")), None)
    if res:
        # Hash decoded pixels: PNG metadata carries the render time and date, so file bytes differ on identical images.
        from PIL import Image
        res["hashes"] = [hashlib.sha256(Image.open(Path(cfg["out_dir"]) / f"r{i:02d}.png").convert("RGBA").tobytes()).hexdigest()
                         for i in range(len(res["times"]))]
        timed = res["times"][1 + a.warmup:]
        rec.update(res, cold_s=res["times"][0], warm_median_s=round(statistics.median(timed), 4), warm_min_s=min(timed),
                   warm_max_s=max(timed), timed_hashes_identical=len(set(res["hashes"][1 + a.warmup:])) == 1)
    else: rec["log_tail"] = "".join(lines[-25:])
    with open(a.out, "a", encoding="utf-8") as f: f.write(json.dumps(rec) + "\n")
    print(json.dumps({k: rec.get(k) for k in ("engine", "device", "gpu_backend", "exit_code", "cold_s", "warm_median_s",
                                                "peak_private_mb", "vram_peak_over_baseline_mb", "blender")}))
    return 0 if res else 1


def table(path):
    rows = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
    print("| Blender | engine | device/backend | cold s | warm median s (min–max) | setup s | peak private MB | VRAM +MB | timed hashes equal | last hash |")
    print("|---|---|---|---:|---:|---:|---:|---:|---|---|")
    for r in rows:
        if "times" not in r: print(f"| {Path(r['blender_exe']).parent.name} | {r['engine']} | {r['device'] or r['gpu_backend']} | failed (exit {r['exit_code']}) | | | | | | |"); continue
        print(f"| {r['blender']} | {r['engine']} | {r['device'] or (r['info'].get('gpu_backend'))} | {r['cold_s']} | "
              f"{r['warm_median_s']} ({r['warm_min_s']}–{r['warm_max_s']}) | {r['setup_s']} | {r['peak_private_mb']} | "
              f"{r['vram_peak_over_baseline_mb']} | {r['timed_hashes_identical']} | {r['hashes'][-1][:12]} |")


def main():
    if INNER_FLAG in sys.argv: return inner(json.loads(sys.argv[sys.argv.index(INNER_FLAG) + 1]))
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--table"); ap.add_argument("--blender"); ap.add_argument("--engine", choices=["cycles", "eevee"], default="cycles")
    ap.add_argument("--device", choices=["CPU", "HIP", "HIPRT"]); ap.add_argument("--gpu-backend", choices=["opengl", "vulkan"])
    ap.add_argument("--samples", type=int); ap.add_argument("--width", type=int, default=1280); ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--warmup", type=int, default=2); ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--blend"); ap.add_argument("--out", default="bench.jsonl")
    a = ap.parse_args()
    if a.table: return table(a.table)
    if not a.blender: ap.error("--blender is required")
    if a.engine == "cycles" and not a.device: ap.error("--device is required for cycles")
    sys.exit(run(a))


if __name__ == "__main__":
    main()
