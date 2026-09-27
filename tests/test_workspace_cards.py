"""Workspace cards (#1221, #1205): named, revisioned records that are not assets. A look is the first kind; the table is
kind-general so a character card needs no migration. Storage only: look rules live in app/looks.py (tests/test_looks.py)."""
import importlib.util
import json
import sqlite3
import tempfile
from contextlib import closing
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location('asset_workspace', Path(__file__).parents[1] / 'app/workspace.py')
workspace = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(workspace)

BODY = {'preset_id': 'zimage-fast', 'template': 'Hand-painted background of {scene}.', 'negative': '', 'controls': {'seed': 7}}
ANCHOR = [{'role': 'anchor', 'sha256': 'c' * 64, 'job_id': 'job-1'}]


class WorkspaceCardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.store = workspace.AssetWorkspace(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def create(self, **overrides):
        payload = {'action': 'create', 'kind': 'look', 'name': 'Night Shift', 'body': BODY, 'lineage': ANCHOR, **overrides}
        return self.store.card_command(payload)

    def test_create_lists_and_reads_back_one_revisioned_card(self):
        card = self.create()
        self.assertRegex(card['id'], r'^[0-9a-f]{32}$')
        self.assertEqual((card['kind'], card['name'], card['revision'], card['origin'], card['trashed_at']), ('look', 'Night Shift', 0, 'owner', None))
        self.assertEqual((card['body'], card['lineage']), (BODY, ANCHOR))
        self.assertEqual(self.store.cards('look'), [card])
        self.assertEqual(self.store.card(card['id']), card)
        self.assertEqual(self.store.cards('character'), [], 'kinds are separate lists')

    def test_cards_survive_a_new_workspace_object_on_the_same_folder(self):
        card = self.create()
        self.assertEqual(workspace.AssetWorkspace(self.root).card(card['id']), card)

    def test_an_existing_workspace_gains_the_table_without_touching_assets(self):
        # A Workspace made before cards existed: drop the table, reopen, and the assets are untouched.
        source = self.root / 'a.png'; source.write_bytes(b'bytes')
        asset = self.store.register({'id': 'job-9', 'preset_name': 'Old', 'outputs': [{'filename': 'a.png'}]}, 0, source)
        with closing(sqlite3.connect(self.store.database)) as db, db: db.execute('DROP TABLE cards')
        reopened = workspace.AssetWorkspace(self.root)
        self.assertEqual(reopened.cards('look'), [])
        self.assertEqual(reopened.get(asset)['title'], 'Old · 1')

    def test_a_client_id_makes_create_idempotent_and_refuses_different_content(self):
        first = self.create(id='night-shift-retro-anime')
        self.assertEqual(self.create(id='night-shift-retro-anime'), first)
        with self.assertRaises(workspace.WorkspaceError) as caught: self.create(id='night-shift-retro-anime', name='Another')
        self.assertEqual((caught.exception.status, caught.exception.code), (409, 'card_id_taken'))
        self.assertEqual(self.store.card('night-shift-retro-anime')['name'], 'Night Shift')

    def test_edit_needs_the_current_revision_and_a_stale_one_changes_nothing(self):
        card = self.create()
        with self.assertRaises(workspace.WorkspaceError) as caught:
            self.store.card_command({'action': 'edit', 'id': card['id'], 'name': 'Renamed'})
        self.assertEqual(caught.exception.status, 428)
        edited = self.store.card_command({'action': 'edit', 'id': card['id'], 'expected_revision': 0, 'name': 'Renamed', 'body': dict(BODY, negative='blur')})
        self.assertEqual((edited['name'], edited['revision'], edited['body']['negative']), ('Renamed', 1, 'blur'))
        self.assertGreaterEqual(edited['updated_at'], card['updated_at'])
        with self.assertRaises(workspace.WorkspaceError) as caught:
            self.store.card_command({'action': 'edit', 'id': card['id'], 'expected_revision': 0, 'name': 'Lost update'})
        self.assertEqual((caught.exception.status, caught.exception.code), (409, 'card_revision_conflict'))
        self.assertEqual(caught.exception.details['current']['name'], 'Renamed')
        self.assertEqual(self.store.card(card['id'])['revision'], 1)

    def test_trash_is_reversible_and_revisioned(self):
        card = self.create()
        trashed = self.store.card_command({'action': 'trash', 'id': card['id'], 'expected_revision': 0})
        self.assertIsNotNone(trashed['trashed_at']); self.assertEqual(trashed['revision'], 1)
        self.assertEqual([c['id'] for c in self.store.cards('look')], [card['id']], 'the list keeps put-away cards; the page groups them')
        restored = self.store.card_command({'action': 'restore', 'id': card['id'], 'expected_revision': 1})
        self.assertEqual((restored['trashed_at'], restored['revision'], restored['body']), (None, 2, BODY))

    def test_malformed_commands_change_nothing(self):
        cases = ([], 'x', {'action': 'create', 'kind': 'poster', 'name': 'x', 'body': {}},
                 {'action': 'create', 'kind': 'look', 'name': '', 'body': {}},
                 {'action': 'create', 'kind': 'look', 'name': 'x' * 121, 'body': {}},
                 {'action': 'create', 'kind': 'look', 'name': 'x', 'body': []},
                 {'action': 'create', 'kind': 'look', 'name': 'x', 'body': {'n': float('nan')}},
                 {'action': 'create', 'kind': 'look', 'name': 'x', 'body': {'t': 'x' * 70000}},
                 {'action': 'create', 'kind': 'look', 'name': 'x', 'body': {}, 'lineage': {}},
                 {'action': 'create', 'kind': 'look', 'name': 'x', 'body': {}, 'lineage': [1]},
                 {'action': 'create', 'kind': 'look', 'name': 'x', 'body': {}, 'lineage': [{}] * 21},
                 {'action': 'create', 'kind': 'look', 'name': 'x', 'body': {}, 'id': 'bad id!'},
                 {'action': 'create', 'kind': 'look', 'name': 'x', 'body': {}, 'surprise': 1},
                 {'action': 'edit', 'id': 'missing', 'expected_revision': 0, 'name': 'x'},
                 {'action': 'edit', 'id': 'missing', 'expected_revision': True, 'name': 'x'},
                 {'action': 'explode', 'id': 'x'})
        for payload in cases:
            with self.subTest(payload=repr(payload)[:80]):
                with self.assertRaises(workspace.WorkspaceError): self.store.card_command(payload)
        self.assertEqual(self.store.cards('look'), [])

    def test_an_edit_without_changes_is_refused(self):
        card = self.create()
        with self.assertRaises(workspace.WorkspaceError):
            self.store.card_command({'action': 'edit', 'id': card['id'], 'expected_revision': 0})

    def test_seeds_insert_once_and_never_overwrite_the_owners_edits_or_trash(self):
        seed = dict(id='look-night-shift', kind='look', name='Night Shift', body=BODY, lineage=ANCHOR)
        self.assertEqual(self.store.seed_cards([seed]), ['look-night-shift'])
        card = self.store.card('look-night-shift'); self.assertEqual((card['origin'], card['revision']), ('seed', 0))
        self.store.card_command({'action': 'edit', 'id': card['id'], 'expected_revision': 0, 'name': 'My Night Shift'})
        self.store.card_command({'action': 'trash', 'id': card['id'], 'expected_revision': 1})
        self.assertEqual(self.store.seed_cards([dict(seed, name='Changed upstream')]), [])
        again = self.store.card('look-night-shift')
        self.assertEqual((again['name'], again['revision']), ('My Night Shift', 2)); self.assertIsNotNone(again['trashed_at'])

    def test_stored_json_is_the_exact_body(self):
        card = self.create()
        with closing(sqlite3.connect(self.store.database)) as db:
            raw = db.execute('SELECT body,lineage FROM cards WHERE id=?', (card['id'],)).fetchone()
        self.assertEqual((json.loads(raw[0]), json.loads(raw[1])), (BODY, ANCHOR))

    def test_asset_by_sha256_finds_a_live_asset_only(self):
        source = self.root / 'a.png'; source.write_bytes(b'anchor bytes')
        asset = self.store.register({'id': 'job-2', 'preset_name': 'Anchor', 'outputs': [{'filename': 'a.png'}]}, 0, source)
        digest = self.store.get(asset)['sha256']
        self.assertEqual(self.store.asset_by_sha256(digest)['id'], asset)
        self.assertIsNone(self.store.asset_by_sha256('0' * 64))
        self.assertIsNone(self.store.asset_by_sha256('not-a-digest'))
        self.store.update({'ids': [asset], 'action': 'trash', 'request_id': 'r' * 32, 'expected_revisions': {asset: 0}})
        self.assertIsNone(self.store.asset_by_sha256(digest))


if __name__ == '__main__':
    unittest.main()
