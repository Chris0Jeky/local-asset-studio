"""Every POSIX snapshot publication owns its directory durability barrier."""
import hashlib
import importlib.util
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('workspace_reuse', Path(__file__).parents[1]/'app/workspace.py')
workspace = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(workspace)


@unittest.skipIf(os.name == 'nt', 'POSIX directory barrier only')
class SnapshotReuseBarrierTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.store = workspace.AssetWorkspace(self.root)
        self.source = self.root/'source.png'
        self.source.write_bytes(b'unchanged original output')
        digest = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.destination = self.store.media/(digest+'.png')
        self.job = {'id': 'reuse-job', 'preset_name': 'P', 'outputs': [{'filename': 'source.png', 'media_type': 'image'}]}

    def assert_no_row(self):
        with self.store.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM assets').fetchone()[0], 0)
        self.assertEqual(self.source.read_bytes(), b'unchanged original output')
        self.assertEqual(list(self.store.media.glob('*.part')), [])

    def fail_directory_sync(self):
        original = os.fsync
        def sync(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                raise OSError('injected directory durability failure')
            return original(fd)
        return patch.object(workspace.os, 'fsync', side_effect=sync)

    def test_existing_verified_snapshot_still_needs_its_own_barrier(self):
        self.store.snapshot_file(self.source)
        with self.fail_directory_sync(), self.assertRaisesRegex(OSError, 'directory durability'):
            self.store.register(self.job, 0, self.source)
        self.assert_no_row()
        self.assertEqual(self.destination.read_bytes(), self.source.read_bytes())

    def test_collision_loser_cannot_return_before_its_own_barrier(self):
        real_link = os.link
        def competing_link(temporary, destination):
            real_link(temporary, destination)
            raise FileExistsError('another publisher won')
        with patch.object(workspace.os, 'link', side_effect=competing_link), self.fail_directory_sync():
            with self.assertRaisesRegex(OSError, 'directory durability'):
                self.store.register(self.job, 0, self.source)
        self.assert_no_row()
        self.assertEqual(self.destination.read_bytes(), self.source.read_bytes())

    def test_retry_after_failed_new_link_cannot_skip_the_failed_barrier(self):
        with self.fail_directory_sync():
            for attempt in range(2):
                with self.subTest(attempt=attempt), self.assertRaisesRegex(OSError, 'directory durability'):
                    self.store.register(self.job, 0, self.source)
                self.assert_no_row()
        asset_id = self.store.register(self.job, 0, self.source)
        self.assertEqual(self.store.get(asset_id)['sha256'], hashlib.sha256(self.source.read_bytes()).hexdigest())
        with self.store.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM assets').fetchone()[0], 1)
        self.assertEqual(len(list(self.store.media.iterdir())), 1)

    def test_corrupt_existing_content_is_refused_before_directory_sync(self):
        self.destination.write_bytes(b'corrupted')
        original = os.fsync
        directories = []
        def sync(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode): directories.append(fd)
            return original(fd)
        with patch.object(workspace.os, 'fsync', side_effect=sync):
            with self.assertRaisesRegex(workspace.WorkspaceError, 'has changed'):
                self.store.register(self.job, 0, self.source)
        self.assertEqual(directories, [])
        self.assert_no_row()
        self.assertEqual(self.destination.read_bytes(), b'corrupted')


if __name__ == '__main__':
    unittest.main()
