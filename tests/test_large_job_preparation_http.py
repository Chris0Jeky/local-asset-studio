import json
import sys
import threading
import unittest
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "app"))
import large_job_preparation
from studio_prompt import http_extension


class Controller:
    def __init__(self):
        self.values = []
        self.error = None

    def run(self, value):
        self.values.append(value)
        if self.error:
            raise self.error
        return {"schema": "studio.large-job-preparation/v1", "final": {"ready": False},
                "generation_submitted": False}


class LargeJobPreparationHTTPTests(unittest.TestCase):
    def setUp(self):
        self.controller = Controller()
        controller = self.controller

        class Base(BaseHTTPRequestHandler):
            studio = SimpleNamespace()
            mutation_allowed = True

            def log_message(self, *args): pass
            def _safe_host(self): return True
            def _safe_mutation(self): return self.mutation_allowed

            def _content_length(self, limit):
                value = int(self.headers.get("Content-Length", "0"))
                if value > limit: raise ValueError("too large")
                return value

            def _json(self, status, value):
                raw = json.dumps(value).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_POST(self): self._json(404, {"error": "base"})
            def do_GET(self): self._json(404, {"error": "base"})

        self.Base = Base
        self.patch = patch.object(large_job_preparation, "controller_for", return_value=controller)
        self.patch.start()
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), http_extension.extend_handler(Base))
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.http.shutdown(); self.http.server_close(); self.thread.join(2); self.patch.stop()

    def post(self, body=None, content_type="application/json"):
        connection = HTTPConnection("127.0.0.1", self.http.server_port, timeout=5)
        try:
            raw = json.dumps(body or {}).encode()
            connection.request("POST", "/api/large-job-preparation", raw, {"Content-Type": content_type})
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def test_same_origin_json_command_uses_lazy_controller_and_never_claims_submission(self):
        request = {"request_id": "prepare-1", "recipe": {"preset_id": "demo"}}
        status, body = self.post(request)
        self.assertEqual(status, 200)
        self.assertEqual(self.controller.values, [request])
        self.assertFalse(body["generation_submitted"])

    def test_cross_origin_and_wrong_media_type_are_refused_before_controller(self):
        self.Base.mutation_allowed = False
        status, _ = self.post()
        self.assertEqual(status, 403)
        self.Base.mutation_allowed = True
        status, body = self.post(content_type="text/plain")
        self.assertEqual(status, 400)
        self.assertFalse(body["generation_submitted"])
        self.assertEqual(self.controller.values, [])

    def test_domain_validation_error_is_bounded_bad_request(self):
        self.controller.error = ValueError("invalid preparation request")
        status, body = self.post()
        self.assertEqual(status, 400)
        self.assertEqual(body["error"], "invalid preparation request")
        self.assertFalse(body["generation_submitted"])


if __name__ == "__main__": unittest.main()
