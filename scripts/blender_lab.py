"""Host side of the Blender lab: run `blender_lab_bpy.py` in a configured Blender with a fixed argv.

Only the executable path supplied by the caller is started, with a literal argument list and a bounded timeout.
The Blender half lives in `blender_lab_bpy.py`; nothing caller-supplied is ever executed as Python.

    python scripts/blender_lab.py probe --blender <blender.exe> --out <probe.json>
    python scripts/blender_lab.py make-fixture --blender <blender.exe> --out-dir <new-dir>
    python scripts/blender_lab.py manifest --blender <blender.exe> --blend <file.blend> --out <manifest.json>
    python scripts/blender_lab.py scene-v1 --blender <blender.exe> --blend <file.blend> --out <scene.json>
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


HERE = Path(__file__).resolve().parent
BPY_SCRIPT = HERE / "blender_lab_bpy.py"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import blender_lab_bpy as bpy_side  # pure helpers only; bpy is imported lazily inside Blender


class BlenderLabError(ValueError):
    """A configured Blender, its run, or its output does not meet the lab contract."""


def require(condition, message):
    if not condition:
        raise BlenderLabError(message)


def file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def executable(blender_path):
    path = Path(blender_path).expanduser()
    require(path.is_absolute(), "blender_path must be absolute")
    path = path.resolve()
    require(path.is_file() and path.name.lower() in {"blender.exe", "blender"}, "Configured Blender executable is missing")
    return path


def command_for(blender_path, *args):
    return [str(blender_path), "--background", "--factory-startup", "--disable-autoexec", "--python", str(BPY_SCRIPT),
            "--", *map(str, args)]


def run(blender_path, args, log_path, timeout=300):
    """Run one Blender-side command; keep argv, exit code, stdout and stderr next to the output."""
    command = command_for(blender_path, *args)
    with Path(log_path).open("x", encoding="utf-8", newline="\n") as log:  # never replace an earlier receipt
        started = time.perf_counter(); error = None
        try:
            completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                       timeout=timeout, check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            returncode, stdout, stderr = completed.returncode, completed.stdout, completed.stderr
        except subprocess.TimeoutExpired as exc:
            returncode, stdout, stderr = "timeout", exc.stdout, exc.stderr
        except OSError as exc:
            returncode, stdout, stderr = "os-error", None, None
            error = f"{type(exc).__name__}: {exc}"[:1000]
        seconds = round(time.perf_counter() - started, 3)
        decode = lambda value: value.decode("utf-8", "replace") if isinstance(value, bytes) else value
        receipt = {"argv": command, "returncode": returncode, "seconds": seconds,
                   "stdout": decode(stdout), "stderr": decode(stderr)}
        if error is not None: receipt["error"] = error
        log.write(json.dumps(receipt, indent=2) + "\n")
    require(returncode != "os-error", f"Blender did not return a result; see {log_path}")
    require(returncode == 0, f"Blender exited {returncode}; see {log_path}")
    return seconds


def probe(blender_path, out_path, timeout=300):
    exe = executable(blender_path)
    out = Path(out_path).expanduser().resolve()
    require(not out.exists(), "out must be a new file")
    seconds = run(exe, ["probe", "--out", out], out.with_name(out.stem + ".log.json"), timeout)
    result = json.loads(out.read_text(encoding="utf-8"))
    require(result.get("kind") == "capability-probe", "Probe output has the wrong kind")
    result["runtime"] = {"executable": exe.as_posix(), "sha256": file_sha(exe), "wall_seconds": seconds}
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return result


def manifest(blender_path, blend_path, out_path, timeout=300):
    """Describe a .blend without saving it; the source bytes must be identical afterwards."""
    exe = executable(blender_path)
    blend = Path(blend_path).expanduser().resolve()
    require(blend.is_file() and blend.suffix.lower() == ".blend", "blend must be an existing .blend file")
    out = Path(out_path).expanduser().resolve()
    require(not out.exists(), "out must be a new file")
    before = file_sha(blend)
    seconds = run(exe, ["manifest", "--blend", blend, "--out", out], out.with_name(out.stem + ".log.json"), timeout)
    require(file_sha(blend) == before, "Source .blend changed during the manifest run")
    result = json.loads(out.read_text(encoding="utf-8"))
    require(result.get("kind") == "scene-manifest", "Manifest output has the wrong kind")
    require(bpy_side.semantic_checksum(result) == result.get("semantic_checksum"), "Manifest checksum does not verify")
    result["source"]["sha256"] = before
    result["runtime"] = {"executable": exe.as_posix(), "wall_seconds": seconds}
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return result


def make_fixture(blender_path, out_dir, timeout=300):
    """Generate the lab test asset (never a real character) into a new directory."""
    exe = executable(blender_path)
    target = Path(out_dir).expanduser().resolve()
    require(not target.exists(), "out_dir must be new")
    target.mkdir(parents=True)
    run(exe, ["make-fixture", "--out-dir", target, "--out", target / "fixture.json"], target / "fixture.log.json", timeout)
    blend = target / "lab-asset.blend"
    require(blend.is_file() and (target / "lab-checker.png").is_file(), "Fixture generation left no asset")
    return blend


def scene_v1(blender_path, blend_path, out_path, timeout=120):
    """Exact `studio.dcc-scene/v1` observation for `studio_workflow.dcc_evidence.compare_scenes`."""
    exe = executable(blender_path)
    blend = Path(blend_path).expanduser().resolve()
    require(blend.is_file() and blend.suffix.lower() == ".blend", "blend must be an existing .blend file")
    out = Path(out_path).expanduser().resolve()
    require(not out.exists(), "out must be a new file")
    before = file_sha(blend)
    run(exe, ["scene-v1", "--blend", blend, "--out", out], out.with_name(out.stem + ".log.json"), timeout)
    require(file_sha(blend) == before, "Source .blend changed during the observation")
    observation = json.loads(out.read_text(encoding="utf-8"))
    require(observation.get("format") == "studio.dcc-scene/v1" and observation.get("complete") is True,
            "Observation is not a complete studio.dcc-scene/v1 record")
    return observation


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    probe_parser = commands.add_parser("probe")
    probe_parser.add_argument("--blender", required=True)
    probe_parser.add_argument("--out", required=True)
    manifest_parser = commands.add_parser("manifest")
    manifest_parser.add_argument("--blender", required=True)
    manifest_parser.add_argument("--blend", required=True)
    manifest_parser.add_argument("--out", required=True)
    fixture_parser = commands.add_parser("make-fixture")
    fixture_parser.add_argument("--blender", required=True)
    fixture_parser.add_argument("--out-dir", required=True)
    scene_parser = commands.add_parser("scene-v1")
    scene_parser.add_argument("--blender", required=True)
    scene_parser.add_argument("--blend", required=True)
    scene_parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "scene-v1":
            result = scene_v1(args.blender, args.blend, args.out)
            print(json.dumps({"out": args.out, "objects": len(result["content"]["objects"]), "findings": result["findings"]}))
            return 0
        if args.command == "manifest":
            result = manifest(args.blender, args.blend, args.out)
            print(json.dumps({"out": args.out, "semantic_checksum": result["semantic_checksum"], "counts": result["counts"]}))
            return 0
        if args.command == "make-fixture":
            print(json.dumps({"blend": str(make_fixture(args.blender, args.out_dir))}))
            return 0
        result = probe(args.blender, args.out)
        print(json.dumps({"out": args.out, "blender": result["blender"]["version_string"],
                          "failed_features": sorted(k for k, v in result["features"].items() if not v["ok"])}))
        return 0
    except (BlenderLabError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
