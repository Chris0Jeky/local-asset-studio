"""#1832: an owner's 'accept this picture for this slot' reuses asset_acceptances; replacing the candidate leaves it as history."""
import copy
import sqlite3
import unittest
from contextlib import closing
import test_scene_briefs as briefs
from test_server import server
import scene_briefs


class SlotAcceptance(unittest.TestCase):
    setUp = briefs.SceneBriefTests.setUp
    create = briefs.SceneBriefTests.create
    asset = briefs.SceneBriefTests.asset
    studio = briefs.SceneBriefTests.studio

    def brief(self, ref=None):
        body = copy.deepcopy(self.body); body['slots']['background']['selected'] = ref; body['slots']['background']['criteria'] = 'Readable at 64 px'
        return self.create(body)

    def ask(self, card, slot='background', revision=None): return {'id': card['id'], 'slot': slot, 'expected_revision': card['revision'] if revision is None else revision}

    def press(self, ref, card, store=None, **extra):
        payload = dict({'reviewer': 'local-user', 'sha256': ref['sha256'], 'brief': self.ask(card)}, **extra)
        return (store or self.store).accept(ref['asset_id'], payload)

    def rows(self): return scene_briefs.inspect(self.studio(), 'brief-one')['acceptances']

    def second_asset(self):
        path = self.store.root / 'second.png'; path.write_bytes(b'a different render')
        identifier = self.store.register({'id': 'job-2', 'created_at': 2, 'outputs': [{'filename': 'second.png', 'media_type': 'image'}]}, 0, path)
        with self.store.connection() as db: sha = db.execute('SELECT sha256 FROM assets WHERE id=?', (identifier,)).fetchone()['sha256']
        return {'asset_id': identifier, 'sha256': sha, 'metadata_revision': self.store.metadata(identifier, self.scope)['metadata_revision']}

    def test_candidate_is_not_accepted_until_the_explicit_press_and_the_receipt_names_everything(self):
        ref = self.asset(); card = self.brief(ref)
        self.assertEqual(self.rows()['background'], [])
        row = self.press(ref, card, note='Reads well')['acceptances'][0]
        self.assertEqual((row['brief_id'], row['slot'], row['sha256'], row['criteria'], row['note'], row['reviewer']), ('brief-one', 'background', ref['sha256'], 'Readable at 64 px', 'Reads well', 'local-user'))
        self.assertIn('Lantern Marsh', row['use'])
        shown = self.rows()['background'][0]
        self.assertTrue(shown['current']); self.assertEqual(shown['asset_id'], ref['asset_id'])
        self.assertEqual(self.store.get(ref['asset_id'])['review'], 'unreviewed')

    def test_agent_or_undeclared_press_records_nothing(self):
        ref = self.asset(); card = self.brief(ref)
        for who in (None, 'agent'):
            with self.subTest(who=who), self.assertRaises(server.WorkspaceError) as caught: self.press(ref, card, reviewer=who)
            self.assertEqual(caught.exception.code, 'acceptance_not_declared')
        self.assertEqual(self.rows()['background'], [])

    def test_replacing_the_candidate_keeps_the_old_acceptance_as_history_and_does_not_carry_it_over(self):
        first = self.asset(); card = self.brief(first); self.press(first, card)
        second = self.second_asset()
        body = copy.deepcopy(card['body']); body['slots']['background'].update(selected=second, previous=first)
        card = self.store.card_command({'action': 'edit', 'id': 'brief-one', 'expected_revision': card['revision'], 'body': body})
        old = self.rows()['background']
        self.assertEqual([(r['asset_id'], r['current'], r['withdrawn_at']) for r in old], [(first['asset_id'], False, None)])   # kept, but not the slot's accepted picture
        with self.assertRaises(server.WorkspaceError) as caught: self.press(first, card)   # the old picture is no longer the slot's candidate
        self.assertEqual(caught.exception.code, 'brief_source_stale')
        self.press(second, card)
        self.assertEqual(sorted((r['asset_id'] == second['asset_id'], r['current']) for r in self.rows()['background']), [(False, False), (True, True)])

    def test_stale_revision_wrong_slot_changed_snapshot_and_bad_shape_cannot_record(self):
        ref = self.asset(); card = self.brief(ref)
        for ask, code in ((self.ask(card, revision=card['revision'] + 1), 'card_revision_conflict'), (self.ask(card, slot='icon'), 'brief_source_stale')):
            with self.subTest(code=code), self.assertRaises(server.WorkspaceError) as caught: self.press(ref, card, brief=ask)
            self.assertEqual(caught.exception.code, code)
        with self.assertRaises(server.WorkspaceError): self.press(ref, card, brief={'id': 'brief-one', 'slot': 'background'})
        with self.store.connection() as db: db.execute('UPDATE assets SET metadata_revision=metadata_revision+1')
        with self.assertRaises(server.WorkspaceError) as caught: self.press(ref, card)
        self.assertEqual(caught.exception.code, 'brief_source_stale')
        self.assertEqual(self.rows()['background'], [])

    def test_repeat_press_is_unchanged_even_after_a_rename_and_accepting_again_after_withdraw_adds_a_row(self):
        ref = self.asset(); card = self.brief(ref); first = self.press(ref, card)
        card = self.store.card_command({'action': 'edit', 'id': 'brief-one', 'expected_revision': card['revision'], 'name': 'Renamed'})
        again = self.press(ref, card); self.assertTrue(again['unchanged']); self.assertEqual(len(again['acceptances']), 1)
        self.store.accept(ref['asset_id'], {'reviewer': 'local-user', 'sha256': ref['sha256'], 'action': 'withdraw', 'acceptance_id': first['acceptances'][0]['id']})
        self.assertFalse(self.rows()['background'][0]['current'])
        self.assertEqual(len(self.press(ref, card)['acceptances']), 2)

    def test_a_library_use_with_the_same_words_does_not_collide_and_an_old_table_migrates(self):
        ref = self.asset(); card = self.brief(ref)
        self.store.accept(ref['asset_id'], {'reviewer': 'local-user', 'sha256': ref['sha256'], 'use': 'background'})
        self.assertEqual(len(self.press(ref, card)['acceptances']), 2)
        with closing(sqlite3.connect(self.store.database)) as db:   # the table exactly as PR 1897 shipped it
            db.execute('DROP TABLE asset_acceptances')
            db.execute('CREATE TABLE asset_acceptances (id TEXT PRIMARY KEY, asset_id TEXT NOT NULL REFERENCES assets(id), sha256 TEXT NOT NULL, use TEXT NOT NULL, note TEXT NOT NULL DEFAULT "", reviewer TEXT NOT NULL, accepted_at REAL NOT NULL, withdrawn_at REAL)')
            db.execute("INSERT INTO asset_acceptances VALUES ('old',?,?,'Cover art','','local-user',1,NULL)", (ref['asset_id'], ref['sha256']))
            db.execute('CREATE UNIQUE INDEX asset_acceptances_live ON asset_acceptances(asset_id, use COLLATE NOCASE) WHERE withdrawn_at IS NULL'); db.commit()
        reopened = server.AssetWorkspace(self.store.root.parent)
        self.assertEqual([(r['id'], r['brief_id']) for r in reopened.acceptances(ref['asset_id'])['acceptances']], [('old', None)])
        self.assertEqual(len(self.press(ref, card, store=reopened)['acceptances']), 2)

    def test_identity_unavailable_is_a_503_not_a_changed_picture(self):
        ref = self.asset()
        with self.store.connection() as db: db.execute('DELETE FROM workspace_identity')
        with self.assertRaises(server.WorkspaceError) as caught: self.store.accept(ref['asset_id'], {'reviewer': 'local-user', 'sha256': ref['sha256'], 'use': 'Cover art', 'workspace_id': 'a' * 32})
        self.assertEqual((caught.exception.status, caught.exception.code), (503, 'asset_workspace_unavailable'))


if __name__ == '__main__': unittest.main()
