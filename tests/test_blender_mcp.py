import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import blender_mcp as mcp

LIVE_BLENDER = os.environ.get("LAS_BLENDER_LAB_EXE")


class FakeWorker:
    def __init__(self): self.calls = []
    def call(self, command, **args): self.calls.append((command, args)); return {"command": command, **args}
    def close(self): pass


def facade(tmp):
    exe = Path(tmp) / "blender.exe"; exe.write_bytes(b"")
    (Path(tmp) / "out").mkdir(); (Path(tmp) / "assets").mkdir()
    result = mcp.Facade(exe, Path(tmp) / "out", Path(tmp) / "assets")
    result.worker = FakeWorker(); result.worker.process = type("P", (), {"poll": lambda self: None})()
    return result


def rpc(server, method, params=None, ident=1):
    return server.handle({"jsonrpc": "2.0", "id": ident, "method": method, "params": params or {}})


class ProtocolTests(unittest.TestCase):
    def test_initialize_and_tool_list_expose_only_typed_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            server = facade(tmp)
            self.assertEqual(rpc(server, "initialize")["result"]["capabilities"], {"tools": {}})
            names = {tool["name"] for tool in rpc(server, "tools/list")["result"]["tools"]}
        self.assertEqual(names, {"blender_ping", "blender_caps", "blender_open", "blender_describe_scene", "blender_render_views",
                                 "blender_save_copy", "blender_export", "blender_apply_edit", "blender_reimport_validate",
                                 "blender_compare_to"})
        self.assertFalse(any(word in name for name in names for word in ("python", "exec", "eval", "script")))

    def test_calls_route_to_the_worker_and_errors_become_tool_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            server = facade(tmp)
            reply = rpc(server, "tools/call", {"name": "blender_export", "arguments": {"path": "a.glb"}})
            self.assertEqual(json.loads(reply["result"]["content"][0]["text"]), {"command": "export", "path": "a.glb"})
            self.assertEqual(rpc(server, "tools/call", {"name": "blender_python", "arguments": {}})["error"]["code"], -32602)
            self.assertEqual(rpc(server, "resources/list")["error"]["code"], -32601)
            self.assertIsNone(server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_malformed_params_and_unadvertised_arguments_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            server = facade(tmp)
            for params in ([1], {"name": []}, {"name": "blender_ping", "arguments": [1]},
                           {"name": "blender_export", "arguments": {"path": "a.glb", "timeout": None}},
                           {"name": "blender_export", "arguments": {}}):
                self.assertEqual(rpc(server, "tools/call", params)["error"]["code"], -32602, params)
            self.assertEqual(server.worker.calls, [])

    def test_open_is_confined_to_the_read_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            server = facade(tmp)
            for bad in ("../outside.blend", str(Path(tmp) / "out" / "x.blend")):
                reply = rpc(server, "tools/call", {"name": "blender_open", "arguments": {"blend": bad}})
                self.assertTrue(reply["result"]["isError"], bad)
            (Path(tmp) / "assets" / "a.blend").write_bytes(b"")
            missing = rpc(server, "tools/call", {"name": "blender_open", "arguments": {"blend": "absent.blend"}})
            self.assertTrue(missing["result"]["isError"])
            ok = rpc(server, "tools/call", {"name": "blender_open", "arguments": {"blend": "a.blend"}})
            self.assertEqual(json.loads(ok["result"]["content"][0]["text"])["blend"], str((Path(tmp) / "assets" / "a.blend").resolve()))
            self.assertEqual([c for c, _ in server.worker.calls], ["open"])

    def test_serve_answers_line_by_line_and_reports_parse_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = io.StringIO()
            mcp.serve(facade(tmp), io.StringIO('{"jsonrpc":"2.0","id":7,"method":"ping"}\nnot json\n'), out)
        replies = [json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual(replies[0], {"jsonrpc": "2.0", "id": 7, "result": {}})
        self.assertEqual(replies[1]["error"]["code"], -32700)


@unittest.skipUnless(LIVE_BLENDER, "set LAS_BLENDER_LAB_EXE to a Blender executable for the live MCP session")
class LiveMcpTests(unittest.TestCase):
    def test_stdio_session_edits_and_validates(self):
        with tempfile.TemporaryDirectory() as tmp:
            blend = mcp.lab.make_fixture(LIVE_BLENDER, Path(tmp) / "assets")
            process = subprocess.Popen([sys.executable, str(ROOT / "scripts" / "blender_mcp.py"), "--blender", LIVE_BLENDER,
                                        "--root", str(Path(tmp) / "out"), "--blend-root", str(blend.parent)],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8")
            def call(method, params=None, ident=[0]):
                ident[0] += 1
                process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": ident[0], "method": method, "params": params or {}}) + "\n")
                process.stdin.flush()
                return json.loads(process.stdout.readline())
            tool = lambda name, **args: call("tools/call", {"name": name, "arguments": args})["result"]
            try:
                call("initialize", {"protocolVersion": mcp.PROTOCOL, "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}})
                opened = json.loads(tool("blender_open", blend="lab-asset.blend", allow_edit=["Badge"])["content"][0]["text"])
                edit = tool("blender_apply_edit", object="Badge", op="hide_render", value=True, expect_checksum=opened["semantic_checksum"])
                self.assertFalse(edit["isError"], edit)
                self.assertTrue(tool("blender_apply_edit", object="Head", op="hide_render", value=True, expect_checksum="x")["isError"])
                tool("blender_apply_edit", object="Badge", op="hide_render", value=False,
                     expect_checksum=json.loads(edit["content"][0]["text"])["after"])
                result = json.loads(tool("blender_reimport_validate", out_dir="rv")["content"][0]["text"])
                self.assertTrue(result["pass"], result["structural_failures"] + result["visual_warnings"])
            finally:
                process.stdin.close(); process.wait(60)


if __name__ == "__main__":
    unittest.main()
