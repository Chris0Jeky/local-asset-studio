"""Contracts for the offline repository-state snapshot used by the operating model."""
from __future__ import annotations

import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts import repository_snapshot as snapshot


HEAD = "a" * 40
CAPTURED = "2026-09-14T12:50:00Z"


def source(**changes):
    value = {
        "schema_version": 1,
        "captured_at": CAPTURED,
        "repository": {"head_sha": HEAD, "default_branch": "main"},
        "pull_requests": [
            {"number": 333, "title": "Reference study", "head": "research/reference-intelligence",
             "base": "main", "type": "research", "readiness": "review",
             "stack_parent": None, "owner_run": False},
            {"number": 334, "title": "Workflow disclosure", "head": "ux/workflow-disclosure",
             "base": "main", "type": "slice", "readiness": "active",
             "stack_parent": None, "owner_run": False},
            {"number": 337, "title": "Create disclosure", "head": "ux/create-disclosure",
             "base": "ux/workflow-disclosure", "type": "slice", "readiness": "active",
             "stack_parent": 334, "owner_run": False},
        ],
        "issues": [
            {"number": 313, "title": "Accepted asset loop", "type": "epic",
             "readiness": "owner-run", "blocked_by": []},
            {"number": 314, "title": "Revision toolkit", "type": "research",
             "readiness": "ready", "blocked_by": []},
            {"number": 315, "title": "Operating model", "type": "slice",
             "readiness": "active", "blocked_by": []},
        ],
        "next_ready": [314],
    }
    value.update(changes)
    return value


def write_repo(root: Path):
    (root / "presets").mkdir(parents=True)
    (root / "presets/catalog.json").write_text(json.dumps({"presets": [
        {"id": "one", "graph": "workflows/api/one.json", "verified": True,
         "visual": "workflows/comfyui/one.json"},
        {"id": "two", "graph": "workflows/api/two.json", "verified": False},
        {"id": "alias", "graph": "workflows/api/two.json", "verified": True},
    ]}), encoding="utf-8")
    (root / "HUMAN_TODO.md").write_text(
        "# Decisions\n\n**q-25 — review the style results (open).** Choose a direction.\n\n"
        "**q-26 — choose permitted LoRAs (open).** Decide intended use.\n\n"
        "**q-6 — answered.** Historical text.\n- [ ] An unnumbered owner check\n- [x] Finished\n",
        encoding="utf-8")


class RepositorySnapshotTests(unittest.TestCase):
    def test_taxonomy_and_readiness_are_explicit_and_complete(self):
        self.assertEqual(snapshot.ALLOWED_TYPES,
                         ("epic", "slice", "defect", "experiment", "decision", "research"))
        self.assertEqual(snapshot.ALLOWED_READINESS,
                         ("blocked", "ready", "active", "review", "owner-run", "parked"))

    def test_builds_deterministic_facts_without_network(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); write_repo(root)
            result = snapshot.build_snapshot(root, source())
        self.assertEqual(result["snapshot_at"], CAPTURED)
        self.assertEqual(result["repository"], {"head_sha": HEAD, "default_branch": "main"})
        self.assertEqual(result["catalog"], {"presets": 3, "unique_graphs": 2,
                                             "verified_presets": 2, "visual_workflows": 1})
        self.assertEqual(result["human_todo"]["open_count"], 3)
        self.assertEqual([item["id"] for item in result["human_todo"]["items"]],
                         ["q-25", "q-26", None])
        self.assertEqual(result["work"]["open_pull_requests"], 3)
        self.assertEqual(result["work"]["independent_lines"], 2)
        self.assertEqual(result["work"]["stack_count"], 1)
        self.assertTrue(result["work"]["within_wip_limit"])
        self.assertEqual(result["work"]["stacks"], [{"parent": 334, "children": [337]}])
        self.assertEqual(result["work"]["next_ready"], [314])
        self.assertEqual(result["issues"]["by_type"], {"epic": 1, "research": 1, "slice": 1})
        self.assertEqual(result["issues"]["by_readiness"], {"active": 1, "owner-run": 1, "ready": 1})
        self.assertEqual(result["measurements"]["tests"]["status"], "unavailable")
        self.assertEqual(result["measurements"]["validation"]["status"], "unavailable")
        self.assertEqual(result["subjective_fields"],
                         ["artistic acceptance", "product percentages", "priority judgement", "licensing approval"])

    def test_matching_and_stale_receipts_are_never_conflated(self):
        test_receipt = {"schema_version": 1, "source_sha": HEAD, "run_at": CAPTURED,
                        "command": "python -m unittest discover -s tests", "total": 100,
                        "passed": 90, "skipped": 10, "failures": 0, "errors": 0,
                        "environment": "ubuntu/python3.12"}
        validation = {"schema_version": 1, "source_sha": "b" * 40, "run_at": CAPTURED,
                      "result": "pass", "graphs": 71, "pins": 129,
                      "tracked_paths": 1359, "loras": 96}
        with TemporaryDirectory() as tmp:
            root = Path(tmp); write_repo(root)
            result = snapshot.build_snapshot(root, source(), test_receipt, validation)
        self.assertEqual(result["measurements"]["tests"]["status"], "current")
        self.assertEqual(result["measurements"]["tests"]["total"], 100)
        self.assertEqual(result["measurements"]["validation"]["status"], "stale")
        self.assertEqual(result["measurements"]["validation"]["source_sha"], "b" * 40)

    def test_rejects_unknown_taxonomy_dangling_stack_and_nonready_queue(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); write_repo(root)
            bad = source(); bad["pull_requests"][0]["type"] = "feature"
            with self.assertRaisesRegex(ValueError, "Unknown work type"):
                snapshot.build_snapshot(root, bad)
            bad = source(); bad["pull_requests"][2]["stack_parent"] = 999
            with self.assertRaisesRegex(ValueError, "Stack parent"):
                snapshot.build_snapshot(root, bad)
            bad = source(next_ready=[315])
            with self.assertRaisesRegex(ValueError, "next_ready"):
                snapshot.build_snapshot(root, bad)

    def test_wip_limit_counts_independent_lines_not_stack_children_or_owner_runs(self):
        value = source()
        value["pull_requests"].extend([
            {"number": 338, "title": "Third line", "head": "third", "base": "main",
             "type": "defect", "readiness": "review", "stack_parent": None, "owner_run": False},
            {"number": 339, "title": "Owner acceptance", "head": "owner", "base": "main",
             "type": "experiment", "readiness": "owner-run", "stack_parent": None, "owner_run": True},
        ])
        with TemporaryDirectory() as tmp:
            root = Path(tmp); write_repo(root)
            result = snapshot.build_snapshot(root, value)
        self.assertEqual(result["work"]["independent_lines"], 3)
        self.assertTrue(result["work"]["within_wip_limit"])
        value["pull_requests"].append(
            {"number": 340, "title": "Fourth line", "head": "fourth", "base": "main",
             "type": "slice", "readiness": "active", "stack_parent": None, "owner_run": False})
        with TemporaryDirectory() as tmp:
            root = Path(tmp); write_repo(root)
            result = snapshot.build_snapshot(root, value)
        self.assertEqual(result["work"]["independent_lines"], 4)
        self.assertFalse(result["work"]["within_wip_limit"])

    def test_markdown_is_stable_and_marks_generated_vs_authored_boundaries(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); write_repo(root)
            built = snapshot.build_snapshot(root, source())
        first = snapshot.render_markdown(built)
        second = snapshot.render_markdown(built)
        self.assertEqual(first, second)
        self.assertIn("<!-- generated by scripts/repository_snapshot.py; do not hand-edit -->", first)
        self.assertIn("## Active work", first)
        self.assertIn("#337", first)
        self.assertIn("stacked on #334", first)
        self.assertIn("## Next ready", first)
        self.assertIn("#314", first)
        self.assertIn("Measurements are unavailable", first)
        self.assertIn("Subjective judgements are deliberately excluded", first)

    def test_cli_writes_and_check_detects_drift(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); write_repo(root)
            src = root / "state.json"; src.write_text(json.dumps(source()), encoding="utf-8")
            out = root / "state.md"
            self.assertEqual(snapshot.main(["--repo-root", str(root), "--source", str(src),
                                            "--format", "markdown", "--output", str(out)]), 0)
            self.assertTrue(out.read_text(encoding="utf-8").startswith("# Repository state"))
            self.assertEqual(snapshot.main(["--repo-root", str(root), "--source", str(src),
                                            "--format", "markdown", "--check", str(out)]), 0)
            out.write_text("drift\n", encoding="utf-8")
            with patch("sys.stderr", new=io.StringIO()) as error:
                self.assertEqual(snapshot.main(["--repo-root", str(root), "--source", str(src),
                                                "--format", "markdown", "--check", str(out)]), 1)
                self.assertIn("differs", error.getvalue())

    def test_json_inputs_are_bounded_and_reject_unknown_fields(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text(json.dumps({**source(), "surprise": True}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Unknown source fields"):
                snapshot.load_source(path)
            path.write_bytes(b"{" + b" " * (snapshot.MAX_INPUT_BYTES + 1))
            with self.assertRaisesRegex(ValueError, "size limit"):
                snapshot.load_source(path)


if __name__ == "__main__":
    unittest.main()
