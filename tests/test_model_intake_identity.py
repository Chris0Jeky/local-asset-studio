"""Cross-platform source identity contracts, including observed Windows ctime divergence."""
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'app'))
import model_intake as intake


class IntakeIdentityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve(); self.comfy = self.root/'comfy'
        self.source = self.root/'source.safetensors'; self.body = bytes(173); self.source.write_bytes(self.body)
        self.expected = intake.source_snapshot(self.source)
        self.target = self.comfy/'models/loras/demo.safetensors'
        reserve = patch.object(intake, 'RESERVE_BYTES', 0); reserve.start(); self.addCleanup(reserve.stop)

    def run_intake(self, identity=None):
        return intake.import_candidate(self.root, self.comfy, self.source, 'loras', 'demo.safetensors',
                                       identity or self.expected, 'operator-selected')

    def assert_source(self):self.assertEqual(self.source.read_bytes(), self.body)

    def test_source_snapshot_uses_descriptor_timestamps_not_path_ctime(self):
        # This pins the Windows 3.12 stat/fstat ctime divergence on every platform.
        value = os.stat(self.source)
        descriptor = SimpleNamespace(st_mode=value.st_mode, st_dev=value.st_dev, st_ino=value.st_ino,
                                     st_size=value.st_size, st_mtime_ns=value.st_mtime_ns,
                                     st_ctime_ns=value.st_ctime_ns+10000000)
        with patch.object(intake.os, 'fstat', return_value=descriptor):
            snapshot = intake.source_snapshot(self.source)
            with self.source.open('rb') as stream:self.assertEqual(snapshot, intake._handle_identity(stream))
        self.assertEqual(snapshot['ctime_ns'], descriptor.st_ctime_ns)
        self.assertNotEqual(snapshot['ctime_ns'], value.st_ctime_ns)

    def test_real_descriptor_snapshot_matches_after_delayed_file_write(self):
        # Creation and last-write time must not coincide by fixture timing accident.
        time.sleep(.01); self.source.write_bytes(self.body)
        snapshot = intake.source_snapshot(self.source)
        with self.source.open('rb') as stream:self.assertEqual(snapshot, intake._handle_identity(stream))
        record = self.run_intake(identity=snapshot)
        self.assertEqual(record['source_identity_api'], 'os.fstat'); self.assert_source()

    def test_same_size_restored_mtime_during_copy_is_not_silently_accepted(self):
        copy = intake._copy
        def mutate(*args):
            digest = copy(*args); time.sleep(.01)
            self.source.write_bytes(b'x'*len(self.body))
            os.utime(self.source, ns=(self.expected['mtime_ns'], self.expected['mtime_ns']))
            if intake.source_snapshot(self.source) == self.expected:
                self.skipTest('filesystem did not expose metadata change')
            return digest
        with patch.object(intake, '_copy', side_effect=mutate):
            with self.assertRaisesRegex(ValueError, 'changed'):self.run_intake()
        self.assertFalse(self.target.exists()); self.assertTrue(self.source.exists())


if __name__ == '__main__':unittest.main()
