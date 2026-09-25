"""Saved setup recipes must remain strict, round-trippable JSON (refs #923)."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import test_server as server_fixtures

workspace = server_fixtures.server.AssetWorkspace
WorkspaceError = server_fixtures.server.WorkspaceError


class SavedSetupJsonTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.store = workspace(Path(temporary.name))
        self.kept = self.store.save_setup({'id': 'kept', 'name': 'Keep', 'recipe': {'preset': 'demo'}})

    def post(self, raw):
        handler = server_fixtures.server.Handler.__new__(server_fixtures.server.Handler)
        handler.studio = SimpleNamespace(assets=self.store)
        handler.path = '/api/setups'
        handler.headers = {'Host': '127.0.0.1:8191', 'Origin': 'http://127.0.0.1:8191',
                           'Content-Type': 'application/json', 'Content-Length': str(len(raw))}
        handler.rfile = io.BytesIO(raw)
        replies = []; handler._json = lambda status, value: replies.append((status, value))
        handler.do_POST()
        self.assertEqual(len(replies), 1)
        return replies[0]

    def test_non_finite_nested_recipe_values_are_refused_without_writes(self):
        before = self.store.setups()
        for number in (float('nan'), float('inf'), float('-inf')):
            with self.subTest(number=number):
                with self.assertRaisesRegex(WorkspaceError, 'finite JSON'):
                    self.store.save_setup({'id': 'bad', 'name': 'Bad',
                        'recipe': {'preset': 'demo', 'controls': {'values': [number]}}})
                self.assertEqual(self.store.setups(), before)

    def test_raw_http_non_finite_and_overflow_numbers_return_400_without_writes(self):
        before = self.store.setups()
        for token in ('NaN', 'Infinity', '-Infinity', '1e9999'):
            with self.subTest(token=token):
                raw = ('{"id":"bad","name":"Bad","recipe":{"preset":"demo","value":' + token + '}}').encode()
                status, value = self.post(raw)
                self.assertEqual(status, 400, value)
                self.assertEqual(value['code'], 'invalid_asset_command')
                self.assertIn('finite JSON', value['error'])
                self.assertEqual(self.store.setups(), before)

    def test_non_json_and_recursive_python_values_are_validation_errors(self):
        recursive = {}; recursive['self'] = recursive
        for recipe in ({'value': {1, 2}}, {'value': b'bytes'}, recursive):
            with self.subTest(kind=type(recipe.get('value')).__name__):
                with self.assertRaisesRegex(WorkspaceError, 'finite JSON'):
                    self.store.save_setup({'id': 'bad', 'name': 'Bad', 'recipe': recipe})
        self.assertEqual([row['id'] for row in self.store.setups()], ['kept'])

    def test_finite_json_and_large_integer_seed_keep_exact_round_trip_and_reuse(self):
        recipe = {'preset': 'demo', 'controls': {'seed': 9223372036854775806,
                  'strength': 0.0, 'nested': [1e308, -1e308, None, True, 'NaN']}}
        payload = {'id': 'valid', 'name': 'Valid', 'recipe': recipe}
        raw = json.dumps(payload, allow_nan=False).encode()
        self.assertEqual(self.post(raw), (200, {'id': 'valid', 'name': 'Valid'}))
        self.assertEqual(self.post(raw), (200, {'id': 'valid', 'name': 'Valid'}))
        self.assertEqual(next(row['recipe'] for row in self.store.setups() if row['id'] == 'valid'), recipe)
        self.assertEqual(len(self.store.setups()), 2)
        json.dumps(self.store.setups(), allow_nan=False)
