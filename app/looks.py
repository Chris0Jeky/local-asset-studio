"""Look templates (#1221): an accepted picture's wording, kept as a template with one `{scene}` slot, plus its recipe.

A look is a Workspace card (app/workspace.py `cards`, kind "look"): name, body and lineage, revisioned, reversible trash.
body: preset_id (one text-to-image recipe), template, negative, controls (only inputs that recipe binds), scene_example,
source_prompt (the anchor's own wording, verbatim) and notes. lineage: the pictures it came from, by sha256.
The lab behind it (background-lab-20260927, strand c): words on the same model carry a look to new scenes; a look picture
through a reference route leaks content. Preparing composes Create's fields and never submits (K8: Generate stays a press).
"""
import json
import math
import re
from pathlib import Path

from workspace import WorkspaceError

KIND = "look"
SLOT = "{scene}"
SCENE_MAX = 1000
TEXT_LIMITS = {"template": 4000, "negative": 4000, "scene_example": 1000, "source_prompt": 8000, "notes": 4000}
BODY_FIELDS = {"preset_id", "controls", *TEXT_LIMITS}
# Wording is the template's job and pictures are not part of a look, so these are never stored as look controls.
NOT_CONTROLS = {"positive", "negative", "reference", "last_reference", "mode"}
PICTURE_KEYS = ("reference", "last_reference", "reference_slots")
LINEAGE_ROLES = ("anchor", "evidence", "canon")
SEEDS = "presets/looks.json"


def _text(value, name, maximum, required=False):
    if value is None and not required: return ""
    if not isinstance(value, str) or len(value) > maximum: raise WorkspaceError(f"{name} must be text up to {maximum} characters")
    value = value.strip()
    if required and not value: raise WorkspaceError(f"{name} is required")
    return value


def _bound(preset, key):
    return bool(preset.get(key)) or bool((preset.get("bindings_extra") or {}).get(key))


def recipe_problem(preset):
    """Why this recipe cannot carry a look, or None. A look is words on the same model: one text-to-image recipe."""
    if (preset.get("modality") or "image") != "image": return "A look needs an image recipe; this one makes " + str(preset.get("modality")) + "."
    if not preset.get("positive"): return "This recipe takes no wording, so a look cannot write it."
    if any(preset.get(key) for key in PICTURE_KEYS): return "A look is carried by words on a text-to-image recipe; this recipe takes a picture, and a look picture leaks content (lab 27 Sep 2026)."
    return None


def validate_body(body, preset):
    """The look body, normalized, for this catalog preset; WorkspaceError with a plain reason otherwise."""
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
    controls = body.get("controls", {})
    if not isinstance(controls, dict) or len(controls) > 40: raise WorkspaceError("Look controls must be an object of up to 40 settings")
    clean = {}
    for key, value in controls.items():
        if key in NOT_CONTROLS or not isinstance(key, str): raise WorkspaceError(f"{key} is not a look setting")
        if not _bound(preset, key): raise WorkspaceError(f"{key} is not bound on {preset.get('name') or preset['id']}")
        if isinstance(value, bool) or not isinstance(value, (int, float, str)) or (isinstance(value, float) and not math.isfinite(value)):
            raise WorkspaceError(f"{key} must be a finite number or text")
        if isinstance(value, str) and len(value) > 300: raise WorkspaceError(f"{key} must be up to 300 characters")
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


def compose(template, scene):
    """The template with the typed scene in its one slot: whitespace collapsed, a trailing full stop dropped (the template has its own)."""
    if not isinstance(scene, str): raise WorkspaceError("Type the scene in a few words")
    scene = " ".join(scene.split()).rstrip(" .")
    if not scene: raise WorkspaceError("Type the scene in a few words")
    if len(scene) > SCENE_MAX: raise WorkspaceError(f"Keep the scene under {SCENE_MAX} characters")
    if SLOT in scene: raise WorkspaceError("The scene is the text that fills " + SLOT + "; leave the token out")
    if template.count(SLOT) != 1: raise WorkspaceError("This look's wording has no single " + SLOT + " slot; edit the look")
    return template.replace(SLOT, scene)


def _presets(studio):
    return {p.get("id"): p for p in studio.catalog()["presets"] if isinstance(p, dict)}


def ensure_seeds(studio):
    """Copy shipped looks into the Workspace once per Studio; the Workspace never takes an overwrite. Invalid seeds are reported, not stored."""
    if getattr(studio, "_look_seed_errors", None) is not None: return studio._look_seed_errors
    errors, valid, path = [], [], Path(studio.root) / SEEDS
    try: entries = json.loads(path.read_text(encoding="utf-8")).get("looks", []) if path.is_file() else []
    except (OSError, ValueError, AttributeError) as error: entries, errors = [], [f"{SEEDS} is unreadable: {error}"]
    presets = _presets(studio)
    for entry in entries if isinstance(entries, list) else []:
        try:
            if not isinstance(entry, dict) or entry.get("kind") != KIND: raise WorkspaceError("not a look")
            preset = presets.get((entry.get("body") or {}).get("preset_id"))
            if preset is None: raise WorkspaceError("its recipe is not in the recipe library")
            valid.append(dict(entry, body=validate_body(entry["body"], preset), lineage=validate_lineage(entry.get("lineage", []))))
        except (WorkspaceError, KeyError, TypeError) as error: errors.append(f"{entry.get('id') if isinstance(entry, dict) else entry}: {error}")
    studio.assets.seed_cards(valid)
    studio._look_seed_errors = errors
    return errors


def listing(studio):
    errors = ensure_seeds(studio); presets = _presets(studio); result = []
    for card in studio.assets.cards(KIND):
        preset = presets.get(card["body"].get("preset_id"))
        reason = "Its recipe (" + str(card["body"].get("preset_id")) + ") is not in the recipe library." if preset is None else recipe_problem(preset)
        anchor = next((entry for entry in card["lineage"] if entry.get("role") == "anchor"), None)
        found = studio.assets.asset_by_sha256(anchor.get("sha256")) if anchor else None
        result.append(dict(card, preset_name=(preset or {}).get("name"), usable=reason is None and not card["trashed_at"],
                           unusable_reason=reason or ("This look is put away. Restore it to use it." if card["trashed_at"] else None),
                           anchor_asset_id=found["id"] if found else None))
    return {"looks": result, "seed_errors": errors, "generation_submitted": False}


def command(studio, payload):
    """Create, edit, put away or restore a look. Bodies are checked against the recipe they name; the anchor comes from the Workspace."""
    ensure_seeds(studio)
    if not isinstance(payload, dict): raise WorkspaceError("Look command must be an object")
    payload, action = dict(payload), payload.get("action")
    if action == "create" and payload.get("kind") != KIND: raise WorkspaceError("This route saves looks; the card kind must be " + KIND)
    if action in ("edit", "trash", "restore") and studio.assets.card(payload.get("id"))["kind"] != KIND: raise WorkspaceError("That card is not a look")
    if "body" in payload:
        preset = _presets(studio).get((payload["body"] or {}).get("preset_id") if isinstance(payload["body"], dict) else None)
        if preset is None: raise WorkspaceError("A look names a recipe from the recipe library")
        payload["body"] = validate_body(payload["body"], preset)
    anchor_id = payload.pop("anchor_asset_id", None)
    if anchor_id is not None:
        if action != "create": raise WorkspaceError("The anchor picture is recorded when the look is saved")
        asset = studio.assets.get(anchor_id)
        payload["lineage"] = [{"role": "anchor", "asset_id": asset["id"], "sha256": asset["sha256"], "job_id": asset["job_id"],
                               **({"preset_id": asset["preset_id"]} if asset.get("preset_id") else {})}, *(payload.get("lineage") or [])]
    if "lineage" in payload: validate_lineage(payload["lineage"])
    return studio.assets.card_command(payload)


def prepare(studio, payload):
    """Create's fields for one look and one typed scene. Reads only; submits nothing (the owner presses Generate)."""
    ensure_seeds(studio)
    if not isinstance(payload, dict) or set(payload) - {"id", "scene", "expected_revision"}: raise WorkspaceError("Prepare takes a look id, the scene and optionally the revision you read")
    card = studio.assets.card(payload.get("id"))
    if card["kind"] != KIND: raise WorkspaceError("That card is not a look")
    if "expected_revision" in payload and payload["expected_revision"] != card["revision"]:
        raise WorkspaceError("This look changed since the page read it; nothing was prepared. Reload looks and try again.", status=409, code="card_revision_conflict", current=card)
    if card["trashed_at"]: raise WorkspaceError("This look is put away. Restore it to use it.")
    preset = _presets(studio).get(card["body"].get("preset_id"))
    if preset is None: raise WorkspaceError("This look's recipe is not in the recipe library")
    body = validate_body(card["body"], preset)
    controls = {"positive": compose(body["template"], payload.get("scene")), **({"negative": body["negative"]} if preset.get("negative") else {}), **body["controls"]}
    return {"preset_id": preset["id"], "preset_name": preset.get("name"), "controls": controls,
            "look": {"id": card["id"], "name": card["name"], "revision": card["revision"]}, "generation_submitted": False}
