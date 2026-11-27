"""Owner-run integration checks against an inert loopback Studio fixture.

No real Studio, ComfyUI, uploads, model files, or image generation are used.
"""
from __future__ import annotations

import copy
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest

import owner_run


SCRIPT = Path(__file__).with_name("owner_run.py")
IDENTITY = {"app": "local-asset-studio", "workspace": r"C:\AI\local-asset-studio", "version": "production-workspace-1"}
UPLOAD = "1" * 32 + "_fixture.png"
UPLOAD_SHA = "f" * 64


def digest(value, *, ascii=False):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=ascii, allow_nan=False).encode()).hexdigest()


def plan_fixture(count=2):
    chunks = []
    for index in range(count):
        name = f"P35 {'a' * 16} route-{index + 1}"
        chunks.append({
            "id": f"route-{index + 1}", "name": name,
            "expected_inputs": [{"file": UPLOAD, "sha256": UPLOAD_SHA}],
            "expected_models": [{"file": "diffusion_models/fixture.safetensors", "sha256": "d" * 64, "bytes": 100}],
            "expected_graph_sha256": [digest({"1": {"class_type": "LoadImage", "inputs": {"image": UPLOAD}},
                 "2": {"class_type": "FixtureSampler", "inputs": {"seed": seed}}}, ascii=True) for seed in (101, 202)],
            "payload": {
                "name": name,
                "recipe": {"preset_id": "fixture-edit", "controls": {"positive": "An inert fixture", "last_reference": UPLOAD},
                           "references": [], "expected_template_sha256": "e" * 64},
                "variants": [{"label": f"seed-{seed}", "controls": {"seed": seed}} for seed in (101, 202)],
                "max_seconds": 60, "max_generations": 2,
            },
        })
    plan = {"schema": "p35-owner-run/v1", "campaign_id": "a" * 64, "backend_id": "primary",
            "expected_identity": copy.deepcopy(IDENTITY), "max_attempts": 12, "max_seconds": 180,
            "chunks": chunks}
    plan["plan_id"] = digest(plan)
    return plan


class FakeStudio:
    """Only the production routes the adapter is permitted to use exist."""
    def __init__(self):
        self.identity = copy.deepcopy(IDENTITY)
        self.backends = {
            "active": "primary", "busy": False, "operation": None, "last_launch_reserve": None,
            "state_issue": None, "shared_state": {"sha256": None, "blocker": None, "resolvable": False},
            "work_blocker": None,
            "profiles": [{"id": "primary", "name": "Primary", "url": "http://127.0.0.1:8188",
                          "root": r"C:\AI\ComfyUI", "description": "Inert test fixture",
                          "readiness": {"ready": True}, "installed": True, "online": True, "active": True}],
            "gpu_lease": {"held": False}, "recovery": {},
        }
        self.requests = []
        self.projects = {}
        self.jobs = {}
        self.create_loss = False
        self.start_loss = False
        self.redirect_identity = None
        self.bad_after_start = None
        self.failed_start_reply = False
        self.stop_requested = False
        self.missing_prompt_ids = False
        self.bad_job = None
        self.bad_inputs = False
        self.changed_graph = False
        self.bad_model = None
        self.pad_pruned_slot = False
        self.pruned_role = "pose"
        self.hold_create = False
        self.hold_start = False
        self.create_received = threading.Event()
        self.start_received = threading.Event()
        self.release_create = threading.Event()
        self.on_create = None
        self.guard = threading.Lock()
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def reply(self, status, value, headers=None):
                body = json.dumps(value).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                for key, value in (headers or {}).items():
                    self.send_header(key, value)
                self.end_headers()
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def lose_response(self):
                try:
                    self.connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                self.connection.close()

            def do_GET(self):
                with fake.guard:
                    fake.requests.append(("GET", self.path, None))
                    if self.path == "/api/identity":
                        if fake.redirect_identity:
                            return self.reply(302, {"error": "redirect fixture"}, {"Location": fake.redirect_identity})
                        return self.reply(200, fake.identity)
                    if self.path == "/api/backends":
                        return self.reply(200, fake.backends)
                    if self.path == "/api/production":
                        return self.reply(200, [fake.public(p, full=False) for p in fake.projects.values()])
                    if self.path.startswith("/api/production/"):
                        identifier = self.path.rsplit("/", 1)[-1]
                        project = fake.projects.get(identifier)
                        if project is None:
                            return self.reply(404, {"error": "Unknown experiment"})
                        if project["state"]["status"] == "queued":
                            fake.finish(project)
                        return self.reply(200, fake.public(project, full=True))
                    return self.reply(404, {"error": "Unsupported fixture route"})

            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                with fake.guard:
                    fake.requests.append(("POST", self.path, payload))
                    if self.path == "/api/production":
                        if fake.on_create:
                            fake.on_create()
                        project = fake.create(payload)
                        fake.create_received.set()
                        value = fake.public(project, full=False)
                        response_loss = fake.create_loss
                        hold = fake.hold_create
                    elif self.path.startswith("/api/production/") and self.path.endswith("/start"):
                        identifier = self.path.split("/")[3]
                        project = fake.projects.get(identifier)
                        if not project or project["state"]["status"] != "planned":
                            return self.reply(400, {"error": "Already started or missing"})
                        project["state"].update(status="queued", reserved=2)
                        project["budget"]["reserved"] = 2
                        value = fake.public(project, full=False)
                        if fake.failed_start_reply:
                            value["state"]["status"] = "failed"
                        response_loss = fake.start_loss
                        hold = fake.hold_start
                        fake.start_received.set()
                    else:
                        return self.reply(404, {"error": "Forbidden fixture mutation"})
                if hold:
                    fake.release_create.wait(8)
                if response_loss:
                    return self.lose_response()
                return self.reply(201 if self.path == "/api/production" else 202, value)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .02}, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def close(self):
        self.release_create.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(3)

    def create(self, payload):
        identifier = f"{len(self.projects) + 1:032x}"
        recipe = copy.deepcopy(payload["recipe"])
        recipe["batch_count"] = 1
        stages = []
        for index, variant in enumerate(payload["variants"]):
            request = copy.deepcopy(recipe)
            request["controls"].update(variant["controls"])
            request["references"] = [dict(reference, slot=slot + 1, bytes=123, width=16, height=16,
                                          transform={"policy": "Inert fixture reference preprocessing"})
                                     for slot, reference in enumerate(recipe["references"])]
            if self.pad_pruned_slot:
                request["references"].append({"slot": len(recipe["references"]) + 1, "role": self.pruned_role,
                                              "file": None, "pruned": True, "contribution": "", "avoid": ""})
            graph = {"1": {"class_type": "LoadImage", "inputs": {"image": UPLOAD}},
                     "2": {"class_type": "FixtureSampler", "inputs": {"seed": variant["controls"]["seed"]}}}
            if self.changed_graph:
                graph["1"]["inputs"]["image"] = "unbound.png"
            stages.append({"operation": "comfy.generate.v1", "label": chr(65 + index), "request": request,
                           "graph": graph, "graph_sha256": digest(graph, ascii=True)})
        models = [{"file": "diffusion_models/fixture.safetensors", "sha256": "d" * 64, "bytes": 100,
                   "path": r"C:\AI\ComfyUI\models\diffusion_models\fixture.safetensors", "mtime_ns": 1}]
        if self.bad_model == "hash":
            models[0]["sha256"] = "0" * 64
        elif self.bad_model == "bytes":
            models[0]["bytes"] = 101
        elif self.bad_model == "extra":
            models.append(dict(models[0], file="checkpoints/fixture.safetensors"))
        elif self.bad_model == "missing":
            models = []
        plan = {"version": 1, "kind": "comparison", "name": payload["name"], "recipe": recipe,
                "axis": "variants", "values": [v["label"] for v in payload["variants"]],
                "variants": [dict(v, rationale="", sources=[]) for v in payload["variants"]],
                "knowledge_sha256": "b" * 64, "parent_project": None, "max_seconds": payload["max_seconds"],
                "stages": stages, "bundle": {"comfy_root": r"C:\AI\ComfyUI", "comfy_url": "http://127.0.0.1:8188",
                "models": models, "inputs": [{"path": "C:\\AI\\ComfyUI\\input\\" + UPLOAD,
                    "sha256": "0" * 64 if self.bad_inputs else UPLOAD_SHA, "bytes": 123}],
                "schema_sha256": "c" * 64, "node_classes": ["LoadImage", "FixtureSampler"],
                "system": {}, "devices": [], "measured_at": 1.0, "terms_note": "Unknown fixture licence",
                "verification": "Inert fixture only"}, "repair_allowance": 0, "review": "unreviewed",
                "created_at": 1.0, "character_source": None}
        plan["sha256"] = digest(plan, ascii=True)
        project = {"id": identifier, "root_id": identifier, "plan": plan, "created_at": 1.0,
                   "budget": {"allowance": len(stages), "reserved": 0},
                   "state": {"status": "planned", "message": "No generation submitted", "attempts": {},
                             "artifacts": [], "stop_requested": False, "review": {"status": "unreviewed", "notes": ""}}}
        self.projects[identifier] = project
        return project

    def finish(self, project):
        if self.bad_after_start:
            project["state"]["status"] = self.bad_after_start
            return
        for index in range(len(project["plan"]["stages"])):
            job_id = f"fixture-job-{project['id']}-{index}"
            prompt_id = f"fixture-prompt-{project['id']}-{index}"
            attempt = {"status": "completed", "job_id": job_id, "prompt_ids": [prompt_id],
                       "operation": "comfy.generate.v1", "started_at": 2.0, "finished_at": 3.0}
            project["state"]["attempts"][str(index)] = attempt
            self.jobs[job_id] = {"id": job_id, "status": "completed", "prompt_ids": [] if self.missing_prompt_ids else [prompt_id],
                                 "submissions": [], "outputs": [], "batch_count": 1, "project_id": project["id"]}
            if self.bad_job == "ownership":
                self.jobs[job_id]["project_id"] = "0" * 32
            elif self.bad_job == "batch":
                self.jobs[job_id]["batch_count"] = 2
            elif self.bad_job == "prompt":
                self.jobs[job_id]["prompt_ids"] = [prompt_id + "-different"]
        project["state"].update(status="awaiting_review", message="Inert comparison finished", finished_at=3.0,
                                stop_requested=self.stop_requested)

    def public(self, project, full=False):
        plan = project["plan"]
        result = {key: copy.deepcopy(project[key]) for key in ("id", "root_id", "created_at", "budget", "state")}
        result.update(name=plan["name"], kind="comparison", parent_project=None, plan_sha256=plan["sha256"],
                      recipe=copy.deepcopy(plan["recipe"]), axis="variants", values=plan["values"], variants=plan["variants"],
                      knowledge_sha256=plan["knowledge_sha256"], combine=None, export_kind=None,
                      can_reconcile_tracking=False, can_reconcile_batch=False, put_away=False,
                      put_away_at=None, can_put_away=True, can_bring_back=False)
        result["stages"] = []
        for index, stage in enumerate(plan["stages"]):
            attempt = project["state"]["attempts"].get(str(index), {})
            result["stages"].append({"label": stage["label"], "operation": stage["operation"], "attempt": copy.deepcopy(attempt),
                                     "job": copy.deepcopy(self.jobs.get(attempt.get("job_id")))})
        if full:
            result["plan"] = copy.deepcopy(plan)
        return result


class OwnerRunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.runtime = self.root / ".runtime"
        self.plan = plan_fixture()
        self.path = self.root / "plan.json"
        self.write_plan()
        self.fake = FakeStudio()

    def tearDown(self):
        self.fake.close()
        self.temp.cleanup()

    def write_plan(self):
        self.plan.pop("plan_id", None)
        self.plan["plan_id"] = digest(self.plan)
        self.path.write_text(json.dumps(self.plan, ensure_ascii=False), encoding="utf-8")

    def command(self, mode):
        return [sys.executable, str(SCRIPT), "--plan", str(self.path), mode,
                "--runtime", str(self.runtime), "--base-url", self.fake.url,
                "--poll-interval", "0.01", "--request-timeout", "2"]

    def invoke(self, mode, ok=True, env=None):
        result = subprocess.run(self.command(mode), text=True, capture_output=True, timeout=15, env=env)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        else:
            self.assertNotEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(result.stdout.strip().startswith("{"), result.stderr + result.stdout)
        return json.loads(result.stdout)

    def journal_path(self):
        return self.runtime / "p35-owner-runs" / self.plan["plan_id"] / "journal.json"

    def journal(self):
        return json.loads(self.journal_path().read_text())

    def posts(self):
        return [(path, body) for method, path, body in self.fake.requests if method == "POST"]

    def test_prepare_creates_planned_projects_without_start_and_preserves_receipts(self):
        summary = self.invoke("--prepare")
        self.assertEqual(summary["state"], "prepared")
        self.assertEqual([path for path, _ in self.posts()], ["/api/production", "/api/production"])
        journal = self.journal()
        self.assertEqual([c["classification"]["execution"] for c in journal["chunks"]], ["planned", "planned"])
        self.assertTrue(all(c["classification"]["visual"] == "unreviewed" for c in journal["chunks"]))
        self.assertTrue(all(c["classification"]["licence"] == "unknown" for c in journal["chunks"]))
        self.assertTrue(list(self.journal_path().parent.glob("evidence/*.body")))
        self.assertFalse(self.journal_path().with_name("run.lock").exists())

    def test_start_uses_studio_sequentially_and_rerun_never_submits_again(self):
        summary = self.invoke("--start")
        self.assertEqual(summary["state"], "completed")
        self.assertEqual(len([p for p, _ in self.posts() if p.endswith("/start")]), 2)
        self.assertEqual(len([p for p, _ in self.posts() if p == "/api/production"]), 2)
        events = [(method, path) for method, path, _ in self.fake.requests]
        first = "/api/production/" + "1".zfill(32)
        second = "/api/production/" + "2".zfill(32)
        self.assertLess(events.index(("POST", first + "/start")), events.index(("POST", second + "/start")))
        self.assertIn(("GET", first), events[events.index(("POST", first + "/start")) + 1:events.index(("POST", second + "/start"))])
        before = len(self.posts())
        self.invoke("--start")
        self.assertEqual(len(self.posts()), before)
        self.assertEqual(len(self.journal()["chunks"][0]["prompt_ids"]), 2)
        self.assertTrue(all(c["classification"]["visual"] == "unreviewed" for c in self.journal()["chunks"]))

    def test_prepare_then_start_records_durable_intent_before_wire_request(self):
        observed = []
        self.fake.on_create = lambda: observed.append(self.journal()["effects"][-1]["phase"])
        self.invoke("--prepare")
        self.assertEqual(observed, ["intent", "intent"])
        self.invoke("--start")
        self.assertEqual(len([p for p, _ in self.posts() if p == "/api/production"]), 2)

    def test_status_only_gets_and_leaves_journal_byte_for_byte_unchanged(self):
        self.invoke("--prepare")
        before_bytes = self.journal_path().read_bytes()
        before_requests = len(self.fake.requests)
        summary = self.invoke("--status")
        self.assertEqual(summary["state"], "prepared")
        self.assertEqual(self.journal_path().read_bytes(), before_bytes)
        self.assertTrue(all(method == "GET" for method, _, _ in self.fake.requests[before_requests:]))

    def test_lost_create_response_never_replays_and_status_only_reconciles_candidates(self):
        self.fake.create_loss = True
        summary = self.invoke("--prepare", ok=False)
        self.assertEqual(summary["state"], "uncertain")
        self.assertEqual(len(self.posts()), 1)
        self.assertIsNone(self.journal()["chunks"][0].get("project_id"))
        self.invoke("--start", ok=False)
        before = self.journal_path().read_bytes()
        status = self.invoke("--status")
        self.assertEqual(len(status["chunks"][0]["reconciliation_candidates"]), 1)
        self.assertEqual(self.journal_path().read_bytes(), before)
        self.assertEqual(len(self.posts()), 1)
        self.assertTrue(self.journal_path().with_name("run.lock").exists())

    def test_lost_start_response_preserves_project_and_never_replays_or_starts_later_chunk(self):
        self.invoke("--prepare")
        self.fake.start_loss = True
        summary = self.invoke("--start", ok=False)
        self.assertEqual(summary["state"], "uncertain")
        self.assertEqual(len([p for p, _ in self.posts() if p.endswith("/start")]), 1)
        self.assertEqual(self.journal()["chunks"][0]["project_id"], "1".zfill(32))
        self.invoke("--start", ok=False)
        before = len(self.posts())
        status = self.invoke("--status")
        self.assertEqual(len(self.posts()), before)
        self.assertEqual(status["chunks"][0]["observed_execution"], "completed")
        self.assertEqual(self.journal()["state"], "uncertain")

    def test_prepared_input_hash_mismatch_prevents_any_start(self):
        self.fake.bad_inputs = True
        summary = self.invoke("--start", ok=False)
        self.assertIn("input", summary["error"].lower())
        self.assertEqual([p for p, _ in self.posts()], ["/api/production"])

    def test_model_hash_size_extra_and_missing_records_are_refused_before_start(self):
        for change in ("hash", "bytes", "extra", "missing"):
            with self.subTest(change=change):
                self.runtime = self.root / change / ".runtime"
                self.plan["campaign_id"] = hashlib.sha256(change.encode()).hexdigest()
                for chunk in self.plan["chunks"]:
                    chunk["name"] = chunk["payload"]["name"] = f"P35 {self.plan['campaign_id'][:16]} {chunk['id']}"
                self.write_plan()
                self.fake.bad_model = change
                before = len(self.posts())
                summary = self.invoke("--start", ok=False)
                self.assertIn("model", summary["error"].lower())
                self.assertEqual([p for p, _ in self.posts()[before:]], ["/api/production"])

    def test_self_consistent_changed_graph_is_refused_before_start(self):
        self.fake.changed_graph = True
        summary = self.invoke("--start", ok=False)
        self.assertIn("graph", summary["error"].lower())
        self.assertEqual([p for p, _ in self.posts()], ["/api/production"])

    def test_only_declared_native_trailing_empty_board_slot_is_accepted(self):
        for chunk in self.plan["chunks"]:
            chunk["payload"]["recipe"]["references"] = [{"file": UPLOAD, "sha256": UPLOAD_SHA, "role": "pose"}]
            chunk["expected_pruned_reference_slots"] = [{"slot": 2, "role": "pose"}]
        self.write_plan()
        self.fake.pad_pruned_slot = True
        summary = self.invoke("--start")
        self.assertEqual(summary["state"], "completed")

    def test_changed_native_pruned_role_is_refused_before_start(self):
        for chunk in self.plan["chunks"]:
            chunk["payload"]["recipe"]["references"] = [{"file": UPLOAD, "sha256": UPLOAD_SHA, "role": "pose"}]
            chunk["expected_pruned_reference_slots"] = [{"slot": 2, "role": "pose"}]
        self.write_plan()
        self.fake.pad_pruned_slot = True
        self.fake.pruned_role = "style"
        self.invoke("--start", ok=False)
        self.assertEqual([p for p, _ in self.posts()], ["/api/production"])

    def test_wrong_backend_and_identity_are_refused_before_any_post(self):
        for kind in ("backend", "identity"):
            with self.subTest(kind=kind):
                self.runtime = self.root / kind / ".runtime"
                self.fake.backends["active"] = "other" if kind == "backend" else "primary"
                self.fake.identity["workspace"] = "wrong" if kind == "identity" else IDENTITY["workspace"]
                self.invoke("--prepare", ok=False)
                self.assertEqual(self.posts(), [])

    def test_unknown_and_failed_states_stop_before_later_start(self):
        for state in ("mystery", "failed", "cancelled", "uncertain", "stopped", "interrupted"):
            with self.subTest(state=state):
                self.runtime = self.root / state / ".runtime"
                self.plan["campaign_id"] = hashlib.sha256(state.encode()).hexdigest()
                for chunk in self.plan["chunks"]:
                    chunk["name"] = chunk["payload"]["name"] = f"P35 {self.plan['campaign_id'][:16]} {chunk['id']}"
                self.write_plan()
                self.fake.bad_after_start = state
                before = len([p for p, _ in self.posts() if p.endswith("/start")])
                self.invoke("--start", ok=False)
                self.assertEqual(len([p for p, _ in self.posts() if p.endswith("/start")]), before + 1)

    def test_redirect_is_not_followed_even_to_another_loopback_server(self):
        other = FakeStudio()
        try:
            self.fake.redirect_identity = other.url + "/api/identity"
            summary = self.invoke("--prepare", ok=False)
            self.assertIn("redirect", summary["error"].lower())
            self.assertEqual(other.requests, [])
            self.assertEqual(self.posts(), [])
        finally:
            other.close()

    def test_non_loopback_or_ambiguous_urls_fail_before_network(self):
        for url in ("http://192.0.2.1:8191", "http://localhost:8191", "http://127.0.0.1:8191/x", "http://127.0.0.1:8191?x=1",
                    "https://127.0.0.1:8191", "http://user@127.0.0.1:8191", "http://127.0.0.1", "http://127.1:8191"):
            with self.subTest(url=url):
                old = self.fake.url
                self.fake.url = url
                try:
                    self.invoke("--prepare", ok=False)
                finally:
                    self.fake.url = old
                self.assertEqual(self.fake.requests, [])

    def test_proxy_environment_is_ignored(self):
        env = dict(os.environ, HTTP_PROXY="http://192.0.2.1:9", HTTPS_PROXY="http://192.0.2.1:9",
                   ALL_PROXY="http://192.0.2.1:9", http_proxy="http://192.0.2.1:9", no_proxy="", NO_PROXY="")
        self.invoke("--prepare", env=env)
        self.assertEqual(len(self.posts()), 2)

    def test_existing_same_name_never_adopts_or_creates_again(self):
        self.fake.create(self.plan["chunks"][0]["payload"])
        summary = self.invoke("--start", ok=False)
        self.assertIn("existing", summary["error"].lower())
        self.assertEqual(self.posts(), [])

    def test_concurrent_launch_has_one_create_and_loser_cannot_remove_lock(self):
        self.fake.hold_create = True
        process = subprocess.Popen(self.command("--prepare"), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            self.assertTrue(self.fake.create_received.wait(5), "Runner never reached create")
            self.invoke("--prepare", ok=False)
            self.assertTrue(self.journal_path().with_name("run.lock").exists())
            self.assertEqual(len(self.posts()), 1)
            self.fake.release_create.set()
            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, stdout + stderr)
            self.assertEqual(len(self.posts()), 2)
        finally:
            self.fake.release_create.set()
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)

    def test_later_lock_winner_reloads_completed_journal_and_preserves_start_intents(self):
        self.invoke("--prepare")
        contender = owner_run.Runner(copy.deepcopy(self.plan), self.runtime, self.fake.url, 2, .01)
        original_acquire = contender.store.acquire

        def earlier_owner_finishes_before_this_lock_is_acquired(plan_id):
            self.invoke("--start")
            original_acquire(plan_id)

        contender.store.acquire = earlier_owner_finishes_before_this_lock_is_acquired
        problem = None
        try:
            result = contender.execute("start")
        except owner_run.RunError as exc:
            problem = exc
        self.assertIsNone(problem, "Contender used a stale pre-lock journal: " + str(problem))
        self.assertEqual(result["state"], "completed")
        self.assertEqual(self.journal()["state"], "completed")
        self.assertEqual(self.journal()["attempts_reserved"], 4)
        self.assertEqual([effect["kind"] for effect in self.journal()["effects"]], ["create", "create", "start", "start"])
        self.assertEqual(len(self.journal()["chunks"][0]["prompt_ids"]), 2)
        self.assertEqual(len([path for path, _ in self.posts() if path.endswith("/start")]), 2)

    def test_killed_runner_keeps_lock_and_intent_and_only_status_can_reconcile(self):
        self.fake.hold_create = True
        process = subprocess.Popen(self.command("--prepare"), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            self.assertTrue(self.fake.create_received.wait(5), "Runner never reached create")
            process.kill()
            process.communicate(timeout=5)
            self.fake.release_create.set()
            self.assertEqual(self.journal()["effects"][-1]["phase"], "intent")
            self.invoke("--start", ok=False)
            self.invoke("--status")
            self.assertEqual(len(self.posts()), 1)
            self.assertTrue(self.journal_path().with_name("run.lock").exists())
        finally:
            self.fake.release_create.set()
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)

    def test_changed_plan_hash_attempt_cap_and_unpinned_refs_refuse_before_network(self):
        original = copy.deepcopy(self.plan)
        mutations = (
            ("stale hash", lambda p: p.update(max_attempts=13), False),
            ("attempt cap", lambda p: p.update(max_attempts=241), True),
            ("insufficient cap", lambda p: p.update(max_attempts=3), True),
            ("missing input", lambda p: p["chunks"][0].update(expected_inputs=[]), True),
            ("unhashed input", lambda p: p["chunks"][0]["expected_inputs"][0].pop("sha256"), True),
            ("unbounded generations", lambda p: p["chunks"][0]["payload"].update(max_generations=16), True),
            ("unsupported side effect", lambda p: p["chunks"][0]["payload"].update(parent_project="f" * 32), True),
        )
        for label, mutate, rehash in mutations:
            with self.subTest(label=label):
                self.plan = copy.deepcopy(original)
                mutate(self.plan)
                if rehash:
                    self.write_plan()
                else:
                    self.path.write_text(json.dumps(self.plan))
                self.invoke("--prepare", ok=False)
                self.assertEqual(self.fake.requests, [])

    def test_json_duplicate_keys_and_oversized_input_are_rejected_before_network(self):
        for content in ('{"schema":"p35-owner-run/v1","schema":"other"}', " " * (2 * 1024 * 1024 + 1)):
            self.path.write_text(content)
            self.invoke("--prepare", ok=False)
            self.assertEqual(self.fake.requests, [])

    def test_owner_stop_request_prevents_starting_later_chunk_even_after_completed_last_stage(self):
        self.fake.stop_requested = True
        self.invoke("--start", ok=False)
        self.assertEqual(len([path for path, _ in self.posts() if path.endswith("/start")]), 1)

    def test_failed_start_reply_stops_even_if_later_get_would_claim_completion(self):
        self.fake.failed_start_reply = True
        self.invoke("--start", ok=False)
        self.assertEqual(len([path for path, _ in self.posts() if path.endswith("/start")]), 1)

    def test_time_cap_prevents_later_chunk_and_cannot_reset_on_rerun(self):
        self.plan["max_seconds"] = 60
        self.write_plan()
        summary = self.invoke("--start", ok=False)
        self.assertIn("time", summary["error"].lower())
        self.assertEqual(len([path for path, _ in self.posts() if path.endswith("/start")]), 1)
        self.invoke("--start", ok=False)
        self.assertEqual(len([path for path, _ in self.posts() if path.endswith("/start")]), 1)

    def test_completion_without_prompt_receipts_is_not_accepted(self):
        self.fake.missing_prompt_ids = True
        self.invoke("--start", ok=False)
        self.assertEqual(len([path for path, _ in self.posts() if path.endswith("/start")]), 1)

    def test_wrong_job_ownership_batch_or_prompt_receipt_stops_later_chunks(self):
        for change in ("ownership", "batch", "prompt"):
            with self.subTest(change=change):
                self.runtime = self.root / change / ".runtime"
                self.plan["campaign_id"] = hashlib.sha256(change.encode()).hexdigest()
                for chunk in self.plan["chunks"]:
                    chunk["name"] = chunk["payload"]["name"] = f"P35 {self.plan['campaign_id'][:16]} {chunk['id']}"
                self.write_plan()
                self.fake.bad_job = change
                before = len([path for path, _ in self.posts() if path.endswith("/start")])
                self.invoke("--start", ok=False)
                self.assertEqual(len([path for path, _ in self.posts() if path.endswith("/start")]), before + 1)

    def test_start_timeout_is_uncertain_and_cannot_be_replayed(self):
        self.invoke("--prepare")
        self.fake.hold_start = True
        command = self.command("--start")
        command[-1] = "0.05"
        result = subprocess.run(command, text=True, capture_output=True, timeout=5)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["state"], "uncertain")
        self.fake.release_create.set()
        self.invoke("--start", ok=False)
        self.invoke("--status")
        self.assertEqual(len([path for path, _ in self.posts() if path.endswith("/start")]), 1)

    def test_create_has_separate_bounded_timeout_recorded_before_post(self):
        self.fake.hold_create = True
        observed_timeouts = []
        self.fake.on_create = lambda: observed_timeouts.append(self.journal()["effects"][-1]["request_timeout_seconds"])
        timer = threading.Timer(.5, self.fake.release_create.set)
        timer.start()
        try:
            command = self.command("--prepare")
            command[-1] = "0.05"  # Ordinary GET/start timeout must not cap model-hashing preparation.
            command.extend(["--prepare-timeout", "1"])
            result = subprocess.run(command, text=True, capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)["state"], "prepared")
            self.assertEqual(observed_timeouts, [1, 1])
            self.assertEqual(self.journal()["prepare_timeout_seconds"], 1)
            self.assertIsNone(self.journal()["run_started_at"])
            self.assertEqual(self.journal()["attempts_reserved"], 0)
        finally:
            self.fake.release_create.set()
            timer.cancel()
            timer.join()

    def test_create_prepare_timeout_still_leaves_uncertainty_without_retry(self):
        self.fake.hold_create = True
        command = self.command("--prepare") + ["--prepare-timeout", "0.05"]
        result = subprocess.run(command, text=True, capture_output=True, timeout=5)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(result.stdout.startswith("{"), result.stderr)
        self.assertEqual(json.loads(result.stdout)["state"], "uncertain")
        self.assertEqual(self.journal()["effects"][-1]["request_timeout_seconds"], .05)
        self.assertIsNone(self.journal()["run_started_at"])
        self.fake.release_create.set()
        self.invoke("--start", ok=False)
        self.invoke("--status")
        self.assertEqual(len(self.posts()), 1)

    def test_prepare_timeout_outside_bounds_is_rejected_before_network(self):
        for value in ("0", "1801", "nan", "inf"):
            with self.subTest(value=value):
                result = subprocess.run(self.command("--prepare") + ["--prepare-timeout", value],
                                        text=True, capture_output=True, timeout=5)
                self.assertNotEqual(result.returncode, 0)
                self.assertTrue(result.stdout.startswith("{"), result.stderr)
                self.assertFalse(json.loads(result.stdout)["ok"])
                self.assertEqual(self.fake.requests, [])

    @unittest.skipIf(os.name == "nt", "SIGINT delivery fixture is POSIX-only; Windows Ctrl+C remains unverified")
    def test_keyboard_interrupt_during_start_preserves_uncertain_intent(self):
        self.invoke("--prepare")
        self.fake.hold_start = True
        process = subprocess.Popen(self.command("--start"), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            self.assertTrue(self.fake.start_received.wait(5))
            process.send_signal(signal.SIGINT)
            stdout, stderr = process.communicate(timeout=5)
            self.assertEqual(process.returncode, 130, stdout + stderr)
            self.assertEqual(self.journal()["effects"][-1]["phase"], "uncertain")
            self.assertTrue(self.journal_path().with_name("run.lock").exists())
            self.invoke("--start", ok=False)
            self.assertEqual(len([path for path, _ in self.posts() if path.endswith("/start")]), 1)
        finally:
            self.fake.release_create.set()
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)


if __name__ == "__main__":
    unittest.main()
