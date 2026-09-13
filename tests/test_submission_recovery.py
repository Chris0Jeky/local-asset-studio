"""Restart/abandonment evidence contracts; no live ComfyUI or GPU."""
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

import test_production as fixtures
from test_server import FakeStudio, server
import submission_evidence

IDLE={'queue_running':[],'queue_pending':[]}
DONE=lambda identifier: {identifier:{'status':{'status_str':'success'},'outputs':{}}}


class SubmissionRecoveryTests(unittest.TestCase):
    setUp=fixtures.ProductionTests.setUp
    tearDown=fixtures.ProductionTests.tearDown
    intent=fixtures.ProductionTests.intent
    post_count=fixtures.ProductionTests.post_count

    def waiting_project(self):
        studio=FakeStudio(self.root,[]);p=studio.production.create(self.intent(values=[1]))
        studio.production.start(p['id'])
        with patch.object(studio,'_wait_for_queue',side_effect=KeyboardInterrupt('restart before POST')):
            with self.assertRaises(KeyboardInterrupt):studio.production.run(p['id'])
        job=next(iter(studio.jobs.values()))
        self.assertEqual(job['status'],'waiting');self.assertEqual(self.post_count(studio),0)
        return studio,p['id'],job

    def test_repeated_waiting_restarts_reuse_identity_and_one_reservation(self):
        studio,identifier,job=self.waiting_project();identity=job['id']
        for _ in range(3):
            studio=FakeStudio(self.root,[]);job=studio.jobs[identity]
            self.assertEqual(job['status'],'not_submitted');self.assertTrue(studio.public(job)['never_submitted'])
            self.assertTrue(studio.queue.empty());self.assertEqual(studio.requests,[])
            studio.production.resume(identifier)
            with patch.object(studio,'_wait_for_queue',side_effect=KeyboardInterrupt('still waiting')):
                with self.assertRaises(KeyboardInterrupt):studio.production.run(identifier)
            self.assertEqual(studio.production.get(identifier)['budget'],{'allowance':2,'reserved':1})
        studio=FakeStudio(self.root,[IDLE,{'prompt_id':'only-post'},DONE('only-post')])
        studio.production.resume(identifier);studio.production.run(identifier)
        self.assertEqual(list(studio.jobs),[identity]);self.assertEqual(self.post_count(studio),1)
        self.assertEqual(studio.production.get(identifier)['state']['status'],'awaiting_review')
        self.assertEqual(studio.production.get(identifier)['budget']['reserved'],1)

    def test_queued_observation_is_never_reclassified_or_reposted(self):
        studio=FakeStudio(self.root,[IDLE,{'prompt_id':'known'},URLError('lost history')])
        p=studio.production.create(self.intent(values=[1]));studio.production.start(p['id']);studio.production.run(p['id'])
        job=next(iter(studio.jobs.values()));studio.resume_job(job['id'])
        self.assertEqual(job['status'],'queued')
        restarted=FakeStudio(self.root,[DONE('known')]);restored=restarted.jobs[job['id']]
        self.assertEqual(restored['status'],'uncertain');self.assertFalse(restarted.public(restored)['never_submitted'])
        with self.assertRaisesRegex(server.StudioError,'never submitted'):restarted._run(restored)
        restarted.production.resume(p['id']);restarted.production.run(p['id'])
        self.assertEqual(restored['status'],'completed');self.assertEqual(self.post_count(restarted),0)

    def test_classifier_requires_explicit_empty_evidence_and_absent_marker(self):
        clean={'status':'waiting','prompt_ids':[],'submissions':[],'outputs':[]}
        self.assertTrue(submission_evidence.never_submitted(clean))
        for field in ('prompt_ids','submissions','outputs'):
            for value in (None,{},'',False,['evidence']):
                with self.subTest(field=field,value=value):
                    self.assertFalse(submission_evidence.never_submitted(dict(clean,**{field:value})))
            missing=dict(clean);missing.pop(field);self.assertFalse(submission_evidence.never_submitted(missing))
        for marker in (None,{},False,{'index':0}):
            self.assertFalse(submission_evidence.never_submitted(dict(clean,pending_submission=marker)))
        for status in ('submitting','running','failed','partial','abandoned'):
            self.assertFalse(submission_evidence.never_submitted(dict(clean,status=status)))

    def test_legacy_uncertain_without_post_can_recover_but_empty_marker_cannot(self):
        studio,identifier,job=self.waiting_project()
        job.update(status='uncertain');studio._save(job)
        restored=FakeStudio(self.root,[]);self.assertEqual(restored.jobs[job['id']]['status'],'not_submitted')
        job.update(pending_submission={});studio._save(job)
        restored=FakeStudio(self.root,[]);self.assertEqual(restored.jobs[job['id']]['status'],'uncertain')
        restored.production.resume(identifier);restored.production.run(identifier)
        self.assertEqual(restored.production.get(identifier)['state']['status'],'uncertain');self.assertEqual(restored.requests,[])
        self.assertTrue(restored.public(restored.jobs[job['id']])['has_pending_submission'])

    def test_changed_recovered_graph_is_rejected_without_rebuilding_or_posting(self):
        studio,identifier,job=self.waiting_project();job['graph']['1']['inputs']['seed']=456;studio._save(job)
        restarted=FakeStudio(self.root,[]);restarted.production.resume(identifier)
        with self.assertRaisesRegex(ValueError,'recovered recipe changed'):restarted.production.run(identifier)
        self.assertEqual(restarted.requests,[]);self.assertEqual(restarted.production.get(identifier)['budget']['reserved'],1)

    def test_changed_bindings_and_abandonment_during_recovery_cannot_submit(self):
        studio,identifier,job=self.waiting_project();studio=FakeStudio(self.root,[]);job=studio.jobs[job['id']]
        studio.production.resume(identifier)
        original=copy.deepcopy(job['seed_bindings']);job['seed_bindings']=[['2','width']]
        with self.assertRaisesRegex(ValueError,'bindings changed'):studio.production.run(identifier)
        job['seed_bindings']=original
        prepare=studio.prepare
        def abandon_before_dispatch(*args,**kwargs):
            result=prepare(*args,**kwargs);studio.abandon_job(job['id'],'Operator abandoned during preflight');return result
        with patch.object(studio,'prepare',side_effect=abandon_before_dispatch):
            with self.assertRaisesRegex(ValueError,'disposition changed'):studio.production.run(identifier)
        self.assertEqual(job['status'],'abandoned');self.assertEqual(studio.requests,[])

    def test_unknown_abandonment_is_explicit_durable_and_preserves_receipts(self):
        studio=FakeStudio(self.root,[IDLE,URLError('POST accepted, response lost')])
        p=studio.production.create(self.intent(values=[1]));studio.production.start(p['id']);studio.production.run(p['id'])
        job=next(iter(studio.jobs.values()));directory=studio.runs/job['id']
        originals={name:(directory/name).read_bytes() for name in ('recipe.json','workflow.json')}
        pending=copy.deepcopy(job['pending_submission']);before=studio.queue.qsize()
        public=studio.public(job);self.assertTrue(public['can_abandon']);self.assertTrue(public['abandon_requires_acknowledgement'])
        self.assertNotIn('pending_submission',public)
        for ack in (False,'true',1,None):
            with self.assertRaisesRegex(server.StudioError,'Acknowledge'):studio.abandon_job(job['id'],'Preserve lost receipt',ack)
        result=studio.abandon_job(job['id'],'Preserve lost receipt',True)
        self.assertEqual(result['status'],'abandoned');self.assertEqual(result['abandonment']['basis'],'outcome_unknown')
        self.assertFalse(result['abandonment']['remote_cancelled']);self.assertEqual(job['pending_submission'],pending)
        self.assertEqual(studio.queue.qsize(),before);self.assertEqual(self.post_count(studio),1)
        self.assertEqual(result,studio.abandon_job(job['id'],'Preserve lost receipt',True))
        with self.assertRaisesRegex(server.StudioError,'already'):studio.abandon_job(job['id'],'Changed reason',True)
        restarted=FakeStudio(self.root,[]);restored=restarted.jobs[job['id']]
        self.assertEqual(restored['abandonment'],result['abandonment']);self.assertEqual(restored['pending_submission'],pending)
        for name,data in originals.items():self.assertEqual((directory/name).read_bytes(),data)
        with self.assertRaises(server.StudioError):restarted.resume_job(job['id'])
        with self.assertRaises(server.StudioError):restarted._run(restored)
        restarted.production.resume(p['id']);restarted.production.run(p['id'])
        self.assertEqual(restarted.production.get(p['id'])['state']['status'],'failed')
        self.assertEqual(restarted.production.get(p['id'])['budget']['reserved'],1);self.assertEqual(restarted.requests,[])
        # The local dead-end is released, but backend switching STILL observes the
        # real queue and refuses busy or unknown queues. No process can be stopped here.
        self.assertFalse(restarted.backends._local_work())
        with patch.object(restarted.backends,'available',return_value=True), \
             patch.object(restarted.backends,'_check_retained_startup'), \
             patch.object(restarted.backends,'_check_startup_processes'), \
             patch.object(restarted.backends,'request',return_value={'queue_running':[['foreign']],'queue_pending':[]}):
            with self.assertRaisesRegex(ValueError,'queue was preserved'):restarted.backends.switch('hidream')
        self.assertFalse(restarted.backends.busy)

    def test_never_submitted_abandonment_and_failed_publication_keep_evidence(self):
        studio,identifier,job=self.waiting_project();studio=FakeStudio(self.root,[]);job=studio.jobs[job['id']]
        before=copy.deepcopy(job);statefile=studio.runs/job['id']/'state.json';disk=statefile.read_bytes()
        with patch.object(studio,'_write_json_atomic',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):studio.abandon_job(job['id'],'No longer needed')
        self.assertEqual(job,before);self.assertEqual(statefile.read_bytes(),disk)
        result=studio.abandon_job(job['id'],'No longer needed')
        self.assertEqual(result['abandonment']['basis'],'never_submitted');self.assertFalse(result['has_pending_submission'])
        self.assertEqual(studio.production.get(identifier)['budget']['reserved'],1);self.assertEqual(studio.requests,[])

    def test_known_or_active_jobs_cannot_be_abandoned(self):
        studio=FakeStudio(self.root,[]);job=studio.jobs[studio.create_job({'preset_id':'demo','controls':{}},enqueue=False)['id']]
        for status in ('queued','waiting','submitting','running','completed'):
            job['status']=status
            with self.assertRaises(server.StudioError):studio.abandon_job(job['id'],'Do not stop active work',True)
        job.update(status='uncertain',prompt_ids=['retained'],submissions=[{'prompt_id':'retained','status':'observing'}])
        with self.assertRaises(server.StudioError):studio.abandon_job(job['id'],'Use known tracking instead',True)
        self.assertEqual(studio.requests,[])

    def test_unknown_batch_tail_cannot_be_observed_into_false_completion(self):
        studio=FakeStudio(self.root,[]);job=studio.jobs[studio.create_job({'preset_id':'demo','controls':{}},enqueue=False)['id']]
        job.update(status='uncertain',prompt_ids=['known'],submissions=[{'prompt_id':'known','status':'observing'}],pending_submission={'index':1})
        with self.assertRaisesRegex(server.StudioError,'unknown'):studio.resume_job(job['id'])
        with self.assertRaisesRegex(server.StudioError,'unknown'):studio._resume(job)
        self.assertEqual(job['status'],'uncertain');self.assertEqual(studio.requests,[])
