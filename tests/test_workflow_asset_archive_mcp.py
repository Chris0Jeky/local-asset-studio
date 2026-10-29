"""Official SDK and real stdio Archive review/approval/recovery on the HTTP owner."""
import asyncio
import importlib.util
import json
from pathlib import Path
import socket
import sys
import unittest
import uuid

import test_workflow_asset_archive_client as fixtures
from studio_workflow.agent_bridge import AgentBridge, OUTPUT_SCHEMA
from studio_workflow.client import Client
from studio_workflow.core import canonical, digest
from studio_workflow.mcp_server import build_server

HAS_MCP = importlib.util.find_spec('mcp') is not None


@unittest.skipUnless(HAS_MCP, 'Install pinned optional MCP SDK for protocol qualification')
class ArchiveMCPTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fixture=fixtures.ArchiveClientTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.requests=[];requests=self.requests
        base=self.fixture.fixture.http.RequestHandlerClass
        class ObservedOwner(base):
            lose=False
            def do_GET(handler):requests.append(('GET',handler.path));return super().do_GET()
            def do_POST(handler):requests.append(('POST',handler.path));return super().do_POST()
            def _json(handler,status,value):
                if handler.path=='/api/assets/update' and status==200 and ObservedOwner.lose:
                    ObservedOwner.lose=False;handler.close_connection=True;handler.connection.shutdown(socket.SHUT_RDWR);return
                return super()._json(status,value)
        self.owner=ObservedOwner;self.fixture.fixture.http.RequestHandlerClass=ObservedOwner

    def result(self,reply):
        self.assertFalse(reply.isError,reply);value=reply.structuredContent
        self.assertTrue(value['ok']);self.assertEqual(json.loads(reply.content[0].text),value)
        data=json.loads(value['data_json']);self.assertEqual(value['data_sha256'],digest(data))
        return data

    async def test_sdk_annotations_and_read_permissions_do_not_dispatch(self):
        from mcp.shared.memory import create_connected_server_and_client_session
        client=Client(self.fixture.client.base,timeout=5)
        for mode in ('read','author'):
            async with create_connected_server_and_client_session(build_server(AgentBridge(client,mode)),raise_exceptions=True) as session:
                tools={item.name:item for item in (await session.list_tools()).tools}
                for name in ('asset_archive_preview','asset_archive_recover'):
                    self.assertTrue(tools[name].annotations.readOnlyHint)
                    self.assertTrue(tools[name].annotations.idempotentHint)
                    self.assertFalse(tools[name].annotations.openWorldHint)
                    self.assertEqual(tools[name].outputSchema,OUTPUT_SCHEMA)
                self.assertEqual('asset_archive_apply' in tools,mode=='author')
                if mode=='author':self.assertFalse(tools['asset_archive_apply'].annotations.readOnlyHint)
                for name,args in [('asset_archive_preview',{'ids':[],'workspace_id':self.fixture.scope,'request_id':uuid.uuid4().hex}),
                                  ('asset_archive_apply',{'plan_json':'{}','approved_plan_sha256':'0'*64}),
                                  ('asset_archive_recover',{'plan_json':'{}'})]:
                    reply=await session.call_tool(name,args);self.assertTrue(reply.isError,reply)
                self.assertEqual(self.requests,[])

    async def test_stdio_lost_write_private_scope_recovery_and_stale_conflict(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        f=self.fixture;root=Path(__file__).resolve().parents[1]
        private=f.store.register({'id':'private-protocol','privacy':'private','outputs':[{'filename':'image.png'}]},0,Path(f.fixture.temp.name)/'image.png')
        params=StdioServerParameters(command=sys.executable,
            args=[str(root/'scripts/workflow-mcp.py'),'--mode','author','--url',f.client.base,'--http-timeout','5'],cwd=f.fixture.temp.name)
        async with asyncio.timeout(40):
            async with stdio_client(params) as (read,write):
                async with ClientSession(read,write) as session:
                    await session.initialize();await session.list_tools();self.assertEqual(self.requests,[])
                    args={'ids':[private],'workspace_id':f.scope,'request_id':uuid.uuid4().hex}
                    hidden=await session.call_tool('asset_archive_preview',args);self.assertTrue(hidden.isError)
                    plan=self.result(await session.call_tool('asset_archive_preview',dict(args,privacy='private')))
                    text=canonical(plan).decode();apply={'plan_json':text,'approved_plan_sha256':plan['plan_sha256']}
                    before=len(self.requests);self.owner.lose=True
                    uncertain=await session.call_tool('asset_archive_apply',apply)
                    self.assertTrue(uncertain.isError);self.assertEqual(uncertain.structuredContent['error']['code'],'outcome_unknown')
                    self.assertEqual(uncertain.structuredContent['context']['request_id'],plan['request_id'])
                    self.assertEqual(len(self.requests),before+1)
                    snapshot=f.store.snapshot(privacy='all')
                    result=self.result(await session.call_tool('asset_archive_recover',{'plan_json':text}))
                    self.assertEqual(result['receipt']['status'],'applied');self.assertEqual(result['privacy'],'private')
                    self.assertEqual(f.store.snapshot(privacy='all'),snapshot)
                    self.assertEqual(self.requests[-1][0],'GET')
                    # An independently edited asset makes the retained plan stale, not a prompt to refresh it.
                    regular=self.result(await session.call_tool('asset_archive_preview',dict(args,ids=f.ids,request_id=uuid.uuid4().hex)))
                    f.store.update(f.fixture.command(ids=f.ids[:1]))
                    before=len(self.requests);snapshot=f.store.snapshot(privacy='all')
                    stale=await session.call_tool('asset_archive_apply',{'plan_json':canonical(regular).decode(),'approved_plan_sha256':regular['plan_sha256']})
                    self.assertTrue(stale.isError);self.assertEqual(stale.structuredContent['error']['code'],'asset_revision_conflict')
                    self.assertEqual(len(self.requests),before+1);self.assertEqual(f.store.snapshot(privacy='all'),snapshot)
        self.assertEqual((Path(f.fixture.temp.name)/'image.png').read_bytes(),b'original')
        self.assertTrue(all(path.split('?')[0] in ('/api/assets/selection','/api/assets/update') or path.startswith('/api/assets/commands/') for _,path in self.requests))
        with f.store.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM asset_commands').fetchone()[0],2)  # Private apply and explicit fixture edit only.
