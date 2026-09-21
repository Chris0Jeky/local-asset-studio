"""Contracts matching CPython's ordered ``atexit.unregister`` semantics."""
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


class _Query:
    pass


class _MatchingCallback:
    def __init__(self):
        self.comparisons = 0

    def __call__(self):
        pass

    def __eq__(self, other):
        if isinstance(other, _Query):
            self.comparisons += 1
            return True
        return False


class _ExplosiveCallback:
    def __init__(self):
        self.comparisons = 0

    def __call__(self):
        pass

    def __eq__(self, other):
        if isinstance(other, _Query):
            self.comparisons += 1
            raise RuntimeError("callback equality failed")
        return False


class AtexitUnregisterSemanticsTests(unittest.TestCase):
    def test_matches_removed_before_a_later_comparison_error_stay_removed(self):
        observer = AtexitCallbackObserver(stream=io.StringIO())
        matching = _MatchingCallback()
        explosive = _ExplosiveCallback()
        observer.install()
        try:
            atexit.register(matching)
            atexit.register(explosive)

            with self.assertRaisesRegex(RuntimeError, "callback equality failed"):
                atexit.unregister(_Query())
            self.assertEqual(matching.comparisons, 1)
            self.assertEqual(explosive.comparisons, 1)

            with self.assertRaisesRegex(RuntimeError, "callback equality failed"):
                atexit.unregister(_Query())
            self.assertEqual(matching.comparisons, 1)
            self.assertEqual(explosive.comparisons, 2)
        finally:
            observer.restore(cancel=True)

    def test_pre_observer_callbacks_keep_native_comparison_order(self):
        original_register = atexit.register
        original_unregister = atexit.unregister
        pre_observer = _ExplosiveCallback()
        original_register(pre_observer)

        observer = AtexitCallbackObserver(stream=io.StringIO())
        observed = _MatchingCallback()
        observer.install()
        try:
            atexit.register(observed)

            with self.assertRaisesRegex(RuntimeError, "callback equality failed"):
                atexit.unregister(_Query())
            self.assertEqual(pre_observer.comparisons, 1)
            self.assertEqual(observed.comparisons, 0)
        finally:
            observer.restore(cancel=True)
            original_unregister(pre_observer)


if __name__ == "__main__":
    unittest.main()
