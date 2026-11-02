"""Repository-retained raw observations reproduce the published synthetic decisions."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import render_critic_policy as policy
import render_critic_study as study

EVIDENCE = ROOT / 'research/agentic-creation/critic-observations'


class RetainedEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((EVIDENCE/'manifest.json').read_text(encoding='utf-8'))
        self.data = (EVIDENCE/'observations.jsonl').read_bytes()
        self.rows = [json.loads(line) for line in self.data.splitlines()]

    def test_manifest_pins_every_raw_observation_and_explicit_limits(self):
        self.assertEqual(self.manifest['observations_sha256'], hashlib.sha256(self.data).hexdigest())
        self.assertEqual(self.manifest['cases'], len(self.rows))
        self.assertEqual(len({r['id'] for r in self.rows}), 24)
        self.assertEqual(self.manifest['evidence_kind'], 'owned_synthetic_pixels')
        self.assertFalse(self.manifest['native_execution'])
        self.assertFalse(self.manifest['production_policy_changed'])

    def test_retained_policies_recompute_without_images_or_models(self):
        with patch('urllib.request.urlopen', side_effect=AssertionError('offline')):
            summary = {}
            for floor in self.manifest['floors']:
                stats = dict(tp=0, fp=0, tn=0, fn=0, incomplete=0)
                for row in self.rows:
                    result = policy.decide(row['receipt'], floor)
                    self.assertNotEqual(result['status'], 'incomplete')
                    expected = row['decisions'][str(floor)]
                    self.assertEqual({k:result[k] for k in expected if k != 'triggering_views'},
                                     {k:v for k,v in expected.items() if k != 'triggering_views'})
                    self.assertEqual(sorted(result['triggering_views']), sorted(expected['triggering_views']))
                    pred, truth = result['requires_review'], row['synthetic_requires_review']
                    stats['tp' if pred and truth else 'fp' if pred else 'fn' if truth else 'tn'] += 1
                summary[str(floor)] = stats
        self.assertEqual(summary, self.manifest['synthetic_confusion'])
        self.assertEqual(summary['0.004']['fn'], 5)

    def test_owned_pixel_recipe_regenerates_the_same_receipts(self):
        # All original images are regenerable; no binary/private evidence is required in Git.
        with tempfile.TemporaryDirectory() as d, patch('urllib.request.urlopen', side_effect=AssertionError('offline')):
            generated = study.run(Path(d)/'generated')
        self.assertEqual(generated['synthetic_confusion'], self.manifest['synthetic_confusion'])
        self.assertEqual({r['id']:r['receipt'] for r in generated['cases']}, {r['id']:r['receipt'] for r in self.rows})
        self.assertEqual(len(generated['artifacts']), self.manifest['generated_artifacts'])
        # Encoded PNG/HTML hashes identify the historical run, not a cross-Pillow/zlib golden.
        # The exact semantic receipts above are the cross-host reproducibility assertion.


if __name__ == '__main__': unittest.main()
