"""Local-only Asset Studio.  Run: python app/server.py --repo-root PATH"""
from __future__ import annotations

import argparse
import copy
import hashlib
from http.client import HTTPException
import io
import json
import math
import mimetypes
import random
import re
import shutil
import sqlite3
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
from urllib.parse import parse_qs, quote, urlencode, urlparse
from urllib.request import Request, urlopen

# The portable Python includes ComfyUI's own `app` package in its search path.
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model_library import ModelLibrary
from workspace import AssetWorkspace, WorkspaceError, digest_file
from references import compile_references, image_record
from production import Production, fingerprint
import mixed_batch
from backends import BackendManager
import host_memory
import wan_capacity
from runtime_recovery import RuntimeRecovery
import prompting
import submission_evidence
import job_resources
import continuation
from studio_prompt.http_extension import extend_handler
from i2v_diagnostics import artifact_path as i2v_artifact_path
from i2v_diagnostics import build_report as build_i2v_report
from i2v_diagnostics import centered_crop_plan, image_metadata, locate_source

HOST, PORT = "127.0.0.1", 8191
IMAGE_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
CONTROL_KEYS = ("positive", "negative", "width", "height", "seed", "steps", "cfg", "denoise", "lora", "reference", "last_reference", "frames", "fps", "style_weight", "pose_strength", "sampler", "scheduler", "lora_name", "lora2", "lora2_name", "lora3", "lora3_name", "lora4", "lora4_name", "lora5", "lora5_name", "lora6", "lora6_name")
METADATA_CONTROL_KEYS = ("mode",)
LORA_SLOTS = ("lora", "lora2", "lora3", "lora4", "lora5", "lora6")
PRE_SUBMIT_QUEUE_WAIT_SECONDS = 60     # yield the single worker; never submit into an unobserved/busy queue
HISTORY_OBSERVATION_SECONDS = 4 * 3600  # ceiling while ComfyUI still lists the prompt; Stop tracking ends observation sooner
HISTORY_QUEUE_CHECK_EVERY = 5            # empty history polls (2 s apart) between /queue liveness reads
HISTORY_UNLISTED_STRIKES = 3             # consecutive unlisted queue reads before the prompt is declared gone
HOST_COMMIT_MINIMUM = 32 * 1024**3
LORA_NAME_KEYS = tuple(k + "_name" for k in LORA_SLOTS)

class StudioError(ValueError): pass

class QueueWaitUnavailable(StudioError): pass

def combo_options(descriptor):
    """Both ComfyUI combo encodings: legacy [[...], {}] and V3 ['COMBO', {options}]."""
    if not isinstance(descriptor, list) or not descriptor: return []
    if isinstance(descriptor[0], list): return [v for v in descriptor[0] if isinstance(v, str)]
    if descriptor[0] == "COMBO" and len(descriptor) > 1 and isinstance(descriptor[1], dict):
        return [v for v in (descriptor[1].get("options") or []) if isinstance(v, str)]
    return []

def is_off(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and float(value) == 0

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
        self._options = None; self._options_at = 0
        self._host_commit = None; self._host_commit_at = 0
        self.jobs = {}; self.queue = Queue(); self.lock = threading.RLock(); self.worker_failure = None
        self._fingerprint_lock = threading.Lock()
        self._load_jobs()
        for job in self.jobs.values():
            # Failed or still-publishing native AV/voice attempts retain their
            # recipe and exact prior asset set for inspection; only completed
            # publication may be indexed on restart. Legacy jobs without a
            # publication marker keep the historical recovery path.
            if job.get("operation") in ("native.av-preview.v1","native.voice-baseline.v1") and "publication_status" in job and job["publication_status"] != "published": continue
            self.index_outputs(job)
        self.production = Production(self)
        self.backends = BackendManager(self)
        self.backends.activate(self.backends.active)
        from studio_prompt.reference_jobs import ReferenceJobs
        self.reference_jobs = ReferenceJobs(self)
        from studio_prompt.projects import PromptProjects
        self.prompt_projects = PromptProjects(self.assets)
        self.resource_observations = job_resources.from_config(self)
        self.worker = threading.Thread(target=self._work, daemon=True, name="asset-studio-worker"); self.worker.start()
        self.runtime_recovery = RuntimeRecovery(self)

    def catalog(self):
        data = read_json(self.catalog_path)
        if not isinstance(data, dict) or not isinstance(data.get("presets"), list): raise StudioError("Invalid presets/catalog.json")
        # Expose the workflow's authored values as editable defaults.  This keeps
        # the catalog compact while never inventing a prompt in the browser.
        result = copy.deepcopy(data)
        loras = self.options().get("loras") or []
        for preset in result["presets"]:
            preset["runtime_block"] = self.config.get("runtime_blocks", {}).get(preset.get("family"))
            if preset.get('family')=='MiniMax H3' and self.config.get('enable_h3_loader_experiment') and getattr(getattr(self,'backends',None),'active',None)=='h3':preset['runtime_block']=None
            backend = preset.get('backend_id', 'primary')
            if hasattr(self, 'backends') and backend != self.backends.active:
                preset['runtime_block'] = 'Switch to ' + self.backends.profiles[backend]['name'] + ' to use this recipe.'
            try:
                graph, template_path = self.graph_for(preset); defaults = {}
                for key in CONTROL_KEYS:
                    binding = preset.get(key)
                    if binding: defaults[key] = graph[str(binding[0])]["inputs"].get(str(binding[1]), "")
                preset["defaults"] = defaults
                capacity = wan_capacity.projection(preset, graph)
                if capacity is not None: preset["wan_decode_capacity"] = capacity
                preset["continuation_capability"] = dict(continuation.capability(preset, graph), template_sha256=hashlib.sha256(template_path.read_bytes()).hexdigest())
                authored = {v for node in graph.values() for field, v in (node.get("inputs") or {}).items() if field == "lora_name" and isinstance(v, str)}
            except (StudioError, KeyError, TypeError, IndexError, AttributeError):
                preset["defaults"] = {}; authored = set()
            # The installed inventory is the allow-list the browser gets; when
            # ComfyUI is offline it is unknown, never "everything is missing".
            preset["missing_loras"] = sorted(name for name in authored if name not in loras) if loras else []
            for key in LORA_NAME_KEYS:
                if preset.get(key) or (preset.get("bindings_extra") or {}).get(key): preset.setdefault("choices", {})[key] = list(loras)
        return result

    def options(self, refresh=False, discover=False):
        """Installed LoRA files and sampler/scheduler names from the node schema.

        Only the endpoint discovers; every internal caller reads the schema
        already cached by health polling, so binding a control never adds a
        ComfyUI round trip.  Unknown inventory is empty, never "all missing".
        """
        cached = getattr(self, "_options", None)
        if not refresh and cached is not None and time.monotonic() - getattr(self, "_options_at", 0) < 120: return copy.deepcopy(cached)
        info = None
        if discover:
            try: info = self.node_info(refresh)
            except (URLError, TimeoutError, OSError, ValueError): info = None
        else: info = getattr(self, "_schema", None)
        def field(class_type, name):
            node = info.get(class_type) if isinstance(info, dict) else None
            if not isinstance(node, dict): return []
            groups = (node.get("input", {}).get("required", {}) or {}) | (node.get("input", {}).get("optional", {}) or {})
            return combo_options(groups.get(name))
        result = {"loras": field("LoraLoaderModelOnly", "lora_name") or field("LoraLoader", "lora_name"),
                  "samplers": field("KSampler", "sampler_name"), "schedulers": field("KSampler", "scheduler"),
                  "source": "comfyui" if isinstance(info, dict) else "unavailable"}
        # Never memoise "unknown": a later schema discovery must fill it in.
        if isinstance(info, dict): self._options = result; self._options_at = time.monotonic()
        return copy.deepcopy(result)

    def knowledge(self):
        """The settings knowledge base, verbatim.  Absent file is not an error."""
        path = self.root / "presets/settings-kb.json"
        if not path.is_file(): return {"available": False, "version": 0, "families": {}, "loras": {}, "sha256": None}
        data = read_json(path)
        if not isinstance(data, dict): raise StudioError("Invalid presets/settings-kb.json")
        return dict(data, available=True, sha256=hashlib.sha256(path.read_bytes()).hexdigest())

    def recipes(self):
        """Authored recipes annotated against the installed LoRA inventory."""
        path = self.root / "presets/recipes.json"
        data = read_json(path) if path.is_file() else None
        if path.is_file() and (not isinstance(data, dict) or not isinstance(data.get("recipes"), list)): raise StudioError("Invalid presets/recipes.json")
        inventory = self.options(); installed = inventory.get("loras") or []
        entries = []
        for recipe in (data or {}).get("recipes", []):
            if not isinstance(recipe, dict): continue
            names = [v for key, v in (recipe.get("controls") or {}).items() if key in LORA_NAME_KEYS and isinstance(v, str)]
            missing = sorted({name for name in names if name not in installed}) if installed else []
            entries.append(dict(recipe, available=(not missing) if installed else None, missing=missing))
        return {"version": (data or {}).get("version", 1), "available": path.is_file(), "source": inventory.get("source"), "recipes": entries}

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

    def _validate_rgba_mask_reference(self, preset, upload):
        """Require the alpha source that a `requires_rgba_mask` graph actually uses.

        Every such preset drives its noise mask and final composite from the core
        `LoadImage` MASK output, which is 1 - alpha: a fully opaque upload is an
        empty mask and would repaint nothing, and nothing here pads or crops.
        """
        from PIL import Image, UnidentifiedImageError
        who = preset.get("name") or preset.get("id") or "This recipe"
        try:
            with Image.open(upload) as decoded:
                if decoded.format != "PNG" or decoded.mode != "RGBA": raise StudioError(who + " requires a real RGBA PNG upload")
                width, height = decoded.size
                if width % 8 or height % 8: raise StudioError(who + " requires width and height divisible by 8; no padding or cropping is applied")
                if decoded.getchannel("A").getextrema()[0] == 255: raise StudioError(who + " requires a transparent repair region in the alpha channel")
        except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
            raise StudioError(who + " requires a valid RGBA PNG upload") from exc

    @staticmethod
    def _i2v_mode(preset, name):
        modes = preset.get("i2v_modes") or []
        for mode in modes:
            if isinstance(mode, dict) and mode.get("id") == name:
                return mode
        raise StudioError("Unsupported I2V mode")

    def _validate_i2v_mode_source(self, preset, mode, graph, controls):
        """Fail closed when a mode promises one exact reference image."""
        required = (mode or {}).get("required_reference")
        if required is None:
            return
        if not isinstance(required, dict) or not re.fullmatch(r"[0-9a-f]{64}", str(required.get("sha256", ""))):
            raise StudioError("I2V mode has an invalid required reference declaration")
        who = mode.get("name") or mode.get("id") or "This I2V mode"
        label = required.get("label") if isinstance(required.get("label"), str) else "declared canonical source"
        name = controls.get("reference")
        if not name:
            raise StudioError(f"{who} requires the {label} upload; the authored example cannot be queued")
        binding = preset.get("reference")
        try:
            bound = graph[str(binding[0])]["inputs"][str(binding[1])]
        except (KeyError, TypeError, IndexError):
            raise StudioError("Preset has an invalid canonical source binding")
        if bound != name:
            raise StudioError(f"{who} did not bind the selected source")
        expected = required["sha256"]
        uploads = self.experiments / "uploads"
        upload = inside(uploads.resolve(), uploads / name)
        comfy_input = inside((self.comfy_root / "input").resolve(), self.comfy_root / "input" / name)
        for source in (upload, comfy_input):
            if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != expected:
                raise StudioError(f"{who} requires the {label}; the selected source does not match")

    def _prepare_i2v(self, preset, graph, controls):
        """Resolve source orientation before dimension bindings are applied.

        Wan's node has an explicit center-crop contract.  The Studio therefore
        chooses the opposite orientation for a known authored resolution pair,
        while retaining an explicit warning for any remaining aspect mismatch.
        """
        if not preset.get("source_orientation") or not controls.get("reference"):
            return
        source = locate_source(self, controls.get("reference"))
        source_path = source.get("path")
        preparation = {"policy": preset.get("source_orientation"), "source": source}
        if not source_path:
            preparation["warning"] = "Source dimensions unavailable; orientation was not changed."
            preset["_prepared_source"] = preparation
            return
        try:
            metadata = image_metadata(Path(source_path))
            preparation["source"].update(metadata)
            width_value = controls.get("width")
            height_value = controls.get("height")
            if width_value is None and preset.get("width"):
                width_value = graph[str(preset["width"][0])]["inputs"][str(preset["width"][1])]
            if height_value is None and preset.get("height"):
                height_value = graph[str(preset["height"][0])]["inputs"][str(preset["height"][1])]
            target_width = number(width_value, "width", preset.get("dimension_limits", [64, 1536])[0], preset.get("dimension_limits", [64, 1536])[1], True)
            target_height = number(height_value, "height", preset.get("dimension_limits", [64, 1536])[0], preset.get("dimension_limits", [64, 1536])[1], True)
        except (StudioError, KeyError, TypeError, IndexError, OSError, ValueError) as exc:
            preparation["warning"] = "Source-aware orientation could not be resolved: " + str(exc)[:200]
            preset["_prepared_source"] = preparation
            return
        source_orientation = metadata["orientation"]
        target_orientation = "square" if target_width == target_height else "landscape" if target_width > target_height else "portrait"
        swapped = False
        pairs = {tuple(pair) for pair in preset.get("orientation_pairs", []) if isinstance(pair, list) and len(pair) == 2}
        if source_orientation in {"portrait", "landscape"} and target_orientation in {"portrait", "landscape"} and source_orientation != target_orientation and (target_width, target_height) in pairs:
            controls["width"], controls["height"] = target_height, target_width
            target_width, target_height = target_height, target_width
            target_orientation = "landscape" if target_width > target_height else "portrait"
            swapped = True
        plan = centered_crop_plan(metadata["width"], metadata["height"], target_width, target_height)
        preparation.update({
            "source_orientation": source_orientation,
            "requested_dimensions_before_orientation": [number(width_value, "width", 1, 16384, True), number(height_value, "height", 1, 16384, True)],
            "dimensions_after_orientation": [target_width, target_height],
            "orientation_action": "swapped to match source" if swapped else "preserved requested orientation",
            "target_orientation": target_orientation,
            "preprocessing": plan,
        })
        if plan["crop"] != "none":
            preparation["warning"] = "Wan22ImageToVideoLatent will center-crop the source before bilinear resampling; no letterbox is used."
        preset["_prepared_source"] = preparation

    def prepare(self, payload):
        if hasattr(self, 'backends') and self.backends.busy: raise StudioError('A backend switch is running. Wait for it to finish.')
        self.require_worker()
        if not isinstance(payload, dict): raise StudioError("JSON object required")
        preset = self.preset(payload.get("preset_id")); graph, graph_path = self.graph_for(preset)
        if preset.get("runtime_block"): raise StudioError(preset["runtime_block"])
        expected = payload.get("expected_template_sha256")
        if expected and expected != hashlib.sha256(graph_path.read_bytes()).hexdigest():
            raise StudioError("The preset changed since this recipe was imported. Re-import it or deliberately select the current preset.")
        controls = payload.get("controls", {})
        if not isinstance(controls, dict): raise StudioError("controls must be an object")
        controls = dict(controls)
        supported = {k for k in CONTROL_KEYS if preset.get(k) or (preset.get("bindings_extra") or {}).get(k)} | set(preset.get("metadata_controls", []))
        unknown = set(controls) - supported
        if unknown: raise StudioError("Unsupported controls: " + ", ".join(sorted(unknown)))
        mode = None
        if "mode" in controls:
            mode = self._i2v_mode(preset, controls["mode"])
            for key, value in (mode.get("controls") or {}).items():
                if key not in controls:
                    controls[key] = value
        self._prepare_i2v(preset, graph, controls)
        for key in ("positive", "negative"):
            if key in controls:
                if not isinstance(controls[key], str) or len(controls[key]) > 8000: raise StudioError(f"{key} must be text up to 8000 characters")
                self._bind_control(graph, preset, key, controls[key])
        # A recipe whose wording carries bracketed fills refuses to run with one left in place on every route, not only a
        # continuation: the authored example would otherwise be submitted literally from the plain Create route (#367).
        authored = graph.get(str(preset["positive"][0]), {}).get("inputs", {}).get(str(preset["positive"][1])) if preset.get("positive") else None
        left = continuation.unfilled(preset, controls.get("positive", authored))
        if left: raise StudioError("Fill in the wording: replace %s before running." % " and ".join("“%s”" % item for item in left))
        for key in LORA_SLOTS:
            if key not in controls: continue
            binding = preset.get(key) or ((preset.get("bindings_extra") or {}).get(key) or [None])[0]
            try: existing = graph[str(binding[0])]["inputs"].get(str(binding[1]))
            except (KeyError, TypeError, IndexError): raise StudioError("Preset has an invalid workflow binding")
            # `lora` stays polymorphic: older presets bind it to a filename input.
            value = number(controls[key], key, 0, 2) if isinstance(existing, (int, float)) and not isinstance(existing, bool) else controls[key]
            if not isinstance(value, (int, float, str)) or (isinstance(value, str) and len(value) > 8000): raise StudioError(f"{key} must be a number or short text")
            self._bind_control(graph, preset, key, value)
        installed = self.options().get("loras") if any(key in controls for key in LORA_NAME_KEYS) else None
        for key in LORA_NAME_KEYS:
            if key not in controls: continue
            name = controls[key]
            if not isinstance(name, str) or not name or len(name) > 200 or name != Path(name).name or "/" in name or "\\" in name or ".." in name or not name.endswith(".safetensors"):
                raise StudioError(f"{key} must be an installed .safetensors filename")
            # ComfyUI rejects an uninstalled combo value with HTTP 400 even at
            # strength 0, so refuse it here while the inventory is known.
            if installed and name not in installed: raise StudioError("Unknown LoRA file: " + name)
            self._bind_control(graph, preset, key, name)
        for key, lo, hi, integer in (("seed", 0, 2**63-1, True), ("steps", 1, 150, True), ("cfg", 0, 30, False), ("denoise", 0, 1, False), ("style_weight", 0, 2, False), ("pose_strength", 0, 2, False)):
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
                limits = preset.get('dimension_limits', [64, 1536])
                dims[key] = number(controls[key], key, limits[0], limits[1], True)
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
            if preset.get("requires_rgba_mask") and key == "reference": self._validate_rgba_mask_reference(preset, upload)
            self._bind_control(graph, preset, key, upload.name)
        if preset.get("requires_rgba_mask") and "reference" not in controls:
            raise StudioError((preset.get("name") or preset.get("id") or "This recipe") + " requires a real RGBA PNG upload; the authored example cannot be queued")
        # A recipe that transforms a picture (a board with a picture to keep, or a declared restyle/combine) needs that
        # picture on every route: the plain Create route would otherwise submit the authored example picture literally.
        source_key = "last_reference" if preset.get("last_reference") else "reference" if preset.get("reference") else None
        if source_key and payload.get("continuation") is None and (preset.get("reference_board") and preset.get("last_reference") or preset.get("continuation_operation")) and source_key not in controls:
            label = preset.get(source_key + "_label") or ("Picture to keep (image 1)" if source_key == "last_reference" else "the picture")
            raise StudioError((preset.get("name") or preset.get("id") or "This recipe") + " needs your picture on " + label + "; the authored example picture cannot be queued")
        if preset.get("max_pixels"):
            actual = {key: graph[str(preset[key][0])]["inputs"][str(preset[key][1])] for key in ("width", "height")}
            if actual["width"] * actual["height"] > preset["max_pixels"]: raise StudioError("Resolution exceeds this workflow's pixel budget")
        if preset.get('resolution_choices'):
            actual = [graph[str(preset[k][0])]['inputs'][str(preset[k][1])] for k in ('width', 'height')]
            if actual not in preset['resolution_choices']: raise StudioError('Choose an authored resolution pair from this recipe')
        if preset.get("reference_slots"):
            preset["_prepared_references"] = compile_references(preset, graph, payload.get("references"), self.experiments / "uploads")
        elif payload.get("references"):
            raise StudioError("This recipe has no role-assigned reference slots; choose a Qwen Atelier recipe")
        batch = number(payload.get("batch_count", 1), "batch_count", 1, 4, True)
        self.prune_disabled_loras(graph)
        continuation.validate(self, payload, preset, graph)
        self.ensure_reference_inputs(graph)
        self._validate_i2v_mode_source(preset, mode, graph, controls)
        wan_capacity.enforce(graph)
        self.host_commit_preflight(preset, graph)
        return preset, graph, graph_path, controls, batch

    def host_commit_reading(self, refresh=False):
        if refresh or self._host_commit is None or time.monotonic() - self._host_commit_at > 3:
            self._host_commit = host_memory.read(); self._host_commit_at = time.monotonic()
        return dict(self._host_commit)

    @staticmethod
    def host_commit_required(preset, graph):
        explicit = preset.get('host_commit_heavy') is True
        model_bound = False; megapixels = 0.0
        for node in graph.values():
            inputs = node.get('inputs', {})
            for field in ('unet_name', 'model_name', 'diffusion_model', 'checkpoint_name'):
                value = inputs.get(field)
                if isinstance(value, str):
                    value = value.lower()
                    if 'qwen-image-edit-2511' in value or 'flux-2' in value or 'flux2-' in value: model_bound = True
            width,height=inputs.get('width'),inputs.get('height')
            if isinstance(width,(int,float)) and not isinstance(width,bool) and isinstance(height,(int,float)) and not isinstance(height,bool): megapixels=max(megapixels,float(width)*float(height)/(1024**2))
            scaled=inputs.get('megapixels')
            if node.get('class_type')=='ImageScaleToTotalPixels' and isinstance(scaled,(int,float)) and not isinstance(scaled,bool): megapixels=max(megapixels,float(scaled))
        return (explicit or model_bound) and megapixels >= 1.0

    def host_commit_preflight(self, preset, graph, refresh=False):
        if not self.config.get('enforce_host_commit_headroom') or not self.host_commit_required(preset, graph): return None
        reading=self.host_commit_reading(refresh)
        reason=reading.get('unknown_reason');available=reading.get('available_bytes')
        if reason: raise StudioError('Host commit headroom is unavailable: '+str(reason))
        if not isinstance(available,int) or available < HOST_COMMIT_MINIMUM:
            actual='unknown' if not isinstance(available,int) else f'{available / 1024**3:.1f} GiB'
            raise StudioError(f'Host commit headroom {actual} is below the required 32 GiB for this Qwen/FLUX.2 submission')
        return reading

    def prune_disabled_loras(self, graph):
        """Drop LoRA loaders left at strength 0 and rewire whatever consumed them.

        A zero-strength loader is a no-op for the sampler but still forces
        ComfyUI to validate (and reject) its filename, so an off slot must leave
        the graph entirely.  Output slot 0 is MODEL, slot 1 is CLIP.
        """
        for _ in range(len(graph) + 1):
            victim = None
            for key, node in graph.items():
                kind = node.get("class_type"); inputs = node.get("inputs") or {}
                if kind == "LoraLoaderModelOnly" and is_off(inputs.get("strength_model")): victim = key; break
                if kind == "LoraLoader" and is_off(inputs.get("strength_model")) and is_off(inputs.get("strength_clip")): victim = key; break
            if victim is None: return graph
            sources = {0: (graph[victim].get("inputs") or {}).get("model"), 1: (graph[victim].get("inputs") or {}).get("clip")}
            del graph[victim]
            for node in graph.values():
                for field, value in list((node.get("inputs") or {}).items()):
                    if not (isinstance(value, list) and len(value) == 2 and str(value[0]) == str(victim)): continue
                    replacement = sources.get(value[1])
                    if replacement is None: raise StudioError("A disabled LoRA slot cannot be bypassed in this workflow; keep its strength above zero")
                    node["inputs"][field] = replacement
        raise StudioError("Workflow LoRA chain could not be resolved")

    def ensure_reference_inputs(self, graph):
        for node in graph.values():
            if node.get('class_type') != 'LoadImage': continue
            name = node['inputs'].get('image')
            if not isinstance(name, str) or Path(name).name != name: continue
            target = self.comfy_root/'input'/name
            if target.is_file(): continue
            for source in (self.experiments/'uploads'/name, self.root/'examples/references'/name):
                if source.is_file():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target); break

    def create_job(self, payload, enqueue=True, job_id=None):
        with self.lock:
            return self._create_job(payload, enqueue, job_id)

    def _create_job(self, payload, enqueue=True, job_id=None):
        if getattr(self, "reference_jobs", None): self.reference_jobs.require_available()
        preset, graph, graph_path, controls, batch = self.prepare(payload)
        parents = payload.get("parent_assets", [])
        if not isinstance(parents, list) or len(parents) > 8: raise StudioError("Use up to eight parent assets")
        for parent in parents: self.assets.get(parent)
        job_id = job_id or str(uuid.uuid4())
        if job_id in self.jobs: raise StudioError('A job with this identity already exists; inspect it instead of resubmitting')
        directory = self.runs / job_id; directory.mkdir(exist_ok=not enqueue)
        job = {"id": job_id, "status": "queued", "created_at": time.time(), "preset_id": preset["id"], "preset_name": preset.get("name", preset["id"]), "controls": controls, "batch_count": batch, "prompt_ids": [], "submissions": [], "outputs": [], "message": "Waiting for the local generation queue", "graph_path": str(graph_path.relative_to(self.root)), "graph": graph}
        if preset.get("_prepared_source"): job["preparation"] = preset["_prepared_source"]
        job["seed_bindings"] = ([preset["seed"]] if preset.get("seed") else []) + preset.get("bindings_extra", {}).get("seed", [])
        job["prompt_bindings"] = {key: ([preset[key]] if preset.get(key) else []) + preset.get("bindings_extra", {}).get(key, []) for key in ("positive", "negative")}
        job["parent_assets"] = parents
        if payload.get("continuation") is not None: job["continuation"] = copy.deepcopy(payload["continuation"])
        job["references"] = preset.get("_prepared_references", [])
        job["comfy_root"] = str(self.comfy_root); job["comfy_url"] = self.comfy_url
        reading=self.host_commit_preflight(preset, graph)
        if reading: job['host_commit_readings']=[dict(reading, phase='prepared', recorded_at=time.time())]
        self._save(job); self.jobs[job_id] = job
        if enqueue: self.queue.put(("generate", job_id))
        return self.public(job)

    def public(self, job):
        allowed = ("id", "status", "created_at", "preset_id", "preset_name", "controls", "batch_count", "prompt_ids", "submissions", "outputs", "message", "failure", "parent_assets", "references", "project_id", "started_at", "finished_at", "elapsed_seconds", "tracking_disposition", "preparation", "continuation", "abandonment")
        result = {k: job.get(k) for k in allowed}
        # Polling the gallery should not transfer every full graph every four seconds.
        result["submissions"] = [{k: v for k, v in s.items() if k != "graph"} for s in job.get("submissions", [])]
        result["can_stop_tracking"] = Studio._stop_tracking_error(self, job) is None
        result["can_resume_tracking"] = Studio._tracking_stopped(job) and Studio._known_prompt_error(job) is None
        result["has_pending_submission"] = "pending_submission" in job
        result["never_submitted"] = submission_evidence.never_submitted(job)
        result["mixed_batch"] = mixed_batch.snapshot(job)
        result["can_abandon"] = submission_evidence.abandonable(job)
        result["abandon_requires_acknowledgement"] = result["can_abandon"] and not result["never_submitted"]
        return result

    @staticmethod
    def _estimate_float(value, fallback=0.0):
        try: result = float(value)
        except (TypeError, ValueError): return fallback
        return result if math.isfinite(result) else fallback

    @staticmethod
    def _estimate_name(value):
        if not isinstance(value, str): return ""
        return value.replace("\\", "/").rsplit("/", 1)[-1].strip()

    @staticmethod
    def _estimate_weighted_median(values):
        ordered = []
        for value, weight in values:
            value = Studio._estimate_float(value, None); weight = Studio._estimate_float(weight, None)
            if value is not None and weight is not None and weight > 0: ordered.append((value, weight))
        ordered.sort()
        if not ordered: return 0.0
        halfway = sum(weight for _, weight in ordered) / 2
        total = 0.0
        for value, weight in ordered:
            total += weight
            if total >= halfway: return value
        return ordered[-1][0]

    def _estimate_graph(self, preset, controls):
        graph, _ = self.graph_for(preset)
        controls = controls if isinstance(controls, dict) else {}
        numeric = {"seed", "steps", "cfg", "width", "height", "denoise", "frames", "fps", "style_weight", "pose_strength", *LORA_SLOTS}
        integer = {"seed", "steps", "width", "height", "frames", "fps"}
        extras = preset.get("bindings_extra") or {}
        for key, raw in controls.items():
            if key not in CONTROL_KEYS or not (preset.get(key) or extras.get(key)): continue
            value = raw
            binding = preset.get(key) or (extras.get(key) or [None])[0]
            try: existing = graph[str(binding[0])]["inputs"].get(str(binding[1]))
            except (KeyError, TypeError, IndexError): existing = None
            if key in numeric and (key not in LORA_SLOTS or isinstance(existing, (int, float)) and not isinstance(existing, bool)):
                parsed = self._estimate_float(raw, None)
                if parsed is None: continue
                value = int(parsed) if key in integer else parsed
            try: self._bind_control(graph, preset, key, value)
            except StudioError: continue
        try: self.prune_disabled_loras(graph)
        except (StudioError, KeyError, TypeError): pass
        return graph

    def _estimate_features(self, preset, graph, controls=None, batch_count=1, reference_count=0):
        controls = controls if isinstance(controls, dict) else {}
        nodes = [node for node in (graph or {}).values() if isinstance(node, dict)]
        model_names, lora_names, lora_strengths, node_types = [], [], [], []
        widths, heights, step_values, frame_values = [], [], [], []
        samplers, schedulers = [], []
        prompt_chars = sum(len(controls.get(key, "")) for key in ("positive", "negative") if isinstance(controls.get(key), str))
        for node in nodes:
            kind = str(node.get("class_type") or "")
            node_types.append(kind)
            inputs = node.get("inputs") or {}
            for field in ("unet_name", "ckpt_name", "checkpoint_name", "model_name", "diffusion_model"):
                name = self._estimate_name(inputs.get(field))
                if name: model_names.append(name)
            for field in ("width", "height"):
                value = self._estimate_float(inputs.get(field), 0)
                if value > 0: (widths if field == "width" else heights).append(value)
            value = self._estimate_float(inputs.get("steps"), 0)
            if value > 0: step_values.append(value)
            for field in ("frames", "length", "num_frames", "video_length"):
                value = self._estimate_float(inputs.get(field), 0)
                if value > 0: frame_values.append(value)
            if isinstance(inputs.get("sampler_name"), str): samplers.append(inputs["sampler_name"])
            if isinstance(inputs.get("scheduler"), str): schedulers.append(inputs["scheduler"])
            for field in ("text", "prompt", "positive", "negative"):
                if isinstance(inputs.get(field), str): prompt_chars = max(prompt_chars, len(inputs[field]))
            name = self._estimate_name(inputs.get("lora_name"))
            if name:
                strength = self._estimate_float(inputs.get("strength_model", inputs.get("strength", 1)), 1)
                if abs(strength) > 0:
                    lora_names.append(name); lora_strengths.append(abs(strength))
        width = max(widths or [512]); height = max(heights or [512]); frames = max(frame_values or [1]); steps = max(step_values or [1])
        lora_names = sorted(set(lora_names)); lora_strength = sum(lora_strengths)
        references = max(int(self._estimate_float(reference_count, 0)), sum(1 for kind in node_types if "LoadImage" in kind))
        complexity = max(1.0, float(len(nodes))) + 0.75 * len(lora_names) + 0.35 * references + 0.25 * len(preset.get("stages") or [])
        complexity += sum(1.5 if any(tag in kind.lower() for tag in ("controlnet", "detailer", "upscale", "tiled")) else 0.5 if "ksampler" in kind.lower() else 0 for kind in node_types)
        complexity += min(2.5, prompt_chars / 1200)
        batch = max(1, min(4, int(self._estimate_float(batch_count, 1))))
        model_names = sorted(set(model_names)); model_key = "|".join(model_names) or str(preset.get("family") or preset.get("id") or "unknown")
        return {"workflow": str(preset.get("id") or ""), "workflow_name": str(preset.get("name") or preset.get("id") or "workflow"),
                "family": str(preset.get("family") or ""), "modality": str(preset.get("modality") or "image"), "model": model_key,
                "model_names": model_names, "lora_key": tuple(lora_names), "lora_names": lora_names, "lora_count": len(lora_names),
                "lora_strength": lora_strength, "pixels": max(0.01, width * height / (1024 ** 2)), "width": width, "height": height,
                "steps": steps, "frames": frames, "references": references, "prompt_chars": prompt_chars, "complexity": complexity,
                "node_count": len(nodes), "sampler": samplers[0] if samplers else "", "scheduler": schedulers[0] if schedulers else "", "batch": batch}

    def estimate(self, payload):
        """Estimate end-to-end time from completed local ComfyUI runs without mutating state."""
        if not isinstance(payload, dict): return {"available": False, "reason": "Estimate input must be an object."}
        try:
            presets = self.catalog().get("presets", [])
            preset = next(p for p in presets if p.get("id") == payload.get("preset_id"))
            controls = payload.get("controls") if isinstance(payload.get("controls"), dict) else {}
            graph = self._estimate_graph(preset, controls)
        except (StopIteration, StudioError, KeyError, TypeError, OSError):
            return {"available": False, "reason": "Choose a supported recipe before estimating."}
        references = payload.get("reference_count", 0)
        target = self._estimate_features(preset, graph, controls, payload.get("batch_count", 1), references)
        samples = []
        for job in list(self.jobs.values()):
            if job.get("status") != "completed" or job.get("operation") or job.get("native_recipe") or not job.get("prompt_ids") or not isinstance(job.get("graph"), dict): continue
            elapsed = self._estimate_float(job.get("elapsed_seconds"), 0)
            if elapsed <= 0: continue
            sample_preset = next((p for p in presets if p.get("id") == job.get("preset_id")), None)
            if not sample_preset: continue
            sample = self._estimate_features(sample_preset, job["graph"], job.get("controls"), job.get("batch_count", 1), sum(1 for r in (job.get("references") or []) if not isinstance(r, dict) or r.get("file")))
            sample["seconds"] = elapsed; samples.append(sample)

        if samples:
            candidates = []
            for sample in samples:
                weight = 1.0
                if sample["workflow"] == target["workflow"]: weight *= 12
                elif sample["family"] and sample["family"] == target["family"]: weight *= 4
                if sample["model"] == target["model"]: weight *= 4
                elif sample["modality"] != target["modality"]: weight *= 0.2
                else: weight *= 0.7
                if sample["lora_key"] == target["lora_key"]: weight *= 3
                elif sample["lora_key"] or target["lora_key"]:
                    overlap = len(set(sample["lora_key"]) & set(target["lora_key"])) / max(1, len(set(sample["lora_key"]) | set(target["lora_key"])))
                    weight *= 1 + 2 * overlap if overlap else 0.65
                if sample["lora_strength"] > 0 and target["lora_strength"] > 0:
                    weight *= max(0.35, math.exp(-0.25 * abs(math.log(target["lora_strength"] / sample["lora_strength"]))))
                elif sample["lora_strength"] != target["lora_strength"]:
                    weight *= 0.75
                for key, coefficient in (("pixels", 1.2), ("steps", 0.8), ("frames", 0.9), ("complexity", 0.6), ("references", 0.35), ("prompt_chars", 0.12)):
                    if sample[key] > 0 and target[key] > 0: weight *= max(0.15, math.exp(-coefficient * abs(math.log(target[key] / sample[key]))))
                if sample["sampler"] == target["sampler"] and target["sampler"]: weight *= 1.15
                if sample["scheduler"] == target["scheduler"] and target["scheduler"]: weight *= 1.1
                scales = []
                for key, exponent in (("pixels", 0.8), ("steps", 0.9), ("frames", 0.75), ("complexity", 0.25)):
                    ratio = max(0.2, min(4.0, target[key] / max(sample[key], 0.01))); scales.append(ratio ** exponent)
                unit_scale = math.prod(scales)
                adjusted = sample["seconds"] / max(1, sample["batch"]) * target["batch"] * (0.3 + 0.7 * unit_scale)
                adjusted *= 1 + max(0, target["lora_count"] - sample["lora_count"]) * 0.04
                candidates.append((max(1.0, adjusted), max(0.001, weight), sample))
            median = self._estimate_weighted_median([(value, weight) for value, weight, _ in candidates])
            mad = self._estimate_weighted_median([(abs(value - median), weight) for value, weight, _ in candidates])
            exact = sum(1 for _, _, sample in candidates if sample["workflow"] == target["workflow"]); model_matches = sum(1 for _, _, sample in candidates if sample["model"] == target["model"])
            confidence = "high" if exact >= 5 else "medium" if exact >= 2 or model_matches >= 4 else "low"
            spread = max(2.0, median * (0.18 if confidence == "high" else 0.3 if confidence == "medium" else 0.45), mad * 1.8)
            matched = exact or model_matches or min(3, len(candidates))
            basis = ([f"{exact} completed run{'s' if exact != 1 else ''} of this workflow"] if exact else [f"{model_matches} completed run{'s' if model_matches != 1 else ''} with this model"] if model_matches else [f"{len(samples)} completed local runs across the library"])
        else:
            base = {"image": 45.0, "video": 240.0, "3d": 180.0, "audio": 30.0}.get(target["modality"], 60.0)
            median = base * max(0.5, target["pixels"] ** 0.8) * max(0.5, target["steps"] / 20) * (1 + target["lora_count"] * 0.08) * target["batch"]
            spread = max(10.0, median * 0.6); confidence = "none"; matched = 0; basis = ["No completed local run is comparable yet", "Generic modality fallback; expect a wide range"]
        basis.append(f"scaled for {target['width']:.0f}×{target['height']:.0f}, {target['steps']:.0f} steps, {target['lora_count']} active LoRA{'s' if target['lora_count'] != 1 else ''}, {target['batch']} output{'s' if target['batch'] != 1 else ''}")
        if target["frames"] > 1: basis.append(f"{target['frames']:.0f} frames at workflow complexity {target['node_count']} nodes")
        return {"available": True, "estimate_seconds": round(max(1.0, median), 1), "range_seconds": [round(max(1.0, median - spread)), round(max(median + spread, median + 1))],
                "confidence": confidence, "sample_count": len(samples), "matched_samples": matched, "basis": basis,
                "features": {"workflow": target["workflow_name"], "model": target["model_names"] or [target["model"]], "loras": target["lora_names"],
                             "resolution": [round(target["width"]), round(target["height"])], "steps": round(target["steps"]), "frames": round(target["frames"]),
                             "node_count": target["node_count"], "references": target["references"], "modality": target["modality"]}}

    def export_recipe(self, job):
        return {"version": 2, "preset_id": job["preset_id"], "controls": job["controls"],
                "batch_count": job["batch_count"], "created_at": job["created_at"],
                "workflow": job["graph"], "submissions": job.get("submissions", []),
                "outputs": job.get("outputs", []), "parent_assets": job.get("parent_assets", []), "references": job.get("references", []),
                "preparation": job.get("preparation"), "native_recipe": job.get('native_recipe'), "continuation": job.get("continuation")}

    def i2v_diagnostic(self, job_id):
        job = self.jobs.get(job_id)
        if not job: raise StudioError("Unknown job")
        try:
            return build_i2v_report(self, job_id)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise StudioError("I2V diagnostic unavailable: " + str(exc)[:300]) from exc

    def i2v_diagnostic_file(self, job_id, filename):
        if job_id not in self.jobs: raise StudioError("Unknown job")
        try:
            return i2v_artifact_path(self, job_id, filename)
        except (OSError, ValueError) as exc:
            raise StudioError(str(exc)) from exc

    def output_path(self, output, job=None):
        if (job or {}).get('operation') in ('native.articulated-prop.v1','native.av-preview.v1','native.voice-baseline.v1'):
            identifier=job.get('project_id','')
            if not re.fullmatch('[0-9a-f]{32}',identifier):raise StudioError('Invalid native project identity')
            base=(self.experiments/'projects'/identifier).resolve()
            return inside(base,base/output['native_path'])
        if (job or {}).get('operation')=='asset.import':
            return inside((self.experiments/'uploads').resolve(),self.experiments/'uploads'/output['uploaded_file'])
        root = Path((job or {}).get("comfy_root", self.comfy_root)).resolve()
        kind = output.get("type", "output")
        if kind not in ("output", "temp"): raise StudioError("Unsupported output location")
        return inside(root / kind, root / kind / str(output.get("subfolder") or "") / str(output.get("filename") or ""))

    def index_outputs(self, job):
        for index, output in enumerate(job.get("outputs", [])):
            try:
                asset_id = self.assets.register(job, index, self.output_path(output, job))
                if asset_id: output["asset_id"] = asset_id
            except (OSError, ValueError, sqlite3.Error) as exc:
                # A storage fault while indexing a known output never changes the remote outcome.
                output["snapshot_error"] = str(exc)[:200]

    def asset_reference(self, asset_id):
        asset = self.assets.get(asset_id)
        if asset["media_type"] != "image": raise StudioError("Choose an image as the reference")
        context = continuation.source_context(self, asset_id)
        source = self.assets.file(asset_id)
        raw = source.read_bytes()
        if hashlib.sha256(raw).hexdigest() != context["sha256"]: raise StudioError("Source changed during attachment; reopen the handoff.")
        result = self.upload(asset["filename"], mimetypes.guess_type(str(source))[0] or "", raw)
        result["parent_asset"] = asset_id
        result["context"] = context
        return result

    def import_image(self, filename, content_type, body):
        uploaded=self.upload(filename,content_type,body)
        identifier=str(uuid.uuid4());(self.runs/identifier).mkdir()
        job={'id':identifier,'operation':'asset.import','status':'completed','created_at':time.time(),
             'preset_id':'imported-image','preset_name':uploaded['original_name'],'controls':{},'batch_count':1,
             'prompt_ids':[],'submissions':[],'parent_assets':[],'references':[uploaded],
             'message':'Imported original image. No generation submitted.','graph_path':'','graph':{},
             'outputs':[{'filename':uploaded['original_name'],'uploaded_file':uploaded['file'],'type':'output','media_type':'image'}]}
        self.index_outputs(job);self._save(job);self.jobs[identifier]=job
        return {'asset':self.assets.get(job['outputs'][0]['asset_id']),'job':self.public(job)}

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
                "batch_count":batch, "preparation":preset.get("_prepared_source"), "template_sha256":hashlib.sha256(graph_path.read_bytes()).hexdigest(),
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

    def validate_graph(self, graph):
        scripts=str(Path(__file__).parents[1]/'scripts')
        if scripts not in sys.path: sys.path.append(scripts)
        from game_asset_pipeline import graph_check
        return graph_check(graph,self.node_info())

    def production_preflight(self, preset, graph):
        wan_capacity.enforce(graph)
        self.host_commit_preflight(preset, graph, refresh=True)
        self.node_info(refresh=True)
        self.validate_graph(graph)
        if shutil.disk_usage(self.experiments).free<2*1024**3:raise StudioError('At least 2 GiB free workspace storage is required')
        inspection=self.inspect_preset(preset['id'],graph)
        cache_path=self.root/'.runtime/model-fingerprints.json';models=[]
        with self._fingerprint_lock:
            cache=read_json(cache_path,{}) or {}
            for requirement in inspection['requirements']:
                if requirement.get('path') is None:
                    raise StudioError('Cannot resolve required model: ' + requirement['file'] + ' — ' + requirement.get('note', 'Inspect the declared location'))
                if requirement.get('present') is not True: raise StudioError('Required model is unavailable: ' + requirement['file'])
                path=Path(requirement['path']).resolve()
                if not path.is_relative_to(self.library.models) or not path.is_file():raise StudioError('Required model is unavailable: '+requirement['file'])
                stat=path.stat();key=str(path);record=cache.get(key,{})
                if record.get('bytes')!=stat.st_size or record.get('mtime_ns')!=stat.st_mtime_ns:
                    record={'path':key,'bytes':stat.st_size,'mtime_ns':stat.st_mtime_ns,'sha256':digest_file(path)};cache[key]=record
                models.append(dict(record,file=requirement['file']))
            cache_path.parent.mkdir(exist_ok=True);self._write_json_atomic(cache_path,cache)
        inputs=[]
        for node in graph.values():
            if node['class_type']=='LoadImage':
                name=node['inputs']['image']
                path=inside((self.comfy_root/'input').resolve(),self.comfy_root/'input'/name)
                if not path.is_file():raise StudioError('Reference input is unavailable: '+name)
                inputs.append({'path':str(path),'sha256':digest_file(path),'bytes':path.stat().st_size})
        stats=self._request('/system_stats')
        classes=sorted({node['class_type'] for node in graph.values()})
        schema=self.node_contract(classes)
        return {'comfy_root':str(self.comfy_root),'comfy_url':self.comfy_url,'models':models,'inputs':inputs,
                'schema_sha256':fingerprint(schema),'node_classes':classes,'system':stats.get('system',{}),
                'devices':stats.get('devices',[]),'measured_at':time.time(),'terms_note':preset.get('commercial_note'),
                'verification':'Model content hashes cached only while size and modification time match; inputs rehashed before each stage. Schema hash excludes changing file-choice inventories.'}

    def node_contract(self, classes):
        schema={name:copy.deepcopy(self.node_info().get(name)) for name in classes}
        for node in schema.values():
            if not node:continue
            for group in ('required','optional'):
                for descriptor in node.get('input',{}).get(group,{}).values():
                    if not isinstance(descriptor,list) or not descriptor:continue
                    if isinstance(descriptor[0],list):descriptor[0]=['<runtime choices>']
                    elif descriptor[0]=='COMBO' and len(descriptor)>1 and isinstance(descriptor[1],dict):descriptor[1]['options']=['<runtime choices>']
        return schema

    def check_production_bundle(self, bundle):
        if bundle['comfy_url']!=self.comfy_url or bundle['comfy_root']!=str(self.comfy_root):raise StudioError('The active backend changed; switch back before resuming this experiment')
        schema=self.node_contract(bundle['node_classes'])
        if fingerprint(schema)!=bundle['schema_sha256']:raise StudioError('The runtime node schema changed; create a new experiment branch')
        for record in bundle['models']:
            path=Path(record['path'])
            if not path.is_file() or path.stat().st_size!=record['bytes'] or path.stat().st_mtime_ns!=record['mtime_ns']:
                raise StudioError('A pinned model changed; prepare a new branch before executing')
        for record in bundle['inputs']:
            path=Path(record['path'])
            if not path.is_file() or digest_file(path)!=record['sha256']:raise StudioError('A pinned input changed; original plan preserved')

    def _write_json_atomic(self, path, value):
        temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
        temp.write_text(json.dumps(value, indent=2), encoding="utf-8")
        temp.replace(path)

    def _save(self, job):
        directory = self.runs / job["id"]
        recipe = {"preset_id": job["preset_id"], "controls": job["controls"], "batch_count": job["batch_count"], "graph_path": job["graph_path"], "created_at": job["created_at"]}
        recipe.update(references=job.get("references", []), parent_assets=job.get("parent_assets", []))
        if job.get("continuation") is not None: recipe["continuation"] = job["continuation"]
        self._write_json_atomic(directory / "recipe.json", recipe)
        self._write_json_atomic(directory / "workflow.json", job["graph"])
        state = {k:v for k,v in job.items() if k != "graph"}; self._write_json_atomic(directory / "state.json", state)

    @staticmethod
    def _tracking_stopped(job):
        disposition = job.get("tracking_disposition")
        return isinstance(disposition, dict) and disposition.get("status") == "stopped"

    @staticmethod
    def _tracking_history(job):
        disposition = job.get("tracking_disposition")
        if not isinstance(disposition, dict): return []
        history = disposition.get("history")
        if isinstance(history, list) and all(isinstance(event, dict) for event in history): return [dict(event) for event in history]
        return [{k: v for k, v in disposition.items() if k != "history"}]

    def tracking_stop_tokens(self, job):
        tokens = []
        for event in self._tracking_history(job):
            if event.get("status") == "stopped":
                tokens.append(event.get("event_id") or f"legacy:{job.get('id')}:{event.get('recorded_at')}")
        return tokens

    @staticmethod
    def _known_prompt_error(job):
        if job.get("pending_submission"): return "A submission outcome is still unknown"
        prompt_ids = job.get("prompt_ids")
        submissions = job.get("submissions")
        if not isinstance(prompt_ids, list) or not prompt_ids or any(type(prompt_id) is not str or not prompt_id.strip() for prompt_id in prompt_ids):
            return "No known prompt IDs are available to observe"
        if len(set(prompt_ids)) != len(prompt_ids) or not isinstance(submissions, list) or not submissions:
            return "Known prompt IDs are inconsistent"
        submission_ids = []
        for submission in submissions:
            prompt_id = submission.get("prompt_id") if isinstance(submission, dict) else None
            if type(prompt_id) is not str or not prompt_id.strip() or prompt_id not in prompt_ids:
                return "Known prompt IDs are inconsistent"
            submission_ids.append(prompt_id)
        if set(submission_ids) != set(prompt_ids) or len(set(submission_ids)) != len(submission_ids):
            return "Known prompt IDs are inconsistent"
        if not any(submission.get("status") not in ("completed", "failed") for submission in submissions):
            return "No unresolved known prompt IDs are available to observe"
        return None

    def _stop_tracking_error(self, job):
        if Studio._tracking_stopped(job): return "Tracking was already stopped"
        if job.get("status") != "uncertain": return "Only an uncertain job can stop tracking"
        return Studio._known_prompt_error(job)

    def stop_tracking(self, job_id, reason):
        if type(reason) is not str: raise StudioError("Stop-tracking reason must be text")
        reason = reason.strip()
        if not reason: raise StudioError("Stop-tracking reason is required")
        if len(reason) > 1000: raise StudioError("Stop-tracking reason must be at most 1000 characters")
        with self.lock:
            job = self.jobs.get(job_id)
            if not job: raise StudioError("Unknown job")
            disposition = job.get("tracking_disposition")
            if self._tracking_stopped(job):
                if disposition.get("reason") != reason: raise StudioError("Tracking was already stopped with a different reason")
                return self.public(job)
            error = self._stop_tracking_error(job)
            if error: raise StudioError(error)
            recorded = {"status": "stopped", "reason": reason, "recorded_at": time.time(), "event_id": uuid.uuid4().hex}
            history = self._tracking_history(job) if isinstance(job.get("tracking_disposition"), dict) else []
            disposition = dict(recorded)
            if history: disposition["history"] = history + [dict(recorded)]
            prospective = dict(job); prospective["tracking_disposition"] = disposition
            self._write_json_atomic(self.runs / job_id / "state.json", {k: v for k, v in prospective.items() if k != "graph"})
            job["tracking_disposition"] = disposition
            return self.public(job)

    def _resume_tracking(self, job):
        self.require_worker()
        if job.get("status") != "uncertain": raise StudioError("Only an uncertain job can resume observation")
        error = self._known_prompt_error(job)
        if error: raise StudioError(error)
        history = self._tracking_history(job)
        resumed = dict(job["tracking_disposition"])
        resumed.update(status="resumed")
        resumed["history"] = history + [{"status": "resumed", "recorded_at": time.time()}]
        prospective = dict(job)
        prospective.update(status="queued", message="Queued to resume observation of retained prompt IDs; no image will be resubmitted.", tracking_disposition=resumed)
        self._write_json_atomic(self.runs / job["id"] / "state.json", {k: v for k, v in prospective.items() if k != "graph"})
        job.update(status=prospective["status"], message=prospective["message"], tracking_disposition=resumed)
        self.queue.put(("observe", job["id"]))
        return self.public(job)

    def abandon_job(self, job_id, reason, acknowledge_unknown=False):
        """Record a terminal local disposition, not remote cancellation or success."""
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
            raise StudioError("Give an abandonment reason of 1 to 1000 characters")
        reason = reason.strip()
        with self.lock:
            job = self.jobs.get(job_id)
            if not job: raise StudioError("Unknown job")
            recorded = job.get("abandonment")
            if job.get("status") == "abandoned" and isinstance(recorded, dict):
                if recorded.get("reason") != reason: raise StudioError("This job already has a retained abandonment reason")
                return self.public(job)
            if not submission_evidence.abandonable(job):
                raise StudioError("Only inactive jobs without prompt IDs can be abandoned; known prompts use Stop tracking")
            never_sent = submission_evidence.never_submitted(job)
            if not never_sent and acknowledge_unknown is not True:
                raise StudioError("Acknowledge that the remote outcome is unknown and no remote work will be cancelled")
            disposition = {"basis": "never_submitted" if never_sent else "outcome_unknown", "reason": reason,
                           "recorded_at": time.time(), "event_id": uuid.uuid4().hex,
                           "acknowledged_unknown": not never_sent, "remote_cancelled": False}
            message = ("Abandoned locally before submission. Recipe and reservations are retained." if never_sent else
                       "Abandoned locally; the remote outcome remains unknown. No remote work was cancelled. Receipts and reservations are retained.")
            prospective = dict(job, status="abandoned", message=message, abandonment=disposition)
            # Commit one complete disposition before mutating memory. Keep the exact
            # recipe, workflow and pending marker; failure leaves the job recoverable.
            self._write_json_atomic(self.runs / job_id / "state.json", {k: v for k, v in prospective.items() if k != "graph"})
            job.update(status="abandoned", message=message, abandonment=disposition)
            return self.public(job)

    def _load_jobs(self):
        for state_path in self.runs.glob("*/state.json"):
            data = read_json(state_path)
            graph = read_json(state_path.parent / "workflow.json")
            if isinstance(data, dict) and isinstance(graph, dict) and data.get("id"):
                data["graph"] = graph
                data.setdefault('comfy_root', str(self.comfy_root))
                data.setdefault('comfy_url', self.comfy_url)
                if data.get("status") in ("queued", "waiting", "submitting", "running", "uncertain"):
                    if submission_evidence.never_submitted(data):
                        data["status"] = "not_submitted"
                        data["message"] = "Restarted before submission. Resume the owning experiment explicitly, or retain the recipe and abandon this local job. Nothing was submitted on restart."
                    else:
                        data["status"] = "uncertain"
                        data["message"] = "Restarted while remote job state was unknown; use Resume observation for known prompt IDs. It was not resubmitted."
                    if "pending_submission" in data and data.get("prompt_ids"):
                        # Restarting a mixed observation must not normalize or
                        # reconstruct its retained recipe/workflow source files.
                        data["message"] = "Restarted with a mixed batch; check known batch receipts or explicitly record a local disposition. The unknown submission was not repeated."
                        self._write_json_atomic(state_path, {k: v for k, v in data.items() if k != "graph"})
                    else:
                        self._save(data)
                self.jobs[data["id"]] = data

    def _request(self, path, method="GET", data=None, timeout=15, base_url=None):
        body = json.dumps(data).encode() if data is not None else None
        req = Request((base_url or self.comfy_url) + path, data=body, method=method, headers={"Content-Type": "application/json"} if body else {})
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

    def worker_available(self):
        worker = getattr(self, 'worker', None)
        return worker is None or worker.ident is None or worker.is_alive()

    def require_worker(self):
        if getattr(self, "reference_jobs", None): self.reference_jobs.require_available()
        # Preserve pre-start/offline fixture behavior; never replace a dead worker
        # or silently replay its queue. All queue writers share this admission.
        if not Studio.worker_available(self):
            raise StudioError('Studio worker is unavailable. Restart Studio; no work was queued or reserved.')

    def health(self, refresh=False):
        worker_alive = self.worker_available()
        worker_failure = copy.deepcopy(self.worker_failure)
        try:
            stats = self._request("/system_stats", timeout=3)
            try: info = self.node_info(refresh); info_available = isinstance(info, dict)
            except (URLError, HTTPError, TimeoutError, OSError, json.JSONDecodeError): info, info_available = {}, False
            missing = {}; observations = {}
            assets = self.library.manifest().get('assets', [])
            from model_requirements import model_selection
            for preset in self.catalog()["presets"]:
                try:
                    graph, _ = self.graph_for(preset)
                    for requirement in self.preset_requirements(preset, graph, assets=assets, observations=observations):
                        if requirement['present'] is not True:
                            label = requirement['file'] if requirement['present'] is False else 'Unresolved dependency: ' + requirement['file'] + ' — ' + requirement['note']
                            missing.setdefault(preset.get('id'), []).append(label)
                    # One endpoint's schema cannot speak for another backend family.
                    if hasattr(self, 'backends') and preset.get('backend_id', 'primary') != self.backends.active: continue
                    for node in graph.values():
                        class_info = info.get(node.get("class_type"), {})
                        if info_available and node.get("class_type") not in info:
                            missing.setdefault(preset.get("id"), []).append(f"node class {node.get('class_type')}")
                            continue
                        options = (class_info.get("input", {}).get("required", {}) | class_info.get("input", {}).get("optional", {}))
                        for field, value in node.get("inputs", {}).items():
                            choice = options.get(field)
                            enum = choice[0] if isinstance(choice, list) and choice and isinstance(choice[0], list) else choice[1].get("options") if isinstance(choice, list) and len(choice) > 1 and isinstance(choice[1], dict) and choice[0] == "COMBO" else None
                            if (field.endswith("_name") or model_selection(node.get("class_type"), field, value)) and isinstance(value, str) and isinstance(enum, list) and value not in enum:
                                missing.setdefault(preset.get("id"), []).append(value)
                except (ValueError, OSError, AttributeError, TypeError) as exc:
                    missing.setdefault(preset.get('id'), []).append('Dependency inspection unavailable: ' + str(exc)[:250])
            missing = {key: list(dict.fromkeys(values)) for key, values in missing.items()}
            return {"app": "local-asset-studio", "workspace": str(self.root), "online": True, "schema_available": info_available, "missing_models": missing, "system": stats.get("system", {}), "devices": stats.get("devices", []), "comfy_url": self.comfy_url, "worker_alive": worker_alive, "degraded": not worker_alive or worker_failure is not None, "worker_failure": worker_failure, "recovery": self.runtime_recovery.snapshot(), "host_commit": self.host_commit_reading()}
        except (URLError, HTTPError, TimeoutError, OSError, json.JSONDecodeError): return {"app": "local-asset-studio", "workspace": str(self.root), "online": False, "missing_models": {}, "worker_alive": worker_alive, "degraded": not worker_alive or worker_failure is not None, "worker_failure": worker_failure, "recovery": self.runtime_recovery.snapshot(), "host_commit": self.host_commit_reading()}

    def inspect_preset(self, preset_id, graph=None):
        preset = self.preset(preset_id)
        if graph is None: graph, _ = self.graph_for(preset)
        return {"id": preset_id, "requirements": self.preset_requirements(preset, graph),
                "nodes": [{"id": key, "type": node.get("class_type")} for key, node in graph.items()], "graph": graph}

    def preset_requirements(self, preset, graph, *, assets=None, observations=None):
        from model_requirements import requirements
        model_root = self.library.models
        if hasattr(self, 'backends'):
            model_root = Path(self.backends.profiles[preset.get('backend_id', 'primary')]['root']) / 'models'
        return requirements(self.library, preset, graph, model_root, assets=assets, observations=observations)

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

    def _wait_for_queue(self, base_url=None):
        deadline = time.monotonic() + PRE_SUBMIT_QUEUE_WAIT_SECONDS
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0: raise QueueWaitUnavailable("ComfyUI's queue is still busy or its idle check expired")
            try: data = self._request("/queue", timeout=min(10, remaining), base_url=base_url)
            except (URLError, HTTPError, TimeoutError, OSError, ValueError, UnicodeError, HTTPException) as exc:
                raise QueueWaitUnavailable("Could not inspect ComfyUI's queue: " + str(exc)[:250]) from exc
            # Missing/invalid collections are not evidence that the queue is idle.
            if not isinstance(data, dict) or any(type(data.get(key)) is not list for key in ("queue_running", "queue_pending")):
                raise QueueWaitUnavailable("Could not inspect ComfyUI's queue: invalid queue response")
            remaining = deadline - time.monotonic()
            if remaining <= 0: raise QueueWaitUnavailable("ComfyUI's queue idle check expired")
            if not data["queue_running"] and not data["queue_pending"]: return
            time.sleep(min(2, remaining))

    def record_job_failure(self, job, exc):
        """Unexpected local failure cannot certify an unobserved remote outcome."""
        with self.lock:
            # A failed persistence of the pre-submit queue timeout still proves no POST.
            if job.get('status') == 'not_submitted' and submission_evidence.never_submitted(job):
                self._save(job); return
            if job.get('status') not in ('abandoned', 'completed', 'partial', 'failed'):
                uncertain = 'pending_submission' in job or bool(job.get('prompt_ids')) or bool(job.get('submissions'))
                job['status'] = 'uncertain' if uncertain else 'failed'
                job['message'] = ('Local processing failed; remote outcome requires inspection. Nothing was resubmitted: ' if uncertain else 'Generation failed before submission: ') + str(exc)[:300]
            self._save(job)

    def _work(self):
        while True:
            action, job_id = self.queue.get()
            mixed_request = None
            job = None
            try:
                if action == "observe-mixed": job_id, mixed_request = job_id
                if action == "reference-analysis": self.reference_jobs.run(job_id)
                elif action == 'production':
                    if getattr(self, "reference_jobs", None): self.reference_jobs.require_available()
                    self.production.run(job_id)
                else:
                    job = self.jobs.get(job_id)
                    if job:
                        if action == "observe-mixed": mixed_batch.run(self, job_id, mixed_request)
                        elif action == "observe": self._resume(job)
                        else: self._run(job)
            except Exception as exc:
                try:
                    if action == 'reference-analysis': self.reference_jobs.record_failure(job_id, exc)
                    elif action == 'production':
                        # Escaping here can be a failed job-state write after a POST.
                        # Only normal stage reconciliation can certify a terminal outcome.
                        self.production._mutate(job_id, status='uncertain', message='Coordinator processing or recording failed; inspect retained job evidence before new work: ' + str(exc)[:400])
                    elif job is not None:
                        if action == "observe-mixed": mixed_batch.record_failure(self, job, exc)
                        else: self.record_job_failure(job, exc)
                except Exception as recording_error:
                    # A disk/SQLite/diagnostic error must not end the only queue
                    # consumer. Keep one bounded, explicitly non-durable alert.
                    self.worker_failure = {'action': action, 'id': job_id, 'error': type(exc).__name__,
                                           'recording_error': str(recording_error)[:500], 'durable': False}
                    try: print('Studio worker could not persist failure:', self.worker_failure, file=sys.stderr, flush=True)
                    except Exception: pass

    def _batch_graph(self, job, index):
        graph = copy.deepcopy(job["graph"])
        bindings = job.get("seed_bindings")
        if bindings is None:
            preset = self.preset(job["preset_id"])
            bindings = ([preset["seed"]] if preset.get("seed") else []) + preset.get("bindings_extra", {}).get("seed", [])
        binding = bindings[0] if bindings else None
        seed = None
        if binding:
            try: base = graph[str(binding[0])]["inputs"][str(binding[1])]
            except (KeyError, TypeError, IndexError): raise StudioError("Preset has an invalid seed binding")
            seed = number(base, "seed", 0, 2**63 - 1, True) + index
            if seed > 2**63 - 1: raise StudioError("seed plus batch count exceeds supported range")
            for bound in bindings: self._bind(graph, bound, seed)
        self._expand_prompts(job, graph, seed, index)
        return graph, seed

    def _expand_prompts(self, job, graph, seed, index):
        """Resolve prompt wildcards per batch member; controls keep the template."""
        bindings = job.get("prompt_bindings")
        if bindings is None:
            try: preset = self.preset(job["preset_id"])
            except StudioError: return
            bindings = {key: ([preset[key]] if preset.get(key) else []) + (preset.get("bindings_extra") or {}).get(key, []) for key in ("positive", "negative")}
        rng = random.Random(f"{seed}:{index}")
        try: self._expand_bound_prompts(graph, bindings, rng)
        except ValueError as exc: raise StudioError(str(exc))

    def _expand_bound_prompts(self, graph, bindings, rng):
        for key in ("positive", "negative"):
            for binding in bindings.get(key) or []:
                try: node, field = str(binding[0]), str(binding[1]); text = graph[node]["inputs"][field]
                except (KeyError, TypeError, IndexError): continue
                if not prompting.has_wildcards(text): continue
                graph[node]["inputs"][field] = prompting.expand(text, rng, self.root)

    @staticmethod
    def _finite_number(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

    @staticmethod
    def _execution_failure(detail):
        """Turn a ComfyUI execution error into a cautious, user-facing diagnosis."""
        detail = detail if isinstance(detail, dict) else {}

        def text(name, limit):
            value = detail.get(name)
            return value.strip()[:limit] if isinstance(value, str) and value.strip() else ""

        node_type = text("node_type", 120)
        node_id = text("node_id", 80)
        exception_type = text("exception_type", 160)
        exception_message = text("exception_message", 450)
        combined = " ".join(value for value in (exception_type, exception_message) if value).lower()
        allocation = bool(re.search(r"bad allocation|out of memory|not enough memory|memory allocation|alloc(?:ation)?_failed|alloc_cpu|paging file|os error 1455", combined))

        if allocation:
            kind = "memory_allocation"
            title = "Memory allocation failed"
            if re.search(r"defaultcpuallocator|alloc_cpu|paging file|os error 1455|commit", combined):
                summary = "ComfyUI could not allocate system memory while running the workflow. This is usually host-memory or commit pressure, not an invalid prompt."
                action = "Close other memory-heavy apps and retry only after host memory has recovered; if it repeats, lower the resolution or batch size. The original prompt was not retried automatically."
            elif re.search(r"cuda|hip|device|gpu|vram", combined):
                summary = "ComfyUI could not allocate GPU memory while running the workflow. This is usually VRAM or backend pressure, not an invalid prompt."
                action = "Release or restart ComfyUI memory, then retry with a smaller resolution, batch, or fewer active LoRAs. The original prompt was not retried automatically."
            else:
                summary = "ComfyUI could not allocate memory while running the workflow. This usually indicates GPU/VRAM pressure or a backend allocation problem, not an invalid prompt."
                action = "Release or restart ComfyUI memory, then retry with a smaller resolution, batch, or fewer active LoRAs. The original prompt was not retried automatically."
        else:
            kind = "execution_error"
            title = "ComfyUI execution failed"
            target = node_type or "the workflow"
            summary = f"ComfyUI reported an execution error in {target}. The recipe and prompt ID were retained so the engine detail can be investigated without resubmitting it."
            action = "Check the engine detail below and retry only after correcting the reported workflow or runtime issue. The original prompt was not retried automatically."

        result = {"kind": kind, "title": title, "summary": summary, "action": action,
                  "detail": exception_message or "No engine exception detail was returned."}
        if node_type: result["node_type"] = node_type
        if node_id: result["node_id"] = node_id
        if exception_type: result["exception_type"] = exception_type
        return result

    def _record_history_failure(self, job, submission, message):
        submission["status"] = "failed"; job["status"] = "failed"; job["message"] = message
        started = job.get("started_at")
        finished = job.get("finished_at")
        if not self._finite_number(finished):
            finished = time.time()
            if self._finite_number(finished): job["finished_at"] = finished
        if self._finite_number(started) and self._finite_number(finished) and finished >= started and not self._finite_number(job.get("elapsed_seconds")):
            job["elapsed_seconds"] = finished - started
        self._save(job)

    def _run(self, job):
        if getattr(self, "reference_jobs", None): self.reference_jobs.require_available()
        with self.lock:
            if job.get('status') not in ('queued', 'not_submitted') or not submission_evidence.never_submitted(job):
                raise StudioError('This job is not proven never submitted; reconcile retained evidence without replaying it')
            job['started_at']=time.time()
            job["status"] = "waiting"; job["message"] = "Waiting for existing ComfyUI work"; self._save(job)
        try: return self._run_generation(job)
        finally: self._resource_observation_event('finish', job)

    def _resource_observation_event(self, kind, job, **details):
        observer = getattr(self, 'resource_observations', None)
        if observer is None: return
        # Optional evidence cannot mutate the job or become submission/save authority.
        try: getattr(observer, kind)(job_resources.event_snapshot(kind, job, **details))
        except Exception: pass

    def _run_generation(self, job):
        try: self._wait_for_queue(job.get('comfy_url'))
        except QueueWaitUnavailable as exc:
            with self.lock:
                job['status'] = 'not_submitted'
                recovery = 'Resume the owning experiment explicitly after checking the queue, or abandon this local job.' if job.get('project_id') else 'You can abandon this local job; its recipe is retained.'
                job['message'] = str(exc) + '. Nothing was submitted. No retry was queued. ' + recovery
                self._save(job)
            return
        for i in range(job["batch_count"]):
            graph, seed = self._batch_graph(job, i)
            try:
                try:preset=self.preset(job['preset_id'])
                except StudioError:preset={}
                continuation.validate(self, job, preset, graph, check_runtime=True)
                wan_capacity.enforce(graph)
                reading=self.host_commit_preflight(preset, graph, refresh=True)
            except (StudioError, ValueError, OSError) as exc:
                job['status']='partial' if job.get('prompt_ids') else 'failed';job['message']=str(exc)+'. No prompt was submitted for output '+str(i+1)+'.';self._save(job);return
            if reading:
                job.setdefault('host_commit_readings',[]).append(dict(reading, phase='pre-submit', index=i, recorded_at=time.time()))
            job["status"] = "submitting"; job["message"] = f"Submitting output {i + 1} of {job['batch_count']}"; job["pending_submission"] = {"index": i, "seed": seed, "graph": graph, "marked_at": time.time()}; self._save(job)
            self._resource_observation_event('intent', job, index=i, graph=graph)
            try: response = self._request("/prompt", "POST", {"prompt": graph, "client_id": "asset-studio"}, timeout=30, base_url=job.get('comfy_url'))
            except HTTPError as exc:
                with exc:
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
            except (URLError, TimeoutError, OSError, json.JSONDecodeError, UnicodeDecodeError, HTTPException) as exc:
                job["status"] = "uncertain"; job["message"] = "Submission outcome is uncertain and will not be retried automatically."; self._save(job); return
            prompt_id = response.get("prompt_id") if isinstance(response, dict) else None
            if not isinstance(response, dict) or not isinstance(prompt_id, str) or not prompt_id.strip():
                job['status']='uncertain';job['message']='No prompt ID was returned. Submission intent is retained and will not be retried.';self._save(job);return
            self._resource_observation_event('accepted', job, index=i, prompt_id=prompt_id)
            submission = {"index": i, "prompt_id": prompt_id, "seed": seed, "graph": graph, "status": "observing"}
            job["prompt_ids"].append(prompt_id); job.setdefault("submissions", []).append(submission); job.pop("pending_submission", None); job["status"] = "running"; job["message"] = f"Generating output {i + 1} of {job['batch_count']}"; self._save(job)
            if not self._wait_history(job, submission): return
        job["status"] = "completed"; job["message"] = "Complete"
        job['finished_at']=time.time();job['elapsed_seconds']=job['finished_at']-job['started_at'];self._save(job)

    def _prompt_listed(self, job, prompt_id):
        """True unless ComfyUI's queue proves the prompt is neither running nor pending; unreadable means listed."""
        try: data = self._request("/queue", timeout=10, base_url=job.get('comfy_url'))
        except (URLError, HTTPError, TimeoutError, OSError, ValueError, UnicodeError, HTTPException): return True
        if not isinstance(data, dict): return True
        for key in ("queue_running", "queue_pending"):
            entries = data.get(key)
            if not isinstance(entries, list): return True
            for entry in entries:
                if not isinstance(entry, (list, tuple)) or len(entry) < 2: return True  # unrecognized shape: assume listed
                if entry[1] == prompt_id: return True
        return False

    def _wait_history(self, job, submission):
        prompt_id = submission["prompt_id"]
        deadline = time.monotonic() + HISTORY_OBSERVATION_SECONDS; empty_polls = 0; unlisted = 0
        while time.monotonic() < deadline:
            with self.lock:
                if self._tracking_stopped(job): return False
            try:
                response = self._request("/history/" + quote(prompt_id, safe=''), timeout=15, base_url=job.get('comfy_url'))
                if not isinstance(response, dict): raise ValueError('Invalid history response')
                history = response.get(prompt_id)
                if history is not None and not isinstance(history, dict): raise ValueError('Invalid prompt history')
            except (URLError, HTTPError, TimeoutError, OSError, ValueError, UnicodeError, HTTPException):
                with self.lock:
                    if self._tracking_stopped(job): return False
                    job["status"] = "uncertain"; job["message"] = "Could not observe a known ComfyUI prompt. Use Resume observation when ComfyUI is available."; self._save(job)
                return False
            if history:
                status = history.get("status", {})
                if status.get("status_str") == "error":
                    errors = [m[1] for m in status.get("messages", []) if isinstance(m, list) and len(m) > 1 and m[0] == "execution_error" and isinstance(m[1], dict)]
                    detail = errors[-1] if errors else {}
                    submission["status"] = "failed"
                    job["failure"] = self._execution_failure(detail)
                    detail_text = f"{detail.get('node_type', '')}: {detail.get('exception_message', '')}".strip(': ')
                    message = "ComfyUI reported an execution error" + (": " + detail_text[:450] if detail_text else "")
                    self._record_history_failure(job, submission, message)
                    raise StudioError(message)
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
            empty_polls += 1
            if empty_polls % HISTORY_QUEUE_CHECK_EVERY == 0:
                # A prompt in neither the queue nor the history is gone (restart, cleared queue); do not wait out the ceiling.
                unlisted = 0 if self._prompt_listed(job, prompt_id) else unlisted + 1
                if unlisted >= HISTORY_UNLISTED_STRIKES:
                    with self.lock:
                        if self._tracking_stopped(job): return False
                        job["status"] = "uncertain"; job["message"] = "ComfyUI no longer lists this prompt in its queue or history (a restart or a cleared queue); it was not resubmitted. Inspect the runtime, then use Resume observation or Stop tracking."; self._save(job)
                    return False
            time.sleep(2)
        with self.lock:
            if self._tracking_stopped(job): return False
            job["status"] = "uncertain"; job["message"] = "Timed out while observing ComfyUI; it was not resubmitted."; self._save(job)
        return False

    def resume_job(self, job_id):
        with self.lock:
            if self.backends.busy: raise StudioError('Wait for the backend switch to finish')
            return self._queue_observation(job_id)

    def _queue_observation(self, job_id):
        self.require_worker()
        job = self.jobs.get(job_id)
        if not job: raise StudioError("Unknown job")
        if job.get('status') == 'abandoned' or 'pending_submission' in job:
            raise StudioError('An abandoned or unknown submission cannot be resumed as a known prompt')
        if self._tracking_stopped(job): return self._resume_tracking(job)
        if job.get("status") in ("queued", "waiting", "submitting", "running"): raise StudioError("This job is already queued or being observed; wait for it to settle")
        pending = [s for s in job.get("submissions", []) if s.get("status") != "completed" and s.get("prompt_id")]
        # Every retained receipt terminal: _resume reconciles the job's own status without any ComfyUI request.
        if not pending and not (job.get("submissions") and job.get("status") in ("uncertain", "partial")): raise StudioError("No known prompt IDs are available to resume")
        if not pending: job["reconciliation"] = {"status": job.get("status"), "message": job.get("message")}  # what the queued reconciliation started from
        job["status"] = "queued"; job["message"] = "Queued to resume observation; no image will be resubmitted."; self._save(job); self.queue.put(("observe", job_id)); return self.public(job)

    def _resume(self, job):
        with self.lock:
            if self._tracking_stopped(job): return
            if job.get('status') == 'abandoned' or 'pending_submission' in job:
                raise StudioError('An abandoned or unknown submission cannot be resumed as a known prompt')
            prior = job.pop("reconciliation", None) or {}
            prior_status, prior_message = prior.get("status", job.get("status")), prior.get("message", job.get("message"))
            unresolved = any(s.get("status") != "completed" for s in job.get("submissions", []))
            job["status"] = "running"; job["message"] = "Resuming observation of known ComfyUI prompt IDs"; self._save(job)
        for submission in job.get("submissions", []):
            if submission.get("status") != "completed" and not self._wait_history(job, submission): return
        observed = len(job.get("submissions", []))
        if observed < job["batch_count"]:
            status = "partial"; message = f"Observed {observed} of {job['batch_count']} requested images. Remaining images were not submitted; start a new job for those."
        else:
            status = "completed"; message = "Complete"
        if not unresolved:
            # Pure reconciliation of terminal receipts: index what was never indexed and keep the
            # recorded reason when the status does not change (a gate refusal explains a partial).
            self.index_outputs(job)
            message = prior_message if status == prior_status and prior_message else "Reconciled from retained receipts: " + message
        job["status"] = status; job["message"] = message
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
    def end_headers(self):
        # One response boundary covers static, JSON, ranged/proxied media and
        # inherited error responses without changing their body or MIME contract.
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "frame-ancestors 'none'")
        super().end_headers()

    studio: Studio = None
    def log_message(self, fmt, *args): pass
    def _json(self, status, obj):
        raw = json.dumps(obj).encode(); self.send_response(status); self.send_header("Content-Type", "application/json"); self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
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
    def _media(self, descriptor, job=None):
        query = urlencode({k:descriptor[k] for k in ("filename", "subfolder", "type") if descriptor.get(k) is not None})
        headers = {}
        requested_range = self.headers.get("Range")
        if requested_range:
            if not re.fullmatch(r"bytes=(?:\d+-\d*|-\d+)", requested_range):
                raise StudioError("A single valid byte range is required")
            headers["Range"] = requested_range
        request = Request((job or {}).get('comfy_url', self.studio.comfy_url) + "/view?" + query, headers=headers)
        try: response = urlopen(request, timeout=30)
        except HTTPError as exc:
            if exc.code != 416: raise
            with exc:
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
    def _asset_query_scope(self):
        scopes = parse_qs(urlparse(self.path).query, keep_blank_values=True).get("workspace_id")
        if scopes is None:
            return None
        if len(scopes) != 1:
            raise WorkspaceError("Supply exactly one Workspace identity")
        return scopes[0]

    def do_GET(self):
        if not self._safe_host(): return self._json(403, {"error":"Loopback Host required"})
        try:
            path = urlparse(self.path).path
            if path == "/api/identity": return self._json(200, self.studio.identity())
            if path == '/api/backends':
                result=self.studio.backends.snapshot();result['recovery']=self.studio.runtime_recovery.snapshot();return self._json(200,result)
            if path == "/api/workspace": return self._json(200, self.studio.assets.snapshot())
            if path.startswith("/api/assets/commands/") and len(path.split("/")) == 5:
                return self._json(200, self.studio.assets.command_status(path.split("/")[4], self._asset_query_scope()))
            if path.startswith("/api/assets/") and path.endswith("/metadata") and len(path.split("/")) == 5:
                return self._json(200, self.studio.assets.metadata(path.split("/")[3], self._asset_query_scope()))
            if path == "/api/setups": return self._json(200, self.studio.assets.setups())
            if path == '/api/production': return self._json(200,self.studio.production.list())
            if path.startswith('/api/production/campaigns/') and len(path.split('/'))==5:
                return self._json(200,self.studio.production.edit_campaign(path.split('/')[4]))
            if path == '/api/voice-baseline':
                from voice_baseline import capabilities
                return self._json(200,{'capabilities':capabilities(self.studio),'projects':[p for p in self.studio.production.list() if p['kind']=='voice']})
            if path=='/api/av':return self._json(200,self.studio.production.av.list())
            if path.startswith('/api/av/'):
                parts=path.split('/')
                if len(parts)==6 and parts[4]=='sources':return self._local_file(self.studio.production.av.source(parts[3],parts[5]))
                if len(parts)==4:return self._json(200,self.studio.production.av.inspect(parts[3]))
                raise StudioError('Unknown scene route')
            if path.startswith('/api/production/'):
                from urllib.parse import unquote
                parts=path.split('/')
                if len(parts)>=6 and parts[4]=='files':return self._local_file(self.studio.production.file(parts[3],unquote('/'.join(parts[5:]))),urlparse(self.path).query=='download')
                return self._json(200,self.studio.production.get(parts[3],True))
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
            if path.startswith("/api/assets/") and path.endswith("/context") and len(path.split("/")) == 5:
                return self._json(200, continuation.source_context(self.studio, path.split("/")[3]))
            if path == "/api/catalog": return self._json(200, self.studio.catalog())
            if path == "/api/options": return self._json(200, self.studio.options(urlparse(self.path).query == "refresh", True))
            if path == "/api/knowledge": return self._json(200, self.studio.knowledge())
            if path == "/api/recipes": return self._json(200, self.studio.recipes())
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
            if path.startswith("/api/jobs/") and path.endswith("/i2v-diagnostic"):
                job_id = path.split("/")[3]
                return self._json(200, self.studio.i2v_diagnostic(job_id))
            if path.startswith("/api/jobs/") and "/i2v-diagnostic/" in path:
                from urllib.parse import unquote
                parts = path.split("/")
                if len(parts) != 6 or parts[4] != "i2v-diagnostic": raise StudioError("Unknown diagnostic artifact")
                return self._local_file(self.studio.i2v_diagnostic_file(parts[3], unquote(parts[5])))
            if path.startswith("/api/jobs/"):
                job = self.studio.jobs.get(path.rsplit("/", 1)[-1]); return self._json(200, self.studio.public(job)) if job else self._json(404, {"error":"Unknown job"})
            if path.startswith("/api/image/"):
                _, _, _, job_id, index = path.split("/"); job = self.studio.jobs.get(job_id); image = job and job.get("outputs", [])[int(index)]
                if not image: return self._json(404, {"error":"Unknown image"})
                if image.get("asset_id"): return self._local_file(self.studio.assets.file(image["asset_id"]))
                return self._media(image, job)
            if path == "/": path = "/index.html"
            if path.startswith("/static/"): path = path[7:]
            file = inside(Path(__file__).parent / "static", Path(__file__).parent / "static" / path.lstrip("/"))
            if not file.is_file() or file.suffix not in (".html", ".js", ".css"): return self._json(404, {"error":"Not found"})
            data = file.read_bytes(); self.send_response(200); self.send_header("Content-Type", mimetypes.guess_type(str(file))[0] or "application/octet-stream"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
        except WorkspaceError as exc: self._json(exc.status, exc.response())
        except (StudioError, ValueError, IndexError) as exc: self._json(400, {"error": str(exc)})
        except (URLError, HTTPError, OSError) as exc: self._json(502, {"error": "ComfyUI image is unavailable"})
    def do_POST(self):
        if not self._safe_mutation(): return self._json(403, {"error":"Local same-origin request required"})
        try:
            if self.path == "/api/estimate": return self._json(200, self.studio.estimate(self._body_json()))
            if self.path == "/api/jobs": return self._json(201, self.studio.create_job(self._body_json()))
            if self.path == '/api/backends/switch': return self._json(202, self.studio.backends.switch(self._body_json().get('id')))
            if self.path == '/api/runtime-recovery/retry': return self._json(202, self.studio.runtime_recovery.reset())
            if self.path == '/api/articulated': return self._json(201,self.studio.production.articulated(self._body_json()))
            if self.path == '/api/assets/import':
                size=self._content_length(20*1024*1024)
                return self._json(201,self.studio.import_image(self.headers.get('X-Filename','reference'),self.headers.get('Content-Type',''),self.rfile.read(size)))
            if self.path == "/api/preview": return self._json(200, self.studio.preview(self._body_json()))
            if self.path == '/api/av':return self._json(201,self.studio.production.av.create(self._body_json()))
            if self.path == '/api/voice-baseline':return self._json(201,self.studio.production.voice_baseline(self._body_json()))
            if self.path.startswith('/api/av/'):
                parts=self.path.split('/')
                if len(parts)!=4:raise StudioError('Unknown scene command route')
                return self._json(200,self.studio.production.av.command(parts[3],self._body_json()))
            if self.path == '/api/production':return self._json(201,self.studio.production.create(self._body_json()))
            if self.path == '/api/production/campaigns':return self._json(201,self.studio.production.register_edit_campaign(self._body_json()))
            if self.path == '/api/production-export':return self._json(201,self.studio.production.native(self._body_json()))
            if self.path == '/api/experiments/plan': return self._json(200, self.studio.production.plan(self._body_json()))
            if self.path.startswith('/api/production/'):
                parts=self.path.split('/');payload=self._body_json();identifier=parts[3]
                if parts[-1]=='start':return self._json(202,self.studio.production.start(identifier))
                if parts[-1]=='stop':return self._json(200,self.studio.production.stop(identifier))
                if parts[-1]=='resume':return self._json(202,self.studio.production.resume(identifier))
                if parts[-1]=='extend-time':
                    if len(parts)!=5:raise StudioError('Unknown time extension route')
                    return self._json(200,self.studio.production.extend_time(identifier,payload))
                if parts[-1]=='review':return self._json(200,self.studio.production.review(identifier,payload))
            if self.path == "/api/references/check": return self._json(200, self.studio.reference_status(self._body_json()))
            if self.path == "/api/assets/update":
                try: return self._json(200, self.studio.assets.update(self._body_json()))
                except sqlite3.Error:
                    return self._json(503, {"error": "Asset storage could not confirm this request. Check its receipt before retrying the exact command.",
                                            "code": "asset_storage_unconfirmed"})
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
            if self.path.startswith("/api/jobs/") and self.path.endswith(("/observe-known", "/dispose-mixed")):
                parts = self.path.split('/')
                if len(parts) != 5: raise StudioError('Unknown mixed batch route')
                action = 'observe' if parts[4] == 'observe-known' else 'dispose'
                result = mixed_batch.command(self.studio, parts[3], action, self._body_json())
                return self._json(202 if action == 'observe' else 200, result)
            if self.path.startswith("/api/jobs/") and self.path.endswith("/abandon"):
                parts = self.path.split('/')
                if len(parts) != 5: raise StudioError('Unknown abandonment route')
                payload = self._body_json()
                if not isinstance(payload, dict): raise StudioError('Abandonment command must be an object')
                return self._json(200, self.studio.abandon_job(parts[3], payload.get('reason'), payload.get('acknowledge_unknown', False)))
            if self.path.startswith("/api/jobs/") and self.path.endswith("/stop-tracking"):
                return self._json(200, self.studio.stop_tracking(self.path.split("/")[3], self._body_json().get("reason")))
            if self.path == "/api/upload":
                size = self._content_length(20 * 1024 * 1024); return self._json(201, self.studio.upload(self.headers.get("X-Filename", "reference"), self.headers.get("Content-Type", ""), self.rfile.read(size)))
            return self._json(404, {"error":"Not found"})
        except WorkspaceError as exc: self._json(exc.status, exc.response())
        except (StudioError, ValueError, json.JSONDecodeError) as exc: self._json(400, {"error": str(exc)})
        except OSError as exc: self._json(500, {"error": "Local operation failed: " + str(exc)[:200]})

def create_server(repo_root, host=HOST, port=PORT, http_server=ThreadingHTTPServer, studio_factory=Studio):
    """Bind the loopback port before creating a Studio worker or queue."""
    handler = extend_handler(Handler)
    http = http_server((host, port), handler)
    try: handler.studio = studio_factory(Path(repo_root))
    except Exception:
        http.server_close(); raise
    return http

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--repo-root", "--root", dest="repo_root", default=str(Path(__file__).parents[1])); args = parser.parse_args()
    with create_server(args.repo_root) as http:
        print(f"Asset Studio ready: http://{HOST}:{PORT}/ (Prompt Lab: /prompt-lab.html)", flush=True)
        http.serve_forever()
if __name__ == "__main__": main()
