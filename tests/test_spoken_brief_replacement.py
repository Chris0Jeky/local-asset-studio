"""Single-segment replacement must never erase history or replay uncertain inference."""
import copy
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from spoken_brief_archive import inspect_run
from spoken_brief_compile import SpokenBriefError, canonical_digest
from spoken_brief_fixture import Fixture, wav_bytes
from spoken_brief_qa import record_review, FINDINGS
from spoken_brief_runtime import run
from spoken_brief_transport import StudioClient, write_json


class ReplacementTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('spoken_brief_replacement'), 'Replacement coordinator is missing')
        self.m = importlib.import_module('spoken_brief_replacement')
        self.a = importlib.import_module('spoken_brief_reassembly')
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.fixture = Fixture(); self.addCleanup(self.fixture.close)
        self.source = Path(self.temp.name).resolve() / 'COMPRESSED.md'
        self.source.write_text('# Brief\n\nLAS has seventeen checks.\n\nKeep all other audio.', encoding='utf-8')
        result = run(self.source, base_url=self.fixture.base_url)
        self.directory = Path(result['receipt']).parent
        self.archive = inspect_run(self.directory); self.segment = self.archive['segments'][1]
        self.review = record_review(self.directory, self.segment['id'], self.segment['audio_sha256'],
            decision='replace', findings={k: 'needs-work' if k == 'pronunciation' else 'not-reviewed' for k in FINDINGS},
            reviewer='owner', reason='Please correct the project acronym.')['id']
        self.original = {str(p.relative_to(self.directory)): p.read_bytes() for p in self.directory.rglob('*') if p.is_file()}
        self.request_count = len(self.fixture.requests)

    def prepare(self, request_id='pronounce-v1', **kwargs):
        return self.m.prepare(self.directory, self.segment['id'], self.review, request_id, **kwargs)

    def state_path(self, request_id='pronounce-v1'):
        return self.directory / 'replacements' / request_id / 'state.json'

    def state(self, request_id='pronounce-v1'):
        return json.loads(self.state_path(request_id).read_bytes())

    def starts(self):
        return [r for r in self.fixture.requests[self.request_count:] if r[0] == 'POST' and r[1].endswith('/start')]

    def creates(self):
        return [r for r in self.fixture.requests[self.request_count:] if r[:2] == ('POST', '/api/voice-baseline')]

    def assert_original_intact(self):
        for name, raw in self.original.items():
            self.assertEqual(raw, (self.directory / name).read_bytes(), name)

    def test_prepare_is_zero_inference_durable_and_exact_replay(self):
        request = self.prepare(); before = self.state_path().read_bytes()
        self.assertEqual('prepared', self.state()['status'])
        self.assertEqual(request, self.prepare())
        self.assertEqual(before, self.state_path().read_bytes())
        self.assertEqual(self.request_count, len(self.fixture.requests))
        self.assert_original_intact()

    def test_changed_request_id_content_is_refused_without_mutation(self):
        self.prepare(); before = self.state_path().read_bytes()
        with self.assertRaises(SpokenBriefError): self.prepare(text='Different spoken words.')
        self.assertEqual(before, self.state_path().read_bytes()); self.assertEqual([], self.creates())

    def test_paths_and_non_replacement_review_are_refused(self):
        for name in ('../escape', 'bad/name', 'C:\\escape', '', True):
            with self.subTest(name=name), self.assertRaises(SpokenBriefError): self.prepare(name)
        kept = record_review(self.directory, self.segment['id'], self.segment['audio_sha256'], decision='keep',
            findings={k: 'acceptable' for k in FINDINGS}, reviewer='owner', reason='Keep this take.')['id']
        with self.assertRaises(SpokenBriefError): self.m.prepare(self.directory, self.segment['id'], kept, 'keep-v1')
        self.assertFalse((self.directory / 'replacements').exists())

    def test_one_explicit_replacement_reuses_every_other_segment(self):
        self.prepare(); take = self.m.start(self.directory, 'pronounce-v1')
        self.assertEqual('artifact-verified', take['state']['status'])
        result = self.a.assemble(self.directory, 'pronounce-v1'); updated = inspect_run(result['directory'])
        self.assertEqual(1, len(self.creates())); self.assertEqual(1, len(self.starts()))
        self.assertEqual([{'id': self.segment['id'], 'text': self.segment['text']}], self.creates()[0][3]['lines'])
        for old, new in zip(self.archive['segments'], updated['segments']):
            if old['id'] == self.segment['id']: self.assertNotEqual(old['audio_sha256'], new['audio_sha256'])
            else: self.assertEqual(old['audio_sha256'], new['audio_sha256'])
        self.assertNotEqual(updated['manifest_sha256'], self.archive['manifest_sha256'])
        self.assert_original_intact()

    def test_override_is_explicit_and_leaves_original_source_authoritative(self):
        text = 'Local asset studio has seventeen checks.'
        request = self.prepare(text=text)
        self.assertEqual(self.segment['text'], request['original_text']); self.assertEqual(text, request['text'])
        self.m.start(self.directory, 'pronounce-v1')
        result = self.a.assemble(self.directory, 'pronounce-v1')
        updated = inspect_run(result['directory'])
        self.assertEqual(text, updated['segments'][1]['text'])
        self.assertEqual(self.archive['source'], updated['source'])
        self.assert_original_intact()

    def test_invalid_override_never_creates_request(self):
        for text in ('', ' word ', 'a\nline', 'x\0', 'x' * 521, '\ud800'):
            with self.subTest(text=repr(text)[:20]), self.assertRaises(SpokenBriefError): self.prepare(text=text)
        self.assertFalse((self.directory / 'replacements').exists())

    def test_reassembly_and_completed_replay_are_offline_and_read_only(self):
        self.prepare(); self.m.start(self.directory, 'pronounce-v1')
        count = len(self.fixture.requests)
        with patch.object(self.m, 'StudioClient', side_effect=AssertionError('No transport for retained take')):
            first = self.a.assemble(self.directory, 'pronounce-v1')
            output = Path(first['directory']); before = {str(p): p.stat().st_mtime_ns for p in output.rglob('*') if p.is_file()}
            self.m.start(self.directory, 'pronounce-v1')
            self.assertTrue(self.a.assemble(self.directory, 'pronounce-v1')['reused'])
            self.assertEqual(before, {str(p): p.stat().st_mtime_ns for p in output.rglob('*') if p.is_file()})
        self.assertEqual(count, len(self.fixture.requests))

    def test_archived_replacement_does_not_require_live_original_markdown(self):
        self.source.unlink(); self.prepare(); self.m.start(self.directory, 'pronounce-v1')
        self.a.assemble(self.directory, 'pronounce-v1'); self.assertFalse(self.source.exists())

    def test_lost_create_response_blocks_same_and_different_request_ids(self):
        self.prepare(); real_post = StudioClient.post_json
        def lost(client, path, body):
            result = real_post(client, path, body)
            if path == '/api/voice-baseline': raise SpokenBriefError('Lost Create response')
            return result
        with patch.object(StudioClient, 'post_json', new=lost):
            with self.assertRaises(SpokenBriefError): self.m.start(self.directory, 'pronounce-v1')
        self.assertEqual('create-unconfirmed', self.state()['status'])
        with self.assertRaises(SpokenBriefError): self.m.start(self.directory, 'pronounce-v1')
        with self.assertRaises(SpokenBriefError): self.prepare('another-request')
        self.assertEqual(1, len(self.creates())); self.assertEqual([], self.starts())

    def test_lost_start_response_observes_known_child_without_reposting(self):
        self.prepare(); real_post = StudioClient.post_json
        def lost(client, path, body):
            result = real_post(client, path, body)
            if path.endswith('/start'): raise SpokenBriefError('Lost Start response')
            return result
        with patch.object(StudioClient, 'post_json', new=lost):
            with self.assertRaises(SpokenBriefError): self.m.start(self.directory, 'pronounce-v1')
        self.assertEqual('start-unconfirmed', self.state()['status']); self.assertIsNotNone(self.state()['project_id'])
        self.m.start(self.directory, 'pronounce-v1')
        self.assertEqual(1, len(self.creates())); self.assertEqual(1, len(self.starts()))
        self.a.assemble(self.directory, 'pronounce-v1')

    def test_start_intent_is_durable_before_post_and_planned_does_not_reauthorize(self):
        self.prepare(); real_post = StudioClient.post_json
        def before(client, path, body):
            if path.endswith('/start'):
                self.assertEqual('starting', self.state()['status']); self.assertIsNotNone(self.state()['project_id'])
                raise KeyboardInterrupt('Crash before Start acknowledgement')
            return real_post(client, path, body)
        with patch.object(StudioClient, 'post_json', new=before):
            with self.assertRaises(KeyboardInterrupt): self.m.start(self.directory, 'pronounce-v1')
        self.assertEqual('starting', self.state()['status'])
        with self.assertRaises(SpokenBriefError): self.m.start(self.directory, 'pronounce-v1')
        self.assertEqual(1, len(self.creates())); self.assertEqual([], self.starts())

    def test_retained_project_id_is_written_before_any_start(self):
        self.prepare()
        def after(project):
            self.assertEqual(project['id'], self.state()['project_id'])
            self.assertEqual('starting', self.state()['status'])
        self.fixture.after_start = after
        self.m.start(self.directory, 'pronounce-v1')

    def test_success_acknowledgements_are_not_project_authority(self):
        self.prepare(); self.fixture.create_response_override = {'id': f'{2:032x}', 'kind': 'wrong', 'plan': {}}
        self.fixture.start_response_override = {'kind': 'wrong'}
        self.m.start(self.directory, 'pronounce-v1')
        self.assertEqual(1, len(self.starts())); self.assertEqual('artifact-verified', self.state()['status'])

    def test_producer_drift_blocks_before_start_and_retains_child(self):
        self.prepare(); self.fixture.producer_revision = 'different-v2'
        with self.assertRaises(SpokenBriefError): self.m.start(self.directory, 'pronounce-v1')
        self.assertEqual(1, len(self.creates())); self.assertEqual([], self.starts())
        self.assertIsNotNone(self.state()['project_id'])
        with self.assertRaises(SpokenBriefError): self.prepare('new-id')

    def test_studio_identity_drift_blocks_before_create(self):
        self.prepare(); self.fixture.identity['workspace'] = 'other-workspace'
        with self.assertRaises(SpokenBriefError): self.m.start(self.directory, 'pronounce-v1')
        self.assertEqual([], self.creates()); self.assertEqual([], self.starts())

    def test_terminal_child_never_replaced_or_restarted(self):
        self.prepare(); self.fixture.after_start = lambda p: p['state'].update(status='failed')
        with self.assertRaises(SpokenBriefError): self.m.start(self.directory, 'pronounce-v1')
        self.assertEqual('terminal', self.state()['status'])
        with self.assertRaises(SpokenBriefError): self.m.start(self.directory, 'pronounce-v1')
        with self.assertRaises(SpokenBriefError): self.prepare('new-id')
        self.assertEqual(1, len(self.creates())); self.assertEqual(1, len(self.starts()))

    def test_invalid_artifact_and_plan_drift_preserve_old_audio(self):
        self.prepare(); self.fixture.mismatch_after_start = True
        with self.assertRaises(SpokenBriefError): self.m.start(self.directory, 'pronounce-v1')
        self.assert_original_intact()
        with self.assertRaises(SpokenBriefError): self.a.assemble(self.directory, 'pronounce-v1')

    def test_missing_or_corrupt_cached_take_does_not_trigger_new_inference(self):
        self.prepare(); self.m.start(self.directory, 'pronounce-v1')
        take = self.state_path().parent / 'take.wav'; take.write_bytes(wav_bytes(1, 0))
        count = len(self.fixture.requests)
        with self.assertRaises(SpokenBriefError): self.m.start(self.directory, 'pronounce-v1')
        with self.assertRaises(SpokenBriefError): self.a.assemble(self.directory, 'pronounce-v1')
        self.assertEqual(count, len(self.fixture.requests)); self.assert_original_intact()

    def test_state_schema_alias_and_forged_profile_are_rejected(self):
        self.prepare(); path = self.state_path(); original = path.read_bytes()
        for mutate in [lambda s: s.update(schema_version=True), lambda s: s.update(request_sha256='f'*64),
                       lambda s: s.update(status='unknown'), lambda s: s.update(project_id='../escape')]:
            state = json.loads(original); mutate(state); write_json(path, state)
            with self.assertRaises(SpokenBriefError): self.m.inspect(self.directory, 'pronounce-v1')
        path.write_bytes(original)

    def test_failed_reassembly_preserves_old_receipts_and_valid_take(self):
        self.prepare(); self.m.start(self.directory, 'pronounce-v1')
        with patch.object(self.a, 'assemble_wav', side_effect=SpokenBriefError('Assembly failure')):
            with self.assertRaises(SpokenBriefError): self.a.assemble(self.directory, 'pronounce-v1')
        self.assert_original_intact()
        count = len(self.fixture.requests)
        self.a.assemble(self.directory, 'pronounce-v1')
        self.assertEqual(count, len(self.fixture.requests))

    def test_replacement_archive_exports_and_accepts_new_separate_review(self):
        from spoken_brief_exports import export_run
        self.prepare(); self.m.start(self.directory, 'pronounce-v1'); result = self.a.assemble(self.directory, 'pronounce-v1')
        count = len(self.fixture.requests); export_run(result['directory'])
        updated = inspect_run(result['directory']); target = updated['segments'][1]
        review = record_review(result['directory'], target['id'], target['audio_sha256'], decision='keep',
            findings={k: 'acceptable' for k in FINDINGS}, reviewer='owner', reason='Accepted this correction.')
        self.assertTrue(Path(review['path']).is_file()); self.assertEqual(count, len(self.fixture.requests))
        self.assert_original_intact()

    def test_linked_replacement_root_is_refused(self):
        outside = self.source.parent / 'outside'; outside.mkdir()
        try: (self.directory / 'replacements').symlink_to(outside, target_is_directory=True)
        except OSError: self.skipTest('Symlink privilege unavailable')
        with self.assertRaises(SpokenBriefError): self.prepare()
        self.assertEqual([], list(outside.iterdir())); self.assertEqual([], self.creates())


    def test_parent_change_during_identity_read_blocks_create(self):
        self.prepare()
        calls = 0
        def changed():
            nonlocal calls
            calls += 1
            if calls == 2:
                self.fixture.on_identity = None
                (self.directory / 'COMPRESSED.spoken.wav').write_bytes(wav_bytes(1, 9))
        self.fixture.on_identity = changed
        with self.assertRaises(SpokenBriefError): self.m.start(self.directory, 'pronounce-v1')
        self.assertEqual([], self.creates()); self.assertEqual([], self.starts())

    def test_child_plan_changed_during_download_is_not_published(self):
        self.prepare(); original = StudioClient.get_bytes
        def drift(client, route):
            raw = original(client, route)
            project = self.fixture.projects[self.state()['project_id']]
            project['plan']['lines'][0]['text'] = 'Changed after the canonical observation.'
            project['plan']['sha256'] = self.m.canonical_digest({k: v for k, v in project['plan'].items() if k != 'sha256'})
            return raw
        with patch.object(StudioClient, 'get_bytes', new=drift):
            with self.assertRaises(SpokenBriefError): self.m.start(self.directory, 'pronounce-v1')
        self.assertFalse((self.state_path().parent / 'take.wav').exists())
        self.assert_original_intact()

    def test_late_assembly_receipt_flush_mutation_cannot_publish_a_bad_archive(self):
        self.prepare(); self.m.start(self.directory, 'pronounce-v1')
        original = self.a.write_json
        def mutate(path, value):
            original(path, value)
            if path.name == 'receipt.json' and '/result/' in value['output']['path'].replace('\\', '/'):
                (path.parent / 'segments' / (self.segment['id'] + '.wav')).write_bytes(wav_bytes(480, 9))
        with patch.object(self.a, 'write_json', side_effect=mutate):
            with self.assertRaises(SpokenBriefError): self.a.assemble(self.directory, 'pronounce-v1')
        self.assertFalse((self.state_path().parent / 'result').exists())
        self.assert_original_intact()

    def test_observed_prepared_state_cannot_authorize_fresh_inference(self):
        self.prepare(); state = self.state(); state['last_observed_status'] = 'running'
        write_json(self.state_path(), state)
        with self.assertRaises(SpokenBriefError): self.m.start(self.directory, 'pronounce-v1')
        self.assertEqual([], self.creates())

    def test_project_history_limit_blocks_before_preparation_side_effects(self):
        with patch.object(self.m, 'MAX_PROJECTS', 1, create=True):
            with self.assertRaises(SpokenBriefError): self.prepare()
        self.assertFalse((self.directory / 'replacements').exists()); self.assertEqual([], self.creates())

    def test_failed_child_identity_persistence_retains_pre_create_intent(self):
        self.prepare(); original = self.m._save
        def fail(path, state, token, guard):
            if state['status'] == 'created': raise OSError('Cannot persist returned child ID')
            return original(path, state, token, guard)
        with patch.object(self.m, '_save', side_effect=fail):
            with self.assertRaises(OSError): self.m.start(self.directory, 'pronounce-v1')
        self.assertEqual('creating', self.state()['status'])
        with self.assertRaises(SpokenBriefError): self.m.start(self.directory, 'pronounce-v1')
        self.assertEqual(1, len(self.creates())); self.assertEqual([], self.starts())

    def test_cached_take_recovers_after_receipt_write_failure_without_new_start(self):
        self.prepare(); original = self.m._save
        def fail(path, state, token, guard):
            if state['status'] == 'artifact-verified': raise OSError('Cannot persist artifact receipt')
            return original(path, state, token, guard)
        with patch.object(self.m, '_save', side_effect=fail):
            with self.assertRaises(OSError): self.m.start(self.directory, 'pronounce-v1')
        self.assertTrue((self.state_path().parent / 'take.wav').is_file())
        self.m.start(self.directory, 'pronounce-v1')
        self.assertEqual(1, len(self.creates())); self.assertEqual(1, len(self.starts()))

    def test_external_state_write_during_flush_is_not_overwritten(self):
        self.prepare(); original = self.m.os.fsync; external = b'external state edit'
        def edit(fd):
            original(fd)
            if list(self.state_path().parent.glob('.state-*.tmp')): self.state_path().write_bytes(external)
        with patch.object(self.m.os, 'fsync', side_effect=edit):
            with self.assertRaises(SpokenBriefError): self.m.start(self.directory, 'pronounce-v1')
        self.assertEqual(external, self.state_path().read_bytes()); self.assertEqual([], self.creates())

    def test_replacement_sample_count_moves_only_later_boundaries(self):
        self.prepare()
        def longer(project):
            artifact = project['state']['artifacts'][0]; raw = wav_bytes(1001, 7)
            self.fixture.audio[artifact['url']] = raw; artifact['sha256'] = self.m.digest_bytes(raw)
        self.fixture.after_start = longer
        self.m.start(self.directory, 'pronounce-v1'); result = self.a.assemble(self.directory, 'pronounce-v1')
        updated = inspect_run(result['directory'])
        self.assertEqual(1001, updated['segments'][1]['samples'])
        self.assertEqual(self.archive['segments'][1]['start_sample'], updated['segments'][1]['start_sample'])
        self.assertEqual(self.archive['segments'][2]['start_sample'] + 521, updated['segments'][2]['start_sample'])

    def test_history_full_refuses_new_requests_but_retains_replay(self):
        self.prepare(); self.m.start(self.directory, 'pronounce-v1')
        with patch.object(self.m, 'MAX_REQUESTS', 1):
            self.prepare()
            with self.assertRaises(SpokenBriefError): self.prepare('next-take')
        self.assertTrue(self.state_path().is_file())

    def test_partial_result_is_refused_without_overwrite(self):
        self.prepare(); self.m.start(self.directory, 'pronounce-v1')
        result = self.state_path().parent / 'result'; result.mkdir(); (result / 'external.txt').write_text('Retain me')
        with self.assertRaises(SpokenBriefError): self.a.assemble(self.directory, 'pronounce-v1')
        self.assertEqual('Retain me', (result / 'external.txt').read_text())
        self.assert_original_intact()

    def test_second_revision_branches_without_losing_first_revision(self):
        self.prepare(); self.m.start(self.directory, 'pronounce-v1'); first = self.a.assemble(self.directory, 'pronounce-v1')
        parent = Path(first['directory']); before = (parent / 'receipt.json').read_bytes(); archive = inspect_run(parent)
        target = archive['segments'][2]
        review = record_review(parent, target['id'], target['audio_sha256'], decision='replace',
            findings={k: 'not-reviewed' for k in FINDINGS}, reviewer='owner', reason='Try the final sentence again.')['id']
        self.m.prepare(parent, target['id'], review, 'second-revision'); self.m.start(parent, 'second-revision')
        second = self.a.assemble(parent, 'second-revision'); updated = inspect_run(second['directory'])
        self.assertEqual(archive['segments'][1]['audio_sha256'], updated['segments'][1]['audio_sha256'])
        self.assertNotEqual(target['audio_sha256'], updated['segments'][2]['audio_sha256'])
        self.assertEqual(before, (parent / 'receipt.json').read_bytes()); self.assert_original_intact()


    def test_external_state_edit_during_identity_read_blocks_create(self):
        self.prepare(); calls = 0
        def changed():
            nonlocal calls
            calls += 1
            if calls == 2: self.state_path().write_bytes(b'external edit before Create')
        self.fixture.on_identity = changed
        with self.assertRaises(SpokenBriefError): self.m.start(self.directory, 'pronounce-v1')
        self.assertEqual([], self.creates())
        self.assertEqual(b'external edit before Create', self.state_path().read_bytes())

    def test_created_marker_with_observed_history_cannot_repeat_start(self):
        self.prepare(); self.m.start(self.directory, 'pronounce-v1')
        state = self.state(); state.update(status='created', artifact=None, last_observed_status='running')
        write_json(self.state_path(), state)
        self.fixture.projects[state['project_id']]['state'].update(status='planned')
        with self.assertRaises(SpokenBriefError): self.m.start(self.directory, 'pronounce-v1')
        self.assertEqual(1, len(self.starts()))

    def test_total_narration_budget_blocks_override_before_side_effects(self):
        maximum = sum(len(s['text']) for s in self.archive['segments'])
        with patch.object(self.m, 'MAX_NARRATED_CHARS', maximum, create=True):
            with self.assertRaises(SpokenBriefError): self.prepare(text='A longer spoken sentence. ' * 10 + 'End.')
        self.assertFalse((self.directory / 'replacements').exists())


if __name__ == '__main__': unittest.main()
