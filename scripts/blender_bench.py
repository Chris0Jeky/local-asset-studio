"""Blender render benchmark: one Blender build, engine and device per run; cold render, warm-ups and timed repeats apart.

  python scripts/blender_bench.py --blender <blender.exe> --engine cycles --device HIPRT --out bench.jsonl
  python scripts/blender_bench.py --blender <blender.exe> --engine eevee --gpu-backend vulkan --out bench.jsonl

Each run starts a fresh Blender, builds a deterministic generated scene (or opens `--blend`), renders once cold (kernel
load/compile, BVH and shader compilation included), then `--warmup` untimed and `--repeats` timed renders, and appends
one JSON line: per-render seconds, median/min/max, peak process RSS and private bytes (sampled every 0.25 s), the
sampled peak of dedicated VRAM over the pre-run baseline (Windows `GPU Adapter Memory`, one query per ~1.5 s, so the
GPU must be otherwise idle), the sha256 of every output's decoded pixels and the timed repeats' drift. Frames go to a
per-run folder; a run counts only if Blender printed its result and exited 0 within `--timeout`. `--table bench.jsonl` prints a Markdown summary. Cycles devices: CPU, HIP (HIP RT off), HIPRT (HIP RT on).
"""
import argparse, hashlib, json, os, statistics, subprocess, sys, tempfile, threading, time
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
    return {}  # gpu.platform is unavailable in background mode; confirm the backend once with --debug-gpu


def inner(cfg):
    import bpy
    t0 = time.perf_counter()
    if cfg["blend"]: bpy.ops.wm.open_mainfile(filepath=cfg["blend"]); sc = bpy.context.scene
    else: sc = build_scene(cfg["engine"], cfg["res"], cfg["samples"])
    info = configure(sc, cfg["engine"], cfg["device"], cfg["samples"]); setup_s = time.perf_counter() - t0
    sc.render.image_settings.file_format = "PNG"  # an opened --blend keeps its own format; the host reads r??.png
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


class Peaks:
    """Sample process-tree memory every 0.25 s and adapter VRAM on its own thread (one typeperf query takes ~1.5 s)."""
    def __init__(self, pid):
        self.pid, self.stop, self.rss, self.private, self.vram = pid, threading.Event(), 0, 0, 0
        self.threads = [threading.Thread(target=f, daemon=True) for f in (self._memory, self._vram)]
        for t in self.threads: t.start()
    def _memory(self):
        import psutil
        try: p = psutil.Process(self.pid)
        except Exception: return
        while not self.stop.is_set():
            try:
                m = [q.memory_info() for q in [p] + p.children(recursive=True)]
                self.rss = max(self.rss, sum(x.rss for x in m)); self.private = max(self.private, sum(getattr(x, "private", 0) for x in m))
            except Exception: pass
            self.stop.wait(0.25)
    def _vram(self):
        while not self.stop.is_set(): self.vram = max(self.vram, vram_bytes() or 0)
    def close(self):
        self.stop.set()
        for t in self.threads: t.join(30)


def summarise(res, returncode, lines, out_dir, warmup):
    """Record fields for one finished Blender process; a run counts only with a result line AND exit code 0."""
    if not res or returncode != 0:
        return {"exit_code": "no result" if returncode == 0 else returncode, "log_tail": "".join(lines[-25:])}
    # Hash decoded pixels: PNG metadata carries the render time and date, so file bytes differ on identical images.
    from PIL import Image, ImageChops
    imgs = [Image.open(Path(out_dir) / f"r{i:02d}.png").convert("RGBA") for i in range(len(res["times"]))]
    hashes = [hashlib.sha256(im.tobytes()).hexdigest() for im in imgs]; first = 1 + warmup; timed = res["times"][first:]
    # GPU path tracing is not bit-deterministic between renders, so also record how far timed repeats drift (0-255).
    drift = max(max(b[1] for b in ImageChops.difference(imgs[first], im).getextrema()) for im in imgs[first:])
    return dict(res, hashes=hashes, repeat_max_abs_diff=drift, cold_s=res["times"][0], warm_median_s=round(statistics.median(timed), 4),
                warm_min_s=min(timed), warm_max_s=max(timed), timed_hashes_identical=len(set(hashes[first:])) == 1)


def kill_tree(proc):
    import psutil
    try: children = psutil.Process(proc.pid).children(recursive=True)
    except Exception: children = []
    for c in children:  # one child exiting first must not spare the rest
        try: c.kill()
        except Exception: pass
    proc.kill()


def run(a):
    stamp = time.strftime("%Y%m%d-%H%M%S"); root = Path(a.out).with_suffix(""); root.mkdir(parents=True, exist_ok=True)
    # Every run gets its own, atomically created frame folder, so earlier records stay reproducible.
    run_dir = tempfile.mkdtemp(prefix=f"{Path(a.blender).parent.name}-{a.engine}-{a.device or a.gpu_backend}-{stamp}-", dir=root)
    cfg = {"engine": a.engine, "device": a.device, "samples": a.samples or (128 if a.engine == "cycles" else 64),
           "res": [a.width, a.height], "warmup": a.warmup, "repeats": a.repeats, "blend": a.blend,
           "out_dir": run_dir}
    argv = [a.blender, "--factory-startup", "-b"] + (["--gpu-backend", a.gpu_backend] if a.gpu_backend else []) + \
           ["--python", __file__, "--", INNER_FLAG, json.dumps(cfg)]
    base = vram_bytes(); t = time.perf_counter()
    proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True)
    peaks = Peaks(proc.pid)
    try: out, _ = proc.communicate(timeout=a.timeout); timed_out = False
    except subprocess.TimeoutExpired:
        kill_tree(proc); timed_out = True
        try: out, _ = proc.communicate(timeout=30)
        except subprocess.TimeoutExpired: out = ""  # a grandchild still holds the pipe; give up on the log tail
    peaks.close(); lines = out.splitlines(keepends=True)
    rec = {"blender_exe": a.blender, "engine": a.engine, "device": a.device, "gpu_backend": a.gpu_backend, "config": cfg,
           "exit_code": proc.returncode, "process_wall_s": round(time.perf_counter() - t, 2),
           "peak_rss_mb": round(peaks.rss / 2**20), "peak_private_mb": round(peaks.private / 2**20),
           "vram_baseline_mb": round(base / 2**20) if base else None, "vram_peak_mb": round(peaks.vram / 2**20) if peaks.vram else None,
           "vram_peak_over_baseline_mb": round((peaks.vram - base) / 2**20) if base and peaks.vram else None,
           "started": stamp}
    res = None if timed_out else next((json.loads(l.split(" ", 1)[1]) for l in lines if l.startswith("BENCH_RESULT ")), None)
    rec.update(summarise(res, proc.returncode, lines, cfg["out_dir"], a.warmup))
    if timed_out: rec["exit_code"] = f"timeout {a.timeout}s"
    with open(a.out, "a", encoding="utf-8") as f: f.write(json.dumps(rec) + "\n")
    print(json.dumps({k: rec.get(k) for k in ("engine", "device", "gpu_backend", "exit_code", "cold_s", "warm_median_s",
                                                "peak_private_mb", "vram_peak_over_baseline_mb", "blender")}))
    return 0 if "times" in rec else 1


def table(path):
    rows = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
    print("| Blender | engine | device/backend | cold s | warm median s (min-max) | setup s | peak private MB | VRAM +MB | repeat max diff | last hash |")
    print("|---|---|---|---:|---:|---:|---:|---:|---:|---|")
    for r in rows:
        if "times" not in r: print(f"| {Path(r['blender_exe']).parent.name} | {r['engine']} | {r['device'] or r['gpu_backend']} | failed (exit {r['exit_code']}) | | | | | | |"); continue
        print(f"| {r['blender']} | {r['engine']} | {r['device'] or r['gpu_backend']} | {r['cold_s']} | "
              f"{r['warm_median_s']} ({r['warm_min_s']}-{r['warm_max_s']}) | {r['setup_s']} | {r['peak_private_mb']} | "
              f"{r['vram_peak_over_baseline_mb']} | {r.get('repeat_max_abs_diff', 0 if r['timed_hashes_identical'] else '?')} | {r['hashes'][-1][:12]} |")


def main():
    if INNER_FLAG in sys.argv: return inner(json.loads(sys.argv[sys.argv.index(INNER_FLAG) + 1]))
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--table"); ap.add_argument("--blender"); ap.add_argument("--engine", choices=["cycles", "eevee"], default="cycles")
    ap.add_argument("--device", choices=["CPU", "HIP", "HIPRT"]); ap.add_argument("--gpu-backend", choices=["opengl", "vulkan"])
    ap.add_argument("--samples", type=int); ap.add_argument("--width", type=int, default=1280); ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--warmup", type=int, default=2); ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--blend"); ap.add_argument("--out", default="bench.jsonl")
    ap.add_argument("--timeout", type=int, default=1800, help="seconds before the Blender process tree is killed")
    a = ap.parse_args()
    if a.table: return table(a.table)
    if not a.blender: ap.error("--blender is required")
    if a.engine == "cycles" and not a.device: ap.error("--device is required for cycles")
    sys.exit(run(a))


if __name__ == "__main__":
    main()
