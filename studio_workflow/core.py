"""Bounded, non-executing API-graph authoring. Not ComfyUI's runtime validator.

The authoring document retains disconnected/disabled nodes. Compilation emits only
selected output closures and never invents a bypass. Unknown UI behaviours require
an adapter; no node JavaScript, Python, expression or URL is executed here.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from typing import Any

VERSION = "studio.workflow/v1"
MAX_BYTES = 1024 * 1024
MAX_NODES = 256
ID = re.compile(r"[A-Za-z0-9_.-]{1,96}\Z")
RESERVED = {"__proto__", "prototype", "constructor"}
SCALARS = {"INT", "FLOAT", "STRING", "BOOLEAN"}


def need(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def decode(raw: bytes | str) -> Any:
    raw = raw.encode("utf-8") if isinstance(raw, str) else raw
    need(len(raw) <= MAX_BYTES, "Document exceeds the 1 MiB authoring limit")
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "Duplicate JSON key: " + key)
            need(key not in RESERVED, "Reserved object key: " + key)
            result[key] = value
        return result
    def constant(value):
        raise ValueError("Non-finite JSON number: " + value)
    try:
        value = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
        _bounded(value)
        return value
    except (RecursionError, UnicodeError) as exc:
        raise ValueError("Invalid or excessively nested JSON") from exc


def _bounded(value: Any, depth: int = 0) -> None:
    need(depth <= 48, "Document nesting exceeds 48 levels")
    if isinstance(value, dict):
        for key, item in value.items():
            need(isinstance(key, str) and key not in RESERVED, "Invalid object key")
            _bounded(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _bounded(item, depth + 1)
    elif isinstance(value, float):
        need(math.isfinite(value), "Numbers must be finite")
    else:
        need(value is None or type(value) in (str, int, bool), "JSON values required")


def link(value: Any) -> bool:
    return (isinstance(value, list) and len(value) == 2 and isinstance(value[0], str)
            and type(value[1]) is int and value[1] >= 0)


def compatible(source: str, target: str) -> bool:
    if not isinstance(source, str) or not isinstance(target, str):
        return False
    from .node_inputs import socket_tokens
    left, right = socket_tokens(source), socket_tokens(target)
    return bool(left and right and (left & right or "*" in left or "*" in right))


def _input(name: str, descriptor: Any, required: bool) -> dict:
    from .node_inputs import descriptor as adapt
    return adapt(name, descriptor, required)


def catalog(info: dict, backend_id: str) -> dict:
    need(isinstance(info, dict), "ComfyUI returned no node definitions")
    nodes = {}
    for class_type, raw in info.items():
        if not isinstance(class_type, str) or class_type in RESERVED:
            continue
        from .node_inputs import inputs as input_ports, evidence
        inputs, schema_errors = input_ports(raw)
        source_definition_json = evidence(raw)
        raw = raw if isinstance(raw, dict) else {}
        from .node_outputs import outputs as output_ports
        outputs, output_errors = output_ports(raw)
        schema_errors.extend(output_errors)
        if 'output_node' in raw and type(raw['output_node']) is not bool:
            schema_errors.append('output_node must be boolean')
        nodes[class_type] = {"class_type": class_type, "name": raw.get("display_name") or class_type,
                             "category": raw.get("category", "Uncategorized"),
                             "description": raw.get("description", ""), "inputs": inputs, "outputs": outputs,
                             "output_node": raw.get("output_node") is True,
                             "module": raw.get("python_module"), "schema_errors": schema_errors,
                             "source_definition_json": source_definition_json,
                             "unsupported": bool(schema_errors) or any(i["widget"] == "unsupported" for i in inputs)}
    return {"version": 1, "backend_id": backend_id, "schema_sha256": digest(info), "nodes": nodes,
            "generation_submitted": False,
            "notice": "Installed schema, not an execution or custom-widget compatibility guarantee."}


def new_document(graph: dict, schema: dict, name: str = "Untitled workflow") -> dict:
    need(isinstance(graph, dict) and "nodes" not in graph and "prompt" not in graph,
         "Import an API-format node map, not a visual workflow or /prompt envelope")
    doc = {"format": VERSION, "name": name, "revision": 0, "backend_id": schema["backend_id"],
           "schema_sha256": schema["schema_sha256"], "nodes": copy.deepcopy(graph),
           "outputs": [key for key, node in graph.items() if isinstance(node, dict)
                       and schema["nodes"].get(node.get("class_type"), {}).get("output_node")],
           "disabled": [], "bypass": {}, "positions": {}}
    document(doc)
    return doc


def document(value: dict) -> dict:
    need(isinstance(value, dict) and value.get("format") == VERSION, "Expected " + VERSION)
    need(len(canonical(value)) <= MAX_BYTES, "Document exceeds the 1 MiB authoring limit")
    _bounded(value)
    need(set(value) <= {"format", "name", "revision", "backend_id", "schema_sha256", "nodes", "outputs",
                        "disabled", "bypass", "positions", "source", "steps"}, "Unknown document fields")
    need(isinstance(value.get("name"), str) and len(value["name"]) <= 160, "Name must be at most 160 characters")
    need(type(value.get("revision")) is int and 0 <= value["revision"] <= 2**53 - 1, "Invalid document revision")
    need(isinstance(value.get("backend_id"), str) and bool(value["backend_id"]), "Backend identity required")
    need(isinstance(value.get("schema_sha256"), str) and re.fullmatch(r"[0-9a-f]{64}", value["schema_sha256"]),
         "Schema fingerprint required")
    nodes = value.get("nodes")
    need(isinstance(nodes, dict) and len(nodes) <= MAX_NODES, "Use at most 256 nodes")
    for key, node in nodes.items():
        need(bool(ID.fullmatch(key)) and key not in RESERVED, "Invalid node ID")
        need(isinstance(node, dict) and set(node) <= {"class_type", "inputs", "_meta"}, "Invalid API node: " + key)
        need(isinstance(node.get("class_type"), str) and node["class_type"] not in RESERVED, "Node class required: " + key)
        need(isinstance(node.get("inputs"), dict), "Node inputs required: " + key)
        if "_meta" in node:
            need(isinstance(node["_meta"], dict), "Node metadata must be an object")
    for name in ("outputs", "disabled"):
        ids = value.get(name)
        need(isinstance(ids, list) and all(isinstance(x, str) and x in nodes for x in ids), "Invalid " + name)
        need(len(set(ids)) == len(ids), "Duplicate " + name)
    need(isinstance(value.get("bypass"), dict), "Bypass map required")
    for key, mapping in value["bypass"].items():
        need(key in nodes and isinstance(mapping, dict), "Invalid bypass node")
        for output, field in mapping.items():
            need(bool(re.fullmatch(r"0|[1-9][0-9]{0,3}", output)) and isinstance(field, str)
                 and field in nodes[key]["inputs"], "Bypass maps an output index to an existing input name")
    positions = value.get("positions")
    need(isinstance(positions, dict), "Positions must be an object")
    for key, xy in positions.items():
        need(key in nodes and isinstance(xy, list) and len(xy) == 2
             and all(type(n) in (int, float) and math.isfinite(n) and abs(n) <= 100000 for n in xy),
             "Invalid node position")
    if "steps" in value:
        from .steps import validate_steps
        validate_steps(value)
    return copy.deepcopy(value)


def compile_document(value: dict, schema: dict) -> dict:
    doc = document(value)
    errors, warnings = [], []
    def error(code, message, node=None, field=None):
        errors.append({"code": code, "message": message, "node": node, "field": field})
    if doc["backend_id"] != schema["backend_id"] or doc["schema_sha256"] != schema["schema_sha256"]:
        error("stale_schema", "Environment or installed node definitions changed. Reload and deliberately rebase the draft.")
    if not doc["outputs"]:
        error("no_output", "Select at least one output node to compile")
    graph, visiting = {}, set()
    nodes, definitions, disabled = doc["nodes"], schema["nodes"], set(doc["disabled"])

    def resolve(value, trail=()):
        if not link(value):
            return copy.deepcopy(value)
        key, port = value
        if key not in disabled:
            return list(value)
        need(key not in trail, "Disabled-node bypass cycle")
        field = doc["bypass"].get(key, {}).get(str(port))
        need(field is not None, "Disabled node " + key + " needs an explicit bypass for output " + str(port))
        replacement = nodes[key]["inputs"].get(field)
        need(link(replacement), "A bypass must forward a connected input, not invent a value")
        kind = definitions.get(nodes[key]["class_type"], {})
        source = next((x for x in kind.get("inputs", []) if x["name"] == field), None)
        output = next((x for x in kind.get("outputs", []) if x["index"] == port), None)
        need(source is not None and output is not None and compatible(source["type"], output["type"]),
             "Bypass input and output types differ")
        result = resolve(replacement, trail + (key,))
        actual_node = nodes.get(result[0], {})
        actual = next((x for x in definitions.get(actual_node.get("class_type"), {}).get("outputs", [])
                       if x["index"] == result[1]), None)
        need(actual is not None and compatible(actual["type"], source["type"])
             and compatible(actual["type"], output["type"]), "Bypass source does not match the declared passthrough types")
        return result

    def visit(key):
        if key in visiting:
            error("cycle", "Connection cycle found", key)
            return
        if key in graph:
            return
        if key not in nodes:
            error("missing_node", "Connection refers to an absent node", key)
            return
        visiting.add(key)
        node = copy.deepcopy(nodes[key])
        kind = definitions.get(node["class_type"])
        if kind is None:
            error("missing_class", "Node is not installed: " + node["class_type"], key)
            kind = {"inputs": [], "outputs": []}
        for problem in kind.get("schema_errors", []):
            error("invalid_node_schema", problem, key)
        if kind.get("output_node") and key not in doc["outputs"]:
            error("unselected_output", "A selected output depends on an unselected output; select it explicitly", key)
        specs = {x["name"]: x for x in kind["inputs"] if not x["hidden"]}
        for field, spec in specs.items():
            if spec["required"] and field not in node["inputs"]:
                error("required_input", "Connect or set " + field, key, field)
        for field, raw in list(node["inputs"].items()):
            spec = specs.get(field)
            if spec is None:
                error("unknown_input", "Input needs an installed schema adapter: " + field, key, field)
                continue
            try:
                current = resolve(raw)
                node["inputs"][field] = current
            except ValueError as exc:
                error("invalid_bypass", str(exc), key, field)
                continue
            if spec["widget"] == "unsupported":
                error("native_adapter_required", spec["reason"], key, field)
                continue
            if link(current):
                other, port = current
                other_node = nodes.get(other)
                outputs = definitions.get(other_node.get("class_type"), {}).get("outputs", []) if other_node else []
                output = next((x for x in outputs if x["index"] == port), None)
                if output is None:
                    error("invalid_port", "Source output does not exist", key, field)
                elif not compatible(output["type"], spec["type"]):
                    error("type_mismatch", str(output["type"]) + " cannot connect to " + spec["type"], key, field)
                visit(other)
            elif spec["widget"] == "unsupported":
                error("native_adapter_required", spec["reason"], key, field)
            elif spec["widget"] == "socket":
                error("connection_required", "A typed connection is required", key, field)
            else:
                options, typ = spec["options"], spec["type"]
                valid = True
                if typ == "INT": valid = type(current) is int
                elif typ == "FLOAT": valid = type(current) in (int, float) and math.isfinite(current)
                elif typ == "BOOLEAN": valid = type(current) is bool
                elif typ == "STRING": valid = isinstance(current, str) and len(current) <= 65536
                elif typ == "COMBO": valid = any(type(current) is type(x) and current == x for x in options.get("options", []))
                if not valid:
                    error("invalid_value", "Value does not match " + typ, key, field)
                elif typ in {"INT", "FLOAT"}:
                    if ("min" in options and current < options["min"]) or ("max" in options and current > options["max"]):
                        error("out_of_range", "Value is outside the node's declared range", key, field)
        visiting.remove(key)
        graph[key] = node

    for key in doc["outputs"]:
        if key in disabled:
            error("disabled_output", "A selected output cannot be disabled", key)
        elif not definitions.get(nodes[key]["class_type"], {}).get("output_node"):
            error("not_output", "Choose a node marked as an output by ComfyUI", key)
        else:
            visit(key)
    omitted = sorted(set(nodes) - set(graph))
    if omitted:
        warnings.append({"code": "omitted_nodes", "message": "Disconnected, disabled or unselected branches are retained in the document, not emitted.", "nodes": omitted})
    warnings.append({"code": "authoring_only", "message": "Static authoring checks only. ComfyUI runtime validation, model compatibility, resources and custom-node behaviour are not certified. No generation was submitted."})
    return {"valid": not errors, "errors": errors, "warnings": warnings,
            "graph": graph if not errors else None, "graph_sha256": digest(graph) if not errors else None,
            "document_sha256": digest(doc), "generation_submitted": False}
