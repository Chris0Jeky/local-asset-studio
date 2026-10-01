"""Headless family exploration must use the shared read-only loopback client."""
import contextlib
import io
import json
import unittest
from unittest.mock import Mock, patch

from studio_workflow import asset_family_client as api


class FamilyClientTests(unittest.TestCase):
    def setUp(self):
        self.scope = 'a'*32
        self.result = {'version': 1, 'workspace_id': self.scope, 'asset_id': 'one',
                       'observation_only': True, 'generation_submitted': False, 'media_bytes_verified': False}
        self.transport = Mock()
        self.transport.request.return_value = self.result
        self.client = api.FamilyClient(self.transport)

    def test_inspect_children_and_recall_are_get_only(self):
        self.assertEqual(self.client.inspect('one', self.scope), self.result)
        self.assertEqual(self.client.inspect('one', self.scope, children=True), self.result)
        self.assertEqual(self.client.recall('one', self.scope), self.result)
        self.assertEqual(self.transport.request.call_args_list, [
            unittest.mock.call('/api/assets/family/one?workspace_id='+self.scope),
            unittest.mock.call('/api/assets/family/one?workspace_id='+self.scope+'&children=true'),
            unittest.mock.call('/api/assets/recall/one?workspace_id='+self.scope)])

    def test_bad_scope_or_path_sends_no_request(self):
        for identifier, scope in (('../other', self.scope), ('one', 'bad'), ([], self.scope)):
            with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                self.client.inspect(identifier, scope)
        with self.assertRaises(ValueError): self.client.inspect('one', self.scope, children=1)
        self.transport.request.assert_not_called()

    def test_foreign_or_mutating_reply_is_refused(self):
        for fields in ({'workspace_id': 'b'*32}, {'asset_id': 'another'}, {'generation_submitted': True},
                       {'version': 2}, {'observation_only': False}, {'media_bytes_verified': True}):
            with self.subTest(fields=fields):
                self.transport.request.return_value = dict(self.result, **fields)
                with self.assertRaises(ValueError): self.client.recall('one', self.scope)

    def test_cli_emits_one_read_only_json_result(self):
        output = io.StringIO()
        with patch.object(api, 'Client', return_value=self.transport), contextlib.redirect_stdout(output):
            code = api.main(['inspect', 'one', '--workspace', self.scope, '--children'])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue()), self.result)
        self.transport.request.assert_called_once_with('/api/assets/family/one?workspace_id='+self.scope+'&children=true')

    def test_cli_failure_does_not_emit_partial_success_or_retry(self):
        output = io.StringIO()
        self.transport.request.side_effect = ValueError('unavailable')
        with patch.object(api, 'Client', return_value=self.transport), contextlib.redirect_stdout(output):
            code = api.main(['recall', 'one', '--workspace', self.scope])
        self.assertEqual(code, 2)
        result = json.loads(output.getvalue())
        self.assertFalse(result['generation_submitted'])
        self.assertIn('unavailable', result['error'])
        self.transport.request.assert_called_once()
