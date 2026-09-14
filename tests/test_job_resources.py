"""Real Studio/files with inert Comfy responses; no workstation or inference."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from types import SimpleNamespace as NS
from urllib.error import URLError

from test_server import FakeStudio, GRAPH, PRESET, server
from test_performance_history import sample

REAL_THREAD_START = threading.Thread.start

IDENTITY = {'profile_id': 'primary', 'profile_sha256': 'a'*64,
            'process': {'pid': 456, 'created_at': 1, 'argv_sha256': 'b'*64}, 'unknown_reason': None}


def history(prompt='p', status='success'):
    return {'status': {'status_str': status, 'messages': [
        ['execution_start', {'prompt_id': prompt, 'timestamp': 1000}],
        ['execution_success' if status == 'success' else 'execution_error',
         {'prompt_id': prompt, 'timestamp': 4200, 'exception_message': 'HIP out of memory'}]]}, 'outputs': {}}


class JobResourceTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('job_resources'), 'Job resource windows are not implemented')
        self.m = importlib.import_module('job_resources')
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for path in ('config', 'presets', 'workflows/api', 'fake-comfy/input'):
            (self.root/path).mkdir(parents=True)
        (self.root/'config/local.json').write_text(json.dumps({'comfy_root': str(self.root/'fake-comfy'),
            'performance_telemetry': {'enabled': True, 'max_samples': 4, 'interval_seconds': 5}}))
        (self.root/'presets/catalog.json').write_text(json.dumps({'presets': [PRESET]}))
        (self.root/'workflows/api/demo-api.json').write_text(json.dumps(GRAPH))
        self.thread_guard = patch.object(threading.Thread, 'start', lambda *_: None)
        self.thread_guard.start(); self.addCleanup(self.thread_guard.stop)
        self.runtime_function = self.m.runtime_identity
        self.identity = patch.object(self.m, 'runtime_identity', return_value=copy.deepcopy(IDENTITY))
        self.identity_mock = self.identity.start(); self.addCleanup(self.identity.stop)
        self.sample_count = 0
        def observe():
            row = sample(self.sample_count); self.sample_count += 1; return row
        self.sampler = patch.object(self.m.resource_probe, 'ResourceSampler', return_value=NS(sample=observe))
        self.sampler_mock = self.sampler.start(); self.addCleanup(self.sampler.stop)

    def studio_job(self, replies=None, batch=1):
        if replies is None: replies = [{'queue_running': [], 'queue_pending': []}, {'prompt_id': 'p'}, {'p': history()}]
        studio = FakeStudio(self.root, replies)
        job = studio.jobs[studio.create_job({'preset_id': 'demo', 'controls': {}, 'batch_count': batch}, enqueue=False)['id']]
        return studio, job

    def inspect_one(self, studio, job):
        result = self.m.inspect(studio, job['id'])
        self.assertFalse(result['execution_authority']); self.assertEqual(len(result['windows']), 1)
        row = result['windows'][0]; self.assertEqual(row['status'], 'finalized', row)
        return row

    def test_run_records_actual_graph_prompt_and_history_without_extra_submit(self):
        studio, job = self.studio_job(); studio._run(job)
        row = self.inspect_one(studio, job)
        self.assertEqual(row['manifest']['prepared_graph_sha256'], self.m.fingerprint(job['graph']))
        self.assertEqual(row['result']['prompt_ids'], ['p'])
        self.assertEqual(row['result']['engine_executions'][0]['elapsed_seconds'], 3.2)
        self.assertTrue(all(value is None for value in row['result']['phase_seconds'].values()))
        self.assertEqual(row['manifest']['condition'], 'unknown')
        self.assertEqual(row['manifest']['production']['status'], 'not_bound')
        self.assertEqual(row['result']['observed_job_status'], 'completed')
        self.assertEqual([a[0] for a, _ in studio.requests], ['/queue', '/prompt', '/history/p'])
        self.assertNotIn('resources', studio.export_recipe(job))

    def test_disabled_is_no_files_no_sampler_and_no_read_dependency(self):
        studio, job = self.studio_job(); studio.config.pop('performance_telemetry')
        studio._run(job)
        self.sampler_mock.assert_not_called(); self.identity_mock.assert_not_called()
        self.assertFalse((studio.runs/job['id']/'resources').exists())
        self.assertEqual(job['status'], 'completed')

    def test_invalid_configuration_cannot_fail_generation(self):
        for config in ({'enabled': True, 'max_samples': 121}, {'enabled': True, 'interval_seconds': False},
                       {'enabled': True, 'unknown': 1}):
            with self.subTest(config=config):
                studio, job = self.studio_job(); studio.config['performance_telemetry'] = config
                studio._run(job); self.assertEqual(job['status'], 'completed')
                self.assertFalse((studio.runs/job['id']/'resources').exists())

    def test_uncertain_post_retains_intent_without_replay_or_new_window(self):
        studio, job = self.studio_job([{'queue_running': [], 'queue_pending': []}, URLError('lost')])
        studio._run(job); row = self.inspect_one(studio, job)
        self.assertEqual(job['status'], 'uncertain'); self.assertTrue(row['result']['has_pending_submission'])
        self.assertIsNone(row['result']['submissions'][0]['prompt_id'])
        before = (studio.runs/job['id']/'recipe.json').read_bytes()
        with self.assertRaises(server.StudioError): studio._run(job)
        self.assertEqual(len([a for a, _ in studio.requests if a[0] == '/prompt']), 1)
        self.assertEqual((studio.runs/job['id']/'recipe.json').read_bytes(), before)
        self.assertEqual(len(self.m.inspect(studio, job['id'])['windows']), 1)

    def test_engine_oom_retains_failed_job_and_observed_engine_timing(self):
        studio, job = self.studio_job([{'queue_running': [], 'queue_pending': []}, {'prompt_id': 'p'}, {'p': history(status='error')}])
        with self.assertRaises(server.StudioError): studio._run(job)
        row = self.inspect_one(studio, job)
        self.assertEqual(job['status'], 'failed'); self.assertEqual(row['result']['observed_job_status'], 'failed')
        self.assertEqual(row['result']['engine_executions'][0]['elapsed_seconds'], 3.2)
        self.assertEqual(job['prompt_ids'], ['p'])

    def test_queue_refusal_creates_no_samples_and_no_prompt(self):
        studio, job = self.studio_job([])
        with patch.object(studio, '_wait_for_queue', side_effect=server.QueueWaitUnavailable('busy')): studio._run(job)
        row = self.inspect_one(studio, job)
        self.assertEqual(job['status'], 'not_submitted'); self.assertEqual(self.sample_count, 0)
        self.assertEqual(row['result']['summary']['sampling']['observed'], 0)
        self.assertFalse(studio.requests)

    def test_sample_limit_and_completion_cadence_never_add_work(self):
        studio, job = self.studio_job(); studio.config['performance_telemetry']['max_samples'] = 1
        studio._run(job); row = self.inspect_one(studio, job)
        self.assertEqual(self.sample_count, 1); self.assertEqual(row['result']['sampling_stop_reason'], 'sample_limit')
        self.assertEqual(job['status'], 'completed')

    def test_sensor_exception_does_not_change_success_or_lose_receipts(self):
        studio, job = self.studio_job()
        self.sampler_mock.return_value.sample = lambda: (_ for _ in ()).throw(OSError('PRIVATE'))
        studio._run(job); row = self.inspect_one(studio, job)
        self.assertEqual(job['status'], 'completed'); self.assertEqual(row['result']['sampling_stop_reason'], 'observation_error')
        self.assertEqual(row['result']['summary']['sampling']['observed'], 0)
        self.assertNotIn('PRIVATE', json.dumps(row))

    def test_manifest_write_failure_does_not_change_generation(self):
        studio, job = self.studio_job()
        with patch.object(self.m, '_publish', side_effect=OSError('full')): studio._run(job)
        self.assertEqual(job['status'], 'completed'); self.assertEqual(job['prompt_ids'], ['p'])

    def test_result_write_failure_is_not_finalized_and_keeps_raw_files(self):
        studio, job = self.studio_job(); publish = self.m._publish
        def fail_final(path, value):
            if path.name == 'result.json': raise OSError('full')
            return publish(path, value)
        with patch.object(self.m, '_publish', side_effect=fail_final): studio._run(job)
        row = self.m.inspect(studio, job['id'])['windows'][0]
        self.assertEqual(row['status'], 'not_finalized'); self.assertEqual(job['status'], 'completed')
        self.assertTrue((studio.runs/job['id']/'resources/01/samples.jsonl').is_file())

    def test_runtime_drift_during_sample_discards_the_sample(self):
        studio, job = self.studio_job()
        changed = copy.deepcopy(IDENTITY); changed['process']['created_at'] = 2
        self.identity_mock.side_effect = [IDENTITY, IDENTITY, changed]
        studio._run(job); row = self.inspect_one(studio, job)
        self.assertEqual(row['result']['summary']['sampling']['observed'], 0)
        self.assertEqual(row['result']['sampling_stop_reason'], 'runtime_identity_changed_or_unknown')
        self.assertEqual(job['status'], 'completed')

    def test_inspect_is_read_only_and_detects_changed_raw_bytes(self):
        studio, job = self.studio_job(); studio._run(job)
        folder = studio.runs/job['id']; before = {str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob('*') if p.is_file()}
        count = len(studio.requests); self.inspect_one(studio, job)
        self.assertEqual(len(studio.requests), count)
        self.assertEqual(before, {str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob('*') if p.is_file()})
        (folder/'resources/01/samples.jsonl').write_bytes(b'corrupt')
        self.assertEqual(self.m.inspect(studio, job['id'])['windows'][0]['status'], 'corrupt')

    def test_existing_slots_are_retained_and_ninth_window_is_refused(self):
        studio, job = self.studio_job()
        for i in range(self.m.MAX_WINDOWS):
            with self.m.observe(studio, job) as window: self.assertIsNotNone(window)
        before = (studio.runs/job['id']/'resources/01/manifest.json').read_bytes()
        with self.m.observe(studio, job) as window: self.assertIsNone(window)
        self.assertEqual((studio.runs/job['id']/'resources/01/manifest.json').read_bytes(), before)
        self.assertEqual(job['status'], 'queued')

    def test_history_identity_ambiguity_keeps_engine_time_unknown(self):
        for mutate in (lambda h: h['status']['messages'].append(h['status']['messages'][0]),
                       lambda h: h['status']['messages'][1][1].update(timestamp=999),
                       lambda h: h['status']['messages'][0][1].update(prompt_id='other'),
                       lambda h: h['status']['messages'][0][1].update(timestamp=True)):
            h = history(); mutate(h)
            self.assertIsNone(self.m.engine_timing('p', h)['elapsed_seconds'])

    def test_private_paths_prompts_and_argv_are_not_returned(self):
        studio, job = self.studio_job(); job['controls']['positive'] = 'PRIVATE_PROMPT'
        studio._run(job); row = self.inspect_one(studio, job)
        serialized = json.dumps(row)
        self.assertNotIn(str(self.root), serialized); self.assertNotIn('PRIVATE_PROMPT', serialized)
        self.assertFalse(row['manifest']['execution_authority'])

    def test_unknown_job_cannot_create_resource_files(self):
        studio, job = self.studio_job()
        with self.assertRaises(ValueError): self.m.inspect(studio, 'missing')
        self.assertFalse((studio.runs/'missing').exists())

    def test_disabled_instrumentation_keeps_existing_two_argument_history_seam(self):
        studio, job = self.studio_job([{'queue_running': [], 'queue_pending': []}, {'prompt_id': 'p'}])
        studio.config.pop('performance_telemetry')
        with patch.object(studio, '_wait_history', side_effect=lambda j, s: True): studio._run(job)
        self.assertEqual(job['status'], 'completed')

    def test_runtime_identity_rechecks_a_fresh_listener_after_cached_handle_reads(self):
        studio, job = self.studio_job()
        profile = studio.backends.profiles[studio.backends.active]
        old = NS(pid=456, create_time=lambda: 1, cmdline=lambda: ['PRIVATE_ARGV'])
        new = NS(pid=456, create_time=lambda: 2, cmdline=lambda: ['PRIVATE_ARGV'])
        with patch.object(studio.backends, 'process', side_effect=[old, new]):
            result = self.runtime_function(studio, job)
        self.assertIsNone(result['process']); self.assertIsNotNone(result['unknown_reason'])
        self.assertNotIn('PRIVATE_ARGV', json.dumps(result))

    def test_runtime_identity_retains_only_a_verified_argv_digest(self):
        studio, job = self.studio_job()
        proc = NS(pid=456, create_time=lambda: 1, cmdline=lambda: ['PRIVATE_ARGV'])
        with patch.object(studio.backends, 'process', return_value=proc):
            result = self.runtime_function(studio, job)
        self.assertEqual(result['process']['argv_sha256'], self.m.fingerprint(['PRIVATE_ARGV']))
        self.assertIsNone(result['unknown_reason']); self.assertNotIn('PRIVATE_ARGV', json.dumps(result))

    def test_telemetry_runs_before_fresh_admission_not_after(self):
        studio, job = self.studio_job(); calls = []
        original = self.sampler_mock.return_value.sample
        def observe(): calls.append('sample'); return original()
        self.sampler_mock.return_value.sample = observe
        def gate(*args, **kwargs): calls.append('admission'); return None
        with patch.object(studio, 'host_commit_preflight', side_effect=gate): studio._run(job)
        self.assertEqual(calls[:2], ['sample', 'admission'])

    def test_byte_and_event_limits_preserve_original_job_evidence(self):
        studio, job = self.studio_job()
        before = (studio.runs/job['id']/'recipe.json').read_bytes()
        with self.m.observe(studio, job) as window:
            with patch.object(self.m, 'MAX_SAMPLE_BYTES', 20): window.sample('test', force=True)
            for _ in range(200): window.event('queue_ready')
        row = self.inspect_one(studio, job)
        self.assertEqual(row['result']['sampling_stop_reason'], 'observation_error')
        path = studio.runs/job['id']/'resources/01/events.jsonl'
        self.assertLessEqual(len(path.read_bytes().splitlines()), self.m.MAX_EVENTS)
        self.assertEqual((studio.runs/job['id']/'recipe.json').read_bytes(), before)

    def test_production_pins_require_actual_stage_graph_and_job_ownership(self):
        studio, job = self.studio_job(); job['project_id'] = 'a'*32
        plan = {'stages': [{'graph': copy.deepcopy(job['graph']), 'graph_sha256': self.m.fingerprint(job['graph']),
                           'request': {'preset_id': job['preset_id']}}],
                'bundle': {'comfy_url': job['comfy_url'], 'comfy_root': job['comfy_root'],
                           'models': [{'sha256': 'c'*64, 'bytes': 12, 'path': 'PRIVATE'}], 'inputs': []}}
        project = {'id': job['project_id'], 'root_id': 'root', 'plan': plan,
                   'state': {'attempts': {'0': {'job_id': job['id']}}}}
        plan['sha256'] = self.m.fingerprint(plan)
        with patch.object(studio.production, '_get', return_value=project):
            result = self.m._pins(studio, job)
            self.assertEqual(result['status'], 'bound_preflight'); self.assertNotIn('PRIVATE', json.dumps(result))
            plan['stages'][0]['graph']['1']['inputs']['text'] = 'different'
            plan['sha256'] = self.m.fingerprint({k:v for k,v in plan.items() if k != 'sha256'})
            self.assertEqual(self.m._pins(studio, job)['status'], 'not_bound')

    def test_interrupted_window_survives_reopen_without_becoming_finalized(self):
        studio, job = self.studio_job()
        window = self.m.Window(studio, job, self.m.settings(studio.config), lambda: 10)
        window.sample('before_admission', force=True); window.close()
        reopened = FakeStudio(self.root, [])
        row = self.m.inspect(reopened, job['id'])['windows'][0]
        self.assertEqual(row['status'], 'not_finalized'); self.assertFalse(reopened.requests)

    def test_engine_message_order_cannot_certify_reversed_execution(self):
        h = history(); h['status']['messages'].reverse()
        self.assertIsNone(self.m.engine_timing('p', h)['elapsed_seconds'])


    def test_final_listener_identity_must_have_numeric_types_not_boolean_aliases(self):
        studio, job = self.studio_job()
        old = NS(pid=1, create_time=lambda: 1, cmdline=lambda: ['same'])
        for new in (NS(pid=True, create_time=lambda: 1, cmdline=lambda: ['same']),
                    NS(pid=1, create_time=lambda: True, cmdline=lambda: ['same'])):
            with self.subTest(new=new), patch.object(studio.backends, 'process', side_effect=[old, new]):
                result = self.runtime_function(studio, job)
                self.assertIsNone(result['process'])

    def test_actual_production_attempt_pins_and_reservations_are_preserved(self):
        studio, unused = self.studio_job()
        bundle = {'comfy_url': studio.comfy_url, 'comfy_root': str(studio.comfy_root),
                  'schema_sha256': 'c'*64, 'models': [{'sha256': 'd'*64, 'bytes': 10}],
                  'inputs': [{'sha256': 'e'*64, 'bytes': 20}]}
        with patch.object(studio, 'production_preflight', return_value=bundle), \
             patch.object(studio, 'check_production_bundle'), patch.object(studio, 'validate_graph'):
            project = studio.production.create({'name': 'Resource trial', 'recipe': {'preset_id': 'demo', 'controls': {}},
                'axis': 'seed', 'values': [17], 'max_generations': 1})
            studio.production.start(project['id']); before = studio.production.get(project['id'])['budget']
            studio.production.run(project['id'])
        project = studio.production.get(project['id'])
        self.assertEqual(project['budget'], before)
        self.assertEqual(project['state']['status'], 'awaiting_review')
        job = studio.jobs[project['state']['attempts']['0']['job_id']]
        row = self.inspect_one(studio, job)
        self.assertEqual(row['manifest']['production']['status'], 'bound_preflight')
        self.assertEqual(row['manifest']['production']['plan_sha256'], studio.production._get(project['id'])['plan']['sha256'])
        self.assertEqual(row['manifest']['production']['models'], bundle['models'])
        self.assertEqual(row['manifest']['production']['inputs'], bundle['inputs'])
        self.assertEqual(sum(a[0]=='/prompt' for a,_ in studio.requests), 1)
        self.assertEqual(unused['status'], 'queued')

    def test_http_inspection_crosses_actual_handler_without_sampling_or_writes(self):
        from http.client import HTTPConnection
        from http.server import HTTPServer
        studio, job = self.studio_job(); studio._run(job)
        row = self.inspect_one(studio, job)
        class Handler(server.Handler): pass
        Handler.studio = studio
        httpd = HTTPServer(('127.0.0.1', 0), Handler)
        worker = threading.Thread(target=httpd.serve_forever, daemon=True)
        REAL_THREAD_START(worker)
        count = self.sample_count; requests = len(studio.requests)
        try:
            for route, host, expected in ((f"/api/jobs/{job['id']}/resources", '127.0.0.1:8191', 200),
                                          ('/api/jobs/missing/resources', '127.0.0.1:8191', 404),
                                          (f"/api/jobs/{job['id']}/resources", 'example.com', 403)):
                connection = HTTPConnection('127.0.0.1', httpd.server_port, timeout=5)
                try:
                    connection.request('GET', route, headers={'Host': host})
                    response = connection.getresponse(); raw = response.read()
                    self.assertEqual(response.status, expected, raw)
                    if expected==200:
                        self.assertEqual(json.loads(raw)['windows'][0], row)
                        self.assertEqual(response.getheader('Cache-Control'), 'no-store')
                finally: connection.close()
        finally:
            httpd.shutdown(); worker.join(5); httpd.server_close()
        self.assertEqual(self.sample_count, count); self.assertEqual(len(studio.requests), requests)

    def test_opportunistic_sampling_uses_completion_spacing_and_cap(self):
        studio, job = self.studio_job(); now = [0]
        with self.m.observe(studio, job, clock=lambda: now[0]) as window:
            window.sample('preflight'); self.assertEqual(self.sample_count, 1)
            now[0] = 4.9; window.sample('history'); self.assertEqual(self.sample_count, 1)
            now[0] = 5; window.sample('history'); self.assertEqual(self.sample_count, 2)
            now[0] = 10; window.sample('history'); self.assertEqual(self.sample_count, 3)
            now[0] = 15; window.sample('history'); self.assertEqual(self.sample_count, 4)
        row = self.inspect_one(studio, job)
        self.assertEqual(self.sample_count, 4)
        self.assertEqual(row['result']['sampling_stop_reason'], 'sample_limit')

    def test_known_prompt_resume_does_not_start_new_sampling_or_replay(self):
        studio, job = self.studio_job([{'queue_running': [], 'queue_pending': []}, {'prompt_id': 'p'}, URLError('lost')])
        studio._run(job); self.assertEqual(job['status'], 'uncertain')
        count = self.sample_count
        studio.replies = iter([{'p': history()}]); studio._resume(job)
        self.assertEqual(job['status'], 'completed'); self.assertEqual(self.sample_count, count)
        result = self.m.inspect(studio, job['id'])
        self.assertEqual(len(result['windows']), 1)
        self.assertEqual(result['current_job_status'], 'completed')
        self.assertEqual(result['windows'][0]['result']['observed_job_status'], 'uncertain')
        self.assertEqual(sum(a[0]=='/prompt' for a,_ in studio.requests), 1)

    def test_symlinked_resource_root_is_refused_without_touching_target(self):
        studio, job = self.studio_job(); target = self.root/'separate'; target.mkdir()
        link = studio.runs/job['id']/'resources'
        try: link.symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError): self.skipTest('symlink unavailable')
        studio._run(job)
        self.assertEqual(job['status'], 'completed'); self.assertEqual(list(target.iterdir()), [])
        self.assertEqual(self.m.inspect(studio, job['id'])['status'], 'unavailable')

    def test_repeated_publish_never_overwrites_existing_document(self):
        target = self.root/'manifest.json'; self.m._publish(target, {'value': 1})
        before = target.read_bytes()
        with self.assertRaises(FileExistsError): self.m._publish(target, {'value': 2})
        self.assertEqual(target.read_bytes(), before)

    def test_runtime_version_drift_is_explicit_summary_failure_not_job_failure(self):
        studio, job = self.studio_job()
        n = [0]
        def observe():
            row = sample(n[0]); n[0] += 1
            row['comfy']['versions']['pytorch_version'] = str(n[0])
            return row
        self.sampler_mock.return_value.sample = observe
        studio._run(job); row = self.inspect_one(studio, job)
        self.assertEqual(job['status'], 'completed')
        self.assertIsNone(row['result']['summary'])
        self.assertEqual(row['result']['summary_error'], 'incomplete_or_incompatible_samples')


if __name__ == '__main__': unittest.main()
