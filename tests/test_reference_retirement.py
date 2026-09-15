"""A retired unknown request can never arrive later as a new inference."""
import copy
import unittest
from unittest.mock import patch
import test_reference_jobs as fixtures
import test_reference_job_http as http_fixtures
from studio_prompt.reference_jobs import ReferenceJobs


class ReferenceRetirementTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.ReferenceJobTests();self.f.setUp()
        self.addCleanup(self.f.doCleanups);self.addCleanup(self.f.tearDown)
        self.command={'workspace_id':self.f.scope,'request_id':self.f.payload['request_id']}

    def test_retire_unknown_prevents_late_create_and_does_not_queue(self):
        result=self.f.service.retire(self.command)
        self.assertEqual(result['state']['status'],'cancelled')
        self.assertTrue(result['state']['retired_without_dispatch'])
        self.assertFalse(result['state']['resource_hold']);self.assertEqual(result['state']['inference_attempts'],0)
        self.assertFalse(result['generation_submitted']);self.assertIsNone(result['result'])
        with self.assertRaisesRegex(ValueError,'retired'):self.f.create()
        self.assertTrue(self.f.studio_instance.queue.empty());self.assertEqual(self.f.calls,[])

    def test_repeated_retirement_and_restart_keep_identical_terminal_receipt(self):
        first=self.f.service.retire(self.command)
        self.assertEqual(self.f.service.retire(self.command),first)
        reopened=ReferenceJobs(self.f.studio_instance)
        self.assertEqual(reopened.get(self.f.scope,self.command['request_id']),first)
        self.assertEqual(reopened.retire(self.command),first)
        self.assertEqual(self.f.calls,[])

    def test_existing_operations_are_returned_without_changing_outcomes_or_holds(self):
        self.f.create()
        for status,hold in [('queued',False),('submitting',True),('uncertain',True),('completed',False)]:
            with self.f.studio_instance.assets.connection() as db:
                db.execute('BEGIN IMMEDIATE');state=self.f.service._state(self.f.service._row(db,self.command['request_id']))
                state.update(status=status,resource_hold=hold)
                self.f.service._save_state(db,self.command['request_id'],state)
            before=self.f.get()
            self.assertEqual(self.f.service.retire(self.command),before)
        self.assertEqual(self.f.calls,[])

    def test_retire_during_slow_intake_is_checked_again_at_commit(self):
        from studio_prompt.reference_jobs import _images
        def during_capture(*args):
            self.f.service.retire(self.command)
            return _images(*args)
        with patch('studio_prompt.reference_jobs._images',side_effect=during_capture):
            with self.assertRaisesRegex(ValueError,'retired'):self.f.create()
        self.assertTrue(self.f.get()['state']['retired_without_dispatch'])
        self.assertTrue(self.f.studio_instance.queue.empty());self.assertEqual(self.f.calls,[])

    def test_wrong_workspace_and_unknown_fields_never_write(self):
        for command in ({**self.command,'workspace_id':'a'*32},{**self.command,'cancel_model':True}):
            with self.subTest(command=command),self.assertRaises(ValueError):self.f.service.retire(command)
        with self.f.studio_instance.assets.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM reference_jobs_v1').fetchone()[0],0)

    def test_retirement_needs_no_model_configuration_but_obeys_retention_cap(self):
        del self.f.studio_instance.config['reference_helper']
        with patch('studio_prompt.reference_jobs.MAX_JOBS',0):
            with self.assertRaisesRegex(ValueError,'full'):self.f.service.retire(self.command)
        self.assertTrue(self.f.service.retire(self.command)['state']['retired_without_dispatch'])
        self.assertEqual(self.f.calls,[])


class ReferenceRetirementHttpTests(unittest.TestCase):
    def setUp(self):
        self.http=http_fixtures.ReferenceJobHttpTests();self.http.setUp();self.addCleanup(self.http.doCleanups)
        self.f=self.http.f;self.command={'workspace_id':self.f.scope,'request_id':self.f.payload['request_id']}

    def test_retire_and_status_use_real_http_without_inference(self):
        code,value=self.http.call('retire',self.command)
        self.assertEqual(code,200)
        self.assertEqual(self.http.call(self.http.status_path())[1],value)
        self.assertEqual(self.http.call('retire',self.command)[1],value)
        self.assertEqual(self.http.call('create',self.f.payload)[0],400)
        self.assertEqual(self.f.calls,[]);self.assertTrue(self.f.studio_instance.queue.empty())

    def test_retirement_requires_same_origin_and_exact_shape(self):
        self.assertEqual(self.http.call('retire',self.command,{'Origin':'https://elsewhere.invalid'})[0],403)
        self.assertEqual(self.http.call('retire',{**self.command,'forget':True})[0],400)
        self.assertEqual(self.http.call(self.http.status_path())[0],404)

    def test_slow_create_and_retire_race_through_real_http_threads(self):
        from studio_prompt.reference_jobs import _images
        retired=[]
        def delayed(*args):
            retired.append(self.http.call('retire',self.command))
            return _images(*args)
        with patch('studio_prompt.reference_jobs._images',side_effect=delayed):
            code,value=self.http.call('create',self.f.payload)
        self.assertEqual(code,400);self.assertIn('retired',value['error'])
        self.assertEqual(retired[0][0],200)
        self.assertTrue(self.http.call(self.http.status_path())[1]['state']['retired_without_dispatch'])
        self.assertEqual(self.f.calls,[]);self.assertTrue(self.f.studio_instance.queue.empty())
