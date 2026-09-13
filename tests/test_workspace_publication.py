"""Real filesystem races at the immutable media publication boundary."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import errno
import hashlib
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from test_workspace import workspace


class WorkspacePublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.store = workspace.AssetWorkspace(self.root)
        self.source = self.root / 'image.png'
        self.content = b'original output bytes' * 300
        self.source.write_bytes(self.content)
        self.digest = hashlib.sha256(self.content).hexdigest()
        self.destination = self.store.media / (self.digest + '.png')

    @contextmanager
    def racing_publication(self, competitor):
        """Run a competing writer immediately before the real publication syscall.

        Both the original replace and corrected link boundary are instrumented;
        the attempted operation itself is real, never a simulated success/error.
        """
        replace, link = Path.replace, os.link
        calls = []
        def before(target):
            if Path(target) == self.destination:
                calls.append(True)
                competitor()
        def replacing(source, target):
            before(target)
            return replace(source, target)
        def linking(source, target, *args, **kwargs):
            before(target)
            return link(source, target, *args, **kwargs)
        with patch.object(Path, 'replace', replacing), patch('os.link', linking):
            yield
        self.assertEqual(calls, [True], 'The real competing writer must have run exactly once')

    def assert_source_and_temporaries(self):
        self.assertEqual(self.source.read_bytes(), self.content)
        self.assertEqual(list(self.store.media.glob('*.part')), [])

    def test_competing_different_bytes_are_never_overwritten_or_registered(self):
        different = b'prior evidence that must survive'
        job = {'id': 'race-job', 'outputs': [{'filename': 'image.png'}]}
        caught = None
        with self.racing_publication(lambda: self.destination.write_bytes(different)):
            try: self.store.register(job, 0, self.source)
            except workspace.WorkspaceError as exc: caught = exc
        self.assertEqual(self.destination.read_bytes(), different)
        self.assertIsInstance(caught, workspace.WorkspaceError)
        self.assertEqual(self.store.snapshot()['assets'], [])
        self.assert_source_and_temporaries()

    def test_competing_identical_snapshot_is_reused_without_replacement(self):
        identity = []
        def competitor():
            self.destination.write_bytes(self.content)
            identity.append(self.destination.stat().st_ino)
        with self.racing_publication(competitor):
            result = self.store.snapshot_file(self.source)
        self.assertEqual(self.destination.stat().st_ino, identity[0])
        self.assertEqual(result, (str(Path('media') / self.destination.name), self.digest, len(self.content)))
        self.assert_source_and_temporaries()

    def test_snapshot_never_aliases_the_mutable_source(self):
        self.store.snapshot_file(self.source)
        self.source.write_bytes(b'later Comfy output')
        self.assertEqual(self.destination.read_bytes(), self.content)

    def test_existing_identical_snapshot_is_reused_and_corruption_is_retained(self):
        self.store.snapshot_file(self.source)
        identity = self.destination.stat().st_ino
        self.store.snapshot_file(self.source)
        self.assertEqual(self.destination.stat().st_ino, identity)
        self.destination.write_bytes(b'changed snapshot')
        with self.assertRaises(workspace.WorkspaceError): self.store.snapshot_file(self.source)
        self.assertEqual(self.destination.read_bytes(), b'changed snapshot')
        self.assert_source_and_temporaries()

    def test_existing_symlink_and_dangling_symlink_are_not_adopted(self):
        outside = self.root / 'external.png'
        outside.write_bytes(self.content)
        try: self.destination.symlink_to(outside)
        except OSError: self.skipTest('Symlink creation is unavailable')
        with self.assertRaises(workspace.WorkspaceError): self.store.snapshot_file(self.source)
        self.assertTrue(self.destination.is_symlink())
        self.assertEqual(outside.read_bytes(), self.content)
        outside.unlink()
        with self.assertRaises(workspace.WorkspaceError): self.store.snapshot_file(self.source)
        self.assertTrue(self.destination.is_symlink())
        self.assertFalse(outside.exists())
        self.assert_source_and_temporaries()

    def test_existing_directory_is_preserved_with_workspace_error(self):
        self.destination.mkdir()
        (self.destination / 'keep.txt').write_text('evidence')
        with self.assertRaises(workspace.WorkspaceError): self.store.snapshot_file(self.source)
        self.assertEqual((self.destination / 'keep.txt').read_text(), 'evidence')
        self.assert_source_and_temporaries()

    def test_unsupported_publication_has_no_clobbering_fallback(self):
        with patch('os.link', side_effect=OSError(errno.EOPNOTSUPP, 'Hardlinks unsupported')):
            with self.assertRaises(OSError): self.store.snapshot_file(self.source)
        self.assertFalse(self.destination.exists())
        self.assert_source_and_temporaries()

    def test_concurrent_identical_publishers_share_one_complete_snapshot(self):
        barrier = threading.Barrier(6)
        def publish(_):
            barrier.wait(timeout=10)
            return self.store.snapshot_file(self.source)
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(publish, range(6)))
        self.assertEqual(len(set(results)), 1)
        self.assertEqual(self.destination.read_bytes(), self.content)
        self.assertEqual(len(list(self.store.media.iterdir())), 1)
        self.assert_source_and_temporaries()


if __name__ == '__main__': unittest.main()
