"""Explicit, bounded live metadata transport for Adult Illustration sources.

Importing this module performs no network or filesystem activity. Network access
only occurs when a caller constructs :class:`BoundedProviderTransport` and
passes it to one of the explicit ``fetch_*`` functions.
"""
from __future__ import annotations

from typing import Any

from .adult_illustration_source_intake import (
    snapshot_civitai,
    snapshot_huggingface,
)
from ._adult_illustration_source_transport_cache import SnapshotResponseCache
from ._adult_illustration_source_transport_common import (
    AUTHORITY,
    FETCH_SCHEMA,
    HttpRequest,
    HttpResponse,
    MetadataPolicy,
    WireResponse,
)
from ._adult_illustration_source_transport_http import (
    BoundedProviderTransport,
    Exchange,
    StdlibMetadataExchange,
)


def _fetch_result(
    snapshot: dict[str, Any],
    transport: BoundedProviderTransport,
) -> dict[str, Any]:
    digest = snapshot.get("raw_payload_sha256")
    transport.finalize(digest)
    receipt = transport.receipt
    return {
        "schema": FETCH_SCHEMA,
        "kind": "source-snapshot-fetch",
        "executable": False,
        "authority": "none",
        "snapshot": snapshot,
        "transport_receipt": receipt,
        "raw_payload_ref": {
            "sha256": digest,
            "cache_key": receipt["request_key"],
            "retained_in_cache": receipt["cache_state"]
            in {"miss", "refreshed", "hit", "revalidated"},
        },
        **AUTHORITY,
    }


def fetch_huggingface(
    repo_id: str,
    revision: str,
    transport: BoundedProviderTransport,
) -> dict[str, Any]:
    """Fetch and parse one explicit Hugging Face metadata snapshot."""
    if not isinstance(transport, BoundedProviderTransport):
        raise TypeError("transport must be BoundedProviderTransport")
    with transport._fetch_scope():
        snapshot = snapshot_huggingface(repo_id, revision, transport)
        return _fetch_result(snapshot, transport)


def fetch_civitai(
    version_id: int,
    transport: BoundedProviderTransport,
) -> dict[str, Any]:
    """Fetch and parse one explicit Civitai model-version metadata snapshot."""
    if not isinstance(transport, BoundedProviderTransport):
        raise TypeError("transport must be BoundedProviderTransport")
    with transport._fetch_scope():
        snapshot = snapshot_civitai(version_id, transport)
        return _fetch_result(snapshot, transport)


__all__ = [
    "BoundedProviderTransport",
    "Exchange",
    "HttpRequest",
    "HttpResponse",
    "MetadataPolicy",
    "SnapshotResponseCache",
    "StdlibMetadataExchange",
    "WireResponse",
    "fetch_civitai",
    "fetch_huggingface",
]
