"""Bake a per-texel world-position map for every image-textured material of every mesh (Blender, bpy + numpy).

  blender -b scene.blend --python scripts/vrm_posmap_bpy.py -- OUTDIR

Writes OUTDIR/<material>.npz (pos: (H, W, 3) float32 world metres, rows top-down like the image; mask: (H, W) bool)
and OUTDIR/<material>__src.png, a copy of the base texture. Paint a VRM's textures by 3D rules with these maps
("below the waist", "front of the torso") without reading its UV layout, or feed the face map to
`vrm_toon.py face-sdf`. Uses the rest-pose mesh; normal, specular and outline textures are skipped."""
import bpy, sys, os, numpy as np
out = sys.argv[sys.argv.index("--") + 1]; os.makedirs(out, exist_ok=True)
def img_of(mat):
    if not mat or not mat.node_tree: return None
    for n in mat.node_tree.nodes:
        if n.type == "TEX_IMAGE" and n.image and "nml" not in n.image.name and "spe" not in n.image.name and "outline" not in n.image.name: return n.image
for ob in [o for o in bpy.context.scene.objects if o.type == "MESH"]:
    me = ob.data; me.calc_loop_triangles(); uv = me.uv_layers.active.data; mw = np.array(ob.matrix_world)
    co = np.array([v.co for v in me.vertices]); co = co @ mw[:3, :3].T + mw[:3, 3]
    for mi, mat in enumerate(me.materials):
        im = img_of(mat)
        if im is None: continue
        W, H = im.size; pos = np.zeros((H, W, 3), np.float32); mask = np.zeros((H, W), bool)
        tris = [t for t in me.loop_triangles if t.material_index == mi]
        for t in tris:
            p = np.array([uv[l].uv for l in t.loops]) * [W, H]; P = co[list(t.vertices)]
            x0, y0 = np.floor(p.min(0)).astype(int); x1, y1 = np.ceil(p.max(0)).astype(int)
            x0, y0 = max(x0, 0), max(y0, 0); x1, y1 = min(x1, W - 1), min(y1, H - 1)
            if x1 < x0 or y1 < y0: continue
            xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + .5, np.arange(y0, y1 + 1) + .5)
            a, b, c = p; d = (b[1]-c[1])*(a[0]-c[0]) + (c[0]-b[0])*(a[1]-c[1])
            if abs(d) < 1e-9: continue
            l0 = ((b[1]-c[1])*(xs-c[0]) + (c[0]-b[0])*(ys-c[1])) / d; l1 = ((c[1]-a[1])*(xs-c[0]) + (a[0]-c[0])*(ys-c[1])) / d; l2 = 1 - l0 - l1
            m = (l0 >= -.02) & (l1 >= -.02) & (l2 >= -.02)
            if not m.any(): continue
            q = l0[..., None]*P[0] + l1[..., None]*P[1] + l2[..., None]*P[2]
            yy, xx = (ys[m] - .5).astype(int), (xs[m] - .5).astype(int)
            pos[yy, xx] = q[m]; mask[yy, xx] = True
        np.savez_compressed(f"{out}/{mat.name}.npz", pos=pos[::-1], mask=mask[::-1], image=im.name, path=bpy.path.abspath(im.filepath) if im.filepath else "")
        im.filepath_raw = f"{out}/{mat.name}__src.png"; im.file_format = "PNG"; im.save()
        print("POSMAP", ob.name, mat.name, W, H, len(tris), int(mask.sum()))
