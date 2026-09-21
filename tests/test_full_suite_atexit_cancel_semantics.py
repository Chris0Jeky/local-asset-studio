"""Cleanup contracts for observed ``atexit`` callback proxies."""
from __future__ import annotations

import atexit
import io
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from runtime_observability import AtexitCallbackObserver  # noqa: E402


class _ExplosiveEqualityCallback:
    def __init__(self):
        self.comparisons = 0

    def __call__(self):
        pass

    def __eq__(self, other):
        self.comparisons += 1
        raise RuntimeError("callback equality failed")


class AtexitCancelSemanticsTests(unittest.TestCase):
    def test_cancel_does_not_reflect_pre_observer_comparisons_into_callback_equality(self):
        original_register = atexit.register
        original_unregister = atexit.unregister
        pre_observer = lambda: None
        original_register(pre_observer)

        observer = AtexitCallbackObserver(stream=io.StringIO())
        callback = _ExplosiveEqualityCallback()
        observer.install()
        try:
            atexit.register(callback)
            with self.assertRaisesRegex(RuntimeError, "callback equality failed"):
                atexit.unregister(object())
            self.assertEqual(callback.comparisons, 1)
        finally:
            try:
                observer.restore(cancel=True)
            finally:
                original_unregister(pre_observer)

        self.assertEqual(callback.comparisons, 1)


if __name__ == "__main__":
    unittest.main()
