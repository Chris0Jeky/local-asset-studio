"""Create immutable figure-crop child assets; never submit generation work."""
from __future__ import annotations

from contextlib import closing

import hashlib
import importlib
import io
import json
import os
import re
import time
import uuid
import zlib
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

BASIS_POINTS = 10_000
MAX_FIGURES = 32
MAX_COMMAND_BYTES = 128 * 1024
MAX_PARENT_BYTES = 64 * 1024 * 1024
MAX_PARENT_PIXELS = 40_000_000
MAX_AGGREGATE_CROP_PIXELS = 80_000_000
SUPPORTED_IMAGE_FORMATS = ("PNG", "JPEG", "WEBP")
_ALLOWED_FIELDS = {
    "workspace_id",
    "request_id",
    "asset_id",
    "parent_sha256",
    "rectangles",
    "require_non_overlapping",
}
_RECTANGLE_FIELDS = {"x", "y", "width", "height"}
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_PNG_CRITICAL_CHUNKS = {b"IHDR", b"PLTE", b"IDAT", b"IEND"}


def workspace_error_type(workspace):
    """Return the error class owned by this concrete Workspace implementation."""
    module = importlib.import_module(workspace.__class__.__module__)
    error_type = getattr(module, "WorkspaceError", None)
    if not isinstance(error_type, type) or not issubclass(error_type, Exception):
        raise RuntimeError("Workspace implementation does not expose WorkspaceError")
    return error_type


def _error(workspace, message, **fields):
    return workspace_error_type(workspace)(message, **fields)


def _fingerprint(workspace, payload):
    try:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as error:
        raise _error(workspace, "Figure split command must contain finite JSON values") from error
    if len(raw.encode("utf-8")) > MAX_COMMAND_BYTES:
        raise _error(workspace, "Figure split command exceeds 128 KiB")
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _rectangles(workspace, value, require_non_overlapping):
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_FIGURES:
        raise _error(workspace, f"Mark between 1 and {MAX_FIGURES} figure rectangles")
    result = []
    for rectangle in value:
        if not isinstance(rectangle, dict) or set(rectangle) != _RECTANGLE_FIELDS:
            raise _error(workspace, "Every figure rectangle needs x, y, width and height basis points")
        if any(type(rectangle[key]) is not int for key in _RECTANGLE_FIELDS):
            raise _error(workspace, "Figure rectangle coordinates must be integers")
        x, y, width, height = (rectangle[key] for key in ("x", "y", "width", "height"))
        if x < 0 or y < 0 or width < 1 or height < 1 or x + width > BASIS_POINTS or y + height > BASIS_POINTS:
            raise _error(workspace, "Figure rectangles must be positive and stay inside the 0–10000 basis-point canvas")
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
                    raise _error(workspace, "Figure rectangles overlap; adjust them or allow overlap explicitly")
    return result


def _validate(payload, workspace):
    if not isinstance(payload, dict):
        raise _error(workspace, "Figure split command must be an object")
    if set(payload) - _ALLOWED_FIELDS:
        raise _error(workspace, "Unknown figure split command fields")
    missing = {"workspace_id", "request_id", "asset_id", "parent_sha256", "rectangles"} - set(payload)
    if missing:
        raise _error(workspace, "Figure split command is incomplete: " + ", ".join(sorted(missing)))
    scope = workspace._validate_scope(payload["workspace_id"])
    request_id = workspace.request_id(payload["request_id"])
    asset_id = payload["asset_id"]
    if not isinstance(asset_id, str) or not 1 <= len(asset_id) <= 128:
        raise _error(workspace, "Choose one existing Workspace image")
    parent_sha256 = payload["parent_sha256"]
    if not isinstance(parent_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", parent_sha256):
        raise _error(workspace, "Parent image hash must be 64 lowercase hexadecimal characters")
    require_non_overlapping = payload.get("require_non_overlapping", False)
    if type(require_non_overlapping) is not bool:
        raise _error(workspace, "require_non_overlapping must be true or false")
    rectangles = _rectangles(workspace, payload["rectangles"], require_non_overlapping)
    return scope, request_id, asset_id, parent_sha256, rectangles, _fingerprint(workspace, payload)


def _parent_row(workspace, db, asset_id, parent_sha256):
    row = db.execute("SELECT * FROM assets WHERE id=?", (asset_id,)).fetchone()
    if row is None:
        raise _error(workspace, "Parent asset was not found")
    if row["media_type"] != "image":
        raise _error(workspace, "Only a Workspace image can be split into figures")
    if row["trashed_at"] is not None:
        raise _error(workspace, "Restore the trashed parent image before splitting it")
    if row["sha256"] != parent_sha256:
        raise _error(workspace, "The parent source changed; reopen it before creating figure children")
    return row


def _verify_png_container(raw):
    """Require one unambiguous critical structure, checked CRCs and terminal IEND."""
    if not raw.startswith(_PNG_SIGNATURE):
        raise SyntaxError("PNG signature is invalid")
    data = memoryview(raw)
    try:
        offset = len(_PNG_SIGNATURE)
        seen_ihdr = False
        seen_plte = False
        seen_idat = False
        idat_closed = False
        bit_depth = None
        color_type = None
        while offset < len(data):
            if len(data) - offset < 12:
                raise SyntaxError("PNG chunk is incomplete")
            size = int.from_bytes(data[offset : offset + 4], "big")
            chunk_type_start = offset + 4
            chunk_data_start = offset + 8
            chunk_data_end = chunk_data_start + size
            chunk_end = chunk_data_end + 4
            if chunk_end > len(data):
                raise SyntaxError("PNG chunk exceeds the bounded file")
            chunk_type = bytes(data[chunk_type_start:chunk_data_start])
            expected_crc = int.from_bytes(data[chunk_data_end:chunk_end], "big")
            actual_crc = zlib.crc32(data[chunk_type_start:chunk_data_end]) & 0xFFFFFFFF
            if actual_crc != expected_crc:
                raise SyntaxError("PNG chunk checksum does not match")
            if any(
                byte not in range(ord("A"), ord("Z") + 1)
                and byte not in range(ord("a"), ord("z") + 1)
                for byte in chunk_type
            ):
                raise SyntaxError("PNG chunk type contains a non-letter byte")
            if chunk_type[2] & 0x20:
                raise SyntaxError("PNG chunk type uses the reserved bit")
            if not seen_ihdr:
                if chunk_type != b"IHDR" or size != 13:
                    raise SyntaxError("PNG must begin with one 13-byte IHDR chunk")
                bit_depth = int(data[chunk_data_start + 8])
                color_type = int(data[chunk_data_start + 9])
                if color_type not in (0, 2, 3, 4, 6):
                    raise SyntaxError("PNG IHDR uses an unsupported colour type")
                seen_ihdr = True
            elif chunk_type == b"IHDR":
                raise SyntaxError("PNG contains more than one IHDR chunk")
            if not (chunk_type[0] & 0x20) and chunk_type not in _PNG_CRITICAL_CHUNKS:
                raise SyntaxError("PNG contains an unsupported critical chunk")
            if chunk_type == b"PLTE":
                if seen_plte:
                    raise SyntaxError("PNG contains more than one PLTE chunk")
                if seen_idat:
                    raise SyntaxError("PNG PLTE appears after IDAT")
                if color_type in (0, 4):
                    raise SyntaxError("PNG colour type forbids PLTE")
                if size == 0 or size > 768 or size % 3:
                    raise SyntaxError("PNG PLTE has an invalid length")
                if color_type == 3 and size // 3 > 1 << bit_depth:
                    raise SyntaxError("PNG PLTE exceeds the indexed bit depth")
                seen_plte = True
            elif chunk_type == b"IDAT":
                if idat_closed:
                    raise SyntaxError("PNG IDAT chunks are not consecutive")
                if color_type == 3 and not seen_plte:
                    raise SyntaxError("Indexed PNG is missing PLTE before IDAT")
                seen_idat = True
            elif chunk_type == b"IEND":
                if not seen_idat:
                    raise SyntaxError("PNG has no IDAT data")
                if size != 0 or chunk_end != len(data):
                    raise SyntaxError("PNG IEND is not the complete terminal chunk")
                return
            elif seen_idat:
                idat_closed = True
            offset = chunk_end
        raise SyntaxError("PNG has no terminal IEND chunk")
    finally:
        data.release()


def _read_parent(workspace, asset_id, expected_sha256):
    path = workspace.file(asset_id)
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_PARENT_BYTES + 1)
    except OSError as error:
        raise _error(
            workspace,
            "The parent image snapshot could not be read",
            status=500,
            code="asset_snapshot_unavailable",
        ) from error
    if not raw or len(raw) > MAX_PARENT_BYTES:
        raise _error(workspace, "Parent image must be nonempty and no larger than 64 MiB")
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise _error(workspace, "The parent image bytes changed; no figure children were created")
    try:
        with Image.open(io.BytesIO(raw)) as opened:
            if opened.format not in SUPPORTED_IMAGE_FORMATS:
                raise _error(workspace, "Parent image format must be PNG, JPEG or WebP")
            width, height = opened.size
            if width < 1 or height < 1 or width * height > MAX_PARENT_PIXELS:
                raise _error(workspace, "Parent image must be at most 40 megapixels")
            if getattr(opened, "n_frames", 1) != 1:
                raise _error(workspace, "Animated images cannot be split into figure children")
            # Pixel decode alone accepts some PNGs with missing IEND or damaged
            # chunk CRCs. Walk the bounded chunk stream so the first IEND must be
            # terminal, then let Pillow verify image semantics on the same bytes.
            if opened.format == "PNG":
                _verify_png_container(raw)
            opened.verify()
        with Image.open(io.BytesIO(raw), formats=SUPPORTED_IMAGE_FORMATS) as opened:
            has_transparency = "A" in opened.getbands() or "transparency" in opened.info
            oriented = ImageOps.exif_transpose(opened)
            oriented.load()
            mode = "RGBA" if has_transparency or "A" in oriented.getbands() or "transparency" in oriented.info else "RGB"
            canvas = oriented.convert(mode)
            if oriented is not opened:
                oriented.close()
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as error:
        raise _error(workspace, "Parent asset is not a complete supported still image (PNG, JPEG or WebP)") from error
    return canvas


def _pixel_box(workspace, rectangle, width, height):
    # Project every normalized edge through the same nearest-pixel rule. Using
    # floor for leading edges and ceil for trailing edges makes adjacent source
    # rectangles overlap whenever their shared edge falls between two pixels.
    def edge(value, dimension):
        return (value * dimension + BASIS_POINTS // 2) // BASIS_POINTS

    left = edge(rectangle["x"], width)
    top = edge(rectangle["y"], height)
    right = edge(rectangle["x"] + rectangle["width"], width)
    bottom = edge(rectangle["y"] + rectangle["height"], height)
    right, bottom = min(width, right), min(height, bottom)
    if left >= right or top >= bottom:
        raise _error(workspace, "A marked figure is smaller than one source pixel")
    return {"left": left, "top": top, "right": right, "bottom": bottom}


def _encode_crops(workspace, canvas, rectangles):
    """Consume the canvas; retain only ordered snapshot metadata, not PNG bytes."""
    width, height = canvas.size
    planned = []
    pixels = 0
    try:
        # Validate every box and the total before allocating a crop or publishing.
        for rectangle in rectangles:
            box = _pixel_box(workspace, rectangle, width, height)
            pixels += (box["right"] - box["left"]) * (box["bottom"] - box["top"])
            if pixels > MAX_AGGREGATE_CROP_PIXELS:
                raise _error(workspace, "Figure crops exceed the 80-megapixel aggregate limit")
            planned.append((rectangle, box))
        snapshots = []
        for rectangle, box in planned:
            with closing(canvas.crop((box["left"], box["top"], box["right"], box["bottom"]))) as crop:
                with io.BytesIO() as stream:
                    crop.save(stream, format="PNG", optimize=False, compress_level=6)
                    # A borrowed view avoids an extra encoded-byte copy. Release
                    # it before closing the buffer or starting the next crop.
                    with stream.getbuffer() as data:
                        if not data:
                            raise _error(workspace, "A figure crop encoded as an empty image")
                        snapshot = _snapshot_png(workspace, data)
            snapshots.append((rectangle, box, snapshot))
        return (width, height), snapshots
    finally:
        canvas.close()


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
                raise _error(
                    workspace,
                    "That request ID already identifies a different command; nothing changed",
                    status=409,
                    code="asset_request_reused",
                    request_id=request_id,
                )
            return workspace._observe_receipt(db, json.loads(receipt["result"]), scope)
        parent = _parent_row(workspace, db, asset_id, parent_sha256)
        parent_path = parent["path"]

    canvas = _read_parent(workspace, asset_id, parent_sha256)
    source_size, crops = _encode_crops(workspace, canvas, rectangles)
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
                raise _error(
                    workspace,
                    "That request ID already identifies a different command; nothing changed",
                    status=409,
                    code="asset_request_reused",
                    request_id=request_id,
                )
            return workspace._observe_receipt(db, json.loads(receipt["result"]), scope)
        parent = _parent_row(workspace, db, asset_id, parent_sha256)
        if parent["path"] != parent_path:
            raise _error(workspace, "The parent asset changed while its figures were being prepared")
        existing = db.execute(
            f"SELECT id FROM assets WHERE id IN ({','.join('?' for _ in child_ids)})", child_ids
        ).fetchall()
        if existing:
            raise _error(workspace, "Figure child identity already exists without its receipt; no changes were made")

        stem = re.sub(r"[^A-Za-z0-9._-]", "_", Path(parent["filename"]).stem)[:80] or "figure"
        job_id = "figure-crop:" + request_id
        figures = []
        for index, ((rectangle, box, snapshot), child_id) in enumerate(
            zip(crops, child_ids), 1
        ):
            path, digest, size = snapshot
            source = {
                "operation": "figure-crop",
                "parent_asset_id": asset_id,
                "parent_sha256": parent_sha256,
                "parent_metadata_revision": parent["metadata_revision"],
                "crop_coordinate_policy": "basis-points-nearest-half-up/v1",
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
