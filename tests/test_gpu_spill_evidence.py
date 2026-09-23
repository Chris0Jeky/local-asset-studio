"""A running job keeps the peak shared GPU memory it saw and flags a WDDM spill; sampling never breaks observation."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'app'))
from server import Studio

GIB = 2 ** 30


def studio(readings):
    queue = list(readings)
    def read(refresh=False):
        value = queue.pop(0)
        if isinstance(value, Exception): raise value
        return value
    return SimpleNamespace(gpu_memory_reading=read)


class GpuSpillEvidenceTests(unittest.TestCase):
    def test_peak_and_spill_flag_accumulate_per_submission(self):
        job, submission = {}, {}
        fake = studio([{'dedicated_bytes': 10 * GIB, 'shared_bytes': GIB // 10, 'spilled': False},
                       {'dedicated_bytes': 15 * GIB, 'shared_bytes': 3 * GIB // 2, 'spilled': True},
                       {'dedicated_bytes': 12 * GIB, 'shared_bytes': GIB, 'spilled': True}])
        for _ in range(3): Studio._sample_gpu_memory(fake, job, submission)
        self.assertEqual(submission['gpu_memory'], {'peak_shared_bytes': 3 * GIB // 2, 'peak_dedicated_bytes': 15 * GIB, 'samples': 3, 'spilled': True})
        self.assertTrue(job['gpu_spill'])

    def test_unknown_or_failing_readings_record_nothing(self):
        job, submission = {}, {}
        fake = studio([{'dedicated_bytes': None, 'shared_bytes': None, 'spilled': None, 'unknown_reason': 'no process'}, RuntimeError('pdh')])
        Studio._sample_gpu_memory(fake, job, submission); Studio._sample_gpu_memory(fake, job, submission)
        self.assertEqual((job, submission), ({}, {}))

    def test_quiet_run_is_not_flagged(self):
        job, submission = {}, {}
        Studio._sample_gpu_memory(studio([{'dedicated_bytes': 10 * GIB, 'shared_bytes': 78 * 2 ** 20, 'spilled': False}]), job, submission)
        self.assertFalse(submission['gpu_memory']['spilled']); self.assertNotIn('gpu_spill', job)


if __name__ == '__main__':
    unittest.main()
