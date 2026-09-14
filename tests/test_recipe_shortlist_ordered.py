"""Ordered advice retains every checked asset and slot without staging any of them."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_recipe_shortlist import make_studio
from test_recipe_shortlist_source import add_source
from studio_workflow.shortlist import query, request, observe
from studio_workflow.sdk import WorkflowClient
from studio_workflow.agent_bridge import AgentBridge


def sources(studio, root):
    result=[]
    for key, color, role in [('identity','white','identity'),('pose','black','pose'),('style','red','style')]:
        item=add_source(studio,root,key,color)
        result.append({'asset_id':item['source_asset_id'],'sha256':item['source_sha256'],'role':role})
    return result


def route(studio, count=3):
    p=studio.add('roles','instruction-edit',count)
    graph={str(i+1):{'class_type':'LoadImage','inputs':{'image':'example.png'}} for i in range(count)}
    graph['text']={'class_type':'Text','inputs':{'text':'example'}}
    graph['join']={'class_type':'Join','inputs':{f'image{i}':[str(i+1),0] for i in range(count)}}
    graph['out']={'class_type':'SaveImage','inputs':{'images':['join',0]}}
    p.update(reference=['1','image'],positive=['text','text'],reference_slots=[{'binding':[str(i+1),'image'],'role':'identity'} for i in range(count)])
    save_graph(studio,p,graph)
    return p


def save_graph(studio,p,graph):
    path=studio.root/p['graph'];path.write_text(json.dumps(graph),encoding='utf-8')
    p['continuation_capability']['template_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()


class OrderedSourcesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.s=make_studio(self.root)
        self.items=sources(self.s,self.root);self.p=route(self.s)
        self.q={'goal':'reference-image','reference_count':3,'sources':copy.deepcopy(self.items)}

    def test_query_infers_count_and_copies_nested_intent(self):
        raw={'goal':'reference-image','sources':copy.deepcopy(self.items)}
        q=query(raw);self.assertEqual(q['reference_count'],3)
        raw['sources'][0]['role']='style';self.assertEqual(q['sources'][0]['role'],'identity')
        self.assertEqual(query({'goal':'new-image'})['reference_count'],0)

    def test_invalid_or_mixed_inputs_refuse_before_any_observation(self):
        malformed=[[],self.items*2,None,'[]',[True],[{**self.items[0],'slot':2}],
                   [{**self.items[0],'asset_id':'../image'}],[{**self.items[0],'sha256':'X'*64}],
                   [{**self.items[0],'role':'mask'}],[{**self.items[0],'role':True}]]
        for value in malformed:
            with self.subTest(value=value),self.assertRaises(ValueError):request({**self.q,'sources':value},self.s)
        for delta in [{'reference_count':2},{'reference_count':True},{'source_role':'pose'},
                      {'source_asset_id':'other','source_sha256':'a'*64,'source_role':'source'}]:
            with self.subTest(delta=delta),self.assertRaises(ValueError):request({**self.q,**delta},self.s)
        self.assertEqual(self.s.calls,[])

    def test_all_bytes_and_exact_slot_bindings_are_reported_in_order(self):
        before=self.s.assets.snapshot();r=request(self.q,self.s)
        self.assertIsNone(r.get('source'))
        self.assertEqual([x['asset_id'] for x in r['sources']],[x['asset_id'] for x in self.items])
        self.assertEqual([x['slot'] for x in r['sources']],[1,2,3])
        self.assertTrue(all(x['bytes_verified'] and not x['staged'] for x in r['sources']))
        a=r['candidates'][0]['source_assignments']
        self.assertEqual([x['binding'] for x in a],[['1','image'],['2','image'],['3','image']])
        self.assertEqual([x['role'] for x in a],['identity','pose','style'])
        self.assertTrue(all(x['role_mode']=='prompt-guidance' for x in a))
        self.assertEqual(self.s.assets.snapshot(),before);self.assertEqual(self.s.jobs,{})
        self.assertFalse((self.root/'uploads').exists())
        self.assertNotIn('path',r['sources'][1]);self.assertFalse(r['execution_authorized'])

    def test_each_nonprimary_source_is_checked_and_never_dropped(self):
        for index in (1,2):
            q=copy.deepcopy(self.q);q['sources'][index]['sha256']='b'*64
            with self.subTest(index=index),self.assertRaisesRegex(ValueError,f'Picture {index+1}'):
                request(q,self.s)
        self.assertEqual(self.s.calls,[])

    def test_later_source_change_during_discovery_refuses_whole_report(self):
        def changed():
            self.s.assets.file(self.items[2]['asset_id']).write_bytes(b'replaced')
            return self.s._schema
        with patch.object(self.s,'node_info',side_effect=changed),self.assertRaisesRegex(ValueError,'Picture 3'):
            request(self.q,self.s)

    def test_reorder_role_and_second_hash_are_part_of_snapshot(self):
        a=request(self.q,self.s)
        for order in [list(reversed(self.items)),[{**self.items[0],'role':'style'},*self.items[1:]]]:
            b=request({**self.q,'sources':order},self.s)
            self.assertNotEqual(a['snapshot_sha256'],b['snapshot_sha256'])
            with self.assertRaisesRegex(ValueError,'changed'):
                request({**self.q,'sources':order,'expected_snapshot':a['snapshot_sha256']},self.s)

    def test_reuse_of_same_asset_in_two_roles_is_explicit_not_deduplicated(self):
        items=[self.items[0],{**self.items[0],'role':'pose'},self.items[2]]
        r=request({**self.q,'sources':items},self.s)
        self.assertEqual(len(r['sources']),3)
        self.assertEqual(r['sources'][0]['sha256'],r['sources'][1]['sha256'])
        self.assertEqual(r['candidates'][0]['source_assignments'][1]['slot'],2)

    def test_missing_duplicate_and_unreachable_bindings_do_not_shift_slots(self):
        for slots in [[self.p['reference_slots'][0],{},self.p['reference_slots'][2]],
                      [self.p['reference_slots'][0],self.p['reference_slots'][0],self.p['reference_slots'][2]]]:
            with patch.dict(self.p,reference_slots=slots):
                r=request(self.q,self.s);a=r['candidates'][0]['source_assignments']
                self.assertEqual(a[2]['binding'],['3','image'])
                self.assertEqual(a[1]['role_mode'],'unsupported')
                self.assertEqual(r['candidates'][0]['status'],'needs_setup')
        graph,_=self.s.graph_for(self.p);del graph['join']['inputs']['image1'];save_graph(self.s,self.p,graph)
        a=request(self.q,self.s)['candidates'][0]['source_assignments']
        self.assertEqual(a[1]['role_mode'],'unsupported');self.assertEqual(a[2]['slot'],3)

    def test_extra_sources_and_mask_requirements_stay_blocked(self):
        self.p['reference_slots']=self.p['reference_slots'][:2]
        self.p['continuation_capability'].update(reference_count=2,requires_mask=True)
        row=request(self.q,self.s)['candidates'][0]
        self.assertEqual(len(row['source_assignments']),3)
        self.assertEqual(row['source_assignments'][2]['role_mode'],'unsupported')
        self.assertIn('unused_references',[x['code'] for x in row['checks']])
        self.assertIn('mask_required',[x['code'] for x in row['checks']])

    def test_broken_graph_retains_unsupported_assignment_for_every_source(self):
        (self.root/self.p['graph']).write_text('{}',encoding='utf-8')
        row=request(self.q,self.s)['candidates'][0]
        self.assertEqual(len(row['source_assignments']),3)
        self.assertTrue(all(x['role_mode']=='unsupported' for x in row['source_assignments']))

    def test_clients_refuse_missing_reordered_fabricated_and_legacy_mixed_evidence(self):
        good=request(self.q,self.s)
        self.assertEqual(observe(lambda *a:good,self.q),good)
        mutations=[lambda r:r.pop('sources'),lambda r:r['sources'].reverse(),
                   lambda r:r['sources'][1].update(role='identity'),lambda r:r['sources'][1].update(staged=True),
                   lambda r:r['sources'][0].update(slot=True),lambda r:r.update(source=r['sources'][0]),
                   lambda r:r['candidates'][0].pop('source_assignments'),
                   lambda r:r['candidates'][0]['source_assignments'].pop(),
                   lambda r:r['candidates'][0]['source_assignments'].reverse(),
                   lambda r:r['candidates'][0]['source_assignments'][1].update(asset_id='other'),
                   lambda r:r['candidates'][0]['source_assignments'][1].update(binding=['2','mask'])]
        for mutate in mutations:
            bad=copy.deepcopy(good);mutate(bad)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):observe(lambda *a:bad,self.q)
        legacy=request({'goal':'reference-image','reference_count':3},self.s);legacy['sources']=good['sources']
        with self.assertRaises(ValueError):observe(lambda *a:legacy,{'goal':'reference-image','reference_count':3})

    def test_sdk_and_read_agent_use_identical_ordered_observations(self):
        c=WorkflowClient();c.request=lambda path,body:request(body,self.s)
        r=c.shortlist('reference-image',sources=self.items)
        a=AgentBridge(c,'read').invoke('recipe_shortlist',self.q)
        self.assertTrue(a['ok'],a)
        self.assertEqual(r['snapshot_sha256'],json.loads(a['data_json'])['snapshot_sha256'])
        self.assertFalse(a.get('execution_authorized',False))

class OrderedHTTPTests(unittest.TestCase):
    def setUp(self):
        from test_recipe_shortlist_integration import ShortlistHTTPTests
        ShortlistHTTPTests.setUp(self)
        self.items=sources(self.s,self.root);route(self.s)
        self.q={'goal':'reference-image','sources':self.items}
    def tearDown(self):
        from test_recipe_shortlist_integration import ShortlistHTTPTests
        ShortlistHTTPTests.tearDown(self)
    def send(self,**kwargs):
        from test_recipe_shortlist_integration import ShortlistHTTPTests
        return ShortlistHTTPTests.send(self,**kwargs)
    def test_production_http_sdk_cli_and_agent_share_the_ordered_snapshot(self):
        import contextlib,io
        from studio_workflow.shortlist import main
        status,r=self.send(value=self.q);self.assertEqual(status,200,r)
        sdk=self.client.shortlist('reference-image',sources=self.items)
        agent=AgentBridge(self.client,'read').invoke('recipe_shortlist',self.q)
        self.assertTrue(agent['ok'],agent)
        path=self.root/'sources.json';path.write_text(json.dumps(self.items),encoding='utf-8')
        out=io.StringIO()
        with contextlib.redirect_stdout(out):code=main(['--url',self.url,'--goal','reference-image','--sources-json',str(path)])
        self.assertEqual(code,0,out.getvalue())
        for result in (sdk,json.loads(agent['data_json']),json.loads(out.getvalue())):
            self.assertEqual(result['snapshot_sha256'],r['snapshot_sha256'])
            self.assertEqual([x['asset_id'] for x in result['sources']],[x['asset_id'] for x in self.items])
        self.assertEqual(self.s.jobs,{})
    def test_transport_guards_and_malformed_queries_precede_any_source_read(self):
        with patch.object(self.s.assets,'get',side_effect=AssertionError('No source read')):
            self.assertEqual(self.send(value=self.q,origin='https://other.invalid')[0],403)
            self.assertEqual(self.send(value={**self.q,'sources':self.items*2})[0],400)
            self.assertEqual(self.send(value={**self.q,'reference_count':2})[0],400)
        self.assertEqual(self.s.calls,[])
    def test_cli_refuses_oversize_duplicate_keys_or_malformed_file_before_http(self):
        import contextlib,io
        from studio_workflow.shortlist import main
        path=self.root/'sources.json'
        for content in [b' '*8193,b'[',b'[{"role":"pose","role":"identity"}]',b'null']:
            path.write_bytes(content);out=io.StringIO()
            with patch.object(WorkflowClient,'request',side_effect=AssertionError('No request')),contextlib.redirect_stdout(out):
                code=main(['--url',self.url,'--goal','reference-image','--sources-json',str(path)])
            self.assertEqual(code,2,out.getvalue());self.assertEqual(self.s.calls,[])
    def test_changed_nonprimary_source_returns_read_error_not_a_partial_report(self):
        self.s.assets.file(self.items[1]['asset_id']).write_bytes(b'changed')
        status,r=self.send(value=self.q)
        self.assertEqual(status,400,r);self.assertIn('Picture 2',r['error'])
        self.assertFalse(r['generation_submitted']);self.assertNotIn('candidates',r)


class ActualOrderedCatalogTests(unittest.TestCase):
    def test_two_and_three_qwen_sources_use_authored_picture_bindings(self):
        from test_recipe_shortlist_integration import ActualCatalogTests
        f=ActualCatalogTests();f.setUp()
        try:
            items=sources(f.s,f.root)
            with patch.object(f.s,'node_info',return_value={'SaveImage':{}}):
                for count in (2,3):
                    r=request({'goal':'reference-image','limit':12,'sources':items[:count]},f.s)
                    row=next(x for x in r['candidates'] if x['preset_id']==f'qwen-{count}ref')
                    self.assertEqual([x['binding'] for x in row['source_assignments']],[['4','image'],['16','image'],['17','image']][:count])
                    self.assertTrue(all(x['role_mode']=='prompt-guidance' for x in row['source_assignments']))
                    self.assertEqual(f.s.jobs,{})
        finally:f.doCleanups()


import importlib.util
@unittest.skipUnless(importlib.util.find_spec('mcp'),'Optional official MCP SDK')
class OrderedMCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_official_protocol_discovers_bounded_array_and_keeps_order(self):
        from types import SimpleNamespace
        from mcp.shared.memory import create_connected_server_and_client_session
        from studio_workflow.mcp_server import build_server
        from studio_workflow.core import digest
        with tempfile.TemporaryDirectory() as root:
            s=make_studio(root);items=sources(s,root);route(s);calls=[]
            def transport(path,body=None):calls.append((path,body));return request(body,s)
            bridge=AgentBridge(SimpleNamespace(request=transport),'read')
            async with create_connected_server_and_client_session(build_server(bridge),raise_exceptions=True) as session:
                tool=next(t for t in (await session.list_tools()).tools if t.name=='recipe_shortlist')
                self.assertTrue(tool.annotations.readOnlyHint)
                self.assertEqual(tool.inputSchema['properties']['sources']['maxItems'],3)
                self.assertEqual(calls,[])
                reply=await session.call_tool('recipe_shortlist',{'goal':'reference-image','sources':items})
                self.assertFalse(reply.isError)
                data=json.loads(reply.structuredContent['data_json'])
                self.assertEqual([x['role'] for x in data['sources']],['identity','pose','style'])
                self.assertEqual(reply.structuredContent['data_sha256'],digest(data))
                self.assertEqual(len(calls),1);self.assertEqual(s.jobs,{})
                await session.call_tool('recipe_shortlist',{'goal':'reference-image','sources':items*2})
                self.assertEqual(len(calls),1)
