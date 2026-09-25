"""Native file barriers, exclusive cleanup and bounded observation publication."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import observation_state as state


class ObservationStateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'state.json'
        self.path.write_bytes(b'old')
        self.value = {'status': 'queued', 'prompt_ids': ['retained'], 'label': 'é'}

    def test_content_sync_precedes_replace_and_parent_barrier(self):
        events = []
        original_sync, original_replace = os.fsync, Path.replace
        def sync(fd):
            if stat.S_ISREG(os.fstat(fd).st_mode):
                self.assertEqual(self.path.read_bytes(), b'old')
                self.assertEqual(os.fstat(fd).st_size, len(json.dumps(self.value, indent=2).encode('utf-8')))
                events.append('file')
            return original_sync(fd)
        def replace(path, target):
            self.assertEqual(events, ['file'])
            self.assertEqual(json.loads(path.read_bytes()), self.value)
            events.append('replace')
            return original_replace(path, target)
        def parent(directory):
            self.assertEqual(events, ['file', 'replace'])
            self.assertEqual(directory, self.path.parent)
            self.assertEqual(json.loads(self.path.read_bytes()), self.value)
            events.append('parent')
            return True
        with patch.object(state.os, 'fsync', side_effect=sync), patch.object(Path, 'replace', replace):
            report = state.publish(self.path, self.value, parent)
        self.assertEqual(events, ['file', 'replace', 'parent'])
        self.assertEqual(report, {'content_synced': True, 'directory_synced': True})
        self.assertEqual(self.path.read_bytes(), json.dumps(self.value, indent=2).encode('utf-8'))
        self.assertEqual(list(self.path.parent.glob('*.tmp')), [])

    def test_temp_collision_preserves_the_existing_entry(self):
        temp = self.path.with_name('state.json.collision.tmp')
        temp.write_bytes(b'foreign')
        parent = Mock()
        with patch.object(state.uuid, 'uuid4', return_value=SimpleNamespace(hex='collision')):
            with self.assertRaises(FileExistsError):
                state.publish(self.path, self.value, parent)
        self.assertEqual(temp.read_bytes(), b'foreign')
        self.assertEqual(self.path.read_bytes(), b'old')
        parent.assert_not_called()

    def test_write_failure_cleans_exclusive_temp_and_keeps_target(self):
        original = Path.open
        @contextmanager
        def open_for_failure(path, *args, **kwargs):
            with original(path, *args, **kwargs) as stream:
                proxy = Mock(wraps=stream)
                proxy.write.side_effect = OSError('write failed')
                yield proxy
        with patch.object(Path, 'open', open_for_failure):
            with self.assertRaisesRegex(OSError, 'write failed'):
                state.publish(self.path, self.value)
        self.assertEqual(self.path.read_bytes(), b'old')
        self.assertEqual(list(self.path.parent.glob('*.tmp')), [])

    def test_failed_replace_cleans_only_the_owned_temp(self):
        parent = Mock()
        with patch.object(Path, 'replace', side_effect=OSError('replace refused')):
            with self.assertRaisesRegex(OSError, 'replace refused'):
                state.publish(self.path, self.value, parent)
        self.assertEqual(self.path.read_bytes(), b'old')
        self.assertEqual(list(self.path.parent.glob('*.tmp')), [])
        parent.assert_not_called()

    def test_visible_replace_then_error_is_not_success(self):
        original = Path.replace
        def replace(path, target):
            original(path, target)
            raise OSError('after replace')
        parent = Mock()
        with patch.object(Path, 'replace', replace):
            with self.assertRaisesRegex(OSError, 'after replace'):
                state.publish(self.path, self.value, parent)
        self.assertEqual(json.loads(self.path.read_bytes()), self.value)
        self.assertEqual(list(self.path.parent.glob('*.tmp')), [])
        parent.assert_not_called()

    def windows_refusal(self):
        err = PermissionError(13, 'Access is denied'); err.winerror = 5; return err

    def test_transient_windows_refusal_is_retried_with_the_temp_still_owned(self):
        original, calls, parent = Path.replace, [], Mock(return_value=False)
        def replace(path, target):
            calls.append(path.read_bytes())  # The owned temp is intact for every attempt.
            if len(calls) == 1: raise self.windows_refusal()
            return original(path, target)
        with patch.object(Path, 'replace', replace), patch.object(state.file_replace.time, 'sleep') as sleep:
            report = state.publish(self.path, self.value, parent)
        self.assertEqual(len(calls), 2); sleep.assert_called_once()
        self.assertEqual(report, {'content_synced': True, 'directory_synced': False})
        self.assertEqual(json.loads(self.path.read_bytes()), self.value)
        self.assertEqual(list(self.path.parent.glob('*.tmp')), []); parent.assert_called_once_with(self.path.parent)

    def test_persistent_windows_refusal_cleans_the_owned_temp_and_grants_nothing(self):
        refusals, parent = [], Mock()
        def replace(path, target):
            refusals.append(self.windows_refusal()); raise refusals[-1]
        with patch.object(Path, 'replace', replace), patch.object(state.file_replace.time, 'sleep'):
            with self.assertRaises(PermissionError) as caught:
                state.publish(self.path, self.value, parent)
        self.assertEqual(len(refusals), len(state.file_replace.DELAYS) + 1)
        self.assertIs(caught.exception, refusals[-1])
        self.assertEqual(self.path.read_bytes(), b'old')
        self.assertEqual(list(self.path.parent.glob('*.tmp')), [])
        parent.assert_not_called()

    def test_foreign_replacement_of_temp_is_not_removed_on_failure(self):
        def replace(path, target):
            path.rename(path.with_suffix('.held'))
            path.write_bytes(b'foreign')
            raise OSError('temp identity changed')
        with patch.object(Path, 'replace', replace):
            with self.assertRaisesRegex(OSError, 'temp identity changed'):
                state.publish(self.path, self.value)
        self.assertEqual(self.path.read_bytes(), b'old')
        self.assertEqual([p.read_bytes() for p in self.path.parent.glob('*.tmp')], [b'foreign'])

    def test_cleanup_failure_keeps_original_sync_exception(self):
        failure = OSError('file sync failed')
        with patch.object(state.os, 'fsync', side_effect=failure), patch.object(Path, 'unlink', side_effect=OSError('cleanup denied')):
            with self.assertRaises(OSError) as caught:
                state.publish(self.path, self.value)
        self.assertIs(caught.exception, failure)
        self.assertTrue(any('cleanup denied' in note for note in failure.__notes__))
        self.assertEqual(self.path.read_bytes(), b'old')
        self.assertEqual(len(list(self.path.parent.glob('*.tmp'))), 1)

    def test_invalid_or_oversized_values_create_no_files(self):
        cyclic = {}; cyclic['self'] = cyclic
        for value in ([], {'v': float('nan')}, {'v': float('inf')}, {'v': object()}, cyclic, {'v': 'x' * 2048}):
            with self.subTest(kind=type(value)), patch.object(state, 'MAX_BYTES', 1024):
                with self.assertRaises(ValueError):
                    state.publish(self.path, value)
            self.assertEqual(self.path.read_bytes(), b'old')
            self.assertEqual(list(self.path.parent.glob('*.tmp')), [])

    def test_file_sync_only_platform_reports_no_directory_sync(self):
        with patch.object(state, 'DIRECTORY_SYNC_SUPPORTED', False), patch.object(state.os, 'open') as opened:
            self.assertFalse(state.sync_parent_directory(self.path.parent))
            report = state.publish(self.path, self.value)
        opened.assert_not_called()
        self.assertEqual(report, {'content_synced': True, 'directory_synced': False})

    @unittest.skipUnless(os.name != 'nt', 'POSIX directory descriptor contract')
    def test_parent_sync_failure_closes_directory_descriptor(self):
        original_close = os.close
        with patch.object(state.os, 'fsync', side_effect=OSError('parent failed')), patch.object(state.os, 'close', wraps=original_close) as close:
            with self.assertRaisesRegex(OSError, 'parent failed'):
                state.sync_parent_directory(self.path.parent)
        close.assert_called_once()
        with self.assertRaises(OSError):
            os.fstat(close.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
