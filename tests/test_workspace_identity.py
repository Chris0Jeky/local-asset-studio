"""Workspace identity is stable without exposing paths or changing asset metadata."""
import tempfile
import unittest
from test_workspace import workspace
AssetWorkspace = workspace.AssetWorkspace

class WorkspaceIdentityTests(unittest.TestCase):
    def test_identity_survives_restart_and_distinguishes_databases(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            a=AssetWorkspace(first); identity=a.snapshot().get('workspace_id')
            self.assertIsInstance(identity, str)
            self.assertRegex(identity, r'^[0-9a-f]{32}$')
            self.assertEqual(identity, AssetWorkspace(first).snapshot()['workspace_id'])
            self.assertNotEqual(identity, AssetWorkspace(second).snapshot()['workspace_id'])
            self.assertEqual(a.snapshot()['assets'], [])

    def test_scoped_command_refuses_another_database_with_the_same_asset_id(self):
        from pathlib import Path
        with tempfile.TemporaryDirectory() as root:
            source=Path(root)/'input.png';source.write_bytes(b'fixture-original')
            a,b=AssetWorkspace(Path(root)/'a'),AssetWorkspace(Path(root)/'b')
            job={'id':'same-job-id','outputs':[{'filename':'input.png','media_type':'image'}]}
            identifier=a.register(job,0,source)
            self.assertEqual(identifier,b.register(job,0,source))
            command={'ids':[identifier],'action':'edit','notes':'Only workspace A',
                     'expected_revisions':{identifier:0},'request_id':'a'*32,'workspace_id':a.snapshot()['workspace_id']}
            with self.assertRaises(workspace.WorkspaceError) as error:b.update(command)
            self.assertEqual(error.exception.code,'asset_workspace_conflict')
            self.assertEqual(b.get(identifier)['notes'],'')
            result=a.update(command)
            self.assertEqual(result,a.update(command))
            self.assertEqual(a.get(identifier)['metadata_revision'],1)

    def test_concurrent_existing_database_migration_shares_one_identity(self):
        from concurrent.futures import ThreadPoolExecutor
        with tempfile.TemporaryDirectory() as root:
            # WAL initialization has an independent pre-existing fresh-database race;
            # this test exercises concurrent identity migration on an existing store.
            store=AssetWorkspace(root)
            with store.connection() as db:db.execute("DELETE FROM workspace_identity")
            with ThreadPoolExecutor(max_workers=4) as pool:
                identities=list(pool.map(lambda _:AssetWorkspace(root).snapshot()['workspace_id'],range(8)))
            self.assertEqual(len(set(identities)),1)
