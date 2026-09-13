"""Deterministic active-time/restart tests without waiting or generating images."""
import copy
import unittest
from unittest.mock import patch
from urllib.error import URLError

import test_production as fixtures
from test_server import FakeStudio
import production_clock as clock

IDLE={'queue_running':[],'queue_pending':[]}
DONE=lambda identifier: {identifier:{'status':{'status_str':'success'},'outputs':{}}}


class ClockContractTests(unittest.TestCase):
    def initial(self):return clock.read({'max_seconds':60},{})

    def test_new_legacy_and_interrupted_time_are_distinct(self):
        fresh=self.initial();self.assertEqual(clock.remaining(fresh),60)
        legacy=clock.read({'max_seconds':60},{'started_at':123})
        self.assertEqual(legacy['measured_seconds'],0);self.assertEqual(legacy['unmeasured_seconds'],60)
        self.assertEqual(legacy['recovery_reason'],'legacy_unmetered')
        active=clock.begin(fresh,'owner');active=clock.checkpoint(active,'owner',12)
        recovered=clock.recover(active)
        self.assertEqual(recovered['measured_seconds'],12);self.assertEqual(recovered['unmeasured_seconds'],48)
        self.assertEqual(clock.remaining(recovered),0);self.assertNotIn('active',recovered)
        self.assertEqual(clock.recover(recovered),recovered)

    def test_checkpoints_add_only_deltas_and_do_not_refill_on_resume(self):
        value=clock.begin(self.initial(),'first')
        value=clock.checkpoint(value,'first',10);value=clock.checkpoint(value,'first',15,finish=True)
        for index in range(5):
            value=clock.begin(value,str(index));value=clock.checkpoint(value,str(index),8,finish=True)
        self.assertEqual(value['measured_seconds'],65);self.assertEqual(clock.remaining(value),0)
        self.assertEqual(value['limit_seconds'],60)

    def test_invalid_measurements_or_interval_owner_do_not_mutate_ledger(self):
        value=clock.begin(self.initial(),'owner');before=copy.deepcopy(value)
        for delta in (-1,True,'10',float('inf'),float('nan')):
            with self.subTest(delta=delta),self.assertRaises(ValueError):clock.checkpoint(value,'owner',delta)
        with self.assertRaises(ValueError):clock.checkpoint(value,'another-owner',2)
        with self.assertRaises(ValueError):clock.begin(value,'second')
        self.assertEqual(value,before)

    def test_retained_malformed_ledger_cannot_become_a_fresh_allowance(self):
        for value in (None,{},False,dict(self.initial(),measured_seconds=float('nan')),
                      dict(self.initial(),revision=True),dict(self.initial(),limit_seconds=14401),
                      dict(self.initial(),active={'token':'bad','reserved_seconds':61})):
            with self.subTest(value=value),self.assertRaises(ValueError):clock.read({'max_seconds':60},{'time_budget':value})

    def test_extensions_are_additive_bounded_and_cannot_erase_charge(self):
        value=clock.read({'max_seconds':60},{'started_at':123})
        updated=clock.extend(value,120,'Approved next two stages',456)
        self.assertEqual(updated['limit_seconds'],180);self.assertEqual(updated['unmeasured_seconds'],60)
        self.assertEqual(updated['amendments'][0]['previous_limit_seconds'],60)
        self.assertEqual(value['limit_seconds'],60)
        for seconds in (0,59,True,'60',60.1,14400):
            with self.subTest(seconds=seconds),self.assertRaises(ValueError):clock.extend(value,seconds,'Reason',456)
        for reason in ('',None,'x'*1001):
            with self.assertRaises(ValueError):clock.extend(value,60,reason,456)
        with self.assertRaises(ValueError):clock.extend(clock.begin(value,'active'),60,'Reason',456)


class ProductionTimeRecoveryTests(unittest.TestCase):
    setUp=fixtures.ProductionTests.setUp
    tearDown=fixtures.ProductionTests.tearDown
    intent=fixtures.ProductionTests.intent
    post_count=fixtures.ProductionTests.post_count

    def finish_after(self,studio,now,seconds,after=None):
        def finish(job):
            now[0]+=seconds;job.update(status='completed',message='Inert completed fixture',prompt_ids=['fixture-'+job['id']])
            job['submissions']=[{'prompt_id':job['prompt_ids'][0],'status':'completed'}]
            studio._save(job)
            if after:after()
        return finish

    def test_repeated_resumes_do_not_reset_exhausted_allowance_or_add_jobs(self):
        studio=FakeStudio(self.root,[]);p=studio.production.create(self.intent(values=[1,2,3],max_generations=3,max_seconds=60));identifier=p['id']
        now=[10.0]
        with patch('production.time.monotonic',side_effect=lambda:now[0]),patch.object(studio,'_run',side_effect=self.finish_after(studio,now,70)) as run:
            studio.production.start(identifier);studio.production.run(identifier)
            initial=studio.production.get(identifier);started=initial['state']['started_at']
            self.assertEqual(initial['state']['stop_reason'],'time_budget');self.assertEqual(run.call_count,1)
            for _ in range(3):
                now[0]+=86400  # downtime must not be charged, or refunded as a fresh budget
                studio.production.resume(identifier);studio.production.run(identifier)
            current=studio.production.get(identifier)
            self.assertEqual(run.call_count,1);self.assertEqual(len(studio.jobs),1)
            self.assertEqual(current['state']['time_budget']['measured_seconds'],70)
            self.assertEqual(current['state']['started_at'],started)
            self.assertEqual(current['budget'],{'allowance':3,'reserved':3})

    def test_operator_stop_then_next_day_resume_preserves_remaining_active_time(self):
        studio=FakeStudio(self.root,[]);p=studio.production.create(self.intent(max_seconds=60));identifier=p['id'];now=[10.0]
        with patch('production.time.monotonic',side_effect=lambda:now[0]):
            studio.production.start(identifier)
            with patch.object(studio,'_run',side_effect=self.finish_after(studio,now,15,lambda:studio.production.stop(identifier))):studio.production.run(identifier)
            before=studio.production.get(identifier);self.assertEqual(before['state']['stop_reason'],'operator')
            self.assertEqual(before['state']['time_budget']['measured_seconds'],15)
            now[0]+=86400;restarted=FakeStudio(self.root,[])
            self.assertTrue(restarted.queue.empty());restarted.production.resume(identifier)
            with patch.object(restarted,'_run',side_effect=self.finish_after(restarted,now,20)) as run:restarted.production.run(identifier)
            current=restarted.production.get(identifier)
            self.assertEqual(run.call_count,1);self.assertEqual(current['state']['status'],'awaiting_review')
            self.assertEqual(current['state']['time_budget']['measured_seconds'],35)
            self.assertEqual(current['state']['time_budget']['unmeasured_seconds'],0)

    def test_exhausted_time_still_harvests_known_prompt_but_never_starts_next(self):
        studio=FakeStudio(self.root,[IDLE,{'prompt_id':'retained'},URLError('lost observation')])
        p=studio.production.create(self.intent(max_seconds=60));identifier=p['id'];studio.production.start(identifier);studio.production.run(identifier)
        state=studio.production._get(identifier)['state'];value=state['time_budget'];value.update(measured_seconds=60,unmeasured_seconds=0)
        studio.production._mutate(identifier,time_budget=value)
        restarted=FakeStudio(self.root,[DONE('retained')]);restarted.production.resume(identifier);restarted.production.run(identifier)
        current=restarted.production.get(identifier)
        self.assertEqual(next(iter(restarted.jobs.values()))['status'],'completed')
        self.assertEqual(self.post_count(restarted),0);self.assertEqual(len(restarted.jobs),1)
        self.assertEqual(current['state']['stop_reason'],'time_budget');self.assertEqual(current['budget']['reserved'],2)

    def test_explicit_revisioned_extension_keeps_pinned_plan_and_never_auto_queues(self):
        studio=FakeStudio(self.root,[]);p=studio.production.create(self.intent(max_seconds=60));identifier=p['id'];now=[10.0]
        with patch('production.time.monotonic',side_effect=lambda:now[0]):
            studio.production.start(identifier)
            with patch.object(studio,'_run',side_effect=self.finish_after(studio,now,70)):studio.production.run(identifier)
            path=studio.production.root/identifier/'plan.json';original=path.read_bytes()
            before=studio.production.get(identifier);revision=before['state']['time_budget']['revision'];queued=studio.queue.qsize()
            command={'expected_revision':revision,'seconds':60,'reason':'Complete the remaining reserved candidate'}
            updated=studio.production.extend_time(identifier,command)
            self.assertEqual(updated['state']['status'],'stopped');self.assertEqual(updated['state']['time_budget']['limit_seconds'],120)
            self.assertEqual(updated['state']['time_budget']['measured_seconds'],70);self.assertEqual(studio.queue.qsize(),queued)
            self.assertEqual(updated['budget'],before['budget']);self.assertEqual(path.read_bytes(),original)
            with self.assertRaisesRegex(ValueError,'conflict'):studio.production.extend_time(identifier,command)
            studio.production.resume(identifier)
            with self.assertRaisesRegex(ValueError,'inactive'):studio.production.extend_time(identifier,dict(command,expected_revision=updated['state']['time_budget']['revision']))
            with patch.object(studio,'_run',side_effect=self.finish_after(studio,now,20)) as run:studio.production.run(identifier)
            self.assertEqual(run.call_count,1);self.assertEqual(studio.production.get(identifier)['state']['status'],'awaiting_review')
            self.assertEqual(path.read_bytes(),original)

    def test_lost_active_interval_is_conservatively_charged_once_on_restart(self):
        studio=FakeStudio(self.root,[]);p=studio.production.create(self.intent(max_seconds=60));identifier=p['id'];studio.production.start(identifier)
        value=clock.checkpoint(clock.begin(clock.read({'max_seconds':60},{}),'lost-process'),'lost-process',20)
        studio.production._mutate(identifier,status='running',started_at=123,time_budget=value)
        restarted=FakeStudio(self.root,[]);after=restarted.production.get(identifier)['state']['time_budget']
        self.assertEqual(after['measured_seconds'],20);self.assertEqual(after['unmeasured_seconds'],40)
        self.assertEqual(after['remaining_seconds'],0);self.assertNotIn('active',after)
        again=FakeStudio(self.root,[]);self.assertEqual(again.production.get(identifier)['state']['time_budget'],after)
        again.production.resume(identifier);again.production.run(identifier)
        self.assertEqual(again.jobs,{});self.assertEqual(again.requests,[])

    def test_legacy_exhaustion_harvests_prompt_and_exposes_unknown_time(self):
        studio=FakeStudio(self.root,[IDLE,{'prompt_id':'legacy'},URLError('lost observation')])
        p=studio.production.create(self.intent(max_seconds=60));identifier=p['id'];studio.production.start(identifier);studio.production.run(identifier)
        state=studio.production._get(identifier)['state'];state.pop('time_budget');state['started_at']=1;studio.production._state(identifier,state)
        restarted=FakeStudio(self.root,[DONE('legacy')]);restarted.production.resume(identifier);restarted.production.run(identifier)
        after=restarted.production.get(identifier)
        self.assertEqual(after['state']['time_budget']['unmeasured_seconds'],60)
        self.assertEqual(after['state']['time_budget']['recovery_reason'],'legacy_unmetered')
        self.assertEqual(next(iter(restarted.jobs.values()))['status'],'completed');self.assertEqual(self.post_count(restarted),0)

    def test_ending_known_only_comparison_can_reach_review_despite_exhaustion(self):
        studio=FakeStudio(self.root,[IDLE,{'prompt_id':'only'},URLError('lost observation')])
        p=studio.production.create(self.intent(values=[1],max_seconds=60));identifier=p['id'];studio.production.start(identifier);studio.production.run(identifier)
        value=studio.production._get(identifier)['state']['time_budget'];value['measured_seconds']=120;studio.production._mutate(identifier,time_budget=value)
        restarted=FakeStudio(self.root,[DONE('only')]);restarted.production.resume(identifier)
        restarted.production.run(identifier)
        self.assertEqual(restarted.production.get(identifier)['state']['status'],'awaiting_review');self.assertEqual(self.post_count(restarted),0)

    def test_extension_validation_does_not_change_state_or_budget(self):
        studio=FakeStudio(self.root,[]);p=studio.production.create(self.intent(max_seconds=60));identifier=p['id']
        studio.production.start(identifier);studio.production._mutate(identifier,status='stopped')
        before=studio.production.get(identifier)
        for command in (None,[],{}, {'expected_revision':True,'seconds':60,'reason':'No'},
                        {'expected_revision':0,'seconds':float('nan'),'reason':'No'},
                        {'expected_revision':0,'seconds':60,'reason':''}):
            with self.subTest(command=command),self.assertRaises(ValueError):studio.production.extend_time(identifier,command)
        self.assertEqual(studio.production.get(identifier),before)
