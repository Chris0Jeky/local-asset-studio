"""Character cards (#1205 v1): "my character" is a Workspace card whose canon is one chosen keeper picture.
Saving, editing and listing never reach ComfyUI or create a job."""
import importlib.util
import json
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("asset_server", ROOT / "app/server.py")
server = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(server)
import characters  # noqa: E402  (app/ is on sys.path once server.py is loaded)
import looks  # noqa: E402
from workspace import WorkspaceError  # noqa: E402

TEXT = {"id": "text-only", "name": "Text only", "modality": "image", "graph": "workflows/api/demo-api.json", "positive": ["1", "text"]}
BODY = {"who": "  Mira, a young elf with\n short silver hair ", "clothes": "a green cloak with gold trim"}


class CharacterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        (self.root / "presets").mkdir(); (self.root / "workflows/api").mkdir(parents=True); (self.root / "config").mkdir()
        (self.root / "fake-comfy/input").mkdir(parents=True)
        (self.root / "config/local.json").write_text(json.dumps({"comfy_root": str(self.root / "fake-comfy")}))
        (self.root / "presets/catalog.json").write_text(json.dumps({"presets": [TEXT]}))
        (self.root / "workflows/api/demo-api.json").write_text(json.dumps({"1": {"inputs": {"text": "x"}}}))
        self.start = patch.object(threading.Thread, "start", lambda *_: None); self.start.start()
        self.addCleanup(self.start.stop); self.addCleanup(self.tmp.cleanup)
        self.studio = server.Studio(self.root)
        self.requests = []; self.studio._request = lambda *a, **k: self.requests.append(a) or {}
        self.canon = self.picture("job-canon", b"canon keeper bytes")

    def picture(self, job, data):
        source = self.root / (job + ".png"); source.write_bytes(data)
        return self.studio.assets.register({"id": job, "preset_id": "text-only", "preset_name": "Text only", "outputs": [{"filename": job + ".png"}]}, 0, source)

    def trash_picture(self, asset):
        self.studio.assets.update({"ids": [asset], "action": "trash", "request_id": "trash-" + asset, "expected_revisions": {asset: self.studio.assets.get(asset)["metadata_revision"]}})

    def create(self, **extra):
        return characters.command(self.studio, {"action": "create", "kind": "character", "name": "Mira", "body": BODY, "canon_asset_id": self.canon, **extra})

    def listed(self):
        return {entry["id"]: entry for entry in characters.listing(self.studio)["characters"]}

    def route(self, method, path, body=None):
        handler = server.Handler.__new__(server.Handler); handler.studio = self.studio; handler.path = path
        handler._safe_mutation = lambda: True; handler._safe_host = lambda: True; handler._body_json = lambda *a: body
        sent = []; handler._json = lambda status, obj: sent.append((status, obj))
        getattr(handler, "do_" + method)()
        return sent[0]

    def test_create_records_the_canon_from_the_workspace_and_normalizes_words(self):
        card = self.create()
        self.assertEqual((card["kind"], card["name"], card["revision"]), ("character", "Mira", 0))
        self.assertEqual(card["body"], {"who": "Mira, a young elf with short silver hair", "clothes": "a green cloak with gold trim"})
        canon = card["lineage"]
        self.assertEqual(len(canon), 1)
        self.assertEqual((canon[0]["role"], canon[0]["asset_id"], canon[0]["job_id"], canon[0]["sha256"]), ("canon", self.canon, "job-canon", self.studio.assets.get(self.canon)["sha256"]))
        entry = self.listed()[card["id"]]
        self.assertEqual((entry["usable"], entry["unusable_reason"], entry["canon_asset_id"]), (True, None, self.canon))
        self.assertEqual((self.studio.jobs, self.requests), ({}, []))

    def test_revise_needs_the_revision_read_and_a_stale_one_changes_nothing(self):
        card = self.create(); other = self.picture("job-other", b"another keeper")
        edited = characters.command(self.studio, {"action": "edit", "id": card["id"], "expected_revision": 0, "body": dict(BODY, avoid="glasses"), "canon_asset_id": other})
        self.assertEqual((edited["revision"], edited["body"]["avoid"], edited["lineage"][0]["asset_id"]), (1, "glasses", other))
        with self.assertRaises(WorkspaceError) as caught:
            characters.command(self.studio, {"action": "edit", "id": card["id"], "expected_revision": 0, "name": "Stale"})
        self.assertEqual((caught.exception.status, caught.exception.code), (409, "card_revision_conflict"))
        self.assertEqual(self.studio.assets.card(card["id"])["name"], "Mira")
        with self.assertRaises(WorkspaceError) as caught: characters.command(self.studio, {"action": "edit", "id": card["id"], "name": "No revision"})
        self.assertEqual(caught.exception.status, 428)

    def test_put_away_and_restore_are_reversible(self):
        card = self.create()
        trashed = characters.command(self.studio, {"action": "trash", "id": card["id"], "expected_revision": 0})
        self.assertTrue(trashed["trashed_at"])
        entry = self.listed()[card["id"]]
        self.assertEqual((entry["usable"], entry["unusable_reason"]), (False, "This character is put away. Restore it to use it."))
        restored = characters.command(self.studio, {"action": "restore", "id": card["id"], "expected_revision": 1})
        self.assertEqual((restored["trashed_at"], restored["revision"], self.listed()[card["id"]]["usable"]), (None, 2, True))

    def test_a_missing_canon_picture_is_reported_unusable_and_a_copy_by_content_still_counts(self):
        card = self.create()
        self.trash_picture(self.canon)
        entry = self.listed()[card["id"]]
        self.assertEqual((entry["usable"], entry["canon_asset_id"]), (False, None))
        self.assertIn("canon picture is no longer in the library", entry["unusable_reason"])
        copy = self.picture("job-copy", b"canon keeper bytes")   # the same bytes imported again: the canon is content, not a row
        self.assertEqual((self.listed()[card["id"]]["usable"], self.listed()[card["id"]]["canon_asset_id"]), (True, copy))

    def test_invalid_fields_are_refused_and_nothing_is_stored(self):
        cases = ({"body": {"clothes": "a cloak"}}, {"body": dict(BODY, who="   ")}, {"body": dict(BODY, who="x" * 601)}, {"body": dict(BODY, clothes=7)},
                 {"body": dict(BODY, surprise=1)}, {"body": dict(BODY, look_id="bad id!")}, {"body": dict(BODY, look_id="look-missing")}, {"body": []},
                 {"canon_asset_id": None}, {"canon_asset_id": "missing-asset"}, {"lineage": [{"role": "canon", "sha256": "0" * 64}]},
                 {"kind": "look"}, {"name": ""}, {"name": "x" * 121}, {"surprise": 1})
        for extra in cases:
            with self.subTest(extra=repr(extra)[:60]), self.assertRaises(WorkspaceError): self.create(**extra)
        self.assertEqual(self.studio.assets.cards("character"), [])
        self.trash_picture(self.canon)
        with self.assertRaisesRegex(WorkspaceError, "put away"): self.create()

    def test_a_preferred_look_must_be_a_saved_look_and_kinds_stay_apart(self):
        look = looks.command(self.studio, {"action": "create", "kind": "look", "name": "Plain", "body": {"preset_id": "text-only", "template": "A {scene}."}})
        card = self.create(body=dict(BODY, look_id=look["id"]))
        self.assertEqual(card["body"]["look_id"], look["id"])
        with self.assertRaisesRegex(WorkspaceError, "not a saved look"): self.create(id="other-character", body=dict(BODY, look_id=card["id"]))
        with self.assertRaisesRegex(WorkspaceError, "not a character"): characters.command(self.studio, {"action": "trash", "id": look["id"], "expected_revision": 0})
        with self.assertRaisesRegex(WorkspaceError, "not a look"): looks.command(self.studio, {"action": "trash", "id": card["id"], "expected_revision": 0})
        self.assertEqual([entry["id"] for entry in looks.listing(self.studio)["looks"]], [look["id"]])

    def test_routes_list_and_save_without_creating_a_job(self):
        status, created = self.route("POST", "/api/characters", {"action": "create", "kind": "character", "name": "Mira", "body": BODY, "canon_asset_id": self.canon})
        self.assertEqual((status, created["revision"]), (200, 0))
        status, listed = self.route("GET", "/api/characters")
        self.assertEqual((status, [entry["id"] for entry in listed["characters"]], listed["characters"][0]["canon_asset_id"], listed["generation_submitted"]),
                         (200, [created["id"]], self.canon, False))
        status, refused = self.route("POST", "/api/characters", {"action": "create", "kind": "character", "name": "Mira", "body": {}, "canon_asset_id": self.canon})
        self.assertEqual(status, 400); self.assertIn("required", refused["error"])
        self.assertEqual((self.studio.jobs, self.requests), ({}, []))

    def set_row(self, table, row_id, **values):
        """Write stored columns directly, past every command, to model a row that never went through validation."""
        assignments = ", ".join(column + "=?" for column in values)
        with closing(sqlite3.connect(self.studio.assets.database)) as db, db: db.execute(f"UPDATE {table} SET {assignments} WHERE id=?", (*values.values(), row_id))

    def clip(self):
        source = self.root / "clip.mp4"; source.write_bytes(b"not really a picture")
        return self.studio.assets.register({"id": "job-clip", "preset_id": "text-only", "preset_name": "Text only", "outputs": [{"filename": "clip.mp4", "media_type": "video"}]}, 0, source)

    def test_a_canon_whose_recorded_digest_no_longer_matches_is_replaced_by_a_content_copy(self):
        card = self.create()
        self.set_row("assets", self.canon, sha256="0" * 64)   # the recorded picture no longer names the canon's bytes: ignored
        entry = self.listed()[card["id"]]
        self.assertEqual((entry["usable"], entry["canon_asset_id"]), (False, None))
        self.assertIn("canon picture is no longer in the library", entry["unusable_reason"])
        copy = self.picture("job-copy", b"canon keeper bytes")   # the same bytes, so the same sha256: the content copy is the canon
        entry = self.listed()[card["id"]]
        self.assertEqual((entry["usable"], entry["canon_asset_id"], entry["unusable_reason"]), (True, copy, None))
        self.assertEqual(self.studio.assets.get(copy)["sha256"], card["lineage"][0]["sha256"])

    def test_a_stored_body_that_was_never_validated_is_listed_unusable_with_its_reason(self):
        card = self.create()
        self.set_row("cards", card["id"], body=json.dumps({"clothes": "a green cloak"}))   # no who: written past the command
        entry = self.listed()[card["id"]]
        self.assertEqual((entry["usable"], entry["unusable_reason"], entry["canon_asset_id"]), (False, "Who they are is required", self.canon))

    def test_a_canon_that_is_not_a_picture_is_listed_unusable(self):
        clip = self.clip()
        card = self.studio.assets.card_command({"action": "create", "kind": "character", "name": "Clip", "body": BODY,
                                                "lineage": [{"role": "canon", "asset_id": clip, "sha256": self.studio.assets.get(clip)["sha256"], "job_id": "job-clip"}]})
        entry = self.listed()[card["id"]]
        self.assertEqual((entry["usable"], entry["unusable_reason"], entry["canon_asset_id"]), (False, "Its canon is not a picture.", clip))

    def test_a_non_picture_canon_is_refused_and_nothing_is_stored(self):
        with self.assertRaisesRegex(WorkspaceError, "A character's canon is a picture"):
            characters.command(self.studio, {"action": "create", "kind": "character", "name": "Clip", "body": BODY, "canon_asset_id": self.clip()})
        self.assertEqual(self.studio.assets.cards("character"), [])

    def test_a_canon_cannot_be_named_when_a_character_is_put_away_or_restored(self):
        card = self.create()
        with self.assertRaisesRegex(WorkspaceError, "chosen when the character is saved or edited"):
            characters.command(self.studio, {"action": "trash", "id": card["id"], "expected_revision": 0, "canon_asset_id": self.canon})
        self.assertIsNone(self.studio.assets.card(card["id"])["trashed_at"])
        trashed = characters.command(self.studio, {"action": "trash", "id": card["id"], "expected_revision": 0})
        with self.assertRaisesRegex(WorkspaceError, "chosen when the character is saved or edited"):
            characters.command(self.studio, {"action": "restore", "id": card["id"], "expected_revision": 1, "canon_asset_id": self.canon})
        self.assertEqual((self.studio.assets.card(card["id"])["trashed_at"], self.studio.assets.card(card["id"])["revision"]), (trashed["trashed_at"], 1))

    def test_the_canon_lineage_carries_a_preset_id_exactly_when_the_picture_has_one(self):
        self.assertEqual(self.create()["lineage"][0]["preset_id"], "text-only")
        bare_source = self.root / "bare.png"; bare_source.write_bytes(b"bare keeper")
        bare = self.studio.assets.register({"id": "job-bare", "outputs": [{"filename": "bare.png"}]}, 0, bare_source)
        self.assertIsNone(self.studio.assets.get(bare)["preset_id"])
        bare_card = self.create(id="bare-character", canon_asset_id=bare)
        self.assertEqual(bare_card["lineage"][0]["asset_id"], bare)
        self.assertNotIn("preset_id", bare_card["lineage"][0])

    def test_a_character_command_must_be_an_object(self):
        for payload in ([], "x", None, 3):
            with self.subTest(payload=repr(payload)), self.assertRaisesRegex(WorkspaceError, "Character command must be an object"):
                characters.command(self.studio, payload)
        self.assertEqual(self.studio.assets.cards("character"), [])

    def test_canon_of_skips_entries_that_are_not_objects_and_is_none_without_a_canon(self):
        canon = {"role": "canon", "asset_id": self.canon, "sha256": "a" * 64}
        self.assertEqual(characters.canon_of({"lineage": ["junk", None, 7, ["canon"], canon]}), canon)
        self.assertIsNone(characters.canon_of({"lineage": ["junk", {"role": "anchor"}]}))
        self.assertIsNone(characters.canon_of({"lineage": []}))
        self.assertIsNone(characters.canon_of({}))


if __name__ == "__main__":
    unittest.main()
