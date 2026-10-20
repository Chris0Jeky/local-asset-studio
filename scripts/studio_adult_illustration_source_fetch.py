#!/usr/bin/env python3
"""Explicitly fetch bounded Adult Illustration provider metadata only."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from studio_prompt.adult_illustration_source_transport import (  # noqa: E402
    BoundedProviderTransport,
    MetadataPolicy,
    SnapshotResponseCache,
    EvidencePolicy,
    SnapshotEvidenceStore,
    HttpRequest,
    resolve_payload_reference,
    fetch_civitai,
    fetch_huggingface,
)
from studio_prompt._adult_illustration_source_transport_common import parse_cache_json  # noqa: E402

_AUTHORITY = {
    "download_authorized": False,
    "install_authorized": False,
    "execution_authorized": False,
    "generation_submitted": False,
    "training_authorized": False,
}


def _add_transport_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="explicitly permit one bounded public provider-metadata GET operation",
    )
    parser.add_argument("--cache-dir", help="optional exact-identity metadata cache")
    parser.add_argument("--evidence-dir", help="optional immutable metadata evidence store, independent of the cache")
    parser.add_argument("--evidence-max-bytes", type=int, help="logical body/provenance byte budget, fixed when creating a store")
    parser.add_argument("--evidence-max-payloads", type=int, help="digest row budget including pruning tombstones")
    parser.add_argument("--evidence-max-observations", type=int, help="bounded source-provenance row budget")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="revalidate an existing cache entry or replace it after a fresh 200",
    )
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--max-redirects", type=int, default=3)
    parser.add_argument("--max-response-bytes", type=int, default=2_097_152)
    parser.add_argument("--retry-backoff", type=float, default=0.25)
    parser.add_argument("--out", help="exclusive-create JSON output path")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    hf = commands.add_parser(
        "huggingface",
        help="fetch one explicit Hugging Face repository/revision metadata record",
    )
    hf.add_argument("--repo", required=True, help="owner/model repository ID")
    hf.add_argument("--revision", required=True, help="explicit requested revision")
    _add_transport_options(hf)

    civitai = commands.add_parser(
        "civitai",
        help="fetch one explicit Civitai model-version metadata record",
    )
    civitai.add_argument("--version-id", required=True, type=int)
    _add_transport_options(civitai)
    resolve = commands.add_parser('resolve', help='resolve an exported payload reference offline; state determines availability')
    resolve.add_argument('--ref', required=True, help='fetch export or raw payload reference JSON, at most 4 MiB')
    resolve.add_argument('--evidence-dir', help='existing immutable evidence store')
    resolve.add_argument('--cache-dir', help='existing cache, only for verifying a legacy export')
    resolve.add_argument('--out', help='exclusive-create JSON result; verified bytes are base64 encoded')
    prune = commands.add_parser('prune', help='explicitly remove one evidence body and retain its pruning tombstone')
    prune.add_argument('--evidence-dir', required=True)
    prune.add_argument('--sha256', required=True)
    prune.add_argument('--out', help='exclusive-create JSON result')
    return parser


def _render(value: object) -> str:
    return json.dumps(
        value,
        indent=2,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
    ) + "\n"


def _preflight_output(output: str | None) -> None:
    """Refuse unusable destinations before any provider exchange can occur."""

    if output is None:
        return
    target = Path(output)
    if target.exists() or target.is_symlink():
        raise ValueError(f"Output already exists: {target}")
    parent = target.parent
    if parent.is_symlink():
        raise ValueError(f"Output parent cannot be a symlink: {parent}")
    if not parent.exists() or not parent.is_dir():
        raise ValueError(f"Output parent must be an existing directory: {parent}")


def _emit(value: object, output: str | None) -> None:
    text = _render(value)
    if output:
        target = Path(output)
        with target.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    else:
        sys.stdout.write(text)


def _policy(args: argparse.Namespace) -> MetadataPolicy:
    return MetadataPolicy(
        timeout_seconds=args.timeout,
        max_attempts=args.max_attempts,
        max_redirects=args.max_redirects,
        max_response_bytes=args.max_response_bytes,
        retry_backoff_seconds=args.retry_backoff,
    )


def _evidence_store(args):
    limits = {'max_total_bytes': args.evidence_max_bytes, 'max_payloads': args.evidence_max_payloads,
              'max_observations': args.evidence_max_observations}
    supplied = {key: value for key, value in limits.items() if value is not None}
    if args.evidence_dir is None:
        if supplied: raise ValueError('--evidence-dir is required with evidence quota options')
        return None
    return SnapshotEvidenceStore(args.evidence_dir, policy=EvidencePolicy(**supplied) if supplied else None)


def _resolve(args):
    path = Path(args.ref)
    if path.is_symlink(): raise ValueError('Reference input cannot be a symlink')
    with path.open('rb') as handle: raw = handle.read(4_194_305)
    if len(raw) > 4_194_304: raise ValueError('Reference input is oversized')
    value = parse_cache_json(raw)
    ref = value.get('raw_payload_ref', value)
    store = SnapshotEvidenceStore(args.evidence_dir, create=False) if args.evidence_dir is not None else None
    cache = None
    if args.cache_dir is not None:
        if not Path(args.cache_dir).is_dir(): raise ValueError('Legacy cache is unavailable')
        cache = SnapshotResponseCache(args.cache_dir)
    request = None
    if isinstance(ref, dict) and 'schema' not in ref:
        snapshot = value.get('snapshot')
        if snapshot is not None and not isinstance(snapshot, dict): raise ValueError('Legacy snapshot must be an object')
        original = snapshot.get('request') if snapshot is not None else None
        if isinstance(original, dict): request = HttpRequest(**original)
    return resolve_payload_reference(ref, evidence_store=store, cache=cache, request=request)


def _error(command: str, exc: Exception) -> dict[str, Any]:
    return {
        "error": str(exc),
        "operation": command,
        "authority": "none",
        **_AUTHORITY,
    }


def main(argv: list[str] | None = None, *, exchange=None) -> int:
    args = _parser().parse_args(argv)
    try:
        _preflight_output(args.out)
        if args.command == 'resolve':
            _emit(_resolve(args), args.out); return 0
        if args.command == 'prune':
            result = SnapshotEvidenceStore(args.evidence_dir, create=False).prune(args.sha256)
            _emit(result, args.out)
            return 0 if result['state'] in ('pruned', 'missing') else 2
        if not args.allow_network:
            raise ValueError(
                "--allow-network is required for explicit provider metadata access"
            )
        evidence = _evidence_store(args)
        cache = (
            SnapshotResponseCache(args.cache_dir)
            if args.cache_dir is not None
            else None
        )
        transport = BoundedProviderTransport(
            exchange=exchange,
            policy=_policy(args),
            cache=cache,
            evidence_store=evidence,
            refresh=args.refresh,
        )
        if args.command == "huggingface":
            value = fetch_huggingface(args.repo, args.revision, transport)
        else:
            value = fetch_civitai(args.version_id, transport)
        _emit(value, args.out)
        return 0
    except (
        ValueError,
        KeyError,
        TypeError,
        OSError,
        RuntimeError,
        RecursionError,
    ) as exc:
        sys.stderr.write(_render(_error(args.command, exc)))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
