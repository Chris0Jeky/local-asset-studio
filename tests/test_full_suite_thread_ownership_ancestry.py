"""Adversarial ancestry contracts for cross-test thread ownership."""
from __future__ import annotations

from pathlib import Path
import queue
import sys
import threading
import unittest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from runtime_observability import (  # noqa: E402
    ThreadOwnershipObserver,
    current_thread_origin,
    set_current_test,
)


class ThreadOwnershipAncestryTests(unittest.TestCase):
    def tearDown(self):
        set_current_test("<between tests>")

    def test_child_of_preexisting_parent_remains_unobserved(self):
        commands: queue.Queue[str] = queue.Queue()
        origins: queue.Queue[dict | None] = queue.Queue()

        def parent_loop():
            while True:
                command = commands.get(timeout=5)
                if command == "stop":
                    return
                child = threading.Thread(
                    target=lambda: origins.put(current_thread_origin()),
                    name="preexisting-parent-child",
                    daemon=True,
                )
                child.start()
                child.join(timeout=5)
                if child.is_alive():
                    origins.put({"status": "test-timeout"})

        parent = threading.Thread(
            target=parent_loop,
            name="preexisting-parent",
            daemon=True,
        )
        parent.start()
        observer = ThreadOwnershipObserver()
        observer.install()
        try:
            set_current_test(
                "test_full_suite_thread_ownership_ancestry."
                "ThreadOwnershipAncestryTests.test_current"
            )
            commands.put("spawn")
            origin = origins.get(timeout=5)
        finally:
            observer.restore()
            commands.put("stop")
            parent.join(timeout=5)

        self.assertFalse(parent.is_alive())
        self.assertIsNotNone(origin)
        self.assertEqual(origin["status"], "unobserved")
        self.assertEqual(origin["reason"], "ancestor-started-before-observer")
        self.assertNotIn("owner_test", origin)
        self.assertEqual(origin["parent_thread"], "preexisting-parent")

    def test_child_of_capacity_skipped_parent_remains_unobserved_after_capacity_frees(self):
        holder_release = threading.Event()
        parent_spawn = threading.Event()
        origins: queue.Queue[dict | None] = queue.Queue()

        def hold_capacity():
            holder_release.wait(timeout=5)

        def skipped_parent():
            parent_spawn.wait(timeout=5)
            child = threading.Thread(
                target=lambda: origins.put(current_thread_origin()),
                name="capacity-skipped-child",
                daemon=True,
            )
            child.start()
            child.join(timeout=5)
            if child.is_alive():
                origins.put({"status": "test-timeout"})

        observer = ThreadOwnershipObserver(max_threads=1)
        observer.install()
        holder = threading.Thread(
            target=hold_capacity,
            name="ownership-capacity-holder",
            daemon=True,
        )
        parent = threading.Thread(
            target=skipped_parent,
            name="capacity-skipped-parent",
            daemon=True,
        )
        try:
            set_current_test(
                "test_full_suite_thread_ownership_ancestry."
                "ThreadOwnershipAncestryTests.test_original_owner"
            )
            holder.start()
            parent.start()

            holder_release.set()
            holder.join(timeout=5)
            self.assertFalse(holder.is_alive())

            set_current_test(
                "test_full_suite_thread_ownership_ancestry."
                "ThreadOwnershipAncestryTests.test_current"
            )
            parent_spawn.set()
            origin = origins.get(timeout=5)
            parent.join(timeout=5)
        finally:
            holder_release.set()
            parent_spawn.set()
            holder.join(timeout=5)
            parent.join(timeout=5)
            observer.restore()

        self.assertFalse(parent.is_alive())
        self.assertIsNotNone(origin)
        self.assertEqual(origin["status"], "unobserved")
        self.assertEqual(origin["reason"], "ancestor-observer-capacity")
        self.assertNotIn("owner_test", origin)
        self.assertEqual(origin["parent_thread"], "capacity-skipped-parent")


if __name__ == "__main__":
    unittest.main()
