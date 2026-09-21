"""Integrity tests for the opt-in H3 safetensors mmap loader."""
import importlib.util
import json
import os
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "h3_mmap_loader_contract",
    ROOT / "scripts" / "h3_mmap_loader.py",
)
h3 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(h3)


class _Dtype:
    itemsize = 4


DTYPES = {"F32": _Dtype()}


class H3MmapHeaderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def write_raw(self, name, header, payload=b""):
        path = self.root / name
        path.write_bytes(struct.pack("<Q", len(header)) + header + payload)
        return path

    def write_json(self, name, header, payload=b""):
        encoded = json.dumps(header, separators=(",", ":")).encode("utf-8")
        return self.write_raw(name, encoded, payload)

    def checked_header(self, path):
        with path.open("rb") as stream:
            return h3.checked_header(stream, path.stat().st_size, DTYPES)

    def test_valid_tensor_header_keeps_exact_extent_checks(self):
        path = self.write_json(
            "valid.safetensors",
            {"tensor": {"dtype": "F32", "shape": [1], "data_offsets": [0, 4]}},
            b"\0" * 4,
        )

        header, data_start = self.checked_header(path)

        self.assertEqual(header["tensor"]["shape"], [1])
        self.assertEqual(data_start + 4, path.stat().st_size)

    def test_duplicate_keys_are_rejected_instead_of_last_key_wins(self):
        header = (
            b'{"tensor":{"dtype":"F32","shape":[1],"data_offsets":[0,4]},'
            b'"tensor":{"dtype":"F32","shape":[1],"data_offsets":[0,4]}}'
        )
        path = self.write_raw("duplicate.safetensors", header, b"\0" * 4)

        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.checked_header(path)

    def test_non_finite_json_constants_are_rejected(self):
        header = (
            b'{"__metadata__":{"score":NaN},'
            b'"tensor":{"dtype":"F32","shape":[1],"data_offsets":[0,4]}}'
        )
        path = self.write_raw("non-finite.safetensors", header, b"\0" * 4)

        with self.assertRaisesRegex(ValueError, "non-finite"):
            self.checked_header(path)

    def test_load_uses_open_descriptor_size_not_a_second_path_lookup(self):
        path = self.write_json(
            "metadata-only.safetensors",
            {"__metadata__": {"source": "synthetic fixture"}},
        ).resolve()
        real_stat = Path.stat

        def shifted_path_size(candidate, *args, **kwargs):
            result = real_stat(candidate, *args, **kwargs)
            if str(candidate) != str(path):
                return result
            fields = list(result)
            fields[6] += 1
            return os.stat_result(fields)

        with mock.patch.object(Path, "stat", autospec=True, side_effect=shifted_path_size):
            state, metadata = h3.load_cpu(path, object(), {}, read_only=True)

        self.assertEqual(state, {})
        self.assertEqual(metadata, {"source": "synthetic fixture"})


if __name__ == "__main__":
    unittest.main()
