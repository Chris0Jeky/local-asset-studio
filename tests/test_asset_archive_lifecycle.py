"""Archive lifecycle inspection remains bounded, scoped and read-only."""
import unittest
import test_asset_archive as fixtures
from studio_workflow.asset_recovery_observation import observe


class ArchiveLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.AssetArchiveTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.store=self.fixture.store;self.ids=self.fixture.ids;self.scope=self.fixture.scope

    def test_current_archive_state_is_not_mistaken_for_historical_receipt_or_trash(self):
        self.fixture.archive()
        value=observe(self.store,self.ids,self.scope)
        self.assertEqual(value['targets'][0].get('archived_at'),self.store.get(self.ids[0])['archived_at'])
        self.assertEqual(value['targets'][0]['state'],'active','The existing state field still describes Trash only')
        self.assertIsNone(value['targets'][1].get('archived_at'))
        self.fixture.apply('trash');value=observe(self.store,self.ids[:1],self.scope)
        self.assertEqual(value['targets'][0]['state'],'trashed');self.assertIsNotNone(value['targets'][0]['archived_at'])
        self.fixture.apply('unarchive');value=observe(self.store,self.ids[:1],self.scope)
        self.assertIsNone(value['targets'][0]['archived_at']);self.assertEqual(value['targets'][0]['state'],'trashed')

    def test_private_lifecycle_is_not_disclosed_by_archive_inspection(self):
        self.fixture.archive([self.fixture.private],privacy='private')
        before=self.store.snapshot(privacy='all')
        self.assertEqual(observe(self.store,[self.fixture.private],self.scope)['targets'],[{'id':self.fixture.private,'state':'missing'}])
        row=observe(self.store,[self.fixture.private],self.scope,privacy='private')['targets'][0]
        self.assertIsNotNone(row.get('archived_at'));self.assertEqual(self.store.snapshot(privacy='all'),before)

    def test_corrupt_archive_timestamp_refuses_whole_observation(self):
        self.fixture.archive()
        for value in ('broken',float('inf'),b'bad',-1):
            with self.subTest(value=value):
                with self.store.connection() as db:db.execute('UPDATE assets SET archived_at=? WHERE id=?',(value,self.ids[0]))
                with self.assertRaises(ValueError):observe(self.store,self.ids,self.scope)


if __name__=='__main__':unittest.main()
