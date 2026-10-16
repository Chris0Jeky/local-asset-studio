"""Character cards (#1205 v1): "my character" is a Workspace card whose canon is one chosen keeper picture.
Saving, editing and listing never reach ComfyUI or create a job."""
import importlib.util
import json
import tempfile
import threading
import unittest
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


if __name__ == "__main__":
    unittest.main()
