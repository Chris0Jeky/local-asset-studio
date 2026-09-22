"""Bounded read-only lifecycle projections over real disposable Workspace storage."""
import importlib
import json
import unittest
from urllib.parse import urlencode
import test_workspace as fixture


class RecoveryObservationTests(unittest.TestCase):
    setUp = fixture.WorkspaceTests.setUp
    tearDown = fixture.WorkspaceTests.tearDown

    def observe(self, ids=None, **kw):
        try:
            module = importlib.import_module('studio_workflow.asset_recovery_observation')
        except ModuleNotFoundError:
            self.fail('The scoped read-only recovery projection is not implemented')
        return module.observe(self.store, ids or [self.asset], self.store.snapshot()['workspace_id'], **kw)

    def command(self, ids=None, **fields):
        import uuid
        selected = ids or [self.asset]
        return dict(ids=selected, action='edit', workspace_id=self.store.snapshot()['workspace_id'],
                    expected_revisions={i:self.store.get(i)['metadata_revision'] for i in selected},
                    request_id=uuid.uuid4().hex, **fields)

    def test_active_trash_restored_and_missing_are_distinct_read_only_observations(self):
        self.assertEqual(self.observe()['targets'][0]['state'], 'active')
        trash = self.command(); trash['action'] = 'trash'; self.store.update(trash)
        self.assertEqual(self.observe()['targets'][0]['state'], 'trashed')
        restore = self.command(); restore['action'] = 'restore'; self.store.update(restore)
        restored = self.observe()['targets'][0]
        self.assertEqual((restored['state'], restored['metadata_revision']), ('active', 2))
        with self.store.connection() as db: db.execute('DELETE FROM assets WHERE id=?', (self.asset,))
        self.assertEqual(self.observe()['targets'][0], {'id': self.asset, 'state': 'missing'})
        self.assertEqual(self.store.command_status(trash['request_id'])['status'], 'applied')

    def test_every_target_is_returned_in_original_order_beyond_receipt_preview_limit(self):
        ids = [self.store.register(dict(self.job, id=f'recovery-{i}'), 0, self.source) for i in range(12)]
        with self.store.connection() as db: db.execute('DELETE FROM assets WHERE id=?', (ids[8],))
        value = self.observe(ids)
        self.assertEqual([r['id'] for r in value['targets']], ids)
        self.assertEqual(value['targets'][8]['state'], 'missing')
        self.assertEqual(value['targets'][11]['state'], 'active')

    def test_collection_existence_and_membership_do_not_replay_historical_receipts(self):
        col = self.store.collection({'name':'Synthetic group'})
        command = self.command(collection_id=col['id']); command['action'] = 'add_collection'
        receipt = self.store.update(command)
        value = self.observe(collection_id=col['id'])
        self.assertTrue(value['collection']['exists']); self.assertTrue(value['targets'][0]['in_collection'])
        self.store.collection({'id':col['id'], 'action':'delete'})
        value = self.observe(collection_id=col['id'])
        self.assertFalse(value['collection']['exists']); self.assertFalse(value['targets'][0]['in_collection'])
        self.assertEqual(self.store.command_status(command['request_id']), {k:v for k,v in receipt.items() if k != 'current'})

    def test_observations_do_not_expose_paths_notes_source_or_change_sqlite_rows(self):
        command=self.command(notes='Private owner notes'); self.store.update(command)
        before=self.store.snapshot()
        value=self.observe()
        self.assertEqual(self.store.snapshot(), before)
        raw=json.dumps(value)
        for denied in ['Private owner notes', str(self.source), '"source"', '"path"', '"url"']:
            self.assertNotIn(denied, raw)
        self.assertIs(value['generation_submitted'], False)

    def test_foreign_workspace_and_malformed_or_ambiguous_targets_fail_closed(self):
        module=importlib.import_module('studio_workflow.asset_recovery_observation')
        scope=self.store.snapshot()['workspace_id']
        for ids in [[], [self.asset]*2, [str(i) for i in range(201)], ['x'*129], [False]]:
            with self.subTest(ids=repr(ids)[:50]), self.assertRaises(ValueError): module.observe(self.store, ids, scope)
        for w in [None, '', 'f'*32]:
            with self.subTest(scope=w), self.assertRaises(ValueError) as raised:
                module.observe(self.store,[self.asset],w)
            self.assertNotIn(self.store.get(self.asset)['title'], str(raised.exception))

    def test_membership_summary_has_an_explicit_limit_and_complete_count(self):
        for i in range(24):
            col=self.store.collection({'name':f'Collection {i:02}'})
            command=self.command(collection_id=col['id']); command['action']='add_collection'; self.store.update(command)
        target=self.observe()['targets'][0]
        self.assertEqual(target['collection_count'], 24)
        self.assertEqual(len(target['collections']),20)
        self.assertTrue(target['collections_limited'])

    def test_http_query_requires_one_scope_and_exact_bounded_ids(self):
        module=importlib.import_module('studio_workflow.asset_recovery_http')
        query=urlencode({'workspace_id':self.store.snapshot()['workspace_id'],'ids':json.dumps([self.asset])})
        raw='/api/assets/recovery-observation?'+query
        self.assertEqual(module.read(raw,self.store)['targets'][0]['id'],self.asset)
        for bad in [raw+'&workspace_id=x', raw+'&unknown=x', raw+'#fragment', raw.replace('ids=', 'other='), '/api/assets/recovery-observation']:
            with self.subTest(route=bad), self.assertRaises(ValueError): module.read(bad,self.store)


    def test_wire_byte_budget_matches_the_http_ascii_json_encoder(self):
        from unittest.mock import patch
        from studio_workflow import asset_recovery_observation as module
        self.store.update(self.command(title='😀' * 200))
        with patch.object(module, 'MAX_RESPONSE_BYTES', 1500):
            with self.assertRaisesRegex(ValueError, 'observation exceeds'):
                self.observe()

    def test_invalid_stored_lifecycle_is_not_presented_as_a_known_state(self):
        for invalid in ['not-a-timestamp', float('inf'), -1]:
            with self.store.connection() as db:
                db.execute('UPDATE assets SET trashed_at=? WHERE id=?', (invalid, self.asset))
            with self.subTest(value=invalid), self.assertRaisesRegex(ValueError, 'lifecycle'):
                self.observe()

    def test_read_snapshot_does_not_mix_states_from_an_interleaved_writer(self):
        from unittest.mock import patch
        col=self.store.collection({'name':'Before concurrent change'})
        add=self.command(collection_id=col['id']);add['action']='add_collection';self.store.update(add)
        original_check=self.store._check_scope
        trash=self.command();trash['action']='trash'
        def interleave(db, expected):
            identity=original_check(db, expected)
            # Disable the hook while the independent writer checks its own scope.
            with patch.object(self.store, '_check_scope', original_check):
                self.store.update(trash)
                self.store.collection({'id':col['id'],'action':'delete'})
            return identity
        with patch.object(self.store, '_check_scope', interleave):
            old=self.observe(collection_id=col['id'])
        self.assertEqual(old['targets'][0]['state'], 'active')
        self.assertTrue(old['collection']['exists'])
        self.assertTrue(old['targets'][0]['in_collection'])
        new=self.observe(collection_id=col['id'])
        self.assertEqual(new['targets'][0]['state'], 'trashed')
        self.assertFalse(new['collection']['exists'])
        self.assertFalse(new['targets'][0]['in_collection'])

    def test_200_targets_are_complete_without_reading_or_repairing_originals(self):
        from unittest.mock import patch
        ids=[self.store.register(dict(self.job,id=f'bounded-{i}'),0,self.source) for i in range(200)]
        with patch.object(self.store, 'file', side_effect=AssertionError('no media access')):
            result=self.observe(ids)
        self.assertEqual([r['id'] for r in result['targets']], ids)
        self.assertLessEqual(len(json.dumps(result).encode()), 2*1024*1024)


class RecoveryObservationHTTP(unittest.TestCase):
    def setUp(self):
        import test_asset_metadata_http as fixture_http
        from studio_workflow.asset_recovery_http import extend_handler
        fixture_http.AssetMetadataHTTP.setUp(self)
        self.http.RequestHandlerClass=extend_handler(self.http.RequestHandlerClass)
        self.query='/api/assets/recovery-observation?'+urlencode({'workspace_id':self.store.snapshot()['workspace_id'],'ids':json.dumps([self.asset,'missing'])})

    def tearDown(self):
        import test_asset_metadata_http as fixture_http
        fixture_http.AssetMetadataHTTP.tearDown(self)

    def request(self,*args,**kwargs):
        import test_asset_metadata_http as fixture_http
        return fixture_http.AssetMetadataHTTP.request(self,*args,**kwargs)

    def test_actual_http_is_no_store_and_accounts_for_missing_without_writes(self):
        before=self.store.snapshot()
        status,data,headers=self.request('GET',self.query)
        self.assertEqual(status,200);self.assertEqual(headers['Cache-Control'],'no-store')
        self.assertEqual(data['targets'][1],{'id':'missing','state':'missing'})
        self.assertEqual(self.store.snapshot(),before)

    def test_host_gate_and_post_refusal_never_enter_metadata_writer(self):
        from http_refusal_transport import atomic_json_post
        status,_,_=self.request('GET',self.query,host='evil.test');self.assertEqual(status,403)
        status,_=atomic_json_post(self.http.server_port,'/api/assets/recovery-observation',b'{}',host='127.0.0.1:8191',origin='http://127.0.0.1:8191')
        self.assertEqual(status,405);self.assertEqual(self.store.get(self.asset)['metadata_revision'],0)

    def test_swapped_workspace_refuses_before_disclosing_same_id_metadata(self):
        import tempfile
        from test_server import server
        with tempfile.TemporaryDirectory() as root:
            replacement=server.AssetWorkspace(root)
            self.http.RequestHandlerClass.studio.assets=replacement
            try:
                status,data,_=self.request('GET',self.query)
                self.assertEqual(status,409);self.assertEqual(data['code'],'asset_workspace_conflict')
                for key in ['targets','collection','current']:self.assertNotIn(key,data)
            finally:self.http.RequestHandlerClass.studio.assets=self.store


if __name__=='__main__': unittest.main()
