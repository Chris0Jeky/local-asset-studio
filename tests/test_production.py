"""Exercise budget and response-loss behavior without touching a live GPU."""
import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from test_server import server, FakeStudio, GRAPH, PRESET


class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        for name in ('presets','workflows/api','config','fake-comfy/input'):(self.root/name).mkdir(parents=True,exist_ok=True)
        (self.root/'config/local.json').write_text(json.dumps({'comfy_root':str(self.root/'fake-comfy')}))
        (self.root/'presets/catalog.json').write_text(json.dumps({'presets':[PRESET]}))
        (self.root/'workflows/api/demo-api.json').write_text(json.dumps(GRAPH))
        self.patches=[patch.object(threading.Thread,'start',lambda *_:None),
            patch.object(server.Studio,'production_preflight',lambda *a:{'test_bundle':True}),
            patch.object(server.Studio,'check_production_bundle',lambda *a:None),
            patch.object(server.Studio,'validate_graph',lambda *a:None)]
        for p in self.patches:p.start()
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()
    def intent(self,**extra):
        return dict({'name':'Seed comparison','recipe':{'preset_id':'demo','controls':{}},'axis':'seed','values':[1,2],'max_generations':2},**extra)
    def post_count(self,studio):return sum(1 for args,_ in studio.requests if args[0]=='/prompt')

    def test_branch_budget_and_start_are_atomic_and_not_reset(self):
        studio=FakeStudio(self.root,[]);lab=studio.production
        parent=lab.create(self.intent());child=lab.create(self.intent(parent_project=parent['id']))
        lab.start(parent['id'])
        with self.assertRaisesRegex(ValueError,'already been started'):lab.start(parent['id'])
        with self.assertRaisesRegex(ValueError,'budget is exhausted'):lab.start(child['id'])
        self.assertEqual(lab.get(child['id'])['budget'],{'allowance':2,'reserved':2})
        self.assertEqual(studio.queue.qsize(),1)

    def test_lost_submission_response_survives_restart_without_duplicate(self):
        studio=FakeStudio(self.root,[{'queue_running':[],'queue_pending':[]},URLError('lost POST response')])
        lab=studio.production;p=lab.create(self.intent(values=[1]));lab.start(p['id']);lab.run(p['id'])
        self.assertEqual(self.post_count(studio),1)
        self.assertEqual(lab.get(p['id'])['state']['status'],'uncertain')
        self.assertTrue(next(iter(studio.jobs.values()))['pending_submission'])
        restarted=FakeStudio(self.root,[])
        restarted.production.resume(p['id']);restarted.production.run(p['id'])
        self.assertEqual(self.post_count(restarted),0)
        self.assertEqual(len(restarted.jobs),1)
        self.assertEqual(restarted.production.get(p['id'])['state']['status'],'uncertain')

    def test_known_prompt_is_observed_then_only_unstarted_stage_runs(self):
        studio=FakeStudio(self.root,[{'queue_running':[],'queue_pending':[]},{'prompt_id':'known-a'},URLError('observation lost')])
        p=studio.production.create(self.intent());studio.production.start(p['id']);studio.production.run(p['id'])
        restarted=FakeStudio(self.root,[{'known-a':{'status':{'status_str':'success'},'outputs':{}}},
            {'queue_running':[],'queue_pending':[]},{'prompt_id':'known-b'},
            {'known-b':{'status':{'status_str':'success'},'outputs':{}}}])
        restarted.production.resume(p['id']);restarted.production.run(p['id'])
        self.assertEqual(self.post_count(restarted),1)
        self.assertEqual(len(restarted.jobs),2)
        self.assertEqual(restarted.production.get(p['id'])['state']['status'],'awaiting_review')
        self.assertEqual(restarted.production.get(p['id'])['budget']['reserved'],2)

    def test_blueprints_and_filename_axes_cannot_be_submitted(self):
        studio=FakeStudio(self.root,[])
        with self.assertRaisesRegex(ValueError,'blueprints'):studio.production.create(self.intent(workflow=GRAPH))
        with self.assertRaisesRegex(ValueError,'numeric'):studio.production.create(self.intent(axis='lora',values=['another.safetensors']))
        self.assertEqual(len(studio.jobs),0);self.assertEqual(studio.queue.qsize(),0)

    def test_changed_plan_and_stop_before_first_stage_never_generate(self):
        studio=FakeStudio(self.root,[]);lab=studio.production;p=lab.create(self.intent())
        lab.start(p['id']);lab.stop(p['id']);lab.run(p['id'])
        self.assertEqual(lab.get(p['id'])['state']['status'],'stopped');self.assertFalse(studio.jobs)
        with lab.connect() as db:
            record=lab._get(p['id'],db);record['plan']['stages'][0]['graph']['1']['inputs']['text']='changed'
            db.execute('UPDATE projects SET plan=? WHERE id=?',(json.dumps(record['plan']),p['id']))
        with self.assertRaisesRegex(ValueError,'plan changed'):lab.run(p['id'])
        self.assertEqual(self.post_count(studio),0)
