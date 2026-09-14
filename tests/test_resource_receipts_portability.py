"""Cross-platform capture and explicit-null regressions for the receipt reader."""
from pathlib import Path
import os
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'app'), str(Path(__file__).resolve().parents[1])]
import resource_receipts as receipts
import test_resource_receipts as fixture


class ReceiptPortabilityTests(unittest.TestCase):
    def test_path_and_descriptor_ctime_domains_may_differ(self):
        # Native Windows 3.12.10: lstat ctime was birth time while fstat ctime
        # was change time. All identity, size, mtime and birthtime fields agreed.
        real_fstat = os.fstat
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'capture'; path.write_bytes(b'original')
            def descriptor_stat(fd):
                info = real_fstat(fd)
                data = {name: getattr(info, name) for name in dir(info) if name.startswith('st_')}
                data['st_ctime_ns'] += 100
                return SimpleNamespace(**data)
            with patch.object(receipts.os, 'fstat', side_effect=descriptor_stat):
                self.assertEqual(receipts.read_evidence_file(path, 100), b'original')

    def test_descriptor_changes_during_capture_are_still_rejected(self):
        real_fstat = os.fstat
        for field in ('st_ctime_ns', 'st_mtime_ns', 'st_ino', 'st_size'):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'capture'; path.write_bytes(b'original'); calls = []
                def descriptor_stat(fd):
                    info = real_fstat(fd); calls.append(fd)
                    data = {name: getattr(info, name) for name in dir(info) if name.startswith('st_')}
                    if len(calls) == 2: data[field] += 1
                    return SimpleNamespace(**data)
                with patch.object(receipts.os, 'fstat', side_effect=descriptor_stat):
                    with self.assertRaises(receipts.EvidenceError) as caught:
                        receipts.read_evidence_file(path, 100)
                self.assertEqual(caught.exception.code, 'file_changed')

    def test_cross_handle_identity_size_and_mtime_cannot_disagree(self):
        real_fstat = os.fstat
        for field in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns'):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'capture'; path.write_bytes(b'original')
                def descriptor_stat(fd):
                    info = real_fstat(fd)
                    data = {name: getattr(info, name) for name in dir(info) if name.startswith('st_')}
                    data[field] += 1
                    return SimpleNamespace(**data)
                with patch.object(receipts.os, 'fstat', side_effect=descriptor_stat):
                    with self.assertRaises(receipts.EvidenceError) as caught:
                        receipts.read_evidence_file(path, 100)
                self.assertEqual(caught.exception.code, 'file_changed')

    def test_source_nullable_fields_must_be_present(self):
        for name in ('commit_at_capture', 'tracked_changes'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                directory = fixture.make_observation(Path(tmp))
                context = fixture.read(directory / 'context.json'); del context['source'][name]
                fixture.write(directory / 'context.json', context); fixture.rehash(directory)
                with self.assertRaises(receipts.EvidenceError) as caught:
                    receipts.inspect_observation(directory)
                self.assertEqual(caught.exception.code, 'context_invalid')

    def test_explicit_null_source_observations_remain_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = fixture.make_observation(Path(tmp))
            context = fixture.read(directory / 'context.json')
            context['source'].update(commit_at_capture=None, tracked_changes=None)
            fixture.write(directory / 'context.json', context); fixture.rehash(directory)
            report = receipts.inspect_observation(directory)
            self.assertEqual(report['integrity'], 'verified')
            self.assertIsNone(report['source_observation']['commit_at_capture'])
            self.assertIsNone(report['source_observation']['tracked_changes'])


if __name__ == '__main__': unittest.main()
