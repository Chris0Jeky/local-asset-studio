from __future__ import annotations

import copy
import hashlib
import json
import unittest

from studio_prompt.adult_illustration_acquisition_plan import (
    AcquisitionSelection,
    prepare_acquisition_plan,
    validate_acquisition_plan,
)


HF_COMMIT = "a" * 40
HF_PATH = "weights/model.safetensors"
HF_FILE_ID = "hf-file-" + hashlib.sha256(HF_PATH.encode("utf-8")).hexdigest()[:20]
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
        "raw_payload_sha256": "d" * 64,
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


def _hf_snapshot() -> dict[str, object]:
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
                    "sha256": "b" * 64,
                    "provider_hashes": {"xet": "xet-id"},
                    "selected": False,
                }
            ],
            "download_authorized": False,
            "install_authorized": False,
            "execution_authorized": False,
        },
    )


def _civitai_snapshot() -> dict[str, object]:
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
            "terms": {"allow_commercial_use": "Image"},
            "metadata": {"status": "Published", "model_type": "Checkpoint"},
            "claims": [],
            "files": [
                {
                    "id": "civitai-file-55",
                    "provider_file_id": 55,
                    "path": "model.safetensors",
                    "bytes": 4096,
                    "sha256": "c" * 64,
                    "provider_hashes": {"sha256": ("c" * 64).upper()},
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


def _selection(provider: str) -> AcquisitionSelection:
    return AcquisitionSelection(
        file_id=HF_FILE_ID if provider == "huggingface" else "civitai-file-55",
        destination_folder="checkpoints",
        destination_name=f"{provider}-candidate.safetensors",
        intended_use="private local qualification",
    )


def _rehash(plan: dict[str, object]) -> None:
    unsigned = copy.deepcopy(plan)
    unsigned.pop("plan_id", None)
    plan["plan_id"] = hashlib.sha256(
        json.dumps(
            unsigned,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


class AcquisitionPlanDerivedIdentityTests(unittest.TestCase):
    def test_rehashed_provider_record_id_must_match_source_identity(self) -> None:
        for provider, snapshot in (
            ("huggingface", _hf_snapshot()),
            ("civitai", _civitai_snapshot()),
        ):
            with self.subTest(provider=provider):
                plan = prepare_acquisition_plan(snapshot, _selection(provider))
                plan["source"]["record_id"] = "forged-record"  # type: ignore[index]
                _rehash(plan)

                with self.assertRaisesRegex(ValueError, "record.*id|identity"):
                    validate_acquisition_plan(plan)

    def test_rehashed_huggingface_file_id_must_match_selected_path(self) -> None:
        plan = prepare_acquisition_plan(_hf_snapshot(), _selection("huggingface"))
        plan["selection"]["file_id"] = "hf-file-00000000000000000000"  # type: ignore[index]
        _rehash(plan)

        with self.assertRaisesRegex(ValueError, "file.*id|path|identity"):
            validate_acquisition_plan(plan)


if __name__ == "__main__":
    unittest.main()
