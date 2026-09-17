"""End-to-end receipt checks for coordinator and observer timestamp boundaries."""
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
from test_resource_receipts import events, make_observation, read, write


class ReceiptWindowIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = make_observation(Path(self.tmp.name))

    def move_last_sample_after_finish(self, sample_seconds, result_seconds):
        profile = self.directory / 'profile.jsonl'
        values = [json.loads(line) for line in profile.read_bytes().splitlines()]
        self.assertEqual(len(values), 2, 'the fixture must contain metadata plus one sample')
        finish = resource_receipts._timestamp(events(self.directory)[-1]['recorded_at'])
        values[-1]['observed_at'] = (finish + timedelta(seconds=sample_seconds)).isoformat()
        raw = b''.join(producer.encoded(value) for value in values)
        profile.write_bytes(raw)
        write(self.directory / 'summary.json', producer.summarize_resource_profile(io.BytesIO(raw)))
        result = read(self.directory / 'result.json')
        result['artifact_hashes'] = producer.artifact_hashes(self.directory)
        result['finished_at'] = (finish + timedelta(seconds=result_seconds)).isoformat()
        write(self.directory / 'result.json', result)

    def test_scheduler_delayed_finish_reaches_public_warning(self):
        self.move_last_sample_after_finish(sample_seconds=5, result_seconds=6)
        report = resource_receipts.inspect_observation(self.directory)
        self.assertIn('sample_window_overshoot', report['warnings'])

    def test_sample_after_observer_result_is_not_verified(self):
        self.move_last_sample_after_finish(sample_seconds=1.001, result_seconds=1)
        with self.assertRaises(resource_receipts.EvidenceError) as caught:
            resource_receipts.inspect_observation(self.directory)
        self.assertEqual(caught.exception.code, 'samples_outside_window')


if __name__ == '__main__':
    unittest.main()
