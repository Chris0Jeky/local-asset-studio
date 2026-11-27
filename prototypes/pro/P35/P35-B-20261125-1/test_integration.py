"""Independent compiler/adapter integration against pinned preparation source.

Set P35_PACKAGE_ROOT to the package under review and P35_SOURCE_ROOT to its
separate pinned Studio source tree. Source preparation is CPU-only with synthetic
non-image uploads, no model reads, no GPU, and no contact with a real service.
The HTTP fixture observes actual source-prepared graphs, not planner.materialize_graph.
"""
from __future__ import annotations

from contextlib import contextmanager
import copy
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path, PureWindowsPath
import subprocess
import sys
import tempfile
import threading
import unittest


PACKAGE = Path(os.environ.get("P35_PACKAGE_ROOT", Path(__file__).resolve().parent)).resolve()
SOURCE = Path(os.environ.get("P35_SOURCE_ROOT", PACKAGE.parents[3])).resolve()


def sha(value, *, ascii=False):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=ascii, allow_nan=False).encode("utf-8")).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


@contextmanager
def selected_modules():
    names = {"qualification": "qualification.py", "_p35_integration_plan": "plan.py",
             "_p35_integration_runner": "owner_run.py", "_p35_integration_source": "source_contract_check.py"}
    previous = {name: sys.modules.get(name) for name in names}
    previous_path = list(sys.path)
    try:
        sys.path.insert(0, str(PACKAGE))
        for name, filename in names.items():
            spec = importlib.util.spec_from_file_location(name, PACKAGE / filename)
            if spec is None or spec.loader is None:
                raise RuntimeError("Selected package cannot be loaded")
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
        yield tuple(sys.modules[name] for name in ("_p35_integration_plan", "_p35_integration_runner", "_p35_integration_source"))
    finally:
        sys.path[:] = previous_path
        for name, module in previous.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


class NativeFixture:
    """Use extracted Studio.prepare/references.py against synthetic input bytes."""
    def __init__(self, planner, source_checker, directory):
        self.planner = planner
        self.directory = directory
        self.uploads = directory / "uploads"
        self.uploads.mkdir()
        self.bundle = read(PACKAGE / "routes.json")
        self.suite = read(PACKAGE / "suite.json")
        self.routes = {route["preset_id"]: route for route in self.bundle["routes"]}
        self.catalog = {preset["id"]: preset for preset in read(SOURCE / "presets/catalog.json")["presets"]}
        self.inventory = {asset["file"]: asset for asset in read(SOURCE / "models/library.json")["assets"]}
        self.prepare_class, self.reference_namespace = source_checker.source_preparer(SOURCE)
        self.owner = planner.owner_template(self.suite)
        self.owner["expected_identity"]["workspace"] = str(directory)
        self.records = {}
        sequence = 0

        def bind(record, label, suffix="source"):
            nonlocal sequence
            sequence += 1
            filename = f"{sequence:032x}_{suffix}.png"
            raw = ("INERT NON-IMAGE FIXTURE ONLY: " + label).encode()
            (self.uploads / filename).write_bytes(raw)
            record.update(file=filename, sha256=hashlib.sha256(raw).hexdigest())
            self.records[filename] = {"file": filename, "sha256": record["sha256"],
                                      "bytes": len(raw), "width": 832, "height": 1248}

        for key, record in self.owner["reference_bindings"].items():
            bind(record, "reference-" + key)
        for key, record in self.owner["guides"].items():
            bind(record, "guide-" + key, "drawn-pose")
        bind(self.owner["default_style"], "default-style", "style")
        for key, character in self.owner["characters"].items():
            character.update(description="Original adult synthetic Épée — 雪 character " + key,
                             outfit="teal coat with a brass clasp", style="cel shading — two tones",
                             details=["violet eyes", "left clasp ⚙"])

        def image_record(root, filename, **_kwargs):
            if Path(root) != self.uploads or filename not in self.records:
                raise ValueError("Source preparation requested an unbound input")
            return copy.deepcopy(self.records[filename])

        self.reference_namespace["image_record"] = image_record
        self.backend = {"url": "http://127.0.0.1:8188", "root": r"C:\P35-inert-fixture\ComfyUI"}

    def compile(self, seed_count, *, owner=None, routes=None):
        return self.planner.compile_plan(self.suite, self.bundle, owner or self.owner,
            route_ids=routes or [route["id"] for route in self.bundle["routes"]],
            case_ids=["ordinary-neutral"], seed_count=seed_count, allow_heavy=True)

    def stage(self, recipe, variant):
        preset = copy.deepcopy(self.catalog[recipe["preset_id"]])
        studio = self.prepare_class()
        studio.experiments = self.directory
        studio.require_worker = lambda: None
        studio.preset = lambda identifier: copy.deepcopy(preset) if identifier == preset["id"] else None
        studio.graph_for = lambda entry: (read(SOURCE / entry["graph"]), SOURCE / entry["graph"])
        studio.options = lambda: {}
        studio._upload_path = lambda name, *_args, **_kwargs: self.uploads / name
        studio.ensure_reference_inputs = lambda *_args: None
        studio._validate_i2v_mode_source = lambda *_args, **_kwargs: None
        studio.host_commit_preflight = lambda *_args, **_kwargs: None
        request = dict(copy.deepcopy(recipe), batch_count=1)
        request["controls"].update(variant["controls"])
        actual_preset, graph, source_path, _normalized_controls, batch = studio.prepare(request)
        if batch != 1:
            raise ValueError("Source fixture unexpectedly created a batch")
        request["references"] = actual_preset.get("_prepared_references", [])
        request["expected_template_sha256"] = hashlib.sha256(source_path.read_bytes()).hexdigest()
        return {"operation": "comfy.generate.v1", "request": request, "graph": graph,
                "graph_sha256": sha(graph, ascii=True)}

    def bundle_for_stages(self, stages):
        # Independent source inventory lookup keyed by each actual graph loader;
        # deliberately do not copy the compiler's expected_models/expected_inputs.
        loaders = {"UnetLoaderGGUF": ("unet_name", "diffusion_models"),
                   "UNETLoader": ("unet_name", "diffusion_models"),
                   "CLIPLoader": ("clip_name", "text_encoders"),
                   "VAELoader": ("vae_name", "vae"),
                   "LoraLoaderModelOnly": ("lora_name", "loras")}
        models, inputs, classes = {}, {}, set()
        for stage in stages:
            for node in stage["graph"].values():
                kind = node["class_type"]
                classes.add(kind)
                if kind in loaders:
                    field, category = loaders[kind]
                    filename = category + "/" + node["inputs"][field].replace("\\", "/")
                    source = self.inventory[filename]
                    models[filename] = {"file": filename, "sha256": source["sha256"], "bytes": source["bytes"],
                        "path": str(PureWindowsPath(self.backend["root"]) / "models" / filename), "mtime_ns": 1}
                if kind == "LoadImage":
                    filename = node["inputs"]["image"]
                    source = self.records[filename]
                    inputs[filename] = {"path": str(PureWindowsPath(self.backend["root"]) / "input" / filename),
                                        "sha256": source["sha256"], "bytes": source["bytes"]}
        return {"comfy_url": self.backend["url"], "comfy_root": self.backend["root"], "models": list(models.values()),
                "inputs": list(inputs.values()), "schema_sha256": "a" * 64, "node_classes": sorted(classes),
                "system": {}, "devices": [], "measured_at": 1.0, "terms_note": "Synthetic fixture; licence unknown",
                "verification": "Source-prepared graph; model metadata from pinned inventory, no model files opened"}

    def project(self, payload, identifier):
        recipe = dict(copy.deepcopy(payload["recipe"]), batch_count=1)
        stages = [dict(self.stage(payload["recipe"], variant), label=chr(65 + index))
                  for index, variant in enumerate(payload["variants"])]
        plan = {"version": 1, "kind": "comparison", "name": payload["name"], "recipe": recipe,
                "axis": "variants", "values": [variant["label"] for variant in payload["variants"]],
                "variants": [dict(variant, rationale="", sources=[]) for variant in payload["variants"]],
                "knowledge_sha256": "b" * 64, "parent_project": None, "max_seconds": payload["max_seconds"],
                "stages": stages, "bundle": self.bundle_for_stages(stages), "repair_allowance": 0,
                "review": "unreviewed", "created_at": 1.0, "character_source": None}
        plan["sha256"] = sha(plan, ascii=True)
        return {"id": identifier, "root_id": identifier, "created_at": 1.0,
                "budget": {"allowance": len(stages), "reserved": 0}, "plan": plan,
                "state": {"status": "planned", "attempts": {}, "artifacts": [], "stop_requested": False,
                          "message": "Inert source preparation only", "review": {"status": "unreviewed", "notes": ""}}}

    @staticmethod
    def public(project, *, full=True):
        result = {key: copy.deepcopy(project[key]) for key in ("id", "root_id", "created_at", "budget", "state")}
        plan = project["plan"]
        result.update(name=plan["name"], kind="comparison", parent_project=None, plan_sha256=plan["sha256"],
                      recipe=copy.deepcopy(plan["recipe"]), axis="variants", values=plan["values"], variants=plan["variants"],
                      knowledge_sha256=plan["knowledge_sha256"], combine=None, export_kind=None,
                      can_reconcile_tracking=False, can_reconcile_batch=False, put_away=False, put_away_at=None,
                      can_put_away=True, can_bring_back=False)
        result["stages"] = []
        for index, stage in enumerate(plan["stages"]):
            attempt = project["state"]["attempts"].get(str(index), {})
            job = None
            if attempt.get("status") == "completed":
                job = {"id": attempt["job_id"], "status": "completed", "project_id": project["id"], "batch_count": 1,
                       "prompt_ids": list(attempt["prompt_ids"]), "submissions": [], "outputs": []}
            result["stages"].append({"label": stage["label"], "operation": stage["operation"],
                                     "attempt": copy.deepcopy(attempt), "job": job})
        if full:
            result["plan"] = copy.deepcopy(plan)
        return result


class HTTPFixture:
    def __init__(self, native):
        self.native, self.projects, self.calls, self.errors = native, {}, [], []
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def reply(self, status, value):
                body = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                fixture.calls.append(("GET", self.path, None))
                if self.path == "/api/identity":
                    return self.reply(200, native.owner["expected_identity"])
                if self.path == "/api/backends":
                    return self.reply(200, {"active": "primary", "busy": False, "operation": None, "state_issue": None,
                        "shared_state": {"blocker": None, "sha256": None, "resolvable": False}, "work_blocker": None,
                        "profiles": [{"id": "primary", **native.backend, "active": True, "online": True,
                                      "installed": True, "readiness": {"ready": True}}], "gpu_lease": {"held": False}})
                if self.path == "/api/production":
                    return self.reply(200, [native.public(project, full=False) for project in fixture.projects.values()])
                if self.path.startswith("/api/production/"):
                    project = fixture.projects[self.path.rsplit("/", 1)[-1]]
                    if project["state"]["status"] == "queued":
                        for index in range(len(project["plan"]["stages"])):
                            project["state"]["attempts"][str(index)] = {"status": "completed", "operation": "comfy.generate.v1",
                                "job_id": f"inert-job-{project['id']}-{index}", "prompt_ids": [f"inert-prompt-{project['id']}-{index}"]}
                        project["state"]["status"] = "awaiting_review"
                    return self.reply(200, native.public(project))
                return self.reply(404, {"error": "Unknown inert fixture route"})

            def do_POST(self):
                try:
                    if self.headers.get("Origin") != fixture.url:
                        raise ValueError("Missing same-origin header")
                    payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                    fixture.calls.append(("POST", self.path, payload))
                    if self.path == "/api/production":
                        identifier = f"{len(fixture.projects) + 1:032x}"
                        project = native.project(payload, identifier)
                        fixture.projects[identifier] = project
                        return self.reply(201, native.public(project, full=False))
                    if self.path.endswith("/start"):
                        if payload != {}:
                            raise ValueError("Start body must be empty")
                        project = fixture.projects[self.path.split("/")[3]]
                        if project["state"]["status"] != "planned":
                            raise ValueError("Duplicate start refused")
                        project["state"]["status"] = "queued"
                        project["budget"]["reserved"] = len(project["plan"]["stages"])
                        project["state"]["reserved"] = project["budget"]["reserved"]
                        return self.reply(202, native.public(project, full=False))
                    raise ValueError("Forbidden inert fixture mutation")
                except Exception as exc:
                    fixture.errors.append(str(exc))
                    return self.reply(500, {"error": str(exc)})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(3)


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (PACKAGE / "plan.py").is_file() or not (SOURCE / "app/server.py").is_file():
            raise unittest.SkipTest("Set P35_PACKAGE_ROOT and P35_SOURCE_ROOT to the package and pinned Studio source")
        cls.context = selected_modules()
        cls.planner, cls.runner, cls.source_checker = cls.context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.context.__exit__(None, None, None)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="p35-independent-integration-")
        self.directory = Path(self.temp.name)
        self.native = NativeFixture(self.planner, self.source_checker, self.directory)

    def tearDown(self):
        self.temp.cleanup()

    def test_all_four_routes_two_and_three_seeds_match_native_preparation_and_runner(self):
        for count in (2, 3):
            result = self.native.compile(count)
            self.assertTrue(result["ready"], result["blockers"])
            run = self.runner.validate_plan(result["owner_run"])
            self.assertEqual(len(run["chunks"]), 4)
            self.assertEqual(run["max_attempts"], 4 * count)
            for index, chunk in enumerate(run["chunks"], start=1):
                with self.subTest(seed_count=count, route=chunk["route_id"]):
                    actual = self.native.project(chunk["payload"], f"{index:032x}")
                    public = self.native.public(actual)
                    self.assertEqual(self.runner.validate_project(public, chunk, self.native.backend, full=True), "planned")
                    self.assertEqual([stage["graph_sha256"] for stage in actual["plan"]["stages"]], chunk["expected_graph_sha256"])
                    self.assertEqual(actual["budget"], {"allowance": count, "reserved": 0})

    def test_unicode_plan_and_graph_hashes_follow_distinct_canonical_contracts(self):
        result = self.native.compile(3)
        run = result["owner_run"]
        self.assertTrue(result["ready"], result["blockers"])
        self.assertEqual(result["plan_sha256"], sha({k: v for k, v in result.items() if k != "plan_sha256"}))
        self.assertEqual(run["plan_id"], sha({k: v for k, v in run.items() if k != "plan_id"}))
        self.assertNotEqual(run["plan_id"], sha({k: v for k, v in run.items() if k != "plan_id"}, ascii=True))
        for chunk in run["chunks"]:
            self.assertIn("Épée — 雪", chunk["payload"]["recipe"]["controls"]["positive"])
            project = self.native.project(chunk["payload"], "1" * 32)
            for stage, expected in zip(project["plan"]["stages"], chunk["expected_graph_sha256"]):
                self.assertEqual(expected, sha(stage["graph"], ascii=True))
                self.assertNotEqual(expected, sha(stage["graph"], ascii=False))

    def test_native_source_projects_complete_through_real_adapter_http_flow(self):
        for count in (2, 3):
            with self.subTest(seed_count=count):
                result = self.native.compile(count)
                self.assertTrue(result["ready"], result["blockers"])
                run = result["owner_run"]
                plan_file = self.directory / f"run-{count}.json"
                plan_file.write_text(json.dumps(run, ensure_ascii=False), encoding="utf-8")
                server = HTTPFixture(self.native)
                try:
                    command = [sys.executable, str(PACKAGE / "owner_run.py"), "--plan", str(plan_file), "--start",
                               "--runtime", str(self.directory / ".runtime"), "--base-url", server.url,
                               "--request-timeout", "2", "--poll-interval", "0.01"]
                    process = subprocess.run(command, text=True, capture_output=True, timeout=15)
                    self.assertEqual(process.returncode, 0, process.stdout + process.stderr + str(server.errors))
                    report = json.loads(process.stdout)
                    self.assertEqual(report["state"], "completed")
                    self.assertEqual(report["attempts_reserved"], 4 * count)
                    self.assertEqual(len([call for call in server.calls if call[:2] == ("POST", "/api/production")]), 4)
                    self.assertEqual(len([call for call in server.calls if call[0] == "POST" and call[1].endswith("/start")]), 4)
                    self.assertEqual([len(chunk["prompt_ids"]) for chunk in report["chunks"]], [count] * 4)
                    self.assertTrue(all(chunk["classification"] == {"execution": "completed", "visual": "unreviewed", "licence": "unknown"}
                                        for chunk in report["chunks"]))
                    self.assertEqual(server.errors, [])
                finally:
                    server.close()

    def test_compiler_does_not_emit_ready_for_identity_runner_will_reject(self):
        for change in ("relative workspace", "extra identity key", "overlong workspace"):
            with self.subTest(change=change):
                owner = copy.deepcopy(self.native.owner)
                if change == "relative workspace":
                    owner["expected_identity"]["workspace"] = "relative-studio"
                elif change == "extra identity key":
                    owner["expected_identity"]["instance"] = "not-an-api-field"
                else:
                    owner["expected_identity"]["workspace"] = "/" + "x" * 2048
                result = self.native.compile(2, owner=owner)
                self.assertFalse(result["ready"], "Compiler promised a ready plan rejected by its owner runner")
                self.assertIsNone(result["owner_run"])

    def test_compiler_does_not_emit_ready_for_prompt_nul_rejected_by_runner(self):
        owner = copy.deepcopy(self.native.owner)
        owner["characters"]["canon-a"]["description"] = "Synthetic\x00character"
        result = self.native.compile(2, owner=owner)
        self.assertFalse(result["ready"], "Compiler promised a ready plan with an invalid control string")
        self.assertIsNone(result["owner_run"])


if __name__ == "__main__":
    unittest.main()
