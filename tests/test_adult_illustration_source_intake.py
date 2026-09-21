import contextlib
import importlib.util
import io
import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "studio_adult_illustration_source_snapshot.py"
HF_SHA = "b" * 40
HF_FILE_SHA = "a" * 64
HF_XET = "c" * 64
CIVITAI_SHA = "d" * 64


def hf_payload():
    return {
        "id": "example-org/example-model",
        "sha": HF_SHA,
        "private": False,
        "gated": False,
        "disabled": False,
        "lastModified": "2026-09-14T20:00:00.000Z",
        "pipeline_tag": "text-to-image",
        "library_name": "diffusers",
        "tags": ["anime", "safetensors"],
        "cardData": {
            "license": "apache-2.0",
            "base_model": "example/base",
            "language": ["en"],
        },
        "siblings": [
            {
                "rfilename": "model.safetensors",
                "size": 1234,
                "lfs": {"sha256": HF_FILE_SHA, "size": 1234, "pointerSize": 133},
                "xetHash": HF_XET,
            },
            {"rfilename": "config.json", "size": 321},
        ],
    }


def civitai_payload():
    return {
        "id": 654321,
        "modelId": 123456,
        "name": "Example v1",
        "createdAt": "2026-09-10T12:00:00.000Z",
        "updatedAt": "2026-09-14T12:00:00.000Z",
        "publishedAt": "2026-09-14T12:00:00.000Z",
        "status": "Published",
        "baseModel": "SDXL 1.0",
        "baseModelType": "Standard",
        "trainedWords": ["example trigger"],
        "air": "urn:air:sdxl:checkpoint:civitai:123456@654321",
        "model": {
            "id": 123456,
            "name": "Example Model",
            "type": "Checkpoint",
            "allowNoCredit": True,
            "allowCommercialUse": ["Image", "RentCivit"],
            "allowDerivatives": True,
            "allowDifferentLicense": False,
        },
        "files": [
            {
                "id": 998877,
                "name": "example.safetensors",
                "sizeKB": 1024.0,
                "type": "Model",
                "primary": True,
                "metadata": {"format": "SafeTensor", "fp": "fp16", "size": "full"},
                "hashes": {
                    "SHA256": CIVITAI_SHA,
                    "AutoV2": "ABCDEF1234",
                    "BLAKE3": "e" * 64,
                },
            }
        ],
    }


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class FakeTransport:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.response


def load_cli():
    spec = importlib.util.spec_from_file_location("adult_source_cli", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load CLI from {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AdultIllustrationSourceIntakeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from studio_prompt import adult_illustration_source_intake as source

        cls.source = source
        cls.cli = load_cli()

    def response(self, url, payload, **overrides):
        values = {
            "request_url": url,
            "final_url": url,
            "status": 200,
            "headers": {
                "content-type": "application/json; charset=utf-8",
                "etag": '"fixture-etag"',
                "last-modified": "Mon, 14 Sep 2026 20:00:00 GMT",
                "x-request-id": "fixture-request",
            },
            "body": encode(payload),
            "redirect_chain": (),
        }
        values.update(overrides)
        return self.source.HttpResponse(**values)

    def run_cli(self, argv):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = self.cli.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_huggingface_snapshot_pins_commit_files_terms_and_zero_authority(self):
        expected_url = (
            "https://huggingface.co/api/models/example-org/example-model/"
            "revision/main?blobs=true"
        )
        transport = FakeTransport(self.response(expected_url, hf_payload()))
        snapshot = self.source.snapshot_huggingface(
            "example-org/example-model", "main", transport
        )
        self.assertEqual(len(transport.requests), 1)
        self.assertEqual(transport.requests[0].url, expected_url)
        record = snapshot["record"]
        self.assertEqual(record["provider_model_id"], "example-org/example-model")
        self.assertEqual(record["immutable_revision"], HF_SHA)
        self.assertEqual(record["terms_state"], "snapshotted")
        self.assertEqual(record["files"][0]["sha256"], HF_FILE_SHA)
        self.assertEqual(record["files"][0]["provider_hashes"]["xet"], HF_XET)
        self.assertFalse(record["files"][0]["selected"])
        self.assertFalse(record["download_authorized"])
        self.assertFalse(record["install_authorized"])
        self.assertFalse(record["execution_authorized"])
        self.assertEqual(len(snapshot["raw_payload_sha256"]), 64)
        self.assertEqual(snapshot["response"]["headers"]["etag"], '"fixture-etag"')

    def test_huggingface_requires_explicit_revision_and_matching_identity(self):
        transport = FakeTransport()
        with self.assertRaisesRegex(ValueError, "revision"):
            self.source.snapshot_huggingface("example-org/example-model", "", transport)
        payload = hf_payload()
        payload["id"] = "other/model"
        url = (
            "https://huggingface.co/api/models/example-org/example-model/"
            "revision/main?blobs=true"
        )
        transport = FakeTransport(self.response(url, payload))
        with self.assertRaisesRegex(ValueError, "identity"):
            self.source.snapshot_huggingface("example-org/example-model", "main", transport)
        self.assertEqual(len(transport.requests), 1)

    def test_huggingface_marks_gated_metadata_without_selecting_files(self):
        payload = hf_payload()
        payload["gated"] = "auto"
        payload["private"] = True
        url = (
            "https://huggingface.co/api/models/example-org/example-model/"
            "revision/" + HF_SHA + "?blobs=true"
        )
        snapshot = self.source.snapshot_huggingface(
            "example-org/example-model",
            HF_SHA,
            FakeTransport(self.response(url, payload)),
        )
        record = snapshot["record"]
        self.assertEqual(record["access_state"], "private_gated")
        self.assertTrue(all(not item["selected"] for item in record["files"]))
        self.assertFalse(record["download_authorized"])

    def test_civitai_snapshot_pins_version_file_hashes_terms_and_air(self):
        url = "https://civitai.com/api/v1/model-versions/654321"
        transport = FakeTransport(self.response(url, civitai_payload()))
        snapshot = self.source.snapshot_civitai(654321, transport)
        self.assertEqual(len(transport.requests), 1)
        record = snapshot["record"]
        self.assertEqual(record["provider_model_id"], 123456)
        self.assertEqual(record["provider_version_id"], 654321)
        self.assertEqual(record["immutable_revision"], "654321")
        self.assertEqual(record["air"], "urn:air:sdxl:checkpoint:civitai:123456@654321")
        file_record = record["files"][0]
        self.assertEqual(file_record["provider_file_id"], 998877)
        self.assertEqual(file_record["bytes"], 1048576)
        self.assertEqual(file_record["sha256"], CIVITAI_SHA)
        self.assertEqual(file_record["provider_hashes"]["autov2"], "ABCDEF1234")
        self.assertEqual(record["terms_state"], "snapshotted")
        self.assertFalse(record["download_authorized"])

    def test_civitai_requires_explicit_positive_version_and_matching_response(self):
        transport = FakeTransport()
        for value in (0, -1, True, "latest"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "version"):
                self.source.snapshot_civitai(value, transport)
        payload = civitai_payload()
        payload["id"] = 7
        url = "https://civitai.com/api/v1/model-versions/654321"
        with self.assertRaisesRegex(ValueError, "version identity"):
            self.source.snapshot_civitai(654321, FakeTransport(self.response(url, payload)))

    def test_cross_provider_redirect_non_json_and_non_200_fail_closed(self):
        hf_url = (
            "https://huggingface.co/api/models/example-org/example-model/"
            "revision/main?blobs=true"
        )
        cross = self.response(
            hf_url,
            hf_payload(),
            final_url="https://evil.example/api/model",
            redirect_chain=("https://evil.example/api/model",),
        )
        with self.assertRaisesRegex(ValueError, "redirect"):
            self.source.snapshot_huggingface(
                "example-org/example-model", "main", FakeTransport(cross)
            )
        html = self.response(
            hf_url,
            hf_payload(),
            headers={"content-type": "text/html"},
            body=b"<html>not json</html>",
        )
        with self.assertRaisesRegex(ValueError, "content type"):
            self.source.snapshot_huggingface(
                "example-org/example-model", "main", FakeTransport(html)
            )
        denied = self.response(hf_url, {}, status=403)
        with self.assertRaisesRegex(ValueError, "HTTP 403"):
            self.source.snapshot_huggingface(
                "example-org/example-model", "main", FakeTransport(denied)
            )

    def test_duplicate_nonfinite_deep_and_oversized_json_are_rejected(self):
        url = "https://civitai.com/api/v1/model-versions/654321"
        duplicate = self.response(url, {}, body=b'{"id":654321,"id":654321}')
        with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
            self.source.snapshot_civitai(654321, FakeTransport(duplicate))
        nonfinite = self.response(url, {}, body=b'{"id":654321,"modelId":NaN}')
        with self.assertRaisesRegex(ValueError, "Non-finite"):
            self.source.snapshot_civitai(654321, FakeTransport(nonfinite))
        value = {"id": 654321, "modelId": 123456}
        cursor = value
        for index in range(25):
            cursor["child"] = {"index": index}
            cursor = cursor["child"]
        deep = self.response(url, value)
        with self.assertRaisesRegex(ValueError, "depth"):
            self.source.snapshot_civitai(654321, FakeTransport(deep))
        oversized = self.response(url, {}, body=b" " * (2_097_153))
        with self.assertRaisesRegex(ValueError, "exceeds"):
            self.source.snapshot_civitai(654321, FakeTransport(oversized))

    def test_unsafe_and_duplicate_file_paths_are_rejected(self):
        payload = hf_payload()
        payload["siblings"][0]["rfilename"] = "../escape.safetensors"
        url = (
            "https://huggingface.co/api/models/example-org/example-model/"
            "revision/main?blobs=true"
        )
        with self.assertRaisesRegex(ValueError, "unsafe"):
            self.source.snapshot_huggingface(
                "example-org/example-model", "main", FakeTransport(self.response(url, payload))
            )
        payload = hf_payload()
        payload["siblings"].append(dict(payload["siblings"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate file path"):
            self.source.snapshot_huggingface(
                "example-org/example-model", "main", FakeTransport(self.response(url, payload))
            )

    def test_transport_is_called_once_and_exceptions_are_not_retried(self):
        transport = FakeTransport(error=TimeoutError("timed out"))
        with self.assertRaisesRegex(TimeoutError, "timed out"):
            self.source.snapshot_civitai(654321, transport)
        self.assertEqual(len(transport.requests), 1)

    def test_snapshot_diff_is_immutable_bounded_and_descriptive(self):
        url = "https://civitai.com/api/v1/model-versions/654321"
        before = self.source.snapshot_civitai(
            654321, FakeTransport(self.response(url, civitai_payload()))
        )
        changed_payload = civitai_payload()
        changed_payload["baseModel"] = "Pony"
        changed_payload["model"]["allowCommercialUse"] = []
        changed_payload["files"][0]["hashes"]["SHA256"] = "f" * 64
        changed_payload["files"].append(
            {
                "id": 112233,
                "name": "vae.safetensors",
                "sizeKB": 128,
                "type": "VAE",
                "primary": False,
                "metadata": {"format": "SafeTensor"},
                "hashes": {"SHA256": "1" * 64},
            }
        )
        after = self.source.snapshot_civitai(
            654321, FakeTransport(self.response(url, changed_payload))
        )
        diff = self.source.diff_snapshots(before, after)
        self.assertEqual(diff["provider"], "civitai")
        self.assertEqual(diff["added_files"], ["vae.safetensors"])
        self.assertEqual(diff["removed_files"], [])
        self.assertEqual(diff["changed_files"], ["example.safetensors"])
        self.assertTrue(diff["terms_changed"])
        self.assertTrue(diff["lineage_changed"])
        self.assertFalse(diff["execution_authorized"])

    def test_cli_uses_local_response_only_and_exclusive_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            response = root / "hf.json"
            response.write_bytes(encode(hf_payload()))
            output = root / "snapshot.json"
            argv = [
                "huggingface",
                "--repo", "example-org/example-model",
                "--revision", "main",
                "--response", str(response),
                "--out", str(output),
            ]
            with mock.patch.object(socket, "create_connection", side_effect=AssertionError("network")):
                first = self.run_cli(argv)
                self.assertEqual(first[0], 0, first[2])
                snapshot = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(snapshot["record"]["immutable_revision"], HF_SHA)
                original = output.read_bytes()
                second = self.run_cli(argv)
                self.assertEqual(second[0], 2)
                self.assertEqual(output.read_bytes(), original)
                error = json.loads(second[2])
                self.assertFalse(error["download_authorized"])
                self.assertFalse(error["execution_authorized"])

    def test_cli_diff_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            response = root / "civitai.json"
            response.write_bytes(encode(civitai_payload()))
            first_path = root / "first.json"
            second_path = root / "second.json"
            create = [
                "civitai", "--version-id", "654321", "--response", str(response),
                "--out", str(first_path),
            ]
            self.assertEqual(self.run_cli(create)[0], 0)
            changed = civitai_payload()
            changed["files"][0]["hashes"]["SHA256"] = "f" * 64
            response.write_bytes(encode(changed))
            create[-1] = str(second_path)
            self.assertEqual(self.run_cli(create)[0], 0)
            code, stdout, stderr = self.run_cli(
                ["diff", "--before", str(first_path), "--after", str(second_path)]
            )
            self.assertEqual(code, 0, stderr)
            self.assertEqual(json.loads(stdout)["changed_files"], ["example.safetensors"])


if __name__ == "__main__":
    unittest.main()
