"""Canonical transitive pins for prepared Krita packages; no native application calls."""
from scripts.character_study import read_json, relative, require, verify_artifact
from integrations.krita import native_edit


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


def collect(root, dependencies):
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
    return native_edit.dependency_manifest(list(pinned.values()))
