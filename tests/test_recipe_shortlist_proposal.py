"""Proposals are exact review data, never recipe application or execution."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from http_refusal_transport import atomic_json_post
from test_recipe_shortlist import make_studio
from test_recipe_shortlist_ordered import sources, route, save_graph
from studio_workflow.http_extension import post

PREFIX='/api/workflow-studio/setup-proposal'


def draft():
    return {'version':1, 'updatedAt':0, 'templateHash':'a'*64, 'pendingInputs':['reference'],
            'recipe':{'preset':'previous', 'controls':{'positive':'Keep this exact brief', 'seed':'9223372036854775807','cfg':'5'},
                      'batch':2, 'references':[], 'parent_assets':['old-source'], 'parent_by_input':{'reference':'old-source'}}}


def payload(p, items):
    return {'goal':'reference-image','preset_id':p['id'], 'expected_template_sha256':p['continuation_capability']['template_sha256'],
            'sources':copy.deepcopy(items), 'draft':draft(), 'positive':'Keep this exact brief', 'negative':'',
            'guidance':[{'contribution':'face','avoid':'background'},{'contribution':'stance','avoid':'costume'},{'contribution':'ink','avoid':'identity'}]}


class SetupProposalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.s=make_studio(self.root)
        self.items=sources(self.s,self.root);self.p=route(self.s)
        graph,_=self.s.graph_for(self.p)
        graph['sampler']={'class_type':'KSampler','inputs':{'seed':9223372036854775807,'cfg':2.0,'steps':12}}
        self.p.update(seed=['sampler','seed'],cfg=['sampler','cfg'],steps=['sampler','steps'])
        graph['scale']={'class_type':'ImageScaleToTotalPixels','inputs':{'image':['1',0],'megapixels':1,'upscale_method':'lanczos'}}
        graph['join']['inputs']['image0']=['scale',0]
        save_graph(self.s,self.p,graph)
        self.q=payload(self.p,self.items)

    def call(self,value=None):return post(PREFIX,self.q if value is None else value,self.s)

    def test_review_contains_complete_before_and_all_ordered_proposed_sources(self):
        before=copy.deepcopy(self.q);assets=self.s.assets.snapshot()
        r=self.call()
        self.assertEqual(r['format'],'studio.setup-proposal/v1')
        self.assertEqual(r['request'],self.q)
        self.assertEqual(r['before'],self.q['draft'])
        self.assertEqual(r['intent']['controls']['positive'],'Keep this exact brief')
        self.assertEqual(r['intent']['controls']['seed'],'9223372036854775807')
        self.assertEqual(r['intent']['batch'],1)
        self.assertEqual([x['asset_id'] for x in r['intent']['sources']],[x['asset_id'] for x in self.items])
        self.assertEqual([x['slot'] for x in r['intent']['sources']],[1,2,3])
        self.assertTrue(all(x['staged'] is False for x in r['intent']['sources']))
        self.assertNotIn('reference',r['intent']['controls'])
        self.assertNotIn('example',r['intent']['controls']['positive'])
        self.assertEqual(r['intent']['sources'][0]['transform']['source_size'],[32,48])
        self.assertIn('Picture 2 — pose: use stance.',r['intent']['compiled_positive'])
        self.assertTrue(any(x['section']=='Pending local inputs' and x['before']==['reference'] for x in r['diff']))
        self.assertEqual(r['precondition']['scope'],'caller-declared browser draft; not a server revision')
        self.assertFalse(r['can_apply']);self.assertFalse(r['execution_authorized']);self.assertFalse(r['generation_submitted'])
        self.assertEqual(self.q,before);self.assertEqual(self.s.assets.snapshot(),assets)
        self.assertTrue(all(c in ['catalog','nodes','requirements:roles','memory:roles'] for c in self.s.calls),self.s.calls)

    def test_identity_binds_draft_sources_order_wording_and_contributions(self):
        first=self.call();self.assertEqual(first['proposal_sha256'],self.call()['proposal_sha256'])
        for modify in [lambda q:q['draft']['recipe']['controls'].update(cfg='6'),lambda q:q.update(positive='other'),
                       lambda q:q['sources'].reverse(),lambda q:q['guidance'][1].update(avoid='changed')]:
            value=copy.deepcopy(self.q);modify(value)
            self.assertNotEqual(first['proposal_sha256'],self.call(value)['proposal_sha256'])

    def test_invalid_request_is_rejected_before_studio_access(self):
        from studio_workflow.setup_proposal import query
        bad=[{**self.q,'approved':True},{**self.q,'sources':None},{**self.q,'draft':{}},
             {**self.q,'positive':'x'*8001},{**self.q,'negative':False},{**self.q,'guidance':[]},
             {**self.q,'expected_template_sha256':'b'}, {**self.q,'guidance':[{'contribution':{},'avoid':''}]*3}]
        for q in bad:
            with self.subTest(q=q),self.assertRaises(ValueError):query(q)
        q=copy.deepcopy(self.q);q['draft']['recipe']['controls']['seed']=9223372036854775807
        with self.assertRaisesRegex(ValueError,'integer|precision|text'):query(q)
        self.assertEqual(self.s.calls,[])

    def test_changed_target_or_nonprimary_source_refuses_without_fallback(self):
        with self.assertRaisesRegex(ValueError,'changed|identity'):self.call({**self.q,'expected_template_sha256':'f'*64})
        self.s.assets.file(self.items[1]['asset_id']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'Picture 2|changed'):self.call()

    def test_change_during_observation_or_after_compilation_refuses(self):
        original=self.s.preset_requirements
        def mutate(*a,**kw):
            self.s.assets.file(self.items[2]['asset_id']).write_bytes(b'changed');return original(*a,**kw)
        with patch.object(self.s,'preset_requirements',side_effect=mutate),self.assertRaisesRegex(ValueError,'Picture 3|changed'):self.call()

    def test_unknown_extra_controls_and_unbound_wording_cannot_disappear(self):
        self.p['positive']=None
        with self.assertRaisesRegex(ValueError,'wording|positive|prompt'):self.call()

    def test_ambiguous_or_missing_slot_refuses_instead_of_compacting(self):
        self.p['reference_slots'][1]['binding']=['1','image']
        with self.assertRaisesRegex(ValueError,'binding|Picture|slot'):self.call()

    def test_source_role_is_not_silently_relabelled_for_named_slots(self):
        q=copy.deepcopy(self.q);q['sources'][1]['role']='source'
        with self.assertRaisesRegex(ValueError,'role|Picture 2'):self.call(q)

    def test_default_settings_are_recomputed_from_exact_graph_not_catalog_advice(self):
        self.p['defaults']={'cfg':999,'positive':'invented'}
        r=self.call();self.assertEqual(r['intent']['controls']['cfg'],'2.0')
        self.assertEqual(r['intent']['controls']['positive'],self.q['positive'])

    def test_compiled_role_wording_and_transform_match_actual_reference_compiler(self):
        from app.references import compile_references
        r=self.call();graph,_=self.s.graph_for(self.p);graph=copy.deepcopy(graph)
        graph['text']['inputs']['text']=self.q['positive']
        uploads=self.root/'uploads';uploads.mkdir()
        records=[]
        for i,item in enumerate(self.items):
            name=f'image{i}.png';(uploads/name).write_bytes(self.s.assets.file(item['asset_id']).read_bytes())
            records.append({'file':name,**item,**self.q['guidance'][i]})
        actual=compile_references(self.p,graph,records,uploads)
        self.assertEqual(r['intent']['compiled_positive'],graph['text']['inputs']['text'])
        self.assertEqual([x['transform'] for x in r['intent']['sources']],[x['transform'] for x in actual])

    def test_shared_client_refuses_unbound_or_modified_proposal(self):
        from studio_workflow.setup_proposal import observe
        r=self.call()
        for mutate in [lambda x:x.update(can_apply=True),lambda x:x['intent']['sources'].reverse(),
                       lambda x:x['before']['recipe']['controls'].update(positive='other'),lambda x:x.update(proposal_sha256='a'*64)]:
            bad=copy.deepcopy(r);mutate(bad)
            with self.subTest(bad=bad),self.assertRaises(ValueError):observe(lambda *_:bad,self.q)
        self.assertEqual(observe(lambda *_:r,self.q),r)

    def test_http_sdk_read_agent_parity_and_no_executable_payload(self):
        from studio_workflow.sdk import WorkflowClient
        from studio_workflow.agent_bridge import AgentBridge
        client=WorkflowClient();client.request=lambda path,data:post(path,data,self.s)
        r=client.setup_proposal(self.q)
        bridge=AgentBridge(client=client,mode='read')
        output=bridge.invoke('recipe_setup_proposal',{'request_json':json.dumps(self.q)})
        self.assertTrue(output['ok'],output)
        agent=json.loads(output['data_json']);self.assertEqual(agent['proposal_sha256'],r['proposal_sha256'])
        self.assertFalse(agent['can_apply']);self.assertNotIn('ticket',agent);self.assertNotIn('graph',agent)

    def test_draft_lineage_uses_the_existing_browser_singular_attribution(self):
        r=self.call()
        self.assertEqual(r['before']['recipe']['parent_by_input'],{'reference':'old-source'})
        self.assertEqual(r['intent']['lineage']['by_input'],{'reference':self.items[0]['asset_id']})
        bad=copy.deepcopy(self.q);bad['draft']['recipe']['parent_by_input']['reference']=['old-source']
        with self.assertRaises(ValueError):self.call(bad)

    def test_exif_oriented_source_geometry_matches_the_compiler_capture(self):
        from PIL import Image
        path=self.root/'oriented.jpg';exif=Image.Exif();exif[274]=6
        Image.new('RGB',(48,32),'white').save(path,exif=exif)
        key=self.s.assets.register({'id':'oriented','outputs':[{'filename':path.name,'media_type':'image'}]},0,path)
        self.q['sources'][0]={'asset_id':key,'sha256':self.s.assets.get(key)['sha256'],'role':'identity'}
        r=self.call();self.assertEqual([r['intent']['sources'][0][k] for k in ('width','height')],[32,48])
        self.assertEqual(r['intent']['sources'][0]['transform']['source_size'],[32,48])

    def test_image_safety_warning_refuses_before_large_decode(self):
        from PIL import Image
        with patch.object(Image,'MAX_IMAGE_PIXELS',1000),self.assertRaisesRegex(ValueError,'Picture 1'):
            self.call()

    def test_catalog_runtime_and_raw_graph_drift_during_projection_refuse(self):
        from app.references import reference_transform as original
        for what in ('runtime','catalog','graph'):
            with self.subTest(what=what):
                old=self.s.catalog_path.read_bytes();graph,path=self.s.graph_for(self.p);raw=path.read_bytes();op=self.s.backends.operation
                def mutate(*args,**kwargs):
                    if what=='runtime':self.s.backends.operation={'id':'changed-and-returned'}
                    elif what=='catalog':self.s.catalog_path.write_bytes(b'{"changed":true}')
                    else:path.write_bytes(raw+b' ')
                    return original(*args,**kwargs)
                try:
                    with patch('app.references.reference_transform',side_effect=mutate),self.assertRaisesRegex(ValueError,'context changed'):self.call()
                finally:self.s.catalog_path.write_bytes(old);path.write_bytes(raw);self.s.backends.operation=op

    def test_extreme_reference_rounding_refuses_before_vae_division(self):
        from app.references import reference_transform
        graph,_=self.s.graph_for(self.p)
        with self.assertRaisesRegex(ValueError,'aspect ratio'):
            reference_transform(self.p,graph,'1',{'width':1,'height':10000000})

    def test_parsed_graph_cannot_borrow_identity_from_different_raw_bytes(self):
        graph,path=self.s.graph_for(self.p);graph['sampler']['inputs']['cfg']=99
        with patch.object(self.s,'graph_for',return_value=(graph,path)),self.assertRaisesRegex(ValueError,'graph.*(bytes|identity)|parsed'):
            self.call()

    def test_semantically_unbound_reply_refuses_even_with_recomputed_digest(self):
        from studio_workflow.setup_proposal import observe
        from studio_workflow.core import canonical
        r=self.call();r['intent']['controls']['positive']='not the reviewed text'
        r['proposal_json']=canonical({k:v for k,v in r.items() if k not in ('proposal_sha256','proposal_json')}).decode()
        r['proposal_sha256']=hashlib.sha256(r['proposal_json'].encode()).hexdigest()
        with self.assertRaises(ValueError):observe(lambda *_:r,self.q)

    def test_client_snapshots_before_a_transport_mutates_the_supplied_object(self):
        from studio_workflow.setup_proposal import observe
        old=copy.deepcopy(self.q)
        def transport(path,body):
            self.q['positive']='changed by caller';return post(path,body,self.s)
        result=observe(transport,self.q)
        self.assertEqual(result['request'],old)


class SetupProposalTransportTests(unittest.TestCase):
    def setUp(self):
        from test_recipe_shortlist_integration import ShortlistHTTPTests
        ShortlistHTTPTests.setUp(self)
        self.items=sources(self.s,self.root);self.p=route(self.s);self.q=payload(self.p,self.items)
    def tearDown(self):
        from test_recipe_shortlist_integration import ShortlistHTTPTests
        ShortlistHTTPTests.tearDown(self)
    def send(self,value=None,**extra):
        from http.client import HTTPConnection
        headers={'Host':'127.0.0.1:8191','Origin':'http://127.0.0.1:8191','Content-Type':'application/json',**extra}
        body=json.dumps(self.q if value is None else value).encode('utf-8')
        # A Host/Origin/media-type refusal answers before the declared body is read, so the
        # reply must be read atomically rather than over a reusable http.client connection
        # the server may close on the unread bytes (#477).
        if extra:
            # Only these three reach the wire below, so a later override of anything else must
            # fail loudly rather than assert a refusal against a request that never carried it.
            assert set(extra)<={'Host','Origin','Content-Type'},'This fixture forwards only Host, Origin and Content-Type'
            return atomic_json_post(self.http.server_port,PREFIX,body,host=headers['Host'],origin=headers['Origin'],content_type=headers['Content-Type'])
        c=HTTPConnection('127.0.0.1',self.http.server_port,timeout=10)
        try:
            c.request('POST',PREFIX,body,headers)
            r=c.getresponse();return r.status,json.loads(r.read())
        finally:c.close()
    def test_actual_http_sdk_cli_and_read_agent_agree(self):
        import contextlib
        import io
        from studio_workflow.setup_proposal import main
        from studio_workflow.agent_bridge import AgentBridge
        status,r=self.send();self.assertEqual(status,200,r)
        sdk=self.client.setup_proposal(self.q)
        agent=AgentBridge(self.client,'read').invoke('recipe_setup_proposal',{'request_json':json.dumps(self.q)})
        self.assertTrue(agent['ok'],agent);self.assertEqual(json.loads(agent['data_json'])['proposal_sha256'],r['proposal_sha256'])
        path=self.root/'request.json';path.write_text(json.dumps(self.q),encoding='utf-8');output=io.StringIO()
        with contextlib.redirect_stdout(output):code=main([str(path),'--url',self.url])
        self.assertEqual(code,0,output.getvalue())
        self.assertEqual(json.loads(output.getvalue())['proposal_sha256'],sdk['proposal_sha256'])
        self.assertEqual(self.s.jobs,{})
    def test_host_origin_and_type_guards_precede_source_inspection(self):
        for headers,status in [({'Host':'other.invalid'},403),({'Origin':'https://other.invalid'},403),({'Content-Type':'text/plain'},400)]:
            with self.subTest(headers=headers):self.assertEqual(self.send(**headers)[0],status)
        self.assertEqual(self.s.calls,[])
    def test_bounded_cli_null_duplicate_and_oversized_input_refuse_without_request(self):
        import contextlib
        import io
        from studio_workflow.setup_proposal import main
        from studio_workflow.sdk import WorkflowClient
        path=self.root/'bad.json'
        with patch.object(WorkflowClient,'setup_proposal',side_effect=AssertionError('No request')):
            for raw in [b'null',b'{"goal":"a","goal":"b"}',b'{"goal":NaN}',b'x'*131073]:
                path.write_bytes(raw)
                with contextlib.redirect_stderr(io.StringIO()):self.assertEqual(main([str(path),'--url',self.url]),2)
    def test_source_error_is_structured_in_sdk_and_read_agent(self):
        from studio_workflow.agent_bridge import AgentBridge
        from studio_workflow.client import ClientError
        self.q['sources'][1]['sha256']='e'*64
        with self.assertRaises(ClientError) as caught:self.client.setup_proposal(self.q)
        self.assertEqual(caught.exception.status,400);self.assertIn('Picture 2',str(caught.exception))
        result=AgentBridge(self.client,'read').invoke('recipe_setup_proposal',{'request_json':json.dumps(self.q)})
        self.assertFalse(result['ok']);self.assertEqual(result['error']['code'],'setup_proposal_unavailable')
        self.assertEqual(self.s.jobs,{})


class ActualProposalCatalogTests(unittest.TestCase):
    def test_actual_qwen_slots_transforms_and_prompt_equal_actual_compiler(self):
        from test_recipe_shortlist_integration import ActualCatalogTests
        from app.references import compile_references
        f=ActualCatalogTests();f.setUp()
        try:
            items=sources(f.s,f.root);uploads=f.root/'review-uploads';uploads.mkdir()
            for i,item in enumerate(items):(uploads/f'picture{i}.png').write_bytes(f.s.assets.file(item['asset_id']).read_bytes())
            with patch.object(f.s,'node_info',return_value={'SaveImage':{}}):
                for count in (1,2,3):
                    preset=next(p for p in f.s.catalog()['presets'] if p['id']==f'qwen-{count}ref')
                    q=payload(preset,items[:count]);q['guidance']=q['guidance'][:count]
                    r=post(PREFIX,q,f.s);graph,_=f.s.graph_for(preset);original=copy.deepcopy(graph)
                    node,key=preset['positive'];graph[node]['inputs'][key]=q['positive']
                    refs=[{'file':f'picture{i}.png',**x,**q['guidance'][i]} for i,x in enumerate(items[:count])]
                    compiled=compile_references(preset,graph,refs,uploads)
                    self.assertEqual(r['intent']['compiled_positive'],graph[node]['inputs'][key])
                    self.assertEqual([x['transform'] for x in r['intent']['sources']],[x['transform'] for x in compiled])
                    self.assertEqual(f.s.graph_for(preset)[0],original)
                    self.assertEqual(len(r['intent']['sources']),count);self.assertEqual(f.s.jobs,{})
        finally:f.doCleanups()


class ProposalJSContracts(unittest.TestCase):
    def test_actual_client_contracts(self):
        import subprocess
        import shutil
        if not shutil.which('node'):self.skipTest('Node not installed')
        r=subprocess.run(['node','--test','tests/setup_proposal_client.cjs'],cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=20)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)


import importlib.util
@unittest.skipUnless(importlib.util.find_spec('mcp'),'Optional official MCP SDK')
class SetupProposalMCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_official_read_protocol_preserves_exact_review_and_has_no_apply(self):
        from types import SimpleNamespace
        from mcp.shared.memory import create_connected_server_and_client_session
        from studio_workflow.mcp_server import build_server
        from studio_workflow.agent_bridge import AgentBridge
        with tempfile.TemporaryDirectory() as root:
            s=make_studio(root);items=sources(s,Path(root));p=route(s);q=payload(p,items);calls=[]
            def transport(path,body=None):calls.append(path);return post(path,body,s)
            async with create_connected_server_and_client_session(build_server(AgentBridge(SimpleNamespace(request=transport),'read')),raise_exceptions=True) as client:
                tool=next(x for x in (await client.list_tools()).tools if x.name=='recipe_setup_proposal')
                self.assertTrue(tool.annotations.readOnlyHint);self.assertEqual(calls,[])
                reply=await client.call_tool('recipe_setup_proposal',{'request_json':json.dumps(q)})
                self.assertFalse(reply.isError);r=json.loads(reply.structuredContent['data_json'])
                self.assertEqual(r['before'],q['draft']);self.assertEqual(len(r['intent']['sources']),3);self.assertFalse(r['can_apply'])
                self.assertEqual(calls,[PREFIX]);self.assertEqual(s.jobs,{})
