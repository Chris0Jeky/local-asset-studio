"""Local-only Asset Studio.  Run: python app/server.py --repo-root PATH"""
from __future__ import annotations

import argparse
import copy
import json
import math
import mimetypes
import re
import shutil
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import Queue
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

HOST, PORT = "127.0.0.1", 8191
IMAGE_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
CONTROL_KEYS = ("positive", "negative", "width", "height", "seed", "steps", "cfg", "denoise", "lora", "reference")

class StudioError(ValueError): pass

def read_json(path: Path, fallback=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback

def inside(root: Path, candidate: Path) -> Path:
    candidate = candidate.resolve()
    if root != candidate and root not in candidate.parents: raise StudioError("Path escapes the repository")
    return candidate

def number(value, name, lo, hi, integer=False):
    if isinstance(value, bool): raise StudioError(f"{name} must be a number")
    try: raw = float(value)
    except (ValueError, TypeError): raise StudioError(f"{name} must be a number")
    if not math.isfinite(raw) or (integer and not raw.is_integer()): raise StudioError(f"{name} must be a finite {'integer' if integer else 'number'}")
    # int(1.9) silently truncates, and float accepts nan/inf.  Neither makes a
    # safe workflow value.
    result = int(raw) if integer else raw
    if result < lo or result > hi: raise StudioError(f"{name} must be between {lo} and {hi}")
    return result

class Studio:
    def __init__(self, repo_root: Path):
        self.root = repo_root.resolve()
        self.catalog_path = inside(self.root, self.root / "presets/catalog.json")
        self.runs = self.root / "experiments/runs"; self.runs.mkdir(parents=True, exist_ok=True)
        self.config = read_json(self.root / "config/local.json", {}) or {}
        self.comfy_url = str(self.config.get("comfy_url", "http://127.0.0.1:8188")).rstrip("/")
        self.comfy_root = Path(self.config.get("comfy_root", "C:/AI/ComfyUI_windows_portable/ComfyUI")).resolve()
        self.jobs = {}; self.queue = Queue(); self.lock = threading.Lock()
        self._load_jobs()
        self.worker = threading.Thread(target=self._work, daemon=True, name="asset-studio-worker"); self.worker.start()

    def catalog(self):
        data = read_json(self.catalog_path)
        if not isinstance(data, dict) or not isinstance(data.get("presets"), list): raise StudioError("Invalid presets/catalog.json")
        # Expose the workflow's authored values as editable defaults.  This keeps
        # the catalog compact while never inventing a prompt in the browser.
        result = copy.deepcopy(data)
        for preset in result["presets"]:
            try:
                graph, _ = self.graph_for(preset); defaults = {}
                for key in CONTROL_KEYS:
                    binding = preset.get(key)
                    if binding: defaults[key] = graph[str(binding[0])]["inputs"].get(str(binding[1]), "")
                preset["defaults"] = defaults
            except (StudioError, KeyError, TypeError, IndexError):
                preset["defaults"] = {}
        return result

    def preset(self, preset_id):
        for p in self.catalog()["presets"]:
            if p.get("id") == preset_id: return p
        raise StudioError("Unknown preset")

    def graph_for(self, preset):
        graph = inside(self.root, self.root / str(preset.get("graph", "")))
        if graph.suffix != ".json" or not graph.is_file(): raise StudioError("Workflow graph is unavailable")
        data = read_json(graph)
        if not isinstance(data, dict): raise StudioError("Workflow graph is invalid")
        return data, graph

    def _bind(self, graph, binding, value):
        if not binding: return
        try: node, field = str(binding[0]), str(binding[1]); graph[node]["inputs"][field] = value
        except (IndexError, KeyError, TypeError): raise StudioError("Preset has an invalid workflow binding")

    def _bind_control(self, graph, preset, key, value):
        """Apply the primary binding plus catalogued companion bindings.

        The catalog is deliberately the allow-list: fixed scaler/export fields can
        never be changed merely because they happen to have the same field name.
        """
        self._bind(graph, preset.get(key), value)
        extras = (preset.get("bindings_extra") or {}).get(key, [])
        if not isinstance(extras, list): raise StudioError("Preset has invalid companion bindings")
        for binding in extras: self._bind(graph, binding, value)

    def prepare(self, payload):
        if not isinstance(payload, dict): raise StudioError("JSON object required")
        preset = self.preset(payload.get("preset_id")); graph, graph_path = self.graph_for(preset)
        controls = payload.get("controls", {})
        if not isinstance(controls, dict): raise StudioError("controls must be an object")
        supported = {k for k in CONTROL_KEYS if preset.get(k) or (preset.get("bindings_extra") or {}).get(k)}
        unknown = set(controls) - supported
        if unknown: raise StudioError("Unsupported controls: " + ", ".join(sorted(unknown)))
        for key in ("positive", "negative"):
            if key in controls:
                if not isinstance(controls[key], str) or len(controls[key]) > 8000: raise StudioError(f"{key} must be text up to 8000 characters")
                self._bind_control(graph, preset, key, controls[key])
        if "lora" in controls:
            binding = preset.get("lora") or ((preset.get("bindings_extra") or {}).get("lora") or [None])[0]
            try: existing = graph[str(binding[0])]["inputs"].get(str(binding[1]))
            except (KeyError, TypeError, IndexError): raise StudioError("Preset has an invalid workflow binding")
            value = number(controls["lora"], "lora", 0, 2) if isinstance(existing, (int, float)) else controls["lora"]
            if not isinstance(value, (int, float, str)) or (isinstance(value, str) and len(value) > 8000): raise StudioError("lora must be a number or short text")
            self._bind_control(graph, preset, "lora", value)
        for key, lo, hi, integer in (("seed", 0, 2**63-1, True), ("steps", 1, 150, True), ("cfg", 0, 30, False), ("denoise", 0, 1, False)):
            if key in controls: self._bind_control(graph, preset, key, number(controls[key], key, lo, hi, integer))
        dims = {}
        for key in ("width", "height"):
            if key in controls:
                dims[key] = number(controls[key], key, 64, 1536, True)
                if dims[key] % 8: raise StudioError(f"{key} must be a multiple of 8")
                self._bind_control(graph, preset, key, dims[key])
        if "reference" in controls:
            name = controls["reference"]
            if not isinstance(name, str) or name != Path(name).name or not re.fullmatch(r"[0-9a-f]{32}_[A-Za-z0-9._-]+\.(?:png|jpg|webp)", name): raise StudioError("Reference upload is invalid")
            uploads = self.root / "experiments/uploads"
            upload = inside(uploads.resolve(), uploads / name)
            if not upload.is_file(): raise StudioError("Reference upload is unavailable")
            self._bind_control(graph, preset, "reference", upload.name)
        batch = number(payload.get("batch_count", 1), "batch_count", 1, 4, True)
        return preset, graph, graph_path, controls, batch

    def create_job(self, payload):
        preset, graph, graph_path, controls, batch = self.prepare(payload)
        job_id = str(uuid.uuid4()); directory = self.runs / job_id; directory.mkdir()
        job = {"id": job_id, "status": "queued", "created_at": time.time(), "preset_id": preset["id"], "preset_name": preset.get("name", preset["id"]), "controls": controls, "batch_count": batch, "prompt_ids": [], "submissions": [], "outputs": [], "message": "Waiting for the local generation queue", "graph_path": str(graph_path.relative_to(self.root)), "graph": graph}
        self._save(job); self.jobs[job_id] = job; self.queue.put(("generate", job_id))
        return self.public(job)

    def public(self, job):
        allowed = ("id", "status", "created_at", "preset_id", "preset_name", "controls", "batch_count", "prompt_ids", "submissions", "outputs", "message")
        return {k: job.get(k) for k in allowed}

    def _write_json_atomic(self, path, value):
        temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
        temp.write_text(json.dumps(value, indent=2), encoding="utf-8")
        temp.replace(path)

    def _save(self, job):
        directory = self.runs / job["id"]
        recipe = {"preset_id": job["preset_id"], "controls": job["controls"], "batch_count": job["batch_count"], "graph_path": job["graph_path"], "created_at": job["created_at"]}
        self._write_json_atomic(directory / "recipe.json", recipe)
        self._write_json_atomic(directory / "workflow.json", job["graph"])
        state = {k:v for k,v in job.items() if k != "graph"}; self._write_json_atomic(directory / "state.json", state)

    def _load_jobs(self):
        for state_path in self.runs.glob("*/state.json"):
            data = read_json(state_path)
            graph = read_json(state_path.parent / "workflow.json")
            if isinstance(data, dict) and isinstance(graph, dict) and data.get("id"):
                data["graph"] = graph
                if data.get("status") in ("queued", "submitting", "running"):
                    data["status"] = "uncertain"; data["message"] = "Restarted while remote job state was unknown; use Resume observation for known prompt IDs. It was not resubmitted."
                    self._save(data)
                self.jobs[data["id"]] = data

    def _request(self, path, method="GET", data=None, timeout=15):
        body = json.dumps(data).encode() if data is not None else None
        req = Request(self.comfy_url + path, data=body, method=method, headers={"Content-Type": "application/json"} if body else {})
        with urlopen(req, timeout=timeout) as response: return json.loads(response.read().decode())

    def health(self):
        try:
            self._request("/system_stats", timeout=3)
            try: info = self._request("/object_info", timeout=8); info_available = isinstance(info, dict)
            except (URLError, HTTPError, TimeoutError, OSError, json.JSONDecodeError): info, info_available = {}, False
            missing = {}
            for preset in self.catalog()["presets"]:
                try:
                    graph, _ = self.graph_for(preset)
                    for node in graph.values():
                        class_info = info.get(node.get("class_type"), {})
                        if info_available and node.get("class_type") not in info:
                            missing.setdefault(preset.get("id"), []).append(f"node class {node.get('class_type')}")
                            continue
                        options = (class_info.get("input", {}).get("required", {}) | class_info.get("input", {}).get("optional", {}))
                        for field, value in node.get("inputs", {}).items():
                            choice = options.get(field)
                            if field.endswith("_name") and isinstance(value, str) and isinstance(choice, list) and choice and isinstance(choice[0], list) and value not in choice[0]:
                                missing.setdefault(preset.get("id"), []).append(value)
                except (StudioError, AttributeError, TypeError): pass
            return {"app": "local-asset-studio", "online": True, "missing_models": missing}
        except (URLError, HTTPError, TimeoutError, OSError, json.JSONDecodeError): return {"app": "local-asset-studio", "online": False, "missing_models": {}}

    def _wait_for_queue(self):
        while True:
            data = self._request("/queue", timeout=10)
            if not data.get("queue_running") and not data.get("queue_pending"): return
            time.sleep(2)

    def _work(self):
        while True:
            action, job_id = self.queue.get()
            job = self.jobs.get(job_id)
            if not job: continue
            try:
                self._resume(job) if action == "observe" else self._run(job)
            except Exception as exc:
                job["status"] = "failed"; job["message"] = f"Generation failed: {str(exc)[:300]}"; self._save(job)

    def _batch_graph(self, job, index):
        graph = copy.deepcopy(job["graph"]); preset = self.preset(job["preset_id"])
        binding = preset.get("seed") or ((preset.get("bindings_extra") or {}).get("seed") or [None])[0]
        if not binding: return graph, None
        try: base = graph[str(binding[0])]["inputs"][str(binding[1])]
        except (KeyError, TypeError, IndexError): raise StudioError("Preset has an invalid seed binding")
        seed = number(base, "seed", 0, 2**63 - 1, True) + index
        if seed > 2**63 - 1: raise StudioError("seed plus batch count exceeds supported range")
        self._bind_control(graph, preset, "seed", seed)
        return graph, seed

    def _run(self, job):
        job["status"] = "waiting"; job["message"] = "Waiting for existing ComfyUI work"; self._save(job)
        self._wait_for_queue()
        for i in range(job["batch_count"]):
            graph, seed = self._batch_graph(job, i)
            job["status"] = "submitting"; job["message"] = f"Submitting image {i + 1} of {job['batch_count']}"; job["pending_submission"] = {"index": i, "seed": seed, "graph": graph, "marked_at": time.time()}; self._save(job)
            try: response = self._request("/prompt", "POST", {"prompt": graph, "client_id": "asset-studio"}, timeout=30)
            except (URLError, HTTPError, TimeoutError, OSError) as exc:
                job["status"] = "uncertain"; job["message"] = "Submission outcome is uncertain and will not be retried automatically."; self._save(job); return
            prompt_id = response.get("prompt_id")
            if not isinstance(prompt_id, str): raise StudioError("ComfyUI did not return a prompt id")
            submission = {"index": i, "prompt_id": prompt_id, "seed": seed, "graph": graph, "status": "observing"}
            job["prompt_ids"].append(prompt_id); job.setdefault("submissions", []).append(submission); job.pop("pending_submission", None); job["status"] = "running"; job["message"] = f"Generating image {i + 1} of {job['batch_count']}"; self._save(job)
            if not self._wait_history(job, submission): return
        job["status"] = "completed"; job["message"] = "Complete"; self._save(job)

    def _wait_history(self, job, submission):
        prompt_id = submission["prompt_id"]
        for _ in range(720):
            try: history = self._request("/history/" + prompt_id, timeout=15).get(prompt_id)
            except (URLError, HTTPError, TimeoutError, OSError, json.JSONDecodeError):
                job["status"] = "uncertain"; job["message"] = "Could not observe a known ComfyUI prompt. Use Resume observation when ComfyUI is available."; self._save(job); return False
            if history:
                status = history.get("status", {})
                if status.get("status_str") == "error": raise StudioError("ComfyUI reported an execution error")
                outputs = history.get("outputs", {})
                for node in outputs.values():
                    for image in node.get("images", []):
                        descriptor = {k: image.get(k) for k in ("filename", "subfolder", "type")}
                        if descriptor["filename"]: descriptor["seed"] = submission.get("seed"); descriptor["prompt_id"] = prompt_id; job["outputs"].append(descriptor)
                submission["status"] = "completed"; self._save(job); return True
            time.sleep(2)
        job["status"] = "uncertain"; job["message"] = "Timed out while observing ComfyUI; it was not resubmitted."; self._save(job)
        return False

    def resume_job(self, job_id):
        job = self.jobs.get(job_id)
        if not job: raise StudioError("Unknown job")
        pending = [s for s in job.get("submissions", []) if s.get("status") != "completed" and s.get("prompt_id")]
        if not pending: raise StudioError("No known prompt IDs are available to resume")
        job["status"] = "queued"; job["message"] = "Queued to resume observation; no image will be resubmitted."; self._save(job); self.queue.put(("observe", job_id)); return self.public(job)

    def _resume(self, job):
        job["status"] = "running"; job["message"] = "Resuming observation of known ComfyUI prompt IDs"; self._save(job)
        for submission in job.get("submissions", []):
            if submission.get("status") != "completed" and not self._wait_history(job, submission): return
        observed = len(job.get("submissions", []))
        if observed < job["batch_count"]:
            job["status"] = "partial"
            job["message"] = f"Observed {observed} of {job['batch_count']} requested images. Remaining images were not submitted; start a new job for those."
        else:
            job["status"] = "completed"; job["message"] = "Complete"
        self._save(job)

    def upload(self, filename, content_type, body):
        mime = content_type.split(";", 1)[0].lower()
        magic = {"image/png": b"\x89PNG\r\n\x1a\n", "image/jpeg": b"\xff\xd8\xff", "image/webp": b"RIFF"}
        if mime not in IMAGE_TYPES or len(body) > 20 * 1024 * 1024 or not body or not body.startswith(magic[mime]): raise StudioError("Upload must be a PNG, JPG, or WebP under 20 MiB")
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", Path(filename or "reference").name)[:100]
        if not safe or safe in (".", ".."): raise StudioError("Invalid upload filename")
        # ComfyUI only receives this generated basename; client paths are never used.
        uploads = self.root / "experiments/uploads"; uploads.mkdir(parents=True, exist_ok=True)
        name = f"{uuid.uuid4().hex}_{safe}{IMAGE_TYPES[mime]}"
        path = uploads / name; path.write_bytes(body)
        comfy_input = self.comfy_root / "input"
        if not comfy_input.is_dir():
            path.unlink(missing_ok=True)
            raise StudioError("Configured ComfyUI input folder is unavailable")
        shutil.copyfile(path, comfy_input / name)
        return {"file": name}

class Handler(BaseHTTPRequestHandler):
    studio: Studio = None
    def log_message(self, fmt, *args): pass
    def _json(self, status, obj):
        raw = json.dumps(obj).encode(); self.send_response(status); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def _safe_host(self):
        return self.headers.get("Host", "") in ("127.0.0.1:8191", "localhost:8191")
    def _safe_mutation(self):
        if not self._safe_host(): return False
        origin = self.headers.get("Origin")
        parsed = urlparse(origin or "")
        return parsed.scheme == "http" and parsed.netloc in ("127.0.0.1:8191", "localhost:8191") and not parsed.username and not parsed.password
    def _content_length(self, limit):
        try: size = int(self.headers.get("Content-Length", ""))
        except ValueError: raise StudioError("Valid Content-Length required")
        if size < 0 or size > limit: raise StudioError("Request body is too large")
        return size
    def _body_json(self):
        if self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json": raise StudioError("application/json required")
        return json.loads(self.rfile.read(self._content_length(1024 * 1024)).decode())
    def do_GET(self):
        if not self._safe_host(): return self._json(403, {"error":"Loopback Host required"})
        try:
            path = urlparse(self.path).path
            if path == "/api/catalog": return self._json(200, self.studio.catalog())
            if path.startswith("/api/workflows/"):
                preset = self.studio.preset(path.rsplit("/", 1)[-1]); _, workflow = self.studio.graph_for(preset)
                data = workflow.read_bytes(); self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Disposition", f'attachment; filename="{preset["id"]}-api.json"'); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data); return
            if path == "/api/health": return self._json(200, self.studio.health())
            if path == "/api/jobs": return self._json(200, [self.studio.public(x) for x in sorted(self.studio.jobs.values(), key=lambda j:j["created_at"], reverse=True)])
            if path.startswith("/api/jobs/") and path.endswith("/recipe"):
                job = self.studio.jobs.get(path.split("/")[3]); return self._json(200, read_json(self.studio.runs / job["id"] / "recipe.json")) if job else self._json(404, {"error":"Unknown job"})
            if path.startswith("/api/jobs/"):
                job = self.studio.jobs.get(path.rsplit("/", 1)[-1]); return self._json(200, self.studio.public(job)) if job else self._json(404, {"error":"Unknown job"})
            if path.startswith("/api/image/"):
                _, _, _, job_id, index = path.split("/"); job = self.studio.jobs.get(job_id); image = job and job.get("outputs", [])[int(index)]
                if not image: return self._json(404, {"error":"Unknown image"})
                query = urlencode({k:v for k,v in image.items() if v is not None})
                with urlopen(self.studio.comfy_url + "/view?" + query, timeout=20) as resp:
                    data = resp.read(); self.send_response(200); self.send_header("Content-Type", resp.headers.get_content_type()); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
                return
            if path == "/": path = "/index.html"
            if path.startswith("/static/"): path = path[7:]
            file = inside(Path(__file__).parent / "static", Path(__file__).parent / "static" / path.lstrip("/"))
            if not file.is_file() or file.suffix not in (".html", ".js", ".css"): return self._json(404, {"error":"Not found"})
            data = file.read_bytes(); self.send_response(200); self.send_header("Content-Type", mimetypes.guess_type(str(file))[0] or "application/octet-stream"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
        except (StudioError, ValueError, IndexError) as exc: self._json(400, {"error": str(exc)})
        except (URLError, HTTPError, OSError) as exc: self._json(502, {"error": "ComfyUI image is unavailable"})
    def do_POST(self):
        if not self._safe_mutation(): return self._json(403, {"error":"Local same-origin request required"})
        try:
            if self.path == "/api/jobs": return self._json(201, self.studio.create_job(self._body_json()))
            if self.path.startswith("/api/jobs/") and self.path.endswith("/resume"):
                self._body_json(); return self._json(202, self.studio.resume_job(self.path.split("/")[3]))
            if self.path == "/api/upload":
                size = self._content_length(20 * 1024 * 1024); return self._json(201, self.studio.upload(self.headers.get("X-Filename", "reference"), self.headers.get("Content-Type", ""), self.rfile.read(size)))
            return self._json(404, {"error":"Not found"})
        except (StudioError, ValueError, json.JSONDecodeError) as exc: self._json(400, {"error": str(exc)})

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--repo-root", "--root", dest="repo_root", default=str(Path(__file__).parents[1])); args = parser.parse_args()
    Handler.studio = Studio(Path(args.repo_root)); ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
if __name__ == "__main__": main()
