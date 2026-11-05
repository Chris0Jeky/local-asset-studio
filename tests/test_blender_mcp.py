import base64
import copy
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
import blender_lab_bpy as manifests

LIVE_BLENDER = os.environ.get("LAS_BLENDER_LAB_EXE")


class FakeWorker:
    def __init__(self, scene=None): self.calls, self.scene, self.error = [], scene, None
    def call(self, command, **args):
        self.calls.append((command, args))
        if command == "describe_scene":
            if self.error: raise self.error
            if self.scene is not None: return self.scene
        return {"command": command, **args}
    def close(self): pass


def facade(tmp, worker=None):
    exe = Path(tmp) / "blender.exe"; exe.write_bytes(b"")
    (Path(tmp) / "out").mkdir(); (Path(tmp) / "assets").mkdir()
    result = mcp.Facade(exe, Path(tmp) / "out", Path(tmp) / "assets")
    result.worker = worker or FakeWorker(); result.worker.process = type("P", (), {"poll": lambda self: None})()
    return result


def rpc(server, method, params=None, ident=1):
    return server.handle({"jsonrpc": "2.0", "id": ident, "method": method, "params": params or {}})


class ProtocolTests(unittest.TestCase):
    def test_caps_preserves_unmeasured_device_state_without_claiming_support(self):
        unknown = {'ok': None, 'state': 'not-probed', 'reason': 'GPU initialization not requested for worker startup'}
        class StartupWorker(FakeWorker):
            def call(self, command, **args): return {'features': {'gpu_backend': unknown, 'cycles_devices': unknown}}
        with tempfile.TemporaryDirectory() as tmp:
            server = facade(tmp, StartupWorker())
            reply = rpc(server, 'tools/call', {'name': 'blender_caps', 'arguments': {}})
        result = json.loads(reply['result']['content'][0]['text'])
        self.assertFalse(reply['result']['isError'])
        self.assertEqual(result['features']['gpu_backend'], unknown)
        self.assertIsNone(result['features']['cycles_devices']['ok'])

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


def scene(names, heavy=0):
    rows = [{"name": name, "type": "MESH", "parent": names[0] if i else None, "parent_type": "OBJECT", "parent_bone": None,
             "matrix_world": [[1, 0, 0, i + 0.12345], [0, 1, 0, 2.34567], [0, 0, 1, -3.45678], [0, 0, 0, 1]],
             "hide_render": bool(i % 2), "visible": not bool(i % 2), "data": "SharedMesh", "vertex_weights": {"groups": "x" * heavy}}
            for i, name in enumerate(names)]
    value = {"schema": "las.blender-lab.v1", "kind": "scene-manifest", "blender": {"version_string": "fixture"},
             "source": {"file": "fixture.blend"}, "scene": {"name": "Fixture", "unit_scale": 1}, "objects": rows,
             "counts": {"objects": len(rows), "meshes": 1, "materials": 1}, "meshes": [{"name": "SharedMesh", "detail": "x" * heavy}],
             "materials": [{"name": "Paint", "detail": "x" * heavy}], "object_samples": {name: {"matrices": [row["matrix_world"]]} for name, row in zip(names, rows)}}
    value["semantic_checksum"] = manifests.semantic_checksum(value)
    return value


class SceneReplyTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.worker = FakeWorker(scene(["Root", "Child"]))
        self.server = facade(tmp.name, self.worker)

    def reply(self, args=None, ident=1):
        return rpc(self.server, "tools/call", {"name": "blender_describe_scene", "arguments": {} if args is None else args}, ident)

    def projection(self, args):
        reply = self.reply(args)
        self.assertIn("result", reply, reply)
        result = reply["result"]
        self.assertFalse(result["isError"], result)
        self.assertLessEqual(len(json.dumps(result).encode("utf-8")), args.get("max_bytes", 32768))
        value = json.loads(result["content"][0]["text"])
        self.assertEqual(value["schema"], "las.blender-scene-summary.v1")
        self.assertEqual(value["checksum_scope"], "full-scene")
        self.assertEqual(value["semantic_checksum"], self.worker.scene["semantic_checksum"])
        return value

    def test_small_recorded_manifests_keep_the_full_reply_with_effective_defaults(self):
        for path in sorted((ROOT / "tests" / "fixtures" / "blender_lab").glob("manifest-*.json")):
            self.worker.scene = json.loads(path.read_text(encoding="utf-8"))
            before = copy.deepcopy(self.worker.scene)
            for args in ({}, {"mode": "auto"}, {"max_bytes": 32768}, {"mode": "auto", "max_bytes": 65536}):
                with self.subTest(path=path.name, args=args):
                    reply = self.reply(args); self.assertIn("result", reply)
                    result = reply["result"]
                    self.assertEqual(json.loads(result["content"][0]["text"]), before)
                    self.assertLessEqual(len(json.dumps(result).encode("utf-8")), args.get("max_bytes", 32768))
            self.assertEqual(self.worker.scene, before)
        self.assertTrue(all(call == ("describe_scene", {}) for call in self.worker.calls))

    def test_exact_result_budget_boundary_selects_full_or_summary(self):
        path = ROOT / "tests" / "fixtures" / "blender_lab" / "manifest-articulated-chest.json"
        self.worker.scene = json.loads(path.read_text(encoding="utf-8"))
        full = self.reply()["result"]; size = len(json.dumps(full).encode("utf-8"))
        self.assertGreater(size, 4096)
        reply = self.reply({"max_bytes": size}); self.assertIn("result", reply)
        self.assertEqual(reply["result"], full)
        self.projection({"max_bytes": size - 1})

    def test_oversized_default_falls_back_to_named_summary_without_mutating_manifest(self):
        self.worker.scene = scene([f"Object-{i:04d}" for i in range(250)], heavy=4096)
        before = copy.deepcopy(self.worker.scene)
        value = self.projection({})
        self.assertGreater(len(value["objects"]), 0)
        self.assertLess(len(value["objects"]), 250)
        self.assertEqual(value["summary_reason"], "result_budget")
        self.assertEqual(value["counts"], before["counts"])
        self.assertEqual(value["omitted_sections"], {"materials": 1, "meshes": 1, "object_samples": 250})
        self.assertEqual(value["omitted_object_fields"], ["data", "vertex_weights"])
        self.assertEqual(value["page"]["objects_excluded_by_filter"], 0)
        self.assertEqual(value["page"]["remaining"], 250 - len(value["objects"]))
        self.assertEqual(self.worker.scene, before)
        self.assertEqual(manifests.semantic_checksum(self.worker.scene), before["semantic_checksum"])

    def test_filter_is_exact_names_and_world_values_use_the_same_summary_shape(self):
        names = ["Case", "case", "é", "e\u0301", "*", "quoted\"\\\n树🌳"]
        self.worker.scene = scene(names, heavy=4000)
        wanted = [names[-1], "Case", "*", "é"]
        value = self.projection({"objects": wanted})
        self.assertEqual([o["name"] for o in value["objects"]], sorted(wanted))
        self.assertEqual(value["page"], {"objects_total": 6, "objects_selected": 4, "objects_excluded_by_filter": 2,
                                         "offset": 0, "returned": 4, "remaining": 0, "next_cursor": None})
        self.assertEqual(value["transform_space"], "world")
        original = {o["name"]: o for o in self.worker.scene["objects"]}
        for row in value["objects"]:
            self.assertEqual(set(row), {"name", "type", "parent", "parent_type", "parent_bone", "matrix_world", "hide_render", "visible"})
            self.assertEqual(row, {k: original[row["name"]][k] for k in row})
        self.assertEqual(self.worker.calls, [("describe_scene", {})])
        self.assertNotIn("materials", value)

    def test_unknown_filter_names_are_reported_without_silent_partial_success(self):
        reply = self.reply({"objects": ["Root", "root", "missing"]})
        self.assertIn("result", reply)
        self.assertTrue(reply["result"]["isError"])
        self.assertIn("2", reply["result"]["content"][0]["text"])
        self.assertIn("not found", reply["result"]["content"][0]["text"])
        self.assertEqual(self.worker.calls, [("describe_scene", {})])

    def test_empty_scene_summary_finishes_without_a_cursor(self):
        self.worker.scene = scene([])
        value = self.projection({"mode": "summary", "max_bytes": 4096})
        self.assertEqual(value["objects"], [])
        self.assertEqual(value["page"], {"objects_total": 0, "objects_selected": 0, "objects_excluded_by_filter": 0,
                                         "offset": 0, "returned": 0, "remaining": 0, "next_cursor": None})

    def test_summary_pages_cover_selected_names_once_with_exact_counts_and_stable_cursors(self):
        names = [f"树🌳-{i:03d}" for i in range(80)]
        self.worker.scene = scene(list(reversed(names)), heavy=1000)
        selected = names[::2]; args = {"mode": "summary", "objects": list(reversed(selected)), "max_bytes": 4096}
        seen = []; token = None
        for _ in range(len(selected) + 1):
            request = {**args, **({"cursor": token} if token else {})}
            value = self.projection(request)
            self.assertEqual(value, self.projection(request), "the same request and scene have deterministic pages")
            page = value["page"]; rows = value["objects"]
            self.assertEqual(page["offset"], len(seen))
            self.assertEqual(page["returned"], len(rows)); self.assertGreater(len(rows), 0)
            self.assertEqual(page["objects_selected"], 40); self.assertEqual(page["objects_excluded_by_filter"], 40)
            seen += [row["name"] for row in rows]
            self.assertEqual(page["remaining"], 40 - len(seen))
            token = page["next_cursor"]
            if token is None: break
            self.assertLessEqual(len(token), 512)
            args["objects"] = selected  # order is irrelevant; case and Unicode spelling are not
        else: self.fail("cursor did not make progress")
        self.assertEqual(seen, selected)
        self.assertTrue(all(call == ("describe_scene", {}) for call in self.worker.calls))

    def test_cursor_stays_summary_when_larger_budget_would_fit_the_full_manifest(self):
        self.worker.scene = scene([f"Object-{i:03d}" for i in range(40)])
        first = self.projection({"mode": "summary", "max_bytes": 4096})
        self.assertIsNotNone(first["page"]["next_cursor"])
        last = self.projection({"cursor": first["page"]["next_cursor"], "max_bytes": 65536})
        self.assertEqual(last["page"]["remaining"], 0)
        self.assertEqual(last["page"]["offset"], first["page"]["returned"])
        self.assertEqual(len(first["objects"]) + len(last["objects"]), 40)
        self.assertNotEqual(self.reply({"max_bytes": 65536})["result"]["content"][0]["text"], json.dumps(last, sort_keys=True))

    def test_invalid_option_types_and_malformed_cursors_never_reach_the_worker(self):
        invalid = [{"mode": v} for v in (None, False, [], "full")] + [
            {"max_bytes": v} for v in (True, None, 4095, 65537, 4096.0, "4096")] + [
            {"objects": v} for v in (None, "Root", [], [True], [""], ["Root", "Root"], ["x" * 257], [str(i) for i in range(101)])] + [
            {"cursor": v} for v in (None, False, "", "a", "%bad", "树", "a" * 513)] + [None, False, 0, "", []]
        for args in invalid:
            with self.subTest(args=args):
                reply = rpc(self.server, "tools/call", {"name": "blender_describe_scene", "arguments": args})
                self.assertEqual(reply.get("error", {}).get("code"), -32602, reply)
        self.assertEqual(self.worker.calls, [])

    def test_cursor_validation_distinguishes_malformed_changed_selection_and_stale_scene(self):
        self.worker.scene = scene([f"Object-{i:03d}" for i in range(50)])
        first = self.projection({"mode": "summary", "max_bytes": 4096})
        token = first["page"]["next_cursor"]
        raw = json.loads(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)))
        for edit in ({"offset": True}, {"offset": 0}, {"offset": -1}, {"version": 2}, {"mode": "auto"}, {"checksum": "bad"}):
            bad = base64.urlsafe_b64encode(json.dumps({**raw, **edit}).encode()).decode().rstrip("=")
            self.worker.calls.clear()
            self.assertEqual(self.reply({"cursor": bad})["error"]["code"], -32602)
            self.assertEqual(self.worker.calls, [])
        self.worker.calls.clear()
        self.assertEqual(self.reply({"cursor": token, "objects": ["Object-000"]})["error"]["code"], -32602)
        self.assertEqual(self.worker.calls, [])
        self.worker.scene["objects"][0]["hide_render"] = True
        self.worker.scene["semantic_checksum"] = manifests.semantic_checksum(self.worker.scene)
        stale = self.reply({"cursor": token})["result"]
        self.assertTrue(stale["isError"]); self.assertIn("scene changed", stale["content"][0]["text"].lower())
        self.assertEqual(self.worker.calls, [("describe_scene", {})])

    def test_out_of_range_cursor_and_unfit_first_row_have_no_zero_progress_continuation(self):
        self.worker.scene = scene([f"Object-{i:03d}" for i in range(40)])
        token = self.projection({"mode": "summary", "max_bytes": 4096})["page"]["next_cursor"]
        raw = json.loads(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))); raw["offset"] = 40
        token = base64.urlsafe_b64encode(json.dumps(raw).encode()).decode().rstrip("=")
        result = self.reply({"cursor": token})["result"]
        self.assertTrue(result["isError"])
        self.worker.scene = scene(["🌳" * 6000])
        result = self.reply({"mode": "summary", "max_bytes": 4096})["result"]
        self.assertTrue(result["isError"]); self.assertLessEqual(len(json.dumps(result).encode()), 4096)
        self.assertIn("cannot fit", result["content"][0]["text"])
        self.assertNotIn("next_cursor", result["content"][0]["text"])

    def test_actual_stdio_result_budget_handles_unicode_escaping_and_preserves_large_rpc_ids(self):
        self.worker.scene = scene([f'"\\\n树🌳-{i:03d}' for i in range(100)], heavy=1000)
        for ident in ('ID-🌳"\\\n' * 1000, 10 ** 4100):
            request = {"jsonrpc": "2.0", "id": ident, "method": "tools/call", "params": {
                "name": "blender_describe_scene", "arguments": {"mode": "summary", "max_bytes": 4096}}}
            out = io.StringIO(); mcp.serve(self.server, io.StringIO(json.dumps(request) + "\n"), out)
            wire = out.getvalue(); reply = json.loads(wire)
            self.assertEqual(reply["id"], ident)
            self.assertTrue("result" in reply, reply.get("error"))
            self.assertLessEqual(len(json.dumps(reply["result"]).encode("utf-8")), 4096)
            self.assertGreater(len(wire.encode("utf-8")), 4096, "caller-owned RPC IDs are not part of the advertised result budget")
            value = json.loads(reply["result"]["content"][0]["text"])
            self.assertGreater(len(value["objects"]), 0)

    def test_worker_errors_are_bounded_by_serialized_bytes_too(self):
        for message in ("汉" * 2000, "🌳" * 2000, '"\\\n' * 2000):
            self.worker.error = ValueError(message)
            reply = self.reply({"max_bytes": 4096})
            self.assertIn("result", reply)
            result = reply["result"]
            self.assertTrue(result["isError"])
            self.assertLessEqual(len(json.dumps(result).encode("utf-8")), 4096)
            if message.startswith(("汉", "🌳")):
                self.assertIn("exceeded", result["content"][0]["text"])
            else:
                self.assertTrue(result["content"][0]["text"].startswith("ValueError: "))


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
