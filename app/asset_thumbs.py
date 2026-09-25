"""Disk-cached, bounded thumbnails for Workspace image assets.

Workspace media is content-addressed and never rewritten, so a thumbnail is keyed by the asset's SHA-256, the
requested long edge and THUMB_VERSION; a repeat request is a file read under `<workspace>/thumbs/`. Decodes run
behind a small semaphore: the server is a ThreadingHTTPServer and one library page asks for many previews at once.
Thumbnails are WEBP (alpha kept), EXIF-transposed and never upscaled. A thumbnail is a view, never evidence:
exports, references and review keep reading the original through `AssetWorkspace.file()`.
"""
from __future__ import annotations

import re
import threading
import uuid
import warnings

import file_replace
from workspace import WorkspaceError

SIZES = (256, 384, 512)
DEFAULT_SIZE = 384
# Bump when the rendering changes, together with ASSET_THUMB_VERSION in app/static/workspace.js (a test pins them):
# cached file names, ETags and the ?v= of every thumbnail URL then all change, so no browser keeps an old rendering.
THUMB_VERSION = 1
CONTENT_TYPE = "image/webp"
MAX_PARALLEL_DECODES = 2
_DECODES = threading.BoundedSemaphore(MAX_PARALLEL_DECODES)
SHA256 = re.compile(r"[0-9a-f]{64}")


def requested_size(values):
    """The long edge named by `?w=` (a parse_qs list, or None when absent): one of SIZES, else a 400."""
    if values is None: return DEFAULT_SIZE
    if len(values) != 1 or values[0] not in {str(size) for size in SIZES}:
        raise WorkspaceError("Thumbnail width must be one of " + ", ".join(map(str, SIZES)), code="invalid_thumbnail_size")
    return int(values[0])


def etag(digest, size): return f'"{digest}-{size}-v{THUMB_VERSION}"'


def url_version(digest):
    """The `?v=` a thumbnail URL carries (workspace.js assetThumbUrl): rendering version plus content prefix."""
    return f"{THUMB_VERSION}-{digest[:16]}"


def names_content(values, tag):
    """Whether a request's `?v=` (a parse_qs list or None) names the bytes behind `tag`, making the response immutable."""
    return values == [url_version(tag[1:65])]


def transparent(image):
    """Alpha channel or tRNS/palette transparency (RGB, L and P PNGs included); Pillow < 10.1 lacks the property."""
    flag = getattr(image, "has_transparency_data", None)
    return flag if isinstance(flag, bool) else image.mode in ("RGBA", "LA", "PA", "RGBa", "La") or "transparency" in image.info


def render(source, size):
    """A decoded, oriented, reduced copy of `source` whose long edge is at most `size`. Raises Pillow's errors."""
    from PIL import Image, ImageOps
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)  # as native_exports: oversized is unreadable
        with Image.open(source) as image:
            image.draft(None, (size, size))  # JPEG: decode at a reduced scale no smaller than the target
            alpha = transparent(image)
            image = ImageOps.exif_transpose(image).convert("RGBA" if alpha else "RGB")
    image.thumbnail((size, size), Image.Resampling.LANCZOS)  # shrinks only; a small image keeps its size
    return image


def thumbnail(workspace, asset_id, size=DEFAULT_SIZE):
    """(path, etag) of the cached thumbnail for an image asset, rendering it once. WorkspaceError for anything else."""
    if size not in SIZES: raise WorkspaceError("Unsupported thumbnail size", code="invalid_thumbnail_size")
    asset = workspace.get(asset_id)
    if asset["media_type"] != "image":
        raise WorkspaceError("Only image assets have thumbnails", status=404, code="thumbnail_unavailable")
    digest = asset["sha256"]
    if not isinstance(digest, str) or not SHA256.fullmatch(digest):
        raise WorkspaceError("Asset content identity is unavailable", status=404, code="thumbnail_unavailable")
    folder = workspace.root / "thumbs"
    target, tag = folder / f"{digest}-{size}-v{THUMB_VERSION}.webp", etag(digest, size)
    if target.is_file(): return target, tag
    source = workspace.file(asset_id)
    from PIL import Image
    with _DECODES:
        if target.is_file(): return target, tag  # another request rendered it while this one waited
        try: image = render(source, size)
        except (OSError, ValueError, SyntaxError, EOFError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise WorkspaceError("The image could not be decoded for a thumbnail; open the original instead",
                                 status=422, code="thumbnail_unreadable") from exc
        folder.mkdir(exist_ok=True)
        temporary = folder / (uuid.uuid4().hex + ".part")
        try:
            image.save(temporary, "WEBP", quality=80, method=4)
            try: file_replace.replace(temporary, target)
            except PermissionError:
                if not target.is_file(): raise  # a same-key render that won the race is equally valid
        except OSError as exc:
            raise WorkspaceError("The thumbnail could not be written", status=500, code="thumbnail_unwritable") from exc
        finally: temporary.unlink(missing_ok=True)
    return target, tag
