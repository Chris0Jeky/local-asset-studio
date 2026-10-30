"""Repair a marked region (#1857): the owner drags boxes over a Library picture and Prepare composes the RGBA input a
`requires_rgba_mask` recipe reads (RGB = the picture, alpha 0 inside the boxes, 255 elsewhere; LoadImage MASK = 1 - alpha).
The mask is the owner's, never detected and never inferred from transparency (#245). Prepare stores it as an upload under the
creation's privacy and returns a plan bound to the source sha; nothing is queued. Generate stays the owner's press, where
`Studio._validate_rgba_mask_reference` checks the attached file like any manual RGBA upload.
"""
from __future__ import annotations

from PIL import Image

import creation_privacy as privacy_scope
import tiles

VERSION = 1
MAX_BOXES = 16
MIN_SIDE = 8
MAX_SHARE = 0.6   # a mark this large is a whole-picture change: an image-to-image recipe redraws it properly
FIELDS = {"asset_id", "preset_id", "boxes", "privacy"}


def boxes_value(value, width, height):
    """The owner's boxes as [[x0,y0,x1,y1], ...] whole source pixels, each inside the picture and at least MIN_SIDE a side."""
    if not isinstance(value, list) or not value: raise ValueError("Mark the region to repair: drag at least one box on the picture.")
    if len(value) > MAX_BOXES: raise ValueError("Mark at most %d boxes." % MAX_BOXES)
    boxes = []
    for box in value:
        if not isinstance(box, list) or len(box) != 4 or any(type(v) is not int for v in box): raise ValueError("Each box is four whole pixel numbers: x0,y0,x1,y1.")
        x0, y0, x1, y1 = box
        if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height): raise ValueError("The box %d,%d,%d,%d is not inside the %d × %d picture." % (x0, y0, x1, y1, width, height))
        if x1 - x0 < MIN_SIDE or y1 - y0 < MIN_SIDE: raise ValueError("The box %d,%d,%d,%d is too small: each side needs at least %d px." % (x0, y0, x1, y1, MIN_SIDE))
        boxes.append([x0, y0, x1, y1])
    return boxes


def alpha_mask(size, boxes):
    """L mask: 0 inside the union of the boxes (the repair region), 255 elsewhere (protected)."""
    alpha = Image.new("L", size, 255)
    for box in boxes: alpha.paste(0, tuple(box))
    return alpha


def repair_input(source, boxes):
    rgba = source.convert("RGB").convert("RGBA"); rgba.putalpha(alpha_mask(rgba.size, boxes)); return rgba


def prepare(studio, payload, privacy="regular", creation_privacy="regular"):
    """Compose and store one RGBA repair input from a library picture and the owner's boxes. Nothing is queued or submitted."""
    if not isinstance(payload, dict) or not set(payload) <= FIELDS or not {"asset_id", "preset_id", "boxes"} <= set(payload):
        raise ValueError("Repair prepare takes asset_id, preset_id and boxes.")
    classification = privacy_scope.normalize(creation_privacy)
    preset = studio.preset(payload["preset_id"])
    if not preset.get("requires_rgba_mask") or preset.get("tile_route"): raise ValueError("Choose a masked-repair recipe; this one does not read a marked region.")
    context, source = tiles._source(studio, payload["asset_id"], privacy)
    # Privacy follows the source (as /api/assets/reference): a private picture is repaired only by a private creation.
    if studio.assets.get(context["asset_id"], privacy=privacy).get("privacy", "regular") == "private" and classification != "private":
        raise ValueError("Keep this private picture private when repairing it.")
    width, height = source.size
    if width % 8 or height % 8: raise ValueError("Masked repair needs a width and height divisible by 8; this picture is %d × %d and is never padded or cropped." % (width, height))
    boxes = boxes_value(payload["boxes"], width, height)
    picture = repair_input(source, boxes)
    marked = picture.getchannel("A").histogram()[0]
    if marked >= MAX_SHARE * width * height:
        raise ValueError("The marked region covers %d%% of the picture. Masked repair fixes a part; for a whole-picture change use an image-to-image recipe." % round(100 * marked / (width * height)))
    upload = studio.upload("repair-mask", "image/png", tiles.png_bytes(picture), privacy=classification)
    plan = {"version": VERSION, "preset_id": preset["id"], "source_asset_id": context["asset_id"], "source_sha256": context["sha256"],
            "mask_file": upload["file"], "mask_sha256": upload["sha256"], "boxes": boxes, "size": [width, height]}
    return {"plan": plan, "file": upload["file"], "sha256": upload["sha256"], "width": width, "height": height, "preset_id": preset["id"],
            "context": context, "generation_submitted": False}
