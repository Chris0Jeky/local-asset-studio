"""Selected-asset advice uses real Workspace bytes, never a staging shortcut."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_recipe_shortlist import make_studio
from studio_workflow.shortlist import query, request, observe
from studio_workflow.sdk import WorkflowClient
from studio_workflow.agent_bridge import AgentBridge
from workspace import AssetWorkspace
from PIL import Image
import continuation


def add_source(studio, root, key='source', color='white'):
    studio.assets = AssetWorkspace(root)
    studio.jobs = {}
    path = Path(root)/(key+'.png'); Image.new('RGB', (32,48), color).save(path)
    job = {'id':key, 'outputs':[{'filename':path.name,'media_type':'image'}]}
    asset_id = studio.assets.register(job,0,path)
    return {'source_asset_id':asset_id,'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'source_role':'source'}


def add_route(studio, key='edit', slots=False):
    preset = studio.add(key, 'instruction-edit' if slots else 'image-to-image',1)
    graph = {'1':{'class_type':'LoadImage','inputs':{'image':'example.png'}},
             '2':{'class_type':'SaveImage','inputs':{'images':['1',0]}},
             '3':{'class_type':'Text','inputs':{'text':'example'}}}
    preset['reference']=['1','image'];preset['positive']=['3','text']
    if slots:preset['reference_slots']=[{'binding':['1','image'],'role':'identity'}]
    path=studio.root/preset['graph'];path.write_text(json.dumps(graph),encoding='utf-8')
    preset['continuation_capability']['template_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    return preset


class SourceShortlistTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.s=make_studio(self.root)
        self.source=add_source(self.s,self.root)
        self.q={'goal':'edit-image','reference_count':1,**self.source}
        add_route(self.s)
    def test_optional_exact_source_query_and_legacy_shape(self):
        self.assertEqual(query(self.q)['source_asset_id'],self.source['source_asset_id'])
        self.assertNotIn('source_asset_id',query({'goal':'new-image'}))
        for field in self.source:
            bad={**self.q};bad.pop(field)
            with self.subTest(field=field),self.assertRaises(ValueError):query(bad)
        for delta in [{'reference_count':0},{'source_role':'magic'},{'source_sha256':'0'},{'source_asset_id':'../source'},{'source_asset_id':True}]:
            with self.subTest(delta=delta),self.assertRaises(ValueError):query({**self.q,**delta})
    def test_exact_bytes_and_first_binding_are_observed_without_staging(self):
        before=self.s.assets.snapshot()
        result=request(self.q,self.s)
        self.assertEqual(result['source']['asset_id'],self.source['source_asset_id'])
        self.assertEqual(result['source']['sha256'],self.source['source_sha256'])
        self.assertTrue(result['source']['bytes_verified']);self.assertFalse(result['source']['staged'])
        self.assertEqual([result['source']['width'],result['source']['height']],[32,48])
        row=result['candidates'][0];self.assertEqual(row['source_assignment']['binding'],['1','image'])
        self.assertEqual(row['source_assignment']['role_mode'],'whole-image')
        self.assertEqual(row['status'],'unknown') # Not staged; observation is not preparation.
        self.assertEqual(before,self.s.assets.snapshot());self.assertEqual(self.s.jobs,{})
        self.assertFalse((self.root/'uploads').exists())
        self.assertNotIn('positive',result['source']);self.assertNotIn('path',result['source'])
    def test_changed_or_wrong_source_hash_never_falls_back_to_count_only(self):
        with self.assertRaisesRegex(ValueError,'changed|identity'):
            request({**self.q,'source_sha256':'a'*64},self.s)
        self.s.assets.file(self.source['source_asset_id']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'changed'):request(self.q,self.s)
    def test_missing_trashed_nonimage_and_oversized_sources_are_rejected(self):
        asset_id=self.source['source_asset_id'];path=self.s.assets.file(asset_id)
        for column,value in [('trashed_at',1),('media_type','video')]:
            before=self.s.assets.get(asset_id)[column]
            with self.s.assets.connection() as db:db.execute('UPDATE assets SET '+column+'=? WHERE id=?',(value,asset_id))
            with self.subTest(column=column),self.assertRaises(ValueError):request(self.q,self.s)
            with self.s.assets.connection() as db:db.execute('UPDATE assets SET '+column+'=? WHERE id=?',(before,asset_id))
        with path.open('wb') as stream:stream.truncate(20*1024*1024+1)
        with self.assertRaisesRegex(ValueError,'20 MiB'):request(self.q,self.s)
        path.unlink()
        with self.assertRaises(ValueError):request(self.q,self.s)
    def test_source_changed_during_observation_is_rechecked(self):
        def mutate(refresh=False):
            self.s.assets.file(self.source['source_asset_id']).write_bytes(b'changed during check')
            return self.s._schema
        with patch.object(self.s,'node_info',side_effect=mutate),self.assertRaisesRegex(ValueError,'changed'):
            request(self.q,self.s)
    def test_role_is_prompt_guidance_only_for_explicit_slots(self):
        add_route(self.s,'role-slots',True)
        result=request({**self.q,'source_role':'pose'},self.s)
        rows={r['preset_id']:r for r in result['candidates']}
        self.assertEqual(rows['role-slots']['source_assignment']['role_mode'],'prompt-guidance')
        self.assertEqual(rows['role-slots']['source_assignment']['role'],'pose')
        self.assertIn('not geometric', ' '.join(c['message'] for c in rows['role-slots']['checks']))
        self.assertEqual(rows['edit']['source_assignment']['role_mode'],'unsupported')
        self.assertEqual(rows['edit']['status'],'needs_setup')
    def test_actual_graph_wiring_not_a_claimed_count_controls_assignment(self):
        p=self.s.presets[0];graph,path=self.s.graph_for(p)
        graph['2']['inputs']['images']=['3',0];path.write_text(json.dumps(graph),encoding='utf-8')
        p['continuation_capability']['template_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        row=request(self.q,self.s)['candidates'][0]
        self.assertIn('source_binding_unavailable',[c['code'] for c in row['checks']])
        self.assertEqual(row['status'],'needs_setup')
    def test_source_does_not_satisfy_an_extra_slot_or_a_mask(self):
        p=self.s.presets[0];p['continuation_capability'].update(reference_count=2,requires_mask=True)
        result=request(self.q,self.s);codes=[c['code'] for c in result['candidates'][0]['checks']]
        self.assertIn('references_missing',codes);self.assertIn('mask_required',codes)
    def test_source_identity_and_role_are_part_of_snapshot(self):
        a=request(self.q,self.s)
        b=request({**self.q,'source_role':'style'},self.s)
        self.assertNotEqual(a['snapshot_sha256'],b['snapshot_sha256'])
        with self.assertRaisesRegex(ValueError,'changed'):
            request({**self.q,'source_role':'style','expected_snapshot':a['snapshot_sha256']},self.s)
    def test_shared_clients_and_read_agent_bind_identical_source(self):
        result=request(self.q,self.s)
        client=WorkflowClient();client.request=lambda path,body:request(body,self.s)
        sdk=client.shortlist('edit-image',reference_count=1,**self.source)
        agent=AgentBridge(client,'read').invoke('recipe_shortlist',self.q)
        self.assertTrue(agent['ok'],agent)
        self.assertEqual(result['snapshot_sha256'],sdk['snapshot_sha256'])
        self.assertEqual(result['snapshot_sha256'],json.loads(agent['data_json'])['snapshot_sha256'])
        for delta in [None,{**result['source'],'sha256':'b'*64},{**result['source'],'role':'pose'},{**result['source'],'staged':True}]:
            with self.subTest(delta=delta),self.assertRaises(ValueError):
                observe(lambda *args:{**result,'source':delta},self.q)
    def test_image_safety_errors_become_actionable_read_errors(self):
        with patch.object(Image,'MAX_IMAGE_PIXELS',1),self.assertRaisesRegex(ValueError,'image.*limit|image.*safety'):
            request(self.q,self.s)
        self.assertEqual(self.s.jobs,{})
    def test_clients_reject_wrong_or_fabricated_source_assignments(self):
        result=request(self.q,self.s)
        original=result['candidates'][0]['source_assignment']
        for delta in [{'asset_id':'other'},{'sha256':'b'*64},{'role':'pose'},{'slot':True},
                      {'binding':['1','mask']},{'role_mode':'geometry-control'}]:
            bad=copy.deepcopy(result);bad['candidates'][0]['source_assignment']={**original,**delta}
            with self.subTest(delta=delta),self.assertRaises(ValueError):observe(lambda *args:bad,self.q)
        legacy=request({'goal':'edit-image','reference_count':1},self.s)
        legacy['candidates'][0]['source_assignment']=original
        with self.assertRaises(ValueError):observe(lambda *args:legacy,{'goal':'edit-image','reference_count':1})
    def test_named_roles_are_supported_by_existing_reference_compiler(self):
        from references import ROLES
        from studio_workflow.shortlist_source import SOURCE_ROLES
        self.assertLessEqual(set(SOURCE_ROLES)-{'source'},set(ROLES))
    def test_legacy_requests_do_not_read_workspace_sources(self):
        with patch.object(self.s.assets,'get',side_effect=AssertionError('No source access')):
            result=request({'goal':'edit-image','reference_count':1},self.s)
        self.assertIsNone(result.get('source'))


class SourceShortlistHTTPTests(unittest.TestCase):
    """Production route/guards with real loopback HTTP and real Workspace media."""
    def setUp(self):
        from test_recipe_shortlist_integration import ShortlistHTTPTests
        ShortlistHTTPTests.setUp(self)
        self.source=add_source(self.s,self.root)
        add_route(self.s,'source-edit',True)
        self.q={'goal':'edit-image','reference_count':1,**self.source}
    def tearDown(self):
        from test_recipe_shortlist_integration import ShortlistHTTPTests
        ShortlistHTTPTests.tearDown(self)
    def send(self,**kwargs):
        from test_recipe_shortlist_integration import ShortlistHTTPTests
        return ShortlistHTTPTests.send(self,**kwargs)
    def test_http_sdk_and_read_agent_observe_same_real_source(self):
        status,http=self.send(value=self.q);self.assertEqual(status,200,http)
        sdk=self.client.shortlist('edit-image',reference_count=1,**self.source)
        agent=AgentBridge(self.client,'read').invoke('recipe_shortlist',self.q)
        self.assertTrue(agent['ok'],agent)
        self.assertEqual(http['snapshot_sha256'],sdk['snapshot_sha256'])
        self.assertEqual(http['snapshot_sha256'],json.loads(agent['data_json'])['snapshot_sha256'])
        self.assertEqual(self.s.jobs,{})
    def test_source_guard_failures_preserve_read_only_errors(self):
        for delta in [{'source_sha256':'b'*64},{'source_role':'unknown'}]:
            status,result=self.send(value={**self.q,**delta});self.assertEqual(status,400,result)
            self.assertFalse(result['generation_submitted']);self.assertNotIn('ticket',result)
        with patch.object(self.s.assets,'get',side_effect=AssertionError('Guard before source read')):
            status,_=self.send(value=self.q,origin='https://other.invalid');self.assertEqual(status,403)
    def test_cli_accepts_source_identity_and_role_without_browser(self):
        import contextlib
        import io
        from studio_workflow.shortlist import main
        output=io.StringIO()
        with contextlib.redirect_stdout(output):
            code=main(['--url',self.url,'--goal','edit-image','--references','1',
                       '--source-asset-id',self.source['source_asset_id'],
                       '--source-sha256',self.source['source_sha256'],'--source-role','pose'])
        self.assertEqual(code,0,output.getvalue())
        result=json.loads(output.getvalue());self.assertEqual(result['source']['role'],'pose')
        self.assertTrue(result['source']['bytes_verified']);self.assertFalse(result['source']['staged'])


class ActualSourceRouteTests(unittest.TestCase):
    def test_actual_qwen_role_and_whole_image_routes_use_their_exact_bindings(self):
        from test_recipe_shortlist_integration import ActualCatalogTests
        fixture=ActualCatalogTests();fixture.setUp()
        try:
            s=fixture.s;source=add_source(s,fixture.root)
            with patch.object(s,'node_info',return_value={'SaveImage':{}}):
                result=request({'goal':'reference-image','reference_count':1,'limit':12,**source,'source_role':'pose'},s)
            row=next(r for r in result['candidates'] if r['preset_id']=='qwen-1ref')
            self.assertEqual(row['source_assignment']['binding'],['4','image'])
            self.assertEqual(row['source_assignment']['role_mode'],'prompt-guidance')
            self.assertEqual(s.jobs,{})
        finally:fixture.doCleanups()


@unittest.skipUnless(importlib.util.find_spec('mcp'),'Optional official MCP SDK')
class SourceShortlistMCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_protocol_discovers_source_fields_and_preserves_exact_binding(self):
        from types import SimpleNamespace
        from mcp.shared.memory import create_connected_server_and_client_session
        from studio_workflow.mcp_server import build_server
        from studio_workflow.core import digest
        from studio_workflow.shortlist import PREFIX
        with tempfile.TemporaryDirectory() as root:
            studio=make_studio(root);source=add_source(studio,root);add_route(studio,'edit',True)
            calls=[]
            def transport(path,body=None):calls.append((path,body));return request(body,studio)
            bridge=AgentBridge(SimpleNamespace(request=transport),'read')
            async with create_connected_server_and_client_session(build_server(bridge),raise_exceptions=True) as session:
                tool=next(t for t in (await session.list_tools()).tools if t.name=='recipe_shortlist')
                self.assertTrue(tool.annotations.readOnlyHint);self.assertEqual(calls,[])
                self.assertIn('pose',tool.inputSchema['properties']['source_role']['enum'])
                q={'goal':'edit-image','reference_count':1,**source,'source_role':'pose'}
                result=await session.call_tool('recipe_shortlist',q)
                self.assertFalse(result.isError);data=json.loads(result.structuredContent['data_json'])
                self.assertEqual(data['source']['asset_id'],source['source_asset_id'])
                self.assertEqual(data['candidates'][0]['source_assignment']['role_mode'],'prompt-guidance')
                self.assertEqual(result.structuredContent['data_sha256'],digest(data))
                self.assertEqual(calls[0][0],PREFIX);self.assertEqual(len(calls),1)
                self.assertEqual(studio.jobs,{})
