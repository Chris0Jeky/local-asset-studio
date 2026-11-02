"""Saved sentinel replay is explicit and cannot clear missing or contradictory evidence."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import render_critic_policy as policy


def receipt(count=26):
    return {'changed': count >= 20, 'evidence_complete': True, 'defects': [], 'model': None,
            'pixel_policy': {'level': 8, 'min_pixels': 20, 'channels': 'decoded-RGBA8', 'colour_management': 'none'},
            'pixel_diff': {'front.lit': {'changed_px': count, 'bbox': [0, 0, 26, 1] if count else None}},
            'view_sizes': {'front.lit': {'candidate': [256, 256], 'reference': [256, 256]}}}


def envelope(count=26):
    return {'schema': 'las.asset-parity-sentinel.v1', 'pass': False, 'visual_warnings': ['primary'],
            'second_signal': {'available': True, 'tool': 'render_critic', 'mode': 'pixel gate',
                              'changed': count >= 20, 'changed_px': count, 'defects': [], 'observation': receipt(count)}}


class SavedSentinelReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.assertTrue(hasattr(policy, 'select_observation'), 'explicit sentinel receipt selection is not implemented')
        for name in ('urllib.request.urlopen', 'subprocess.Popen'):
            p = mock.patch(name, side_effect=AssertionError('replay may not execute or connect'))
            p.start(); self.addCleanup(p.stop)

    def replay(self, doc, **options):
        src, out = self.root / 'source.json', self.root / 'decision.json'
        src.write_text(json.dumps(doc), encoding='utf-8')
        return policy.replay(src, out, .004, **options)

    def test_successful_saved_sentinel_uses_exact_observation(self):
        doc = envelope(); before = copy.deepcopy(doc)
        selected = policy.select_observation(doc, 'sentinel')
        self.assertEqual(selected, doc['second_signal']['observation'])
        self.assertEqual(doc, before)
        r = self.replay(doc, input_kind='sentinel')
        self.assertEqual(r['status'], 'below_floor'); self.assertIs(r['raw_changed'], True)
        self.assertEqual(r['input_kind'], 'sentinel')
        self.assertEqual(r['observation_pointer'], '/second_signal/observation')
        self.assertEqual(r['receipt_sha256'], hashlib.sha256((self.root/'source.json').read_bytes()).hexdigest())

    def test_default_remains_raw_receipt_not_heuristic_unwrapping(self):
        r = self.replay(envelope())
        self.assertEqual(r['status'], 'incomplete'); self.assertTrue(r['requires_review'])
        self.assertEqual(r['input_kind'], 'receipt')

    def test_explicit_raw_receipt_mode_is_backward_compatible(self):
        r = self.replay(receipt(), input_kind='receipt')
        self.assertEqual(r['status'], 'below_floor'); self.assertEqual(r['observation_pointer'], '')

    def test_unknown_input_kind_is_caller_error(self):
        for kind in ('auto', None, True, 3, [], {}):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                policy.select_observation(envelope(), kind)

    def test_schema_is_required_and_version_exact(self):
        for schema in (None, 'las.asset-parity-sentinel.v0', 'las.other.v1'):
            doc = envelope(); doc['schema'] = schema
            r = policy.decide(policy.select_observation(doc, 'sentinel'), .004)
            self.assertEqual(r['status'], 'incomplete'); self.assertTrue(r['requires_review'])

    def test_wrong_container_type_stays_incomplete(self):
        for doc in (None, [], 1, 'source.blend', {}):
            with self.subTest(doc=doc):
                self.assertEqual(policy.decide(policy.select_observation(doc, 'sentinel'), 0)['status'], 'incomplete')

    def test_unavailable_critic_cannot_be_replayed_as_quiet(self):
        for value in (False, None, 1, 'true'):
            doc = envelope(0); doc['second_signal']['available'] = value; doc['pass'] = True
            selected = policy.select_observation(doc, 'sentinel')
            self.assertEqual(policy.decide(selected, .004)['status'], 'incomplete')

    def test_error_key_or_incomplete_signal_cannot_be_ignored(self):
        for extra in ({'error': ''}, {'error': 'unreachable'}, {'evidence_complete': False}):
            doc = envelope(0); doc['second_signal'].update(extra)
            self.assertEqual(policy.decide(policy.select_observation(doc, 'sentinel'), .004)['status'], 'incomplete')

    def test_legacy_summary_without_observation_is_incomplete(self):
        doc = envelope(); del doc['second_signal']['observation']
        r = self.replay(doc, input_kind='sentinel')
        self.assertEqual(r['status'], 'incomplete'); self.assertTrue(r['requires_review'])
        self.assertIn('observation', r['error'].lower())

    def test_incomplete_raw_compatibility_bit_does_not_become_a_detection(self):
        doc = envelope(); doc['second_signal']['observation'] = {
            'changed': True, 'error': 'high-bit PNG', 'evidence_complete': False, 'pixel_diff': {}}
        r = self.replay(doc, input_kind='sentinel')
        self.assertEqual(r['status'], 'incomplete')

    def test_changed_summary_must_agree_with_raw_observation(self):
        for field, value in (('changed', False), ('changed', 1), ('changed_px', 0), ('changed_px', True),
                             ('tool', 'different-critic'), ('mode', 'model only')):
            doc = envelope(); doc['second_signal'][field] = value
            selected = policy.select_observation(doc, 'sentinel')
            with self.subTest(field=field, value=value):
                self.assertEqual(policy.decide(selected, 0)['status'], 'incomplete')

    def test_invalid_raw_counts_remain_incomplete(self):
        doc = envelope(); doc['second_signal']['observation']['pixel_diff']['front.lit']['changed_px'] = -1
        self.assertEqual(self.replay(doc, input_kind='sentinel')['status'], 'incomplete')

    def test_recorded_primary_outcome_does_not_override_critic_evidence(self):
        doc = envelope(0); doc['pass'] = False
        r = self.replay(doc, input_kind='sentinel')
        self.assertEqual(r['status'], 'raw_gate_quiet')
        self.assertNotIn('pass', r)  # not an overall sentinel verdict

    def test_no_document_path_is_followed(self):
        doc = envelope(); doc['source'] = {'file': '../../private.blend'}
        doc['artifacts'] = [{'path': 'https://example.invalid/private'}]
        self.assertEqual(self.replay(doc, input_kind='sentinel')['status'], 'below_floor')
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['decision.json', 'source.json'])

    def test_existing_output_is_never_replaced(self):
        doc = envelope(); (self.root/'decision.json').write_text('earlier evidence')
        with self.assertRaises(FileExistsError): self.replay(doc, input_kind='sentinel')
        self.assertEqual((self.root/'decision.json').read_text(), 'earlier evidence')

    def test_vision_named_signal_retains_the_same_pixel_policy(self):
        doc = envelope(); doc['second_signal']['mode'] = 'pixel gate + vision model'
        doc['second_signal']['observation']['model'] = 'local-test-model'
        self.assertEqual(self.replay(doc, input_kind='sentinel')['status'], 'below_floor')


class SavedSentinelCliTests(unittest.TestCase):
    def test_cli_selects_saved_sentinel_and_has_usable_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); src = root/'sentinel.json'; src.write_text(json.dumps(envelope()))
            for fraction, expected in (('0', 1), ('0.004', 0)):
                out = root/f'decision-{fraction}.json'
                run = subprocess.run([sys.executable, policy.__file__, 'replay', str(src), '--input-kind', 'sentinel',
                                      '--fraction', fraction, '--out', str(out)], capture_output=True, text=True, timeout=10)
                self.assertEqual(run.returncode, expected, run.stderr)
                self.assertEqual(json.loads(out.read_text())['input_kind'], 'sentinel')


if __name__ == '__main__': unittest.main()
