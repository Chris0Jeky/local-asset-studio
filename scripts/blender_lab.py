"""Host side of the Blender lab: run `blender_lab_bpy.py` in a configured Blender with a fixed argv.

Only the executable path supplied by the caller is started, with a literal argument list and a bounded timeout.
The Blender half lives in `blender_lab_bpy.py`; nothing caller-supplied is ever executed as Python.

    python scripts/blender_lab.py probe --blender <blender.exe> --out <probe.json>
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
        started = time.perf_counter()
        try:
            completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                       timeout=timeout, check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            returncode, stdout, stderr = completed.returncode, completed.stdout, completed.stderr
        except subprocess.TimeoutExpired as exc:
            returncode, stdout, stderr = "timeout", exc.stdout, exc.stderr
        seconds = round(time.perf_counter() - started, 3)
        decode = lambda value: value.decode("utf-8", "replace") if isinstance(value, bytes) else value
        log.write(json.dumps({"argv": command, "returncode": returncode, "seconds": seconds,
                              "stdout": decode(stdout), "stderr": decode(stderr)}, indent=2) + "\n")
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    probe_parser = commands.add_parser("probe")
    probe_parser.add_argument("--blender", required=True)
    probe_parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        result = probe(args.blender, args.out)
        print(json.dumps({"out": args.out, "blender": result["blender"]["version_string"],
                          "failed_features": sorted(k for k, v in result["features"].items() if not v["ok"])}))
        return 0
    except (BlenderLabError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
