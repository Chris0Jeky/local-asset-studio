"""Stage-aware, evidence-bound resource admission for Studio jobs.

A reservation is a Studio concurrency contract. It does not reserve physical RAM,
Windows commit, or VRAM from the operating system or backend. Unknown counters and
unknown workflow profiles stay distinct from measured safe and measured unsafe.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import threading
import time

import host_memory
import resource_probe
import wan_capacity

SCHEMA = "studio.resource-admission/v1"
PROFILE_SCHEMA = "studio.resource-admission-profile/v1"
IDENTITY_SCHEMA = "studio.resource-admission-identity/v2"
DIMENSIONS = ("physical_ram_bytes", "windows_commit_bytes", "vram_bytes")
DECISIONS = {"observed_safe", "estimated_safe", "unknown", "observed_unsafe"}
ACTIVE_STATES = {"reserved", "retained"}
MAX_STAGES = 16
MAX_RECEIPTS = 32
MAX_DOCUMENT_BYTES = 64 * 1024
MAX_PROFILE_BYTES = 32 * 1024
MODEL_FIELDS = {
    "unet_name", "model_name", "ckpt_name", "checkpoint_name", "diffusion_model",
    "vae_name", "clip_name", "lora_name", "control_net_name", "controlnet_name",
}
SHAPE_FIELDS = {
    "width", "height", "length", "frames", "num_frames", "video_length",
    "batch_size", "batch", "steps", "megapixels", "tile_size", "overlap",
}
TERMINAL_STATUSES = {"completed", "failed", "partial", "not_submitted", "abandoned"}
_HASH = re.compile(r"[0-9a-f]{64}\Z")


class AdmissionError(ValueError):
    def __init__(self, message, receipt):
        super().__init__(message)
        self.receipt = copy.deepcopy(receipt)


def _canonical(value, limit=MAX_DOCUMENT_BYTES):
    try:
        data = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("Resource admission value is not canonical JSON") from exc
    if len(data) > limit:
        raise ValueError("Resource admission document exceeds its byte limit")
    return data


def _digest(value, limit=MAX_DOCUMENT_BYTES):
    return hashlib.sha256(_canonical(value, limit)).hexdigest()


def _counter(value):
    if (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value >= 0):
        return int(value)
    return None


def _model_and_shape(graph):
    models, shapes, classes = [], [], []
    if not isinstance(graph, dict):
        raise ValueError("Workflow graph must be an object")
    if len(graph) > 2000:
        raise ValueError("Workflow graph exceeds the admission node limit")
    for identifier, node in sorted(graph.items(), key=lambda item: str(item[0])):
        if not isinstance(node, dict):
            raise ValueError("Workflow node must be an object")
        kind = str(node.get("class_type") or "")[:160]
        classes.append((str(identifier)[:80], kind))
        inputs = node.get("inputs") or {}
        if not isinstance(inputs, dict):
            raise ValueError("Workflow inputs must be an object")
        for field, value in sorted(inputs.items()):
            if field in MODEL_FIELDS and isinstance(value, str):
                models.append((
                    str(identifier)[:80],
                    kind,
                    field,
                    value.replace("\\", "/")[:512],
                ))
            if field in SHAPE_FIELDS:
                number = _counter(value)
                if number is not None:
                    shapes.append((str(identifier)[:80], kind, field, number))
    return models, shapes, classes


def _declared_bindings(preset, key):
    bindings = []
    primary = preset.get(key) if isinstance(preset, dict) else None
    if primary is not None:
        bindings.append(primary)
    extras = (preset.get("bindings_extra") or {}).get(key, []) if isinstance(preset, dict) else []
    if isinstance(extras, list):
        bindings.extend(extras)
    return bindings


def _resource_graph(preset, graph):
    """Redact only declared prompt/seed values while retaining all graph shape facts."""
    projected = copy.deepcopy(graph)
    for role in ("seed", "positive", "negative"):
        for binding in _declared_bindings(preset, role):
            if not isinstance(binding, (list, tuple)) or len(binding) != 2:
                continue
            node_id, field = str(binding[0]), str(binding[1])
            node = projected.get(node_id)
            inputs = node.get("inputs") if isinstance(node, dict) else None
            if isinstance(inputs, dict) and field in inputs:
                inputs[field] = {"studio_resource_binding": role}
    return projected


def workflow_identity(studio, preset, graph, runtime):
    """Return a bounded workflow-shape/backend/model/runtime identity plus exact graph evidence."""
    models, shapes, classes = _model_and_shape(graph)
    backend_id = str(preset.get("backend_id", "primary"))
    manager = getattr(studio, "backends", None)
    profile = copy.deepcopy(getattr(manager, "profiles", {}).get(backend_id)) if manager is not None else None
    if not isinstance(profile, dict):
        profile = {"id": backend_id, "url": str(getattr(studio, "comfy_url", ""))}
    # Paths and launch arguments matter to backend identity, but receipts store only the canonical digest.
    profile_digest = _digest(profile, MAX_PROFILE_BYTES)
    versions = runtime.get("versions") if isinstance(runtime, dict) else None
    if not isinstance(versions, dict):
        versions = {}
    resource_graph_sha256 = _digest(_resource_graph(preset, graph))
    profile_identity = {
        "schema": IDENTITY_SCHEMA,
        "preset_id": str(preset.get("id", ""))[:200],
        "backend_id": backend_id[:80],
        "backend_profile_sha256": profile_digest,
        "runtime_versions": {
            str(key)[:80]: str(value)[:160]
            for key, value in sorted(versions.items())
        },
        "resource_graph_sha256": resource_graph_sha256,
        "model_bindings": models,
        "shape_bindings": shapes,
        "node_classes_sha256": _digest(classes),
        "wan_decode_projection": wan_capacity.projection(preset, graph),
    }
    identity = dict(profile_identity)
    identity["submitted_graph_sha256"] = _digest(graph)
    identity["identity_sha256"] = _digest(profile_identity)
    return identity


def observe(studio):
    """Take one fresh admission snapshot; missing facts remain explicit."""
    physical = resource_probe.physical_memory()
    commit = host_memory.read()
    runtime = {"observed": False, "versions": {}, "devices": [], "unknown_reason": None}
    try:
        raw = studio._request(
            "/system_stats",
            timeout=3,
            base_url=getattr(studio, "comfy_url", None),
        )
        runtime.update(resource_probe.project_stats(raw), observed=True, unknown_reason=None)
    except Exception as exc:
        runtime["unknown_reason"] = "ComfyUI counters unavailable: " + type(exc).__name__
    device_index = (getattr(studio, "config", {}) or {}).get(
        "resource_admission_device_index", 0)
    vram = None
    vram_reason = runtime.get("unknown_reason")
    if type(device_index) is int and 0 <= device_index < len(runtime.get("devices") or []):
        device = runtime["devices"][device_index]
        # ComfyUI's vram_free is driver free plus torch's reserved-but-unused pool (model_management.get_free_memory);
        # torch_vram_free is only that pool (reserved minus active): near 0 when nothing is loaded or the pool is in use.
        # Taking the smaller of the two reported "no VRAM" on an empty 16 GB card (#306 live proof, 25 Sep 2026).
        free = _counter(device.get("vram_free_bytes"))
        if free is not None:
            vram, vram_reason = free, None
        else:
            vram_reason = "Selected device returned no valid free-VRAM counter"
    elif vram_reason is None:
        vram_reason = "Configured admission device is unavailable"
    return {
        "schema": "studio.resource-observation/v1",
        "observed_at": time.time(),
        "physical_ram": copy.deepcopy(physical),
        "windows_commit": copy.deepcopy(commit),
        "vram": {
            "available_bytes": vram,
            "device_index": device_index,
            "unknown_reason": vram_reason,
        },
        "runtime": runtime,
    }


def _profile(value, identity):
    required = {"schema", "identity_sha256", "basis", "source", "stages"}
    if not isinstance(value, dict) or value.get("schema") != PROFILE_SCHEMA:
        raise ValueError("Admission profile must use " + PROFILE_SCHEMA)
    if set(value) != required:
        raise ValueError("Admission profile has missing or unsupported fields")
    if value.get("identity_sha256") != identity["identity_sha256"]:
        raise ValueError("Admission profile identity does not match the exact workflow/runtime identity")
    basis = value.get("basis")
    if basis not in ("observed", "estimated"):
        raise ValueError("Admission profile basis must be observed or estimated")
    source = value.get("source")
    if (not isinstance(source, dict)
            or set(source) - {"receipt_sha256", "kind"}
            or not _HASH.fullmatch(str(source.get("receipt_sha256", "")))):
        raise ValueError("Admission profile requires a source receipt SHA-256")
    stages = value.get("stages")
    if not isinstance(stages, list) or not 1 <= len(stages) <= MAX_STAGES:
        raise ValueError("Admission profile needs 1 to 16 stages")
    normalized = []
    names = set()
    stage_required = {"name", *DIMENSIONS}
    stage_allowed = stage_required | {"note"}
    for stage in stages:
        if not isinstance(stage, dict) or set(stage) - stage_allowed:
            raise ValueError("Admission stage has unsupported fields")
        if stage_required - set(stage):
            raise ValueError("Admission stage must declare every resource dimension explicitly")
        name = stage.get("name")
        if (not isinstance(name, str) or not name.strip()
                or len(name) > 80 or name in names):
            raise ValueError("Admission stage names must be unique short text")
        names.add(name)
        record = {"name": name}
        for dimension in DIMENSIONS:
            amount = stage[dimension]
            if type(amount) is not int or amount < 0:
                raise ValueError("Admission stage resources must be non-negative integer bytes")
            record[dimension] = amount
        if isinstance(stage.get("note"), str):
            record["note"] = stage["note"][:300]
        normalized.append(record)
    result = {
        "schema": PROFILE_SCHEMA,
        "identity_sha256": identity["identity_sha256"],
        "basis": basis,
        "source": {
            "receipt_sha256": source["receipt_sha256"],
            "kind": str(source.get("kind", "local-observation"))[:80],
        },
        "stages": normalized,
    }
    result["profile_sha256"] = _digest(result, MAX_PROFILE_BYTES)
    return result


def profile_for(studio, identity):
    profiles = (getattr(studio, "config", {}) or {}).get(
        "resource_admission_profiles", {})
    if not isinstance(profiles, dict):
        raise ValueError("resource_admission_profiles must be an object")
    value = profiles.get(identity["identity_sha256"])
    return None if value is None else _profile(value, identity)


def _available(observation):
    return {
        "physical_ram_bytes": _counter(
            (observation.get("physical_ram") or {}).get("available_bytes")),
        "windows_commit_bytes": _counter(
            (observation.get("windows_commit") or {}).get("available_bytes")),
        "vram_bytes": _counter(
            (observation.get("vram") or {}).get("available_bytes")),
    }


def _unknown_reasons(observation):
    return {
        "physical_ram_bytes": (
            observation.get("physical_ram") or {}).get("unknown_reason"),
        "windows_commit_bytes": (
            observation.get("windows_commit") or {}).get("unknown_reason"),
        "vram_bytes": (observation.get("vram") or {}).get("unknown_reason"),
    }


def _definitive_terminal(job):
    if (not isinstance(job, dict)
            or job.get("status") not in TERMINAL_STATUSES
            or job.get("pending_submission")):
        return False
    submissions = job.get("submissions") or []
    return all(
        isinstance(item, dict) and item.get("status") in ("completed", "failed")
        for item in submissions
    )


def _validated_receipt(value, owner_id):
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        raise ValueError("Stored resource admission receipt is invalid")
    if value.get("owner_id") != owner_id:
        raise ValueError("Stored resource admission receipt owner does not match the job")
    claimed = value.get("receipt_sha256")
    unsigned = {key: item for key, item in value.items() if key != "receipt_sha256"}
    if not isinstance(claimed, str) or not _HASH.fullmatch(claimed) or _digest(unsigned) != claimed:
        raise ValueError("Stored resource admission receipt SHA-256 is invalid")
    state = value.get("state")
    if state in ACTIVE_STATES:
        identity_sha256 = value.get("identity_sha256")
        if not isinstance(identity_sha256, str) or not _HASH.fullmatch(identity_sha256):
            raise ValueError("Stored active resource admission identity is invalid")
        if state == "retained":
            retained_identity = value.get("retained_identity_sha256")
            if retained_identity is not None and (
                    not isinstance(retained_identity, str)
                    or not _HASH.fullmatch(retained_identity)):
                raise ValueError("Stored retained resource admission identity is invalid")
        reservation = value.get("reservation")
        if not isinstance(reservation, dict) or set(reservation) != set(DIMENSIONS):
            raise ValueError("Stored active resource admission reservation is invalid")
        for dimension in DIMENSIONS:
            if type(reservation[dimension]) is not int or reservation[dimension] < 0:
                raise ValueError("Stored active resource admission reservation is invalid")
    return copy.deepcopy(value)


class ReservationLedger:
    """Atomically check and reserve Studio-declared capacity across local callers."""
    def __init__(self):
        self.lock = threading.RLock()
        self.reservations = {}

    def restore(self, owner_id, record):
        validated = _validated_receipt(record, owner_id)
        state = validated.get("state")
        if state not in ACTIVE_STATES:
            return
        values = {
            key: validated["reservation"][key]
            for key in DIMENSIONS
        }
        active_identity = (
            validated.get("retained_identity_sha256")
            or validated["identity_sha256"]
        )
        with self.lock:
            existing = self.reservations.get(owner_id)
            candidate = {
                "identity_sha256": active_identity,
                "reservation": values,
            }
            if existing is not None:
                if existing != candidate:
                    raise ValueError("Restored resource admission reservation disagrees with memory")
                return
            self.reservations[owner_id] = candidate

    def release(self, owner_id):
        with self.lock:
            return self.reservations.pop(owner_id, None)

    def reservation_for(self, owner_id):
        with self.lock:
            return copy.deepcopy(self.reservations.get(owner_id))

    def snapshot(self, exclude=None):
        with self.lock:
            totals = {key: 0 for key in DIMENSIONS}
            owners = []
            for owner_id, record in self.reservations.items():
                if owner_id == exclude:
                    continue
                owners.append(owner_id)
                for key in DIMENSIONS:
                    totals[key] += record["reservation"][key]
            return {"owners": sorted(owners), "totals": totals}

    def admit(self, owner_id, identity, profile, observation, publish=None):
        with self.lock:
            previous = self.reservations.get(owner_id)
            if (previous is not None
                    and previous.get("identity_sha256") != identity["identity_sha256"]):
                raise ValueError("An existing reservation has a different workflow identity")
            before = self.snapshot(exclude=owner_id)
            available = _available(observation)
            reasons = _unknown_reasons(observation)
            evaluations = []
            has_unknown = False
            has_unsafe = False
            for stage in profile["stages"]:
                dimensions = {}
                for dimension in DIMENSIONS:
                    required = stage[dimension]
                    current = available[dimension]
                    effective = (
                        None if current is None
                        else max(0, current - before["totals"][dimension])
                    )
                    if required == 0:
                        state = "not_required"
                    elif effective is None:
                        state = "unknown"
                        has_unknown = True
                    elif effective < required:
                        state = "unsafe"
                        has_unsafe = True
                    else:
                        state = "safe"
                    dimensions[dimension] = {
                        "required_bytes": required,
                        "observed_available_bytes": current,
                        "reserved_elsewhere_bytes": before["totals"][dimension],
                        "effective_available_bytes": effective,
                        "state": state,
                        "unknown_reason": reasons[dimension] if state == "unknown" else None,
                    }
                evaluations.append({"stage": stage["name"], "dimensions": dimensions})
            if has_unknown:
                decision = "unknown"
            elif has_unsafe:
                decision = "observed_unsafe"
            else:
                decision = (
                    "observed_safe"
                    if profile["basis"] == "observed"
                    else "estimated_safe"
                )
            safe = decision in ("observed_safe", "estimated_safe")
            reservation = {
                dimension: max(stage[dimension] for stage in profile["stages"])
                for dimension in DIMENSIONS
            }
            retained = previous if not safe else None
            receipt = {
                "schema": SCHEMA,
                "owner_id": owner_id,
                "kind": "generation",
                "recorded_at": time.time(),
                "identity_sha256": identity["identity_sha256"],
                "identity": identity,
                "profile_sha256": profile["profile_sha256"],
                "profile_basis": profile["basis"],
                "profile_source": profile["source"],
                "observation": observation,
                "reservations_before": before,
                "stage_evaluations": evaluations,
                "decision": decision,
                "reservation": (
                    reservation if safe
                    else copy.deepcopy((retained or {}).get("reservation"))
                ),
                "state": "reserved" if safe else "retained" if retained else "refused",
                "contract": "Studio concurrency reservation; not a physical-memory guarantee",
            }
            receipt["receipt_sha256"] = _digest(receipt)
            if publish is not None:
                if not callable(publish):
                    raise ValueError("Resource admission receipt publisher must be callable")
                publish(copy.deepcopy(receipt))
            if safe:
                self.reservations[owner_id] = {
                    "identity_sha256": identity["identity_sha256"],
                    "reservation": reservation,
                }
            return receipt


class AdmissionController:
    def __init__(self, studio, *, observer=observe, ledger=None):
        self.studio = studio
        self.observer = observer
        self.ledger = ledger or ReservationLedger()
        self._restored = False

    @staticmethod
    def _ensure_record_capacity(job):
        history = job.get("resource_admission")
        if history is None:
            return
        if not isinstance(history, list):
            raise ValueError("Stored resource admission history is invalid")
        if len(history) >= MAX_RECEIPTS:
            raise ValueError("Resource admission receipt retention is full")

    def _record(self, job, receipt):
        self._ensure_record_capacity(job)
        history = job.setdefault("resource_admission", [])
        candidate = _validated_receipt(receipt, str(job.get("id", "")))
        _canonical(candidate)
        history.append(candidate)

    def _restore(self):
        if self._restored:
            return
        for owner_id, job in list(getattr(self.studio, "jobs", {}).items()):
            history = job.get("resource_admission") if isinstance(job, dict) else None
            if not isinstance(history, list) or not history:
                continue
            last = _validated_receipt(history[-1], owner_id)
            if last.get("state") in ACTIVE_STATES and not _definitive_terminal(job):
                self.ledger.restore(owner_id, last)
        self._restored = True

    def reconcile(self):
        self._restore()
        for owner_id, job in list(getattr(self.studio, "jobs", {}).items()):
            history = job.get("resource_admission") if isinstance(job, dict) else None
            if not isinstance(history, list) or not history or not _definitive_terminal(job):
                continue
            last = _validated_receipt(history[-1], owner_id)
            if last.get("state") not in ACTIVE_STATES:
                continue
            active = self.ledger.reservation_for(owner_id)
            release_identity = (
                (active or {}).get("identity_sha256")
                or last.get("retained_identity_sha256")
                or last.get("identity_sha256")
            )
            receipt = {
                "schema": SCHEMA,
                "owner_id": owner_id,
                "kind": "release",
                "recorded_at": time.time(),
                "identity_sha256": release_identity,
                "decision": "released",
                "state": "released",
                "reservation": (
                    (active or {}).get("reservation") or last.get("reservation")
                ),
                "basis": "definitive_terminal_job_state",
            }
            receipt["receipt_sha256"] = _digest(receipt)
            self._record(job, receipt)
            saver = getattr(self.studio, "_save", None)
            try:
                if callable(saver):
                    saver(job)
            except Exception:
                history.pop()
                raise
            self.ledger.release(owner_id)

    def admit(self, job, preset, graph):
        self.reconcile()
        self._ensure_record_capacity(job)
        observation = self.observer(self.studio)
        identity = workflow_identity(
            self.studio,
            preset,
            graph,
            observation.get("runtime") or {},
        )
        owner_id = str(job.get("id", ""))

        def refusal(reason):
            retained = self.ledger.reservation_for(owner_id)
            receipt = {
                "schema": SCHEMA,
                "owner_id": owner_id,
                "kind": "generation",
                "recorded_at": time.time(),
                "identity_sha256": identity["identity_sha256"],
                "identity": identity,
                "observation": observation,
                "decision": "unknown",
                "state": "retained" if retained else "refused",
                "reservation": (retained or {}).get("reservation"),
                "retained_identity_sha256": (retained or {}).get("identity_sha256"),
                "reason": reason,
            }
            receipt["receipt_sha256"] = _digest(receipt)
            self._record(job, receipt)
            return receipt

        try:
            profile = profile_for(self.studio, identity)
        except ValueError as exc:
            receipt = refusal(str(exc))
            raise AdmissionError(
                str(exc) + ". No prompt was submitted.", receipt) from exc
        if profile is None:
            receipt = refusal("No exact admission profile")
            raise AdmissionError(
                "Stage-aware resource admission is unknown for exact identity "
                + identity["identity_sha256"]
                + ". Record a bounded measured profile before retrying. "
                "No prompt was submitted.",
                receipt,
            )
        try:
            receipt = self.ledger.admit(
                owner_id,
                identity,
                profile,
                observation,
                publish=lambda candidate: self._record(job, candidate),
            )
        except ValueError as exc:
            receipt = refusal(str(exc))
            raise AdmissionError(
                str(exc)
                + ". Existing capacity remains retained; no prompt was submitted.",
                receipt,
            ) from exc
        if receipt["decision"] in ("observed_safe", "estimated_safe"):
            return copy.deepcopy(receipt)
        failing = next((
            item for item in receipt["stage_evaluations"]
            if any(
                value["state"] in ("unknown", "unsafe")
                for value in item["dimensions"].values()
            )
        ), None)
        if receipt["decision"] == "unknown":
            detail = "required resource counters are unavailable"
        else:
            bad = next((
                name for name, value in failing["dimensions"].items()
                if value["state"] == "unsafe"
            ), "resource")
            detail = (
                bad.replace("_bytes", "").replace("_", " ")
                + " headroom is below the profiled requirement"
            )
        raise AdmissionError(
            "Resource admission refused at stage "
            + str((failing or {}).get("stage", "unknown"))
            + ": " + detail + ". No prompt was submitted.",
            receipt,
        )


def controller_for(studio):
    controller = getattr(studio, "_stage_resource_admission", None)
    if controller is None:
        controller = AdmissionController(studio)
        studio._stage_resource_admission = controller
    return controller


def pre_submit(studio, job, preset, graph):
    """Run after queue wait and immediately before the existing submission intent."""
    config = getattr(studio, "config", {}) or {}
    if config.get("enforce_stage_resource_admission") is not True:
        return None
    if not isinstance(job, dict) or not isinstance(job.get("id"), str):
        raise ValueError("Admission requires a durable job identity")
    return controller_for(studio).admit(job, preset, graph)
