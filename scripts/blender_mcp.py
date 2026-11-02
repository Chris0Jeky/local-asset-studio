"""Narrow MCP façade (stdio JSON-RPC) over the typed Blender worker. There is no tool for arbitrary Python.

The Blender executable, the worker's write root and the tree it may read .blend files from are fixed at launch;
an MCP client cannot choose them. Each tool maps to one typed worker command, and the worker enforces its own
allow-lists, precondition checksums and path rules.

    python scripts/blender_mcp.py --blender <blender.exe> --root <write-dir> --blend-root <read-dir>
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import blender_lab as lab
import blender_worker as bw

PROTOCOL = "2025-06-18"
OBJ = lambda props, required=(): {"type": "object", "properties": props, "required": list(required), "additionalProperties": False}
NAME = {"type": "string", "description": "a new plain path relative to the worker root"}
TOOLS = {
    "blender_ping": ("Worker liveness, call count, datablock counts and scene state.", OBJ({})),
    "blender_caps": ("Capability probe of the configured Blender (feature tests, not version checks).", OBJ({})),
    "blender_open": ("Open a .blend under the configured read tree without scripts; allow_edit lists the objects apply_edit may change.",
                     OBJ({"blend": {"type": "string"}, "allow_edit": {"type": "array", "items": {"type": "string"}}}, ["blend"])),
    "blender_describe_scene": ("Typed scene/rig manifest with a semantic checksum.", OBJ({})),
    "blender_render_views": ("Fixed-camera evidence renders (4 views x lit, clay, object-ID, material-ID) into a new folder.",
                             OBJ({"out_dir": NAME, "size": {"type": "integer", "minimum": 64, "maximum": 512},
                                  "samples": {"type": "integer", "minimum": 1, "maximum": 64}}, ["out_dir"])),
    "blender_save_copy": ("Save a copy of the open scene to a new .blend inside the worker root.", OBJ({"path": NAME}, ["path"])),
    "blender_export": ("Export a GLB with the existing LAS settings to a new path inside the worker root.", OBJ({"path": NAME}, ["path"])),
    "blender_apply_edit": ("Bounded edit on an allow-listed object; refused unless expect_checksum equals the current semantic checksum.",
                           OBJ({"object": {"type": "string"},
                                "op": {"type": "string", "enum": ["location", "rotation_euler", "scale", "hide_render", "material", "shape_key"]},
                                "value": {"description": "[x,y,z] | bool | {slot, material} | {key, value}"},
                                "expect_checksum": {"type": "string"}}, ["object", "op", "value", "expect_checksum"])),
    "blender_reimport_validate": ("Export, reimport in a NEW Blender process and compare structure and renders (Asset Parity Sentinel).",
                                  OBJ({"out_dir": {"type": "string", "description": "a new plain folder name"}}, ["out_dir"])),
}


class Facade:
    def __init__(self, blender, root, blend_root):
        self.blender, self.root = lab.executable(blender), Path(root).expanduser().resolve()
        self.blend_root = Path(blend_root).expanduser().resolve()
        lab.require(self.root.is_dir() and self.blend_root.is_dir(), "root and blend_root must be existing directories")
        self.worker = None

    def _worker(self):
        if self.worker is None or self.worker.process.poll() is not None:
            self.worker = bw.BlenderWorker(self.blender, self.root)  # (re)start after a crash or kill
        return self.worker

    def call(self, name, args):
        command = name.removeprefix("blender_")
        if command == "open":
            blend = Path(str(args.get("blend", ""))).expanduser()
            blend = (self.blend_root / blend if not blend.is_absolute() else blend).resolve()
            lab.require(blend.is_relative_to(self.blend_root), "blend must be inside the configured read tree")
            args = {**args, "blend": str(blend)}
        if command == "reimport_validate": return self._worker().reimport_validate(**args)
        return self._worker().call(command, **args)

    def handle(self, message):
        method, ident = message.get("method"), message.get("id")
        if ident is None: return None  # notifications (initialized, cancelled) need no reply
        if method == "initialize":
            result = {"protocolVersion": PROTOCOL, "capabilities": {"tools": {}},
                      "serverInfo": {"name": "las-blender", "version": "1"}}
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": [{"name": n, "description": d, "inputSchema": s} for n, (d, s) in TOOLS.items()]}
        elif method == "tools/call":
            params = message.get("params") or {}
            name, args = params.get("name"), params.get("arguments") or {}
            if name not in TOOLS or not isinstance(args, dict):
                return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32602, "message": f"unknown tool {name!r}"}}
            try:
                result = {"content": [{"type": "text", "text": json.dumps(self.call(name, args), sort_keys=True)}], "isError": False}
            except (lab.BlenderLabError, OSError, ValueError, TypeError) as exc:
                result = {"content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"[:2000]}], "isError": True}
        else:
            return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32601, "message": f"method {method!r} not supported"}}
        return {"jsonrpc": "2.0", "id": ident, "result": result}

    def close(self):
        if self.worker is not None: self.worker.close()


def serve(facade, stdin=sys.stdin, stdout=sys.stdout):
    try:
        for line in stdin:
            if not line.strip(): continue
            try: message = json.loads(line)
            except ValueError:
                reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
            else:
                reply = facade.handle(message) if isinstance(message, dict) else {
                    "jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "invalid request"}}
            if reply is not None:
                stdout.write(json.dumps(reply) + "\n"); stdout.flush()
    finally:
        facade.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--blend-root", required=True)
    args = parser.parse_args(argv)
    os.makedirs(args.root, exist_ok=True)
    serve(Facade(args.blender, args.root, args.blend_root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
