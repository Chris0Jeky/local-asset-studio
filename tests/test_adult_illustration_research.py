import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "studio_adult_illustration_research.py"


def common(schema, kind):
    return {
        "schema": schema,
        "kind": kind,
        "executable": False,
        "authority": "none",
        "research_date": "2026-09-15",
        "source_baseline": "a" * 40,
    }


def fixture_documents():
    programme = common("studio.adult-illustration-programme-index/v0", "architecture-index")
    programme.update(
        {
            "epic": 403,
            "issues": {"agents": 413, "research_discovery": 435},
            "milestones": [{"id": "A0", "goal": "contracts", "issues": [403, 435]}],
            "requirements": [{"id": "AI-AGENT", "issues": [413, 435]}],
            "reuse": [9, 10, 123],
            "next_issue": 435,
            "notes": ["navigation only"],
        }
    )
    controls = common("studio.adult-illustration-control-ontology/v0", "control-ontology")
    controls.update(
        {
            "controls": [
                {
                    "id": "pose.action",
                    "domain": "geometry",
                    "description": "pose",
                    "mechanisms": ["geometry_artifact"],
                },
                {
                    "id": "subject.adult_assertion",
                    "domain": "policy",
                    "description": "reviewed adult status",
                    "mechanisms": ["review_decision"],
                },
            ]
        }
    )
    routes = common("studio.adult-illustration-route-candidates/v0", "research-candidates")
    routes.update(
        {
            "issue": 405,
            "candidates": [
                {
                    "id": "route-b",
                    "lane": "quality_generation",
                    "evidence_state": "discovered",
                    "source_revision": None,
                    "installed": None,
                    "executable": False,
                    "terms": "unknown",
                    "unknowns": ["exact model file"],
                },
                {
                    "id": "route-a",
                    "lane": "fast_preview",
                    "evidence_state": "source_reviewed",
                    "source_revision": "main",
                    "installed": None,
                    "executable": False,
                    "terms": "source terms need immutable snapshot",
                    "unknowns": ["RX 9070 XT memory", "exact graph"],
                },
            ],
        }
    )
    packs = common("studio.adult-illustration-genre-packs/v0", "non-executing-pack-candidates")
    packs["packs"] = [
        {
            "id": "hot-spring-steam",
            "title": "Hot spring",
            "executable": False,
            "content_class": "sensual_non_explicit",
            "authorized_candidate_cap": 0,
        }
    ]
    corpus = common("studio.adult-illustration-benchmark-corpus/v0", "non-executing-corpus")
    corpus["cases"] = [
        {
            "id": "case-b",
            "kind": "geometry",
            "content_class": "sensual_non_explicit",
            "required_controls": ["subject.adult_assertion", "pose.action"],
            "proposed_smoke_candidates": 3,
            "authorized_candidate_cap": 0,
            "real_sources_in_git": False,
        },
        {
            "id": "case-a",
            "kind": "text_to_image",
            "content_class": "sensual_non_explicit",
            "required_controls": ["subject.adult_assertion"],
            "proposed_smoke_candidates": 2,
            "authorized_candidate_cap": 0,
            "real_sources_in_git": False,
        },
    ]
    dialects = common(
        "studio.adult-illustration-prompt-dialects/v0", "prompt-dialect-candidates"
    )
    dialects["profiles"] = [
        {
            "id": "dialect-a",
            "route_candidate_ids": ["route-a"],
            "mode": "hybrid",
            "evidence_state": "source_reviewed",
            "ready_for_compilation": False,
            "source_revision": "main",
            "unknowns": ["immutable tokenizer revision"],
        }
    ]
    techniques = common(
        "studio.adult-illustration-technique-candidates/v0", "technique-candidates"
    )
    techniques["candidates"] = [
        {
            "id": "technique-a",
            "category": "geometry_preprocessor",
            "evidence_state": "source_reviewed",
            "source_revision": "main",
            "installed": None,
            "executable": False,
            "ready_for_qualification": False,
            "promotion_blockers": ["exact installed revision is unknown"],
        }
    ]
    sources = common("studio.adult-illustration-source-intake/v0", "source-intake-examples")
    sources["records"] = [
        {
            "id": "source-a",
            "provider": "huggingface",
            "snapshot_state": "source_reviewed",
            "terms_state": "unknown",
            "immutable_revision": None,
            "download_authorized": False,
            "install_authorized": False,
            "execution_authorized": False,
        }
    ]
    return {
        "programme.json": programme,
        "control-ontology.json": controls,
        "route-candidates.json": routes,
        "genre-packs.json": packs,
        "benchmark-corpus.json": corpus,
        "prompt-dialects.json": dialects,
        "technique-candidates.json": techniques,
        "source-intake-example.json": sources,
    }


def write_fixture(root, documents=None):
    directory = Path(root) / "research" / "adult-illustration"
    directory.mkdir(parents=True, exist_ok=True)
    for name, value in (documents or fixture_documents()).items():
        (directory / name).write_text(
            json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    return directory


def load_cli():
    spec = importlib.util.spec_from_file_location("adult_research_cli", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load CLI from {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AdultIllustrationResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from studio_prompt import adult_illustration_research as research

        cls.research = research
        cls.cli = load_cli()

    def make_root(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        write_fixture(root)
        self.addCleanup(temp.cleanup)
        return root

    def run_cli(self, argv):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = self.cli.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_catalogs_are_stable_bounded_and_non_authoritative(self):
        root = self.make_root()
        first = self.research.catalogs(root)
        second = self.research.catalogs(root)
        self.assertEqual(first, second)
        self.assertEqual(
            [item["id"] for item in first["catalogs"]],
            ["cases", "controls", "dialects", "packs", "routes", "sources", "techniques"],
        )
        self.assertFalse(first["execution_authorized"])
        self.assertEqual(first["authority"], "none")
        self.assertTrue(all(len(item["manifest_sha256"]) == 64 for item in first["catalogs"]))

    def test_list_and_get_are_sorted_deterministic_and_exact(self):
        root = self.make_root()
        listing = self.research.list_records(root, "routes")
        self.assertEqual([item["id"] for item in listing["records"]], ["route-a", "route-b"])
        exact = self.research.get_record(root, "routes", "route-a")
        self.assertEqual(exact["record"]["unknowns"], ["RX 9070 XT memory", "exact graph"])
        self.assertEqual(exact, self.research.get_record(root, "routes", "route-a"))
        self.assertFalse(exact["execution_authorized"])

    def test_unknown_catalog_or_record_fails_closed(self):
        root = self.make_root()
        with self.assertRaisesRegex(ValueError, "Unknown catalog"):
            self.research.list_records(root, "models")
        with self.assertRaisesRegex(KeyError, "missing"):
            self.research.get_record(root, "routes", "missing")

    def test_duplicate_ids_and_duplicate_json_keys_are_rejected(self):
        root = self.make_root()
        route_path = root / "research" / "adult-illustration" / "route-candidates.json"
        value = json.loads(route_path.read_text(encoding="utf-8"))
        value["candidates"][1]["id"] = "route-b"
        route_path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate id"):
            self.research.list_records(root, "routes")

        write_fixture(root)
        route_path.write_text('{"schema":"a","schema":"b","candidates":[]}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
            self.research.list_records(root, "routes")

    @unittest.skipIf(os.name == "nt", "symlink permissions vary on Windows CI")
    def test_symlink_manifest_escape_is_rejected(self):
        root = self.make_root()
        directory = root / "research" / "adult-illustration"
        outside = root / "outside.json"
        outside.write_text(json.dumps(fixture_documents()["route-candidates.json"]), encoding="utf-8")
        target = directory / "route-candidates.json"
        target.unlink()
        target.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.research.list_records(root, "routes")

    def test_programme_status_retains_issues_and_zero_authority(self):
        root = self.make_root()
        status = self.research.programme_status(root)
        self.assertEqual(status["epic"], 403)
        self.assertEqual(status["issues"]["research_discovery"], 435)
        self.assertEqual(status["catalog_count"], 7)
        self.assertFalse(status["execution_authorized"])
        self.assertFalse(status["download_authorized"])

    def test_comparison_plan_is_hashed_finite_and_has_zero_authority(self):
        root = self.make_root()
        plan = self.research.comparison_plan(
            root,
            case_ids=["case-a", "case-b"],
            route_ids=["route-a"],
            dialect_ids=["dialect-a"],
            technique_ids=["technique-a"],
        )
        self.assertEqual(plan["estimated_candidate_count"], 5)
        self.assertEqual(plan["authorized_candidate_cap"], 0)
        self.assertFalse(plan["execution_authorized"])
        self.assertFalse(plan["generation_submitted"])
        self.assertFalse(plan["download_authorized"])
        self.assertFalse(plan["install_authorized"])
        self.assertFalse(plan["training_authorized"])
        self.assertEqual(len(plan["plan_id"]), 64)
        joined = "\n".join(plan["compatibility_gaps"])
        self.assertIn("RX 9070 XT memory", joined)
        self.assertIn("immutable tokenizer revision", joined)
        self.assertIn("exact installed revision is unknown", joined)
        self.assertEqual(plan, self.research.comparison_plan(
            root,
            case_ids=["case-b", "case-a"],
            route_ids=["route-a"],
            dialect_ids=["dialect-a"],
            technique_ids=["technique-a"],
        ))

    def test_comparison_plan_rejects_empty_duplicate_excess_and_incompatible_requests(self):
        root = self.make_root()
        with self.assertRaisesRegex(ValueError, "case_ids"):
            self.research.comparison_plan(root, case_ids=[], route_ids=["route-a"])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.research.comparison_plan(root, case_ids=["case-a", "case-a"], route_ids=["route-a"])
        with self.assertRaisesRegex(ValueError, "route_ids"):
            self.research.comparison_plan(root, case_ids=["case-a"], route_ids=[])
        with self.assertRaisesRegex(ValueError, "does not target"):
            self.research.comparison_plan(
                root,
                case_ids=["case-a"],
                route_ids=["route-b"],
                dialect_ids=["dialect-a"],
            )
        with self.assertRaisesRegex(ValueError, "at most"):
            self.research.comparison_plan(
                root,
                case_ids=["case-a"],
                route_ids=["route-a"] * 17,
            )

    def test_manifest_change_changes_plan_identity_and_input_hash(self):
        root = self.make_root()
        before = self.research.comparison_plan(root, case_ids=["case-a"], route_ids=["route-a"])
        path = root / "research" / "adult-illustration" / "route-candidates.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["candidates"][1]["unknowns"].append("new gap")
        path.write_text(json.dumps(value, indent=2), encoding="utf-8")
        after = self.research.comparison_plan(root, case_ids=["case-a"], route_ids=["route-a"])
        self.assertNotEqual(before["plan_id"], after["plan_id"])
        self.assertNotEqual(
            before["input_manifests"]["routes"],
            after["input_manifests"]["routes"],
        )

    def test_read_operations_do_not_use_network_or_subprocess(self):
        root = self.make_root()
        with mock.patch("socket.create_connection", side_effect=AssertionError("network")), mock.patch(
            "subprocess.run", side_effect=AssertionError("subprocess")
        ):
            self.research.catalogs(root)
            self.research.list_records(root, "sources")
            self.research.comparison_plan(root, case_ids=["case-a"], route_ids=["route-a"])

    def test_cli_list_get_and_plan_return_canonical_json(self):
        root = self.make_root()
        code, stdout, stderr = self.run_cli(["--root", str(root), "list", "routes"])
        self.assertEqual(code, 0, stderr)
        self.assertEqual([item["id"] for item in json.loads(stdout)["records"]], ["route-a", "route-b"])
        code, stdout, stderr = self.run_cli(
            [
                "--root", str(root), "comparison-plan",
                "--case", "case-a", "--route", "route-a", "--dialect", "dialect-a",
            ]
        )
        self.assertEqual(code, 0, stderr)
        self.assertEqual(json.loads(stdout)["authorized_candidate_cap"], 0)

    def test_cli_output_is_exclusive_and_errors_preserve_no_authority(self):
        root = self.make_root()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "plan.json"
            argv = [
                "--root", str(root), "comparison-plan", "--case", "case-a",
                "--route", "route-a", "--out", str(target),
            ]
            first = self.run_cli(argv)
            self.assertEqual(first[0], 0, first[2])
            original = target.read_bytes()
            second = self.run_cli(argv)
            self.assertEqual(second[0], 2)
            self.assertEqual(target.read_bytes(), original)
            error = json.loads(second[2])
            self.assertFalse(error["execution_authorized"])
            self.assertFalse(error["download_authorized"])
            self.assertFalse(error["generation_submitted"])


if __name__ == "__main__":
    unittest.main()
