from __future__ import annotations

import copy
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

# Standalone runs (one test module) must not depend on another module having
# put app/ on the path first.
APP = str(Path(__file__).resolve().parents[1] / "app")
if APP not in sys.path:
    sys.path.insert(0, APP)

import resource_admission  # noqa: E402
from large_job_preparation import LargeJobPreparation, PreparationError  # noqa: E402

GIB = 1024 ** 3


def observation(*, ram=40 * GIB, commit=40 * GIB, vram=16 * GIB, version="1"):
    return {
        "schema": "studio.resource-observation/v1",
        "observed_at": 1,
        "physical_ram": {"available_bytes": ram, "unknown_reason": None if ram is not None else "missing"},
        "windows_commit": {"available_bytes": commit, "unknown_reason": None if commit is not None else "missing"},
        "vram": {"available_bytes": vram, "device_index": 0, "unknown_reason": None if vram is not None else "missing"},
        "runtime": {"versions": {"comfyui_version": version}, "devices": []},
    }


# Stored in the merged #178 config shape (``resource_admission_profiles``) and keyed by
# the exact workflow/runtime identity; ``resource_admission.profile_for`` validates it.
PROFILE = {
    "schema": resource_admission.PROFILE_SCHEMA,
    "basis": "observed",
    "source": {"receipt_sha256": "a" * 64, "kind": "job-resource-observation"},
    "stages": [
        {"name": "load", "physical_ram_bytes": 6 * GIB, "windows_commit_bytes": 18 * GIB, "vram_bytes": 12 * GIB},
        {"name": "decode", "physical_ram_bytes": 20 * GIB, "windows_commit_bytes": 35 * GIB, "vram_bytes": 8 * GIB},
    ],
}


class Process:
    def __init__(self, pid=40, created=100.0):
        self.pid = pid
        self.created = created
        self.terminated = False
        self.wait_error = None

    def create_time(self):
        return self.created

    def terminate(self):
        self.terminated = True

    def wait(self, timeout):
        if self.wait_error:
            raise self.wait_error


class Manager:
    def __init__(self):
        self.active = "primary"
        self.busy = False
        self.profiles = {"primary": {"id": "primary", "url": "http://127.0.0.1:8188"}}
        self.current = Process()
        self.configured = [self.current]
        self.queue = {"queue_running": [], "queue_pending": []}
        self.requests = []
        self.launches = 0
        self.launch_error = None
        self.system_ready = True
        self.on_queue = None

    def request(self, profile, route, timeout):
        self.requests.append((route, timeout))
        if route == "/queue":
            if self.on_queue:
                self.on_queue(self)
            return copy.deepcopy(self.queue)
        if route == "/system_stats":
            if not self.system_ready:
                raise OSError("not ready")
            return {"system": {"comfyui_version": "1"}, "devices": []}
        raise AssertionError(route)

    def process(self, profile):
        return self.current

    def configured_processes(self, profile):
        return list(self.configured)

    def launch_recovery(self, profile):
        self.launches += 1
        new = Process(90 + self.launches, 200.0 + self.launches)
        self.current = new
        self.configured = [new]
        if self.launch_error:
            error = self.launch_error
            self.launch_error = None
            raise error
        return new.pid


class Production:
    def __init__(self):
        self.items = []

    def list(self):
        return copy.deepcopy(self.items)


class ReferenceJobs:
    def __init__(self):
        self.active = False

    def busy(self):
        return self.active


class Studio:
    def __init__(self, root: Path, observations):
        self.root = root
        self._config = {
            "enable_large_job_resource_cleanup": True,
            "enable_idle_retained_commit_cleanup": False,
            "enable_large_job_backend_restart": False,
            "large_job_release_settle_seconds": 0,
            "large_job_restart_startup_timeout_seconds": 2,
            "large_job_restart_stop_timeout_seconds": 1,
        }
        self.backends = Manager()
        self.jobs = {}
        self.production = Production()
        self.reference_jobs = ReferenceJobs()
        self.lock = threading.RLock()
        self.observations = list(observations)
        self.profile = copy.deepcopy(PROFILE)
        self.profile_identity = None
        self.free_calls = []
        self.free_error = None
        self.prepare_calls = 0
        self.created_jobs = 0

    @staticmethod
    def _prepared(recipe):
        return {"id": recipe.get("preset_id", "demo")}, {"1": {"class_type": "Demo", "inputs": {"width": 1024}}}

    def exact_identity(self, version="1"):
        preset, graph = self._prepared({"preset_id": "demo"})
        runtime = observation(version=version)["runtime"]
        return resource_admission.workflow_identity(self, preset, graph, runtime)["identity_sha256"]

    @property
    def config(self):
        # Rebind on every read so a test can move the profile to another identity.
        key = self.profile_identity or self.exact_identity()
        document = dict(copy.deepcopy(self.profile), identity_sha256=key)
        self._config["resource_admission_profiles"] = {key: document}
        return self._config

    def prepare(self, recipe):
        self.prepare_calls += 1
        preset, graph = self._prepared(recipe)
        return preset, graph, Path("demo.json"), {}, 1

    def _request(self, route, **kwargs):
        if route != "/free":
            raise AssertionError(route)
        self.free_calls.append((route, copy.deepcopy(kwargs)))
        if self.free_error:
            raise self.free_error
        return None

    def _write_json_atomic(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
        temporary.replace(path)


class Clock:
    def __init__(self):
        self.value = 1000.0

    def time(self):
        self.value += 0.01
        return self.value

    def monotonic(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


class LargeJobPreparationTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.clock = Clock()

    def tearDown(self):
        self.tmp.cleanup()

    def controller(self, studio):
        return LargeJobPreparation(
            studio,
            observer=lambda value: value.observations.pop(0),
            sleeper=self.clock.sleep,
            monotonic=self.clock.monotonic,
            clock=self.clock.time,
        )

    @staticmethod
    def request(**changes):
        value = {
            "request_id": "prepare-1",
            "recipe": {"preset_id": "demo", "controls": {}},
            "dry_run": False,
            "allow_release": True,
            "allow_restart": False,
            "mode": "explicit",
        }
        value.update(changes)
        return value
