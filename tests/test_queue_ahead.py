"""Queue position on waiting jobs (#1707): a read-only count of unfinished jobs created earlier."""
import unittest
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
        result = self.studio.public(waiting)
        self.assertEqual(result['queue_ahead'], 1); self.assertNotIn('PRIVATE-CANARY', repr(result))


if __name__ == '__main__': unittest.main()
