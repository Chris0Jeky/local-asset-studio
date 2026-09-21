"""Review regressions for repository-state communication and declared limits."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import unittest

from scripts import repository_snapshot as snapshot


ROOT = Path(__file__).resolve().parents[1]
HEAD = "a" * 40
CAPTURED = "2026-09-14T12:50:00Z"
CATALOG_TEXT = json.dumps({"presets": [{"id": "one", "graph": "one.json", "verified": True}]})
TODO_TEXT = "**q-25 — choose a result (open).** Review it.\n"


def blob_sha(text):
    raw = text.encode("utf-8")
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def source():
    return {
        "schema_version": 1,
        "captured_at": CAPTURED,
        "repository": {
            "head_sha": HEAD,
            "default_branch": "main",
            "facts_sha": HEAD,
            "catalog_blob_sha": blob_sha(CATALOG_TEXT),
            "human_todo_blob_sha": blob_sha(TODO_TEXT),
        },
        "pull_requests": [],
        "issues": [{"number": 314, "title": "Revision toolkit", "type": "research",
                    "readiness": "ready", "blocked_by": []}],
        "next_ready": [314],
    }


def write_repo(root):
    (root / "presets").mkdir(parents=True)
    (root / "presets/catalog.json").write_text(CATALOG_TEXT, encoding="utf-8", newline="")
    (root / "HUMAN_TODO.md").write_text(TODO_TEXT, encoding="utf-8", newline="")


class RepositorySnapshotReviewTests(unittest.TestCase):
    def test_markdown_retains_receipt_revision_time_and_test_command(self):
        tests = {"schema_version": 1, "source_sha": HEAD, "run_at": CAPTURED,
                 "command": "python -m unittest discover -s tests", "total": 10,
                 "passed": 9, "skipped": 1, "failures": 0, "errors": 0,
                 "environment": "ubuntu/python3.12"}
        validation = {"schema_version": 1, "source_sha": "b" * 40, "run_at": CAPTURED,
                      "result": "pass", "graphs": 71, "pins": 129,
                      "tracked_paths": 1359, "loras": 96}
        with TemporaryDirectory() as tmp:
            root = Path(tmp); write_repo(root)
            text = snapshot.render_markdown(snapshot.build_snapshot(root, source(), tests, validation))
        self.assertIn(HEAD, text)
        self.assertIn("b" * 40, text)
        self.assertGreaterEqual(text.count(CAPTURED), 3)
        self.assertIn("python -m unittest discover -s tests", text)

    def test_ready_queue_is_labelled_as_authored_capture_not_generated_priority(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); write_repo(root)
            text = snapshot.render_markdown(snapshot.build_snapshot(root, source()))
        self.assertIn("## Captured next-ready selection", text)
        self.assertIn("authored", text.lower())
        self.assertNotIn("## Next ready\n", text)

    def test_operating_model_marker_matches_generator_and_triggers_snapshot_ci(self):
        model = (ROOT / "docs/PROJECT-OPERATING-MODEL.md").read_text(encoding="utf-8")
        match = re.search(r"repository-snapshot-wip: independent=(\d+) stacks=(\d+) owner-run=(\d+)", model)
        self.assertIsNotNone(match, "Operating guide must expose one machine-checked WIP marker")
        self.assertEqual(tuple(map(int, match.groups())),
                         (snapshot.WIP_LIMITS["independent_lines"], snapshot.WIP_LIMITS["stacks"],
                          snapshot.WIP_LIMITS["owner_run_lines"]))
        workflow = (ROOT / ".github/workflows/repository-state.yml").read_text(encoding="utf-8")
        self.assertGreaterEqual(workflow.count("docs/PROJECT-OPERATING-MODEL.md"), 2,
                                "Push and pull-request filters must both watch the declaration")


if __name__ == "__main__":
    unittest.main()
