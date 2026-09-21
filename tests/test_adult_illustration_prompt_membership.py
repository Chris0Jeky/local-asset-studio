from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from studio_prompt.adult_illustration_projection import project
from studio_prompt.adult_illustration_prompt_membership import (
    inspect_prompt_membership,
    validate_prompt_membership_report,
)
from studio_prompt.adult_illustration_prompt_projection import compile_prompt
from studio_prompt.adult_illustration_taxonomy import build_taxonomy_index
from studio_prompt.adult_illustration_taxonomy_contracts import (
    canonical_bytes,
    sha256,
)
from tests.test_adult_illustration_prompt_profiles import sample_projection
from tests.test_adult_illustration_taxonomy import (
    csv_bytes,
    review_entry,
    write_contracts,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "studio_adult_illustration_prompt.py"


def load_cli():
    spec = importlib.util.spec_from_file_location("adult_prompt_membership_cli", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load CLI from {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rehash(index: dict[str, object]) -> None:
    unsigned = copy.deepcopy(index)
    unsigned.pop("index_id", None)
    index["index_id"] = sha256(canonical_bytes(unsigned))


def write_fixture(root: Path):
    rows = [
        (1, "solo", 0, 100),
        (2, "mystery_tag", 0, 50),
        (3, "second_mystery_tag", 0, 40),
        (4, "watermark", 0, 25),
        (5, "blocked_tag", 0, 10),
    ]
    source = csv_bytes(rows)
    reviews = [
        review_entry("solo", facets=["subject"]),
        review_entry(
            "watermark",
            facets=["quality"],
            polarity="negative",
        ),
        review_entry("blocked_tag", facets=["style"], accepted=False),
    ]
    write_contracts(root, source, rows, reviews)
    target = root / "research" / "adult-illustration"
    shutil.copyfile(
        ROOT / "research" / "adult-illustration" / "prompt-profile-vocabulary.json",
        target / "prompt-profile-vocabulary.json",
    )

    intent = copy.deepcopy(sample_projection()["intent"])
    intent["tags"] = [
        "solo",
        "mystery_tag",
        "second mystery tag",
        "blocked tag",
        "not in source",
    ]
    intent["avoid"] = ["watermark"]
    projection = project(intent)
    compiled = compile_prompt(projection, "animagine-xl4-ordered-v1", root)
    index = build_taxonomy_index(source, root)
    return projection, compiled, index, source


def by_input(report: dict[str, object]) -> dict[tuple[str, str], dict[str, object]]:
    return {
        (item["channel"], item["input"]): item
        for item in report["inspections"]
    }


class PromptMembershipTests(unittest.TestCase):
    def test_report_distinguishes_all_membership_states_and_match_kinds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            projection, compiled, index, taxonomy_source = write_fixture(root)
            report = inspect_prompt_membership(compiled, projection, index, taxonomy_source, root)

        self.assertEqual(
            report["format"],
            "studio.adult-illustration.prompt-membership-report/v1",
        )
        self.assertEqual(
            report["counts"],
            {
                "inputs": 6,
                "source_known_reviewed_accepted": 2,
                "source_known_reviewed_ineligible": 1,
                "source_known_unreviewed": 2,
                "not_in_pinned_source": 1,
            },
        )
        rows = by_input(report)
        self.assertEqual(
            rows[("positive", "solo")]["membership"]["classification"],
            "source_known_reviewed_accepted",
        )
        exact = rows[("positive", "mystery_tag")]["membership"]
        self.assertEqual(exact["classification"], "source_known_unreviewed")
        self.assertEqual(exact["source_name"], "mystery_tag")
        self.assertEqual(exact["match_kind"], "canonical")
        normalised = rows[("positive", "second mystery tag")]["membership"]
        self.assertEqual(normalised["classification"], "source_known_unreviewed")
        self.assertEqual(normalised["source_name"], "second_mystery_tag")
        self.assertEqual(normalised["match_kind"], "normalised_space")
        self.assertEqual(
            rows[("positive", "blocked tag")]["membership"]["classification"],
            "source_known_reviewed_ineligible",
        )
        self.assertEqual(
            rows[("positive", "blocked tag")]["compiler"]["status"],
            "not_accepted",
        )
        self.assertEqual(
            rows[("positive", "not in source")]["membership"]["classification"],
            "not_in_pinned_source",
        )
        self.assertIsNone(
            rows[("positive", "not in source")]["membership"]["source_name"]
        )
        self.assertEqual(
            rows[("negative", "watermark")]["compiler"]["source"],
            "reviewed_taxonomy",
        )
        self.assertTrue(report["taxonomy"]["source_revalidated"])
        self.assertTrue(report["taxonomy"]["index_identity_validated"])
        self.assertTrue(report["taxonomy"]["current_contracts_validated"])
        self.assertTrue(all(value is False for value in report["authority"].values()))

    def test_report_is_deterministic_and_recomputed_validation_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            projection, compiled, index, taxonomy_source = write_fixture(root)
            first = inspect_prompt_membership(compiled, projection, index, taxonomy_source, root)
            second = inspect_prompt_membership(
                copy.deepcopy(compiled),
                copy.deepcopy(projection),
                copy.deepcopy(index),
                taxonomy_source,
                root,
            )
            self.assertEqual(first, second)
            unsigned = copy.deepcopy(first)
            report_sha256 = unsigned.pop("report_sha256")
            self.assertEqual(report_sha256, sha256(canonical_bytes(unsigned)))
            self.assertEqual(
                validate_prompt_membership_report(
                    first, compiled, projection, index, taxonomy_source, root
                ),
                first,
            )
            changed = copy.deepcopy(first)
            changed["inspections"][0]["membership"]["classification"] = (
                "not_in_pinned_source"
            )
            with self.assertRaisesRegex(ValueError, "Changed or invalid"):
                validate_prompt_membership_report(
                    changed, compiled, projection, index, taxonomy_source, root
                )

    def test_stale_index_contract_identities_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            projection, compiled, index, taxonomy_source = write_fixture(root)
            for field in ("source_manifest_sha256", "review_manifest_sha256"):
                with self.subTest(field=field):
                    stale = copy.deepcopy(index)
                    stale["contracts"][field] = "0" * 64
                    rehash(stale)
                    with self.assertRaisesRegex(ValueError, "source/review contracts"):
                        inspect_prompt_membership(compiled, projection, stale, taxonomy_source, root)

    def test_stale_source_metadata_is_rejected_even_after_rehash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            projection, compiled, index, taxonomy_source = write_fixture(root)
            stale = copy.deepcopy(index)
            stale["source"]["sha256"] = "0" * 64
            rehash(stale)
            with self.assertRaisesRegex(ValueError, "pinned source contract"):
                inspect_prompt_membership(compiled, projection, stale, taxonomy_source, root)

    def test_changed_reviewed_entry_is_rejected_even_after_rehash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            projection, compiled, index, taxonomy_source = write_fixture(root)
            changed = copy.deepcopy(index)
            reviewed = next(item for item in changed["entries"] if item["reviewed"])
            reviewed["display"] += " changed"
            rehash(changed)
            with self.assertRaisesRegex(ValueError, "current review contract"):
                inspect_prompt_membership(compiled, projection, changed, taxonomy_source, root)

    def test_rehashed_structurally_invalid_index_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            projection, compiled, index, taxonomy_source = write_fixture(root)
            malformed = copy.deepcopy(index)
            malformed["entries"].append(copy.deepcopy(malformed["entries"][0]))
            malformed["counts"]["source"] += 1
            malformed["source"]["records"] += 1
            rehash(malformed)
            with self.assertRaisesRegex(ValueError, "duplicate"):
                inspect_prompt_membership(compiled, projection, malformed, taxonomy_source, root)

    def test_changed_source_projection_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            projection, compiled, index, taxonomy_source = write_fixture(root)
            changed = copy.deepcopy(projection)
            changed["creative_intent"]["brief"] += " Changed without reprojection."
            with self.assertRaisesRegex(
                ValueError, "Changed or invalid adult illustration projection"
            ):
                inspect_prompt_membership(compiled, changed, index, taxonomy_source, root)

    def test_inspection_does_not_open_runtime_or_network_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            projection, compiled, index, taxonomy_source = write_fixture(root)
            with mock.patch(
                "socket.socket", side_effect=AssertionError("network access")
            ), mock.patch(
                "subprocess.run", side_effect=AssertionError("subprocess access")
            ):
                report = inspect_prompt_membership(
                    compiled,
                    projection,
                    index,
                    taxonomy_source,
                    root,
                )
        self.assertFalse(report["execution_authorized"])
        self.assertFalse(report["generation_submitted"])


class PromptMembershipCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cli = load_cli()

    def run_cli(self, argv: list[str]):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = self.cli.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_json_reader_stops_at_the_requested_bound(self) -> None:
        class RecordingStream(io.BytesIO):
            requested = None

            def read(self, size=-1):
                self.requested = size
                return super().read(size)

        stream = RecordingStream(b'{"too":"large"}')
        with mock.patch.object(Path, "open", return_value=stream), self.assertRaisesRegex(
            ValueError, "5 byte limit"
        ):
            self.cli._read_json(Path("ignored.json"), limit=5)
        self.assertEqual(stream.requested, 6)

    def test_cli_round_trip_and_exclusive_create(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            projection, compiled, index, taxonomy_source = write_fixture(root)
            source_path = root / "source.json"
            compiled_path = root / "compiled.json"
            index_path = root / "index.json"
            taxonomy_source_path = root / "selected_tags.csv"
            report_path = root / "report.json"
            source_path.write_text(json.dumps(projection), encoding="utf-8")
            compiled_path.write_text(json.dumps(compiled), encoding="utf-8")
            index_path.write_text(json.dumps(index), encoding="utf-8")
            taxonomy_source_path.write_bytes(taxonomy_source)
            args = [
                "inspect-membership",
                str(compiled_path),
                "--source",
                str(source_path),
                "--taxonomy-index",
                str(index_path),
                "--taxonomy-source",
                str(taxonomy_source_path),
                "--repo-root",
                str(root),
                "--out",
                str(report_path),
            ]
            code, stdout, stderr = self.run_cli(args)
            self.assertEqual(code, 0, stderr)
            self.assertEqual(stdout, "")
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["counts"]["source_known_unreviewed"], 2)
            self.assertEqual(
                report["counts"]["source_known_reviewed_ineligible"], 1
            )
            original = report_path.read_bytes()
            code, stdout, stderr = self.run_cli(args)
            self.assertEqual(code, 2)
            self.assertEqual(stdout, "")
            self.assertEqual(report_path.read_bytes(), original)
            error = json.loads(stderr)
            self.assertFalse(error["execution_authorized"])
            self.assertFalse(error["generation_submitted"])


if __name__ == "__main__":
    unittest.main()
