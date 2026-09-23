"""A running job keeps the peak shared GPU memory it saw and flags a WDDM spill; sampling never breaks observation."""
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'app'))
from server import Studio
import gpu_memory

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


class FastSamplerAndMessageTests(unittest.TestCase):
    READING = {'adapters': {'a': {7: {'dedicated_bytes': 10 * GIB, 'shared_bytes': 0}, 2288: {'dedicated_bytes': 6 * GIB, 'shared_bytes': 0}}}}

    def reading(self, shared):
        return {'adapters': {'a': {7: {'dedicated_bytes': 10 * GIB, 'shared_bytes': shared}, 2288: {'dedicated_bytes': 6 * GIB, 'shared_bytes': 0}}}}

    def test_sampler_keeps_the_peak_and_the_holders_at_that_moment(self):
        readings = iter([self.reading(GIB // 10), self.reading(4 * GIB), self.reading(GIB)])
        sampler = gpu_memory.Sampler(7, reader=lambda: next(readings))
        with patch('psutil.Process', side_effect=lambda pid: SimpleNamespace(name=lambda: 'dwm.exe')):
            for _ in range(3): sampler.sample()
        peak = sampler.take()
        self.assertEqual((peak['peak_shared_bytes'], peak['samples']), (4 * GIB, 3))
        self.assertEqual(peak['holders'], [{'pid': 2288, 'name': 'dwm.exe', 'dedicated_bytes': 6 * GIB}])
        self.assertIsNone(sampler.take())                               # taken once
        broken = gpu_memory.Sampler(7, reader=lambda: 1 / 0); broken.sample(); self.assertIsNone(broken.take())

    def test_sampler_thread_starts_and_stops(self):
        seen = []
        sampler = gpu_memory.Sampler(7, interval=0.01, reader=lambda: seen.append(1) or self.reading(0)).start()
        deadline = time.time() + 5
        while not seen and time.time() < deadline: time.sleep(0.01)
        sampler.stop(); self.assertTrue(seen); self.assertFalse(sampler._thread.is_alive())

    def test_merge_marks_a_spill_the_poll_readings_missed(self):
        job, submission = {}, {}
        batch = {'peak_shared_bytes': 4 * GIB, 'peak_dedicated_bytes': 11 * GIB, 'samples': 9, 'holders': [{'pid': 2288, 'name': 'dwm.exe', 'dedicated_bytes': 6 * GIB}]}
        fake = studio([{'dedicated_bytes': 9 * GIB, 'shared_bytes': 80 * 2 ** 20, 'spilled': False}])
        Studio._sample_gpu_memory(fake, job, submission, SimpleNamespace(take=lambda: batch))
        self.assertEqual(submission['gpu_memory'], {'peak_shared_bytes': 4 * GIB, 'peak_dedicated_bytes': 11 * GIB, 'samples': 10, 'spilled': True, 'top_holders': batch['holders']})
        self.assertTrue(job['gpu_spill'])

    def test_settle_tells_a_drained_overflow_from_a_lingering_spill(self):
        drained = {'gpu_memory': {'spilled': True}}
        Studio._settle_gpu_memory(studio([{'shared_bytes': 3 * GIB}, {'shared_bytes': 80 * 2 ** 20}]), drained)
        self.assertEqual((drained['gpu_memory']['lingering'], drained['gpu_memory']['settled_shared_bytes']), (False, 80 * 2 ** 20))
        stuck = {'gpu_memory': {'spilled': True}}
        with patch('server.time.monotonic', side_effect=[0, 0, 10]), patch('server.time.sleep'):
            Studio._settle_gpu_memory(studio([{'shared_bytes': 3 * GIB}, {'shared_bytes': 3 * GIB}]), stuck)
        self.assertTrue(stuck['gpu_memory']['lingering'])
        quiet = {'gpu_memory': {'spilled': False}}; Studio._settle_gpu_memory(studio([]), quiet); self.assertNotIn('lingering', quiet['gpu_memory'])

    def test_messages_name_the_holder_and_only_blame_comfyui_when_the_spill_lingers(self):
        holders = [{'pid': 2288, 'name': 'dwm.exe', 'dedicated_bytes': 6 * GIB}]
        transient = {'submissions': [{'gpu_memory': {'peak_shared_bytes': 4 * GIB, 'spilled': True, 'lingering': False, 'top_holders': holders}}]}
        message = Studio.spill_message(transient)
        self.assertTrue(message.startswith('Complete. GPU memory overflowed 4.0 GB')); self.assertIn('dwm.exe (the Windows desktop) with 6.0 GB', message)
        self.assertNotIn('restart ComfyUI', message)
        lingering = {'submissions': [{'gpu_memory': {'peak_shared_bytes': 5 * GIB, 'spilled': True, 'lingering': True, 'settled_shared_bytes': 2 * GIB}}]}
        message = Studio.spill_message(lingering)
        self.assertTrue(message.startswith('Complete, but slowly')); self.assertIn('2.0 GB was still there', message); self.assertIn('restart ComfyUI', message)


if __name__ == '__main__':
    unittest.main()
