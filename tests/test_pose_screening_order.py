"""Route blocks and prompt dialects are part of the frozen pose-screening identity."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from studio_workflow import pose_screening


class PoseScreeningOrderTests(unittest.TestCase):
    def source(self):
        return json.loads((ROOT / 'examples/pose-control/screening-manifest.json').read_text(encoding='utf-8'))

    def test_plan_is_blocked_by_route_and_retains_campaign_identity(self):
        source = self.source()
        self.assertTrue(all('prompt_dialect' in route['pins'] for route in source['routes']))
        plan = pose_screening.compile_plan(source)
        expected = [route['id'] for route in source['routes'] for _ in range(16)]
        self.assertEqual([cell['route_id'] for cell in plan['cells']], expected)
        self.assertEqual(plan['campaign_id'], source['campaign_id'])

    def test_prompt_dialect_pin_is_required_and_hashed(self):
        source = self.source(); del source['routes'][0]['pins']['prompt_dialect']
        with self.assertRaises(ValueError): pose_screening.compile_plan(source)
        source = self.source(); source['routes'][1]['pins']['prompt_dialect'] = 'not-a-hash'
        with self.assertRaises(ValueError): pose_screening.compile_plan(source)
        source = self.source(); source['routes'][2]['pins']['prompt_dialect'] = 'c' * 64
        self.assertEqual(pose_screening.compile_plan(copy.deepcopy(source))['candidate_count'], 48)


if __name__ == '__main__':
    unittest.main()
