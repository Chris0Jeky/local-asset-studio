"""Native temporary-file and synchronization contracts for the recovery owner."""
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
import recovery_state as state


class RecoveryStateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'runtime-recovery.json'
        self.path.write_bytes(b'previous record')
        self.value = {'status': 'launching', 'attempts': 1, 'message': 'Selected profile é', 'launch_pending': True}

    def test_write_flush_content_sync_replace_parent_precede_completion(self):
        events = []
        original_open, original_sync, original_replace = Path.open, os.fsync, Path.replace
        @contextmanager
        def open_file(path, *args, **kwargs):
            with original_open(path, *args, **kwargs) as stream:
                if not args or args[0] != 'xb': yield stream; return
                proxy = Mock(wraps=stream)
                def write(raw):
                    self.assertEqual(self.path.read_bytes(), b'previous record')
                    events.append('write'); return stream.write(raw)
                def flush(): events.append('flush'); return stream.flush()
                proxy.write.side_effect = write; proxy.flush.side_effect = flush
                yield proxy
        def sync(descriptor):
            self.assertEqual(events, ['write', 'flush'])
            self.assertTrue(stat.S_ISREG(os.fstat(descriptor).st_mode))
            events.append('file'); return original_sync(descriptor)
        def replace(path, target):
            self.assertEqual(events, ['write', 'flush', 'file'])
            self.assertEqual(json.loads(path.read_bytes()), self.value)
            events.append('replace'); return original_replace(path, target)
        def parent(directory):
            self.assertEqual(events, ['write', 'flush', 'file', 'replace'])
            self.assertEqual(json.loads(self.path.read_bytes()), self.value)
            self.assertEqual(directory, self.path.parent)
            events.append('parent'); return True
        with patch.object(Path, 'open', open_file), patch.object(state.os, 'fsync', side_effect=sync), \
             patch.object(Path, 'replace', replace), patch.object(state, 'sync_parent_directory', side_effect=parent):
            result = state.publish(self.path, self.value)
        self.assertEqual(events, ['write', 'flush', 'file', 'replace', 'parent'])
        self.assertEqual(result, {'content_synced': True, 'directory_synced': True})
        self.assertEqual(list(self.path.parent.glob('*.tmp')), [])

    def test_content_faults_preserve_prior_target_and_clean_only_owned_temp(self):
        original_open, original_sync = Path.open, os.fsync
        root = self.path.parent
        for phase in ('write', 'short-write', 'flush', 'file-sync', 'replace'):
            with self.subTest(phase=phase):
                self.path = root / phase / 'runtime-recovery.json'
                self.path.parent.mkdir()
                self.path.write_bytes(b'previous record')
                @contextmanager
                def open_file(path, *args, **kwargs):
                    with original_open(path, *args, **kwargs) as stream:
                        if not args or args[0] != 'xb': yield stream; return
                        proxy = Mock(wraps=stream)
                        if phase == 'write': proxy.write.side_effect = OSError('write fault')
                        if phase == 'short-write': proxy.write.side_effect = lambda raw: stream.write(raw[:3])
                        if phase == 'flush': proxy.flush.side_effect = OSError('flush fault')
                        yield proxy
                def sync(descriptor):
                    if phase == 'file-sync': raise OSError('file-sync fault')
                    return original_sync(descriptor)
                original_replace = Path.replace
                def replace(path, target):
                    if phase == 'replace': raise OSError('replace fault')
                    return original_replace(path, target)
                with patch.object(Path, 'open', open_file), patch.object(state.os, 'fsync', side_effect=sync), \
                     patch.object(Path, 'replace', replace):
                    with self.assertRaises(OSError): state.publish(self.path, self.value)
                self.assertEqual(self.path.read_bytes(), b'previous record')
                self.assertEqual(list(self.path.parent.glob('*.tmp')), [])

    def test_exclusive_collision_keeps_foreign_bytes(self):
        temp = self.path.with_name(self.path.name + '.collision.tmp')
        temp.write_bytes(b'foreign')
        with patch.object(state.uuid, 'uuid4', return_value=SimpleNamespace(hex='collision')):
            with self.assertRaises(FileExistsError): state.publish(self.path, self.value)
        self.assertEqual(temp.read_bytes(), b'foreign')
        self.assertEqual(self.path.read_bytes(), b'previous record')

    def test_temp_substitution_is_preserved_when_replacement_raises(self):
        def replace(path, target):
            path.rename(path.with_suffix('.held'))
            path.write_bytes(b'foreign')
            raise OSError('temporary entry changed')
        with patch.object(Path, 'replace', replace):
            with self.assertRaisesRegex(OSError, 'temporary entry changed'): state.publish(self.path, self.value)
        self.assertEqual(self.path.read_bytes(), b'previous record')
        self.assertEqual([path.read_bytes() for path in self.path.parent.glob('*.tmp')], [b'foreign'])

    def test_post_replace_error_keeps_visible_target_without_acknowledgment(self):
        original = Path.replace
        def replace(path, target): original(path, target); raise OSError('post-replace fault')
        with patch.object(Path, 'replace', replace), patch.object(state, 'sync_parent_directory') as parent:
            with self.assertRaisesRegex(OSError, 'post-replace fault'): state.publish(self.path, self.value)
        self.assertEqual(json.loads(self.path.read_bytes()), self.value)
        self.assertEqual(list(self.path.parent.glob('*.tmp')), [])
        parent.assert_not_called()

    def test_parent_failure_does_not_remove_a_new_occupant_of_consumed_temp_name(self):
        original = Path.replace
        def replace(path, target): original(path, target); path.write_bytes(b'new occupant')
        with patch.object(Path, 'replace', replace), patch.object(state, 'sync_parent_directory', side_effect=OSError('parent fault')):
            with self.assertRaisesRegex(OSError, 'parent fault'): state.publish(self.path, self.value)
        self.assertEqual(json.loads(self.path.read_bytes()), self.value)
        self.assertEqual([path.read_bytes() for path in self.path.parent.glob('*.tmp')], [b'new occupant'])

    def test_cleanup_failure_preserves_primary_content_fault_and_evidence(self):
        failure = OSError('content fault')
        with patch.object(state.os, 'fsync', side_effect=failure), patch.object(Path, 'unlink', side_effect=OSError('cleanup fault')):
            with self.assertRaises(OSError) as caught: state.publish(self.path, self.value)
        self.assertIs(caught.exception, failure)
        self.assertTrue(any('cleanup fault' in note for note in getattr(failure, '__notes__', [])))
        self.assertEqual(self.path.read_bytes(), b'previous record')
        self.assertEqual(len(list(self.path.parent.glob('*.tmp'))), 1)

    def test_temp_close_failure_preserves_the_original_write_fault(self):
        original = Path.open
        failure = OSError('original write fault')
        @contextmanager
        def open_file(path, *args, **kwargs):
            with original(path, *args, **kwargs) as stream:
                if not args or args[0] != 'xb': yield stream; return
                proxy = Mock(wraps=stream); proxy.write.side_effect = failure
                try: yield proxy
                finally: raise OSError('temporary close fault')
        with patch.object(Path, 'open', open_file):
            with self.assertRaises(OSError) as caught: state.publish(self.path, self.value)
        self.assertIs(caught.exception, failure)
        self.assertTrue(any('temporary close fault' in note for note in getattr(failure, '__notes__', [])))
        self.assertEqual(self.path.read_bytes(), b'previous record')
        self.assertEqual(list(self.path.parent.glob('*.tmp')), [])

    def test_invalid_or_oversized_serialization_creates_nothing(self):
        cyclic = {}; cyclic['self'] = cyclic
        values = [[], {'v': float('nan')}, {'v': float('inf')}, {'v': object()}, cyclic, {'v': 'x' * 2048}]
        for value in values:
            with self.subTest(value=repr(value)[:80]), patch.object(state, 'MAX_BYTES', 1024):
                with self.assertRaises(ValueError): state.publish(self.path, value)
                self.assertEqual(self.path.read_bytes(), b'previous record')
                self.assertEqual(list(self.path.parent.glob('*.tmp')), [])

    def test_windows_contract_reports_no_directory_barrier(self):
        with patch.object(state, 'DIRECTORY_SYNC_SUPPORTED', False), patch.object(state.os, 'open') as opened:
            result = state.publish(self.path, self.value)
        opened.assert_not_called()
        self.assertEqual(result, {'content_synced': True, 'directory_synced': False})

    @unittest.skipIf(os.name == 'nt', 'Native POSIX parent barrier')
    def test_parent_open_failure_propagates_after_visible_replacement(self):
        with patch.object(state.os, 'open', side_effect=OSError('parent open fault')):
            with self.assertRaisesRegex(OSError, 'parent open fault'): state.publish(self.path, self.value)
        self.assertEqual(json.loads(self.path.read_bytes()), self.value)
        self.assertEqual(list(self.path.parent.glob('*.tmp')), [])

    @unittest.skipIf(os.name == 'nt', 'Native POSIX parent barrier')
    def test_parent_sync_failure_closes_its_descriptor(self):
        original = os.close
        with patch.object(state.os, 'fsync', side_effect=OSError('parent sync fault')), patch.object(state.os, 'close', wraps=original) as close:
            with self.assertRaisesRegex(OSError, 'parent sync fault'): state.sync_parent_directory(self.path.parent)
        close.assert_called_once()
        with self.assertRaises(OSError): os.fstat(close.call_args.args[0])

    @unittest.skipIf(os.name == 'nt', 'Native POSIX parent barrier')
    def test_directory_close_fault_preserves_primary_sync_failure(self):
        failure = OSError('parent sync fault')
        original = os.close
        def close(descriptor): original(descriptor); raise OSError('directory close fault')
        with patch.object(state.os, 'fsync', side_effect=failure), patch.object(state.os, 'close', side_effect=close):
            with self.assertRaises(OSError) as caught: state.sync_parent_directory(self.path.parent)
        self.assertIs(caught.exception, failure)
        self.assertTrue(any('directory close fault' in note for note in getattr(failure, '__notes__', [])))


if __name__ == '__main__': unittest.main()
