"""Immutable local storage for editable pose artifacts. Storage grants no execution authority."""
from __future__ import annotations

import hashlib
import os
import re
import stat
import uuid
from pathlib import Path

from . import pose_artifact

DIRECTORY = "pose-artifacts"
SUFFIX = ".pose.json"
_ID = re.compile(r"[0-9a-f]{64}\Z")


def _directory(experiments) -> Path:
    root = Path(experiments).resolve()
    directory = root / DIRECTORY
    directory.mkdir(parents=True, exist_ok=True)
    if directory.is_symlink() or not directory.is_dir() or directory.resolve().parent != root:
        raise ValueError("Editable pose artifact directory is unsafe")
    return directory


def _identifier(value: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError("Pose artifact ID must be 64 lowercase hexadecimal characters")
    return value


def _encoded(value: dict) -> tuple[dict, bytes]:
    validated = pose_artifact.validate(value)
    data = pose_artifact.canonical(validated) + b"\n"
    if len(data) > pose_artifact.MAX_BYTES:
        raise ValueError("Editable pose artifact exceeds the 1 MiB limit")
    return validated, data


def _read_path(path: Path, expected_id: str) -> bytes:
    if path.is_symlink():
        raise ValueError("Stored editable pose artifact changed")
    try:
        with path.open("rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError("Stored editable pose artifact changed")
            raw = stream.read(pose_artifact.MAX_BYTES + 1)
    except FileNotFoundError as exc:
        raise ValueError("Editable pose artifact is unavailable") from exc
    if len(raw) > pose_artifact.MAX_BYTES:
        raise ValueError("Stored editable pose artifact changed")
    try:
        restored = pose_artifact.validate(pose_artifact.loads(raw))
        canonical = pose_artifact.canonical(restored) + b"\n"
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError("Stored editable pose artifact changed") from exc
    if restored["id"] != expected_id or raw != canonical:
        raise ValueError("Stored editable pose artifact changed")
    return raw


def read(experiments, artifact_id: str) -> bytes:
    """Return exact canonical bytes after revalidating filename, schema and content identity."""
    identifier = _identifier(artifact_id)
    return _read_path(_directory(experiments) / (identifier + SUFFIX), identifier)


def publish(experiments, value: dict) -> dict:
    """Publish once by content identity, or verify an identical existing artifact."""
    validated, data = _encoded(value)
    identifier = validated["id"]
    directory = _directory(experiments)
    destination = directory / (identifier + SUFFIX)
    temporary = directory / ("." + uuid.uuid4().hex + ".part")
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError:
            pass
        stored = _read_path(destination, identifier)
        if stored != data:
            raise ValueError("Stored editable pose artifact changed")
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "id": identifier,
        "schema": pose_artifact.SCHEMA,
        "file": identifier + SUFFIX,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "url": "/api/pose/artifacts/" + identifier,
        "authority": validated["authority"],
        "review": validated["review"],
    }
