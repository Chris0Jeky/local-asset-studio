"""Offline policy hypotheses cannot rewrite evidence or clear invalid receipts."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
try:
    import render_critic_policy as policy
except ImportError:
    policy = None


def receipt(count=26, size=256, n=4):
    counts = [count] + [0] * (n - 1)
    return {'changed': sum(counts) >= 20, 'evidence_complete': True, 'defects': [],
            'pixel_policy': {'level': 8, 'min_pixels': 20, 'channels': 'decoded-RGBA8', 'colour_management': 'none'},
            'pixel_diff': {str(i): {'changed_px': c, 'bbox': [0, 0, size, size] if c else None}
                           for i, c in enumerate(counts)},
            'view_sizes': {str(i): {'candidate': [size, size], 'reference': [size, size]} for i in range(n)}}


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(policy, 'offline policy module is not implemented')

    def test_zero_floor_preserves_the_raw_signal(self):
        r = policy.decide(receipt(), 0)
        self.assertEqual((r['status'], r['requires_review'], r['raw_changed']), ('changed', True, True))

    def test_small_change_is_only_below_a_hypothetical_floor(self):
        source = receipt(); before = copy.deepcopy(source)
        r = policy.decide(source, .004)
        self.assertEqual((r['status'], r['requires_review'], r['raw_changed']), ('below_floor', False, True))
        self.assertTrue(r['experimental']); self.assertEqual(source, before)
        self.assertEqual(r['views']['0']['total_px'], 256 * 256)
        self.assertEqual(r['views']['0']['changed_fraction'], 26 / (256 * 256))

    def test_unchanged_is_not_promoted_to_art_acceptance(self):
        r = policy.decide(receipt(0), .004)
        self.assertEqual(r['status'], 'raw_gate_quiet'); self.assertNotIn('pass', r)

    def test_extra_unchanged_views_do_not_dilute_a_local_change(self):
        for n in (1, 4, 32):
            with self.subTest(n=n):
                self.assertTrue(policy.decide(receipt(300, n=n), .004)['requires_review'])

    def test_fraction_boundary_is_strict_and_raw_gate_still_applies(self):
        self.assertFalse(policy.decide(receipt(40, size=100), .004)['requires_review'])
        self.assertTrue(policy.decide(receipt(41, size=100), .004)['requires_review'])
        self.assertFalse(policy.decide(receipt(19, size=8), 0)['requires_review'])

    def test_identical_pixel_count_is_resolution_dependent(self):
        self.assertTrue(policy.decide(receipt(171, size=96), .004)['requires_review'])
        self.assertFalse(policy.decide(receipt(171, size=512), .004)['requires_review'])

    def test_size_mismatch_cannot_be_suppressed(self):
        r = receipt(1, size=1, n=1); r['changed'] = True
        r['view_sizes']['0']['reference'] = [256, 256]
        r['pixel_diff']['0']['size_mismatch'] = [[1, 1], [256, 256]]
        self.assertTrue(policy.decide(r, 1)['requires_review'])

    def test_missing_dimensions_never_get_an_assumed_resolution(self):
        r = receipt(); del r['view_sizes']
        self.assertEqual(policy.decide(r, .004)['status'], 'incomplete')

    def test_invalid_receipts_cannot_clear(self):
        bad = [None, [], {}, {'error': 'missing', 'changed': True}, receipt()]
        bad[-1]['evidence_complete'] = False
        for source in bad:
            with self.subTest(source=source):
                r = policy.decide(source, .004)
                self.assertEqual(r['status'], 'incomplete'); self.assertTrue(r['requires_review'])

    def test_denominators_and_counts_are_strict_integers(self):
        for value in (0, -1, True, 1.5, '256', float('inf'), 100000000000):
            r = receipt(); r['view_sizes']['0']['candidate'][0] = value
            with self.subTest(value=value): self.assertEqual(policy.decide(r, .004)['status'], 'incomplete')
        for value in (-1, True, 2.5, '26', 65537, float('nan')):
            r = receipt(); r['pixel_diff']['0']['changed_px'] = value
            with self.subTest(value=value): self.assertTrue(policy.decide(r, .004)['requires_review'])

    def test_metadata_sets_must_match(self):
        r = receipt(); del r['view_sizes']['3']
        self.assertEqual(policy.decide(r, .004)['status'], 'incomplete')

    def test_tampered_changed_boolean_cannot_clear(self):
        r = receipt(600); r['changed'] = False
        self.assertEqual(policy.decide(r, .004)['status'], 'incomplete')
        r = receipt(0); r['changed'] = 'false'
        self.assertEqual(policy.decide(r, .004)['status'], 'incomplete')

    def test_unknown_sample_policy_cannot_clear(self):
        r = receipt(); r['pixel_policy']['channels'] = 'RGB'
        self.assertEqual(policy.decide(r, .004)['status'], 'incomplete')
        r = receipt(); r['pixel_policy']['min_pixels'] = True
        self.assertEqual(policy.decide(r, .004)['status'], 'incomplete')

    def test_size_flag_must_agree_with_recorded_sizes(self):
        r = receipt(); r['view_sizes']['0']['reference'] = [4, 4]
        self.assertEqual(policy.decide(r, .004)['status'], 'incomplete')
        r = receipt(); r['pixel_diff']['0']['size_mismatch'] = [[8, 8], [1, 1]]
        self.assertEqual(policy.decide(r, .004)['status'], 'incomplete')

    def test_invalid_floor_is_a_caller_error(self):
        for f in (-.1, 1.1, float('nan'), float('inf'), True, '0.004', None):
            with self.subTest(f=f), self.assertRaises(ValueError): policy.decide(receipt(), f)

    def test_empty_and_oversized_view_sets_are_incomplete(self):
        for n in (0, 257):
            r = receipt(n=max(1, n));
            if not n: r['pixel_diff'] = {}; r['view_sizes'] = {}
            self.assertEqual(policy.decide(r, 0)['status'], 'incomplete')

    def test_replay_never_overwrites_and_pins_input_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            src, out = Path(d) / 'receipt.json', Path(d) / 'decision.json'
            src.write_text(json.dumps(receipt()), encoding='utf-8')
            import hashlib
            expected = hashlib.sha256(src.read_bytes()).hexdigest()
            r = policy.replay(src, out, .004)
            self.assertEqual(r['receipt_sha256'], expected)
            saved = out.read_bytes()
            with self.assertRaises(FileExistsError): policy.replay(src, out, 0)
            self.assertEqual(saved, out.read_bytes())
            self.assertEqual(expected, hashlib.sha256(src.read_bytes()).hexdigest())

    def test_replay_refuses_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as d:
            src, out = Path(d) / 'receipt.json', Path(d) / 'decision.json'
            src.write_text('{"changed":true,"changed":false}')
            with self.assertRaises(ValueError): policy.replay(src, out, 0)
            self.assertFalse(out.exists())

    def test_cli_exit_status_is_machine_usable(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / 'receipt.json'; src.write_text(json.dumps(receipt()))
            script = str(Path(policy.__file__))
            for floor, code in ((0, 1), (.004, 0)):
                p = subprocess.run([sys.executable, script, 'replay', str(src), '--fraction', str(floor),
                                    '--out', str(Path(d) / f'{floor}.json')], capture_output=True, text=True, timeout=10)
                self.assertEqual(p.returncode, code, p.stderr)


if __name__ == '__main__': unittest.main()
