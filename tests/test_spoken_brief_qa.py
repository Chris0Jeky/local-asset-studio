"""Independent transcript evidence is not a listening decision or inference authority."""
import copy
import importlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from spoken_brief_compile import SpokenBriefError, canonical_digest, compile_source, run_directory
from spoken_brief_transport import assemble_wav, digest_file, write_json
from spoken_brief_fixture import wav_bytes, Fixture


def lexicon(entries=None):
    return {'schema_version': 1, 'id': 'test-lexicon', 'revision': 1, 'entries': entries or []}


class TranscriptTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('spoken_brief_transcript'), 'Transcript comparator is missing')
        self.m = importlib.import_module('spoken_brief_transcript')

    def test_exact_and_punctuation_match(self):
        result = self.m.compare_text('Hello, WORLD!', 'hello world')
        self.assertEqual('match', result['status']); self.assertEqual([], result['edits'])
        self.assertEqual(0, result['word_error_rate'])

    def test_word_substitution_insertion_and_deletion(self):
        for expected, actual, kind in [('a red door', 'a blue door', 'substitution'),
                                       ('a door', 'a red door', 'insertion'),
                                       ('a red door', 'a door', 'deletion')]:
            with self.subTest(kind=kind):
                result = self.m.compare_text(expected, actual)
                self.assertEqual('differences', result['status'])
                self.assertEqual([kind], [x['op'] for x in result['edits']])
                self.assertEqual(1, result['counts'][kind])

    def test_empty_transcription_is_not_a_success(self):
        result = self.m.compare_text('one two', '...')
        self.assertEqual('empty', result['status']); self.assertEqual(2, result['counts']['deletion'])
        self.assertEqual(1, result['word_error_rate'])

    def test_numbers_unicode_and_meaningful_signs(self):
        self.assertEqual('match', self.m.compare_text('１２, 1,000 and 2.5%', 'twelve one thousand and two point five percent')['status'])
        self.assertEqual('match', self.m.compare_text('-7 and 007', 'minus seven and zero zero seven')['status'])
        self.assertEqual('differences', self.m.compare_text('-7', '7')['status'])
        self.assertEqual('differences', self.m.compare_text("don't go", 'do go')['status'])

    def test_longest_lexicon_match_and_no_recursive_rewrite(self):
        book = lexicon([{'written': 'LAS', 'spoken': 'local asset studio'},
                        {'written': 'LAS UI', 'spoken': 'studio interface'},
                        {'written': 'studio interface', 'spoken': 'another phrase'}])
        self.assertEqual(['studio', 'interface'], self.m.normalize('LAS UI', book))
        self.assertEqual(['local', 'asset', 'studio'], self.m.normalize('LAS', book))

    def test_lexicon_rejects_ambiguous_empty_and_unversioned_entries(self):
        for book in [lexicon([{'written': 'LAS', 'spoken': 'a'}, {'written': 'las!', 'spoken': 'b'}]),
                     lexicon([{'written': 'x', 'spoken': ''}]),
                     {**lexicon(), 'revision': True}, {**lexicon(), 'unknown': 1}]:
            with self.subTest(book=book), self.assertRaises(SpokenBriefError): self.m.normalize('LAS', book)

    def test_alignment_budget_withholds_score_instead_of_truncating(self):
        with patch.object(self.m, 'MAX_ALIGNMENT_CELLS', 8):
            result = self.m.compare_text('one two three', 'one four three')
        self.assertEqual('unaligned-budget', result['status']); self.assertIsNone(result['word_error_rate'])
        self.assertIsNone(result['counts']); self.assertEqual([], result['edits'])

    def test_exact_long_transcript_avoids_quadratic_alignment(self):
        with patch.object(self.m, 'MAX_ALIGNMENT_CELLS', 1):
            self.assertEqual('match', self.m.compare_text('word ' * 3000, 'word ' * 3000)['status'])

    def test_alignment_tie_break_and_indexes_are_deterministic(self):
        result = self.m.compare_text('a b', 'b a')
        self.assertEqual(result, self.m.compare_text('a b', 'b a'))
        self.assertEqual(2, result['counts']['substitution'])
        self.assertEqual([0, 1], [x['expected_index'] for x in result['edits']])

    def test_invalid_and_oversized_inputs_fail_closed(self):
        for value in [None, 1, 'x\0', '\ud800', 'x' * 200001]:
            with self.subTest(value=str(value)[:20]), self.assertRaises(SpokenBriefError): self.m.normalize(value)


class QATests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('spoken_brief_qa'), 'QA report module is missing')
        self.m = importlib.import_module('spoken_brief_qa')
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name).resolve() / 'COMPRESSED.md'
        self.source.write_text('# Brief\n\nLAS has 17 checks.\n\nKeep the old audio.', encoding='utf-8')
        self.manifest = compile_source(self.source); self.directory = run_directory(self.source, self.manifest['manifest_sha256'])
        self.directory.mkdir(parents=True); (self.directory / 'segments').mkdir()
        entries = []
        for i, s in enumerate(self.manifest['segments']):
            p = self.directory / 'segments' / (s['id'] + '.wav'); p.write_bytes(wav_bytes(500 + i, i))
            entries.append({'id': s['id'], 'path': p, 'pause_after_ms': s['pause_after_ms'], 'expected_sha256': digest_file(p)})
        receipt = {'schema_version': 2, 'manifest_sha256': self.manifest['manifest_sha256'], 'source': self.manifest['source'],
            'speaker_id': self.manifest['speaker_id'], 'studio': {'base_url': 'http://127.0.0.1:8765',
            'identity': {'app': 'local-asset-studio', 'workspace': 'fixture', 'version': '1'}},
            'producer_sha256': 'a' * 64, 'projects': ['b' * 32], 'project_plans': [{'id': 'b' * 32, 'sha256': 'c' * 64}],
            'segments': [{k: s[k] for k in ('id', 'text_sha256', 'pause_after_ms')} for s in self.manifest['segments']],
            'output': assemble_wav(entries, self.directory / 'COMPRESSED.spoken.wav')}
        write_json(self.directory / 'manifest.json', self.manifest); write_json(self.directory / 'receipt.json', receipt)
        self.archive = self.m.inspect_run(self.directory)
        self.evidence = {'schema_version': 1, 'manifest_sha256': self.archive['manifest_sha256'],
                         'master_sha256': self.archive['master']['sha256'], 'observations': []}
        self.findings = {x: 'not-reviewed' for x in ('pronunciation', 'omissions_repetitions', 'delivery', 'fatigue')}

    def observation(self, index=1, text=None, method='independent-asr'):
        s = self.archive['segments'][index]
        return {'target': s['id'], 'audio_sha256': s['audio_sha256'], 'text': s['text'] if text is None else text,
            'method': method, 'producer': {'id': 'offline-fixture', 'revision': 'fixture-v1',
            'runtime_sha256': 'd' * 64, 'configuration_sha256': 'e' * 64}}

    def report(self):
        return self.m.build_report(self.archive, self.evidence)

    def review(self, **kwargs):
        s = self.archive['segments'][1]
        return self.m.record_review(self.directory, s['id'], s['audio_sha256'], decision='replace',
            findings=self.findings, reviewer='owner', reason='The acronym needs listening correction.', **kwargs)

    def test_partial_evidence_does_not_hide_untranscribed_segments(self):
        self.evidence['observations'] = [self.observation()]
        report = self.report()
        self.assertEqual(['not-transcribed', 'match', 'not-transcribed', 'not-transcribed'],
                         [x['transcript_status'] for x in report['targets']])
        self.assertTrue(all(x['listening_status'] == 'unreviewed' for x in report['targets']))
        self.assertEqual(3, len(report['review_targets']))

    def test_master_observation_is_bound_to_actual_master(self):
        obs = self.observation(); obs.update(target='master', audio_sha256=self.archive['master']['sha256'],
                                            text=' '.join(s['text'] for s in self.archive['segments']))
        self.evidence['observations'] = [obs]
        self.assertEqual('match', self.report()['targets'][-1]['transcript_status'])
        obs['audio_sha256'] = 'f' * 64
        with self.assertRaises(SpokenBriefError): self.report()

    def test_wrong_segment_audio_text_target_and_duplicate_evidence_fail(self):
        for mutate in [lambda o: o.update(audio_sha256='f' * 64), lambda o: o.update(target='../source'),
                       lambda o: o.update(text=None), lambda o: o.update(approval=True),
                       lambda o: o['producer'].update(runtime_sha256='not-a-hash')]:
            self.evidence['observations'] = [self.observation()]; mutate(self.evidence['observations'][0])
            with self.assertRaises(SpokenBriefError): self.report()
        self.evidence['observations'] = [self.observation(), self.observation()]
        with self.assertRaises(SpokenBriefError): self.report()

    def test_forced_alignment_is_never_transcript_accuracy(self):
        self.evidence['observations'] = [self.observation(method='forced-alignment')]
        target = self.report()['targets'][1]
        self.assertEqual('not-independent', target['transcript_status']); self.assertIsNone(target['comparison'])

    def test_lexicon_and_revision_bind_report_without_rewriting_source(self):
        self.evidence['observations'] = [self.observation(text='Local asset studio has seventeen checks.')]
        book = lexicon([{'written': 'LAS', 'spoken': 'local asset studio'}])
        report = self.m.build_report(self.archive, self.evidence, book)
        self.assertEqual('match', report['targets'][1]['transcript_status'])
        book['revision'] += 1
        self.assertNotEqual(report['report_sha256'], self.m.build_report(self.archive, self.evidence, book)['report_sha256'])
        self.assertEqual(self.manifest['segments'][1]['text'], report['targets'][1]['intended_text'])

    def test_report_read_and_compare_have_no_filesystem_or_network_side_effects(self):
        with patch('spoken_brief_runtime.StudioClient', side_effect=AssertionError('No inference')):
            self.report()
        self.assertFalse((self.directory / 'qa').exists())

    def test_save_and_replay_are_immutable_and_read_only(self):
        before = (self.directory / 'receipt.json').read_bytes()
        first = self.m.save_report(self.directory, self.evidence); p = Path(first['path']); stamp = p.stat().st_mtime_ns
        again = self.m.save_report(self.directory, self.evidence)
        self.assertTrue(again['reused']); self.assertEqual(stamp, p.stat().st_mtime_ns)
        self.assertEqual(before, (self.directory / 'receipt.json').read_bytes())
        self.assertEqual(first['id'], self.m.load_report(self.directory, first['id'])['report_sha256'])

    def test_boolean_aliases_do_not_pass_persisted_report_or_review_validation(self):
        report = self.m.save_report(self.directory, self.evidence)
        review = self.review()
        for saved, loader in [(report, self.m.load_report), (review, self.m.load_review)]:
            p = Path(saved['path']); value = json.loads(p.read_bytes()); value['schema_version'] = True
            write_json(p, value)
            with self.assertRaises(SpokenBriefError): loader(self.directory, saved['id'])

    def test_manual_transcript_is_evidence_not_machine_or_owner_acceptance(self):
        obs = self.observation(method='manual-transcript')
        obs['producer'].update(runtime_sha256=None, configuration_sha256=None)
        self.evidence['observations'] = [obs]
        self.assertEqual('match', self.report()['targets'][1]['transcript_status'])
        self.assertEqual('unreviewed', self.report()['targets'][1]['listening_status'])
        obs['producer']['runtime_sha256'] = 'e' * 64
        with self.assertRaises(SpokenBriefError): self.report()

    def test_existing_claim_blocks_a_second_writer_without_mutating_records(self):
        from spoken_brief_transport import acquire_run_claim, release_run_claim
        claim = acquire_run_claim(self.directory, self.archive['manifest_sha256'])
        try:
            with self.assertRaises(SpokenBriefError): self.m.save_report(self.directory, self.evidence)
            self.assertFalse((self.directory / 'qa').exists())
        finally: release_run_claim(claim)

    def test_no_overwrite_publication_preserves_racing_record(self):
        real_link = self.m.os.link
        def race(source, target):
            Path(target).write_bytes(b'external record')
            return real_link(source, target)
        with patch.object(self.m.os, 'link', side_effect=race):
            with self.assertRaises(SpokenBriefError): self.m.save_report(self.directory, self.evidence)
        self.assertEqual([b'external record'], [p.read_bytes() for p in self.directory.glob('qa/reports/*.json')])

    def test_changed_evidence_preserves_previous_report(self):
        first = self.m.save_report(self.directory, self.evidence); old = Path(first['path']).read_bytes()
        self.evidence['observations'] = [self.observation(text='Wrong words.')]
        second = self.m.save_report(self.directory, self.evidence)
        self.assertNotEqual(first['id'], second['id']); self.assertEqual(old, Path(first['path']).read_bytes())

    def test_rehashed_forged_report_status_cannot_masquerade_as_comparison(self):
        saved = self.m.save_report(self.directory, self.evidence); p = Path(saved['path']); report = json.loads(p.read_bytes())
        report['targets'][0]['transcript_status'] = 'match'
        report['report_sha256'] = canonical_digest({k: v for k,v in report.items() if k != 'report_sha256'})
        forged = p.with_name(report['report_sha256'] + '.json'); write_json(forged, report)
        with self.assertRaises(SpokenBriefError): self.m.load_report(self.directory, report['report_sha256'])

    def test_bounded_empty_master_report_saves_and_reloads(self):
        transcript = importlib.import_module('spoken_brief_transcript')
        from spoken_brief_exports import _json_bytes
        master_text = ('a ' * 16000).strip()
        archive = {'manifest_sha256': 'a' * 64, 'manifest_file_sha256': 'b' * 64,
            'assembly_receipt_sha256': 'c' * 64, 'producer_sha256': 'd' * 64,
            'source': {'sha256': 'e' * 64}, 'master': {'sha256': 'f' * 64},
            'segments': [{'id': 's1', 'text': master_text, 'audio_sha256': '0' * 64}]}
        evidence = {'schema_version': 1, 'manifest_sha256': archive['manifest_sha256'],
            'master_sha256': archive['master']['sha256'], 'observations': [
            {'target': 'master', 'audio_sha256': archive['master']['sha256'], 'text': '',
             'method': 'independent-asr', 'producer': {'id': 'offline-fixture', 'revision': 'fixture-v1',
             'runtime_sha256': 'd' * 64, 'configuration_sha256': 'e' * 64}}]}
        # Causal baseline: the legacy full-edit encoding cannot fit the 2 MiB record bound.
        full = transcript.compare_text(master_text, '')
        self.assertEqual('empty', full['status']); self.assertEqual(16000, full['counts']['deletion'])
        with self.assertRaises(SpokenBriefError):
            _json_bytes(full)
        report = self.m.build_report(archive, evidence)
        master = report['targets'][-1]
        self.assertEqual('empty', master['transcript_status']); self.assertEqual('unreviewed', master['listening_status'])
        self.assertEqual(16000, master['comparison']['counts']['deletion'])
        self.assertEqual(1, master['comparison']['word_error_rate'])
        self.assertEqual(64, len(master['comparison']['edits']))
        self.assertEqual(16000 - 64, master['comparison']['edits_omitted'])
        self.assertEqual(report['report_sha256'], self.m.build_report(archive, evidence)['report_sha256'])
        with patch.object(self.m, 'inspect_run', return_value=archive):
            first = self.m.save_report(self.directory, evidence)
            self.assertEqual(report['report_sha256'], first['id'])
            loaded = self.m.load_report(self.directory, first['id'])
            self.assertEqual(first['id'], loaded['report_sha256'])
            self.assertEqual(16000, loaded['targets'][-1]['comparison']['counts']['deletion'])
            self.assertEqual(16000 - 64, loaded['targets'][-1]['comparison']['edits_omitted'])
            self.assertEqual('empty', loaded['targets'][-1]['transcript_status'])
            again = self.m.save_report(self.directory, evidence)
            self.assertTrue(again['reused']); self.assertEqual(first['id'], again['id'])

    def test_legacy_full_edit_report_still_loads(self):
        transcript = importlib.import_module('spoken_brief_transcript')
        master_text = ('a ' * 100).strip()
        archive = {'manifest_sha256': 'a' * 64, 'manifest_file_sha256': 'b' * 64,
            'assembly_receipt_sha256': 'c' * 64, 'producer_sha256': 'd' * 64,
            'source': {'sha256': 'e' * 64}, 'master': {'sha256': 'f' * 64},
            'segments': [{'id': 's1', 'text': master_text, 'audio_sha256': '1' * 64}]}
        evidence = {'schema_version': 1, 'manifest_sha256': archive['manifest_sha256'],
            'master_sha256': archive['master']['sha256'], 'observations': [
            {'target': 'master', 'audio_sha256': archive['master']['sha256'], 'text': '',
             'method': 'independent-asr', 'producer': {'id': 'offline-fixture', 'revision': 'fixture-v1',
             'runtime_sha256': 'd' * 64, 'configuration_sha256': 'e' * 64}}]}
        bounded = self.m.build_report(archive, evidence)
        self.assertEqual(64, len(bounded['targets'][-1]['comparison']['edits']))
        # Reconstruct the genuine pre-change record: full edits, no omission marker.
        full = transcript.compare_text(master_text, '')
        self.assertEqual(100, len(full['edits'])); self.assertNotIn('edits_omitted', full)
        legacy = copy.deepcopy(bounded)
        legacy['targets'][-1]['comparison'] = full
        del legacy['report_sha256']
        legacy['report_sha256'] = canonical_digest({k: v for k, v in legacy.items() if k != 'report_sha256'})
        write_json(self.directory / 'qa' / 'reports' / (legacy['report_sha256'] + '.json'), legacy)
        with patch.object(self.m, 'inspect_run', return_value=archive):
            loaded = self.m.load_report(self.directory, legacy['report_sha256'])
        self.assertEqual(100, len(loaded['targets'][-1]['comparison']['edits']))
        self.assertNotIn('edits_omitted', loaded['targets'][-1]['comparison'])
        self.assertEqual(100, loaded['targets'][-1]['comparison']['counts']['deletion'])
        self.assertEqual('empty', loaded['targets'][-1]['transcript_status'])

    def test_retained_per_target_bounded_report_still_loads(self):
        transcript = importlib.import_module('spoken_brief_transcript')
        text = ('a ' * 100).strip()
        archive = {'manifest_sha256': 'a' * 64, 'manifest_file_sha256': 'b' * 64,
            'assembly_receipt_sha256': 'c' * 64, 'producer_sha256': 'd' * 64,
            'source': {'sha256': 'e' * 64}, 'master': {'sha256': 'f' * 64},
            'segments': [{'id': f's{i}', 'text': text, 'audio_sha256': f'{i:064x}'} for i in (1, 2)]}
        producer = {'id': 'offline-fixture', 'revision': 'fixture-v1',
            'runtime_sha256': 'd' * 64, 'configuration_sha256': 'e' * 64}
        observations = [{'target': target, 'audio_sha256': audio_sha256, 'text': '',
            'method': 'independent-asr', 'producer': producer}
            for target, audio_sha256 in [('s1', f'{1:064x}'), ('s2', f'{2:064x}'),
                                         ('master', archive['master']['sha256'])]]
        evidence = {'schema_version': 1, 'manifest_sha256': archive['manifest_sha256'],
            'master_sha256': archive['master']['sha256'], 'observations': observations}
        retained = copy.deepcopy(self.m.build_report(archive, evidence))
        for target in retained['targets']:
            full = transcript.compare_text(target['intended_text'], '')
            target['comparison'] = self.m._bound_comparison(full, self.m.MAX_COMPARISON_EDITS)
        self.assertEqual(3 * 64, sum(len(t['comparison']['edits']) for t in retained['targets']))
        del retained['report_sha256']
        retained['report_sha256'] = canonical_digest(retained)
        write_json(self.directory / 'qa' / 'reports' / (retained['report_sha256'] + '.json'), retained)
        with patch.object(self.m, 'inspect_run', return_value=archive):
            self.assertEqual(retained, self.m.load_report(self.directory, retained['report_sha256']))

    def test_many_empty_segments_share_one_report_edit_budget(self):
        from spoken_brief_exports import _json_bytes
        from spoken_brief_transport import MAX_JSON_BYTES
        segments = [{'id': f's{i:03}', 'text': ('a ' * 66).strip(),
                     'audio_sha256': f'{i:064x}'} for i in range(240)]
        archive = {'manifest_sha256': 'a' * 64, 'manifest_file_sha256': 'b' * 64,
            'assembly_receipt_sha256': 'c' * 64, 'producer_sha256': 'd' * 64,
            'source': {'sha256': 'e' * 64}, 'master': {'sha256': 'f' * 64},
            'segments': segments}
        producer = {'id': 'offline-fixture', 'revision': 'fixture-v1',
            'runtime_sha256': 'd' * 64, 'configuration_sha256': 'e' * 64}
        observations = [{'target': segment['id'], 'audio_sha256': segment['audio_sha256'],
            'text': '', 'method': 'independent-asr', 'producer': producer} for segment in segments]
        observations.append({'target': 'master', 'audio_sha256': archive['master']['sha256'],
            'text': '', 'method': 'independent-asr', 'producer': producer})
        evidence = {'schema_version': 1, 'manifest_sha256': archive['manifest_sha256'],
            'master_sha256': archive['master']['sha256'], 'observations': observations}
        report = self.m.build_report(archive, evidence)
        comparisons = [target['comparison'] for target in report['targets']]
        self.assertEqual(15840, comparisons[-1]['counts']['deletion'])
        self.assertTrue(all(target['transcript_status'] == 'empty' for target in report['targets']))
        self.assertEqual(64, sum(len(value['edits']) for value in comparisons))
        self.assertEqual(31680 - 64, sum(value.get('edits_omitted', 0) for value in comparisons))
        self.assertLessEqual(len(_json_bytes(report)), MAX_JSON_BYTES)
        with patch.object(self.m, 'inspect_run', return_value=archive):
            first = self.m.save_report(self.directory, evidence)
            loaded = self.m.load_report(self.directory, first['id'])
            self.assertEqual(report, loaded)
            self.assertTrue(self.m.save_report(self.directory, evidence)['reused'])

    def test_review_is_separate_and_exact_audio_bound(self):
        before = (self.directory / 'receipt.json').read_bytes(); saved = self.review()
        value = self.m.load_review(self.directory, saved['id'])
        self.assertEqual('replace', value['decision']); self.assertEqual(self.findings, value['findings'])
        self.assertEqual(before, (self.directory / 'receipt.json').read_bytes())
        self.assertEqual('unreviewed', self.report()['targets'][1]['listening_status'])
        self.assertTrue(self.review()['reused'])

    def test_review_must_reference_this_audio_and_valid_findings(self):
        s = self.archive['segments'][1]
        for audio, findings in [('f' * 64, self.findings), (s['audio_sha256'], {'pronunciation': 'good'})]:
            with self.assertRaises(SpokenBriefError):
                self.m.record_review(self.directory, s['id'], audio, decision='replace', findings=findings,
                                     reviewer='owner', reason='review')
        self.assertFalse((self.directory / 'qa').exists())

    def test_review_can_link_report_but_cannot_inherit_machine_acceptance(self):
        report = self.m.save_report(self.directory, self.evidence)
        review = self.review(report_sha256=report['id'])
        self.assertEqual(report['id'], self.m.load_review(self.directory, review['id'])['report_sha256'])
        with self.assertRaises(SpokenBriefError): self.review(report_sha256='f' * 64)

    def test_quota_refuses_new_records_without_pruning_or_blocking_replay(self):
        saved = self.m.save_report(self.directory, self.evidence)
        with patch.object(self.m, 'MAX_RECORDS', 1):
            self.assertTrue(self.m.save_report(self.directory, self.evidence)['reused'])
            self.evidence['observations'] = [self.observation()]
            with self.assertRaises(SpokenBriefError): self.m.save_report(self.directory, self.evidence)
        self.assertTrue(Path(saved['path']).is_file())

    def test_linked_record_directory_is_refused(self):
        outside = self.source.parent / 'outside'; outside.mkdir()
        try: (self.directory / 'qa').symlink_to(outside, target_is_directory=True)
        except OSError: self.skipTest('Symlink privilege unavailable')
        with self.assertRaises(SpokenBriefError): self.m.save_report(self.directory, self.evidence)
        self.assertEqual([], list(outside.iterdir()))

    def test_failed_publication_preserves_existing_records(self):
        first = self.m.save_report(self.directory, self.evidence); before = Path(first['path']).read_bytes()
        self.evidence['observations'] = [self.observation()]
        with patch.object(self.m.os, 'link', side_effect=OSError('publication failed')):
            with self.assertRaises(SpokenBriefError): self.m.save_report(self.directory, self.evidence)
        self.assertEqual(before, Path(first['path']).read_bytes())

    def test_mutation_during_flush_never_publishes_corrupt_record(self):
        real_sync = self.m.os.fsync
        def mutate(fd):
            real_sync(fd)
            for p in self.directory.glob('qa/reports/.qa-*.tmp'): p.write_bytes(b'corrupt')
        with patch.object(self.m.os, 'fsync', side_effect=mutate):
            with self.assertRaises(SpokenBriefError): self.m.save_report(self.directory, self.evidence)
        self.assertEqual([], list(self.directory.glob('qa/reports/*.json')))

    def test_report_from_real_coordinator_archive_adds_no_requests(self):
        fixture = Fixture(); self.addCleanup(fixture.close)
        from spoken_brief_runtime import run
        other = self.source.parent / 'other.md'; other.write_text('An independent brief.', encoding='utf-8')
        result = run(other, base_url=fixture.base_url); requests = len(fixture.requests)
        directory = Path(result['receipt']).parent; a = self.m.inspect_run(directory)
        self.m.save_report(directory, {'schema_version': 1, 'manifest_sha256': a['manifest_sha256'],
                            'master_sha256': a['master']['sha256'], 'observations': []})
        self.assertEqual(requests, len(fixture.requests))


if __name__ == '__main__': unittest.main()
