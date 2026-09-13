"""Build live-document requests and install the optional inert Krita extension.

This script never launches Krita, submits a generation, or edits a document.  A
user invokes the installed GUI actions after choosing a capture and request.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from integrations.krita import document_session as session
from integrations.krita import native_edit
from scripts import character_krita as krita
from scripts.character_study import inside, read_json, relative, require, verify_artifact


PACKAGE_FILES = (
    "__init__.py",
    "plugin.py",
    "document_session.py",
    "native_edit.py",
)
PACKAGE_SOURCE = ROOT / "integrations" / "krita"
PLUGIN_SOURCE = PACKAGE_SOURCE / "studio_session"


def _absolute(value, label):
    path = Path(value)
    require(path.is_absolute(), "Configure an absolute " + label)
    return path.resolve()


def _workspace_file(root, value):
    value = str(value)
    if Path(value).is_absolute():
        path = Path(value).resolve(strict=True)
        require(path.is_relative_to(root), "Artifact escapes workspace")
        return path
    return inside(root, value)


def _record(root, value):
    path = _workspace_file(root, value)
    return {"path": str(path), "sha256": native_edit.digest(path.read_bytes())}


def _artifact(value):
    return isinstance(value, dict) and {"path", "sha256"} <= value.keys() and isinstance(value["path"], str)


def _pin(value, root, pinned, seen_json):
    """Pin explicit artifact records only, following referenced JSON artifacts.

    Records embedded in a workspace plan use the workspace root.  Bundle file
    records are handled separately because they are relative to bundle.json.
    """
    if _artifact(value):
        artifact = {"path": value["path"], "sha256": value["sha256"]}
        path = verify_artifact(root, artifact)
        identity = (str(path), artifact["sha256"])
        pinned[identity] = {"path": str(path), "sha256": artifact["sha256"]}
        if path.suffix.lower() == ".json" and str(path) not in seen_json:
            seen_json.add(str(path))
            _pin(read_json(path), root, pinned, seen_json)
        return
    if isinstance(value, dict):
        for child in value.values():
            _pin(child, root, pinned, seen_json)
    elif isinstance(value, list):
        for child in value:
            _pin(child, root, pinned, seen_json)


def _pins(root, native_plan):
    dependencies = native_plan["dependencies"]
    plan_path = verify_artifact(root, dependencies["plan"])
    current_path = verify_artifact(root, dependencies["current_document"])
    result_path = verify_artifact(root, dependencies["result"])
    source_path = verify_artifact(root, dependencies["native_source"])
    relative(dependencies["bundle"])
    bundle_folder = (root / dependencies["bundle"]).resolve(strict=True)
    require(bundle_folder.is_relative_to(root) and bundle_folder.is_dir() and not bundle_folder.is_symlink(), "Bundle folder escapes workspace")
    bundle_path = bundle_folder / "bundle.json"
    require(bundle_path.is_file() and not bundle_path.is_symlink(), "Missing bundle receipt")

    pinned, seen_json = {}, set()
    for item in (dependencies["plan"], dependencies["current_document"], dependencies["result"], dependencies["native_source"]):
        _pin(item, root, pinned, seen_json)
    for value in (read_json(plan_path), read_json(current_path), read_json(result_path)):
        _pin(value, root, pinned, seen_json)

    bundle = read_json(bundle_path)
    # bundle.source retains its workspace-relative meaning; bundle.files are
    # relative to the folder containing bundle.json.
    _pin({key: value for key, value in bundle.items() if key != "files"}, root, pinned, seen_json)
    for value in bundle.get("files", {}).values():
        _pin(value, bundle_folder, pinned, seen_json)
    bundle_digest = native_edit.digest(bundle_path.read_bytes())
    pinned[(str(bundle_path.resolve()), bundle_digest)] = {"path": str(bundle_path.resolve()), "sha256": bundle_digest}

    require(len(pinned) <= 256, "Native request has more than 256 pinned dependencies")
    return list(pinned.values())


def request(workspace, snapshot, package, out):
    root = Path(workspace).resolve(strict=True)
    require(root.is_dir(), "Workspace must be a directory")
    native_path = _workspace_file(root, str(package).replace("\\", "/").rstrip("/") + "/native-plan.json")
    native_plan = read_json(native_path)
    require(native_plan.get("workspace") == str(root), "Native package belongs to another workspace")
    expected, _ = krita._expected(root, native_plan["dependencies"])
    require(native_plan == expected, "Native plan changed since preparation")
    native_edit.read_plan(native_path)
    capture = _absolute(snapshot, "capture snapshot path")
    output = _absolute(out, "request output path")
    return session.prepare_request(capture, native_path, output, _pins(root, native_plan))


def _source_files(include_proof=False):
    files = {"__init__.py": (PLUGIN_SOURCE / "__init__.py").read_bytes(),
             "plugin.py": (PLUGIN_SOURCE / "plugin.py").read_bytes(),
             "document_session.py": (PACKAGE_SOURCE / "document_session.py").read_bytes(),
             "native_edit.py": (PACKAGE_SOURCE / "native_edit.py").read_bytes()}
    if include_proof:
        proof = PLUGIN_SOURCE / "session_proof.py"
        require(proof.is_file(), "The optional session proof module is not available")
        files["session_proof.py"] = proof.read_bytes()
    return files


def _desktop(module):
    template = (PLUGIN_SOURCE.parent / "studio_session.desktop").read_text(encoding="utf-8")
    return template.replace("@MODULE@", module).encode("utf-8")


def _write_new(path, raw):
    with path.open("xb") as stream:
        stream.write(raw)


def _same_file(path, raw, label):
    require(not path.is_symlink(), label + " is a link")
    require(path.is_file() and path.read_bytes() == raw, label + " differs from its pinned source")


def install(config, target, include_proof=False):
    require(target in {"runner", "gui"}, "Target must be runner or gui")
    require(not include_proof or target == "runner", "Optional proof code is runner-only")
    executable_key = "kritarunner" if target == "runner" else "krita"
    scripts_key = "kritarunner_scripts" if target == "runner" else "krita_scripts"
    executable = _absolute(config.get(executable_key, ""), executable_key + " executable")
    scripts = _absolute(config.get(scripts_key, ""), scripts_key + " directory")
    require(executable.is_file() and not executable.is_symlink(), "Configured " + executable_key + " executable is missing")
    require(executable.suffix.lower() == ".exe", "Configured native executable must be an .exe")
    sources = _source_files(include_proof)
    package_hash = native_edit.digest(b"".join(name.encode("utf-8") + b"\0" + sources[name] for name in sorted(sources)))
    module = "studio_character_session_" + package_hash
    scripts.mkdir(parents=True, exist_ok=True)
    require(scripts.is_dir() and not scripts.is_symlink(), "Configured script directory is unsafe")
    destination = scripts / module
    if destination.exists():
        require(destination.is_dir() and not destination.is_symlink(), "Installed package is not a directory")
        require({path.name for path in destination.iterdir()} == set(sources), "Installed package has an unexpected file set")
        for name, raw in sources.items():
            _same_file(destination / name, raw, "Installed module " + name)
    else:
        destination.mkdir()
        for name, raw in sources.items():
            _write_new(destination / name, raw)
    outputs = {name: {"path": str(destination / name), "sha256": native_edit.digest(raw)} for name, raw in sources.items()}
    if target == "gui":
        desktop = scripts / (module + ".desktop")
        raw = _desktop(module)
        if desktop.exists():
            _same_file(desktop, raw, "Installed desktop entry")
        else:
            _write_new(desktop, raw)
        outputs[desktop.name] = {"path": str(desktop), "sha256": native_edit.digest(raw)}
    return {"target": target, "executable": str(executable), "executable_sha256": native_edit.digest(executable.read_bytes()),
            "module": module, "package_sha256": package_hash, "outputs": outputs,
            "launches_application": False, "generation_submitted": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("request")
    build.add_argument("--workspace", required=True, type=Path)
    build.add_argument("--snapshot", required=True, type=Path)
    build.add_argument("--package", required=True)
    build.add_argument("--out", required=True, type=Path)
    setup = commands.add_parser("install")
    setup.add_argument("--config", required=True, type=Path)
    setup.add_argument("--target", required=True, choices=("runner", "gui"))
    setup.add_argument("--include-proof", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "request":
            value = request(args.workspace, args.snapshot, args.package, args.out)
        else:
            value = install(read_json(args.config), args.target, args.include_proof)
        print(json.dumps(value, indent=2)); return 0
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(2, "character-krita-session: " + str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
