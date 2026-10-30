"""Offline wording preview follows the submission path without registering work."""
import copy
import hashlib
import json
import unittest
from unittest.mock import patch

import test_server as fixture

server = fixture.server


class WildcardPreviewTests(unittest.TestCase):
    setUp = fixture.ServerTests.setUp
    tearDown = fixture.ServerTests.tearDown

    def studio(self, *, seed=True):
        preset, graph = copy.deepcopy(fixture.PRESET), copy.deepcopy(fixture.GRAPH)
        preset['negative'] = ['2','text']; graph['2']['inputs']['text'] = 'avoid {blur|noise}'
        preset['bindings_extra']['positive'] = [['3','text']]; graph['3'] = {'inputs':{'text':'extra __lighting__'}}
        preset['bindings_extra']['seed'] = [['3','seed']]; graph['3']['inputs']['seed'] = 1
        if not seed: preset.pop('seed'); preset['bindings_extra'].pop('seed')
        (self.root/'presets/catalog.json').write_text(json.dumps({'presets':[preset]}), encoding='utf-8', newline='\n')
        (self.root/'workflows/api/demo-api.json').write_text(json.dumps(graph), encoding='utf-8', newline='\n')
        cards = self.root/'presets/wildcards'; cards.mkdir(exist_ok=True)
        (cards/'lighting.txt').write_bytes(b'__tone__ light\n{rim|soft} light\n')
        (cards/'tone.txt').write_bytes(b'warm\ncool\n')
        return fixture.FakeStudio(self.root, [])

    def test_preview_matches_submission_and_shared_helper_for_each_seed_and_index(self):
        studio = self.studio(); payload = {'preset_id':'demo','controls':{'positive':'portrait __lighting__','seed':'9007199254740993'},'batch_count':4}
        preview = studio.wildcard_preview(payload)
        job = studio.jobs[studio.create_job(payload, enqueue=False)['id']]
        for member in preview['members']:
            index = member['index']; submitted, seed = studio._batch_graph(job, index)
            shared = copy.deepcopy(job['graph'])
            studio._resolve_prompts(shared, job['prompt_bindings'], seed, index)
            self.assertEqual(seed, 9007199254740993 + index)
            self.assertEqual(member, {'index':index,'seed':seed,'seed_text':str(seed),'positive':'\n\u2014 '.join(dict.fromkeys(submitted[n]['inputs']['text'] for n in ('1','3'))),'negative':submitted['2']['inputs']['text']})
            for node in ('1','2','3'): self.assertEqual(shared[node]['inputs']['text'], submitted[node]['inputs']['text'])
            self.assertEqual(submitted['3']['inputs']['seed'], seed)
        self.assertEqual(job['graph']['1']['inputs']['text'], payload['controls']['positive'])
        self.assertEqual(preview, studio.wildcard_preview(payload))
        for name, digest in preview['wildcard_files'].items():
            self.assertEqual(digest, hashlib.sha256((self.root/'presets/wildcards'/f'{name}.txt').read_bytes()).hexdigest())
        self.assertIn('lighting', preview['wildcard_files']); self.assertIn('tone', preview['wildcard_files'])

    def test_member_cap_and_text_truncation_without_changing_execution(self):
        studio = self.studio(); payload = {'preset_id':'demo','controls':{'positive':'x'*2100+'{a|b}','negative':'y'*2200+'{c|d}'}}
        prepared = studio.prepare(payload)
        # Production prepare currently caps batches at four; retain a defensive preview cap for future callers.
        with patch.object(studio, 'prepare', return_value=(*prepared[:4], 20)):
            preview = studio.wildcard_preview(payload)
        self.assertEqual([m['index'] for m in preview['members']], list(range(16)))
        self.assertTrue(all(len(m['positive']) == len(m['negative']) == 2000 for m in preview['members']))
        self.assertTrue(all(m['truncated'] is True for m in preview['members']))
        graph, _ = studio._batch_graph({'preset_id':'demo','graph':prepared[1]}, 0)
        self.assertEqual(len(graph['1']['inputs']['text']), 2101)

    def test_distinct_bound_texts_and_exact_truncation_boundary(self):
        studio = self.studio(); preset = studio.preset('demo')
        preset['bindings_extra']['positive'] += [['3','text']]
        for length in (2000,2001):
            with self.subTest(length=length), patch.object(studio, 'preset', return_value=preset):
                payload = {'preset_id':'demo','controls':{'negative':'plain'}}
                prepared = studio.prepare(payload); prepared[1]['3']['inputs']['text'] = 'x'*(length-1)+'{a}'
                with patch.object(studio, 'prepare', return_value=prepared): member = studio.wildcard_preview(payload)['members'][0]
                self.assertEqual(member['positive'], ('x'*(length-1)+'a')[:2000])
                self.assertEqual(member.get('truncated', False), length > 2000)

    def test_no_wildcards_returns_no_members_or_file_hashes(self):
        studio = self.studio()
        payload = {'preset_id':'demo','controls':{'positive':'plain','negative':'plain'}}
        # Remove the extra authored wildcard too.
        preset = studio.preset('demo'); preset['bindings_extra'].pop('positive')
        with patch.object(studio, 'preset', return_value=preset):
            self.assertEqual(studio.wildcard_preview(payload), {'members':[],'wildcard_files':{}})

    def test_extra_binding_wildcards_are_included_even_when_main_text_is_plain(self):
        studio = self.studio()
        preview = studio.wildcard_preview({'preset_id':'demo','controls':{'negative':'plain'}})
        self.assertEqual(len(preview['members']), 1); self.assertIn('lighting', preview['wildcard_files'])
        graph, _ = studio._batch_graph({'preset_id':'demo','graph':studio.prepare({'preset_id':'demo','controls':{'negative':'plain'}})[1]}, 0)
        self.assertEqual(preview['members'][0]['positive'], graph['3']['inputs']['text'])
        self.assertTrue(preview['members'][0]['positive'].startswith('extra '))
        self.assertEqual(preview['members'][0]['negative'], '')
        self.assertNotIn('truncated', preview['members'][0])

    def test_missing_seed_binding_is_unknown_and_still_uses_execution_rng(self):
        studio = self.studio(seed=False); payload = {'preset_id':'demo','controls':{'positive':'__lighting__'}}
        member = studio.wildcard_preview(payload)['members'][0]
        graph, seed = studio._batch_graph({'preset_id':'demo','graph':studio.prepare(payload)[1]}, 0)
        self.assertIsNone(seed); self.assertIsNone(member['seed']); self.assertTrue(member['seed_unknown'])
        self.assertEqual(member['positive'], '\n\u2014 '.join(dict.fromkeys(graph[n]['inputs']['text'] for n in ('1','3'))))

    def test_random_seed_sentinels_are_refused_as_in_execution(self):
        studio = self.studio()
        for seed in (-1, '-1', 'random'):
            with self.subTest(seed=seed):
                payload = {'preset_id':'demo','controls':{'positive':'__lighting__','seed':seed}}
                with self.assertRaises(server.StudioError): studio.wildcard_preview(payload)
                with self.assertRaises(server.StudioError): studio.prepare(payload)
        self.assertFalse(studio.jobs); self.assertTrue(studio.queue.empty()); self.assertFalse(studio.requests)

    def handler(self, studio, payload, headers=None):
        handler = server.Handler.__new__(server.Handler); handler.studio = studio; handler.path = '/api/wildcards/preview'
        handler.headers = {'Host':'127.0.0.1:8191','Origin':'http://127.0.0.1:8191',**(headers or {})}
        handler._body_json = lambda: payload; handler._drain_refused_body = lambda: None
        sent = []; handler._json = lambda status, body: sent.append((status, body))
        return handler, sent

    def test_route_uses_creation_privacy_without_jobs_queue_files_or_requests(self):
        studio = self.studio(); before = sorted(str(p) for p in self.root.rglob('*'))
        payload = {'preset_id':'demo','controls':{'positive':'private __lighting__'}}
        handler, sent = self.handler(studio, payload, {'X-Studio-Privacy':'private','X-Studio-Creation-Privacy':'private'})
        with patch.object(studio, 'prepare', wraps=studio.prepare) as prepare, patch.object(studio, 'create_job', side_effect=AssertionError('created job')):
            handler.do_POST()
        self.assertEqual(sent[0][0], 200); self.assertEqual(prepare.call_args.args[0]['privacy'], 'private')
        self.assertFalse(studio.jobs); self.assertTrue(studio.queue.empty()); self.assertFalse(studio.requests)
        self.assertEqual(before, sorted(str(p) for p in self.root.rglob('*')))

    def test_route_preserves_scope_and_creation_privacy_refusals(self):
        studio = self.studio()
        for headers, payload in (({'X-Studio-Privacy':'invalid'}, {'preset_id':'demo'}),
                ({'X-Studio-Creation-Privacy':'private'}, {'preset_id':'demo','privacy':'regular'}),
                ({'Origin':'http://elsewhere.invalid'}, {'preset_id':'demo'})):
            handler, sent = self.handler(studio, payload, headers); handler.do_POST()
            self.assertIn(sent[0][0], (400,403)); self.assertFalse(studio.jobs); self.assertTrue(studio.queue.empty())

    def test_preview_does_not_stage_reference_files_into_comfy_inputs(self):
        studio = self.studio(); name = 'a'*32 + '_source.png'
        (studio.experiments/'uploads').mkdir(parents=True)
        (studio.experiments/'uploads'/name).write_bytes(fixture.png())
        path = self.root/'workflows/api/demo-api.json'; graph = json.loads(path.read_text())
        graph['4'] = {'class_type':'LoadImage','inputs':{'image':name}}
        path.write_text(json.dumps(graph), encoding='utf-8', newline='\n')
        payload = {'preset_id':'demo','controls':{'positive':'__lighting__','reference':name}}
        studio.wildcard_preview(payload)
        self.assertFalse((studio.comfy_root/'input'/name).exists())
        self.assertFalse(studio.jobs); self.assertTrue(studio.queue.empty()); self.assertFalse(studio.requests)
        studio.preview(payload)
        self.assertEqual((studio.comfy_root/'input'/name).read_bytes(), fixture.png())


if __name__ == '__main__': unittest.main()
