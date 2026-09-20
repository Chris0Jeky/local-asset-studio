"""Bounded history observations over the real shared setup tables, without runtime I/O."""
import copy
import hashlib
import importlib
import json
import tempfile
import unittest
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import patch

from studio_workflow.core import canonical
from test_revision_consistency_matrix import SetupAdapter


class SetupHistoryTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('studio_workflow.setup_history'),
                             'Bounded shared setup history service is missing')
        self.module = importlib.import_module('studio_workflow.setup_history')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.adapter = SetupAdapter(Path(self.temp.name))
        self.adapter.create()
        self.store = self.adapter.store
        self.history = self.module.SetupHistory(self.store)
        self.key, self.scope = self.adapter.key, self.adapter.scope

    def page(self, **kwargs):
        return self.history.page(self.key, workspace_id=self.scope, **kwargs)

    def edit(self, revision, marker):
        self.adapter.edit('edit-' + str(revision), revision - 1, marker)

    def evidence(self):
        with self.store.workspace.connection() as db:
            return tuple(tuple(tuple(row) for row in db.execute('SELECT * FROM ' + table))
                         for table in ('setup_drafts_v1', 'setup_versions_v1', 'setup_operations_v1'))

    def test_hundred_revisions_walk_without_losing_identity_or_expanding_records(self):
        for revision in range(2, 101):
            self.edit(revision, 'Revision ' + str(revision))
        before = self.evidence()
        revisions, args = [], {'limit': 13}
        while True:
            result = self.page(**args)
            self.assertEqual(result['head_revision'], 100)
            self.assertLessEqual(len(result['revisions']), 13)
            self.assertLess(len(canonical(result)), 16384)
            self.assertNotIn('draft', result['revisions'][0])
            revisions.extend(row['revision'] for row in result['revisions'])
            if result['next_before_revision'] is None:
                break
            args.update(before_revision=result['next_before_revision'], expected_head=100)
        self.assertEqual(revisions, list(range(100, 0, -1)))
        self.assertEqual(before, self.evidence())

    def test_continuation_requires_expected_head_and_refuses_drift(self):
        self.edit(2, 'Second')
        page = self.page(limit=1)
        with self.assertRaises(ValueError):
            self.page(limit=1, before_revision=page['next_before_revision'])
        self.edit(3, 'Third')
        with self.assertRaises(ValueError) as error:
            self.page(limit=1, before_revision=2, expected_head=2)
        self.assertEqual(error.exception.code, 'setup_revision_conflict')
        self.assertEqual(self.page()['head_revision'], 3)

    def test_foreign_scope_and_invalid_bounds_refuse_before_record_loading(self):
        with patch.object(self.history, '_record', side_effect=AssertionError('Record reached')):
            for kwargs in ({'limit': True}, {'limit': 0}, {'limit': 26},
                           {'before_revision': True}, {'expected_head': 0}):
                with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                    self.page(**kwargs)
            with self.assertRaises(ValueError):
                self.history.page(self.key, workspace_id='f' * 32)

    def test_typed_diff_partitions_wording_controls_and_lineage_without_writes(self):
        draft = copy.deepcopy(self.adapter.draft)
        draft['recipe']['controls'].update(positive='After', seed='42')
        draft['recipe']['parent_assets'] = ['parent-one']
        self.store.command({'action': 'replace', 'workspace_id': self.scope, 'request_id': 'domains',
                            'draft_id': self.key, 'expected_revision': 1, 'draft': draft})
        before = self.evidence()
        result = self.history.compare(self.key, 1, 2, workspace_id=self.scope)
        sections = {row['section']: row for row in result['sections']}
        self.assertTrue(sections['wording']['changed'])
        self.assertEqual(sections['controls']['after'], {'seed': '42'})
        self.assertTrue(sections['lineage']['changed'])
        self.assertFalse(sections['recipe_graph']['changed'])
        self.assertEqual(before, self.evidence())

    def test_large_diff_is_explicitly_omitted_with_exact_hashes(self):
        self.edit(2, 'After' * 3000)
        with patch.object(self.module, 'MAX_SECTION_BYTES', 100):
            result = self.history.compare(self.key, 1, 2, workspace_id=self.scope)
        section = next(x for x in result['sections'] if x['section'] == 'wording')
        self.assertTrue(section['omitted'])
        self.assertNotIn('before', section)
        self.assertNotIn('after', section)
        self.assertEqual(section['after_sha256'], hashlib.sha256(canonical({'positive': 'After' * 3000})).hexdigest())

    def test_export_is_canonical_exact_metadata_not_dependency_acceptance(self):
        original = self.store.get(self.key, 1)
        before = self.evidence()
        with ExitStack() as stack:
            for name in ('_runtime', '_inputs', '_graph_identity', '_check_record'):
                stack.enter_context(patch.object(self.store, name, side_effect=AssertionError('Runtime I/O')))
            stack.enter_context(patch.object(self.store.workspace, 'file', side_effect=AssertionError('Media I/O')))
            self.page()
            self.history.compare(self.key, 1, 1, workspace_id=self.scope)
            result = self.history.export_revision(self.key, 1, workspace_id=self.scope)
        raw = result['export_json'].encode('utf-8')
        document = json.loads(raw)
        self.assertEqual(canonical(document), raw)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), result['export_sha256'])
        self.assertEqual(len(raw), result['export_bytes'])
        self.assertEqual(canonical(document['record']).decode(), original['record_json'])
        self.assertEqual(document['record_sha256'], original['record_sha256'])
        for flag in ('dependencies_checked', 'generation_submitted', 'staging_performed'):
            self.assertIs(result[flag], False)
            self.assertIs(document[flag], False)
        self.assertEqual(before, self.evidence())

    def test_exact_historical_export_survives_new_head_and_reopen(self):
        first = self.history.export_revision(self.key, 1, workspace_id=self.scope)
        self.edit(2, 'New head')
        self.adapter.reopen()
        other = self.module.SetupHistory(self.adapter.store)
        later = other.export_revision(self.key, 1, workspace_id=self.scope)
        self.assertEqual(first['export_json'], later['export_json'])
        self.assertEqual(first['export_sha256'], later['export_sha256'])
        self.assertEqual(later['head_revision'], 2)

    def test_corrupt_record_accounting_or_noncanonical_bytes_refuse_without_repair(self):
        with self.store.workspace.connection() as db:
            original = dict(db.execute('SELECT * FROM setup_versions_v1').fetchone())
        for column, value in (('bytes', -1), ('sha256', 'f' * 64), ('record', ' ' + original['record']),
                              ('record', 'x' * (self.module.MAX_RECORD_BYTES + 1))):
            with self.subTest(column=column, size=len(str(value))):
                with self.store.workspace.connection() as db:
                    db.execute('UPDATE setup_versions_v1 SET record=?,sha256=?,bytes=?',
                               (original['record'], original['sha256'], original['bytes']))
                    db.execute('UPDATE setup_versions_v1 SET ' + column + '=?', (value,))
                before = self.evidence()
                with self.assertRaises(ValueError) as error:
                    self.page()
                self.assertEqual(error.exception.code, 'setup_history_corrupt')
                self.assertEqual(before, self.evidence())

    def test_holes_are_not_empty_history(self):
        self.edit(2, 'Second')
        with self.store.workspace.connection() as db:
            db.execute('DELETE FROM setup_versions_v1 WHERE revision=1')
        with self.assertRaises(ValueError) as error:
            self.page()
        self.assertEqual(error.exception.code, 'setup_history_corrupt')

    def test_export_budget_refusal_retains_all_evidence(self):
        before = self.evidence()
        with patch.object(self.module, 'MAX_EXPORT_BYTES', 10), self.assertRaises(ValueError):
            self.history.export_revision(self.key, 1, workspace_id=self.scope)
        self.assertEqual(before, self.evidence())

    def test_wal_writer_cannot_mix_scope_head_and_history_rows(self):
        workspace = self.store.workspace
        with workspace.connection() as db:
            db.execute('PRAGMA journal_mode=WAL')
        original_scope = workspace._check_scope
        def concurrent_write(db, scope):
            result = original_scope(db, scope)
            with workspace.connection() as writer:
                writer.execute('INSERT INTO setup_versions_v1 SELECT draft_id,2,record,sha256,bytes FROM setup_versions_v1 WHERE revision=1')
                writer.execute('UPDATE setup_drafts_v1 SET head=2')
            return result
        with patch.object(workspace, '_check_scope', side_effect=concurrent_write):
            observed = self.page()
        self.assertEqual(observed['head_revision'], 1)
        self.assertEqual([row['revision'] for row in observed['revisions']], [1])
        self.assertEqual(self.page()['head_revision'], 2)


    def test_future_orphan_revision_refuses_without_silently_repairing_head(self):
        with self.store.workspace.connection() as db:
            db.execute('INSERT INTO setup_versions_v1 SELECT draft_id,2,record,sha256,bytes FROM setup_versions_v1')
        before = self.evidence()
        with self.assertRaises(ValueError) as error:
            self.page()
        self.assertEqual(error.exception.code, 'setup_history_corrupt')
        self.assertEqual(before, self.evidence())

    def test_self_consistent_digest_does_not_bypass_record_schema_validation(self):
        original = self.store.get(self.key, 1)
        record = json.loads(original['record_json'])
        record['draft']['version'] = 2
        raw = canonical(record)
        with self.store.workspace.connection() as db:
            db.execute('UPDATE setup_versions_v1 SET record=?,sha256=?,bytes=?',
                       (raw.decode(), hashlib.sha256(raw).hexdigest(), len(raw)))
        with self.assertRaises(ValueError) as error:
            self.history.export_revision(self.key, 1, workspace_id=self.scope)
        self.assertEqual(error.exception.code, 'setup_history_corrupt')

    def test_all_observations_work_with_sqlite_query_only_connections(self):
        connect = self.store.workspace.connection
        @contextmanager
        def query_only():
            with connect() as db:
                db.execute('PRAGMA query_only=ON')
                yield db
        with patch.object(self.store.workspace, 'connection', side_effect=query_only):
            self.assertEqual(self.page()['head_revision'], 1)
            self.history.compare(self.key, 1, 1, workspace_id=self.scope)
            self.history.export_revision(self.key, 1, workspace_id=self.scope)

if __name__ == '__main__':
    unittest.main()
