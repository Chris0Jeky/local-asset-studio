import base64
import http.client
import hashlib
import io
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest


SPEC = importlib.util.spec_from_file_location("prompt_startup_server", Path(__file__).parents[1] / "app/server.py")
server = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(server)


class FakeStudio:
    def __init__(self, root): self.root = Path(root); self.jobs = {}
    def identity(self): return {"app": "local-asset-studio", "workspace": str(self.root)}


class PromptStartupTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js is required for frontend behavior checks')
    def test_browser_script_loads_profiles_and_reports_http_failure(self):
        result = subprocess.run([shutil.which('node'), str(Path(__file__).with_name('prompt_lab_frontend.cjs'))], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Prompt Lab frontend contracts passed', result.stdout, result.stdout + result.stderr)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.http = server.create_server(self.temporary.name, port=0, studio_factory=FakeStudio)
        self.worker = threading.Thread(target=self.http.serve_forever, daemon=True); self.worker.start()

    def tearDown(self):
        self.http.shutdown(); self.http.server_close(); self.worker.join(2); self.temporary.cleanup()

    def request(self, method, path, payload=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.http.server_port)
        supplied = {"Host": "127.0.0.1:8191"}; supplied.update(headers or {})
        if payload is not None: supplied.setdefault("Content-Type", "application/json")
        connection.request(method, path, json.dumps(payload) if payload is not None else None, supplied)
        response = connection.getresponse(); body = json.loads(response.read()); connection.close()
        return response.status, body

    def test_normal_server_exposes_prompt_routes_without_creating_jobs(self):
        status, identity = self.request("GET", "/api/identity")
        self.assertEqual((status, identity["app"]), (200, "local-asset-studio"))
        status, profiles = self.request("GET", "/api/prompt/profiles")
        self.assertEqual(status, 200); self.assertTrue(profiles["profiles"]); self.assertFalse(profiles["generation_submitted"])
        intent = {"schema_version": 1, "id": "creative-brief", "task": "image", "brief": "An observatory keeper.", "facets": {}, "tags": [], "avoid": [], "constraints": [], "references": [], "verbatim": {}, "parameters": {}, "locked": ["verbatim"]}
        status, compiled = self.request("POST", "/api/prompt/compile", {"intent": intent, "profile_id": "sdxl-prose-v1"}, {"Origin": "http://127.0.0.1:8191"})
        self.assertEqual(status, 200); self.assertFalse(compiled["generation_submitted"]); self.assertEqual(self.http.RequestHandlerClass.studio.jobs, {})

    def test_metadata_http_accepts_actual_formats_and_bound_sidecar_without_jobs(self):
        from PIL import Image
        image = Image.new('RGB', (2, 3))
        origin = {"Origin": "http://127.0.0.1:8191"}
        for fmt in ('PNG', 'JPEG', 'WEBP'):
            with self.subTest(format=fmt):
                stream = io.BytesIO(); image.save(stream, format=fmt); raw = stream.getvalue()
                sidecar = {"schema_version": 1, "image_sha256": hashlib.sha256(raw).hexdigest(),
                           "producer": {"name": "HTTP fixture", "version": "1"},
                           "entries": [{"keyword": "parameters", "value": "Fixture, not generation evidence"}]}
                status, report = self.request("POST", "/api/prompt/metadata", {
                    "media_base64": base64.b64encode(raw).decode(),
                    "sidecar_base64": base64.b64encode(json.dumps(sidecar).encode()).decode()}, origin)
                self.assertEqual(status, 200, report)
                self.assertFalse(report["workflow_executed"])
                self.assertEqual(report["sidecar"]["image_binding"], "hash_matched_not_authenticated")
                self.assertEqual(report["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(self.http.RequestHandlerClass.studio.jobs, {})

    def test_metadata_http_malformed_payload_is_400_and_never_generates(self):
        for payload in ({"media_base64": "%%%%"}, {"media_base64": "AA=="},
                        {"media_base64": "", "png_base64": ""}, {"media_base64": "", "execute": True}):
            with self.subTest(payload=payload):
                status, error = self.request("POST", "/api/prompt/metadata", payload,
                                             {"Origin": "http://127.0.0.1:8191"})
                self.assertEqual(status, 400)
                self.assertFalse(error["generation_submitted"])
        self.assertEqual(self.http.RequestHandlerClass.studio.jobs, {})

    def test_prompt_routes_keep_loopback_host_and_origin_guards(self):
        status, _ = self.request("GET", "/api/prompt/profiles", headers={"Host": "studio.example:8191"})
        self.assertEqual(status, 403)
        status, _ = self.request("POST", "/api/prompt/compile", {"intent": {}, "profile_id": "sdxl-prose-v1"}, {"Origin": "http://studio.example:8191"})
        self.assertEqual(status, 403); self.assertEqual(self.http.RequestHandlerClass.studio.jobs, {})

    def test_port_failure_happens_before_studio_creation(self):
        created = []
        class OccupiedPort:
            def __init__(self, *args): raise OSError("already in use")
        with self.assertRaisesRegex(OSError, "already in use"):
            server.create_server(self.temporary.name, http_server=OccupiedPort, studio_factory=lambda root: created.append(root))
        self.assertEqual(created, [])

    def test_second_server_cannot_bind_a_listening_port(self):
        created = []
        with self.assertRaises(OSError):
            server.create_server(self.temporary.name, port=self.http.server_port, studio_factory=lambda root: created.append(root))
        self.assertEqual(created, [])
