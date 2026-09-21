"""Regression contracts for accelerator planning and planner diagnostics (#601)."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import unittest

import test_production as P
import test_settings_planner as S


class PlannerNumberTests(unittest.TestCase):
    def test_decimal_that_overflows_float_is_not_finite(self):
        with self.assertRaisesRegex(ValueError, 'finite number'):
            S.planner._number('1e9999')
        self.assertEqual(S.planner._number('1e9999', 7), 7.0)


class AcceleratorIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.p, self.k = copy.deepcopy(S.PRESET), copy.deepcopy(S.KB)
        self.k['loras']['a.safetensors']['role'] = 'accelerator'

    def test_disabled_accelerator_is_not_injected_or_described_as_selected(self):
        self.p['defaults'].update(lora=0, lora2=0.9)
        rows = S.planner.plan_remix(self.p, self.k, {'lora2': 0.9})
        self.assertEqual([row['label'] for row in rows], ['NIJISIS lead'])
        for row in rows:
            self.assertNotIn('lora', row['controls'])
            self.assertNotIn('lora_name', row['controls'])
            self.assertNotIn('selected accelerator', row['rationale'].lower())
            self.assertNotIn('non-accelerator', row['label'].lower())

    def test_two_active_accelerators_are_held_together(self):
        self.k['loras']['b.safetensors']['role'] = 'accelerator'
        self.k['loras']['c.safetensors'] = {
            'family': self.p['family'], 'label': 'Ordinary style', 'role': 'style',
            'source': 'https://example.invalid/c',
        }
        self.p.update(lora3=['12', 'strength_model'], lora3_name=['12', 'lora_name'])
        self.p['defaults'].update(lora=0.75, lora2=0.5, lora3=0.9, lora3_name='c.safetensors')
        rows = S.planner.plan_remix(self.p, self.k, {'lora3': 0.9})
        self.assertEqual(set(S.planner.accelerator_slots(self.p, self.k)), {'lora', 'lora2'})
        self.assertEqual([row['label'] for row in rows], ['Ordinary style lead'])
        for row in rows:
            self.assertEqual((row['controls']['lora'], row['controls']['lora2']), (0.75, 0.5))
            self.assertEqual((row['controls']['lora_name'], row['controls']['lora2_name']),
                             ('a.safetensors', 'b.safetensors'))
            self.assertIn('selected accelerator strengths', row['rationale'])

    def test_nonstandard_bound_alias_is_withheld_when_it_writes_accelerator_input(self):
        self.p['style_weight'] = list(self.p['lora'])
        self.k['families'][self.p['family']]['axes'].append({
            'id': 'style-alias', 'control': 'style_weight', 'values': [0.4, 0.8],
            'rationale': 'same physical input', 'sources': [],
        })
        report = S.planner.inspect_axes(self.p, self.k)
        row = next(item for item in report['axes_withheld'] if item['id'] == 'style-alias')
        self.assertEqual(row['code'], 'shared_accelerator_input')
        self.assertEqual(row['accelerator_slots'], ['lora'])
        self.assertNotIn('style-alias', [item['id'] for item in report['axes_available']])

    def test_choice_axis_with_no_supported_values_stays_visible_as_withheld(self):
        report = S.planner.inspect_axes(self.p, self.k, {'lora': 0})
        row = next(item for item in report['axes_withheld'] if item['id'] == 'empty')
        self.assertEqual(row['code'], 'unsupported_choice_values')
        self.assertEqual(row['documented_values'], ['karras'])
        self.assertEqual(row['offered_values'], ['simple', 'beta'])
        self.assertEqual(row['accelerator_slots'], [])


class ProductionPlannerMessageTests(unittest.TestCase):
    setUp = P.PlannedSweepTests.setUp
    tearDown = P.PlannedSweepTests.tearDown

    def test_no_axis_without_accelerator_does_not_claim_one(self):
        lab = P.FakeStudio(self.root, []).production
        with self.assertRaisesRegex(ValueError, 'documents no axis') as caught:
            lab.plan({'preset_id': 'demo', 'mode': 'grid'})
        self.assertNotIn('accelerator', str(caught.exception).lower())

    def test_no_axis_with_active_accelerator_keeps_exact_configuration_guidance(self):
        kb = json.loads(self.kb_bytes)
        kb['loras']['a.safetensors']['role'] = 'accelerator'
        (self.root/'presets/settings-kb.json').write_text(json.dumps(kb), encoding='utf-8')
        lab = P.FakeStudio(self.root, []).production
        with self.assertRaisesRegex(ValueError, 'selected accelerator settings'):
            lab.plan({'preset_id': 'planned', 'mode': 'grid',
                      'controls': {'lora': 1, 'lora_name': 'a.safetensors'}})


class PlannerFrontendIntegrityTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node required for actual frontend contract')
    def test_failed_and_superseded_requests_leave_coherent_ui_state(self):
        result = subprocess.run(
            [shutil.which('node'), str(Path(__file__).with_name('production_planner_integrity.cjs'))],
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
