"""Exercise budget and response-loss behavior without touching a live GPU."""
import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from test_server import server, FakeStudio, GRAPH, PRESET, png


class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        for name in ('presets','workflows/api','config','fake-comfy/input'):(self.root/name).mkdir(parents=True,exist_ok=True)
        (self.root/'config/local.json').write_text(json.dumps({'comfy_root':str(self.root/'fake-comfy')}))
        (self.root/'presets/catalog.json').write_text(json.dumps({'presets':[PRESET]}))
        (self.root/'workflows/api/demo-api.json').write_text(json.dumps(GRAPH))
        self.patches=[patch.object(threading.Thread,'start',lambda *_:None),
            patch.object(server.Studio,'production_preflight',lambda s,*a:{'test_bundle':True,'comfy_url':s.comfy_url}),
            patch.object(server.Studio,'check_production_bundle',lambda *a:None),
            patch.object(server.Studio,'validate_graph',lambda *a:None)]
        for p in self.patches:p.start()
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()
    def intent(self,**extra):
        return dict({'name':'Seed comparison','recipe':{'preset_id':'demo','controls':{}},'axis':'seed','values':[1,2],'max_generations':2},**extra)
    def post_count(self,studio):return sum(1 for args,_ in studio.requests if args[0]=='/prompt')

    def test_native_job_is_persisted_before_blender_and_resume_never_repeats(self):
        import articulated
        studio=FakeStudio(self.root,[])
        operation={'operation':articulated.OPERATION,'intent':{'name':'Chest'},'options':{},'sha256':'pinned'}
        with patch.object(articulated,'prepare',return_value=operation):project=studio.production.articulated({})
        def lost_parent(s,identifier,plan):
            attempt=s.production.get(identifier)['state']['attempts']['0']
            self.assertTrue((s.runs/attempt['job_id']/'state.json').is_file())
            (s.production.root/identifier/'articulated-job.json').write_text('{}')
            raise KeyboardInterrupt('Simulated parent loss')
        studio.production.start(project['id'])
        with patch.object(articulated,'run',side_effect=lost_parent):
            with self.assertRaises(KeyboardInterrupt):studio.production.run(project['id'])
        restarted=FakeStudio(self.root,[]);restarted.production.resume(project['id'])
        recovered={'job':articulated._native_job(project['id'],operation),'artifacts':[],'measurements':{},'limitations':[]}
        recovered['job'].update(status='completed',outputs=[])
        with patch.object(articulated,'run') as run,patch.object(articulated,'recover',return_value=recovered) as recover:
            restarted.production.run(project['id'])
        run.assert_not_called();recover.assert_called_once()
        self.assertEqual(restarted.production.get(project['id'])['state']['status'],'completed')

    def test_krita_export_pins_runtime_and_packs_native_document_without_generation(self):
        import zipfile
        from native_exports import krita_roundtrip
        (self.root/'scripts').mkdir()
        for name in ('game_asset_media.py','godot_asset_adapter.py'):
            (self.root/'scripts'/name).write_bytes((Path(__file__).parents[1]/'scripts'/name).read_bytes())
        studio=FakeStudio(self.root,[])
        asset=studio.import_image('paint.png','image/png',png())['asset']
        runtime={'path':str(self.root/'krita.exe'),'sha256':'a'*64}
        def save_native(source,target,configured):
            self.assertTrue(source.is_file());target.mkdir()
            (target/'roundtrip.kra').write_bytes(b'native proof fixture')
            return {'native_kra_save_reopen_proved':True,'kra':{'layers':[{'name':'Paint'}]}}
        with patch.object(krita_roundtrip,'preflight',return_value=runtime),patch.object(krita_roundtrip,'execute',side_effect=save_native) as execute:
            project=studio.production.native({'kind':'ora','ids':[asset['id']],'options':{'clip':'paint-study'},'verify_krita':True})
            self.assertEqual(execute.call_count,0)
            studio.production.start(project['id']);studio.production.run(project['id'])
        execute.assert_called_once()
        state=studio.production.get(project['id'])['state']
        self.assertTrue(state['krita']['native_kra_save_reopen_proved'])
        with zipfile.ZipFile(studio.production.root/project['id']/'export.zip') as archive:
            self.assertIn('krita/roundtrip.kra',archive.namelist());self.assertIn('layers.ora',archive.namelist())
        self.assertEqual(self.post_count(studio),0)
        with patch.object(krita_roundtrip,'preflight',return_value=runtime):
            changed=studio.production.native({'kind':'ora','ids':[asset['id']],'options':{'clip':'changed-krita'},'verify_krita':True})
        with patch.object(krita_roundtrip,'preflight',return_value=dict(runtime,sha256='b'*64)),patch.object(krita_roundtrip,'execute') as execute:
            studio.production.start(changed['id'])
            with self.assertRaisesRegex(ValueError,'Krita changed'):studio.production.run(changed['id'])
        execute.assert_not_called()

    def test_branch_budget_and_start_are_atomic_and_not_reset(self):
        studio=FakeStudio(self.root,[]);lab=studio.production
        parent=lab.create(self.intent());child=lab.create(self.intent(parent_project=parent['id']))
        lab.start(parent['id'])
        with self.assertRaisesRegex(ValueError,'already been started'):lab.start(parent['id'])
        with self.assertRaisesRegex(ValueError,'budget is exhausted'):lab.start(child['id'])
        self.assertEqual(lab.get(child['id'])['budget'],{'allowance':2,'reserved':2})
        self.assertEqual(studio.queue.qsize(),1)

    def test_numeric_aliases_cannot_create_duplicate_candidates(self):
        studio=FakeStudio(self.root,[]);lab=studio.production
        for values in (['1','1.0'],['0','-0.0'],['1','1e0'],[1,'01']):
            with self.subTest(values=values),self.assertRaisesRegex(ValueError,'values must differ'):
                lab.create(self.intent(values=values))
        self.assertEqual(lab.list(),[])
        self.assertEqual(studio.queue.qsize(),0)
        distinct=lab.create(self.intent(values=['1.0','2']))
        self.assertEqual(len(distinct['stages']),2)
        self.assertEqual(distinct['budget']['reserved'],0)

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
