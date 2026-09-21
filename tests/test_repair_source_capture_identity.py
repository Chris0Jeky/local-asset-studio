"""Causal filesystem capture races, without neural/runtime or private inputs."""
import os
import subprocess
import sys
from types import SimpleNamespace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import repair_source as source


class CaptureIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'source.bin'
        self.path.write_bytes(b'abcdefgh')

    def test_exact_limit_and_empty_file_remain_valid(self):
        self.assertEqual(source.read_bounded(self.path, 8), b'abcdefgh')
        self.path.write_bytes(b'')
        self.assertEqual(source.read_bounded(self.path, 0), b'')

    def test_oversized_file_is_refused_before_open_or_allocation(self):
        with patch.object(Path, 'open', side_effect=AssertionError('must not open oversized input')), \
             patch.object(os, 'open', side_effect=AssertionError('must not open oversized input')):
            with self.assertRaisesRegex(ValueError, 'byte limit'):
                source.read_bounded(self.path, 7)

    def test_replacement_between_stat_and_open_is_refused(self):
        stat_path = Path.stat
        replaced = []
        other = self.root / 'replacement.bin'
        other.write_bytes(b'ABCDEFGH')
        def swapping_stat(path, *args, **kwargs):
            info = stat_path(path, *args, **kwargs)
            if path == self.path and not replaced:
                replaced.append(True)
                os.replace(other, path)
            return info
        with patch.object(Path, 'stat', swapping_stat):
            with self.assertRaisesRegex(ValueError, 'changed'):
                source.read_bounded(self.path, 8)
        self.assertTrue(replaced)
        self.assertEqual(self.path.read_bytes(), b'ABCDEFGH')

    def test_in_place_rewrite_during_read_cannot_return_mixed_bytes(self):
        self.mutating_read('rewrite')

    def test_growth_and_truncation_during_read_are_refused(self):
        for action in ('grow', 'truncate'):
            with self.subTest(action=action):
                self.path.write_bytes(b'abcdefgh')
                self.mutating_read(action)

    def mutating_read(self, action):
        path_open, fdopen = Path.open, os.fdopen
        calls = []
        target = self.path
        class Reader:
            def __init__(self, stream): self.stream = stream
            def __enter__(self): return self
            def __exit__(self, *args): self.stream.close()
            def fileno(self): return self.stream.fileno()
            def read(self, maximum):
                calls.append(maximum)
                first = self.stream.read(4)
                # Drop buffered remainder, then change the same inode. Explicit
                # mtime change removes filesystem clock-resolution dependence.
                self.stream.seek(4)
                with path_open(target, 'r+b', buffering=0) as writer:
                    writer.seek(4)
                    writer.write(b'WXYZ' if action == 'rewrite' else b'WXYZ-more')
                    if action == 'truncate': writer.truncate(5)
                info = target.stat()
                os.utime(target, ns=(info.st_atime_ns, info.st_mtime_ns + 2_000_000_000))
                return first + self.stream.read(max(0, maximum - 4))
        def opened(path, *args, **kwargs): return Reader(path_open(path, *args, **kwargs))
        def descriptor(fd, *args, **kwargs): return Reader(fdopen(fd, *args, **kwargs))
        with patch.object(Path, 'open', opened), patch.object(os, 'fdopen', descriptor):
            with self.assertRaisesRegex(ValueError, 'changed|byte limit'):
                source.read_bounded(target, 32)
        self.assertEqual(len(calls), 1)

    def test_symlink_policy_remains_explicit(self):
        link = self.root / 'link.bin'
        try: link.symlink_to(self.path)
        except OSError: self.skipTest('Symlink creation unavailable')
        self.assertEqual(source.read_bounded(link, 8), b'abcdefgh')
        with self.assertRaisesRegex(ValueError, 'symlink|plain'):
            source.read_bounded(link, 8, reject_symlink=True)

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'POSIX FIFO fixture')
    def test_nonregular_inputs_refuse_without_open(self):
        fifo = self.root / 'source.pipe'
        os.mkfifo(fifo)
        with patch.object(os, 'open', side_effect=AssertionError('must not open known FIFO')):
            with self.assertRaisesRegex(ValueError, 'regular'):
                source.read_bounded(fifo, 32)

    def test_invalid_limits_refuse_before_filesystem_access(self):
        for limit in (True, -1, 1.5, None):
            with self.subTest(limit=limit), patch.object(Path, 'stat', side_effect=AssertionError('invalid limit must not inspect')):
                with self.assertRaisesRegex(ValueError, 'limit'):
                    source.read_bounded(self.path, limit)

    @staticmethod
    def stat_view(info, **changes):
        fields = {name: getattr(info, name) for name in
                  ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_mode')}
        fields['st_file_attributes'] = getattr(info, 'st_file_attributes', 0)
        return SimpleNamespace(**(fields | changes))

    def test_path_and_descriptor_change_times_need_not_match(self):
        original = Path.stat
        def path_stat(path, *args, **kwargs):
            info = original(path, *args, **kwargs)
            return self.stat_view(info, st_ctime_ns=info.st_ctime_ns + 100)
        with patch.object(Path, 'stat', path_stat):
            self.assertEqual(source.read_bounded(self.path, 8), b'abcdefgh')

    def test_descriptor_change_time_alone_invalidates_capture(self):
        original = os.fstat
        calls = []
        def descriptor_stat(fd):
            info = original(fd)
            calls.append(fd)
            return self.stat_view(info, st_ctime_ns=info.st_ctime_ns + (1 if len(calls) > 1 else 0))
        with patch.object(os, 'fstat', descriptor_stat):
            with self.assertRaisesRegex(ValueError, 'changed'):
                source.read_bounded(self.path, 8)
        self.assertEqual(len(calls), 2)

    def test_reparse_point_marker_is_refused_before_open(self):
        info = self.path.stat()
        with patch.object(Path, 'stat', return_value=self.stat_view(info, st_file_attributes=0x400)), \
             patch.object(os, 'open', side_effect=AssertionError('must not open reparse point')):
            with self.assertRaisesRegex(ValueError, 'reparse'):
                source.read_bounded(self.path, 8, reject_symlink=True)

    def test_descriptor_is_closed_when_inspection_or_stream_creation_fails(self):
        real_open = os.open
        for boundary in ('fstat', 'fdopen'):
            opened = []
            def recording_open(*args, **kwargs):
                fd = real_open(*args, **kwargs)
                opened.append(fd)
                return fd
            with self.subTest(boundary=boundary):
                with patch.object(os, 'open', recording_open), \
                     patch.object(os, boundary, side_effect=OSError('injected failure')):
                    with self.assertRaisesRegex(OSError, 'injected failure'):
                        source.read_bounded(self.path, 8)
                self.assertEqual(len(opened), 1)
                with self.assertRaises(OSError): os.fstat(opened[0])

    @unittest.skipUnless(hasattr(os, 'mkfifo') and hasattr(os, 'O_NONBLOCK'), 'POSIX FIFO fixture')
    def test_regular_file_swapped_for_fifo_cannot_block_open(self):
        # A bounded child keeps a regression to blocking open from hanging the
        # suite. There is no writer on the FIFO, so successful blocking open is
        # impossible; the only valid result is the explicit changed-file refusal.
        code = """
import os
import sys
from pathlib import Path
from unittest.mock import patch
from scripts import repair_source
path = Path(sys.argv[1])
original = Path.stat
changed = False
def swapping_stat(value, *args, **kwargs):
    global changed
    info = original(value, *args, **kwargs)
    if value == path and not changed:
        changed = True
        path.unlink()
        os.mkfifo(path)
    return info
with patch.object(Path, 'stat', swapping_stat):
    try:
        repair_source.read_bounded(path, 8)
    except ValueError as exc:
        assert 'changed' in str(exc), str(exc)
        print('FIFO swap refused')
    else:
        raise AssertionError('FIFO was accepted')
"""
        result = subprocess.run([sys.executable, '-c', code, str(self.path)],
                                cwd=Path(__file__).resolve().parents[1],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('FIFO swap refused', result.stdout)

    def test_capture_failure_never_creates_a_packet(self):
        from test_repair_source import png
        self.path.write_bytes(png())
        before = Path.stat
        changed = []
        def growing_stat(path, *args, **kwargs):
            info = before(path, *args, **kwargs)
            if path == self.path and not changed:
                changed.append(True)
                with path.open('ab') as stream: stream.write(b'x')
            return info
        output = self.root / 'packet'
        with patch.object(Path, 'stat', growing_stat):
            with self.assertRaisesRegex(ValueError, 'changed'):
                source.capture(self.path, output)
        self.assertFalse(output.exists())


if __name__ == '__main__': unittest.main()
