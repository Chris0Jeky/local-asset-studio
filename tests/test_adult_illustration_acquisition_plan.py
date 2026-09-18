from __future__ import annotations

import copy
import hashlib
import json
import unittest

from studio_prompt.adult_illustration_acquisition_plan import (
    AcquisitionSelection,
    prepare_acquisition_plan,
    render_acquisition_plan,
    validate_acquisition_plan,
)


HF_COMMIT = "a" * 40
HF_SHA = "b" * 64
CIVITAI_SHA = "c" * 64
RAW_SHA = "d" * 64
HF_PATH = "weights/model.safetensors"
HF_ALT_PATH = "weights/alternate.safetensors"
HF_FILE_ID = "hf-file-" + hashlib.sha256(HF_PATH.encode()).hexdigest()[:20]
HF_ALT_FILE_ID = "hf-file-" + hashlib.sha256(HF_ALT_PATH.encode()).hexdigest()[:20]

AUTHORITY = {
    "download_authorized": False,
    "install_authorized": False,
    "execution_authorized": False,
    "generation_submitted": False,
    "training_authorized": False,
}


def _base_snapshot(provider: str, record: dict[str, object]) -> dict[str, object]:
    url = (
        "https://huggingface.co/api/models/owner/model/revision/main?blobs=true"
        if provider == "huggingface"
        else "https://civitai.com/api/v1/model-versions/123"
    )
    return {
        "schema": "studio.adult-illustration-source-snapshot/v1",
        "kind": "source-snapshot-proposal",
        "executable": False,
        "authority": "none",
        "provider": provider,
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
        "record": record,
        **AUTHORITY,
    }


def hf_snapshot() -> dict[str, object]:
    return _base_snapshot(
        "huggingface",
        {
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
                },
                {
                    "id": HF_ALT_FILE_ID,
                    "path": HF_ALT_PATH,
                    "bytes": 2048,
                    "sha256": "e" * 64,
                    "provider_hashes": {},
                    "selected": False,
                },
            ],
            "download_authorized": False,
            "install_authorized": False,
            "execution_authorized": False,
        },
    )


def civitai_snapshot() -> dict[str, object]:
    return _base_snapshot(
        "civitai",
        {
            "id": "civitai-9-123",
            "provider": "civitai",
            "synthetic": False,
            "canonical_url": "https://civitai.com/models/9?modelVersionId=123",
            "provider_model_id": 9,
            "provider_version_id": 123,
            "immutable_revision": "123",
            "snapshot_state": "pinned",
            "terms_state": "snapshotted",
            "access_state": "public_metadata",
            "air": "urn:air:sdxl:checkpoint:civitai:9@123",
            "lineage": {"base_model": "SDXL 1.0"},
            "terms": {
                "allow_no_credit": False,
                "allow_commercial_use": "Image",
                "allow_derivatives": True,
                "allow_different_license": False,
            },
            "metadata": {"status": "Published", "model_type": "Checkpoint"},
            "claims": [],
            "files": [
                {
                    "id": "civitai-file-55",
                    "provider_file_id": 55,
                    "path": "model.safetensors",
                    "bytes": 4096,
                    "sha256": CIVITAI_SHA,
                    "provider_hashes": {"sha256": CIVITAI_SHA.upper()},
                    "file_type": "Model",
                    "primary": True,
                    "metadata": {"format": "SafeTensor"},
                    "selected": False,
                }
            ],
            "download_authorized": False,
            "install_authorized": False,
            "execution_authorized": False,
        },
    )


def hf_selection(**changes: object) -> AcquisitionSelection:
    values: dict[str, object] = {
        "file_id": HF_FILE_ID,
        "destination_folder": "checkpoints",
        "destination_name": "adult-anime-candidate.safetensors",
        "intended_use": "private local qualification",
        "terms_review_ref": None,
    }
    values.update(changes)
    return AcquisitionSelection(**values)  # type: ignore[arg-type]


def _canonical_id(value: dict[str, object]) -> str:
    unsigned = copy.deepcopy(value)
    unsigned.pop("plan_id", None)
    return hashlib.sha256(
        json.dumps(
            unsigned,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _assert_zero_authority(test: unittest.TestCase, value: dict[str, object]) -> None:
    for field in AUTHORITY:
        test.assertFalse(value[field])


class AcquisitionPlanTests(unittest.TestCase):
    def test_huggingface_plan_is_deterministic_pinned_and_dry_run_only(self) -> None:
        snapshot = hf_snapshot()
        first = prepare_acquisition_plan(snapshot, hf_selection())
        second = prepare_acquisition_plan(copy.deepcopy(snapshot), hf_selection())

        self.assertEqual(render_acquisition_plan(first), render_acquisition_plan(second))
        self.assertEqual(first["plan_id"], _canonical_id(first))
        self.assertEqual(first["source"]["provider"], "huggingface")
        self.assertEqual(first["source"]["provider_model_id"], "owner/model")
        self.assertEqual(first["source"]["immutable_revision"], HF_COMMIT)
        self.assertEqual(first["selection"]["file_id"], HF_FILE_ID)
        self.assertEqual(first["selection"]["source_path"], HF_PATH)
        self.assertEqual(first["selection"]["bytes"], 1024)
        self.assertEqual(first["selection"]["sha256"], HF_SHA)
        self.assertEqual(
            first["selection"]["destination_relative_path"],
            "checkpoints/adult-anime-candidate.safetensors",
        )
        self.assertEqual(first["handoff"]["script"], "scripts/fetch-hf.py")
        self.assertEqual(
            first["handoff"]["dry_run_arguments"],
            [
                "--repo", "owner/model", "--path", HF_PATH,
                "--revision", HF_COMMIT, "--dest-folder", "checkpoints",
                "--name", "adult-anime-candidate.safetensors", "--dry-run",
            ],
        )
        self.assertFalse(first["handoff"]["transfer_arguments_authorized"])
        self.assertEqual(first["gates"]["human_terms_review"]["state"], "required")
        self.assertEqual(first["authorized_candidate_cap"], 0)
        _assert_zero_authority(self, first)
        self.assertEqual(validate_acquisition_plan(first, snapshot), first)

    def test_civitai_plan_uses_exact_version_and_file_without_token(self) -> None:
        snapshot = civitai_snapshot()
        selection = AcquisitionSelection(
            file_id="civitai-file-55",
            destination_folder="checkpoints",
            destination_name="civitai-candidate.safetensors",
            intended_use="private local qualification",
            terms_review_ref="HUMAN_TODO.md#q-29",
        )
        plan = prepare_acquisition_plan(snapshot, selection)

        self.assertEqual(plan["source"]["provider"], "civitai")
        self.assertEqual(plan["source"]["provider_version_id"], 123)
        self.assertEqual(plan["selection"]["provider_file_id"], 55)
        self.assertEqual(plan["handoff"]["script"], "scripts/civitai-fetch.py")
        self.assertEqual(
            plan["handoff"]["dry_run_arguments"],
            [
                "--version-id", "123", "--file-id", "55",
                "--dest-folder", "checkpoints", "--name",
                "civitai-candidate.safetensors", "--dry-run",
            ],
        )
        self.assertTrue(plan["handoff"]["transfer_credentials_external"])
        self.assertFalse(plan["handoff"]["credentials_embedded"])
        self.assertNotIn("token", render_acquisition_plan(plan).casefold())
        self.assertEqual(
            plan["gates"]["human_terms_review"]["state"],
            "reference_declared_unverified",
        )
        self.assertEqual(
            plan["gates"]["human_terms_review"]["evidence_ref"],
            "HUMAN_TODO.md#q-29",
        )
        _assert_zero_authority(self, plan)

    def test_terms_reference_never_authorizes_download(self) -> None:
        plan = prepare_acquisition_plan(
            hf_snapshot(), hf_selection(terms_review_ref="decision-record-123")
        )
        self.assertEqual(
            plan["gates"]["human_terms_review"]["state"],
            "reference_declared_unverified",
        )
        self.assertFalse(plan["download_authorized"])
        self.assertFalse(plan["handoff"]["transfer_arguments_authorized"])

    def test_blocked_source_states_are_refused(self) -> None:
        for field, value in [
            ("access_state", "private"),
            ("access_state", "gated"),
            ("synthetic", True),
            ("snapshot_state", "moving"),
        ]:
            with self.subTest(field=field, value=value):
                snapshot = hf_snapshot()
                snapshot["record"][field] = value  # type: ignore[index]
                with self.assertRaises(ValueError):
                    prepare_acquisition_plan(snapshot, hf_selection())

        disabled = hf_snapshot()
        disabled["record"]["metadata"]["disabled"] = True  # type: ignore[index]
        with self.assertRaisesRegex(ValueError, "disabled"):
            prepare_acquisition_plan(disabled, hf_selection())

    def test_file_selection_requires_unique_exact_unselected_pinned_file(self) -> None:
        cases: list[tuple[str, object]] = [
            ("unknown", "missing-file"),
            ("missing hash", None),
            ("invalid hash", "not-a-hash"),
            ("missing bytes", None),
            ("zero bytes", 0),
            ("preselected", True),
            ("unsupported suffix", "weights/model.ckpt"),
            ("unsafe path", "../model.safetensors"),
        ]
        for label, value in cases:
            with self.subTest(label=label):
                snapshot = hf_snapshot()
                selection = hf_selection()
                file_record = snapshot["record"]["files"][0]  # type: ignore[index]
                if label == "unknown":
                    selection = hf_selection(file_id=value)
                elif label in {"missing hash", "invalid hash"}:
                    file_record["sha256"] = value
                elif label in {"missing bytes", "zero bytes"}:
                    file_record["bytes"] = value
                elif label == "preselected":
                    file_record["selected"] = value
                else:
                    file_record["path"] = value
                with self.assertRaises(ValueError):
                    prepare_acquisition_plan(snapshot, selection)

        duplicate = hf_snapshot()
        duplicate_file = copy.deepcopy(duplicate["record"]["files"][1])  # type: ignore[index]
        duplicate_file["id"] = HF_FILE_ID
        duplicate["record"]["files"].append(duplicate_file)  # type: ignore[index]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            prepare_acquisition_plan(duplicate, hf_selection())

    def test_destination_and_operator_fields_are_bounded(self) -> None:
        invalid = [
            {"destination_folder": "unknown"},
            {"destination_name": "../escape.safetensors"},
            {"destination_name": ".hidden.safetensors"},
            {"destination_name": "candidate.ckpt"},
            {"intended_use": "x\ny"},
            {"intended_use": "x" * 513},
            {"terms_review_ref": "x\ny"},
            {"terms_review_ref": "x" * 1025},
        ]
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(ValueError):
                prepare_acquisition_plan(hf_snapshot(), hf_selection(**values))

    def test_plan_validation_detects_tampering_and_rehashed_semantic_changes(self) -> None:
        snapshot = hf_snapshot()
        plan = prepare_acquisition_plan(snapshot, hf_selection())

        changed = json.loads(render_acquisition_plan(plan))
        changed["selection"]["bytes"] += 1
        with self.assertRaisesRegex(ValueError, "plan_id|match"):
            validate_acquisition_plan(changed, snapshot)

        rehashed = json.loads(render_acquisition_plan(plan))
        rehashed["handoff"]["dry_run_arguments"].remove("--dry-run")
        rehashed["plan_id"] = _canonical_id(rehashed)
        with self.assertRaisesRegex(ValueError, "dry-run|handoff|arguments"):
            validate_acquisition_plan(rehashed, snapshot)

        wrong_snapshot = hf_snapshot()
        wrong_snapshot["raw_payload_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "snapshot"):
            validate_acquisition_plan(plan, wrong_snapshot)

    def test_validation_rejects_unknown_fields_even_when_rehashed(self) -> None:
        plan = prepare_acquisition_plan(hf_snapshot(), hf_selection())
        rehashed = json.loads(render_acquisition_plan(plan))
        rehashed["unexpected"] = True
        rehashed["plan_id"] = _canonical_id(rehashed)
        with self.assertRaisesRegex(ValueError, "unknown|field|schema"):
            validate_acquisition_plan(rehashed)


if __name__ == "__main__":
    unittest.main()
