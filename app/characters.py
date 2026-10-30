"""Character cards (#1205 v1): "my character", a Workspace card (kind "character") whose canon is ONE chosen picture.

Owner decision (16 Oct 2026): any picture can be the canon, regardless of review; a character LoRA comes once about 20
keepers exist (#411, out of scope). Consistency is the point: every new picture goes back to the canon as it is, never to an
edit of an edit. body: who, clothes (with colours), avoid (optional), look_id (optional preferred look card). lineage: the
canon, named by asset id and sha256 like a look's anchor, set only from the Workspace; a swap also keeps the replaced canon as previous_canon. Saving or choosing a card never submits.
"""
import re

import looks
from workspace import CARD_ID, WorkspaceError

KIND = "character"
TEXT_LIMITS = {"who": 600, "clothes": 600, "avoid": 600}   # Make's fields take 600 characters
BODY_FIELDS = {"look_id", *TEXT_LIMITS}
SHA256 = re.compile(r"[0-9a-f]{64}")


def _text(value, name, maximum, required=False):
    if value is None:
        if required: raise WorkspaceError(f"{name} is required")
        return ""
    if not isinstance(value, str) or len(value) > maximum: raise WorkspaceError(f"{name} must be text up to {maximum} characters")
    value = " ".join(value.split())
    if required and not value: raise WorkspaceError(f"{name} is required")
    return value


def validate_body(body):
    """The character body, normalized; WorkspaceError with a plain reason otherwise. who is required, the rest optional."""
    if not isinstance(body, dict): raise WorkspaceError("A character must be an object")
    if set(body) - BODY_FIELDS: raise WorkspaceError("Unknown character fields: " + ", ".join(sorted(map(str, set(body) - BODY_FIELDS))))
    result = {"who": _text(body.get("who"), "Who they are", TEXT_LIMITS["who"], True)}
    for field in ("clothes", "avoid"):
        value = _text(body.get(field), field.capitalize(), TEXT_LIMITS[field])
        if value: result[field] = value
    look = body.get("look_id")
    if look not in (None, ""):
        if not isinstance(look, str) or not CARD_ID.fullmatch(look): raise WorkspaceError("A preferred look is named by its card id")
        result["look_id"] = look
    return result


def canon_of(card, role="canon"):
    return next((entry for entry in card.get("lineage", []) if isinstance(entry, dict) and entry.get("role") == role), None)


def canon_asset(studio, card, role="canon"):
    """The live picture whose bytes are the canon (or the previous canon), or None: the recorded asset if its bytes still match, else any live copy."""
    entry = canon_of(card, role)
    if not entry or not isinstance(entry.get("sha256"), str) or not SHA256.fullmatch(entry["sha256"]): return None
    try:
        asset = studio.assets.get(entry.get("asset_id"))
        if not asset.get("trashed_at") and asset.get("sha256") == entry["sha256"]: return asset
    except WorkspaceError: pass
    return studio.assets.asset_by_sha256(entry["sha256"])


def listing(studio):
    result, saved_looks = [], None
    for card in studio.assets.cards(KIND):
        asset, reason, body = canon_asset(studio, card), None, {}
        previous = canon_asset(studio, card, "previous_canon")
        try: body = validate_body(card["body"])
        except WorkspaceError as error: reason = str(error)
        if asset is None: reason = reason or "Its canon picture is no longer in the library. Restore it, or make another picture the canon."
        elif (asset.get("media_type") or "image") != "image": reason = reason or "Its canon is not a picture."
        if card["trashed_at"]: reason = "This character is put away. Restore it to use it."
        look_note = None
        if body.get("look_id"):
            if saved_looks is None: saved_looks = {look["id"]: look for look in looks.listing(studio)["looks"]}
            look = saved_looks.get(body["look_id"])
            if look and look["trashed_at"]: look_note = "Its preferred look is put away; Make uses the goal's default look."
            elif not look or not look["usable"]: look_note = "Its preferred look's recipe is no longer usable; Make uses the goal's default look."
        result.append(dict(card, usable=reason is None, unusable_reason=reason, canon_asset_id=asset["id"] if asset else None,
                           previous_canon_asset_id=(previous or {}).get("id"), look_note=look_note))
    return {"characters": result, "generation_submitted": False}


def command(studio, payload):
    """Create, edit, put away or restore a character. The canon comes from the Workspace by asset id; the page never writes lineage."""
    if not isinstance(payload, dict): raise WorkspaceError("Character command must be an object")
    payload, action = dict(payload), payload.get("action")
    if "lineage" in payload: raise WorkspaceError("The canon picture is recorded from the library; send canon_asset_id")
    if action == "create" and payload.get("kind") != KIND: raise WorkspaceError("This route saves characters; the card kind must be " + KIND)
    if action in ("edit", "trash", "restore") and studio.assets.card(payload.get("id"))["kind"] != KIND: raise WorkspaceError("That card is not a character")
    if "body" in payload:
        payload["body"] = validate_body(payload["body"])
        look = payload["body"].get("look_id")
        if look:
            try: found = studio.assets.card(look)
            except WorkspaceError: found = None
            if not found or found["kind"] != "look": raise WorkspaceError("The preferred look is not a saved look")
    canon_id = payload.pop("canon_asset_id", None)
    if action == "create" and canon_id is None: raise WorkspaceError("Choose the canon picture: a character starts from one picture")
    if canon_id is not None:
        if action not in ("create", "edit"): raise WorkspaceError("The canon picture is chosen when the character is saved or edited")
        asset = studio.assets.get(canon_id)
        if asset.get("trashed_at"): raise WorkspaceError("That picture is put away; restore it before making it the canon")
        if (asset.get("media_type") or "image") != "image": raise WorkspaceError("A character's canon is a picture")
        record = lambda role, found: {"role": role, "asset_id": found["id"], "sha256": found["sha256"], "job_id": found.get("job_id"), **({"preset_id": found["preset_id"]} if found.get("preset_id") else {})}
        payload["lineage"] = [record("canon", asset)]
        # A swap keeps the one canon it replaces as previous_canon, so the Line-up can offer it back (#1718); one entry, never a chain.
        old = canon_asset(studio, studio.assets.card(payload.get("id"))) if action == "edit" else None
        if old and old["id"] != asset["id"]: payload["lineage"].append(record("previous_canon", old))
    return studio.assets.card_command(payload)
