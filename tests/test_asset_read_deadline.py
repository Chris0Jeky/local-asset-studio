"""Absolute observation deadlines must not relax an existing socket bound."""
import io
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from studio_workflow import asset_read_http as transport


class AssetReadDeadlineTests(unittest.TestCase):
    def handler(self, timeout=None):
        payload = {'workspace_id': 'a' * 32, 'ids': ['asset-one']}
        raw = json.dumps(payload).encode('utf-8')
        applied = []
        connection = SimpleNamespace(timeout=timeout)
        connection.gettimeout = lambda: connection.timeout
        def settimeout(value):
            applied.append(value)
            connection.timeout = value
        connection.settimeout = settimeout
        handler = SimpleNamespace(connection=connection, rfile=io.BytesIO(raw),
                                  _content_length=lambda _: len(raw))
        return handler, payload, applied

    def test_body_never_extends_a_shorter_existing_socket_timeout(self):
        handler, payload, applied = self.handler(timeout=0.25)
        with patch.object(transport.time, 'monotonic', return_value=0):
            self.assertEqual(transport._body(handler), payload)
        self.assertTrue(applied)
        self.assertTrue(all(value <= 0.25 for value in applied), applied)
        self.assertEqual(handler.connection.timeout, 0.25)

    def test_final_complete_chunk_after_deadline_is_not_accepted(self):
        handler, _, _ = self.handler()
        with patch.object(transport.time, 'monotonic', side_effect=[0, 1, 6]):
            with self.assertRaises(ValueError) as error:
                transport._body(handler)
        self.assertEqual(error.exception.status, 408)
        self.assertIsNone(handler.connection.timeout)

    def test_read_failure_restores_original_timeout(self):
        handler, _, _ = self.handler(timeout=0.25)
        handler.rfile = SimpleNamespace(read1=lambda _: (_ for _ in ()).throw(TimeoutError()))
        with self.assertRaises(TimeoutError):
            transport._body(handler)
        self.assertEqual(handler.connection.timeout, 0.25)


if __name__ == '__main__':
    unittest.main()
