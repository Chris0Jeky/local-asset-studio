from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from studio_prompt.adult_illustration_prompt_projection import compile_prompt
from studio_prompt.adult_illustration_taxonomy_contracts import (
    AUTHORITY,
    INDEX_SCHEMA,
    canonical_bytes,
    load_taxonomy_contracts,
    sha256,
)
from studio_prompt.adult_illustration_taxonomy_membership import (
    inspect_prompt_taxonomy_membership,
)
from tests.test_adult_illustration_taxonomy_prompt_integration import (
    projection_with_terms,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "studio_adult_illustration_prompt.py"


def synthetic_index() -> dict[str, object]:
    """Build bounded index evidence without retaining the external source CSV."""
    contracts = load_taxonomy_contracts(ROOT)
    source = contracts["source"]
    review = contracts["review"]
    category = next(iter(source["categories"].values()))
    entries: list[dict[str, object]] = []
    tag_id = 1

    for reviewed in review["entries"]:
        entries.append(
            {
                "tag_id": tag_id,
                "source_name": reviewed["source_name"],
                "source_category": category["id"],
                "source_category_value": category["source_value"],
                "frequency": 1000 - tag_id,
                "reviewed": True,
                "display": reviewed["display"],
                "aliases": list(reviewed["aliases"]),
                "implications": list(reviewed["implications"]),
                "deprecated_by": reviewed["deprecated_by"],
                "semantic_facets": list(reviewed["semantic_facets"]),
                "polarity": reviewed["polarity"],
                "profile_ids": list(reviewed["profile_ids"]),
                "accepted_for_compilation": reviewed["accepted_for_compilation"],
            }
        )
        tag_id += 1

    entries.append(
        {
            "tag_id": tag_id,
            "source_name": "source_only_term",
            "source_category": category["id"],
            "source_category_value": category["source_value"],
            "frequency": 7,
            "reviewed": False,
            "display": "source only term",
            "aliases": [],
            "implications": [],
            "deprecated_by": None,
            "semantic_facets": [],
            "polarity": None,
            "profile_ids": [],
            "accepted_for_compilation": False,
        }
    )
    tag_id += 1

    while len(entries) < source["source"]["records"]:
        name = f"synthetic_source_term_{len(entries):05d}"
        entries.append(
            {
                "tag_id": tag_id,
                "source_name": name,
                "source_category": category["id"],
                "source_category_value": category["source_value"],
                "frequency": 0,
                "reviewed": False,
                "display": name.replace("_", " "),
                "aliases": [],
                "implications": [],
                "deprecated_by": None,
                "semantic_facets": [],
                "polarity": None,
                "profile_ids": [],
                "accepted_for_compilation": False,
            }
        )
        tag_id += 1

    entries.sort(key=lambda item: (str(item["source_name"]).casefold(), int(item["tag_id"])))
    index: dict[str, object] = {
        "schema": INDEX_SCHEMA,
        "kind": "anime-tag-taxonomy-index",
        "executable": False,
        "authority": dict(AUTHORITY),
        **AUTHORITY,
        "source": {
            key: source["source"][key]
            for key in (
                "provider",
                "repository",
                "revision",
                "selected_file",
                "bytes",
                "sha256",
                "records",
            )
        },
        "contracts": {
            "source_manifest_sha256": source["manifest_sha256"],
            "review_manifest_sha256": review["manifest_sha256"],
        },
        "counts": {
            "source": len(entries),
            "reviewed": len(review["entries"]),
            "accepted": sum(
                int(entry["accepted_for_compilation"]) for entry in review["entries"]
            ),
            "aliases": sum(len(entry["aliases"]) for entry in review["entries"]),
        },
        "entries": entries,
        "notes": [
            "Synthetic source membership fixture; exact source bytes are not reconstructed."
        ],
    }
    index["index_id"] = sha256(canonical_bytes(index))
    return index


def rehash(index: dict[str, object]) -> dict[str, object]:
    value = copy.deepcopy(index)
    value.pop("index_id", None)
    value["index_id"] = sha256(canonical_bytes(value))
    return value


def load_cli():
    spec = importlib.util.spec_from_file_location("adult_prompt_membership_cli", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class PromptTaxonomyMembershipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.index = synthetic_index()
        cls.source = projection_with_terms(
            ["hot spring", "source only term", "not in pinned source"],
            ["watermark"],
        )
        cls.compiled = compile_prompt(
            cls.source, "animagine-xl4-ordered-v1", ROOT
        )

    def inspect(self, index=None, source=None, compiled=None):
        return inspect_prompt_taxonomy_membership(
            self.compiled if compiled is None else compiled,
            self.source if source is None else source,
            self.index if index is None else index,
            ROOT,
        )

    def test_reports_reviewed_unreviewed_and_absent_membership_once(self) -> None:
        result = self.inspect()
        rows = {
            (item["channel"], item["input"]): item
            for item in result["memberships"]
        }
        self.assertEqual(len(rows), len(self.compiled["vocabulary_resolutions"]))

        reviewed = rows[("positive", "hot spring")]
        self.assertEqual(reviewed["compiler"]["source"], "reviewed_taxonomy")
        self.assertEqual(reviewed["membership"], "reviewed")
        self.assertEqual(reviewed["match_kind"], "alias")
        self.assertEqual(reviewed["source_name"], "onsen")
        self.assertTrue(reviewed["accepted_for_compilation"])

        unreviewed = rows[("positive", "source only term")]
        self.assertEqual(unreviewed["compiler"]["status"], "unknown")
        self.assertEqual(unreviewed["membership"], "source_known_unreviewed")
        self.assertEqual(unreviewed["match_kind"], "normalised_space")
        self.assertEqual(unreviewed["source_name"], "source_only_term")
        self.assertFalse(unreviewed["reviewed"])

        absent = rows[("positive", "not in pinned source")]
        self.assertEqual(absent["membership"], "absent")
        self.assertIsNone(absent["source_name"])
        self.assertIsNone(absent["tag_id"])

    def test_report_is_deterministic_content_addressed_and_non_executing(self) -> None:
        first = self.inspect()
        second = self.inspect()
        self.assertEqual(first, second)
        unsigned = dict(first)
        identity = unsigned.pop("report_sha256")
        self.assertEqual(identity, sha256(canonical_bytes(unsigned)))
        self.assertFalse(first["source_revalidated"])
        self.assertEqual(first["authority"], AUTHORITY)
        self.assertTrue(all(value is False for value in first["authority"].values()))

    def test_stale_contract_hash_is_rejected_even_after_rehash(self) -> None:
        stale = copy.deepcopy(self.index)
        stale["contracts"]["review_manifest_sha256"] = "0" * 64
        stale = rehash(stale)
        with self.assertRaisesRegex(ValueError, "review contract"):
            self.inspect(index=stale)

    def test_rehashed_structurally_invalid_index_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.index)
        invalid["entries"][1]["source_name"] = invalid["entries"][0]["source_name"]
        invalid = rehash(invalid)
        with self.assertRaisesRegex(ValueError, "duplicate canonical"):
            self.inspect(index=invalid)

    def test_changed_source_projection_cannot_be_joined_to_retained_prompt(self) -> None:
        changed = projection_with_terms(["closed eyes"])
        with self.assertRaisesRegex(ValueError, "Changed or invalid prompt projection"):
            self.inspect(source=changed)

    def test_inspection_has_no_network_process_or_socket_side_effect(self) -> None:
        with (
            patch.object(socket, "create_connection", side_effect=AssertionError("network")),
            patch.object(subprocess, "run", side_effect=AssertionError("process")),
            patch("urllib.request.urlopen", side_effect=AssertionError("download")),
        ):
            result = self.inspect()
        self.assertFalse(result["authority"]["generation_submitted"])

    def test_cli_reads_large_index_and_never_overwrites_output(self) -> None:
        cli = load_cli()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_path = root / "source.json"
            compiled_path = root / "compiled.json"
            index_path = root / "index.json"
            output_path = root / "report.json"
            source_path.write_text(json.dumps(self.source), encoding="utf-8")
            compiled_path.write_text(json.dumps(self.compiled), encoding="utf-8")
            index_path.write_text(json.dumps(self.index), encoding="utf-8")
            arguments = [
                "inspect-membership",
                str(compiled_path),
                "--source",
                str(source_path),
                "--taxonomy-index",
                str(index_path),
                "--repo-root",
                str(ROOT),
                "--out",
                str(output_path),
            ]
            self.assertEqual(cli.main(arguments), 0)
            report = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(
                report["schema"],
                "studio.adult-illustration.prompt-taxonomy-membership/v1",
            )
            self.assertEqual(cli.main(arguments), 2)


if __name__ == "__main__":
    unittest.main()
