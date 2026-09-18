"""Strict zero-network acquisition plans for Adult Illustration sources."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Mapping

from studio_workflow.model_contracts import FOLDERS

from .adult_illustration_source_intake import read_snapshot_json

PLAN_SCHEMA = "studio.adult-illustration-acquisition-plan/v1"
PLAN_KIND = "source-acquisition-plan"
MAX_PLAN_BYTES = 1_048_576
SHA256 = re.compile(r"[0-9a-f]{64}")
SHA40 = re.compile(r"[0-9a-f]{40}")
HF_REPO = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}/[A-Za-z0-9][A-Za-z0-9._-]{0,95}"
)
FILE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
DESTINATION_NAME = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9._-]{0,180}\.safetensors"
)
AUTHORITY = {
    "download_authorized": False,
    "install_authorized": False,
    "execution_authorized": False,
    "generation_submitted": False,
    "training_authorized": False,
}
SNAPSHOT_FIELDS = {
    "schema",
    "kind",
    "executable",
    "authority",
    "provider",
    "raw_payload_sha256",
    "request",
    "response",
    "record",
    *tuple(AUTHORITY),
}
HF_RECORD_FIELDS = {
    "id",
    "provider",
    "synthetic",
    "canonical_url",
    "provider_model_id",
    "provider_version_id",
    "immutable_revision",
    "requested_revision",
    "snapshot_state",
    "terms_state",
    "access_state",
    "lineage",
    "terms",
    "metadata",
    "claims",
    "files",
    "download_authorized",
    "install_authorized",
    "execution_authorized",
}
CIVITAI_RECORD_FIELDS = (HF_RECORD_FIELDS - {"requested_revision"}) | {"air"}
HF_FILE_FIELDS = {
    "id",
    "path",
    "bytes",
    "sha256",
    "provider_hashes",
    "selected",
}
CIVITAI_FILE_FIELDS = HF_FILE_FIELDS | {
    "provider_file_id",
    "file_type",
    "primary",
    "metadata",
}
PLAN_FIELDS = {
    "schema",
    "kind",
    "executable",
    "authority",
    "issue",
    "source",
    "selection",
    "handoff",
    "gates",
    "authorized_candidate_cap",
    *tuple(AUTHORITY),
    "plan_id",
}
SOURCE_FIELDS = {
    "provider",
    "record_id",
    "snapshot_sha256",
    "raw_payload_sha256",
    "canonical_url",
    "provider_model_id",
    "provider_version_id",
    "immutable_revision",
    "access_state",
    "terms_state",
    "terms_claims",
    "terms_claims_sha256",
}
SELECTION_FIELDS = {
    "file_id",
    "provider_file_id",
    "source_path",
    "bytes",
    "sha256",
    "provider_hashes",
    "destination_folder",
    "destination_name",
    "destination_relative_path",
    "intended_use",
    "terms_review_ref",
}
HANDOFF_FIELDS = {
    "script",
    "dry_run_arguments",
    "live_metadata_recheck_required",
    "transfer_arguments_authorized",
    "credentials_embedded",
    "transfer_credentials_external",
    "expected_sha256",
    "expected_bytes",
}
GATE_NAMES = {
    "human_terms_review",
    "destination_collision",
    "inventory_reconciliation",
    "local_compatibility",
    "storage_budget",
}
GATE_FIELDS = {"state", "evidence_ref"}
BLOCKED_CIVITAI_STATUSES = {
    "archived",
    "deleted",
    "draft",
    "hidden",
    "rejected",
    "taken down",
    "takedown",
    "unpublished",
}


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError(f"Acquisition data is not canonical JSON: {exc}") from exc


def _sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase 64-hex SHA-256")
    return value


def _text(value: Any, label: str, maximum: int) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or value != value.strip()
        or len(value) > maximum
        or "\r" in value
        or "\n" in value
        or "\x00" in value
    ):
        raise ValueError(f"{label} is empty, untrimmed, multiline or oversized")
    return value


def _exact(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{label} has missing or unknown fields")
    return value


def _positive(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _false_authority(value: Mapping[str, Any], label: str) -> None:
    for field in AUTHORITY:
        if value.get(field) is not False:
            raise ValueError(f"{label} must keep {field} false")


def _bounded_json(value: Any, label: str) -> Any:
    encoded = _canonical_bytes(value)
    if len(encoded) > 65_536:
        raise ValueError(f"{label} is oversized")
    stack = [value]
    nodes = 0
    while stack:
        item = stack.pop()
        nodes += 1
        if nodes > 2_048:
            raise ValueError(f"{label} has too many JSON values")
        if isinstance(item, dict):
            if len(item) > 128 or not all(isinstance(key, str) for key in item):
                raise ValueError(f"{label} contains an invalid object")
            stack.extend(item.values())
        elif isinstance(item, list):
            if len(item) > 256:
                raise ValueError(f"{label} contains an oversized array")
            stack.extend(item)
        elif isinstance(item, str):
            if len(item) > 4_096 or "\x00" in item:
                raise ValueError(f"{label} contains an invalid string")
        elif item is not None and not isinstance(item, (bool, int, float)):
            raise ValueError(f"{label} contains an unsupported value")
    return copy.deepcopy(value)


def _relative_source_path(value: Any) -> str:
    text = _text(value, "source file path", 1_024)
    if "\\" in text or ":" in text:
        raise ValueError("source file path is unsafe")
    path = PurePosixPath(text)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("source file path is unsafe")
    return path.as_posix()


def _selected_source_path(value: Any) -> str:
    path = _relative_source_path(value)
    if PurePosixPath(path).suffix.casefold() != ".safetensors":
        raise ValueError("acquisition plans support safetensors files only")
    return path


def _provider_hashes(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or len(value) > 32:
        raise ValueError("provider hashes must be a bounded object")
    result: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        key = _text(raw_key, "provider hash key", 64).casefold()
        item = _text(raw_value, f"provider hash {key}", 512)
        if key in result:
            raise ValueError(f"duplicate provider hash {key!r}")
        result[key] = item
    return result


@dataclass(frozen=True)
class AcquisitionSelection:
    """One explicit file/destination choice; never an authorization record."""

    file_id: str
    destination_folder: str
    destination_name: str
    intended_use: str
    terms_review_ref: str | None = None

    def __post_init__(self) -> None:
        file_id = _text(self.file_id, "selection file id", 128)
        if FILE_ID.fullmatch(file_id) is None:
            raise ValueError("selection file id has an invalid shape")
        folder = _text(self.destination_folder, "destination folder", 128)
        if folder not in FOLDERS:
            raise ValueError(f"unsupported destination folder {folder!r}")
        name = _text(self.destination_name, "destination name", 200)
        if DESTINATION_NAME.fullmatch(name) is None:
            raise ValueError(
                "destination name must be a plain bounded safetensors basename"
            )
        intended_use = _text(self.intended_use, "intended use", 512)
        review = self.terms_review_ref
        if review is not None:
            review = _text(review, "terms review reference", 1_024)
        object.__setattr__(self, "file_id", file_id)
        object.__setattr__(self, "destination_folder", folder)
        object.__setattr__(self, "destination_name", name)
        object.__setattr__(self, "intended_use", intended_use)
        object.__setattr__(self, "terms_review_ref", review)


def _validate_snapshot(
    snapshot: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], str]:
    parsed = read_snapshot_json(_canonical_bytes(snapshot))
    snapshot_sha = hashlib.sha256(_canonical_bytes(parsed)).hexdigest()
    _exact(parsed, SNAPSHOT_FIELDS, "source snapshot")
    _false_authority(parsed, "source snapshot")
    provider = parsed.get("provider")
    if provider not in {"huggingface", "civitai"}:
        raise ValueError(f"unsupported source provider {provider!r}")
    raw_payload_sha = _sha(parsed.get("raw_payload_sha256"), "raw payload identity")
    if not isinstance(parsed.get("request"), dict) or not isinstance(parsed.get("response"), dict):
        raise ValueError("source snapshot request and response must be objects")

    record_fields = HF_RECORD_FIELDS if provider == "huggingface" else CIVITAI_RECORD_FIELDS
    record = _exact(parsed.get("record"), record_fields, "source snapshot record")
    for field in ("download_authorized", "install_authorized", "execution_authorized"):
        if record.get(field) is not False:
            raise ValueError(f"source record must keep {field} false")
    if record.get("provider") != provider:
        raise ValueError("source record provider does not match snapshot")
    if record.get("synthetic") is not False:
        raise ValueError("synthetic sources cannot enter acquisition planning")
    if record.get("snapshot_state") != "pinned":
        raise ValueError("source record must be pinned")
    if record.get("terms_state") not in {"snapshotted", "unknown"}:
        raise ValueError("source terms state is unsupported")
    if not isinstance(record.get("terms"), dict):
        raise ValueError("source terms claims must be an object")
    _bounded_json(record["terms"], "source terms claims")
    metadata = record.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("source metadata must be an object")

    if provider == "huggingface":
        repo = record.get("provider_model_id")
        commit = record.get("immutable_revision")
        if not isinstance(repo, str) or HF_REPO.fullmatch(repo) is None:
            raise ValueError("Hugging Face source needs owner/model identity")
        if not isinstance(commit, str) or SHA40.fullmatch(commit) is None:
            raise ValueError("Hugging Face source needs an immutable lowercase commit")
        if record.get("provider_version_id") is not None:
            raise ValueError("Hugging Face provider version id must be null")
        if record.get("access_state") != "public":
            raise ValueError("Hugging Face source is private or gated")
        if metadata.get("disabled") is not False:
            raise ValueError("Hugging Face source is disabled or has ambiguous status")
        expected_url = f"https://huggingface.co/{repo}/tree/{commit}"
        expected_id = f"huggingface-{repo.replace('/', '--').casefold()}-{commit[:12]}"
    else:
        model_id = _positive(record.get("provider_model_id"), "Civitai model id")
        version_id = _positive(record.get("provider_version_id"), "Civitai version id")
        if record.get("immutable_revision") != str(version_id):
            raise ValueError("Civitai immutable revision does not match version id")
        if record.get("access_state") != "public_metadata":
            raise ValueError("Civitai source does not have public metadata access")
        status = metadata.get("status")
        if isinstance(status, str) and status.strip().casefold() in BLOCKED_CIVITAI_STATUSES:
            raise ValueError(f"Civitai source status {status!r} is blocked")
        expected_url = (
            f"https://civitai.com/models/{model_id}?modelVersionId={version_id}"
        )
        expected_id = f"civitai-{model_id}-{version_id}"
    if record.get("canonical_url") != expected_url:
        raise ValueError("source canonical URL does not match provider identity")
    if record.get("id") != expected_id:
        raise ValueError("source record id does not match provider identity")

    raw_files = record.get("files")
    if not isinstance(raw_files, list) or not raw_files or len(raw_files) > 1_024:
        raise ValueError("source files must be a bounded non-empty array")
    ids: set[str] = set()
    paths: set[str] = set()
    validated_files: list[dict[str, Any]] = []
    for raw in raw_files:
        fields = HF_FILE_FIELDS if provider == "huggingface" else CIVITAI_FILE_FIELDS
        item = _exact(raw, fields, "source file")
        file_id = _text(item.get("id"), "source file id", 128)
        if FILE_ID.fullmatch(file_id) is None:
            raise ValueError("source file id has an invalid shape")
        path = _relative_source_path(item.get("path"))
        if file_id in ids or path in paths:
            raise ValueError("source snapshot contains duplicate file identity")
        ids.add(file_id)
        paths.add(path)
        if item.get("selected") is not False:
            raise ValueError("source snapshot files must remain unselected")
        byte_count = item.get("bytes")
        if byte_count is not None and (
            not isinstance(byte_count, int)
            or isinstance(byte_count, bool)
            or byte_count < 0
        ):
            raise ValueError("source file byte count is invalid")
        digest = item.get("sha256")
        if digest is not None:
            _sha(digest, "source file SHA-256")
        hashes = _provider_hashes(item.get("provider_hashes"))
        provider_file_id: int | None = None
        if provider == "civitai":
            provider_file_id = _positive(
                item.get("provider_file_id"), "Civitai provider file id"
            )
            if file_id != f"civitai-file-{provider_file_id}":
                raise ValueError("Civitai file id does not match provider file id")
            if not isinstance(item.get("primary"), bool):
                raise ValueError("Civitai primary file flag must be boolean")
            if item.get("file_type") is not None and not isinstance(item.get("file_type"), str):
                raise ValueError("Civitai file type must be text or null")
            if not isinstance(item.get("metadata"), dict):
                raise ValueError("Civitai file metadata must be an object")
            _bounded_json(item["metadata"], "Civitai file metadata")
        elif re.fullmatch(r"hf-file-[0-9a-f]{20}", file_id) is None:
            raise ValueError("Hugging Face file id has an invalid shape")
        normalized_file = {
            **copy.deepcopy(item),
            "id": file_id,
            "path": path,
            "provider_hashes": hashes,
        }
        if provider == "civitai":
            normalized_file["provider_file_id"] = provider_file_id
        validated_files.append(normalized_file)

    validated = copy.deepcopy(parsed)
    validated["raw_payload_sha256"] = raw_payload_sha
    validated["record"]["files"] = validated_files
    return validated, record, snapshot_sha


def _handoff(source: Mapping[str, Any], selection: Mapping[str, Any]) -> dict[str, Any]:
    provider = source["provider"]
    if provider == "huggingface":
        script = "scripts/fetch-hf.py"
        arguments = [
            "--repo",
            str(source["provider_model_id"]),
            "--path",
            selection["source_path"],
            "--revision",
            source["immutable_revision"],
            "--dest-folder",
            selection["destination_folder"],
            "--name",
            selection["destination_name"],
            "--dry-run",
        ]
    else:
        script = "scripts/civitai-fetch.py"
        arguments = [
            "--version-id",
            str(source["provider_version_id"]),
            "--file-id",
            str(selection["provider_file_id"]),
            "--dest-folder",
            selection["destination_folder"],
            "--name",
            selection["destination_name"],
            "--dry-run",
        ]
    return {
        "script": script,
        "dry_run_arguments": arguments,
        "live_metadata_recheck_required": True,
        "transfer_arguments_authorized": False,
        "credentials_embedded": False,
        "transfer_credentials_external": provider == "civitai",
        "expected_sha256": selection["sha256"],
        "expected_bytes": selection["bytes"],
    }


def _gates(review_ref: str | None) -> dict[str, dict[str, str | None]]:
    return {
        "human_terms_review": {
            "state": (
                "reference_declared_unverified" if review_ref is not None else "required"
            ),
            "evidence_ref": review_ref,
        },
        "destination_collision": {"state": "unresolved", "evidence_ref": None},
        "inventory_reconciliation": {"state": "required", "evidence_ref": None},
        "local_compatibility": {"state": "unresolved", "evidence_ref": None},
        "storage_budget": {"state": "unresolved", "evidence_ref": None},
    }


def prepare_acquisition_plan(
    snapshot: dict[str, Any],
    selection: AcquisitionSelection,
) -> dict[str, Any]:
    """Build one deterministic dry-run handoff without executing anything."""

    if not isinstance(selection, AcquisitionSelection):
        raise TypeError("selection must be AcquisitionSelection")
    validated, record, snapshot_sha = _validate_snapshot(snapshot)
    matches = [
        item for item in validated["record"]["files"] if item["id"] == selection.file_id
    ]
    if len(matches) != 1:
        raise ValueError(f"source snapshot has no unique file {selection.file_id!r}")
    file_record = matches[0]
    source_path = _selected_source_path(file_record.get("path"))
    byte_count = _positive(file_record.get("bytes"), "selected file byte count")
    digest = _sha(file_record.get("sha256"), "selected file SHA-256")
    terms = _bounded_json(record["terms"], "source terms claims")
    terms_sha = hashlib.sha256(_canonical_bytes(terms)).hexdigest()
    provider = validated["provider"]
    source = {
        "provider": provider,
        "record_id": record["id"],
        "snapshot_sha256": snapshot_sha,
        "raw_payload_sha256": validated["raw_payload_sha256"],
        "canonical_url": record["canonical_url"],
        "provider_model_id": record["provider_model_id"],
        "provider_version_id": record["provider_version_id"],
        "immutable_revision": record["immutable_revision"],
        "access_state": record["access_state"],
        "terms_state": record["terms_state"],
        "terms_claims": terms,
        "terms_claims_sha256": terms_sha,
    }
    selected = {
        "file_id": file_record["id"],
        "provider_file_id": file_record.get("provider_file_id"),
        "source_path": source_path,
        "bytes": byte_count,
        "sha256": digest,
        "provider_hashes": copy.deepcopy(file_record["provider_hashes"]),
        "destination_folder": selection.destination_folder,
        "destination_name": selection.destination_name,
        "destination_relative_path": (
            f"{selection.destination_folder}/{selection.destination_name}"
        ),
        "intended_use": selection.intended_use,
        "terms_review_ref": selection.terms_review_ref,
    }
    plan: dict[str, Any] = {
        "schema": PLAN_SCHEMA,
        "kind": PLAN_KIND,
        "executable": False,
        "authority": "none",
        "issue": 433,
        "source": source,
        "selection": selected,
        "handoff": _handoff(source, selected),
        "gates": _gates(selection.terms_review_ref),
        "authorized_candidate_cap": 0,
        **AUTHORITY,
    }
    plan["plan_id"] = hashlib.sha256(_canonical_bytes(plan)).hexdigest()
    _validate_plan_structure(plan)
    return plan


def _validate_source(value: Any) -> dict[str, Any]:
    source = _exact(value, SOURCE_FIELDS, "acquisition plan source")
    provider = source.get("provider")
    if provider not in {"huggingface", "civitai"}:
        raise ValueError("acquisition plan source provider is unsupported")
    record_id = _text(source.get("record_id"), "source record id", 256)
    _sha(source.get("snapshot_sha256"), "source snapshot SHA-256")
    _sha(source.get("raw_payload_sha256"), "source raw payload SHA-256")
    canonical = _text(source.get("canonical_url"), "source canonical URL", 4_096)
    immutable = _text(source.get("immutable_revision"), "source immutable revision", 256)
    if source.get("terms_state") not in {"snapshotted", "unknown"}:
        raise ValueError("acquisition plan terms state is unsupported")
    terms = _bounded_json(source.get("terms_claims"), "acquisition plan terms claims")
    if hashlib.sha256(_canonical_bytes(terms)).hexdigest() != source.get(
        "terms_claims_sha256"
    ):
        raise ValueError("acquisition plan terms claims SHA-256 does not match")
    if provider == "huggingface":
        repo = source.get("provider_model_id")
        if not isinstance(repo, str) or HF_REPO.fullmatch(repo) is None:
            raise ValueError("acquisition plan Hugging Face identity is invalid")
        if source.get("provider_version_id") is not None:
            raise ValueError("Hugging Face plan version id must be null")
        if SHA40.fullmatch(immutable) is None:
            raise ValueError("Hugging Face plan revision must be an immutable commit")
        if source.get("access_state") != "public":
            raise ValueError("Hugging Face acquisition source must be public")
        expected_url = f"https://huggingface.co/{repo}/tree/{immutable}"
        expected_record_id = (
            f"huggingface-{repo.replace('/', '--').casefold()}-{immutable[:12]}"
        )
    else:
        model_id = _positive(source.get("provider_model_id"), "Civitai model id")
        version_id = _positive(source.get("provider_version_id"), "Civitai version id")
        if immutable != str(version_id):
            raise ValueError("Civitai plan revision does not match version id")
        if source.get("access_state") != "public_metadata":
            raise ValueError("Civitai acquisition source needs public metadata")
        expected_url = (
            f"https://civitai.com/models/{model_id}?modelVersionId={version_id}"
        )
        expected_record_id = f"civitai-{model_id}-{version_id}"
    if canonical != expected_url:
        raise ValueError("acquisition plan canonical URL does not match source")
    if record_id != expected_record_id:
        raise ValueError(
            "acquisition plan source record id does not match provider identity"
        )
    return source


def _validate_selection(value: Any, provider: str) -> tuple[dict[str, Any], AcquisitionSelection]:
    selected = _exact(value, SELECTION_FIELDS, "acquisition plan selection")
    file_id = _text(selected.get("file_id"), "selected file id", 128)
    if FILE_ID.fullmatch(file_id) is None:
        raise ValueError("selected file id has an invalid shape")
    source_path = _selected_source_path(selected.get("source_path"))
    provider_file_id = selected.get("provider_file_id")
    if provider == "civitai":
        provider_file_id = _positive(provider_file_id, "Civitai provider file id")
        if file_id != f"civitai-file-{provider_file_id}":
            raise ValueError("Civitai selected file identity is inconsistent")
    else:
        if provider_file_id is not None:
            raise ValueError("Hugging Face selected provider file id must be null")
        expected_file_id = (
            "hf-file-"
            + hashlib.sha256(source_path.encode("utf-8")).hexdigest()[:20]
        )
        if file_id != expected_file_id:
            raise ValueError(
                "Hugging Face selected file id does not match source path"
            )
    byte_count = _positive(selected.get("bytes"), "selected file byte count")
    digest = _sha(selected.get("sha256"), "selected file SHA-256")
    hashes = _provider_hashes(selected.get("provider_hashes"))
    selection = AcquisitionSelection(
        file_id=file_id,
        destination_folder=selected.get("destination_folder"),
        destination_name=selected.get("destination_name"),
        intended_use=selected.get("intended_use"),
        terms_review_ref=selected.get("terms_review_ref"),
    )
    if selected.get("destination_relative_path") != (
        f"{selection.destination_folder}/{selection.destination_name}"
    ):
        raise ValueError("acquisition destination relative path does not match")
    normalized = {
        **selected,
        "file_id": file_id,
        "provider_file_id": provider_file_id,
        "source_path": source_path,
        "bytes": byte_count,
        "sha256": digest,
        "provider_hashes": hashes,
    }
    return normalized, selection


def _validate_gates(value: Any, review_ref: str | None) -> None:
    gates = _exact(value, GATE_NAMES, "acquisition plan gates")
    expected = _gates(review_ref)
    for name, gate in gates.items():
        _exact(gate, GATE_FIELDS, f"acquisition gate {name}")
    if gates != expected:
        raise ValueError("acquisition plan gates do not match unresolved review state")


def _validate_plan_structure(plan: Any) -> dict[str, Any]:
    value = _exact(plan, PLAN_FIELDS, "acquisition plan")
    if value.get("schema") != PLAN_SCHEMA or value.get("kind") != PLAN_KIND:
        raise ValueError("unsupported acquisition plan schema or kind")
    if value.get("executable") is not False or value.get("authority") != "none":
        raise ValueError("acquisition plan must be non-executing with authority none")
    if value.get("issue") != 433:
        raise ValueError("acquisition plan issue owner must be #433")
    if value.get("authorized_candidate_cap") != 0:
        raise ValueError("acquisition plan authorized candidate cap must be zero")
    _false_authority(value, "acquisition plan")
    source = _validate_source(value.get("source"))
    selected, selection = _validate_selection(
        value.get("selection"), source["provider"]
    )
    handoff = _exact(value.get("handoff"), HANDOFF_FIELDS, "acquisition handoff")
    if handoff != _handoff(source, selected):
        raise ValueError("acquisition handoff arguments are not exact dry-run arguments")
    _validate_gates(value.get("gates"), selection.terms_review_ref)
    plan_id = _sha(value.get("plan_id"), "acquisition plan id")
    unsigned = copy.deepcopy(value)
    unsigned.pop("plan_id")
    if hashlib.sha256(_canonical_bytes(unsigned)).hexdigest() != plan_id:
        raise ValueError("acquisition plan_id does not match canonical content")
    rendered = _canonical_bytes(value)
    if len(rendered) > MAX_PLAN_BYTES:
        raise ValueError("acquisition plan is oversized")
    return value


def validate_acquisition_plan(
    plan: dict[str, Any],
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate a persisted plan and optionally bind it to its source snapshot."""

    value = _validate_plan_structure(plan)
    if snapshot is not None:
        selected = value["selection"]
        expected = prepare_acquisition_plan(
            snapshot,
            AcquisitionSelection(
                file_id=selected["file_id"],
                destination_folder=selected["destination_folder"],
                destination_name=selected["destination_name"],
                intended_use=selected["intended_use"],
                terms_review_ref=selected["terms_review_ref"],
            ),
        )
        if value != expected:
            raise ValueError("acquisition plan does not match the source snapshot")
    return value


def render_acquisition_plan(plan: dict[str, Any]) -> str:
    """Render a validated plan deterministically for storage or review."""

    value = validate_acquisition_plan(plan)
    return json.dumps(
        value,
        indent=2,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
    ) + "\n"


__all__ = [
    "AcquisitionSelection",
    "prepare_acquisition_plan",
    "render_acquisition_plan",
    "validate_acquisition_plan",
]