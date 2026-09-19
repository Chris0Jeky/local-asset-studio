import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import spoken_brief
import spoken_brief_transport
from spoken_brief_fixture import Fixture, signed_plan, wav_bytes


class SpokenBriefHardeningTests(unittest.TestCase):
    def make_pack(self, temporary, text='Only one sentence.'):
        pack = Path(temporary) / 'handoff'
        pack.mkdir()
        source = pack / 'COMPRESSED.md'
        source.write_text(text, encoding='utf-8')
        return pack, source

    def test_state_and_receipt_retain_studio_project_and_producer_provenance(self):
        fixture = Fixture(); self.addCleanup(fixture.close)
        with tempfile.TemporaryDirectory() as temporary:
            pack, _ = self.make_pack(temporary)
            result = spoken_brief.run(pack, base_url=fixture.base_url, poll_seconds=0.01, deadline_seconds=5)
            receipt_path = Path(result['receipt'])
            state = spoken_brief.read_json(receipt_path.parent / 'state.json')
            receipt = spoken_brief.read_json(receipt_path)
            identifier = result['projects'][0]
            plan_sha256 = fixture.projects[identifier]['plan']['sha256']
            expected_studio = {'base_url': fixture.base_url, 'identity': fixture.identity}
            self.assertEqual(state['studio'], expected_studio)
            self.assertEqual(receipt['studio'], expected_studio)
            self.assertEqual(state['batches'][0]['project_plan_sha256'], plan_sha256)
            self.assertEqual(receipt['project_plans'], [{'id': identifier, 'sha256': plan_sha256}])
            self.assertRegex(state['producer_sha256'], r'^[0-9a-f]{64}$')
            self.assertEqual(receipt['producer_sha256'], state['producer_sha256'])

    def test_resumed_run_refuses_a_different_studio_workspace(self):
        fixture = Fixture(); self.addCleanup(fixture.close)
        with tempfile.TemporaryDirectory() as temporary:
            pack, _ = self.make_pack(temporary)
            result = spoken_brief.run(pack, base_url=fixture.base_url, poll_seconds=0.01, deadline_seconds=5)
            Path(result['receipt']).unlink()
            Path(result['output']).unlink()
            fixture.identity = {**fixture.identity, 'workspace': 'different-workspace'}
            with self.assertRaisesRegex(spoken_brief.SpokenBriefError, r'Studio.*identity changed'):
                spoken_brief.run(pack, base_url=fixture.base_url, poll_seconds=0.01, deadline_seconds=5)
            self.assertFalse(any(method == 'POST' for method, _, _, _ in fixture.requests[len(fixture.requests):]))

    def test_workspace_change_between_batches_blocks_the_next_create(self):
        fixture = Fixture(); self.addCleanup(fixture.close)
        def change_workspace(_project):
            if fixture.counter == 1:
                fixture.identity = {**fixture.identity, 'workspace': 'replacement-workspace'}
        fixture.after_start = change_workspace
        with tempfile.TemporaryDirectory() as temporary:
            text = '\n\n'.join(f'Paragraph {index}.' for index in range(7))
            pack, _ = self.make_pack(temporary, text)
            with self.assertRaisesRegex(spoken_brief.SpokenBriefError, r'Studio.*identity changed'):
                spoken_brief.run(pack, base_url=fixture.base_url, poll_seconds=0.01, deadline_seconds=5)
            creates = [item for item in fixture.requests if item[0] == 'POST' and item[1] == '/api/voice-baseline']
            self.assertEqual(len(creates), 1)

    def test_source_change_after_identity_check_blocks_create(self):
        fixture = Fixture(); self.addCleanup(fixture.close)
        with tempfile.TemporaryDirectory() as temporary:
            pack, source = self.make_pack(temporary)
            fixture.on_identity = lambda: source.write_text('Changed after compilation.', encoding='utf-8')
            with self.assertRaisesRegex(spoken_brief.SpokenBriefError, r'source changed'):
                spoken_brief.run(pack, base_url=fixture.base_url, poll_seconds=0.01, deadline_seconds=5)
            self.assertFalse(any(method == 'POST' for method, _, _, _ in fixture.requests))

    def test_source_change_after_create_blocks_start_but_retains_project_id(self):
        fixture = Fixture(); self.addCleanup(fixture.close)
        with tempfile.TemporaryDirectory() as temporary:
            pack, source = self.make_pack(temporary)
            compiled = spoken_brief.compile_source(source)
            run_dir = spoken_brief.run_directory(source, compiled['manifest_sha256'])
            fixture.after_create = lambda _project: source.write_text('Changed after Create.', encoding='utf-8')
            with self.assertRaisesRegex(spoken_brief.SpokenBriefError, r'source changed'):
                spoken_brief.run(pack, base_url=fixture.base_url, poll_seconds=0.01, deadline_seconds=5)
            state = spoken_brief.read_json(run_dir / 'state.json')
            self.assertIsNotNone(state['batches'][0]['project_id'])
            self.assertEqual(len([item for item in fixture.requests if item[0] == 'POST' and item[1] == '/api/voice-baseline']), 1)
            self.assertFalse(any(method == 'POST' and path.endswith('/start') for method, path, _, _ in fixture.requests))

    def test_source_change_after_start_blocks_artifact_publication(self):
        fixture = Fixture(); self.addCleanup(fixture.close)
        with tempfile.TemporaryDirectory() as temporary:
            pack, source = self.make_pack(temporary)
            compiled = spoken_brief.compile_source(source)
            run_dir = spoken_brief.run_directory(source, compiled['manifest_sha256'])
            fixture.after_start = lambda _project: source.write_text('Changed after Start.', encoding='utf-8')
            with self.assertRaisesRegex(spoken_brief.SpokenBriefError, r'source changed'):
                spoken_brief.run(pack, base_url=fixture.base_url, poll_seconds=0.01, deadline_seconds=5)
            self.assertFalse((run_dir / 'receipt.json').exists())

    def test_invalid_remote_plan_fingerprint_blocks_before_start(self):
        fixture = Fixture(); self.addCleanup(fixture.close)
        with tempfile.TemporaryDirectory() as temporary:
            pack, source = self.make_pack(temporary)
            compiled = spoken_brief.compile_source(source)
            batch = spoken_brief.batch_segments(compiled['segments'])[0]
            identifier = 'd' * 32
            payload = {'name': 'retained', 'speaker_id': 'brief-narrator',
                       'lines': [{'id': line['id'], 'text': line['text']} for line in batch]}
            plan = signed_plan(payload)
            plan['producer_revision'] = 'tampered-without-rehash'
            fixture.projects[identifier] = {'id': identifier, 'kind': 'voice', 'name': 'retained', 'plan': plan,
                'state': {'status': 'planned', 'message': 'prepared', 'artifacts': []}}
            run_dir = spoken_brief.run_directory(source, compiled['manifest_sha256']); run_dir.mkdir(parents=True)
            state = spoken_brief.initial_state(compiled)
            state['batches'][0].update(project_id=identifier, status='planned')
            spoken_brief.write_json(run_dir / 'state.json', state)
            with self.assertRaisesRegex(spoken_brief.SpokenBriefError, r'plan fingerprint'):
                spoken_brief.run(pack, base_url=fixture.base_url, poll_seconds=0.01, deadline_seconds=5)
            self.assertFalse(any(method == 'POST' for method, _, _, _ in fixture.requests))

    def test_project_plan_drift_after_start_blocks_artifact_use(self):
        fixture = Fixture(); self.addCleanup(fixture.close)
        def mutate_plan(project):
            project['plan']['producer_revision'] = 'fixture-v2'
            unsigned = {key: value for key, value in project['plan'].items() if key != 'sha256'}
            project['plan']['sha256'] = hashlib.sha256(
                json.dumps(unsigned, sort_keys=True, separators=(',', ':')).encode('utf-8')
            ).hexdigest()
        fixture.after_start = mutate_plan
        with tempfile.TemporaryDirectory() as temporary:
            pack, _ = self.make_pack(temporary)
            with self.assertRaisesRegex(spoken_brief.SpokenBriefError, r'plan changed'):
                spoken_brief.run(pack, base_url=fixture.base_url, poll_seconds=0.01, deadline_seconds=5)
            self.assertFalse(any('/files/' in path for method, path, _, _ in fixture.requests if method == 'GET'))

    def test_producer_change_between_batches_blocks_second_start(self):
        fixture = Fixture(); self.addCleanup(fixture.close)
        def change_producer(_project):
            if fixture.counter == 1:
                fixture.producer_revision = 'fixture-v2'
        fixture.after_start = change_producer
        with tempfile.TemporaryDirectory() as temporary:
            text = '\n\n'.join(f'Paragraph {index}.' for index in range(7))
            pack, source = self.make_pack(temporary, text)
            compiled = spoken_brief.compile_source(source)
            run_dir = spoken_brief.run_directory(source, compiled['manifest_sha256'])
            with self.assertRaisesRegex(spoken_brief.SpokenBriefError, r'producer.*changed'):
                spoken_brief.run(pack, base_url=fixture.base_url, poll_seconds=0.01, deadline_seconds=5)
            creates = [item for item in fixture.requests if item[0] == 'POST' and item[1] == '/api/voice-baseline']
            starts = [item for item in fixture.requests if item[0] == 'POST' and item[1].endswith('/start')]
            self.assertEqual((len(creates), len(starts)), (2, 1))
            state = spoken_brief.read_json(run_dir / 'state.json')
            self.assertIsNotNone(state['batches'][1]['project_id'])

    def test_state_rejects_an_invalid_project_plan_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, source = self.make_pack(temporary)
            compiled = spoken_brief.compile_source(source)
            batches = spoken_brief.batch_segments(compiled['segments'])
            state = spoken_brief.initial_state(compiled)
            state['batches'][0]['project_plan_sha256'] = 'not-a-sha256'
            with self.assertRaisesRegex(spoken_brief.SpokenBriefError, r'plan hash'):
                spoken_brief.validate_state(state, compiled, batches)

    def test_completed_receipt_requires_project_plan_provenance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / 'brief.spoken.wav'; output.write_bytes(wav_bytes(10))
            receipt_path = root / 'receipt.json'
            spoken_brief.write_json(receipt_path, {
                'manifest_sha256': 'a' * 64,
                'output': {'path': str(output), 'sha256': hashlib.sha256(output.read_bytes()).hexdigest()},
                'projects': ['b' * 32],
            })
            with self.assertRaisesRegex(spoken_brief.SpokenBriefError, r'project plan provenance'):
                spoken_brief_transport._completed_result(receipt_path, 'a' * 64, output)

    def test_loopback_json_must_be_an_object(self):
        fixture = Fixture(); self.addCleanup(fixture.close)
        client = spoken_brief.StudioClient(fixture.base_url)
        with self.assertRaisesRegex(spoken_brief.SpokenBriefError, r'JSON object'):
            client.get_json('/json-array')

    def test_loopback_url_rejects_an_out_of_range_port(self):
        with self.assertRaisesRegex(spoken_brief.SpokenBriefError, r'port'):
            spoken_brief.StudioClient('http://127.0.0.1:70000')

    def test_state_and_claim_intent_are_fsynced_before_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(spoken_brief_transport.os, 'fsync', wraps=os.fsync) as fsync:
                spoken_brief.write_json(root / 'state.json', {'status': 'creating'})
                claim = spoken_brief.acquire_run_claim(root, 'a' * 64)
                spoken_brief.release_run_claim(claim)
            self.assertGreaterEqual(fsync.call_count, 2)


if __name__ == '__main__': unittest.main()
