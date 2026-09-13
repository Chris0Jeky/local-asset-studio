"""Exercise budget and response-loss behavior without touching a live GPU."""
import copy
import hashlib
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
            patch.object(server.Studio,'production_preflight',lambda s,*a:{'test_bundle':True,'comfy_url':s.comfy_url,'comfy_root':str(s.comfy_root)}),
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
        self.assertEqual(lab.get(p['id'])['budget']['reserved'],1)
        self.assertTrue(next(iter(studio.jobs.values()))['pending_submission'])
        restarted=FakeStudio(self.root,[])
        restarted.production.resume(p['id']);restarted.production.run(p['id'])
        self.assertEqual(self.post_count(restarted),0)
        self.assertEqual(len(restarted.jobs),1)
        self.assertEqual(restarted.production.get(p['id'])['state']['status'],'uncertain')
        self.assertEqual(restarted.production.get(p['id'])['budget']['reserved'],1)

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

    def test_stopped_tracking_blocks_production_resume_and_later_stages_without_changing_reservation(self):
        studio=FakeStudio(self.root,[{'queue_running':[],'queue_pending':[]},{'prompt_id':'known-a'},URLError('observation lost')])
        project=studio.production.create(self.intent());studio.production.start(project['id']);studio.production.run(project['id'])
        state=studio.production.get(project['id'])['state'];job=next(iter(studio.jobs.values()))
        plan=(studio.production.root/project['id']/'plan.json').read_bytes();budget=studio.production.get(project['id'])['budget'];queued=studio.queue.qsize()
        studio.stop_tracking(job['id'],'Native runtime stopped before history could be read')
        with self.assertRaisesRegex(ValueError,'Resume observation'):studio.production.resume(project['id'])
        self.assertEqual(studio.queue.qsize(),queued);self.assertEqual(self.post_count(studio),1)
        studio.resume_job(job['id']);studio.replies=iter([{'known-a':{'status':{'status_str':'success'},'outputs':{}}}]);studio._resume(job)
        self.assertEqual(job['status'],'completed');self.assertEqual(self.post_count(studio),1)
        studio.production.run(project['id'])
        after=studio.production.get(project['id'])
        self.assertEqual(after['state']['status'],'uncertain');self.assertEqual(after['state']['started_at'],state['started_at'])
        self.assertEqual(after['budget'],budget);self.assertEqual((studio.production.root/project['id']/'plan.json').read_bytes(),plan)
        self.assertEqual(len(studio.jobs),1);self.assertEqual(self.post_count(studio),1)
        studio.production.resume(project['id']);self.assertEqual(studio.production.get(project['id'])['state']['tracking_stop_authorizations'],studio.tracking_stop_tokens(job))
        restarted=FakeStudio(self.root,[])
        restored=next(iter(restarted.jobs.values()))
        self.assertEqual(restored['tracking_disposition']['reason'],'Native runtime stopped before history could be read')
        self.assertEqual(restarted.production.get(project['id'])['state']['tracking_stop_authorizations'],restarted.tracking_stop_tokens(restored))
        self.assertEqual(restarted.requests,[]);self.assertEqual(restarted.production.get(project['id'])['budget'],budget)

    def test_blueprints_and_filename_axes_cannot_be_submitted(self):
        studio=FakeStudio(self.root,[])
        with self.assertRaisesRegex(ValueError,'blueprints'):studio.production.create(self.intent(workflow=GRAPH))
        with self.assertRaisesRegex(ValueError,'numeric'):studio.production.create(self.intent(axis='lora',values=['another.safetensors']))
        self.assertEqual(len(studio.jobs),0);self.assertEqual(studio.queue.qsize(),0)

    def test_tracking_stop_during_stage_dispatch_cannot_resubmit_retained_prompt(self):
        for boundary in ('bundle', 'attempt'):
            with self.subTest(boundary=boundary):
                studio=FakeStudio(self.root,[{'queue_running':[],'queue_pending':[]},{'prompt_id':'retained-'+boundary},URLError('observation lost')])
                lab=studio.production;project=lab.create(self.intent(max_generations=4));lab.start(project['id']);lab.run(project['id'])
                job=studio.jobs[lab.get(project['id'])['state']['attempts']['0']['job_id']]
                prompt_ids=copy.deepcopy(job['prompt_ids']);submissions=copy.deepcopy(job['submissions']);budget=lab.get(project['id'])['budget']
                lab.resume(project['id'])
                fired=[]
                def stop_and_resume(*args, **kwargs):
                    if not fired:
                        fired.append(True);studio.stop_tracking(job['id'],'Stop arrived during dispatch');studio.resume_job(job['id'])
                original=lab._attempt
                def attempt(*args, **kwargs):
                    stop_and_resume();return original(*args, **kwargs)
                studio.replies=iter([{prompt_ids[0]:{'status':{'status_str':'success'},'outputs':{}}}])
                target=patch.object(studio,'check_production_bundle',side_effect=stop_and_resume) if boundary=='bundle' else patch.object(lab,'_attempt',side_effect=attempt)
                with target,patch.object(studio,'_run') as generate:
                    lab.run(project['id'])
                self.assertTrue(fired);generate.assert_not_called()
                self.assertEqual(self.post_count(studio),1);self.assertEqual(job['prompt_ids'],prompt_ids)
                self.assertEqual(len(job['submissions']),len(submissions));self.assertEqual(job['submissions'][0]['graph'],submissions[0]['graph'])
                self.assertEqual(lab.get(project['id'])['state']['status'],'uncertain');self.assertEqual(lab.get(project['id'])['budget'],budget)
                self.assertEqual(len(lab.get(project['id'])['state']['attempts']),1)

    def test_queued_gallery_observation_reconciles_without_resubmitting_its_stage(self):
        studio=FakeStudio(self.root,[{'queue_running':[],'queue_pending':[]},{'prompt_id':'retained'},URLError('observation lost')])
        lab=studio.production;project=lab.create(self.intent(values=[1]));lab.start(project['id']);lab.run(project['id'])
        job=next(iter(studio.jobs.values()));lab.resume(project['id']);studio.resume_job(job['id'])
        studio.replies=iter([{'retained':{'status':{'status_str':'success'},'outputs':{}}}])
        with patch.object(studio,'_run') as generate:lab.run(project['id'])
        generate.assert_not_called();self.assertEqual(self.post_count(studio),1)
        self.assertEqual(job['prompt_ids'],['retained']);self.assertEqual(lab.get(project['id'])['state']['status'],'awaiting_review')

    def test_changed_plan_and_stop_before_first_stage_never_generate(self):
        studio=FakeStudio(self.root,[]);lab=studio.production;p=lab.create(self.intent())
        lab.start(p['id']);lab.stop(p['id']);lab.run(p['id'])
        self.assertEqual(lab.get(p['id'])['state']['status'],'stopped');self.assertFalse(studio.jobs)
        with lab.connect() as db:
            record=lab._get(p['id'],db);record['plan']['stages'][0]['graph']['1']['inputs']['text']='changed'
            db.execute('UPDATE projects SET plan=? WHERE id=?',(json.dumps(record['plan']),p['id']))
        with self.assertRaisesRegex(ValueError,'plan changed'):lab.run(p['id'])
        self.assertEqual(self.post_count(studio),0)


PLAN_GRAPH={'1':{'class_type':'KSampler','inputs':{'text':'a witch in a lantern-lit atelier','seed':1,'steps':8,'cfg':1,'sampler_name':'euler','scheduler':'simple'}},
            '10':{'class_type':'LoraLoaderModelOnly','inputs':{'lora_name':'a.safetensors','strength_model':1.0}},
            '11':{'class_type':'LoraLoaderModelOnly','inputs':{'lora_name':'b.safetensors','strength_model':0.0}}}
PLAN_PRESET={'id':'planned','name':'Planned sweep','category':'Test','family':'Krea 2 Turbo','graph':'workflows/api/planned-api.json',
             'positive':['1','text'],'seed':['1','seed'],'steps':['1','steps'],'cfg':['1','cfg'],
             'sampler':['1','sampler_name'],'scheduler':['1','scheduler'],'lora':['10','strength_model'],
             'choices':{'sampler':['euler','euler_ancestral'],'scheduler':['simple','beta']}}
# Inline Contract 4 fixture: the lane must not depend on presets/settings-kb.json existing.
PLAN_KB={'version':1,'updated':'2026-09-12','families':{'Krea 2 Turbo':{
            'defaults':{'sampler':'euler','scheduler':'simple','steps':8,'cfg':1.0},
            'axes':[{'id':'steps','control':'steps','values':[8,15],'rationale':'distilled for 8','sources':['https://example.invalid/steps']},
                    {'id':'sampler','control':'sampler','values':['euler','euler_ancestral','er_sde'],'rationale':'community cards','sources':['https://example.invalid/sampler']}],
            'lora_rules':{'ladder':[1.0,0.8,0.6],'warn_total_strength':2.5}}},
         'loras':{'a.safetensors':{'family':'Krea 2 Turbo','label':'TextFusion','role':'adherence','source':'https://example.invalid/a'}}}


class PlannedSweepTests(unittest.TestCase):
    """Multi-setting sweeps planned from the settings library, still bounded."""
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        for name in ('presets','workflows/api','config','fake-comfy/input'):(self.root/name).mkdir(parents=True,exist_ok=True)
        (self.root/'config/local.json').write_text(json.dumps({'comfy_root':str(self.root/'fake-comfy')}))
        (self.root/'presets/catalog.json').write_text(json.dumps({'presets':[PRESET,PLAN_PRESET]}))
        (self.root/'workflows/api/demo-api.json').write_text(json.dumps(GRAPH))
        (self.root/'workflows/api/planned-api.json').write_text(json.dumps(PLAN_GRAPH))
        self.kb_bytes=json.dumps(PLAN_KB).encode('utf-8');(self.root/'presets/settings-kb.json').write_bytes(self.kb_bytes)
        self.patches=[patch.object(threading.Thread,'start',lambda *_:None),
            patch.object(server.Studio,'production_preflight',lambda s,*a:{'test_bundle':True,'comfy_url':s.comfy_url,'comfy_root':str(s.comfy_root)}),
            patch.object(server.Studio,'check_production_bundle',lambda *a:None),
            patch.object(server.Studio,'validate_graph',lambda *a:None)]
        for p in self.patches:p.start()
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()
    def intent(self,variants,**extra):
        return dict({'name':'Planned sweep','recipe':{'preset_id':'planned','controls':{}},'variants':variants,'max_generations':4},**extra)
    def variant(self,label,**controls):return {'label':label,'controls':controls,'rationale':'documented','sources':['https://example.invalid/steps']}

    def test_planned_variants_become_labelled_candidates_and_record_the_library(self):
        studio=FakeStudio(self.root,[]);lab=studio.production
        project=lab.create(self.intent([self.variant('Fast 8-step euler',steps=8,sampler='euler'),
                                        self.variant('Target 15-step euler_a',steps=15,sampler='euler_ancestral')]))
        self.assertEqual(project['axis'],'variants')
        self.assertEqual(project['values'],['Fast 8-step euler','Target 15-step euler_a'])
        self.assertEqual([v['rationale'] for v in project['variants']],['documented','documented'])
        self.assertEqual(project['variants'][1]['sources'],['https://example.invalid/steps'])
        self.assertEqual(project['knowledge_sha256'],hashlib.sha256(self.kb_bytes).hexdigest())
        self.assertEqual([s['label'] for s in project['stages']],['A','B'])
        plan=lab._get(project['id'])['plan']
        self.assertEqual(plan['stages'][1]['request']['controls'],{'steps':15,'sampler':'euler_ancestral'})
        self.assertEqual(plan['stages'][0]['graph']['1']['inputs']['steps'],8)
        self.assertEqual(project['budget'],{'allowance':4,'reserved':0})
        self.assertFalse(studio.jobs);self.assertEqual(studio.queue.qsize(),0)

    def test_planned_variants_are_refused_when_they_repeat_overflow_or_touch_unbound_controls(self):
        studio=FakeStudio(self.root,[]);lab=studio.production
        cases=[('labels must differ',[self.variant('Same',steps=8),self.variant('Same',steps=15)]),
               ('different graphs',[self.variant('One',steps=8),self.variant('Two',steps=8)]),
               ('one to eight',[self.variant('V%d'%i,steps=i+1) for i in range(9)]),
               ('at least one control',[{'label':'Empty','controls':{}}]),
               ('Unsupported controls',[self.variant('Unbound',denoise=0.5)]),
               ('needs a label',[{'label':'','controls':{'steps':8}}])]
        for message,variants in cases:
            with self.subTest(message=message),self.assertRaisesRegex(ValueError,message):lab.create(self.intent(variants))
        with self.assertRaisesRegex(ValueError,'exceeds the generation budget'):
            lab.create(self.intent([self.variant('A',steps=8),self.variant('B',steps=15)],max_generations=1))
        self.assertEqual(lab.list(),[]);self.assertFalse(studio.jobs);self.assertEqual(studio.queue.qsize(),0)

    def test_plan_route_offers_documented_variants_without_reserving_anything(self):
        studio=FakeStudio(self.root,[]);lab=studio.production
        offer=lab.plan({'preset_id':'planned','controls':{'seed':3},'mode':'grid','limit':4})
        self.assertEqual([a['id'] for a in offer['axes_available']],['steps','sampler'])
        self.assertEqual([a['values'] for a in offer['axes_available']],[[8,15],['euler','euler_ancestral']])
        self.assertEqual(offer['variants'][0]['label'],'steps=8 · sampler=euler')
        self.assertIn('steps=8',offer['variants'][0]['description'])
        self.assertEqual(offer['knowledge_sha256'],hashlib.sha256(self.kb_bytes).hexdigest())
        remix=lab.plan({'preset_id':'planned','controls':{'lora':1.0,'lora_name':'a.safetensors'},'mode':'remix'})
        self.assertEqual([v['label'] for v in remix['variants']],['TextFusion lead'])
        for payload,message in (({'preset_id':'planned','mode':'sideways'},'grid or a LoRA remix'),
                                ({'preset_id':'demo','mode':'grid'},'documents no axis'),
                                ({'preset_id':'planned','mode':'remix','controls':{'lora':0}},'at least one LoRA slot')):
            with self.subTest(message=message),self.assertRaisesRegex(ValueError,message):lab.plan(payload)
        self.assertEqual(lab.list(),[]);self.assertFalse(studio.jobs);self.assertEqual(studio.queue.qsize(),0)
        # What the planner offers is exactly what the create route accepts.
        project=lab.create(self.intent(offer['variants'][:2]))
        self.assertEqual(len(project['stages']),2)
        self.assertEqual(project['variants'][0]['controls'],{'seed':3,'steps':8,'sampler':'euler'})

    def test_a_missing_knowledge_base_plans_nothing_and_records_no_digest(self):
        (self.root/'presets/settings-kb.json').unlink()
        studio=FakeStudio(self.root,[]);lab=studio.production
        with self.assertRaisesRegex(ValueError,'documents no axis'):lab.plan({'preset_id':'planned','mode':'grid'})
        project=lab.create(self.intent([self.variant('Hand-written 15 steps',steps=15)]))
        self.assertEqual(project['knowledge_sha256'],'')

    def test_the_single_axis_route_is_unchanged_by_the_variant_path(self):
        studio=FakeStudio(self.root,[]);lab=studio.production
        project=lab.create({'name':'Seeds','recipe':{'preset_id':'planned','controls':{}},'axis':'seed','values':[1,2],'max_generations':2})
        self.assertEqual((project['axis'],project['values'],project['variants'],project['knowledge_sha256']),('seed',[1,2],None,None))
        with self.assertRaisesRegex(ValueError,'values must differ'):
            lab.create({'name':'Seeds','recipe':{'preset_id':'planned','controls':{}},'axis':'seed','values':['1','1.0'],'max_generations':2})
