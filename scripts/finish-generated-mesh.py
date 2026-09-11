"""Run with Blender --background --python THIS_FILE -- --input model.glb --output preview.glb.

Optional bottom trimming is destructive to geometry in the new export only.
Original files are preserved. UVs/materials pass through Blender's modifiers;
inspect the resulting mapping and cut boundary before using it in a project.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
import bmesh

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--input', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--target-faces', type=int, default=80000, help='Total triangle budget; approximate')
parser.add_argument('--trim-bottom-fraction', type=float, default=0, help='Fraction of each mesh Z height after object transforms to cut; 0 disables')
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
if not bpy.app.background: parser.error('Run this script in a separate background Blender process')
source, target = args.input.resolve(), args.output.resolve()
if source.suffix.lower() != '.glb' or not source.is_file(): parser.error('Input must be an existing GLB')
if target.suffix.lower() != '.glb' or target.exists() or target.with_suffix('.finish.json').exists(): parser.error('Choose a new GLB output path')
if not 100 <= args.target_faces <= 1000000: parser.error('Target faces must be 100..1000000')
if not 0 <= args.trim_bottom_fraction <= .25: parser.error('Trim fraction must be 0..0.25')

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(source))
meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
if not meshes: raise RuntimeError('No meshes in input')
record = dict(source=source.name, source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
              blender=bpy.app.version_string, target_faces=args.target_faces,
              trim_bottom_fraction=args.trim_bottom_fraction, meshes=[])
for obj in meshes:
    bpy.ops.object.select_all(action='DESELECT'); obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    before = len(obj.data.polygons)
    if args.trim_bottom_fraction:
        lo, hi = min(v.co.z for v in obj.data.vertices), max(v.co.z for v in obj.data.vertices)
        cut = lo + (hi - lo) * args.trim_bottom_fraction
        bm = bmesh.new(); bm.from_mesh(obj.data)
        bmesh.ops.bisect_plane(bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces),
                              dist=1e-6, plane_co=(0, 0, cut), plane_no=(0, 0, 1),
                              clear_inner=True, clear_outer=False)
        bm.to_mesh(obj.data); bm.free(); obj.data.update()
    record['meshes'].append(dict(name=obj.name, original_faces=before, after_trim=len(obj.data.polygons)))

remaining = sum(len(obj.data.polygons) for obj in meshes)
if not remaining: raise RuntimeError('Trimming removed all faces; no output written')
ratio = min(1.0, args.target_faces / remaining)
for obj, item in zip(meshes, record['meshes']):
    bpy.ops.object.select_all(action='DESELECT'); obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    if ratio < 1:
        modifier = obj.modifiers.new('Studio preview reduction', 'DECIMATE')
        modifier.ratio = ratio; modifier.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    item['final_faces'] = len(obj.data.polygons)

target.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.export_scene.gltf(filepath=str(target), export_format='GLB', export_materials='EXPORT', export_cameras=False, export_lights=False)
record['output_sha256'] = hashlib.sha256(target.read_bytes()).hexdigest()
record['output_bytes'] = target.stat().st_size
target.with_suffix('.finish.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
print(json.dumps(record))
