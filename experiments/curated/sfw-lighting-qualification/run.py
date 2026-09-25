"""One deliberate Studio lighting comparison at a time; never retry an uncertain POST.

Usage: python run.py baseline|moderate|strong|baseline2|moderate2
Inspect results.json and the output after each invocation before advancing.
"""
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
STUDIO = "http://127.0.0.1:8191"
COMFY = "http://127.0.0.1:8188"
PROMPT = ("1woman, adult woman, mature face, original character, long dark auburn hair, amber eyes, "
          "high-collared dark green travelling coat, leather gloves, brass lantern in raised right hand, "
          "standing on a stone bridge over a night river, moonlit mist, dark, dim lighting, dark background, "
          "cowboy shot, fantasy, masterpiece, best quality, amazing quality")
NEGATIVE = "bad quality, worst quality, worst detail, sketch, censor, shiny skin, nsfw"
RUNS = {"baseline": 0.0, "moderate": 0.6, "strong": 1.0,
        "baseline2": 0.0, "moderate2": 0.6}
BUSY = {"queued", "running", "waiting", "submitting", "observing", "resumed"}


def request(url, payload=None):
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        headers["Origin"] = STUDIO
    data = None if payload is None else json.dumps(payload).encode()
    with urllib.request.urlopen(urllib.request.Request(url, data, headers), timeout=60) as response:
        return json.load(response)


def write(path, value):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def main(name):
    if name not in RUNS:
        raise SystemExit("Run must be baseline, moderate, strong, baseline2 or moderate2")
    result_path = HERE / (name + ".result.json")
    marker = HERE / (name + ".submission-started.json")
    if result_path.exists() or marker.exists():
        raise SystemExit("This run already has a result or uncertain submission; inspect it, do not resubmit")

    health = request(STUDIO + "/api/health")
    backend = request(STUDIO + "/api/backends")
    queue = request(COMFY + "/queue")
    jobs = request(STUDIO + "/api/jobs")
    if not health.get("online") or not health.get("worker_alive") or health.get("degraded"):
        raise SystemExit("Studio health is not ready")
    if backend.get("active") != "primary" or backend.get("busy") or backend.get("gpu_lease", {}).get("held"):
        raise SystemExit("Primary backend is not idle")
    if queue.get("queue_running") or queue.get("queue_pending") or any(j.get("status") in BUSY for j in jobs):
        raise SystemExit("A ComfyUI or Studio job is in flight")

    controls = {"positive": PROMPT, "negative": NEGATIVE, "width": 832, "height": 1216,
                "seed": 2026092502 if name.endswith("2") else 2026092501,
                "steps": 30, "cfg": 5.0, "denoise": 1.0,
                "sampler": "euler_ancestral", "scheduler": "normal", "lora": RUNS[name]}
    if RUNS[name]:
        controls["lora_name"] = "Dark_Illustrious_v1.safetensors"
    intent = {"preset_id": "wai", "controls": controls, "batch_count": 1,
              "references": [], "parent_assets": []}
    write(marker, {"name": name, "intent": intent, "started_at": time.time(),
                   "warning": "If POST response is lost, reconcile Studio jobs and ComfyUI history before any retry."})
    try:
        job = request(STUDIO + "/api/jobs", intent)
    except urllib.error.HTTPError as error:
        write(result_path, {"name": name, "status": "rejected", "http_status": error.code,
                            "error": error.read().decode("utf-8", "replace")[:2000]})
        marker.unlink()
        raise SystemExit("Studio rejected the request; see result JSON")
    # A network error leaves the marker in place. No automatic retry is safe.
    job_id = job["id"]
    write(marker, {"name": name, "intent": intent, "job_id": job_id, "started_at": time.time()})
    print(name, "job", job_id, flush=True)
    deadline = time.monotonic() + 1800
    while time.monotonic() < deadline:
        time.sleep(4)
        state = request(STUDIO + "/api/jobs/" + job_id)
        if state.get("status") in {"completed", "failed", "stopped", "abandoned", "uncertain"}:
            recipe_error = None
            try:
                recipe = request(STUDIO + "/api/jobs/" + job_id + "/recipe")
                write(HERE / (name + ".recipe.json"), recipe)
            except (OSError, ValueError) as error:
                recipe_error = f"{type(error).__name__}: {error}"
            result = {"name": name, "intent": intent, "job": state,
                      "observed_at": time.time()}
            if recipe_error:
                result["recipe_capture_error"] = recipe_error
            write(result_path, result)
            if recipe_error:
                print(name, "recipe capture failed; reconcile the saved job and marker",
                      file=sys.stderr, flush=True)
                return 1
            marker.unlink()
            print(name, state.get("status"), state.get("prompt_ids"), flush=True)
            return 0 if state.get("status") == "completed" else 1
    raise SystemExit("Job outcome unresolved; inspect saved marker and job ID, never resubmit blindly")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else ""))
