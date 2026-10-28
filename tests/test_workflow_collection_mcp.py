"""Official SDK and real stdio collection discovery, with no storage commands."""
import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import unittest

import test_collection_read_client as fixtures
import test_workflow_asset_mcp as asset_protocol
from studio_workflow.agent_bridge import AgentBridge, OUTPUT_SCHEMA
from studio_workflow.client import Client
from studio_workflow.mcp_server import build_server

HAS_MCP = importlib.util.find_spec('mcp') is not None


@unittest.skipUnless(HAS_MCP, 'Install pinned optional MCP SDK for protocol qualification')
class CollectionMCPTests(unittest.IsolatedAsyncioTestCase):
    assert_result = asset_protocol.AssetMCPTests.assert_result

    def setUp(self):
        self.fixture=fixtures.CollectionReadHTTPTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.bridge=AgentBridge(Client(self.fixture.url,timeout=5))

    def assert_no_writes(self,before):
        f=self.fixture;self.assertEqual(f.fixture.store.snapshot(privacy='all'),before)
        self.assertTrue(all(method=='GET' and path.split('?')[0]=='/api/collections' for method,path in f.requests))
        self.assertEqual((Path(f.fixture.temp.name)/'image.png').read_bytes(),b'original')
        with f.fixture.store.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM asset_commands').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM collection_commands_v1').fetchone()[0],0)

    async def test_official_schema_annotations_and_invalid_arguments_are_inert(self):
        from mcp.shared.memory import create_connected_server_and_client_session
        f=self.fixture;before=f.fixture.store.snapshot(privacy='all')
        async with create_connected_server_and_client_session(build_server(self.bridge),raise_exceptions=True) as session:
            tools={item.name:item for item in (await session.list_tools()).tools}
            self.assertIn('collection_page',tools)
            tool=tools['collection_page']
            self.assertTrue(tool.annotations.readOnlyHint);self.assertTrue(tool.annotations.idempotentHint)
            self.assertFalse(tool.annotations.destructiveHint);self.assertFalse(tool.annotations.openWorldHint)
            self.assertEqual(tool.outputSchema,OUTPUT_SCHEMA)
            self.assertEqual(f.requests,[])
            for args in ({'limit':True},{'limit':101},{'privacy':'unknown'},{'cursor':'bad'},{'workspace_id':'other'},{'extra':1}):
                result=await session.call_tool('collection_page',args)
                self.assertTrue(result.isError,(args,result));self.assertEqual(f.requests,[])
            result=self.assert_result(await session.call_tool('collection_page',{}))
            self.assertEqual([c['id'] for c in result['collections']],['alpha','beta'])
            self.assertEqual(len(f.requests),1)
        self.assert_no_writes(before)

    async def test_real_stdio_paging_scopes_and_stale_catalogue_keep_original_context(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        f=self.fixture;root=Path(__file__).resolve().parents[1]
        params=StdioServerParameters(command=sys.executable,
            args=[str(root/'scripts/workflow-mcp.py'),'--mode','read','--url',f.url,'--http-timeout','5'],
            cwd=f.fixture.temp.name)
        async with asyncio.timeout(35):
            async with stdio_client(params) as (read,write):
                async with ClientSession(read,write) as session:
                    await session.initialize();await session.list_tools();self.assertEqual(f.requests,[])
                    before=f.fixture.store.snapshot(privacy='all')
                    first=self.assert_result(await session.call_tool('collection_page',{'limit':1}))
                    self.assertEqual(first['collections'][0]['id'],'alpha')
                    args={'limit':1,'cursor':first['next_cursor'],'privacy':'regular','workspace_id':first['workspace_id']}
                    second=self.assert_result(await session.call_tool('collection_page',args))
                    self.assertEqual(second['collections'][0]['id'],'beta');self.assertIsNone(second['next_cursor'])
                    private=self.assert_result(await session.call_tool('collection_page',{'privacy':'private'}))
                    self.assertEqual([c['id'] for c in private['collections']],['hidden'])
                    all_rows=self.assert_result(await session.call_tool('collection_page',{'privacy':'all'}))
                    self.assertEqual(len(all_rows['collections']),3);self.assertEqual(len(f.requests),4)
                    result=await session.call_tool('collection_page',dict(args,privacy='private'))
                    self.assertTrue(result.isError);self.assertEqual(len(f.requests),4)
                    self.assert_no_writes(before)
                    with f.fixture.store.connection() as db:db.execute("UPDATE collections SET name='Changed' WHERE id='beta'")
                    before=f.fixture.store.snapshot(privacy='all')
                    result=await session.call_tool('collection_page',args)
                    self.assertTrue(result.isError)
                    value=result.structuredContent
                    self.assertEqual(value['error']['code'],'collection_cursor_stale')
                    self.assertEqual(value['context'],args);self.assertNotIn('recovery',value['error'])
                    self.assertEqual(len(f.requests),5)
                    self.assert_no_writes(before)
