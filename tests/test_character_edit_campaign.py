import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout

from scripts import character_edit_campaign as campaign


class CampaignReceiptTests(unittest.TestCase):
    def test_create_is_canonical_and_validate_returns_a_copy(self):
        value = campaign.create("character-pilot", 12, campaign_id="a" * 32)
        self.assertEqual("character_edit_campaign", value["kind"])
        self.assertEqual(value["campaign_sha256"], campaign.io.hashed({key: item for key, item in value.items() if key != "campaign_sha256"}))
        checked = campaign.validate(value)
        checked["budget_owner"] = "changed"
        self.assertEqual("character-pilot", value["budget_owner"])

    def test_validate_rejects_changed_identity_hash_keys_and_bool_bounds(self):
        value = campaign.create("character-pilot", 12, campaign_id="a" * 32)
        cases = []
        changed = copy.deepcopy(value); changed["campaign_sha256"] = "0" * 64; cases.append(changed)
        changed = copy.deepcopy(value); changed["max_generation_attempts"] = 13; cases.append(changed)
        changed = copy.deepcopy(value); changed["campaign_id"] = "b" * 32; cases.append(changed)
        changed = copy.deepcopy(value); changed["unknown"] = True; cases.append(changed)
        changed = copy.deepcopy(value); del changed["budget_owner"]; cases.append(changed)
        for changed in cases:
            with self.subTest(changed=changed):
                with self.assertRaises(ValueError): campaign.validate(changed)
        for bad in (True, False, 0, 65):
            changed = copy.deepcopy(value); changed["max_generation_attempts"] = bad
            changed["campaign_sha256"] = campaign.io.hashed({key: item for key, item in changed.items() if key != "campaign_sha256"})
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError): campaign.validate(changed)
        changed = copy.deepcopy(value); changed["schema_version"] = True
        changed["campaign_sha256"] = campaign.io.hashed({key: item for key, item in changed.items() if key != "campaign_sha256"})
        with self.assertRaises(ValueError): campaign.validate(changed)

    def test_explicit_campaign_ids_remain_distinct(self):
        first = campaign.create("character-pilot", 12, campaign_id="a" * 32)
        second = campaign.create("character-pilot", 12, campaign_id="b" * 32)
        self.assertNotEqual(first["campaign_id"], second["campaign_id"])
        self.assertNotEqual(first["campaign_sha256"], second["campaign_sha256"])

    def test_write_is_exclusive_and_refuses_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = campaign.write(root, "campaign.json", "character-pilot", 12, campaign_id="a" * 32)
            saved = (root / "campaign.json").read_bytes()
            self.assertEqual(first, campaign.io.read(root / "campaign.json"))
            with self.assertRaises(FileExistsError):
                campaign.write(root, "campaign.json", "other", 1, campaign_id="b" * 32)
            self.assertEqual(saved, (root / "campaign.json").read_bytes())
            with self.assertRaises(ValueError): campaign.write(root, "../outside.json", "owner", 1)

    def test_cli_create_and_inspect_are_offline_file_operations(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(0, campaign.main(["create", "--workspace", str(root), "--out", "campaign.json", "--budget-owner", "character-pilot", "--max-generation-attempts", "12", "--campaign-id", "a" * 32]))
            self.assertEqual("a" * 32, json.loads(output.getvalue())["campaign_id"])
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(0, campaign.main(["inspect", "--workspace", str(root), "--campaign", "campaign.json"]))
            self.assertEqual("character_edit_campaign", json.loads(output.getvalue())["kind"])


if __name__ == "__main__":
    unittest.main()
