"""Real SQLite + Studio upload mechanics, with no Comfy/model execution."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from http_refusal_transport import atomic_json_post
from test_recipe_shortlist import make_studio
from test_recipe_shortlist_ordered import sources, route
from test_recipe_shortlist_proposal import payload
from studio_workflow.setup_proposal import request as propose


class SetupApplyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.s=make_studio(self.root)
        self.items=sources(self.s,self.root); self.p=route(self.s)
        self.s.experiments=self.root/'experiments'; self.s.experiments.mkdir(exist_ok=True)
        self.s.comfy_root=self.root/'comfy'; (self.s.comfy_root/'input').mkdir(parents=True)
        self.s.upload_count=0
        from server import Studio
        self.s.upload=lambda *a:Studio.upload(self.s,*a)
        self.s._write_json_atomic=lambda path,value:path.write_text(json.dumps(value),encoding='utf-8')
        def stage(key):
            self.s.upload_count+=1
            asset=self.s.assets.get(key)
            value=self.s.upload(asset['filename'],'image/png',self.s.assets.file(key).read_bytes())
            return dict(value,parent_asset=key)
        self.s.asset_reference=stage
        self.before={'version':1,'updatedAt':0,'templateHash':self.p['continuation_capability']['template_sha256'],
                     'pendingInputs':[], 'recipe':{'preset':self.p['id'],'controls':{'positive':'Before'},'batch':2,
                     'references':[],'parent_assets':[],'parent_by_input':{}}}
        self.q=payload(self.p,self.items);self.q['draft']=copy.deepcopy(self.before)
        self.scope=self.s.assets.snapshot()['workspace_id']

    def store(self):
        from studio_workflow.setup_drafts import SetupDrafts
        return SetupDrafts(self.s)

    def command(self,action,**extra):
        return self.store().command(dict(action=action,workspace_id=self.scope,request_id=extra.pop('request_id',action+'-request'),**extra))

    def create(self):return self.command('create',draft=self.before)

    def apply(self,current,report=None,**extra):
        report=report or propose(self.q,self.s)
        return self.command('apply',draft_id=current['draft_id'],expected_revision=current['revision'],
                            proposal_json=report['proposal_json'],approved_proposal_sha256=report['proposal_sha256'],**extra)

    def test_create_replay_and_restart_preserve_the_exact_before_state(self):
        first=self.create();second=self.create()
        self.assertEqual(first['revision'],1);self.assertFalse(first['replayed']);self.assertTrue(second['replayed'])
        self.assertEqual(first['draft_id'],second['draft_id']);self.assertEqual(self.store().get(first['draft_id'])['draft'],self.before)
        self.assertEqual(self.s.upload_count,0)
        self.assertFalse(first['generation_submitted'])

    def test_same_request_different_content_and_wrong_workspace_refuse(self):
        self.create();changed=copy.deepcopy(self.before);changed['recipe']['controls']['positive']='Changed'
        with self.assertRaisesRegex(ValueError,'request|Request'):self.command('create',draft=changed)
        with self.assertRaisesRegex(ValueError,'Workspace|workspace'):
            self.store().command(dict(action='create',workspace_id='f'*32,request_id='other',draft=self.before))

    def test_two_clients_cannot_overwrite_each_other_and_history_is_immutable(self):
        a=self.create();b=copy.deepcopy(self.before);b['recipe']['controls']['positive']='Agent edit'
        new=self.command('replace',draft_id=a['draft_id'],expected_revision=1,draft=b)
        self.assertEqual(new['revision'],2)
        with self.assertRaisesRegex(ValueError,'revision|Revision'):
            self.command('replace',request_id='late-human',draft_id=a['draft_id'],expected_revision=1,draft=self.before)
        self.assertEqual(self.store().get(a['draft_id'],1)['draft'],self.before)
        self.assertEqual(self.store().get(a['draft_id'])['draft'],b)

    def test_apply_stages_all_ordered_sources_once_and_keeps_before_revision(self):
        a=self.create();r=propose(self.q,self.s);result=self.apply(a,r)
        self.assertEqual(result['status'],'committed');self.assertEqual(result['revision'],2)
        self.assertEqual(self.s.upload_count,3)
        refs=result['draft']['recipe']['references']
        self.assertEqual([x['role'] for x in refs],['identity','pose','style'])
        self.assertEqual([x['parent_asset'] for x in refs],[x['asset_id'] for x in self.items])
        self.assertEqual(result['draft']['recipe']['controls']['positive'],self.q['positive'])
        self.assertEqual(result['draft']['recipe']['batch'],1)
        self.assertEqual(self.store().get(a['draft_id'],1)['draft'],self.before)
        self.assertTrue(self.apply(a,r)['replayed']);self.assertEqual(self.s.upload_count,3)
        self.assertFalse(result['generation_submitted'])

    def test_changed_proposal_or_source_never_stages_or_advances(self):
        a=self.create();r=propose(self.q,self.s)
        self.s.assets.file(self.items[1]['asset_id']).write_bytes(b'changed')
        result=self.apply(a,r)
        self.assertEqual(result['status'],'failed');self.assertEqual(self.s.upload_count,0)
        self.assertEqual(self.store().get(a['draft_id'])['revision'],1)
        self.assertEqual(self.store().recover('apply-request')['status'],'failed')

    def test_second_copy_failure_retains_receipt_and_recovery_never_retries(self):
        a=self.create();original=self.s.asset_reference
        def fail(key):
            if key==self.items[1]['asset_id']:raise OSError('disk full fixture')
            return original(key)
        with patch.object(self.s,'asset_reference',side_effect=fail):result=self.apply(a)
        self.assertEqual(result['status'],'failed');self.assertEqual(len(result['staged']),1)
        self.assertEqual(result['attempting_slot'],2);self.assertTrue(result['staging_may_have_occurred'])
        files={str(p):p.read_bytes() for p in (self.s.experiments/'uploads').iterdir()}
        self.assertEqual(self.store().recover('apply-request')['status'],'failed')
        self.assertEqual(self.apply(a)['status'],'failed');self.assertEqual(self.s.upload_count,1)
        self.assertEqual(files,{str(p):p.read_bytes() for p in (self.s.experiments/'uploads').iterdir()})
        self.assertEqual(self.store().get(a['draft_id'])['revision'],1)

    def test_concurrent_stale_apply_refuses_before_staging(self):
        a=self.create();r=propose(self.q,self.s);changed=copy.deepcopy(self.before);changed['recipe']['controls']['positive']='Agent'
        self.command('replace',draft_id=a['draft_id'],expected_revision=1,draft=changed)
        with self.assertRaisesRegex(ValueError,'revision|Revision'):self.apply(a,r)
        self.assertEqual(self.s.upload_count,0)

    def test_restore_appends_an_inverse_revision_without_deleting_staged_inputs(self):
        a=self.create();result=self.apply(a)
        restored=self.command('restore',draft_id=a['draft_id'],expected_revision=2,revision=1)
        self.assertEqual(restored['revision'],3);self.assertEqual(restored['draft'],self.before)
        self.assertEqual(self.store().get(a['draft_id'],2)['draft'],result['draft'])
        self.assertEqual(self.s.upload_count,3)
        self.assertEqual(len(list((self.s.comfy_root/'input').iterdir())),3)

    def test_pending_local_inputs_refuse_checkpoint_without_discarding_anything(self):
        value=copy.deepcopy(self.before);value['pendingInputs']=['reference']
        with self.assertRaisesRegex(ValueError,'pending|local|attach'):self.command('create',draft=value)
        self.assertEqual(self.s.upload_count,0)

    def test_declared_before_state_must_equal_the_shared_revision(self):
        a=self.create();q=copy.deepcopy(self.q);q['draft']['recipe']['controls']['positive']='Forged before'
        result=self.apply(a,propose(q,self.s))
        self.assertEqual(result['status'],'failed');self.assertEqual(self.s.upload_count,0)

    def test_uploaded_byte_mismatch_refuses_before_commit(self):
        a=self.create();original=self.s.asset_reference
        def corrupt(key):
            r=original(key);(self.s.comfy_root/'input'/r['file']).write_bytes(b'bad');return r
        with patch.object(self.s,'asset_reference',side_effect=corrupt):result=self.apply(a)
        self.assertEqual(result['status'],'failed');self.assertEqual(self.store().get(a['draft_id'])['revision'],1)

    def test_interrupted_operation_remains_held_until_explicit_abandon(self):
        a=self.create()
        with patch.object(self.s,'asset_reference',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):self.apply(a)
        old=self.store().recover('apply-request');self.assertEqual(old['status'],'staging')
        with self.assertRaisesRegex(ValueError,'pending|operation|active'):
            self.command('replace',draft_id=a['draft_id'],expected_revision=1,draft=self.before)
        ended=self.command('abandon',draft_id=a['draft_id'],expected_revision=1,operation_id='apply-request')
        self.assertEqual(ended['status'],'abandoned');self.assertEqual(self.store().get(a['draft_id'])['revision'],1)
        self.assertEqual(self.s.upload_count,0)

    def test_restore_refuses_changed_graph_even_without_a_browser_template_hash(self):
        self.before['templateHash']=None;self.q['draft']=copy.deepcopy(self.before)
        a=self.create();b=self.apply(a)
        _,path=self.s.graph_for(self.p);path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'graph|Graph'):
            self.command('restore',draft_id=a['draft_id'],expected_revision=2,revision=1)
        self.assertEqual(self.store().get(a['draft_id'])['revision'],2)

    def test_load_checks_checkpoint_graph_when_browser_has_no_template_hash(self):
        self.before['templateHash']=None;a=self.create()
        _,path=self.s.graph_for(self.p);path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'graph|Graph'):self.store().check(a['draft_id'],1)

    def test_checkpoint_refuses_an_old_declared_graph_without_registering_a_draft(self):
        self.before['templateHash']='0'*64
        with self.assertRaisesRegex(ValueError,'graph|Graph'):self.create()
        self.assertEqual(self.store().list()['drafts'],[])

    def test_two_independent_runtime_locks_cannot_overwrite_one_shared_revision(self):
        from concurrent.futures import ThreadPoolExecutor
        from studio_workflow.setup_drafts import SetupDrafts
        a=self.create();other=object.__new__(type(self.s));other.__dict__.update(self.s.__dict__);other.lock=threading.RLock();barrier=threading.Barrier(2)
        def edit(index):
            store=SetupDrafts([self.s,other][index]);barrier.wait(5)
            q=dict(action='replace',workspace_id=self.scope,request_id='concurrent-'+str(index),draft_id=a['draft_id'],expected_revision=1,draft=self.before)
            try:return store.command(q)['status']
            except ValueError:return 'conflict'
        with ThreadPoolExecutor(2) as pool:results=list(pool.map(edit,(0,1)))
        self.assertCountEqual(results,['committed','conflict']);self.assertEqual(self.store().get(a['draft_id'])['revision'],2)

    def test_backend_and_input_changes_prevent_restore_without_copy_or_deletion(self):
        a=self.create();b=self.apply(a)
        self.s.comfy_url='http://127.0.0.1:9999'
        with self.assertRaisesRegex(ValueError,'backend'):self.command('restore',draft_id=a['draft_id'],expected_revision=2,revision=1)
        self.s.comfy_url='http://127.0.0.1:8188'
        source=b['inputs'][0];(self.s.comfy_root/'input'/source['file']).write_bytes(b'changed')
        with self.assertRaises((ValueError,OSError)):self.store().check(a['draft_id'],2)
        self.assertEqual(self.s.upload_count,3);self.assertEqual(self.store().get(a['draft_id'])['revision'],2)

    def test_revision_budget_is_checked_before_source_copy(self):
        a=self.create()
        with patch('studio_workflow.setup_drafts.MAX_REVISIONS',1),self.assertRaisesRegex(ValueError,'revision'):
            self.apply(a)
        self.assertEqual(self.s.upload_count,0)
        with patch('studio_workflow.setup_drafts.MAX_STORAGE',1),self.assertRaisesRegex(ValueError,'budget'):
            self.apply(a)
        self.assertEqual(self.s.upload_count,0)

    def test_corrupted_receipt_is_retained_and_not_used_to_replay(self):
        a=self.create()
        with self.s.assets.connection() as db:db.execute("UPDATE setup_operations_v1 SET receipt='{}'")
        with self.assertRaises((ValueError,KeyError)):self.create()
        with self.s.assets.connection() as db:self.assertEqual(db.execute('SELECT receipt FROM setup_operations_v1').fetchone()[0],'{}')
        self.assertEqual(self.store().get(a['draft_id'])['revision'],1);self.assertEqual(self.s.upload_count,0)

    def test_real_qwen_staged_drafts_compile_to_the_reviewed_prompt_and_transforms(self):
        import studio_browser_smoke as fixture
        from app.references import compile_references
        from test_recipe_shortlist import ROOT
        self.s.presets=copy.deepcopy(fixture.CATALOG['presets']);self.s.catalog_path=ROOT/'presets/catalog.json'
        self.s.graph_for=lambda p:(json.loads((ROOT/p['graph']).read_bytes()),ROOT/p['graph'])
        self.s.requirements={p['id']:[] for p in self.s.presets}
        for count in (1,2,3):
            p=next(p for p in self.s.presets if p['id']==f'qwen-{count}ref')
            self.before['recipe']['preset']=p['id'];self.before['templateHash']=p['continuation_capability']['template_sha256']
            q=payload(p,self.items[:count]);q['draft']=copy.deepcopy(self.before);q['guidance']=q['guidance'][:count]
            a=self.command('create',request_id='qwen-before-'+str(count),draft=self.before)
            report=propose(q,self.s);b=self.apply(a,report,request_id='qwen-apply-'+str(count))
            self.assertEqual(b['status'],'committed',b)
            graph,_=self.s.graph_for(p);node,field=p['positive'];graph[node]['inputs'][field]=b['draft']['recipe']['controls']['positive']
            actual=compile_references(p,graph,b['draft']['recipe']['references'],self.s.experiments/'uploads')
            self.assertEqual(graph[node]['inputs'][field],report['intent']['compiled_positive'])
            self.assertEqual([x['transform'] for x in actual],[x['transform'] for x in report['intent']['sources']])
        self.assertEqual(self.s.upload_count,6)


class SetupApplyTransportTests(unittest.TestCase):
    def setUp(self):
        SetupApplyTests.setUp(self)
        from test_server import server
        from studio_workflow.sdk import WorkflowClient
        from urllib.request import Request
        self.http=server.create_server(self.root,port=0,studio_factory=lambda _:self.s)
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
        def close():self.http.shutdown();self.http.server_close();self.thread.join(5)
        self.addCleanup(close)
        self.url='http://127.0.0.1:'+str(self.http.server_port);self.client=WorkflowClient(self.url,5)
        def wire(url,*args,**kwargs):
            kwargs['headers']={**kwargs.get('headers',{}),'Host':'127.0.0.1:8191','Origin':'http://127.0.0.1:8191'}
            return Request(url,*args,**kwargs)
        self.patch=patch('studio_workflow.client.Request',side_effect=wire);self.patch.start();self.addCleanup(self.patch.stop)

    def test_actual_http_sdk_author_bridge_and_cli_recover_same_revision(self):
        from studio_workflow.agent_bridge import AgentBridge
        from studio_workflow.setup_draft_client import main
        import contextlib,io
        drafts=self.client.setup_drafts
        current=drafts.create(self.before,workspace_id=self.scope,request_id='http-create')
        report=propose(self.q,self.s)
        command=dict(action='apply',workspace_id=self.scope,request_id='http-apply',draft_id=current['draft_id'],
                     expected_revision=1,proposal_json=report['proposal_json'],approved_proposal_sha256=report['proposal_sha256'])
        read=AgentBridge(self.client,'read').invoke('setup_draft_command',{'command_json':json.dumps(command)})
        self.assertFalse(read['ok']);self.assertEqual(self.s.upload_count,0)
        result=AgentBridge(self.client,'author').invoke('setup_draft_command',{'command_json':json.dumps(command)})
        self.assertTrue(result['ok'],result);saved=json.loads(result['data_json']);self.assertEqual(saved['revision'],2)
        self.assertEqual(drafts.recover('http-apply')['record_sha256'],saved['record_sha256'])
        output=io.StringIO()
        with contextlib.redirect_stdout(output):code=main(['--url',self.url,'recover','http-apply'])
        self.assertEqual(code,0);self.assertEqual(json.loads(output.getvalue())['revision'],2)
        self.assertEqual(self.s.upload_count,3)

    def test_origin_type_and_duplicate_input_guards_precede_writes(self):
        from studio_workflow.setup_drafts import PREFIX
        for raw,headers,status in [(b'{}',{'Origin':'https://other.invalid'},403),
                                  (b'{}',{'Host':'other.invalid'},403),
                                  (b'{}',{'Content-Type':'text/plain'},400),
                                  (b'{"action":"create","action":"apply"}',{},400)]:
            # Same unread-body refusal shape as the proposal fixture (#477).
            wire={'Host':'127.0.0.1:8191','Origin':'http://127.0.0.1:8191','Content-Type':'application/json',**headers}
            with self.subTest(headers=headers):
                self.assertEqual(atomic_json_post(self.http.server_port,PREFIX,raw,host=wire['Host'],origin=wire['Origin'],content_type=wire['Content-Type'])[0],status)
        self.assertEqual(self.s.upload_count,0)

    def test_client_transport_loss_reports_unknown_and_never_retries_the_write(self):
        from studio_workflow.setup_draft_client import SetupDraftClient,UnknownSetupOutcome
        seen=[]
        def transport(path,value=None):
            seen.append((path,value));raise OSError('response disappeared')
        c=SetupDraftClient(transport)
        with self.assertRaises(UnknownSetupOutcome) as error:
            c.create(self.before,workspace_id=self.scope,request_id='lost-create')
        self.assertEqual(error.exception.request_id,'lost-create');self.assertEqual(len(seen),1)

    def test_mismatched_receipt_is_unknown_for_writes_not_false_success(self):
        from studio_workflow.setup_draft_client import SetupDraftClient,UnknownSetupOutcome
        current=self.client.setup_drafts.create(self.before,workspace_id=self.scope,request_id='real')
        c=SetupDraftClient(lambda *_:current)
        with self.assertRaises(UnknownSetupOutcome):c.create(self.before,workspace_id=self.scope,request_id='different')

    def test_server_failure_after_write_is_unknown_to_client_not_a_safe_retry(self):
        from studio_workflow.setup_draft_client import SetupDraftClient,UnknownSetupOutcome
        from studio_workflow.client import ClientError
        calls=[]
        def transport(path,q):
            calls.append(q);raise ClientError(503,{'error':'reply unavailable after possible commit'})
        with self.assertRaises(UnknownSetupOutcome) as exc:
            SetupDraftClient(transport).create(self.before,workspace_id=self.scope,request_id='uncertain')
        self.assertEqual(exc.exception.request_id,'uncertain');self.assertEqual(len(calls),1)

    def test_malformed_command_shapes_are_validation_errors_before_any_write(self):
        from studio_workflow.setup_drafts import validate_command
        base=dict(action='create',workspace_id=self.scope,request_id='invalid-shapes',draft=self.before)
        for change in ({'action':[]},{'action':None},{'workspace_id':[]},{'workspace_id':'wrong'},
                       {'request_id':False},{'draft':None}):
            with self.subTest(change=change),self.assertRaises(ValueError):validate_command({**base,**change})


class SetupApplyBrowserContracts(unittest.TestCase):
    def test_actual_controller_contracts(self):
        import shutil,subprocess
        node=shutil.which('node')
        if not node:self.skipTest('Node is not installed')
        result=subprocess.run([node,'--test',str(Path(__file__).with_name('setup_apply_client.cjs'))],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)


import importlib.util
@unittest.skipUnless(importlib.util.find_spec('mcp'),'Optional official MCP SDK')
class SetupApplyMCPProtocol(unittest.IsolatedAsyncioTestCase):
    async def test_author_protocol_applies_and_read_protocol_only_observes_original_receipt(self):
        from types import SimpleNamespace
        from mcp.shared.memory import create_connected_server_and_client_session
        from studio_workflow.mcp_server import build_server
        from studio_workflow.agent_bridge import AgentBridge
        from studio_workflow.setup_draft_http import route
        f=SetupApplyTests();f.setUp()
        try:
            a=f.create();r=propose(f.q,f.s);calls=[]
            q=dict(action='apply',workspace_id=f.scope,request_id='protocol-apply',draft_id=a['draft_id'],expected_revision=1,proposal_json=r['proposal_json'],approved_proposal_sha256=r['proposal_sha256'])
            def transport(path,body=None):calls.append((path,body));return route(path,body,f.s)
            async with create_connected_server_and_client_session(build_server(AgentBridge(SimpleNamespace(request=transport),'author')),raise_exceptions=True) as c:
                tool=next(t for t in (await c.list_tools()).tools if t.name=='setup_draft_command')
                self.assertFalse(tool.annotations.readOnlyHint)
                result=await c.call_tool('setup_draft_command',{'command_json':json.dumps(q)})
                self.assertFalse(result.isError);self.assertEqual(json.loads(result.structuredContent['data_json'])['revision'],2)
            async with create_connected_server_and_client_session(build_server(AgentBridge(SimpleNamespace(request=transport),'read')),raise_exceptions=True) as c:
                self.assertNotIn('setup_draft_command',[t.name for t in (await c.list_tools()).tools])
                result=await c.call_tool('setup_draft_recover',{'request_id':'protocol-apply'})
                self.assertFalse(result.isError);self.assertEqual(json.loads(result.structuredContent['data_json'])['revision'],2)
            self.assertEqual(f.s.upload_count,3);self.assertEqual(len(calls),2);self.assertIsNone(calls[-1][1])
        finally:f.doCleanups()
