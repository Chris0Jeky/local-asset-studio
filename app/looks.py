"""Look templates (#1221): an accepted picture's wording, kept as a template with one `{scene}` slot, plus its recipe.

A look is a Workspace card (app/workspace.py `cards`, kind "look"): name, body and lineage, revisioned, reversible trash.
body: preset_id (one text-to-image recipe), template, negative, controls (only inputs that recipe binds), scene_example,
source_prompt (the anchor's own wording, verbatim), notes and options. lineage: the pictures it came from, by sha256.
options (owner, 27 Sep 2026): optional lines, each a sentence with an id, a label, and a default. The template holds `{<id>}` once
where the line goes; Prepare writes the line only when it is on. Layout sentences belong here, so the scene decides the layout.
A shipped look reaches an existing Workspace through workspace.seed_cards: new ids are inserted, and an updated look lists the
digests it `supersedes`, so a copy never edited takes the new version while an owner's edit is kept as it is.
The lab behind it (background-lab-20260927, strand c): words on the same model carry a look to new scenes; a look picture
through a reference route leaks content. Preparing composes Create's fields and never submits (K8: Generate stays a press).
"""
import json
import math
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from workspace import CARD_ID, WorkspaceError

KIND = "look"
SLOT = "{scene}"
SCENE_MAX = 1000
TEXT_LIMITS = {"template": 4000, "negative": 4000, "scene_example": 1000, "source_prompt": 8000, "notes": 4000}
BODY_FIELDS = {"preset_id", "controls", "options", *TEXT_LIMITS}
OPTION_ID = re.compile(r"[a-z][a-z0-9_]{1,31}")
OPTION_FIELDS = {"id", "label", "text", "default"}
OPTIONS_MAX = 6
# Wording is the template's job and pictures are not part of a look, so these are never stored as look controls.
NOT_CONTROLS = {"positive", "negative", "reference", "last_reference", "mode"}
PICTURE_KEYS = ("reference", "last_reference", "reference_slots")
LINEAGE_ROLES = ("anchor", "evidence", "canon")
SEEDS = "presets/looks.json"
# Display-only MA study, never the saved Look's Z2 anchor or a recipe input.
NIGHT_SHIFT_PREVIEW_DIGEST = "4efd82ed42acaea321891906f9e2b87ccd66577189b493086f5ab3beabd6f853"
NIGHT_SHIFT_PREVIEW = {
    "src": "/static/look-previews/night-shift-ma-responsive-1024.webp",
    "title": "Night Shift visual reference",
    "alt": "Empty late-night workshop: quiet graphite wall, rainy window, desk lamp and glowing CRT.",
}
# Exact server control vocabulary minus wording and references. A parity test guards drift.
CONTROL_KEYS = frozenset(("width", "height", "seed", "steps", "cfg", "denoise", "lora", "frames", "fps",
                          "style_weight", "pose_strength", "depth_cut", "sampler", "scheduler", "lora_name",
                          "lora2", "lora2_name", "lora3", "lora3_name", "lora4", "lora4_name",
                          "lora5", "lora5_name", "lora6", "lora6_name"))
LORA_SLOTS = ("lora", "lora2", "lora3", "lora4", "lora5", "lora6")


# server.py NUMBER_RANGES plus its LoRA strength, frames and fps ranges (a parity test guards drift): a saved control outside
# them would only fail later, when /api/jobs binds it, after Prepare had already handed it to the page.
NUMBER_RANGES = {"seed": (0, 2**63-1, True), "steps": (1, 150, True), "cfg": (0, 30, False), "denoise": (0, 1, False),
                 "style_weight": (0, 2, False), "pose_strength": (0, 2, False), "depth_cut": (0, 100, True),
                 "frames": (5, 365, True), "fps": (1, 60, True), **{k: (0, 2, False) for k in LORA_SLOTS}}


def _number(value, lo, hi, integer):
    if isinstance(value, bool): return False
    try: raw = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError): return False
    return raw.is_finite() and lo <= raw <= hi and (not integer or raw == raw.to_integral_value())


def _adapter_file(value):
    return isinstance(value, str) and 0 < len(value) <= 200 and value == Path(value).name and not re.search(r"[\\/]|\.\.", value) and value.endswith(".safetensors")


def control_problem(preset, key, value):
    """Why a saved control value would be refused at /api/jobs, or None. Installed files and live choices are checked there."""
    # Older presets bind `lora` to a filename input: a filename is a slot value only where the authored input holds one.
    if key in LORA_SLOTS and isinstance((preset.get("defaults") or {}).get(key), str):
        return None if _adapter_file(value) else f"{key} must be a .safetensors adapter filename"
    if key in NUMBER_RANGES:
        lo, hi, integer = NUMBER_RANGES[key]
        return None if _number(value, lo, hi, integer) else f"{key} must be a{'n integer' if integer else ' number'} from {lo} to {hi}"
    if key.endswith("_name"): return None if _adapter_file(value) else f"{key} must be a .safetensors adapter filename"
    if key in ("width", "height"):
        (lo, hi), multiple = preset.get("dimension_limits", [64, 1536]), preset.get("dimension_multiple", 8)
        return None if _number(value, lo, hi, True) and int(Decimal(str(value))) % multiple == 0 else f"{key} must be a multiple of {multiple} from {lo} to {hi}"
    if key in ("sampler", "scheduler"):
        choices = (preset.get("choices") or {}).get(key)
        return None if choices and value in choices else f"{key} {value} is not offered by {preset.get('name') or preset.get('id')}"
    return None


def _offered_default(preset, key, value):
    """(default, notice) when a saved sampler/scheduler is no longer offered and the recipe's authored default is (owner, 16 Oct 2026:
    swap it and say so), else None: a recipe with no offered default keeps the plain refusal from control_problem."""
    default, choices = (preset.get("defaults") or {}).get(key), (preset.get("choices") or {}).get(key)
    if key not in ("sampler", "scheduler") or control_problem(preset, key, value) is None or not isinstance(default, str) or not choices or default not in choices: return None
    return default, f"This look's {key} {value} is no longer offered by {preset.get('name') or preset.get('id')}; using the recipe's default {default}."


def _text(value, name, maximum, required=False):
    if value is None and not required: return ""
    if not isinstance(value, str) or len(value) > maximum: raise WorkspaceError(f"{name} must be text up to {maximum} characters")
    value = value.strip()
    if required and not value: raise WorkspaceError(f"{name} is required")
    return value


def _bound(preset, key):
    if key not in CONTROL_KEYS: return False
    extras = preset.get("bindings_extra")
    binding = preset.get(key) or (extras.get(key) if isinstance(extras, dict) else None)
    return (isinstance(binding, (list, tuple)) and len(binding) == 2
            and all(isinstance(part, str) and bool(part.strip()) for part in binding))


MODEL_LOADERS = {"CheckpointLoaderSimple": "ckpt_name", "UNETLoader": "unet_name", "UnetLoaderGGUF": "unet_name"}


def model_of(graph):
    """A recipe's base model for Make's Tune this look: its file, loader node and text encoders, or None when the graph has
    not exactly one model loader. Two recipes with the same loader and encoders take the same wording and adapters."""
    nodes = [n for n in graph.values() if isinstance(n, dict) and isinstance(n.get("inputs"), dict)]
    found = [(n["class_type"], n["inputs"].get(MODEL_LOADERS[n["class_type"]])) for n in nodes if n.get("class_type") in MODEL_LOADERS]
    if len(found) != 1 or not isinstance(found[0][1], str): return None
    encoders = sorted(v for n in nodes if "CLIPLoader" in str(n.get("class_type")) for k, v in n["inputs"].items() if k.startswith("clip_name") and isinstance(v, str))
    return {"file": found[0][1], "loader": found[0][0], "encoders": encoders}


def recipe_problem(preset):
    """Why this recipe cannot carry a look, or None. A look is words on the same model: one text-to-image recipe."""
    if (preset.get("modality") or "image") != "image": return "A look needs an image recipe; this one makes " + str(preset.get("modality")) + "."
    if not preset.get("positive"): return "This recipe takes no wording, so a look cannot write it."
    if any(preset.get(key) for key in PICTURE_KEYS): return "A look is carried by words on a text-to-image recipe; this recipe takes a picture, and a look picture leaks content (lab 27 Sep 2026)."
    return None


def token(option_id):
    return "{" + option_id + "}"


def _options(value, template):
    """Optional lines, normalized: each id's token appears exactly once in the template; a line holds no slot of its own."""
    if not isinstance(value, list) or len(value) > OPTIONS_MAX: raise WorkspaceError(f"Optional lines must be a list of up to {OPTIONS_MAX}")
    result = []
    for option in value:
        if not isinstance(option, dict) or set(option) - OPTION_FIELDS: raise WorkspaceError("An optional line has the fields " + ", ".join(sorted(OPTION_FIELDS)))
        identifier = option.get("id")
        if not isinstance(identifier, str) or not OPTION_ID.fullmatch(identifier) or token(identifier) == SLOT:
            raise WorkspaceError("An optional line id is 2-32 lowercase letters, digits or underscores, starting with a letter, and not scene")
        if any(identifier == other["id"] for other in result): raise WorkspaceError(f"Name the optional line {identifier} once")
        if template.count(token(identifier)) != 1: raise WorkspaceError(f"Write {token(identifier)} exactly once in the wording, where that line goes")
        if not isinstance(option.get("default", False), bool): raise WorkspaceError("An optional line's default is true or false")
        clean = {"id": identifier, "label": _text(option.get("label"), "Optional line label", 120, True), "text": _text(option.get("text"), "Optional line text", 1000, True),
                 "default": option.get("default", False)}
        result.append(clean)
    if any(t in option["text"] for option in result for t in [SLOT, *(token(other["id"]) for other in result)]):
        raise WorkspaceError("An optional line is plain words: it holds no slot or line token")
    # At most six lines: check all choices, including slots assembled by several replacements.
    for mask in range(1 << len(result)):
        wording = template
        for index, option in enumerate(result):
            wording = wording.replace(token(option["id"]), option["text"] if mask & (1 << index) else "")
        if wording.count(SLOT) != 1: raise WorkspaceError("Optional lines must leave exactly one " + SLOT + " slot in the wording")
    return result


def validate_body(body, preset, notices=None):
    """The look body, normalized, for this catalog preset; WorkspaceError with a plain reason otherwise. An unoffered sampler or
    scheduler becomes the recipe's default and, when `notices` is a list, its plain notice is appended."""
    if not isinstance(body, dict): raise WorkspaceError("A look must be an object")
    if set(body) - BODY_FIELDS: raise WorkspaceError("Unknown look fields: " + ", ".join(sorted(set(body) - BODY_FIELDS)))
    if body.get("preset_id") != preset.get("id"): raise WorkspaceError("A look names the recipe it was made on")
    problem = recipe_problem(preset)
    if problem: raise WorkspaceError(problem)
    result = {"preset_id": preset["id"]}
    for field, maximum in TEXT_LIMITS.items():
        if field in body or field in ("template", "negative"): result[field] = _text(body.get(field), field.replace("_", " ").capitalize(), maximum, field == "template")
    if result["template"].count(SLOT) != 1: raise WorkspaceError("Write " + SLOT + " exactly once in the wording, where a new scene goes")
    if result["negative"] and not preset.get("negative"): raise WorkspaceError("This recipe takes no negative prompt; put the exclusions in the wording")
    if "options" in body: result["options"] = _options(body["options"], result["template"])
    controls = body.get("controls", {})
    if not isinstance(controls, dict) or len(controls) > 40: raise WorkspaceError("Look controls must be an object of up to 40 settings")
    clean = {}
    for key, value in controls.items():
        if key in NOT_CONTROLS or not isinstance(key, str): raise WorkspaceError(f"{key} is not a look setting")
        if not _bound(preset, key): raise WorkspaceError(f"{key} is not bound on {preset.get('name') or preset['id']}")
        if isinstance(value, bool) or not isinstance(value, (int, float, str)) or (isinstance(value, float) and not math.isfinite(value)):
            raise WorkspaceError(f"{key} must be a finite number or text")
        if isinstance(value, str) and len(value) > 300: raise WorkspaceError(f"{key} must be up to 300 characters")
        swapped = _offered_default(preset, key, value)
        if swapped:
            value = swapped[0]
            if notices is not None: notices.append(swapped[1])
        problem = control_problem(preset, key, value)
        if problem: raise WorkspaceError(problem)
        clean[key] = value
    result["controls"] = clean
    return result


def validate_lineage(lineage):
    """Up to 20 pictures a look came from, named by content: role, and a sha256 when it names a picture."""
    if not isinstance(lineage, list) or len(lineage) > 20: raise WorkspaceError("Lineage must be a list of up to 20 entries")
    for entry in lineage:
        if not isinstance(entry, dict) or entry.get("role") not in LINEAGE_ROLES: raise WorkspaceError("Each lineage entry names its role: " + ", ".join(LINEAGE_ROLES))
        if "sha256" in entry and not (isinstance(entry["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])): raise WorkspaceError("A lineage sha256 is 64 lowercase hexadecimal characters")
        if any(isinstance(v, (dict, list)) or (isinstance(v, str) and len(v) > 500) for v in entry.values()): raise WorkspaceError("Lineage values are short text or numbers")
    return lineage


def chosen_options(options, chosen=None):
    """{id: on} for each optional line: the caller's choice, else the line's default."""
    chosen = {} if chosen is None else chosen
    if not isinstance(chosen, dict): raise WorkspaceError("Optional lines are an object of line id to true or false")
    unknown = sorted(str(key) for key in chosen if key not in {option["id"] for option in options})
    if unknown: raise WorkspaceError("Unknown optional line: " + ", ".join(unknown))
    if any(not isinstance(value, bool) for value in chosen.values()): raise WorkspaceError("Each optional line is true or false")
    return {option["id"]: chosen.get(option["id"], option["default"]) for option in options}


def compose(template, scene, options=(), chosen=None):
    """The template with the typed scene in its one slot: whitespace collapsed, a trailing full stop dropped (the template has its own).
    Optional lines are written first, so a scene's own braces stay its words; a line that is off leaves no double space."""
    if not isinstance(scene, str): raise WorkspaceError("Type the scene in a few words")
    scene = " ".join(scene.split()).rstrip(" .")
    if not scene: raise WorkspaceError("Type the scene in a few words")
    if len(scene) > SCENE_MAX: raise WorkspaceError(f"Keep the scene under {SCENE_MAX} characters")
    if SLOT in scene: raise WorkspaceError("The scene is the text that fills " + SLOT + "; leave the token out")
    if template.count(SLOT) != 1: raise WorkspaceError("This look's wording has no single " + SLOT + " slot; edit the look")
    on = chosen_options(options, chosen)
    for option in options: template = template.replace(token(option["id"]), option["text"] if on[option["id"]] else "")
    if template.count(SLOT) != 1: raise WorkspaceError("This look's optional lines leave no single " + SLOT + " slot; edit the look")
    text = template.replace(SLOT, scene)
    return re.sub(r" {2,}", " ", text).strip() if options else text


def _presets(studio):
    return {p.get("id"): p for p in studio.catalog()["presets"] if isinstance(p, dict)}


def ensure_seeds(studio):
    """Copy shipped looks into the Workspace once per Studio; the Workspace never takes an overwrite. Invalid seeds are reported, not stored."""
    if getattr(studio, "_look_seed_errors", None) is not None: return studio._look_seed_errors
    errors, valid, path = [], [], Path(studio.root) / SEEDS
    try: entries = json.loads(path.read_text(encoding="utf-8")).get("looks", []) if path.is_file() else []
    except (OSError, ValueError, AttributeError) as error: entries, errors = [], [f"{SEEDS} is unreadable: {error}"]
    if not isinstance(entries, list):
        errors.append(f"{SEEDS} looks must be a list")
        entries = []
    presets = _presets(studio)
    for entry in entries:
        try:
            if not isinstance(entry, dict) or entry.get("kind") != KIND: raise WorkspaceError("not a look")
            if not isinstance(entry.get("id"), str) or not CARD_ID.fullmatch(entry["id"]): raise WorkspaceError("Invalid seed card id")
            name = _text(entry.get("name"), "Look name", 120, True)
            if not isinstance(entry.get("body"), dict): raise WorkspaceError("A look must be an object")
            preset = presets.get(entry["body"].get("preset_id"))
            if preset is None: raise WorkspaceError("its recipe is not in the recipe library")
            supersedes = entry.get("supersedes", [])
            if not isinstance(supersedes, list) or len(supersedes) > 20 or not all(isinstance(d, str) and re.fullmatch(r"[0-9a-f]{64}", d) for d in supersedes):
                raise WorkspaceError("supersedes is a list of up to 20 sha256 digests of earlier shipped versions")
            candidate = dict(entry, name=name, body=validate_body(entry["body"], preset), lineage=validate_lineage(entry.get("lineage", [])))
            # Reuse the Workspace size/JSON checks before its atomic batch, so a bad peer cannot roll back valid seeds.
            studio.assets._card_fields(candidate, True)
            valid.append(candidate)
        except (WorkspaceError, KeyError, TypeError, AttributeError) as error: errors.append(f"{entry.get('id') if isinstance(entry, dict) else entry}: {error}")
    studio.assets.seed_cards(valid)
    studio._look_seed_errors = errors
    return errors


def listing(studio):
    # A swapped sampler/scheduler is a notice for Prepare, not a reason to list the look as unusable.
    errors = ensure_seeds(studio); presets = _presets(studio); result = []
    for card in studio.assets.cards(KIND):
        preset = presets.get(card["body"].get("preset_id"))
        reason = "Its recipe (" + str(card["body"].get("preset_id")) + ") is not in the recipe library." if preset is None else None
        if preset is not None:
            try: validate_body(card["body"], preset)
            except WorkspaceError as error: reason = str(error)
        anchor = next((entry for entry in card["lineage"] if entry.get("role") == "anchor"), None)
        found = studio.assets.asset_by_sha256(anchor.get("sha256")) if anchor else None
        result.append(dict(card, preset_name=(preset or {}).get("name"), usable=reason is None and not card["trashed_at"],
                           unusable_reason=reason or ("This look is put away. Restore it to use it." if card["trashed_at"] else None),
                           anchor_asset_id=found["id"] if found else None))
        if (result[-1]['usable'] and card['origin'] == 'seed'
                and card['id'] == 'look-night-shift-retro-anime'
                and studio.assets.card_digest(card) == NIGHT_SHIFT_PREVIEW_DIGEST):
            result[-1]['visual_reference'] = dict(NIGHT_SHIFT_PREVIEW)
    return {"looks": result, "seed_errors": errors, "generation_submitted": False}


def command(studio, payload):
    """Create, edit, put away or restore a look. Bodies are checked against the recipe they name; the anchor comes from the Workspace."""
    ensure_seeds(studio); notices = []
    if not isinstance(payload, dict): raise WorkspaceError("Look command must be an object")
    payload, action = dict(payload), payload.get("action")
    if action == "create" and payload.get("kind") != KIND: raise WorkspaceError("This route saves looks; the card kind must be " + KIND)
    if action in ("edit", "trash", "restore") and studio.assets.card(payload.get("id"))["kind"] != KIND: raise WorkspaceError("That card is not a look")
    if "body" in payload:
        preset = _presets(studio).get((payload["body"] or {}).get("preset_id") if isinstance(payload["body"], dict) else None)
        if preset is None: raise WorkspaceError("A look names a recipe from the recipe library")
        payload["body"] = validate_body(payload["body"], preset, notices)
    anchor_id = payload.pop("anchor_asset_id", None)
    if anchor_id is not None:
        if action != "create": raise WorkspaceError("The anchor picture is recorded when the look is saved")
        asset = studio.assets.get(anchor_id)
        payload["lineage"] = [{"role": "anchor", "asset_id": asset["id"], "sha256": asset["sha256"], "job_id": asset["job_id"],
                               **({"preset_id": asset["preset_id"]} if asset.get("preset_id") else {})}, *(payload.get("lineage") or [])]
    if "lineage" in payload: validate_lineage(payload["lineage"])
    card = studio.assets.card_command(payload)
    return dict(card, notices=notices) if notices else card


def run_look(studio, value):
    """Validate prepared attribution against the Workspace; edits to Create remain in job controls."""
    if value is None: return None
    if not isinstance(value, dict) or set(value) - {'id', 'name', 'revision', 'options'} or type(value.get('revision')) is not int:
        raise WorkspaceError('A prepared look needs its id, integer revision and optional lines')
    ensure_seeds(studio)
    card = studio.assets.card(value.get('id'))
    if card['kind'] != KIND or card['trashed_at']:
        raise WorkspaceError('This prepared look is unavailable; prepare it again or reset the recipe')
    if card['revision'] != value['revision']:
        raise WorkspaceError('This prepared look changed; prepare it again or reset the recipe')
    on = chosen_options(card['body'].get('options', []), value.get('options'))
    return {'id': card['id'], 'name': card['name'], 'revision': card['revision'], **({'options': on} if on else {})}


def prepare(studio, payload):
    """Create's fields for one look and one typed scene. Reads only; submits nothing (the owner presses Generate)."""
    ensure_seeds(studio)
    if not isinstance(payload, dict) or set(payload) - {"id", "scene", "options", "expected_revision"}:
        raise WorkspaceError("Prepare takes a look id, the scene, and optionally its optional lines and the revision you read")
    card = studio.assets.card(payload.get("id"))
    if card["kind"] != KIND: raise WorkspaceError("That card is not a look")
    if "expected_revision" in payload and payload["expected_revision"] != card["revision"]:
        raise WorkspaceError("This look changed since the page read it; nothing was prepared. Reload looks and try again.", status=409, code="card_revision_conflict", current=card)
    if card["trashed_at"]: raise WorkspaceError("This look is put away. Restore it to use it.")
    preset = _presets(studio).get(card["body"].get("preset_id"))
    if preset is None: raise WorkspaceError("This look's recipe is not in the recipe library")
    notices = []; body = validate_body(card["body"], preset, notices)
    options = body.get("options", []); on = chosen_options(options, payload.get("options"))
    controls = {"positive": compose(body["template"], payload.get("scene"), options, on), **({"negative": body["negative"]} if preset.get("negative") else {}), **body["controls"]}
    return {"preset_id": preset["id"], "preset_name": preset.get("name"), "controls": controls,
            "look": {"id": card["id"], "name": card["name"], "revision": card["revision"], **({"options": on} if options else {})},
            **({"notices": notices} if notices else {}), "generation_submitted": False}
