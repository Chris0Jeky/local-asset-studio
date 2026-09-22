"""Preserve #723's 14 scenarios in #724's single owner, plus #737 regressions.

Deliberate v2 differences: Workspace constructor, 20-row pages, preview-only
comparisons and an inspection export, not a full private runtime record.
"""
import copy
import hashlib
import importlib
import json
import tempfile
import unittest
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode

from studio_workflow.core import canonical, digest
from studio_workflow.setup_drafts import SetupError
from test_revision_consistency_matrix import SetupAdapter
import test_reviewed_setup_history_edges as http_fixture

FLAGS = {'observation_only': True, 'dependencies_checked': False,
         'generation_submitted': False, 'staging_performed': False}


class ReconciledHistoryTests(unittest.TestCase):
    def setUp(self):
        self.module = importlib.import_module('studio_workflow.setup_history')
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.adapter = SetupAdapter(Path(temp.name)); self.adapter.create()
        self.store = self.adapter.store
        self.history = self.module.SetupHistory(self.store.workspace)
        self.key, self.scope = self.adapter.key, self.adapter.scope

    def page(self, **kwargs):
        return self.history.page(self.key, workspace_id=self.scope, **kwargs)

    def edit(self, revision, marker):
        self.adapter.edit('edit-' + str(revision), revision - 1, marker)

    def evidence(self):
        with self.store.workspace.connection() as db:
            return tuple(tuple(tuple(row) for row in db.execute('SELECT * FROM ' + table))
                         for table in ('setup_drafts_v1', 'setup_versions_v1', 'setup_operations_v1'))

    def corrupt_error(self, call):
        before = self.evidence()
        with self.assertRaises(ValueError) as error: call()
        self.assertIsInstance(error.exception, SetupError)
        self.assertEqual(error.exception.code, 'setup_history_corrupt')
        self.assertEqual(error.exception.status, 503)
        self.assertEqual(before, self.evidence())

    def rewrite(self, record, revision=1):
        raw = canonical(record)
        with self.store.workspace.connection() as db:
            db.execute('UPDATE setup_versions_v1 SET record=?,sha256=?,bytes=? WHERE revision=?',
                       (raw.decode(), hashlib.sha256(raw).hexdigest(), len(raw), revision))

    def test_hundred_revisions_walk_without_losing_identity_or_expanding_records(self):
        for revision in range(2, 101): self.edit(revision, 'Revision ' + str(revision))
        before = self.evidence(); revisions = []; args = {'limit': 13}
        while True:
            result = self.page(**args)
            self.assertEqual(result['head_revision'], 100)
            self.assertLessEqual(len(result['revisions']), 13)
            self.assertLess(len(canonical(result)), 16384)
            self.assertNotIn('draft', result['revisions'][0])
            revisions.extend(row['revision'] for row in result['revisions'])
            if result['next_before_revision'] is None: break
            args.update(before_revision=result['next_before_revision'], expected_head=100)
        self.assertEqual(revisions, list(range(100, 0, -1)))
        self.assertEqual(before, self.evidence())

    def test_continuation_requires_expected_head_and_refuses_drift(self):
        self.edit(2, 'Second'); page = self.page(limit=1)
        with self.assertRaises(ValueError): self.page(limit=1, before_revision=page['next_before_revision'])
        self.edit(3, 'Third')
        with self.assertRaises(ValueError) as error: self.page(limit=1, before_revision=2, expected_head=2)
        self.assertEqual(error.exception.code, 'setup_history_head_changed')
        self.assertEqual(self.page()['head_revision'], 3)

    def test_foreign_scope_and_invalid_bounds_refuse_before_record_loading(self):
        with patch.object(self.history, '_read', side_effect=AssertionError('Record reached')):
            for kwargs in ({'limit': True}, {'limit': 0}, {'limit': 21}, {'before_revision': True}, {'expected_head': 0}):
                with self.subTest(kwargs=kwargs), self.assertRaises(ValueError): self.page(**kwargs)
            with self.assertRaises(ValueError): self.history.page(self.key, workspace_id='f' * 32)

    def test_typed_diff_partitions_wording_controls_and_lineage_without_writes(self):
        draft = copy.deepcopy(self.adapter.draft)
        draft['recipe']['controls'].update(positive='After', seed='42')
        draft['recipe']['parent_assets'] = ['parent-one']
        self.store.command({'action': 'replace', 'workspace_id': self.scope, 'request_id': 'domains',
                            'draft_id': self.key, 'expected_revision': 1, 'draft': draft})
        before = self.evidence(); result = self.history.compare(self.key, 1, 2, workspace_id=self.scope)
        sections = {row['section']: row for row in result['sections']}
        self.assertTrue(sections['wording']['changed'])
        self.assertFalse(sections['controls']['right']['truncated'])
        self.assertEqual(json.loads(sections['controls']['right']['preview']), {'seed': '42'})
        self.assertTrue(sections['lineage']['changed'])
        self.assertFalse(sections['recipe_graph']['changed'])
        self.assertEqual(before, self.evidence())

    def test_large_diff_is_explicitly_truncated_with_exact_hashes(self):
        self.edit(2, 'After' * 3000)
        with patch.object(self.module, 'MAX_PREVIEW', 100):
            result = self.history.compare(self.key, 1, 2, workspace_id=self.scope)
        right = next(x for x in result['sections'] if x['section'] == 'wording')['right']
        raw = canonical({'positive': 'After' * 3000})
        self.assertTrue(right['truncated']); self.assertEqual(len(right['preview']), 100)
        self.assertEqual(right['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(right['bytes'], len(raw))
        self.assertEqual(right.get('omitted_bytes'), len(raw) - len(right['preview'].encode('utf-8')))

    def test_export_is_canonical_inspection_not_dependency_acceptance(self):
        original = self.store.get(self.key, 1); before = self.evidence()
        with ExitStack() as stack:
            for name in ('_runtime', '_inputs', '_graph_identity', '_check_record'):
                stack.enter_context(patch.object(self.store, name, side_effect=AssertionError('Runtime I/O')))
            stack.enter_context(patch.object(self.store.workspace, 'file', side_effect=AssertionError('Media I/O')))
            self.page(); self.history.compare(self.key, 1, 1, workspace_id=self.scope)
            result = self.history.export_revision(self.key, 1, workspace_id=self.scope)
        raw = result['export_json'].encode('utf-8'); document = json.loads(raw)
        self.assertEqual(canonical(document), raw)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), result['export_sha256'])
        self.assertEqual(len(raw), result.get('export_bytes'))
        self.assertEqual(document['draft'], original['draft'])
        self.assertEqual(document['inputs'], original['inputs'])
        self.assertEqual(document['source_record_sha256'], original['record_sha256'])
        self.assertNotIn('record', document); self.assertNotIn('runtime', document)
        self.assertNotEqual(result['export_sha256'], original['record_sha256'])
        for flag, value in FLAGS.items():
            self.assertIs(result.get(flag), value); self.assertIs(document.get(flag), value)
        self.assertEqual(before, self.evidence())

    def test_exact_historical_export_survives_new_head_and_reopen(self):
        first = self.history.export_revision(self.key, 1, workspace_id=self.scope)
        self.edit(2, 'New head'); self.adapter.reopen()
        other = self.module.SetupHistory(self.adapter.store.workspace)
        later = other.export_revision(self.key, 1, workspace_id=self.scope)
        self.assertEqual(first['export_json'], later['export_json'])
        self.assertEqual(first['export_sha256'], later['export_sha256'])
        self.assertEqual(later['head_revision'], 2)

    def test_corrupt_accounting_or_noncanonical_bytes_refuse_without_repair(self):
        with self.store.workspace.connection() as db:
            original = dict(db.execute('SELECT * FROM setup_versions_v1').fetchone())
        for column, value in (('bytes', -1), ('sha256', 'f' * 64), ('record', ' ' + original['record']),
                              ('record', 'x' * (self.module.MAX_COMMAND + 1))):
            with self.subTest(column=column, size=len(str(value))):
                with self.store.workspace.connection() as db:
                    db.execute('UPDATE setup_versions_v1 SET record=?,sha256=?,bytes=?',
                               (original['record'], original['sha256'], original['bytes']))
                    db.execute('UPDATE setup_versions_v1 SET ' + column + '=?', (value,))
                self.corrupt_error(self.page)

    def test_holes_are_not_empty_history(self):
        self.edit(2, 'Second')
        with self.store.workspace.connection() as db: db.execute('DELETE FROM setup_versions_v1 WHERE revision=1')
        self.corrupt_error(self.page)

    def test_export_budget_refusal_retains_all_evidence(self):
        before = self.evidence()
        with patch.object(self.module, 'MAX_EXPORT_BYTES', 10, create=True), self.assertRaises(ValueError):
            self.history.export_revision(self.key, 1, workspace_id=self.scope)
        self.assertEqual(before, self.evidence())

    def test_wal_writer_cannot_mix_scope_head_and_history_rows(self):
        workspace = self.store.workspace
        with workspace.connection() as db: db.execute('PRAGMA journal_mode=WAL')
        original_scope = workspace._check_scope
        def concurrent_write(db, scope):
            result = original_scope(db, scope)
            with workspace.connection() as writer:
                writer.execute('INSERT INTO setup_versions_v1 SELECT draft_id,2,record,sha256,bytes FROM setup_versions_v1 WHERE revision=1')
                writer.execute('UPDATE setup_drafts_v1 SET head=2')
            return result
        with patch.object(workspace, '_check_scope', side_effect=concurrent_write): observed = self.page()
        self.assertEqual(observed['head_revision'], 1)
        self.assertEqual([row['revision'] for row in observed['revisions']], [1])
        self.assertEqual(self.page()['head_revision'], 2)

    def test_future_orphan_revision_refuses_without_repairing_head(self):
        with self.store.workspace.connection() as db:
            db.execute('INSERT INTO setup_versions_v1 SELECT draft_id,2,record,sha256,bytes FROM setup_versions_v1')
        self.corrupt_error(self.page)

    def test_rehash_does_not_bypass_record_schema_validation(self):
        record = json.loads(self.store.get(self.key, 1)['record_json'])
        record['draft']['version'] = 2; self.rewrite(record)
        self.corrupt_error(lambda: self.history.export_revision(self.key, 1, workspace_id=self.scope))

    def test_all_observations_work_with_sqlite_query_only_connections(self):
        connect = self.store.workspace.connection
        @contextmanager
        def query_only():
            with connect() as db: db.execute('PRAGMA query_only=ON'); yield db
        with patch.object(self.store.workspace, 'connection', side_effect=query_only):
            self.assertEqual(self.page()['head_revision'], 1)
            self.history.compare(self.key, 1, 1, workspace_id=self.scope)
            self.history.export_revision(self.key, 1, workspace_id=self.scope)

    def test_off_page_corrupt_head_refuses_every_successful_observation(self):
        self.edit(2, 'Second')
        with self.store.workspace.connection() as db: db.execute('UPDATE setup_versions_v1 SET bytes=bytes+1 WHERE revision=2')
        calls = [lambda: self.page(before_revision=2, expected_head=2), lambda: self.page(before_revision=1, expected_head=2),
                 lambda: self.history.compare(self.key, 1, 1, workspace_id=self.scope),
                 lambda: self.history.export_revision(self.key, 1, workspace_id=self.scope)]
        for index, call in enumerate(calls):
            with self.subTest(index=index): self.corrupt_error(call)

    def test_versioned_envelopes_bind_head_and_explicit_observation_flags(self):
        head_hash = self.store.get(self.key)['record_sha256']
        for kind, result in [('page', self.page()), ('compare', self.history.compare(self.key, 1, 1, workspace_id=self.scope)),
                             ('export', self.history.export_revision(self.key, 1, workspace_id=self.scope))]:
            with self.subTest(kind=kind):
                self.assertEqual(result['format'], 'studio.setup-history-' + kind + '/v2')
                self.assertEqual(result.get('head_record_sha256'), head_hash)
                for flag, value in FLAGS.items(): self.assertIs(result.get(flag), value)
        self.assertEqual(self.page(limit=3).get('limit'), 3)

    def test_runtime_changes_are_detected_but_private_values_are_not_projected(self):
        self.edit(2, 'Second')
        record = json.loads(self.store.get(self.key, 2)['record_json'])
        record['runtime'].update(root='/private/new-root', endpoint='http://private-endpoint')
        self.rewrite(record, 2)
        result = self.history.compare(self.key, 1, 2, workspace_id=self.scope)
        sections = {row['section']: row for row in result['sections']}
        self.assertIn('runtime', sections)
        section = sections['runtime']; self.assertTrue(section['changed'])
        self.assertEqual(section['right']['sha256'], digest(record['runtime']))
        self.assertIsNone(section['right']['preview']); self.assertTrue(section['right']['redacted'])
        encoded = canonical(result).decode()
        self.assertNotIn('/private/new-root', encoded); self.assertNotIn('private-endpoint', encoded)

    def test_bad_staged_input_fields_remain_corruption_even_after_rehash(self):
        original = json.loads(self.store.get(self.key, 1)['record_json'])
        item = {'file': 'input.png', 'sha256': 'a'*64, 'bytes': 10, 'width': 2, 'height': 3}
        bad = [{}, dict(item, width=True), dict(item, bytes=0), dict(item, sha256='x'),
               dict(item, file='../input.png'), dict(item, extra=True)]
        for row in bad:
            with self.subTest(row=row):
                record = copy.deepcopy(original); record['inputs'] = [row]; self.rewrite(record)
                self.corrupt_error(self.page)
        record = copy.deepcopy(original); record['inputs'] = [item, item]; self.rewrite(record)
        self.corrupt_error(self.page)

    def test_runtime_and_head_scalar_bounds_are_typed_corruption(self):
        original = json.loads(self.store.get(self.key, 1)['record_json'])
        for runtime in [dict(original['runtime'], root='x'*4097), dict(original['runtime'], backend_id='')]:
            record = copy.deepcopy(original); record['runtime'] = runtime; self.rewrite(record)
            self.corrupt_error(self.page)
        self.rewrite(original)
        for head in (0, 'bad', 257):
            with self.subTest(head=head):
                with self.store.workspace.connection() as db: db.execute('UPDATE setup_drafts_v1 SET head=?', (head,))
                self.corrupt_error(self.page)

    def test_head_payload_is_loaded_once_and_reused_for_current_requests(self):
        reader = self.history._read
        for call in (self.page, lambda: self.history.compare(self.key, 1, 1, workspace_id=self.scope),
                     lambda: self.history.export_revision(self.key, 1, workspace_id=self.scope)):
            with patch.object(self.history, '_read', wraps=reader) as observed:
                call(); self.assertEqual(observed.call_count, 1)


class ReconciledHistoryHTTPTests(unittest.TestCase):
    setUp = http_fixture.HistoryHTTPTests.setUp
    store = http_fixture.HistoryHTTPTests.store
    command = http_fixture.HistoryHTTPTests.command
    create = http_fixture.HistoryHTTPTests.create
    revisions = http_fixture.HistoryHTTPTests.revisions
    url = http_fixture.HistoryHTTPTests.url
    request = http_fixture.HistoryHTTPTests.request

    def test_compare_and_export_accept_expected_head_and_refuse_drift(self):
        for action, values in [('compare', {'left': 1, 'right': 2}), ('export', {'revision': 1})]:
            for expected, status in [(3, 200), (2, 409)]:
                with self.subTest(action=action, expected=expected):
                    code, value, _ = self.request(self.url(self.key, action, expected_head=expected, **values))
                    self.assertEqual(code, status, value)
                    if status == 409:
                        self.assertEqual(value['code'], 'setup_history_head_changed')
                        self.assertNotIn('export', value); self.assertNotIn('sections', value)

    def test_corrupt_head_has_503_read_only_error_on_historical_http_reads(self):
        with self.s.assets.connection() as db: db.execute('UPDATE setup_versions_v1 SET bytes=bytes+1 WHERE revision=3')
        for action, values in [('history', {'before_revision': 2, 'expected_head': 3}),
                               ('compare', {'left': 1, 'right': 2}), ('export', {'revision': 1})]:
            with self.subTest(action=action):
                status, result, _ = self.request(self.url(self.key, action, **values))
                self.assertEqual(status, 503, result)
                self.assertEqual(result['code'], 'setup_history_corrupt')
                for flag, value in FLAGS.items(): self.assertIs(result.get(flag), value)
                self.assertNotIn('original request receipt', result.get('recovery', ''))

    def test_expected_head_bounds_are_request_errors_and_no_writes_occur(self):
        for expected in ('0', 'true', '01', '257'):
            path = self.url(self.key, 'compare', left=1, right=2) + '&expected_head=' + expected
            with self.subTest(expected=expected): self.assertEqual(self.request(path)[0], 400)
        self.assertEqual(self.store().get(self.key)['revision'], 3)
        self.assertEqual(self.s.upload_count, 0)
