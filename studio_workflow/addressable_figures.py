"""Create immutable figure-crop child assets; never submit generation work."""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import time
import uuid
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

try:
    from workspace import WorkspaceError
except ModuleNotFoundError as error:
    if error.name != "workspace":
        raise
    from app.workspace import WorkspaceError

BASIS_POINTS = 10_000
MAX_FIGURES = 32
MAX_COMMAND_BYTES = 128 * 1024
MAX_PARENT_BYTES = 64 * 1024 * 1024
MAX_PARENT_PIXELS = 40_000_000
MAX_AGGREGATE_CROP_PIXELS = 80_000_000
_ALLOWED_FIELDS = {
    "workspace_id",
    "request_id",
    "asset_id",
    "parent_sha256",
    "rectangles",
    "require_non_overlapping",
}
_RECTANGLE_FIELDS = {"x", "y", "width", "height"}


def _fingerprint(payload):
    try:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as error:
        raise WorkspaceError("Figure split command must contain finite JSON values") from error
    if len(raw.encode("utf-8")) > MAX_COMMAND_BYTES:
        raise WorkspaceError("Figure split command exceeds 128 KiB")
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _rectangles(value, require_non_overlapping):
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_FIGURES:
        raise WorkspaceError(f"Mark between 1 and {MAX_FIGURES} figure rectangles")
    result = []
    for rectangle in value:
        if not isinstance(rectangle, dict) or set(rectangle) != _RECTANGLE_FIELDS:
            raise WorkspaceError("Every figure rectangle needs x, y, width and height basis points")
        if any(type(rectangle[key]) is not int for key in _RECTANGLE_FIELDS):
            raise WorkspaceError("Figure rectangle coordinates must be integers")
        x, y, width, height = (rectangle[key] for key in ("x", "y", "width", "height"))
        if x < 0 or y < 0 or width < 1 or height < 1 or x + width > BASIS_POINTS or y + height > BASIS_POINTS:
            raise WorkspaceError("Figure rectangles must be positive and stay inside the 0–10000 basis-point canvas")
        result.append({"x": x, "y": y, "width": width, "height": height})
    if require_non_overlapping:
        for index, left in enumerate(result):
            for right in result[index + 1 :]:
                if (
                    left["x"] < right["x"] + right["width"]
                    and right["x"] < left["x"] + left["width"]
                    and left["y"] < right["y"] + right["height"]
                    and right["y"] < left["y"] + left["height"]
                ):
                    raise WorkspaceError("Figure rectangles overlap; adjust them or allow overlap explicitly")
    return result


def _validate(payload, workspace):
    if not isinstance(payload, dict):
        raise WorkspaceError("Figure split command must be an object")
    if set(payload) - _ALLOWED_FIELDS:
        raise WorkspaceError("Unknown figure split command fields")
    missing = {"workspace_id", "request_id", "asset_id", "parent_sha256", "rectangles"} - set(payload)
    if missing:
        raise WorkspaceError("Figure split command is incomplete: " + ", ".join(sorted(missing)))
    scope = workspace._validate_scope(payload["workspace_id"])
    request_id = workspace.request_id(payload["request_id"])
    asset_id = payload["asset_id"]
    if not isinstance(asset_id, str) or not 1 <= len(asset_id) <= 128:
        raise WorkspaceError("Choose one existing Workspace image")
    parent_sha256 = payload["parent_sha256"]
    if not isinstance(parent_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", parent_sha256):
        raise WorkspaceError("Parent image hash must be 64 lowercase hexadecimal characters")
    require_non_overlapping = payload.get("require_non_overlapping", False)
    if type(require_non_overlapping) is not bool:
        raise WorkspaceError("require_non_overlapping must be true or false")
    rectangles = _rectangles(payload["rectangles"], require_non_overlapping)
    return scope, request_id, asset_id, parent_sha256, rectangles, _fingerprint(payload)


def _parent_row(workspace, db, asset_id, parent_sha256):
    row = db.execute("SELECT * FROM assets WHERE id=?", (asset_id,)).fetchone()
    if row is None:
        raise WorkspaceError("Parent asset was not found")
    if row["media_type"] != "image":
        raise WorkspaceError("Only a Workspace image can be split into figures")
    if row["trashed_at"] is not None:
        raise WorkspaceError("Restore the trashed parent image before splitting it")
    if row["sha256"] != parent_sha256:
        raise WorkspaceError("The parent source changed; reopen it before creating figure children")
    return row


def _read_parent(workspace, asset_id, expected_sha256):
    path = workspace.file(asset_id)
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_PARENT_BYTES + 1)
    except OSError as error:
        raise WorkspaceError(
            "The parent image snapshot could not be read",
            status=500,
            code="asset_snapshot_unavailable",
        ) from error
    if not raw or len(raw) > MAX_PARENT_BYTES:
        raise WorkspaceError("Parent image must be nonempty and no larger than 64 MiB")
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise WorkspaceError("The parent image bytes changed; no figure children were created")
    try:
        with Image.open(io.BytesIO(raw)) as opened:
            if getattr(opened, "n_frames", 1) != 1:
                raise WorkspaceError("Animated images cannot be split into figure children")
            oriented = ImageOps.exif_transpose(opened)
            oriented.load()
            width, height = oriented.size
            if width < 1 or height < 1 or width * height > MAX_PARENT_PIXELS:
                raise WorkspaceError("Parent image must be at most 40 megapixels")
            mode = "RGBA" if "A" in oriented.getbands() else "RGB"
            canvas = oriented.convert(mode)
            if oriented is not opened:
                oriented.close()
    except WorkspaceError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as error:
        raise WorkspaceError("Parent asset is not a complete supported still image") from error
    return canvas


def _pixel_box(rectangle, width, height):
    left = rectangle["x"] * width // BASIS_POINTS
    top = rectangle["y"] * height // BASIS_POINTS
    right = ((rectangle["x"] + rectangle["width"]) * width + BASIS_POINTS - 1) // BASIS_POINTS
    bottom = ((rectangle["y"] + rectangle["height"]) * height + BASIS_POINTS - 1) // BASIS_POINTS
    right, bottom = min(width, right), min(height, bottom)
    if left >= right or top >= bottom:
        raise WorkspaceError("A marked figure is smaller than one source pixel")
    return {"left": left, "top": top, "right": right, "bottom": bottom}


def _encode_crops(canvas, rectangles):
    width, height = canvas.size
    encoded = []
    pixels = 0
    try:
        for rectangle in rectangles:
            box = _pixel_box(rectangle, width, height)
            pixels += (box["right"] - box["left"]) * (box["bottom"] - box["top"])
            if pixels > MAX_AGGREGATE_CROP_PIXELS:
                raise WorkspaceError("Figure crops exceed the 80-megapixel aggregate limit")
            with canvas.crop((box["left"], box["top"], box["right"], box["bottom"])) as crop:
                stream = io.BytesIO()
                crop.save(stream, format="PNG", optimize=False, compress_level=6)
                data = stream.getvalue()
            if not data:
                raise WorkspaceError("A figure crop encoded as an empty image")
            encoded.append((rectangle, box, data))
    finally:
        canvas.close()
    return (width, height), encoded


def _snapshot_png(workspace, data):
    digest = hashlib.sha256(data).hexdigest()
    destination = workspace.media / (digest + ".png")
    temporary = workspace.media / (uuid.uuid4().hex + ".part")
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if destination.exists():
            workspace._verify_snapshot(destination, digest)
        else:
            try:
                os.link(temporary, destination)
            except FileExistsError:
                workspace._verify_snapshot(destination, digest)
        return str(destination.relative_to(workspace.root)), digest, len(data)
    finally:
        temporary.unlink(missing_ok=True)


def split_figures(workspace, payload):
    """Create ordered child assets and their immutable receipt in one DB transaction."""
    scope, request_id, asset_id, parent_sha256, rectangles, fingerprint = _validate(payload, workspace)
    with workspace.connection() as db:
        db.execute("BEGIN")
        identity = workspace._check_scope(db, scope)
        receipt = db.execute(
            "SELECT fingerprint,result FROM asset_commands WHERE request_id=?", (request_id,)
        ).fetchone()
        if receipt:
            if receipt["fingerprint"] != fingerprint:
                raise WorkspaceError(
                    "That request ID already identifies a different command; nothing changed",
                    status=409,
                    code="asset_request_reused",
                    request_id=request_id,
                )
            return workspace._observe_receipt(db, json.loads(receipt["result"]), scope)
        parent = _parent_row(workspace, db, asset_id, parent_sha256)
        parent_path = parent["path"]

    canvas = _read_parent(workspace, asset_id, parent_sha256)
    source_size, crops = _encode_crops(canvas, rectangles)
    snapshots = [_snapshot_png(workspace, data) for _, _, data in crops]
    child_ids = [
        uuid.uuid5(uuid.NAMESPACE_URL, f"asset-studio:figure:{identity}:{request_id}:{index}").hex
        for index in range(len(crops))
    ]
    created_at = time.time()

    with workspace.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        identity = workspace._check_scope(db, scope)
        receipt = db.execute(
            "SELECT fingerprint,result FROM asset_commands WHERE request_id=?", (request_id,)
        ).fetchone()
        if receipt:
            if receipt["fingerprint"] != fingerprint:
                raise WorkspaceError(
                    "That request ID already identifies a different command; nothing changed",
                    status=409,
                    code="asset_request_reused",
                    request_id=request_id,
                )
            return workspace._observe_receipt(db, json.loads(receipt["result"]), scope)
        parent = _parent_row(workspace, db, asset_id, parent_sha256)
        if parent["path"] != parent_path:
            raise WorkspaceError("The parent asset changed while its figures were being prepared")
        existing = db.execute(
            f"SELECT id FROM assets WHERE id IN ({','.join('?' for _ in child_ids)})", child_ids
        ).fetchall()
        if existing:
            raise WorkspaceError("Figure child identity already exists without its receipt; no changes were made")

        stem = re.sub(r"[^A-Za-z0-9._-]", "_", Path(parent["filename"]).stem)[:80] or "figure"
        job_id = "figure-crop:" + request_id
        figures = []
        for index, ((rectangle, box, _), snapshot, child_id) in enumerate(
            zip(crops, snapshots, child_ids), 1
        ):
            path, digest, size = snapshot
            source = {
                "operation": "figure-crop",
                "parent_asset_id": asset_id,
                "parent_sha256": parent_sha256,
                "request_id": request_id,
                "crop_basis_points": rectangle,
                "crop_pixels": box,
                "source_width": source_size[0],
                "source_height": source_size[1],
                "generation_submitted": False,
            }
            db.execute(
                """INSERT INTO assets
                (id,job_id,output_index,title,media_type,path,filename,sha256,bytes,
                 created_at,preset_id,preset_name,source,lineage)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    child_id,
                    job_id,
                    index - 1,
                    str(parent["title"])[:180] + f" · Figure {index}",
                    "image",
                    path,
                    f"{stem}-figure-{index}.png",
                    digest,
                    size,
                    created_at,
                    parent["preset_id"],
                    parent["preset_name"],
                    json.dumps(source, sort_keys=True, separators=(",", ":")),
                    json.dumps([asset_id]),
                ),
            )
            figures.append(
                {
                    "asset_id": child_id,
                    "index": index,
                    "sha256": digest,
                    "bytes": size,
                    "crop_basis_points": rectangle,
                    "crop_pixels": box,
                }
            )
        result = {
            "status": "created",
            "request_id": request_id,
            "action": "split_figures",
            "workspace_id": identity,
            "parent_asset_id": asset_id,
            "parent_sha256": parent_sha256,
            "created": child_ids,
            "figures": figures,
            "generation_submitted": False,
        }
        db.execute(
            "INSERT INTO asset_commands VALUES (?,?,?,?)",
            (request_id, fingerprint, json.dumps(result, sort_keys=True, separators=(",", ":")), created_at),
        )
        return workspace._observe_receipt(db, result, scope)


def install(workspace_type):
    """Install the bounded primitive on the existing Workspace class at its extension seam."""
    existing = getattr(workspace_type, "split_figures", None)
    if existing is not None and existing is not split_figures:
        raise RuntimeError("AssetWorkspace already has a different split_figures implementation")
    workspace_type.split_figures = split_figures
