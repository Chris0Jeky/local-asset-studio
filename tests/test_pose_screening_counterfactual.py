"""Case 8 must bind its baseline and variant donor identities into the plan."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from studio_workflow import pose_screening


class PoseScreeningCounterfactualTests(unittest.TestCase):
    def source(self):
        source = json.loads((ROOT / 'examples/pose-control/screening-manifest.json').read_text(encoding='utf-8'))
        case = source['cases'][7]
        case.pop('source_ref')
        case['source_refs'] = {
            'baseline': 'local-source-8-baseline',
            'variant': 'local-source-8-variant',
        }
        return source

    def test_pair_cells_bind_distinct_declared_sources_at_one_seed(self):
        source = self.source()
        plan = pose_screening.compile_plan(source)
        expected = source['cases'][7]['source_refs']
        for route_id in plan['route_order']:
            pair = [cell for cell in plan['cells']
                    if cell['route_id'] == route_id and cell['case_ordinal'] == 8]
            self.assertEqual([cell['slot'] for cell in pair], ['baseline', 'variant'])
            self.assertEqual([cell['source_ref'] for cell in pair],
                             [expected['baseline'], expected['variant']])
            self.assertNotEqual(pair[0]['source_ref'], pair[1]['source_ref'])
            self.assertEqual(pair[0]['seed'], pair[1]['seed'])

    def test_pair_source_identities_change_manifest_plan_and_cell_ids(self):
        source = self.source()
        first = pose_screening.compile_plan(source)
        changed = copy.deepcopy(source)
        changed['cases'][7]['source_refs']['variant'] = 'local-source-8-other-variant'
        second = pose_screening.compile_plan(changed)
        self.assertNotEqual(first['manifest_sha256'], second['manifest_sha256'])
        self.assertNotEqual(first['plan_id'], second['plan_id'])
        first_pair = [cell['id'] for cell in first['cells'] if cell['case_ordinal'] == 8]
        second_pair = [cell['id'] for cell in second['cells'] if cell['case_ordinal'] == 8]
        self.assertNotEqual(first_pair, second_pair)

    def test_rejects_missing_equal_malformed_or_ambiguous_pair_sources(self):
        variants = []
        source = self.source(); del source['cases'][7]['source_refs']['variant']; variants.append(source)
        source = self.source(); source['cases'][7]['source_refs']['variant'] = source['cases'][7]['source_refs']['baseline']; variants.append(source)
        source = self.source(); source['cases'][7]['source_refs']['baseline'] = '../private/donor.png'; variants.append(source)
        source = self.source(); source['cases'][7]['source_ref'] = 'ambiguous-third-source'; variants.append(source)
        for source in variants:
            with self.subTest(case=source['cases'][7]), self.assertRaises(ValueError):
                pose_screening.compile_plan(source)

    def test_non_counterfactual_cases_reject_pair_source_maps(self):
        source = self.source()
        source['cases'][0]['source_refs'] = {
            'baseline': 'not-applicable-a',
            'variant': 'not-applicable-b',
        }
        with self.assertRaises(ValueError):
            pose_screening.compile_plan(source)


if __name__ == '__main__':
    unittest.main()
