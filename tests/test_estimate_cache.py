import copy
from concurrent.futures import ThreadPoolExecutor
import json
import os
import unittest
from unittest.mock import patch

import test_server as fixture


class EstimateCacheTests(unittest.TestCase):
    setUp = fixture.ServerTests.setUp
    tearDown = fixture.ServerTests.tearDown

    def studio(self):
        studio = fixture.server.Studio(self.root)
        self.enterContext(patch.object(studio, '_request', side_effect=AssertionError('Estimate must stay offline')))
        studio.jobs = {str(i): self.job(str(i), seconds) for i, seconds in enumerate((12, 24, 36, 48, 60))}
        return studio

    def job(self, identifier, seconds=24):
        return {'id': identifier, 'status': 'completed', 'preset_id': 'demo', 'prompt_ids': ['retained-prompt'],
                'graph': copy.deepcopy(fixture.GRAPH), 'controls': {}, 'batch_count': 1, 'elapsed_seconds': seconds}

    def write_json(self, path, value):
        before = path.stat()
        path.write_text(json.dumps(value), encoding='utf-8', newline='\n')
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))

    def fresh_answer(self, studio, request):
        studio.__dict__.pop('_estimate_cache', None)
        return studio.estimate(request)

    def test_cached_and_uncached_answers_match_original_history_results(self):
        studio = self.studio(); before = copy.deepcopy(studio.jobs)
        # Captured from the original uncached estimator with this fixture history.
        base = {'available': True, 'basis': ['5 completed runs of this workflow',
                'scaled for 512\u00d7512, 20 steps, 0 active LoRAs, 1 output'],
                'confidence': 'high', 'estimate_seconds': 36.0, 'matched_samples': 5, 'sample_count': 5,
                'range_seconds': [14, 58], 'features': {'workflow': 'Demo', 'model': ['demo'], 'loras': [],
                'resolution': [512, 512], 'steps': 20, 'frames': 1, 'node_count': 2, 'references': 0, 'modality': 'image'}}
        requests = [({'preset_id': 'demo'}, base)]
        scaled = copy.deepcopy(base); scaled.update(estimate_seconds=98.5, range_seconds=[39, 158])
        scaled['basis'][1] = 'scaled for 512\u00d7512, 32 steps, 0 active LoRAs, 2 outputs'; scaled['features']['steps'] = 32
        requests.append(({'preset_id': 'demo', 'controls': {'steps': 32}, 'batch_count': 2}, scaled))
        wider = copy.deepcopy(base); wider.update(estimate_seconds=58.0, range_seconds=[23, 93])
        wider['basis'][1] = 'scaled for 1024\u00d7512, 20 steps, 0 active LoRAs, 1 output'
        wider['features'].update(resolution=[1024, 512], references=2)
        requests.append(({'preset_id': 'demo', 'controls': {'width': 1024, 'positive': 'hello'}, 'reference_count': 2}, wider))
        for request, expected in requests:
            with self.subTest(request=request):
                uncached = self.fresh_answer(studio, request)
                self.assertEqual(uncached, expected)
                self.assertEqual(json.dumps(studio.estimate(request)), json.dumps(uncached))
        self.assertEqual(studio.jobs, before)

    def test_identical_request_reuses_features_and_templates(self):
        studio = self.studio(); request = {'preset_id': 'demo', 'controls': {'steps': 32}}
        with patch.object(studio, '_estimate_features', wraps=studio._estimate_features) as features:
            first = studio.estimate(request)
            self.assertEqual(features.call_count, 6)
            features.reset_mock()
            with patch.object(studio, 'graph_for', side_effect=AssertionError('Template reread')), \
                 patch.object(fixture.server, 'read_json', side_effect=AssertionError('Catalog reread')):
                self.assertEqual(studio.estimate(request), first)
            features.assert_not_called()

    def test_completion_addition_and_removal_update_samples_and_bound_cache(self):
        studio = self.studio(); request = {'preset_id': 'demo'}
        initial = studio.estimate(request)
        studio.jobs['0']['status'] = 'running'
        self.assertEqual(studio.estimate(request)['sample_count'], 4)
        studio.jobs['0'].update(status='completed', elapsed_seconds=240, finished_at=123)
        completed = studio.estimate(request)
        self.assertNotEqual(completed['estimate_seconds'], initial['estimate_seconds'])
        studio.jobs['added'] = self.job('added', 300)
        self.assertEqual(studio.estimate(request)['sample_count'], 6)
        del studio.jobs['added']
        self.assertEqual(studio.estimate(request), completed)
        self.assertNotIn(('job', 'added'), studio._estimate_cache['features'])

    def test_mutating_a_response_does_not_change_cached_features(self):
        studio = self.studio(); request = {'preset_id': 'demo'}
        baseline = studio.estimate(request); result = studio.estimate(request)
        result['features']['model'].append('caller mutation'); result['features']['loras'].append('caller mutation')
        self.assertEqual(studio.estimate(request), baseline)

    def test_mutated_feature_inputs_invalidate_only_the_changed_job(self):
        studio = self.studio(); request = {'preset_id': 'demo'}
        changes = [('elapsed', lambda job: job.update(elapsed_seconds=240)),
                   ('finished', lambda job: job.update(finished_at=123)),
                   ('batch', lambda job: job.update(batch_count=3)),
                   ('controls', lambda job: job['controls'].update(positive='x' * 2000)),
                   ('graph', lambda job: job['graph']['1']['inputs'].update(steps=80)),
                   ('references', lambda job: job.update(references=[{'file': 'reference.png'}]))]
        for name, change in changes:
            with self.subTest(field=name):
                studio.jobs['0'] = self.job('0')
                studio.estimate(request); change(studio.jobs['0'])
                with patch.object(studio, '_estimate_features', wraps=studio._estimate_features) as features:
                    actual = studio.estimate(request)
                self.assertEqual(features.call_count, 1)
                self.assertEqual(actual, self.fresh_answer(studio, request))

    def test_sample_eligibility_is_checked_on_every_request(self):
        studio = self.studio(); request = {'preset_id': 'demo'}
        for update in ({'status': 'failed'}, {'operation': 'native.test'}, {'native_recipe': {'id': 'native'}},
                       {'prompt_ids': []}, {'graph': None}, {'elapsed_seconds': 0}, {'preset_id': 'unknown'}):
            with self.subTest(update=update):
                studio.jobs['0'] = self.job('0'); studio.estimate(request)
                studio.jobs['0'].update(update)
                self.assertEqual(studio.estimate(request)['sample_count'], 4)

    def test_catalog_mtime_edit_refreshes_metadata_and_bindings(self):
        studio = self.studio(); request = {'preset_id': 'demo', 'controls': {'steps': 32}}
        studio.estimate(request)
        preset = dict(fixture.PRESET, name='Edited', stages=['one', 'two'], steps=['2', 'steps'])
        self.write_json(self.root / 'presets/catalog.json', {'presets': [preset]})
        actual = studio.estimate(request)
        self.assertEqual(actual['features']['workflow'], 'Edited')
        self.assertEqual(actual, self.fresh_answer(studio, request))

    def test_template_mtime_edit_and_removal_are_observed(self):
        studio = self.studio(); request = {'preset_id': 'demo'}
        before = studio.estimate(request)
        graph = copy.deepcopy(fixture.GRAPH); graph['1']['inputs']['steps'] = 80
        path = self.root / fixture.PRESET['graph']; self.write_json(path, graph)
        actual = studio.estimate(request)
        self.assertEqual(actual['features']['steps'], 80)
        self.assertNotEqual(actual['estimate_seconds'], before['estimate_seconds'])
        self.assertEqual(actual, self.fresh_answer(studio, request))
        path.unlink()
        self.assertFalse(studio.estimate(request)['available'])
        path.write_text(json.dumps(fixture.GRAPH), encoding='utf-8', newline='\n')
        self.assertEqual(studio.estimate(request), before)

    def test_invalid_catalog_does_not_serve_cached_presets(self):
        studio = self.studio(); request = {'preset_id': 'demo'}
        studio.estimate(request)
        self.write_json(self.root / 'presets/catalog.json', {'presets': None})
        self.assertFalse(studio.estimate(request)['available'])

    def test_privacy_is_filtered_live_even_after_private_cache_is_warm(self):
        studio = self.studio(); regular = {'preset_id': 'demo'}; private = dict(regular, privacy='private')
        baseline = studio.estimate(regular)
        studio.jobs['private'] = dict(self.job('private', 90000), privacy='private')
        self.assertEqual(studio.estimate(private)['estimate_seconds'], 90000)
        self.assertEqual(studio.estimate(regular), baseline)
        studio.jobs['0']['privacy'] = 'private'
        self.assertEqual(studio.estimate(regular)['sample_count'], 4)
        self.assertEqual(studio.estimate(private)['sample_count'], 2)
        studio.jobs['private']['privacy'] = 'regular'
        self.assertEqual(studio.estimate(regular)['sample_count'], 5)
        self.assertEqual(studio.estimate(regular), self.fresh_answer(studio, regular))

    def test_concurrent_cold_requests_share_cache_without_studio_lock(self):
        studio = self.studio(); request = {'preset_id': 'demo'}
        self.start.stop()  # Only these HTTP-style caller threads run; no Studio worker starts.
        with studio.lock, patch.object(studio, '_estimate_features', wraps=studio._estimate_features) as features, \
             patch.object(studio, 'graph_for', wraps=studio.graph_for) as templates:
            with ThreadPoolExecutor(max_workers=4) as pool:
                futures = [pool.submit(studio.estimate, request) for _ in range(12)]
                answers = [future.result(timeout=10) for future in futures]
        self.assertTrue(all(answer == answers[0] for answer in answers))
        self.assertEqual(features.call_count, 6); self.assertEqual(templates.call_count, 1)


if __name__ == '__main__': unittest.main()
