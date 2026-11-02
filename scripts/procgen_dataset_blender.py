"""Runs inside Blender 5.x for procgen_dataset.py: render labelled views of factory scenes, or validate them.

render:   blender -b --factory-startup -P procgen_dataset_blender.py -- render <pool> <out> <first_scene> <scenes> <views>
validate: blender -b --factory-startup -P procgen_dataset_blender.py -- validate <dataset> <pool> <stride>
seed:     blender -b --factory-startup -P procgen_dataset_blender.py -- seed <scene_dir>   (test helper: one defect per view 01-05)

Labels come from a 1-sample Cycles pass with a 0.01 px box filter, so each label pixel is one ray through the pixel
centre. Validation never reuses the render scene: it re-imports each GLB, applies the recorded root matrix, builds its
own BVH and casts pixel-centre rays from camera.json alone.
"""
import json, math, random, sys, time
from pathlib import Path

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.interpolate import poly_3d_calc
import numpy as np
import OpenImageIO as oiio

RES = (512, 384)
COLLISION = ('-colonly', '-convcolonly')
GROUND = [(-20, -16, 0), (20, -16, 0), (20, 24, 0), (-20, 24, 0)]
THRESH = {'mask_agreement': 0.995, 'planar_rel_err_p99': 1e-4, 'reproj_m_p99': 1e-3, 'normal_deg_p99': 1.0}


def clear():
    for o in list(bpy.data.objects): bpy.data.objects.remove(o)
    for m in list(bpy.data.meshes): bpy.data.meshes.remove(m)


def import_instance(pool, glb, matrix):
    """Import one GLB with its collision proxies removed (they duplicate render faces) and place its root."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(pool / glb))
    for o in [o for o in bpy.data.objects if o not in before and o.name.endswith(COLLISION)]: bpy.data.objects.remove(o)
    new = [o for o in bpy.data.objects if o not in before]
    roots = [o for o in new if o.parent is None]
    if len(roots) != 1: raise SystemExit(f'{glb}: expected one root, got {[o.name for o in roots]}')
    roots[0].matrix_world = matrix
    bpy.context.view_layer.update()
    return [o for o in new if o.type == 'MESH']


# ---------------------------------------------------------------- render

def world_aabb(objs):
    pts = np.array([tuple(o.matrix_world @ Vector(c)) for o in objs for c in o.bound_box])
    return pts.min(0), pts.max(0)


def compose(pool, kind, base, props, rng):
    clear()
    registry, instances = [], []
    def add(build, instance, matrix):
        for o in import_instance(pool, f'{build}/asset_LOD0.glb', matrix):
            part = o.name.split('.')[0]
            o.pass_index = len(registry) + 1; o.name = f'{instance}/{part}'
            registry.append({'id': o.pass_index, 'object': o.name, 'instance': instance, 'build': build, 'part': part, 'class': part})
        instances.append({'instance': instance, 'build': build, 'glb': f'{build}/asset_LOD0.glb', 'root_matrix': [list(r) for r in matrix]})
    if kind == 'shrine':
        me = bpy.data.meshes.new('ground'); me.from_pydata(GROUND, [], [(0, 1, 2, 3)]); me.update()
        ground = bpy.data.objects.new('ground', me); bpy.context.scene.collection.objects.link(ground)
        mat = bpy.data.materials.new('ground'); mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.32, 0.38, 0.22, 1)
        me.materials.append(mat); ground.pass_index = 1
        registry.append({'id': 1, 'object': 'ground', 'instance': 'ground', 'build': None, 'part': 'ground', 'class': 'ground', 'geometry': GROUND})
    add(base, 'base', Matrix.Identity(4))
    base_params = json.loads((pool / f'{base}.json').read_text())['params']
    if kind == 'room':
        W, D = base_params['width'], base_params['depth']
        area, z = ((-W / 2 + 0.25, W / 2 - 0.25), (0.25, D - 0.25)), 0.06
        keep = ('desk', 'bed_frame', 'shelf', 'mattress', 'wall_left', 'wall_right', 'wall_back')
        occupied = [world_aabb([o]) for o in bpy.data.objects if o.type == 'MESH' and o.name.split('/')[-1] in keep]
    else:
        area, z = ((-6, 6), (-5, 9)), 0.0
        occupied = [world_aabb([o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith('base/')])]
    for i in range(rng.randint(3, 6)):
        build = rng.choice(props); pp = json.loads((pool / f'{build}.json').read_text())['params']
        r = max(pp['width'], 0.2) * 0.75
        for _ in range(40):
            x, y = rng.uniform(*area[0]), rng.uniform(*area[1])
            box = (np.array([x - r, y - r, z]), np.array([x + r, y + r, z + pp['height']]))
            if not any(all(box[0][k] - 0.02 < o[1][k] and o[0][k] - 0.02 < box[1][k] for k in range(2)) for o in occupied):
                occupied.append(box)
                add(build, f'prop{i}', Matrix.Translation((x, y, z)) @ Matrix.Rotation(rng.uniform(0, 2 * math.pi), 4, 'Z'))
                break
    return registry, instances, base_params


def setup_render(rng):
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'
    scene.render.resolution_x, scene.render.resolution_y = RES; scene.render.resolution_percentage = 100
    world = bpy.data.worlds.get('ds') or bpy.data.worlds.new('ds'); scene.world = world
    bg = world.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = (rng.uniform(.4, .7), rng.uniform(.5, .75), rng.uniform(.65, .95), 1)
    bg.inputs['Strength'].default_value = rng.uniform(.6, 1.2)
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sun.data.energy = rng.uniform(2, 4.5)
    sun.rotation_euler = (math.radians(rng.uniform(25, 60)), 0, math.radians(rng.uniform(-80, 80))); scene.collection.objects.link(sun)
    vl = scene.view_layers[0]; vl.use_pass_z = vl.use_pass_normal = vl.use_pass_object_index = True
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); scene.collection.objects.link(cam); scene.camera = cam
    cam.data.sensor_fit = 'HORIZONTAL'; cam.data.clip_start = 0.05; cam.data.clip_end = 200
    return scene, cam


def pick_camera(kind, p, rng, cam, blockers):
    for _ in range(200):
        if kind == 'room':
            W, D, H = p['width'], p['depth'], p['height']
            pos = Vector((rng.uniform(-W / 2 + 0.4, W / 2 - 0.4), rng.uniform(-1.2, 0.45 * D), rng.uniform(0.9, min(H - 0.2, 2.0))))
            target = Vector((rng.uniform(-W / 2 + 0.3, W / 2 - 0.3), rng.uniform(0.5 * D, D - 0.2), rng.uniform(0.3, 1.2)))
        else:
            r, az = rng.uniform(5, 12), math.radians(rng.uniform(-80, 80))
            pos = Vector((r * math.sin(az), 2.0 - r * math.cos(az), rng.uniform(1.0, 4.0)))
            target = Vector((rng.uniform(-1, 1), rng.uniform(1.5, 3.5), rng.uniform(0.5, 2.5)))
        if any(all(lo[k] - 0.15 < pos[k] < hi[k] + 0.15 for k in range(3)) for lo, hi in blockers): continue
        cam.location = pos; cam.rotation_euler = (target - pos).to_track_quat('-Z', 'Y').to_euler()
        cam.data.lens = rng.uniform(18, 32)
        return True
    return False


def write_image(arr, path, fmt):
    b = oiio.ImageBuf(oiio.ImageSpec(arr.shape[1], arr.shape[0], arr.shape[2], fmt))
    b.set_pixels(oiio.ROI(), arr.astype(np.float32 if fmt == oiio.FLOAT else np.uint16)); b.write(str(path))


def split_labels(path, view_dir):
    # Blender 5.4 writes a multi-part EXR (one subimage per pass) and names the index pass "Object Index".
    planes = {}
    for sub in range(oiio.ImageBuf(str(path)).nsubimages):
        buf = oiio.ImageBuf(str(path), sub, 0); px = buf.get_pixels(oiio.FLOAT)
        for i, n in enumerate(buf.spec().channelnames): planes[n] = px[:, :, i]
    pick = lambda *suffixes: next(planes[n] for n in planes if n.endswith(suffixes))
    write_image(pick('Depth.Z')[:, :, None], view_dir / 'depth.exr', oiio.FLOAT)
    write_image(np.stack([pick(f'Normal.{a}') for a in 'XYZ'], 2), view_dir / 'normal.exr', oiio.FLOAT)
    write_image(np.rint(pick('IndexOB.X', 'Object Index.X'))[:, :, None], view_dir / 'mask.png', oiio.UINT16)
    path.unlink()
    return sorted(planes)


def render(pool, out, first, count, views):
    summary = json.loads((pool / 'pool.json').read_text())['builds']
    ok = sorted(k for k, v in summary.items() if not v['failed_gates'])
    scenes = [('room', k) for k in ok if k.startswith('room_kit')] + [('shrine', k) for k in ok if k.startswith('shrine')]
    props = [k for k in ok if k.startswith('prop')]
    for s in range(first, min(first + count, len(scenes))):
        kind, base = scenes[s]; rng = random.Random(1000 + s)
        registry, instances, p = compose(pool, kind, base, props, rng)
        scene, cam = setup_render(rng)
        sdir = out / f'scene_{s:02d}'; sdir.mkdir(parents=True, exist_ok=True)
        (sdir / 'objects.json').write_text(json.dumps({'kind': kind, 'base': base, 'objects': registry, 'instances': instances}, indent=1))
        blockers = [world_aabb([o]) for o in bpy.data.objects if o.type == 'MESH' and o.name != 'ground']
        for v in range(views):
            if not pick_camera(kind, p, rng, cam, blockers): continue
            vdir = sdir / f'view_{v:02d}'; vdir.mkdir(exist_ok=True)
            st = scene.render.image_settings
            scene.cycles.samples = 1; scene.cycles.pixel_filter_type = 'BOX'; scene.cycles.filter_width = 0.01
            scene.cycles.use_denoising = False; scene.cycles.seed = 0
            st.media_type = 'MULTI_LAYER_IMAGE'; st.file_format = 'OPEN_EXR_MULTILAYER'; st.color_depth = '32'
            scene.render.filepath = str(vdir / 'labels.exr'); bpy.ops.render.render(write_still=True)
            channels = split_labels(vdir / 'labels.exr', vdir)
            scene.cycles.samples = 32; scene.cycles.pixel_filter_type = 'BLACKMAN_HARRIS'; scene.cycles.filter_width = 1.5
            scene.cycles.use_denoising = True
            st.media_type = 'IMAGE'; st.file_format = 'PNG'; st.color_depth = '8'
            scene.render.filepath = str(vdir / 'rgb.png'); bpy.ops.render.render(write_still=True)
            w, h = RES; fx = cam.data.lens / cam.data.sensor_width * w
            (vdir / 'camera.json').write_text(json.dumps({
                'resolution': [w, h], 'K': [[fx, 0, w / 2], [0, fx, h / 2], [0, 0, 1]], 'cam_to_world': [list(r) for r in cam.matrix_world],
                'depth': 'planar (camera-space -Z), metres; background 1e10', 'normal': 'world space, shading normal',
                'convention': 'Blender camera looks down -Z, +Y up; OpenCV cam_to_world = cam_to_world @ diag(1,-1,-1,1); pixel centres at +0.5',
                'clip': [cam.data.clip_start, cam.data.clip_end], 'exr_channels': channels}, indent=1))
        print('SCENE_DONE', s, kind, base, len(registry), flush=True)


# ---------------------------------------------------------------- validate

def scene_geometry(pool, meta):
    ids = {(o['instance'], o['part']): o['id'] for o in meta['objects']}
    verts, tris, tri_id, tri_normals = [], [], [], []
    for o in meta['objects']:
        if 'geometry' in o:
            base = len(verts); verts += [tuple(v) for v in o['geometry']]
            for t in ((0, 1, 2), (0, 2, 3)):
                tris.append(tuple(base + i for i in t)); tri_id.append(o['id']); tri_normals.append([(0, 0, 1)] * 3)
    for inst in meta['instances']:
        clear()
        for o in import_instance(pool, inst['glb'], Matrix(inst['root_matrix'])):
            oid = ids[(inst['instance'], o.name.split('.')[0])]
            mw = o.matrix_world; nm = mw.to_3x3().inverted().transposed()
            me = o.data; me.calc_loop_triangles(); cn = me.corner_normals
            base = len(verts); verts += [tuple(mw @ v.co) for v in me.vertices]
            for lt in me.loop_triangles:
                tris.append(tuple(base + i for i in lt.vertices)); tri_id.append(oid)
                tri_normals.append([tuple((nm @ cn[l].vector).normalized()) for l in lt.loops])
    return verts, tris, tri_id, tri_normals


def check_view(vdir, bvh, verts, tris, tri_id, tri_normals, stride):
    cam = json.loads((vdir / 'camera.json').read_text())
    (fx, _, cx), (_, fy, cy), _ = cam['K']; c2w = Matrix(cam['cam_to_world'])
    origin, rot = c2w.translation, c2w.to_3x3(); fwd = (rot @ Vector((0, 0, -1))).normalized()
    mask = oiio.ImageBuf(str(vdir / 'mask.png')).get_pixels(oiio.UINT16)[:, :, 0].astype(int)
    depth = oiio.ImageBuf(str(vdir / 'depth.exr')).get_pixels(oiio.FLOAT)[:, :, 0]
    normal = oiio.ImageBuf(str(vdir / 'normal.exr')).get_pixels(oiio.FLOAT)
    h, w = mask.shape
    pixels = disagree = 0; planar, rng_err, reproj, ndeg = [], [], [], []
    for v in range(stride // 2, h, stride):
        for u in range(stride // 2, w, stride):
            d = (rot @ Vector(((u + 0.5 - cx) / fx, -(v + 0.5 - cy) / fy, -1))).normalized()
            loc, _, idx, dist = bvh.ray_cast(origin, d, cam['clip'][1])
            want = tri_id[idx] if loc is not None else 0
            pixels += 1; disagree += int(mask[v, u] != want)
            if loc is None or mask[v, u] != want: continue
            z, cos = float(depth[v, u]), d.dot(fwd)
            planar.append(abs(z - dist * cos) / (dist * cos)); rng_err.append(abs(z - dist) / dist)
            reproj.append(bvh.find_nearest(origin + d * (z / cos))[3])
            wts = poly_3d_calc([Vector(verts[i]) for i in tris[idx]], loc)
            n = sum((Vector(tri_normals[idx][k]) * wts[k] for k in range(3)), Vector()).normalized()
            rn = Vector(normal[v, u, :3])
            if rn.length > 0.5: ndeg.append(math.degrees(n.angle(rn.normalized(), math.pi)))
    q = lambda xs, p: float(np.percentile(xs, p)) if xs else None
    r = {'view': f'{vdir.parent.name}/{vdir.name}', 'pixels': pixels, 'hits': len(planar), 'mask_agreement': 1 - disagree / pixels,
         'planar_rel_err_p50': q(planar, 50), 'planar_rel_err_p99': q(planar, 99), 'range_rel_err_p50': q(rng_err, 50),
         'reproj_m_p99': q(reproj, 99), 'reproj_m_max': max(reproj) if reproj else None,
         'normal_deg_p99': q(ndeg, 99), 'normal_deg_max': max(ndeg) if ndeg else None,
         'normal_nonzero_frac': float(np.mean(np.array(ndeg) > 1e-6)) if ndeg else None}
    r['passed'] = bool(r['hits'] and r['mask_agreement'] >= THRESH['mask_agreement'] and r['planar_rel_err_p99'] <= THRESH['planar_rel_err_p99']
                       and r['reproj_m_p99'] <= THRESH['reproj_m_p99'] and r['normal_deg_p99'] is not None and r['normal_deg_p99'] <= THRESH['normal_deg_p99'])
    return r


def validate(data, pool, stride):
    results, t0 = [], time.time()
    for sdir in sorted(data.glob('scene_*')):
        meta = json.loads((sdir / 'objects.json').read_text())
        verts, tris, tri_id, tri_normals = scene_geometry(pool, meta)
        bvh = BVHTree.FromPolygons(verts, tris, all_triangles=True)
        for vdir in sorted(sdir.glob('view_*')):
            if (vdir / 'camera.json').exists():
                results.append(check_view(vdir, bvh, verts, tris, tri_id, tri_normals, stride)); print('VIEW', json.dumps(results[-1]), flush=True)
    hit = [r for r in results if r['hits']]
    summary = {'views': len(results), 'passed': sum(r['passed'] for r in results), 'thresholds': THRESH, 'stride': stride,
               'ray_cast_pixels': sum(r['pixels'] for r in results), 'worst_mask_agreement': min((r['mask_agreement'] for r in results), default=None),
               'median_planar_rel_err': float(np.median([r['planar_rel_err_p50'] for r in hit])) if hit else None,
               'median_range_rel_err': float(np.median([r['range_rel_err_p50'] for r in hit])) if hit else None,
               'seconds': round(time.time() - t0, 1)}
    (data / 'label-validation.json').write_text(json.dumps({'summary': summary, 'views': results}, indent=1))
    print('SUMMARY', json.dumps(summary))


def seed(sdir):
    def rw(path, fn, fmt):
        a = fn(oiio.ImageBuf(str(path)).get_pixels(fmt)); write_image(a, path, fmt)
    rw(sdir / 'view_01/mask.png', lambda a: np.roll(a, 1, axis=1), oiio.UINT16)
    rw(sdir / 'view_02/depth.exr', lambda a: a * 1.01, oiio.FLOAT)
    rw(sdir / 'view_03/normal.exr', lambda a: -a, oiio.FLOAT)
    cam = json.loads((sdir / 'view_04/camera.json').read_text()); cam['K'][0][0] *= 1.02; cam['K'][1][1] *= 1.02
    (sdir / 'view_04/camera.json').write_text(json.dumps(cam))
    rw(sdir / 'view_05/mask.png', lambda a: np.where(a == a.max(), 0, a), oiio.UINT16)


args = sys.argv[sys.argv.index('--') + 1:]
if args[0] == 'render': render(Path(args[1]), Path(args[2]), int(args[3]), int(args[4]), int(args[5]))
elif args[0] == 'validate': validate(Path(args[1]), Path(args[2]), int(args[3]))
elif args[0] == 'seed': seed(Path(args[1]))
else: raise SystemExit(f'unknown mode {args[0]!r}')
