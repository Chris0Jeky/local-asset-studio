"""studio.jobs snapshot tests: readers must tolerate a concurrent insert.

Deterministic, no threads: the iteration itself mutates studio.jobs through a
job dict whose .get() inserts a new key the first time it is called, which
raises RuntimeError on a live dict view but not on a list() snapshot.
"""
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "app"))
from backends import BackendManager
from runtime_recovery import RuntimeRecovery


class MutatingJob(dict):
    """A job record that inserts an inert job into studio.jobs on first .get()."""

    def __init__(self, jobs, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._jobs = jobs
        self._mutated = False

    def get(self, key, default=None):
        if not self._mutated:
            self._mutated = True
            self._jobs["injected"] = {"status": "done"}
        return super().get(key, default)


class FixtureStudio:
    def __init__(self, root, **config):
        self.root = root
        self.comfy_root = root / "comfy"
        self.jobs = {}
        self.lock = threading.Lock()
        self.config = {"comfy_root": str(self.comfy_root), "python": str(root / "python.exe"),
                       "hidream_root": str(root / "isolated/ComfyUI"),
                       "qwen21_root": str(root / "qwen21/ComfyUI"), **config}
        self.production = SimpleNamespace(list=lambda: [])

    def _write_json_atomic(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data))
        temporary.replace(path)


class RecoveryStudio:
    def __init__(self, root):
        self.root = root
        self.config = {"runtime_auto_recover": False, "runtime_recovery_autostart": False}
        self.jobs = {}
        self.production = SimpleNamespace(list=lambda: [])
        self.lock = threading.RLock()

    def _write_json_atomic(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")


class JobsSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_local_work_survives_insert_during_iteration(self):
        studio = FixtureStudio(self.root)
        manager = BackendManager(studio)
        studio.jobs = {"a": {"status": "done"}}
        expected = manager._local_work()
        self.assertFalse(expected)
        studio.jobs = {}
        studio.jobs["a"] = MutatingJob(studio.jobs, {"status": "done"})
        self.assertEqual(manager._local_work(), expected)

    def test_stopped_results_survives_insert_during_iteration(self):
        studio = FixtureStudio(self.root)
        manager = BackendManager(studio)
        stopped = {"id": "aaaa1111", "status": "uncertain", "prompt_ids": [],
                   "tracking_disposition": {"status": "stopped", "reason": "r"}}
        studio.jobs = {"a": dict(stopped)}
        with patch.object(manager, "process", return_value=None):
            expected = manager._stopped_results()
        self.assertIsNone(expected)
        studio.jobs = {}
        studio.jobs["a"] = MutatingJob(studio.jobs, stopped)
        with patch.object(manager, "process", return_value=None):
            self.assertEqual(manager._stopped_results(), expected)

    def test_fresh_work_survives_insert_during_iteration(self):
        studio = RecoveryStudio(self.root)
        monitor = RuntimeRecovery(studio)
        studio.jobs = {"a": {"status": "done"}}
        expected = monitor._fresh_work()
        self.assertFalse(expected)
        studio.jobs = {}
        studio.jobs["a"] = MutatingJob(studio.jobs, {"status": "done"})
        self.assertEqual(monitor._fresh_work(), expected)


if __name__ == "__main__":
    unittest.main()
