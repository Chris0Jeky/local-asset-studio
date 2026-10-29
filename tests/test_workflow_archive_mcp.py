"""Official SDK and real stdio Archive discovery, without mutation authority."""
import asyncio
import importlib.util
from pathlib import Path
import sys
import unittest

import test_workflow_asset_mcp as fixture
from studio_workflow.mcp_server import build_server

HAS_MCP=importlib.util.find_spec('mcp') is not None


@unittest.skipUnless(HAS_MCP,'Install optional workflow-mcp requirements for protocol tests')
class ArchiveMCPTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fixture=fixture.AssetMCPTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.http=self.fixture.fixture;f=self.http
        self.private=f.store.register({'id':'archive-private','privacy':'private','outputs':[{'filename':'image.png'}]},0,Path(f.temp.name)/'image.png')
        for ids,scope,request in [(f.ids[:2],'regular','archive-regular-request'),([self.private],'private','archive-private-request')]:
            f.store.update({'ids':ids,'action':'archive','workspace_id':f.scope,'request_id':request,
                            'expected_revisions':dict.fromkeys(ids,0)},privacy=scope)
        self.before=f.store.snapshot(privacy='all')

    def result(self,value):return self.fixture.assert_result(value)

    def assert_read_only(self):
        f=self.http
        self.assertEqual(f.store.snapshot(privacy='all'),self.before)
        with f.store.connection() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM asset_commands').fetchone()[0],2)
        self.assertTrue(all(path.split('?')[0] in ('/api/assets/page','/api/assets/selection') for _,path in self.fixture.requests))
        self.assertEqual((Path(f.temp.name)/'image.png').read_bytes(),b'original')

    async def test_official_sdk_declares_archive_as_read_filter_not_mutation_authority(self):
        from mcp.shared.memory import create_connected_server_and_client_session
        async with create_connected_server_and_client_session(build_server(self.fixture.bridge),raise_exceptions=True) as session:
            tools={tool.name:tool for tool in (await session.list_tools()).tools}
            page=tools['asset_page'];self.assertTrue(page.annotations.readOnlyHint)
            self.assertEqual(page.inputSchema['properties']['filters']['properties']['archive']['enum'],['active','archived','all'])
            self.assertNotIn('asset_archive',tools);self.assertEqual(self.fixture.requests,[])
            result=self.result(await session.call_tool('asset_page',{'filters':{'archive':'archived'}}))
            self.assertEqual({row['id'] for row in result['assets']},set(self.http.ids[:2]))
            self.assertTrue(all(isinstance(row['archived_at'],(int,float)) for row in result['assets']))
            count=len(self.fixture.requests)
            self.assertTrue((await session.call_tool('asset_page',{'filters':{'archive':'trash'}})).isError)
            self.assertTrue((await session.call_tool('asset_archive',{})).isError)
            self.assertEqual(len(self.fixture.requests),count)
        self.assert_read_only()

    async def test_stdio_scoped_archive_paging_and_explicit_selection_are_read_only(self):
        from mcp import ClientSession,StdioServerParameters
        from mcp.client.stdio import stdio_client
        f=self.http;root=Path(__file__).resolve().parents[1]
        params=StdioServerParameters(command=sys.executable,args=[str(root/'scripts/workflow-mcp.py'),
            '--mode','read','--url',self.fixture.url,'--http-timeout','5'],cwd=f.temp.name)
        async with asyncio.timeout(35):
            async with stdio_client(params) as (read,write):
                async with ClientSession(read,write) as session:
                    await session.initialize()
                    active=self.result(await session.call_tool('asset_page',{}))
                    self.assertEqual([row['id'] for row in active['assets']],f.ids[2:])
                    args={'workspace_id':f.scope,'filters':{'archive':'archived'},'limit':1}
                    first=self.result(await session.call_tool('asset_page',args))
                    second=self.result(await session.call_tool('asset_page',{**args,'cursor':first['next_cursor']}))
                    self.assertEqual([first['assets'][0]['id'],second['assets'][0]['id']],list(reversed(f.ids[:2])))
                    self.assertIsNone(second['next_cursor'])
                    all_rows=self.result(await session.call_tool('asset_page',{'filters':{'archive':'all'}}))
                    self.assertEqual({row['id'] for row in all_rows['assets']},set(f.ids))
                    private=self.result(await session.call_tool('asset_page',{'filters':{'archive':'archived','privacy':'private'}}))
                    self.assertEqual([row['id'] for row in private['assets']],[self.private])
                    selected=self.result(await session.call_tool('asset_selection',{'workspace_id':f.scope,'ids':[f.ids[0],self.private]}))
                    self.assertIsNotNone(selected['items'][0]['asset']['archived_at']);self.assertEqual(selected['items'][1]['state'],'missing')
                    before=len(self.fixture.requests)
                    mismatch=await session.call_tool('asset_page',{**args,'filters':{'archive':'all'},'cursor':first['next_cursor']})
                    self.assertTrue(mismatch.isError);self.assertEqual(len(self.fixture.requests),before,'Cross-filter cursor refuses before transport')
        self.assert_read_only()
