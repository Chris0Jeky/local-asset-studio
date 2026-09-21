"""LIFO nesting contracts for thread ownership observation."""
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


class ThreadOwnershipNestingTests(unittest.TestCase):
    def tearDown(self):
        set_current_test("<between tests>")

    @staticmethod
    def _capture_origin(name: str) -> dict | None:
        origins: queue.Queue[dict | None] = queue.Queue()
        thread = threading.Thread(
            target=lambda: origins.put(current_thread_origin()),
            name=name,
            daemon=True,
        )
        thread.start()
        thread.join(timeout=5)
        if thread.is_alive():
            raise AssertionError(f"{name} did not terminate")
        return origins.get(timeout=5)

    def test_inner_restore_reactivates_outer_observer(self):
        outer = ThreadOwnershipObserver()
        inner = ThreadOwnershipObserver()
        outer.install()
        try:
            set_current_test("thread_ownership.outer_owner")
            inner.install()
            try:
                set_current_test("thread_ownership.inner_owner")
                inner_origin = self._capture_origin("inner-owned-thread")
            finally:
                inner.restore()

            set_current_test("thread_ownership.outer_after_restore")
            outer_origin = self._capture_origin("outer-owned-thread")
        finally:
            if inner._installed:
                inner.restore()
            outer.restore()

        self.assertEqual(inner_origin["status"], "observed")
        self.assertEqual(inner_origin["owner_test"], "thread_ownership.inner_owner")
        self.assertEqual(outer_origin["status"], "observed")
        self.assertEqual(
            outer_origin["owner_test"],
            "thread_ownership.outer_after_restore",
        )


if __name__ == "__main__":
    unittest.main()
