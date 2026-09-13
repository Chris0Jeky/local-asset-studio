"""Client protocol/fault tests use an inert Studio boundary, never a neural model."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch
from PIL import Image
from scripts import character_edit_bridge as b


def png(size=(96,96), colour=(80,100,120,255)):
    stream=io.BytesIO();Image.new('RGBA',size,colour).save(stream,format='PNG');return stream.getvalue()


def fixture_preset():
    return {'id':'qwen-2ref','graph':'workflows/api/qwen-2ref-api.json',
            'positive':['1','text'],'seed':['1','seed'],'width':['1','width'],'height':['1','height'],
            'reference_slots':[{'role':'identity','binding':['4','image']},
                               {'role':'pose','binding':['16','image']}]}


def handoff(root):
    # This is a protocol fixture, not a canon approval or a production plan.
    for name,raw in [('source.png',png()),('context.png',png()),('identity.png',png((64,64))),('plan.json',b'{}')]:
        (root/name).write_bytes(raw)
    template=b.canonical({'1':{'class_type':'TestOnly','inputs':{'text':'base','width':96,'height':96,'seed':1}},
                          '4':{'class_type':'LoadImage','inputs':{'image':'base.png'}},
                          '16':{'class_type':'LoadImage','inputs':{'image':'base.png'}}})
    value={'schema_version':1,'kind':'character_edit_studio_handoff','plan':b.artifact(root,'plan.json'),
        'edit_plan_sha256':'1'*64,'document_sha256':'2'*64,'bundle':'prepared','bundle_sha256':'3'*64,
        'originals':[b.artifact(root,'source.png'),b.artifact(root,'plan.json')],
        'references':[{'image':b.artifact(root,'context.png'),'role':'composition','contribution':'Current crop','avoid':'Unrequested edits'},
                      {'image':b.artifact(root,'identity.png'),'role':'identity','contribution':'Identity','avoid':'Pose'}],
        'size':[96,96],'seeds':[11,22],'preset_id':'qwen-2ref','template_sha256':b.digest(template),'native_preset':fixture_preset(),'preset_sha256':b.hashed(fixture_preset()),'positive':'Repair the hand.',
        'max_candidates':3,'reserved_repairs':1,'max_seconds':1800,'budget_owner':'test-only',
        'policy':{'eligible_by_preference':True},'scope':'fixture','context_conversion':'fixture','submits_generation':False}
    value['sha256']=b.hashed(value); (root/'handoff.json').write_bytes(b.canonical(value));return value,template


class InertStudio:
    def __init__(self, template):
        self.template=template;self.calls=[];self.uploads={};self.projects={};self.assets=[];self.files={};self.recipes={}
        self.preset=fixture_preset()
        self.identity={'app':'local-asset-studio','workspace':'fixture-workspace','version':'fixture'}
        self.lost_create=False;self.lost_start=False;self.create_commits=True;self.preview_hook=lambda p:p
    def graph(self, request):
        # Independent tiny compiler fixture. The real repo compiler is exercised by NativeHTTP.
        graph=json.loads(self.template)
        for control,value in request['controls'].items():
            node,field=self.preset[control];graph[node]['inputs'][field]=value
        for slot,ref in zip(self.preset['reference_slots'],request['references']):
            node,field=slot['binding'];graph[node]['inputs'][field]=ref['file']
        lines=[f"Picture {i+1} — {r['role']}: use {r['contribution'].strip() or 'the assigned visual role'}. Avoid transferring: {r['avoid'].strip() or 'unrequested details'}." for i,r in enumerate(request['references'])]
        node,field=self.preset['positive'];graph[node]['inputs'][field]='\n'.join(lines)+'\n\nRequested result:\n'+request['controls']['positive']
        return graph
    def preview(self, request):
        refs=copy.deepcopy(request['references'])
        refs[0]['transform']={'policy':'scale-to-total-pixels','source_size':[request['controls']['width'],request['controls']['height']]}
        return self.preview_hook({'workflow':self.graph(request),'references':refs,'batch_count':1,
                                 'template_sha256':request['expected_template_sha256'],'submitted':False})
    def request(self, method,path,body=None,**options):
        self.calls.append((method,path,copy.deepcopy(body),options))
        if path=='/api/identity':return copy.deepcopy(self.identity)
        if path=='/api/catalog':return {'presets':[copy.deepcopy(self.preset)]}
        if path.startswith('/api/workflows/'):return self.template
        if path=='/api/upload':
            name=uuid.uuid4().hex+'_'+options['filename']+'.png';self.uploads[name]=body
            return {'file':name,'sha256':b.digest(body)}
        if path.startswith('/api/uploads/'):return self.uploads[path.rsplit('/',1)[-1]]
        if path=='/api/preview':return self.preview(body)
        if path=='/api/production' and method=='GET':return [copy.deepcopy(p) for p in self.projects.values()]
        if path=='/api/production' and method=='POST':
            pid=uuid.uuid4().hex;stages=[]
            for index,seed in enumerate(body['values']):
                request=copy.deepcopy(body['recipe']);request['controls']['seed']=seed
                graph=self.graph(request)
                stages.append({'operation':'comfy.generate.v1','label':chr(65+index),'request':request,'graph':graph,
                               'graph_sha256':b.digest(json.dumps(graph,sort_keys=True,separators=(',',':')).encode())})
            plan={'kind':'comparison','name':body['name'],'parent_project':None,'axis':'seed','values':body['values'],
                'stages':stages,'bundle':{'inputs':[{'path':'C:\\Comfy\\input\\'+r['file'],'sha256':r['sha256']} for r in body['recipe']['references']]}}
            plan['sha256']=b.digest(json.dumps(plan,sort_keys=True,separators=(',',':')).encode())
            project={'id':pid,'root_id':pid,'plan_sha256':plan['sha256'],'name':body['name'],'plan':plan,
                'budget':{'allowance':body['max_generations'],'reserved':0},'state':{'status':'planned'},
                'stages':[{'label':s['label'],'operation':s['operation'],'job':None,'attempt':{}} for s in stages]}
            if self.create_commits:self.projects[pid]=project
            if self.lost_create:raise TimeoutError('Create response lost')
            return copy.deepcopy(project)
        if path.startswith('/api/production/'):
            pid=path.split('/')[3];project=self.projects[pid]
            if method=='POST' and path.endswith('/start'):
                project['budget']['reserved']=len(project['stages']);project['state'].update(status='queued',reserved=len(project['stages']))
                if self.lost_start:raise TimeoutError('Start response lost')
            return copy.deepcopy(project)
        if path=='/api/workspace':return {'assets':copy.deepcopy(self.assets)}
        if path.startswith('/api/assets/'):return self.files[path.split('/')[3]]
        if path.startswith('/api/jobs/'):return copy.deepcopy(self.recipes[path.split('/')[3]])
        raise AssertionError((method,path))
    def count(self, method, path):return sum(m==method and p==path for m,p,_,_ in self.calls)
    def finish(self, pid, index=0, raw=None):
        project=self.projects[pid];stage=project['stages'][index]
        jid=str(uuid.uuid5(uuid.NAMESPACE_URL,f'asset-studio:{pid}:stage:{index}'));aid=uuid.uuid4().hex
        stage['attempt']={'job_id':jid,'status':'completed'}
        stage['job']={'id':jid,'status':'completed','batch_count':1,'project_id':pid,'prompt_ids':['fixture-prompt-not-a-model'],
                      'outputs':[{'asset_id':aid,'media_type':'image'}]}
        self.files[aid]=raw or png(colour=(220,80,30,255))
        self.assets.append({'id':aid,'job_id':jid,'sha256':b.digest(self.files[aid]),'trashed_at':None,'media_type':'image'})
        self.recipes[jid]={'workflow':project['plan']['stages'][index]['graph'],'batch_count':1}
        project['state']['status']='awaiting_review';return aid


class BridgeProtocol(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.handoff,self.template=handoff(self.root);self.http=InertStudio(self.template)
        self.bridge=b.Bridge(self.root,'handoff.json',self.http)
    def staged(self):return self.bridge.stage()['project']['id']
    def complete(self):
        pid=self.staged();self.bridge.start();aid=self.http.finish(pid);return pid,aid
    def test_catalog_only_reference_swap_blocks_before_upload(self):
        slots=self.http.preset['reference_slots'];slots[0]['binding'],slots[1]['binding']=slots[1]['binding'],slots[0]['binding']
        with self.assertRaisesRegex(ValueError,'catalog bindings'):self.bridge.stage()
        self.assertEqual(0,self.http.count('POST','/api/upload'))
        self.assertEqual(0,self.http.count('POST','/api/production'))
    def test_catalog_drift_after_staging_blocks_start(self):
        pid=self.staged();self.http.preset['seed']=['1','width']
        with self.assertRaisesRegex(ValueError,'catalog bindings'):self.bridge.start()
        self.assertEqual(0,self.http.count('POST','/api/production/'+pid+'/start'))
    def test_reference_swap_race_during_preview_is_not_a_new_baseline(self):
        original=self.http.request;swapped=False
        def drift(method,path,*args,**kw):
            nonlocal swapped
            if path=='/api/preview' and not swapped:
                slots=self.http.preset['reference_slots'];slots[0]['binding'],slots[1]['binding']=slots[1]['binding'],slots[0]['binding'];swapped=True
            return original(method,path,*args,**kw)
        with patch.object(self.http,'request',side_effect=drift):
            with self.assertRaisesRegex(ValueError,'pinned catalog projection'):self.bridge.stage()
        self.assertEqual(0,self.http.count('POST','/api/production'))
    def test_ui_derived_catalog_fields_do_not_invalidate_bindings(self):
        self.http.preset.update(defaults={'seed':99},missing_loras=[],runtime_block=None)
        self.staged()
    def test_runtime_block_rejected_before_upload(self):
        self.http.preset['runtime_block']='Switch backend first'
        with self.assertRaisesRegex(ValueError,'runtime is blocked'):self.bridge.stage()
        self.assertEqual(0,self.http.count('POST','/api/upload'))
    def test_stage_binds_roles_without_starting(self):
        pid=self.staged();self.assertEqual('staged',self.bridge.state()['phase'])
        self.assertEqual(0,self.http.projects[pid]['budget']['reserved'])
        self.assertEqual(0,self.http.count('POST','/api/production/'+pid+'/start'))
        self.assertEqual(['composition','identity'],[r['role'] for r in self.bridge.state()['request']['recipe']['references']])
    def test_stage_does_not_regenerate_on_repeat(self):
        self.staged()
        with self.assertRaises(ValueError):self.bridge.stage()
        self.assertEqual(1,self.http.count('POST','/api/production'))
    def test_explicit_start_once_across_client_restart(self):
        pid=self.staged();self.bridge.start();restarted=b.Bridge(self.root,'handoff.json',self.http)
        with self.assertRaises(ValueError):restarted.start()
        self.assertEqual(1,self.http.count('POST','/api/production/'+pid+'/start'))
        self.assertEqual(2,self.http.projects[pid]['budget']['reserved'])
    def test_creation_response_loss_can_adopt_without_post(self):
        self.http.lost_create=True
        with self.assertRaises(TimeoutError):self.bridge.stage()
        with self.assertRaises(ValueError):self.bridge.stage()
        recovered=b.Bridge(self.root,'handoff.json',self.http);result=recovered.reconcile()
        self.assertEqual(0,result['mutating_http_requests']);self.assertEqual(1,self.http.count('POST','/api/production'))
        self.assertEqual('staged',recovered.state()['phase'])
    def test_lost_uncommitted_creation_is_not_repeated(self):
        self.http.lost_create=True;self.http.create_commits=False
        with self.assertRaises(TimeoutError):self.bridge.stage()
        with self.assertRaisesRegex(ValueError,'No unique'):self.bridge.reconcile()
        self.assertEqual(1,self.http.count('POST','/api/production'))
    def test_ambiguous_named_projects_are_not_adopted(self):
        self.http.lost_create=True
        with self.assertRaises(TimeoutError):self.bridge.stage()
        key=next(iter(self.http.projects));other=copy.deepcopy(self.http.projects[key]);self.http.projects['b'*32]=other
        with self.assertRaisesRegex(ValueError,'No unique'):self.bridge.reconcile()
    def test_start_response_loss_retains_id_and_can_collect(self):
        pid=self.staged();self.http.lost_start=True
        with self.assertRaises(TimeoutError):self.bridge.start()
        self.assertEqual('start_pending',self.bridge.state()['phase'])
        self.assertEqual('queued',self.bridge.status()['project']['state']['status'])
        with self.assertRaises(ValueError):self.bridge.start()
        self.http.finish(pid);self.assertFalse(self.bridge.collect(0)['semantic_approval'])
        self.assertEqual(1,self.http.count('POST','/api/production/'+pid+'/start'))
    def test_legacy_start_response_loss_reconciles_only_the_retained_start(self):
        pid=self.staged();self.http.lost_start=True
        with self.assertRaises(TimeoutError):self.bridge.start()
        before=len(self.http.calls);result=self.bridge.reconcile_start()
        calls=self.http.calls[before:]
        self.assertEqual('started',self.bridge.state()['phase'])
        self.assertEqual({'status':'queued','reserved':2}, {k:result['observation'][k] for k in ('status','reserved')})
        self.assertIsInstance(result['observation']['checked_at'],float)
        self.assertFalse(result['generation_submitted']);self.assertEqual(0,result['mutating_http_requests'])
        self.assertTrue(calls and all(method=='GET' for method,_,_,_ in calls))
        self.assertEqual(1,self.http.count('POST','/api/production/'+pid+'/start'))
        with self.assertRaises(ValueError):self.bridge.start()
    def test_preexisting_named_project_prevents_fresh_budget(self):
        self.http.projects['a'*32]={'name':self.bridge.name}
        with self.assertRaisesRegex(ValueError,'already exists'):self.bridge.stage()
        self.assertEqual(0,self.http.count('POST','/api/production'))
    def test_source_drift_blocks_start_before_post(self):
        pid=self.staged();(self.root/'source.png').write_bytes(png(colour=(1,2,3,255)))
        with self.assertRaisesRegex(ValueError,'Artifact changed'):self.bridge.start()
        self.assertEqual(0,self.http.count('POST','/api/production/'+pid+'/start'))
    def test_template_drift_blocks_start(self):
        pid=self.staged();self.http.template=b'{}'
        with self.assertRaisesRegex(ValueError,'template changed'):self.bridge.start()
        self.assertEqual(0,self.http.count('POST','/api/production/'+pid+'/start'))
    def test_server_identity_drift_blocks_start(self):
        pid=self.staged();self.http.identity['workspace']='another'
        with self.assertRaisesRegex(ValueError,'identity changed'):self.bridge.start()
    def test_wrong_app_rejected_before_upload(self):
        self.http.identity['app']='not-studio'
        with self.assertRaisesRegex(ValueError,'Not a Studio'):self.bridge.stage()
        self.assertEqual(0,self.http.count('POST','/api/upload'))
    def test_relabelled_reference_is_rejected(self):
        def drift(p):p['references'][1]['role']='pose';return p
        self.http.preview_hook=drift
        with self.assertRaisesRegex(ValueError,'reference role'):self.bridge.stage()
        self.assertEqual(0,self.http.count('POST','/api/production'))
    def test_missing_reference_is_rejected(self):
        def drift(p):p['references'].pop();return p
        self.http.preview_hook=drift
        with self.assertRaisesRegex(ValueError,'lost a reference'):self.bridge.stage()
    def test_preview_dimension_drift_rejected(self):
        def drift(p):p['references'][0]['transform']['source_size']=[64,64];return p
        self.http.preview_hook=drift
        with self.assertRaisesRegex(ValueError,'dimensions'):self.bridge.stage()
    def test_preview_canvas_drift_rejected(self):
        # The explicit latent, not the reference, decides the candidate size now.
        def drift(p):p['workflow']['1']['inputs']['height']=64;return p
        self.http.preview_hook=drift
        with self.assertRaisesRegex(ValueError,'dimensions'):self.bridge.stage()
        self.assertEqual(0,self.http.count('POST','/api/production'))
    def test_missing_transform_record_is_refused_not_raised(self):
        def drift(p):p['references'][0]['transform']={};return p
        self.http.preview_hook=drift
        with self.assertRaisesRegex(ValueError,'dimensions'):self.bridge.stage()
    def test_missing_canvas_node_is_refused_not_raised(self):
        def drift(p):p['workflow']['1']={};return p
        self.http.preview_hook=drift
        with self.assertRaisesRegex(ValueError,'dimensions'):self.bridge.stage()
    def test_batch_boolean_alias_rejected(self):
        def drift(p):p['batch_count']=True;return p
        self.http.preview_hook=drift
        with self.assertRaises(ValueError):self.bridge.stage()
    def test_remote_input_digest_drift_rejected(self):
        pid=self.staged();self.http.projects[pid]['plan']['bundle']['inputs'][0]['sha256']='f'*64
        with self.assertRaisesRegex(ValueError,'exact uploaded'):self.bridge.start()
    def test_remote_graph_drift_rejected_even_if_rehashed(self):
        pid=self.staged();p=self.http.projects[pid]['plan'];p['stages'][0]['graph']['1']['inputs']['text']='changed'
        p['stages'][0]['graph_sha256']=b.digest(json.dumps(p['stages'][0]['graph'],sort_keys=True,separators=(',',':')).encode())
        p['sha256']=b.digest(json.dumps({k:v for k,v in p.items() if k!='sha256'},sort_keys=True,separators=(',',':')).encode())
        with self.assertRaisesRegex(ValueError,'graph changed'):self.bridge.start()
    def test_wrong_budget_parent_rejected(self):
        pid=self.staged();self.http.projects[pid]['root_id']='b'*32
        with self.assertRaisesRegex(ValueError,'ownership'):self.bridge.start()
    def test_collect_preserves_job_and_candidate_evidence(self):
        pid,aid=self.complete();r=self.bridge.collect(0)
        self.assertEqual(aid,r['asset_id']);self.assertEqual(pid,r['project_id']);self.assertEqual('unreviewed',r['review_state'])
        self.assertEqual(self.http.files[aid],b.bytes_of(self.root,r['candidate']))
        self.assertEqual(['fixture-prompt-not-a-model'],r['prompt_ids'])
    def test_collect_does_not_overwrite(self):
        self.complete();r=self.bridge.collect(0);raw=b.bytes_of(self.root,r['candidate'])
        with self.assertRaisesRegex(ValueError,'already collected'):self.bridge.collect(0)
        self.assertEqual(raw,b.bytes_of(self.root,r['candidate']))
    def test_collect_does_not_require_other_cases_to_succeed(self):
        pid,aid=self.complete();self.http.projects[pid]['state']['status']='failed'
        self.assertEqual(aid,self.bridge.collect(0)['asset_id'])
    def test_collect_rejects_pending_job(self):
        self.staged()
        with self.assertRaisesRegex(ValueError,'completed'):self.bridge.collect(0)
    def test_collect_rejects_wrong_stage_job(self):
        pid,_=self.complete();self.http.projects[pid]['stages'][0]['job']['id']='wrong'
        with self.assertRaises(ValueError):self.bridge.collect(0)
    def test_collect_rejects_asset_from_another_job(self):
        self.complete();self.http.assets[0]['job_id']='wrong'
        with self.assertRaisesRegex(ValueError,'provenance'):self.bridge.collect(0)
    def test_collect_rejects_changed_asset_bytes(self):
        _,aid=self.complete();self.http.files[aid]=png(colour=(1,2,3,255))
        with self.assertRaisesRegex(ValueError,'digest'):self.bridge.collect(0)
    def test_collect_rejects_changed_dimensions(self):
        pid=self.staged();self.bridge.start();self.http.finish(pid,raw=png((64,64)))
        with self.assertRaisesRegex(ValueError,'size mismatch'):self.bridge.collect(0)
    def test_collect_rejects_extra_outputs(self):
        pid,_=self.complete();self.http.projects[pid]['stages'][0]['job']['outputs']*=2
        with self.assertRaisesRegex(ValueError,'exactly one'):self.bridge.collect(0)
    def test_collect_rejects_source_changed_after_generation(self):
        self.complete();(self.root/'source.png').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'Artifact changed'):self.bridge.collect(0)
    def test_stage_upload_interruption_needs_explicit_resume(self):
        request=self.http.request
        with patch.object(self.http,'request',side_effect=lambda m,p,*a,**kw: (_ for _ in ()).throw(TimeoutError()) if p=='/api/upload' else request(m,p,*a,**kw)):
            with self.assertRaises(TimeoutError):self.bridge.stage()
        with self.assertRaisesRegex(ValueError,'resume-uploads'):self.bridge.stage()
        self.bridge.stage(resume_uploads=True);self.assertEqual(1,self.http.count('POST','/api/production'))
    def test_command_lock_prevents_competing_mutation(self):
        with self.bridge.locked():
            with self.assertRaisesRegex(ValueError,'command'):self.bridge.stage()
        self.assertEqual([],self.http.calls)
    def test_existing_handoff_cannot_reset_allowance(self):
        self.staged();changed=copy.deepcopy(self.handoff);changed['seeds']=[33]
        changed['sha256']=b.hashed({k:v for k,v in changed.items() if k!='sha256'});(self.root/'another.json').write_bytes(b.canonical(changed))
        other=b.Bridge(self.root,'another.json',self.http)
        with self.assertRaisesRegex(ValueError,'different handoff'):other.stage()
        self.assertEqual(1,self.http.count('POST','/api/production'))
    def test_status_is_read_only(self):
        self.staged();before=len([c for c in self.http.calls if c[0]=='POST']);self.bridge.status()
        self.assertEqual(before,len([c for c in self.http.calls if c[0]=='POST']))


class Validation(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.value,_=handoff(self.root)
    def check(self, key, value):
        self.value[key]=value;self.value['sha256']=b.hashed({k:v for k,v in self.value.items() if k!='sha256'})
        with self.assertRaises((ValueError,KeyError,TypeError)):b.validate_handoff(self.root,self.value)
    def test_path_identity_cannot_escape(self):self.check('edit_plan_sha256','../../outside')
    def test_bool_seed(self):self.check('seeds',[True])
    def test_float_seed(self):self.check('seeds',[1.0])
    def test_duplicate_seed(self):self.check('seeds',[11,11])
    def test_budget_boolean(self):self.check('max_candidates',True)
    def test_hidden_extra_budget(self):self.check('max_candidates',17)
    def test_repairs_counted_in_same_allowance(self):self.check('max_candidates',2)
    def test_false_policy(self):self.check('policy',{'eligible_by_preference':False})
    def test_unsupported_profile(self):self.check('preset_id','some-random-model')
    def test_positive_prompt_matches_server_limit(self):self.check('positive','x'*8001)
    def test_native_preset_digest_rejected(self):self.check('preset_sha256','0'*64)
    def test_wrong_model_context_size(self):self.check('size',[64,64])
    def test_duplicate_json_keys(self):
        with self.assertRaises(ValueError):b.decode(b'{"x":1,"x":2}')
    def test_nonfinite_json(self):
        with self.assertRaises(ValueError):b.decode(b'{"x":NaN}')
    def test_escape_reference(self):
        with self.assertRaises(ValueError):b.local(self.root,'../outside')
    def test_symlink_source(self):
        try:(self.root/'link.png').symlink_to(self.root/'source.png')
        except OSError:self.skipTest('Symlink creation unavailable')
        with self.assertRaises(ValueError):b.local(self.root,'link.png')
    def test_png_metadata_requires_explicit_normalization(self):
        data=io.BytesIO();Image.new('RGB',(2,2)).save(data,format='PNG',icc_profile=b'test-profile')
        with self.assertRaisesRegex(ValueError,'ICC'):b.image_info(data.getvalue())

if __name__=='__main__':unittest.main()
