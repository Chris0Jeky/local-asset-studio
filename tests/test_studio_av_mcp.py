"""Real optional SDK tests. Dedicated CI installs the pinned SDK; no protocol mock."""
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
try:
    from mcp import Client,StdioServerParameters
    from mcp.server import MCPServer
    HAVE=True
except ImportError:HAVE=False

@unittest.skipUnless(HAVE,'Official MCP 2.2 SDK is optional/not installed')
class MCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_stdio_discovery_and_denial(self):
        with tempfile.TemporaryDirectory() as tmp:
            async with Client(StdioServerParameters(command=sys.executable,args=[str(ROOT/'scripts/studio_av_mcp.py'),'--workspace',tmp])) as client:
                tools=(await client.list_tools()).tools
                names={x.name for x in tools}
                self.assertTrue(all(t.output_schema is not None for t in tools))
                self.assertIn('plan_preview',names);self.assertNotIn('render_preview',names)
                answer=await client.call_tool('capabilities',{});self.assertFalse(answer.is_error)
                self.assertIsNotNone(answer.structured_content)
                self.assertFalse(answer.structured_content['render_enabled'])
                self.assertFalse(answer.structured_content['model_inference'])
                bad=await client.call_tool('validate_project',{'project_path':'../escape.json'})
                self.assertTrue(bad.is_error)
    async def test_render_is_explicit_opt_in(self):
        from studio_av.mcp_server import build_server
        with tempfile.TemporaryDirectory() as tmp:
            async with Client(build_server(tmp,True)) as client:
                self.assertIn('render_preview',{x.name for x in (await client.list_tools()).tools})
if __name__=='__main__':unittest.main()
