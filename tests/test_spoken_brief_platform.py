"""Native file metadata contracts with actionable platform diagnostics."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import spoken_brief_compile as compiler
import spoken_brief_inbox as inbox


class NativeFileTests(unittest.TestCase):
    def test_captures_ordinary_native_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'source.md'; path.write_bytes(b'Ordinary source.')
            try:
                raw, _ = inbox._capture(path, 1024)
            except compiler.SpokenBriefError as exc:
                with path.open('rb') as stream:
                    self.fail(f'{exc}; lstat={inbox._identity(path.lstat())}; '
                              f'fstat={inbox._identity(os.fstat(stream.fileno()))}')
            self.assertEqual(b'Ordinary source.', raw)

    def test_captures_atomically_replaced_state(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'root'; root.mkdir()
            state = Path(folder) / 'inbox.json'
            instance = inbox.Inbox(root, state)
            instance.scan()
            try:
                inbox._capture(state, inbox.MAX_STATE_BYTES)
            except compiler.SpokenBriefError as exc:
                with state.open('rb') as stream:
                    self.fail(f'{exc}; lstat={inbox._identity(state.lstat())}; '
                              f'fstat={inbox._identity(os.fstat(stream.fileno()))}')

    def test_captured_compiler_does_not_resolve_or_open_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder).resolve() / 'missing.md'
            with patch.object(Path, 'resolve', side_effect=AssertionError('No path resolution')):
                result = compiler.compile_snapshot(path, b'Captured text.')
            self.assertEqual(str(path), result['source']['path'])
            self.assertFalse(path.exists())


if __name__ == '__main__': unittest.main()
