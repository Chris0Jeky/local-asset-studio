"""Bounded native asset exports for trusted Studio asset records.

This module packages supplied media only.  It does not submit generation, accept
art, inspect licences, evaluate user code, or start Godot.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import warnings
import zipfile


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
import game_asset_media as media
import godot_asset_adapter as godot
import krita_roundtrip


MAX_IMAGES = 32
MAX_PIXELS = 16 * 1024 * 1024
IMAGE_TYPES = {"image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WEBP"}
GLB_TYPE = "model/gltf-binary"
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)


class NativeExportError(ValueError):
    """A requested native export does not meet the bounded file contract."""


def require(condition, message):
    if not condition:
        raise NativeExportError(message)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _slug(value, name):
    require(isinstance(value, str) and re.fullmatch(r"[a-z][a-z0-9-]{1,63}", value),
            f"Invalid {name}")
    return value


def _text(value, name):
    require(isinstance(value, str) and 0 < len(value.strip()) <= 12000, f"Invalid {name}")
    return value


def _json_value(value, name):
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise NativeExportError(f"Invalid {name}: JSON value required") from exc


def _relative_file(root, value, name):
    _text(value, name)
    require("\0" not in value and "\\" not in value, f"Invalid {name}")
    candidate = PurePosixPath(value)
    require(not candidate.is_absolute() and ".." not in candidate.parts and candidate.parts,
            f"{name} escapes media_root")
    path = (root / Path(*candidate.parts)).resolve()
    require(path.is_relative_to(root) and path.is_file(), f"{name} is missing or escapes media_root")
    return path


def _filename(value):
    _text(value, "filename")
    require("/" not in value and "\\" not in value and "\0" not in value and Path(value).name == value,
            "filename must be a single filename")
    return value


def _write_json(path, value, replace=False):
    payload = json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    mode = "w" if replace else "x"
    with Path(path).open(mode, encoding="utf-8", newline="\n") as stream:
        stream.write(payload)


def _zip_entry(archive, source, name):
    info = zipfile.ZipInfo(name, date_time=ZIP_EPOCH)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o600 << 16
    with Path(source).open("rb") as input_stream, archive.open(info, "w") as output_stream:
        shutil.copyfileobj(input_stream, output_stream, 1024 * 1024)


class NativeExports:
    """Create exclusive atlas, ORA, or non-executed Godot packages from known assets."""

    def __init__(self, repo_root, media_root, godot_path=None):
        self.repo_root = Path(repo_root).expanduser().resolve()
        self.media_root = Path(media_root).expanduser().resolve()
        require(self.repo_root.is_dir(), "repo_root must be an existing directory")
        require(self.media_root.is_dir(), "media_root must be an existing directory")
        require((self.repo_root / "scripts" / "game_asset_media.py").is_file(),
                "repo_root has no game_asset_media adapter")
        require((self.repo_root / "scripts" / "godot_asset_adapter.py").is_file(),
                "repo_root has no Godot adapter")
        self.godot_path = None
        if godot_path is not None:
            candidate = Path(godot_path).expanduser()
            require(candidate.is_absolute(), "godot_path must be an absolute local executable file")
            candidate = candidate.resolve()
            require(candidate.is_file(), "godot_path must be a local executable file")
            self.godot_path = candidate

    def _asset_records(self, kind, assets):
        require(isinstance(assets, list), "assets must be an ordered list")
        images = []
        glb = None
        seen = set()
        for index, raw in enumerate(assets):
            require(isinstance(raw, dict), f"Asset {index} must be an object")
            asset_id = _slug(raw.get("id"), "asset ID")
            require(asset_id not in seen, "Duplicate asset ID")
            seen.add(asset_id)
            filename = _filename(raw.get("filename"))
            media_type = raw.get("media_type")
            require(media_type in set(IMAGE_TYPES) | {GLB_TYPE}, "Unsupported media_type")
            source = _relative_file(self.media_root, raw.get("path"), "asset path")
            supplied_sha = raw.get("sha256")
            require(isinstance(supplied_sha, str) and re.fullmatch(r"[0-9a-f]{64}", supplied_sha),
                    "Asset requires lowercase SHA-256")
            actual_sha = sha256(source)
            require(actual_sha == supplied_sha, f"Asset hash mismatch: {asset_id}")
            record = {"id": asset_id, "filename": filename, "media_type": media_type,
                      "source": source, "sha256": actual_sha}
            for field in ("recipe", "metadata"):
                if field in raw:
                    record[field] = _json_value(raw[field], f"asset {field}")
            if media_type in IMAGE_TYPES:
                images.append(record)
            else:
                require(glb is None, "At most one GLB asset is supported")
                glb = record
        require(1 <= len(images) <= MAX_IMAGES, "Expected 1..32 ordered image assets")
        if kind in {"atlas", "ora"}:
            require(glb is None, f"{kind} does not accept GLB assets")
        return images, glb

    def _images(self, records):
        try:
            from PIL import Image, ImageCms
        except ImportError as exc:
            raise NativeExportError("Pillow is required for native image exports") from exc
        converted = []
        dimensions = None
        total_pixels = 0
        for record in records:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(record["source"]) as source:
                    require(source.format == IMAGE_TYPES[record["media_type"]],
                            f"Asset media_type does not match bytes: {record['id']}")
                    source.load()
                    require(1 <= source.width <= 8192 and 1 <= source.height <= 8192,
                            "Image dimensions exceed native export limits")
                    total_pixels += source.width * source.height
                    require(total_pixels <= MAX_PIXELS, "Total image pixels exceed native export limit")
                    current = (source.width, source.height)
                    require(dimensions is None or current == dimensions,
                            "All images must share one canvas; no individual trimming or resizing occurs")
                    dimensions = current
                    profile = source.info.get("icc_profile")
                    if profile:
                        try:
                            image = ImageCms.profileToProfile(
                                source, ImageCms.ImageCmsProfile(io.BytesIO(profile)),
                                ImageCms.createProfile("sRGB"), outputMode="RGBA")
                        except (ImageCms.PyCMSError, OSError, ValueError) as exc:
                            raise NativeExportError(f"Invalid ICC profile: {record['id']}") from exc
                    else:
                        image = source.convert("RGBA")
                    converted.append((record, image.copy()))
        return dimensions, total_pixels, converted

    def _options(self, options, records, dimensions):
        count = len(records)
        require(isinstance(options, dict), "options must be an object")
        allowed = {"clip", "duration_ms", "anchor", "loop", "filter", "columns", "layer_names"}
        require(set(options) <= allowed, "Unknown native export option")
        clip = _slug(options.get("clip", "native-export"), "clip")
        value = options.get("duration_ms", 100)
        durations = value if isinstance(value, list) else [value] * count
        require(isinstance(durations, list) and len(durations) == count
                and all(type(item) is int and 1 <= item <= 60000 for item in durations),
                "duration_ms must be one integer or one valid integer per image")
        anchor = options.get("anchor", [dimensions[0] // 2, dimensions[1]])
        require(isinstance(anchor, list) and len(anchor) == 2 and all(type(item) is int for item in anchor)
                and 0 <= anchor[0] <= dimensions[0] and 0 <= anchor[1] <= dimensions[1],
                "anchor must be [x,y] within the shared canvas")
        loop = options.get("loop", True)
        require(type(loop) is bool, "loop must be boolean")
        texture_filter = options.get("filter", "nearest")
        require(texture_filter in {"nearest", "linear"}, "filter must be nearest or linear")
        columns = options.get("columns", min(8, count))
        require(type(columns) is int and 1 <= columns <= MAX_IMAGES, "columns must be 1..32")
        names = options.get("layer_names")
        if names is None:
            names = [Path(record["filename"]).stem for record in records]
        require(isinstance(names, list) and len(names) == count, "layer_names must match image count")
        names = [_text(name, "layer name") for name in names]
        return {"clip": clip, "duration_ms": durations, "anchor": anchor, "loop": loop,
                "filter": texture_filter, "columns": columns, "layer_names": names}

    def _artifacts(self, output_root):
        return [{"path": path.relative_to(output_root).as_posix(), "sha256": sha256(path),
                 "bytes": path.stat().st_size}
                for path in sorted(output_root.rglob("*"))
                if path.is_file() and ".godot" not in path.relative_to(output_root).parts]

    def _pack(self, output_root):
        pack = output_root / "native-sources.zip"
        with zipfile.ZipFile(pack, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(output_root.rglob("*")):
                relative = path.relative_to(output_root)
                if path.is_file() and path != pack and ".godot" not in relative.parts:
                    _zip_entry(archive, path, relative.as_posix())
        return pack

    def execute(self, output_root, kind, assets, options):
        require(kind in {"atlas", "ora", "godot"}, "kind must be atlas, ora, or godot")
        target = Path(output_root).expanduser()
        require(target.is_absolute(), "output_root must be absolute")
        target = target.resolve()
        require(not target.exists(), "output_root must be new")
        records, glb = self._asset_records(kind, assets)
        dimensions, total_pixels, converted = self._images(records)
        resolved_options = self._options(options, records, dimensions)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.mkdir()
        try:
            (target / "sources").mkdir()
            (target / "interchange").mkdir()
            snapshots = []
            for index, record in enumerate(records + ([glb] if glb else [])):
                suffix = Path(record["filename"]).suffix.lower()
                snapshot = target / "sources" / f"{index:02d}-{record['id']}{suffix}"
                shutil.copyfile(record["source"], snapshot)
                require(sha256(snapshot) == record["sha256"], "Source snapshot copy failed")
                snapshots.append({"id": record["id"], "media_type": record["media_type"],
                                  "original_filename": record["filename"],
                                  "source_snapshot": snapshot.relative_to(target).as_posix(),
                                  "sha256": record["sha256"],
                                  **{field: record[field] for field in ("recipe", "metadata") if field in record}})
            frames = []
            for index, (record, image) in enumerate(converted):
                interchange = target / "interchange" / f"frame-{index:02d}-{record['id']}.png"
                image.save(interchange, format="PNG")
                frames.append({"id": record["id"], "path": interchange.relative_to(target).as_posix(),
                               "sha256": sha256(interchange), "duration_ms": resolved_options["duration_ms"][index]})
            frame_manifest = {"schema_version": 1, "clip": resolved_options["clip"],
                              "canvas": list(dimensions), "anchor": resolved_options["anchor"],
                              "loop": resolved_options["loop"], "frames": frames}
            _write_json(target / "frames.json", frame_manifest)
            recipe = {"schema_version": 1, "kind": kind, "options": resolved_options,
                      "input_order": [record["id"] for record in records]}
            _write_json(target / "recipe.json", recipe)
            output_details = {}
            if kind in {"atlas", "godot"}:
                atlas = media.atlas(frame_manifest, target, target / "atlas", columns=resolved_options["columns"])
                manifest_path = target / "atlas" / "manifest.json"
                atlas["filter"] = resolved_options["filter"]
                _write_json(manifest_path, atlas, replace=True)
                output_details["atlas"] = {"manifest": "atlas/manifest.json", "png": "atlas/atlas.png",
                                           "frames": len(frames), "dimensions": atlas["dimensions"]}
            if kind == "ora":
                layers = {"schema_version": 1, "name": resolved_options["clip"], "canvas": list(dimensions),
                          "layers": [{"id": frame["id"], "name": resolved_options["layer_names"][index],
                                      "path": frame["path"], "sha256": frame["sha256"]}
                                     for index, frame in enumerate(frames)]}
                _write_json(target / "layers.json", layers)
                result = media.ora(layers, target, target / "layers.ora")
                output_details["ora"] = {"path": "layers.ora", "layers": result["layers"]}
            if kind == "godot":
                glb_path = None
                if glb:
                    glb_path = next(item["source_snapshot"] for item in snapshots if item["id"] == glb["id"])
                package = godot.package_project(target, "atlas/manifest.json", target / "godot", glb_path)
                output_details["godot"] = {"project": "godot", "frame_count": package["frame_count"],
                                           "glb_included": glb is not None,
                                           "configured_executable": self.godot_path.name if self.godot_path else None,
                                           "executed": False}
            limitations = ["No generation was submitted.", "No art acceptance or licensing decision is made.",
                           "Still images were converted to RGBA sRGB PNG without resizing or individual trimming."]
            if kind == "ora":
                limitations.append("ORA preserves flat normal RGBA layers only; it omits animation, rigs, groups, masks, non-normal blend modes, and ICC profiles.")
            if kind == "godot":
                limitations.append("Godot packaging uses fixed local templates only; this export does not start Godot or claim engine verification.")
            metadata = {"schema_version": 1, "kind": kind, "source_provenance": snapshots,
                        "measurements": {"canvas": list(dimensions), "image_count": len(frames),
                                         "total_source_pixels": total_pixels, "anchor": resolved_options["anchor"],
                                         "durations_ms": resolved_options["duration_ms"], "loop": resolved_options["loop"],
                                         "filter": resolved_options["filter"]}, "outputs": output_details,
                        "limitations": limitations}
            _write_json(target / "metadata.json", metadata)
            self._pack(target)
            return {"kind": kind, "artifacts": self._artifacts(target), "source_provenance": snapshots,
                    "measurements": metadata["measurements"], "limitations": limitations}
        except Exception as exc:
            # Keep the exclusive attempt directory for diagnosis; never erase partial native sources.
            _write_json(target/'failure.json',{'status':'failed','message':str(exc)[:1000]})
            raise
