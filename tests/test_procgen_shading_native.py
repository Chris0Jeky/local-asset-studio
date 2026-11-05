"""Opt-in real Blender export qualification; offline mocks cannot satisfy this gate."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from procgen_shading_probe import qualify

BLENDER = os.environ.get('PROCGEN_LIVE_BLENDER')
if os.environ.get('PROCGEN_REQUIRE_SHADING_NATIVE') == '1' and not BLENDER:
    raise RuntimeError('Required shading qualification lacks explicit PROCGEN_LIVE_BLENDER executable')


@unittest.skipUnless(BLENDER, 'Explicit PROCGEN_LIVE_BLENDER required; no native shading export ran')
class NativeShading(unittest.TestCase):
    def test_round_normals_survive_export_and_preserve_hard_edges_and_geometry(self):
        if os.environ.get('PROCGEN_SHADING_EVIDENCE'):
            output = Path(os.environ['PROCGEN_SHADING_EVIDENCE'])
        else:
            temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
            output = Path(temporary.name) / 'shading'
        receipt = qualify(BLENDER, output)
        self.assertEqual(receipt['state'], 'passed', receipt['failures'])
        self.assertEqual(len(receipt['cases']), 6)
        self.assertTrue(all(len(case['lods']) == 3 for case in receipt['cases']))


if __name__ == '__main__': unittest.main()
