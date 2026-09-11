"""Local-only Asset Studio.  Run: python app/server.py --repo-root PATH"""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import math
import mimetypes
import re
import shutil
import sys
import threading
import time
import uuid
import zipfile
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import Queue
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

# The portable Python includes ComfyUI's own `app` package in its search path.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_library import ModelLibrary
from workspace import AssetWorkspace, WorkspaceError, digest_file
from references import compile_references, image_record

HOST, PORT = "127.0.0.1", 8191
IMAGE_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
CONTROL_KEYS = ("positive", "negative", "width", "height", "seed", "steps", "cfg", "denoise", "lora", "reference", "last_reference", "frames", "fps", "sampler", "scheduler")

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
    try: raw = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError): raise StudioError(f"{name} must be a number")
    if not raw.is_finite() or (integer and raw != raw.to_integral_value()): raise StudioError(f"{name} must be a finite {'integer' if integer else 'number'}")
    # int(1.9) silently truncates, and float accepts nan/inf.  Neither makes a
    # safe workflow value.
    if raw < lo or raw > hi: raise StudioError(f"{name} must be between {lo} and {hi}")
    result = int(raw) if integer else float(raw)
    return result

class Studio:
    def __init__(self, repo_root: Path):
        self.root = repo_root.resolve()
        self.catalog_path = inside(self.root, self.root / "presets/catalog.json")
        self.config = read_json(self.root / "config/local.json", {}) or {}
        self.experiments = Path(self.config.get("experiments_root", self.root / "experiments")).resolve()
        self.runs = self.experiments / "runs"; self.runs.mkdir(parents=True, exist_ok=True)
        self.comfy_url = str(self.config.get("comfy_url", "http://127.0.0.1:8188")).rstrip("/")
        self.comfy_root = Path(self.config.get("comfy_root", "C:/AI/ComfyUI_windows_portable/ComfyUI")).resolve()
        self.library = ModelLibrary(self.root, self.comfy_root)
        self.assets = AssetWorkspace(self.experiments)
        self._schema_lock = threading.Lock()
        self._schema = None; self._schema_at = 0
        self.jobs = {}; self.queue = Queue(); self.lock = threading.Lock()
        self._load_jobs()
        for job in self.jobs.values(): self.index_outputs(job)
        self.worker = threading.Thread(target=self._work, daemon=True, name="asset-studio-worker"); self.worker.start()

    def catalog(self):
        data = read_json(self.catalog_path)
        if not isinstance(data, dict) or not isinstance(data.get("presets"), list): raise StudioError("Invalid presets/catalog.json")
        # Expose the workflow's authored values as editable defaults.  This keeps
        # the catalog compact while never inventing a prompt in the browser.
        result = copy.deepcopy(data)
        for preset in result["presets"]:
            preset["runtime_block"] = self.config.get("runtime_blocks", {}).get(preset.get("family"))
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
        if preset.get("runtime_block"): raise StudioError(preset["runtime_block"])
        expected = payload.get("expected_template_sha256")
        if expected and expected != hashlib.sha256(graph_path.read_bytes()).hexdigest():
            raise StudioError("The preset changed since this recipe was imported. Re-import it or deliberately select the current preset.")
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
        for key, lo, hi in (("frames", 5, 365), ("fps", 1, 60)):
            if key in controls:
                value = number(controls[key], key, lo, hi, True)
                grid = preset.get("frame_grid", 1)
                offset = preset.get("frame_offset", 0)
                if key == "frames" and (value - offset) % grid:
                    raise StudioError(f"frames must follow {grid}k + {offset}; use the suggested durations")
                self._bind_control(graph, preset, key, value)
        for key in ("sampler", "scheduler"):
            if key in controls:
                if controls[key] not in preset.get("choices", {}).get(key, []): raise StudioError(f"Unsupported {key}")
                self._bind_control(graph, preset, key, controls[key])
        dims = {}
        for key in ("width", "height"):
            if key in controls:
                dims[key] = number(controls[key], key, 64, 1536, True)
                multiple = preset.get("dimension_multiple", 8)
                if dims[key] % multiple: raise StudioError(f"{key} must be a multiple of {multiple}")
                self._bind_control(graph, preset, key, dims[key])
        for key in ("reference", "last_reference"):
            if key not in controls: continue
            name = controls[key]
            if not isinstance(name, str) or name != Path(name).name or not re.fullmatch(r"[0-9a-f]{32}_[A-Za-z0-9._-]+\.(?:png|jpg|webp)", name): raise StudioError("Reference upload is invalid")
            uploads = self.experiments / "uploads"
            upload = inside(uploads.resolve(), uploads / name)
            if not upload.is_file(): raise StudioError("Reference upload is unavailable")
            self._bind_control(graph, preset, key, upload.name)
        if preset.get("max_pixels"):
            actual = {key: graph[str(preset[key][0])]["inputs"][str(preset[key][1])] for key in ("width", "height")}
            if actual["width"] * actual["height"] > preset["max_pixels"]: raise StudioError("Resolution exceeds this workflow's pixel budget")
        if preset.get("reference_slots"):
            preset["_prepared_references"] = compile_references(preset, graph, payload.get("references"), self.experiments / "uploads")
        elif payload.get("references"):
            raise StudioError("This recipe has no role-assigned reference slots; choose a Qwen Atelier recipe")
        batch = number(payload.get("batch_count", 1), "batch_count", 1, 4, True)
        return preset, graph, graph_path, controls, batch

    def create_job(self, payload):
        preset, graph, graph_path, controls, batch = self.prepare(payload)
        parents = payload.get("parent_assets", [])
        if not isinstance(parents, list) or len(parents) > 8: raise StudioError("Use up to eight parent assets")
        for parent in parents: self.assets.get(parent)
        job_id = str(uuid.uuid4()); directory = self.runs / job_id; directory.mkdir()
        job = {"id": job_id, "status": "queued", "created_at": time.time(), "preset_id": preset["id"], "preset_name": preset.get("name", preset["id"]), "controls": controls, "batch_count": batch, "prompt_ids": [], "submissions": [], "outputs": [], "message": "Waiting for the local generation queue", "graph_path": str(graph_path.relative_to(self.root)), "graph": graph}
        job["seed_bindings"] = ([preset["seed"]] if preset.get("seed") else []) + preset.get("bindings_extra", {}).get("seed", [])
        job["parent_assets"] = parents
        job["references"] = preset.get("_prepared_references", [])
        job["comfy_root"] = str(self.comfy_root); job["comfy_url"] = self.comfy_url
        self._save(job); self.jobs[job_id] = job; self.queue.put(("generate", job_id))
        return self.public(job)

    def public(self, job):
        allowed = ("id", "status", "created_at", "preset_id", "preset_name", "controls", "batch_count", "prompt_ids", "submissions", "outputs", "message", "parent_assets", "references")
        result = {k: job.get(k) for k in allowed}
        # Polling the gallery should not transfer every full graph every four seconds.
        result["submissions"] = [{k: v for k, v in s.items() if k != "graph"} for s in job.get("submissions", [])]
        return result

    def export_recipe(self, job):
        return {"version": 2, "preset_id": job["preset_id"], "controls": job["controls"],
                "batch_count": job["batch_count"], "created_at": job["created_at"],
                "workflow": job["graph"], "submissions": job.get("submissions", []),
                "outputs": job.get("outputs", []), "parent_assets": job.get("parent_assets", []), "references": job.get("references", [])}

    def output_path(self, output, job=None):
        root = Path((job or {}).get("comfy_root", self.comfy_root)).resolve()
        kind = output.get("type", "output")
        if kind not in ("output", "temp"): raise StudioError("Unsupported output location")
        return inside(root / kind, root / kind / str(output.get("subfolder") or "") / str(output.get("filename") or ""))

    def index_outputs(self, job):
        for index, output in enumerate(job.get("outputs", [])):
            try:
                asset_id = self.assets.register(job, index, self.output_path(output, job))
                if asset_id: output["asset_id"] = asset_id
            except (OSError, ValueError) as exc:
                output["snapshot_error"] = str(exc)[:200]

    def asset_reference(self, asset_id):
        asset = self.assets.get(asset_id)
        if asset["media_type"] != "image": raise StudioError("Choose an image as the reference")
        source = self.assets.file(asset_id)
        result = self.upload(asset["filename"], mimetypes.guess_type(str(source))[0] or "", source.read_bytes())
        result["parent_asset"] = asset_id
        return result

    def export_assets(self, payload):
        ids = payload.get("ids")
        if not isinstance(ids, list) or not 1 <= len(ids) <= 200: raise StudioError("Select 1–200 assets to export")
        assets = [self.assets.get(i) for i in dict.fromkeys(ids)]
        if any(a["trashed_at"] for a in assets): raise StudioError("Restore trashed assets before exporting")
        total = sum(a["bytes"] for a in assets)
        if shutil.disk_usage(self.experiments).free - total < 2 * 1024**3: raise StudioError("Export needs more free disk space")
        directory = self.assets.root / "exports"; directory.mkdir(exist_ok=True)
        identifier = uuid.uuid4().hex
        target = directory / (identifier + ".zip")
        temporary = target.with_suffix(".part")
        try:
            with zipfile.ZipFile(temporary, "x", compression=zipfile.ZIP_STORED) as archive:
                for asset in assets:
                    source = self.assets.file(asset["id"])
                    if digest_file(source) != asset["sha256"]: raise StudioError("An asset changed; export stopped")
                    archive.write(source, "assets/" + asset["id"] + source.suffix)
                    job = self.jobs.get(asset["job_id"])
                    if job:
                        archive.writestr("recipes/" + asset["id"] + ".json", json.dumps(self.export_recipe(job), indent=2))
                archive.writestr("manifest.json", json.dumps({"version": 1, "assets": assets, "created_at": time.time(), "note": "Review states are creative selections, not model-license or engine acceptance."}, indent=2))
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        return {"id": identifier, "url": "/api/exports/" + identifier, "count": len(assets)}

    def check_recipe(self, recipe):
        if not isinstance(recipe, dict) or not isinstance(recipe.get("workflow"), dict):
            raise StudioError("This older recipe has no embedded workflow. Load its settings as a saved setup, or open its original workflow in ComfyUI.")
        _, graph, path, _, _ = self.prepare(recipe)
        if graph != recipe["workflow"]:
            raise StudioError("The exported workflow differs from the current preset. Nothing was loaded or queued. Open the embedded workflow in ComfyUI, or select the current preset to start a new experiment.")
        return {"matches": True, "template_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def preview(self, payload):
        preset, graph, graph_path, controls, batch = self.prepare(payload)
        return {"preset_id":preset["id"], "workflow":graph, "references":preset.get("_prepared_references", []),
                "batch_count":batch, "template_sha256":hashlib.sha256(graph_path.read_bytes()).hexdigest(),
                "submitted":False}

    def reference_status(self, payload):
        names=payload.get("files", [])
        if not isinstance(names,list) or len(names)>8: raise StudioError("Use up to eight reference files")
        records=[]
        for name in names:
            if not isinstance(name,str) or name!=Path(name).name: raise StudioError("Invalid reference filename")
            try: records.append(dict(image_record(self.experiments/'uploads',name), available=True))
            except (ValueError,OSError): records.append({"file":name,"available":False})
        return records

    def _write_json_atomic(self, path, value):
        temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
        temp.write_text(json.dumps(value, indent=2), encoding="utf-8")
        temp.replace(path)

    def _save(self, job):
        directory = self.runs / job["id"]
        recipe = {"preset_id": job["preset_id"], "controls": job["controls"], "batch_count": job["batch_count"], "graph_path": job["graph_path"], "created_at": job["created_at"]}
        recipe.update(references=job.get("references", []), parent_assets=job.get("parent_assets", []))
        self._write_json_atomic(directory / "recipe.json", recipe)
        self._write_json_atomic(directory / "workflow.json", job["graph"])
        state = {k:v for k,v in job.items() if k != "graph"}; self._write_json_atomic(directory / "state.json", state)

    def _load_jobs(self):
        for state_path in self.runs.glob("*/state.json"):
            data = read_json(state_path)
            graph = read_json(state_path.parent / "workflow.json")
            if isinstance(data, dict) and isinstance(graph, dict) and data.get("id"):
                data["graph"] = graph
                if data.get("status") in ("queued", "waiting", "submitting", "running"):
                    data["status"] = "uncertain"; data["message"] = "Restarted while remote job state was unknown; use Resume observation for known prompt IDs. It was not resubmitted."
                    self._save(data)
                self.jobs[data["id"]] = data

    def _request(self, path, method="GET", data=None, timeout=15):
        body = json.dumps(data).encode() if data is not None else None
        req = Request(self.comfy_url + path, data=body, method=method, headers={"Content-Type": "application/json"} if body else {})
        with urlopen(req, timeout=timeout) as response: return json.loads(response.read().decode())

    def identity(self):
        return {"app": "local-asset-studio", "workspace": str(self.root), "version": "production-workspace-1"}

    def node_info(self, refresh=False):
        with self._schema_lock:
            if refresh or self._schema is None or time.monotonic() - self._schema_at > 120:
                info = self._request("/object_info", timeout=8)
                if not isinstance(info, dict): raise StudioError("Invalid ComfyUI node schema")
                self._schema = info; self._schema_at = time.monotonic()
            return self._schema

    def health(self, refresh=False):
        try:
            stats = self._request("/system_stats", timeout=3)
            try: info = self.node_info(refresh); info_available = isinstance(info, dict)
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
                            enum = choice[0] if isinstance(choice, list) and choice and isinstance(choice[0], list) else choice[1].get("options") if isinstance(choice, list) and len(choice) > 1 and isinstance(choice[1], dict) and choice[0] == "COMBO" else None
                            if field.endswith("_name") and isinstance(value, str) and isinstance(enum, list) and value not in enum:
                                missing.setdefault(preset.get("id"), []).append(value)
                except (StudioError, AttributeError, TypeError): pass
            return {"app": "local-asset-studio", "workspace": str(self.root), "online": True, "schema_available": info_available, "missing_models": missing, "system": stats.get("system", {}), "devices": stats.get("devices", []), "comfy_url": self.comfy_url}
        except (URLError, HTTPError, TimeoutError, OSError, json.JSONDecodeError): return {"app": "local-asset-studio", "workspace": str(self.root), "online": False, "missing_models": {}}

    def inspect_preset(self, preset_id):
        preset = self.preset(preset_id); graph, _ = self.graph_for(preset)
        known = {Path(a["file"]).name: a for a in self.library.manifest().get("assets", [])}
        folders = {"ckpt_name": "checkpoints", "unet_name": "diffusion_models", "clip_name": "text_encoders", "vae_name": "vae", "lora_name": "loras", "control_net_name": "controlnet", "clip_vision_name": "clip_vision"}
        requirements = []
        for node in graph.values():
            for field, value in node.get("inputs", {}).items():
                if not isinstance(value, str) or Path(value).suffix.lower() not in (".safetensors", ".gguf", ".pth", ".pt", ".onnx"): continue
                asset = known.get(Path(value).name, {})
                folder = folders.get(field, "upscale_models" if node.get("class_type") == "UpscaleModelLoader" else "ultralytics" if node.get("class_type") == "UltralyticsDetectorProvider" else "models")
                relative = asset.get("file", folder + "/" + value)
                path = self.library.models / relative
                if relative not in [r["file"] for r in requirements]: requirements.append({"file": relative, "path": str(path), "present": path.is_file(), "asset_id": asset.get("id"), "source": asset.get("source"), "folder": folder})
        return {"id": preset_id, "requirements": requirements, "nodes": [{"id": key, "type": node.get("class_type")} for key, node in graph.items()], "graph": graph}

    def inspect_workflow(self, payload):
        data = payload.get("workflow") if isinstance(payload, dict) else None
        if not isinstance(data, dict): raise StudioError("A ComfyUI JSON object is required")
        classes, models, aliases = [], set(), set()
        visual = isinstance(data.get("nodes"), list)
        groups = [data]
        if visual:
            groups += data.get("definitions", {}).get("subgraphs", [])
            aliases = {g.get("id") for g in groups if isinstance(g, dict)}
        def filenames(value, depth=0):
            if depth > 25: raise StudioError("Workflow nesting is too deep")
            if isinstance(value, str) and value.lower().endswith((".safetensors", ".gguf", ".pt", ".pth", ".onnx")):
                models.add(value.replace("\\", "/"))
            elif isinstance(value, list):
                for item in value: filenames(item, depth + 1)
            elif isinstance(value, dict):
                for item in value.values(): filenames(item, depth + 1)
        for group in groups:
            if not isinstance(group, dict): raise StudioError("Invalid workflow subgraph")
            nodes = group.get("nodes", []) if visual else group.values()
            for item in nodes:
                if not isinstance(item, dict): continue
                kind = item.get("type") if visual else item.get("class_type")
                if not isinstance(kind, str): continue
                classes.append(kind)
                if len(classes) > 2000: raise StudioError("Workflow exceeds 2000 nodes")
                filenames(item.get("widgets_values", []) if visual else item.get("inputs", {}))
        if not classes: raise StudioError("No ComfyUI nodes found")
        try: info = self.node_info(); available = True
        except (URLError, OSError, ValueError): info = {}; available = False
        ui_only = {"Note", "MarkdownNote", "Reroute", "PrimitiveNode", "PrimitiveBoolean", "PrimitiveFloat", "PrimitiveInt"}
        missing_nodes = sorted(set(classes) - set(info) - aliases - ui_only) if available else []
        inventory = self.library.snapshot()["inventory"]
        names = {m["file"].split("/", 1)[-1] for m in inventory} | {Path(m["file"]).name for m in inventory}
        return {"format": "Visual workflow" if visual else "API graph", "node_count": len(classes), "missing_nodes": missing_nodes,
                "models": sorted(models), "missing_models": sorted(m for m in models if m not in names), "schema_available": available,
                "note": "Static dependency inspection only. No graph was run or code installed. Bypassed nodes are included; filenames selected dynamically may be absent." if available else "ComfyUI is offline: missing node status is unknown. Model filenames were inspected locally; nothing was run."}

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
        graph = copy.deepcopy(job["graph"])
        bindings = job.get("seed_bindings")
        if bindings is None:
            preset = self.preset(job["preset_id"])
            bindings = ([preset["seed"]] if preset.get("seed") else []) + preset.get("bindings_extra", {}).get("seed", [])
        binding = bindings[0] if bindings else None
        if not binding: return graph, None
        try: base = graph[str(binding[0])]["inputs"][str(binding[1])]
        except (KeyError, TypeError, IndexError): raise StudioError("Preset has an invalid seed binding")
        seed = number(base, "seed", 0, 2**63 - 1, True) + index
        if seed > 2**63 - 1: raise StudioError("seed plus batch count exceeds supported range")
        for bound in bindings: self._bind(graph, bound, seed)
        return graph, seed

    def _run(self, job):
        job["status"] = "waiting"; job["message"] = "Waiting for existing ComfyUI work"; self._save(job)
        self._wait_for_queue()
        for i in range(job["batch_count"]):
            graph, seed = self._batch_graph(job, i)
            job["status"] = "submitting"; job["message"] = f"Submitting output {i + 1} of {job['batch_count']}"; job["pending_submission"] = {"index": i, "seed": seed, "graph": graph, "marked_at": time.time()}; self._save(job)
            try: response = self._request("/prompt", "POST", {"prompt": graph, "client_id": "asset-studio"}, timeout=30)
            except HTTPError as exc:
                if exc.code == 400:
                    try: details = json.loads(exc.read(65536))
                    except (ValueError, OSError): details = {}
                    job.pop("pending_submission", None)
                    job["status"] = "failed"
                    job["validation_errors"] = details.get("node_errors", {})
                    error = details.get("error", {})
                    detail = error.get("message", "Invalid workflow") if isinstance(error, dict) else str(error)
                    job["message"] = "ComfyUI rejected the workflow before queuing: " + detail[:400]
                    self._save(job); return
                job["status"] = "uncertain"; job["message"] = "Submission outcome is uncertain and will not be retried automatically."; self._save(job); return
            except (URLError, TimeoutError, OSError) as exc:
                job["status"] = "uncertain"; job["message"] = "Submission outcome is uncertain and will not be retried automatically."; self._save(job); return
            prompt_id = response.get("prompt_id")
            if not isinstance(prompt_id, str): raise StudioError("ComfyUI did not return a prompt id")
            submission = {"index": i, "prompt_id": prompt_id, "seed": seed, "graph": graph, "status": "observing"}
            job["prompt_ids"].append(prompt_id); job.setdefault("submissions", []).append(submission); job.pop("pending_submission", None); job["status"] = "running"; job["message"] = f"Generating output {i + 1} of {job['batch_count']}"; self._save(job)
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
                if status.get("status_str") == "error":
                    errors = [m[1] for m in status.get("messages", []) if isinstance(m, list) and len(m) > 1 and m[0] == "execution_error" and isinstance(m[1], dict)]
                    detail = errors[-1] if errors else {}
                    submission["status"] = "failed"
                    detail_text = f"{detail.get('node_type', '')}: {detail.get('exception_message', '')}".strip(': ')
                    raise StudioError("ComfyUI reported an execution error" + (": " + detail_text[:450] if detail_text else ""))
                outputs = history.get("outputs", {})
                for node in outputs.values():
                    for collection in ("images", "gifs", "videos", "audio", "3d"):
                        for output in node.get(collection, []):
                            if not isinstance(output, dict): continue
                            descriptor = {k: output.get(k) for k in ("filename", "subfolder", "type")}
                            if descriptor["filename"]:
                                ext = Path(descriptor["filename"]).suffix.lower()
                                descriptor.update(seed=submission.get("seed"), prompt_id=prompt_id,
                                                  media_type="video" if ext in (".mp4", ".webm", ".mov") else "3d" if ext in (".glb", ".gltf", ".obj", ".ply", ".stl") else "audio" if ext in (".mp3", ".wav", ".flac") else "image")
                                if not any(o.get("filename") == descriptor["filename"] and o.get("subfolder") == descriptor["subfolder"] and o.get("prompt_id") == prompt_id for o in job["outputs"]): job["outputs"].append(descriptor)
                submission["status"] = "completed"; self.index_outputs(job); self._save(job); return True
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
        from PIL import Image, UnidentifiedImageError
        try:
            with Image.open(io.BytesIO(body)) as decoded:
                width, height = decoded.size
                if width * height > 40_000_000 or width < 1 or height < 1: raise StudioError("Reference must be at most 40 megapixels")
                if Image.MIME.get(decoded.format) != mime: raise StudioError("The image format does not match its content type")
                decoded.verify()
            with Image.open(io.BytesIO(body)) as decoded: decoded.load()
        except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
            raise StudioError("Reference image is damaged or incomplete; choose a valid PNG, JPG or WebP") from exc
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", Path(filename or "reference").name)[:100]
        if not safe or safe in (".", ".."): raise StudioError("Invalid upload filename")
        # ComfyUI only receives this generated basename; client paths are never used.
        uploads = self.experiments / "uploads"; uploads.mkdir(parents=True, exist_ok=True)
        name = f"{uuid.uuid4().hex}_{safe}{IMAGE_TYPES[mime]}"
        path = uploads / name; path.write_bytes(body)
        comfy_input = self.comfy_root / "input"
        if not comfy_input.is_dir():
            path.unlink(missing_ok=True)
            raise StudioError("Configured ComfyUI input folder is unavailable")
        shutil.copyfile(path, comfy_input / name)
        metadata = {"file": name, "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body), "width": width, "height": height, "original_name": safe}
        self._write_json_atomic(uploads / (name + ".json"), metadata)
        return metadata

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
    def _media(self, descriptor):
        query = urlencode({k:descriptor[k] for k in ("filename", "subfolder", "type") if descriptor.get(k) is not None})
        headers = {}
        requested_range = self.headers.get("Range")
        if requested_range:
            if not re.fullmatch(r"bytes=(?:\d+-\d*|-\d+)", requested_range):
                raise StudioError("A single valid byte range is required")
            headers["Range"] = requested_range
        request = Request(self.studio.comfy_url + "/view?" + query, headers=headers)
        try: response = urlopen(request, timeout=30)
        except HTTPError as exc:
            if exc.code != 416: raise
            self.send_response(416)
            if exc.headers.get("Content-Range"): self.send_header("Content-Range", exc.headers["Content-Range"])
            self.send_header("Content-Length", "0"); self.end_headers(); return
        with response:
            self.send_response(response.status)
            for key in ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges", "ETag", "Last-Modified"):
                if response.headers.get(key): self.send_header(key, response.headers[key])
            self.end_headers()
            try:
                while chunk := response.read(64 * 1024): self.wfile.write(chunk)
            except (BrokenPipeError, ConnectionResetError): return

    def _local_file(self, file, download=False):
        size = file.stat().st_size
        start, end = 0, size - 1
        requested = self.headers.get("Range")
        if requested:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", requested)
            if not match or not any(match.groups()): raise StudioError("A single byte range is required")
            left, right = match.groups()
            if left: start, end = int(left), min(int(right), end) if right else end
            else: start = max(0, size - int(right))
            if start > end or start >= size:
                self.send_response(416); self.send_header("Content-Range", f"bytes */{size}"); self.send_header("Content-Length", "0"); self.end_headers(); return
        self.send_response(206 if requested else 200)
        self.send_header("Content-Type", mimetypes.guess_type(str(file))[0] or "application/octet-stream")
        self.send_header("Content-Length", str(end - start + 1)); self.send_header("Accept-Ranges", "bytes")
        if requested: self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        if download: self.send_header("Content-Disposition", f'attachment; filename="{file.name}"')
        self.end_headers()
        try:
            with file.open("rb") as stream:
                stream.seek(start); remaining = end - start + 1
                while remaining:
                    chunk = stream.read(min(65536, remaining))
                    if not chunk: break
                    self.wfile.write(chunk); remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError): pass
    def do_GET(self):
        if not self._safe_host(): return self._json(403, {"error":"Loopback Host required"})
        try:
            path = urlparse(self.path).path
            if path == "/api/identity": return self._json(200, self.studio.identity())
            if path == "/api/workspace": return self._json(200, self.studio.assets.snapshot())
            if path == "/api/setups": return self._json(200, self.studio.assets.setups())
            if path.startswith("/api/uploads/"):
                from urllib.parse import unquote
                name=unquote(path.rsplit("/",1)[-1])
                if not re.fullmatch(r"[0-9a-f]{32}_[A-Za-z0-9._-]+\.(?:png|jpg|webp)",name): raise StudioError("Invalid upload")
                return self._local_file(inside(self.studio.experiments/'uploads',self.studio.experiments/'uploads'/name))
            if path.startswith("/api/assets/") and path.endswith("/file"):
                return self._local_file(self.studio.assets.file(path.split("/")[3]), urlparse(self.path).query == "download")
            if path.startswith("/api/exports/"):
                identifier = path.rsplit("/", 1)[-1]
                if not re.fullmatch(r"[0-9a-f]{32}", identifier): raise StudioError("Invalid export")
                file = inside(self.studio.assets.root, self.studio.assets.root / "exports" / (identifier + ".zip"))
                return self._local_file(file, True)
            if path == "/api/catalog": return self._json(200, self.studio.catalog())
            if path.startswith("/api/workflows/"):
                preset = self.studio.preset(path.rsplit("/", 1)[-1]); _, workflow = self.studio.graph_for(preset)
                if urlparse(self.path).query == "visual" and preset.get("visual"):
                    workflow = inside(self.studio.root, self.studio.root / preset["visual"])
                suffix = "visual" if urlparse(self.path).query == "visual" and preset.get("visual") else "api"
                data = workflow.read_bytes(); self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Disposition", f'attachment; filename="{preset["id"]}-{suffix}.json"'); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data); return
            if path == "/api/health": return self._json(200, self.studio.health(urlparse(self.path).query == "refresh"))
            if path == "/api/library": return self._json(200, self.studio.library.snapshot())
            if path.startswith("/api/inspect/"): return self._json(200, self.studio.inspect_preset(path.rsplit("/", 1)[-1]))
            if path.startswith("/api/examples/"):
                file = inside(self.studio.root / "examples", self.studio.root / "examples" / path[len("/api/examples/"):])
                if file.suffix.lower() not in (".png", ".jpg", ".webp", ".gif", ".glb") or not file.is_file(): return self._json(404, {"error": "Example not found"})
                data = file.read_bytes(); self.send_response(200); self.send_header("Content-Type", mimetypes.guess_type(str(file))[0] or "application/octet-stream"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data); return
            if path == "/api/jobs": return self._json(200, [self.studio.public(x) for x in sorted(self.studio.jobs.values(), key=lambda j:j["created_at"], reverse=True)])
            if path.startswith("/api/jobs/") and path.endswith("/recipe"):
                job = self.studio.jobs.get(path.split("/")[3]); return self._json(200, self.studio.export_recipe(job)) if job else self._json(404, {"error":"Unknown job"})
            if path.startswith("/api/jobs/"):
                job = self.studio.jobs.get(path.rsplit("/", 1)[-1]); return self._json(200, self.studio.public(job)) if job else self._json(404, {"error":"Unknown job"})
            if path.startswith("/api/image/"):
                _, _, _, job_id, index = path.split("/"); job = self.studio.jobs.get(job_id); image = job and job.get("outputs", [])[int(index)]
                if not image: return self._json(404, {"error":"Unknown image"})
                if image.get("asset_id"): return self._local_file(self.studio.assets.file(image["asset_id"]))
                return self._media(image)
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
            if self.path == "/api/preview": return self._json(200, self.studio.preview(self._body_json()))
            if self.path == "/api/references/check": return self._json(200, self.studio.reference_status(self._body_json()))
            if self.path == "/api/assets/update": return self._json(200, self.studio.assets.update(self._body_json()))
            if self.path == "/api/collections": return self._json(200, self.studio.assets.collection(self._body_json()))
            if self.path == "/api/setups": return self._json(200, self.studio.assets.save_setup(self._body_json()))
            if self.path == "/api/assets/reference": return self._json(200, self.studio.asset_reference(self._body_json().get("id")))
            if self.path == "/api/assets/export": return self._json(201, self.studio.export_assets(self._body_json()))
            if self.path == "/api/recipe-check": return self._json(200, self.studio.check_recipe(self._body_json()))
            if self.path == "/api/folders/open": return self._json(200, self.studio.library.open_folder(self._body_json().get("id")))
            if self.path == "/api/models/install": return self._json(202, self.studio.library.start_install(self._body_json().get("id")))
            if self.path == "/api/workflow-inspect": return self._json(200, self.studio.inspect_workflow(self._body_json()))
            if self.path.startswith("/api/jobs/") and self.path.endswith("/resume"):
                self._body_json(); return self._json(202, self.studio.resume_job(self.path.split("/")[3]))
            if self.path == "/api/upload":
                size = self._content_length(20 * 1024 * 1024); return self._json(201, self.studio.upload(self.headers.get("X-Filename", "reference"), self.headers.get("Content-Type", ""), self.rfile.read(size)))
            return self._json(404, {"error":"Not found"})
        except (StudioError, ValueError, json.JSONDecodeError) as exc: self._json(400, {"error": str(exc)})
        except OSError as exc: self._json(500, {"error": "Local operation failed: " + str(exc)[:200]})

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--repo-root", "--root", dest="repo_root", default=str(Path(__file__).parents[1])); args = parser.parse_args()
    Handler.studio = Studio(Path(args.repo_root)); ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
if __name__ == "__main__": main()
