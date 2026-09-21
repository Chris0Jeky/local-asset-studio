from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "studio_adult_illustration_acquisition_plan.py"
MAX_LOCAL_JSON_BYTES = 4_194_304
HF_COMMIT = "a" * 40
HF_SHA = "b" * 64
RAW_SHA = "d" * 64
HF_PATH = "weights/model.safetensors"
HF_FILE_ID = "hf-file-" + hashlib.sha256(HF_PATH.encode("utf-8")).hexdigest()[:20]
AUTHORITY_FIELDS = (
    "download_authorized",
    "install_authorized",
    "execution_authorized",
    "generation_submitted",
    "training_authorized",
)


def hf_snapshot() -> dict[str, object]:
    url = "https://huggingface.co/api/models/owner/model/revision/main?blobs=true"
    return {
        "schema": "studio.adult-illustration-source-snapshot/v1",
        "kind": "source-snapshot-proposal",
        "executable": False,
        "authority": "none",
        "provider": "huggingface",
        "raw_payload_sha256": RAW_SHA,
        "request": {
            "method": "GET",
            "url": url,
            "headers": {
                "accept": "application/json",
                "user-agent": "local-asset-studio-source-snapshot/1",
            },
        },
        "response": {
            "status": 200,
            "final_url": url,
            "redirect_chain": [],
            "headers": {"content-type": "application/json"},
        },
        "record": {
            "id": "huggingface-owner--model-aaaaaaaaaaaa",
            "provider": "huggingface",
            "synthetic": False,
            "canonical_url": f"https://huggingface.co/owner/model/tree/{HF_COMMIT}",
            "provider_model_id": "owner/model",
            "provider_version_id": None,
            "immutable_revision": HF_COMMIT,
            "requested_revision": "main",
            "snapshot_state": "pinned",
            "terms_state": "snapshotted",
            "access_state": "public",
            "lineage": {"base_models": ["base/model"]},
            "terms": {"license": "apache-2.0"},
            "metadata": {"disabled": False},
            "claims": [],
            "files": [
                {
                    "id": HF_FILE_ID,
                    "path": HF_PATH,
                    "bytes": 1024,
                    "sha256": HF_SHA,
                    "provider_hashes": {"xet": "xet-id"},
                    "selected": False,
                }
            ],
            "download_authorized": False,
            "install_authorized": False,
            "execution_authorized": False,
        },
        **{field: False for field in AUTHORITY_FIELDS},
    }


def run_cli(*arguments: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *(str(item) for item in arguments)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def prepare_arguments(snapshot: Path, output: Path | None = None) -> list[str]:
    arguments = [
        "prepare",
        "--snapshot",
        str(snapshot),
        "--file-id",
        HF_FILE_ID,
        "--destination-folder",
        "checkpoints",
        "--destination-name",
        "adult-anime-candidate.safetensors",
        "--intended-use",
        "private local qualification",
    ]
    if output is not None:
        arguments.extend(["--out", str(output)])
    return arguments


class AcquisitionPlanCliTests(unittest.TestCase):
    def write_snapshot(self, directory: Path) -> Path:
        path = directory / "snapshot.json"
        path.write_text(
            json.dumps(hf_snapshot(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return path

    def assert_zero_authority_error(
        self,
        result: subprocess.CompletedProcess[str],
        operation: str,
    ) -> dict[str, object]:
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        payload = json.loads(result.stderr)
        self.assertEqual(payload["schema"], "studio.adult-illustration-acquisition-plan-error/v1")
        self.assertEqual(payload["kind"], "acquisition-plan-error")
        self.assertEqual(payload["operation"], operation)
        self.assertEqual(payload["authority"], "none")
        self.assertFalse(payload["executable"])
        self.assertIn("error", payload)
        for field in AUTHORITY_FIELDS:
            self.assertIs(payload[field], False)
        return payload

    def test_help_lists_prepare_and_validate_without_running_a_downloader(self) -> None:
        result = run_cli("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("prepare", result.stdout)
        self.assertIn("validate", result.stdout)

    def test_prepare_and_validate_round_trip_on_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            snapshot = self.write_snapshot(directory)

            prepared = run_cli(*prepare_arguments(snapshot))
            self.assertEqual(prepared.returncode, 0, prepared.stderr)
            self.assertEqual(prepared.stderr, "")
            plan = json.loads(prepared.stdout)
            self.assertEqual(
                plan["schema"], "studio.adult-illustration-acquisition-plan/v1"
            )
            self.assertEqual(plan["authorized_candidate_cap"], 0)
            self.assertEqual(plan["authority"], "none")
            self.assertFalse(plan["handoff"]["transfer_arguments_authorized"])
            for field in AUTHORITY_FIELDS:
                self.assertIs(plan[field], False)

            plan_path = directory / "plan.json"
            plan_path.write_text(prepared.stdout, encoding="utf-8", newline="\n")
            validated = run_cli(
                "validate",
                "--plan",
                plan_path,
                "--snapshot",
                snapshot,
            )
            self.assertEqual(validated.returncode, 0, validated.stderr)
            self.assertEqual(validated.stdout, prepared.stdout)
            self.assertEqual(validated.stderr, "")

    def test_output_is_exclusive_and_a_second_attempt_preserves_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            snapshot = self.write_snapshot(directory)
            output = directory / "plan.json"

            first = run_cli(*prepare_arguments(snapshot, output))
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(first.stdout, "")
            original = output.read_bytes()
            self.assertTrue(original.endswith(b"\n"))
            self.assertEqual(
                json.loads(original)["schema"],
                "studio.adult-illustration-acquisition-plan/v1",
            )

            second = run_cli(*prepare_arguments(snapshot, output))
            payload = self.assert_zero_authority_error(second, "prepare")
            self.assertRegex(str(payload["error"]), "(?i)output|exist|occupied")
            self.assertEqual(output.read_bytes(), original)

    def test_occupied_output_is_preflighted_before_a_missing_input(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            output = directory / "plan.json"
            output.write_bytes(b"keep-this-exactly\n")
            missing = directory / "missing-snapshot.json"

            result = run_cli(*prepare_arguments(missing, output))
            payload = self.assert_zero_authority_error(result, "prepare")
            self.assertRegex(str(payload["error"]), "(?i)output|exist|occupied")
            self.assertNotRegex(str(payload["error"]), "(?i)missing snapshot")
            self.assertEqual(output.read_bytes(), b"keep-this-exactly\n")

    def test_snapshot_symlink_and_directory_inputs_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            snapshot = self.write_snapshot(directory)
            link = directory / "snapshot-link.json"
            try:
                os.symlink(snapshot, link)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlinks are unavailable: {exc}")

            linked = run_cli(*prepare_arguments(link))
            payload = self.assert_zero_authority_error(linked, "prepare")
            self.assertRegex(str(payload["error"]), "(?i)symlink|link")

            directory_input = run_cli(*prepare_arguments(directory))
            payload = self.assert_zero_authority_error(directory_input, "prepare")
            self.assertRegex(str(payload["error"]), "(?i)regular|file")

    def test_oversized_snapshot_is_refused_before_json_parsing(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "oversized.json"
            path.write_bytes(b" " * (MAX_LOCAL_JSON_BYTES + 1))

            result = run_cli(*prepare_arguments(path))
            payload = self.assert_zero_authority_error(result, "prepare")
            self.assertRegex(str(payload["error"]), "(?i)oversized|4194304|4,194,304")

    def test_validate_rejects_duplicate_json_keys(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            snapshot = self.write_snapshot(directory)
            prepared = run_cli(*prepare_arguments(snapshot))
            self.assertEqual(prepared.returncode, 0, prepared.stderr)
            duplicate = prepared.stdout.replace(
                '  "schema": "studio.adult-illustration-acquisition-plan/v1",',
                '  "schema": "duplicate",\n'
                '  "schema": "studio.adult-illustration-acquisition-plan/v1",',
                1,
            )
            self.assertNotEqual(duplicate, prepared.stdout)
            plan = directory / "duplicate.json"
            plan.write_text(duplicate, encoding="utf-8", newline="\n")

            result = run_cli("validate", "--plan", plan)
            payload = self.assert_zero_authority_error(result, "validate")
            self.assertRegex(str(payload["error"]), "(?i)duplicate")

    def test_output_symlink_is_refused_without_changing_its_target(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            snapshot = self.write_snapshot(directory)
            target = directory / "existing.json"
            target.write_bytes(b"do-not-replace\n")
            output = directory / "linked-output.json"
            try:
                os.symlink(target, output)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlinks are unavailable: {exc}")

            result = run_cli(*prepare_arguments(snapshot, output))
            payload = self.assert_zero_authority_error(result, "prepare")
            self.assertRegex(str(payload["error"]), "(?i)symlink|output|exist")
            self.assertEqual(target.read_bytes(), b"do-not-replace\n")

    def test_cli_source_does_not_import_network_or_downloader_modules(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        for forbidden in (
            "fetch-hf",
            "civitai-fetch",
            "subprocess",
            "socket",
            "requests",
            "urllib",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
