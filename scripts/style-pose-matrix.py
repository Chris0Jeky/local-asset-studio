"""Run a Style + Pose matrix through the Studio, one job at a time, and build a contact sheet.

Every cell is a normal Studio job (POST /api/jobs) so the exact recipe, prompt ID and outputs are
persisted under experiments/runs/<job-id>/ like any other run. Cells are grouped by recipe so each
checkpoint loads once. Nothing is resubmitted: a cell that fails or times out is recorded as such and
the matrix moves on. Host commit is read before every cell and the run stops when it passes --max-commit.

    python scripts/style-pose-matrix.py --plan plan.json --out experiments/curated/style-pose-matrix/<date>

plan.json:
{
  "style": "<upload file name>", "poses": [{"id": "throne", "file": "<upload>", "tags": "sitting, ..."}, ...],
  "subject": "...", "recipes": [{"preset_id": "style-pose-wai", "prefix": "", "suffix": ", masterpiece"}, ...],
  "loras": [{"id": "none"}, {"id": "cine", "controls": {"lora": 0.5, "lora_name": "cinematic lighting.safetensors"}, "tag": "cinematic lighting"}],
  "controls": {"width": 832, "height": 1216, "seed": 2026091410}
}
"""
import argparse, json, subprocess, sys, time, urllib.request
from pathlib import Path

STUDIO = "http://127.0.0.1:8191"


def api(path, payload=None, timeout=30):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(STUDIO + path, data=data, method="POST" if data else "GET",
                                 headers={"Content-Type": "application/json", "Origin": STUDIO})
    with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read().decode("utf-8"))


def host_commit():
    if sys.platform != "win32": return None
    try:
        out = subprocess.check_output(["powershell", "-NoProfile", "-Command",
            "(Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory).PercentCommittedBytesInUse"], text=True, timeout=30)
        return int(out.strip())
    except (subprocess.SubprocessError, ValueError, OSError): return None


TERMINAL = {"completed", "failed", "stopped", "abandoned", "not_submitted", "uncertain"}


def wait(job_id, timeout):
    """Poll until the Studio reports a terminal status; 'waiting', 'submitting' and 'observing' are in flight."""
    start = time.time()
    while time.time() - start < timeout:
        job = api("/api/jobs/" + job_id)
        if job["status"] in TERMINAL: return job
        time.sleep(5)
    return api("/api/jobs/" + job_id)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--comfy-root", default=None, help="ComfyUI root, to copy outputs; defaults to config/local.json comfy_root")
    ap.add_argument("--timeout", type=int, default=900, help="seconds per cell before it is recorded as timed out (never resubmitted)")
    ap.add_argument("--max-commit", type=int, default=90, help="stop before a cell when host commit %% is above this")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    comfy_root = Path(args.comfy_root or json.loads((root / "config/local.json").read_text(encoding="utf-8"))["comfy_root"])
    cells = []
    for recipe in plan["recipes"]:
        for lora in plan["loras"]:
            for pose in plan["poses"]:
                if lora.get("poses") and pose["id"] not in lora["poses"]: continue  # a LoRA setting may run on a subset of poses
                positive = recipe.get("prefix", "") + plan["subject"] + ", " + pose["tags"] + recipe.get("suffix", "")
                if lora.get("tag"): positive += ", " + lora["tag"]
                controls = dict(plan.get("controls", {}), positive=positive, reference=plan["style"], last_reference=pose["file"], **lora.get("controls", {}))
                cells.append({"recipe": recipe["preset_id"], "lora": lora["id"], "pose": pose["id"], "controls": controls})
    manifest_path = out / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"plan": plan, "cells": []}
    done = {(c["recipe"], c["lora"], c["pose"]) for c in manifest["cells"] if c.get("status") in TERMINAL}
    # A cell whose job was submitted but not seen to finish is re-waited on its own job id, never resubmitted.
    pending = {(c["recipe"], c["lora"], c["pose"]): c for c in manifest["cells"] if c.get("job_id") and c.get("status") not in TERMINAL}
    print(f"{len(cells)} cells, {len(done)} already finished, {len(pending)} to resume")
    if args.dry_run:
        for c in cells: print(c["recipe"], c["lora"], c["pose"], "|", c["controls"]["positive"][:90])
        return 0
    for cell in cells:
        key = (cell["recipe"], cell["lora"], cell["pose"])
        if key in done: continue
        commit = host_commit()
        if commit is not None and commit > args.max_commit:
            print(f"STOP: host commit {commit}% above {args.max_commit}% before {key}"); break
        t0 = time.time()
        if key in pending:
            job = {"id": pending[key]["job_id"]}; manifest["cells"].remove(pending[key])
        else:
            try: job = api("/api/jobs", {"preset_id": cell["recipe"], "controls": cell["controls"], "batch_count": 1})
            except Exception as exc:  # the cell is recorded, never retried
                manifest["cells"].append(dict(cell, status="submit-failed", error=str(exc)[:300], commit_before=commit)); manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8"); continue
        job = wait(job["id"], args.timeout)
        record = dict(cell, job_id=job["id"], status=job["status"], prompt_ids=job.get("prompt_ids"), failure=job.get("failure"),
                      wall_seconds=round(time.time() - t0, 1), elapsed_seconds=job.get("elapsed_seconds"), commit_before=commit, outputs=[])
        for o in job.get("outputs") or []:
            src = comfy_root / "output" / (o.get("subfolder") or "") / o["filename"]
            dst = out / f"{cell['recipe']}__{cell['lora']}__{cell['pose']}.png"
            if src.is_file(): dst.write_bytes(src.read_bytes()); record["outputs"].append({"file": dst.name, "comfy_file": str(src.relative_to(comfy_root)), "seed": o.get("seed"), "asset_id": o.get("asset_id")})
        manifest["cells"].append(record); manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"{record['status']:10} {record['wall_seconds']:6.1f}s commit {commit}% {key} {record.get('failure') or ''}")
    contact_sheet(manifest, out)
    return 0


def contact_sheet(manifest, out):
    """One row per recipe x LoRA, one column per pose; small JPEG so it can live in Git."""
    from PIL import Image, ImageDraw
    cells = [c for c in manifest["cells"] if c.get("outputs")]
    if not cells: print("no outputs to sheet"); return
    poses = [p["id"] for p in manifest["plan"]["poses"]]
    rows = list(dict.fromkeys((c["recipe"], c["lora"]) for c in cells))
    w, h, label = 256, 374, 18
    sheet = Image.new("RGB", (label * 8 + w * len(poses), (h + label) * len(rows)), "white"); draw = ImageDraw.Draw(sheet)
    for r, (recipe, lora) in enumerate(rows):
        y = r * (h + label); draw.text((4, y + 2), f"{recipe} / {lora}", fill="black")
        for cidx, pose in enumerate(poses):
            cell = next((c for c in cells if (c["recipe"], c["lora"], c["pose"]) == (recipe, lora, pose)), None)
            if not cell: continue
            im = Image.open(out / cell["outputs"][0]["file"]).convert("RGB"); im.thumbnail((w, h))
            sheet.paste(im, (label * 8 + cidx * w, y + label))
    sheet.save(out / "contact-sheet.jpg", quality=80); print("contact sheet:", out / "contact-sheet.jpg", sheet.size)


if __name__ == "__main__": sys.exit(main())
