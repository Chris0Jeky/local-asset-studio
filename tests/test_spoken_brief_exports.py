"""Sample-accurate chapter and immutable listening derivative contracts."""
import copy
import importlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from spoken_brief_compile import SpokenBriefError, canonical_digest, compile_source, run_directory
from spoken_brief_transport import assemble_wav, digest_file, write_json
from spoken_brief_fixture import wav_bytes


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('spoken_brief_exports'), 'listening export module is missing')
        self.module = importlib.import_module('spoken_brief_exports')
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name).resolve() / 'COMPRESSED.md'
        self.source.write_text('# First chapter\n\nA short paragraph.\n\n## Second chapter\n\nThe final sentence.', encoding='utf-8')
        self.manifest = compile_source(self.source)
        self.directory = run_directory(self.source, self.manifest['manifest_sha256']); self.directory.mkdir(parents=True)
        (self.directory / 'segments').mkdir()
        self.lengths = [481, 997, 2051, 43]
        entries = []
        for segment, count in zip(self.manifest['segments'], self.lengths):
            path = self.directory / 'segments' / (segment['id'] + '.wav'); path.write_bytes(wav_bytes(count, len(entries) + 1))
            entries.append({'id': segment['id'], 'path': path, 'pause_after_ms': segment['pause_after_ms'], 'expected_sha256': digest_file(path)})
        self.output = self.directory / 'COMPRESSED.spoken.wav'
        self.receipt = {'schema_version': 2, 'manifest_sha256': self.manifest['manifest_sha256'],
            'source': self.manifest['source'], 'speaker_id': self.manifest['speaker_id'],
            'studio': {'base_url': 'http://127.0.0.1:8765', 'identity': {'app': 'local-asset-studio', 'workspace': 'fixture', 'version': '1'}},
            'producer_sha256': 'c' * 64, 'projects': ['a' * 32], 'project_plans': [{'id': 'a' * 32, 'sha256': 'b' * 64}],
            'segments': [{key: segment[key] for key in ('id', 'text_sha256', 'pause_after_ms')} for segment in self.manifest['segments']],
            'output': assemble_wav(entries, self.output)}
        write_json(self.directory / 'manifest.json', self.manifest); self.save_receipt()

    def save_receipt(self):
        write_json(self.directory / 'receipt.json', self.receipt)

    def test_chapters_use_measured_samples_and_exact_pauses(self):
        result = self.module.inspect_run(self.directory)
        expected = self.lengths[0] + 31200 + self.lengths[1] + 31200
        self.assertEqual([0, expected], [x['start_sample'] for x in result['chapters']])
        self.assertEqual(self.receipt['output']['samples'], result['chapters'][-1]['end_sample'])
        self.assertEqual(self.lengths[0], result['segments'][0]['speech_end_sample'])
        self.assertEqual(self.lengths[0] + 31200, result['segments'][0]['end_sample'])
        self.assertEqual('Second chapter', result['chapters'][1]['title'])
        self.assertEqual(self.manifest['segments'][2]['text_sha256'], result['segments'][2]['text_sha256'])

    def test_preamble_and_split_heading_make_distinct_nonduplicated_chapters(self):
        segments = copy.deepcopy(self.manifest['segments'])
        segments[0]['kind'] = 'paragraph'; segments[1]['kind'] = 'heading'
        segments[2]['block'] = segments[1]['block']; segments[2]['kind'] = 'heading'
        self.manifest['segments'] = segments
        self.manifest['manifest_sha256'] = canonical_digest({k:v for k,v in self.manifest.items() if k != 'manifest_sha256'})
        self.receipt['manifest_sha256'] = self.manifest['manifest_sha256']
        write_json(self.directory / 'manifest.json', self.manifest); self.save_receipt()
        result = self.module.inspect_run(self.directory)
        self.assertEqual(2, len(result['chapters']))
        self.assertEqual('Introduction', result['chapters'][0]['title'])
        self.assertEqual('A short paragraph. Second chapter', result['chapters'][1]['title'])

    def test_inspection_never_needs_original_markdown_or_network(self):
        self.source.unlink()
        with patch('spoken_brief_runtime.StudioClient', side_effect=AssertionError('No TTS')):
            self.assertEqual(4, len(self.module.inspect_run(self.directory)['segments']))
        self.assertFalse((self.directory / 'exports').exists())

    def test_tampered_archival_wav_is_refused(self):
        self.output.write_bytes(wav_bytes(50))
        with self.assertRaises(SpokenBriefError): self.module.inspect_run(self.directory)

    def test_receipt_sample_lengths_cannot_forge_chapter_offsets(self):
        self.receipt['output']['inputs'][0]['samples'] += 10; self.save_receipt()
        with self.assertRaises(SpokenBriefError): self.module.inspect_run(self.directory)

    def test_receipt_input_pcm_must_match_master_even_with_rehashed_receipt(self):
        path = Path(self.receipt['output']['inputs'][0]['path']); path.write_bytes(wav_bytes(self.lengths[0], 12))
        self.receipt['output']['inputs'][0]['sha256'] = digest_file(path); self.save_receipt()
        with self.assertRaises(SpokenBriefError): self.module.inspect_run(self.directory)

    def test_manifest_receipt_text_and_pause_bindings_are_enforced(self):
        for key, value in [('text_sha256', 'f' * 64), ('pause_after_ms', 0), ('id', 'segment-9999')]:
            with self.subTest(key=key):
                prior = self.receipt['segments'][0][key]; self.receipt['segments'][0][key] = value; self.save_receipt()
                with self.assertRaises(SpokenBriefError): self.module.inspect_run(self.directory)
                self.receipt['segments'][0][key] = prior

    def test_corrupt_manifest_digest_is_refused(self):
        self.manifest['segments'][0]['text'] = 'Changed text.'
        write_json(self.directory / 'manifest.json', self.manifest)
        with self.assertRaises(SpokenBriefError): self.module.inspect_run(self.directory)

    def test_duplicate_json_keys_are_refused(self):
        path = self.directory / 'receipt.json'; path.write_text('{"schema_version":2,"schema_version":2}', encoding='utf-8')
        with self.assertRaises(SpokenBriefError): self.module.inspect_run(self.directory)

    def test_receipt_cannot_redirect_master_or_segment_paths(self):
        for record in [self.receipt['output'], self.receipt['output']['inputs'][0]]:
            original = record['path']; record['path'] = str(self.source); self.save_receipt()
            with self.assertRaises(SpokenBriefError): self.module.inspect_run(self.directory)
            record['path'] = original

    def test_linked_master_is_refused(self):
        outside = self.source.with_suffix('.wav'); shutil.copyfile(self.output, outside); self.output.unlink()
        try: self.output.symlink_to(outside)
        except OSError: self.skipTest('Symlink privilege unavailable')
        with self.assertRaises(SpokenBriefError): self.module.inspect_run(self.directory)

    def test_chapter_export_is_deterministic_and_repeat_is_read_only(self):
        result = self.module.export_run(self.directory)
        export = Path(result['directory']); before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in export.iterdir()}
        with patch.object(self.module, '_run_tool', side_effect=AssertionError('No process')):
            again = self.module.export_run(self.directory)
        self.assertTrue(again['reused']); self.assertEqual(result['directory'], again['directory'])
        self.assertEqual(before, {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in export.iterdir()})
        self.assertIn('TIMEBASE=1/48000', (export / 'chapters.ffmeta').read_text(encoding='utf-8'))
        self.assertEqual(self.receipt['output']['sha256'], digest_file(self.output))

    def test_metadata_escaping_cannot_inject_an_extra_chapter(self):
        sidecar = self.module.inspect_run(self.directory)
        sidecar['chapters'][0]['title'] = 'a=b;#\\\n[CHAPTER]\nSTART=0'
        text = self.module.ffmetadata(sidecar)
        self.assertIn('title=a\\=b\\;\\#\\\\\\\n[CHAPTER]\\\nSTART\\=0', text)

    def test_partial_existing_export_is_never_silently_replaced(self):
        result = self.module.export_run(self.directory); export = Path(result['directory'])
        (export / 'chapters.json').write_text('{}', encoding='utf-8')
        with self.assertRaises(SpokenBriefError): self.module.export_run(self.directory)
        self.assertEqual('{}', (export / 'chapters.json').read_text(encoding='utf-8'))

    def test_failed_publication_preserves_master_and_all_prior_exports(self):
        before = self.output.read_bytes()
        with patch.object(self.module.os, 'rename', side_effect=OSError('disk failure')):
            with self.assertRaises(SpokenBriefError): self.module.export_run(self.directory)
        self.assertEqual(before, self.output.read_bytes())
        self.assertFalse(list((self.directory / 'exports').iterdir()))
        self.assertFalse((self.directory / '.spoken-brief.lock').exists())

    def test_lossy_export_requires_explicit_tool_and_full_hash_before_writes(self):
        for kwargs in [{'format': 'mp3'}, {'format': 'm4b', 'ffmpeg': sys.executable, 'ffmpeg_sha256': 'bad'}]:
            with self.assertRaises(SpokenBriefError): self.module.export_run(self.directory, **kwargs)
        self.assertFalse((self.directory / 'exports').exists())

    def test_wrong_tool_hash_never_executes(self):
        with patch.object(self.module, '_run_tool', side_effect=AssertionError('No process')):
            with self.assertRaises(SpokenBriefError): self.module.export_run(self.directory, format='mp3', ffmpeg=sys.executable, ffmpeg_sha256='0' * 64)
        self.assertFalse(list((self.directory / 'exports').glob('*')))

    def test_playback_defaults_are_read_only_and_updates_are_separate(self):
        receipt = (self.directory / 'receipt.json').read_bytes()
        self.assertEqual(0, self.module.load_playback(self.directory)['sample'])
        self.assertFalse((self.directory / 'playback.json').exists())
        self.module.save_playback(self.directory, sample=481, rate=1.25, loop=[20, 800])
        reloaded = self.module.load_playback(self.directory)
        self.assertEqual(481, reloaded['sample']); self.assertEqual([20, 800], reloaded['loop'])
        self.assertEqual(receipt, (self.directory / 'receipt.json').read_bytes())

    def test_invalid_playback_never_overwrites_previous_state(self):
        self.module.save_playback(self.directory, sample=10)
        before = (self.directory / 'playback.json').read_bytes()
        for kwargs in [{'sample': -1}, {'sample': True}, {'sample': 999999999}, {'sample': 0, 'rate': float('nan')}, {'sample': 0, 'loop': [100, 10]}]:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(SpokenBriefError): self.module.save_playback(self.directory, **kwargs)
                self.assertEqual(before, (self.directory / 'playback.json').read_bytes())

    def test_playback_cannot_be_rebound_to_different_audio(self):
        self.module.save_playback(self.directory, sample=5)
        path = self.directory / 'playback.json'; value = json.loads(path.read_text(encoding='utf-8')); value['master_sha256'] = '0' * 64
        write_json(path, value)
        with self.assertRaises(SpokenBriefError): self.module.load_playback(self.directory)

    @unittest.skipUnless(shutil.which('ffmpeg'), 'Installed FFmpeg required for real synthetic encode/decode')
    def test_real_mp3_and_m4b_encode_decode_and_reuse_without_tts(self):
        binary = Path(shutil.which('ffmpeg')).resolve(); pin = digest_file(binary)
        for format in ('mp3', 'm4b'):
            with self.subTest(format=format), patch('spoken_brief_runtime.StudioClient', side_effect=AssertionError('No TTS')):
                result = self.module.export_run(self.directory, format=format, ffmpeg=binary, ffmpeg_sha256=pin)
                path = Path(result['directory']); receipt = json.loads((path / 'receipt.json').read_text(encoding='utf-8'))
                self.assertEqual(pin, receipt['tool']['sha256']); self.assertIn('ffmpeg version', receipt['tool']['version'])
                self.assertLessEqual(abs(receipt['decoded']['samples'] - self.receipt['output']['samples']), 2400)
                self.assertTrue((path / ('listening.' + format)).is_file())
                with patch.object(self.module, '_run_tool', side_effect=AssertionError('No repeat encoding')):
                    self.assertTrue(self.module.export_run(self.directory, format=format, ffmpeg=binary, ffmpeg_sha256=pin)['reused'])


    def test_staged_artifact_change_during_final_flush_blocks_publication(self):
        original = os.fsync; changed = False
        def change(descriptor):
            nonlocal changed
            original(descriptor)
            for stage in (self.directory / 'exports').glob('.export-*'):
                if not changed and (stage / 'receipt.json').exists():
                    changed = True; (stage / 'chapters.ffmeta').write_bytes(b'Changed bytes')
        with patch.object(self.module.os, 'fsync', side_effect=change):
            with self.assertRaises(SpokenBriefError): self.module.export_run(self.directory)
        self.assertTrue(changed)
        self.assertFalse(list((self.directory / 'exports').iterdir()))
        self.assertEqual(self.receipt['output']['sha256'], digest_file(self.output))

    def test_boolean_pauses_cannot_alias_numeric_receipt_identity(self):
        for record in (self.receipt['segments'][-1], self.receipt['output']['inputs'][-1]):
            with self.subTest(record=record):
                record['pause_after_ms'] = False; self.save_receipt()
                with self.assertRaises(SpokenBriefError): self.module.inspect_run(self.directory)
                record['pause_after_ms'] = 0

    def test_metadata_embeds_title_and_exact_identity_bindings(self):
        text = self.module.ffmetadata(self.module.inspect_run(self.directory))
        globals = text.split('[CHAPTER]', 1)[0]
        self.assertIn('title=First chapter', globals)
        self.assertIn(self.manifest['source']['sha256'], globals)
        self.assertIn(self.manifest['manifest_sha256'], globals)
        self.assertIn(self.receipt['producer_sha256'], globals)
        self.assertIn(self.receipt['output']['sha256'], globals)

    def test_rehashed_sidecar_cannot_be_reused_for_a_different_manifest(self):
        path = Path(self.module.export_run(self.directory)['directory'])
        sidecar = json.loads((path / 'chapters.json').read_text(encoding='utf-8'))
        sidecar['manifest_sha256'] = '0' * 64
        write_json(path / 'chapters.json', sidecar)
        receipt = json.loads((path / 'receipt.json').read_text(encoding='utf-8'))
        receipt['files']['chapters.json'] = {'sha256': digest_file(path / 'chapters.json'), 'bytes': (path / 'chapters.json').stat().st_size}
        receipt['receipt_sha256'] = canonical_digest({k:v for k,v in receipt.items() if k != 'receipt_sha256'})
        write_json(path / 'receipt.json', receipt)
        with self.assertRaises(SpokenBriefError): self.module.export_run(self.directory)

    def test_tool_is_rechecked_between_version_and_encode(self):
        binary = self.source.parent / 'owned-ffmpeg'; binary.write_bytes(b'owned tool')
        pin = digest_file(binary); calls = []
        def replace_after_version(argv, *args, **kwargs):
            calls.append(argv)
            if len(calls) > 1: raise AssertionError('A changed executable must never run')
            binary.write_bytes(b'different tool')
            return 'ffmpeg version synthetic-fixture'
        with patch.object(self.module, '_run_tool', side_effect=replace_after_version):
            with self.assertRaises(SpokenBriefError):
                self.module.export_run(self.directory, format='mp3', ffmpeg=binary, ffmpeg_sha256=pin)
        self.assertEqual(1, len(calls))
        self.assertFalse(list((self.directory / 'exports').iterdir()))

    @unittest.skipIf(os.name == 'nt', 'POSIX simulation; native Windows contract runs separately')
    def test_publication_flush_uses_writable_file_handles(self):
        import fcntl
        original = os.fsync
        def require_write(descriptor):
            if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
                if fcntl.fcntl(descriptor, fcntl.F_GETFL) & os.O_ACCMODE == os.O_RDONLY:
                    raise OSError('Windows FlushFileBuffers needs GENERIC_WRITE')
            original(descriptor)
        with patch.object(self.module.os, 'fsync', side_effect=require_write):
            self.module.export_run(self.directory)

    def test_playback_external_write_during_flush_is_not_overwritten(self):
        self.module.save_playback(self.directory, sample=10)
        path = self.directory / 'playback.json'; original = os.fsync; changed = False
        foreign = path.read_bytes() + b' '
        def change(descriptor):
            nonlocal changed
            original(descriptor)
            if not changed and list(self.directory.glob('.playback.json-*.tmp')):
                changed = True; path.write_bytes(foreign)
        with patch.object(self.module.os, 'fsync', side_effect=change):
            with self.assertRaises(SpokenBriefError): self.module.save_playback(self.directory, sample=20)
        self.assertTrue(changed)
        self.assertEqual(foreign, path.read_bytes())

    def test_boolean_schema_is_not_accepted_as_numeric_playback_version(self):
        self.module.save_playback(self.directory, sample=10)
        path = self.directory / 'playback.json'; value = json.loads(path.read_text(encoding='utf-8'))
        value['schema_version'] = True; write_json(path, value)
        with self.assertRaises(SpokenBriefError): self.module.load_playback(self.directory)

    def test_unheard_and_completed_states_do_not_mutate_generation_receipt(self):
        original = (self.directory / 'receipt.json').read_bytes()
        self.assertEqual('unheard', self.module.load_playback(self.directory)['status'])
        self.module.save_playback(self.directory, sample=self.receipt['output']['samples'])
        self.assertEqual('completed', self.module.load_playback(self.directory)['status'])
        self.assertEqual(original, (self.directory / 'receipt.json').read_bytes())

    def test_export_claim_blocks_before_any_process_or_artifact_mutation(self):
        (self.directory / '.spoken-brief.lock').write_text('Another owner', encoding='utf-8')
        with self.assertRaises(SpokenBriefError): self.module.export_run(self.directory)
        self.assertFalse((self.directory / 'exports').exists())
        self.assertEqual('Another owner', (self.directory / '.spoken-brief.lock').read_text(encoding='utf-8'))

    def test_failed_derivative_preserves_an_earlier_valid_export(self):
        prior = Path(self.module.export_run(self.directory)['directory'])
        hashes = {p.name: digest_file(p) for p in prior.iterdir()}
        with patch.object(self.module, '_run_tool', side_effect=SpokenBriefError('Encoder failed')):
            with self.assertRaises(SpokenBriefError):
                self.module.export_run(self.directory, format='mp3', ffmpeg=Path(sys.executable).resolve(), ffmpeg_sha256=digest_file(Path(sys.executable).resolve()))
        self.assertEqual(hashes, {p.name: digest_file(p) for p in prior.iterdir()})
        self.assertEqual([prior], list((self.directory / 'exports').iterdir()))

    def test_owned_child_timeout_and_log_limit_are_visible_failures(self):
        with self.assertRaisesRegex(SpokenBriefError, 'time budget'):
            self.module._run_tool([sys.executable, '-c', 'import time; time.sleep(30)'], self.directory, timeout=0.05)
        with patch.object(self.module, 'MAX_LOG_BYTES', 1024):
            with self.assertRaisesRegex(SpokenBriefError, 'log byte'):
                self.module._run_tool([sys.executable, '-c', 'print("x" * 100000)'], self.directory, timeout=5)

    def test_archive_generated_by_existing_coordinator_exports_without_new_requests(self):
        import spoken_brief_runtime
        from spoken_brief_fixture import Fixture
        fixture = Fixture(); self.addCleanup(fixture.close)
        pack = self.source.parent / 'fresh'; pack.mkdir()
        (pack / 'COMPRESSED.md').write_text('# Real coordinator fixture\n\nOne sentence.', encoding='utf-8')
        result = spoken_brief_runtime.run(pack, base_url=fixture.base_url, poll_seconds=0.01, deadline_seconds=5)
        before = len(fixture.requests)
        export = self.module.export_run(Path(result['receipt']).parent)
        self.assertTrue(Path(export['receipt']).is_file())
        self.assertEqual(before, len(fixture.requests))

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'Installed FFmpeg and FFprobe required')
    def test_high_preset_retains_embedded_chapters_and_identity_in_actual_containers(self):
        binary = Path(shutil.which('ffmpeg')).resolve()
        expected = self.module.inspect_run(self.directory)
        for format in ('mp3', 'm4b'):
            result = self.module.export_run(self.directory, format=format, preset='high', ffmpeg=binary, ffmpeg_sha256=digest_file(binary))
            output = Path(result['directory']) / ('listening.' + format)
            probe = subprocess.run([shutil.which('ffprobe'), '-v', 'error', '-show_chapters', '-show_format', '-of', 'json', str(output)], capture_output=True, check=True, timeout=15)
            metadata = json.loads(probe.stdout)
            self.assertEqual(len(expected['chapters']), len(metadata['chapters']))
            for measured, embedded in zip(expected['chapters'], metadata['chapters']):
                self.assertLessEqual(abs(float(embedded['start_time']) * 48000 - measured['start_sample']), 48)
                self.assertEqual(measured['title'], embedded['tags']['title'])
            self.assertIn(self.manifest['manifest_sha256'], json.dumps(metadata['format']['tags']))


if __name__ == '__main__': unittest.main()
