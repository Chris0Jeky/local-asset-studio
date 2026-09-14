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
    return session.prepare_request(capture, native_path, output)


def _source_files(include_proof=False):
    files = {"__init__.py": (PLUGIN_SOURCE / "__init__.py").read_bytes(),
             "plugin.py": (PLUGIN_SOURCE / "plugin.py").read_bytes(),
             "document_session.py": (PACKAGE_SOURCE / "document_session.py").read_bytes(),
             "native_edit.py": (PACKAGE_SOURCE / "native_edit.py").read_bytes()}
    if include_proof:
        proof = PACKAGE_SOURCE / "session_proof.py"
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


def _installed_names(destination, sources):
    names = {path.name for path in destination.iterdir()}
    extra = names - set(sources)
    require(extra <= {"__pycache__"}, "Installed package has an unexpected file set")
    cache = destination / "__pycache__"
    if cache.exists():
        require(cache.is_dir() and not cache.is_symlink(), "Installed bytecode cache is unsafe")
        for entry in cache.iterdir():
            require(entry.is_file() and not entry.is_symlink() and entry.suffix == ".pyc"
                    and entry.name.split(".", 1)[0] in {Path(name).stem for name in sources},
                    "Installed bytecode cache has an unexpected file")


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
        _installed_names(destination, sources)
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
