"""The checked-in pose screen is a valid synthetic example, not execution evidence."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from studio_workflow import pose_screening


class PoseScreeningExampleTests(unittest.TestCase):
    def test_example_compiles_without_real_sources_or_execution_authority(self):
        path = ROOT / 'examples/pose-control/screening-manifest.json'
        source = json.loads(path.read_text(encoding='utf-8'))
        plan = pose_screening.compile_plan(source)
        self.assertEqual(plan['candidate_count'], 48)
        self.assertFalse(plan['execution_authorized'])
        self.assertFalse(plan['generation_submitted'])
        expected_sources = {'local-source-' + str(i) for i in range(1, 8)} | {
            'local-source-8-baseline', 'local-source-8-variant'
        }
        self.assertEqual({cell['source_ref'] for cell in plan['cells']}, expected_sources)
        pair = [cell for cell in plan['cells']
                if cell['route_id'] == plan['route_order'][0] and cell['case_ordinal'] == 8]
        self.assertNotEqual(pair[0]['source_ref'], pair[1]['source_ref'])
        for route in source['routes']:
            for value in route['pins'].values():
                self.assertEqual(len(set(value)), 1, 'example pins must remain visibly synthetic')


if __name__ == '__main__':
    unittest.main()
