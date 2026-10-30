"""Queue position on waiting jobs (#1707): a read-only count of runs ahead in the worker FIFO."""
import unittest
from unittest.mock import patch
import test_looks as fixture


class QueueAheadTests(unittest.TestCase):
    setUp = fixture.LookTests.setUp

    def job(self, created, status):
        job = self.studio.create_job({'preset_id': self.studio.catalog()['presets'][0]['id'], 'controls': {}}, enqueue=False)
        stored = self.studio.jobs[job['id']]; stored['created_at'] = created; stored['status'] = status
        return stored

    def test_counts_unfinished_jobs_created_earlier_only_for_a_waiting_job(self):
        self.job(1, 'running'); self.job(2, 'completed'); self.job(3, 'queued'); self.job(4, 'failed'); waiting = self.job(5, 'queued'); later = self.job(6, 'queued')
        self.assertEqual(self.studio.public(waiting)['queue_ahead'], 2)
        self.assertEqual(self.studio.public(later)['queue_ahead'], 3)
        later['status'] = 'running'
        self.assertNotIn('queue_ahead', self.studio.public(later), 'only a waiting job carries a position')

    def test_private_job_ahead_counts_without_its_content(self):
        private = self.job(1, 'queued'); private['privacy'] = 'private'; private['controls'] = {'positive': 'PRIVATE-CANARY'}
        waiting = self.job(2, 'queued')
        self.studio.queue.put(('generate', private['id'])); self.studio.queue.put(('generate', waiting['id']))
        result = self.studio.public(waiting)
        self.assertEqual(result['queue_ahead'], 1); self.assertNotIn('PRIVATE-CANARY', repr(result))

    def test_counts_observe_production_and_native_entries_without_mutating_queue(self):
        waiting = self.job(1, 'queued')
        entries = [('observe', 'resumed'), ('production', 'comparison'), ('production', 'av-preview'), ('production', 'voice-baseline'), ('observe-mixed', ('mixed', 'request')), ('generate', waiting['id']), ('generate', 'later')]
        for entry in entries: self.studio.queue.put(entry)
        self.assertEqual(self.studio.public(waiting)['queue_ahead'], 5)
        self.assertEqual(self.studio.queue.qsize(), len(entries))
        with self.studio.queue.mutex: self.assertEqual(list(self.studio.queue.queue), entries)

    def test_fifo_overrides_created_at(self):
        earlier = self.job(1, 'queued'); later = self.job(2, 'queued')
        self.studio.queue.put(('generate', later['id'])); self.studio.queue.put(('generate', earlier['id']))
        self.assertEqual(self.studio.public(later)['queue_ahead'], 0)
        self.assertEqual(self.studio.public(earlier)['queue_ahead'], 1)

    def test_same_tick_jobs_follow_fifo(self):
        first = self.job(1, 'queued'); second = self.job(1, 'queued')
        self.studio.queue.put(('generate', first['id'])); self.studio.queue.put(('generate', second['id']))
        self.assertEqual(self.studio.public(first)['queue_ahead'], 0)
        self.assertEqual(self.studio.public(second)['queue_ahead'], 1)

    def test_busy_worker_adds_one(self):
        waiting = self.job(1, 'queued'); self.studio.queue.put(('generate', waiting['id']))
        self.assertEqual(self.studio.public(waiting)['queue_ahead'], 0)
        self.studio._worker_busy = True
        self.assertEqual(self.studio.public(waiting)['queue_ahead'], 1)

    def test_absent_entry_falls_back_even_when_worker_busy(self):
        self.job(1, 'running'); waiting = self.job(2, 'queued'); self.job(3, 'queued')
        self.studio.queue.put(('production', 'comparison')); self.studio._worker_busy = True
        self.assertEqual(self.studio.public(waiting)['queue_ahead'], 1)

    def test_worker_clears_busy_after_success_and_failure(self):
        for fails in (False, True):
            with self.subTest(fails=fails):
                job = self.job(1, 'queued')
                def run(job):
                    self.assertTrue(self.studio._worker_busy)
                    if fails: raise ValueError('worker failure')
                with patch.object(self.studio.queue, 'get', side_effect=[('generate', job['id']), KeyboardInterrupt]), patch.object(self.studio, '_run', side_effect=run), patch.object(self.studio, 'record_job_failure') as failure:
                    with self.assertRaises(KeyboardInterrupt): self.studio._work()
                self.assertFalse(self.studio._worker_busy)
                self.assertEqual(failure.call_count, int(fails))


class QueueAheadSkipsSettledEntries(unittest.TestCase):
    setUp = fixture.LookTests.setUp

    def test_a_cancelled_run_left_in_the_queue_is_not_counted(self):
        make = lambda: self.studio.jobs[self.studio.create_job({'preset_id': self.studio.catalog()['presets'][0]['id'], 'controls': {}}, enqueue=True)['id']]
        first, second, third = make(), make(), make()
        for job in (first, second, third): job['status'] = 'queued'
        second['status'] = 'cancelled'
        self.assertEqual(self.studio.public(third)['queue_ahead'], 1, 'only the first run is really ahead')


if __name__ == '__main__': unittest.main()
