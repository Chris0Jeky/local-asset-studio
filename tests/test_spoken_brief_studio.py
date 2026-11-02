"""The Studio archive facade uses retained evidence, never generation authority."""
import copy
import importlib
import importlib.util
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import test_spoken_brief_exports as fixtures
from spoken_brief_archive import inspect_run
from spoken_brief_compile import SpokenBriefError, canonical_digest
from spoken_brief_exports import load_playback
from spoken_brief_qa import FINDINGS, save_report, load_review


class StudioArchiveTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('studio_spoken'), 'Studio archive facade is missing')
        self.m = importlib.import_module('studio_spoken.core')
        self.f = fixtures.ExportTests(); self.addCleanup(self.f.doCleanups); self.f.setUp()
        self.root = self.f.source.parent
        self.key = self.f.directory.relative_to(self.root).as_posix()
        self.access = self.m.ArchiveAccess({'archive_root': str(self.root)})
        self.archive = inspect_run(self.f.directory)
        self.pin = self.archive['chapters_sha256']

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob('*') if p.is_file()}

    def review_body(self):
        target = self.archive['segments'][0]
        return {'archive_sha256': self.pin, 'target': target['id'], 'audio_sha256': target['audio_sha256'],
                'decision': 'replace', 'findings': {k: 'not-reviewed' for k in FINDINGS},
                'reviewer': 'owner', 'reason': 'Listen again to the first word', 'report_sha256': None}

    def bookmark_body(self):
        return {'archive_sha256': self.pin,
                'expected_playback_sha256': canonical_digest(load_playback(self.f.directory)),
                'sample': 9, 'rate': 1.0, 'loop': None}

    def test_disabled_and_invalid_config_never_scan_or_create_state(self):
        self.assertFalse(self.m.ArchiveAccess(None).status()['enabled'])
        with self.assertRaises(SpokenBriefError): self.m.ArchiveAccess(None).archives()
        for config in ({'archive_root': '.'}, {'archive_root': str(self.root), 'auto_start': True}, [], True):
            with self.subTest(config=config), self.assertRaises(SpokenBriefError): self.m.ArchiveAccess(config)

    def preview(self, key='.'):
        return self.access.source_preview(key, self.access.status()['source_root_id'])

    def test_source_selection_uses_compiler_precedence_and_exact_bytes(self):
        from spoken_brief_compile import compile_source
        pack = self.root / 'fictional-pack'; pack.mkdir()
        index = pack / 'INDEX.md'; index.write_text('# Index\n\nFallback text.', encoding='utf-8')
        self.assertEqual(compile_source(index), self.preview('fictional-pack')['manifest'])
        compressed = pack / 'COMPRESSED.md'; compressed.write_bytes(b'# Lantern\r\n\r\nKeep blue.\r\n')
        self.assertEqual(compile_source(compressed), self.preview('fictional-pack')['manifest'])
        self.assertEqual(compile_source(index), self.preview('fictional-pack/INDEX.md')['manifest'])
        first = self.preview('fictional-pack')['manifest']['source']['sha256']
        compressed.write_text('# Lantern\n\nNow green.', encoding='utf-8')
        self.assertNotEqual(first, self.preview('fictional-pack')['manifest']['source']['sha256'])

    def test_source_refusals_do_not_write_or_invoke_runtime(self):
        from spoken_brief_compile import MAX_SOURCE_BYTES
        source = self.root / 'COMPRESSED.md'
        for raw, message in [(b'\xff', 'UTF-8'), (b'', 'regular file'),
                             (b'x' * (MAX_SOURCE_BYTES + 1), 'regular file'),
                             (b'```\ncode only\n```', 'no narratable')]:
            source.write_bytes(raw); before = self.snapshot()
            with self.subTest(message=message), self.assertRaisesRegex(SpokenBriefError, message):
                self.preview()
            self.assertEqual(before, self.snapshot())
        for key in ('../outside.md', '/outside.md', 'C:/outside.md', 'a\\b.md', 'pack/../brief.md', 'absent.md'):
            with self.subTest(key=key), self.assertRaises((SpokenBriefError, OSError)):
                self.preview(key)
        source.rename(self.root / 'source.txt')
        with self.assertRaisesRegex(SpokenBriefError, 'Markdown'):
            self.preview('source.txt')
        with self.assertRaisesRegex(SpokenBriefError, 'root changed'):
            self.access.source_preview('.', 'a' * 64)

    def test_source_changed_during_compilation_is_refused(self):
        source = self.root / 'COMPRESSED.md'; source.write_bytes(b'# Before\n\nSnapshot.')
        compile_snapshot = self.m.compile_snapshot
        def changing(path, raw):
            result = compile_snapshot(path, raw)
            source.write_bytes(b'# After\n\nDifferent source.')
            return result
        with patch.object(self.m, 'compile_snapshot', side_effect=changing):
            with self.assertRaisesRegex(SpokenBriefError, 'changed'):
                self.preview()

    def test_source_links_cannot_escape_configured_root(self):
        link = self.root / 'COMPRESSED.md'
        try: link.symlink_to(self.f.source)
        except OSError: self.skipTest('Symlink creation unavailable')
        with self.assertRaisesRegex(SpokenBriefError, 'Symlink/reparse'):
            self.preview()
        with self.assertRaisesRegex(SpokenBriefError, 'Symlink/reparse'):
            self.preview('COMPRESSED.md')

    def test_source_windows_reparse_marker_is_refused_before_open(self):
        from types import SimpleNamespace
        source = self.root / 'COMPRESSED.md'; source.write_bytes(b'# Fictional\n\nText.')
        original = Path.lstat
        def reparse(path, *args, **kwargs):
            info = original(path, *args, **kwargs)
            if path == source:
                return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
            return info
        with patch.object(Path, 'lstat', reparse), patch('os.open', side_effect=AssertionError('Must refuse before opening')):
            with self.assertRaisesRegex(SpokenBriefError, 'Symlink/reparse'):
                self.preview()

    def test_listing_and_inspection_are_read_only_and_never_create_clients(self):
        before = self.snapshot()
        with patch('spoken_brief_runtime.StudioClient', side_effect=AssertionError('No inference')):
            listing = self.access.archives()
            self.assertEqual([self.key], [x['key'] for x in listing['archives']])
            self.assertEqual('not-verified', listing['archives'][0]['verification'])
            result = self.access.inspect(self.key)
        self.assertEqual(self.archive, result['archive'])
        self.assertEqual(self.pin, result['archive_sha256'])
        self.assertFalse(result['generation_submitted'])
        self.assertEqual(before, self.snapshot())

    def test_list_preserves_incomplete_archive_for_explicit_inspection(self):
        (self.f.directory / 'receipt.json').unlink()
        self.assertEqual(self.key, self.access.archives()['archives'][0]['key'])
        with self.assertRaises(SpokenBriefError): self.access.inspect(self.key)

    def test_path_spellings_and_root_escapes_are_rejected(self):
        for key in ('../elsewhere', '/tmp', 'a/../b', 'a//b', 'a\\b', 'C:/elsewhere', '', 'x\x00y', 'x/', 'x. '):
            with self.subTest(key=key), self.assertRaises(SpokenBriefError): self.access.inspect(key)

    def test_links_are_visible_refusals_and_never_followed(self):
        link = self.root / 'alias'
        try: link.symlink_to(self.f.directory, target_is_directory=True)
        except OSError: self.skipTest('Symlink creation unavailable')
        listing = self.access.archives()
        self.assertTrue(listing['refusals'])
        with self.assertRaises(SpokenBriefError): self.access.inspect('alias')

    def test_listing_is_bounded_and_reports_truncation(self):
        with patch.object(self.m, 'MAX_ENTRIES', 1):
            result = self.access.archives()
        self.assertTrue(result['truncated'])

    def test_audio_and_segment_streams_are_exact_and_read_only(self):
        before = self.snapshot()
        for target, path in [('master', self.f.output), ('segment-0001', self.f.directory / 'segments/segment-0001.wav')]:
            with self.access.audio(self.key, self.pin, target) as (stream, size):
                self.assertEqual(path.read_bytes(), stream.read())
                self.assertEqual(path.stat().st_size, size)
        self.assertEqual(before, self.snapshot())

    def test_invalid_audio_targets_or_stale_archive_cannot_serve_bytes(self):
        for pin, target in [(self.pin, '../receipt'), ('f' * 64, 'master'), (self.pin, 'segment-9999')]:
            with self.subTest(target=target), self.assertRaises(SpokenBriefError):
                with self.access.audio(self.key, pin, target): self.fail('Should not yield a stream')

    def test_review_write_is_exact_archive_bound_and_idempotent(self):
        original = (self.f.directory / 'receipt.json').read_bytes()
        body = self.review_body(); result = self.access.review(self.key, body)
        self.assertEqual('replace', load_review(self.f.directory, result['id'])['decision'])
        self.assertTrue(self.access.review(self.key, body)['reused'])
        self.assertIn(result['id'], self.access.inspect(self.key)['reviews'])
        self.assertEqual(original, (self.f.directory / 'receipt.json').read_bytes())
        self.assertFalse((self.f.directory / 'replacements').exists())

    def test_stale_review_and_unknown_fields_fail_before_writes(self):
        for change in ({'archive_sha256': 'f' * 64}, {'auto_start': True}, {'report_sha256': '../file'}):
            body = self.review_body(); body.update(change)
            with self.subTest(change=change), self.assertRaises(SpokenBriefError): self.access.review(self.key, body)
        self.assertFalse((self.f.directory / 'qa').exists())

    def test_bookmark_requires_explicit_identity_and_detects_stale_tabs(self):
        body = self.bookmark_body(); result = self.access.bookmark(self.key, body)
        self.assertEqual(9, result['playback']['sample'])
        self.assertEqual(canonical_digest(result['playback']), result['playback_sha256'])
        body['sample'] = 17
        with self.assertRaises(SpokenBriefError): self.access.bookmark(self.key, body)
        self.assertEqual(9, load_playback(self.f.directory)['sample'])

    def test_optional_writer_arguments_are_mandatory_at_the_web_boundary(self):
        for field in ('archive_sha256', 'expected_playback_sha256'):
            body = self.bookmark_body(); body[field] = None
            with self.subTest(field=field), self.assertRaises(SpokenBriefError): self.access.bookmark(self.key, body)
        self.assertFalse((self.f.directory / 'playback.json').exists())

    def test_machine_report_selection_does_not_become_owner_acceptance(self):
        evidence = {'schema_version': 1, 'manifest_sha256': self.archive['manifest_sha256'],
                    'master_sha256': self.archive['master']['sha256'], 'observations': []}
        identifier = save_report(self.f.directory, evidence)['id']
        before = self.snapshot()
        report = self.access.report(self.key, self.pin, identifier)
        self.assertTrue(all(x['transcript_status'] == 'not-transcribed' for x in report['targets']))
        self.assertTrue(all(x['listening_status'] == 'unreviewed' for x in report['targets']))
        self.assertEqual(before, self.snapshot())

    def test_record_lists_do_not_auto_select_or_follow_linked_records(self):
        self.access.review(self.key, self.review_body())
        group = self.f.directory / 'qa/reviews'
        try: (group / ('f' * 64 + '.json')).symlink_to(self.f.output)
        except OSError: self.skipTest('Symlink creation unavailable')
        result = self.access.inspect(self.key)
        self.assertEqual(1, len(result['reviews']))
        self.assertTrue(result['record_refusals'])

    def test_changed_archive_between_facade_and_review_writer_is_refused(self):
        import spoken_brief_qa as qa
        real = qa.inspect_run
        changed = copy.deepcopy(self.archive); changed['chapters_sha256'] = 'd' * 64
        with patch.object(qa, 'inspect_run', return_value=changed):
            with self.assertRaises(SpokenBriefError): self.access.review(self.key, self.review_body())
        self.assertFalse((self.f.directory / 'qa').exists())

    def test_discovery_quota_does_not_skip_final_root_identity_check(self):
        original = self.m._lineage
        calls = 0
        def lineage(path):
            nonlocal calls
            result = original(path)
            if path == self.root:
                calls += 1
                if calls >= 4: return result + [('changed-root', 1, 2)]
            return result
        with patch.object(self.m, 'MAX_ENTRIES', 1), patch.object(self.m, '_lineage', side_effect=lineage):
            with self.assertRaises(SpokenBriefError): self.access.archives()

    def test_inspect_rechecks_archive_after_reading_user_evidence(self):
        real = self.access._records
        def changed(directory, group):
            result = real(directory, group)
            if group == 'reviews': (self.f.directory / 'receipt.json').write_bytes(b'{}')
            return result
        with patch.object(self.access, '_records', side_effect=changed):
            with self.assertRaises(SpokenBriefError): self.access.inspect(self.key)

    def test_lone_surrogate_paths_are_refused_as_domain_errors(self):
        with self.assertRaises(SpokenBriefError): self.access.inspect('bad\ud800')


if __name__ == '__main__': unittest.main()
