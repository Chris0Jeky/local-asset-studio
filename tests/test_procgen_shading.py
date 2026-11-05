"""Offline graph regressions; native GLB qualification lives in test_procgen_shading_native."""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import procgen_factory as factory


class Socket:
    def __init__(self, name): self.name, self.enabled, self.default_value = name, True, None


class Sockets:
    def __init__(self, names): self.items = [Socket(n) for n in names]
    def __iter__(self): return iter(self.items)
    def __getitem__(self, key): return self.items[key] if isinstance(key, int) else next(s for s in self.items if s.name == key)


class Nodes:
    def __init__(self): self.items = []
    def new(self, kind):
        inputs = {'GeometryNodeMeshCube': ['Size'], 'GeometryNodeMeshCylinder': ['Vertices', 'Radius', 'Depth'],
                  'GeometryNodeMeshCone': ['Vertices', 'Radius Bottom', 'Radius Top', 'Depth'],
                  'GeometryNodeMeshUVSphere': ['Segments', 'Rings', 'Radius'],
                  'GeometryNodeMeshGrid': ['Size X', 'Size Y', 'Vertices X', 'Vertices Y'],
                  'GeometryNodeStoreNamedAttribute': ['Geometry', 'Name', 'Value'],
                  'GeometryNodeSetMaterial': ['Geometry', 'Material'],
                  'GeometryNodeTransform': ['Geometry', 'Translation', 'Scale', 'Rotation'],
                  'GeometryNodeSetShadeSmooth': ['Mesh', 'Selection', 'Shade Smooth'],
                  'FunctionNodeBooleanMath': ['Boolean', 'Boolean'],
                  'ShaderNodeMath': ['Value', 'Value']}[kind]
        node = SimpleNamespace(kind=kind, bl_idname=kind, inputs=Sockets(inputs), outputs=Sockets(['Mesh', 'UV Map', 'Geometry', 'Top', 'Bottom', 'Boolean', 'Value']))
        # Real Blender's first output varies with node type.
        if kind not in ('GeometryNodeMeshCube', 'GeometryNodeMeshCylinder', 'GeometryNodeMeshCone', 'GeometryNodeMeshUVSphere', 'GeometryNodeMeshGrid'):
            node.outputs = Sockets(['Boolean' if kind == 'FunctionNodeBooleanMath' else 'Value' if kind == 'ShaderNodeMath'
                                    else 'Mesh' if kind == 'GeometryNodeSetShadeSmooth' else 'Geometry'])
        self.items.append(node)
        return node


class GraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('procgen_blender_test', ROOT / 'scripts/procgen_blender.py')
        cls.module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'bpy': SimpleNamespace(types=SimpleNamespace(NodeSocket=Socket)),
                                     'bmesh': SimpleNamespace(), 'numpy': SimpleNamespace(), 'mathutils': SimpleNamespace(Matrix=None, Vector=None)}):
            spec.loader.exec_module(cls.module)

    def builder(self, smooth):
        links = []
        tree = SimpleNamespace(nodes=Nodes(), links=SimpleNamespace(new=lambda a, b: links.append((a, b))))
        b = self.module.B(tree, {'test': object()}, 12)
        b.smooth = self.module.S(b, smooth)
        return b, tree.nodes.items, links

    def test_sphere_shading_is_driven_by_socket_before_placement(self):
        control = Socket('smooth'); b, nodes, links = self.builder(control)
        b.sphere((0, 0, 0), (1, 2, 3), 8, 'test')
        shade, = [n for n in nodes if n.kind == 'GeometryNodeSetShadeSmooth']
        sphere, = [n for n in nodes if n.kind == 'GeometryNodeMeshUVSphere']
        self.assertEqual(shade.domain, 'FACE')
        self.assertIn((control, shade.inputs['Shade Smooth']), links)
        self.assertIn((sphere.outputs['Mesh'], shade.inputs['Mesh']), links)
        uv = next(n for n in nodes if n.kind == 'GeometryNodeStoreNamedAttribute')
        self.assertIn((shade.outputs[0], uv.inputs['Geometry']), links)
        self.assertIn((sphere.outputs['UV Map'], uv.inputs['Value']), links)

    def test_cylinder_and_cone_select_only_side_faces(self):
        for top in (None, 0.5):
            with self.subTest(top=top):
                control = Socket('smooth'); b, nodes, links = self.builder(control)
                b.cyl(1, 2, (0, 0, 0), 6, 'test', top=top)
                primitive = nodes[0]
                shade, = [n for n in nodes if n.kind == 'GeometryNodeSetShadeSmooth']
                boolean = [n for n in nodes if n.kind == 'FunctionNodeBooleanMath']
                union, invert = boolean
                self.assertEqual((union.operation, invert.operation), ('OR', 'NOT'))
                self.assertIn((primitive.outputs['Top'], union.inputs[0]), links)
                self.assertIn((primitive.outputs['Bottom'], union.inputs[1]), links)
                self.assertIn((union.outputs[0], invert.inputs[0]), links)
                self.assertIn((invert.outputs[0], shade.inputs['Selection']), links)
                self.assertIn((control, shade.inputs['Shade Smooth']), links)

    def test_group_interface_exposes_schema_and_links_smooth_into_builder(self):
        inputs = []
        def new_socket(name, in_out, socket_type):
            socket = Socket(name); socket.socket_type = socket_type
            if in_out == 'INPUT': inputs.append(socket)
            return socket
        def new_node(kind):
            return SimpleNamespace(outputs=inputs) if kind == 'NodeGroupInput' else SimpleNamespace(inputs={'Geometry': Socket('Geometry')})
        tree = SimpleNamespace(interface=SimpleNamespace(new_socket=new_socket), nodes=SimpleNamespace(new=new_node),
                               links=SimpleNamespace(new=lambda a, b: None))
        captured = []
        def generator(b, params):
            captured.append((b, params)); return Socket('result')
        spec = factory.load_schema()['generators']['prop']
        with patch.object(self.module.bpy, 'data', SimpleNamespace(node_groups=SimpleNamespace(new=lambda *a: tree)), create=True), \
             patch.dict(self.module.GENERATORS, {'prop': generator}):
            self.module.build_tree('prop', spec, {})
        b, params = captured[0]
        control = next(s for s in inputs if s.name == 'smooth')
        self.assertIs(b.smooth.s, control)
        self.assertIs(params['smooth'].s, control)
        self.assertEqual((control.socket_type, control.min_value, control.max_value, control.default_value), ('NodeSocketInt', 0, 1, 0))
        self.assertEqual(control.description, spec['params']['smooth']['doc'])

    def test_box_and_grid_never_receive_smoothing(self):
        b, nodes, _ = self.builder(Socket('smooth'))
        b.box((0, 0, 0), (1, 1, 1), 4, 'test')
        b.grid(1, 1, (0, 0, 0), (0, 0, 0), 5, 'test')
        self.assertFalse(any(n.kind == 'GeometryNodeSetShadeSmooth' for n in nodes))


class ShadingSchema(unittest.TestCase):
    def test_every_generator_defaults_to_flat_and_accepts_only_integer_switch(self):
        for name, spec in factory.load_schema()['generators'].items():
            with self.subTest(generator=name):
                self.assertEqual(spec['params']['smooth']['default'], 0)
                self.assertTrue(spec['params']['smooth'].get('gn', True))
                for value in (0, 1):
                    params, errors = factory.resolve_params(spec, {'smooth': value})
                    self.assertEqual(errors, [])
                    self.assertEqual(params['smooth'], value)
                for value in (-1, 2, True, 1.0, '1'):
                    _, errors = factory.resolve_params(spec, {'smooth': value})
                    self.assertTrue(errors, value)
                self.assertIn('round', spec['params']['smooth']['doc'])


if __name__ == '__main__': unittest.main()
