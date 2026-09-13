"""Offline diagnostics for recorded image-to-video jobs.

This module deliberately has no ComfyUI submission path.  It reads a recorded
Studio job, its local output and input files, and the local canonical graph.
Frame extraction is an inspection operation; it never calls ``/prompt``.
"""
from __future__ import annotations

import hashlib
import json
import math
import mimetypes
import re
import shutil
import struct
import subprocess
import time
import uuid
from pathlib import Path

from PIL import Image, ImageDraw


DEFAULT_SAMPLE_FRAMES = (0, 1, 4, 8, 16, 32, 48, 64, 80)
MODEL_SUFFIXES = {".safetensors", ".gguf", ".pt", ".pth", ".onnx"}
MODEL_FOLDERS = {
    "unet_name": "diffusion_models",
    "clip_name": "text_encoders",
    "vae_name": "vae",
    "lora_name": "loras",
    "head": "inpaint",
}
CANONICAL_WORKFLOW_URL = (
    "https://github.com/comfyanonymous/ComfyUI_examples/blob/master/"
    "wan22/image_to_video_wan22_5B.json"
)
CANONICAL_SOURCE_URL = (
    "https://github.com/comfyanonymous/ComfyUI_examples/blob/master/"
    "chroma/fennec_girl_hug.png"
)


def _read_json(path: Path, fallback=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback


def _write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ratio(width, height):
    return round(width / height, 6) if width and height else None


def _orientation(width, height):
    if width == height:
        return "square"
    return "landscape" if width > height else "portrait"


def centered_crop_plan(source_width, source_height, target_width, target_height):
    """Reproduce common_upscale's center crop dimensions and offsets.

    ComfyUI computes the crop in the original tensor and then calls
    ``torch.nn.functional.interpolate(..., mode='bilinear')``.  Keeping this
    calculation here makes the report auditable even when the optional local
    image renderer is unavailable.
    """
    old_aspect = source_width / source_height
    new_aspect = target_width / target_height
    x = y = 0
    if old_aspect > new_aspect:
        x = round((source_width - source_width * (new_aspect / old_aspect)) / 2)
    elif old_aspect < new_aspect:
        y = round((source_height - source_height * (old_aspect / new_aspect)) / 2)
    crop_width = source_width - x * 2
    crop_height = source_height - y * 2
    return {
        "source_dimensions": [source_width, source_height],
        "target_dimensions": [target_width, target_height],
        "source_aspect_ratio": _ratio(source_width, source_height),
        "target_aspect_ratio": _ratio(target_width, target_height),
        "crop": "center" if (x or y) else "none",
        "crop_box": [x, y, x + crop_width, y + crop_height],
        "crop_dimensions": [crop_width, crop_height],
        "crop_pixels": {"left": x, "right": x, "top": y, "bottom": y},
        "resample": "bilinear",
        "letterbox": False,
        "stretches_full_source": False,
        "strategy": "center crop then bilinear resample",
    }


def render_preprocessed(source: Path, target: Path, width: int, height: int):
    """Render a diagnostic preview with ComfyUI's crop geometry.

    Pillow's bilinear kernel is used as the portable renderer.  The report
    states this explicitly: the crop box and dimensions match ComfyUI exactly,
    while byte-for-byte pixel parity with PyTorch is not claimed.
    """
    with Image.open(source) as image:
        plan = centered_crop_plan(*image.size, width, height)
        image = image.convert("RGB").crop(tuple(plan["crop_box"]))
        image = image.resize((width, height), Image.Resampling.BILINEAR)
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(target, "PNG")
    return plan


def locate_source(studio, name):
    if not isinstance(name, str) or not name:
        return {"filename": name, "candidates": [], "path": None}
    roots = [
        ("upload", studio.experiments / "uploads"),
        ("comfy_input", studio.comfy_root / "input"),
        ("repo_example", studio.root / "examples" / "references"),
    ]
    record = {"filename": name, "candidates": [], "path": None}
    for kind, root in roots:
        root = root.resolve()
        candidate = (root / name).resolve()
        if candidate != root and root not in candidate.parents:
            record["candidates"].append({"kind": kind, "path": str(candidate), "present": False, "error": "candidate escapes its source folder"})
            continue
        present = candidate.is_file()
        item = {"kind": kind, "path": str(candidate), "present": present}
        if present:
            try:
                item.update({"bytes": candidate.stat().st_size, "sha256": sha256_file(candidate)})
            except OSError as exc:
                item["error"] = str(exc)[:200]
        record["candidates"].append(item)
        if present and record["path"] is None:
            record["path"] = str(candidate)
            record["path_kind"] = kind
    return record


def image_metadata(path: Path):
    with Image.open(path) as image:
        image.load()
        width, height = image.size
        return {
            "width": width,
            "height": height,
            "dimensions": [width, height],
            "aspect_ratio": _ratio(width, height),
            "orientation": _orientation(width, height),
            "format": image.format,
            "mode": image.mode,
        }


def _tool(studio, name):
    configured = studio.config.get(name, "") if isinstance(getattr(studio, "config", None), dict) else ""
    if isinstance(configured, str) and configured and Path(configured).is_file():
        return configured
    return shutil.which(name)


def probe_video(studio, video: Path):
    executable = _tool(studio, "ffprobe")
    if not executable:
        return {"available": False, "error": "ffprobe is not configured"}
    command = [
        executable,
        "-v",
        "error",
        "-count_frames",
        "-show_entries",
        "format=filename,size,duration:stream=index,codec_name,width,height,pix_fmt,r_frame_rate,nb_frames,nb_read_frames,bit_rate:format_tags=encoder",
        "-of",
        "json",
        str(video),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
        if result.returncode:
            return {"available": False, "error": result.stderr.strip()[:500] or "ffprobe failed"}
        data = json.loads(result.stdout)
        stream = next((x for x in data.get("streams", []) if x.get("codec_type", "video") == "video"), None)
        if stream is None and data.get("streams"):
            stream = data["streams"][0]
        frames = None
        if stream:
            for key in ("nb_frames", "nb_read_frames"):
                try:
                    frames = int(stream.get(key))
                    break
                except (TypeError, ValueError):
                    pass
        return {"available": True, "format": data.get("format", {}), "stream": stream or {}, "frame_count": frames}
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        return {"available": False, "error": str(exc)[:500]}


def _extract_samples(studio, video: Path, directory: Path, indices):
    executable = _tool(studio, "ffmpeg")
    if not executable:
        return {"available": False, "error": "ffmpeg is not configured", "frames": []}
    directory.mkdir(parents=True, exist_ok=True)
    for old in directory.glob("sample-*.png"):
        old.unlink(missing_ok=True)
    frames, errors = [], []
    for index in indices:
        target = directory / f"sample-{index:03d}.png"
        target.unlink(missing_ok=True)
        command = [
            executable,
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-y",
            "-i",
            str(video),
            "-vf",
            f"select=eq(n\\,{index})",
            "-frames:v",
            "1",
            str(target),
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
            if result.returncode and not target.is_file():
                errors.append({"index": index, "error": result.stderr.strip()[:300] or "ffmpeg failed"})
            elif target.is_file():
                frames.append({"index": index, "path": str(target), "filename": target.name})
            else:
                errors.append({"index": index, "error": "Frame was not present in the video"})
        except (OSError, subprocess.TimeoutExpired) as exc:
            errors.append({"index": index, "error": str(exc)[:300]})
    return {"available": bool(frames), "error": None if not errors else "Some requested frames were unavailable", "frames": frames, "errors": errors}


def _contact_sheet(directory: Path, frames, target: Path):
    if not frames:
        return None
    tile_width, tile_height, label_height = 420, 420, 34
    columns = 3
    rows = math.ceil(len(frames) / columns)
    sheet = Image.new("RGB", (tile_width * columns, (tile_height + label_height) * rows), "#182026")
    draw = ImageDraw.Draw(sheet)
    for position, item in enumerate(frames):
        with Image.open(item["path"]) as image:
            image = image.convert("RGB")
            image.thumbnail((tile_width, tile_height), Image.Resampling.LANCZOS)
            x = (position % columns) * tile_width + (tile_width - image.width) // 2
            y = (position // columns) * (tile_height + label_height) + label_height + (tile_height - image.height) // 2
            sheet.paste(image, (x, y))
        draw.text(((position % columns) * tile_width + 12, (position // columns) * (tile_height + label_height) + 9), f"frame {item['index']}", fill="white")
    target.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(target, "PNG")
    return target


def _safetensors_header(path: Path):
    try:
        size = path.stat().st_size
        with path.open("rb") as stream:
            raw_length = stream.read(8)
            if len(raw_length) != 8:
                raise ValueError("missing safetensors header length")
            header_length = struct.unpack("<Q", raw_length)[0]
            if header_length > size - 8 or header_length > 128 * 1024 * 1024:
                raise ValueError("safetensors header exceeds file bounds")
            header = json.loads(stream.read(header_length).decode("utf-8"))
        data_start = 8 + header_length
        tensor_count = 0
        for name, entry in header.items():
            if name == "__metadata__":
                continue
            if not isinstance(entry, dict) or not isinstance(entry.get("data_offsets"), list) or len(entry["data_offsets"]) != 2:
                raise ValueError("invalid tensor data offsets")
            start, end = entry["data_offsets"]
            if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end < start or data_start + end > size:
                raise ValueError("tensor data offset exceeds file bounds")
            tensor_count += 1
        return {"status": "valid", "header_bytes": header_length, "tensor_count": tensor_count}
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        return {"status": "invalid", "error": str(exc)[:300]}


def _cached_file_hash(path: Path, cache):
    key = str(path)
    try:
        identity = {"bytes": path.stat().st_size, "mtime_ns": path.stat().st_mtime_ns}
    except OSError as exc:
        return {"path": key, "present": False, "error": str(exc)[:200]}
    previous = cache.get(key)
    if isinstance(previous, dict) and all(previous.get(k) == v for k, v in identity.items()) and previous.get("sha256"):
        digest = previous["sha256"]
    else:
        digest = sha256_file(path)
        cache[key] = dict(identity, sha256=digest)
    return {"path": key, "present": True, **identity, "sha256": digest}


def model_records(studio, graph, directory: Path):
    cache_path = directory / "model-hashes.json"
    cache = _read_json(cache_path, {})
    if not isinstance(cache, dict):
        cache = {}
    manifest = _read_json(studio.root / "models/library.json", {"assets": []}) or {"assets": []}
    pins = {}
    for entry in manifest.get("assets", []):
        if isinstance(entry, dict) and isinstance(entry.get("file"), str):
            pins[entry["file"]] = entry
    records, seen = [], set()
    for node in graph.values():
        inputs = node.get("inputs") or {}
        for field, value in inputs.items():
            if not isinstance(value, str) or Path(value).suffix.lower() not in MODEL_SUFFIXES:
                continue
            folder = MODEL_FOLDERS.get(field, "models")
            relative = f"{folder}/{Path(value).name}"
            if relative in seen:
                continue
            seen.add(relative)
            path = (Path(getattr(studio, "comfy_root", "")) / "models" / relative).resolve()
            identity = _cached_file_hash(path, cache) if path.is_file() else {"path": str(path), "present": False}
            pin = pins.get(relative) or next((entry for key, entry in pins.items() if Path(key).name == Path(value).name), None)
            expected_bytes = pin.get("bytes") if pin else None
            expected_hash = pin.get("sha256") if pin else None
            size_matches = bool(identity.get("present") and expected_bytes == identity.get("bytes")) if pin else None
            hash_matches = bool(identity.get("present") and expected_hash and expected_hash.lower() == identity.get("sha256", "").lower()) if pin else None
            record = {
                "filename": Path(value).name,
                "field": field,
                "relative_path": relative,
                "path": str(path),
                "present": bool(identity.get("present")),
                "bytes": identity.get("bytes"),
                "sha256": identity.get("sha256"),
                "expected_bytes": expected_bytes,
                "expected_sha256": expected_hash,
                "size_matches_pin": size_matches,
                "hash_matches_pin": hash_matches,
                "pin_status": "verified" if size_matches and hash_matches else "mismatch" if pin and identity.get("present") else "missing" if pin else "unPinned",
            }
            if identity.get("present") and Path(value).suffix.lower() == ".safetensors":
                record["container_header"] = _safetensors_header(path)
            if pin:
                record["pin_source"] = {key: pin.get(key) for key in ("id", "source", "revision", "url") if pin.get(key) is not None}
            records.append(record)
    _write_json(cache_path, cache)
    return records


def _semantic_value(value, graph):
    if isinstance(value, list) and len(value) == 2 and str(value[0]) in graph and isinstance(value[1], int):
        return {"ref_class": graph[str(value[0])].get("class_type"), "slot": value[1]}
    if isinstance(value, list):
        return [_semantic_value(item, graph) for item in value]
    if isinstance(value, dict):
        return {key: _semantic_value(item, graph) for key, item in value.items()}
    return value


def semantic_graph(graph):
    result = []
    for key, node in graph.items():
        result.append({
            "node_id": str(key),
            "class_type": node.get("class_type"),
            "inputs": {field: _semantic_value(value, graph) for field, value in (node.get("inputs") or {}).items()},
        })
    return result


def graph_diff(actual, canonical):
    """Compare API graphs by node order/class and normalized connections."""
    left, right = semantic_graph(actual), semantic_graph(canonical)
    changes = []
    for index in range(max(len(left), len(right))):
        if index >= len(left):
            changes.append({"kind": "added", "position": index, "canonical_node_id": None, "actual_node_id": right[index]["node_id"], "canonical": None, "actual": right[index]})
            continue
        if index >= len(right):
            changes.append({"kind": "removed", "position": index, "canonical_node_id": left[index]["node_id"], "actual_node_id": None, "canonical": left[index], "actual": None})
            continue
        actual_node, canonical_node = left[index], right[index]
        if actual_node["class_type"] != canonical_node["class_type"]:
            changes.append({"kind": "node_type", "position": index, "canonical_node_id": canonical_node["node_id"], "actual_node_id": actual_node["node_id"], "canonical": canonical_node["class_type"], "actual": actual_node["class_type"]})
        fields = set(actual_node["inputs"]) | set(canonical_node["inputs"])
        for field in sorted(fields):
            actual_value = actual_node["inputs"].get(field)
            canonical_value = canonical_node["inputs"].get(field)
            if actual_value != canonical_value:
                changes.append({"kind": "input", "position": index, "canonical_node_id": canonical_node["node_id"], "actual_node_id": actual_node["node_id"], "class_type": actual_node["class_type"], "field": field, "canonical": canonical_value, "actual": actual_value})
    return changes


def _binding_value(graph, preset, key):
    binding = preset.get(key)
    if not binding:
        return None
    try:
        return graph[str(binding[0])]["inputs"][str(binding[1])]
    except (KeyError, TypeError, IndexError):
        return None


def _node_by_class(graph, class_type):
    return next((node for node in graph.values() if node.get("class_type") == class_type), None)


def _runtime_identity(studio, job):
    root = Path(job.get("comfy_root") or getattr(studio, "comfy_root", ""))
    result = {"comfy_root": str(root), "comfy_url": job.get("comfy_url") or getattr(studio, "comfy_url", None)}
    for relative in ("comfy_extras/nodes_wan.py", "comfy/utils.py"):
        path = root / relative
        if path.is_file():
            result[relative] = {
                "path": str(path),
                "bytes": path.stat().st_size,
                "mtime_ns": path.stat().st_mtime_ns,
                "sha256": sha256_file(path),
            }
    version_path = root / "comfyui_version.py"
    if version_path.is_file():
        version_source = version_path.read_text(encoding="utf-8", errors="replace")
        version_match = re.search(r'__version__\s*=\s*["\']([^"\']+)', version_source)
        result["comfyui_version"] = version_match.group(1) if version_match else None
        result["comfyui_version_source"] = {"path": str(version_path), "sha256": sha256_file(version_path)}
    wan_path = root / "comfy_extras/nodes_wan.py"
    if wan_path.is_file():
        wan_source = wan_path.read_text(encoding="utf-8", errors="replace")
        class_match = re.search(r"^class Wan22ImageToVideoLatent\b", wan_source, re.MULTILINE)
        result["node_implementations"] = {
            "Wan22ImageToVideoLatent": {
                "module": "comfy_extras.nodes_wan",
                "class": "Wan22ImageToVideoLatent",
                "source_path": str(wan_path),
                "source_sha256": sha256_file(wan_path),
                "class_line": wan_source[:class_match.start()].count("\n") + 1 if class_match else None,
                "package_version": None,
                "version_basis": "source hash; the built-in node has no separate package version",
            }
        }
    try:
        completed = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5, check=False)
        if completed.returncode == 0:
            result["git_head"] = completed.stdout.strip()
        described = subprocess.run(["git", "-C", str(root), "describe", "--always", "--dirty"], capture_output=True, text=True, timeout=5, check=False)
        if described.returncode == 0:
            result["git_describe"] = described.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return result


def _artifact_record(path: Path, job_id: str):
    if not path.is_file():
        return {"filename": path.name, "present": False}
    return {
        "filename": path.name,
        "present": True,
        "path": str(path),
        "url": f"/api/jobs/{job_id}/i2v-diagnostic/{path.name}",
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "content_type": mimetypes.guess_type(str(path))[0] or "application/octet-stream",
    }


def build_report(studio, job_id):
    job = studio.jobs.get(job_id)
    if not job:
        raise ValueError("Unknown job")
    outputs = [output for output in job.get("outputs", []) if output.get("media_type") == "video" or Path(output.get("filename", "")).suffix.lower() in {".mp4", ".webm", ".mov"}]
    if not outputs:
        raise ValueError("This job has no recorded video output")
    output = outputs[0]
    video = studio.output_path(output, job)
    if not video.is_file():
        raise ValueError("Recorded video output is unavailable")
    directory = (studio.experiments / "diagnostics" / job_id).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    video_identity = {"path": str(video), "filename": video.name, "bytes": video.stat().st_size, "sha256": sha256_file(video)}
    probe = probe_video(studio, video)
    graph = job.get("graph") or {}
    preset = studio.preset(job.get("preset_id"))
    source_node = _node_by_class(graph, "LoadImage") or {}
    source = locate_source(studio, (source_node.get("inputs") or {}).get("image"))
    source_meta = {}
    if source.get("path"):
        try:
            source_meta = image_metadata(Path(source["path"]))
            source_meta.update({"path": source["path"], "sha256": sha256_file(Path(source["path"])), "bytes": Path(source["path"]).stat().st_size})
        except (OSError, ValueError) as exc:
            source_meta = {"path": source["path"], "error": str(exc)[:300]}
    latent = _node_by_class(graph, "Wan22ImageToVideoLatent") or {}
    latent_inputs = latent.get("inputs") or {}
    sampler = _node_by_class(graph, "KSampler") or {}
    sampler_inputs = sampler.get("inputs") or {}
    sampling = _node_by_class(graph, "ModelSamplingSD3") or {}
    sampling_inputs = sampling.get("inputs") or {}
    video_node = _node_by_class(graph, "CreateVideo") or {}
    video_inputs = video_node.get("inputs") or {}
    width, height = latent_inputs.get("width"), latent_inputs.get("height")
    preprocessing = None
    if source_meta.get("width") and isinstance(width, int) and isinstance(height, int):
        preprocessing = centered_crop_plan(source_meta["width"], source_meta["height"], width, height)
        if source_meta.get("path"):
            preprocessed = directory / "preprocessed-first-frame.png"
            try:
                render_preprocessed(Path(source_meta["path"]), preprocessed, width, height)
                preprocessing["artifact"] = _artifact_record(preprocessed, job_id)
                preprocessing["renderer"] = "Pillow bilinear parity render; ComfyUI uses torch bilinear"
            except (OSError, ValueError) as exc:
                preprocessing["artifact_error"] = str(exc)[:300]
    canonical_path = studio.root / str(preset.get("canonical_graph", "workflows/api/wan22-i2v-upstream-api.json"))
    canonical = _read_json(canonical_path, {}) or {}
    diff = graph_diff(graph, canonical) if canonical else [{"kind": "canonical_unavailable", "path": str(canonical_path)}]
    frame_count = probe.get("frame_count")
    if not isinstance(frame_count, int):
        frame_count = int(latent_inputs.get("length", 0) or 0)
    requested_indices = list(DEFAULT_SAMPLE_FRAMES)
    valid_indices = [index for index in requested_indices if not frame_count or index < frame_count]
    samples = _extract_samples(studio, video, directory, valid_indices)
    contact = None
    if samples.get("frames"):
        contact = _contact_sheet(directory, samples["frames"], directory / "contact-sheet.png")
    models = model_records(studio, graph, directory)
    model_compatibility = {
        "filenames_present_and_pin_verified": bool(models) and all(item.get("pin_status") == "verified" for item in models),
        "safetensors_headers_valid": bool(models) and all(item.get("container_header", {}).get("status") == "valid" for item in models if Path(item.get("filename", "")).suffix.lower() == ".safetensors"),
        "recorded_execution_loaded_graph": job.get("status") == "completed" and bool(job.get("prompt_ids")) and bool(job.get("submissions")),
        "interpretation": "The exact files were present, matched the Studio pins, passed container checks and were used by the recorded completed graph. This is not a future GPU or visual-quality guarantee.",
    }
    asset_review = None
    for candidate in job.get("outputs", []):
        if candidate is output and candidate.get("asset_id"):
            try:
                asset_review = studio.assets.get(candidate["asset_id"])
            except (OSError, ValueError):
                pass
    prompt_values = {
        "positive": _binding_value(graph, preset, "positive"),
        "negative": _binding_value(graph, preset, "negative"),
    }
    report = {
        "schema_version": 1,
        "kind": "offline-i2v-diagnostic",
        "offline": True,
        "generation_submitted": False,
        "generated_at": time.time(),
        "job": {
            "id": job_id,
            "preset_id": job.get("preset_id"),
            "preset_name": job.get("preset_name"),
            "status": job.get("status"),
            "message": job.get("message"),
            "prompt_ids": job.get("prompt_ids", []),
            "created_at": job.get("created_at"),
            "started_at": job.get("started_at"),
            "finished_at": job.get("finished_at"),
            "elapsed_seconds": job.get("elapsed_seconds"),
            "review": asset_review.get("review") if asset_review else None,
            "quality_acceptance": False,
            "quality_note": "Execution and visual review are separate; this report never infers art acceptance.",
        },
        "video": dict(video_identity, probe=probe, artifact=_artifact_record(video, job_id)),
        "source": dict(source, **source_meta),
        "requested": {
            "width": width,
            "height": height,
            "dimensions": [width, height] if width and height else None,
            "aspect_ratio": _ratio(width, height) if width and height else None,
            "frames": latent_inputs.get("length"),
            "batch_size": latent_inputs.get("batch_size"),
            "steps": sampler_inputs.get("steps"),
            "cfg": sampler_inputs.get("cfg"),
            "seed": sampler_inputs.get("seed"),
            "denoise": sampler_inputs.get("denoise"),
            "sampler": sampler_inputs.get("sampler_name"),
            "scheduler": sampler_inputs.get("scheduler"),
            "shift": sampling_inputs.get("shift"),
            "fps": video_inputs.get("fps"),
            "mode": job.get("controls", {}).get("mode"),
        },
        "preprocessing": preprocessing or {"strategy": "unknown; source dimensions or target dimensions unavailable"},
        "recommended": {
            "resolution": {"width": 1280, "height": 704, "dimensions": [1280, 704], "aspect_ratio": _ratio(1280, 704)},
            "quick_test_frames": 41,
            "full_reference_frames": 121,
            "steps": 30,
            "cfg": 5,
            "sampler": "uni_pc",
            "scheduler": "simple",
            "denoise": 1.0,
            "shift": 8.0,
            "workflow_url": CANONICAL_WORKFLOW_URL,
            "source_url": CANONICAL_SOURCE_URL,
            "note": "The upstream visual workflow uses 41 frames as a quick test; its note recommends 1280x704 and length 121 for the full reference case.",
        },
        "prompts": {"positive": prompt_values["positive"], "negative": prompt_values["negative"]},
        "models": models,
        "model_compatibility": model_compatibility,
        "runtime": _runtime_identity(studio, job),
        "graph": {
            "submitted": graph,
            "canonical_path": str(canonical_path),
            "canonical": canonical,
            "semantic_diff": diff,
            "official_visual_adapter": {
                "workflow_url": CANONICAL_WORKFLOW_URL,
                "output_difference": "Official visual JSON saves WEBP and WEBM; Studio's API graph uses SaveVideo for MP4 playback and asset indexing.",
            },
        },
        "samples": {
            "requested_indices": requested_indices,
            "decoded_indices": [item["index"] for item in samples.get("frames", [])],
            "missing_indices": [index for index in requested_indices if index not in [item["index"] for item in samples.get("frames", [])]],
            "extractor": samples,
            "contact_sheet": _artifact_record(contact, job_id) if contact else None,
        },
        "artifacts": {
            "report": {"filename": "report.json", "url": f"/api/jobs/{job_id}/i2v-diagnostic/report.json"},
            "contact_sheet": _artifact_record(contact, job_id) if contact else None,
            "preprocessed_first_frame": preprocessing.get("artifact") if preprocessing else None,
        },
    }
    _write_json(directory / "report.json", report)
    report["artifacts"]["report"] = _artifact_record(directory / "report.json", job_id)
    return report


def artifact_path(studio, job_id, filename):
    if not isinstance(job_id, str) or not re.fullmatch(r"[0-9a-f-]{36}", job_id) or not isinstance(filename, str) or Path(filename).name != filename or filename in (".", ".."):
        raise ValueError("Invalid diagnostic artifact")
    root = (studio.experiments / "diagnostics" / job_id).resolve()
    path = (root / filename).resolve()
    if path.parent != root or not path.is_file():
        raise ValueError("Diagnostic artifact is unavailable")
    return path
