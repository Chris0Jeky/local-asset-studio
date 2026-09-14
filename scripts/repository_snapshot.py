"""Generate a bounded, offline repository-state snapshot from explicit evidence.

The source file is a captured projection of GitHub work state, not a second project
manager. Local catalog/HUMAN_TODO facts are bound to declared Git blob identities.
Test and validator measurements are accepted only through separately recorded
receipts and are marked stale when they name another local-facts revision.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys

ALLOWED_TYPES = ("epic", "slice", "defect", "experiment", "decision", "research")
ALLOWED_READINESS = ("blocked", "ready", "active", "review", "owner-run", "parked")
MAX_INPUT_BYTES = 1024 * 1024
MAX_ITEMS = 1000
_SHA = re.compile(r"[0-9a-f]{40}")
_CAPTURED = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_Q_OPEN = re.compile(r"^\*\*(q-\d+)\s+—\s+(.+?)\s+\(open\)\.\*\*(?:\s|$)", re.IGNORECASE)
_UNCHECKED = re.compile(r"^\s*-\s*\[\s\]\s+(.+?)\s*$")
_REPOSITORY_FIELDS = ("head_sha", "default_branch", "facts_sha", "catalog_blob_sha", "human_todo_blob_sha")


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"Duplicate JSON key: {key}")
        value[key] = item
    return value


def _decode(raw: bytes, label: str):
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"Non-finite JSON value: {value}")))
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label} must be UTF-8 JSON") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is invalid JSON: {exc.msg}") from exc


def _read_bytes(path: Path, label: str):
    path = Path(path)
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_INPUT_BYTES + 1)
    except OSError as exc:
        raise ValueError(f"Cannot read {label}: {exc}") from exc
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError(f"{label} exceeds the {MAX_INPUT_BYTES}-byte size limit")
    return raw


def _read_json(path: Path, label: str):
    return _decode(_read_bytes(path, label), label)


def _fields(value, allowed, label):
    if type(value) is not dict:
        raise ValueError(f"{label} must be an object")
    unknown = set(value) - set(allowed)
    missing = set(allowed) - set(value)
    if unknown:
        raise ValueError(f"Unknown {label} fields: {', '.join(sorted(unknown))}")
    if missing:
        raise ValueError(f"Missing {label} fields: {', '.join(sorted(missing))}")


def _integer(value, label, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}")
    return value


def _text(value, label, limit=240):
    if type(value) is not str or not value.strip() or len(value) > limit or any(ord(ch) < 32 and ch not in "\t\n" for ch in value):
        raise ValueError(f"{label} must be non-empty bounded text")
    return value.strip()


def _sha(value, label="source_sha"):
    if type(value) is not str or not _SHA.fullmatch(value):
        raise ValueError(f"{label} must be a lowercase 40-character Git SHA")
    return value


def _timestamp(value, label="captured_at"):
    if type(value) is not str or not _CAPTURED.fullmatch(value):
        raise ValueError(f"{label} must be UTC in YYYY-MM-DDTHH:MM:SSZ form")
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValueError(f"{label} is not a valid UTC timestamp") from exc
    return value


def _git_blob_sha(raw: bytes):
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def _validate_repository(value):
    _fields(value, _REPOSITORY_FIELDS, "repository")
    _sha(value["head_sha"], "repository.head_sha")
    _text(value["default_branch"], "repository.default_branch", 100)
    _sha(value["facts_sha"], "repository.facts_sha")
    _sha(value["catalog_blob_sha"], "repository.catalog_blob_sha")
    _sha(value["human_todo_blob_sha"], "repository.human_todo_blob_sha")


def load_source(path: Path):
    value = _read_json(path, "source")
    _fields(value, ("schema_version", "captured_at", "repository", "pull_requests", "issues", "next_ready"), "source")
    if value["schema_version"] != 1:
        raise ValueError("Unsupported source schema_version")
    _timestamp(value["captured_at"])
    _validate_repository(value["repository"])
    _validate_work(value)
    return value


def _validate_work(value):
    prs, issues, next_ready = value["pull_requests"], value["issues"], value["next_ready"]
    if type(prs) is not list or len(prs) > MAX_ITEMS:
        raise ValueError("pull_requests must be a bounded list")
    if type(issues) is not list or len(issues) > MAX_ITEMS:
        raise ValueError("issues must be a bounded list")
    if type(next_ready) is not list or len(next_ready) > MAX_ITEMS:
        raise ValueError("next_ready must be a bounded list")
    pr_numbers = set()
    pr_by_number = {}
    for row in prs:
        _fields(row, ("number", "title", "head", "base", "type", "readiness", "stack_parent", "owner_run"), "pull request")
        number = _integer(row["number"], "pull request number", 1)
        if number in pr_numbers:
            raise ValueError("Duplicate pull request number")
        pr_numbers.add(number); pr_by_number[number] = row
        _text(row["title"], "pull request title", 300)
        _text(row["head"], "pull request head", 200)
        _text(row["base"], "pull request base", 200)
        if row["type"] not in ALLOWED_TYPES:
            raise ValueError(f"Unknown work type: {row['type']}")
        if row["readiness"] not in ALLOWED_READINESS:
            raise ValueError(f"Unknown readiness: {row['readiness']}")
        if row["stack_parent"] is not None:
            _integer(row["stack_parent"], "stack_parent", 1)
        if type(row["owner_run"]) is not bool:
            raise ValueError("owner_run must be boolean")
        if row["owner_run"] != (row["readiness"] == "owner-run"):
            raise ValueError(f"owner_run and readiness disagree for #{number}")
        if row["owner_run"] and row["stack_parent"] is not None:
            raise ValueError(f"Owner-run PR #{number} cannot also be a stack child")
    for row in prs:
        parent = row["stack_parent"]
        if parent is None:
            continue
        if parent not in pr_numbers or parent == row["number"]:
            raise ValueError(f"Stack parent for #{row['number']} is missing or self-referential")
        parent_row = pr_by_number[parent]
        if parent_row["stack_parent"] is not None:
            raise ValueError(f"Stack parent for #{row['number']} must name root PR #{parent_row['stack_parent']}, not nested parent #{parent}")
    issue_numbers = set()
    issue_by_number = {}
    for row in issues:
        _fields(row, ("number", "title", "type", "readiness", "blocked_by"), "issue")
        number = _integer(row["number"], "issue number", 1)
        if number in issue_numbers:
            raise ValueError("Duplicate issue number")
        issue_numbers.add(number); issue_by_number[number] = row
        _text(row["title"], "issue title", 300)
        if row["type"] not in ALLOWED_TYPES:
            raise ValueError(f"Unknown work type: {row['type']}")
        if row["readiness"] not in ALLOWED_READINESS:
            raise ValueError(f"Unknown readiness: {row['readiness']}")
        if type(row["blocked_by"]) is not list or len(row["blocked_by"]) > MAX_ITEMS:
            raise ValueError("blocked_by must be a bounded list")
        for blocker in row["blocked_by"]:
            _integer(blocker, "blocked_by item", 1)
    seen_ready = set()
    for number in next_ready:
        _integer(number, "next_ready item", 1)
        if number in seen_ready:
            raise ValueError("Duplicate next_ready item")
        seen_ready.add(number)
        row = issue_by_number.get(number)
        if row is None or row["readiness"] != "ready" or row["blocked_by"]:
            raise ValueError(f"next_ready #{number} is missing, not ready, or blocked")


def _load_receipt(value, kind):
    if value is None:
        return None
    if isinstance(value, (str, Path)):
        value = _read_json(Path(value), f"{kind} receipt")
    if kind == "tests":
        fields = ("schema_version", "source_sha", "run_at", "command", "total", "passed", "skipped", "failures", "errors", "environment")
    else:
        fields = ("schema_version", "source_sha", "run_at", "result", "graphs", "pins", "tracked_paths", "loras")
    _fields(value, fields, f"{kind} receipt")
    if value["schema_version"] != 1:
        raise ValueError(f"Unsupported {kind} receipt schema_version")
    _sha(value["source_sha"])
    _timestamp(value["run_at"], "run_at")
    result = dict(value)
    if kind == "tests":
        _text(value["command"], "test command", 500)
        _text(value["environment"], "test environment", 240)
        for name in ("total", "passed", "skipped", "failures", "errors"):
            _integer(value[name], name)
        if value["total"] != value["passed"] + value["skipped"] + value["failures"] + value["errors"]:
            raise ValueError("Test receipt totals do not add up")
    else:
        if value["result"] not in ("pass", "fail"):
            raise ValueError("Validation result must be pass or fail")
        for name in ("graphs", "pins", "tracked_paths", "loras"):
            _integer(value[name], name)
    return result


def _bound_local_file(root: Path, relative: str, label: str, expected_blob: str):
    raw = _read_bytes(Path(root) / relative, label)
    observed = _git_blob_sha(raw)
    if observed != expected_blob:
        raise ValueError(f"{label} Git blob mismatch: expected {expected_blob}, observed {observed}")
    return raw


def catalog_facts(root: Path, expected_blob: str):
    value = _decode(_bound_local_file(root, "presets/catalog.json", "preset catalog", expected_blob), "preset catalog")
    if type(value) is not dict or type(value.get("presets")) is not list:
        raise ValueError("Preset catalog must contain a presets list")
    presets = value["presets"]
    if len(presets) > MAX_ITEMS:
        raise ValueError("Preset catalog exceeds snapshot item limit")
    graphs, verified, visuals = set(), 0, 0
    for row in presets:
        if type(row) is not dict:
            raise ValueError("Preset catalog rows must be objects")
        graph = row.get("graph")
        if type(graph) is str and graph:
            graphs.add(graph)
        if row.get("verified") is True:
            verified += 1
        if type(row.get("visual")) is str and row["visual"]:
            visuals += 1
    return {"presets": len(presets), "unique_graphs": len(graphs),
            "verified_presets": verified, "visual_workflows": visuals}


def human_todo_facts(root: Path, expected_blob: str):
    raw = _bound_local_file(root, "HUMAN_TODO.md", "HUMAN_TODO.md", expected_blob)
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise ValueError("HUMAN_TODO.md must be UTF-8") from exc
    items = []
    for line in lines:
        match = _Q_OPEN.match(line)
        if match:
            items.append({"id": match.group(1).lower(), "text": match.group(2).strip()}); continue
        match = _UNCHECKED.match(line)
        if match:
            items.append({"id": None, "text": match.group(1).strip()})
    return {"open_count": len(items), "items": items}


def _measurement(receipt, facts_head):
    if receipt is None:
        return {"status": "unavailable"}
    result = {key: item for key, item in receipt.items() if key != "schema_version"}
    result["status"] = "current" if receipt["source_sha"] == facts_head else "stale"
    return result


def _validate_source_object(source):
    _fields(source, ("schema_version", "captured_at", "repository", "pull_requests", "issues", "next_ready"), "source")
    if source["schema_version"] != 1:
        raise ValueError("Unsupported source schema_version")
    _timestamp(source["captured_at"])
    _validate_repository(source["repository"])
    _validate_work(source)


def build_snapshot(root: Path, source, test_receipt=None, validation_receipt=None):
    if isinstance(source, (str, Path)):
        source = load_source(Path(source))
    else:
        source = json.loads(json.dumps(source)); _validate_source_object(source)
    tests = _load_receipt(test_receipt, "tests")
    validation = _load_receipt(validation_receipt, "validation")
    repository = source["repository"]
    prs = sorted(source["pull_requests"], key=lambda row: row["number"])
    active = {"active", "review"}
    independent = [row for row in prs if row["readiness"] in active and row["stack_parent"] is None and not row["owner_run"]]
    owner_runs = [row for row in prs if row["owner_run"] and row["readiness"] in active | {"owner-run"}]
    stack_map = {}
    for row in prs:
        if row["readiness"] in active and row["stack_parent"] is not None:
            stack_map.setdefault(row["stack_parent"], []).append(row["number"])
    stacks = [{"parent": parent, "children": sorted(children)} for parent, children in sorted(stack_map.items())]
    issues = sorted(source["issues"], key=lambda row: row["number"])
    within = len(independent) <= 3 and len(stacks) <= 1 and len(owner_runs) <= 1
    return {
        "schema_version": 1,
        "generated_by": "scripts/repository_snapshot.py",
        "snapshot_at": source["captured_at"],
        "repository": dict(repository),
        "catalog": catalog_facts(root, repository["catalog_blob_sha"]),
        "human_todo": human_todo_facts(root, repository["human_todo_blob_sha"]),
        "work": {
            "wip_limits": {"independent_lines": 3, "stacks": 1, "owner_run_lines": 1},
            "open_pull_requests": len(prs),
            "independent_lines": len(independent),
            "stack_count": len(stacks),
            "owner_run_lines": len(owner_runs),
            "within_wip_limit": within,
            "stacks": stacks,
            "pull_requests": prs,
            "next_ready": list(source["next_ready"]),
        },
        "issues": {
            "total": len(issues),
            "by_type": dict(sorted(Counter(row["type"] for row in issues).items())),
            "by_readiness": dict(sorted(Counter(row["readiness"] for row in issues).items())),
            "items": issues,
        },
        "measurements": {
            "tests": _measurement(tests, repository["facts_sha"]),
            "validation": _measurement(validation, repository["facts_sha"]),
        },
        "subjective_fields": ["artistic acceptance", "product percentages", "priority judgement", "licensing approval"],
    }


def _measurement_text(value, kind):
    if value["status"] == "unavailable":
        return "Measurements are unavailable; no receipt was supplied."
    prefix = "Current" if value["status"] == "current" else "Stale"
    if kind == "tests":
        return (f"{prefix}: {value['total']} total, {value['passed']} passed, {value['skipped']} skipped, "
                f"{value['failures']} failures, {value['errors']} errors ({value['environment']}).")
    return (f"{prefix}: validator {value['result']}; {value['graphs']} graphs, {value['pins']} pins, "
            f"{value['tracked_paths']} tracked paths, {value['loras']} LoRA names.")


def render_markdown(value):
    repository = value["repository"]
    lines = [
        "# Repository state", "",
        "<!-- generated by scripts/repository_snapshot.py; do not hand-edit -->", "",
        (f"Snapshot: `{value['snapshot_at']}` · work capture `{repository['head_sha']}` · "
         f"local facts `{repository['facts_sha']}` · default branch `{repository['default_branch']}`."),
        "",
        (f"Local fact blobs: catalog `{repository['catalog_blob_sha']}` · "
         f"HUMAN_TODO `{repository['human_todo_blob_sha']}`."),
        "",
        "This is a generated factual projection. `STATUS.md` owns authored product judgement; `CURRENT_STATE.md` remains the evidence ledger.",
        "", "## Active work", "",
        "| PR | Type | Readiness | Line | Title |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in value["work"]["pull_requests"]:
        line = (f"stacked on #{row['stack_parent']}" if row["stack_parent"] is not None
                else "owner-run" if row["owner_run"] else "independent")
        lines.append(f"| #{row['number']} | {row['type']} | {row['readiness']} | {line} | {row['title']} |")
    work = value["work"]
    verdict = "within" if work["within_wip_limit"] else "over"
    lines += ["", (f"WIP is **{verdict} the declared limit**: {work['independent_lines']}/3 independent lines, "
                  f"{work['stack_count']}/1 stack and {work['owner_run_lines']}/1 owner-run lanes.")]
    if work["stacks"]:
        lines += ["", "Stacks: " + "; ".join(f"#{row['parent']} → " + ", ".join(f"#{child}" for child in row["children"]) for row in work["stacks"]) + "."]
    lines += ["", "## Next ready", ""]
    issue_map = {row["number"]: row for row in value["issues"]["items"]}
    if work["next_ready"]:
        lines += ["| Issue | Type | Title |", "| --- | --- | --- |"]
        for number in work["next_ready"]:
            row = issue_map[number]; lines.append(f"| #{number} | {row['type']} | {row['title']} |")
    else:
        lines.append("No unblocked ready item was declared in this capture.")
    lines += [
        "", "## Stable facts", "",
        "| Fact | Value |", "| --- | --- |",
        f"| Catalog | {value['catalog']['presets']} presets; {value['catalog']['unique_graphs']} unique API graphs; {value['catalog']['verified_presets']} verified presets; {value['catalog']['visual_workflows']} visual links |",
        f"| Open owner decisions | {value['human_todo']['open_count']} |",
        f"| Tests | {_measurement_text(value['measurements']['tests'], 'tests')} |",
        f"| Repository validation | {_measurement_text(value['measurements']['validation'], 'validation')} |",
        "", "## Open owner decisions", "",
    ]
    if value["human_todo"]["items"]:
        for item in value["human_todo"]["items"]:
            label = f"**{item['id']}** — " if item["id"] else ""; lines.append(f"- {label}{item['text']}")
    else:
        lines.append("No open item was parsed from `HUMAN_TODO.md`.")
    lines += [
        "", "## Taxonomy counts", "",
        "Types: " + ", ".join(f"{key} {count}" for key, count in value["issues"]["by_type"].items()) + ".",
        "", "Readiness: " + ", ".join(f"{key} {count}" for key, count in value["issues"]["by_readiness"].items()) + ".",
        "", "## Deliberate boundary", "",
        "Subjective judgements are deliberately excluded: " + ", ".join(value["subjective_fields"]) + ".",
        "", "Passing checks, a completed job or a generated snapshot never closes a broad issue or records owner acceptance.", "",
    ]
    return "\n".join(lines)


def render_json(value):
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _write(path: Path, text: str):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--source", required=True)
    parser.add_argument("--test-receipt")
    parser.add_argument("--validation-receipt")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("--output"); destination.add_argument("--check")
    args = parser.parse_args(argv)
    try:
        value = build_snapshot(Path(args.repo_root), load_source(Path(args.source)),
                               args.test_receipt, args.validation_receipt)
        text = render_json(value) if args.format == "json" else render_markdown(value)
        if args.check:
            try:
                actual = Path(args.check).read_text(encoding="utf-8")
            except OSError as exc:
                raise ValueError(f"Cannot read check target: {exc}") from exc
            if actual != text:
                print(f"Repository snapshot differs from {args.check}; regenerate it.", file=sys.stderr); return 1
        elif args.output:
            _write(Path(args.output), text)
        else:
            sys.stdout.write(text)
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr); return 2


if __name__ == "__main__":
    raise SystemExit(main())
