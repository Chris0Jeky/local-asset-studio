"""Minimal repros using pre-existing APIs: both fail on f85c00e6 (before fixes)."""
import unittest
from urllib.error import URLError
import test_production as fixtures
from test_server import FakeStudio


class OldestIssueRegressions(unittest.TestCase):
    setUp=fixtures.ProductionTests.setUp
    tearDown=fixtures.ProductionTests.tearDown
    intent=fixtures.ProductionTests.intent

    def test_94_waiting_without_post_recovers_as_not_submitted(self):
        studio=FakeStudio(self.root,[])
        job=studio.jobs[studio.create_job({'preset_id':'demo','controls':{}},enqueue=False)['id']]
        job['status']='waiting';studio._save(job)
        restarted=FakeStudio(self.root,[])
        self.assertEqual(restarted.jobs[job['id']]['status'],'not_submitted')
        self.assertEqual(restarted.requests,[]);self.assertTrue(restarted.queue.empty())

    def test_93_expired_legacy_deadline_does_not_prevent_known_prompt_reconciliation(self):
        studio=FakeStudio(self.root,[{'queue_running':[],'queue_pending':[]},{'prompt_id':'retained'},URLError('lost history')])
        p=studio.production.create(self.intent(max_seconds=60));studio.production.start(p['id']);studio.production.run(p['id'])
        state=studio.production._get(p['id'])['state'];state.pop('time_budget',None);state['started_at']=1
        studio.production._state(p['id'],state)
        restarted=FakeStudio(self.root,[{'retained':{'status':{'status_str':'success'},'outputs':{}}}])
        restarted.production.resume(p['id']);restarted.production.run(p['id'])
        self.assertEqual(next(iter(restarted.jobs.values()))['status'],'completed')
        self.assertFalse(any(args[0]=='/prompt' for args,_ in restarted.requests))


if __name__=='__main__':unittest.main()
