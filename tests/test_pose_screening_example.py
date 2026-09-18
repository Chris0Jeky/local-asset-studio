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
        self.assertEqual({cell['source_ref'] for cell in plan['cells']},
                         {'local-source-' + str(i) for i in range(1, 9)})
        for route in source['routes']:
            for value in route['pins'].values():
                self.assertEqual(len(set(value)), 1, 'example pins must remain visibly synthetic')


if __name__ == '__main__':
    unittest.main()
