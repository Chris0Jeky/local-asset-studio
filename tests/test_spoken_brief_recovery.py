import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import spoken_brief
from spoken_brief_fixture import Fixture, wav_bytes


class SpokenBriefTests(unittest.TestCase):
    def test_terminal_failed_project_is_never_recreated(self):
        fixture = Fixture(); self.addCleanup(fixture.close)
        with tempfile.TemporaryDirectory() as temporary:
            pack = Path(temporary) / 'handoff'; pack.mkdir(); source = pack / 'COMPRESSED.md'; source.write_text('Only one sentence.', encoding='utf-8')
            compiled = spoken_brief.compile_source(source, speaker_id='brief-narrator')
            run_dir = spoken_brief.run_directory(source, compiled['manifest_sha256'])
            run_dir.mkdir(parents=True)
            identifier = 'f' * 32
            batch = spoken_brief.batch_segments(compiled['segments'])[0]
            fixture.projects[identifier] = {'id': identifier, 'kind': 'voice', 'name': 'failed',
                'plan': {'speaker_id': 'brief-narrator', 'lines': [{'id': line['id'], 'text': line['text']} for line in batch]},
                'state': {'status': 'failed', 'message': 'retained failure', 'artifacts': []}}
            state = spoken_brief.initial_state(compiled)
            state['batches'][0].update(project_id=identifier, status='failed')
            spoken_brief.write_json(run_dir / 'state.json', state)
            with self.assertRaisesRegex(spoken_brief.SpokenBriefError, 'retained failure'):
                spoken_brief.run(pack, base_url=fixture.base_url, poll_seconds=0.01, deadline_seconds=5)
            self.assertFalse(any(method == 'POST' and path == '/api/voice-baseline' for method, path, _, _ in fixture.requests))

    def test_invalid_create_response_is_retained_as_unconfirmed_and_never_reposted(self):
        fixture = Fixture(); self.addCleanup(fixture.close); fixture.create_id_override = 'not-a-project-id'
        with tempfile.TemporaryDirectory() as temporary:
            pack = Path(temporary) / 'handoff'; pack.mkdir(); (pack / 'COMPRESSED.md').write_text('Only one sentence.', encoding='utf-8')
            with self.assertRaisesRegex(spoken_brief.SpokenBriefError, 'invalid project identity'):
                spoken_brief.run(pack, base_url=fixture.base_url, poll_seconds=0.01, deadline_seconds=5)
            fixture.create_id_override = None
            with self.assertRaisesRegex(spoken_brief.SpokenBriefError, 'unconfirmed'):
                spoken_brief.run(pack, base_url=fixture.base_url, poll_seconds=0.01, deadline_seconds=5)
            creates = [request for request in fixture.requests if request[0] == 'POST' and request[1] == '/api/voice-baseline']
            self.assertEqual(len(creates), 1)

    def test_unconfirmed_creation_state_blocks_without_another_post(self):
        fixture = Fixture(); self.addCleanup(fixture.close)
        with tempfile.TemporaryDirectory() as temporary:
            pack = Path(temporary) / 'handoff'; pack.mkdir(); source = pack / 'COMPRESSED.md'; source.write_text('Only one sentence.', encoding='utf-8')
            compiled = spoken_brief.compile_source(source, speaker_id='brief-narrator')
            run_dir = spoken_brief.run_directory(source, compiled['manifest_sha256']); run_dir.mkdir(parents=True)
            state = spoken_brief.initial_state(compiled); state['batches'][0]['status'] = 'create-unconfirmed'
            spoken_brief.write_json(run_dir / 'state.json', state)
            with self.assertRaisesRegex(spoken_brief.SpokenBriefError, 'unconfirmed'):
                spoken_brief.run(pack, base_url=fixture.base_url, poll_seconds=0.01, deadline_seconds=5)
            self.assertFalse(any(method == 'POST' for method, _, _, _ in fixture.requests))

    def test_retained_terminal_batch_without_a_project_id_never_creates_replacement(self):
        fixture = Fixture(); self.addCleanup(fixture.close)
        with tempfile.TemporaryDirectory() as temporary:
            pack = Path(temporary) / 'handoff'; pack.mkdir(); source = pack / 'COMPRESSED.md'; source.write_text('Only one sentence.', encoding='utf-8')
            compiled = spoken_brief.compile_source(source, speaker_id='brief-narrator')
            run_dir = spoken_brief.run_directory(source, compiled['manifest_sha256']); run_dir.mkdir(parents=True)
            state = spoken_brief.initial_state(compiled); state['batches'][0]['status'] = 'failed'
            spoken_brief.write_json(run_dir / 'state.json', state)
            with self.assertRaisesRegex(spoken_brief.SpokenBriefError, 'state.*project identity'):
                spoken_brief.run(pack, base_url=fixture.base_url, poll_seconds=0.01, deadline_seconds=5)
            self.assertEqual(fixture.requests, [])

    def test_retained_state_must_match_the_compiled_batch_plan(self):
        fixture = Fixture(); self.addCleanup(fixture.close)
        with tempfile.TemporaryDirectory() as temporary:
            pack = Path(temporary) / 'handoff'; pack.mkdir(); source = pack / 'COMPRESSED.md'; source.write_text('Only one sentence.', encoding='utf-8')
            compiled = spoken_brief.compile_source(source, speaker_id='brief-narrator')
            run_dir = spoken_brief.run_directory(source, compiled['manifest_sha256']); run_dir.mkdir(parents=True)
            state = spoken_brief.initial_state(compiled); state['batches'] = []
            spoken_brief.write_json(run_dir / 'state.json', state)
            with self.assertRaisesRegex(spoken_brief.SpokenBriefError, 'state.*batch'):
                spoken_brief.run(pack, base_url=fixture.base_url, poll_seconds=0.01, deadline_seconds=5)
            self.assertEqual(fixture.requests, [])

    def test_retained_project_must_match_the_exact_batch_before_start(self):
        fixture = Fixture(); self.addCleanup(fixture.close)
        with tempfile.TemporaryDirectory() as temporary:
            pack = Path(temporary) / 'handoff'; pack.mkdir(); source = pack / 'COMPRESSED.md'; source.write_text('Only one sentence.', encoding='utf-8')
            compiled = spoken_brief.compile_source(source, speaker_id='brief-narrator')
            run_dir = spoken_brief.run_directory(source, compiled['manifest_sha256']); run_dir.mkdir(parents=True)
            identifier = 'e' * 32
            fixture.projects[identifier] = {'id': identifier, 'kind': 'voice', 'name': 'wrong retained plan',
                'plan': {'speaker_id': 'brief-narrator', 'lines': [{'id': 'segment-0001', 'text': 'Different words.'}]},
                'state': {'status': 'planned', 'message': 'prepared', 'artifacts': []}}
            state = spoken_brief.initial_state(compiled); state['batches'][0].update(project_id=identifier, status='planned')
            spoken_brief.write_json(run_dir / 'state.json', state)
            with self.assertRaisesRegex(spoken_brief.SpokenBriefError, 'does not match'):
                spoken_brief.run(pack, base_url=fixture.base_url, poll_seconds=0.01, deadline_seconds=5)
            self.assertFalse(any(method == 'POST' for method, _, _, _ in fixture.requests))


    def test_post_start_project_observation_must_still_match_the_batch(self):
        fixture = Fixture(); self.addCleanup(fixture.close); fixture.mismatch_after_start = True
        with tempfile.TemporaryDirectory() as temporary:
            pack = Path(temporary) / 'handoff'; pack.mkdir(); (pack / 'COMPRESSED.md').write_text('Only one sentence.', encoding='utf-8')
            with self.assertRaisesRegex(spoken_brief.SpokenBriefError, 'does not match'):
                spoken_brief.run(pack, base_url=fixture.base_url, poll_seconds=0.01, deadline_seconds=5)
            self.assertFalse(any('/files/' in path for method, path, _, _ in fixture.requests if method == 'GET'))

    def test_existing_run_claim_blocks_a_second_coordinator_before_network_use(self):
        fixture = Fixture(); self.addCleanup(fixture.close)
        with tempfile.TemporaryDirectory() as temporary:
            pack = Path(temporary) / 'handoff'; pack.mkdir(); source = pack / 'COMPRESSED.md'; source.write_text('Only one sentence.', encoding='utf-8')
            compiled = spoken_brief.compile_source(source, speaker_id='brief-narrator')
            run_dir = spoken_brief.run_directory(source, compiled['manifest_sha256']); run_dir.mkdir(parents=True)
            (run_dir / '.spoken-brief.lock').write_text('{"pid": 10}', encoding='utf-8')
            with self.assertRaisesRegex(spoken_brief.SpokenBriefError, 'already active'):
                spoken_brief.run(pack, base_url=fixture.base_url, poll_seconds=0.01, deadline_seconds=5)
            self.assertEqual(fixture.requests, [])

    def test_completed_receipt_cannot_redirect_reuse_outside_its_run_directory(self):
        fixture = Fixture(); self.addCleanup(fixture.close)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); pack = root / 'handoff'; pack.mkdir(); source = pack / 'COMPRESSED.md'; source.write_text('Only one sentence.', encoding='utf-8')
            compiled = spoken_brief.compile_source(source, speaker_id='brief-narrator')
            run_dir = spoken_brief.run_directory(source, compiled['manifest_sha256']); run_dir.mkdir(parents=True)
            outside = root / 'outside.wav'; outside.write_bytes(wav_bytes(10))
            spoken_brief.write_json(run_dir / 'receipt.json', {'manifest_sha256': compiled['manifest_sha256'],
                'output': {'path': str(outside), 'sha256': hashlib.sha256(outside.read_bytes()).hexdigest()}, 'projects': []})
            with self.assertRaisesRegex(spoken_brief.SpokenBriefError, 'receipt.*output'):
                spoken_brief.run(pack, base_url=fixture.base_url, poll_seconds=0.01, deadline_seconds=5)
            self.assertEqual(fixture.requests, [])

    def test_completed_receipt_makes_repeated_command_read_only(self):
        fixture = Fixture(); self.addCleanup(fixture.close)
        with tempfile.TemporaryDirectory() as temporary:
            pack = Path(temporary) / 'handoff'; pack.mkdir(); (pack / 'COMPRESSED.md').write_text('One sentence.', encoding='utf-8')
            first = spoken_brief.run(pack, base_url=fixture.base_url, poll_seconds=0.01, deadline_seconds=5)
            request_count = len(fixture.requests)
            second = spoken_brief.run(pack, base_url=fixture.base_url, poll_seconds=0.01, deadline_seconds=5)
            self.assertEqual(len(fixture.requests), request_count)
            self.assertTrue(second['reused']); self.assertEqual(second['output'], first['output'])


    def test_artifact_url_must_match_the_retained_artifact_path(self):
        identifier = 'f' * 32
        project = {'state': {'artifacts': [{'role': 'audio', 'path': 'voice/segment-0001-scene.wav',
                    'url': f'/api/production/{identifier}/files/voice/another-scene.wav', 'sha256': 'a' * 64}]}}
        with self.assertRaisesRegex(spoken_brief.SpokenBriefError, 'artifact route'):
            spoken_brief.artifact_for(project, 'segment-0001', identifier)

    def test_artifact_url_must_stay_on_the_project_file_route(self):
        project = {'state': {'artifacts': [{'role': 'audio', 'path': 'voice/segment-0001-scene.wav',
                    'url': 'https://example.test/stolen.wav', 'sha256': 'a' * 64}]}}
        with self.assertRaisesRegex(spoken_brief.SpokenBriefError, 'artifact route'):
            spoken_brief.artifact_for(project, 'segment-0001', 'f' * 32)



if __name__ == '__main__': unittest.main()
