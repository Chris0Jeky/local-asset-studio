"""Contracts for side-effect-free callback identity projection."""
from __future__ import annotations

import functools
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from runtime_observability import callable_identity  # noqa: E402


def sample_callback():
    pass


class CallbackOwner:
    def callback(self):
        pass


class CallbackMetadataProbe:
    metadata_reads: list[str] = []

    def __call__(self):
        pass

    def __getattribute__(self, name):
        if name in {"__module__", "__qualname__", "__name__"}:
            type(self).metadata_reads.append(name)
        return object.__getattribute__(self, name)


class CallbackMetaclass(type):
    metadata_reads: list[str] = []

    def __getattribute__(cls, name):
        if name in {"__module__", "__qualname__", "__name__"}:
            CallbackMetaclass.metadata_reads.append(name)
        return type.__getattribute__(cls, name)


class MetaclassCallback(metaclass=CallbackMetaclass):
    def __call__(self):
        pass


class CallableIdentityTests(unittest.TestCase):
    def test_callable_object_identity_does_not_execute_instance_metadata(self):
        CallbackMetadataProbe.metadata_reads.clear()
        callback = CallbackMetadataProbe()

        identity = callable_identity(callback)

        self.assertEqual(identity, f"{__name__}.CallbackMetadataProbe")
        self.assertEqual(CallbackMetadataProbe.metadata_reads, [])

    def test_class_identity_bypasses_custom_metaclass_metadata(self):
        CallbackMetaclass.metadata_reads.clear()

        identity = callable_identity(MetaclassCallback)

        self.assertEqual(identity, f"{__name__}.MetaclassCallback")
        self.assertEqual(CallbackMetaclass.metadata_reads, [])

    def test_function_method_and_partial_identities_retain_the_owner(self):
        owner = CallbackOwner()

        self.assertEqual(
            callable_identity(sample_callback),
            f"{__name__}.sample_callback",
        )
        self.assertEqual(
            callable_identity(owner.callback),
            f"{__name__}.CallbackOwner.callback",
        )
        self.assertEqual(
            callable_identity(functools.partial(sample_callback, "secret")),
            f"functools.partial({__name__}.sample_callback)",
        )


if __name__ == "__main__":
    unittest.main()
