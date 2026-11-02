from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import blender_lab as lab
import blender_sentinel as sentinel


def evidence(lit_device="CPU", engine="BLENDER_WORKBENCH", **timings):
    return {"timings": timings, "lit": {"device": lit_device}, "id_passes": {"engine": engine}}


class GpuCostTests(unittest.TestCase):
    def test_cpu_cycles_and_gpu_workbench_are_split_and_classified(self):
        light = lab.gpu_cost(evidence(lit=4.0, clay=0.5, object_id=0.5, material_id=0.5), evidence(lit=4.0, clay=0.6))
        self.assertEqual((light["cpu_seconds"], light["gpu_seconds"], light["class"]), (8.0, 2.1, "light"))
        heavy = lab.gpu_cost(evidence(lit_device="HIP", lit=31.0))
        self.assertEqual((heavy["gpu_seconds"], heavy["class"]), (31.0, "heavy"))


class FakeStudio(BaseHTTPRequestHandler):
    calls, refuse = [], False

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeStudio.calls.append((self.path, body, self.headers.get("Origin")))
        status, reply = (409, {"error": "busy", "code": "studio_work_active"}) if FakeStudio.refuse and self.path == "/api/gpu-lease" \
            else (200, {"granted": True} if self.path == "/api/gpu-lease" else {"released": True})
        raw = json.dumps(reply).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)

    def log_message(self, *args): pass


class StudioLeaseTests(unittest.TestCase):
    def setUp(self):
        FakeStudio.calls, FakeStudio.refuse = [], False
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeStudio)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown(); self.server.server_close()

    def test_acquire_and_release_with_same_origin(self):
        with lab.StudioGpuLease(self.url, ttl_seconds=120) as grant:
            self.assertTrue(grant["granted"])
        holder = FakeStudio.calls[0][1]["holder"]
        self.assertRegex(holder, r"^blender-lab-[0-9a-f]{12}$")
        self.assertEqual([(p, b) for p, b, _ in FakeStudio.calls],
                         [("/api/gpu-lease", {"holder": holder, "ttl_seconds": 120}), ("/api/gpu-lease/release", {"holder": holder})])
        self.assertEqual({origin for _, _, origin in FakeStudio.calls}, {self.url})

    def test_refused_lease_starts_no_blender(self):
        FakeStudio.refuse = True
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "blender.exe"; exe.write_bytes(b"")
            blend = Path(tmp) / "a.blend"; blend.write_bytes(b"")
            with mock.patch.object(lab, "run") as run, self.assertRaisesRegex(lab.BlenderLabError, "studio_work_active"):
                sentinel.sentinel(exe, blend, Path(tmp) / "out", studio_lease=self.url)
            run.assert_not_called()

    def test_each_run_has_its_own_holder_and_a_ttl_covering_both_processes(self):
        self.assertNotEqual(lab.StudioGpuLease(self.url).holder, lab.StudioGpuLease(self.url).holder)
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "blender.exe"; exe.write_bytes(b"")
            blend = Path(tmp) / "a.blend"; blend.write_bytes(b"")
            with mock.patch.object(lab, "run", side_effect=lab.BlenderLabError("stop after acquire")):
                with self.assertRaises(lab.BlenderLabError): sentinel.sentinel(exe, blend, Path(tmp) / "out", timeout=600, studio_lease=self.url)
        self.assertEqual(FakeStudio.calls[0][1]["ttl_seconds"], 1500)
        self.assertEqual(FakeStudio.calls[-1][0], "/api/gpu-lease/release")  # released on the failure path

    def test_uncertain_grant_releases_its_own_holder(self):
        lease = lab.StudioGpuLease(self.url)
        posted = []
        def flaky(path, payload):
            posted.append(path)
            if path == "/api/gpu-lease": raise lab.BlenderLabError("Studio GPU lease /api/gpu-lease unreachable: timed out")
            return {"released": True}
        with mock.patch.object(lease, "_post", side_effect=flaky), self.assertRaises(lab.BlenderLabError):
            with lease: pass
        self.assertEqual(posted, ["/api/gpu-lease", "/api/gpu-lease/release"])

    def test_only_loopback_http_urls_are_accepted(self):
        for bad in ("https://127.0.0.1:8191", "http://example.com:8191", "http://127.0.0.1", "http://u:p@127.0.0.1:8191",
                    "http://127.0.0.1:8191/api"):
            with self.assertRaises(lab.BlenderLabError, msg=bad): lab.StudioGpuLease(bad)


if __name__ == "__main__":
    unittest.main()
