import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('dcc_probe', ROOT / 'scripts/blender_scene_probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def mesh():
    return NS(vertices=[NS(co=(0., 0., 0.), groups=[]), NS(co=(1., 0., 0.), groups=[]),
                        NS(co=(0., 1., 0.), groups=[])],
              edges=[NS(vertices=(0, 1)), NS(vertices=(1, 2)), NS(vertices=(2, 0))],
              polygons=[NS(vertices=(0, 1, 2), material_index=0)], uv_layers=[], shape_keys=None)


def curve():
    point = NS(co=(1., 0.), handle_left=(0., 0.), handle_right=(2., 0.), interpolation='LINEAR')
    return NS(data_path='location', array_index=0, keyframe_points=[point], sampled_points=[], modifiers=[])


class ProbeTests(unittest.TestCase):
    def test_topology_hash_changes_when_only_connectivity_changes(self):
        a = mesh(); b = copy.deepcopy(a); b.polygons[0].vertices = (0, 2, 1)
        one, two = probe.mesh_record(a, probe.Budget()), probe.mesh_record(b, probe.Budget())
        self.assertEqual(one['vertices'], two['vertices'])
        self.assertNotEqual(one['topology_sha256'], two['topology_sha256'])
        self.assertEqual(one['positions_sha256'], two['positions_sha256'])

    def test_displacement_changes_positions_not_topology(self):
        a = mesh(); b = copy.deepcopy(a); b.vertices[0].co = (0., 0., 0.1)
        one, two = probe.mesh_record(a, probe.Budget()), probe.mesh_record(b, probe.Budget())
        self.assertEqual(one['topology_sha256'], two['topology_sha256'])
        self.assertNotEqual(one['positions_sha256'], two['positions_sha256'])

    def test_nonfinite_geometry_and_exhausted_budget_refused(self):
        a = mesh(); a.vertices[0].co = (float('nan'), 0., 0.)
        with self.assertRaises(ValueError): probe.mesh_record(a, probe.Budget())
        with self.assertRaisesRegex(ValueError, 'budget'): probe.mesh_record(mesh(), probe.Budget(2))

    def test_layered_actions_read_without_ensure_or_legacy_api(self):
        action = NS(layers=[NS(name='Layer', strips=[NS(channelbags=[NS(slot_handle=7, fcurves=[curve()])])])],
                    slots=[NS(handle=7, identifier='OBCube')], frame_range=(1., 10.))
        def forbidden(*args): self.fail('Read-only probe used a mutating ensure function')
        action.fcurve_ensure_for_datablock = forbidden
        result = probe.action_record(action, probe.Budget())
        self.assertEqual(result['path'], 'layered')
        self.assertEqual(result['curves'][0]['slot_handle'], 7)
        self.assertEqual(result['curves'][0]['data_path'], 'location')

    def test_legacy_actions_remain_readable(self):
        result = probe.action_record(NS(fcurves=[curve()], frame_range=(1., 10.)), probe.Budget())
        self.assertEqual(result['path'], 'legacy')
        self.assertEqual(len(result['curves']), 1)

    def test_unknown_animation_api_is_not_empty_success(self):
        with self.assertRaisesRegex(ValueError, 'animation'): probe.action_record(NS(), probe.Budget())

    def test_uv_and_weight_changes_are_observable(self):
        a = mesh(); a.uv_layers = [NS(name='UVMap', data=[NS(uv=(0., 0.))])]
        b = copy.deepcopy(a); b.uv_layers[0].data[0].uv = (1., 0.)
        self.assertNotEqual(probe.mesh_record(a, probe.Budget())['uv'],
                            probe.mesh_record(b, probe.Budget())['uv'])
        b = copy.deepcopy(a); b.vertices[0].groups = [NS(group=0, weight=1.)]
        self.assertNotEqual(probe.mesh_record(a, probe.Budget())['weights_sha256'],
                            probe.mesh_record(b, probe.Budget())['weights_sha256'])

    def test_shape_key_hash_retains_relative_basis(self):
        a = mesh()
        key = NS(name='Smile', value=0., relative_key=NS(name='Basis'),
                 data=[NS(co=(0., 0., 0.))])
        a.shape_keys = NS(key_blocks=[key])
        result = probe.mesh_record(a, probe.Budget())
        self.assertEqual(result['shape_keys'][0]['relative_key'], 'Basis')
        self.assertEqual(len(result['shape_keys'][0]['positions_sha256']), 64)

    def test_material_socket_default_is_observed(self):
        material = NS(name='Paint', library=None, diffuse_color=(1., 0., 0., 1.),
                      use_nodes=True, node_tree=NS(nodes=[NS(name='Principled BSDF',
                      bl_idname='ShaderNodeBsdfPrincipled', inputs=[NS(name='Base Color',
                      identifier='Base Color', default_value=(1., 0., 0., 1.))], outputs=[])], links=[]))
        one = probe.material_record(material, probe.Budget())
        material.node_tree.nodes[0].inputs[0].default_value = (1., 1., 1., 1.)
        two = probe.material_record(material, probe.Budget())
        self.assertNotEqual(one, two)

    def test_editable_output_defaults_are_observed(self):
        for kind, identifier, original, changed in (
            ('ShaderNodeRGB', 'Color', (1., 0., 0., 1.), (0., 1., 0., 1.)),
            ('ShaderNodeValue', 'Value', 0.25, 0.75),
        ):
            with self.subTest(node=kind):
                socket = NS(identifier=identifier, default_value=original)
                node = NS(name='Constant', bl_idname=kind, inputs=[], outputs=[socket])
                material = NS(name='Paint', library=None, diffuse_color=(1., 1., 1., 1.),
                              use_nodes=True, node_tree=NS(nodes=[node], links=[]))
                before = probe.material_record(material, probe.Budget())
                socket.default_value = changed
                after = probe.material_record(material, probe.Budget())
                self.assertNotEqual(before, after, 'An authored output value changed')
                socket.default_value = original
                self.assertEqual(before, probe.material_record(material, probe.Budget()))

    def test_output_defaults_keep_scalar_and_finite_value_limits(self):
        socket = NS(identifier='Value', default_value=0.5)
        node = NS(name='Constant', bl_idname='ShaderNodeValue', inputs=[], outputs=[socket])
        material = NS(name='Paint', library=None, diffuse_color=(1., 1., 1., 1.),
                      use_nodes=True, node_tree=NS(nodes=[node], links=[]))
        with self.assertRaisesRegex(ValueError, 'budget'):
            probe.material_record(material, probe.Budget(1))
        socket.default_value = float('nan')
        with self.assertRaisesRegex(ValueError, 'Non-finite'):
            probe.material_record(material, probe.Budget())

    def test_identity_includes_linked_library(self):
        self.assertNotEqual(probe.identity(NS(name='Mesh', library=None)),
                            probe.identity(NS(name='Mesh', library=NS(filepath='//library.blend'))))

    def test_material_node_count_is_bounded_before_inventory(self):
        node = NS(name='N', bl_idname='ShaderNodeValue', inputs=[])
        material = NS(name='M', library=None, diffuse_color=(0., 0., 0., 1.), use_nodes=True,
                      node_tree=NS(nodes=[node] * 2049, links=[]))
        with self.assertRaisesRegex(ValueError, 'budget'):
            probe.material_record(material, probe.Budget())

    def test_bone_count_is_bounded_before_serialization(self):
        class TooManyBones:
            def __len__(self): return 4097
            def __iter__(self): raise AssertionError('Unbounded bone iteration')
        obj = NS(name='Rig', library=None, type='ARMATURE', mode='OBJECT', parent=None,
                 matrix_world=[], hide_render=False, modifiers=[], constraints=[], material_slots=[],
                 data=NS(bones=TooManyBones()), animation_data=None)
        bpy = NS(data=NS(objects=[obj], actions=[], images=[]))
        with self.assertRaisesRegex(ValueError, 'budget'): probe.collect(bpy)
