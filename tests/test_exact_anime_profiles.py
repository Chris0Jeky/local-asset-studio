"""Opt-in model dialects with exact registered-template text handoff."""
import copy
import json
from pathlib import Path
import unittest
import subprocess
import sys
import tempfile

from studio_prompt.schema import new_brief, profiles, digest
from studio_prompt.compiler import compile_brief
from studio_prompt.review import bind_graph

ROOT = Path(__file__).resolve().parents[1]
AESTHETIC = 'anima-aesthetic11-prose-v1'
BASE = 'anima-base10-prose-v1'
ANIMAGINE = 'animagine40-opt-tags-v1'
LEGACY = {
    'sdxl-prose-v1': 'f17199ac8e1871213eba8cfac1715cb89ac39b69e11b52d1c360828158ef5856',
    'animagine4-tags-v1': '260c13a7d680d182a8885941c4df868f7584112371c7668b3ad9dd79e303991b',
    'flux2-prose-v1': '51168356ba5809978248336a2e80bfadd952c76cdaccd37c9a4cb9975b862556',
    'qwen-edit2511-three-v1': '09cea7f0fab891cbe5d862764741b3eca09be45da33715a4dd1d10c4c1cb23c8',
    'wan22-i2v-v1': '9115c0141f7efad31836ed42a0b749852103669088b961b6022aaf5aa26de041',
    'qwen3-voice-design-v1': 'c6420fb84f94e17cf004e377ce031a59da908783459915be5deeff81fb4ce8fc',
    'ace15-music-v1': 'b2c6ef090d794f58933e30542417c42190bfb5d67282fa62455a5d8b3248f8ce',
    'stable-audio-sfx-v1': '6b7025296e21a0c8e5de3afb1e238497284eb35b6745cdc289229d5bc67847c1',
    'trellis2-image-v1': '0ac670f8bd180e1ca7fc35b3e39e11c6ba13c2fa310b8bb6f137e135b94c7a05',
}


class ExactAnimeProfileTests(unittest.TestCase):
    def compile(self, profile_id, brief=None):
        self.assertIn(profile_id, profiles(), 'Missing opt-in exact-template profile')
        brief = brief or new_brief('An original adult keeper holding a lantern.')
        if profile_id == ANIMAGINE and not brief['tags']: brief['tags'] = ['solo', 'coat']
        return compile_brief(brief, profile_id)

    def bound(self, profile_id, preset_id):
        a = self.compile(profile_id)
        preset = next(p for p in json.loads((ROOT/'presets/catalog.json').read_text())['presets'] if p['id']==preset_id)
        g = json.loads((ROOT/preset['graph']).read_text())
        binding = {'preset_id':preset_id,'profile_sha256':a['profile_sha256'],'graph_sha256':digest(g),
                   'bindings':{k:preset[k] for k in a['fields']}}
        return a, g, binding

    def test_malformed_opt_in_contracts_fail_closed(self):
        from unittest.mock import patch
        data=json.loads((ROOT/'research/prompt-studio/profiles.json').read_text())
        self.assertIn(AESTHETIC,{p['id'] for p in data['profiles']})
        for mutation in ('unknown_check','empty_templates','duplicate_template','bad_hash','swapped_recipes','missing_checks'):
            with self.subTest(mutation=mutation):
                bad=copy.deepcopy(data);p=next(p for p in bad['profiles'] if p['id']==AESTHETIC)
                if mutation=='unknown_check':p['dialect_check']='guess'
                if mutation=='empty_templates':p['template_bindings']=[]
                if mutation=='duplicate_template':p['template_bindings'].append(copy.deepcopy(p['template_bindings'][0]))
                if mutation=='bad_hash':p['template_bindings'][0]['graph_sha256']='main'
                if mutation=='swapped_recipes':p['recipes']=['wrong']
                if mutation=='missing_checks':p.pop('dialect_check')
                with patch('studio_prompt.schema.read_json',return_value=bad),self.assertRaises(ValueError):profiles()

    def test_legacy_profile_records_keep_exact_digests(self):
        self.assertEqual({k:digest(profiles()[k]) for k in LEGACY}, LEGACY)

    def test_new_profiles_do_not_invent_tags_sampling_or_acceptance(self):
        for profile_id in (AESTHETIC, BASE, ANIMAGINE):
            with self.subTest(profile=profile_id):
                a = self.compile(profile_id)
                self.assertEqual(a['state'], 'review_required')
                self.assertEqual(set(a['fields']), {'positive', 'negative'})
                self.assertIsNone(a['token_count']); self.assertFalse(a['generation_submitted'])
                self.assertNotIn('masterpiece', a['fields']['positive'])

    def test_aesthetic_score_conflicts_cover_both_channels_without_rewriting(self):
        for field in ('tags','avoid','brief'):
            with self.subTest(field=field):
                b = new_brief('An original keeper.')
                b[field] = 'Use SCORE_7, please.' if field=='brief' else ['score_7']
                before = copy.deepcopy(b)
                a = self.compile(AESTHETIC, b)
                self.assertEqual(a['state'], 'blocked')
                self.assertTrue(any(x['code']=='MODEL_SCORE_TOKEN_CONFLICT' for x in a['errors']))
                self.assertIn('score_7', '\n'.join(a['fields'].values()).lower())
                self.assertEqual(b, before); self.assertEqual(a['intent'], before)

    def test_base_and_plain_score_word_are_not_aesthetic_conflicts(self):
        b = new_brief('A keeper beside a scoreboard.'); b['tags']=['score_7']
        self.assertEqual(self.compile(BASE, b)['errors'], [])
        b['tags']=['solo']; self.assertEqual(self.compile(AESTHETIC, b)['errors'], [])

    def test_animagine_quality_tail_is_checked_not_reordered_or_invented(self):
        b = new_brief('An original keeper.')
        for tags, blocked in ((['solo','coat'],False), (['solo','coat','masterpiece','high score'],False),
                              (['masterpiece','solo'],True), (['solo, masterpiece, coat'],True), (['solo','score_9_up'],True)):
            with self.subTest(tags=tags):
                b['tags']=tags
                a=self.compile(ANIMAGINE,b)
                self.assertEqual(a['fields']['positive'], ', '.join(tags))
                self.assertEqual(a['state']=='blocked',blocked)

    def test_declared_templates_match_current_repository_and_bind_only_text(self):
        for profile_id in (AESTHETIC,BASE,ANIMAGINE):
            a=self.compile(profile_id)
            for template in a['profile']['template_bindings']:
                with self.subTest(profile=profile_id,preset=template['preset_id']):
                    a,g,b=self.bound(profile_id,template['preset_id']); original=copy.deepcopy(g)
                    self.assertEqual(template['graph_sha256'],digest(g))
                    self.assertEqual(template['bindings'],b['bindings'])
                    result=bind_graph(a,g,b); restored=copy.deepcopy(result['workflow_preview'])
                    for key,(node,field) in b['bindings'].items(): restored[node]['inputs'][field]=g[node]['inputs'][field]
                    self.assertEqual(restored,original); self.assertEqual(g,original)
                    self.assertFalse(result['generation_submitted'])

    def test_changed_model_or_schedule_refuses_even_when_caller_rehashes(self):
        for node,field,value in (('1','unet_name','anima-base-v1.0.safetensors'), ('1','weight_dtype','fp8_e4m3fn')):
            with self.subTest(field=field):
                a,g,b=self.bound(AESTHETIC,'anima-portrait');g[node]['inputs'][field]=value;b['graph_sha256']=digest(g)
                with self.assertRaisesRegex(ValueError,'Exact profile template'): bind_graph(a,g,b)

    def test_wrong_preset_and_swapped_positive_negative_are_not_authorized(self):
        a,g,b=self.bound(AESTHETIC,'anima-portrait');b['preset_id']='anima-v1-baseline'
        with self.assertRaisesRegex(ValueError,'Exact profile template'): bind_graph(a,g,b)
        a,g,b=self.bound(AESTHETIC,'anima-portrait');b['bindings']={'positive':['5','text'],'negative':['4','text']}
        with self.assertRaisesRegex(ValueError,'Exact profile template'): bind_graph(a,g,b)

    def test_rehashed_profile_contract_tamper_does_not_change_authority(self):
        a,g,b=self.bound(AESTHETIC,'anima-portrait')
        a['profile']['template_bindings']=[];a['profile_sha256']=digest(a['profile']);b['profile_sha256']=a['profile_sha256']
        a['artifact_sha256']=digest({k:v for k,v in a.items() if k!='artifact_sha256'})
        with self.assertRaisesRegex(ValueError,'Profile/compiler drift'): bind_graph(a,g,b)
    def test_real_cli_compiles_and_refuses_rehashed_wrong_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); brief=root/'brief.json'; brief.write_text(json.dumps(new_brief('An original keeper.')))
            command=[sys.executable,str(ROOT/'scripts/studio_prompt.py')]
            run=subprocess.run(command+['compile',str(brief),'--profile',AESTHETIC],capture_output=True,text=True,timeout=15)
            self.assertEqual(run.returncode,0,run.stderr)
            a=json.loads(run.stdout);self.assertFalse(a['generation_submitted'])
            _,g,b=self.bound(AESTHETIC,'anima-portrait');b['profile_sha256']=a['profile_sha256']
            g['1']['inputs']['unet_name']='wrong.safetensors';b['graph_sha256']=digest(g)
            for name,value in [('compiled.json',a),('graph.json',g),('binding.json',b)]: (root/name).write_text(json.dumps(value))
            before={p.name:p.read_bytes() for p in root.iterdir()}
            run=subprocess.run(command+['bind',str(root/'compiled.json'),str(root/'graph.json'),str(root/'binding.json'),'--out',str(root/'result.json')],capture_output=True,text=True,timeout=15)
            self.assertEqual(run.returncode,2,run.stderr)
            self.assertIn('Exact profile template',run.stderr)
            self.assertEqual(before,{p.name:p.read_bytes() for p in root.iterdir()})


class ExactAnimeHTTPTests(unittest.TestCase):
    def test_actual_composed_handler_compiles_binds_and_refuses_changed_model(self):
        from test_prompt_startup import server
        from http.client import HTTPConnection
        import threading
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); path=root/'graph.json'
            preset=next(p for p in json.loads((ROOT/'presets/catalog.json').read_text())['presets'] if p['id']=='anima-portrait')
            original=(ROOT/preset['graph']).read_bytes();path.write_bytes(original)
            class NoRuntime:
                def __init__(self,root): self.root=root
                def preset(self,key):
                    if key!=preset['id']: raise ValueError('Unknown preset')
                    return copy.deepcopy(preset)
                def graph_for(self,p): return json.loads(path.read_bytes()),path
                def __getattr__(self,key): raise AssertionError('Unexpected runtime access: '+key)
            http=server.create_server(root,port=0,studio_factory=NoRuntime)
            thread=threading.Thread(target=http.serve_forever);thread.start()
            def post(route,value):
                connection=HTTPConnection('127.0.0.1',http.server_port,timeout=5)
                try:
                    connection.request('POST',route,json.dumps(value),headers={'Host':'127.0.0.1:8191','Origin':'http://127.0.0.1:8191','Content-Type':'application/json'})
                    reply=connection.getresponse();return reply.status,json.loads(reply.read())
                finally: connection.close()
            try:
                status,a=post('/api/prompt/compile',{'intent':new_brief('An original keeper.'),'profile_id':AESTHETIC})
                self.assertEqual(status,200,a)
                binding={'preset_id':preset['id'],'profile_sha256':a['profile_sha256'],'graph_sha256':digest(json.loads(original)),
                         'bindings':{k:preset[k] for k in a['fields']}}
                status,result=post('/api/prompt/bind',{'compiled':a,'binding':binding})
                self.assertEqual(status,200,result);self.assertFalse(result['generation_submitted']);self.assertEqual(path.read_bytes(),original)
                changed=json.loads(original);changed['1']['inputs']['unet_name']='wrong.safetensors';path.write_text(json.dumps(changed))
                binding['graph_sha256']=digest(changed);before=path.read_bytes()
                status,result=post('/api/prompt/bind',{'compiled':a,'binding':binding})
                self.assertEqual(status,400,result);self.assertFalse(result['generation_submitted'])
                self.assertIn('Exact profile template',result['error']);self.assertEqual(path.read_bytes(),before)
            finally: http.shutdown();http.server_close();thread.join(5)


if __name__=='__main__': unittest.main()
