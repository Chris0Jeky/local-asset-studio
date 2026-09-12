import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts import character_edit as ed
from scripts.character_edit_demo import create
from scripts.character_study import read_json, sha

ROOT = Path(__file__).resolve().parents[1]

class EditContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'job'; create(self.root)
        self.doc = read_json(self.root/'document.json'); self.intent = read_json(self.root/'intent.json')
        self.cat = read_json(ROOT/'research/character-consistency/edit-routes.json')
    def plan(self): return ed.make_plan(self.doc,self.intent,self.cat)
    def rebind(self): self.intent['document_sha256']=sha(self.doc)
    def test_valid_reproducible_plan(self):
        a=self.plan(); self.assertEqual(a,self.plan()); self.assertFalse(a['submits_generation']); ed.check_plan(a)
    def test_stale_revision(self):
        self.doc['revision']+=1
        with self.assertRaises(ValueError): self.plan()
    def test_stale_source(self):
        self.doc['source']['sha256']='0'*64
        with self.assertRaises(ValueError): self.plan()
    def test_actor_local_references(self):
        refs=self.plan()['reference_bindings']; self.assertEqual(['amber','violet'],[r['actor'] for r in refs])
        self.assertEqual(['neutral','neutral'],[r['reference_id'] for r in refs])
    def test_identity_not_silently_editable(self):
        self.intent['changes'][0]['facet']='identity'
        with self.assertRaises(ValueError): self.plan()
    def test_costume_not_anatomy_edit(self):
        self.intent['operation']='anatomy-repair'
        with self.assertRaises(ValueError): self.plan()
    def test_anatomy_route(self):
        self.intent['operation']='anatomy-repair'; self.intent['changes'][0]['facet']='anatomy'
        self.assertIn('actor:amber:anatomy',self.plan()['changes'])
    def test_original_instruction_preserved(self):
        instruction='Correct this fictional figure’s hand. Preserve σ, 対 and the brief exactly.'
        self.intent['changes'][0]['instruction']=instruction
        self.assertEqual(instruction,self.plan()['intent']['changes'][0]['instruction'])
    def test_no_silent_extra_fields(self):
        self.intent['unrestricted']=True
        with self.assertRaises(ValueError): self.plan()
    def test_outside_box(self):
        self.intent['context_box']=[0,0,800,600]
        with self.assertRaises(ValueError): self.plan()
    def test_boolean_box(self):
        self.intent['context_box'][0]=True
        with self.assertRaises(ValueError): self.plan()
    def test_boolean_version(self):
        self.doc['schema_version']=True; self.rebind()
        with self.assertRaises(ValueError): self.plan()
    def test_float_version(self):
        self.doc['schema_version']=1.0; self.rebind()
        with self.assertRaises(ValueError): self.plan()
    def test_alignment_explicit(self):
        self.intent['patch_alignment']=7
        with self.assertRaises(ValueError): self.plan()
    def test_unknown_actor(self):
        self.intent['changes'][0]['actor']='missing'
        with self.assertRaises(ValueError): self.plan()
    def test_duplicate_actor(self):
        self.doc['actors'].append(copy.deepcopy(self.doc['actors'][0])); self.rebind()
        with self.assertRaises(ValueError): self.plan()
    def test_actor_identity_required(self):
        self.doc['actors'][1]['references'][0]['role']='style'; self.rebind()
        with self.assertRaises(ValueError): self.plan()
    def test_local_scene_redesign_rejected(self):
        self.intent['scene_change']=self.doc['scene']
        with self.assertRaises(ValueError): self.plan()
    def test_unknown_relation(self):
        self.doc['relations']=[dict(kind='contact',**{'from':'amber','to':'absent','note':'Hands'})]; self.rebind()
        with self.assertRaises(ValueError): self.plan()
    def test_occlusion_cycle(self):
        self.doc['relations']=[{'kind':'in_front_of','from':a,'to':b,'note':'Depth'} for a,b in [('amber','violet'),('violet','amber')]]; self.rebind()
        with self.assertRaises(ValueError): self.plan()
    def set_layout(self):
        self.intent['layout']={'actors':[{'id':a['id'],'bounds':a['bounds'][:],'pose_reference':None} for a in self.doc['actors']],
            'occlusion_order':['amber','violet'],'contact_regions':[{'actors':['amber','violet'],'bounds':[135,100,220,170],'instruction':'Review the meeting hands'}]}
    def test_interaction_requires_contact(self):
        self.intent['operation']='interaction'; self.intent['changes']=[{'actor':a,'facet':'pose','instruction':'Shake hands'} for a in ['amber','violet']]
        with self.assertRaises(ValueError): self.plan()
        self.doc['relations']=[{'kind':'contact','from':'amber','to':'violet','note':'Right hands meet between both wrists'}]; self.rebind(); self.set_layout()
        self.assertIn('contact-review',[s['id'] for s in self.plan()['steps']])
    def test_scenario_per_actor_passes(self):
        self.intent['operation']='scenario'; self.intent['scene_change']=copy.deepcopy(self.doc['scene'])
        self.intent['changes']=[{'actor':a,'facet':'placement','instruction':'Stand at the observatory railing'} for a in ['amber','violet']]
        self.set_layout(); plan=self.plan(); self.assertEqual(['amber','violet'],[s['actor'] for s in plan['steps'] if s.get('actor')])
        self.assertIn('scene:lighting',plan['changes'])
    def test_scenario_budget_covers_actor_passes(self):
        self.intent['operation']='scenario'; self.intent['scene_change']=self.doc['scene']
        self.intent['changes']=[{'actor':a,'facet':'placement','instruction':'Move'} for a in ['amber','violet']]
        self.set_layout(); self.intent['budget'].update(max_candidates=1,max_repairs=0)
        with self.assertRaises(ValueError): self.plan()
    def test_order_agrees_with_front_relation(self):
        self.intent['operation']='scenario'; self.intent['scene_change']=self.doc['scene']
        self.intent['changes']=[{'actor':a,'facet':'placement','instruction':'Move'} for a in ['amber','violet']]
        self.doc['relations']=[{'kind':'in_front_of','from':'amber','to':'violet','note':'Amber in front'}]
        self.rebind(); self.set_layout()
        with self.assertRaises(ValueError): self.plan()
        self.intent['layout']['occlusion_order']=['violet','amber']; self.plan()
    def test_layout_required_for_scenario(self):
        self.intent['operation']='scenario'; self.intent['changes'][0]['facet']='placement'; self.intent['scene_change']=self.doc['scene']
        with self.assertRaises(ValueError): self.plan()
    def test_local_operation_rejects_layout(self):
        self.set_layout()
        with self.assertRaises(ValueError): self.plan()
    def test_scenario_layout_duplicates(self):
        self.intent['operation']='scenario'; self.intent['scene_change']=self.doc['scene']
        self.intent['changes']=[{'actor':a,'facet':'placement','instruction':'Move'} for a in ['amber','violet']]
        self.set_layout(); self.intent['layout']['actors'][1]['id']='amber'
        with self.assertRaises(ValueError): self.plan()
    def test_occlusion_order_must_be_complete(self):
        self.intent['operation']='scenario'; self.intent['scene_change']=self.doc['scene']
        self.intent['changes']=[{'actor':a,'facet':'placement','instruction':'Move'} for a in ['amber','violet']]
        self.set_layout(); self.intent['layout']['occlusion_order']=['amber','amber']
        with self.assertRaises(ValueError): self.plan()
    def test_repair_budget_not_extra(self):
        self.intent['budget']['max_repairs']=3; self.intent['budget']['max_candidates']=3
        with self.assertRaises(ValueError): self.plan()
    def test_rehashed_derived_tampering(self):
        plan=self.plan(); plan['steps']=[]; plan['plan_sha256']=sha({k:v for k,v in plan.items() if k!='plan_sha256'})
        with self.assertRaises(ValueError): ed.check_plan(plan)
    def test_plan_boolean_alias(self):
        plan=self.plan(); plan['submits_generation']=0
        with self.assertRaises(ValueError): ed.check_plan(plan)
    def test_hosted_excluded_without_fallback(self):
        self.assertNotIn('gpt-image-hosted',self.plan()['candidate_routes'])
    def test_documented_weight_restrictions_excluded(self):
        self.assertNotIn('klein-edit-local',self.plan()['candidate_routes'])
    def test_unknown_is_warning_not_unrestricted(self):
        report=next(r for r in self.plan()['route_reports'] if r['route_id']=='qwen-edit-local')
        self.assertTrue(report['eligible_by_preference']); self.assertTrue(report['warnings'])
        self.assertEqual('unknown',report['content_policy']['input_filter'])
    def test_strict_unknown_returns_no_neural_route(self):
        self.intent['policy_preference']['unknown_policy']='exclude'
        self.assertEqual('no_route_matches_preference',self.plan()['readiness'])
    def test_upstream_not_runtime_policy(self):
        self.intent['policy_preference']['exclude_documented_weight_restrictions']=False
        self.assertIn('klein-edit-local',self.plan()['candidate_routes'])
    def test_known_filter_excluded(self):
        self.cat['routes'][1]['content_policy']['input_filter']='present'
        self.assertNotIn('qwen-edit-local',self.plan()['candidate_routes'])
    def test_route_claim_unrestricted_rejected(self):
        self.cat['routes'][1]['content_policy']['input_filter']='unrestricted'
        with self.assertRaises(ValueError): self.plan()
    def test_boolean_preference_required(self):
        self.intent['policy_preference']['local_only']=1
        with self.assertRaises(ValueError): self.plan()
    def test_relative_input_path(self):
        self.doc['source']['path']='../escape.png'; self.rebind()
        with self.assertRaises(ValueError): self.plan()
    def test_duplicate_json_rejected(self):
        f=self.root/'bad.json'; f.write_text('{"x":1,"x":2}')
        with self.assertRaises(ValueError): read_json(f)
    def test_nonfinite_json_rejected(self):
        f=self.root/'bad.json'; f.write_text('{"x":NaN}')
        with self.assertRaises(ValueError): read_json(f)
    def test_dependency_invalidation_specific(self):
        nodes=[{'id':'amber-panel','depends_on':[],'reads':['actor:amber:costume']},
               {'id':'violet-panel','depends_on':[],'reads':['actor:violet:costume']},
               {'id':'pair-card','depends_on':['amber-panel','violet-panel'],'reads':[]}]
        self.assertEqual(['amber-panel','pair-card'],ed.affected_outputs(nodes,['actor:amber:costume']))
    def test_dependency_cycle_rejected(self):
        nodes=[{'id':a,'depends_on':[b],'reads':[]} for a,b in [('aa','bb'),('bb','aa')]]
        with self.assertRaises(ValueError): ed.affected_outputs(nodes,['layout'])
    def test_dependency_unknown_rejected(self):
        with self.assertRaises(ValueError): ed.affected_outputs([{'id':'aa','depends_on':['missing'],'reads':[]}],['layout'])
    def test_cli_describe(self):
        run=subprocess.run([sys.executable,str(ROOT/'scripts/character_edit.py'),'describe'],capture_output=True,text=True)
        self.assertEqual(0,run.returncode,run.stderr); self.assertFalse(json.loads(run.stdout)['defaults']['network'])
    def test_cli_plan_new_output_only(self):
        cmd=[sys.executable,str(ROOT/'scripts/character_edit.py'),'plan','--document',str(self.root/'document.json'),
             '--intent',str(self.root/'intent.json'),'--out',str(self.root/'new-plan.json')]
        self.assertEqual(0,subprocess.run(cmd,capture_output=True).returncode)
        self.assertEqual(2,subprocess.run(cmd,capture_output=True).returncode)
    def test_benchmark_arithmetic_and_unknown_measurements(self):
        design=read_json(ROOT/'research/character-consistency/edit-benchmark.json')
        d=design['design']; n=d['original_identities']*len(d['tasks_per_identity'])*len(d['strategies'])*d['seeds_per_task_strategy']
        self.assertEqual(n,d['primary_attempts'])
        self.assertEqual(n+len(d['strategies'])*d['repair_attempts_reserved_per_strategy'],d['total_image_candidate_cap'])
        self.assertTrue(all(v is None for v in design['measured'].values())); self.assertEqual('not_run',design['status'])
    def test_registered_presets_exist_in_repo(self):
        catalog=ROOT/'presets/catalog.json'
        if not catalog.is_file(): self.skipTest('Full native preset catalog checked in repository CI')
        ids={p['id'] for p in read_json(catalog)['presets']}
        for route in self.cat['routes']:
            self.assertLessEqual(set(route['preset_ids']),ids)

if __name__=='__main__': unittest.main()
