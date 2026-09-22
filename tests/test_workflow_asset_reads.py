"""Bounded asset observations through the real bridge, raw HTTP and SQLite.

The parent fixtures supply observations, not an alternate client implementation.
Every response still passes through AssetReadClient's raw decoder and validator.
"""
import copy
from http.client import IncompleteRead
import io
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

import test_asset_read_client as client_fixture
import test_asset_read_http as http_fixture
from studio_workflow import asset_reads
from studio_workflow.agent_bridge import AgentBridge, MODES
from studio_workflow.client import Client
from studio_workflow.core import canonical, digest
from studio_workflow.mcp_server import main


def data(result):
    return json.loads(result['data_json'])


class WorkflowAssetReadTests(unittest.TestCase):
    def setUp(self):
        self.fixture = client_fixture.AssetReadClientTests()
        self.fixture.setUp()
        self.scope = self.fixture.scope
        # Use the ordinary client used by the real MCP entry point, not a fake
        # .request() result that bypasses response bytes and schema validation.
        self.client = Client(timeout=7)
        self.bridge = AgentBridge(self.client)

    def reply(self, value, **kwargs):
        response = self.fixture.reply(value, **kwargs)
        self.client.opener = self.fixture.client.opener
        return response

    def assert_refusal(self, result, code):
        self.assertFalse(result['ok'], result)
        self.assertEqual(result['error']['code'], code, result)
        self.assertNotIn('recovery', result['error'])
        self.assertEqual(data(result), {})

    def test_both_tools_are_read_only_in_every_mode_and_definitions_are_isolated(self):
        with patch.object(self.client.opener, 'open', side_effect=AssertionError('Unexpected I/O')):
            for mode in MODES:
                definitions = AgentBridge(self.client, mode).definitions()
                for name in ('asset_page', 'asset_selection'):
                    self.assertIn(name, definitions)
                    self.assertEqual(definitions[name]['mode'], 'read')
                    self.assertIs(definitions[name]['mutating'], False)
                    self.assertIs(definitions[name]['inputSchema']['additionalProperties'], False)
            definitions['asset_page']['inputSchema']['properties'].clear()
            self.assertIn('limit', self.bridge.definitions()['asset_page']['inputSchema']['properties'])

    def test_describe_neither_loads_sdk_nor_contacts_studio(self):
        with patch.object(Client, 'request', side_effect=AssertionError('Unexpected HTTP')), \
             patch('studio_workflow.mcp_server.serve', side_effect=AssertionError('SDK entry reached')), \
             patch('sys.stdout', new_callable=io.StringIO) as output:
            self.assertEqual(main(['--describe']), 0)
        self.assertIn('asset_selection', json.loads(output.getvalue())['tools'])

    def test_exact_page_uses_existing_transport_timeout_and_one_get(self):
        response = self.reply(self.fixture.page)
        with patch.object(self.client, 'request', side_effect=AssertionError('Loose decoder used')), \
             patch.object(self.client.opener, 'open', wraps=self.client.opener.open) as calls:
            result = self.bridge.invoke('asset_page', {'workspace_id': self.scope})
        self.assertTrue(result['ok'], result)
        self.assertEqual(data(result), self.fixture.page)
        self.assertEqual(result['data_sha256'], digest(self.fixture.page))
        self.assertEqual(result['context']['workspace_id'], self.scope)
        self.assertEqual(calls.call_count, 1)
        request = calls.call_args.args[0]
        self.assertEqual(request.get_method(), 'GET')
        self.assertTrue(request.full_url.startswith(self.client.base + '/api/assets/page?'))
        self.assertEqual(request.get_header('Origin'), self.client.base)
        self.assertEqual(calls.call_args.kwargs['timeout'], 7)
        self.assertTrue(response.closed)

    def test_invalid_arguments_are_local_not_http_failures(self):
        cases = [None, [], {'workspace_id': 'bad'}, {'workspace_id': None},
                 {'limit': True}, {'limit': 0}, {'limit': 101}, {'limit': 1.5},
                 {'cursor': ''}, {'cursor': 'not-a-cursor'}, {'cursor': 'a' * 2049},
                 {'filters': None}, {'filters': []}, {'filters': {'extra': 1}},
                 {'filters': {'favorite': 1}}, {'filters': {'visibility': None}},
                 {'filters': {'review': 'invented'}}, {'filters': {'collection_id': '../x'}},
                 {'url': 'http://remote.test'}, {'automatic_pages': True}]
        with patch.object(self.client.opener, 'open', side_effect=AssertionError('Unexpected I/O')) as calls:
            for args in cases:
                with self.subTest(args=str(args)[:90]):
                    self.assert_refusal(self.bridge.invoke('asset_page', args), 'invalid_arguments')
            cases = [{}, {'ids': ['a']}, {'workspace_id': self.scope, 'ids': []},
                     {'workspace_id': self.scope, 'ids': ['a', 'a']},
                     {'workspace_id': self.scope, 'ids': ['x' * 129]},
                     {'workspace_id': self.scope, 'ids': ['a.']},
                     {'workspace_id': self.scope, 'ids': ['a' + str(i) for i in range(201)]},
                     {'workspace_id': self.scope, 'ids': 'a'},
                     {'workspace_id': self.scope, 'ids': [False]}]
            for args in cases:
                with self.subTest(args=str(args)[:90]):
                    self.assert_refusal(self.bridge.invoke('asset_selection', args), 'invalid_arguments')
            self.assertEqual(calls.call_count, 0)

    def test_valid_cursor_with_different_scope_filter_or_limit_refuses_before_transport(self):
        cursor = asset_reads._encode_cursor(self.scope, self.fixture.stamp,
                    digest(asset_reads.normalize_filters()), 1, self.fixture.asset)
        for change in ({'limit': 2}, {'workspace_id': 'f' * 32}, {'filters': {'favorite': True}}):
            with self.subTest(change=change), patch.object(self.client.opener, 'open') as calls:
                result = self.bridge.invoke('asset_page', dict(limit=1, cursor=cursor) | change)
                self.assert_refusal(result, 'invalid_arguments')
                self.assertEqual(calls.call_count, 0)

    def test_response_scope_flags_order_and_shapes_use_strict_asset_contract(self):
        mutations = [lambda p: p.update(workspace_id='f' * 32),
                     lambda p: p.update(generation_submitted=0),
                     lambda p: p.update(extra=True),
                     lambda p: p['assets'].append(copy.deepcopy(p['assets'][0])),
                     lambda p: p['assets'][0].update(url='https://remote.test/file'),
                     lambda p: p['assets'][0].update(metadata_revision=True),
                     lambda p: p.update(next_cursor='bad')]
        for mutate in mutations:
            value = copy.deepcopy(self.fixture.page); mutate(value)
            response = self.reply(value)
            result = self.bridge.invoke('asset_page', {'workspace_id': self.scope})
            self.assert_refusal(result, 'request_failed')
            self.assertTrue(response.closed)

    def test_duplicate_keys_invalid_utf8_and_nonfinite_are_not_normalized(self):
        raw = canonical(self.fixture.page)
        for bad in (b'{"assets":[],"assets":[]}', b'\xff', b'{"n":NaN}',
                    raw.replace(b'"limit":50', b'"limit":25,"limit":50')):
            response = self.reply(bad)
            self.assert_refusal(self.bridge.invoke('asset_page', {}), 'request_failed')
            self.assertTrue(response.closed)

    def test_response_size_and_framing_failures_close_streams(self):
        for size in (asset_reads.MAX_RESPONSE_BYTES + 1, 50000):
            response = self.reply(self.fixture.page, length=size)
            self.assert_refusal(self.bridge.invoke('asset_page', {}), 'request_failed')
            self.assertTrue(response.closed)

    def test_transport_failure_is_one_failed_read_not_an_unknown_mutation(self):
        for name, args in [('asset_page', {}), ('asset_selection', {'workspace_id': self.scope, 'ids': ['a']})]:
            for failure in (TimeoutError('lost response'), IncompleteRead(b'{', 30)):
                with self.subTest(name=name, failure=type(failure).__name__), \
                     patch.object(self.client.opener, 'open', side_effect=failure) as calls:
                    self.assert_refusal(self.bridge.invoke(name, args), 'request_failed')
                    self.assertEqual(calls.call_count, 1)

    def test_http_error_preserves_status_without_retry_and_has_its_own_byte_limit(self):
        value = {'error': 'Explicitly refresh', 'code': 'asset_cursor_stale'}
        for maximum in (False, True):
            response = client_fixture.Reply(canonical(value), length=65537 if maximum else None)
            error = HTTPError(self.client.base, 409, 'Conflict', response.headers, response)
            with patch.object(self.client.opener, 'open', side_effect=error) as calls:
                result = self.bridge.invoke('asset_page', {})
            self.assertFalse(result['ok']); self.assertTrue(response.closed)
            self.assertEqual(calls.call_count, 1)
            self.assertNotIn('recovery', result['error'])
            if maximum:
                self.assert_refusal(result, 'request_failed')
            else:
                self.assertEqual(result['error']['code'], 'asset_cursor_stale')
                self.assertEqual(result['error']['http_status'], 409)
                self.assertEqual(data(result), value)

    def selection(self, ids):
        result = {key: value for key, value in self.fixture.page.items() if key in
                  ('workspace_id', 'catalogue', 'observation_only', 'media_bytes_verified', 'generation_submitted')}
        return dict(result, format='studio.asset-selection/v1',
                    items=[{'id': key, 'state': 'missing', 'asset': None} for key in ids])

    def test_asset_ids_are_not_coerced_to_workflow_ids_or_silently_pruned(self):
        ids = ['x' * 128, '__proto__', 'constructor', 'prototype']
        expected = self.selection(ids); response = self.reply(expected)
        with patch.object(self.client.opener, 'open', wraps=self.client.opener.open) as calls:
            result = self.bridge.invoke('asset_selection', {'workspace_id': self.scope, 'ids': ids})
        self.assertTrue(result['ok'], result); self.assertEqual(data(result), expected)
        request = calls.call_args.args[0]
        self.assertEqual(request.get_method(), 'POST')
        self.assertEqual(json.loads(request.data), {'workspace_id': self.scope, 'ids': ids})
        self.assertEqual(calls.call_count, 1); self.assertTrue(response.closed)

    def test_selection_missing_or_reordered_items_cannot_pass_as_complete(self):
        expected = self.selection(['a', 'b'])
        for mutate in (lambda p: p['items'].pop(), lambda p: p['items'].reverse(),
                       lambda p: p['items'][0].update(state='active')):
            value = copy.deepcopy(expected); mutate(value); response = self.reply(value)
            result = self.bridge.invoke('asset_selection', {'workspace_id': self.scope, 'ids': ['a', 'b']})
            self.assert_refusal(result, 'request_failed'); self.assertTrue(response.closed)

    def test_large_unicode_selection_retains_all_ids_under_observation_not_authoring_budget(self):
        ids = ['a' + str(i) for i in range(200)]; value = self.selection(ids)
        for item in value['items']:
            item.update(state='active', asset=dict(self.fixture.asset, id=item['id'],
                url='/api/assets/' + item['id'] + '/file', title='🌙' * 200,
                filename='🌙' * 256, preset_name='🌙' * 200))
        raw = json.dumps(value).encode('utf-8')
        self.assertGreater(len(raw), 1024 * 1024)
        self.assertLess(len(raw), asset_reads.MAX_RESPONSE_BYTES)
        response = self.reply(raw)
        result = self.bridge.invoke('asset_selection', {'workspace_id': self.scope, 'ids': ids})
        self.assertTrue(result['ok'], result)
        self.assertEqual(data(result), value); self.assertEqual(result['data_sha256'], digest(value))
        self.assertTrue(response.closed)

    def test_asset_reads_share_four_slot_admission_and_release_on_failure(self):
        self.assertIn('asset_page', self.bridge.definitions())
        entered = threading.Barrier(5); release = threading.Event(); results = []
        def held(*args, **kwargs):
            entered.wait(timeout=5)
            if not release.wait(5): raise AssertionError('Fixture was not released')
            raise TimeoutError('lost read')
        with patch.object(self.client.opener, 'open', side_effect=held) as calls:
            workers = [threading.Thread(target=lambda: results.append(self.bridge.invoke('asset_page', {}))) for _ in range(4)]
            try:
                for worker in workers: worker.start()
                entered.wait(timeout=5)
                self.assert_refusal(self.bridge.invoke('asset_page', {}), 'gateway_busy')
                self.assert_refusal(self.bridge.invoke('workflow_list', {}), 'gateway_busy')
                self.assertEqual(calls.call_count, 4)
            finally:
                release.set()
                for worker in workers: worker.join(7)
        self.assertTrue(all(not worker.is_alive() for worker in workers))
        self.assertEqual(len(results), 4)
        for result in results: self.assert_refusal(result, 'request_failed')
        self.reply(self.fixture.page)
        self.assertTrue(self.bridge.invoke('asset_page', {})['ok'])


class WorkflowAssetHTTPTests(unittest.TestCase):
    def setUp(self):
        self.fixture = http_fixture.AssetReadHTTPTests()
        self.fixture.setUp(); self.addCleanup(self.fixture.tearDown)
        self.client, _ = self.fixture.make_client()
        self.bridge = AgentBridge(self.client)

    def test_explicit_paging_and_off_page_selection_use_the_real_sqlite_owner(self):
        f = self.fixture
        with f.store.connection() as db:
            db.execute('UPDATE assets SET trashed_at=0 WHERE id=?', (f.ids[1],))
        before = f.store.snapshot()
        with patch.object(self.client.opener, 'open', wraps=self.client.opener.open) as calls:
            first = self.bridge.invoke('asset_page', {'limit': 1, 'workspace_id': f.scope})
            self.assertTrue(first['ok'], first)
            page = data(first); self.assertEqual(page['assets'][0]['id'], f.ids[2])
            self.assertEqual(calls.call_count, 1)
            next_page = self.bridge.invoke('asset_page', {'limit': 1, 'cursor': page['next_cursor']})
            self.assertTrue(next_page['ok'], next_page)
            self.assertEqual(data(next_page)['assets'][0]['id'], f.ids[0])
            self.assertIsNone(data(next_page)['next_cursor'])
            selected = self.bridge.invoke('asset_selection', {'workspace_id': f.scope,
                'ids': [f.ids[0], 'gone', f.ids[1]]})
            self.assertTrue(selected['ok'], selected)
            self.assertEqual([r['state'] for r in data(selected)['items']], ['active', 'missing', 'trashed'])
            self.assertEqual(calls.call_count, 3)
        self.assertEqual(before, f.store.snapshot())
        with f.store.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM asset_commands').fetchone()[0], 0)
        self.assertEqual((Path(f.temp.name) / 'image.png').read_bytes(), b'original')

    def test_stale_and_foreign_workspace_return_typed_conflicts_without_implicit_refresh(self):
        f = self.fixture
        first = self.bridge.invoke('asset_page', {'limit': 1})
        self.assertTrue(first['ok'], first)
        with f.store.connection() as db: db.execute("UPDATE assets SET title='new'")
        cases = [('asset_page', {'limit': 1, 'cursor': data(first)['next_cursor']}, 'asset_cursor_stale'),
                 ('asset_selection', {'workspace_id': 'f' * 32, 'ids': [f.ids[0]]}, 'asset_workspace_conflict')]
        for name, args, code in cases:
            with patch.object(self.client.opener, 'open', wraps=self.client.opener.open) as calls:
                result = self.bridge.invoke(name, args)
            self.assertFalse(result['ok']); self.assertEqual(result['error']['code'], code)
            self.assertEqual(result['error']['http_status'], 409)
            self.assertNotIn('recovery', result['error']); self.assertEqual(calls.call_count, 1)


if __name__ == '__main__': unittest.main()
