"""Contracts for the offline repository-state snapshot used by the operating model."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts import repository_snapshot as snapshot


HEAD = "a" * 40
FACTS_HEAD = "c" * 40
CAPTURED = "2026-09-14T12:50:00Z"
CATALOG_DATA = {"presets": [
    {"id": "one", "graph": "workflows/api/one.json", "verified": True,
     "visual": "workflows/comfyui/one.json"},
    {"id": "two", "graph": "workflows/api/two.json", "verified": False},
    {"id": "alias", "graph": "workflows/api/two.json", "verified": True},
]}
CATALOG_TEXT = json.dumps(CATALOG_DATA)
TODO_TEXT = ("# Decisions\n\n**q-25 — review the style results (open).** Choose a direction.\n\n"
             "**q-26 — choose permitted LoRAs (open).** Decide intended use.\n\n"
             "**q-6 — answered.** Historical text.\n- [ ] An unnumbered owner check\n- [x] Finished\n")


def git_blob_sha(text: str):
    raw = text.encode("utf-8")
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


CATALOG_BLOB_SHA = git_blob_sha(CATALOG_TEXT)
TODO_BLOB_SHA = git_blob_sha(TODO_TEXT)


def source(**changes):
    value = {
        "schema_version": 1,
        "captured_at": CAPTURED,
        "repository": {
            "head_sha": HEAD,
            "default_branch": "main",
            "facts_sha": HEAD,
            "catalog_blob_sha": CATALOG_BLOB_SHA,
            "human_todo_blob_sha": TODO_BLOB_SHA,
        },
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
    (root / "presets/catalog.json").write_text(CATALOG_TEXT, encoding="utf-8", newline="")
    (root / "HUMAN_TODO.md").write_text(TODO_TEXT, encoding="utf-8", newline="")


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
        self.assertEqual(result["repository"], {
            "head_sha": HEAD,
            "default_branch": "main",
            "facts_sha": HEAD,
            "catalog_blob_sha": CATALOG_BLOB_SHA,
            "human_todo_blob_sha": TODO_BLOB_SHA,
        })
        self.assertEqual(result["local_facts"], {"status": "excluded"})
        self.assertEqual(result["work"]["open_pull_requests"], 3)
        self.assertEqual(result["work"]["independent_lines"], 2)
        self.assertEqual(result["work"]["stack_count"], 1)
        self.assertEqual(result["work"]["owner_run_lines"], 0)
        self.assertTrue(result["work"]["within_wip_limit"])
        self.assertEqual(result["work"]["stacks"], [{"parent": 334, "children": [337]}])
        self.assertEqual(result["work"]["next_ready"], [314])
        self.assertEqual(result["issues"]["by_type"], {"epic": 1, "research": 1, "slice": 1})
        self.assertEqual(result["issues"]["by_readiness"], {"active": 1, "owner-run": 1, "ready": 1})
        self.assertEqual(result["measurements"]["tests"]["status"], "unavailable")
        self.assertEqual(result["measurements"]["validation"]["status"], "unavailable")
        self.assertEqual(result["subjective_fields"],
                         ["artistic acceptance", "product percentages", "priority judgement", "licensing approval"])

    def test_checkout_facts_are_optional_observations_never_a_generation_failure(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); write_repo(root)
            result = snapshot.build_snapshot(root, source(), include_local=True)
            local = result["local_facts"]
            self.assertEqual(local["status"], "observed")
            self.assertEqual(local["catalog"], {"blob_sha": CATALOG_BLOB_SHA, "presets": 3, "unique_graphs": 2,
                                                "verified_presets": 2, "visual_workflows": 1})
            self.assertEqual(local["human_todo"]["blob_sha"], TODO_BLOB_SHA)
            self.assertEqual(local["human_todo"]["open_count"], 3)
            self.assertEqual([item["id"] for item in local["human_todo"]["items"]], ["q-25", "q-26", None])
            self.assertTrue(local["catalog_matches_capture"])
            self.assertTrue(local["human_todo_matches_capture"])
            (root / "HUMAN_TODO.md").write_text(TODO_TEXT + "- [ ] A later owner check" + chr(10), encoding="utf-8", newline="")
            (root / "presets/catalog.json").write_text(json.dumps({"presets": []}), encoding="utf-8")
            moved = snapshot.build_snapshot(root, source(), include_local=True)
        self.assertFalse(moved["local_facts"]["catalog_matches_capture"])
        self.assertFalse(moved["local_facts"]["human_todo_matches_capture"])
        self.assertEqual(moved["local_facts"]["human_todo"]["open_count"], 4)
        self.assertIn("differs from the capture", snapshot.render_markdown(moved))

    def test_committed_projection_never_depends_on_catalog_or_owner_backlog_bytes(self):
        """Regression for #461: the drift gate must not fail on unrelated backlog edits."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp); write_repo(root)
            src = root / "state.json"; src.write_text(json.dumps(source()), encoding="utf-8")
            out = root / "state.md"
            self.assertEqual(snapshot.main(["--repo-root", str(root), "--source", str(src),
                                            "--format", "markdown", "--output", str(out)]), 0)
            (root / "HUMAN_TODO.md").write_text("**q-99 — a new owner choice (open).** Decide." + chr(10), encoding="utf-8")
            (root / "presets/catalog.json").write_text(json.dumps({"presets": []}), encoding="utf-8")
            self.assertEqual(snapshot.main(["--repo-root", str(root), "--source", str(src),
                                            "--format", "markdown", "--check", str(out)]), 0)
            (root / "HUMAN_TODO.md").unlink(); (root / "presets/catalog.json").unlink()
            self.assertEqual(snapshot.main(["--repo-root", str(root), "--source", str(src),
                                            "--format", "markdown", "--check", str(out)]), 0)
            body = out.read_text(encoding="utf-8")
            self.assertNotIn("q-25", body)
            self.assertNotIn("presets;", body)
            for sink in ("--check", "--output"):
                with patch("sys.stderr", new=io.StringIO()) as error:
                    self.assertEqual(snapshot.main(["--repo-root", str(root), "--source", str(src),
                                                    "--format", "markdown", "--local-facts", sink, str(out)]), 2)
                    self.assertIn("writes to stdout only", error.getvalue())
            self.assertEqual(out.read_text(encoding="utf-8"), body)

    def test_receipt_currency_uses_the_measured_revision(self):
        test_receipt = {"schema_version": 1, "source_sha": FACTS_HEAD, "run_at": CAPTURED,
                        "command": "python -m unittest discover -s tests", "total": 100,
                        "passed": 90, "skipped": 10, "failures": 0, "errors": 0,
                        "environment": "ubuntu/python3.12"}
        validation = {"schema_version": 1, "source_sha": HEAD, "run_at": CAPTURED,
                      "result": "pass", "graphs": 71, "pins": 129,
                      "tracked_paths": 1359, "loras": 96}
        value = source()
        value["repository"]["facts_sha"] = FACTS_HEAD
        with TemporaryDirectory() as tmp:
            root = Path(tmp); write_repo(root)
            result = snapshot.build_snapshot(root, value, test_receipt, validation)
        self.assertEqual(result["repository"]["head_sha"], HEAD)
        self.assertEqual(result["repository"]["facts_sha"], FACTS_HEAD)
        self.assertEqual(result["measurements"]["tests"]["status"], "current")
        self.assertEqual(result["measurements"]["validation"]["status"], "stale")

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

    def test_rejects_unknown_taxonomy_dangling_nonroot_stack_and_nonready_queue(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp); write_repo(root)
            bad = source(); bad["pull_requests"][0]["type"] = "feature"
            with self.assertRaisesRegex(ValueError, "Unknown work type"):
                snapshot.build_snapshot(root, bad)
            bad = source(); bad["pull_requests"][2]["stack_parent"] = 999
            with self.assertRaisesRegex(ValueError, "Stack parent"):
                snapshot.build_snapshot(root, bad)
            bad = source()
            bad["pull_requests"].extend([
                {"number": 338, "title": "Stack root", "head": "root", "base": "main",
                 "type": "slice", "readiness": "review", "stack_parent": None, "owner_run": False},
                {"number": 339, "title": "Stack child", "head": "child", "base": "root",
                 "type": "slice", "readiness": "review", "stack_parent": 338, "owner_run": False},
                {"number": 344, "title": "Nested child", "head": "nested", "base": "child",
                 "type": "slice", "readiness": "review", "stack_parent": 339, "owner_run": False},
            ])
            with self.assertRaisesRegex(ValueError, "root"):
                snapshot.build_snapshot(root, bad)
            bad = source(next_ready=[315])
            with self.assertRaisesRegex(ValueError, "next_ready"):
                snapshot.build_snapshot(root, bad)

    def test_wip_limit_counts_independent_stack_and_owner_run_lanes(self):
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
        self.assertEqual(result["work"]["owner_run_lines"], 1)
        self.assertTrue(result["work"]["within_wip_limit"])
        value["pull_requests"].append(
            {"number": 340, "title": "Second owner acceptance", "head": "owner-two", "base": "main",
             "type": "experiment", "readiness": "owner-run", "stack_parent": None, "owner_run": True})
        with TemporaryDirectory() as tmp:
            root = Path(tmp); write_repo(root)
            result = snapshot.build_snapshot(root, value)
        self.assertEqual(result["work"]["owner_run_lines"], 2)
        self.assertFalse(result["work"]["within_wip_limit"])
        value["pull_requests"].append(
            {"number": 341, "title": "Fourth line", "head": "fourth", "base": "main",
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
        self.assertIn(f"work capture `{HEAD}`", first)
        self.assertIn(f"measured revision `{HEAD}`", first)
        self.assertIn("## Active work", first)
        self.assertIn("#337", first)
        self.assertIn("stacked on #334", first)
        self.assertIn("0/1 owner-run lanes", first)
        self.assertIn("## Captured next-ready selection", first)
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
