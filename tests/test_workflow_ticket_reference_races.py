"""Deterministic disk changes exercise ticket reference pins before dispatch."""
import copy
import hashlib
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from studio_workflow import execution
from test_workflow_preset_adapter import GRAPH, Runtime


class TicketReferenceRaceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.runtime = Runtime(temp.name)
        graph = copy.deepcopy(GRAPH)
        graph['9'] = {'class_type': 'LoadImage', 'inputs': {'image': 'ref.png'}}
        self.runtime.path.write_text(json.dumps(graph), encoding='utf-8')
        folder = self.runtime.comfy_root / 'input'
        folder.mkdir(parents=True)
        self.reference = folder / 'ref.png'
        self.reference.write_bytes(b'abcd')
        self.recipe = {'preset_id': 'example', 'controls': {},
                       'expected_template_sha256': hashlib.sha256(self.runtime.path.read_bytes()).hexdigest()}

    def change(self, kind):
        before = self.reference.stat()
        if kind == 'size':
            self.reference.write_bytes(b'abcde')
            os.utime(self.reference, ns=(before.st_atime_ns, before.st_mtime_ns))
        else:
            self.reference.write_bytes(b'wxyz')
            os.utime(self.reference, ns=(before.st_atime_ns, before.st_mtime_ns + 2_000_000_000))
        after = self.reference.stat()
        self.assertEqual(after.st_mtime_ns == before.st_mtime_ns, kind == 'size')
        self.assertEqual(after.st_size == before.st_size, kind != 'size')

    def assert_no_dispatch(self):
        self.assertEqual(self.runtime.calls, 0)
        self.assertEqual(self.runtime.jobs, {})
        self.assertEqual(list((self.runtime.runs / 'workflow-requests').glob('*.json')), [])

    def test_size_change_during_hashing_is_refused_even_with_original_mtime(self):
        original = execution.hashlib.file_digest
        def digest(stream, algorithm):
            result = original(stream, algorithm)
            self.change('size')
            return result
        with patch.object(execution.hashlib, 'file_digest', side_effect=digest):
            with self.assertRaisesRegex(ValueError, 'Reference changed during preparation'):
                execution._pins(self.runtime, self.recipe)
        self.assert_no_dispatch()

    def test_same_size_mtime_change_during_hashing_is_refused(self):
        original = execution.hashlib.file_digest
        def digest(stream, algorithm):
            result = original(stream, algorithm)
            self.change('mtime')
            return result
        with patch.object(execution.hashlib, 'file_digest', side_effect=digest):
            with self.assertRaisesRegex(ValueError, 'Reference changed during preparation'):
                execution._pins(self.runtime, self.recipe)
        self.assert_no_dispatch()

    def test_changed_content_with_restored_size_and_mtime_invalidates_prepared_ticket(self):
        ticket = execution.prepare_ticket(self.runtime, self.recipe)
        before = self.reference.stat()
        self.reference.write_bytes(b'wxyz')
        os.utime(self.reference, ns=(before.st_atime_ns, before.st_mtime_ns))
        after = self.reference.stat()
        self.assertEqual((before.st_size, before.st_mtime_ns), (after.st_size, after.st_mtime_ns))
        with self.assertRaisesRegex(ValueError, 'Recipe, references, workspace or environment changed'):
            execution.run_ticket(self.runtime, ticket, approved=True)
        self.assert_no_dispatch()

    def test_dispatch_time_hash_race_creates_no_intent_or_job(self):
        ticket = execution.prepare_ticket(self.runtime, self.recipe)
        original = execution.hashlib.file_digest
        def digest(stream, algorithm):
            result = original(stream, algorithm)
            self.change('mtime')
            return result
        with patch.object(execution.hashlib, 'file_digest', side_effect=digest):
            with self.assertRaisesRegex(ValueError, 'Reference changed during preparation'):
                execution.run_ticket(self.runtime, ticket, approved=True)
        self.assert_no_dispatch()

    def test_unchanged_reference_dispatches_once_and_reuses_its_receipt(self):
        ticket = execution.prepare_ticket(self.runtime, self.recipe)
        self.assertEqual(ticket['pins']['load_image_files'],
                         [{'name': 'ref.png', 'sha256': hashlib.sha256(b'abcd').hexdigest()}])
        first = execution.run_ticket(self.runtime, ticket, approved=True)
        second = execution.run_ticket(self.runtime, ticket, approved=True)
        self.assertTrue(first['dispatch_attempted'])
        self.assertFalse(second['dispatch_attempted'])
        self.assertTrue(second['replayed'])
        self.assertEqual(first['job']['id'], second['job']['id'])
        self.assertEqual(self.runtime.calls, 1)
        self.assertEqual(len(list((self.runtime.runs / 'workflow-requests').glob('*.json'))), 1)


if __name__ == '__main__':
    unittest.main()
