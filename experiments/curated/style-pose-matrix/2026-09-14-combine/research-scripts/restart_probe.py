"""The slow state (15 September 2026): after some Qwen runs every FLUX.2 Klein 9B render sampled at ~60 s/step instead of ~6.5 s/step, and
POST /free did not restore it. This probe measures, in order: the ComfyUI process's host memory (private bytes vs resident working set,
page faults) while idle, the same after POST /free, one Klein 9B depth render's step rate, and, if it is still slow, the same after a
ComfyUI restart through the owner's launchers (C:/AI/Stop-ComfyUI.ps1, C:/AI/Start-ComfyUI.ps1 -NoBrowser). Nothing is stopped while the
queue is busy; the Studio's own jobs must be idle (checked). Report: restart_probe.json next to this file."""
import json, time, urllib.request, os, re, subprocess, sys
import psutil
OUT = os.path.dirname(os.path.abspath(__file__)); COMFY = "http://127.0.0.1:8188"; STUDIO = "http://127.0.0.1:8191"
LOG = "C:/AI/ComfyUI_windows_portable/ComfyUI/user/comfyui_8188.log"
GRAPH = json.load(open(OUT + "/pose3-depth-feet.graph.json"))
report = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "steps": []}
def note(**kw): kw["t"] = time.strftime("%H:%M:%S"); report["steps"].append(kw); print(json.dumps(kw), flush=True); json.dump(report, open(OUT + "/restart_probe.json", "w"), indent=1)
def get(url, timeout=10): return json.load(urllib.request.urlopen(url, timeout=timeout))
def comfy_process():
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cl = " ".join(p.info["cmdline"] or [])
            if "ComfyUI\\main.py" in cl or "ComfyUI/main.py" in cl: return p
        except (psutil.NoSuchProcess, psutil.AccessDenied): continue
    return None
def mem(label):
    p = comfy_process(); vm = psutil.virtual_memory(); sw = psutil.swap_memory(); d = dict(label=label, pid=p.pid if p else None, os_available_gb=round(vm.available / 2**30, 1), os_percent=vm.percent, swap_used_gb=round(sw.used / 2**30, 1))
    if p:
        try: mi = p.memory_info(); d.update(rss_gb=round(mi.rss / 2**30, 2), private_gb=round(getattr(mi, "private", 0) / 2**30, 2), pagefile_gb=round(getattr(mi, "pagefile", 0) / 2**30, 2), page_faults=getattr(mi, "num_page_faults", None))
        except psutil.Error as e: d["error"] = str(e)
    try: st = get(COMFY + "/system_stats", 5); d["vram_free_gb"] = round(st["devices"][0]["vram_free"] / 2**30, 1)
    except Exception as e: d["system_stats"] = "unreachable"
    note(**d); return d
def queue_idle():
    q = get(COMFY + "/queue", 5); return len(q["queue_running"]) + len(q["queue_pending"]) == 0
def wait_idle(limit=2400):
    t0 = time.time()
    while time.time() - t0 < limit:
        try:
            if queue_idle(): return True
        except Exception: pass
        time.sleep(5)
    return False
ACTIVE = ("pending", "preparing", "waiting", "submitting", "queued", "running", "submitted", "partial")   # every pre-submit and in-flight Studio state
def studio_idle():
    jobs = get(STUDIO + "/api/jobs", 10); jobs = jobs.get("jobs", jobs) if isinstance(jobs, dict) else jobs
    if [j for j in jobs if j.get("status") in ACTIVE]: return False
    try: plans = get(STUDIO + "/api/production", 10); plans = plans.get("plans", plans) if isinstance(plans, dict) else plans
    except Exception: return False
    return not [p for p in (plans if isinstance(plans, list) else []) if isinstance(p, dict) and p.get("status") in ("queued", "running")]
def step_rate():
    tail = open(LOG, "rb").read()[-6000:].decode("utf-8", "replace").replace("\r", "\n")
    rates = re.findall(r"(\d+)/(\d+) \[(\d\d:\d\d)<[^\]]*, *([\d.]+)(s/it|it/s)\]", tail)
    done = [r for r in rates if r[0] == r[1]]
    return (done[-1][2], float(done[-1][3]), done[-1][4]) if done else None
def render(label, seed=2026091411):
    g = json.loads(json.dumps(GRAPH)); g["7"]["inputs"]["noise_seed"] = seed; g["13"]["inputs"]["filename_prefix"] = "Research/probe-speed-" + label
    req = urllib.request.Request(COMFY + "/prompt", json.dumps({"prompt": g}).encode(), {"Content-Type": "application/json"})
    pid = get_json(req)["prompt_id"]; t0 = time.time()
    while time.time() - t0 < 1800:
        time.sleep(5); h = get(COMFY + "/history/" + pid, 30)
        if pid in h:
            st = h[pid].get("status", {}); files = [o["filename"] for n in h[pid].get("outputs", {}).values() for o in n.get("images", [])]
            r = step_rate(); note(label=label, prompt_id=pid, status=st.get("status_str"), seconds=round(time.time() - t0, 1), files=files, steps=r[0] if r else None, rate=(str(r[1]) + " " + r[2]) if r else None)
            return r[1] if r and r[2] == "s/it" else (1 / r[1] if r else None)
    note(label=label, prompt_id=pid, status="timeout"); return None
def get_json(req): return json.load(urllib.request.urlopen(req, timeout=60))
def restart():
    if not (queue_idle() and studio_idle()): note(label="restart refused", reason="queue or Studio not idle"); return False
    r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-File", "C:/AI/Stop-ComfyUI.ps1"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    note(label="stop", rc=r.returncode, out=r.stdout[-300:], err=r.stderr[-300:]); t0 = time.time()
    while time.time() - t0 < 60 and comfy_process(): time.sleep(2)
    note(label="stopped", gone=comfy_process() is None, seconds=round(time.time() - t0, 1))
    t0 = time.time(); came_back = False
    while time.time() - t0 < 45:
        try: get(COMFY + "/system_stats", 3); came_back = True; break
        except Exception: time.sleep(3)
    note(label="self-relaunch check", relaunched_by_studio=came_back)
    if not came_back:
        r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-File", "C:/AI/Start-ComfyUI.ps1", "-NoBrowser"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=400)
        note(label="start", rc=r.returncode, out=r.stdout[-300:], err=r.stderr[-300:])
    for _ in range(120):
        try: get(COMFY + "/system_stats", 3); break
        except Exception: time.sleep(2)
    try: note(label="studio health after restart", recovery=get(STUDIO + "/api/health", 15).get("recovery"))
    except Exception as e: note(label="studio health after restart", error=str(e))
    return True
if __name__ == "__main__":
    note(label="waiting for the queue")
    if not wait_idle() or not studio_idle(): note(label="aborted", reason="the ComfyUI queue or the Studio never went idle; nothing freed, nothing submitted"); sys.exit(1)
    mem("idle before /free")
    urllib.request.urlopen(urllib.request.Request(COMFY + "/free", json.dumps({"unload_models": True, "free_memory": True}).encode(), {"Content-Type": "application/json"}), timeout=60).read()
    time.sleep(15); mem("after /free")
    rate = render("afterfree"); mem("after render 1")
    if rate is None or rate > 20:
        if restart():
            mem("after restart, idle"); rate2 = render("afterrestart"); mem("after render 2")
            if rate2 is not None and rate2 < 20: render("afterrestart-2", 2026091412); mem("after render 3")
    else: note(label="fast after /free; no restart")
    report["finished"] = time.strftime("%Y-%m-%d %H:%M:%S"); json.dump(report, open(OUT + "/restart_probe.json", "w"), indent=1); print("done", flush=True)
