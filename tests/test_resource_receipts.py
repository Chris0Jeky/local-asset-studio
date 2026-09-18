"""Inspect actual recorder artifacts with synthetic counters, never GPU work."""
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
sys.path.insert(0, str(ROOT))
import job_resources as producer
import test_performance_history as profiles


def make_observation(root, job_id='fixture-job', *, status='completed', elapsed=10.0):
    """Use the shipped threaded writer; only sensors/source capture are injected."""
    class Sampler:
        def __init__(self, *_):
            self.binding = {'captured_at': producer.now(), 'epoch': {'pid': 12, 'created_at': 10,
                'argv_sha256': 'a' * 64}, 'profile_sha256': 'b' * 64,
                'unknown_reason': None, 'lost': False, 'last_bracket_at': None}
        def sample(self):
            value = profiles.sample()
            value['observed_at'] = producer.now()
            self.binding['last_bracket_at'] = producer.now()
            return value
    source = {'captured_at': producer.now(), 'commit_at_capture': 'c' * 40,
              'tracked_changes': False, 'loaded_code_matches_commit': None,
              'untracked_files_examined': False, 'unknown_reason': 'Not attested'}
    manager = producer.JobResourceObservations(root, NS(), samples=1, interval=1,
                     sampler_factory=Sampler, source_reader=lambda _: copy.deepcopy(source))
    job = {'id': job_id, 'comfy_url': 'http://127.0.0.1:8188', 'controls': {}, 'references': []}
    manager.intent(producer.event_snapshot('intent', job, index=0, graph={'seed': 1}))
    try:
        # Loaded Windows runners can spend several seconds scheduling the writer thread.
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            directory = manager.last.path
            if directory and (directory / 'profile.jsonl').is_file():
                if len((directory / 'profile.jsonl').read_bytes().splitlines()) == 2: break
            if manager.last.done.wait(0.01): raise AssertionError(manager.last.result)
        else: raise AssertionError('Fixture writer did not produce a sample')
        manager.accepted(producer.event_snapshot('accepted', job, index=0, prompt_id=job_id + '-prompt'))
        manager.finish(producer.event_snapshot('finish', dict(job, status=status, elapsed_seconds=elapsed)))
        if not manager.last.done.wait(5): raise AssertionError('Fixture did not finalize')
        return manager.last.path
    finally:
        manager.last.stop.set(); manager.thread.join(timeout=5)
        if manager.thread.is_alive(): raise AssertionError('Fixture observer leaked')


def read(path): return json.loads(path.read_bytes())
def write(path, value): path.write_bytes(producer.encoded(value))
def rehash(directory):
    result = read(directory / 'result.json')
    result['artifact_hashes'] = producer.artifact_hashes(directory)
    result['finished_at'] = producer.now()
    write(directory / 'result.json', result)


def events(directory): return [json.loads(line) for line in (directory / 'events.jsonl').read_bytes().splitlines()]
def put_events(directory, values):
    (directory / 'events.jsonl').write_bytes(b''.join(producer.encoded(v) for v in values)); rehash(directory)


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('resource_receipts'), 'Offline receipt inspector is absent')
        self.api = __import__('resource_receipts')
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.directory = make_observation(self.root)

    def inspect(self, **kwargs): return self.api.inspect_observation(self.directory, **kwargs)
    def refuses(self, code=None, **kwargs):
        with self.assertRaises(self.api.EvidenceError) as caught: self.inspect(**kwargs)
        if code: self.assertEqual(caught.exception.code, code)
        self.assertNotIn('PRIVATE', str(caught.exception))

    def test_real_producer_and_reducer_round_trip_no_side_effect(self):
        before = {p.name: p.read_bytes() for p in self.directory.iterdir()}
        pin = hashlib.sha256(before['result.json']).hexdigest()
        result = self.inspect(expected_result_sha256=pin, expected_job_id='fixture-job')
        self.assertEqual(result['schema'], 'studio.job-resource-inspection/v1')
        self.assertEqual(result['integrity'], 'verified')
        self.assertEqual(result['result_sha256'], pin)
        self.assertEqual(result['profile_summary'], producer.summarize_resource_profile(io.BytesIO(before['profile.jsonl'])))
        self.assertTrue(result['summary_verified'])
        self.assertFalse(result['qualified_benchmark']); self.assertFalse(result['execution_authority'])
        self.assertEqual(result['finish_snapshot']['status'], 'completed')
        self.assertEqual(result['finish_snapshot']['elapsed_seconds'], 10.0)
        self.assertEqual(result['submissions'][0]['prompt_id'], 'fixture-job-prompt')
        self.assertIsNone(result['source_observation']['loaded_code_matches_commit'])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.directory.iterdir()})
        self.assertNotIn('PRIVATE', json.dumps(result))

    def test_external_result_pin_and_job_pin_are_checked(self):
        self.refuses('result_pin_mismatch', expected_result_sha256='0' * 64)
        self.refuses('job_pin_mismatch', expected_job_id='another-job')
        for bad in ('short', True, 1): self.refuses('invalid_expected_pin', expected_result_sha256=bad)

    def test_real_writer_partial_summary_fault_is_not_accepted(self):
        original = producer.write_document
        def write_document(path, value):
            if path.name == 'summary.json':
                path.write_bytes(b'{')
                raise OSError('PRIVATE_DISK_FULL')
            return original(path, value)
        other = self.root / 'other'; other.mkdir()
        with patch.object(producer, 'write_document', side_effect=write_document):
            directory = make_observation(other)
        self.assertTrue(read(directory / 'result.json')['summary_available'])
        with self.assertRaises(self.api.EvidenceError) as caught:
            self.api.inspect_observation(directory)
        self.assertEqual(caught.exception.code, 'invalid_json')

    def test_invalid_path_is_a_payload_free_diagnostic(self):
        with self.assertRaises(self.api.EvidenceError) as caught:
            self.api.inspect_observation(Path('PRIVATE\x00'))
        self.assertNotIn('PRIVATE', str(caught.exception))

    def test_torn_summary_is_not_valid_just_because_available_and_hash_bound(self):
        (self.directory / 'summary.json').write_bytes(b'{"PRIVATE":')
        rehash(self.directory)
        self.assertTrue(read(self.directory / 'result.json')['summary_available'])
        self.refuses('invalid_json')

    def test_forged_summary_rehashed_in_result_must_equal_independent_reduction(self):
        summary = read(self.directory / 'summary.json')
        summary['metrics']['commit_headroom_bytes']['sampled_min'] = 999
        write(self.directory / 'summary.json', summary); rehash(self.directory)
        self.refuses('summary_mismatch')

    def test_boolean_number_substitution_does_not_match_summary(self):
        summary = read(self.directory / 'summary.json'); summary['sampling']['observed'] = True
        write(self.directory / 'summary.json', summary); rehash(self.directory)
        self.refuses('summary_mismatch')

    def test_every_fixed_artifact_hash_and_count_is_checked(self):
        original = read(self.directory / 'result.json')
        for name in ('context.json', 'events.jsonl', 'profile.jsonl', 'summary.json'):
            for key, bad in (('sha256', '0' * 64), ('bytes', 0), ('bytes', True)):
                with self.subTest(name=name, key=key):
                    value = copy.deepcopy(original); value['artifact_hashes'][name][key] = bad
                    write(self.directory / 'result.json', value); self.refuses()
        write(self.directory / 'result.json', original)
        self.assertEqual(self.inspect()['integrity'], 'verified')

    def test_missing_result_or_manifest_entry_is_incomplete_not_a_success(self):
        path = self.directory / 'result.json'; raw = path.read_bytes(); path.unlink()
        with self.assertRaises(self.api.EvidenceError) as caught: self.inspect()
        self.assertEqual(caught.exception.code, 'artifact_missing')
        self.assertTrue(caught.exception.incomplete); path.write_bytes(raw)

        result = read(path)
        del result['artifact_hashes']['summary.json']
        result['summary_available'] = False
        write(path, result)
        with self.assertRaises(self.api.EvidenceError) as caught: self.inspect()
        self.assertEqual(caught.exception.code, 'artifact_missing')
        self.assertTrue(caught.exception.incomplete)

    def test_missing_manifest_listed_artifact_is_invalid(self):
        for name in ('summary.json', 'context.json'):
            path = self.directory / name; raw = path.read_bytes(); path.unlink()
            with self.subTest(name=name), self.assertRaises(self.api.EvidenceError) as caught: self.inspect()
            self.assertEqual(caught.exception.code, 'artifact_missing')
            self.assertFalse(caught.exception.incomplete); path.write_bytes(raw)

    def test_operator_doc_splits_incomplete_capture_from_deleted_listed_sidecar(self):
        text = (ROOT / 'docs/performance/RECEIPT-INTEGRITY.md').read_text(encoding='utf-8')
        self.assertNotIn('with `incomplete=True` for missing\nartifacts.', text)
        self.assertIn('complete four-name manifest whose', text)
        self.assertIn('listed sidecar is gone', text)
        self.assertIn('incomplete=False', text)
        path = self.directory / 'result.json'; raw = path.read_bytes(); path.unlink()
        with self.assertRaises(self.api.EvidenceError) as caught: self.inspect()
        self.assertTrue(caught.exception.incomplete, 'missing result.json must stay incomplete')
        path.write_bytes(raw)
        sidecar = self.directory / 'summary.json'; sidecar.unlink()
        with self.assertRaises(self.api.EvidenceError) as caught: self.inspect()
        self.assertEqual(caught.exception.code, 'artifact_missing')
        self.assertFalse(caught.exception.incomplete, 'deleted listed sidecar must be invalid')

    def test_artifact_names_cannot_escape_fixed_set(self):
        result = read(self.directory / 'result.json')
        result['artifact_hashes']['../PRIVATE'] = {'sha256': 'a' * 64, 'bytes': 1}
        write(self.directory / 'result.json', result); self.refuses('artifact_manifest_invalid')

    def test_context_event_job_and_first_intent_must_agree(self):
        original = read(self.directory / 'context.json')
        for change in ('job_id', 'intent'):
            value = copy.deepcopy(original)
            if change == 'job_id': value['job_id'] = 'another'
            else: value['intent']['graph_sha256'] = 'f' * 64
            write(self.directory / 'context.json', value); rehash(self.directory); self.refuses()
        write(self.directory / 'context.json', original)
        value = events(self.directory); value[1]['job_id'] = 'another'
        put_events(self.directory, value); self.refuses('event_invalid')

    def test_event_order_indices_duplicates_and_prompt_digest(self):
        original = events(self.directory)
        mutations = [lambda e: e.reverse(), lambda e: e.insert(2, copy.deepcopy(e[1])),
                     lambda e: e[1].update(index=True), lambda e: e[1].update(index=3),
                     lambda e: e[1].update(prompt_id_sha256='a' * 64),
                     lambda e: e[2].update(coordinator_elapsed_seconds=True),
                     lambda e: e[0].update(fact='invented'),
                     lambda e: e[2].update(recorded_at='2000-01-01T00:00:00Z')]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                value = copy.deepcopy(original); mutate(value); put_events(self.directory, value); self.refuses()
        put_events(self.directory, original)
        self.assertEqual(len(self.inspect()['submissions']), 1)

    def test_uncertain_without_accepted_keeps_unobserved_response(self):
        value = events(self.directory); value.pop(1); value[-1]['coordinator_exit_status'] = 'uncertain'
        put_events(self.directory, value)
        result = self.inspect()
        self.assertEqual(result['finish_snapshot']['status'], 'uncertain')
        self.assertEqual(result['submissions'][0]['response'], 'not_recorded')
        self.assertIsNone(result['submissions'][0]['prompt_id'])
        self.assertFalse(result['qualified_benchmark'])

    def test_missing_finish_and_running_snapshot_are_not_terminal_outcomes(self):
        original = events(self.directory); put_events(self.directory, original[:-1])
        result = self.inspect(); self.assertIsNone(result['finish_snapshot'])
        self.assertIn('coordinator_exit_missing', result['warnings'])
        original[-1]['coordinator_exit_status'] = 'running'; put_events(self.directory, original)
        self.assertEqual(self.inspect()['finish_snapshot']['status'], 'running')
        self.assertFalse(self.inspect()['qualified_benchmark'])

    def test_metadata_only_and_short_sampling_keep_coverage(self):
        raw = (self.directory / 'profile.jsonl').read_bytes().splitlines(keepends=True)[0]
        (self.directory / 'profile.jsonl').write_bytes(raw)
        write(self.directory / 'summary.json', producer.summarize_resource_profile(io.BytesIO(raw)))
        rehash(self.directory)
        result = self.inspect()
        self.assertEqual(result['profile_summary']['sampling']['observed'], 0)
        self.assertIn('sampling_incomplete', result['warnings'])

    def test_torn_raw_and_mismatched_declared_limits_are_refused(self):
        raw = (self.directory / 'profile.jsonl').read_bytes()
        (self.directory / 'profile.jsonl').write_bytes(raw + b'{')
        rehash(self.directory); self.refuses('profile_invalid')
        (self.directory / 'profile.jsonl').write_bytes(raw)
        context = read(self.directory / 'context.json'); context['limits']['samples'] = 2
        write(self.directory / 'context.json', context); rehash(self.directory)
        self.refuses('sampling_contract_mismatch')

    def test_runtime_gap_retained_and_malformed_binding_refused(self):
        result = read(self.directory / 'result.json')
        result['runtime_binding'].update(lost=True, unknown_reason='PRIVATE_UNAVAILABLE')
        write(self.directory / 'result.json', result)
        report = self.inspect(); self.assertTrue(report['runtime_observation']['lost'])
        self.assertIn('runtime_bracket_lost', report['warnings']); self.assertNotIn('PRIVATE', json.dumps(report))
        result['runtime_binding']['epoch']['pid'] = True
        write(self.directory / 'result.json', result); self.refuses('runtime_binding_invalid')

    def test_unattested_v1_fields_cannot_be_promoted(self):
        original = read(self.directory / 'context.json')
        for key, value in (('warmth', 'warm'), ('generation_allowance_added', True), ('model_content_identity', 'a'*64)):
            context = copy.deepcopy(original); context[key] = value
            write(self.directory / 'context.json', context); rehash(self.directory); self.refuses('context_invalid')

    def test_json_constants_duplicates_deep_and_oversize_are_bounded(self):
        path = self.directory / 'result.json'
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e999}', b'['*2000,
                    b'0'* (256*1024+1)):
            path.write_bytes(raw); self.refuses()

    def test_shared_backend_url_contract_preserves_trailing_slash(self):
        value = events(self.directory); value[0]['comfy_url'] += '/'
        context = read(self.directory / 'context.json'); context['intent'] = value[0]
        write(self.directory / 'context.json', context); put_events(self.directory, value)
        self.assertEqual(self.inspect()['integrity'], 'verified')
        value[0]['comfy_url'] = 'http://example.com:8188'
        context['intent'] = value[0]; write(self.directory / 'context.json', context)
        put_events(self.directory, value); self.refuses('event_invalid')

    def test_disappearing_capture_is_a_bounded_diagnostic(self):
        original = self.api._capture_file
        def capture(path, limit):
            raw = original(path, limit)
            if path.name == 'context.json': path.unlink()
            return raw
        with patch.object(self.api, '_capture_file', side_effect=capture):
            self.refuses('file_changed')

    def test_post_capture_modification_cannot_supply_its_own_signature(self):
        original = self.api._capture_file
        def capture(path, limit):
            value = original(path, limit)
            if path.name == 'context.json':
                with path.open('ab') as output: output.write(b' ')
            return value
        with patch.object(self.api, '_capture_file', side_effect=capture):
            self.refuses('file_changed')

    def test_root_changed_during_inspection_cannot_be_adopted(self):
        original = self.api.read_evidence_file; roots = []
        def capture(path, limit):
            if path.name == 'result.json':
                roots.append(path)
                if len(roots) == 2: path.write_bytes(path.read_bytes() + b' ')
            return original(path, limit)
        with patch.object(self.api, 'read_evidence_file', side_effect=capture):
            self.refuses('result_changed')

    def test_four_batch_graphs_preserve_order_and_unicode_prompt_digests(self):
        original = events(self.directory); values = []
        for index in range(4):
            intent = dict(original[0], index=index, graph_sha256=str(index)*64)
            accepted = dict(original[1], index=index, recorded_at=original[0]['recorded_at'],
                            prompt_id='prompt-\u03b1-' + str(index))
            accepted['prompt_id_sha256'] = producer.digest(accepted['prompt_id'])
            values.extend((intent, accepted))
        values.append(original[-1])
        context = read(self.directory / 'context.json'); context['intent'] = values[0]
        write(self.directory / 'context.json', context); put_events(self.directory, values)
        report = self.inspect()
        self.assertEqual([s['index'] for s in report['submissions']], [0, 1, 2, 3])
        self.assertEqual(report['submissions'][-1]['prompt_id'], 'prompt-\u03b1-3')
        values[3]['prompt_id'] = values[1]['prompt_id']
        values[3]['prompt_id_sha256'] = values[1]['prompt_id_sha256']
        put_events(self.directory, values); self.refuses('event_invalid')

    @unittest.skipUnless(hasattr(os, 'symlink'), 'Symlinks unavailable')
    def test_linked_artifact_and_directory_are_refused(self):
        path = self.directory / 'summary.json'; target = self.root / 'outside'
        path.rename(target)
        try: path.symlink_to(target)
        except OSError as error: self.skipTest(str(error))
        self.refuses('file_not_regular')
        path.unlink(); target.rename(path)
        link = self.root / 'linked'; link.symlink_to(self.directory, target_is_directory=True)
        with self.assertRaises(self.api.EvidenceError): self.api.inspect_observation(link)

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'FIFO is POSIX-specific')
    def test_fifo_refused_without_waiting_for_writer(self):
        path = self.directory / 'summary.json'; path.unlink(); os.mkfifo(path)
        self.refuses('file_not_regular')


class ReceiptCLITests(unittest.TestCase):
    def test_real_cli_outside_checkout_exclusive_output_and_error_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); directory = make_observation(root); output = root / 'report.json'
            script = ROOT / 'scripts/inspect-resource-observation.py'
            self.assertTrue(script.is_file(), 'Receipt inspector CLI is absent')
            command = [sys.executable, str(script), str(directory)]
            result = subprocess.run(command + ['--output', str(output)], cwd=tmp, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = read(output); self.assertEqual(report['integrity'], 'verified')
            prior = output.read_bytes()
            result = subprocess.run(command + ['--output', str(output)], capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0); self.assertEqual(output.read_bytes(), prior)
            (directory / 'summary.json').write_bytes(b'{')
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)['integrity'], 'invalid')
            self.assertNotIn('Traceback', result.stderr)

    def test_inspector_import_and_cli_have_no_live_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = make_observation(Path(tmp)); script = ROOT / 'scripts/inspect-resource-observation.py'
            self.assertTrue(script.is_file(), 'Receipt inspector CLI is absent')
            guard = '''import sys,runpy
class Guard:
 def find_spec(self,name,path=None,target=None):
  if name.split('.')[0] in {'server','job_resources','resource_probe','torch','psutil','subprocess','http','socket'}:
   raise AssertionError('Live dependency: '+name)
sys.meta_path.insert(0,Guard())
def audit(event,args):
 if event in {'socket.connect','socket.bind','subprocess.Popen','os.system'}: raise AssertionError(event)
sys.addaudithook(audit)
sys.argv=sys.argv[1:]
runpy.run_path(sys.argv[0],run_name='__main__')
'''
            result = subprocess.run([sys.executable,'-c',guard,str(script),str(directory)], cwd=tmp,
                                    capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['integrity'],'verified')


if __name__ == '__main__': unittest.main()
