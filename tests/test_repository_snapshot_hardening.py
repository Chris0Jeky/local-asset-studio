"""Regression contracts for repository snapshot stack and projection integrity."""
from __future__ import annotations

import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts import repository_snapshot as snapshot


ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 40
CAPTURED = "2026-09-18T20:25:00Z"


def pr(number, head, base, *, parent=None, title=None):
    return {
        "number": number,
        "title": title or f"PR {number}",
        "head": head,
        "base": base,
        "type": "slice",
        "readiness": "review",
        "stack_parent": parent,
        "owner_run": False,
    }


def source(prs=None, *, issue_title="Ready issue"):
    return {
        "schema_version": 1,
        "captured_at": CAPTURED,
        "repository": {
            "head_sha": SHA,
            "default_branch": "main",
            "facts_sha": SHA,
            "catalog_blob_sha": SHA,
            "human_todo_blob_sha": SHA,
        },
        "pull_requests": prs if prs is not None else [],
        "issues": [{
            "number": 20,
            "title": issue_title,
            "type": "slice",
            "readiness": "ready",
            "blocked_by": [],
        }],
        "next_ready": [20],
    }


class RepositorySnapshotHardeningTests(unittest.TestCase):
    def test_captured_base_relationship_requires_the_exact_stack_root(self):
        valid = [
            pr(10, "root", "main"),
            pr(11, "child", "root", parent=10),
            pr(12, "grandchild", "child", parent=10),
        ]
        with TemporaryDirectory() as tmp:
            result = snapshot.build_snapshot(Path(tmp), source(valid))
        self.assertEqual(result["work"]["independent_lines"], 1)
        self.assertEqual(result["work"]["stacks"], [{"parent": 10, "children": [11, 12]}])

        missing = [dict(row) for row in valid]
        missing[1]["stack_parent"] = None
        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, r"#11.*root PR #10"):
                snapshot.build_snapshot(Path(tmp), source(missing))

        false_stack = [pr(10, "root", "main"), pr(11, "child", "main", parent=10)]
        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, r"#11.*base.*captured PR head"):
                snapshot.build_snapshot(Path(tmp), source(false_stack))

    def test_duplicate_heads_are_rejected_before_base_resolution(self):
        duplicate = [pr(10, "same", "main"), pr(11, "same", "main")]
        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "Duplicate pull request head"):
                snapshot.build_snapshot(Path(tmp), source(duplicate))

    def test_markdown_escapes_table_pipes_and_titles_are_single_line(self):
        prs = [pr(10, "root", "main", title="Parse a|b")]
        with TemporaryDirectory() as tmp:
            rendered = snapshot.render_markdown(
                snapshot.build_snapshot(Path(tmp), source(prs, issue_title="Ready | blocked"))
            )
        self.assertIn(r"Parse a\|b", rendered)
        self.assertIn(r"Ready \| blocked", rendered)
        self.assertNotIn("| Parse a|b |", rendered)

        multiline = [pr(10, "root", "main", title="line one\nline two")]
        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "single-line"):
                snapshot.build_snapshot(Path(tmp), source(multiline))

    def test_deep_json_and_output_failures_use_the_bounded_cli_contract(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            deep = root / "deep.json"
            deep.write_bytes(b"[" * 10_000 + b"0" + b"]" * 10_000)
            with patch("sys.stderr", new=io.StringIO()) as error:
                self.assertEqual(snapshot.main(["--source", str(deep)]), 2)
                self.assertRegex(error.getvalue(), r"source (?:is too deeply nested|must be an object)")

            src = root / "source.json"
            src.write_text(json.dumps(source()), encoding="utf-8")
            blocker = root / "not-a-directory"
            blocker.write_text("occupied", encoding="utf-8")
            with patch("sys.stderr", new=io.StringIO()) as error:
                self.assertEqual(
                    snapshot.main([
                        "--source", str(src),
                        "--output", str(blocker / "snapshot.md"),
                    ]),
                    2,
                )
                self.assertIn("Cannot write output", error.getvalue())

    def test_committed_projection_matches_the_committed_capture(self):
        self.assertEqual(
            snapshot.main([
                "--repo-root", str(ROOT),
                "--source", str(ROOT / "research/repository-state/active-work.json"),
                "--test-receipt", str(ROOT / "research/repository-state/test-receipt.json"),
                "--validation-receipt", str(ROOT / "research/repository-state/validation-receipt.json"),
                "--format", "markdown",
                "--check", str(ROOT / "docs/generated/REPOSITORY-STATE.md"),
            ]),
            0,
        )


if __name__ == "__main__":
    unittest.main()
