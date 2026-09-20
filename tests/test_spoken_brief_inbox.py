"""Review inbox contracts: real files, controlled observation time, no inference."""
import importlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import spoken_brief_compile as compiler


class InboxTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('spoken_brief_inbox'), 'review-first inbox is missing')
        self.module = importlib.import_module('spoken_brief_inbox')
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'handoffs'; self.root.mkdir()
        self.state = Path(self.temp.name) / 'inbox.json'
        self.now = 0.0
        self.inbox = self.module.Inbox(self.root, self.state, clock=lambda: self.now)

    def source(self, pack='one', content='# Brief\n\nHello world.', name='COMPRESSED.md'):
        path = self.root / pack / name; path.parent.mkdir(exist_ok=True, parents=True)
        path.write_text(content, encoding='utf-8'); return path

    def settle(self):
        self.inbox.scan(); self.now += 3; return self.inbox.scan()

    def test_empty_listing_is_read_only(self):
        self.assertEqual([], self.inbox.list()['candidates'])
        self.assertFalse(self.state.exists())
        self.assertEqual([], list(self.root.iterdir()))

    def test_requires_two_stable_observations(self):
        self.source()
        self.assertEqual([], self.inbox.scan()['candidates'])
        self.now += 1
        self.assertEqual([], self.inbox.scan()['candidates'])
        self.now += 2
        result = self.inbox.scan()
        self.assertEqual(1, len(result['candidates']))
        item = self.inbox.preview(result['candidates'][0]['id'])
        self.assertEqual('spoken-brief', item['manifest']['kind'])
        self.assertEqual('pending', item['status'])
        self.assertFalse(item['generation_submitted'])
        self.assertEqual(2, len(item['manifest']['segments']))
        self.assertEqual(item['source_sha256'], item['manifest']['source']['sha256'])

    def test_same_size_same_mtime_rewrite_restarts_stability(self):
        path = self.source(content='Alpha sentence.'); self.inbox.scan(); old = path.stat()
        path.write_text('Bravo sentence.', encoding='utf-8'); os.utime(path, ns=(old.st_atime_ns, old.st_mtime_ns))
        self.now += 3
        self.assertEqual([], self.inbox.scan()['candidates'])
        self.now += 3
        item = self.inbox.scan()['candidates'][0]
        self.assertEqual('Bravo sentence.', self.inbox.preview(item['id'])['manifest']['segments'][0]['text'])

    def test_atomic_rename_restarts_stability_even_with_same_bytes(self):
        path = self.source(); self.inbox.scan(); old = path.stat()
        temp = path.with_suffix('.new'); temp.write_bytes(path.read_bytes())
        os.utime(temp, ns=(old.st_atime_ns, old.st_mtime_ns)); os.replace(temp, path)
        self.now += 3
        self.assertEqual([], self.inbox.scan()['candidates'])
        self.now += 3
        self.assertEqual(1, len(self.inbox.scan()['candidates']))

    def test_preference_and_no_fallback_for_invalid_preferred_source(self):
        self.source(content='Fallback.', name='INDEX.md'); self.source(content='Chosen.')
        item = self.settle()['candidates'][0]
        self.assertEqual('Chosen.', self.inbox.preview(item['id'])['manifest']['segments'][0]['text'])
        self.source(content='')
        result = self.settle()
        self.assertEqual(1, len(result['candidates']))
        self.assertTrue(result['refusals'])

    def test_index_fallback_and_root_pack(self):
        self.source(pack='', name='INDEX.md')
        self.assertEqual(1, len(self.settle()['candidates']))

    def test_hash_dedupe_across_paths_and_repeated_events(self):
        self.source(); self.source(pack='two')
        result = self.settle()
        self.assertEqual(1, len(result['candidates']))
        self.assertEqual(2, len(result['candidates'][0]['sources']))
        self.assertEqual(1, len(self.settle()['candidates']))

    def test_changed_source_retains_previous_preview_and_relationship(self):
        path = self.source(); first = self.settle()['candidates'][0]
        prior = self.inbox.preview(first['id'])
        path.write_text('New narration.', encoding='utf-8')
        result = self.settle(); self.assertEqual(2, len(result['candidates']))
        later = next(item for item in result['candidates'] if item['id'] != first['id'])
        self.assertIn(first['id'], later['supersedes'])
        self.assertEqual(prior, self.inbox.preview(first['id']))

    def test_restart_preserves_candidates_and_ignore_without_jobs(self):
        self.source(); item = self.settle()['candidates'][0]
        self.inbox.ignore(item['id'])
        reopened = self.module.Inbox(self.root, self.state, clock=lambda: self.now)
        with patch('spoken_brief_runtime.StudioClient', side_effect=AssertionError('No network')):
            self.assertEqual('ignored', reopened.list()['candidates'][0]['status'])
            reopened.scan(); self.now += 3; result = reopened.scan()
            self.assertEqual(1, len(result['candidates']))
            self.assertEqual('ignored', result['candidates'][0]['status'])
        self.assertFalse((self.root / 'one' / '_spoken').exists())

    def test_restart_never_reuses_unfinished_stability_timer(self):
        self.source(); self.inbox.scan(); self.now += 100
        self.inbox = self.module.Inbox(self.root, self.state, clock=lambda: self.now)
        self.assertEqual([], self.inbox.scan()['candidates'])
        self.now += 3; self.assertEqual(1, len(self.inbox.scan()['candidates']))

    def test_invalid_sources_are_visible_refusals(self):
        for name, data in [('empty', b''), ('encoding', b'\xff'), ('large', b'x' * (compiler.MAX_SOURCE_BYTES + 1)), ('code', b'```\ncode\n```')]:
            self.source(pack=name).write_bytes(data)
        result = self.settle()
        self.assertEqual([], result['candidates'])
        self.assertEqual(4, len(result['refusals']))

    def test_symlinks_are_not_followed_and_preference_cannot_be_laundered(self):
        outside = Path(self.temp.name) / 'outside.md'; outside.write_text('Secret.', encoding='utf-8')
        pack = self.root / 'one'; pack.mkdir(); (pack / 'INDEX.md').write_text('Fallback.', encoding='utf-8')
        try: (pack / 'COMPRESSED.md').symlink_to(outside)
        except OSError: self.skipTest('Symlinks require Windows developer mode')
        result = self.settle()
        self.assertFalse(result['candidates']); self.assertTrue(result['refusals'])
        self.assertNotIn('Secret.', json.dumps(result))

    def test_directory_symlink_is_a_visible_refusal(self):
        outside = Path(self.temp.name) / 'outside'; outside.mkdir(); (outside / 'COMPRESSED.md').write_text('Secret.', encoding='utf-8')
        try: (self.root / 'escape').symlink_to(outside, target_is_directory=True)
        except OSError: self.skipTest('Symlinks require Windows developer mode')
        result = self.settle()
        self.assertFalse(result['candidates']); self.assertTrue(result['refusals'])

    @unittest.skipUnless(os.name == 'nt', 'Windows junction boundary')
    def test_windows_junction_is_a_visible_refusal(self):
        outside = Path(self.temp.name) / 'outside'; outside.mkdir(); (outside / 'COMPRESSED.md').write_text('Secret.', encoding='utf-8')
        link = self.root / 'escape'
        completed = subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(outside)], capture_output=True)
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.addCleanup(lambda: link.rmdir() if link.exists() else None)
        result = self.settle()
        self.assertFalse(result['candidates']); self.assertTrue(result['refusals'])

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'POSIX FIFO boundary')
    def test_fifo_is_refused_without_waiting_for_a_writer(self):
        pack = self.root / 'one'; pack.mkdir(); os.mkfifo(pack / 'COMPRESSED.md')
        result = self.settle(); self.assertFalse(result['candidates']); self.assertTrue(result['refusals'])

    def test_generated_and_hidden_directories_are_not_discovered(self):
        self.source(pack='_spoken'); self.source(pack='.git'); self.source(pack='one/_spoken')
        self.assertFalse(self.settle()['candidates'])

    def test_candidate_quota_refuses_without_pruning(self):
        self.source(); first = self.settle()['candidates'][0]
        with patch.object(self.module, 'MAX_CANDIDATES', 1):
            self.source(pack='two', content='Different.'); result = self.settle()
        self.assertEqual([first['id']], [item['id'] for item in result['candidates']])
        self.assertTrue(any('capacity' in item['error'].lower() for item in result['refusals']))

    def test_duplicate_json_keys_and_non_finite_constants_fail_closed(self):
        for raw in ['{"schema_version":1,"schema_version":1}', '{"x":NaN}', '{"x":Infinity}']:
            with self.subTest(raw=raw):
                self.state.write_text(raw, encoding='utf-8')
                with self.assertRaises(compiler.SpokenBriefError): self.inbox.scan()
                self.assertEqual(raw, self.state.read_text(encoding='utf-8'))

    def test_corrupted_source_snapshot_is_refused(self):
        self.source(); self.settle()
        state = json.loads(self.state.read_text(encoding='utf-8'))
        state['candidates'][0]['source_text'] = 'Tampered.'
        self.state.write_text(json.dumps(state), encoding='utf-8')
        with self.assertRaises(compiler.SpokenBriefError): self.inbox.list()

    def test_state_cannot_be_rebound_to_a_different_root(self):
        self.source(); self.settle(); other = Path(self.temp.name) / 'other'; other.mkdir()
        with self.assertRaises(compiler.SpokenBriefError): self.module.Inbox(other, self.state).list()

    def test_lost_source_does_not_delete_retained_preview(self):
        path = self.source(); item = self.settle()['candidates'][0]; path.unlink()
        self.inbox.scan()
        self.assertEqual(item['source_sha256'], self.inbox.preview(item['id'])['source_sha256'])

    def test_unknown_candidate_and_path_like_id_are_refused(self):
        for identifier in ['../outside', 'f' * 64]:
            with self.assertRaises(compiler.SpokenBriefError): self.inbox.preview(identifier)
            with self.assertRaises(compiler.SpokenBriefError): self.inbox.ignore(identifier)

    def test_invalid_utf8_refusal_stays_visible_on_each_scan(self):
        self.source().write_bytes(b'\xff'); self.settle()
        self.assertTrue(self.inbox.scan()['refusals'])

    def test_preference_change_is_related_to_previous_pack_candidate(self):
        self.source(name='INDEX.md'); first = self.settle()['candidates'][0]
        self.source(content='A new compressed handoff.')
        result = self.settle()
        newer = next(x for x in result['candidates'] if x['id'] != first['id'])
        self.assertIn(first['id'], newer['supersedes'])

    def test_external_write_during_flush_is_not_overwritten(self):
        self.source(); item = self.settle()['candidates'][0]
        changed = False; original_fsync = os.fsync
        def change(descriptor):
            nonlocal changed
            original_fsync(descriptor)
            if not changed:
                changed = True; self.state.write_text('{"external":true}', encoding='utf-8')
        with patch.object(self.module.os, 'fsync', side_effect=change):
            with self.assertRaises(compiler.SpokenBriefError): self.inbox.ignore(item['id'])
        self.assertEqual('{"external":true}', self.state.read_text(encoding='utf-8'))

    def test_rehashed_but_malformed_segments_are_refused(self):
        self.source(); self.settle(); value = json.loads(self.state.read_text(encoding='utf-8'))
        manifest = value['candidates'][0]['manifest']; manifest['segments'][0]['pause_after_ms'] = 'not samples'
        manifest['manifest_sha256'] = compiler.canonical_digest({k:v for k,v in manifest.items() if k != 'manifest_sha256'})
        self.state.write_text(json.dumps(value), encoding='utf-8')
        with self.assertRaises(compiler.SpokenBriefError): self.inbox.list()

    def test_competing_writer_is_refused_and_lock_releases(self):
        self.source(); item = self.settle()['candidates'][0]
        other = self.module.Inbox(self.root, self.state)
        with self.inbox._lock():
            with self.assertRaises(compiler.SpokenBriefError): other.ignore(item['id'])
        self.assertEqual('ignored', other.ignore(item['id'])['status'])

    def test_capture_rejects_file_replaced_during_open(self):
        path = self.source(); original_open = os.open; replaced = False
        def replace(file, flags, *args, **kwargs):
            nonlocal replaced
            if Path(file) == path and not replaced:
                replacement = path.with_suffix('.new'); replacement.write_text('Foreign bytes.', encoding='utf-8')
                os.replace(replacement, path); replaced = True
            return original_open(file, flags, *args, **kwargs)
        with patch.object(self.module.os, 'open', side_effect=replace):
            with self.assertRaises(compiler.SpokenBriefError): self.module._capture(path, compiler.MAX_SOURCE_BYTES)

    def test_atomic_write_failure_preserves_previous_inbox(self):
        self.source(); item = self.settle()['candidates'][0]; prior = self.state.read_bytes()
        with patch.object(self.module.os, 'replace', side_effect=OSError('disk write failed')):
            with self.assertRaises(compiler.SpokenBriefError): self.inbox.ignore(item['id'])
        self.assertEqual(prior, self.state.read_bytes())


class CapturedCompilerTests(unittest.TestCase):
    def test_captured_bytes_compile_without_reading_or_creating_source(self):
        self.assertTrue(hasattr(compiler, 'compile_snapshot'), 'captured-byte compiler is missing')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'COMPRESSED.md'; raw = b'# Brief\r\n\r\nStable text.'
            manifest = compiler.compile_snapshot(path, raw)
            self.assertFalse(path.exists())
            path.write_bytes(raw)
            self.assertEqual(compiler.compile_source(path), manifest)


if __name__ == '__main__': unittest.main()
