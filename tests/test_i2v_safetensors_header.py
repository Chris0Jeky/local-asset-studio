"""Adversarial container-header tests for the read-only I2V diagnostic."""
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "app"))
from i2v_diagnostics import _safetensors_header


class SafetensorsHeaderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def write_raw(self, name, header, data=b""):
        path = self.root / name
        path.write_bytes(struct.pack("<Q", len(header)) + header + data)
        return path

    def write_json(self, name, header, data=b""):
        encoded = json.dumps(header, separators=(",", ":")).encode("utf-8")
        return self.write_raw(name, encoded, data)

    def test_valid_bounded_header_reports_exact_size_and_tensor_count(self):
        header = {
            "__metadata__": {"source": "synthetic fixture"},
            "tensor": {"dtype": "F32", "shape": [1], "data_offsets": [0, 4]},
        }
        path = self.write_json("valid.safetensors", header, b"\0" * 4)

        report = _safetensors_header(path)

        self.assertEqual(report["status"], "valid")
        self.assertEqual(report["header_bytes"], len(json.dumps(header, separators=(",", ":")).encode("utf-8")))
        self.assertEqual(report["tensor_count"], 1)

    def test_non_object_json_roots_are_structured_invalid_results(self):
        for index, root in enumerate(([], "header", None)):
            with self.subTest(root=root):
                report = _safetensors_header(self.write_json(f"root-{index}.safetensors", root))
                self.assertEqual(report["status"], "invalid")
                self.assertIn("object", report["error"].lower())

    def test_boolean_offsets_are_not_accepted_as_integers(self):
        path = self.write_json(
            "boolean-offsets.safetensors",
            {"tensor": {"dtype": "F32", "shape": [1], "data_offsets": [False, True]}},
            b"\0",
        )

        report = _safetensors_header(path)

        self.assertEqual(report["status"], "invalid")
        self.assertIn("offset", report["error"].lower())

    def test_duplicate_keys_are_rejected_instead_of_last_key_wins(self):
        header = (
            b'{"tensor":{"dtype":"F32","shape":[1],"data_offsets":[0,4]},'
            b'"tensor":{"dtype":"F32","shape":[1],"data_offsets":[0,4]}}'
        )
        path = self.write_raw("duplicate.safetensors", header, b"\0" * 4)

        report = _safetensors_header(path)

        self.assertEqual(report["status"], "invalid")
        self.assertIn("duplicate", report["error"].lower())

    def test_duplicate_surrogate_key_error_remains_utf8_report_safe(self):
        path = self.write_raw(
            "duplicate-surrogate.safetensors",
            b'{"\\ud800":1,"\\ud800":2}',
        )

        report = _safetensors_header(path)

        self.assertEqual(report["status"], "invalid")
        self.assertIn("duplicate", report["error"].lower())
        self.assertNotIn("\ud800", report["error"])
        encoded = json.dumps(
            {"container_header": report}, ensure_ascii=False
        ).encode("utf-8")
        self.assertIn(b"duplicate", encoded)

    def test_non_finite_json_constants_are_rejected(self):
        header = (
            b'{"__metadata__":{"score":NaN},'
            b'"tensor":{"dtype":"F32","shape":[1],"data_offsets":[0,4]}}'
        )
        path = self.write_raw("non-finite.safetensors", header, b"\0" * 4)

        report = _safetensors_header(path)

        self.assertEqual(report["status"], "invalid")
        self.assertIn("non-finite", report["error"].lower())


if __name__ == "__main__":
    unittest.main()
