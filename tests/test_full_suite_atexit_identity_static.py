"""Contracts for side-effect-free callback identity projection."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from runtime_observability import callable_identity  # noqa: E402


class CallbackMetadataProbe:
    metadata_reads: list[str] = []

    def __call__(self):
        pass

    def __getattribute__(self, name):
        if name in {"__module__", "__qualname__", "__name__"}:
            type(self).metadata_reads.append(name)
        return object.__getattribute__(self, name)


class CallableIdentityTests(unittest.TestCase):
    def test_callable_object_identity_does_not_execute_instance_metadata(self):
        CallbackMetadataProbe.metadata_reads.clear()
        callback = CallbackMetadataProbe()

        identity = callable_identity(callback)

        self.assertEqual(identity, f"{__name__}.CallbackMetadataProbe")
        self.assertEqual(CallbackMetadataProbe.metadata_reads, [])


if __name__ == "__main__":
    unittest.main()
