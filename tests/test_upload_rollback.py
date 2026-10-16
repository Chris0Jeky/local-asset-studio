"""Synthetic upload failures preserve only unrelated or subsequently edited files."""
import hashlib
import io
import json
import os
from pathlib import Path
import types
import unittest
from unittest.mock import patch

import test_server as fixtures

server = fixtures.server


class UploadRollbackTests(unittest.TestCase):
    def setUp(self):
        fixtures.ServerTests.setUp(self)
        self.studio = server.Studio(self.root)
        self.uploads = self.studio.experiments / 'uploads'
        self.input = self.studio.comfy_root / 'input'
        self.payload = fixtures.png()

    def tearDown(self):
        fixtures.ServerTests.tearDown(self)

    def inventory(self):
        return {str(path): path.read_bytes() for root in (self.uploads, self.input)
                if root.exists() for path in root.iterdir() if path.is_file()}

    def fail_metadata(self, change=None):
        original_link = os.link
        def fault(*args, **kwargs):
            if change: change()
            raise OSError('sidecar volume full')
        def link(source, target, *args, **kwargs):
            if Path(target).suffix == '.json': return fault()
            return original_link(source, target, *args, **kwargs)
        return (patch.object(self.studio, '_write_json_atomic', side_effect=fault),
                patch.object(os, 'link', side_effect=link))

    def test_partial_copy_failure_and_retries_leave_no_orphans(self):
        # Exercise the old direct copy and the new staged raw-write fault seams.
        original_write = os.write
        staged_inputs = set()
        original_mkstemp = __import__('tempfile').mkstemp
        partial = set()
        def mkstemp(*args, **kwargs):
            descriptor, name = original_mkstemp(*args, **kwargs)
            if Path(name).parent == self.input: staged_inputs.add(descriptor)
            return descriptor, name
        def write(descriptor, data):
            if descriptor in staged_inputs:
                if descriptor in partial: raise OSError('copy volume full')
                partial.add(descriptor)
                return original_write(descriptor, data[:17])
            return original_write(descriptor, data)
        def copy(source, target):
            Path(target).write_bytes(Path(source).read_bytes()[:17])
            raise OSError('copy volume full')
        for _ in range(3):
            staged_inputs.clear(); partial.clear()
            with patch.object(server.shutil, 'copyfile', side_effect=copy), \
                    patch('tempfile.mkstemp', side_effect=mkstemp), patch.object(os, 'write', side_effect=write):
                with self.assertRaises((OSError, server.StudioError)):
                    self.studio.upload('frame.png', 'image/png', self.payload)
            self.assertEqual(self.inventory(), {})
            self.assertEqual(self.studio.jobs, {})

    def test_metadata_failure_rolls_back_exact_request_paths(self):
        first, second = self.fail_metadata()
        with first, second:
            with self.assertRaises((OSError, server.StudioError)):
                self.studio.upload('frame.png', 'image/png', self.payload)
        self.assertEqual(self.inventory(), {})
        self.assertEqual(self.studio.jobs, {})

    def test_generated_name_collision_never_overwrites_any_destination(self):
        fixed = types.SimpleNamespace(hex='a' * 32)
        name = fixed.hex + '_frame.png.png'
        self.uploads.mkdir(parents=True, exist_ok=True)
        for target in (self.uploads / name, self.input / name, self.uploads / (name + '.json')):
            with self.subTest(target=target):
                target.write_bytes(b'prior human bytes')
                before = self.inventory()
                with patch.object(server.uuid, 'uuid4', return_value=fixed):
                    with self.assertRaises((OSError, server.StudioError)):
                        self.studio.upload('frame.png', 'image/png', self.payload)
                self.assertEqual(self.inventory(), before)
                target.unlink()

    def test_rollback_preserves_later_replacement_and_same_inode_edit(self):
        for replace in (False, True):
            with self.subTest(replace=replace):
                changed = []
                def change():
                    target = next(path for path in self.uploads.glob('*.png'))
                    if replace:
                        replacement = self.root / 'later.png'
                        replacement.write_bytes(b'later human bytes')
                        os.replace(replacement, target)
                    else: target.write_bytes(b'later human bytes')
                    changed.append(target)
                first, second = self.fail_metadata(change)
                with first, second:
                    with self.assertRaises((OSError, server.StudioError)) as caught:
                        self.studio.upload('frame.png', 'image/png', self.payload)
                self.assertEqual(changed[0].read_bytes(), b'later human bytes')
                self.assertEqual(self.inventory(), {str(changed[0]): b'later human bytes'})
                self.assertIn(str(changed[0]), str(caught.exception))
                changed[0].unlink()

    def test_other_successful_upload_survives_failed_request(self):
        original_link = os.link
        original_metadata = self.studio._write_json_atomic
        completed = []
        def another():
            completed.append(self.studio.upload('other.png', 'image/png', self.payload))
            raise OSError('sidecar failed')
        def metadata(path, value):
            if value['original_name'] == 'fail.png': return another()
            return original_metadata(path, value)
        def link(source, target, *args, **kwargs):
            if str(target).endswith('_fail.png.png.json'): return another()
            return original_link(source, target, *args, **kwargs)
        with patch.object(self.studio, '_write_json_atomic', side_effect=metadata), \
                patch.object(os, 'link', side_effect=link):
            with self.assertRaises((OSError, server.StudioError)):
                self.studio.upload('fail.png', 'image/png', self.payload)
        expected = completed[0]
        self.assertEqual(set(self.inventory()), {str(self.uploads / expected['file']),
                                               str(self.input / expected['file']),
                                               str(self.uploads / (expected['file'] + '.json'))})
        self.assertEqual((self.input / expected['file']).read_bytes(), self.payload)

    def test_cleanup_refusal_reports_retained_exact_path(self):
        original_unlink = Path.unlink
        refused = []
        def unlink(path, *args, **kwargs):
            if path.parent == self.uploads and path.suffix == '.png':
                refused.append(path); raise PermissionError('held open')
            return original_unlink(path, *args, **kwargs)
        first, second = self.fail_metadata()
        with first, second, patch.object(Path, 'unlink', unlink):
            with self.assertRaises((OSError, server.StudioError)) as caught:
                self.studio.upload('frame.png', 'image/png', self.payload)
        self.assertEqual(len(refused), 1)
        self.assertEqual(refused[0].read_bytes(), self.payload)
        self.assertIn(str(refused[0]), str(caught.exception))
        self.assertEqual(set(self.inventory()), {str(refused[0])})

    def test_success_receipt_matches_both_files_and_sidecar(self):
        result = self.studio.upload('frame.png', 'image/png', self.payload)
        self.assertEqual(result['sha256'], hashlib.sha256(self.payload).hexdigest())
        self.assertEqual(result['bytes'], len(self.payload))
        self.assertEqual((result['width'], result['height']), (8, 12))
        self.assertEqual((self.uploads / result['file']).read_bytes(), self.payload)
        self.assertEqual((self.input / result['file']).read_bytes(), self.payload)
        self.assertEqual(json.loads((self.uploads / (result['file'] + '.json')).read_text()), result)
        self.assertEqual(len(self.inventory()), 3)

    def test_link_that_publishes_then_raises_is_rolled_back(self):
        original_link = os.link
        def link(source, target, *args, **kwargs):
            original_link(source, target, *args, **kwargs)
            if Path(target).suffix == '.json': raise OSError('reply lost after link')
        first, _ = self.fail_metadata()
        with first, patch.object(os, 'link', side_effect=link):
            with self.assertRaises((OSError, server.StudioError)):
                self.studio.upload('frame.png', 'image/png', self.payload)
        self.assertEqual(self.inventory(), {})

    def test_changed_private_stage_is_retained_and_not_published(self):
        original_mkstemp = __import__('tempfile').mkstemp
        stages = []
        def mkstemp(*args, **kwargs):
            result = original_mkstemp(*args, **kwargs)
            if stages: stages[0].write_bytes(b'later private edit')
            stages.append(Path(result[1]))
            return result
        # The old copy fault establishes the old lack of selective rollback.
        def copy(source, target):
            Path(source).write_bytes(b'later private edit')
            raise OSError('stage changed')
        with patch('tempfile.mkstemp', side_effect=mkstemp), \
                patch.object(server.shutil, 'copyfile', side_effect=copy):
            with self.assertRaises((OSError, server.StudioError)) as caught:
                self.studio.upload('frame.png', 'image/png', self.payload)
        self.assertEqual(len(self.inventory()), 1)
        retained = next(iter(self.inventory()))
        self.assertEqual(self.inventory()[retained], b'later private edit')
        self.assertIn(retained, str(caught.exception))
        self.assertFalse(list(self.input.glob('*.png')))
        self.assertFalse(list(self.uploads.glob('*.json')))

    def test_zero_progress_write_is_refused_without_files(self):
        def copy(*args): raise OSError('zero write')
        with patch.object(os, 'write', return_value=0), \
                patch.object(server.shutil, 'copyfile', side_effect=copy):
            with self.assertRaises((OSError, server.StudioError)):
                self.studio.upload('frame.png', 'image/png', self.payload)
        self.assertEqual(self.inventory(), {})

    def test_http_storage_failure_exposes_exact_retained_paths(self):
        def change():
            next(self.uploads.glob('*.png')).write_bytes(b'later human bytes')
        first, second = self.fail_metadata(change)
        handler = server.Handler.__new__(server.Handler)
        handler.studio = self.studio; handler.path = '/api/upload'
        handler.headers = {'X-Filename': 'frame.png', 'Content-Type': 'image/png'}
        handler.rfile = io.BytesIO(self.payload)
        handler._safe_mutation = lambda: True
        handler._content_length = lambda limit: len(self.payload)
        handler._drain_refused_body = lambda: None
        seen = {}
        handler._json = lambda status, body: seen.update(status=status, body=body)
        with first, second: handler.do_POST()
        self.assertEqual(seen['status'], 503)
        self.assertEqual(seen['body']['code'], 'upload_storage_unconfirmed')
        self.assertEqual(seen['body']['retained_paths'], list(self.inventory()))
        self.assertEqual(len(seen['body']['retained_paths']), 1)
        self.assertEqual(self.studio.jobs, {})
