"""Source-bound continuation policy. No inference, catalog mutation or queue.

A family name is not an operation contract. Static reachability is deliberately
narrow: a bound LoadImage must contribute to every supported saved output. This
proves wiring, not model semantics, identity retention or pixel preservation.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import resource_admission


OUTPUTS = {"SaveImage", "SaveAnimatedWEBP", "SaveAnimatedPNG", "SaveVideo", "SaveGLB", "VHS_VideoCombine"}
INSTRUCTION_NODES = {"TextEncodeQwenImageEditPlus", "HiDreamO1Conditioning", "ReferenceLatent"}
ROUTES = {
    "edit": {"image-to-image", "instruction-edit", "localized-detail", "upscale"},
    "repair": {"image-to-image", "localized-detail", "upscale", "masked-repair"},
    "restyle": {"restyle"},
    "combine": {"combine"},
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
    restyle_board = bool(preset.get("reference_board")) and bool(preset.get("last_reference"))
    # A reference edit may declare itself a Restyle destination: the picture is the model's own reference
    # (ReferenceLatent) and the prepared wording carries the look, so there is no style board to fill.
    restyle_declared = preset.get("continuation_operation") == "restyle" and role == "instruction" and not restyle_board
    # A board may instead declare itself a Combine destination: the source stays image 1 and the board pictures
    # lend it something else (a pose). Same wiring as a board restyle; a different promise, so a different route.
    combine_board = restyle_board and preset.get("continuation_operation") == "combine"
    restyle = (restyle_board or restyle_declared) and not combine_board
    # A sampler whose starting latent descends from a bound picture keeps that picture's layout (img2img).
    latent_from_reference = any(
        node.get("class_type") == "KSampler"
        and isinstance((node.get("inputs") or {}).get("latent_image"), list)
        and any(str(binding[0]) in ancestors(graph, node["inputs"]["latent_image"][0]) for binding in bindings)
        for node in graph.values()
    )
    if not consumed: operation = "new-image" if not preset.get("reference") else "unsupported-reference"
    elif preset.get("requires_rgba_mask"): operation = "masked-repair"
    elif preset.get("parallax_route"): operation = "parallax-stage"   # #1219: reached only from Make parallax layers, never a Continue route
    elif combine_board: operation = "combine"
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
        "source_input": "last_reference" if consumed and restyle_board else "reference",
        "board_min": int((preset.get("reference_board") or {}).get("min", 1)) if consumed and restyle_board else 0,
        # A board keeps the picture when the sampler resamples it (img2img) or when the recipe declares the board a
        # Restyle destination (the source is the model's own reference latent). A Combine board changes the pose.
        "keeps_picture": bool(consumed and (restyle_board and (latent_from_reference or preset.get("continuation_operation") == "restyle") or restyle_declared)),
        "scope": "Static registered graph wiring; not a guarantee of visual preservation.",
    }


VARY_FIELDS = {"sources", "status", "subtle", "strong"}
VARY_STATUS = {"starting-value", "owner-approved"}
# A round picks its own new seeds and keeps the kept picture and its words; a strength only moves sampling settings.
VARY_FIXED = {"seed", "positive", "negative", "reference", "last_reference", "width", "height"}


def _models(graph):
    # checkpoint_name is a loader field too. model_name is not: face detectors use it, and counting it would call two checkpoints the same family.
    keys = ("ckpt_name", "unet_name", "checkpoint_name")
    return {value for node in graph.values() for key, value in (node.get("inputs") or {}).items() if key in keys and isinstance(value, str)}


def _downstream(graph, start):
    """Node ids reachable forward from start, including start. A LoRA chained through another LoRA still reaches the sampler."""
    seen, stack = set(), [str(start)]
    while stack:
        node = stack.pop()
        if node in seen: continue
        seen.add(node)
        for key, other in graph.items():
            if str(key) in seen: continue
            for value in (other.get("inputs") or {}).values():
                if isinstance(value, list) and value and str(value[0]) == node:
                    stack.append(str(key)); break
    return seen


VARY_LORA_SLOTS = ("lora", "lora2", "lora3", "lora4", "lora5", "lora6")


def _lora_nodes(graph):
    return {str(key) for key, node in graph.items() if str(node.get("class_type") or "").startswith("LoraLoader")}


def _slot_fields(preset, slot):
    """Every input one LoRA strength control writes (the model strength plus any clip fan-out)."""
    return sorted(str(item[1]) for item in [preset[slot]] + list((preset.get("bindings_extra") or {}).get(slot) or [])) if preset.get(slot) else []


def _carry_problems(preset, graph, vary, sources, graph_of, bound):
    """A route that carries its source's recorded LoRA stack (`carry`, a list of control names the page copies from the
    picture's run) must draw with the same checkpoint, carry every adapter the source can use, and add none of its own."""
    name, carry = preset.get("id"), vary["carry"]
    if not isinstance(carry, list) or not carry or any(not isinstance(item, str) for item in carry) or len(set(carry)) != len(carry):
        return ["%s: vary carry must be a non-empty list of distinct control names" % name]
    problems, own = [], set()
    for strength in ("subtle", "strong"):
        if isinstance(vary.get(strength), dict) and isinstance(vary[strength].get("controls"), dict): own |= set(vary[strength]["controls"])
    for key in carry:
        if key in VARY_FIXED or key in own: problems.append("%s: vary may not carry %s: the round sets it itself" % (name, key))
        elif key not in bound: problems.append("%s: vary carries %s, which the recipe does not bind" % (name, key))
    for slot in VARY_LORA_SLOTS:
        if (slot in carry) != (slot + "_name" in carry): problems.append("%s: vary carries %s without its file %s, or the file without its strength" % (name, slot, slot + "_name"))
        elif slot in carry and preset.get(slot) and preset.get(slot + "_name") and str(preset[slot][0]) != str(preset[slot + "_name"][0]):
            problems.append("%s: vary %s and %s_name bind different nodes" % (name, slot, slot))
    carried_nodes = {str(preset[slot][0]) for slot in VARY_LORA_SLOTS if slot in carry and preset.get(slot)}
    samplers = {str(key) for key, node in graph.items() if str(node.get("class_type") or "").startswith("KSampler")}
    encoders = {str(key) for key, node in graph.items() if str(node.get("class_type") or "").startswith("CLIPTextEncode")}
    for node in sorted(carried_nodes):
        reached = _downstream(graph, node)
        if (samplers and not reached & samplers) or (encoders and not reached & encoders):
            problems.append("%s: vary adapter node %s does not feed the sampler and the text encoders" % (name, node))
    for node in sorted(_lora_nodes(graph) - carried_nodes):
        problems.append("%s: vary route has an adapter it does not take from the source (node %s); it would change the picture's LoRA stack" % (name, node))
    models = _models(graph)
    for source in sources:
        source_id, source_graph = source.get("id"), graph_of(source)
        if not models or _models(source_graph) != models:
            problems.append("%s: vary source %s draws with another checkpoint (%s, not %s); a route that carries the recipe keeps its model" % (
                name, source_id, ", ".join(sorted(_models(source_graph))) or "none", ", ".join(sorted(models)) or "none"))
        for node in sorted(_lora_nodes(source_graph)):
            if not any(slot in carry and source.get(slot) and str(source[slot][0]) == node for slot in VARY_LORA_SLOTS):
                problems.append("%s: vary source %s has an adapter the route does not carry (node %s); varying it here would drop it" % (name, source_id, node))
        for key in carry:
            if not source.get(key): problems.append("%s: vary source %s does not bind carried %s, so its recorded value is unknown" % (name, source_id, key)); continue
            if key in VARY_LORA_SLOTS and preset.get(key) and _slot_fields(source, key) != _slot_fields(preset, key):
                problems.append("%s: vary carries %s, but its strength reaches %s here and %s on %s" % (name, key, _slot_fields(preset, key), _slot_fields(source, key), source_id))
            accepted = (preset.get("choices") or {}).get(key)
            if accepted is not None:
                recorded = (source.get("choices") or {}).get(key)
                if recorded is None:
                    try: recorded = [source_graph[str(source[key][0])]["inputs"][str(source[key][1])]]
                    except (KeyError, TypeError, IndexError): recorded = [None]
                refused = [value for value in recorded if value not in accepted]
                if refused: problems.append("%s: vary source %s records %s values the route refuses: %s" % (name, source_id, key, ", ".join(map(str, refused))))
    return problems


def vary_problems(preset, graph, presets, graph_of):
    """What is wrong with one recipe's declared Vary route (#1202); empty when sound or undeclared.

    A route resamples the kept picture (img2img) at the declared denoise with new seeds. Its sources are the
    recipes whose pictures it may vary: each must draw with the same model family or checkpoint as the route.
    A route that declares `carry` copies those controls from the picture's recorded run (WAI keeps its LoRA stack);
    it is held to the same checkpoint exactly, never a family label, and to the same adapters.
    """
    vary, name = preset.get("vary"), preset.get("id")
    if vary is None: return []
    if not isinstance(vary, dict) or set(vary) - {"carry"} != VARY_FIELDS: return ["%s: vary needs exactly %s (and optionally carry)" % (name, ", ".join(sorted(VARY_FIELDS)))]
    problems = []
    cap = capability(preset, graph)
    if cap["operation"] != "image-to-image" or cap["prompt_role"] != "description" or not preset.get("denoise") or not preset.get("seed"):
        problems.append("%s: a Vary route must be an image-to-image recipe with seed and denoise controls and a description prompt" % name)
    if vary["status"] not in VARY_STATUS: problems.append("%s: vary status must be one of %s" % (name, ", ".join(sorted(VARY_STATUS))))
    bound = {key for key, value in preset.items() if isinstance(value, list) and len(value) == 2 and all(isinstance(part, str) for part in value)} | set(preset.get("bindings_extra") or {})
    denoise = {}
    for strength in ("subtle", "strong"):
        entry = vary[strength]
        if not isinstance(entry, dict) or set(entry) != {"controls", "basis"} or not isinstance(entry["controls"], dict):
            problems.append("%s: vary %s needs exactly controls and basis" % (name, strength)); continue
        if not isinstance(entry["basis"], str) or not entry["basis"].strip(): problems.append("%s: vary %s needs a basis saying where its values come from" % (name, strength))
        for key in sorted(set(entry["controls"]) - bound): problems.append("%s: vary %s sets %s, which the recipe does not bind" % (name, strength, key))
        for key in sorted(set(entry["controls"]) & VARY_FIXED): problems.append("%s: vary %s may not set %s" % (name, strength, key))
        value = entry["controls"].get("denoise")
        if type(value) not in (int, float) or not 0 < value < 1: problems.append("%s: vary %s needs a denoise between 0 and 1" % (name, strength))
        else: denoise[strength] = value
    if len(denoise) == 2 and not denoise["subtle"] < denoise["strong"]: problems.append("%s: vary subtle must resample less than vary strong" % name)
    sources = vary["sources"]
    if not isinstance(sources, list) or not sources or any(not isinstance(item, str) for item in sources) or len(set(sources)) != len(sources):
        return problems + ["%s: vary sources must be a non-empty list of distinct recipe ids" % name]
    known = {p.get("id"): p for p in presets}
    checked = []
    for source_id in sources:
        source = known.get(source_id)
        if source is None: problems.append("%s: vary source %s is not a recipe" % (name, source_id)); continue
        if source.get("modality", "image") != "image": problems.append("%s: vary source %s does not make pictures" % (name, source_id)); continue
        checked.append(source)
        if "carry" in vary: continue   # held to the exact checkpoint below
        same_family = bool(preset.get("family")) and source.get("family") == preset.get("family")
        if not same_family and not _models(graph) & _models(graph_of(source)):
            problems.append("%s: vary source %s draws with another model; varying it here would change the model" % (name, source_id))
    if "carry" in vary: problems += _carry_problems(preset, graph, vary, checked, graph_of, bound)
    return problems


def vary_catalog_problems(presets, graph_of):
    """Every Vary route's problems, plus a source claimed by more than one route (the page must pick one)."""
    problems, owner = [], {}
    for preset in presets:
        if preset.get("vary") is None: continue
        problems += vary_problems(preset, graph_of(preset), presets, graph_of)
        sources = (preset["vary"] or {}).get("sources") if isinstance(preset["vary"], dict) else None
        for source_id in [item for item in sources if isinstance(item, str)] if isinstance(sources, list) else []:
            if source_id in owner: problems.append("vary source %s is claimed by more than one route (%s, %s)" % (source_id, owner[source_id], preset["id"]))
            owner.setdefault(source_id, preset["id"])
    return problems


def unfilled(preset, text):
    """The recipe's bracketed fills (`continuation_placeholder`, one string or a list) still present in the wording."""
    declared = preset.get("continuation_placeholder")
    if not isinstance(text, str): return []
    return [item for item in (declared if isinstance(declared, list) else [declared]) if isinstance(item, str) and item and item in text]


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
    if claim is None:
        if check_runtime: resource_admission.pre_submit(studio, payload, preset, graph)
        return None
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
    board = preset.get("reference_board") if cap["operation"] in ("restyle", "combine") else None
    # (binding, file name, recorded hash, optional): a style-board slot is optional and pruned when empty.
    declared = []
    if preset.get("reference_slots"):
        supplied = payload.get("references")
        slots = preset["reference_slots"]
        # Match board compilation's positional padding, not an inferred attachment.
        # Every padded loader must still be absent below; named source inputs stay explicit.
        if board is not None:
            if supplied is None: supplied = []
            if isinstance(supplied, list) and len(supplied) <= len(slots):
                supplied = supplied + [{} for _ in range(len(slots) - len(supplied))]
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
        # A recipe whose prepared wording carries bracketed placeholders (one string or a list) refuses to run until
        # every one of them is replaced. Studio.prepare() applies the same rule to every route, claim or not.
        left = unfilled(preset, text)
        if left:
            raise ValueError("Fill in the wording: replace %s before running." % " and ".join("“%s”" % item for item in left))
    if check_runtime: resource_admission.pre_submit(studio, payload, preset, graph)
    return dict(claim)


def tile_route_problems(presets):
    """Catalog contract, checked by scripts/validate-repo.py (#1220; kept here because the validator lane has no Pillow): at most one tile route, and it is a masked repaint of one picture."""
    routes = [preset for preset in presets if preset.get("tile_route")]
    problems = ["more than one tile_route recipe: " + ", ".join(p["id"] for p in routes)] if len(routes) > 1 else []
    for preset in routes:
        if preset.get("tile_route") is not True: problems.append(preset["id"] + ": tile_route must be true")
        if not preset.get("requires_rgba_mask") or not preset.get("reference"): problems.append(preset["id"] + ": a tile route repaints an RGBA cross, so it needs requires_rgba_mask and a reference binding")
        if preset.get("modality", "image") != "image": problems.append(preset["id"] + ": a tile route makes pictures")
        if preset.get("width") or preset.get("height"): problems.append(preset["id"] + ": a tile route draws at the source size; it binds no width or height")
    return problems


def parallax_route_problems(presets):
    """Catalog contract, checked by scripts/validate-repo.py (#1219; Pillow-free like the tile check): at most one parallax
    route, an instruction edit of one attached picture that draws at a bound width and height, one picture per run."""
    routes = [preset for preset in presets if preset.get("parallax_route")]
    problems = ["more than one parallax_route recipe: " + ", ".join(p["id"] for p in routes)] if len(routes) > 1 else []
    for preset in routes:
        if preset.get("parallax_route") is not True: problems.append(preset["id"] + ": parallax_route must be true")
        if not preset.get("reference") or preset.get("reference_slots") or preset.get("last_reference"): problems.append(preset["id"] + ": a parallax route edits exactly one attached picture (reference)")
        if not preset.get("positive") or not preset.get("width") or not preset.get("height"): problems.append(preset["id"] + ": a parallax route binds positive, width and height")
        if preset.get("requires_rgba_mask") or preset.get("tile_route"): problems.append(preset["id"] + ": a parallax route is a whole-picture edit, not a masked repaint or a tile")
        if preset.get("modality", "image") != "image": problems.append(preset["id"] + ": a parallax route makes pictures")
        limits = preset.get("dimension_limits", [64, 1536])
        if not (limits[0] <= 512 and 1536 <= limits[1]): problems.append(preset["id"] + ": a parallax route must accept every size Make parallax layers offers (512-1536 px a side)")
    return problems
