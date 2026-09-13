"""Shared HTTP/client contracts; all runtime files and replies are synthetic."""
import copy
from http.client import HTTPConnection
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.request import Request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
from test_recipe_shortlist import make_studio
from studio_workflow.agent_bridge import AgentBridge
from studio_workflow.sdk import WorkflowClient
from studio_workflow.shortlist import request, GOALS, PREFIX
from test_server import server


class ShortlistHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.s=make_studio(self.root);self.s.add('plain')
        self.http=server.create_server(self.root,port=0,studio_factory=lambda _:self.s)
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
        self.url='http://127.0.0.1:'+str(self.http.server_port);self.client=WorkflowClient(self.url,5)
        # Production has a fixed Host/origin policy; retain it over an ephemeral test socket.
        def wire(url,*args,**kwargs):
            headers=dict(kwargs.get('headers',{}));headers['Host']='127.0.0.1:8191';headers['Origin']='http://127.0.0.1:8191';kwargs['headers']=headers
            return Request(url,*args,**kwargs)
        self.transport_patch=patch('studio_workflow.client.Request',side_effect=wire);self.transport_patch.start();self.addCleanup(self.transport_patch.stop)
    def tearDown(self):self.http.shutdown();self.http.server_close();self.thread.join(5);self.temp.cleanup()
    def send(self,value=None,origin=None,content_type='application/json',host=None):
        conn=HTTPConnection('127.0.0.1',self.http.server_port,timeout=5)
        try:
            headers={'Host':host or '127.0.0.1:8191','Origin':origin or 'http://127.0.0.1:8191','Content-Type':content_type}
            if host:headers['Host']=host
            conn.request('POST',PREFIX,json.dumps(value or {'goal':'new-image'}),headers)
            r=conn.getresponse();return r.status,json.loads(r.read())
        finally:conn.close()
    def test_ui_http_sdk_and_read_agent_share_snapshot_and_no_execution_access(self):
        before={str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        status,ui=self.send();self.assertEqual(status,200)
        sdk=self.client.shortlist('new-image')
        bridge=AgentBridge(self.client,'read');tools=bridge.definitions()
        self.assertIn('recipe_shortlist',tools)
        result=bridge.invoke('recipe_shortlist',{'goal':'new-image'})
        self.assertTrue(result['ok'],result);agent=json.loads(result['data_json'])
        self.assertEqual(ui['snapshot_sha256'],sdk['snapshot_sha256']);self.assertEqual(agent['snapshot_sha256'],sdk['snapshot_sha256'])
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        self.assertEqual(self.s.calls.count('nodes'),3)
    def test_host_origin_type_and_payload_guards_precede_observation(self):
        for kwargs,expected in [({'origin':'https://other.invalid'},403),({'host':'other.invalid'},403),({'content_type':'text/plain'},400),({'value':{'goal':'new-image','run':True}},400)]:
            with self.subTest(kwargs=kwargs):self.assertEqual(self.send(**kwargs)[0],expected)
        self.assertEqual(self.s.calls,[])
    def test_sdk_and_agent_reject_invalid_options_before_http(self):
        with patch.object(self.client,'request',side_effect=AssertionError('No request expected')):
            for value in [True,4,-1]:
                with self.assertRaises(ValueError):self.client.shortlist('new-image',reference_count=value)
            self.assertFalse(AgentBridge(self.client).invoke('recipe_shortlist',{'goal':'bad'})['ok'])
    def test_cli_reads_same_http_snapshot_and_is_import_safe_away_from_repo(self):
        code="""import sys
sys.path.insert(0,sys.argv[1])
from urllib.request import Request
import studio_workflow.client as transport
def wire(url,*args,**kwargs):
    kwargs['headers']={**kwargs.get('headers',{}),'Host':'127.0.0.1:8191','Origin':'http://127.0.0.1:8191'}
    return Request(url,*args,**kwargs)
transport.Request=wire
from studio_workflow.shortlist import main
sys.exit(main(sys.argv[2:]))
"""
        proc=subprocess.run([sys.executable,'-c',code,str(ROOT),'--url',self.url,'--goal','new-image'],cwd=self.root,capture_output=True,text=True,timeout=15)
        self.assertEqual(proc.returncode,0,proc.stderr+proc.stdout)
        self.assertEqual(json.loads(proc.stdout)['snapshot_sha256'],self.client.shortlist('new-image')['snapshot_sha256'])
        help_result=subprocess.run([sys.executable,'-m','studio_workflow.shortlist','--help'],cwd=ROOT,capture_output=True,text=True,timeout=10)
        self.assertEqual(help_result.returncode,0);self.assertNotIn('Traceback',help_result.stderr)
    def test_failed_observation_has_no_ticket_job_or_silent_retry(self):
        with patch.object(self.s,'catalog',side_effect=ValueError('catalog unavailable')):
            status,value=self.send();self.assertEqual(status,400);self.assertFalse(value['generation_submitted'])
        self.assertNotIn('job',value);self.assertNotIn('ticket',value)

    def test_agent_and_sdk_retain_snapshot_recovery_error_detail(self):
        first=self.client.shortlist('new-image')
        self.s.requirements['plain']=[{'file':'changed','present':False}]
        with self.assertRaisesRegex(ValueError,'Shortlist changed'):
            self.client.shortlist('new-image',expected_snapshot=first['snapshot_sha256'])
        result=AgentBridge(self.client).invoke('recipe_shortlist',{'goal':'new-image','expected_snapshot':first['snapshot_sha256']})
        self.assertFalse(result['ok']);self.assertIn('Shortlist changed',result['error']['message'])
    def test_agent_goal_enum_is_discoverable_without_requests(self):
        tool=AgentBridge(self.client).definitions()['recipe_shortlist']
        self.assertEqual(set(tool['inputSchema']['properties']['goal']['enum']),set(GOALS))
        self.assertEqual(self.s.calls,[])


class ActualCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        for folder in ('presets','models','config','fake-comfy/input'):(self.root/folder).mkdir(parents=True,exist_ok=True)
        shutil.copytree(ROOT/'workflows',self.root/'workflows')
        shutil.copy(ROOT/'presets/catalog.json',self.root/'presets/catalog.json')
        shutil.copy(ROOT/'models/library.json',self.root/'models/library.json')
        (self.root/'config/local.json').write_text(json.dumps({'comfy_root':str(self.root/'fake-comfy')}),encoding='utf-8')
        with patch.object(threading.Thread,'start',lambda *_:None):self.s=server.Studio(self.root)
        self.s.worker=SimpleNamespace(is_alive=lambda:True)
    def test_all_current_goals_use_real_catalog_graph_and_requirement_projection(self):
        # Actual graphs/capability extraction, deliberately incomplete installed schema.
        with (patch.object(self.s,'node_info',return_value={'SaveImage':{}}),patch.object(self.s,'_request',side_effect=AssertionError('No runtime transport')),
              patch.object(self.s,'prepare',side_effect=AssertionError('No preparation'))):
            reports={goal:request({'goal':goal,'reference_count':0 if goal=='new-image' else 1,'limit':12},self.s) for goal in GOALS}
        self.assertTrue(all(r['total']>0 for r in reports.values()))
        self.assertEqual(self.s.jobs,{})
        rows=[c for r in reports.values() for c in r['candidates']]
        self.assertTrue(all(c['template_sha256'] and c['status']!='observed' for c in rows))
        self.assertTrue(any(c['requirements'] for c in rows))
        # A known ordinary-decoder long I2V default must obey existing admission.
        original=self.s.catalog()
        wan=next(p for p in original['presets'] if p['id']=='wan22-i2v')
        graph,path=self.s.graph_for(wan)
        latent=next(n for n in graph.values() if n.get('class_type')=='Wan22ImageToVideoLatent')
        latent['inputs']['length']=81;path.write_text(json.dumps(graph),encoding='utf-8')
        with patch.object(self.s,'node_info',return_value={'SaveImage':{}}):
            result=request({'goal':'animate-image','reference_count':1,'limit':12},self.s)
        row=next(c for c in result['candidates'] if c['preset_id']=='wan22-i2v')
        self.assertIn('capacity_hold',[c['code'] for c in row['checks']])
    def test_actual_mask_routes_never_promote_a_declared_file_to_valid_mask(self):
        with patch.object(self.s,'node_info',side_effect=OSError('offline')):
            result=request({'goal':'masked-repair','reference_count':1,'limit':12},self.s)
        self.assertTrue(result['candidates'])
        self.assertTrue(all('mask_required' in [c['code'] for c in row['checks']] for row in result['candidates']))
        self.assertEqual(self.s.jobs,{})


class ClientPolicyTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'),'Node required for shipped client policy')
    def test_actual_client_contracts(self):
        result=subprocess.run(['node','--test','tests/recipe_shortlist_client.cjs'],cwd=ROOT,capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)


@unittest.skipUnless(importlib.util.find_spec('mcp'),'Optional official MCP SDK')
class ShortlistMCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_protocol_read_tool_reuses_shared_policy_and_exact_reply(self):
        from mcp.shared.memory import create_connected_server_and_client_session
        from studio_workflow.mcp_server import build_server
        from studio_workflow.core import digest
        with tempfile.TemporaryDirectory() as root:
            studio=make_studio(root);studio.add('plain')
            calls=[]
            def transport(path,body=None):calls.append((path,body));return request(body,studio)
            bridge=AgentBridge(SimpleNamespace(request=transport),'read')
            async with create_connected_server_and_client_session(build_server(bridge),raise_exceptions=True) as session:
                tools={x.name:x for x in (await session.list_tools()).tools}
                self.assertTrue(tools['recipe_shortlist'].annotations.readOnlyHint);self.assertEqual(calls,[])
                result=await session.call_tool('recipe_shortlist',{'goal':'new-image'})
                self.assertFalse(result.isError);data=json.loads(result.structuredContent['data_json'])
                self.assertEqual(result.structuredContent['data_sha256'],digest(data));self.assertFalse(data['execution_authorized'])
                self.assertEqual(calls[0][0],PREFIX);self.assertEqual(len(calls),1)
