"""Persisted attempt links cannot borrow another project's mixed-batch evidence."""
import copy
import unittest
from unittest.mock import patch

import test_mixed_batch as fixtures
from test_server import FakeStudio, server


class MixedBatchOwnerTests(unittest.TestCase):
    def setUp(self):
        self.case=fixtures.MixedBatchTests();self.case.setUp();self.addCleanup(self.case.doCleanups)
        self.studio=self.case.studio;self.lab=self.studio.production
        self.owner=self.case.owning_project()

    def dispose(self):
        self.case.command('dispose',self.case.payload('dispose-owner-1',reason='Keep all evidence',acknowledge_unknown=True))

    def assert_held(self,identifier):
        before=copy.deepcopy(self.lab._get(identifier));jobs=copy.deepcopy(self.studio.jobs)
        files=self.case.files();requests=list(self.studio.requests)
        public=self.lab.get(identifier)
        self.assertFalse(public['can_reconcile_batch'],'Mislinked evidence offered local reconciliation')
        self.assertIn('ownership',public.get('batch_reconciliation_error',''))
        with patch.object(self.studio,'require_worker',side_effect=AssertionError('No admission')), \
             patch.object(self.lab,'_comparison_clock',side_effect=AssertionError('No clock charge')), \
             patch.object(self.studio,'check_production_bundle',side_effect=AssertionError('No network preflight')):
            with self.assertRaisesRegex(ValueError,'ownership'):self.lab.resume(identifier)
            with self.assertRaisesRegex(ValueError,'ownership'):self.lab.run(identifier)
        self.assertEqual(self.lab._get(identifier),before)
        self.assertEqual(self.studio.jobs,jobs);self.assertEqual(self.case.files(),files)
        self.assertEqual(self.studio.requests,requests);self.assertTrue(self.studio.queue.empty())

    def test_foreign_disposition_cannot_fail_another_project_even_with_matching_graph(self):
        self.dispose();other=self.lab.create(self.case.fixture.intent())['id']
        self.lab._mutate(other,status='uncertain',attempts={'0':{'job_id':self.case.job['id']}})
        self.assert_held(other)
        self.assertTrue(self.lab.get(self.owner)['can_reconcile_batch'])

    def test_missing_owner_is_not_adopted_as_a_legacy_job(self):
        self.case.job.pop('project_id');self.dispose();self.assert_held(self.owner)

    def test_stage_must_be_a_canonical_in_range_index(self):
        self.dispose()
        for index in ('-1','00','2','not-a-stage'):
            with self.subTest(index=index):
                self.lab._mutate(self.owner,attempts={index:{'job_id':self.case.job['id']}})
                self.assert_held(self.owner)

    def test_same_job_cannot_supply_two_stage_dispositions(self):
        self.dispose();self.lab._mutate(self.owner,attempts={str(i):{'job_id':self.case.job['id']} for i in range(2)})
        self.assert_held(self.owner)

    def test_retained_graph_must_match_the_pinned_stage(self):
        self.case.job['graph']['unplanned']={'class_type':'Extra','inputs':{}}
        self.dispose();self.assert_held(self.owner)

    def test_preset_and_backend_must_match_the_plan(self):
        original=copy.deepcopy(self.case.job)
        for key,value in (('preset_id','another-recipe'),('comfy_url','http://127.0.0.1:8192')):
            with self.subTest(key=key):
                self.case.job.clear();self.case.job.update(copy.deepcopy(original));self.case.job[key]=value
                self.dispose();self.assert_held(self.owner)

    def test_backend_storage_root_must_match_the_plan_even_when_url_matches(self):
        self.case.job['comfy_root']=str(self.case.root/'different-comfy-storage')
        self.dispose();self.assert_held(self.owner)

    def test_missing_backend_storage_root_is_not_adopted_as_legacy_evidence(self):
        self.case.job.pop('comfy_root');self.dispose();self.assert_held(self.owner)

    def test_mapping_key_must_match_the_retained_job_identity(self):
        self.dispose();self.studio.jobs['alias']=self.case.job
        self.lab._mutate(self.owner,attempts={'0':{'job_id':'alias'}});self.assert_held(self.owner)

    def test_foreign_link_stays_held_after_restart_with_receipts_and_budget_unchanged(self):
        self.dispose();other=self.lab.create(self.case.fixture.intent())['id']
        self.lab._mutate(other,status='uncertain',attempts={'0':{'job_id':self.case.job['id']}})
        before=self.lab.get(other)['budget'];files=self.case.files()
        restarted=FakeStudio(self.case.root,[])
        self.assertFalse(restarted.production.get(other)['can_reconcile_batch'])
        with self.assertRaisesRegex(ValueError,'ownership'):restarted.production.resume(other)
        self.assertEqual(restarted.production.get(other)['budget'],before)
        self.assertEqual(self.case.files(),files);self.assertEqual(restarted.requests,[])
        self.assertTrue(restarted.queue.empty())

    def test_matching_legacy_job_needs_no_new_fields_or_deterministic_id(self):
        # Existing records already bind owner, graph, preset and backend. Do not
        # invent a new mandatory receipt field to repair their association.
        self.dispose();before=self.lab.get(self.owner);files=self.case.files()
        self.assertTrue(before['can_reconcile_batch'])
        first=self.lab.resume(self.owner);second=self.lab.resume(self.owner)
        self.assertEqual(first,second);self.assertEqual(first['state']['status'],'failed')
        self.assertEqual(first['budget'],before['budget']);self.assertEqual(self.case.files(),files)
        self.assertFalse(first['state']['batch_terminal_reconciliation']['new_work_authorized'])
        self.assertTrue(self.studio.queue.empty());self.case.no_posts_since(2)


if __name__=='__main__':unittest.main()
