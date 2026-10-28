"""Read-only collection schemas and the strict raw-transport MCP binding."""
from .asset_read_tools import WORKSPACE, PRIVACY
from .client import Client
from .collection_read_client import CollectionReadClient
from .core import need

PAGE_ARGUMENTS = {
    'workspace_id': WORKSPACE,
    'limit': {'type': 'integer', 'minimum': 1, 'maximum': 100},
    'cursor': {'type': 'string', 'pattern': r'^[A-Za-z0-9_-]+$', 'maxLength': 2048},
    'privacy': PRIVACY,
}


class CollectionToolClient(CollectionReadClient):
    def __init__(self, client, request_started):
        need(isinstance(client, Client), 'Collection observations require the raw Studio Client transport')
        super().__init__(client.base, client.timeout)
        self.opener = client.opener
        self._request_started = request_started

    def _observe(self, path, body=None):
        self._request_started()
        return super()._observe(path, body)
