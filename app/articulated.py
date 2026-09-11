"""Production-operation boundary for the fixed authored articulated-prop adapter."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re
import sys
import time
import uuid
import zipfile


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
import articulated_prop


VERSION = "articulated-operation.v1"
OPERATION = "native.articulated-prop.v1"
PROJECT_ID = re.compile(r"[0-9a-f]{32}")
RENDER_NAMES = ("closed", "open", "front", "side")


class ArticulatedOperationError(ValueError):
    """The durable native-articulated operation cannot safely proceed."""


def require(condition, message):
    if not condition:
        raise ArticulatedOperationError(message)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_safe(value, label):
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise ArticulatedOperationError(f"Invalid {label}") from exc


def _write_json(path, value):
    path = Path(path)
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _configured_blender(studio):
    configured = getattr(studio, "config", {}).get("blender")
    require(isinstance(configured, str) and configured, "A configured Blender executable is required")
    runtime = articulated_prop.preflight(configured)
    return {"path": runtime["path"], "sha256": runtime["sha256"]}


def prepare(studio, payload):
    """Validate an explicit authored-prop request without creating files or starting Blender."""
    require(isinstance(payload, dict), "Articulated prop intent must be an object")
    require(set(payload) <= {"name", "options"}, "Articulated props accept only name and numeric options")
    name = payload.get("name")
    require(isinstance(name, str) and 1 <= len(name.strip()) <= 120, "Name the articulated prop (1–120 characters)")
    options = articulated_prop.normalize_options(payload.get("options", {}))
    blender = _configured_blender(studio)
    plan = {"version": 1, "operation": OPERATION, "adapter_version": VERSION,
            "intent": {"name": name.strip(), "kind": "authored-stylized-chest"},
            "options": options, "blender": blender,
            "no_comfy_submission": True,
            "outputs": ["chest.blend", "chest.glb", "metadata.json",
                        *(f"views/{name}.png" for name in RENDER_NAMES)]}
    plan["sha256"] = fingerprint(plan)
    return _json_safe(plan, "prepared plan")


def _validate_project_id(project_id):
    require(isinstance(project_id, str) and PROJECT_ID.fullmatch(project_id) is not None, "Invalid project ID")
    return project_id


def _validate_plan(studio, plan):
    require(isinstance(plan, dict), "Articulated plan must be an object")
    required = {"version", "operation", "adapter_version", "intent", "options", "blender", "no_comfy_submission", "outputs", "sha256"}
    require(set(plan) == required, "Articulated plan shape changed")
    copy_plan = {key: value for key, value in plan.items() if key != "sha256"}
    require(plan["sha256"] == fingerprint(copy_plan), "Articulated plan hash mismatch")
    require(plan["version"] == 1 and plan["operation"] == OPERATION and plan["adapter_version"] == VERSION,
            "Unsupported articulated plan")
    require(plan["no_comfy_submission"] is True, "Articulated plans never submit to ComfyUI")
    intent = plan["intent"]
    require(isinstance(intent, dict) and set(intent) == {"name", "kind"} and intent["kind"] == "authored-stylized-chest"
            and isinstance(intent["name"], str) and 1 <= len(intent["name"]) <= 120, "Invalid articulated intent")
    option_fields = {"width", "depth", "body_height", "lid_height", "clearance", "render_size", "samples"}
    require(isinstance(plan["options"], dict) and set(plan["options"]) == option_fields | {"fps", "open_degrees", "keyframes"},
            "Articulated options changed")
    require(plan["options"] == articulated_prop.normalize_options({key: plan["options"][key] for key in option_fields}),
            "Articulated options changed")
    require(plan["outputs"] == ["chest.blend", "chest.glb", "metadata.json", *(f"views/{name}.png" for name in RENDER_NAMES)],
            "Articulated output contract changed")
    configured = _configured_blender(studio)
    require(plan["blender"] == configured, "Configured Blender changed; prepare a new plan")
    return copy.deepcopy(plan)


def _project_directory(studio, project_id):
    experiments = Path(studio.experiments).resolve()
    directory = (experiments / "projects" / project_id).resolve()
    require(directory.is_relative_to(experiments), "Project path escapes experiments")
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _public_record(project_id, directory, path, role, asset_id=None):
    path = Path(path).resolve()
    require(path.is_relative_to(directory) and path.is_file(), "Native artifact is unavailable")
    relative = path.relative_to(directory).as_posix()
    result = {"path": relative, "url": f"/api/production/{project_id}/files/{relative}",
              "sha256": file_sha(path), "bytes": path.stat().st_size, "role": role}
    if asset_id:
        result["asset_id"] = asset_id
    return result


def _write_export(directory):
    source = directory / "articulated"
    recipe = directory / "recipe.json"
    target = directory / "export.zip"
    require(not target.exists(), "Articulated export already exists")
    names = ["chest.blend", "chest.glb", "metadata.json", *(f"views/{name}.png" for name in RENDER_NAMES)]
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            path = source / name
            require(path.is_file(), f"Missing native artifact: {name}")
            archive.write(path, name)
        archive.write(recipe, "recipe.json")
    return target


def _native_job(project_id, plan):
    job_id = uuid.uuid5(uuid.NAMESPACE_URL, f"asset-studio:{project_id}:{OPERATION}").hex
    outputs = [{"filename": "chest.glb", "media_type": "mesh", "source": {"operation": OPERATION, "role": "animated-glb"}}]
    outputs.extend({"filename": f"{name}.png", "media_type": "image", "source": {"operation": OPERATION, "role": f"inspection-{name}"}}
                   for name in RENDER_NAMES)
    return {"id": job_id, "status": "running", "operation": OPERATION, "prompt_ids": [], "submissions": [],
            "created_at": time.time(), "preset_id": "articulated-prop", "preset_name": plan["intent"]["name"],
            "parent_assets": [], "outputs": outputs, "project_id": project_id,
            "message": "Running the fixed CPU Blender articulated-prop operation; no ComfyUI prompt was submitted."}


def _register(studio, job, source, index):
    asset_id = studio.assets.register(job, index, source)
    require(asset_id is not None, "Native artifact could not be snapshotted")
    job["outputs"][index]["asset_id"] = asset_id
    return asset_id


def run(studio, project_id, plan):
    """Execute the exactly-once native operation and retain every output or failure file."""
    project_id = _validate_project_id(project_id)
    plan = _validate_plan(studio, plan)
    directory = _project_directory(studio, project_id)
    target = directory / "articulated"
    receipt_path = directory / "articulated-job.json"
    require(not target.exists() and not receipt_path.exists(), "An articulated attempt already exists; its files are retained")
    _write_json(directory / "recipe.json", {"operation": OPERATION, "adapter_version": VERSION,
                                              "intent": plan["intent"], "options": plan["options"], "blender": plan["blender"],
                                              "plan_sha256": plan["sha256"]})
    job = _native_job(project_id, plan)
    _write_json(receipt_path, job)
    try:
        result = articulated_prop.execute(target, plan["options"], blender_path=plan["blender"]["path"])
        metadata = result["metadata"]
        require(metadata.get("render", {}).get("device") == "CPU" and metadata["render"].get("threads") == 4,
                "Articulated operation did not retain the CPU render contract")
        sources = [target / "chest.glb", *(target / "views" / f"{name}.png" for name in RENDER_NAMES)]
        asset_ids = [_register(studio, job, source, index) for index, source in enumerate(sources)]
        export = _write_export(directory)
        job.update(status="completed", finished_at=time.time(), message="Native Blender operation completed; no ComfyUI prompt was submitted.",
                   metadata=metadata, asset_ids=asset_ids)
        _write_json(receipt_path, job)
        artifacts = [_public_record(project_id, directory, export, "native-export")]
        artifacts.extend(_public_record(project_id, directory, source, "animated-glb" if index == 0 else "inspection-render",
                                        asset_ids[index]) for index, source in enumerate(sources))
        artifacts.extend([_public_record(project_id, directory, target / "metadata.json", "native-metadata"),
                          _public_record(project_id, directory, directory / "recipe.json", "native-recipe")])
        return {"job": _json_safe(job, "job receipt"), "artifacts": artifacts,
                "measurements": metadata.get("render", {}), "limitations": metadata.get("limitations", [])}
    except Exception as exc:
        job.update(status="failed", finished_at=time.time(), message=str(exc)[:500], failure_files=True)
        _write_json(receipt_path, job)
        return {"job": _json_safe(job, "job receipt"), "artifacts": [], "measurements": {},
                "limitations": ["The failed owned attempt directory is retained; create a new project to retry."]}
