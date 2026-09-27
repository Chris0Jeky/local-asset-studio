"""Ticket pins: the LoadImage staging gate, the template re-read and GPU admission's error split."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from studio_workflow import execution
from test_workflow_preset_adapter import GRAPH, Runtime


class TicketPinTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.runtime = Runtime(temp.name)
        graph = copy.deepcopy(GRAPH); graph['9'] = {'class_type': 'LoadImage', 'inputs': {'image': 'ref.png'}}
        self.graph = graph; self.write(graph)
        (self.runtime.comfy_root / 'input').mkdir(parents=True)

    def write(self, graph):
        self.runtime.path.write_text(json.dumps(graph), encoding='utf-8')

    def pins(self):
        sha = hashlib.sha256(self.runtime.path.read_bytes()).hexdigest()
        return execution._pins(self.runtime, {'preset_id': 'example', 'controls': {}, 'expected_template_sha256': sha})

    def test_a_staged_input_is_pinned_by_name_and_content(self):
        (self.runtime.comfy_root / 'input/ref.png').write_bytes(b'staged bytes')
        self.assertEqual(self.pins()['load_image_files'], [{'name': 'ref.png', 'sha256': hashlib.sha256(b'staged bytes').hexdigest()}])

    def test_loadimage_names_outside_the_input_folder_are_refused(self):
        outside = Path(self.runtime.root) / 'outside.png'; outside.write_bytes(b'x')
        for name in ('../outside.png', str(outside), 'sub/ref.png', 'sub\\ref.png', '.', '..', 7, None):
            with self.subTest(name=name):
                self.graph['9']['inputs']['image'] = name; self.write(self.graph)
                with self.assertRaisesRegex(ValueError, 'LoadImage requires a staged local input file'): self.pins()

    def test_a_missing_or_non_file_staged_input_is_unavailable(self):
        (self.runtime.comfy_root / 'input/folder.png').mkdir()
        for name in ('ref.png', 'folder.png'):
            with self.subTest(name=name):
                self.graph['9']['inputs']['image'] = name; self.write(self.graph)
                with self.assertRaisesRegex(ValueError, 'Staged reference is unavailable: ' + name): self.pins()

    def test_a_template_replaced_between_prepare_and_the_pin_is_refused(self):
        (self.runtime.comfy_root / 'input/ref.png').write_bytes(b'staged bytes')
        changed = copy.deepcopy(self.graph); changed['3']['inputs']['steps'] = 21
        original = self.runtime.graph_for
        calls = []
        def graph_for(preset):
            calls.append(preset)
            return (copy.deepcopy(changed), self.runtime.path) if len(calls) > 1 else original(preset)
        with patch.object(self.runtime, 'graph_for', side_effect=graph_for):
            with self.assertRaisesRegex(ValueError, 'Template changed while preparing'): self.pins()

    def test_only_a_proven_held_lease_becomes_an_admission_refusal(self):
        held = ValueError('held by local-qwen'); held.code = 'gpu_leased'; held.details = {'holder': 'local-qwen'}
        with self.assertRaises(execution.RunAdmissionRefused):
            execution._require_gpu(SimpleNamespace(gpu_lease=SimpleNamespace(require_available=lambda: (_ for _ in ()).throw(held))))
        other = ValueError('lease state unreadable')
        with self.assertRaises(ValueError) as caught:
            execution._require_gpu(SimpleNamespace(gpu_lease=SimpleNamespace(require_available=lambda: (_ for _ in ()).throw(other))))
        self.assertIs(caught.exception, other)
        self.assertIsNone(execution._require_gpu(SimpleNamespace()))


if __name__ == '__main__': unittest.main()
