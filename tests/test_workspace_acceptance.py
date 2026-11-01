"""#1832: 'I accept this picture for <use>' is its own owner record: never inferred, per use, withdrawable and reversible."""
import sqlite3
from contextlib import closing
import tempfile
import unittest
import uuid
from pathlib import Path
import test_asset_metadata_http as metadata_http
from test_workspace import workspace

OWNER = {'reviewer': 'local-user'}


class AcceptanceStore(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.store = workspace.AssetWorkspace(self.root)
        source = self.root/'render.png'; source.write_bytes(b'rendered bytes')
        self.asset = self.store.register({'id': 'job-1', 'preset_name': 'Study', 'outputs': [{'filename': 'render.png', 'media_type': 'image'}]}, 0, source)

    def tearDown(self): self.temp.cleanup()

    def accept(self, use='Game sprite', **extra): return self.store.accept(self.asset, dict(OWNER, use=use, **extra))

    def act(self, action, identifier): return self.store.accept(self.asset, dict(OWNER, action=action, acceptance_id=identifier))['acceptances'][0]

    def test_review_and_favourite_never_imply_acceptance(self):
        self.store.update({'request_id': uuid.uuid4().hex, 'ids': [self.asset], 'action': 'edit', 'review': 'selected', 'favorite': True,
                           'expected_revisions': {self.asset: 0}})
        self.assertEqual(self.store.get(self.asset)['review'], 'selected')
        self.assertEqual(self.store.acceptances(self.asset)['acceptances'], [])

    def test_only_an_explicit_local_user_declaration_records_one(self):
        for who in (None, 'agent', 'Local-User', 7):
            with self.subTest(who=who), self.assertRaises(workspace.WorkspaceError) as caught: self.store.accept(self.asset, {'reviewer': who, 'use': 'Game sprite'})
            self.assertEqual(caught.exception.code, 'acceptance_not_declared')
        with self.assertRaises(workspace.WorkspaceError): self.store.accept(self.asset, {'use': 'Game sprite'})
        self.assertEqual(self.store.acceptances(self.asset)['acceptances'], [])

    def test_a_picture_can_be_accepted_for_several_uses_and_each_names_its_bytes(self):
        self.accept('Game sprite', note='Idle frame'); data = self.accept('  Cover   art ')
        self.assertEqual(sorted(r['use'] for r in data['acceptances']), ['Cover art', 'Game sprite'])
        self.assertTrue(all(r['sha256'] == self.store.get(self.asset)['sha256'] and r['reviewer_kind'] == 'human' and r['withdrawn_at'] is None for r in data['acceptances']))
        self.assertIn('independent of Keep', data['scope'])

    def test_a_repeat_press_for_the_same_use_is_one_record_and_a_bad_use_is_refused(self):
        self.accept('Game sprite')
        self.assertEqual(len(self.accept('game SPRITE')['acceptances']), 1)
        for use in ('', '   ', None, 'x' * 81):
            with self.subTest(use=use), self.assertRaises(workspace.WorkspaceError): self.accept(use)

    def test_withdraw_keeps_the_record_and_restore_reverses_it(self):
        identifier = self.accept()['acceptances'][0]['id']
        first = self.act('withdraw', identifier)['withdrawn_at']; self.assertIsNotNone(first)
        self.assertEqual(self.act('withdraw', identifier)['withdrawn_at'], first)
        restored = self.act('restore', identifier)
        self.assertIsNone(restored['withdrawn_at']); self.assertEqual(restored['id'], identifier)

    def test_restore_cannot_duplicate_a_live_use_and_a_withdrawn_use_can_be_accepted_anew(self):
        old = self.accept()['acceptances'][0]['id']; self.act('withdraw', old)
        self.assertEqual(len(self.accept()['acceptances']), 2)
        with self.assertRaises(workspace.WorkspaceError) as caught: self.act('restore', old)
        self.assertEqual(caught.exception.status, 409)

    def test_withdraw_needs_a_known_id_and_a_trashed_picture_cannot_gain_acceptances(self):
        with self.assertRaises(workspace.WorkspaceError) as caught: self.act('withdraw', 'nope')
        self.assertEqual(caught.exception.status, 404)
        identifier = self.accept()['acceptances'][0]['id']
        self.store.update({'request_id': uuid.uuid4().hex, 'ids': [self.asset], 'action': 'trash', 'expected_revisions': {self.asset: 0}})
        with self.assertRaisesRegex(workspace.WorkspaceError, 'Trash'): self.accept('Cover art')
        self.assertIsNotNone(self.act('withdraw', identifier)['withdrawn_at'])

    def test_acceptance_leaves_the_asset_row_alone_and_survives_reopening(self):
        before = self.store.get(self.asset); self.accept()
        self.assertEqual(self.store.get(self.asset), before)
        self.assertEqual(len(workspace.AssetWorkspace(self.root).acceptances(self.asset)['acceptances']), 1)

    def test_migration_is_additive_on_an_existing_database(self):
        with closing(sqlite3.connect(self.store.database)) as db: db.execute('DROP TABLE asset_acceptances')
        reopened = workspace.AssetWorkspace(self.root)
        self.assertEqual(reopened.acceptances(self.asset)['acceptances'], [])
        self.assertEqual(reopened.get(self.asset)['id'], self.asset)


class AcceptanceHTTP(unittest.TestCase):
    setUp = metadata_http.AssetMetadataHTTP.setUp
    tearDown = metadata_http.AssetMetadataHTTP.tearDown
    request = metadata_http.AssetMetadataHTTP.request

    def test_route_reads_records_and_refuses_an_undeclared_press(self):
        route = '/api/assets/' + self.asset + '/acceptances'
        status, data, _ = self.request('GET', route); self.assertEqual((status, data['acceptances']), (200, []))
        status, data, _ = self.request('POST', route, {'use': 'Game sprite'}); self.assertEqual((status, data['code']), (400, 'acceptance_not_declared'))
        status, data, _ = self.request('POST', route, {'reviewer': 'local-user', 'use': 'Game sprite'})
        self.assertEqual(status, 200); self.assertEqual(data['acceptances'][0]['use'], 'Game sprite')
        status, data, _ = self.request('GET', route); self.assertEqual(len(data['acceptances']), 1)
        status, _, _ = self.request('GET', '/api/assets/missing/acceptances'); self.assertEqual(status, 400)


if __name__ == '__main__': unittest.main()
