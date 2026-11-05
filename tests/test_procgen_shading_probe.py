import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from engine_fixture import glb_bytes, model

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import procgen_shading_probe as probe
from engine_validation import EvidenceError


class ExportedNormals(unittest.TestCase):
    def inspect(self, doc, binary):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'fixture.glb'; path.write_bytes(glb_bytes(doc, binary))
            return probe.read_triangles(path)

    def test_reads_actual_position_normal_and_index_accessors(self):
        doc, binary = model()
        triangles = self.inspect(doc, binary)['Panel']
        self.assertEqual(len(triangles), 1)
        self.assertEqual(triangles[0][0][1], (0, 0, 1))
        self.assertEqual(probe.normal_summary(triangles)['varying_triangles'], 0)
        changed = copy.deepcopy(triangles)
        changed[0][1] = (changed[0][1][0], (0, .6, .8))
        self.assertEqual(probe.normal_summary(changed)['varying_triangles'], 1)
        self.assertEqual(probe.geometry_key(changed), probe.geometry_key(triangles))

    def test_missing_and_zero_normals_fail_closed(self):
        doc, binary = model(); del doc['meshes'][0]['primitives'][0]['attributes']['NORMAL']
        with self.assertRaises(EvidenceError): self.inspect(doc, binary)
        with self.assertRaises(EvidenceError): probe.normal_summary([[((0, 0, 0), (0, 0, 0))] * 3])

    def test_rejects_truncated_views_and_out_of_range_indices(self):
        doc, binary = model(); doc['bufferViews'][0]['byteLength'] = 1
        with self.assertRaises(EvidenceError): self.inspect(doc, binary)
        doc, binary = model(); doc['accessors'][2]['count'] = 99
        with self.assertRaises(EvidenceError): self.inspect(doc, binary)

    def test_smooth_rim_cannot_hide_flat_cone_side(self):
        flat_cone = [((0, 0, 0), (0, 0, 1)), ((1, 1, 0), (0, 0, 1)), ((0, 1, 1), (0, 0, 1))]
        smooth_rim = [((0, 0, 0), (1, 0, 0)), ((1, 0, 0), (.6, 0, .8)), ((1, 1, 0), (0, 0, 1))]
        hard_cap = [((0, 0, 0), (0, 1, 0)), ((1, 0, 0), (0, 1, 0)), ((0, 0, 1), (0, 1, 0))]
        summary = probe.normal_summary([flat_cone, smooth_rim, hard_cap])
        self.assertEqual(summary, {'triangles': 3, 'varying_triangles': 1, 'hard_cap_triangles': 1})
        for name in ('pot', 'lantern_caps', 'pot_lod1', 'lantern_caps_lod2'):
            with self.subTest(mesh=name), self.assertRaisesRegex(EvidenceError, 'every side triangle'):
                probe.require_capped_round_shading(summary, name)
        smooth_cone = [(position, smooth_rim[i][1]) for i, (position, _) in enumerate(flat_cone)]
        corrected = probe.normal_summary([smooth_cone, smooth_rim, hard_cap])
        self.assertEqual(corrected, {'triangles': 3, 'varying_triangles': 2, 'hard_cap_triangles': 1})
        probe.require_capped_round_shading(corrected, 'pot')

    def test_capped_round_gate_requires_both_caps_and_sides(self):
        for summary in ({'triangles': 0, 'varying_triangles': 0, 'hard_cap_triangles': 0},
                        {'triangles': 1, 'varying_triangles': 1, 'hard_cap_triangles': 0},
                        {'triangles': 1, 'varying_triangles': 0, 'hard_cap_triangles': 1}):
            with self.subTest(summary=summary), self.assertRaises(EvidenceError):
                probe.require_capped_round_shading(summary, 'pot')

    def test_native_failure_retains_failed_receipt_and_request(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'qualification'
            with patch.object(probe, 'run_command', side_effect=EvidenceError('native export failed')):
                receipt = probe.qualify(Path(directory) / 'absent-blender', output)
            self.assertEqual(receipt['state'], 'failed')
            self.assertIn('native export failed', receipt['failures'][0])
            self.assertTrue((output / 'receipt.json').is_file())
            self.assertTrue((output / 'prop-0-smooth-0/request.json').is_file())
            self.assertTrue((output / 'prop-0-smooth-0/plan.json').is_file())

    def test_completed_cases_and_later_failure_keep_immutable_receipts(self):
        # Exercise real evidence writes across several cases; native geometry is covered by the opt-in gate.
        for fail_at in (None, 3):
            with self.subTest(fail_at=fail_at), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / 'qualification'; calls = []
                def run(command, folder, name, timeout):
                    calls.append(folder)
                    if len(calls) == fail_at: raise EvidenceError('third native export failed')
                    probe.write_json(folder / 'measurements.json', {'blender': {'fixture': True}})
                    for level in range(3): (folder / f'asset_LOD{level}.glb').write_bytes(glb_bytes(*model()))
                def triangles(path):
                    request = probe.read_json(path.parent / 'request.json')
                    kind, smooth = request['params']['kind'], request['params']['smooth']
                    level = int(path.stem[-1]); suffix = '' if level == 0 else f'_lod{level}'
                    positions = ((0, 0, 0), (1, 0, 0), (1, 1, 0))
                    normals = ((1, 0, 0), (.6, 0, .8), (0, 0, 1)) if smooth and kind != 1 else ((0, 0, 1),) * 3
                    side = list(zip(positions, normals))
                    cap = [((0, 0, 0), (0, 1, 0)), ((1, 0, 0), (0, 1, 0)), ((0, 0, 1), (0, 1, 0))]
                    if kind == 1: return {'crate' + suffix: [side]}
                    body, caps = ('lantern_body', 'lantern_caps') if kind == 0 else ('foliage', 'pot')
                    return {body + suffix: [side], caps + suffix: [side, cap]}
                with patch.object(probe, 'run_command', side_effect=run), \
                     patch.object(probe.factory, 'evaluate_gates', return_value=[{'passed': True}]), \
                     patch.object(probe, 'read_triangles', side_effect=triangles):
                    receipt = probe.qualify(Path(directory) / 'fixture-blender', output)
                count = 6 if fail_at is None else 2
                self.assertEqual(receipt['state'], 'passed' if fail_at is None else 'failed')
                self.assertEqual(len(receipt['cases']), count)
                self.assertEqual(probe.read_json(output / 'receipt.json'), receipt)
                self.assertEqual(len(list(output.glob('prop-*/shading.json'))), count)
                for row in receipt['cases']:
                    self.assertEqual(probe.read_json(output / f"prop-{row['kind']}-smooth-{row['smooth']}" / 'shading.json'), row)
                if fail_at is not None: self.assertIn('third native export failed', receipt['failures'][0])

    def test_geometry_key_retains_topology_and_ignores_export_vertex_order(self):
        triangle = [((0, 0, 0), (0, 0, 1)), ((1, 0, 0), (0, 0, 1)), ((0, 1, 0), (0, 0, 1))]
        self.assertEqual(probe.geometry_key([triangle]), probe.geometry_key([triangle[1:] + triangle[:1]]))
        self.assertNotEqual(probe.geometry_key([triangle]), probe.geometry_key([triangle, triangle]))


if __name__ == '__main__': unittest.main()
