#!/usr/bin/env python3
"""Prepare or validate zero-network Adult Illustration acquisition plans."""
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from studio_prompt.adult_illustration_acquisition_plan import (  # noqa: E402
    AcquisitionSelection,
    prepare_acquisition_plan,
    render_acquisition_plan,
    validate_acquisition_plan,
)
from studio_prompt.adult_illustration_source_intake import (  # noqa: E402
    read_snapshot_json,
)

MAX_LOCAL_JSON_BYTES = 4_194_304
ERROR_SCHEMA = "studio.adult-illustration-acquisition-plan-error/v1"
ERROR_KIND = "acquisition-plan-error"
AUTHORITY = {
    "download_authorized": False,
    "install_authorized": False,
    "execution_authorized": False,
    "generation_submitted": False,
    "training_authorized": False,
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser(
        "prepare",
        help="prepare one deterministic dry-run handoff from a stored snapshot",
    )
    prepare.add_argument("--snapshot", required=True, help="stored source snapshot JSON")
    prepare.add_argument("--file-id", required=True, help="exact source-snapshot file ID")
    prepare.add_argument(
        "--destination-folder",
        required=True,
        help="existing Model Library folder role",
    )
    prepare.add_argument(
        "--destination-name",
        required=True,
        help="plain .safetensors destination basename",
    )
    prepare.add_argument(
        "--intended-use",
        required=True,
        help="bounded operator statement; it grants no authority",
    )
    prepare.add_argument(
        "--terms-review-ref",
        help="optional unverified pointer to a human terms decision",
    )
    prepare.add_argument("--out", help="exclusive-create JSON output path")

    validate = commands.add_parser(
        "validate",
        help="validate a stored acquisition plan and optional source snapshot",
    )
    validate.add_argument("--plan", required=True, help="stored acquisition plan JSON")
    validate.add_argument(
        "--snapshot",
        help="optional source snapshot used to rederive and bind the plan",
    )
    validate.add_argument("--out", help="exclusive-create JSON output path")
    return parser


def _error_text(exc: BaseException) -> str:
    text = str(exc).replace("\r", " ").replace("\n", " ").strip()
    return (text or exc.__class__.__name__)[:2_048]


def _render_error(operation: str, exc: BaseException) -> str:
    value = {
        "schema": ERROR_SCHEMA,
        "kind": ERROR_KIND,
        "operation": operation,
        "error": _error_text(exc),
        "error_type": exc.__class__.__name__,
        "executable": False,
        "authority": "none",
        **AUTHORITY,
    }
    return json.dumps(
        value,
        indent=2,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
    ) + "\n"


def _preflight_output(raw_path: str | None) -> Path | None:
    if raw_path is None:
        return None
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValueError("output path must be non-empty")
    target = Path(raw_path)
    if target.name in {"", ".", ".."}:
        raise ValueError("output path must name a file")

    try:
        info = target.lstat()
    except FileNotFoundError:
        info = None
    if info is not None:
        if stat.S_ISLNK(info.st_mode):
            raise ValueError("output path cannot be a symlink")
        raise FileExistsError("output path already exists; refusing to overwrite it")

    parent = target.parent
    try:
        parent_info = parent.lstat()
    except FileNotFoundError as exc:
        raise ValueError("output parent directory does not exist") from exc
    if stat.S_ISLNK(parent_info.st_mode):
        raise ValueError("output parent directory cannot be a symlink")
    if not stat.S_ISDIR(parent_info.st_mode):
        raise ValueError("output parent must be a directory")
    return target


def _same_file(left: os.stat_result, right: os.stat_result) -> bool:
    try:
        return os.path.samestat(left, right)
    except (AttributeError, OSError):
        return (
            getattr(left, "st_dev", None),
            getattr(left, "st_ino", None),
        ) == (
            getattr(right, "st_dev", None),
            getattr(right, "st_ino", None),
        )


def _read_bounded(raw_path: str | Path, label: str) -> bytes:
    source = Path(raw_path)
    try:
        before = source.lstat()
    except FileNotFoundError as exc:
        raise ValueError(f"{label} does not exist") from exc
    if stat.S_ISLNK(before.st_mode):
        raise ValueError(f"{label} cannot be a symlink")
    if not stat.S_ISREG(before.st_mode):
        raise ValueError(f"{label} must be a regular file")
    if before.st_size > MAX_LOCAL_JSON_BYTES:
        raise ValueError(
            f"{label} is oversized; maximum is {MAX_LOCAL_JSON_BYTES} bytes"
        )

    flags = os.O_RDONLY
    flags |= getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(source, flags)
    try:
        opened = os.fstat(descriptor)
        after_open = source.lstat()
        if (
            not stat.S_ISREG(opened.st_mode)
            or stat.S_ISLNK(after_open.st_mode)
            or not _same_file(before, opened)
            or not _same_file(after_open, opened)
        ):
            raise ValueError(f"{label} changed while it was being opened")
        if opened.st_size > MAX_LOCAL_JSON_BYTES:
            raise ValueError(
                f"{label} is oversized; maximum is {MAX_LOCAL_JSON_BYTES} bytes"
            )

        chunks: list[bytes] = []
        total = 0
        while True:
            block = os.read(
                descriptor,
                min(65_536, MAX_LOCAL_JSON_BYTES + 1 - total),
            )
            if not block:
                break
            chunks.append(block)
            total += len(block)
            if total > MAX_LOCAL_JSON_BYTES:
                raise ValueError(
                    f"{label} is oversized; maximum is {MAX_LOCAL_JSON_BYTES} bytes"
                )

        final = os.fstat(descriptor)
        after_read = source.lstat()
        if (
            not _same_file(opened, final)
            or not _same_file(after_read, final)
            or final.st_size != opened.st_size
            or final.st_size != total
        ):
            raise ValueError(f"{label} changed while it was being read")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _duplicate_safe_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key {key!r}")
        value[key] = item
    return value


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON value {value!r} is not supported")


def _read_plan(path: str | Path) -> dict[str, Any]:
    data = _read_bounded(path, "acquisition plan")
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("acquisition plan must be valid UTF-8") from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_duplicate_safe_object,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise ValueError(f"acquisition plan is invalid JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ValueError("acquisition plan must be a JSON object")
    return value


def _prepare(args: argparse.Namespace) -> str:
    snapshot = read_snapshot_json(_read_bounded(args.snapshot, "source snapshot"))
    selection = AcquisitionSelection(
        file_id=args.file_id,
        destination_folder=args.destination_folder,
        destination_name=args.destination_name,
        intended_use=args.intended_use,
        terms_review_ref=args.terms_review_ref,
    )
    plan = prepare_acquisition_plan(snapshot, selection)
    return render_acquisition_plan(plan)


def _validate(args: argparse.Namespace) -> str:
    plan = _read_plan(args.plan)
    snapshot = None
    if args.snapshot is not None:
        snapshot = read_snapshot_json(
            _read_bounded(args.snapshot, "source snapshot")
        )
    validated = validate_acquisition_plan(plan, snapshot)
    return render_acquisition_plan(validated)


def _write_exclusive(target: Path, text: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(target, flags, 0o600)
    created = True
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("output must be a regular file")
        payload = text.encode("utf-8")
        written = 0
        while written < len(payload):
            count = os.write(descriptor, payload[written:])
            if count <= 0:
                raise OSError("output write made no progress")
            written += count
        os.fsync(descriptor)
        created = False
    finally:
        os.close(descriptor)
        if created:
            try:
                target.unlink()
            except FileNotFoundError:
                pass


def _emit(text: str, target: Path | None) -> None:
    if target is None:
        sys.stdout.write(text)
    else:
        _write_exclusive(target, text)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        output = _preflight_output(args.out)
        text = _prepare(args) if args.command == "prepare" else _validate(args)
        _emit(text, output)
        return 0
    except (
        ValueError,
        KeyError,
        TypeError,
        OSError,
        RecursionError,
        UnicodeError,
    ) as exc:
        sys.stderr.write(_render_error(args.command, exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
