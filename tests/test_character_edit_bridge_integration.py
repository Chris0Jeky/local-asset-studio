"""Real repo contracts and Handler/Production/Workspace, with inert model execution.

These tests must run in the full repository. No model, native editor or art approval
is established by a synthetic canon or a substituted neural boundary.
"""
import copy
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading
import unittest
import tempfile
from unittest.mock import patch
from PIL import Image

from scripts import character_edit as edit, character_edit_bridge as bridge
from scripts.character_edit_demo import create
from scripts.character_study import attest_canon, file_sha, sha, read_json, write_json
from test_server import server, FakeStudio
ROOT=Path(__file__).resolve().parents[1]


def reviewed_fixture(root):
    create(root)
    doc=read_json(root/'document.json');intent=read_json(root/'intent.json');doc['actors']=doc['actors'][:1]
    canon={'schema_version':1,'kind':'character_canon','asset_id':'amber','revision':1,
        **{k:{'id':'fixture-'+k,'description':'Synthetic test '+k,'invariants':['Fixture invariant only']} for k in ('identity','costume','representation','style')},
        'references':[{'id':'neutral','path':'amber-reference.png','sha256':file_sha(root/'amber-reference.png'),
                       'role':'identity','take':['Fixture identity'],'ignore':['Other figure']}],
        'checks':{'same-identity':'Synthetic identity remains stable'},
        'approval':{'state':'draft','reviewer':None,'reviewer_kind':None,'note':'Test fixture; no owner decision','subject_sha256':None}}
    canon=attest_canon(canon,'synthetic-test-reviewer','human','Synthetic unit-test attestation, not actual owner approval')
    (root/'amber-design.json').write_text(json.dumps(canon),encoding='utf-8')
    doc['actors'][0]['canon']['sha256']=file_sha(root/'amber-design.json')
    intent['document_sha256']=sha(doc)
    write_json(root/'current-document.json',doc)
    plan=edit.make_plan(doc,intent,read_json(ROOT/'research/character-consistency/edit-routes.json'))
    write_json(root/'bridge-plan.json',plan);return plan


class Preparation(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)/'art'
        self.plan=reviewed_fixture(self.root)
    def prepare(self,seeds=None):return bridge.prepare(self.root,'bridge-plan.json','handoff',seeds or [11,22])
    def rewrite(self):
        self.plan['intent']['document_sha256']=sha(self.plan['document'])
        self.plan=edit.make_plan(self.plan['document'],self.plan['intent'],self.plan['catalog'])
        (self.root/'bridge-plan.json').write_text(json.dumps(self.plan),encoding='utf-8')
    def test_oversized_native_prompt_rejected_before_output_creation(self):
        self.plan['intent']['changes'][0]['instruction']='x'*8000;self.rewrite()
        with self.assertRaisesRegex(ValueError,'8000'):self.prepare()
        self.assertFalse((self.root/'handoff').exists())
    def test_exact_native_prompt_limit_is_retained(self):
        suffix=bridge.compile_instruction([{'instruction':''}])
        self.plan['intent']['changes'][0]['instruction']='x'*(8000-len(suffix));self.rewrite()
        value=self.prepare();self.assertEqual(8000,len(value['positive']))
    def test_handoff_pins_real_catalog_and_raw_template(self):
        value=self.prepare();catalog=read_json(ROOT/'presets/catalog.json')
        preset=next(p for p in catalog['presets'] if p['id']==value['preset_id'])
        self.assertEqual(bridge.preset_contract(preset),value['native_preset'])
        self.assertEqual(bridge.hashed(value['native_preset']),value['preset_sha256'])
    def test_actual_native_handoff_prepares_no_network(self):
        with patch.object(bridge.StudioHTTP,'request',side_effect=AssertionError('Unexpected HTTP')):
            value=self.prepare()
        self.assertEqual('qwen-2ref',value['preset_id']);self.assertEqual([96,96],value['size'])
        self.assertEqual(['composition','identity'],[r['role'] for r in value['references']])
        self.assertFalse(value['submits_generation']);bridge.validate_handoff(self.root,value)
    def test_model_context_preserves_crop_and_explicit_black_padding(self):
        value=self.prepare()
        with Image.open(self.root/'source.png') as source, Image.open(self.root/value['references'][0]['image']['path']) as context:
            self.assertEqual('RGB',context.mode)
            self.assertEqual(source.crop((50,96,137,189)).convert('RGB').tobytes(),context.crop((0,0,87,93)).tobytes())
            self.assertEqual((0,0,0),context.getpixel((87,95)))
    def test_prepare_refuses_to_overwrite(self):
        self.prepare()
        with self.assertRaisesRegex(ValueError,'new handoff'):self.prepare()
    def test_budget_reserves_repairs(self):
        with self.assertRaisesRegex(ValueError,'reserved repairs'):self.prepare([1,2,3])
    def test_no_implicit_scene_adapter(self):
        self.plan['document']['actors'].append(copy.deepcopy(self.plan['document']['actors'][0]));self.plan['document']['actors'][-1]['id']='violet'
        self.rewrite()
        with self.assertRaisesRegex(ValueError,'Multi-actor'):self.prepare()
    def test_references_are_not_truncated(self):
        for rid in ('detail-one','detail-two'):
            ref=copy.deepcopy(self.plan['document']['actors'][0]['references'][0]);ref.update(id=rid,role='style')
            self.plan['document']['actors'][0]['references'].append(ref)
        self.rewrite()
        with self.assertRaisesRegex(ValueError,'never truncates'):self.prepare()
    def test_costume_reference_maps_to_costume_not_pose(self):
        ref=copy.deepcopy(self.plan['document']['actors'][0]['references'][0]);ref.update(id='new-costume',role='costume')
        self.plan['document']['actors'][0]['references'].append(ref);self.rewrite()
        value=self.prepare();self.assertEqual('qwen-3ref',value['preset_id'])
        self.assertEqual(['composition','identity','costume'],[r['role'] for r in value['references']])
    def test_draft_canon_cannot_be_silently_approved(self):
        canon=read_json(self.root/'amber-design.json')
        canon['approval']={'state':'draft','reviewer':None,'reviewer_kind':None,'note':'Draft test','subject_sha256':None}
        (self.root/'amber-design.json').write_text(json.dumps(canon));self.plan['document']['actors'][0]['canon']['sha256']=file_sha(self.root/'amber-design.json');self.rewrite()
        with self.assertRaisesRegex(ValueError,'approved canon'):self.prepare()
    def test_transparent_source_crop_rejected_without_implied_matte(self):
        path=self.root/'source.png'
        with Image.open(path) as source:im=source.copy()
        im.putpixel((80,120),(10,20,30,0));im.save(path)
        self.plan['document']['source']['sha256']=file_sha(path);self.rewrite()
        with self.assertRaisesRegex(ValueError,'Transparent source'):self.prepare()
    def test_policy_exclusion_is_honoured(self):
        self.plan['intent']['policy_preference']['unknown_policy']='exclude';self.rewrite()
        with self.assertRaisesRegex(ValueError,'excluded'):self.prepare()
    def test_unreviewed_identity_substitution_rejected(self):
        self.plan['document']['actors'][0]['references'][0]['image']={'path':'source.png','sha256':file_sha(self.root/'source.png')};self.rewrite()
        with self.assertRaisesRegex(ValueError,'not an identity reference'):self.prepare()


class NativeHTTP(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);base=Path(self.tmp.name)
        self.art=base/'art';reviewed_fixture(self.art)
        self.repo=base/'studio'
        for folder in ('presets','config','workflows/api','research/character-consistency','fake-comfy/input','fake-comfy/output'):
            (self.repo/folder).mkdir(parents=True,exist_ok=True)
        catalog=read_json(ROOT/'presets/catalog.json');presets=[p for p in catalog['presets'] if p['id'] in ('qwen-2ref','qwen-3ref')]
        (self.repo/'presets/catalog.json').write_text(json.dumps({'presets':presets}))
        for preset in presets:(self.repo/preset['graph']).write_bytes((ROOT/preset['graph']).read_bytes())
        (self.repo/'research/character-consistency/edit-routes.json').write_bytes((ROOT/'research/character-consistency/edit-routes.json').read_bytes())
        (self.repo/'config/local.json').write_text(json.dumps({'comfy_root':str(self.repo/'fake-comfy')}))
        with patch.object(threading.Thread,'start',lambda *_:None):self.studio=FakeStudio(self.repo,[])
        self.inference_calls=[]
        def preflight(preset,graph):
            inputs=[]
            for node in graph.values():
                if node.get('class_type')=='LoadImage':
                    path=self.studio.comfy_root/'input'/node['inputs']['image']
                    inputs.append({'path':str(path),'sha256':file_sha(path),'bytes':path.stat().st_size})
            return {'comfy_url':self.studio.comfy_url,'inputs':inputs,'models':[],'test_only':True}
        def synthesize(job):
            # Substitute ONLY the neural execution boundary; real job/provenance/export follows.
            self.inference_calls.append(job['id']);name=job['id']+'.png'
            Image.new('RGB',(96,96),(236,123,58)).save(self.studio.comfy_root/'output'/name)
            job.update(status='completed',message='Inert integration fixture, no neural inference',prompt_ids=['synthetic-no-model'],
                       submissions=[{'prompt_id':'synthetic-no-model','graph':copy.deepcopy(job['graph']),'status':'completed','index':0}],
                       outputs=[{'filename':name,'subfolder':'','type':'output','media_type':'image'}])
            self.studio.index_outputs(job);self.studio._save(job)
        self.patches=[patch.object(self.studio,'production_preflight',side_effect=preflight),
                      patch.object(self.studio,'check_production_bundle',return_value=None),
                      patch.object(self.studio,'validate_graph',return_value=None),patch.object(self.studio,'_run',side_effect=synthesize)]
        for p in self.patches:p.start();self.addCleanup(p.stop)
        studio=self.studio
        class TestHandler(server.Handler):
            # Ephemeral-port adaptation only; existing HTTP guard tests cover fixed production 8191.
            def _safe_host(self):return self.headers.get('Host')==f'127.0.0.1:{self.server.server_port}'
            def _safe_mutation(self):return self._safe_host() and self.headers.get('Origin')==f'http://127.0.0.1:{self.server.server_port}'
        TestHandler.studio=studio
        self.http=ThreadingHTTPServer(('127.0.0.1',0),TestHandler);self.worker=threading.Thread(target=self.http.serve_forever,daemon=True);self.worker.start()
        self.addCleanup(self.shutdown)
        self.handoff=bridge.prepare(self.art,'bridge-plan.json','handoff',[11],repo=self.repo)
        self.client=bridge.StudioHTTP(self.http.server_port,timeout=10);self.bridge=bridge.Bridge(self.art,'handoff/handoff.json',self.client)
    def shutdown(self):
        self.http.shutdown();self.http.server_close();self.worker.join(timeout=5)
    def test_real_catalog_binding_swap_is_blocked_without_generation(self):
        path=self.repo/'presets/catalog.json';catalog=read_json(path)
        preset=next(p for p in catalog['presets'] if p['id']=='qwen-2ref')
        slots=preset['reference_slots'];slots[0]['binding'],slots[1]['binding']=slots[1]['binding'],slots[0]['binding']
        path.write_text(json.dumps(catalog))
        with self.assertRaisesRegex(ValueError,'catalog bindings'):self.bridge.stage()
        self.assertEqual([],self.studio.production.list());self.assertTrue(self.studio.queue.empty())
        self.assertEqual([],self.inference_calls)
    def test_real_http_queue_capture_and_protected_composition(self):
        source_sha=file_sha(self.art/'source.png')
        pid=self.bridge.stage()['project']['id'];self.assertEqual([],self.inference_calls);self.assertTrue(self.studio.queue.empty())
        self.assertEqual({'allowance':3,'reserved':0},self.studio.production.get(pid)['budget'])
        self.bridge.start();self.assertEqual(('production',pid),self.studio.queue.get_nowait());self.assertEqual([],self.inference_calls)
        self.studio.production.run(pid);self.assertEqual(1,len(self.inference_calls))
        receipt=self.bridge.collect(0);self.assertEqual(pid,receipt['project_id'])
        result=self.bridge.compose(0,'current-document.json','bridge-result')
        self.assertEqual(4032,result['composition']['changed_pixels']);self.assertEqual(0,result['composition']['outside_mask_changed_pixels'])
        self.assertEqual(0,result['composition']['protected_changed_pixels']);self.assertFalse(result['semantic_approval'])
        self.assertEqual(source_sha,file_sha(self.art/'source.png'));self.assertEqual([],self.studio.requests)
        with self.assertRaises(ValueError):self.bridge.start()
        self.assertEqual({'allowance':3,'reserved':1},self.studio.production.get(pid)['budget'])
    def test_lost_create_response_reconciles_real_persisted_plan_without_queue(self):
        request=self.client.request
        def lost(method,path,*a,**kw):
            value=request(method,path,*a,**kw)
            if method=='POST' and path=='/api/production':raise TimeoutError('Synthetic lost client response after server commit')
            return value
        with patch.object(self.client,'request',side_effect=lost):
            with self.assertRaises(TimeoutError):self.bridge.stage()
        self.assertEqual(1,len(self.studio.production.list()));self.assertTrue(self.studio.queue.empty())
        self.bridge.reconcile();self.assertEqual(1,len(self.studio.production.list()));self.assertTrue(self.studio.queue.empty())
    def test_stale_exported_document_blocks_apply(self):
        pid=self.bridge.stage()['project']['id'];self.bridge.start();self.studio.production.run(pid);self.bridge.collect(0)
        doc=read_json(self.art/'current-document.json');doc['revision']+=1
        (self.art/'current-document.json').write_text(json.dumps(doc))
        with self.assertRaisesRegex(ValueError,'document is stale'):self.bridge.compose(0,'current-document.json','stale-result')
        self.assertFalse((self.art/'stale-result').exists())

if __name__=='__main__':unittest.main()
