"""Timestamp-window contracts for offline resource receipts."""
from datetime import timedelta
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
sys.path.insert(0, str(ROOT))
import resource_receipts as receipts


BASE = '2026-09-14T20:00:00+00:00'


def stamp(seconds):
    return (receipts._timestamp(BASE) + timedelta(seconds=seconds)).isoformat()


def sampling(*, first=0.25, last=9.75, interval=1):
    return {
        'observed': 1,
        'first_observed_at': stamp(first),
        'last_observed_at': stamp(last),
        'interval_seconds_after_completion': interval,
    }


class SampleWindowTests(unittest.TestCase):
    def verify(self, value, *, finish=10, finished=11):
        warnings = []
        receipts._verify_sample_window(
            [{'recorded_at': stamp(0)}],
            None if finish is None else {'recorded_at': stamp(finish)},
            receipts._timestamp(stamp(finished)),
            value,
            warnings,
        )
        return warnings

    def test_post_coordinator_sample_before_observer_finish_is_warning(self):
        warnings = self.verify(sampling(last=10.5), finish=10, finished=11)
        self.assertEqual(warnings, ['sample_window_overshoot'])

    def test_scheduler_delay_is_not_guessed_from_sampling_interval(self):
        warnings = self.verify(sampling(last=15, interval=1), finish=10, finished=16)
        self.assertEqual(warnings, ['sample_window_overshoot'])

    def test_sample_after_observer_result_timestamp_is_refused(self):
        with self.assertRaises(receipts.EvidenceError) as caught:
            self.verify(sampling(last=11.001), finish=10, finished=11)
        self.assertEqual(caught.exception.code, 'samples_outside_window')

    def test_sample_before_intent_is_still_refused(self):
        with self.assertRaises(receipts.EvidenceError) as caught:
            self.verify(sampling(first=-0.001))
        self.assertEqual(caught.exception.code, 'samples_outside_window')

    def test_in_window_and_no_sample_cases_add_no_warning(self):
        self.assertEqual(self.verify(sampling(last=10)), [])
        value = sampling()
        value['observed'] = 0
        self.assertEqual(self.verify(value), [])

    def test_missing_finish_uses_only_observer_result_boundary(self):
        self.assertEqual(self.verify(sampling(last=10.5), finish=None, finished=11), [])
        with self.assertRaises(receipts.EvidenceError) as caught:
            self.verify(sampling(last=11.001), finish=None, finished=11)
        self.assertEqual(caught.exception.code, 'samples_outside_window')


if __name__ == '__main__':
    unittest.main()
