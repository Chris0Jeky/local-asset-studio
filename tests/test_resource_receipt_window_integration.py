"""End-to-end receipt checks for the bounded finish-event sampling race."""
from datetime import timedelta
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
import resource_receipts
from test_resource_receipts import events, make_observation, rehash, write


class ReceiptWindowIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = make_observation(Path(self.tmp.name))

    def move_last_sample_after_finish(self, seconds):
        profile = self.directory / 'profile.jsonl'
        values = [json.loads(line) for line in profile.read_bytes().splitlines()]
        self.assertEqual(len(values), 2, 'the fixture must contain metadata plus one sample')
        finish = resource_receipts._timestamp(events(self.directory)[-1]['recorded_at'])
        values[-1]['observed_at'] = (finish + timedelta(seconds=seconds)).isoformat()
        raw = b''.join(producer.encoded(value) for value in values)
        profile.write_bytes(raw)
        write(self.directory / 'summary.json', producer.summarize_resource_profile(io.BytesIO(raw)))
        rehash(self.directory)

    def test_small_finish_race_reaches_public_warning(self):
        self.move_last_sample_after_finish(0.05)
        report = resource_receipts.inspect_observation(self.directory)
        self.assertIn('sample_window_overshoot', report['warnings'])

    def test_late_post_completion_sample_is_not_verified(self):
        self.move_last_sample_after_finish(0.101)
        with self.assertRaises(resource_receipts.EvidenceError) as caught:
            resource_receipts.inspect_observation(self.directory)
        self.assertEqual(caught.exception.code, 'samples_outside_window')


if __name__ == '__main__':
    unittest.main()
