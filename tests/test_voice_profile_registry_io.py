"""Actual OS ownership and fault boundaries for the private profile registry."""
import importlib
import importlib.util
import multiprocessing
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import voice_profile as vp
from test_voice_profile_contract import accepted_ember, profile_by_id


def hold_lock(path, ready, release):
    import voice_profile_registry_io as io
    with io.writer_lock(Path(path), timeout=5):
        ready.set()
        release.wait(15)


def crash_at_boundary(path, command, boundary):
    import voice_profile_registry as registry
    from unittest.mock import patch
    if boundary == 'flushed':
        original = registry.io.os.fsync
        def crash(fd):
            original(fd)
            os._exit(73)
        with patch.object(registry.io.os, 'fsync', side_effect=crash):
            registry.update_registry(Path(path), command)
    else:
        original = registry.io.os.replace
        def crash(source, destination):
            original(source, destination)
            os._exit(74)
        with patch.object(registry.io.os, 'replace', side_effect=crash):
            registry.update_registry(Path(path), command)


class RegistryIO(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('voice_profile_registry'),
                             'the owned registry update boundary is missing')
        self.r = importlib.import_module('voice_profile_registry')
        self.io = self.r.io
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.path = self.root / 'registry.json'

    def command(self):
        state = self.r.inspect_registry(self.path)
        base = profile_by_id(state, 'ember-brief-v1')
        return {'schema_version': 1, 'request_id': 'update-a',
                'expected_registry_sha256': state['registry_sha256'],
                'expected_profile_sha256': vp.profile_digest(base),
                'profile': accepted_ember(base, vp.profile_digest(base))}

    def test_external_replacement_while_waiting_for_lock_is_refused_even_for_same_bytes(self):
        self.r.update_registry(self.path, self.command())
        command = self.command(); command['request_id'] = 'update-b'
        raw = self.path.read_bytes()
        original_lock = self.io.writer_lock
        def replaced_before_lock(*args, **kwargs):
            replacement = self.root / 'external.json'
            replacement.write_bytes(raw)
            os.replace(replacement, self.path)
            return original_lock(*args, **kwargs)
        with patch.object(self.io, 'writer_lock', side_effect=replaced_before_lock):
            with self.assertRaisesRegex(vp.VoiceProfileError, 'changed'):
                self.r.update_registry(self.path, command)
        self.assertEqual(self.path.read_bytes(), raw)
        self.assertIsNone(self.r.get_receipt(self.path, 'update-b'))

    def test_external_edit_during_flush_is_not_overwritten(self):
        command = self.command()
        fsync = self.io.os.fsync
        def edited_during_flush(fd):
            fsync(fd)
            self.path.write_bytes(b'externally changed')
        with patch.object(self.io.os, 'fsync', side_effect=edited_during_flush):
            with self.assertRaises(vp.VoiceProfileError): self.r.update_registry(self.path, command)
        self.assertEqual(self.path.read_bytes(), b'externally changed')

    def test_catalogue_changed_after_flush_cannot_publish(self):
        command = self.command(); catalog = vp.load_catalog()
        fsync = self.io.os.fsync
        def changed(fd):
            fsync(fd)
            catalog['profiles'][0]['name'] += ' changed'
        with patch.object(vp, 'load_catalog', side_effect=lambda: catalog):
            with patch.object(self.io.os, 'fsync', side_effect=changed):
                with self.assertRaisesRegex(vp.VoiceProfileError, 'catalog'):
                    self.r.update_registry(self.path, command)
        self.assertFalse(self.path.exists())

    def test_lock_path_replacement_cannot_publish(self):
        command = self.command(); fsync = self.io.os.fsync
        def changed(fd):
            fsync(fd)
            lock = self.path.with_name(self.path.name + '.lock')
            try: lock.unlink()
            except PermissionError: return  # Windows itself refuses deleting the open lock.
            lock.write_bytes(b'replacement')
        with patch.object(self.io.os, 'fsync', side_effect=changed):
            try: self.r.update_registry(self.path, command)
            except vp.VoiceProfileError: self.assertFalse(self.path.exists())
            else:
                self.assertEqual(os.name, 'nt')
                self.assertIsNotNone(self.r.get_receipt(self.path, 'update-a'))

    def test_symlink_and_linked_parent_refused_without_touching_target(self):
        command = self.command()
        target = self.root / 'target'; target.write_bytes(b'private target')
        try: self.path.symlink_to(target)
        except (OSError, NotImplementedError): self.skipTest('symlinks unavailable')
        with self.assertRaises(vp.VoiceProfileError): self.r.update_registry(self.path, command)
        self.assertEqual(target.read_bytes(), b'private target')
        self.path.unlink()
        directory = self.root / 'real'; directory.mkdir()
        linked = self.root / 'linked'; linked.symlink_to(directory, target_is_directory=True)
        with self.assertRaises(vp.VoiceProfileError):
            self.r.inspect_registry(linked / 'registry.json')
        self.assertEqual(list(directory.iterdir()), [])

    def test_lock_symlink_is_never_followed(self):
        command = self.command()
        target = self.root / 'target'; target.write_bytes(b'private target')
        try: (self.root / 'registry.json.lock').symlink_to(target)
        except (OSError, NotImplementedError): self.skipTest('symlinks unavailable')
        with self.assertRaises(vp.VoiceProfileError): self.r.update_registry(self.path, command)
        self.assertEqual(target.read_bytes(), b'private target')
        self.assertFalse(self.path.exists())

    def test_oversize_refuses_before_open_and_inspection_never_creates_parent(self):
        self.path.write_bytes(b' ' * (self.r.MAX_REGISTRY_BYTES + 1))
        with patch.object(self.io.os, 'open', side_effect=AssertionError('open before byte check')):
            with self.assertRaisesRegex(vp.VoiceProfileError, 'byte'): self.r.inspect_registry(self.path)
        with self.assertRaises(vp.VoiceProfileError):
            self.r.inspect_registry(self.root / 'missing' / 'registry.json')
        self.assertFalse((self.root / 'missing').exists())

    def test_real_process_lock_timeout_is_bounded_and_never_falls_back(self):
        command = self.command()
        ctx = multiprocessing.get_context('spawn')
        ready, release = ctx.Event(), ctx.Event()
        child = ctx.Process(target=hold_lock, args=(str(self.path), ready, release))
        child.start()
        try:
            self.assertTrue(ready.wait(10))
            with self.assertRaisesRegex(vp.VoiceProfileError, 'lock'):
                self.r.update_registry(self.path, command, lock_timeout=0.05)
            self.assertFalse(self.path.exists())
        finally:
            release.set(); child.join(10)
            if child.is_alive(): child.terminate(); child.join(5)
        self.assertEqual(child.exitcode, 0)
        self.r.update_registry(self.path, command)
        self.assertTrue((self.root / 'registry.json.lock').is_file())

    @unittest.skipUnless(os.name == 'posix', 'directory fsync is POSIX-only')
    def test_post_replace_directory_flush_failure_is_unconfirmed_but_receipted(self):
        command = self.command(); fsync = self.io.os.fsync
        import stat
        def fail_directory(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode): raise OSError('directory flush lost')
            fsync(fd)
        with patch.object(self.io.os, 'fsync', side_effect=fail_directory):
            with self.assertRaises(self.r.RegistryUnconfirmed): self.r.update_registry(self.path, command)
        self.assertIsNotNone(self.r.get_receipt(self.path, 'update-a'))
        self.r.update_registry(self.path, command)

    @unittest.skipUnless(os.name == 'posix', 'directory fsync is POSIX-only')
    def test_change_during_final_directory_flush_is_not_acknowledged(self):
        command = self.command(); fsync = self.io.os.fsync
        import stat
        def edit_after_commit(fd):
            fsync(fd)
            if stat.S_ISDIR(os.fstat(fd).st_mode): self.path.write_bytes(b'external replacement')
        with patch.object(self.io.os, 'fsync', side_effect=edit_after_commit):
            with self.assertRaises(self.r.RegistryUnconfirmed): self.r.update_registry(self.path, command)
        self.assertEqual(self.path.read_bytes(), b'external replacement')

    def test_lock_release_failure_is_unconfirmed_and_replayable(self):
        command = self.command()
        with patch.object(self.io, '_unlock', side_effect=OSError('unlock error')):
            with self.assertRaises(self.r.RegistryUnconfirmed): self.r.update_registry(self.path, command)
        self.assertIsNotNone(self.r.get_receipt(self.path, 'update-a'))
        self.r.update_registry(self.path, command)

    def test_hardlinked_registry_refuses_without_mutating_either_name(self):
        self.r.update_registry(self.path, self.command())
        alias = self.root / 'alias'
        try: os.link(self.path, alias)
        except (OSError, NotImplementedError): self.skipTest('hardlinks unavailable')
        before = self.path.read_bytes()
        with self.assertRaises(vp.VoiceProfileError): self.r.inspect_registry(self.path)
        self.assertEqual(alias.read_bytes(), before)

    def test_real_process_death_releases_lock_and_preserves_the_commit_boundary(self):
        command = self.command(); ctx = multiprocessing.get_context('spawn')
        for boundary, exitcode in (('flushed', 73), ('replaced', 74)):
            child = ctx.Process(target=crash_at_boundary, args=(str(self.path), command, boundary))
            child.start()
            try:
                child.join(15)
                self.assertFalse(child.is_alive(), 'crash fixture exceeded its bound')
                self.assertEqual(child.exitcode, exitcode)
            finally:
                if child.is_alive(): child.terminate(); child.join(5)
            receipt = self.r.get_receipt(self.path, 'update-a')
            if boundary == 'flushed':
                self.assertIsNone(receipt)
                self.assertFalse(self.path.exists())
                self.assertTrue(list(self.root.glob('.registry.json.pending-*')))
            else:
                self.assertIsNotNone(receipt)
                before = self.path.read_bytes()
                self.assertEqual(self.r.update_registry(self.path, command), receipt)
                self.assertEqual(self.path.read_bytes(), before)

    def test_fdopen_failure_closes_descriptor(self):
        command = self.command(); self.r.update_registry(self.path, command)
        descriptors = []; real_open = self.io.os.open
        def record(*args, **kwargs):
            fd = real_open(*args, **kwargs); descriptors.append(fd); return fd
        with patch.object(self.io.os, 'open', side_effect=record):
            with patch.object(self.io.os, 'fdopen', side_effect=OSError('stream failure')):
                with self.assertRaises(vp.VoiceProfileError): self.r.inspect_registry(self.path)
        self.assertTrue(descriptors)
        for fd in descriptors:
            with self.assertRaises(OSError): os.fstat(fd)


if __name__ == '__main__': unittest.main()
