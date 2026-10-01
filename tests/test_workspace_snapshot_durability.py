import importlib.util, os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
SPEC = importlib.util.spec_from_file_location('asset_workspace_durability', Path(__file__).parents[1] / 'app/workspace.py')
workspace = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(workspace)


class SnapshotDurabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.store = workspace.AssetWorkspace(self.root)
        self.source = self.root / 'render.png'; self.source.write_bytes(b'original rendered bytes')

    def tearDown(self):
        self.temp.cleanup()

    def test_content_is_synced_before_the_snapshot_is_linked(self):
        events = []
        real_fsync = os.fsync; real_link = os.link
        def recording_fsync(fd):
            events.append('fsync'); return real_fsync(fd)
        def recording_link(a, b, *args, **kwargs):
            events.append('link'); return real_link(a, b, *args, **kwargs)
        with patch('os.fsync', recording_fsync), patch('os.link', recording_link):
            rel, digest, size = self.store.snapshot_file(self.source)
        self.assertIn('fsync', events); self.assertIn('link', events)
        self.assertLess(events.index('fsync'), events.index('link'))
        self.assertEqual((self.store.root / rel).read_bytes(), self.source.read_bytes())

    def test_register_commits_only_after_content_sync(self):
        events = []
        real_fsync = os.fsync; real_link = os.link
        real_connection = workspace.AssetWorkspace.connection
        def recording_fsync(fd):
            events.append('fsync'); return real_fsync(fd)
        def recording_link(a, b, *args, **kwargs):
            events.append('link'); return real_link(a, b, *args, **kwargs)
        def recording_connection(store_self):
            events.append('db'); return real_connection(store_self)
        with patch('os.fsync', recording_fsync), patch('os.link', recording_link), patch.object(workspace.AssetWorkspace, 'connection', recording_connection):
            self.store.register({'id': 'J', 'preset_name': 'P', 'outputs': [{'filename': 'render.png', 'media_type': 'image'}]}, 0, self.source)
        self.assertIn('fsync', events); self.assertIn('link', events); self.assertIn('db', events)
        self.assertLess(events.index('fsync'), events.index('link'))
        last_db = max(i for i, e in enumerate(events) if e == 'db')
        self.assertLess(events.index('link'), last_db)

    def test_empty_source_still_refused_without_leftovers(self):
        empty = self.root / 'empty.png'; empty.write_bytes(b'')
        with self.assertRaisesRegex(workspace.WorkspaceError, 'The output file is empty'):
            self.store.snapshot_file(empty)
        self.assertEqual(list(self.store.media.glob('*.part')), [])

    @unittest.skipIf(os.name == 'nt', 'POSIX directory barrier only')
    def test_posix_directory_barrier_runs_after_a_new_link(self):
        events = []
        real_fsync = os.fsync; real_link = os.link
        def recording_fsync(fd):
            events.append('fsync'); return real_fsync(fd)
        def recording_link(a, b, *args, **kwargs):
            events.append('link'); return real_link(a, b, *args, **kwargs)
        with patch('os.fsync', recording_fsync), patch('os.link', recording_link):
            self.store.snapshot_file(self.source)
        self.assertIn('fsync', events); self.assertIn('link', events)
        first_link = events.index('link')
        self.assertTrue(any(e == 'fsync' for e in events[first_link + 1:]))
