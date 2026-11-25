#!/usr/bin/env python3
"""Compare the package materializer with extracted, pinned Studio preparation.

Standard library only. This exercises source preparation against synthetic file
placeholders. It never constructs Studio, contacts a service, decodes real images,
loads models, or submits generation. Runtime and pixel validation are stubbed;
the emitted report lists those boundaries explicitly.
"""
from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager
import copy
from decimal import Decimal, InvalidOperation
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import sys
import tempfile
from types import SimpleNamespace


ROUTES = {"klein4-reference", "klein9-copy-pose", "klein9-skeleton", "qwen-3ref"}
PINNED_REVISION = "0270760a3d4fd9e005a1788bba59d8242b77c2f4"
PINNED_SOURCE_SHA256 = {
    "app/server.py": "bcf3f1e628e345cf827cbf73a203ee27e4cf0c04f757176c8d954c05a29688aa",
    "app/references.py": "fb65b4fd8f0194c64f09871e61c19c4b71d53adc653757d6c2a744041a2ecdea",
    "presets/catalog.json": "8a246463e974720a70140d71ceabf8ca66dd962467d302011a2e1eed029ec214",
}
STUBS = [
    "worker availability and backend admission",
    "image decoding: synthetic references report 832 by 1248 pixels",
    "live installed-model inventory: empty observation, no model access",
    "continuation placeholder and continuation/tile/parallax validators",
    "Wan capacity, host memory preflight and i2v source validation",
    "copying uploads into the backend input directory",
]


def studio_hash(value):
    """Production.fingerprint uses ASCII-escaped canonical JSON."""
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def verify_source_pins(source_root):
    """Even behavior-preserving source edits invalidate this pinned-source claim."""
    actual = {}
    for name, expected in PINNED_SOURCE_SHA256.items():
        actual[name] = hashlib.sha256((Path(source_root) / name).read_bytes()).hexdigest()
        if actual[name] != expected:
            raise ValueError("Pinned source bytes differ: " + name)
    return actual


def _extract_functions(tree, names):
    found = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names}
    if set(found) != set(names):
        raise ValueError("Pinned source functions unavailable: " + ", ".join(sorted(set(names) - set(found))))
    return [found[name] for name in sorted(names)]


def _extract_assignments(tree, names):
    rows = [node for node in tree.body if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id in names for target in node.targets)]
    found = {target.id for node in rows for target in node.targets if isinstance(target, ast.Name)}
    if not set(names) <= found:
        raise ValueError("Pinned source constants unavailable")
    return rows


def _compile(body, namespace, filename):
    module = ast.fix_missing_locations(ast.Module(body=body, type_ignores=[]))
    exec(compile(module, filename, "exec"), namespace)


@contextmanager
def package_modules(package):
    """Use only the selected package, including when called from unittest."""
    previous_path = list(sys.path)
    previous = {name: sys.modules.get(name) for name in ("qualification", "_p35_contract_plan")}
    try:
        sys.path.insert(0, str(package))
        for name, filename in (("qualification", "qualification.py"), ("_p35_contract_plan", "plan.py")):
            spec = importlib.util.spec_from_file_location(name, package / filename)
            if spec is None or spec.loader is None:
                raise ValueError("Cannot load the selected qualification package")
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
        yield sys.modules["_p35_contract_plan"]
    finally:
        sys.path[:] = previous_path
        for name, module in previous.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def source_preparer(source_root):
    reference_path = source_root / "app" / "references.py"
    reference_tree = ast.parse(reference_path.read_text(encoding="utf-8"))
    reference_names = {"apply_drawn_pose_sidecar", "board_spec", "board_transform", "scale_node", "scaled_size",
                       "prune_missing_slot", "prune_empty_board", "compile_board", "reference_transform",
                       "guidance_text", "compile_references"}
    reference_constants = {"ROLES", "BOARD_POLICY", "DRAWN_POSE_FILENAME", "DRAWN_POSE_ARTIFACT_ID"}
    reference_namespace = {"copy": copy, "hashlib": hashlib, "math": math, "re": re, "Path": Path}
    _compile(_extract_assignments(reference_tree, reference_constants) + _extract_functions(reference_tree, reference_names),
             reference_namespace, str(reference_path))

    server_path = source_root / "app" / "server.py"
    server_tree = ast.parse(server_path.read_text(encoding="utf-8"))
    classes = [node for node in server_tree.body if isinstance(node, ast.ClassDef) and node.name == "Studio"]
    if len(classes) != 1:
        raise ValueError("Pinned Studio class unavailable")
    method_names = {"prepare", "_bind", "_bind_control", "_prepare_i2v", "_lora_file", "prune_disabled_loras"}
    extracted = ast.ClassDef(name="PreparationOnly", bases=[], keywords=[], decorator_list=[],
                             body=_extract_functions(classes[0], method_names))

    def regular_only(value):
        if value != "regular":
            raise ValueError("This source check admits regular synthetic fixtures only")
        return value

    noop = SimpleNamespace(validate=lambda *args: None)
    namespace = {"Path": Path, "re": re, "hashlib": hashlib, "Decimal": Decimal, "InvalidOperation": InvalidOperation,
                 "StudioError": ValueError, "privacy_scope": SimpleNamespace(normalize=regular_only),
                 "continuation": SimpleNamespace(unfilled=lambda *args: [], validate=lambda *args: None),
                 "tiles": noop, "parallax": noop, "wan_capacity": SimpleNamespace(enforce=lambda *args: None),
                 "compile_references": reference_namespace["compile_references"]}
    constants = {"CONTROL_KEYS", "LORA_SLOTS", "LORA_NAME_KEYS", "NUMBER_RANGES"}
    _compile(_extract_assignments(server_tree, constants) + _extract_functions(server_tree, {"number", "is_off"}) + [extracted],
             namespace, str(server_path))
    return namespace["PreparationOnly"], reference_namespace


def fixture_owner(planner, suite, uploads):
    owner = planner.owner_template(suite)
    owner["expected_identity"]["workspace"] = str(uploads.parent)
    lookup = {}

    def bind(record, index, label, suffix):
        name = f"{index:032x}_{suffix}.png"
        raw = ("Synthetic P35 preparation fixture only: " + label).encode("utf-8")
        (uploads / name).write_bytes(raw)
        record.update(file=name, sha256=hashlib.sha256(raw).hexdigest())
        lookup[name] = record

    for index, (name, record) in enumerate(owner["reference_bindings"].items(), 1):
        bind(record, index, name, "fixture")
    for index, (name, record) in enumerate(owner["guides"].items(), 1001):
        bind(record, index, "guide-" + name, "drawn-pose")
    bind(owner["default_style"], 9999, "default-style", "fixture-style")
    for name, record in owner["characters"].items():
        record.update(description="Synthetic original adult character " + name + " — Épée",
                      outfit="teal coat and brass clasp", style="two-tone cel shading", details=["violet eyes"])
    return owner, lookup


def check_contract(source_root, package):
    source_root, package = Path(source_root).resolve(), Path(package).resolve()
    sources = verify_source_pins(source_root)
    prepare_class, reference_namespace = source_preparer(source_root)
    with package_modules(package) as planner, tempfile.TemporaryDirectory(prefix="p35-source-contract-") as temporary:
        bundle = planner.read_json(package / "routes.json")
        planner.validate_bundle(package, bundle)
        if bundle.get("source_revision") != PINNED_REVISION:
            raise ValueError("Route bundle names another source revision")
        if {route["id"] for route in bundle["routes"]} != ROUTES:
            raise ValueError("This source comparison supports exactly the four frozen P35 routes")
        suite = planner.read_json(package / "suite.json")
        catalog = planner.read_json(source_root / "presets" / "catalog.json")["presets"]
        case = next(case for case in suite["cases"] if case["id"] == "ordinary-neutral")
        uploads = Path(temporary) / "uploads"
        uploads.mkdir()
        owner, records = fixture_owner(planner, suite, uploads)

        def image_record(root, name):
            if Path(root) != uploads or name not in records:
                raise ValueError("Preparation requested an undeclared fixture source")
            return {"file": name, "sha256": records[name]["sha256"], "width": 832, "height": 1248}

        reference_namespace["image_record"] = image_record
        results = []
        for route in bundle["routes"]:
            matches = [preset for preset in catalog if preset.get("id") == route["preset_id"]]
            if len(matches) != 1 or planner.stable_hash(matches[0]) != route["source"]["catalog_entry_sha256"]:
                raise ValueError("Source catalog entry differs from its frozen route pin: " + route["id"])
            preset = copy.deepcopy(matches[0])
            graph_path = source_root / preset["graph"]
            if graph_path.read_bytes() != (package / route["graph"]).read_bytes():
                raise ValueError("Original and bundled graph bytes differ: " + route["id"])
            studio = prepare_class()
            studio.experiments = Path(temporary)
            studio.require_worker = lambda: None
            studio.preset = lambda identifier, p=preset: copy.deepcopy(p) if identifier == p["id"] else None
            studio.graph_for = lambda p: (planner.read_json(source_root / p["graph"]), source_root / p["graph"])
            studio.options = lambda: {}
            studio._upload_path = lambda name, *args, **kwargs: uploads / name
            studio.ensure_reference_inputs = lambda *args: None
            studio._validate_i2v_mode_source = lambda *args, **kwargs: None
            studio.host_commit_preflight = lambda *args, **kwargs: None
            inputs, problems, unsupported = planner._case_inputs(case, route, owner)
            if problems or unsupported:
                raise ValueError("Synthetic route inputs unexpectedly refused: " + route["id"])
            request = planner._request(case, route, owner, inputs)
            comparisons = []
            for seed in suite["seeds"][:2]:
                stage_request = copy.deepcopy(request)
                stage_request["controls"]["seed"] = seed
                actual_preset, actual, _path, _controls, batch = studio.prepare(stage_request)
                expected = planner.materialize_graph(route, planner.read_json(package / route["graph"]), request, seed)
                if actual != expected or studio_hash(actual) != planner.studio_hash(expected) or batch != 1:
                    raise ValueError("Prepared graph, Production hash or batch differs: " + route["id"])
                prepared_refs = actual_preset.get("_prepared_references", [])
                comparisons.append({"seed": seed, "graph_sha256": studio_hash(actual),
                                    "prepared_reference_slots": len(prepared_refs),
                                    "pruned_reference_slots": [ref["slot"] for ref in prepared_refs if ref.get("pruned")]})
            results.append({"route_id": route["id"], "preset_id": route["preset_id"], "matches": True, "variants": comparisons})
        return {"schema": "p35.source-contract-check/v1", "source_revision": bundle["source_revision"],
                "source_files_sha256": sources, "routes": results, "graph_comparisons": sum(len(row["variants"]) for row in results),
                "fixture_mode": "synthetic_non_image_bytes_and_unicode_prompt", "stubbed_boundaries": STUBS,
                "verification": "Pinned preparation source subset; not live Studio, GPU, image or host qualification",
                "generation_submitted": False, "models_loaded": False, "network_accessed": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--source-root", type=Path)
    args = parser.parse_args(argv)
    source = args.source_root or args.package.resolve().parents[3]
    try:
        result = check_contract(source, args.package)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, StopIteration) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
