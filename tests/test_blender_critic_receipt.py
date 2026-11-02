"""Real CPU image evidence at the sentinel/critic boundary; no native process or model call."""
import copy
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock
import zlib

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import blender_sentinel as sentinel
import render_critic
import render_critic_policy as policy


def png16(path, value):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    row = b'\0' + struct.pack('>H', value) * (8 * 3)
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 8, 8, 16, 2, 0, 0, 0))
                     + chunk(b'IDAT', zlib.compress(row * 8)) + chunk(b'IEND', b''))


class CriticReceiptTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name); self.ref = self.root / 'reference'; self.ref.mkdir()
        self.cand = self.root / 'candidate'; self.cand.mkdir()
        net = mock.patch('urllib.request.urlopen', side_effect=AssertionError('unexpected inference'))
        self.network = net.start(); self.addCleanup(net.stop)
        native = mock.patch.object(sentinel.lab, 'run', side_effect=AssertionError('unexpected Blender execution'))
        self.native = native.start(); self.addCleanup(native.stop)
        for folder in (self.ref, self.cand):
            for v in sentinel.lab.bpy_side.VIEWS:
                Image.new('RGBA', (8, 8), (50, 60, 70, 255)).save(folder / f'{v}.lit.png')
        self.first = f'{sentinel.lab.bpy_side.VIEWS[0]}.lit.png'

    def test_unsupported_real_evidence_cannot_agree_with_warning_primary(self):
        png16(self.ref / self.first, 0x4000); png16(self.cand / self.first, 0xf000)
        primary = sentinel.compare_image(self.ref / self.first, self.cand / self.first,
                                         self.root / 'diff.png', 'lit')
        self.assertTrue(primary['warn'])  # primary really observes a difference; the critic refuses source precision
        signal = sentinel.critic_signal(self.ref, self.cand)
        warnings = ['primary observed a change']; before = warnings.copy()
        self.assertFalse(signal['available'])
        self.assertIn('high-bit', signal['error'])
        self.assertIsNone(sentinel.second_opinion(signal, warnings))
        self.assertEqual(warnings, before)
        self.assertNotIn('changed', signal)
        self.network.assert_not_called(); self.native.assert_not_called()

    def test_unsupported_evidence_cannot_create_a_critic_only_warning(self):
        png16(self.cand / self.first, 0x4000)
        warnings = []; signal = sentinel.critic_signal(self.ref, self.cand)
        self.assertIsNone(sentinel.second_opinion(signal, warnings))
        self.assertEqual(warnings, [])
        self.assertFalse(signal.get('evidence_complete', True))

    def test_incomplete_observation_is_retained_not_relabelled_a_result(self):
        png16(self.cand / self.first, 0x4000)
        signal = sentinel.critic_signal(self.ref, self.cand)
        self.assertIn('observation', signal)
        self.assertIs(signal['observation']['evidence_complete'], False)
        self.assertIs(signal['observation']['changed'], True)  # compatibility bit, NOT a successful signal
        self.assertIn('error', signal['observation'])

    def test_success_retains_replayable_per_view_observation(self):
        signal = sentinel.critic_signal(self.ref, self.cand)
        self.assertTrue(signal['available'])
        self.assertIn('observation', signal)
        observation = json.loads(json.dumps(signal['observation']))
        self.assertTrue(observation['evidence_complete'])
        self.assertEqual(set(observation['view_sizes']), {f'{v}.lit' for v in sentinel.lab.bpy_side.VIEWS})
        self.assertEqual(policy.decide(observation, 0)['status'], 'raw_gate_quiet')
        self.assertTrue(sentinel.second_opinion(signal, []))

    def test_changed_real_evidence_still_warns_and_replays(self):
        Image.new('RGBA', (8, 8), (255, 60, 70, 255)).save(self.cand / self.first)
        signal = sentinel.critic_signal(self.ref, self.cand)
        warnings = []
        self.assertTrue(signal['available']); self.assertTrue(signal['changed'])
        self.assertEqual(signal['changed_px'], 64)
        self.assertFalse(sentinel.second_opinion(signal, warnings))
        self.assertEqual(len(warnings), 1)
        self.assertIn('observation', signal)
        self.assertTrue(policy.decide(signal['observation'], 0)['requires_review'])

    def test_error_key_is_not_dropped_even_when_empty(self):
        result = {'changed': True, 'pixel_diff': {}, 'defects': [], 'error': '', 'evidence_complete': True}
        with mock.patch.object(render_critic, 'check', return_value=result):
            signal = sentinel.critic_signal(self.ref, self.cand)
        self.assertFalse(signal['available']); self.assertIn('error', signal)

    def test_false_completion_without_error_is_unavailable(self):
        result = {'changed': True, 'pixel_diff': {}, 'defects': [], 'evidence_complete': False}
        with mock.patch.object(render_critic, 'check', return_value=result):
            signal = sentinel.critic_signal(self.ref, self.cand)
        self.assertFalse(signal['available']); self.assertIn('incomplete', signal['error'].lower())

    def test_malformed_critic_return_never_discards_primary_evidence(self):
        for result in (None, [], {'changed': 'false', 'pixel_diff': {}},
                       {'changed': True, 'pixel_diff': {'front': {'changed_px': -1}}}):
            with self.subTest(result=result), mock.patch.object(render_critic, 'check', return_value=result):
                signal = sentinel.critic_signal(self.ref, self.cand)
                self.assertFalse(signal['available']); self.assertIn('error', signal)

    def test_missing_image_is_unavailable_not_clean(self):
        (self.cand / self.first).unlink()
        signal = sentinel.critic_signal(self.ref, self.cand)
        self.assertFalse(signal['available']); self.assertIn('error', signal)
        self.assertIsNone(sentinel.second_opinion(signal, []))

    def test_missing_optional_module_stays_optional(self):
        with mock.patch.dict(sys.modules, {'render_critic': None}):
            self.assertEqual(sentinel.critic_signal(self.ref, self.cand), {'available': False})

    def test_error_and_false_completion_defensively_prevent_agreement(self):
        for extra in ({'error': 'bad evidence'}, {'evidence_complete': False}):
            signal = dict(available=True, changed=True, changed_px=99, **extra)
            warnings = ['primary warning']
            self.assertIsNone(sentinel.second_opinion(signal, warnings))
            self.assertEqual(warnings, ['primary warning'])

    def test_legacy_success_remains_compatible_but_not_replayable(self):
        legacy = {'changed': True, 'pixel_diff': {'front.lit': {'changed_px': 40}}, 'defects': []}
        with mock.patch.object(render_critic, 'check', return_value=copy.deepcopy(legacy)):
            signal = sentinel.critic_signal(self.ref, self.cand)
        self.assertTrue(signal['available']); self.assertEqual(signal['changed_px'], 40)
        self.assertIn('observation', signal)
        self.assertEqual(policy.decide(signal['observation'], 0)['status'], 'incomplete')

    def test_critic_exception_is_bounded_and_primary_survives(self):
        with mock.patch.object(render_critic, 'check', side_effect=OSError('x' * 1000)):
            signal = sentinel.critic_signal(self.ref, self.cand, server='http://127.0.0.1:9')
        self.assertFalse(signal['available']); self.assertLessEqual(len(signal['error']), 300)
        self.assertIsNone(sentinel.second_opinion(signal, ['primary']))


if __name__ == '__main__': unittest.main()
