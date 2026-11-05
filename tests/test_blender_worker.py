import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import blender_lab_bpy as bpy_side
import blender_worker as bw

LIVE_BLENDER = os.environ.get("LAS_BLENDER_LAB_EXE")
FAKE = r'''
import json, sys, time
print("Blender noise line")
print("@@LAS@@ " + json.dumps({"ready": True, "blender": "fake"}), flush=True)
for line in sys.stdin:
    request = json.loads(line)
    if request["cmd"] == "quit": break
    if request["cmd"] == "hang": time.sleep(30)
    if request["cmd"] == "deaf": time.sleep(30)  # stops reading stdin
    if request["cmd"] == "die": sys.exit(3)
    print("Fra:1 render noise", flush=True)
    ok = request["cmd"] != "bad"
    print("@@LAS@@ " + json.dumps({"id": request["id"], "ok": ok, "result": request["args"], "error": "WorkerError: no"}), flush=True)
'''


class ClientTests(unittest.TestCase):
    def worker(self, tmp):
        script = Path(tmp) / "fake_worker.py"; script.write_text(FAKE)
        exe = Path(tmp) / "blender.exe"; exe.write_bytes(b"")
        with mock.patch.object(bw.lab, "command_for", return_value=[sys.executable, str(script)]):
            return bw.BlenderWorker(exe, tmp, start_timeout=30)

    def test_replies_are_filtered_from_blender_noise_and_matched_by_id(self):
        with tempfile.TemporaryDirectory() as tmp, self.worker(tmp) as worker:
            self.assertEqual(worker.ready["blender"], "fake")
            self.assertEqual(worker.call("ping", x=1), {"x": 1})
            self.assertEqual(worker.call("ping", x=2), {"x": 2})

    def test_refusal_raises_and_the_worker_survives(self):
        with tempfile.TemporaryDirectory() as tmp, self.worker(tmp) as worker:
            with self.assertRaises(bw.WorkerFailed): worker.call("bad")
            self.assertEqual(worker.call("ping"), {})

    def test_a_worker_that_stops_reading_cannot_block_past_the_deadline(self):
        with tempfile.TemporaryDirectory() as tmp:
            worker = self.worker(tmp)
            worker.process.stdin.write(json.dumps({"id": 0, "cmd": "deaf", "args": {}}) + "\n"); worker.process.stdin.flush()
            started = time.monotonic()
            with self.assertRaises(bw.WorkerFailed):
                for _ in range(40): worker.call("ping", blob="x" * 16000, timeout=1)
            self.assertLess(time.monotonic() - started, 10)
            self.assertIsNotNone(worker.process.poll()); worker.close()

    def test_oversized_request_is_refused_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp, self.worker(tmp) as worker:
            with self.assertRaisesRegex(bw.lab.BlenderLabError, "too large"): worker.call("ping", blob="x" * bw.MAX_REQUEST_BYTES)
            self.assertEqual(worker.call("ping"), {})

    def test_reimport_validate_out_dir_must_be_a_plain_name(self):
        client = object.__new__(bw.BlenderWorker)
        with tempfile.TemporaryDirectory() as tmp:
            client.root = Path(tmp)
            for bad in ("../escape", "..", "a/b", str(Path(tmp).parent / "x"), ""):
                with self.assertRaises(bw.lab.BlenderLabError, msg=bad): client.reimport_validate(bad)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_timeout_kills_and_exit_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            worker = self.worker(tmp)
            with self.assertRaisesRegex(bw.WorkerFailed, "no reply"): worker.call("hang", timeout=1)
            self.assertIsNotNone(worker.process.poll()); worker.close()
            worker = self.worker(tmp)
            with self.assertRaisesRegex(bw.WorkerFailed, "exited"): worker.call("die", timeout=10)
            worker.close()


class VocabularyTests(unittest.TestCase):
    def test_output_paths_stay_new_and_inside_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            worker = object.__new__(bpy_side.Worker); worker.root = os.path.realpath(tmp)
            Path(tmp, "taken.glb").write_bytes(b"")
            self.assertTrue(worker._out("a/b.glb", ".glb").endswith("b.glb"))
            for bad in ("../x.glb", "taken.glb", "x.png", "", os.path.join(tmp, "..", "y.glb")):
                with self.assertRaises(bpy_side.WorkerError, msg=bad): worker._out(bad, ".glb")

    def test_camera_view_names_cannot_become_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            worker = object.__new__(bpy_side.Worker); worker.root, worker.source = os.path.realpath(tmp), "x.blend"
            spec = {"target": [0, 0, 0], "ortho_scale": 2.0, "frame": 1, "views": {"../../victim": [0.0, 0.0]}}
            with self.assertRaisesRegex(bpy_side.WorkerError, "fixed views"): worker.render_views("r", cameras=spec)
            spec["views"] = {"front": [0.0, "x"]}
            with self.assertRaises(bpy_side.WorkerError): worker.render_views("r", cameras=spec)
            self.assertEqual(os.listdir(tmp), [])

    def test_numbers_are_finite_and_bounded(self):
        self.assertEqual(bpy_side._finite(2, 0, 5), 2.0)
        for bad in (float("nan"), float("inf"), 6, "1", True):
            with self.assertRaises(bpy_side.WorkerError): bpy_side._finite(bad, 0, 5)

    def test_unknown_command_and_bad_args_are_refused_without_dying(self):
        worker = object.__new__(bpy_side.Worker); worker.calls = 0
        self.assertFalse(worker.handle({"id": 1, "cmd": "exec", "args": {}})["ok"])
        self.assertIn("TypeError", worker.handle({"id": 2, "cmd": "ping", "args": {"code": "x"}})["error"])
        self.assertEqual(worker.calls, 2)

    def test_bench_plan_mixes_reads_writes_and_reversible_edits(self):
        plan = bw._plan(30)
        self.assertEqual(len(plan), 30)
        self.assertEqual(plan.count("apply_edit"), plan.count("apply_edit_revert"))
        self.assertIn("render_views", plan)


class StartupProbeTests(unittest.TestCase):
    class NativeGraphicsAbort(BaseException): pass  # _attempt cannot catch a native process abort either

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); scratch = self.root / 'scratch'; scratch.mkdir()
        app = SimpleNamespace(version=(5, 4, 0), version_string='5.4.0 Alpha', version_cycle='alpha',
                              build_hash=b'fixture', build_branch=b'main', build_date=b'2026-11-05',
                              build_platform=b'Linux', background=True)
        bpy = SimpleNamespace(app=app, ops=SimpleNamespace(wm=SimpleNamespace(read_factory_settings=mock.Mock())),
                              context=SimpleNamespace(preferences=SimpleNamespace(system=SimpleNamespace(gpu_backend='VULKAN'))),
                              types=SimpleNamespace(PreferencesSystem=object()))
        self.gpu = SimpleNamespace(init=mock.Mock(side_effect=self.NativeGraphicsAbort('no graphics runtime')),
                                   platform=SimpleNamespace(**{name: mock.Mock(return_value='fixture') for name in
                                                              ('backend_type_get', 'vendor_get', 'renderer_get', 'version_get')}))
        patches = [mock.patch.dict(sys.modules, {'bpy': bpy, 'gpu': self.gpu}),
                   mock.patch.object(tempfile, 'mkdtemp', return_value=str(scratch)),
                   mock.patch.object(bpy_side, '_enum_ids', return_value=[])]
        for name in ('_action_api', '_shader_nodes', '_projects', '_point_clouds', '_gltf_export', '_render_engines'):
            patches.append(mock.patch.object(bpy_side, name, return_value={'fixture': True}))
        for patcher in patches: patcher.start(); self.addCleanup(patcher.stop)
        self.cycles = mock.patch.object(bpy_side, '_cycles', side_effect=self.NativeGraphicsAbort('device enumeration'))
        self.cycles_mock = self.cycles.start(); self.addCleanup(self.cycles.stop)

    def test_worker_startup_never_initializes_or_queries_gpu_and_reports_unknown(self):
        worker = bpy_side.Worker(str(self.root))
        self.gpu.init.assert_not_called(); self.cycles_mock.assert_not_called()
        self.gpu.platform.backend_type_get.assert_not_called()
        for name in ('gpu_backend', 'cycles_devices'):
            feature = worker.caps()['features'][name]
            self.assertIsNone(feature['ok']); self.assertEqual(feature['state'], 'not-probed')
            self.assertIn('not requested', feature['reason'])

    def test_explicit_probe_still_initializes_graphics_and_enumerates_devices(self):
        self.gpu.init.side_effect = None
        self.cycles_mock.side_effect = None; self.cycles_mock.return_value = {'gpu_visible': []}
        result = bpy_side.probe()
        self.gpu.init.assert_called_once_with(); self.cycles_mock.assert_called_once_with()
        self.assertTrue(result['features']['gpu_backend']['ok'])
        self.assertTrue(result['features']['cycles_devices']['ok'])


@unittest.skipUnless(LIVE_BLENDER, "set LAS_BLENDER_LAB_EXE to a Blender executable for the live worker")
class LiveWorkerTests(unittest.TestCase):
    def test_session_is_typed_leak_free_and_validates_a_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            blend = bw.lab.make_fixture(LIVE_BLENDER, Path(tmp) / "asset")
            (Path(tmp) / "root").mkdir()
            with bw.BlenderWorker(LIVE_BLENDER, Path(tmp) / "root") as worker:
                with self.assertRaisesRegex(bw.WorkerFailed, "allow_edit"): worker.call("open", blend=str(blend), allow_edit=["Nope"])
                with self.assertRaisesRegex(bw.WorkerFailed, "open a .blend first"):  # the refused open left no authority
                    worker.call("apply_edit", object="Badge", op="hide_render", value=True, expect_checksum="x")
                start = worker.call("open", blend=str(blend), allow_edit=["Badge"])["semantic_checksum"]
                state = worker.call("ping")["state"]
                worker.call("render_views", out_dir="r", size=64, samples=1)
                self.assertEqual(worker.call("describe_scene")["semantic_checksum"], start)
                self.assertEqual(worker.call("ping")["state"], state)
                moved = worker.call("apply_edit", object="Badge", op="location", value=[0.22, -0.37, 1.3], expect_checksum=start)
                self.assertNotEqual(moved["after"], start)
                with self.assertRaisesRegex(bw.WorkerFailed, "precondition"):
                    worker.call("apply_edit", object="Badge", op="location", value=[0, 0, 0], expect_checksum=start)
                with self.assertRaisesRegex(bw.WorkerFailed, "allow_edit"):
                    worker.call("apply_edit", object="Head", op="hide_render", value=True, expect_checksum=moved["after"])
                back = worker.call("apply_edit", object="Badge", op="location", value=[0.22, -0.37, 1.05], expect_checksum=moved["after"])
                self.assertEqual(back["after"], start)
                result = worker.reimport_validate("rv")
                self.assertTrue(result["pass"], result["structural_failures"] + result["visual_warnings"])


if __name__ == "__main__":
    unittest.main()
