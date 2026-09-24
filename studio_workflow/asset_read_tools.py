"""MCP schema and raw-transport binding for the existing asset observer.

No second response decoder, Workspace owner or automatic continuation. Tool
annotations follow the operation's semantics, not selection's HTTP POST verb.
"""
from . import asset_reads
from .asset_read_client import AssetReadClient
from .client import Client
from .core import need

WORKSPACE = {'type': 'string', 'pattern': r'^[0-9a-f]{32}$', 'maxLength': 32}
ASSET_ID = {'type': 'string', 'pattern': r'^[A-Za-z0-9_-]{1,128}$', 'maxLength': 128}
PAGE_ARGUMENTS = {
    'workspace_id': WORKSPACE,
    'limit': {'type': 'integer', 'minimum': 1, 'maximum': asset_reads.MAX_PAGE},
    'cursor': {'type': 'string', 'pattern': r'^[A-Za-z0-9_-]+$', 'maxLength': asset_reads.MAX_CURSOR},
    'filters': {'type': 'object', 'additionalProperties': False, 'properties': {
        'visibility': {'type': 'string', 'enum': ['active', 'trash', 'all']},
        'media_type': {'type': ['string', 'null'], 'pattern': r'^[^\x00-\x1f\x7f]+$', 'minLength': 1, 'maxLength': 32},
        'review': {'type': ['string', 'null'], 'enum': [*asset_reads.REVIEWS, None]},
        'favorite': {'type': ['boolean', 'null']},
        'collection_id': {**ASSET_ID, 'type': ['string', 'null']}}}}
SELECTION_ARGUMENTS = {
    'workspace_id': WORKSPACE,
    'ids': {'type': 'array', 'minItems': 1, 'maxItems': asset_reads.MAX_SELECTION,
            'uniqueItems': True, 'items': ASSET_ID}}


class AssetToolClient(AssetReadClient):
    """Reuse the bridge's configured raw transport, preserving strict decoding.

    AssetReadClient validates cursor/query/selection before calling _observe.
    Mark only entry into that transport so local refusals remain local, while a
    lost read never becomes write-outcome uncertainty. No state survives a call.
    """
    def __init__(self, client, request_started):
        need(isinstance(client, Client), 'Asset observations require the raw Studio Client transport')
        super().__init__(client.base, client.timeout)
        self.opener = client.opener
        self._request_started = request_started

    def _observe(self, path, body=None):
        self._request_started()
        return super()._observe(path, body)
