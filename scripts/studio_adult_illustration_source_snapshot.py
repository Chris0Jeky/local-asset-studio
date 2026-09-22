#!/usr/bin/env python3
"""Build source-snapshot proposals from retained local provider responses only."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from studio_prompt.adult_illustration_source_intake import (  # noqa: E402
    HttpResponse,
    diff_snapshots,
    read_snapshot_json,
    snapshot_civitai,
    snapshot_huggingface,
)

MAX_LOCAL_RESPONSE_BYTES = 2_097_152


class LocalResponseTransport:
    """One-shot transport backed by an explicit local JSON response file."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.used = False

    def __call__(self, request):
        if self.used:
            raise RuntimeError("Local response transport may be called only once")
        self.used = True
        if self.path.is_symlink():
            raise ValueError("Local provider response cannot be a symlink")
        resolved = self.path.resolve(strict=True)
        if not resolved.is_file():
            raise ValueError("Local provider response must be a file")
        if resolved.stat().st_size > MAX_LOCAL_RESPONSE_BYTES:
            raise ValueError(
                f"Local provider response exceeds {MAX_LOCAL_RESPONSE_BYTES} bytes"
            )
        body = resolved.read_bytes()
        return HttpResponse(
            request_url=request.url,
            final_url=request.url,
            status=200,
            headers={"content-type": "application/json; charset=utf-8"},
            body=body,
            redirect_chain=(),
        )


def _add_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out", help="exclusive-create JSON output path")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    hf = commands.add_parser(
        "huggingface",
        help="snapshot one retained Hugging Face API response",
    )
    hf.add_argument("--repo", required=True, help="explicit owner/model repository ID")
    hf.add_argument("--revision", required=True, help="explicit requested revision")
    hf.add_argument("--response", required=True, help="retained local API JSON response")
    _add_output(hf)

    civitai = commands.add_parser(
        "civitai",
        help="snapshot one retained Civitai model-version API response",
    )
    civitai.add_argument("--version-id", required=True, type=int)
    civitai.add_argument("--response", required=True, help="retained local API JSON response")
    _add_output(civitai)

    diff = commands.add_parser("diff", help="compare two stored source snapshots")
    diff.add_argument("--before", required=True)
    diff.add_argument("--after", required=True)
    _add_output(diff)
    return parser


def _render(value: object) -> str:
    return json.dumps(
        value,
        indent=2,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
    ) + "\n"


def _emit(value: object, output: str | None) -> None:
    text = _render(value)
    if output:
        target = Path(output)
        with target.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    else:
        sys.stdout.write(text)


def _read_bounded(path: str | Path, label: str) -> bytes:
    source = Path(path)
    if source.is_symlink():
        raise ValueError(f"{label} cannot be a symlink")
    resolved = source.resolve(strict=True)
    if not resolved.is_file():
        raise ValueError(f"{label} must be a file")
    if resolved.stat().st_size > MAX_LOCAL_RESPONSE_BYTES:
        raise ValueError(f"{label} exceeds {MAX_LOCAL_RESPONSE_BYTES} bytes")
    return resolved.read_bytes()


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "huggingface":
            value = snapshot_huggingface(
                args.repo,
                args.revision,
                LocalResponseTransport(args.response),
            )
        elif args.command == "civitai":
            value = snapshot_civitai(
                args.version_id,
                LocalResponseTransport(args.response),
            )
        else:
            before = read_snapshot_json(_read_bounded(args.before, "before snapshot"))
            after = read_snapshot_json(_read_bounded(args.after, "after snapshot"))
            value = diff_snapshots(before, after)
        _emit(value, args.out)
        return 0
    except (ValueError, KeyError, TypeError, OSError, RecursionError) as exc:
        error = {
            "error": str(exc),
            "operation": args.command,
            "authority": "none",
            "download_authorized": False,
            "install_authorized": False,
            "execution_authorized": False,
            "generation_submitted": False,
            "training_authorized": False,
        }
        sys.stderr.write(_render(error))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
