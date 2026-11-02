"""Bounded read-only base-scene inventory; stdlib only in Blender's own Python.

Run only via an explicitly selected Blender executable and disabled autoexec.
This does not render, evaluate deformations, save a BLEND or establish parity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

FORMAT = 'studio.dcc-scene/v1'
LIMITATIONS = [
    'Base meshes only: no evaluated modifiers, pose deformation, contact or temporal checks.',
    'Material input/output socket defaults, links and ramps are observed; nested node-group internals are not.',
    'Image paths/packing/presence are observed; texture pixels and packed bytes are not hashed.',
    'Constraints/modifiers and animation modifiers are inventoried, not fully serialized.',
    'Object/library names are identities here; GLB renaming/triangulation needs an explicit mapping.',
    'Autoexec is disabled: scripted drivers are not evaluated or qualified.',
    'No GPU backend, renderer performance, artistic quality or licence qualification.'
]


class Budget:
    def __init__(self, limit=20000000):
        self.remaining = limit

    def take(self, count=1):
        self.remaining -= count
        if self.remaining < 0:
            raise ValueError('Probe scalar budget exceeded; no truncated success is written')


def identity(value):
    library = getattr(value, 'library', None)
    return (library.filepath + '::' if library else '') + value.name


def numeric_hash(rows, budget):
    checksum = hashlib.sha256()
    for row in rows:
        values = tuple(row)
        budget.take(len(values))
        checksum.update(struct.pack('<I', len(values)))
        for number in values:
            if type(number) not in (int, float) or not math.isfinite(number):
                raise ValueError('Non-finite or unsupported numeric geometry')
            checksum.update(b'i' + struct.pack('<q', number) if type(number) is int
                            else b'f' + struct.pack('<d', number))
    return checksum.hexdigest()


def mesh_record(mesh, budget):
    keys = getattr(mesh, 'shape_keys', None)
    if len(mesh.uv_layers) > 64 or keys and len(keys.key_blocks) > 256:
        raise ValueError('UV/shape-key count exceeds probe budget')
    def topology():
        for edge in mesh.edges:
            yield (0, *edge.vertices)
        for polygon in mesh.polygons:
            yield (1, *polygon.vertices)
    keys = getattr(mesh, 'shape_keys', None)
    return {'vertices': len(mesh.vertices), 'edges': len(mesh.edges), 'polygons': len(mesh.polygons),
            'topology_sha256': numeric_hash(topology(), budget),
            'positions_sha256': numeric_hash((v.co for v in mesh.vertices), budget),
            'face_materials_sha256': numeric_hash(((p.material_index,) for p in mesh.polygons), budget),
            'weights_sha256': numeric_hash(((i, g.group, g.weight) for i, v in enumerate(mesh.vertices)
                                            for g in sorted(v.groups, key=lambda x: x.group)), budget),
            'uv': {uv.name: numeric_hash((point.uv for point in uv.data), budget) for uv in mesh.uv_layers},
            'shape_keys': [{'name': key.name, 'value': key.value,
                            'relative_key': key.relative_key.name if key.relative_key else None,
                            'vertices': len(key.data),
                            'positions_sha256': numeric_hash((point.co for point in key.data), budget)}
                           for key in keys.key_blocks] if keys else []}


def _value(value, budget):
    budget.take()
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError('Non-finite material value')
        return value
    if hasattr(value, 'name'):
        return {'datablock': identity(value)}
    try:
        values = list(value)
    except TypeError:
        return {'unrecorded_type': type(value).__name__}
    if len(values) > 32:
        raise ValueError('Unexpectedly large material socket value')
    return [_value(item, budget) for item in values]


def material_record(material, budget):
    if material is None:
        return None
    result = {'id': identity(material), 'diffuse_color': list(material.diffuse_color),
              'use_nodes': material.use_nodes, 'nodes': {}, 'links': []}
    tree = material.node_tree
    if not material.use_nodes or tree is None:
        return result
    if len(tree.nodes) > 2048 or len(tree.links) > 8192:
        raise ValueError('Material graph exceeds probe budget')
    budget.take(len(tree.links) * 4)
    for node in tree.nodes:
        budget.take()
        entry = {'type': node.bl_idname, 'mute': getattr(node, 'mute', False),
                 'inputs': [{'id': socket.identifier, 'value': _value(socket.default_value, budget)}
                            for socket in node.inputs if hasattr(socket, 'default_value')],
                 'outputs': [{'id': socket.identifier, 'value': _value(socket.default_value, budget)}
                             for socket in node.outputs if hasattr(socket, 'default_value')]}
        for field in ('image', 'node_tree'):
            target = getattr(node, field, None)
            if target is not None:
                entry[field] = identity(target)
        ramp = getattr(node, 'color_ramp', None)
        if ramp:
            entry['ramp'] = {'interpolation': ramp.interpolation,
                             'elements': [[element.position, *element.color] for element in ramp.elements]}
        result['nodes'][node.name] = entry
    result['links'] = sorted([link.from_node.name, link.from_socket.identifier,
                              link.to_node.name, link.to_socket.identifier] for link in tree.links)
    return result


def action_record(action, budget):
    curves = []
    def add(curve, layer, strip, slot):
        budget.take()
        curves.append({'layer': layer, 'strip': strip, 'slot_handle': slot,
                       'data_path': curve.data_path, 'array_index': curve.array_index,
                       'keyframes_sha256': numeric_hash(((*p.co, *p.handle_left, *p.handle_right)
                                                        for p in curve.keyframe_points), budget),
                       'interpolation': [p.interpolation for p in curve.keyframe_points],
                       'samples_sha256': numeric_hash((p.co for p in curve.sampled_points), budget),
                       'modifiers': [m.type for m in curve.modifiers]})
    layers = getattr(action, 'layers', None)
    if layers:
        path = 'layered'
        for layer_index, layer in enumerate(layers):
            for strip_index, strip in enumerate(layer.strips):
                if not hasattr(strip, 'channelbags'):
                    raise ValueError('Unknown animation strip API; refusing incomplete inventory')
                for bag in strip.channelbags:
                    for curve in bag.fcurves:
                        add(curve, layer_index, strip_index, bag.slot_handle)
    elif hasattr(action, 'fcurves'):
        path = 'legacy'
        for curve in action.fcurves:
            add(curve, 0, 0, None)
    elif layers is not None:
        path = 'layered'
    else:
        raise ValueError('Unknown animation API; no empty-success fallback')
    return {'path': path, 'range': list(action.frame_range), 'curves': curves,
            'slots': [{'handle': slot.handle, 'identifier': slot.identifier}
                      for slot in getattr(action, 'slots', [])]}


def collect(bpy):
    budget, objects, findings = Budget(), {}, []
    if any(len(getattr(bpy.data, field)) > 2048 for field in ('objects', 'actions', 'images')):
        raise ValueError('Datablock count exceeds the probe budget')
    for obj in bpy.data.objects:
        budget.take()
        if getattr(obj, 'mode', None) == 'EDIT':
            raise ValueError('Edit-mode base mesh may be stale; save a source copy in Object Mode first')
        if max(len(obj.modifiers), len(obj.constraints), len(obj.material_slots)) > 2048:
            raise ValueError('Object component count exceeds probe budget')
        budget.take(len(obj.modifiers) + len(obj.constraints) + len(obj.material_slots))
        key = identity(obj)
        if key in objects:
            raise ValueError('Duplicate object identity')
        record = {'type': obj.type, 'parent': identity(obj.parent) if obj.parent else None,
                  'matrix_world': [list(row) for row in obj.matrix_world],
                  'hide_render': obj.hide_render,
                  'modifiers': [{'name': m.name, 'type': m.type, 'show_render': m.show_render,
                                 'show_viewport': m.show_viewport} for m in obj.modifiers],
                  'constraints': [{'name': c.name, 'type': c.type} for c in obj.constraints],
                  'materials': [material_record(slot.material, budget) for slot in obj.material_slots]}
        if obj.type == 'MESH':
            record['mesh'] = mesh_record(obj.data, budget)
            record['vertex_groups'] = [g.name for g in obj.vertex_groups]
        if obj.type == 'ARMATURE':
            if len(obj.data.bones) > 4096:
                raise ValueError('Bone count exceeds probe budget')
            budget.take(len(obj.data.bones) * 20)
            record['bones'] = {bone.name: {'parent': bone.parent.name if bone.parent else None,
                                           'rest_matrix': [list(row) for row in bone.matrix_local],
                                           'deform': bone.use_deform} for bone in obj.data.bones}
        animation = obj.animation_data
        record['action'] = identity(animation.action) if animation and animation.action else None
        record['action_slot_handle'] = getattr(animation, 'action_slot_handle', None) if animation else None
        objects[key] = record
    images = {}
    for image in bpy.data.images:
        packed = bool(image.packed_file or getattr(image, 'packed_files', []))
        status = 'packed' if packed else 'not_checked'
        if not packed and image.source == 'FILE':
            resolved = Path(bpy.path.abspath(image.filepath, library=image.library))
            status = 'present' if resolved.is_file() else 'missing'
            if status == 'missing':
                findings.append({'code': 'missing_external_image', 'id': identity(image)})
        images[identity(image)] = {'path': image.filepath, 'source': image.source, 'status': status,
                                   'size': list(image.size), 'colorspace': image.colorspace_settings.name}
    build_hash = bpy.app.build_hash
    return {'format': FORMAT, 'complete': True,
            'runtime': {'blender_version': list(bpy.app.version),
                        'build_hash': build_hash.decode(errors='replace') if isinstance(build_hash, bytes) else str(build_hash),
                        'python': sys.version, 'binary_path': bpy.app.binary_path,
                        'capabilities': {'action_layers': hasattr(bpy.types.Action, 'layers'),
                                         'legacy_action_fcurves': hasattr(bpy.types.Action, 'fcurves'),
                                         'gpu_execution': 'not_probed'}},
            'content': {'objects': objects, 'images': images,
                        'actions': {identity(a): action_record(a, budget) for a in bpy.data.actions}},
            'findings': findings, 'limitations': LIMITATIONS,
            'remaining_scalar_budget': budget.remaining}


def main():
    required = {'--background', '--factory-startup', '--disable-autoexec'}
    if not required <= set(sys.argv) or '--enable-autoexec' in sys.argv:
        raise ValueError('Use the fixed background/factory-startup/disable-autoexec invocation')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    if args.source.is_symlink() or not args.source.is_file() or args.source.suffix.lower() != '.blend':
        raise ValueError('Expected an existing .blend source copy')
    if args.out.exists() or args.out.is_symlink() or not args.out.parent.is_dir():
        raise ValueError('Output must be new and have an existing parent')
    import bpy  # Never imported into LAS or ComfyUI's Python environment.
    bpy.ops.wm.open_mainfile(filepath=str(args.source.resolve()))
    observation = collect(bpy)
    raw = json.dumps(observation, ensure_ascii=False, sort_keys=True, allow_nan=False).encode('utf-8')
    if len(raw) > 1048576:
        raise ValueError('Observation exceeds 1 MiB; no truncated success is written')
    with args.out.open('xb') as stream:
        stream.write(raw)
    print('DCC_SCENE_OBSERVATION_WRITTEN', str(args.out))


if __name__ == '__main__':
    main()
