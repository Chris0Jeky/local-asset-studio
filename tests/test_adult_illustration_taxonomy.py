from __future__ import annotations

import contextlib
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from studio_prompt.adult_illustration_taxonomy import (
    build_taxonomy_index,
    load_taxonomy_contracts,
    lookup_taxonomy,
    render_taxonomy_index,
    validate_taxonomy_index,
)
from studio_prompt.adult_illustration_taxonomy_contracts import canonical_bytes, sha256


AUTHORITY = {
    "execution_authorized": False,
    "generation_submitted": False,
    "download_authorized": False,
    "install_authorized": False,
    "training_authorized": False,
}


def csv_bytes(rows: list[tuple[int, str, int, int]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["tag_id", "name", "category", "count"])
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def review_entry(
    source_name: str,
    *,
    aliases: list[str] | None = None,
    implications: list[str] | None = None,
    deprecated_by: str | None = None,
    facets: list[str] | None = None,
    polarity: str = "positive",
    profiles: list[str] | None = None,
    accepted: bool = True,
) -> dict[str, object]:
    return {
        "source_name": source_name,
        "display": source_name.replace("_", " "),
        "aliases": aliases or [],
        "implications": implications or [],
        "deprecated_by": deprecated_by,
        "semantic_facets": facets or ["style"],
        "polarity": polarity,
        "profile_ids": profiles or ["animagine-xl4-ordered-v1"],
        "accepted_for_compilation": accepted,
    }


def write_contracts(
    root: Path,
    source: bytes,
    rows: list[tuple[int, str, int, int]],
    entries: list[dict[str, object]],
) -> None:
    target = root / "research" / "adult-illustration"
    target.mkdir(parents=True)
    source_contract = {
        "schema": "studio.adult-illustration-taxonomy-source/v1",
        "kind": "anime-tag-taxonomy-source",
        "executable": False,
        "authority": AUTHORITY,
        "research_date": "2026-09-18",
        "source_baseline": "a" * 40,
        "issue": 437,
        "source": {
            "provider": "huggingface",
            "repository": "owner/model",
            "revision": "b" * 40,
            "selected_file": "selected_tags.csv",
            "source_url": "https://huggingface.co/owner/model",
            "selected_file_url": "https://huggingface.co/owner/model/blob/" + "b" * 40 + "/selected_tags.csv",
            "download_url": "https://huggingface.co/owner/model/resolve/" + "b" * 40 + "/selected_tags.csv?download=true",
            "bytes": len(source),
            "sha256": hashlib.sha256(source).hexdigest(),
            "records": len(rows),
            "columns": ["tag_id", "name", "category", "count"],
            "license_claim": {
                "value": "apache-2.0",
                "source_url": "https://huggingface.co/owner/model/blob/" + "b" * 40 + "/README.md",
                "reviewed_at": "2026-09-18",
            },
        },
        "categories": [
            {"source_value": 0, "id": "general", "display": "general"},
            {"source_value": 4, "id": "character", "display": "character"},
            {"source_value": 9, "id": "rating", "display": "rating"},
        ],
        "published_fields": {
            "canonical": "name",
            "source_category": "category",
            "frequency": "count",
            "aliases": None,
            "implications": None,
            "deprecations": None,
        },
        "semantic_facets": ["subject", "pose", "environment", "style", "quality"],
        "profile_ids": ["animagine-xl4-ordered-v1", "anima-aesthetic-hybrid-v1"],
        "bounds": {
            "max_source_bytes": 1048576,
            "max_records": 20000,
            "max_term_length": 256,
            "max_review_entries": 4096,
            "max_aliases_per_entry": 16,
            "max_implications_per_entry": 16,
            "max_relationship_depth": 8,
            "max_index_bytes": 16777216,
        },
        "accepted_for_compilation": False,
        "notes": ["fixture"],
    }
    review = {
        "schema": "studio.adult-illustration-taxonomy-review/v1",
        "kind": "anime-tag-taxonomy-review",
        "executable": False,
        "authority": AUTHORITY,
        "research_date": "2026-09-18",
        "issue": 437,
        "source_sha256": hashlib.sha256(source).hexdigest(),
        "entries": entries,
        "notes": ["fixture"],
    }
    (target / "taxonomy-source.json").write_text(json.dumps(source_contract), encoding="utf-8")
    (target / "taxonomy-review.json").write_text(json.dumps(review), encoding="utf-8")


class TaxonomyTests(unittest.TestCase):
    def test_build_preserves_every_source_row_and_only_review_promotes_terms(self) -> None:
        rows = [(1, "solo", 0, 900), (2, "sitting", 0, 700), (3, "unreviewed", 0, 1)]
        source = csv_bytes(rows)
        entries = [
            review_entry("solo", aliases=["single subject"], facets=["subject"]),
            review_entry("sitting", facets=["pose"]),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_contracts(root, source, rows, entries)
            index = build_taxonomy_index(source, root)

        self.assertEqual(index["counts"], {"source": 3, "reviewed": 2, "accepted": 2, "aliases": 1})
        by_name = {entry["source_name"]: entry for entry in index["entries"]}
        self.assertTrue(by_name["solo"]["accepted_for_compilation"])
        self.assertEqual(by_name["solo"]["aliases"], ["single subject"])
        self.assertFalse(by_name["unreviewed"]["reviewed"])
        self.assertFalse(by_name["unreviewed"]["accepted_for_compilation"])
        self.assertFalse(index["execution_authorized"])
        self.assertFalse(index["generation_submitted"])

    def test_source_bytes_and_hash_must_match_before_csv_parsing(self) -> None:
        rows = [(1, "solo", 0, 900)]
        source = csv_bytes(rows)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_contracts(root, source, rows, [review_entry("solo")])
            with self.assertRaisesRegex(ValueError, "byte count"):
                build_taxonomy_index(source + b"x", root)

    def test_duplicate_ids_names_normalized_names_and_bad_categories_fail(self) -> None:
        cases = [
            [(1, "solo", 0, 10), (1, "sitting", 0, 9)],
            [(1, "solo", 0, 10), (2, "solo", 0, 9)],
            [(1, "hot_spring", 0, 10), (2, "hot spring", 0, 9)],
            [(1, "solo", 7, 10)],
        ]
        for rows in cases:
            with self.subTest(rows=rows), tempfile.TemporaryDirectory() as tmp:
                source = csv_bytes(rows)
                root = Path(tmp)
                write_contracts(root, source, rows, [])
                with self.assertRaises(ValueError):
                    build_taxonomy_index(source, root)

    def test_alias_collision_with_source_or_another_alias_fails(self) -> None:
        rows = [(1, "solo", 0, 10), (2, "sitting", 0, 9)]
        source = csv_bytes(rows)
        reviews = [
            [review_entry("solo", aliases=["sitting"])],
            [review_entry("solo", aliases=["one subject"]), review_entry("sitting", aliases=["one_subject"])],
        ]
        for entries in reviews:
            with self.subTest(entries=entries), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                write_contracts(root, source, rows, entries)
                with self.assertRaisesRegex(ValueError, "alias"):
                    build_taxonomy_index(source, root)

    def test_implication_and_deprecation_cycles_fail(self) -> None:
        rows = [(1, "solo", 0, 10), (2, "sitting", 0, 9)]
        source = csv_bytes(rows)
        reviews = [
            [review_entry("solo", implications=["sitting"]), review_entry("sitting", implications=["solo"])],
            [review_entry("solo", deprecated_by="sitting", accepted=False), review_entry("sitting", deprecated_by="solo", accepted=False)],
        ]
        for entries in reviews:
            with self.subTest(entries=entries), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                write_contracts(root, source, rows, entries)
                with self.assertRaisesRegex(ValueError, "cycle"):
                    build_taxonomy_index(source, root)

    def test_implication_requires_matching_polarity_and_profile_support(self) -> None:
        rows = [(1, "solo", 0, 10), (2, "sitting", 0, 9)]
        source = csv_bytes(rows)
        reviews = [
            [review_entry("solo", implications=["sitting"]), review_entry("sitting", polarity="negative")],
            [
                review_entry("solo", implications=["sitting"], profiles=["animagine-xl4-ordered-v1", "anima-aesthetic-hybrid-v1"]),
                review_entry("sitting", profiles=["animagine-xl4-ordered-v1"]),
            ],
        ]
        for entries in reviews:
            with self.subTest(entries=entries), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                write_contracts(root, source, rows, entries)
                with self.assertRaisesRegex(ValueError, "implication"):
                    build_taxonomy_index(source, root)

    def test_render_is_deterministic_and_validation_detects_tampering(self) -> None:
        rows = [(2, "sitting", 0, 9), (1, "solo", 0, 10)]
        source = csv_bytes(rows)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_contracts(root, source, rows, [review_entry("solo")])
            first = build_taxonomy_index(source, root)
            second = build_taxonomy_index(source, root)
            self.assertEqual(render_taxonomy_index(first), render_taxonomy_index(second))
            self.assertEqual(validate_taxonomy_index(first, source, root), first)
            changed = json.loads(render_taxonomy_index(first))
            changed["entries"][0]["frequency"] += 1
            with self.assertRaisesRegex(ValueError, "does not match"):
                validate_taxonomy_index(changed, source, root)

    def test_lookup_rejects_rehashed_structurally_invalid_index(self) -> None:
        rows = [(1, "solo", 0, 10), (2, "sitting", 0, 9)]
        source = csv_bytes(rows)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_contracts(root, source, rows, [review_entry("solo")])
            index = build_taxonomy_index(source, root)

        duplicate = json.loads(render_taxonomy_index(index))
        duplicate["entries"].append(dict(duplicate["entries"][0]))
        duplicate["counts"]["source"] += 1
        duplicate["source"]["records"] += 1
        unsigned = dict(duplicate)
        unsigned.pop("index_id")
        duplicate["index_id"] = sha256(canonical_bytes(unsigned))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            lookup_taxonomy(duplicate, "solo")

    def test_lookup_resolves_reviewed_alias_but_keeps_unreviewed_source_ineligible(self) -> None:
        rows = [(1, "solo", 0, 10), (2, "unreviewed", 0, 9)]
        source = csv_bytes(rows)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_contracts(root, source, rows, [review_entry("solo", aliases=["single subject"])])
            index = build_taxonomy_index(source, root)
        alias = lookup_taxonomy(index, "single_subject")
        raw = lookup_taxonomy(index, "unreviewed")
        self.assertEqual(alias["source_name"], "solo")
        self.assertEqual(alias["match_kind"], "alias")
        self.assertFalse(raw["accepted_for_compilation"])
        self.assertIsNone(lookup_taxonomy(index, "missing"))

    def test_checked_in_contracts_build_against_retained_real_source(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        source_path = repository_root / ".runtime-test-source" / "selected_tags.csv"
        if not source_path.exists():
            self.skipTest("retained source fixture was not staged")
        contracts = load_taxonomy_contracts(repository_root)
        index = build_taxonomy_index(source_path.read_bytes(), repository_root)
        self.assertEqual(index["counts"]["source"], contracts["source"]["source"]["records"])
        self.assertGreaterEqual(index["counts"]["reviewed"], 30)
        self.assertEqual(lookup_taxonomy(index, "hot spring")["source_name"], "onsen")


class TaxonomyCliTests(unittest.TestCase):
    def test_cli_build_lookup_validate_and_exclusive_create(self) -> None:
        from scripts.studio_adult_illustration_taxonomy import main

        rows = [(1, "solo", 0, 10)]
        source = csv_bytes(rows)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_contracts(root, source, rows, [review_entry("solo", aliases=["single subject"])])
            source_path = root / "selected_tags.csv"
            index_path = root / "index.json"
            source_path.write_bytes(source)
            self.assertEqual(main(["build", str(source_path), "--repo-root", str(root), "--out", str(index_path)]), 0)
            original = index_path.read_bytes()
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self.assertEqual(main(["build", str(source_path), "--repo-root", str(root), "--out", str(index_path)]), 2)
            self.assertEqual(index_path.read_bytes(), original)
            self.assertIn("already exists", stderr.getvalue())
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(main(["lookup", str(index_path), "single subject"]), 0)
            self.assertEqual(json.loads(stdout.getvalue())["entry"]["source_name"], "solo")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(main(["validate", str(source_path), str(index_path), "--repo-root", str(root)]), 0)
            self.assertEqual(json.loads(stdout.getvalue())["counts"]["source"], 1)

    def test_cli_structured_failure_retains_zero_authority(self) -> None:
        from scripts.studio_adult_illustration_taxonomy import main

        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            status = main(["build", "missing.csv", "--out", "never.json"])
        self.assertEqual(status, 2)
        error = json.loads(stderr.getvalue())
        self.assertFalse(error["execution_authorized"])
        self.assertFalse(error["generation_submitted"])

    def test_cli_rejects_duplicate_saved_index_keys(self) -> None:
        from scripts.studio_adult_illustration_taxonomy import main

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "duplicate.json"
            path.write_text('{"schema":"first","schema":"second"}', encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                status = main(["lookup", str(path), "solo"])
        self.assertEqual(status, 2)
        self.assertIn("Duplicate JSON key", json.loads(stderr.getvalue())["error"])


if __name__ == "__main__":
    unittest.main()
