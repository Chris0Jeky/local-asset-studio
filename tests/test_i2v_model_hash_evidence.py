"""Integrity regressions for I2V model-file hash evidence."""
import hashlib
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "i2v_model_hash_evidence_contract",
    ROOT / "app" / "i2v_diagnostics.py",
)
i2v = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(i2v)


class I2VModelHashEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.comfy = self.root / "comfy"
        self.model_directory = self.comfy / "models" / "diffusion_models"
        self.model_directory.mkdir(parents=True)
        (self.root / "models").mkdir()
        self.report_directory = self.root / "report"
        self.report_directory.mkdir()
        self.model = (self.model_directory / "fixture.safetensors").resolve()
        self.studio = SimpleNamespace(root=self.root, comfy_root=self.comfy)
        self.graph = {
            "1": {
                "class_type": "UNETLoader",
                "inputs": {"unet_name": self.model.name},
            }
        }

    def tearDown(self):
        self.temporary.cleanup()

    def write_library(self, expected):
        payload = {
            "assets": [
                {
                    "id": "fixture-model",
                    "file": "diffusion_models/" + self.model.name,
                    "bytes": len(expected),
                    "sha256": hashlib.sha256(expected).hexdigest(),
                    "url": "",
                    "terms": "Synthetic test fixture only.",
                }
            ]
        }
        (self.root / "models" / "library.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )

    def test_pinned_file_never_inherits_a_cached_digest_from_matching_size_and_mtime(self):
        expected = b"A" * 64
        current = b"B" * 64
        self.model.write_bytes(current)
        self.write_library(expected)
        observed = self.model.stat()
        key = str(self.model)
        stale_digest = hashlib.sha256(expected).hexdigest()
        (self.report_directory / "model-hashes.json").write_text(
            json.dumps(
                {
                    key: {
                        "bytes": observed.st_size,
                        "mtime_ns": observed.st_mtime_ns,
                        "sha256": stale_digest,
                    }
                }
            ),
            encoding="utf-8",
        )

        records = i2v.model_records(self.studio, self.graph, self.report_directory)

        self.assertEqual(len(records), 1)
        record = records[0]
        current_digest = hashlib.sha256(current).hexdigest()
        self.assertEqual(record["sha256"], current_digest)
        self.assertFalse(record["hash_matches_pin"])
        self.assertEqual(record["pin_status"], "mismatch")
        refreshed = json.loads(
            (self.report_directory / "model-hashes.json").read_text(encoding="utf-8")
        )
        self.assertEqual(refreshed[key]["sha256"], current_digest)

    def test_new_cache_records_retain_descriptor_identity_fields(self):
        self.model.write_bytes(b"un-pinned fixture")
        cache = {}

        result = i2v._cached_file_hash(self.model, cache)

        self.assertTrue(result["present"])
        self.assertEqual(result["sha256"], hashlib.sha256(b"un-pinned fixture").hexdigest())
        retained = cache[str(self.model)]
        for field in ("bytes", "mtime_ns", "ctime_ns", "device", "inode"):
            with self.subTest(field=field):
                self.assertIn(field, retained)

    @unittest.skipIf(os.name == "nt", "Windows denies replacement of this open-file fixture")
    def test_path_replacement_during_hashing_cannot_publish_the_old_digest_as_current(self):
        original = b"old descriptor bytes"
        replacement_bytes = b"new path bytes......"
        self.assertEqual(len(original), len(replacement_bytes))
        self.model.write_bytes(original)
        model = self.model
        before = model.stat()
        replacement = model.with_name("replacement.safetensors")
        real_open = Path.open
        replaced = False

        class ReplacingStream:
            def __init__(self, stream):
                self.stream = stream

            def __enter__(self):
                self.stream.__enter__()
                return self

            def __exit__(self, *args):
                return self.stream.__exit__(*args)

            def __getattr__(self, name):
                return getattr(self.stream, name)

            def read(self, *args, **kwargs):
                nonlocal replaced
                if not replaced:
                    replacement.write_bytes(replacement_bytes)
                    replacement.replace(model)
                    os.utime(
                        model,
                        ns=(before.st_atime_ns, before.st_mtime_ns),
                    )
                    replaced = True
                return self.stream.read(*args, **kwargs)

        def opening(candidate, *args, **kwargs):
            stream = real_open(candidate, *args, **kwargs)
            if candidate == model and args and args[0] == "rb":
                return ReplacingStream(stream)
            return stream

        with mock.patch.object(Path, "open", autospec=True, side_effect=opening):
            result = i2v._cached_file_hash(model, {})

        self.assertTrue(replaced)
        self.assertEqual(model.read_bytes(), replacement_bytes)
        self.assertTrue(result["present"])
        self.assertNotIn("sha256", result)
        self.assertIn("changed while hashing", result["error"].lower())


if __name__ == "__main__":
    unittest.main()
