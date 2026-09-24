"""Bounded retry of transient Windows replace refusals; everything else propagates at once."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import file_replace


def refusal(winerror=5):
    err = PermissionError(13, 'Access is denied'); err.winerror = winerror; return err


class FileReplaceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.source, self.target = root / 'state.json.abc.tmp', root / 'state.json'
        self.source.write_bytes(b'new'); self.target.write_bytes(b'old')

    def run_with(self, failures):
        """Path.replace raises each queued error once, then really replaces."""
        original, calls, sleeps = Path.replace, [], []
        def replace(path, target):
            calls.append(path)
            if failures: raise failures.pop(0)
            return original(path, target)
        with patch.object(Path, 'replace', replace):
            return file_replace.replace(self.source, self.target, sleeps.append), calls, sleeps

    def test_transient_refusals_are_retried_until_the_replace_succeeds(self):
        for code in (5, 32):
            with self.subTest(winerror=code):
                self.source.write_bytes(b'new'); self.target.write_bytes(b'old')
                attempts, calls, sleeps = self.run_with([refusal(code), refusal(code)])
                self.assertEqual((attempts, len(calls)), (3, 3))
                self.assertEqual(sleeps, list(file_replace.DELAYS[:2]))
                self.assertEqual(self.target.read_bytes(), b'new'); self.assertFalse(self.source.exists())

    def test_first_attempt_success_does_not_sleep(self):
        self.assertEqual(self.run_with([])[::2], (1, []))
        self.assertEqual(self.target.read_bytes(), b'new')

    def test_persistent_refusal_raises_after_the_bound(self):
        failures = [refusal() for _ in range(20)]
        with self.assertRaises(PermissionError) as caught: self.run_with(failures)
        self.assertEqual(caught.exception.winerror, 5)
        self.assertEqual(len(failures), 20 - len(file_replace.DELAYS) - 1)
        self.assertTrue(any('refused 6 times' in note for note in caught.exception.__notes__))
        self.assertLessEqual(sum(file_replace.DELAYS), 2.0)
        self.assertEqual((self.source.read_bytes(), self.target.read_bytes()), (b'new', b'old'))

    def test_other_errors_propagate_without_retry(self):
        plain = PermissionError(13, 'Permission denied')  # POSIX EACCES: no winerror, a real refusal
        for error in (plain, refusal(2), FileNotFoundError('gone'), OSError('disk full')):
            with self.subTest(error=error):
                failures = [error]
                with self.assertRaises(type(error)) as caught: self.run_with(failures)
                self.assertIs(caught.exception, error); self.assertEqual(failures, [])
                self.assertFalse(hasattr(caught.exception, '__notes__'))

    def test_default_sleep_is_the_module_clock(self):
        failures, original, sleeps = [refusal()], Path.replace, []
        def replace(path, target):
            if failures: raise failures.pop(0)
            return original(path, target)
        with patch.object(Path, 'replace', replace), patch.object(file_replace.time, 'sleep', sleeps.append):
            self.assertEqual(file_replace.replace(self.source, self.target), 2)
        self.assertEqual(sleeps, [file_replace.DELAYS[0]])

    @unittest.skipUnless(os.name == 'nt', 'Windows share-mode semantics')
    def test_real_windows_reader_hold_is_outlasted(self):
        # Python's open() shares read/write but not delete, like the receipt reader seen live.
        # The reader lets go during the first back-off, so the OS itself must have refused attempt one.
        holder = open(self.target, 'rb'); self.addCleanup(holder.close); sleeps = []
        def release(delay): sleeps.append(delay); holder.close()
        self.assertEqual(file_replace.replace(self.source, self.target, release), 2)
        self.assertEqual(sleeps, [file_replace.DELAYS[0]]); self.assertEqual(self.target.read_bytes(), b'new')


if __name__ == '__main__':
    unittest.main()
