"""One real-SQLite consistency oracle for workflow documents and setup drafts.

Adapters keep domain commands, receipts and errors typed. The matrix only shares
observable facts: head, revision count, request count, accounted history bytes and exact fault evidence.
No filesystem/model action is claimed atomic with either SQLite transaction.
"""
from __future__ import annotations

import copy
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from studio_workflow.core import catalog, new_document
from studio_workflow.documents import DocumentError, WorkflowDocuments
from studio_workflow.setup_drafts import SetupDrafts, SetupError
from test_recipe_shortlist import make_studio
from test_recipe_shortlist_ordered import route
from test_workflow_documents import GRAPH, INFO, SQLiteWorkspace
from workspace import AssetWorkspace


@dataclass(frozen=True)
class ConsistencyFacts:
    head: int
    revisions: int
    requests: int
    accounted_bytes: int


@dataclass(frozen=True)
class StoredEvidence:
    payload: str
    sha256: str


class WorkflowAdapter:
    domain = 'workflow-documents'
    request_conflict = 'request_conflict'
    revision_conflict = 'revision_conflict'

    def __init__(self, root: Path):
        self.root = root
        self.workspace = SQLiteWorkspace(root)
        self.store = WorkflowDocuments(self.workspace)
        self.original_marker = 'Matrix workflow'
        self.document = new_document(copy.deepcopy(GRAPH), catalog(INFO, 'primary'), self.original_marker)
        self.key = None

    @staticmethod
    def _view(value):
        return {
            'revision': value['revision'],
            'head': value['head_revision'],
            'marker': value['document']['name'],
            'replayed': value.get('replayed', False),
        }

    def create(self):
        value = self.store.create({'request_id': 'matrix-create', 'document': copy.deepcopy(self.document)})
        self.key = value['id']
        return self._view(value)

    def edit_payload(self, request_id: str, expected: int, marker: str, *, reordered: bool = False):
        value = {
            'request_id': request_id,
            'expected_revision': expected,
            'commands': [{'op': 'rename', 'name': marker}],
        }
        return dict(reversed(tuple(value.items()))) if reordered else value

    def edit(self, request_id: str, expected: int, marker: str, *, reordered: bool = False):
        return self._view(self.store.command(
            self.key, self.edit_payload(request_id, expected, marker, reordered=reordered)
        ))

    def restore(self, request_id: str, expected: int, revision: int):
        return self._view(self.store.command(
            self.key,
            {'request_id': request_id, 'expected_revision': expected, 'revision': revision},
            restore=True,
        ))

    def revision_marker(self, revision: int):
        return self.store.get(self.key, revision)['document']['name']

    def reopen(self):
        self.workspace = SQLiteWorkspace(self.root)
        self.store = WorkflowDocuments(self.workspace)

    def facts(self):
        with self.workspace.connection() as db:
            head = db.execute('SELECT head FROM workflow_documents_v1 WHERE id=?', (self.key,)).fetchone()[0]
            revision = db.execute(
                'SELECT COUNT(*),COALESCE(SUM(bytes),0) FROM workflow_revisions_v1 WHERE document_id=?',
                (self.key,),
            ).fetchone()
            requests = db.execute(
                'SELECT COUNT(*) FROM workflow_requests_v1 WHERE document_id=?', (self.key,)
            ).fetchone()[0]
        return ConsistencyFacts(head, revision[0], requests, revision[1])

    def integrity_evidence(self):
        with self.workspace.connection() as db:
            row = db.execute(
                'SELECT document,sha256 FROM workflow_revisions_v1 WHERE document_id=? AND revision=(SELECT head FROM workflow_documents_v1 WHERE id=?)',
                (self.key, self.key),
            ).fetchone()
        return StoredEvidence(row['document'], row['sha256'])

    def corrupt(self, kind: str):
        column, value = ('document', '{}') if kind == 'json' else ('sha256', '0' * 64)
        with self.workspace.connection() as db:
            db.execute(
                f'UPDATE workflow_revisions_v1 SET {column}=? WHERE document_id=? AND revision=(SELECT head FROM workflow_documents_v1 WHERE id=?)',
                (value, self.key, self.key),
            )

    def read_head(self):
        return self._view(self.store.get(self.key))

    @staticmethod
    def assert_integrity_error(case: unittest.TestCase, error: Exception):
        case.assertIsInstance(error, DocumentError)
        case.assertEqual(error.code, 'storage_unavailable')
        case.assertEqual(error.status, 503)

    def budget_refusal(self):
        before = self.facts()
        with patch('studio_workflow.documents.MAX_HISTORY_BYTES', before.accounted_bytes):
            self.edit('matrix-over-budget', before.head, 'Too large')

    def race(self):
        barrier = threading.Barrier(2)

        def attempt(index: int):
            store = WorkflowDocuments(SQLiteWorkspace(self.root))
            barrier.wait(5)
            try:
                value = store.command(
                    self.key,
                    self.edit_payload(f'matrix-race-{index}', 1, f'Writer {index}'),
                )
                return ('committed', value['revision'])
            except DocumentError as error:
                return (error.code, None)

        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(attempt, (1, 2)))


class SetupAdapter:
    domain = 'setup-drafts'
    request_conflict = 'setup_request_conflict'
    revision_conflict = 'setup_revision_conflict'

    def __init__(self, root: Path):
        self.root = root
        self.studio = make_studio(root)
        self.studio.assets = AssetWorkspace(root)
        self.studio.jobs = {}
        self.preset = route(self.studio)
        self.studio.experiments = root / 'experiments'
        self.studio.experiments.mkdir(exist_ok=True)
        self.studio.comfy_root = root / 'comfy'
        (self.studio.comfy_root / 'input').mkdir(parents=True)
        self.scope = self.studio.assets.snapshot()['workspace_id']
        self.store = SetupDrafts(self.studio)
        self.original_marker = 'Matrix setup'
        self.draft = {
            'version': 1,
            'updatedAt': 0,
            'templateHash': self.preset['continuation_capability']['template_sha256'],
            'pendingInputs': [],
            'recipe': {
                'preset': self.preset['id'],
                'controls': {'positive': self.original_marker},
                'batch': 1,
                'references': [],
                'parent_assets': [],
                'parent_by_input': {},
            },
        }
        self.key = None

    @staticmethod
    def _view(value):
        return {
            'revision': value['revision'],
            'head': value['head_revision'],
            'marker': value['draft']['recipe']['controls']['positive'],
            'replayed': value.get('replayed', False),
        }

    def create_payload(self):
        return {
            'action': 'create',
            'workspace_id': self.scope,
            'request_id': 'matrix-create',
            'draft': copy.deepcopy(self.draft),
        }

    def create(self):
        value = self.store.command(self.create_payload())
        self.key = value['draft_id']
        return self._view(value)

    def edit_payload(self, request_id: str, expected: int, marker: str, *, reordered: bool = False):
        draft = copy.deepcopy(self.draft)
        draft['recipe']['controls']['positive'] = marker
        value = {
            'action': 'replace',
            'workspace_id': self.scope,
            'request_id': request_id,
            'draft_id': self.key,
            'expected_revision': expected,
            'draft': draft,
        }
        return dict(reversed(tuple(value.items()))) if reordered else value

    def edit(self, request_id: str, expected: int, marker: str, *, reordered: bool = False):
        return self._view(self.store.command(
            self.edit_payload(request_id, expected, marker, reordered=reordered)
        ))

    def restore(self, request_id: str, expected: int, revision: int):
        value = self.store.command({
            'action': 'restore',
            'workspace_id': self.scope,
            'request_id': request_id,
            'draft_id': self.key,
            'expected_revision': expected,
            'revision': revision,
        })
        return self._view(value)

    def revision_marker(self, revision: int):
        return self.store.get(self.key, revision)['draft']['recipe']['controls']['positive']

    def reopen(self):
        studio = object.__new__(type(self.studio))
        studio.__dict__.update(self.studio.__dict__)
        studio.assets = AssetWorkspace(self.root)
        studio.lock = threading.RLock()
        self.studio = studio
        self.store = SetupDrafts(studio)

    def facts(self):
        with self.studio.assets.connection() as db:
            head = db.execute('SELECT head FROM setup_drafts_v1 WHERE id=?', (self.key,)).fetchone()[0]
            revision = db.execute(
                'SELECT COUNT(*),COALESCE(SUM(bytes),0) FROM setup_versions_v1 WHERE draft_id=?',
                (self.key,),
            ).fetchone()
            requests = db.execute(
                'SELECT COUNT(*),COALESCE(SUM(bytes),0) FROM setup_operations_v1 WHERE draft_id=?',
                (self.key,),
            ).fetchone()
        return ConsistencyFacts(head, revision[0], requests[0], revision[1] + requests[1])

    def integrity_evidence(self):
        with self.studio.assets.connection() as db:
            row = db.execute(
                'SELECT record,sha256 FROM setup_versions_v1 WHERE draft_id=? AND revision=(SELECT head FROM setup_drafts_v1 WHERE id=?)',
                (self.key, self.key),
            ).fetchone()
        return StoredEvidence(row['record'], row['sha256'])

    def corrupt(self, kind: str):
        column, value = ('record', '{}') if kind == 'json' else ('sha256', '0' * 64)
        with self.studio.assets.connection() as db:
            db.execute(
                f'UPDATE setup_versions_v1 SET {column}=? WHERE draft_id=? AND revision=(SELECT head FROM setup_drafts_v1 WHERE id=?)',
                (value, self.key, self.key),
            )

    def read_head(self):
        return self._view(self.store.get(self.key))

    @staticmethod
    def assert_integrity_error(case: unittest.TestCase, error: Exception):
        case.assertIsInstance(error, ValueError)
        case.assertIn('integrity', str(error).lower())

    def budget_refusal(self):
        before = self.facts()
        with patch('studio_workflow.setup_drafts.MAX_STORAGE', before.accounted_bytes):
            self.edit('matrix-over-budget', before.head, 'Too large')

    def race(self):
        other = object.__new__(type(self.studio))
        other.__dict__.update(self.studio.__dict__)
        other.lock = threading.RLock()
        stores = (SetupDrafts(self.studio), SetupDrafts(other))
        barrier = threading.Barrier(2)

        def attempt(index: int):
            barrier.wait(5)
            try:
                value = stores[index].command(
                    self.edit_payload(f'matrix-race-{index}', 1, f'Writer {index}')
                )
                return ('committed', value['revision'])
            except SetupError as error:
                return (error.code, None)

        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(attempt, (0, 1)))


ADAPTERS = (WorkflowAdapter, SetupAdapter)


class RevisionConsistencyFaultMatrix(unittest.TestCase):
    @contextmanager
    def adapter(self, factory):
        with tempfile.TemporaryDirectory() as root:
            yield factory(Path(root))

    def test_exact_canonical_replay_and_changed_request_refusal(self):
        for factory in ADAPTERS:
            with self.subTest(domain=factory.domain), self.adapter(factory) as adapter:
                adapter.create()
                first = adapter.edit('matrix-edit', 1, 'Committed')
                before = adapter.facts()
                replay = adapter.edit('matrix-edit', 1, 'Committed', reordered=True)
                self.assertTrue(replay['replayed'])
                self.assertEqual(replay['revision'], first['revision'])
                self.assertEqual(replay['marker'], first['marker'])
                self.assertEqual(adapter.facts(), before)
                with self.assertRaises(ValueError) as caught:
                    adapter.edit('matrix-edit', 1, 'Different bytes')
                self.assertEqual(getattr(caught.exception, 'code', None), adapter.request_conflict)
                self.assertEqual(adapter.facts(), before)

    def test_stale_head_refuses_without_receipt_or_revision(self):
        for factory in ADAPTERS:
            with self.subTest(domain=factory.domain), self.adapter(factory) as adapter:
                adapter.create()
                adapter.edit('matrix-current', 1, 'Current')
                before = adapter.facts()
                with self.assertRaises(ValueError) as caught:
                    adapter.edit('matrix-stale', 1, 'Stale')
                self.assertEqual(getattr(caught.exception, 'code', None), adapter.revision_conflict)
                self.assertEqual(adapter.facts(), before)
                self.assertEqual(adapter.read_head()['marker'], 'Current')

    def test_two_interleaved_connections_commit_one_expected_head(self):
        for factory in ADAPTERS:
            with self.subTest(domain=factory.domain), self.adapter(factory) as adapter:
                adapter.create()
                outcomes = adapter.race()
                self.assertEqual(sum(kind == 'committed' for kind, _ in outcomes), 1)
                self.assertEqual(sum(kind == adapter.revision_conflict for kind, _ in outcomes), 1)
                facts = adapter.facts()
                self.assertEqual((facts.head, facts.revisions, facts.requests), (2, 2, 2))

    def test_lost_response_is_recovered_after_store_reopen_without_new_write(self):
        for factory in ADAPTERS:
            with self.subTest(domain=factory.domain), self.adapter(factory) as adapter:
                adapter.create()
                committed = adapter.edit('matrix-lost-response', 1, 'Recovered')
                before = adapter.facts()
                adapter.reopen()
                replay = adapter.edit('matrix-lost-response', 1, 'Recovered', reordered=True)
                self.assertTrue(replay['replayed'])
                self.assertEqual(replay['revision'], committed['revision'])
                self.assertEqual(replay['head'], committed['head'])
                self.assertEqual(replay['marker'], 'Recovered')
                self.assertEqual(adapter.facts(), before)

    def test_deliberate_json_and_digest_faults_fail_closed_without_repair(self):
        for factory in ADAPTERS:
            for fault in ('json', 'digest'):
                with self.subTest(domain=factory.domain, fault=fault), self.adapter(factory) as adapter:
                    adapter.create()
                    before = adapter.facts()
                    original = adapter.integrity_evidence()
                    adapter.corrupt(fault)
                    corrupted = adapter.integrity_evidence()
                    self.assertNotEqual(corrupted, original)
                    with self.assertRaises(ValueError) as caught:
                        adapter.read_head()
                    adapter.assert_integrity_error(self, caught.exception)
                    self.assertEqual(adapter.integrity_evidence(), corrupted)
                    self.assertEqual(adapter.facts(), before)

    def test_storage_budget_refusal_preserves_all_prior_evidence(self):
        for factory in ADAPTERS:
            with self.subTest(domain=factory.domain), self.adapter(factory) as adapter:
                adapter.create()
                before = adapter.facts()
                with self.assertRaises(ValueError) as caught:
                    adapter.budget_refusal()
                self.assertIn('budget', str(caught.exception).lower())
                self.assertEqual(adapter.facts(), before)
                self.assertEqual(adapter.read_head()['marker'], adapter.original_marker)

    def test_restore_appends_a_new_head_without_rewriting_old_revisions(self):
        for factory in ADAPTERS:
            with self.subTest(domain=factory.domain), self.adapter(factory) as adapter:
                adapter.create()
                adapter.edit('matrix-before-restore', 1, 'Changed')
                restored = adapter.restore('matrix-restore', 2, 1)
                self.assertEqual(restored['revision'], 3)
                self.assertEqual(restored['head'], 3)
                self.assertEqual(restored['marker'], adapter.original_marker)
                self.assertEqual(adapter.revision_marker(1), adapter.original_marker)
                self.assertEqual(adapter.revision_marker(2), 'Changed')
                self.assertEqual(adapter.revision_marker(3), adapter.original_marker)
                facts = adapter.facts()
                self.assertEqual((facts.head, facts.revisions, facts.requests), (3, 3, 3))


if __name__ == '__main__':
    unittest.main()
