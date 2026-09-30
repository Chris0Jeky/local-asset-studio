"""A refused durability barrier must not publish a successful asset row."""
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_workspace_snapshot_durability import workspace


class SnapshotFsyncFailureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = workspace.AssetWorkspace(self.root)
        self.source = self.root / "render.png"
        self.original = b"original rendered bytes"
        self.source.write_bytes(self.original)
        self.job = {"id": "sync-failure", "preset_name": "P", "outputs": [
            {"filename": "render.png", "media_type": "image"}]}

    def assert_no_registration(self):
        with self.store.connection() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM assets").fetchone()[0], 0)
        self.assertEqual(self.source.read_bytes(), self.original)
        self.assertEqual(list(self.store.media.glob("*.part")), [])

    def test_content_sync_failure_keeps_source_and_does_not_link_or_register(self):
        with patch.object(workspace.os, "fsync", side_effect=OSError("content sync failed")), \
                patch.object(workspace.os, "link") as link:
            with self.assertRaisesRegex(OSError, "content sync failed"):
                self.store.register(self.job, 0, self.source)
        link.assert_not_called()
        self.assert_no_registration()
        self.assertEqual(list(self.store.media.iterdir()), [])

    @unittest.skipIf(os.name == "nt", "POSIX directory barrier only")
    def test_directory_sync_failure_keeps_link_but_not_row_and_closes_descriptor(self):
        directory_fds = []
        real_fsync = os.fsync

        def fail_directory(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                directory_fds.append(fd)
                raise OSError("directory sync failed")
            return real_fsync(fd)

        with patch.object(workspace.os, "fsync", side_effect=fail_directory):
            with self.assertRaisesRegex(OSError, "directory sync failed"):
                self.store.register(self.job, 0, self.source)
        self.assert_no_registration()
        self.assertEqual(len(directory_fds), 1)
        with self.assertRaises(OSError):
            os.fstat(directory_fds[0])
        snapshots = list(self.store.media.glob("*.png"))
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].read_bytes(), self.original)


if __name__ == "__main__":
    unittest.main()
