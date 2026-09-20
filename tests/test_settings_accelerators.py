"""Generic family sweeps may not retune a known acceleration configuration."""
import copy
import unittest

from test_settings_planner import planner, PRESET, KB, ROOT


class AcceleratorPlannerTests(unittest.TestCase):
    def setUp(self):
        self.p = copy.deepcopy(PRESET)
        self.k = copy.deepcopy(KB)
        self.k['loras']['a.safetensors']['role'] = 'accelerator'
        self.p['defaults'].update(lora=0.85, lora2=0.9)
        self.k['families']['Krea 2 Turbo']['axes'].extend([
            {'id': 'strength', 'control': 'lora', 'values': [0, 0.6, 1], 'sources': [], 'rationale': 'style ladder'},
            {'id': 'style', 'control': 'lora2', 'values': [0.6, 0.8], 'sources': [], 'rationale': 'style ladder'},
        ])

    def test_active_accelerator_holds_family_schedule_and_its_strength(self):
        self.assertEqual([a['id'] for a in planner.axes_for(self.p, self.k)], ['style'])
        for axis in ('steps', 'sampler', 'strength'):
            with self.subTest(axis=axis), self.assertRaises(ValueError):
                planner.plan_grid(self.p, self.k, {}, [axis])

    def test_current_controls_override_defaults_before_offering_axes(self):
        disabled = {'lora': '0'}
        axes = planner.axes_for(self.p, self.k, disabled)
        self.assertEqual([a['id'] for a in axes], ['steps', 'sampler', 'style'])
        self.assertEqual(len(planner.plan_grid(self.p, self.k, disabled, ['steps'])), 2)
        # A strength axis cannot turn an accelerator on with an unchanged full schedule.
        with self.assertRaises(ValueError): planner.plan_grid(self.p, self.k, disabled, ['strength'])
        ordinary = {'lora_name': 'b.safetensors'}
        self.assertIn('strength', [a['id'] for a in planner.axes_for(self.p, self.k, ordinary)])

    def test_missing_or_invalid_accelerator_strength_does_not_infer_inactive(self):
        for value in (None, True, '', 'NaN', 'Infinity', -0.5):
            with self.subTest(value=value):
                self.p['defaults']['lora'] = value
                self.assertNotIn('steps', [a['id'] for a in planner.axes_for(self.p, self.k)])
        self.p['defaults'].pop('lora')
        self.assertNotIn('steps', [a['id'] for a in planner.axes_for(self.p, self.k)])

    def test_remix_preserves_accelerator_and_only_varies_ordinary_slots(self):
        base = {'lora': '0.85', 'lora_name': 'a.safetensors', 'lora2': 0.9, 'steps': 4, 'cfg': 1}
        before = copy.deepcopy((self.p, self.k, base))
        rows = planner.plan_remix(self.p, self.k, base)
        self.assertEqual([r['label'] for r in rows], ['NIJISIS lead'])
        for row in rows:
            self.assertEqual(row['controls']['lora'], '0.85')
            self.assertEqual(row['controls']['lora_name'], 'a.safetensors')
            self.assertEqual((row['controls']['steps'], row['controls']['cfg']), (4, 1))
            self.assertIn('accelerator', row['rationale'])
            self.assertIn('unchanged', row['rationale'])
        self.assertEqual((self.p, self.k, base), before)

    def test_default_accelerator_is_retained_and_counted_in_total(self):
        self.k['families']['Krea 2 Turbo']['lora_rules']['warn_total_strength'] = 1.5
        row = planner.plan_remix(self.p, self.k, {})[0]
        self.assertEqual(row['controls']['lora'], 0.85)
        self.assertEqual(row['controls']['lora_name'], 'a.safetensors')
        self.assertIn('exceeds the documented 1.5', row['rationale'])

    def test_accelerator_only_has_no_style_remix(self):
        with self.assertRaisesRegex(ValueError, 'non-accelerator'):
            planner.plan_remix(self.p, self.k, {'lora2': 0})

    def test_sixth_companion_slot_is_also_held(self):
        self.p['bindings_extra'] = {'lora6': [['99', 'strength_model']]}
        self.p['defaults'].update(lora6=1, lora6_name='a.safetensors')
        row = planner.plan_remix(self.p, self.k, {'lora': 0})[0]
        self.assertEqual(row['controls']['lora6'], 1)
        self.assertEqual(row['controls']['lora6_name'], 'a.safetensors')
        self.assertEqual(row['label'], 'NIJISIS lead')

    def test_unknown_companion_only_strength_refuses_instead_of_counting_zero(self):
        self.p['bindings_extra']={'lora6':[['99','strength_model']]}
        self.p['defaults']['lora6_name']='a.safetensors'
        for value in (None,True,'NaN','Infinity','1e9999'):
            with self.subTest(value=value):
                base={'lora':0}
                if value is not None:base['lora6']=value
                with self.assertRaisesRegex(ValueError,'finite accelerator strength'):
                    planner.plan_remix(self.p,self.k,base)
        row=planner.plan_remix(self.p,self.k,{'lora':0,'lora6':0.75})[0]
        self.assertEqual(row['controls']['lora6'],0.75)

    def test_omitted_companion_strength_is_not_proved_inactive_by_primary_default(self):
        self.p['defaults']['lora']=0
        self.p['bindings_extra']={'lora':[['10','strength_clip']]}
        self.assertNotIn('steps',[a['id'] for a in planner.axes_for(self.p,self.k)])
        # An explicit zero applies to both primary and companion inputs.
        self.assertIn('steps',[a['id'] for a in planner.axes_for(self.p,self.k,{'lora':0})])

    def test_remix_does_not_flatten_unknown_companion_defaults(self):
        self.p['defaults']['lora']=0
        self.p['bindings_extra']={'lora':[['10','strength_clip']]}
        before=copy.deepcopy((self.p,self.k))
        with self.assertRaisesRegex(ValueError,'companion'):
            planner.plan_remix(self.p,self.k,{})
        # An explicit value is a reviewed write to every bound strength.
        row=planner.plan_remix(self.p,self.k,{'lora':0})[0]
        self.assertEqual(row['controls']['lora'],0)
        self.assertEqual((self.p,self.k),before)

    def test_alias_controls_cannot_change_a_held_accelerator(self):
        self.p['bindings_extra'] = {'lora2': [['10', 'strength_model']]}
        self.assertEqual(planner.axes_for(self.p, self.k), [])
        with self.assertRaisesRegex(ValueError, 'non-accelerator'):
            planner.plan_remix(self.p, self.k, {})

    def test_disabled_accelerator_does_not_claim_held_provenance(self):
        self.p['lora3'] = ['12', 'strength_model']
        self.p['lora3_name'] = ['12', 'lora_name']
        self.p['defaults'].update(lora=0, lora2=0.9, lora3=0.8,
                                  lora3_name='b.safetensors')
        rows = planner.plan_remix(self.p, self.k, {'lora': 0})
        blend = rows[-1]
        self.assertEqual(blend['label'], 'All active LoRAs at 0.8')
        self.assertNotIn('selected accelerator', blend['rationale'])
        self.assertTrue(all('selected accelerator' not in row['rationale'] for row in rows))

    def test_anima_generic_steps_exclude_conditional_turbo_value(self):
        kb, _ = planner.load_kb(ROOT)
        steps = next(a for a in kb['families']['Anima']['axes'] if a['id'] == 'steps')
        self.assertNotIn(8, steps['values'])
        # Exact resource-scoped authored advice survives, rather than a new registry.
        claim = next(c for c in kb['guidance']['claims'] if c['id'] == 'anima-turbo-authored-schedule')
        self.assertTrue(claim['when'])
        self.assertTrue(any(s['target'].get('control') == 'steps' and s['recommended'] == {'values': [8]} for s in claim['settings']))


if __name__ == '__main__': unittest.main()
