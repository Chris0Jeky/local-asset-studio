"""Narrow MCP façade (stdio JSON-RPC) over the typed Blender worker. There is no tool for arbitrary Python.

The Blender executable, the worker's write root and the tree it may read .blend files from are fixed at launch;
an MCP client cannot choose them. Each tool maps to one typed worker command, and the worker enforces its own
allow-lists, precondition checksums and path rules.

    python scripts/blender_mcp.py --blender <blender.exe> --root <write-dir> --blend-root <read-dir>
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import blender_lab as lab
import blender_worker as bw

PROTOCOL = "2025-06-18"
OBJ = lambda props, required=(): {"type": "object", "properties": props, "required": list(required), "additionalProperties": False}
NAME = {"type": "string", "description": "a new plain path relative to the worker root"}
SCENE_BYTES = 32768
SCENE_FIELDS = ("name", "type", "parent", "parent_type", "parent_bone", "matrix_world", "hide_render", "visible")
SHA = re.compile(r"[a-f0-9]{64}")
TOOLS = {
    "blender_ping": ("Worker liveness, call count, datablock counts and scene state.", OBJ({})),
    "blender_caps": ("Capability probe of the configured Blender (feature tests, not version checks).", OBJ({})),
    "blender_open": ("Open a .blend under the configured read tree without scripts; allow_edit lists the objects apply_edit may change.",
                     OBJ({"blend": {"type": "string"}, "allow_edit": {"type": "array", "items": {"type": "string"}}}, ["blend"])),
    "blender_describe_scene": ("Typed scene manifest; small auto replies stay complete, otherwise a bounded object summary with "
                               "the full-scene checksum and a continuation cursor. Matrices are world-space, not local edit values.",
                               OBJ({"mode": {"type": "string", "enum": ["auto", "summary"], "default": "auto"},
                                    "objects": {"type": "array", "minItems": 1, "maxItems": 100, "uniqueItems": True,
                                                "items": {"type": "string", "minLength": 1, "maxLength": 256},
                                                "description": "Exact, case-sensitive object names; repeat the same selection with a cursor."},
                                    "cursor": {"type": "string", "minLength": 1, "maxLength": 512,
                                               "description": "Continue the same summary and unchanged scene; omit to start again."},
                                    "max_bytes": {"type": "integer", "minimum": 4096, "maximum": 65536, "default": SCENE_BYTES,
                                                  "description": "UTF-8 bytes of the serialized MCP result, including content escaping; excludes the outer JSON-RPC envelope and ID."}})),
    "blender_render_views": ("Fixed-camera evidence renders (4 views x lit, clay, object-ID, material-ID) into a new folder.",
                             OBJ({"out_dir": NAME, "size": {"type": "integer", "minimum": 64, "maximum": 512},
                                  "samples": {"type": "integer", "minimum": 1, "maximum": 64}}, ["out_dir"])),
    "blender_save_copy": ("Save a copy of the open scene to a new .blend inside the worker root.", OBJ({"path": NAME}, ["path"])),
    "blender_export": ("Export a GLB with the existing LAS settings to a new path inside the worker root.", OBJ({"path": NAME}, ["path"])),
    "blender_apply_edit": ("Bounded edit on an allow-listed object; refused unless expect_checksum equals the current semantic checksum.",
                           OBJ({"object": {"type": "string"},
                                "op": {"type": "string", "enum": ["location", "rotation_euler", "scale", "hide_render", "material", "shape_key", "delete"]},
                                "value": {"description": "[x,y,z] | bool | {slot, material} | {key, value}"},
                                "expect_checksum": {"type": "string"}}, ["object", "op", "value", "expect_checksum"])),
    "blender_compare_to": ("Compare the open scene with a reference .blend under the read tree: semantic checksums, structural "
                           "differences (phrased reference -> current; 'after the roundtrip' means 'in the current scene') and "
                           "localised visual changes ('material A -> B on Mesh', 'object X is missing or hidden here').",
                           OBJ({"reference": {"type": "string"}}, ["reference"])),
    "blender_reimport_validate": ("Export, reimport in a NEW Blender process and compare structure and renders (Asset Parity Sentinel).",
                                  OBJ({"out_dir": {"type": "string", "description": "a new plain folder name"}}, ["out_dir"])),
}


def text_result(value):
    return {"content": [{"type": "text", "text": json.dumps(value, sort_keys=True)}], "isError": False}


def result_bytes(result):
    # Match serve's JSON encoding, including the nested text's quotes, backslashes and Unicode escapes.
    # The caller-owned JSON-RPC ID/envelope is deliberately outside this tool-result budget.
    return len(json.dumps(result).encode("utf-8"))


def scene_options(args):
    """Validate all facade options before starting or calling Blender; none are worker arguments."""
    mode, names, budget = args.get("mode", "auto"), args.get("objects"), args.get("max_bytes", SCENE_BYTES)
    lab.require(isinstance(mode, str) and mode in ("auto", "summary"), "mode must be auto or summary")
    lab.require(type(budget) is int and 4096 <= budget <= 65536, "max_bytes must be an integer from 4096 to 65536")
    if "objects" in args:
        lab.require(isinstance(names, list) and 1 <= len(names) <= 100
                    and all(isinstance(n, str) and 1 <= len(n) <= 256 for n in names),
                    "objects must contain 1 to 100 exact names, each a string of 1 to 256 characters")
        lab.require(len(set(names)) == len(names), "objects must contain unique names")
        names = sorted(names)  # no case folding or Unicode normalization
    selection = hashlib.sha256(json.dumps(names, separators=(",", ":")).encode("utf-8")).hexdigest()
    cursor = None
    if "cursor" in args:
        token = args["cursor"]
        lab.require(isinstance(token, str) and 1 <= len(token) <= 512 and re.fullmatch(r"[A-Za-z0-9_-]+", token),
                    "cursor must be a bounded summary continuation token")
        try: cursor = json.loads(base64.b64decode(token + "=" * (-len(token) % 4), altchars=b"-_", validate=True))
        except (ValueError, UnicodeError): raise lab.BlenderLabError("cursor is malformed") from None
        lab.require(isinstance(cursor, dict) and set(cursor) == {"version", "mode", "checksum", "selection", "offset"}
                    and type(cursor["version"]) is int and cursor["version"] == 1 and cursor["mode"] == "summary"
                    and all(isinstance(cursor[k], str) and SHA.fullmatch(cursor[k]) for k in ("checksum", "selection"))
                    and type(cursor["offset"]) is int and cursor["offset"] > 0, "cursor is malformed or unsupported")
        lab.require(cursor["selection"] == selection, "cursor objects selection changed; repeat the same exact names")
    return {"mode": mode, "objects": names, "selection": selection, "cursor": cursor, "max_bytes": budget}


def scene_result(manifest, options):
    budget, names, cursor = options["max_bytes"], options["objects"], options["cursor"]
    if options["mode"] == "auto" and names is None and cursor is None:
        full = text_result(manifest)
        if result_bytes(full) <= budget: return full
    lab.require(isinstance(manifest, dict) and isinstance(manifest.get("semantic_checksum"), str)
                and SHA.fullmatch(manifest["semantic_checksum"]), "Scene manifest has no usable semantic checksum")
    source = manifest.get("objects")
    lab.require(isinstance(source, list) and all(isinstance(o, dict) and isinstance(o.get("name"), str)
                and all(k in o for k in SCENE_FIELDS) for o in source), "Scene manifest lacks typed object summaries")
    indexed = {o["name"]: o for o in source}
    lab.require(len(indexed) == len(source), "Scene manifest has duplicate object names")
    if names is not None:
        missing = set(names) - indexed.keys()
        lab.require(not missing, f"{len(missing)} requested object name(s) were not found; use summary mode to inspect exact names")
    selected = [indexed[n] for n in (names if names is not None else sorted(indexed))]
    start = 0
    if cursor is not None:
        lab.require(cursor["checksum"] == manifest["semantic_checksum"], "Scene changed since this cursor; start again without cursor")
        start = cursor["offset"]
        lab.require(start < len(selected), "cursor offset is outside this scene selection; start again without cursor")
    kept = {"schema", "kind", "semantic_checksum", "objects", "blender", "source", "scene", "counts"}
    header = {k: manifest[k] for k in ("blender", "source", "scene", "counts") if k in manifest}
    header.update(schema="las.blender-scene-summary.v1", kind="scene-summary", semantic_checksum=manifest["semantic_checksum"],
                  checksum_scope="full-scene", transform_space="world",
                  summary_reason="continuation" if cursor else "objects_filter" if names is not None else
                                 "requested" if options["mode"] == "summary" else "result_budget",
                  omitted_sections={k: len(v) if isinstance(v, (list, dict)) else None for k, v in manifest.items() if k not in kept},
                  omitted_object_fields=sorted({k for o in selected for k in o if k not in SCENE_FIELDS}))
    rows = []
    def packed():
        end = start + len(rows)
        next_cursor = None
        if end < len(selected):
            value = {"version": 1, "mode": "summary", "checksum": manifest["semantic_checksum"],
                     "selection": options["selection"], "offset": end}
            next_cursor = base64.urlsafe_b64encode(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).decode().rstrip("=")
        return text_result({**header, "objects": rows, "page": {
            "objects_total": len(source), "objects_selected": len(selected), "objects_excluded_by_filter": len(source) - len(selected),
            "offset": start, "returned": len(rows), "remaining": len(selected) - end, "next_cursor": next_cursor}})
    result = packed()
    lab.require(result_bytes(result) <= budget, "Scene summary metadata cannot fit max_bytes; use a larger allowed budget")
    for obj in selected[start:]:
        rows.append({k: obj[k] for k in SCENE_FIELDS})
        candidate = packed()
        if result_bytes(candidate) > budget:
            rows.pop()
            lab.require(rows, "The next object summary cannot fit max_bytes; no object was skipped. Use a larger allowed budget or another exact name")
            break
        result = candidate
    return result


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
        for key in ("blend", "reference"):  # every .blend the client names must sit inside the read tree
            if key not in args: continue
            given = str(args[key])
            # Refuse absolute, drive, UNC and parent paths before touching the filesystem (a UNC resolve sends SMB/NTLM).
            parts = given.replace("\\", "/").split("/")
            lab.require(given and not given.startswith(("\\", "/")) and ":" not in given and ".." not in parts,
                        f"{key} must be a relative path inside the configured read tree")
            blend = (self.blend_root / given).resolve()
            lab.require(blend.is_relative_to(self.blend_root) and blend.suffix.lower() == ".blend" and blend.is_file(),
                        f"{key} must be an existing .blend inside the configured read tree")
            args = {**args, key: str(blend)}
        if command == "compare_to": return self._worker().compare_to(**args)
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
            name = params.get("name") if isinstance(params, dict) else None
            args = params.get("arguments", {}) if isinstance(params, dict) else None
            if not isinstance(name, str) or name not in TOOLS or not isinstance(args, dict):
                return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32602, "message": f"unknown tool or bad arguments: {name!r}"[:200]}}
            schema = TOOLS[name][1]
            if not set(args) <= set(schema["properties"]) or not set(schema["required"]) <= set(args):
                # only advertised arguments reach the worker (no client-chosen timeouts or internals)
                return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32602, "message": f"{name} takes {sorted(schema['properties'])}"}}
            try: options = scene_options(args) if name == "blender_describe_scene" else None
            except (lab.BlenderLabError, ValueError) as exc:
                return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32602, "message": str(exc)}}
            try:
                value = self.call(name, {} if options is not None else args)
                result = scene_result(value, options) if options is not None else text_result(value)
            except (lab.BlenderLabError, OSError, ValueError, TypeError) as exc:
                result = {"content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"[:2000]}], "isError": True}
                if options is not None and result_bytes(result) > options["max_bytes"]:
                    result = {"content": [{"type": "text", "text": "Scene description failed; error details exceeded max_bytes."}], "isError": True}
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
                try:
                    reply = facade.handle(message) if isinstance(message, dict) else {
                        "jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "invalid request"}}
                except Exception as exc:  # no request may take the server down
                    ident = message.get("id") if isinstance(message, dict) else None
                    reply = {"jsonrpc": "2.0", "id": ident, "error": {"code": -32603, "message": f"{type(exc).__name__}: {exc}"[:500]}}
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
