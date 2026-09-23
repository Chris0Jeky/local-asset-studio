"""`python phase_probe.py <tag> <preset>...`: SFW SDXL jobs through the running Studio, sampling ComfyUI/dwm GPU memory every 0.25 s and the ComfyUI log line count. Never resubmits."""
import json, sys, time, threading, urllib.request, glob, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "app")); import gpu_memory
HOST = "127.0.0.1:8191"; ROOT = Path(r"C:/Users/jekyt/source/local-asset-studio/experiments/runs")
TAG = sys.argv[1]; CELLS = sys.argv[2:]
OUT = Path(__file__).with_name(f"phase_{TAG}.json")
LOG = max(glob.glob(r"C:/AI/logs/*-error.log"), key=os.path.getmtime)
def req(method, path, body=None, timeout=60):
    r = urllib.request.Request(f"http://{HOST}{path}", data=None if body is None else json.dumps(body).encode(), method=method,
                               headers={"Host": HOST, "Origin": f"http://{HOST}", "Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=timeout) as resp: return json.loads(resp.read().decode())
NEG = "nude, nsfw, explicit, suggestive, worst quality, low quality, blurry, bad anatomy, bad hands, text, watermark"
POS = "masterpiece, best quality, 1girl, solo, adult woman, knight in silver plate armor, standing in a castle courtyard, full body, daytime"
def controls(seed, scheduler): return {"positive": POS, "negative": NEG, "width": 832, "height": 1216, "seed": seed, "steps": 20, "cfg": 5,
                                     "sampler": "euler_ancestral", "scheduler": scheduler, "denoise": 1, "lora": 0, "lora2": 0}
SEEDS = {"wai": (2026092381, "normal"), "cstati-v3-baseline": (2026092382, "karras"), "yumeflux-ilv1-baseline": (2026092383, "normal")}
samples = []; stop = threading.Event(); comfy_pid = req("GET", "/api/health")["gpu_memory"]["pid"]
def sampler():
    while not stop.is_set():
        r = gpu_memory.read(); a = gpu_memory.select_adapter(r["adapters"] or {}, comfy_pid) if r["adapters"] else None
        procs = (r["adapters"] or {}).get(a, {})
        me = procs.get(comfy_pid, {}); others = sum(p["dedicated_bytes"] for pid, p in procs.items() if pid != comfy_pid)
        dwm = max((p["dedicated_bytes"] for pid, p in procs.items() if pid == 2288), default=None)
        try: lines = sum(1 for _ in open(LOG, encoding="utf-8", errors="replace"))
        except OSError: lines = None
        samples.append({"t": round(time.time(), 2), "ded": me.get("dedicated_bytes"), "shared": me.get("shared_bytes"), "others": others, "dwm": dwm, "log_lines": lines})
        time.sleep(0.25)
th = threading.Thread(target=sampler, daemon=True); th.start(); rows = []
for preset in CELLS:
    seed, sch = SEEDS[preset]
    job_id = req("POST", "/api/jobs", {"preset_id": preset, "controls": controls(seed, sch), "batch_count": 1})["id"]; print("JOB", preset, job_id, flush=True)
    t0 = time.time(); deadline = t0 + 600; state = None
    while time.time() < deadline:
        p = ROOT / job_id / "state.json"
        state = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
        if state and state.get("status") in ("completed", "failed", "uncertain", "not_submitted", "partial"): break
        time.sleep(1)
    subs = (state or {}).get("submissions") or [{}]
    row = {"preset": preset, "job_id": job_id, "prompt_id": subs[0].get("prompt_id"), "status": (state or {}).get("status"), "seconds": (state or {}).get("elapsed_seconds"),
           "t0": t0, "t1": time.time(), "message": (state or {}).get("message"), "gpu_memory": subs[0].get("gpu_memory"), "model_evictions": (state or {}).get("model_evictions")}
    rows.append(row); print(json.dumps(row), flush=True)
    if row["status"] != "completed": print("STOP", row["status"]); break
time.sleep(2); stop.set(); th.join()
OUT.write_text(json.dumps({"log": LOG, "comfy_pid": comfy_pid, "rows": rows, "samples": samples}, indent=0))
peak = max(samples, key=lambda s: s["shared"] or 0)
print("peak shared sample", peak, "n", len(samples)); print("DONE")
