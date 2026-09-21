"""The setup-context CLI must reject oversized input without reading it all."""
from __future__ import annotations

import io
import json
from pathlib import Path
import unittest
from unittest import mock

from studio_workflow import setup_context_compatibility as L


class _GuardedStream(io.BytesIO):
    def __init__(self, value: bytes):
        super().__init__(value)
        self.read_sizes: list[int] = []

    def read(self, size: int = -1) -> bytes:
        self.read_sizes.append(size)
        return super().read(size)


class SetupContextCompatibilityCliBoundTests(unittest.TestCase):
    def test_cli_reads_only_limit_plus_sentinel_before_refusing_oversized_input(self):
        stream = _GuardedStream(b'{' + b' ' * L.MAX_INPUT_BYTES + b'}')
        output = io.StringIO()
        with mock.patch.object(Path, 'read_bytes',
                               side_effect=AssertionError('unbounded read_bytes used')),
             mock.patch.object(Path, 'open', return_value=stream),
             mock.patch('sys.stdout', output):
            code = L.main(['oversized.json'])

        self.assertEqual(code, 2)
        self.assertEqual(stream.read_sizes, [L.MAX_INPUT_BYTES + 1])
        error = json.loads(output.getvalue())['error']
        self.assertEqual(error['code'], 'invalid_setup_context')
        self.assertIn('exceeds 1 MiB', error['message'])


if __name__ == '__main__':
    unittest.main()
