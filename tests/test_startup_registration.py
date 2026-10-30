"""Restart re-registration (#1761): known outputs are found with one query, not one connection each; everything else is unchanged."""
import sqlite3
import unittest
from contextlib import contextmanager
from unittest.mock import patch

import test_looks as fixture
from workspace import AssetWorkspace

server = fixture.server


class StartupRegistrationTests(unittest.TestCase):
    setUp = fixture.LookTests.setUp

    def seed(self, count, start=0):
        """Completed jobs with one registered output each, saved so that a new Studio reloads them."""
        jobs = []
        for number in range(start, start + count):
            job = self.studio.create_job({'preset_id': self.studio.catalog()['presets'][0]['id'], 'controls': {}}, enqueue=False)
            stored = self.studio.jobs[job['id']]; stored['status'] = 'completed'
            path = self.root / f'fake-comfy/output/result-{number}.png'; path.parent.mkdir(exist_ok=True); path.write_bytes(b'bytes %d' % number)
            stored['outputs'] = [{'filename': path.name, 'subfolder': '', 'type': 'output', 'media_type': 'image'}]
            self.studio.index_outputs(stored, advise=False); self.studio._save(stored); jobs.append(stored)
        return jobs

    def restart(self):
        """A new Studio on the same root, with the counts of workspace connections, registrations and media copies it made."""
        calls = {'connection': 0, 'register': 0, 'snapshot': 0}
        connection, register, snapshot = AssetWorkspace.connection, AssetWorkspace.register, AssetWorkspace.snapshot_file
        @contextmanager
        def counted_connection(store):
            calls['connection'] += 1
            with connection(store) as db: yield db
        def counted(name, original):
            def wrapper(*args, **kwargs): calls[name] += 1; return original(*args, **kwargs)
            return wrapper
        with patch.object(AssetWorkspace, 'connection', counted_connection), patch.object(AssetWorkspace, 'register', counted('register', register)), \
                patch.object(AssetWorkspace, 'snapshot_file', counted('snapshot', snapshot)):
            self.studio = server.Studio(self.root)
        self.studio._request = lambda *a, **k: {}
        return calls

    def ids(self):
        return {job_id: [o.get('asset_id') for o in job['outputs']] for job_id, job in self.studio.jobs.items()}

    def test_restart_connections_do_not_grow_with_the_outputs_and_copy_nothing(self):
        self.seed(4); small = self.restart()
        self.seed(12, start=4); large = self.restart()
        self.assertEqual(large['connection'], small['connection'], 'the restart opens the same few connections whatever the number of outputs')
        self.assertLess(large['connection'], 16)
        self.assertEqual((large['register'], large['snapshot']), (0, 0), 'known outputs are neither looked up one by one nor copied again')

    def test_ids_match_the_unbatched_path(self):
        self.seed(6); self.restart(); batched = self.ids()
        self.assertEqual(len(batched), 6); self.assertTrue(all(ids and all(ids) for ids in batched.values()))
        for job in self.studio.jobs.values():
            for output in job['outputs']: output.pop('asset_id')
            self.studio.index_outputs(job, advise=False)   # no prefetch: every output goes through register()
        self.assertEqual(self.ids(), batched)

    def test_a_missing_registration_is_still_registered(self):
        jobs = self.seed(3); lost = jobs[1]; lost_id = lost['outputs'][0]['asset_id']
        with self.studio.assets.connection() as db: db.execute('DELETE FROM assets WHERE id=?', (lost_id,))
        calls = self.restart()
        self.assertEqual((calls['register'], calls['snapshot']), (1, 1), 'only the lost output is registered, and copied once')
        self.assertEqual(self.studio.jobs[lost['id']]['outputs'][0]['asset_id'], lost_id)
        self.assertIn(lost_id, self.studio.assets.registered_ids())

    def test_a_privacy_mismatch_still_meets_the_conflict_check(self):
        jobs = self.seed(3); other = jobs[2]['outputs'][0]['asset_id']
        with self.studio.assets.connection() as db:
            try: db.execute("UPDATE assets SET privacy='private' WHERE id=?", (other,))
            except sqlite3.Error as exc: self.skipTest(f'privacy is immutable in the store: {exc}')
        calls = self.restart()
        self.assertEqual(calls['register'], 1, 'only the differently classified output is handed to register()')
        self.assertIn('different privacy', self.studio.jobs[jobs[2]['id']]['outputs'][0]['snapshot_error'])
        self.assertNotIn('snapshot_error', self.studio.jobs[jobs[0]['id']]['outputs'][0])


if __name__ == '__main__':
    unittest.main()
