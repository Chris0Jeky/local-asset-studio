"""#1776: a failed final replace in _write_json_atomic removes its own temp file and still raises."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_looks  # noqa: F401  (puts app/ on sys.path)
import server
import file_replace


class AtomicWriteCleanupTests(unittest.TestCase):
    def test_failed_replace_leaves_no_temp_and_raises(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'state.json'; target.write_text('{"old": true}', encoding='utf-8')
            with patch.object(file_replace, 'replace', side_effect=PermissionError('locked')):
                with self.assertRaises(PermissionError): server.Studio._write_json_atomic(None, target, {'new': True})
            self.assertEqual(sorted(p.name for p in Path(folder).iterdir()), ['state.json'])
            self.assertEqual(target.read_text(encoding='utf-8'), '{"old": true}', 'the previous record is untouched')

    def test_successful_replace_writes_the_value(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'state.json'
            server.Studio._write_json_atomic(None, target, {'new': True})
            self.assertIn('"new": true', target.read_text(encoding='utf-8'))
            self.assertEqual([p.name for p in Path(folder).iterdir()], ['state.json'])


if __name__ == '__main__': unittest.main()
