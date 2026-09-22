"""Compatibility, real HTTP and stored-data adversarial history contracts."""
import json
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from urllib.parse import urlencode

import test_reviewed_setup_history as base
import test_recipe_shortlist_apply as fixture
from studio_workflow.core import canonical, digest
from studio_workflow.setup_draft_http import route
from studio_workflow.setup_history import SetupHistory
from test_server import server


class HistoryEdgeTests(unittest.TestCase):
    setUp = fixture.SetupApplyTests.setUp
    store = fixture.SetupApplyTests.store
    command = fixture.SetupApplyTests.command
    create = fixture.SetupApplyTests.create
    revisions = base.ReviewedSetupHistoryTests.revisions
    url = base.ReviewedSetupHistoryTests.url

    def test_existing_receipt_ids_matching_new_read_actions_keep_their_route(self):
        for request_id in ('history', 'compare', 'export'):
            with self.subTest(request_id=request_id):
                original = self.command('create', request_id=request_id, draft=self.before)
                result = route('/api/workflow-studio/setup-drafts/requests/' + request_id, None, self.s)
                self.assertEqual(result['request_id'], request_id)
                self.assertEqual(result['record_sha256'], original['record_sha256'])

    def test_no_setup_tables_are_created_by_an_uninitialized_history_read(self):
        with self.s.assets.connection() as db:
            before = [tuple(r) for r in db.execute('SELECT name,sql FROM sqlite_master ORDER BY name')]
        with self.assertRaisesRegex(ValueError, 'not initialized'):
            SetupHistory(self.s.assets).page('absent', workspace_id=self.scope)
        with self.s.assets.connection() as db:
            self.assertEqual([tuple(r) for r in db.execute('SELECT name,sql FROM sqlite_master ORDER BY name')], before)

    def test_scalar_hash_and_record_corruption_is_bounded_and_preserved(self):
        key = self.revisions(1)
        with self.s.assets.connection() as db:
            original = dict(db.execute('SELECT * FROM setup_versions_v1').fetchone())
        for column, value in [('sha256', '0'*64), ('bytes', b'x'*100000), ('sha256', b'x'*100000), ('record', '{}')]:
            with self.subTest(column=column, value=repr(value)[:30]):
                with self.s.assets.connection() as db:
                    db.execute('UPDATE setup_versions_v1 SET record=?,sha256=?,bytes=?', (original['record'], original['sha256'], original['bytes']))
                    db.execute('UPDATE setup_versions_v1 SET '+column+'=?', (value,))
                with self.assertRaises(ValueError): SetupHistory(self.s.assets).page(key, workspace_id=self.scope)
                with self.s.assets.connection() as db:
                    self.assertEqual(db.execute('SELECT '+column+' FROM setup_versions_v1').fetchone()[0], value)

    def test_rehashed_unsupported_fields_do_not_become_exportable(self):
        key = self.revisions(1)
        with self.s.assets.connection() as db:
            value = json.loads(db.execute('SELECT record FROM setup_versions_v1').fetchone()[0])
            value['future_authority'] = True
            raw = canonical(value)
            db.execute('UPDATE setup_versions_v1 SET record=?,sha256=?,bytes=?', (raw.decode(), digest(value), len(raw)))
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            SetupHistory(self.s.assets).export_revision(key, 1, workspace_id=self.scope)

    def test_actual_staged_handles_export_even_when_copies_are_missing(self):
        first = self.create()
        applied = fixture.SetupApplyTests.apply(self, first)
        original = self.store().get(first['draft_id'], 2)['record_sha256']
        for item in applied['inputs']:
            (self.s.comfy_root/'input'/item['file']).unlink()
            (self.s.experiments/'uploads'/item['file']).unlink()
        exported = SetupHistory(self.s.assets).export_revision(first['draft_id'], 2, workspace_id=self.scope)
        self.assertEqual(exported['export']['inputs'], applied['inputs'])
        self.assertEqual(exported['export']['source_record_sha256'], original)
        self.assertEqual(self.s.upload_count, 3, 'history must not restage missing files')

    def test_response_budget_counts_actual_ascii_wire_bytes_not_canonical_bytes(self):
        self.before['recipe']['controls']['positive'] = '界' * 1000
        key = self.revisions(1)
        history = SetupHistory(self.s.assets)
        value = history.export_revision(key, 1, workspace_id=self.scope)
        canonical_size = len(canonical(value))
        self.assertGreater(len(json.dumps(value).encode()), canonical_size)
        with patch('studio_workflow.setup_history.MAX_READ_BYTES', canonical_size), self.assertRaisesRegex(ValueError, 'response exceeds'):
            history.export_revision(key, 1, workspace_id=self.scope)


class HistoryHTTPTests(unittest.TestCase):
    store = fixture.SetupApplyTests.store
    command = fixture.SetupApplyTests.command
    create = fixture.SetupApplyTests.create
    revisions = base.ReviewedSetupHistoryTests.revisions
    url = base.ReviewedSetupHistoryTests.url

    def setUp(self):
        fixture.SetupApplyTests.setUp(self)
        self.key = self.revisions(3)
        from studio_workflow.setup_draft_http import extend_handler
        studio = self.s
        class Handler(extend_handler(server.Handler)):
            pass
        Handler.studio = studio
        self.http = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        worker = threading.Thread(target=self.http.serve_forever, daemon=True)
        worker.start()
        def close():
            self.http.shutdown(); self.http.server_close(); worker.join(5)
        self.addCleanup(close)

    def request(self, path, method='GET', host='127.0.0.1:8191'):
        connection = HTTPConnection('127.0.0.1', self.http.server_port, timeout=5)
        try:
            connection.request(method, path, '{}' if method == 'POST' else None,
                               {'Host': host, 'Origin': 'http://127.0.0.1:8191', 'Content-Type': 'application/json'})
            response = connection.getresponse()
            return response.status, json.loads(response.read()), dict(response.getheaders())
        finally: connection.close()

    def test_native_http_uses_read_projection_no_store_and_exact_exports(self):
        for action, values in [('history', {'limit': 2}), ('compare', {'left': 1, 'right': 3}), ('export', {'revision': 1})]:
            status, value, headers = self.request(self.url(self.key, action, **values))
            self.assertEqual(status, 200, value)
            self.assertEqual(headers['Cache-Control'], 'no-store')
            self.assertFalse(value['generation_submitted'])
        self.assertEqual(self.store().get(self.key)['revision'], 3)
        self.assertEqual(self.s.upload_count, 0)

    def test_host_and_scope_refusal_reveal_no_revision_metadata(self):
        path = self.url(self.key, 'history')
        for url, host, expected in [(path, 'evil.test', 403), (path.replace(self.scope, 'f'*32), '127.0.0.1:8191', 409)]:
            status, value, _ = self.request(url, host=host)
            self.assertEqual(status, expected)
            for key in ('revisions', 'export', 'sections', 'head_revision'): self.assertNotIn(key, value)

    def test_post_and_duplicate_query_are_refused_without_head_change(self):
        path = self.url(self.key, 'history')
        status, value, _ = self.request(path, 'POST')
        self.assertEqual(status, 400, value)
        status, _, _ = self.request(path + '&workspace_id=' + self.scope)
        self.assertEqual(status, 400)
        self.assertEqual(self.store().get(self.key)['revision'], 3)
