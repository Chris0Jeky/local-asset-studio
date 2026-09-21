"""Frozen pose-screening identities must not drift behind syntactically valid fields."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from studio_workflow import pose_screening


class PoseScreeningIdentityTests(unittest.TestCase):
    def source(self):
        return json.loads((ROOT / 'examples/pose-control/screening-manifest.json').read_text(encoding='utf-8'))

    def test_rejects_route_ids_swapped_onto_different_mechanisms(self):
        source = self.source()
        source['routes'][0]['id'], source['routes'][2]['id'] = (
            source['routes'][2]['id'], source['routes'][0]['id'])
        with self.assertRaises(ValueError):
            pose_screening.compile_plan(source)

    def test_rejects_case_specific_observation_drift(self):
        for index in range(8):
            source = self.source()
            source['cases'][index]['required_observations'] = ['owner_acceptance']
            with self.subTest(case=source['cases'][index]['id']), self.assertRaises(ValueError):
                pose_screening.compile_plan(source)

    def test_rejects_case_specific_observation_reordering(self):
        source = self.source()
        source['cases'][6]['required_observations'] = list(
            reversed(source['cases'][6]['required_observations']))
        with self.assertRaises(ValueError):
            pose_screening.compile_plan(source)


if __name__ == '__main__':
    unittest.main()
