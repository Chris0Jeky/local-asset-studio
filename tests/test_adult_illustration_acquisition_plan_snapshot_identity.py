from __future__ import annotations

import hashlib
import json
import unittest

from studio_prompt.adult_illustration_acquisition_plan import (
    AcquisitionSelection,
    prepare_acquisition_plan,
)


HF_COMMIT = "a" * 40
MODEL_PATH = "weights/model.safetensors"
CONFIG_PATH = "config.json"
MODEL_ID = "hf-file-" + hashlib.sha256(MODEL_PATH.encode("utf-8")).hexdigest()[:20]
CONFIG_ID = "hf-file-" + hashlib.sha256(CONFIG_PATH.encode("utf-8")).hexdigest()[:20]


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def snapshot(*, include_config: bool) -> dict[str, object]:
    request_url = (
        "https://huggingface.co/api/models/owner/model/revision/main?blobs=true"
    )
    files: list[dict[str, object]] = [
        {
            "id": MODEL_ID,
            "path": MODEL_PATH,
            "bytes": 1024,
            "sha256": "b" * 64,
            "provider_hashes": {"XET": "provider-object-id"},
            "selected": False,
        }
    ]
    if include_config:
        files.append(
            {
                "id": CONFIG_ID,
                "path": CONFIG_PATH,
                "bytes": 128,
                "sha256": "c" * 64,
                "provider_hashes": {},
                "selected": False,
            }
        )
    return {
        "schema": "studio.adult-illustration-source-snapshot/v1",
        "kind": "source-snapshot-proposal",
        "executable": False,
        "authority": "none",
        "provider": "huggingface",
        "raw_payload_sha256": "d" * 64,
        "request": {
            "method": "GET",
            "url": request_url,
            "headers": {
                "accept": "application/json",
                "user-agent": "local-asset-studio-source-snapshot/1",
            },
        },
        "response": {
            "status": 200,
            "final_url": request_url,
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
            "files": files,
            "download_authorized": False,
            "install_authorized": False,
            "execution_authorized": False,
        },
        "download_authorized": False,
        "install_authorized": False,
        "execution_authorized": False,
        "generation_submitted": False,
        "training_authorized": False,
    }


def selection() -> AcquisitionSelection:
    return AcquisitionSelection(
        file_id=MODEL_ID,
        destination_folder="checkpoints",
        destination_name="adult-anime-candidate.safetensors",
        intended_use="private local qualification",
    )


class AcquisitionPlanSnapshotIdentityTests(unittest.TestCase):
    def test_unselected_non_safetensors_files_do_not_block_a_safe_selection(self) -> None:
        value = snapshot(include_config=True)

        plan = prepare_acquisition_plan(value, selection())

        self.assertEqual(plan["selection"]["file_id"], MODEL_ID)
        self.assertEqual(plan["selection"]["source_path"], MODEL_PATH)

    def test_snapshot_identity_hashes_exact_canonical_snapshot_before_normalization(self) -> None:
        value = snapshot(include_config=False)
        expected = _canonical_sha256(value)

        plan = prepare_acquisition_plan(value, selection())

        self.assertEqual(plan["source"]["snapshot_sha256"], expected)


if __name__ == "__main__":
    unittest.main()
