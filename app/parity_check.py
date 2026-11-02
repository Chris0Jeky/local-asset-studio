"""Export parity check for a completed native articulated build.

Probes the configured Blender, then runs the Asset Parity Sentinel on the project's own BLEND: GLB export with the LAS
settings, reimport in a new Blender process, structural comparison, localised visual comparison and, when installed,
the render critic as a second signal. It runs at most once per project: the receipt is created exclusively before
Blender starts, every file is kept on failure, and recovery reads retained evidence without running Blender again.
No ComfyUI prompt is submitted and no art or licence decision is made.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time

import articulated

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
import blender_lab
import blender_sentinel

OPERATION = "native.parity-check.v1"
FOLDER, RECEIPT = "parity-check", "parity-check-job.json"


class ParityCheckError(ValueError):
    """The export check cannot safely run or recover."""


def require(condition, message):
    if not condition:
        raise ParityCheckError(message)


def summarise(result, probe=None, delivered=None):
    """What the Studio shows: the verdict, localised findings first, then the structural and visual detail. The sentinel
    checks a fresh export of the BLEND, so the verdict covers the delivered chest.glb only when the bytes are identical."""
    critic = result.get("second_signal") or {}
    checked = result.get("export", {}).get("glb_sha256")
    return {"pass": bool(result["pass"]), "delivered_glb_checked": bool(delivered and checked and delivered == checked),
            "localisation": [entry["statement"] for entry in result.get("localisation", [])],
            "structural_failures": result["structural_failures"], "visual_warnings": result["visual_warnings"],
            "format_losses": result["format_losses"], "expected_exclusions": result["expected_exclusions"],
            "second_signal": ({"changed": critic.get("changed"), "agrees_with_primary": critic.get("agrees_with_primary")}
                              if critic.get("available") else None),
            "gpu_cost": result.get("gpu_cost"), "blender": result["blender"]["version_string"],
            "capabilities": None if probe is None else sorted(k for k, v in probe["features"].items() if v["ok"])}


def _write(path, value, exclusive=False):
    text, path = json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n", Path(path)
    if exclusive:
        with path.open("x", encoding="utf-8", newline="\n") as stream: stream.write(text)
        return
    partial = path.with_name(path.name + ".partial")  # an interrupted rewrite never leaves a truncated receipt
    partial.write_text(text, encoding="utf-8", newline="\n"); os.replace(partial, path)


def _delivered(directory):
    glb = directory / "articulated" / "chest.glb"
    return blender_lab.file_sha(glb) if glb.is_file() else None


def _verdict(summary):
    if not summary["pass"]: return "Export check found differences between the source and the reimported GLB."
    if summary["delivered_glb_checked"]: return "Export check passed: the delivered chest.glb reimports to match the source."
    return "A fresh export passed, but the delivered chest.glb is missing or differs from it, so the delivered file was not verified."


def run_check(studio, project_id, timeout=600):
    """Check a completed articulated build exactly once; a second call recovers the first attempt."""
    project_id = articulated._validate_project_id(project_id)
    directory = articulated._project_directory(studio, project_id)
    receipt = directory / RECEIPT
    if receipt.exists():
        return recover(studio, project_id)
    source, build = directory / "articulated" / "chest.blend", directory / "articulated-job.json"
    require(source.is_file() and build.is_file(), "Check this export needs a completed articulated build")
    require(json.loads(build.read_text(encoding="utf-8")).get("status") == "completed", "The articulated build did not complete")
    blender = articulated._configured_blender(studio)
    job = {"operation": OPERATION, "status": "running", "project_id": project_id, "created_at": time.time(),
           "blender": blender, "source": {"path": "articulated/chest.blend", "sha256": blender_lab.file_sha(source)},
           "message": "Checking the export: GLB export, reimport in a new Blender process and comparison. No ComfyUI prompt."}
    try:
        _write(receipt, job, exclusive=True)  # two concurrent requests cannot both start Blender
    except FileExistsError:
        return recover(studio, project_id)
    try:
        target = directory / FOLDER
        target.mkdir()
        probe = blender_lab.probe(blender["path"], target / "probe.json", timeout)
        result = blender_sentinel.sentinel(blender["path"], source, target / "sentinel", timeout=timeout)
        summary = summarise(result, probe, _delivered(directory))
        job.update(status="completed", finished_at=time.time(), summary=summary, message=_verdict(summary))
    except Exception as exc:  # keep every file; never retry automatically
        job.update(status="failed", finished_at=time.time(), message=f"Export check failed: {str(exc)[:400]}", failure_files=True)
    _write(receipt, job)
    return job


def recover(studio, project_id):
    """Report a retained check without running Blender: a finished receipt as recorded, an interrupted one from its
    retained result.json when that exists, otherwise uncertain."""
    project_id = articulated._validate_project_id(project_id)
    directory = articulated._project_directory(studio, project_id)
    try:
        job = json.loads((directory / RECEIPT).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"operation": OPERATION, "status": "uncertain", "message": f"No readable export-check receipt: {exc}"[:400]}
    if job.get("status") in ("completed", "failed"):
        return job
    result_path = directory / FOLDER / "sentinel" / "result.json"
    if result_path.is_file():
        try:
            summary = summarise(json.loads(result_path.read_text(encoding="utf-8")), delivered=_delivered(directory))
        except (OSError, ValueError, KeyError, TypeError) as exc:  # a result.json cut short by the interruption
            job.update(status="uncertain", message=f"An earlier export check left an unreadable result ({exc}). Its files are kept; Blender was not run again."[:400])
            return job
        job.update(status="completed", summary=summary, finished_at=job.get("finished_at") or time.time(),
                   message=_verdict(summary) + " Recovered from the retained result; Blender was not run again.")
        _write(directory / RECEIPT, job)
        return job
    job.update(status="uncertain", message="An earlier export check did not finish. Its files are kept; Blender was not run again.")
    return job
