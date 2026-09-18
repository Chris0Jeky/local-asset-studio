from __future__ import annotations

import copy
from pathlib import Path
import tempfile
import unittest

from studio_prompt.adult_illustration_prompt_membership import inspect_prompt_membership
from tests.test_adult_illustration_prompt_membership import rehash, write_fixture
from tests.test_adult_illustration_taxonomy import csv_bytes


ROWS = [
    (1, "solo", 0, 100),
    (2, "mystery_tag", 0, 50),
    (3, "second_mystery_tag", 0, 40),
    (4, "watermark", 0, 25),
    (5, "blocked_tag", 0, 10),
]


class PromptMembershipSourceAuthenticationTests(unittest.TestCase):
    def test_exact_source_bytes_authenticate_unreviewed_membership(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            projection, compiled, index = write_fixture(root)
            report = inspect_prompt_membership(
                compiled,
                projection,
                index,
                csv_bytes(ROWS),
                root,
            )

        self.assertTrue(report["taxonomy"]["source_revalidated"])
        self.assertEqual(report["counts"]["source_known_unreviewed"], 2)
        self.assertEqual(report["counts"]["not_in_pinned_source"], 1)

    def test_rehashed_changed_unreviewed_row_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            projection, compiled, index = write_fixture(root)
            changed = copy.deepcopy(index)
            row = next(
                item
                for item in changed["entries"]
                if item["source_name"] == "mystery_tag"
            )
            row["source_name"] = "invented_tag"
            row["display"] = "invented tag"
            rehash(changed)

            with self.assertRaisesRegex(
                ValueError,
                "does not match exact source and review contracts",
            ):
                inspect_prompt_membership(
                    compiled,
                    projection,
                    changed,
                    csv_bytes(ROWS),
                    root,
                )

    def test_wrong_source_bytes_are_rejected_before_classification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            projection, compiled, index = write_fixture(root)
            with self.assertRaisesRegex(ValueError, "source byte count|source SHA-256"):
                inspect_prompt_membership(
                    compiled,
                    projection,
                    index,
                    b"tag_id,name,category,count\n1,forged,0,1\n",
                    root,
                )


if __name__ == "__main__":
    unittest.main()
