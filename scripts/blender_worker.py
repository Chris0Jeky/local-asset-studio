"""Typed persistent Blender worker: one long-lived background Blender over stdin/stdout pipes, a closed vocabulary.

Commands: ping, caps, open, describe_scene, render_views, save_copy, export, apply_edit (allow-listed objects plus a
precondition checksum), and reimport_validate, which runs host-side: worker evidence and export, then a reimport in a
NEW Blender process (the sentinel's rule), then comparison. Pipes rather than a socket mean no other process can
connect. There is no command that runs caller-supplied code. `fresh_call` is the one-process-per-call fallback.

    python scripts/blender_worker.py bench --blender <blender.exe> --blend <asset.blend> --out-dir <new-dir> [--calls 30]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import queue
import re
import statistics
import subprocess
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import blender_lab as lab
import blender_sentinel as sentinel
from blender_lab import require

REPLY = "@@LAS@@ "
MAX_REQUEST_BYTES = 32 * 1024
OUT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")


class WorkerFailed(lab.BlenderLabError):
    """The worker died, timed out, or refused a request."""


class BlenderWorker:
    def __init__(self, blender_path, root, start_timeout=120):
        exe = lab.executable(blender_path)
        self.root = Path(root).expanduser().resolve()
        require(self.root.is_dir(), "root must be an existing directory")
        self.exe, self.next_id, self.lines = exe, 0, queue.Queue()
        self.log = (self.root / "worker-stderr.log").open("a", encoding="utf-8")
        self.process = subprocess.Popen(lab.command_for(exe, "serve", "--root", self.root), stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=self.log, text=True, encoding="utf-8", errors="replace",
                                        bufsize=1, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        threading.Thread(target=self._pump, daemon=True).start()
        self.ready = self._reply(start_timeout)
        require(self.ready.get("ready") is True, "Worker did not report ready")

    def _pump(self):
        for line in self.process.stdout:
            if line.startswith(REPLY): self.lines.put(json.loads(line[len(REPLY):]))
        self.lines.put(None)  # stdout closed: the process ended

    def _send(self, line):
        try:
            self.process.stdin.write(line); self.process.stdin.flush()
        except OSError:
            pass  # a dead worker is reported by the reply wait

    def _reply(self, timeout):
        try: reply = self.lines.get(timeout=timeout)
        except queue.Empty:
            self.kill(); raise WorkerFailed(f"Worker gave no reply within {timeout} s; killed")
        if reply is None: raise WorkerFailed(f"Worker exited (code {self.process.poll()})")
        return reply

    def call(self, cmd, timeout=300, **args):
        require(self.process.poll() is None, "Worker is not running")
        self.next_id += 1
        line = json.dumps({"id": self.next_id, "cmd": cmd, "args": args}) + "\n"
        require(len(line.encode()) < MAX_REQUEST_BYTES, "request too large")
        started = time.monotonic()
        writer = threading.Thread(target=self._send, args=(line,), daemon=True)
        writer.start()
        writer.join(timeout)  # a worker that stops reading must not block past the deadline
        if writer.is_alive():
            self.kill(); raise WorkerFailed(f"Worker did not accept the request within {timeout} s; killed")
        reply = self._reply(max(0.1, timeout - (time.monotonic() - started)))
        require(reply.get("id") == self.next_id, "Worker reply out of order")
        if not reply["ok"]: raise WorkerFailed(reply["error"])
        return reply["result"]

    def reimport_validate(self, out_dir, timeout=600):
        """Worker-side evidence and export, then the sentinel's new-process reimport and comparison."""
        require(isinstance(out_dir, str) and OUT_NAME.fullmatch(out_dir) is not None and set(out_dir) != {"."}, "out_dir must be a plain name")
        target = self.root / out_dir
        require(not target.exists(), "out_dir must be new")
        (target / "source").mkdir(parents=True)
        source_manifest = self.call("describe_scene")
        (target / "source" / "manifest.json").write_text(json.dumps(source_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        evidence = self.call("render_views", out_dir=f"{out_dir}/source/renders")
        (target / "source" / "evidence.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        export = self.call("export", path=f"{out_dir}/export.glb")
        _, rt_manifest, _, structure, views, warnings, seconds = sentinel.roundtrip_and_compare(self.exe, target, timeout)
        result = {"schema": "las.asset-parity-sentinel.v1", "pass": not structure["failures"] and not warnings,
                  "source": {"semantic_checksum": source_manifest["semantic_checksum"], "counts": source_manifest["counts"]},
                  "export": {"settings": export["settings"], "glb_sha256": lab.file_sha(target / "export.glb")},
                  "roundtrip": {"semantic_checksum": rt_manifest["semantic_checksum"], "seconds": seconds,
                                "process": "new Blender process, factory-empty scene, glTF import"},
                  "structural_failures": structure["failures"], "format_losses": structure["format_losses"],
                  "expected_exclusions": structure["expected_exclusions"], "visual_warnings": warnings, "views": views}
        (target / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return result

    def close(self, timeout=20):
        if self.process.poll() is None:
            try:
                self.process.stdin.write(json.dumps({"cmd": "quit"}) + "\n"); self.process.stdin.flush()
                self.process.wait(timeout)
            except (OSError, subprocess.TimeoutExpired):
                self.kill()
        for stream in (self.process.stdin, self.process.stdout):
            try: stream.close()
            except OSError: pass  # the pipe to a killed process may already be broken
        self.log.close()

    def kill(self):
        if self.process.poll() is None:
            self.process.kill(); self.process.wait(10)

    def __enter__(self): return self
    def __exit__(self, *exc): self.close()


def fresh_call(blender_path, root, blend, cmd, allow_edit=(), **args):
    """Fallback: a new Blender per call (start, open, call, quit)."""
    with BlenderWorker(blender_path, root) as worker:
        worker.call("open", blend=str(blend), allow_edit=list(allow_edit))
        return worker.call(cmd, **args)


def _plan(calls):
    """A mixed agent-like session: reads dominate, with renders, exports and reversible edits."""
    cycle = ["ping", "describe_scene", "apply_edit", "describe_scene", "export", "apply_edit_revert", "describe_scene",
             "render_views", "ping", "save_copy"]
    return [cycle[i % len(cycle)] for i in range(calls)]


def bench(blender_path, blend, out_dir, calls=30, edit_object=None):
    target = Path(out_dir).expanduser().resolve()
    require(not target.exists(), "out_dir must be new")
    target.mkdir(parents=True)
    blend = Path(blend).expanduser().resolve()
    plan = _plan(calls)
    report = {"blender": str(lab.executable(blender_path)), "blend": blend.name, "calls": calls, "plan": plan}
    (target / "probe").mkdir()
    scene = fresh_call(blender_path, target / "probe", blend, "describe_scene")
    edited = next((o for o in scene["objects"] if o["name"] == edit_object), None)
    require(edited is not None, f"--edit-object {edit_object!r} is not in the scene")
    require(edited["parent"] is None or all(row == [float(i == j) for j in range(4)] for i, row in
            enumerate(next(o for o in scene["objects"] if o["name"] == edited["parent"])["matrix_world"])),
            "bench edits need an object whose parent sits at identity")
    origin = [row[3] for row in edited["matrix_world"][:3]]

    def args_for(index, cmd, checksum):
        if cmd in ("apply_edit", "apply_edit_revert"):
            return "apply_edit", {"object": edit_object, "op": "location", "expect_checksum": checksum,
                                  "value": [origin[0], origin[1], origin[2] + 0.25] if cmd == "apply_edit" else origin}
        return cmd, {"render_views": {"out_dir": f"{index:02d}-renders", "size": 128, "samples": 8},
                     "export": {"path": f"{index:02d}-export.glb"}, "save_copy": {"path": f"{index:02d}-copy.blend"}}.get(cmd, {})

    def run(mode):
        root = target / mode
        root.mkdir()
        timings, checks, started = [], {"render_leaks": [], "export_leaks": []}, time.perf_counter()
        worker = BlenderWorker(blender_path, root) if mode == "persistent" else None
        startup = round(time.perf_counter() - started, 3)
        try:
            if worker:
                worker.call("open", blend=str(blend), allow_edit=[edit_object])
                checks["initial"] = worker.call("describe_scene")["semantic_checksum"]
                checks["datablocks_before"], checks["state_before"] = (lambda p: (p["datablocks"], p["state"]))(worker.call("ping"))
            checksum = fresh_call(blender_path, root, blend, "describe_scene")["semantic_checksum"] if not worker else checks["initial"]
            for index, cmd in enumerate(plan):
                name, args = args_for(index, cmd, checksum)
                if not worker and name == "apply_edit":
                    args["expect_checksum"] = checksum = fresh_call(blender_path, root, blend, "describe_scene")["semantic_checksum"]
                before = worker.call("describe_scene")["semantic_checksum"] if worker and name in ("render_views", "export") else None
                tick = time.perf_counter()
                result = (worker.call(name, **args) if worker
                          else fresh_call(blender_path, root, blend, name, allow_edit=[edit_object], **args))
                timings.append({"cmd": cmd, "seconds": round(time.perf_counter() - tick, 4)})
                if name == "apply_edit": checksum = result["after"]
                if before is not None:
                    after = worker.call("describe_scene")["semantic_checksum"]
                    if after != before: checks[f"{name.split('_')[0]}_leaks"].append(index)
            if worker:
                checks["final"] = worker.call("describe_scene")["semantic_checksum"]
                checks["datablocks_after"], checks["state_after"] = (lambda p: (p["datablocks"], p["state"]))(worker.call("ping"))
                checks["fresh_process_checksum"] = fresh_call(blender_path, root, blend, "describe_scene")["semantic_checksum"]
                import psutil
                checks["worker_rss_mb"] = round(psutil.Process(worker.process.pid).memory_info().rss / 2 ** 20, 1)
        finally:
            if worker: worker.close()
        total = round(time.perf_counter() - started, 3)
        by_cmd = {}
        for item in timings: by_cmd.setdefault(item["cmd"], []).append(item["seconds"])
        return {"startup_s": startup, "total_s": total, "calls_s": round(sum(t["seconds"] for t in timings), 3),
                "median_by_cmd": {k: round(statistics.median(v), 4) for k, v in sorted(by_cmd.items())},
                "timings": timings, "checks": checks}

    report["persistent"], report["fresh"] = run("persistent"), run("fresh")
    p, f = report["persistent"], report["fresh"]
    c = p["checks"]
    report["summary"] = {
        "speedup_calls": round(f["calls_s"] / p["calls_s"], 2), "saved_s": round(f["calls_s"] - p["calls_s"], 3),
        "median_speedup_by_cmd": {k: round(f["median_by_cmd"][k] / v, 1) for k, v in p["median_by_cmd"].items() if v},
        "no_state_leak": not c["render_leaks"] and not c["export_leaks"] and c["initial"] == c["final"] == c["fresh_process_checksum"]
                         and c["datablocks_before"] == c["datablocks_after"] and c["state_before"] == c["state_after"]}
    (target / "bench.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    bench_parser = commands.add_parser("bench")
    bench_parser.add_argument("--blender", required=True)
    bench_parser.add_argument("--blend", required=True)
    bench_parser.add_argument("--out-dir", required=True)
    bench_parser.add_argument("--calls", type=int, default=30)
    bench_parser.add_argument("--edit-object", default="Badge")
    args = parser.parse_args(argv)
    try:
        report = bench(args.blender, args.blend, args.out_dir, args.calls, args.edit_object)
    except (lab.BlenderLabError, OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps({"summary": report["summary"], "persistent": {k: report["persistent"][k] for k in ("startup_s", "calls_s", "median_by_cmd")},
                      "fresh": {k: report["fresh"][k] for k in ("calls_s", "median_by_cmd")}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
