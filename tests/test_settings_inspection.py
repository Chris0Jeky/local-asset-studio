"""Explain the existing accelerator policy without creating a new planner."""
import copy
import unittest

import test_settings_planner as F


class SettingsInspectionTests(unittest.TestCase):
    def setUp(self):
        self.p, self.k = copy.deepcopy(F.PRESET), copy.deepcopy(F.KB)
        self.k['loras']['a.safetensors']['role'] = 'accelerator'
        self.k['families'][self.p['family']]['axes'].extend([
            {'id': 'accelerator', 'control': 'lora', 'values': [0.6, 1]},
            {'id': 'appearance', 'control': 'lora2', 'values': [0.6, 1]},
        ])

    def inspect(self, controls=None):
        self.assertTrue(callable(getattr(F.planner, 'inspect_axes', None)), 'Missing shared settings inspection')
        return F.planner.inspect_axes(self.p, self.k, controls)

    def test_inspection_explains_held_axes_and_preserves_available_contract(self):
        before = copy.deepcopy((self.p, self.k))
        report = self.inspect()
        self.assertEqual(report['axes_available'], F.planner.axes_for(self.p, self.k))
        self.assertEqual([r['id'] for r in report['axes_withheld']], ['steps', 'sampler', 'empty', 'accelerator'])
        self.assertEqual([r['code'] for r in report['axes_withheld']],
                         ['accelerator_schedule', 'accelerator_schedule', 'unsupported_choice_values', 'accelerator_strength'])
        held=[r for r in report['axes_withheld'] if r['code']!='unsupported_choice_values']
        self.assertTrue(all(r['accelerator_slots'] == ['lora'] for r in held))
        unavailable=next(r for r in report['axes_withheld'] if r['id']=='empty')
        self.assertEqual((unavailable['documented_values'],unavailable['offered_values']),(['karras'],['simple','beta']))
        self.assertIn('not installed-byte', report['notice'])
        self.assertEqual((self.p, self.k), before)
        report['axes_available'][0]['values'].clear()
        self.assertEqual((self.p, self.k), before)

    def test_explicit_zero_restores_schedule_but_not_accelerator_strength_sweep(self):
        report = self.inspect({'lora': '0'})
        self.assertEqual([r['id'] for r in report['axes_withheld']], ['empty', 'accelerator'])
        self.assertEqual(report['axes_available'], F.planner.axes_for(self.p, self.k, {'lora': '0'}))

    def test_shared_binding_hold_identifies_the_actual_accelerator(self):
        self.p['bindings_extra'] = {'lora2': [self.p['lora']]}
        report = self.inspect()
        row = next(r for r in report['axes_withheld'] if r['id'] == 'appearance')
        self.assertEqual(row['code'], 'shared_accelerator_input')
        self.assertEqual(row['accelerator_slots'], ['lora'])
        self.assertEqual(report['axes_available'], [])

    def test_unknown_activity_is_not_claimed_active_or_compatible(self):
        for value in (None, True, 'NaN', '1e9999'):
            with self.subTest(value=value):
                row = self.inspect({'lora': value})['axes_withheld'][0]
                self.assertIn('inactivity is not established', row['message'])
        # Unknown filenames do not receive invented accelerator identities.
        report = self.inspect({'lora_name': 'unknown.safetensors'})
        self.assertEqual([r['id'] for r in report['axes_withheld']], ['empty'])
        self.assertIn('unknown files', report['notice'].lower())

    def test_only_bound_offered_axes_are_classified_and_report_is_deterministic(self):
        self.assertEqual(self.inspect(), self.inspect())
        ids = [r['id'] for r in self.inspect()['axes_withheld']]
        self.assertNotIn('frames', ids)
        self.assertIn('empty', ids)
        self.assertEqual(next(r for r in self.inspect()['axes_withheld'] if r['id']=='empty')['code'],
                         'unsupported_choice_values')


if __name__ == '__main__': unittest.main()
