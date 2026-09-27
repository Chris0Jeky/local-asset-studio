"""#302: each prompt's window carries its sampled Windows commit peak and minimum headroom; telemetry never changes a job's outcome."""
from pathlib import Path
import sys
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'app'))
import host_memory
import server

GIB = 2 ** 30


def reading(available, limit=96 * GIB):
    return {'available_bytes': available, 'limit_bytes': limit, 'committed_bytes': limit - available, 'unknown_reason': None}


class SamplerTests(unittest.TestCase):
    def test_window_keeps_peak_minimum_and_counts_unknowns(self):
        values = iter([reading(40 * GIB), reading(12 * GIB), {'available_bytes': None, 'limit_bytes': None, 'committed_bytes': None, 'unknown_reason': 'pdh'}, reading(30 * GIB)])
        clock = iter([10.0, 11.0, 12.0, 13.0])
        sampler = host_memory.Sampler(reader=lambda: next(values))
        with patch.object(host_memory, '_clock', lambda: next(clock)):
            for _ in range(4): sampler.sample()
        window = sampler.take()
        self.assertEqual((window['samples'], window['unknown_samples']), (3, 1))
        self.assertEqual((window['peak_committed_bytes'], window['peak_at'], window['limit_bytes'], window['min_available_bytes']), (84 * GIB, 11.0, 96 * GIB, 12 * GIB))
        self.assertEqual((window['first_at'], window['last_at']), (10.0, 13.0))
        self.assertIsNone(sampler.take(), 'a window is handed over once')

    def test_failing_reader_is_counted_unknown_never_zero(self):
        sampler = host_memory.Sampler(reader=lambda: 1 / 0); sampler.sample()
        window = sampler.take()
        self.assertEqual((window['samples'], window['unknown_samples']), (0, 1)); self.assertNotIn('min_available_bytes', window)

    def test_thread_samples_at_start_and_stop_and_exits(self):
        seen = []
        sampler = host_memory.Sampler(interval=0.01, reader=lambda: seen.append(1) or reading(50 * GIB)).start()
        self.assertEqual(len(seen), 1, 'start takes one reading synchronously')
        sampler.stop(); self.assertFalse(sampler._thread.is_alive()); self.assertGreaterEqual(len(seen), 2)

    def test_the_gate_reading_and_clock_are_not_the_ones_telemetry_uses(self):
        # A patched gate reading (tests, callers) must never be consumed by the sampler thread.
        with patch.object(host_memory, 'read', side_effect=AssertionError('gate reading consumed')):
            sampler = host_memory.Sampler(reader=None); sampler.sample()
        self.assertIsNotNone(sampler.take())


class ServerFoldTests(unittest.TestCase):
    def fake(self):
        saved = []
        return SimpleNamespace(_save=lambda job: saved.append(dict(job))), saved

    def window(self, available):
        sampler = host_memory.Sampler(reader=lambda: reading(available)); sampler.sample(); return sampler

    def test_window_is_kept_per_prompt_without_touching_the_submission_receipt(self):
        fake, saved = self.fake(); job = {}; submission = {'index': 1, 'prompt_id': 'p2', 'status': 'completed'}
        server.Studio._record_host_commit(fake, job, submission, self.window(12 * GIB))
        self.assertEqual(submission, {'index': 1, 'prompt_id': 'p2', 'status': 'completed'})
        window, = job['host_commit_windows']
        self.assertEqual((window['index'], window['prompt_id'], window['min_available_bytes'], window['interval_seconds']), (1, 'p2', 12 * GIB, server.GPU_SAMPLE_SECONDS))
        self.assertEqual(len(saved), 1)

    def test_windows_are_bounded_and_failures_never_raise(self):
        fake, _ = self.fake(); job = {'host_commit_windows': [{}] * server.HOST_COMMIT_WINDOWS}
        server.Studio._record_host_commit(fake, job, {'index': 0}, self.window(20 * GIB))
        self.assertEqual(len(job['host_commit_windows']), server.HOST_COMMIT_WINDOWS)
        broken = SimpleNamespace(_save=lambda job: (_ for _ in ()).throw(OSError('disk full')))
        job = {}; server.Studio._record_host_commit(broken, job, {'index': 0}, self.window(20 * GIB))
        self.assertEqual(len(job['host_commit_windows']), 1)
        server.Studio._record_host_commit(broken, {}, {'index': 0}, SimpleNamespace(stop=lambda: 1 / 0))

    def test_a_real_run_records_one_window_per_prompt_and_publishes_it(self):
        import tempfile, json
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for d in ('presets', 'workflows/api', 'config', 'fake-comfy/input'): (root / d).mkdir(parents=True)
            (root / 'config/local.json').write_text(json.dumps({'comfy_root': str(root / 'fake-comfy')}))
            (root / 'presets/catalog.json').write_text(json.dumps({'presets': [{'id': 'demo', 'name': 'Demo', 'graph': 'workflows/api/demo-api.json', 'seed': ['1', 'seed']}]}))
            (root / 'workflows/api/demo-api.json').write_text(json.dumps({'1': {'class_type': 'KSampler', 'inputs': {'seed': 1}}}))
            replies = iter([{'queue_running': [], 'queue_pending': []}, {'prompt_id': 'a'}, {'a': {'status': {'status_str': 'success'}, 'outputs': {}}},
                            {'prompt_id': 'b'}, {'b': {'status': {'status_str': 'success'}, 'outputs': {}}}])
            with patch.object(threading.Thread, 'start', lambda *_: None), patch.object(host_memory, '_counters', lambda: reading(33 * GIB)):
                studio = server.Studio(root); studio._request = lambda *a, **k: next(replies)
                job = studio.jobs[studio.create_job({'preset_id': 'demo', 'controls': {}, 'batch_count': 2}, enqueue=False)['id']]; studio._run(job)
            self.assertEqual(job['status'], 'completed')
            self.assertEqual([(w['index'], w['prompt_id'], w['min_available_bytes']) for w in job['host_commit_windows']], [(0, 'a', 33 * GIB), (1, 'b', 33 * GIB)])
            self.assertEqual(studio.public(job)['host_commit_windows'], job['host_commit_windows'])
            self.assertTrue(all('host_commit' not in s for s in job['submissions']))
            saved = json.loads((root / 'experiments/runs' / job['id'] / 'state.json').read_text())
            self.assertEqual(len(saved['host_commit_windows']), 2)


if __name__ == '__main__':
    unittest.main()
