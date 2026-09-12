"""Plan sweeps from a documented knowledge base without a catalog or a GPU."""
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).parents[1]
SPEC=importlib.util.spec_from_file_location('settings_planner',ROOT/'app/settings_planner.py')
planner=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(planner)

# Small inline fixture: the planner must work from the Contract 4 shape alone,
# never from whichever presets/settings-kb.json happens to be on disk.
KB={'version':1,'updated':'2026-09-12','families':{'Krea 2 Turbo':{
      'prompt':{'style':'natural language paragraph','negative':None},
      'defaults':{'sampler':'euler','scheduler':'simple','steps':8,'cfg':1.0},
      'resolutions':[[768,1152]],
      'axes':[{'id':'steps','control':'steps','values':[8,15],'rationale':'distilled for 8; the target used 15','sources':['https://example.invalid/steps']},
              {'id':'sampler','control':'sampler','values':['euler','euler_ancestral','er_sde'],'rationale':'community LoRA cards','sources':['https://example.invalid/sampler']},
              {'id':'frames','control':'frames','values':[16],'rationale':'not an image control','sources':[]},
              {'id':'empty','control':'scheduler','values':['karras'],'rationale':'not offered here','sources':[]}],
      'lora_rules':{'max_active':3,'warn_total_strength':2.5,'ladder':[1.0,0.8,0.6],'notes':['stack effect unmeasured']}}},
    'loras':{'a.safetensors':{'family':'Krea 2 Turbo','label':'TextFusion','role':'adherence','source':'https://example.invalid/a','notes':['no trigger']},
             'b.safetensors':{'family':'Krea 2 Turbo','label':'NIJISIS','role':'style','source':'https://example.invalid/b','mirror':'https://example.invalid/b-mirror'}}}

PRESET={'id':'krea-anime-atelier','family':'Krea 2 Turbo','steps':['7','steps'],'cfg':['7','cfg'],
        'sampler':['7','sampler_name'],'scheduler':['7','scheduler'],
        'lora':['10','strength_model'],'lora_name':['10','lora_name'],
        'lora2':['11','strength_model'],'lora2_name':['11','lora_name'],
        'choices':{'sampler':['euler','euler_ancestral'],'scheduler':['simple','beta']},
        'defaults':{'steps':15,'cfg':1.0,'lora':1.0,'lora_name':'a.safetensors','lora2':0.0,'lora2_name':'b.safetensors'}}


class KnowledgeBaseTests(unittest.TestCase):
    def test_missing_file_is_an_empty_library_not_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            kb,digest=planner.load_kb(Path(tmp))
            self.assertEqual((kb['families'],kb['loras'],digest),({},{},''))
            self.assertEqual(planner.axes_for(PRESET,kb),[])

    def test_digest_is_the_file_on_disk_even_when_its_json_is_broken(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'presets').mkdir()
            raw=json.dumps(KB).encode('utf-8');(root/'presets/settings-kb.json').write_bytes(raw)
            kb,digest=planner.load_kb(root)
            self.assertEqual(digest,hashlib.sha256(raw).hexdigest())
            self.assertIn('Krea 2 Turbo',kb['families'])
            (root/'presets/settings-kb.json').write_text('{not json',encoding='utf-8')
            broken,broken_digest=planner.load_kb(root)
            self.assertEqual(broken['families'],{})
            self.assertEqual(len(broken_digest),64)


class AxisTests(unittest.TestCase):
    def test_only_bound_controls_and_offered_choices_survive(self):
        axes=planner.axes_for(PRESET,KB)
        self.assertEqual([a['id'] for a in axes],['steps','sampler'])
        self.assertEqual(axes[1]['values'],['euler','euler_ancestral'])
        self.assertEqual(axes[0]['sources'],['https://example.invalid/steps'])

    def test_companion_only_bindings_count_as_bound(self):
        preset=dict(PRESET);preset.pop('steps');preset['bindings_extra']={'steps':[['8','steps']]}
        self.assertIn('steps',[a['id'] for a in planner.axes_for(preset,KB)])

    def test_unknown_family_documents_nothing(self):
        self.assertEqual(planner.axes_for(dict(PRESET,family='Nonexistent'),KB),[])


class GridTests(unittest.TestCase):
    def test_first_axis_varies_slowest_and_controls_merge_over_the_base(self):
        variants=planner.plan_grid(PRESET,KB,{'seed':7,'positive':'a witch'},['steps','sampler'])
        self.assertEqual([v['label'] for v in variants],
                         ['steps=8 · sampler=euler','steps=8 · sampler=euler_ancestral','steps=15 · sampler=euler','steps=15 · sampler=euler_ancestral'])
        self.assertEqual(variants[2]['controls'],{'seed':7,'positive':'a witch','steps':15,'sampler':'euler'})
        self.assertEqual(variants[0]['sources'],['https://example.invalid/steps','https://example.invalid/sampler'])
        self.assertIn('distilled for 8',variants[0]['rationale'])

    def test_truncation_and_refused_limits_and_axes(self):
        self.assertEqual(len(planner.plan_grid(PRESET,KB,{},['steps','sampler'],limit=3)),3)
        for bad in (0,9,'3',2.0,True):
            with self.subTest(limit=bad),self.assertRaisesRegex(ValueError,'one and eight'):planner.plan_grid(PRESET,KB,{},['steps'],limit=bad)
        with self.assertRaisesRegex(ValueError,'Unknown or unbound axis'):planner.plan_grid(PRESET,KB,{},['frames'])
        with self.assertRaisesRegex(ValueError,'at least one documented axis'):planner.plan_grid(PRESET,KB,{},[])

    def test_a_repeated_axis_is_not_a_second_dimension(self):
        self.assertEqual(len(planner.plan_grid(PRESET,KB,{},['steps','steps'])),2)


class RemixTests(unittest.TestCase):
    def test_one_variant_per_active_slot_plus_a_blend(self):
        variants=planner.plan_remix(PRESET,KB,{'lora':1.0,'lora2':0.9})
        self.assertEqual([v['label'] for v in variants],['TextFusion lead','NIJISIS lead','All active LoRAs at 0.8'])
        self.assertEqual([(v['controls']['lora'],v['controls']['lora2']) for v in variants],[(1.0,0.6),(0.6,1.0),(0.8,0.8)])
        self.assertEqual(variants[1]['sources'],['https://example.invalid/b','https://example.invalid/b-mirror'])
        self.assertIn('leads at 1.0',variants[0]['rationale'])

    def test_off_slots_stay_off_and_preset_defaults_supply_the_base(self):
        variants=planner.plan_remix(PRESET,KB,{})
        self.assertEqual([v['label'] for v in variants],['TextFusion lead'])
        self.assertNotIn('lora2',variants[0]['controls'])
        with self.assertRaisesRegex(ValueError,'at least one LoRA slot'):planner.plan_remix(PRESET,KB,{'lora':0})

    def test_documented_total_strength_warning_is_carried_into_the_rationale(self):
        kb=json.loads(json.dumps(KB));kb['families']['Krea 2 Turbo']['lora_rules']['warn_total_strength']=1.0
        variants=planner.plan_remix(PRESET,kb,{'lora':1.0,'lora2':1.0})
        self.assertTrue(all('exceeds the documented 1.0' in v['rationale'] for v in variants))

    def test_an_explicit_ladder_overrides_the_family_and_needs_two_steps(self):
        variants=planner.plan_remix(PRESET,KB,{'lora':1.0,'lora2':1.0},ladder=[1.2,0.5])
        self.assertEqual([(v['controls']['lora'],v['controls']['lora2']) for v in variants],[(1.2,0.5),(0.5,1.2),(0.5,0.5)])
        with self.assertRaisesRegex(ValueError,'at least two strengths'):planner.plan_remix(PRESET,KB,{'lora':1.0},ladder=[1.0])

    def test_unnamed_slots_fall_back_to_the_file_stem_or_the_slot(self):
        preset=dict(PRESET,defaults={'lora':1.0,'lora_name':'unlisted-lora.safetensors'})
        self.assertEqual(planner.plan_remix(preset,KB,{})[0]['label'],'unlisted-lora lead')


class DescribeTests(unittest.TestCase):
    def test_description_shows_settings_without_the_prompt(self):
        variant=planner.plan_grid(PRESET,KB,{'positive':'a very long prompt'},['steps'])[0]
        text=planner.describe(variant)
        self.assertIn('steps=8',text);self.assertNotIn('long prompt',text);self.assertIn('distilled for 8',text)


if __name__=='__main__':unittest.main()
