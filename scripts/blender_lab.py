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
from urllib import error as url_error, request as url_request
from urllib.parse import urlsplit


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
    # --python-exit-code 1: a Python exception inside Blender must not leave a receipt with exit code 0.
    return [str(blender_path), "--background", "--factory-startup", "--disable-autoexec", "--python-exit-code", "1",
            "--python", str(BPY_SCRIPT),
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


GPU_ENGINES = {"BLENDER_WORKBENCH", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"}
HEAVY_GPU_SECONDS = 30  # the R&D programme's lease threshold for renders


def gpu_cost(*evidence_records):
    """Measured render time split by device from evidence records, and its class at the 30 s lease threshold."""
    gpu = cpu = 0.0
    for evidence in evidence_records:
        for pass_name, seconds in (evidence.get("timings") or {}).items():
            on_gpu = (evidence["id_passes"]["engine"] in GPU_ENGINES) if pass_name != "lit" else evidence["lit"]["device"] != "CPU"
            gpu, cpu = (gpu + seconds, cpu) if on_gpu else (gpu, cpu + seconds)
    return {"gpu_seconds": round(gpu, 3), "cpu_seconds": round(cpu, 3),
            "class": "heavy" if gpu > HEAVY_GPU_SECONDS else "light", "heavy_above_gpu_seconds": HEAVY_GPU_SECONDS}


class StudioGpuLease:
    """Hold the Studio's GPU lease (POST /api/gpu-lease) around a Blender run. The Studio grants it only when its own
    work is idle and then pauses its ComfyUI, so take it only for heavy GPU work, never by default."""

    def __init__(self, studio_url, holder=None, ttl_seconds=900):
        parts = urlsplit(studio_url)
        require(parts.scheme == "http" and parts.hostname in ("127.0.0.1", "localhost") and parts.port
                and not parts.username and parts.path in ("", "/"), "studio_url must be http://127.0.0.1:<port>")
        require(type(ttl_seconds) is int and 60 <= ttl_seconds <= 4 * 3600, "ttl_seconds must be 60..14400")
        import uuid
        # One holder per run: the Studio treats a repeat acquire by the same holder as a renewal, so a shared name would
        # let one run release the lease another run is still rendering under.
        holder = holder or f"blender-lab-{uuid.uuid4().hex[:12]}"
        self.origin, self.holder, self.ttl, self.grant = f"http://{parts.hostname}:{parts.port}", holder, ttl_seconds, None

    def _post(self, path, payload):
        call = url_request.Request(self.origin + path, data=json.dumps(payload).encode(), method="POST",
                                   headers={"Content-Type": "application/json", "Origin": self.origin})
        try:
            with url_request.urlopen(call, timeout=60) as response: return json.loads(response.read() or b"{}")
        except url_error.HTTPError as exc:
            detail = json.loads(exc.read() or b"{}") if exc.headers.get("Content-Type", "").startswith("application/json") else {}
            raise BlenderLabError(f"Studio GPU lease {path} refused ({exc.code}): {detail.get('code')}: {detail.get('error')}") from exc
        except (url_error.URLError, OSError) as exc:
            raise BlenderLabError(f"Studio GPU lease {path} unreachable: {exc}") from exc

    def __enter__(self):
        try:
            self.grant = self._post("/api/gpu-lease", {"holder": self.holder, "ttl_seconds": self.ttl})
        except BlenderLabError as exc:
            if "refused (" not in str(exc):  # the grant may have happened: release this run's own holder, best effort
                try: self._post("/api/gpu-lease/release", {"holder": self.holder})
                except BlenderLabError: pass
            raise
        require(self.grant.get("granted") is True, "Studio did not grant the GPU lease")
        return self.grant

    def __exit__(self, *exc):
        self.released = self._post("/api/gpu-lease/release", {"holder": self.holder})


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
    # The collector refuses symlinks; check the caller's paths before resolving would hide them.
    raw_blend, raw_out = Path(blend_path).expanduser(), Path(out_path).expanduser()
    require(not raw_blend.is_symlink() and not raw_out.is_symlink(), "blend and out must not be symlinks")
    blend, out = raw_blend.resolve(), raw_out.resolve()
    require(blend.is_file() and blend.suffix.lower() == ".blend", "blend must be an existing .blend file")
    require(not out.exists(), "out must be a new file")
    before = file_sha(blend)
    run(exe, ["scene-v1", "--blend", blend, "--out", out], out.with_name(out.stem + ".log.json"), timeout)
    require(file_sha(blend) == before, "Source .blend changed during the observation")
    observation = json.loads(out.read_text(encoding="utf-8"))
    require(observation.get("format") == "studio.dcc-scene/v1" and observation.get("complete") is True,
            "Observation is not a complete studio.dcc-scene/v1 record")
    return observation


def dcc_bundle(blender_path, blend_path, out_dir, cameras=None, timeout=300):
    """Exact observation plus the fixed-camera renders of one .blend, written as a `studio.dcc-evidence/v1` bundle so
    `studio_workflow.dcc_evidence.compare_bundles` can strictly compare two captures (an unchanged rerun, before and
    after an edit). Pass the first bundle's `cameras.json` to the second so the capture contracts match."""
    import shutil
    exe = executable(blender_path)
    target = Path(out_dir).expanduser().resolve()
    require(not target.exists(), "out_dir must be new")
    blend = Path(blend_path).expanduser().resolve()
    require(blend.is_file() and blend.suffix.lower() == ".blend", "blend must be an existing .blend file")
    target.mkdir(parents=True)
    work = target / "work"; work.mkdir()
    scene_v1(exe, blend, target / "scene.json", timeout)
    args = ["evidence", "--blend", blend, "--out-dir", work / "capture", "--out", work / "capture.json"]
    if cameras: args += ["--cameras", Path(cameras).expanduser().resolve()]
    run(exe, args, work / "capture.log.json", timeout)
    evidence = json.loads((work / "capture" / "evidence.json").read_text(encoding="utf-8"))
    spec = evidence["camera_spec"]
    (target / "cameras.json").write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    (target / "views").mkdir()
    views = {}
    for name in sorted(evidence["files"]):
        view_id = name.removesuffix(".png").replace(".", "-")  # dcc view ids allow [a-z0-9_-] only
        shutil.copyfile(work / "capture" / "renders" / name, target / "views" / f"{view_id}.png")
        views[view_id] = {"path": f"views/{view_id}.png", "sha256": file_sha(target / "views" / f"{view_id}.png")}
    canonical = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    bundle = {"format": "studio.dcc-evidence/v1",
              "capture_contract": {"view_ids": sorted(views), "resolution": [evidence["size"], evidence["size"]],
                                   "camera_rig_sha256": hashlib.sha256(canonical(spec)).hexdigest(),
                                   "render_settings": {k: evidence[k] for k in ("lit", "id_passes", "view_transform")}},
              "views": views, "scene": {"path": "scene.json", "sha256": file_sha(target / "scene.json")},
              "producer": {"tool": "scripts/blender_lab.py dcc-bundle", "blender": exe.as_posix(), "source_sha256": file_sha(blend)}}
    (target / "evidence.json").write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return bundle


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
    bundle_parser = commands.add_parser("dcc-bundle")
    bundle_parser.add_argument("--blender", required=True)
    bundle_parser.add_argument("--blend", required=True)
    bundle_parser.add_argument("--out-dir", required=True)
    bundle_parser.add_argument("--cameras")
    scene_parser = commands.add_parser("scene-v1")
    scene_parser.add_argument("--blender", required=True)
    scene_parser.add_argument("--blend", required=True)
    scene_parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "dcc-bundle":
            bundle = dcc_bundle(args.blender, args.blend, args.out_dir, args.cameras)
            print(json.dumps({"out_dir": args.out_dir, "views": len(bundle["views"])}))
            return 0
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
