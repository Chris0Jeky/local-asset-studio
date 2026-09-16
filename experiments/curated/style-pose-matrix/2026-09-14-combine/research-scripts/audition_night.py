"""Night audition, 16 September 2026: purposeful Studio jobs (POST /api/jobs, the page's own path) that turn tonight's single proving runs
into small auditions and characterise the new control. Results are retained in audition_night.json; every accepted job ID is atomically
written before polling. Re-running resumes a submitted job by ID and treats a terminal receipt as a zero-side-effect replay.
  depthcut  the depth recipe at depth_cut 80 and 92 (seed 2026091441; 86 and 100 already recorded) -> what the hint should say
  editor    the page-rendered guide (same file as the proving run) at two more seeds -> a 3-seed claim for the editor
  copypose  the Copy Pose recipe at two more seeds -> a 3-seed claim through the Studio
  expression the Klein edit on the pack portrait with a stricter instruction (no grin) -> HUMAN_TODO q-30 (e)
Usage: python audition_night.py [group ...]"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

OUT = Path(__file__).resolve().parent
STUDIO = "http://127.0.0.1:8191"
CHAR = "e71a593a0fc04452b231b278c62eb31b_yande.re_1252703_sample_bluefield_ellen_joe_tail_zenless_zone_zero.jpg.jpg"
POSE = "6895e9e00de94178892b56d1d59dd21a_yande.re_1250070_sample_ass_ellen_joe_floralmi_heels_maid_pantsu_pantyhose_see_through_skirt_lift_ta.jpg"
GUIDE = "0d468872db0a4cb0b05a49fd94c4ec0b_drawn-pose.png"
PORTRAIT_ASSET = "021731c057d955b4a2487395a37fadf6"
WHO = "Ellen Joe, a girl with short black hair with red tips, red eyes and a black choker"
CLOTHES = "a black long-sleeved crop top with red SHARK lettering, bright pink shorts, bare legs, bare feet"
POSEWORDS = "bent forward deeply at the waist, seen from behind, legs crossed, looking back over her shoulder"
SKELWORDS = "bent forward deeply at the waist, seen from behind, legs crossed, one arm raised behind the head, looking back over her shoulder"
TERMINAL_STATUSES = frozenset({"completed", "failed", "not_submitted", "uncertain", "abandoned"})


def post(path, body):
    request = urllib.request.Request(
        STUDIO + path,
        json.dumps(body).encode(),
        {"Content-Type": "application/json", "Origin": STUDIO},
    )
    try:
        return json.load(urllib.request.urlopen(request, timeout=120))
    except urllib.error.HTTPError as error:
        raise SystemExit(
            "rejected %s %s %s"
            % (path, error.code, error.read().decode("utf-8", "replace")[:1500])
        ) from None


def wait(job_id):
    started = time.time()
    while time.time() - started < 1800:
        time.sleep(5)
        job = json.load(
            urllib.request.urlopen(STUDIO + "/api/jobs/" + job_id, timeout=30)
        )
        if job.get("status") in TERMINAL_STATUSES:
            return job
    raise SystemExit("timeout " + job_id)


def _results_path(results_path=None):
    return Path(results_path) if results_path is not None else Path(OUT) / "audition_night.json"


def load(results_path=None):
    path = _results_path(results_path)
    if not path.exists():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise ValueError(f"Night-audition receipt must be a JSON array of objects: {path}")
    return value


def save(results, results_path=None):
    path = _results_path(results_path)
    if not isinstance(results, list) or not all(isinstance(row, dict) for row in results):
        raise ValueError("Night-audition receipt must be a JSON array of objects")
    payload = json.dumps(
        results, indent=1, ensure_ascii=True, allow_nan=False
    ) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _matches(record, group, extra):
    return record.get("group") == group and all(
        record.get(key) == value for key, value in extra.items()
    )


def _find(records, group, extra):
    matches = [record for record in records if _matches(record, group, extra)]
    if len(matches) > 1:
        raise ValueError(f"Duplicate night-audition receipt for {group}: {extra}")
    return matches[0] if matches else None


def _upsert(records, group, extra, replacement):
    for index, record in enumerate(records):
        if _matches(record, group, extra):
            records[index] = replacement
            return
    records.append(replacement)


def record(group, job, extra, *, results_path=None):
    if (
        not isinstance(job, dict)
        or not isinstance(job.get("id"), str)
        or not job["id"]
        or job.get("status") not in TERMINAL_STATUSES
    ):
        raise ValueError("Studio returned an invalid terminal job")
    result = {
        key: job.get(key)
        for key in (
            "id",
            "status",
            "preset_id",
            "prompt_ids",
            "outputs",
            "elapsed_seconds",
            "error",
        )
    }
    result["group"] = group
    result.update(extra)
    rows = load(results_path)
    _find(rows, group, extra)
    _upsert(rows, group, extra, result)
    save(rows, results_path)
    print(
        group,
        result.get("seed"),
        result.get("depth_cut", ""),
        result["id"][:8],
        result["status"],
        round(result.get("elapsed_seconds") or 0, 1),
        [output["filename"] for output in result.get("outputs") or []],
        str(result.get("error") or "")[:120],
        flush=True,
    )
    return result


def run_experiment(
    group,
    body,
    extra,
    *,
    results_path=None,
    post_job=post,
    wait_job=wait,
):
    """Submit once, persist before polling, resume submitted work, and retain one keyed row."""
    rows = load(results_path)
    prior = _find(rows, group, extra)
    if prior is not None:
        status = prior.get("status")
        if status in TERMINAL_STATUSES:
            print(
                "skip",
                group,
                extra,
                prior["id"][:8],
                status,
                "(terminal receipt)",
                flush=True,
            )
            return prior
        if status != "submitted" or not isinstance(prior.get("id"), str) or not prior["id"]:
            raise ValueError(f"Invalid resumable receipt for {group}: {extra}")
        job_id = prior["id"]
        print("resume", group, extra, job_id[:8], flush=True)
    else:
        payload = body() if callable(body) else body
        job = post_job("/api/jobs", payload)
        if not isinstance(job, dict) or not isinstance(job.get("id"), str) or not job["id"]:
            raise ValueError("Studio returned an invalid accepted job")
        job_id = job["id"]
        submitted = {"group": group, "id": job_id, "status": "submitted", **extra}
        _upsert(rows, group, extra, submitted)
        save(rows, results_path)

    terminal = wait_job(job_id)
    if not isinstance(terminal, dict) or terminal.get("id") != job_id:
        raise ValueError("Studio returned a mismatched terminal job")
    return record(group, terminal, extra, results_path=results_path)


def filled(preset, values):
    text = preset["continuation_prompt"]
    placeholders = preset["continuation_placeholder"]
    for placeholder in placeholders:
        keys = [key for key in values if placeholder.startswith(key)]
        if len(keys) != 1 or placeholder not in text:
            raise ValueError(f"Unresolved continuation placeholder: {placeholder}")
        text = text.replace(placeholder, values[keys[0]])
    return text


def main(argv=None):
    groups = list(sys.argv[1:] if argv is None else argv) or [
        "depthcut",
        "editor",
        "copypose",
        "expression",
    ]
    preset_cache = None

    def preset(preset_id):
        nonlocal preset_cache
        if preset_cache is None:
            catalog = json.load(
                urllib.request.urlopen(STUDIO + "/api/catalog", timeout=30)
            )
            preset_cache = {value["id"]: value for value in catalog["presets"]}
        try:
            return preset_cache[preset_id]
        except KeyError:
            raise SystemExit("missing preset " + preset_id) from None

    if "depthcut" in groups:
        for cut in (80, 92):
            extra = {"seed": 2026091441, "depth_cut": cut}

            def depth_body(cut=cut):
                value = preset("combine-klein-9b-depth")
                text = filled(
                    value,
                    {
                        "[who is in image 2": WHO,
                        "[image 1's pose": POSEWORDS,
                        "[image 2's clothes": CLOTHES,
                    },
                )
                return {
                    "preset_id": value["id"],
                    "controls": {
                        "positive": text,
                        "last_reference": CHAR,
                        "seed": 2026091441,
                        "depth_cut": cut,
                    },
                    "batch_count": 1,
                    "references": [{"file": POSE, "role": "pose"}],
                    "parent_assets": [],
                }

            run_experiment("depthcut", depth_body, extra)

    if "editor" in groups:
        for seed in (2026091462, 2026091463):
            extra = {"seed": seed, "guide": GUIDE}

            def editor_body(seed=seed):
                value = preset("combine-klein-9b-skeleton")
                text = filled(
                    value,
                    {
                        "[who is in image 2": WHO,
                        "[image 1's pose": SKELWORDS,
                        "[image 2's clothes": CLOTHES,
                    },
                )
                return {
                    "preset_id": value["id"],
                    "controls": {
                        "positive": text,
                        "last_reference": CHAR,
                        "seed": seed,
                    },
                    "batch_count": 1,
                    "references": [{"file": GUIDE, "role": "pose"}],
                    "parent_assets": [],
                }

            run_experiment("editor", editor_body, extra)

    if "copypose" in groups:
        for seed in (2026091472, 2026091473):
            extra = {"seed": seed}

            def copypose_body(seed=seed):
                value = preset("combine-klein-9b-copypose")
                text = filled(
                    value,
                    {
                        "[who is in image 1": WHO,
                        "[image 1's clothes": CLOTHES,
                        "[image 2's pose": POSEWORDS,
                    },
                )
                return {
                    "preset_id": value["id"],
                    "controls": {
                        "positive": text,
                        "last_reference": CHAR,
                        "seed": seed,
                    },
                    "batch_count": 1,
                    "references": [{"file": POSE, "role": "pose"}],
                    "parent_assets": [],
                }

            run_experiment("copypose", copypose_body, extra)

    if "expression" in groups:
        extra = {
            "seed": 2026091301,
            "source_asset": PORTRAIT_ASSET,
            "instruction": "surprised, no grin",
        }

        def expression_body():
            value = preset("flux-edit")
            staged = post("/api/assets/reference", {"id": PORTRAIT_ASSET})
            text = value["continuation_prompt"].replace("{source}", "")
            placeholder = value["continuation_placeholder"]
            placeholder = placeholder[0] if isinstance(placeholder, list) else placeholder
            text = text.replace(
                placeholder,
                "change her expression to surprised: eyebrows raised, eyes a little wider, "
                "lips parted slightly as if about to speak, no smile and no grin",
            )
            return {
                "preset_id": value["id"],
                "controls": {
                    "positive": text,
                    "reference": staged["file"],
                    "seed": 2026091301,
                    "width": 832,
                    "height": 1216,
                },
                "batch_count": 1,
                "references": [],
                "parent_assets": [PORTRAIT_ASSET],
            }

        run_experiment("expression", expression_body, extra)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
