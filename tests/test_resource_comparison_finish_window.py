"""Post-coordinator samples are visible evidence, never comparison input."""
from datetime import timedelta
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
sys.path.insert(0, str(ROOT))

import job_resources as producer
import resource_comparison
import resource_receipts
from test_resource_receipts import events, make_observation, read, write


def binding(path):
    return {
        'directory': str(path),
        'result_sha256': hashlib.sha256((path / 'result.json').read_bytes()).hexdigest(),
        'job_id': read(path / 'result.json')['job_id'],
    }


class ComparisonFinishWindowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.baseline = make_observation(self.root, 'base')
        self.candidate = make_observation(self.root, 'candidate')

    def test_post_coordinator_sample_withholds_descriptive_arithmetic(self):
        finish = resource_receipts._timestamp(events(self.candidate)[-1]['recorded_at'])
        profile = self.candidate / 'profile.jsonl'
        values = [json.loads(line) for line in profile.read_bytes().splitlines()]
        values[-1]['observed_at'] = (finish + timedelta(seconds=5)).isoformat()
        raw = b''.join(producer.encoded(value) for value in values)
        profile.write_bytes(raw)
        write(self.candidate / 'summary.json', producer.summarize_resource_profile(io.BytesIO(raw)))
        result = read(self.candidate / 'result.json')
        result['artifact_hashes'] = producer.artifact_hashes(self.candidate)
        result['finished_at'] = (finish + timedelta(seconds=6)).isoformat()
        write(self.candidate / 'result.json', result)

        plan = {
            'schema': 'studio.resource-comparison-plan/v1',
            'generation_allowance': 0,
            'pairs': [{
                'id': 'pair-1',
                'condition': 'unspecified',
                'baseline': binding(self.baseline),
                'candidate': binding(self.candidate),
            }],
        }
        manifest = self.root / 'pairs.json'
        manifest.write_text(json.dumps(plan), encoding='utf-8')
        pair = resource_comparison.compare_observations(manifest)['pairs'][0]

        self.assertEqual(pair['candidate']['state'], 'verified')
        self.assertIn('sample_window_overshoot', pair['candidate']['observation']['warnings'])
        self.assertEqual(pair['comparison']['state'], 'withheld')
        self.assertIn('sample_window_overshoot', pair['comparison']['blockers'])
        self.assertEqual(pair['comparison']['host_metrics'], {})
        self.assertEqual(pair['comparison']['devices'], [])


if __name__ == '__main__':
    unittest.main()
