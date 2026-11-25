#!/usr/bin/env python3
"""Bounded, one-shot owner adapter for the existing Studio Production API.

Python 3.12+, standard library only. This is not a generation worker. It only
prepares Studio comparison projects, explicitly starts each once, and observes.
An unconfirmed request or abandoned lock is never automatically retried/reclaimed.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import http.client
import ipaddress
import json
import math
import os
from pathlib import Path, PureWindowsPath
import re
import sys
import time
from urllib.parse import urlsplit
import uuid


MAX_PLAN_BYTES = 2 * 1024 * 1024
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_JOURNAL_BYTES = 16 * 1024 * 1024
MAX_EVIDENCE_BYTES = 512 * 1024 * 1024
MAX_RECEIPTS = 12000
SHA = re.compile(r"[0-9a-f]{64}\Z")
PROJECT_ID = re.compile(r"[0-9a-f]{32}\Z")
CHUNK_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")
UPLOAD = re.compile(r"[0-9a-f]{32}_[A-Za-z0-9._-]+\.(?:png|jpg|webp)\Z")
ROLES = {"identity", "pose", "style", "costume", "composition", "geometry", "motion", "mask"}
LIVE = {"queued", "running", "observing"}
SUCCESS = {"awaiting_review", "reviewed", "completed"}
STOP = {"failed", "cancelled", "stopped", "interrupted", "uncertain"}
KNOWN = {"planned"} | LIVE | SUCCESS | STOP


class RunError(Exception):
    def __init__(self, message, *, uncertain=False):
        super().__init__(message)
        self.uncertain = uncertain


def require(condition, message, *, uncertain=False):
    if not condition:
        raise RunError(message, uncertain=uncertain)


def canonical(value, *, ascii=False):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=ascii, allow_nan=False).encode("utf-8")


def digest(value, *, ascii=False):
    return hashlib.sha256(canonical(value, ascii=ascii)).hexdigest()


def decode_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key: " + key[:100])
            result[key] = value
        return result

    def constant(_value):
        raise ValueError("Non-finite JSON number")

    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise RunError("Invalid JSON: " + str(exc)[:300]) from exc


def read_json(path, maximum):
    require(path.is_file() and not path.is_symlink(), "Expected a regular JSON file: " + str(path))
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    require(len(raw) <= maximum, "JSON input exceeds its byte limit")
    return decode_json(raw)


def text_value(value, maximum, label, *, empty=False):
    require(isinstance(value, str) and (empty or bool(value.strip())) and len(value) <= maximum,
            label + " must be bounded text")
    require("\x00" not in value, label + " contains a NUL")
    return value


def integer(value, low, high, label):
    require(type(value) is int and low <= value <= high, f"{label} must be an integer from {low} to {high}")
    return value


def hex_sha(value, label):
    require(isinstance(value, str) and bool(SHA.fullmatch(value)), label + " must be a lowercase SHA-256")
    return value


def model_file(value, *, expected=False):
    require(isinstance(value, str) and 1 <= len(value) <= 512 and not any(ord(c) < 32 for c in value),
            "Model filename must be bounded relative text", uncertain=not expected)
    normalized = value.replace("\\", "/")
    require(":" not in normalized and all(part not in {"", ".", ".."} for part in normalized.split("/"))
            and (not expected or normalized == value), "Model filenames must be normalized relative POSIX paths", uncertain=not expected)
    return normalized


def checked_url(value):
    """Numeric loopback only: no DNS, credentials, URL paths, redirects or proxy."""
    require(isinstance(value, str) and len(value) <= 200 and not any(c.isspace() for c in value), "Invalid loopback URL")
    try:
        parsed = urlsplit(value)
        address = ipaddress.ip_address(parsed.hostname or "")
        port = parsed.port
    except ValueError as exc:
        raise RunError("Use an explicit numeric loopback IP and port") from exc
    require(parsed.scheme == "http" and address.is_loopback and port is not None and 1 <= port <= 65535
            and parsed.username is None and parsed.password is None and not parsed.path and not parsed.query
            and not parsed.fragment, "Use only http://<numeric-loopback-IP>:<port>, without any URL suffix")
    host = f"[{address}]" if address.version == 6 else str(address)
    normalized = f"http://{host}:{port}"
    require(value == normalized, "Loopback URL must use canonical IP and port spelling")
    return str(address), port


def validate_plan(plan):
    require(isinstance(plan, dict) and plan.get("schema") == "p35-owner-run/v1", "Unsupported owner-run plan schema")
    plan_id = hex_sha(plan.get("plan_id"), "plan_id")
    require(plan_id == digest({key: value for key, value in plan.items() if key != "plan_id"}), "Plan hash does not match its reviewed content")
    campaign = hex_sha(plan.get("campaign_id"), "campaign_id")
    require(plan.get("backend_id") == "primary", "Only the explicitly selected primary backend is supported")
    identity = plan.get("expected_identity")
    require(isinstance(identity, dict) and set(identity) == {"app", "workspace", "version"}
            and identity.get("app") == "local-asset-studio" and identity.get("version") == "production-workspace-1",
            "Pin the complete documented Studio identity")
    workspace = text_value(identity.get("workspace"), 2048, "expected workspace")
    require(Path(workspace).is_absolute() or PureWindowsPath(workspace).is_absolute(), "Expected workspace must be an absolute owner-selected path")
    max_attempts = integer(plan.get("max_attempts"), 1, 240, "max_attempts")
    max_seconds = integer(plan.get("max_seconds"), 60, 14400, "max_seconds")
    chunks = plan.get("chunks")
    require(isinstance(chunks, list) and 1 <= len(chunks) <= 120, "Use one to 120 bounded chunks")
    identifiers = set()
    total = 0
    for chunk in chunks:
        require(isinstance(chunk, dict), "Each chunk must be an object")
        identifier = chunk.get("id")
        require(isinstance(identifier, str) and CHUNK_ID.fullmatch(identifier) and identifier not in identifiers,
                "Chunk IDs must be unique safe identifiers")
        identifiers.add(identifier)
        name = text_value(chunk.get("name"), 120, "chunk name")
        require(name == f"P35 {campaign[:16]} {identifier}", "Chunk names must contain the frozen campaign prefix and chunk ID")
        payload = chunk.get("payload")
        require(isinstance(payload, dict) and set(payload) == {"name", "recipe", "variants", "max_seconds", "max_generations"},
                "Only the bounded Studio comparison-create payload is supported")
        require(payload.get("name") == name, "Payload and chunk names differ")
        integer(payload.get("max_seconds"), 60, max_seconds, "chunk max_seconds")
        variants = payload.get("variants")
        require(isinstance(variants, list) and len(variants) in (2, 3), "Each route/case must have two or three explicit seed variants")
        expected_graphs = chunk.get("expected_graph_sha256")
        require(isinstance(expected_graphs, list) and len(expected_graphs) == len(variants),
                "Pin one expected_graph_sha256 per ordered seed variant")
        for expected_graph in expected_graphs:
            hex_sha(expected_graph, "expected graph sha256")
        require(len(set(expected_graphs)) == len(expected_graphs), "Expected variant graphs must be distinct")
        models = chunk.get("expected_models")
        require(isinstance(models, list) and 1 <= len(models) <= 64, "Pin every expected model file, hash and byte count")
        model_names = set()
        for model in models:
            require(isinstance(model, dict) and set(model) == {"file", "sha256", "bytes"}, "Expected models need exactly file, sha256 and bytes")
            model_name = model_file(model.get("file"), expected=True)
            require(model_name not in model_names, "Expected model files must be unique")
            model_names.add(model_name)
            hex_sha(model.get("sha256"), "model sha256")
            integer(model.get("bytes"), 1, 2**63 - 1, "model bytes")
        require(type(payload.get("max_generations")) is int and payload["max_generations"] == len(variants), "Generation allowance must equal this chunk's seed count")
        seeds, labels = set(), set()
        for variant in variants:
            require(isinstance(variant, dict) and set(variant) == {"label", "controls"}, "Variants may only carry a label and seed override")
            label = text_value(variant.get("label"), 120, "variant label")
            require(label == label.strip() and label not in labels, "Variant labels must be distinct and trimmed")
            labels.add(label)
            controls = variant.get("controls")
            require(isinstance(controls, dict) and set(controls) == {"seed"}, "Only seed may vary within a chunk")
            seed = integer(controls["seed"], 0, 2**63 - 1, "seed")
            require(seed not in seeds, "Seeds must be distinct within each chunk")
            seeds.add(seed)
        recipe = payload.get("recipe")
        require(isinstance(recipe, dict) and {"preset_id", "controls", "references", "expected_template_sha256"} <= set(recipe)
                and set(recipe) <= {"preset_id", "controls", "references", "parent_assets", "expected_template_sha256"},
                "Use a pinned catalog recipe, never a workflow or executable graph")
        preset = text_value(recipe.get("preset_id"), 120, "preset_id")
        require(re.fullmatch(r"[A-Za-z0-9_-]+", preset), "Invalid preset identifier")
        hex_sha(recipe.get("expected_template_sha256"), "expected_template_sha256")
        controls = recipe.get("controls")
        require(isinstance(controls, dict) and len(controls) <= 64, "Recipe controls must be a bounded object")
        for key, value in controls.items():
            require(isinstance(key, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", key), "Invalid control name")
            require(type(value) in (str, int, float, bool), "Controls must be scalar values")
            if isinstance(value, str):
                text_value(value, 8000, "control", empty=True)
            if isinstance(value, float):
                require(math.isfinite(value), "Controls must be finite")
        parents = recipe.get("parent_assets", [])
        require(isinstance(parents, list) and len(parents) <= 8 and all(isinstance(p, str) and 1 <= len(p) <= 128 for p in parents), "Use at most eight explicit parent asset IDs")
        expected = chunk.get("expected_inputs")
        require(isinstance(expected, list) and len(expected) <= 9, "expected_inputs must list all pinned uploaded inputs")
        expected_map = {}
        for record in expected:
            require(isinstance(record, dict) and set(record) == {"file", "sha256"}, "Each expected input needs exactly file and sha256")
            name = record.get("file")
            require(isinstance(name, str) and UPLOAD.fullmatch(name) and name not in expected_map, "Expected inputs must be unique Studio upload basenames")
            expected_map[name] = hex_sha(record.get("sha256"), "input sha256")
        referenced = set()
        for field in ("reference", "last_reference"):
            if field in controls:
                name = controls[field]
                require(isinstance(name, str) and name in expected_map, "Every named reference control needs a pinned expected input")
                referenced.add(name)
        refs = recipe.get("references")
        require(isinstance(refs, list) and len(refs) <= 8, "Use at most eight explicit reference slots")
        pruned = chunk.get("expected_pruned_reference_slots", [])
        require(isinstance(pruned, list) and len(refs) + len(pruned) <= 8, "Declare only bounded native trailing empty slots")
        for index, entry in enumerate(pruned, start=len(refs) + 1):
            require(isinstance(entry, dict) and set(entry) == {"slot", "role"} and type(entry.get("slot")) is int
                    and entry["slot"] == index and entry.get("role") in ROLES,
                    "Expected pruned slots must be contiguous native trailing slots with explicit roles")
        for reference in refs:
            require(isinstance(reference, dict), "Reference slots must be objects")
            name = reference.get("file")
            if name is None:
                require(not reference.get("sha256"), "An empty reference cannot carry a file hash")
                continue
            require(isinstance(name, str) and name in expected_map and reference.get("sha256") == expected_map[name], "Every reference slot needs its expected input hash")
            require(reference.get("role") in ROLES, "Every filled reference needs an explicit supported role")
            for field in ("contribution", "avoid"):
                text_value(reference.get(field, ""), 1500, "reference guidance", empty=True)
            referenced.add(name)
        require(referenced == set(expected_map), "Expected inputs must exactly cover explicit reference slots and named reference controls")
        total += len(variants)
    require(total <= max_attempts, "Selected chunks exceed the reviewed attempt cap")
    return plan


def sync_directory(path):
    # Windows uses write-through replacement below; POSIX also flushes directory entries.
    if os.name != "nt":
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def exclusive_write(path, raw):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    sync_directory(path.parent)


def atomic_write(path, raw):
    require(not path.is_symlink(), "Refusing a linked runtime file")
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    exclusive_write(temporary, raw)
    if os.name == "nt":
        import ctypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        replace = kernel.MoveFileExW
        replace.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
        replace.restype = ctypes.c_int
        if not replace(str(temporary), str(path), 0x1 | 0x8):  # REPLACE_EXISTING | WRITE_THROUGH
            raise ctypes.WinError(ctypes.get_last_error())
    else:
        os.replace(temporary, path)
    sync_directory(path.parent)


class Store:
    def __init__(self, runtime, plan_id):
        runtime = runtime.absolute()
        require(runtime.name == ".runtime", "Runtime receipts must be kept in an explicit .runtime directory")
        for path in (runtime, *runtime.parents):
            require(not path.is_symlink(), "Refusing a linked runtime directory")
        self.directory = runtime / "p35-owner-runs" / plan_id
        self.journal_path = self.directory / "journal.json"
        self.lock_path = self.directory / "run.lock"
        self.evidence = self.directory / "evidence"
        for path in (self.directory.parent, self.directory, self.evidence):
            require(not path.is_symlink(), "Refusing a linked runtime directory")
        self.evidence.mkdir(parents=True, exist_ok=True)
        self.token = None
        files = list(self.evidence.iterdir())
        require(all(p.is_file() and not p.is_symlink() for p in files), "Evidence directory contains a non-regular entry")
        self.evidence_bytes = sum(p.stat().st_size for p in files)
        self.receipts = sum(p.name.endswith(".receipt.json") for p in files)

    def acquire(self, plan_id):
        token = uuid.uuid4().hex
        try:
            exclusive_write(self.lock_path, canonical({"pid": os.getpid(), "token": token, "plan_id": plan_id, "created_at": time.time()}))
        except FileExistsError as exc:
            raise RunError("Run lock already exists. Use --status for read-only inspection; no automatic lock reclaim or retry is permitted.", uncertain=True) from exc
        self.token = token

    def release(self):
        lock = read_json(self.lock_path, 4096)
        require(self.token is not None and lock.get("token") == self.token, "Lock ownership changed; retaining it for inspection", uncertain=True)
        self.lock_path.unlink()
        sync_directory(self.directory)
        self.token = None

    def save(self, journal, *, initial=False):
        raw = canonical(journal)
        require(len(raw) <= MAX_JOURNAL_BYTES, "Journal byte limit reached", uncertain=True)
        if initial:
            exclusive_write(self.journal_path, raw)
        else:
            atomic_write(self.journal_path, raw)

    def capacity(self):
        require(self.receipts < MAX_RECEIPTS and self.evidence_bytes + MAX_RESPONSE_BYTES + 65536 <= MAX_EVIDENCE_BYTES,
                "Evidence storage limit reached; inspect retained receipts", uncertain=True)

    def record(self, metadata, raw):
        self.capacity()
        identifier = f"{time.time_ns()}-{uuid.uuid4().hex}"
        body_path = self.evidence / (identifier + ".body")
        receipt_path = self.evidence / (identifier + ".receipt.json")
        exclusive_write(body_path, raw)
        metadata.update(body_file=body_path.name, body_bytes=len(raw), body_sha256=hashlib.sha256(raw).hexdigest())
        serialized = canonical(metadata)
        exclusive_write(receipt_path, serialized)
        self.evidence_bytes += len(raw) + len(serialized)
        self.receipts += 1
        return str(receipt_path.relative_to(self.directory))


class API:
    def __init__(self, base_url, store, timeout, prepare_timeout=600):
        self.host, self.port = checked_url(base_url)
        require(math.isfinite(timeout) and 0.01 <= timeout <= 60, "request-timeout must be 0.01..60 seconds")
        require(math.isfinite(prepare_timeout) and 0.01 <= prepare_timeout <= 1800, "prepare-timeout must be 0.01..1800 seconds")
        self.base_url, self.store, self.timeout = base_url, store, timeout
        self.prepare_timeout = prepare_timeout

    def request(self, method, path, payload=None, *, timeout=None):
        require(method in ("GET", "POST") and path.startswith("/api/") and not any(c in path for c in "?#\r\n"), "Unsupported API request")
        self.store.capacity()
        body = None if payload is None else canonical(payload)
        require(body is None or len(body) <= MAX_PLAN_BYTES, "Request body exceeds byte limit")
        # Production create hashes every pinned model for every seed before its reply.
        # Its separately selected limit must not weaken the short start/observation bound.
        request_limit = self.prepare_timeout if method == "POST" and path == "/api/production" else self.timeout
        duration = min(request_limit, timeout) if timeout is not None else request_limit
        require(duration > 0, "Observation time allowance exhausted", uncertain=True)
        connection = http.client.HTTPConnection(self.host, self.port, timeout=duration)
        metadata = {"at": time.time(), "method": method, "path": path, "status": None, "headers": [], "complete": False,
                    "timeout_seconds": duration}
        raw = bytearray()
        error = None
        started = time.monotonic()
        try:
            # http.client connects directly; it never reads proxy environment variables or follows redirects.
            headers = {"Accept": "application/json", "Origin": self.base_url, "Connection": "close"}
            if body is not None:
                headers["Content-Type"] = "application/json"
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            metadata.update(status=response.status, headers=response.getheaders())
            if response.length is not None and response.length > MAX_RESPONSE_BYTES:
                raise RunError("HTTP response exceeds byte limit")
            while True:
                require(time.monotonic() - started < duration, "HTTP response exceeded its time limit")
                part = response.read1(min(65536, MAX_RESPONSE_BYTES + 1 - len(raw)))
                if not part:
                    break
                raw.extend(part)
                require(len(raw) <= MAX_RESPONSE_BYTES, "HTTP response exceeds byte limit")
            require(response.length in (None, 0), "HTTP response ended before its declared length")
            metadata["complete"] = True
        except (OSError, http.client.HTTPException, RunError) as exc:
            error = str(exc) or type(exc).__name__
            metadata["error"] = error[:1000]
        finally:
            connection.close()
        receipt = self.store.record(metadata, bytes(raw[:MAX_RESPONSE_BYTES]))
        if error:
            raise RunError("Unconfirmed HTTP response: " + error[:400] + "; receipt " + receipt, uncertain=True)
        status = metadata["status"]
        require(not 300 <= status < 400, "HTTP redirect refused; receipt " + receipt, uncertain=method == "POST")
        expected = 200 if method == "GET" else 201 if path == "/api/production" else 202
        require(status == expected, f"HTTP {status} instead of {expected}; receipt {receipt}", uncertain=method == "POST")
        content_types = [value.lower().split(";", 1)[0].strip() for key, value in metadata["headers"] if key.lower() == "content-type"]
        require(content_types == ["application/json"], "Expected one JSON Content-Type; receipt " + receipt, uncertain=True)
        try:
            value = decode_json(bytes(raw))
        except RunError as exc:
            raise RunError(str(exc) + "; receipt " + receipt, uncertain=True) from exc
        return value, receipt


def prompt_ids(value):
    result = set()
    def visit(item, depth=0):
        require(depth <= 64, "Response nesting exceeds limit", uncertain=True)
        if isinstance(item, dict):
            for key, child in item.items():
                if key == "prompt_id" and child is not None:
                    require(isinstance(child, str) and 1 <= len(child) <= 512, "Malformed prompt ID", uncertain=True)
                    result.add(child)
                elif key == "prompt_ids":
                    require(isinstance(child, list) and len(child) <= 240 and all(isinstance(p, str) and 1 <= len(p) <= 512 for p in child), "Malformed prompt IDs", uncertain=True)
                    result.update(child)
                else:
                    visit(child, depth + 1)
        elif isinstance(item, list):
            for child in item:
                visit(child, depth + 1)
    visit(value)
    return sorted(result)


def validate_project(project, chunk, backend, *, full):
    require(isinstance(project, dict) and isinstance(project.get("id"), str) and PROJECT_ID.fullmatch(project["id"]), "Malformed Studio project identity", uncertain=True)
    require(project.get("name") == chunk["name"] and project.get("kind") == "comparison", "Studio project differs from the reviewed chunk", uncertain=True)
    state = project.get("state")
    require(isinstance(state, dict) and state.get("status") in KNOWN and isinstance(state.get("attempts"), dict)
            and type(state.get("stop_requested")) is bool, "Malformed or unknown Studio project state", uncertain=True)
    count = len(chunk["payload"]["variants"])
    require(set(state["attempts"]) <= {str(i) for i in range(count)} and all(isinstance(v, dict) for v in state["attempts"].values()), "Unexpected stage attempts", uncertain=True)
    budget = project.get("budget")
    require(isinstance(budget, dict) and type(budget.get("allowance")) is int and budget["allowance"] == count
            and type(budget.get("reserved")) is int and 0 <= budget["reserved"] <= count, "Studio budget differs from the bounded plan", uncertain=True)
    stages = project.get("stages")
    require(isinstance(stages, list) and len(stages) == count, "Unexpected Studio stage count", uncertain=True)
    for index, stage in enumerate(stages):
        require(isinstance(stage, dict) and stage.get("operation") == "comfy.generate.v1"
                and stage.get("attempt") == state["attempts"].get(str(index), {}), "Malformed stage receipt", uncertain=True)
    status = state["status"]
    if status == "planned":
        require(not state["attempts"] and budget["reserved"] == 0 and all(stage.get("job") is None for stage in stages), "Planned project already has execution evidence", uncertain=True)
    if status in SUCCESS:
        require(budget["reserved"] == count, "Completed project lacks its reservation receipt", uncertain=True)
        for stage in stages:
            attempt, job = stage["attempt"], stage.get("job")
            require(attempt.get("status") == "completed" and isinstance(job, dict) and job.get("status") == "completed"
                    and job.get("id") == attempt.get("job_id") and job.get("project_id") == project["id"]
                    and type(job.get("batch_count")) is int and job["batch_count"] == 1
                    and len(prompt_ids(job)) == 1 and isinstance(job.get("prompt_ids"), list) and len(job["prompt_ids"]) == 1
                    and job["prompt_ids"] == attempt.get("prompt_ids"),
                    "Completion lacks a matching owned single-image job, attempt or prompt receipt", uncertain=True)
    prompt_ids(project)
    if not full:
        return "completed" if status in SUCCESS else status
    plan = project.get("plan")
    require(isinstance(plan, dict) and plan.get("sha256") == project.get("plan_sha256")
            and plan.get("sha256") == digest({key: value for key, value in plan.items() if key != "sha256"}, ascii=True),
            "Studio full plan hash is inconsistent", uncertain=True)
    payload = chunk["payload"]
    expected_recipe = dict(copy.deepcopy(payload["recipe"]), batch_count=1)
    require(plan.get("kind") == "comparison" and plan.get("name") == chunk["name"]
            and plan.get("recipe") == expected_recipe and plan.get("max_seconds") == payload["max_seconds"]
            and plan.get("parent_project") is None and plan.get("repair_allowance") == 0,
            "Prepared recipe or time budget differs from the reviewed payload", uncertain=True)
    bundle = plan.get("bundle")
    require(isinstance(bundle, dict) and bundle.get("comfy_url") == backend["url"] and bundle.get("comfy_root") == backend["root"],
            "Prepared plan belongs to a different backend", uncertain=True)
    models = bundle.get("models")
    require(isinstance(models, list) and 1 <= len(models) <= 64, "Malformed or missing prepared model evidence", uncertain=True)
    actual_models = {}
    for record in models:
        require(isinstance(record, dict) and isinstance(record.get("sha256"), str) and SHA.fullmatch(record["sha256"])
                and type(record.get("bytes")) is int and 1 <= record["bytes"] <= 2**63 - 1,
                "Malformed prepared model hash or byte count", uncertain=True)
        name = model_file(record.get("file"))
        fingerprint = (record["sha256"], record["bytes"])
        require(name not in actual_models or actual_models[name] == fingerprint, "Conflicting prepared model fingerprints", uncertain=True)
        actual_models[name] = fingerprint
    require(actual_models == {record["file"]: (record["sha256"], record["bytes"]) for record in chunk["expected_models"]},
            "Prepared model files, hashes or byte counts differ from the reviewed pins", uncertain=True)
    inputs = bundle.get("inputs")
    require(isinstance(inputs, list) and len(inputs) <= 24, "Malformed prepared input evidence", uncertain=True)
    actual_inputs = {}
    for record in inputs:
        require(isinstance(record, dict) and isinstance(record.get("path"), str) and isinstance(record.get("sha256"), str), "Malformed prepared input evidence", uncertain=True)
        name = record["path"].replace("\\", "/").rsplit("/", 1)[-1]
        require(name not in actual_inputs or actual_inputs[name] == record["sha256"], "Conflicting prepared input hashes", uncertain=True)
        actual_inputs[name] = record["sha256"]
    require(actual_inputs == {record["file"]: record["sha256"] for record in chunk["expected_inputs"]}, "Prepared input hashes differ from the reviewed uploaded references", uncertain=True)
    prepared = plan.get("stages")
    require(isinstance(prepared, list) and len(prepared) == count, "Prepared stage count differs", uncertain=True)
    for stage, variant, expected_graph in zip(prepared, payload["variants"], chunk["expected_graph_sha256"]):
        request = stage.get("request") if isinstance(stage, dict) else None
        require(isinstance(request, dict) and stage.get("operation") == "comfy.generate.v1"
                and request.get("preset_id") == expected_recipe["preset_id"]
                and request.get("expected_template_sha256") == expected_recipe["expected_template_sha256"]
                and request.get("controls") == dict(expected_recipe["controls"], **variant["controls"])
                and request.get("batch_count") == 1 and request.get("parent_assets", []) == expected_recipe.get("parent_assets", []),
                "Prepared stage controls or template differ", uncertain=True)
        graph = stage.get("graph")
        require(isinstance(graph, dict) and bool(graph) and stage.get("graph_sha256") == expected_graph
                and expected_graph == digest(graph, ascii=True), "Prepared graph hash differs from the reviewed seed variant", uncertain=True)
        references = request.get("references")
        pruned = chunk.get("expected_pruned_reference_slots", [])
        require(isinstance(references, list) and len(references) == len(expected_recipe["references"]) + len(pruned), "Prepared reference slots differ", uncertain=True)
        for index, (actual, expected) in enumerate(zip(references, expected_recipe["references"]), start=1):
            require(isinstance(actual, dict), "Malformed prepared reference", uncertain=True)
            if expected.get("file") is None:
                require(actual.get("file") is None and actual.get("pruned") is True, "Empty reference slot was not pruned", uncertain=True)
            else:
                require(actual.get("slot") == index and all(actual.get(key) == expected.get(key) for key in ("file", "sha256", "role")),
                        "Prepared reference provenance or order differs", uncertain=True)
        for actual, expected in zip(references[len(expected_recipe["references"]):], pruned):
            require(actual == {"slot": expected["slot"], "role": expected["role"], "file": None,
                               "pruned": True, "contribution": "", "avoid": ""},
                    "Prepared trailing reference slot differs from its declared native pruning", uncertain=True)
    return "completed" if status in SUCCESS else status


class Runner:
    def __init__(self, plan, runtime, base_url, request_timeout, poll_interval, prepare_timeout=600):
        self.plan = validate_plan(plan)
        checked_url(base_url)
        self.store = Store(runtime, plan["plan_id"])
        self.api = API(base_url, self.store, request_timeout, prepare_timeout)
        self.base_url, self.poll_interval = base_url, poll_interval
        self.journal = None
        self.deadline = None

    def load(self):
        journal = read_json(self.store.journal_path, MAX_JOURNAL_BYTES)
        require(isinstance(journal, dict) and journal.get("schema") == "p35-owner-journal/v1"
                and journal.get("plan_id") == self.plan["plan_id"] and journal.get("plan") == self.plan
                and journal.get("base_url") == self.base_url, "Journal identity, endpoint or reviewed plan differs", uncertain=True)
        rows = journal.get("chunks")
        require(isinstance(rows, list) and len(rows) == len(self.plan["chunks"])
                and all(isinstance(row, dict) and row.get("id") == chunk["id"] and row.get("name") == chunk["name"]
                        for row, chunk in zip(rows, self.plan["chunks"])), "Malformed journal chunks", uncertain=True)
        for row in rows:
            require(row.get("project_id") is None or isinstance(row["project_id"], str) and PROJECT_ID.fullmatch(row["project_id"]), "Malformed retained project ID", uncertain=True)
        require(isinstance(journal.get("effects"), list) and len(journal["effects"]) <= len(rows) * 2, "Malformed retained effects", uncertain=True)
        self.journal = journal
        return journal

    def save(self):
        self.store.save(self.journal)

    def initial(self):
        self.journal = {
            "schema": "p35-owner-journal/v1", "plan_id": self.plan["plan_id"], "campaign_id": self.plan["campaign_id"],
            "plan": self.plan, "base_url": self.base_url, "created_at": time.time(), "state": "preparing",
            "prepare_timeout_seconds": self.api.prepare_timeout,
            "attempts_reserved": 0, "run_started_at": None, "pinned_backend": None, "effects": [],
            "chunks": [{"id": chunk["id"], "name": chunk["name"], "state": "planned", "generation_state": "planned",
                        "project_id": None, "prompt_ids": [], "classification": {"execution": "planned", "visual": "unreviewed", "licence": "unknown"}}
                       for chunk in self.plan["chunks"]],
        }
        self.store.save(self.journal, initial=True)

    def identity(self):
        identity, receipt = self.api.request("GET", "/api/identity")
        require(isinstance(identity, dict) and all(identity.get(key) == value for key, value in self.plan["expected_identity"].items()),
                "Studio identity differs from the owner-pinned workspace")
        return receipt

    def preflight(self):
        self.identity()
        value, _receipt = self.api.request("GET", "/api/backends")
        require(isinstance(value, dict) and value.get("active") == "primary" and value.get("busy") is False,
                "Primary backend must already be selected and idle from switching")
        require("state_issue" in value and not value["state_issue"] and "work_blocker" in value and not value["work_blocker"]
                and isinstance(value.get("shared_state"), dict) and "blocker" in value["shared_state"] and not value["shared_state"]["blocker"],
                "Studio backend admission is blocked or malformed")
        if "gpu_lease" in value:
            require(isinstance(value["gpu_lease"], dict) and value["gpu_lease"].get("held") is False, "Studio GPU lease is held or unknown")
        profiles = value.get("profiles")
        require(isinstance(profiles, list) and all(isinstance(profile, dict) for profile in profiles), "Malformed backend profiles")
        primary = [profile for profile in profiles if profile.get("id") == "primary"]
        require(len(primary) == 1 and primary[0].get("active") is True and primary[0].get("installed") is True
                and primary[0].get("online") is True and isinstance(primary[0].get("readiness"), dict) and primary[0]["readiness"].get("ready") is True
                and sum(profile.get("active") is True for profile in profiles) == 1, "Primary backend is unavailable or its readiness is unknown")
        selected = {key: primary[0].get(key) for key in ("url", "root")}
        checked_url(selected["url"])
        text_value(selected["root"], 2048, "primary backend root")
        pinned = self.journal.get("pinned_backend")
        require(pinned is None or pinned == selected, "Primary backend configuration changed since preparation")
        if pinned is None:
            self.journal["pinned_backend"] = selected
            self.save()

    def list_projects(self):
        projects, receipt = self.api.request("GET", "/api/production")
        require(isinstance(projects, list) and len(projects) <= 10000 and all(isinstance(p, dict) for p in projects), "Malformed or oversized project listing", uncertain=True)
        return projects, receipt

    def effect(self, kind, row, path, payload):
        require(not any(effect.get("kind") == kind and effect.get("chunk_id") == row["id"] for effect in self.journal["effects"]),
                "This side effect already has an intent; use read-only status", uncertain=True)
        effect = {"kind": kind, "chunk_id": row["id"], "path": path, "phase": "intent", "at": time.time(),
                  "request": payload, "request_sha256": digest(payload),
                  "request_timeout_seconds": self.api.prepare_timeout if kind == "create" else self.api.timeout}
        self.journal["effects"].append(effect)
        self.save()  # File fsync + atomic publication completes before a byte of the POST is sent.
        try:
            value, receipt = self.api.request("POST", path, payload)
        except BaseException as exc:
            effect.update(phase="uncertain", error=(str(exc) or type(exc).__name__)[:1000])
            row.update(state="uncertain", generation_state="uncertain")
            row["classification"]["execution"] = "uncertain"
            self.journal["state"] = "uncertain"
            self.save()
            raise
        effect.update(phase="observed", receipt=receipt, observed_at=time.time())
        self.save()
        return value

    def observe(self, row, chunk):
        timeout = None if self.deadline is None else self.deadline - time.monotonic()
        project, receipt = self.api.request("GET", "/api/production/" + row["project_id"], timeout=timeout)
        require(project.get("id") == row["project_id"] if isinstance(project, dict) else False, "Observation returned a different project", uncertain=True)
        classification = validate_project(project, chunk, self.journal["pinned_backend"], full=True)
        row.update(latest_evidence=receipt, observed_status=project["state"]["status"], stop_requested=project["state"]["stop_requested"],
                   prompt_ids=sorted(set(row["prompt_ids"]) | set(prompt_ids(project))))
        row["classification"]["execution"] = classification
        row["generation_state"] = classification
        self.save()
        return classification

    def prepare(self):
        for chunk, row in zip(self.plan["chunks"], self.journal["chunks"]):
            self.preflight()
            existing, _receipt = self.list_projects()
            matches = [project for project in existing if project.get("name") == chunk["name"]]
            require(not matches, "An existing project has this unique chunk name. Inspect it with --status; never automatically adopt or recreate it.", uncertain=True)
            row["state"] = "create_intent"
            value = self.effect("create", row, "/api/production", chunk["payload"])
            validate_project(value, chunk, self.journal["pinned_backend"], full=False)
            require(value["state"]["status"] == "planned", "Created project was not in planned state", uncertain=True)
            row["project_id"] = value["id"]
            self.save()
            require(self.observe(row, chunk) == "planned", "Created project already started externally", uncertain=True)
            row["state"] = "prepared"
            self.save()
        self.journal["state"] = "prepared"
        self.save()

    def start(self):
        require(self.journal["state"] == "prepared" and self.journal.get("run_started_at") is None
                and self.journal.get("attempts_reserved") == 0 and all(row.get("state") == "prepared" for row in self.journal["chunks"])
                and len(self.journal["effects"]) == len(self.plan["chunks"])
                and all(effect.get("kind") == "create" and effect.get("phase") == "observed" for effect in self.journal["effects"]),
                "Only a fully prepared, never-started journal may start; retries need a newly reviewed plan", uncertain=True)
        for chunk, row in zip(self.plan["chunks"], self.journal["chunks"]):
            self.preflight()
            require(self.observe(row, chunk) == "planned", "Prepared project changed or was started elsewhere", uncertain=True)
            if self.deadline is not None:
                require(self.deadline - time.monotonic() >= chunk["payload"]["max_seconds"],
                        "Remaining campaign time cannot admit this chunk's reviewed time allowance")
            else:
                self.deadline = time.monotonic() + self.plan["max_seconds"]
                self.journal["run_started_at"] = time.time()
            count = len(chunk["payload"]["variants"])
            self.journal["attempts_reserved"] += count
            require(self.journal["attempts_reserved"] <= self.plan["max_attempts"], "Reviewed attempt cap exhausted")
            self.journal["state"] = "running"
            row["state"] = "start_intent"
            value = self.effect("start", row, "/api/production/" + row["project_id"] + "/start", {})
            require(isinstance(value, dict) and value.get("id") == row["project_id"], "Start returned a different project", uncertain=True)
            classification = validate_project(value, chunk, self.journal["pinned_backend"], full=False)
            row["prompt_ids"] = sorted(set(row["prompt_ids"]) | set(prompt_ids(value)))
            row["classification"]["execution"] = classification
            row["generation_state"] = classification
            self.save()
            require(classification in LIVE | {"completed"}, "Start reply reports stopped or unknown execution: " + classification,
                    uncertain=classification in {"uncertain", "interrupted", "planned"})
            require(not value["state"]["stop_requested"], "Studio records an owner stop request; later chunks remain unstarted")
            row["state"] = "running"
            self.save()
            while True:
                require(time.monotonic() < self.deadline, "Campaign observation time exhausted; active work may still finish. Use --status.", uncertain=True)
                classification = self.observe(row, chunk)
                require(not row["stop_requested"], "Studio records an owner stop request; later chunks remain unstarted")
                if classification == "completed":
                    row["state"] = "completed"
                    self.save()
                    break
                require(classification in LIVE, "Studio stopped this chunk with state " + classification,
                        uncertain=classification in {"uncertain", "interrupted", "planned"})
                time.sleep(min(self.poll_interval, max(0, self.deadline - time.monotonic())))
        self.journal.update(state="completed", finished_at=time.time())
        self.save()

    def summary(self):
        return {"ok": True, "state": self.journal["state"], "plan_id": self.plan["plan_id"],
                "journal": str(self.store.journal_path), "lock_retained": self.store.lock_path.exists(),
                "attempts_reserved": self.journal.get("attempts_reserved", 0),
                "chunks": [{key: row.get(key) for key in ("id", "name", "state", "project_id", "classification", "prompt_ids", "latest_evidence")}
                           for row in self.journal["chunks"]]}

    def status(self):
        self.load()
        self.identity()
        # Read-only status remains available even when another backend is selected.
        backends, _receipt = self.api.request("GET", "/api/backends")
        result = self.summary()
        result["active_backend"] = backends.get("active") if isinstance(backends, dict) else None
        listing = None
        for chunk, row, reported in zip(self.plan["chunks"], self.journal["chunks"], result["chunks"]):
            if row.get("project_id"):
                project, receipt = self.api.request("GET", "/api/production/" + row["project_id"])
                require(isinstance(project, dict) and project.get("id") == row["project_id"], "Status returned a different project", uncertain=True)
                reported["observed_execution"] = validate_project(project, chunk, self.journal["pinned_backend"], full=True)
                reported["prompt_ids"] = sorted(set(row["prompt_ids"]) | set(prompt_ids(project)))
                reported["status_evidence"] = receipt
            else:
                if listing is None:
                    listing, _receipt = self.list_projects()
                matches = [project for project in listing if project.get("name") == chunk["name"]]
                reported["reconciliation_candidates"] = []
                for candidate in matches:
                    identifier = candidate.get("id")
                    require(isinstance(identifier, str) and PROJECT_ID.fullmatch(identifier), "Malformed reconciliation candidate ID", uncertain=True)
                    project, receipt = self.api.request("GET", "/api/production/" + identifier)
                    # A candidate is evidence only, never adopted into the journal or started.
                    require(isinstance(project, dict) and project.get("id") == identifier and project.get("name") == chunk["name"], "Reconciliation candidate changed", uncertain=True)
                    reported["reconciliation_candidates"].append({"project_id": identifier, "observed_status": (project.get("state") or {}).get("status"),
                                                                  "prompt_ids": prompt_ids(project), "status_evidence": receipt})
        return result

    def execute(self, mode):
        if mode == "status":
            return self.status()
        if self.store.lock_path.exists():
            raise RunError("Run lock already exists. Use --status; never delete/reclaim it to repeat this journal.", uncertain=True)
        self.store.acquire(self.plan["plan_id"])
        read_only = False
        try:
            # A contender may have finished between the initial existence check and
            # acquiring this lock. Never write from a snapshot loaded before ownership.
            if self.store.journal_path.exists():
                self.load()
                read_only = self.journal["state"] == "completed" or mode == "prepare" and self.journal["state"] == "prepared"
                require(read_only or self.journal["state"] == "prepared" and mode == "start",
                        "This journal cannot perform further writes; use --status", uncertain=True)
            else:
                self.initial()
                self.prepare()
            if mode == "start" and not read_only:
                self.start()
            self.store.release()
        except BaseException as exc:
            if self.journal is not None:
                uncertain = isinstance(exc, (KeyboardInterrupt, SystemExit)) or not isinstance(exc, RunError) or exc.uncertain
                self.journal.update(state="uncertain" if uncertain else "halted", error=(str(exc) or type(exc).__name__)[:1000])
                try:
                    self.save()
                except Exception:
                    pass  # Preserve the previous durable intent and lock; never issue another request.
            raise
        return self.status() if read_only else self.summary()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True, help="Reviewed p35-owner-run/v1 JSON")
    action = parser.add_mutually_exclusive_group(required=True)
    for mode in ("prepare", "start", "status"):
        action.add_argument("--" + mode, action="store_const", dest="mode", const=mode)
    parser.add_argument("--runtime", type=Path, default=Path.cwd() / ".runtime", help="Receipt root named .runtime (default: current directory/.runtime)")
    parser.add_argument("--base-url", default="http://127.0.0.1:8191")
    parser.add_argument("--request-timeout", type=float, default=60)
    parser.add_argument("--prepare-timeout", type=float, default=600,
                        help="Bound for each create response while Studio hashes pinned models (0.01..1800 seconds); never retries")
    parser.add_argument("--poll-interval", type=float, default=5)
    args = parser.parse_args(argv)
    runner = None
    try:
        require(sys.version_info >= (3, 12), "Python 3.12 or newer is required")
        require(math.isfinite(args.request_timeout) and 0.01 <= args.request_timeout <= 60, "request-timeout must be 0.01..60 seconds")
        require(math.isfinite(args.prepare_timeout) and 0.01 <= args.prepare_timeout <= 1800, "prepare-timeout must be 0.01..1800 seconds")
        require(math.isfinite(args.poll_interval) and 0.01 <= args.poll_interval <= 60, "poll-interval must be 0.01..60 seconds")
        plan = validate_plan(read_json(args.plan, MAX_PLAN_BYTES))
        runner = Runner(plan, args.runtime, args.base_url, args.request_timeout, args.poll_interval, args.prepare_timeout)
        result = runner.execute(args.mode)
        code = 0
    except (RunError, OSError, ValueError, TypeError, RecursionError, KeyboardInterrupt) as exc:
        result = runner.summary() if runner is not None and runner.journal is not None else {"state": "refused"}
        result.update(ok=False, error=(str(exc) or type(exc).__name__)[:1500])
        code = 130 if isinstance(exc, KeyboardInterrupt) else 2
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
