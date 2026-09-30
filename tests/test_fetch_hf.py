"""Unverified downloads must not publish; pinned downloads must still verify and install.

Covers both provider downloaders and the Hugging Face metadata-only dry run.
"""
import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("fetch_hf", ROOT / "scripts" / "fetch-hf.py")
fetch_hf = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fetch_hf)
CIVITAI_SPEC = importlib.util.spec_from_file_location("civitai_fetch", ROOT / "scripts" / "civitai-fetch.py")
civitai_fetch = importlib.util.module_from_spec(CIVITAI_SPEC)
CIVITAI_SPEC.loader.exec_module(civitai_fetch)

PAYLOAD = b"fake-safetensors-bytes"


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self._offset = 0

    def read(self, size=-1):
        if self._offset >= len(self._payload):
            return b""
        block = self._payload[self._offset:self._offset + size]
        self._offset += len(block)
        return block

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeOpener:
    def __init__(self, payload):
        self._payload = payload

    def open(self, request, timeout=None):
        return _FakeResponse(self._payload)


class RefuseUnverifiedDownload(unittest.TestCase):
    def test_none_sha_refuses_to_publish(self):
        """None expected_sha aborts before part.rename: no target, .part preserved."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "model.safetensors"
            with self.assertRaises(SystemExit):
                fetch_hf.download("https://example.invalid/file", target,
                                  expected_size=None, expected_sha=None,
                                  opener=_FakeOpener(PAYLOAD))
            self.assertFalse(target.exists(), "unverified download must not be published")
            part = target.with_suffix(target.suffix + ".part")
            self.assertTrue(part.is_file(), "partial file must be preserved on refusal")
            self.assertEqual(part.read_bytes(), PAYLOAD)

    def test_pinned_sha_verifies_and_installs(self):
        """Pinned SHA-256 still verifies and installs to the destination."""
        digest = hashlib.sha256(PAYLOAD).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "model.safetensors"
            size, actual, _ = fetch_hf.download(
                "https://example.invalid/file", target,
                expected_size=len(PAYLOAD), expected_sha=digest,
                opener=_FakeOpener(PAYLOAD))
            self.assertEqual(size, len(PAYLOAD))
            self.assertEqual(actual, digest)
            self.assertEqual(target.read_bytes(), PAYLOAD)
            self.assertFalse(target.with_suffix(target.suffix + ".part").exists())

    def test_allow_unverified_publishes_when_flag_passed(self):
        """Explicit --allow-unverified opt-in still publishes; default keeps refusing."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "model.safetensors"
            size, actual, _ = fetch_hf.download(
                "https://example.invalid/file", target,
                expected_size=None, expected_sha=None,
                opener=_FakeOpener(PAYLOAD), allow_unverified=True)
            self.assertEqual(size, len(PAYLOAD))
            self.assertEqual(actual, hashlib.sha256(PAYLOAD).hexdigest())
            self.assertEqual(target.read_bytes(), PAYLOAD)

    def test_civitai_none_sha_refuses_to_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "model.safetensors"
            with self.assertRaises(SystemExit):
                civitai_fetch.download(
                    "https://civitai.com/api/download/models/1", target, "secret",
                    expected_size=None, expected_sha=None,
                    opener=_FakeOpener(PAYLOAD))
            self.assertFalse(target.exists(), "unverified download must not be published")
            self.assertEqual(target.with_suffix(target.suffix + ".part").read_bytes(), PAYLOAD)

    def test_hugging_face_unverified_dry_run_remains_metadata_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = [{"path": "model.safetensors", "size": len(PAYLOAD)}]
            with patch.object(fetch_hf, "load_config", return_value={"comfy_root": tmp}), \
                 patch.object(fetch_hf, "fetch_json", return_value=tree):
                result = fetch_hf.main([
                    "--repo", "owner/repo", "--path", "model.safetensors", "--dry-run"
                ])
            self.assertEqual(result, 0)
            self.assertFalse((Path(tmp) / "models" / "loras" / "model.safetensors").exists())


if __name__ == "__main__":
    unittest.main()
