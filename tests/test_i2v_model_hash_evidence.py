"""Integrity regressions for I2V model-file hash evidence."""
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
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
        for field in ("bytes", "mtime_ns", "ctime_ns", "device", "inode", "birthtime_ns"):
            with self.subTest(field=field):
                self.assertIn(field, retained)
                self.assertIn(field, retained["path_identity"])

    def test_cache_hit_tolerates_cross_api_ctime_difference(self):
        self.model.write_bytes(b"cached fixture")
        identity = i2v._file_identity(self.model.stat())
        digest = hashlib.sha256(b"cached fixture").hexdigest()
        key = str(self.model)
        cached_descriptor = dict(identity, ctime_ns=identity["ctime_ns"] + 1)
        cache = {
            key: {
                **cached_descriptor,
                "path_identity": identity,
                "sha256": digest,
            }
        }
        real, calls = i2v._file_identity, []

        def windows_like(observed):
            current = real(observed)
            calls.append(dict(current))
            # _cached_file_hash observes the path, validates the descriptor,
            # then rechecks the path. Only the descriptor uses its own ctime domain.
            if len(calls) == 2:
                current = dict(current, ctime_ns=cached_descriptor["ctime_ns"])
            return current

        with mock.patch.object(i2v, "_file_identity", windows_like):
            with mock.patch.object(i2v, "_hash_open_file", side_effect=AssertionError("cache miss")):
                result = i2v._cached_file_hash(self.model, cache)

        self.assertEqual(len(calls), 3, calls)
        self.assertEqual(result["sha256"], digest)

    def test_unpinned_hit_avoids_rereading_file_contents(self):
        self.model.write_bytes(b"stable fixture bytes")
        cache = {}
        first = i2v._cached_file_hash(self.model, cache)
        self.assertIn("sha256", first)

        with mock.patch.object(i2v, "_hash_open_file", side_effect=AssertionError("must not rehash on a valid hit")):
            result = i2v._cached_file_hash(self.model, cache)

        self.assertEqual(result["sha256"], first["sha256"])
        self.assertNotIn("error", result, result)

    def test_unpinned_hit_rechecks_path_after_opening_descriptor(self):
        self.model.write_bytes(b"cached fixture bytes")
        cache = {}
        first = i2v._cached_file_hash(self.model, cache)

        class SwappedPath:
            def __init__(self, path):
                self.path, self.calls = path, 0

            def __fspath__(self):
                return os.fspath(self.path)

            def __str__(self):
                return str(self.path)

            def stat(self):
                self.calls += 1
                value = self.path.stat()
                if self.calls == 1:
                    return value
                return SimpleNamespace(st_size=value.st_size, st_mtime_ns=value.st_mtime_ns,
                                       st_ctime_ns=value.st_ctime_ns, st_dev=value.st_dev,
                                       st_ino=value.st_ino + 1,
                                       st_birthtime_ns=getattr(value, "st_birthtime_ns", None))

        swapped = SwappedPath(self.model)
        fresh = dict(first, sha256="b" * 64)
        with mock.patch.object(i2v, "_hash_open_file", return_value=fresh) as hashed:
            result = i2v._cached_file_hash(swapped, cache)

        self.assertEqual(swapped.calls, 2)
        hashed.assert_called_once_with(swapped)
        self.assertEqual(result["sha256"], fresh["sha256"])

    def test_same_size_restored_mtime_rehashes_when_path_identity_matches(self):
        original = b"original model bytes...."
        replacement = b"replaced model bytes...."
        self.assertEqual(len(original), len(replacement))
        self.model.write_bytes(original)
        cache = {}
        first = i2v._cached_file_hash(self.model, cache)
        stale_digest = first["sha256"]
        self.assertEqual(stale_digest, hashlib.sha256(original).hexdigest())
        original_stat = self.model.stat()

        self.model.write_bytes(replacement)
        os.utime(self.model, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
        current = i2v._file_identity(self.model.stat())
        # Simulate Windows path identity stability: the path lookup still
        # matches the cached entry even though the bytes changed in place.
        key = str(self.model)
        cache[key]["path_identity"] = {field: current[field] for field in i2v._CACHE_PATH_IDENTITY_FIELDS}

        result = i2v._cached_file_hash(self.model, cache)

        self.assertEqual(result["sha256"], hashlib.sha256(replacement).hexdigest())
        self.assertNotEqual(result["sha256"], stale_digest)
        self.assertNotIn("error", result, result)
        self.assertEqual(cache[key]["sha256"], result["sha256"])

    @unittest.skipUnless(os.name == "nt", "native Windows path-ctime contract")
    def test_windows_same_size_restored_mtime_returns_current_bytes(self):
        original = b"windows original bytes.."
        replacement = b"windows changed bytes..."
        self.assertEqual(len(original), len(replacement))
        self.model.write_bytes(original)
        cache = {}
        first = i2v._cached_file_hash(self.model, cache)
        old_mtime = self.model.stat().st_mtime_ns
        old_atime = self.model.stat().st_atime_ns

        self.model.write_bytes(replacement)
        os.utime(self.model, ns=(old_atime, old_mtime))

        result = i2v._cached_file_hash(self.model, cache)

        self.assertEqual(self.model.read_bytes(), replacement)
        self.assertEqual(result["sha256"], hashlib.sha256(replacement).hexdigest())
        self.assertNotEqual(result["sha256"], first["sha256"])

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX FIFO contract")
    def test_unpinned_fifo_replacement_does_not_reuse_stale_digest(self):
        self.model.write_bytes(b"regular fixture bytes")
        cache = {}
        first = i2v._cached_file_hash(self.model, cache)
        self.assertIn("sha256", first)
        self.model.unlink()
        os.mkfifo(self.model)

        result = i2v._cached_file_hash(self.model, cache)

        self.assertNotIn("sha256", result, result)
        self.assertTrue(result["present"])
        self.assertIn("regular file", result["error"].lower())
        self.assertNotIn(str(self.model), cache)

    def test_cache_miss_preserves_same_domain_ctime_rewrite_detection(self):
        self.model.write_bytes(b"rewritten fixture")
        identity = i2v._file_identity(self.model.stat())
        key = str(self.model)
        cache = {
            key: {
                **identity,
                "path_identity": {**identity, "ctime_ns": identity["ctime_ns"] + 1},
                "sha256": hashlib.sha256(b"old fixture").hexdigest(),
            }
        }
        replacement = {"path": key, "present": True, **identity, "sha256": hashlib.sha256(b"rewritten fixture").hexdigest()}
        with mock.patch.object(i2v, "_hash_open_file", return_value=replacement) as hashed:
            result = i2v._cached_file_hash(self.model, cache)

        hashed.assert_called_once_with(self.model)
        self.assertEqual(result["sha256"], replacement["sha256"])

    def test_a_ctime_only_divergence_between_the_two_stat_calls_still_yields_a_digest(self):
        """Deterministic on every platform: inject the Windows domain difference instead of waiting for it.

        The third _file_identity call in _hash_open_file is the one made from path.stat(); perturbing only its
        ctime reproduces what Windows does on its own for about 8% of freshly written files.
        """
        target = (self.model_directory / "injected.safetensors").resolve()
        target.write_bytes(b"injected fixture")
        real, calls = i2v._file_identity, []

        def perturbed(observed):
            identity = real(observed)
            calls.append(identity)
            if len(calls) == 3: identity = dict(identity, ctime_ns=identity["ctime_ns"] - 1000000)
            return identity

        with mock.patch.object(i2v, "_file_identity", perturbed):
            result = i2v._hash_open_file(target)
        self.assertEqual(len(calls), 3, "the path stat is the third identity in this path; the test drifted")
        self.assertNotIn("error", result, result)
        self.assertEqual(result["sha256"], hashlib.sha256(b"injected fixture").hexdigest())

    def test_the_hashing_path_is_the_one_that_tolerates_it(self):
        """Guards the call site, not just the helper: _hash_open_file must go through _same_file."""
        target = (self.model_directory / "callsite.safetensors").resolve()
        target.write_bytes(b"callsite fixture")
        with mock.patch.object(i2v, "_same_file", return_value=False):
            result = i2v._hash_open_file(target)
        self.assertEqual(result.get("error"), "Model path changed while hashing")

    def test_a_ctime_only_difference_is_the_same_file(self):
        """Windows reports st_ctime_ns differently from os.stat() and os.fstat(); that is not a swapped path."""
        descriptor = {"bytes": 64, "mtime_ns": 5, "ctime_ns": 5, "device": 1, "inode": 2}
        by_path = dict(descriptor, ctime_ns=descriptor["ctime_ns"] - 1000000)
        self.assertTrue(i2v._same_file(by_path, descriptor))
        self.assertNotIn("ctime_ns", i2v._PATH_IDENTITY_FIELDS)

    def test_a_swapped_file_is_still_rejected(self):
        descriptor = {"bytes": 64, "mtime_ns": 5, "ctime_ns": 5, "device": 1, "inode": 2}
        for field, value in (("inode", 99), ("device", 99), ("bytes", 65), ("mtime_ns", 6)):
            with self.subTest(field=field):
                self.assertFalse(i2v._same_file(dict(descriptor, **{field: value}), descriptor))

    def test_a_freshly_written_file_hashes_instead_of_reporting_a_change(self):
        """The regression this guards: no digest at all, because the path stat disagreed about ctime."""
        for attempt in range(25):
            with self.subTest(attempt=attempt):
                target = self.model_directory / ("fresh-%d.safetensors" % attempt)
                target.write_bytes(b"fixture %d" % attempt)
                observed = i2v._hash_open_file(target.resolve())
                self.assertNotIn("error", observed, observed)
                self.assertEqual(observed["sha256"], hashlib.sha256(b"fixture %d" % attempt).hexdigest())

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX FIFO contract")
    def test_fifo_candidate_is_rejected_without_waiting_for_a_writer(self):
        fifo = self.model_directory / "blocked.safetensors"
        os.mkfifo(fifo)
        program = """
import importlib.util
import json
import sys
from pathlib import Path
spec = importlib.util.spec_from_file_location('i2v_fifo_child', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print(json.dumps(module._cached_file_hash(Path(sys.argv[2]), {}, require_current=True)))
"""
        try:
            completed = subprocess.run(
                [sys.executable, "-c", program, str(ROOT / "app" / "i2v_diagnostics.py"), str(fifo)],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
        except subprocess.TimeoutExpired:
            self.fail("FIFO model candidate blocked instead of failing closed")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertTrue(result["present"])
        self.assertNotIn("sha256", result)
        self.assertIn("regular file", result["error"].lower())

    @unittest.skipIf(os.name == "nt", "Windows denies replacement of this open-file fixture")
    def test_path_replacement_during_hashing_cannot_publish_the_old_digest_as_current(self):
        original = b"old descriptor bytes"
        replacement_bytes = b"new path bytes......"
        self.assertEqual(len(original), len(replacement_bytes))
        self.model.write_bytes(original)
        model = self.model
        before = model.stat()
        replacement = model.with_name("replacement.safetensors")
        real_open = i2v._open_model_candidate
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

        def opening(candidate):
            stream = real_open(candidate)
            if Path(candidate) == model:
                return ReplacingStream(stream)
            return stream

        with mock.patch.object(
            i2v,
            "_open_model_candidate",
            side_effect=opening,
        ):
            result = i2v._cached_file_hash(model, {})

        self.assertTrue(replaced)
        self.assertEqual(model.read_bytes(), replacement_bytes)
        self.assertTrue(result["present"])
        self.assertNotIn("sha256", result)
        self.assertIn("changed while hashing", result["error"].lower())


if __name__ == "__main__":
    unittest.main()
