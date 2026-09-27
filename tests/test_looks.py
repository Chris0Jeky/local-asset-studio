"""Look templates (#1221): a saved wording template with a {scene} slot plus its recipe, stored as a Workspace card.
Choosing a look and typing a scene prepares Create; nothing here reaches ComfyUI or creates a job."""
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
import looks  # noqa: E402  (app/ is on sys.path once server.py is loaded, as under the launcher)
from workspace import WorkspaceError  # noqa: E402

GRAPH = {"1": {"inputs": {"text": "authored", "width": 512, "height": 512, "seed": 1, "steps": 8}}}
TEXT = {"id": "text-only", "name": "Text only", "modality": "image", "graph": "workflows/api/demo-api.json", "positive": ["1", "text"],
        "width": ["1", "width"], "height": ["1", "height"], "seed": ["1", "seed"], "steps": ["1", "steps"]}
WITH_NEGATIVE = dict(TEXT, id="with-negative", name="With negative", negative=["1", "text"])
PICTURE = dict(TEXT, id="picture", name="Picture route", reference=["1", "text"])
VIDEO = dict(TEXT, id="video", name="Video", modality="video")
TEMPLATE = "No people. Painted background of {scene}. Quiet left half, amber accents."
BODY = {"preset_id": "text-only", "template": TEMPLATE, "negative": "", "controls": {"seed": 77, "width": 1344, "height": 768}}
WALL = {"id": "quiet_wall", "label": "Keep the quiet wall for UI backgrounds", "text": "The left half is a plain wall.", "default": False}
OPTIONAL = dict(BODY, template="No people. Painted background of {scene}. {quiet_wall} Amber accents.", options=[WALL])
V1 = ROOT / "tests/fixtures/looks-v1-2026-09-27.json"   # presets/looks.json as #1224 shipped it
NIGHT = "look-night-shift-retro-anime"


class LookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        (self.root / "presets").mkdir(); (self.root / "workflows/api").mkdir(parents=True); (self.root / "config").mkdir()
        (self.root / "fake-comfy/input").mkdir(parents=True)
        (self.root / "config/local.json").write_text(json.dumps({"comfy_root": str(self.root / "fake-comfy")}))
        (self.root / "presets/catalog.json").write_text(json.dumps({"presets": [TEXT, WITH_NEGATIVE, PICTURE, VIDEO]}))
        (self.root / "workflows/api/demo-api.json").write_text(json.dumps(GRAPH))
        self.start = patch.object(threading.Thread, "start", lambda *_: None); self.start.start()
        self.addCleanup(self.start.stop); self.addCleanup(self.tmp.cleanup)
        self.studio = server.Studio(self.root)
        self.requests = []; self.studio._request = lambda *a, **k: self.requests.append(a) or {}

    def create(self, **extra):
        return looks.command(self.studio, {"action": "create", "kind": "look", "name": "Night Shift", "body": BODY, **extra})

    def route(self, method, path, body=None):
        handler = server.Handler.__new__(server.Handler); handler.studio = self.studio; handler.path = path
        handler._safe_mutation = lambda: True; handler._safe_host = lambda: True; handler._body_json = lambda *a: body
        sent = []; handler._json = lambda status, obj: sent.append((status, obj))
        getattr(handler, "do_" + method)()
        return sent[0]

    # ------------------------------------------------------------------ composing
    def test_compose_puts_the_scene_in_the_one_slot(self):
        self.assertEqual(looks.compose(TEMPLATE, "  a rainy\n rooftop.  "), "No people. Painted background of a rainy rooftop. Quiet left half, amber accents.")
        for scene in ("", "   ", ".", "x" * (looks.SCENE_MAX + 1), "a {scene} inside", 7, None):
            with self.subTest(scene=repr(scene)[:40]), self.assertRaises(WorkspaceError): looks.compose(TEMPLATE, scene)

    def test_a_template_has_exactly_one_scene_slot(self):
        preset = TEXT
        for template in ("no slot", "{scene} and {scene}", "", "x" * 4001 + "{scene}"):
            with self.subTest(template=template[:30]), self.assertRaises(WorkspaceError): looks.validate_body(dict(BODY, template=template), preset)
        self.assertEqual(looks.validate_body(dict(BODY, template="  " + TEMPLATE + " "), preset)["template"], TEMPLATE)

    def test_a_look_belongs_to_one_text_to_image_recipe_and_only_its_bound_controls(self):
        with self.assertRaisesRegex(WorkspaceError, "picture"): looks.validate_body(dict(BODY, preset_id="picture"), PICTURE)
        with self.assertRaisesRegex(WorkspaceError, "image"): looks.validate_body(dict(BODY, preset_id="video"), VIDEO)
        with self.assertRaisesRegex(WorkspaceError, "not bound"): looks.validate_body(dict(BODY, controls={"cfg": 3}), TEXT)
        for controls in ({"positive": "x"}, {"reference": "a.png"}, {"seed": float("inf")}, {"seed": [1]}, {"seed": None}, []):
            with self.subTest(controls=repr(controls)), self.assertRaises(WorkspaceError): looks.validate_body(dict(BODY, controls=controls), TEXT)
        with self.assertRaisesRegex(WorkspaceError, "negative"): looks.validate_body(dict(BODY, negative="blurry"), TEXT)
        self.assertEqual(looks.validate_body(dict(BODY, preset_id="with-negative", negative=" blurry "), WITH_NEGATIVE)["negative"], "blurry")
        with self.assertRaisesRegex(WorkspaceError, "Unknown look fields"): looks.validate_body(dict(BODY, surprise=1), TEXT)
        with self.assertRaisesRegex(WorkspaceError, "recipe"): looks.validate_body(dict(BODY, preset_id="other"), TEXT)

    # ------------------------------------------------------------------ optional lines
    def test_an_optional_line_is_a_named_sentence_with_one_place_in_the_wording(self):
        """Owner, 27 Sep 2026: layout sentences leave the always-on wording for a line the owner can switch on."""
        self.assertEqual(looks.validate_body(OPTIONAL, TEXT)["options"], [WALL])
        self.assertEqual(looks.validate_body(dict(OPTIONAL, options=[dict(WALL, label=" Keep it ", default=True)]), TEXT)["options"][0]["label"], "Keep it")
        self.assertNotIn("options", looks.validate_body(BODY, TEXT), "a look without optional lines stores none")
        bad = [
            ([dict(WALL, id="Quiet wall")], "id"), ([dict(WALL, id="scene")], "id"), ([WALL, WALL], "once"),
            ([dict(WALL, id="other")], "exactly once"), ([dict(WALL, text="")], "required"), ([dict(WALL, label="")], "required"),
            ([dict(WALL, text="of {scene}")], "slot"), ([dict(WALL, text="again {quiet_wall}")], "slot"), ([dict(WALL, default="yes")], "true or false"),
            ([dict(WALL, extra=1)], "fields"), ("wall", "list"), ([WALL] * 7, "list"), ([dict(WALL, text="x" * 1001)], "1000"),
        ]
        for options, message in bad:
            with self.subTest(options=repr(options)[:60]), self.assertRaisesRegex(WorkspaceError, message): looks.validate_body(dict(OPTIONAL, options=options), TEXT)
        with self.assertRaisesRegex(WorkspaceError, "exactly once"): looks.validate_body(dict(OPTIONAL, template=OPTIONAL["template"] + " {quiet_wall}"), TEXT)

    def test_compose_writes_an_optional_line_only_when_it_is_on(self):
        options = [WALL]; template = OPTIONAL["template"]
        self.assertEqual(looks.compose(template, "a hall", options), "No people. Painted background of a hall. Amber accents.")
        self.assertEqual(looks.compose(template, "a hall", options, {"quiet_wall": True}), "No people. Painted background of a hall. The left half is a plain wall. Amber accents.")
        self.assertEqual(looks.compose(template, "a hall", [dict(WALL, default=True)]), "No people. Painted background of a hall. The left half is a plain wall. Amber accents.")
        self.assertIn("{quiet_wall}", looks.compose(template, "a {quiet_wall} sign", options), "a scene's own braces are the scene's words")
        for chosen, message in (({"other": True}, "Unknown optional line"), ({"quiet_wall": "on"}, "true or false"), (["quiet_wall"], "object")):
            with self.subTest(chosen=chosen), self.assertRaisesRegex(WorkspaceError, message): looks.compose(template, "a hall", options, chosen)

    def test_prepare_takes_the_optional_lines_and_says_which_were_on(self):
        card = self.create(body=OPTIONAL)
        plain = looks.prepare(self.studio, {"id": card["id"], "scene": "a hall"})
        self.assertEqual((plain["controls"]["positive"], plain["look"]["options"]), ("No people. Painted background of a hall. Amber accents.", {"quiet_wall": False}))
        walled = looks.prepare(self.studio, {"id": card["id"], "scene": "a hall", "options": {"quiet_wall": True}, "expected_revision": 0})
        self.assertIn("The left half is a plain wall.", walled["controls"]["positive"]); self.assertEqual(walled["look"]["options"], {"quiet_wall": True})
        with self.assertRaisesRegex(WorkspaceError, "Unknown optional line"): looks.prepare(self.studio, {"id": card["id"], "scene": "a hall", "options": {"x": True}})
        self.assertEqual((self.studio.jobs, self.requests), ({}, []))

    # ------------------------------------------------------------------ storing
    def test_saving_a_look_records_the_anchor_picture_from_the_workspace(self):
        source = self.root / "anchor.png"; source.write_bytes(b"anchor picture bytes")
        asset = self.studio.assets.register({"id": "job-anchor", "preset_id": "text-only", "preset_name": "Text only", "outputs": [{"filename": "anchor.png"}]}, 0, source)
        card = self.create(anchor_asset_id=asset)
        anchor = card["lineage"][0]
        self.assertEqual((anchor["role"], anchor["asset_id"], anchor["job_id"], anchor["preset_id"]), ("anchor", asset, "job-anchor", "text-only"))
        self.assertEqual(anchor["sha256"], self.studio.assets.get(asset)["sha256"])
        with self.assertRaises(WorkspaceError): self.create(anchor_asset_id="missing-asset")
        with self.assertRaisesRegex(WorkspaceError, "kind"): looks.command(self.studio, {"action": "create", "kind": "character", "name": "x", "body": BODY})

    def test_edits_are_validated_and_revision_guarded(self):
        card = self.create()
        with self.assertRaises(WorkspaceError): looks.command(self.studio, {"action": "edit", "id": card["id"], "expected_revision": 0, "body": dict(BODY, template="no slot")})
        edited = looks.command(self.studio, {"action": "edit", "id": card["id"], "expected_revision": 0, "body": dict(BODY, controls={"seed": 5})})
        self.assertEqual((edited["revision"], edited["body"]["controls"]), (1, {"seed": 5}))
        with self.assertRaises(WorkspaceError) as caught: looks.command(self.studio, {"action": "trash", "id": card["id"], "expected_revision": 0})
        self.assertEqual(caught.exception.status, 409)

    def test_listing_says_which_looks_can_be_used_and_finds_the_anchor_by_content(self):
        source = self.root / "anchor.png"; source.write_bytes(b"anchor picture bytes")
        asset = self.studio.assets.register({"id": "job-anchor", "preset_name": "Text only", "outputs": [{"filename": "anchor.png"}]}, 0, source)
        digest = self.studio.assets.get(asset)["sha256"]
        self.create(lineage=[{"role": "anchor", "sha256": digest, "job_id": "elsewhere"}])
        orphan = looks.command(self.studio, {"action": "create", "kind": "look", "name": "Orphan", "body": BODY})
        with self.studio.assets.connection() as db:
            db.execute("UPDATE cards SET body=? WHERE id=?", (json.dumps(dict(BODY, preset_id="removed")), orphan["id"]))
        listed = {entry["name"]: entry for entry in looks.listing(self.studio)["looks"]}
        self.assertEqual((listed["Night Shift"]["usable"], listed["Night Shift"]["preset_name"], listed["Night Shift"]["anchor_asset_id"]), (True, "Text only", asset))
        self.assertEqual((listed["Orphan"]["usable"], listed["Orphan"]["anchor_asset_id"]), (False, None))
        self.assertIn("not in the recipe library", listed["Orphan"]["unusable_reason"])

    # ------------------------------------------------------------------ preparing
    def test_prepare_composes_the_wording_and_submits_nothing(self):
        card = self.create()
        ready = looks.prepare(self.studio, {"id": card["id"], "scene": "a narrow corridor with a vending machine", "expected_revision": 0})
        self.assertEqual(ready["preset_id"], "text-only")
        self.assertEqual(ready["controls"], {"positive": "No people. Painted background of a narrow corridor with a vending machine. Quiet left half, amber accents.",
                                             "seed": 77, "width": 1344, "height": 768})
        self.assertEqual((ready["look"], ready["generation_submitted"]), ({"id": card["id"], "name": "Night Shift", "revision": 0}, False))
        self.assertEqual((self.studio.jobs, self.requests), ({}, []))

    def test_prepare_writes_the_looks_negative_only_where_the_recipe_has_one(self):
        card = looks.command(self.studio, {"action": "create", "kind": "look", "name": "Neg", "body": dict(BODY, preset_id="with-negative", negative="blurry")})
        self.assertEqual(looks.prepare(self.studio, {"id": card["id"], "scene": "a hall"})["controls"]["negative"], "blurry")

    def test_prepare_refuses_a_put_away_stale_or_broken_look(self):
        card = self.create()
        with self.assertRaises(WorkspaceError) as caught: looks.prepare(self.studio, {"id": card["id"], "scene": "a hall", "expected_revision": 3})
        self.assertEqual(caught.exception.status, 409)
        looks.command(self.studio, {"action": "trash", "id": card["id"], "expected_revision": 0})
        with self.assertRaisesRegex(WorkspaceError, "put away"): looks.prepare(self.studio, {"id": card["id"], "scene": "a hall"})
        for payload in ({}, {"id": card["id"]}, {"id": "missing", "scene": "a hall"}, [], {"id": card["id"], "scene": "a hall", "extra": 1}):
            with self.subTest(payload=repr(payload)), self.assertRaises(WorkspaceError): looks.prepare(self.studio, payload)
        self.assertEqual(self.studio.jobs, {})

    # ------------------------------------------------------------------ routes
    def test_routes_list_save_and_prepare_without_creating_a_job(self):
        status, created = self.route("POST", "/api/looks", {"action": "create", "kind": "look", "name": "Night Shift", "body": BODY})
        self.assertEqual(status, 200); self.assertEqual(created["revision"], 0)
        status, listed = self.route("GET", "/api/looks")
        self.assertEqual((status, [entry["id"] for entry in listed["looks"]], listed["generation_submitted"]), (200, [created["id"]], False))
        status, ready = self.route("POST", "/api/looks/prepare", {"id": created["id"], "scene": "a rooftop"})
        self.assertEqual((status, ready["generation_submitted"]), (200, False))
        self.assertIn("a rooftop", ready["controls"]["positive"])
        status, refused = self.route("POST", "/api/looks", {"action": "edit", "id": created["id"], "name": "x"})
        self.assertEqual((status, refused["code"]), (428, "card_precondition_required"))
        for body in ([], "text", 3, None, True):
            with self.subTest(body=repr(body)):
                self.assertEqual(self.route("POST", "/api/looks", body)[0], 400)
                self.assertEqual(self.route("POST", "/api/looks/prepare", body)[0], 400)
        self.assertEqual((self.studio.jobs, self.requests), ({}, []))

    # ------------------------------------------------------------------ the shipped look
    def test_seeds_arrive_once_and_the_owner_keeps_the_last_word(self):
        (self.root / "presets/looks.json").write_text(json.dumps({"version": 1, "looks": [
            {"id": "look-seeded", "kind": "look", "name": "Seeded", "body": BODY, "lineage": []},
            {"id": "look-broken", "kind": "look", "name": "Broken", "body": dict(BODY, preset_id="gone"), "lineage": []}]}))
        first = looks.listing(self.studio)
        self.assertEqual([entry["id"] for entry in first["looks"]], ["look-seeded"])
        self.assertEqual(len(first["seed_errors"]), 1); self.assertIn("look-broken", first["seed_errors"][0])
        looks.command(self.studio, {"action": "trash", "id": "look-seeded", "expected_revision": 0})
        again = server.Studio(self.root)
        self.assertIsNotNone(looks.listing(again)["looks"][0]["trashed_at"], "a restart never resurrects a put-away seed")

    def test_the_shipped_night_shift_look_is_valid_against_the_real_catalog(self):
        shipped = json.loads((ROOT / "presets/looks.json").read_text(encoding="utf-8"))
        catalog = {p["id"]: p for p in json.loads((ROOT / "presets/catalog.json").read_text(encoding="utf-8"))["presets"]}
        night = next(entry for entry in shipped["looks"] if entry["id"] == "look-night-shift-retro-anime")
        body = looks.validate_body(night["body"], catalog[night["body"]["preset_id"]])
        looks.validate_lineage(night["lineage"])
        self.assertEqual(body["preset_id"], "zimage-fast")
        anchor = night["lineage"][0]
        self.assertEqual((anchor["role"], anchor["sha256"], anchor["prompt_id"]), ("anchor", "c22b723c65198b896ff9e542b05745742a447b62e91a7e5cfb8c0f593df7dfa9", "adfc94c4-0de0-44af-ae72-72b3133742f0"))
        # The recorded source prompt is the accepted anchor's exact wording, and every look sentence of the template is taken from it.
        plan = json.loads((ROOT / "experiments/curated/asset-kit-20260927/receipts/zimage-studio-plan.json").read_text(encoding="utf-8"))
        z2 = next(entry for entry in plan if entry["key"] == "retro-anime-master-z2")
        self.assertEqual((body["source_prompt"], body["controls"]["seed"]), (z2["controls"]["positive"], z2["controls"]["seed"]))
        for sentence in ("Hand-painted anime film background of", "muted graphite palette with small amber accents.",
                         "Fixed eye-level camera, calm and quiet, hand-painted cel anime film background art.", "No text, no signs, no logos, no characters, no people, no figures."):
            self.assertIn(sentence, body["template"]); self.assertIn(sentence, z2["controls"]["positive"])
        # Owner, 27 Sep 2026 ("a rain-soaked arcade entrance" came out as a shutter): the scene decides the layout. The quiet-wall
        # composition is an optional line, off by default; switched on, the wording is exactly what #1224 shipped.
        wall = next(option for option in body["options"] if option["id"] == "quiet_wall")
        self.assertEqual((wall["default"], wall["label"]), (False, "Keep the quiet wall for UI backgrounds"))
        for layout in ("graphite wall", "left half", "almost empty"):
            self.assertNotIn(layout, body["template"]); self.assertIn(layout, wall["text"])
        old = next(entry for entry in json.loads(V1.read_text(encoding="utf-8"))["looks"] if entry["id"] == NIGHT)
        scene = "a rain-soaked arcade entrance"
        self.assertEqual(looks.compose(body["template"], scene, body["options"], {"quiet_wall": True}), looks.compose(old["body"]["template"], scene))
        self.assertNotIn("wall", looks.compose(body["template"], scene, body["options"]))
        self.assertEqual((body["source_prompt"], night["lineage"][0]), (old["body"]["source_prompt"], old["lineage"][0]), "anchor and its exact prompt kept")
        self.assertIn("27 September 2026", body["notes"]); self.assertIn("shutter", body["notes"])
        self.assertTrue(any("shutter" in entry.get("evidence", "") for entry in night["lineage"]), "the lineage records why the wording changed")
        self.assertEqual((body["controls"]["width"], body["controls"]["height"]), (z2["controls"]["width"], z2["controls"]["height"]))
        self.assertIn(night["body"]["scene_example"].split(";")[0], "a narrow late-night apartment corridor")

    def test_a_workspace_holding_the_first_shipped_night_shift_takes_the_loosened_one_and_an_edited_copy_is_kept(self):
        """How an updated shipped look reaches an existing Workspace: #1224's Night Shift, never edited, becomes the loosened one;
        an owner who edited it keeps the edit (their version is theirs; the new wording is in presets/looks.json)."""
        shipped = json.loads((ROOT / "presets/looks.json").read_text(encoding="utf-8"))
        night = next(entry for entry in shipped["looks"] if entry["id"] == NIGHT)
        catalog = (ROOT / "presets/catalog.json").read_bytes()
        outcomes = {}
        for case in ("untouched", "edited"):
            root = Path(tempfile.mkdtemp(dir=self.tmp.name))
            for folder in ("presets", "config"): (root / folder).mkdir()
            (root / "presets/catalog.json").write_bytes(catalog); (root / "presets/looks.json").write_bytes(V1.read_bytes())
            (root / "config/local.json").write_bytes((self.root / "config/local.json").read_bytes())
            first = server.Studio(root); self.assertEqual([entry["revision"] for entry in looks.listing(first)["looks"]], [0])
            self.assertIn(first.assets.card_digest(first.assets.card(NIGHT)), night["supersedes"], "the update names the version #1224 seeded")
            if case == "edited": looks.command(first, {"action": "edit", "id": NIGHT, "expected_revision": 0, "name": "My Night Shift"})
            (root / "presets/looks.json").write_text(json.dumps(shipped), encoding="utf-8")
            outcomes[case] = looks.listing(server.Studio(root))["looks"][0]
            self.assertEqual(looks.listing(server.Studio(root))["looks"][0]["revision"], outcomes[case]["revision"], "a later start changes nothing")
        self.assertEqual((outcomes["untouched"]["revision"], outcomes["untouched"]["body"], outcomes["untouched"]["lineage"]), (1, night["body"], night["lineage"]))
        self.assertEqual((outcomes["edited"]["name"], outcomes["edited"]["revision"], "{quiet_wall}" in outcomes["edited"]["body"]["template"]), ("My Night Shift", 1, False))


if __name__ == "__main__":
    unittest.main()
