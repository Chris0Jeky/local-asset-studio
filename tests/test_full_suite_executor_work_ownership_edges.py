"""Adversarial contracts for pooled-work ownership observation."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import queue
import sys
import threading
import unittest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from executor_work_observability import (  # noqa: E402
    ExecutorWorkObserver,
    current_work_origin,
)
from runtime_observability import (  # noqa: E402
    ThreadOwnershipObserver,
    current_thread_origin,
    set_current_test,
)


class ExecutorWorkOwnershipEdgeTests(unittest.TestCase):
    def setUp(self):
        set_current_test(self.id())

    def tearDown(self):
        set_current_test("<between tests>")

    def test_cancelled_queued_work_releases_observation_capacity(self):
        observer = ExecutorWorkObserver(max_tasks=2)
        observer.install()
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="capacity-pool")
        started = threading.Event()
        release = threading.Event()

        def blocking():
            started.set()
            release.wait(5)

        first = executor.submit(blocking)
        self.assertTrue(started.wait(5))
        second = executor.submit(lambda: None)
        try:
            self.assertTrue(second.cancel())
            third = executor.submit(current_work_origin)
            release.set()
            first.result(timeout=5)
            origin = third.result(timeout=5)
        finally:
            release.set()
            executor.shutdown(wait=True, cancel_futures=True)
            observer.restore()

        self.assertEqual(origin["status"], "observed")
        self.assertEqual(origin["owner_test"], self.id())

    def test_submitter_thread_origin_owns_work_during_a_later_test(self):
        thread_observer = ThreadOwnershipObserver()
        work_observer = ExecutorWorkObserver()
        thread_observer.install()
        work_observer.install()
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="submitter-pool")
        ready = threading.Event()
        submit = threading.Event()
        futures = queue.Queue()

        owner = "fixture.Owner.test_01_start_submitter"
        victim = "fixture.Victim.test_02_observe_work"
        set_current_test(owner)

        def submitter():
            ready.set()
            submit.wait(5)
            futures.put(executor.submit(current_work_origin))

        thread = threading.Thread(target=submitter, name="retained-submitter", daemon=True)
        thread.start()
        self.assertTrue(ready.wait(5))
        set_current_test(victim)
        submit.set()
        try:
            future = futures.get(timeout=5)
            origin = future.result(timeout=5)
        finally:
            submit.set()
            thread.join(timeout=5)
            executor.shutdown(wait=True, cancel_futures=True)
            work_observer.restore()
            thread_observer.restore()

        self.assertFalse(thread.is_alive())
        self.assertEqual(origin["status"], "observed")
        self.assertEqual(origin["owner_test"], owner)
        self.assertEqual(origin["submitted_during_test"], victim)
        self.assertEqual(origin["ownership_source"], "thread-origin")
        self.assertEqual(origin["submitter_thread"], "retained-submitter")

    def test_thread_started_inside_reused_work_inherits_work_owner(self):
        thread_observer = ThreadOwnershipObserver(
            work_origin_provider=current_work_origin,
        )
        work_observer = ExecutorWorkObserver()
        thread_observer.install()
        work_observer.install()
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="handoff-pool")
        origins = queue.Queue()

        creator = "fixture.Creator.test_01_prime_pool"
        submitter = "fixture.Submitter.test_02_start_child"
        set_current_test(creator)
        executor.submit(lambda: None).result(timeout=5)
        set_current_test(submitter)

        def start_child():
            child = threading.Thread(
                target=lambda: origins.put(current_thread_origin()),
                name="work-owned-child",
                daemon=True,
            )
            child.start()
            child.join(timeout=5)
            self.assertFalse(child.is_alive())

        try:
            executor.submit(start_child).result(timeout=5)
            origin = origins.get(timeout=5)
        finally:
            executor.shutdown(wait=True, cancel_futures=True)
            work_observer.restore()
            thread_observer.restore()

        self.assertEqual(origin["status"], "observed")
        self.assertEqual(origin["owner_test"], submitter)
        self.assertEqual(origin["started_during_test"], submitter)
        self.assertEqual(origin["ownership_source"], "parent-work")
        self.assertTrue(origin["parent_thread"].startswith("handoff-pool"))

    def test_nested_observers_restore_outer_submit_hook_in_lifo_order(self):
        outer = ExecutorWorkObserver()
        inner = ExecutorWorkObserver()
        outer.install()
        inner.install()
        try:
            with self.assertRaisesRegex(RuntimeError, "LIFO"):
                outer.restore()
            inner.restore()
            with ThreadPoolExecutor(max_workers=1) as executor:
                origin = executor.submit(current_work_origin).result(timeout=5)
            self.assertEqual(origin["status"], "observed")
            self.assertEqual(origin["owner_test"], self.id())
        finally:
            if inner._installed:
                inner.restore()
            outer.restore()

    def test_work_origin_excludes_task_arguments(self):
        observer = ExecutorWorkObserver()
        observer.install()
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                origin = executor.submit(
                    lambda _secret: current_work_origin(),
                    "do-not-retain-this-argument",
                ).result(timeout=5)
        finally:
            observer.restore()

        encoded = json.dumps(origin, sort_keys=True)
        self.assertNotIn("do-not-retain-this-argument", encoded)
        self.assertIn("callable", origin)


if __name__ == "__main__":
    unittest.main()
