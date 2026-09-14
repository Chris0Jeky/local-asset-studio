"""Source-bound continuation policy. No inference, catalog mutation or queue.

A family name is not an operation contract. Static reachability is deliberately
narrow: a bound LoadImage must contribute to every supported saved output. This
proves wiring, not model semantics, identity retention or pixel preservation.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path


OUTPUTS = {"SaveImage", "SaveAnimatedWEBP", "SaveAnimatedPNG", "SaveVideo", "SaveGLB", "VHS_VideoCombine"}
INSTRUCTION_NODES = {"TextEncodeQwenImageEditPlus", "HiDreamO1Conditioning", "ReferenceLatent"}
ROUTES = {
    "edit": {"image-to-image", "instruction-edit", "localized-detail", "upscale"},
    "repair": {"image-to-image", "localized-detail", "upscale", "masked-repair"},
    "restyle": {"restyle"},
    "animate": {"image-to-video"},
    "mesh": {"image-to-3d"},
}


def ancestors(graph, start):
    seen, pending = set(), [str(start)]
    while pending:
        key = pending.pop()
        if key in seen or key not in graph: continue
        seen.add(key)
        for value in (graph[key].get("inputs") or {}).values():
            if isinstance(value, list) and len(value) == 2 and type(value[1]) is int and str(value[0]) in graph:
                pending.append(str(value[0]))
    return seen


def consumes_reference(graph, binding):
    if not isinstance(binding, (list, tuple)) or len(binding) != 2: return False
    key, field = str(binding[0]), binding[1]
    if field != "image" or graph.get(key, {}).get("class_type") != "LoadImage": return False
    outputs = [node_id for node_id, node in graph.items() if node.get("class_type") in OUTPUTS]
    return bool(outputs) and all(key in ancestors(graph, output) for output in outputs)


def reference_bindings(preset):
    """Return every declared image input once, in primary-source order."""
    # Role slots (Qwen Atelier, style boards) and the plain inputs can coexist: a style board keeps its pose
    # picture on last_reference. Duplicates collapse below.
    values = [slot.get("binding") for slot in preset.get("reference_slots") or [] if isinstance(slot, dict)]
    values += [preset.get("reference"), preset.get("last_reference")]
    result = []
    for value in values:
        if isinstance(value, (list, tuple)) and len(value) == 2 and list(value) not in result:
            result.append(list(value))
    return result


def prompt_role(graph, has_positive=True, modality="image"):
    if not has_positive: return "none"
    if modality == "video": return "motion"
    kinds = {node.get("class_type") for node in graph.values()}
    if kinds & INSTRUCTION_NODES: return "instruction"
    return "description"


def capability(preset, graph):
    bindings = reference_bindings(preset)
    # A compiled style board has its empty slots pruned; those absent loaders do not break consumption.
    board_nodes = {str(slot["binding"][0]) for slot in preset.get("reference_slots") or []
                   if preset.get("reference_board") and isinstance(slot, dict) and isinstance(slot.get("binding"), (list, tuple)) and len(slot["binding"]) == 2}
    active = [binding for binding in bindings if not (str(binding[0]) in board_nodes and str(binding[0]) not in graph)]
    consumed = bool(active) and all(consumes_reference(graph, binding) for binding in active)
    role = prompt_role(graph, bool(preset.get("positive")), preset.get("modality", "image"))
    kinds = {node.get("class_type") for node in graph.values()}
    # A style board with its own pose picture: the continuation source becomes the pose picture, and the
    # board (one to three optional pictures) carries the look. Only then does the source live on last_reference.
    restyle = bool(preset.get("reference_board")) and bool(preset.get("last_reference"))
    # A sampler whose starting latent descends from a bound picture keeps that picture's layout (img2img).
    latent_from_reference = any(
        node.get("class_type") == "KSampler"
        and isinstance((node.get("inputs") or {}).get("latent_image"), list)
        and any(str(binding[0]) in ancestors(graph, node["inputs"]["latent_image"][0]) for binding in bindings)
        for node in graph.values()
    )
    if not consumed: operation = "new-image" if not preset.get("reference") else "unsupported-reference"
    elif preset.get("requires_rgba_mask"): operation = "masked-repair"
    elif restyle: operation = "restyle"
    elif role == "motion": operation = "image-to-video"
    elif preset.get("modality") == "3d": operation = "image-to-3d"
    elif "FaceDetailer" in kinds: operation = "localized-detail"
    elif role == "instruction": operation = "instruction-edit"
    elif not preset.get("positive"): operation = "upscale"
    elif latent_from_reference: operation = "image-to-image"
    else: operation = "reference-guided-generation"
    return {
        "version": 1,
        "consumes_source": consumed,
        "operation": operation,
        "prompt_role": role,
        "requires_mask": bool(preset.get("requires_rgba_mask")),
        "reference_count": len(bindings) if consumed else 0,
        "source_input": "last_reference" if consumed and restyle else "reference",
        "board_min": int((preset.get("reference_board") or {}).get("min", 1)) if consumed and restyle else 0,
        "keeps_picture": bool(consumed and restyle and latent_from_reference),
        "scope": "Static registered graph wiring; not a guarantee of visual preservation.",
    }


def _text(graph, bindings):
    if not isinstance(bindings, list) or not bindings: return None
    values = []
    for binding in bindings:
        try: value = graph[str(binding[0])]["inputs"][str(binding[1])]
        except (KeyError, TypeError, IndexError): return None
        if not isinstance(value, str) or len(value) > 8000: return None
        values.append(value)
    # Companion inputs with different text cannot be collapsed to one editable field.
    return values[0] if len(set(values)) == 1 else None


def source_context(studio, asset_id):
    asset = studio.assets.get(asset_id)
    if asset.get("trashed_at") or asset.get("media_type") != "image":
        raise ValueError("Restore an image asset before continuing with it.")
    path = studio.assets.file(asset_id)
    if path.stat().st_size > 20 * 1024 * 1024: raise ValueError("Source exceeds the 20 MiB reference limit.")
    if hashlib.sha256(path.read_bytes()).hexdigest() != asset["sha256"]:
        raise ValueError("Source bytes changed. Restore the original asset before continuing.")
    job = studio.jobs.get(asset.get("job_id")) or {}
    prompt_id = (asset.get("source") or {}).get("prompt_id")
    matches = [submission for submission in job.get("submissions", []) if prompt_id and submission.get("prompt_id") == prompt_id]
    graph = matches[0].get("graph") if len(matches) == 1 else None
    bindings = job.get("prompt_bindings") or {}
    positive = _text(graph, bindings.get("positive")) if isinstance(graph, dict) else None
    negative = _text(graph, bindings.get("negative")) if isinstance(graph, dict) else None
    origin = "submitted-output" if positive is not None else "unavailable"
    warning = "" if positive is not None else "No unambiguous submitted prompt is retained for this output. Describe the desired result; the recipe example will not be used."
    role = prompt_role(graph, True) if isinstance(graph, dict) else "unknown"
    from PIL import Image
    with Image.open(path) as image: width, height = image.size
    return {
        "version": 1,
        "asset_id": asset["id"],
        "sha256": asset["sha256"],
        "title": asset.get("title", asset["filename"]),
        "preset_id": asset.get("preset_id"),
        "preset_name": asset.get("preset_name"),
        "job_id": asset.get("job_id"),
        "prompt_id": prompt_id,
        "positive": positive,
        "negative": negative,
        "prompt_origin": origin,
        "prompt_role": role,
        "warning": warning,
        "width": width,
        "height": height,
    }


def validate(studio, payload, preset, graph, check_runtime=False):
    """Validate an opt-in continuation during preparation and before dispatch."""
    claim = payload.get("continuation")
    if claim is None: return None
    fields = {"version", "intent", "source_asset_id", "source_sha256", "preset_id", "reference_file", "template_sha256"}
    if not isinstance(claim, dict) or set(claim) != fields or type(claim.get("version")) is not int or claim["version"] != 1:
        raise ValueError("Invalid continuation context. Reopen Continue with this asset.")
    for key in fields - {"version"}:
        if not isinstance(claim[key], str) or not claim[key] or len(claim[key]) > 255:
            raise ValueError("Invalid continuation context field: " + key)
    if claim["intent"] not in ROUTES or any(not re.fullmatch("[a-f0-9]{64}", claim[key]) for key in ("source_sha256", "template_sha256")):
        raise ValueError("Invalid continuation intent or source identity.")
    cap = capability(preset, graph)
    if claim["preset_id"] != preset.get("id") or not cap["consumes_source"]:
        raise ValueError("This is not the selected source-consuming route. Leave continuation explicitly to start a new image.")
    if cap["operation"] not in ROUTES[claim["intent"]]:
        raise ValueError("This graph does not support the requested continuation operation.")
    _, template_path = studio.graph_for(preset)
    if hashlib.sha256(template_path.read_bytes()).hexdigest() != claim["template_sha256"]:
        raise ValueError("The destination graph changed. Reopen the handoff and review the new route.")
    if cap["requires_mask"]:
        raise ValueError("This route needs a prepared RGBA repair mask, not an unchanged source copy. Prepare the mask in the dedicated repair workflow.")
    source = source_context(studio, claim["source_asset_id"])
    if source["sha256"] != claim["source_sha256"]:
        raise ValueError("The continuation source changed. Reopen Continue with this asset.")
    parents = payload.get("parent_assets")
    if not isinstance(parents, list) or claim["source_asset_id"] not in parents:
        raise ValueError("Continuation source is missing from lineage.")
    controls = payload.get("controls") or {}
    board = preset.get("reference_board") if cap["operation"] == "restyle" else None
    # (binding, file name, recorded hash, optional): a style-board slot is optional and pruned when empty.
    declared = []
    if preset.get("reference_slots"):
        supplied = payload.get("references")
        slots = preset["reference_slots"]
        if not isinstance(supplied, list) or len(supplied) != len(slots):
            raise ValueError("Attach every declared source input explicitly; authored example inputs are not allowed.")
        declared = [(slot.get("binding"), record.get("file") if isinstance(record, dict) else None,
                     record.get("sha256") if isinstance(record, dict) else None, board is not None) for slot, record in zip(slots, supplied)]
        if preset.get("last_reference"): declared.append((preset["last_reference"], controls.get("last_reference"), None, False))
    else:
        declared = [(preset.get(key), controls.get(key), None, False) for key in ("reference", "last_reference") if preset.get(key)]
    source_index = len(declared) - 1 if cap["source_input"] == "last_reference" else 0
    if not declared or declared[source_index][1] != claim["reference_file"]:
        raise ValueError("Attach every declared source input explicitly; authored example inputs are not allowed.")
    if board is not None and sum(1 for entry in declared if entry[3] and isinstance(entry[1], str) and entry[1]) < cap["board_min"]:
        raise ValueError("Add at least %d picture%s whose look you want to the style board." % (cap["board_min"], "" if cap["board_min"] == 1 else "s"))
    upload_root = studio.experiments / "uploads"
    runtime_root = Path(payload.get("comfy_root", studio.comfy_root)) / "input"
    for index, (binding, name, recorded_hash, optional) in enumerate(declared):
        if optional and name is None:
            # An empty board slot must be gone from the graph, not left on the authored example picture.
            if str(binding[0]) in graph: raise ValueError("An empty style-board slot still carries the recipe example; reattach the board.")
            continue
        try:
            node, field = binding
            bound = graph[str(node)]["inputs"][str(field)]
        except (KeyError, TypeError, ValueError):
            raise ValueError("Every declared source input must have a valid graph binding.") from None
        if not isinstance(name, str) or bound != name or not re.fullmatch(r"[0-9a-f]{32}_[A-Za-z0-9._-]+\.(?:png|jpg|webp)", name):
            raise ValueError("Attach every declared source input explicitly; authored example inputs are not allowed.")
        upload = upload_root / name
        if upload.is_symlink() or not upload.is_file() or upload.stat().st_size > 20 * 1024 * 1024:
            raise ValueError("Continuation input bytes changed or are missing. Reattach every source before running.")
        upload_hash = hashlib.sha256(upload.read_bytes()).hexdigest()
        expected = source["sha256"] if index == source_index else recorded_hash or upload_hash
        if upload_hash != expected:
            raise ValueError("Continuation input bytes changed or are missing. Reattach every source before running.")
        if check_runtime:
            runtime = runtime_root / name
            if runtime.is_symlink() or not runtime.is_file() or runtime.stat().st_size > 20 * 1024 * 1024 or hashlib.sha256(runtime.read_bytes()).hexdigest() != upload_hash:
                raise ValueError("Continuation input bytes changed or are missing. Reattach every source before running.")
    if preset.get("positive"):
        text = controls.get("positive")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Describe the desired result or the requested change before running this continuation.")
    return dict(claim)
