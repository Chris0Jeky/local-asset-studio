"""A stat-shaped cache is not content evidence for a pinned production model."""
import hashlib
import os
import unittest
from unittest.mock import patch
import test_preset_model_readiness as fixture


class PinnedFreshnessTests(unittest.TestCase):
    setUp = fixture.PresetModelReadinessTests.setUp
    studio = fixture.PresetModelReadinessTests.studio
    put = fixture.PresetModelReadinessTests.put
    pin = fixture.PresetModelReadinessTests.pin
    pinned_file = fixture.PresetModelReadinessTests.pinned_file
    cache = fixture.PresetModelReadinessTests.cache
    preflight = fixture.PresetModelReadinessTests.preflight

    def test_same_size_in_place_rewrite_with_preserved_mtime_is_refused(self):
        pin, path = self.pinned_file(); studio = self.studio(); self.cache(path, pin['sha256'])
        stamp = path.stat(); path.write_bytes(b'x' * stamp.st_size)
        os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        with self.assertRaisesRegex(fixture.server.StudioError, 'does not match its library pin'):
            self.preflight(studio)
        self.assertFalse(studio.jobs); self.assertTrue(studio.queue.empty())

    def test_same_size_atomic_replacement_with_preserved_mtime_is_refused(self):
        pin, path = self.pinned_file(); studio = self.studio(); self.cache(path, pin['sha256'])
        stamp = path.stat(); other = path.with_name('replacement.tmp')
        other.write_bytes(b'x' * stamp.st_size); os.utime(other, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        os.replace(other, path)
        with self.assertRaisesRegex(fixture.server.StudioError, 'does not match its library pin'):
            self.preflight(studio)
        self.assertFalse(studio.jobs); self.assertTrue(studio.queue.empty())

    def test_matching_cache_without_receipt_still_hashes_current_pinned_bytes(self):
        pin, path = self.pinned_file(); studio = self.studio(); self.cache(path, pin['sha256'])
        with patch.object(fixture.server, 'digest_file', wraps=fixture.server.digest_file) as digest:
            result = self.preflight(studio)
        digest.assert_called_once_with(path.resolve())
        self.assertEqual(result['models'][0]['sha256'], pin['sha256'])

    def test_file_changed_during_hash_does_not_publish_cache_evidence(self):
        pin, path = self.pinned_file(); studio = self.studio()
        def changing(candidate):
            digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
            candidate.write_bytes(b'changed size while hashing')
            return digest
        target = self.root/'.runtime/model-fingerprints.json'
        with patch.object(fixture.server, 'digest_file', side_effect=changing), \
             self.assertRaisesRegex(fixture.server.StudioError, 'changed while hashing'):
            self.preflight(studio)
        self.assertFalse(target.exists()); self.assertFalse(studio.jobs); self.assertTrue(studio.queue.empty())
