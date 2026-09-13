"""Small typed authoring SDK over the same HTTP commands used by the Studio UI."""
from __future__ import annotations
from .client import Client, ClientError
from .commands import identifier

PREFIX = '/api/workflow-studio/documents'


class WorkflowClient(Client):
    def shortlist(self, goal: str, *, reference_count: int | None = None, limit: int = 6,
                  offset: int = 0, expected_snapshot: str | None = None, source_asset_id: str | None = None,
                  source_sha256: str | None = None, source_role: str | None = None, sources: list[dict] | None = None) -> dict:
        """Observe starting-preset options; never prepares or dispatches a job."""
        from .shortlist import observe
        value = {'goal': goal, 'limit': limit, 'offset': offset}
        if reference_count is not None: value['reference_count'] = reference_count
        if sources is not None: value['sources'] = sources
        if expected_snapshot is not None: value['expected_snapshot'] = expected_snapshot
        for key, item in [('source_asset_id',source_asset_id),('source_sha256',source_sha256),('source_role',source_role)]:
            if item is not None: value[key] = item
        return observe(self.request, value)

    def documents(self) -> dict:
        return self.request(PREFIX)

    def get_document(self, document_id: str, revision: int | None = None) -> dict:
        path = PREFIX + '/' + identifier(document_id)
        if revision is not None:
            if type(revision) is not int or revision < 1: raise ValueError('Positive revision required')
            path += '/revisions/' + str(revision)
        return self.request(path)

    def create_document(self, document: dict, *, request_id: str) -> dict:
        return self.request(PREFIX, {'request_id': identifier(request_id), 'document': document})

    def apply(self, document_id: str, commands: list[dict], *, expected_revision: int, request_id: str) -> dict:
        return self.request(PREFIX + '/' + identifier(document_id) + '/commands',
                            {'request_id': identifier(request_id), 'expected_revision': expected_revision, 'commands': commands})

    def preview(self, document_id: str, commands: list[dict], *, expected_revision: int) -> dict:
        return self.request(PREFIX + '/' + identifier(document_id) + '/preview',
                            {'expected_revision': expected_revision, 'commands': commands})

    def history(self, document_id: str) -> dict:
        return self.request(PREFIX + '/' + identifier(document_id) + '/history')

    def restore(self, document_id: str, revision: int, *, expected_revision: int, request_id: str) -> dict:
        return self.request(PREFIX + '/' + identifier(document_id) + '/restore',
                            {'request_id': identifier(request_id), 'expected_revision': expected_revision, 'revision': revision})

    def fork(self, document_id: str, revision: int, name: str, *, request_id: str) -> dict:
        return self.request(PREFIX + '/' + identifier(document_id) + '/fork',
                            {'request_id': identifier(request_id), 'revision': revision, 'name': name})

    def prepare_document(self, document: dict, *, preset_id: str) -> dict:
        """Prepare compatible image-recipe edits; returns a report containing its run ticket."""
        return self.request('/api/workflow-studio/prepare-document',
                            {'document': document, 'preset_id': identifier(preset_id)})

    @property
    def saved_runs(self):
        """Prepare/recover revision-bound tickets; never executes them."""
        from .run_client import SavedRuns
        return SavedRuns(self.request)
