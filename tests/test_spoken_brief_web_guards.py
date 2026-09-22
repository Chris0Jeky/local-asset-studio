"""Archive and bookmark identities must be checked at the actual write boundary."""
import unittest
from unittest.mock import patch

import test_spoken_brief_exports as fixtures
from spoken_brief_archive import inspect_run
from spoken_brief_compile import SpokenBriefError, canonical_digest
from spoken_brief_exports import load_playback, save_playback
from spoken_brief_qa import FINDINGS, record_review


class WebWriteGuardTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.ExportTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.archive = inspect_run(self.f.directory)

    def test_stale_bookmark_cannot_overwrite_a_newer_save(self):
        initial = canonical_digest(load_playback(self.f.directory))
        save_playback(self.f.directory, sample=13, expected_playback_sha256=initial,
                      expected_archive_sha256=self.archive['chapters_sha256'])
        before = (self.f.directory / 'playback.json').read_bytes()
        with self.assertRaisesRegex(SpokenBriefError, 'Playback.*changed'):
            save_playback(self.f.directory, sample=21, expected_playback_sha256=initial,
                          expected_archive_sha256=self.archive['chapters_sha256'])
        self.assertEqual(before, (self.f.directory / 'playback.json').read_bytes())

    def test_guarded_save_accepts_exact_current_digest(self):
        for sample in (9, 27, 0):
            previous = load_playback(self.f.directory)
            result = save_playback(self.f.directory, sample=sample,
                expected_playback_sha256=canonical_digest(previous),
                expected_archive_sha256=self.archive['chapters_sha256'])
            self.assertEqual(sample, result['sample'])

    def test_stale_archive_blocks_bookmark_before_a_claim_or_file(self):
        with self.assertRaisesRegex(SpokenBriefError, 'Archive.*changed'):
            save_playback(self.f.directory, sample=13, expected_archive_sha256='f' * 64)
        self.assertFalse((self.f.directory / 'playback.json').exists())
        self.assertFalse((self.f.directory / '.coordinator.lock').exists())

    def test_stale_archive_blocks_review_even_when_segment_audio_matches(self):
        segment = self.archive['segments'][0]
        with self.assertRaisesRegex(SpokenBriefError, 'Archive.*changed'):
            record_review(self.f.directory, segment['id'], segment['audio_sha256'],
                decision='keep', findings={k: 'acceptable' for k in FINDINGS},
                reviewer='owner', reason='Reviewed this exact archive',
                expected_archive_sha256='f' * 64)
        self.assertFalse((self.f.directory / 'qa').exists())

    def test_bookmark_compare_occurs_under_the_existing_claim(self):
        import spoken_brief_exports as exports
        initial = canonical_digest(load_playback(self.f.directory))
        real_claim = exports._claim
        def competing(*args):
            with patch.object(exports, '_claim', real_claim):
                save_playback(self.f.directory, sample=7)
            return real_claim(*args)
        with patch.object(exports, '_claim', side_effect=competing):
            with self.assertRaisesRegex(SpokenBriefError, 'Playback.*changed'):
                save_playback(self.f.directory, sample=9, expected_playback_sha256=initial)
        self.assertEqual(7, load_playback(self.f.directory)['sample'])


if __name__ == '__main__': unittest.main()
