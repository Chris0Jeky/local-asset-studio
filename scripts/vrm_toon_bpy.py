"""Anime toon materials for a VRM/VRoid scene in Blender 5.4 EEVEE (bpy). See docs/ANIME-TOON-KIT.md.

  blender -b scene.blend --python scripts/vrm_toon_bpy.py -- ml|classic FACE_SDF.png OUT.blend

Every material with a base texture is rebuilt by its VRoid role (`vrm_toon.material_role`).

ml: the 5.4 Material Lighting loop. Per light: Light Evaluation (diffuse) x Shadow Raycast -> smoothstep cel ramp,
    rim on the lit side, glossy-step hair highlight, SDF face shadow from the light's direction in object space;
    Light Accumulation sums the lights, an emission term carries the shade colour.
classic: Diffuse BSDF -> Shader to RGB -> smoothstep ramp -> base x mix(shade, 1) as emission (one lighting sum,
    no per-light colour, N.L on the face).
Both: inverted-hull outlines (Solidify, flipped, back-face culled), Standard view transform, key/rim sun rig."""
import bpy, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vrm_toon import SHADE, material_role
argv = sys.argv[sys.argv.index("--") + 1:]; STYLE, SDF, OUT = argv[0], argv[1], argv[2]
if STYLE not in ("ml", "classic"): raise SystemExit("style must be ml or classic")
RIM = .35; SOFT = .03; OUTLINE = (.07, .05, .09, 1)


def base_image(m):
    for n in m.node_tree.nodes:
        if n.type == "TEX_IMAGE" and n.image and n.name.startswith("Mtoon1BaseColorTexture"): return n.image
    for n in m.node_tree.nodes:
        if n.type == "TEX_IMAGE" and n.image and not any(k in n.image.name for k in ("nml", "spe", "outline")): return n.image


class G:
    """Tiny node-graph helper: G(m).n(type, **inputs) creates a node and links/sets inputs by socket name or index."""
    def __init__(s, m):
        s.nt = m.node_tree; s.nt.nodes.clear(); s.x = 0
    def n(s, t, *, props=None, **ins):
        nd = s.nt.nodes.new(t); nd.location = (s.x, 0); s.x += 200
        for k, v in (props or {}).items(): setattr(nd, k, v)
        for k, v in ins.items():
            k = k.replace("_", " "); sock = nd.inputs[int(k[1:])] if k.startswith("i") and k[1:].isdigit() else nd.inputs[k]
            if isinstance(v, bpy.types.NodeSocket): s.nt.links.new(v, sock)
            else: sock.default_value = v
        return nd
    def math(s, op, a, b=0.0, clamp=False):
        return s.n("ShaderNodeMath", props={"operation": op, "use_clamp": clamp}, i0=a, i1=b).outputs[0]
    def mix(s, op, a, b, f=1.0):
        return s.n("ShaderNodeMix", props={"data_type": "RGBA", "blend_type": op}, Factor=f, A=a, B=b).outputs[2]
    def step(s, v, lo, hi):
        return s.n("ShaderNodeMapRange", props={"interpolation_type": "SMOOTHSTEP"}, Value=v, From_Min=lo, From_Max=hi).outputs[0]
    def finish(s, shader, alpha):
        tr = s.n("ShaderNodeBsdfTransparent"); mx = s.n("ShaderNodeMixShader", Fac=alpha, i1=tr.outputs[0], i2=shader)
        s.n("ShaderNodeOutputMaterial", Surface=mx.outputs[0])


def build(m, k, sdf):
    im = base_image(m); g = G(m)
    tex = g.n("ShaderNodeTexImage", props={"image": im}); col, alpha = tex.outputs["Color"], tex.outputs["Alpha"]
    if k == "unlit":
        return g.finish(g.n("ShaderNodeEmission", Color=col, Strength=1.0).outputs[0], alpha)
    shade = (*SHADE[k], 1)
    ambient = g.n("ShaderNodeEmission", Color=g.mix("MULTIPLY", col, shade), Strength=1.0).outputs[0]
    facing = g.n("ShaderNodeLayerWeight", Blend=.5).outputs["Facing"]; rim = g.step(facing, .62, .70)
    if STYLE == "classic":
        lum = g.n("ShaderNodeRGBToBW", Color=g.n("ShaderNodeShaderToRGB", Shader=g.n("ShaderNodeBsdfDiffuse", Color=(1, 1, 1, 1)).outputs[0]).outputs[0]).outputs[0]
        lit = g.step(lum, .18 - SOFT, .18 + SOFT)
        light = g.math("ADD", lit, g.math("MULTIPLY", rim, g.math("MULTIPLY", lit, RIM)))
        tone = g.mix("MIX", shade, (1, 1, 1, 1), light)
        out = g.mix("MULTIPLY", col, tone)
        if k == "hair":
            glo = g.n("ShaderNodeRGBToBW", Color=g.n("ShaderNodeShaderToRGB", Shader=g.n("ShaderNodeBsdfAnisotropic" if hasattr(bpy.types, "ShaderNodeBsdfAnisotropic") else "ShaderNodeBsdfGlossy", Roughness=.25).outputs[0]).outputs[0]).outputs[0]
            out = g.mix("ADD", out, (1, .95, .85, 1), g.math("MULTIPLY", g.step(glo, .5, .56), .45))
        return g.finish(g.n("ShaderNodeEmission", Color=out, Strength=1.0).outputs[0], alpha)
    # ---- 5.4 Material Lighting loop: everything below is evaluated once per light ----
    info = g.n("ShaderNodeLightInfo"); shadow = g.n("ShaderNodeRGBToBW", Color=g.n("ShaderNodeShadowRaycast", Softness=.15).outputs[0]).outputs[0]
    if k == "face":
        ev = g.n("ShaderNodeLightEvaluation", props={"mode": "DIFFUSE"})
        L = g.n("ShaderNodeVectorTransform", props={"vector_type": "VECTOR", "convert_from": "WORLD", "convert_to": "OBJECT"}, Vector=ev.outputs["Direction"]).outputs[0]
        sep = g.n("ShaderNodeSeparateXYZ", Vector=L)
        flat = g.math("SQRT", g.math("ADD", g.math("MULTIPLY", sep.outputs[0], sep.outputs[0]), g.math("MULTIPLY", sep.outputs[1], sep.outputs[1])))
        cos = g.math("DIVIDE", g.math("MULTIPLY", sep.outputs[1], -1.0), g.math("MAXIMUM", flat, 1e-4))
        ang = g.math("DIVIDE", g.math("ARCCOSINE", g.math("MINIMUM", g.math("MAXIMUM", cos, -1.0), 1.0)), math.pi)
        sd = g.n("ShaderNodeTexImage", props={"image": sdf, "interpolation": "Linear"}); sdf.colorspace_settings.name = "Non-Color"
        rgb = g.n("ShaderNodeSeparateColor", Color=sd.outputs["Color"])
        left = g.math("GREATER_THAN", sep.outputs[0], 0.0)                                   # light on her left (+X)
        t = g.n("ShaderNodeMix", props={"data_type": "FLOAT"}, Factor=left, A=rgb.outputs[1], B=rgb.outputs[0]).outputs[0]
        up = g.step(ev.outputs["Factor"], 0.0, 0.02)                                          # no light from below the surface
        lit = g.math("MULTIPLY", g.step(g.math("SUBTRACT", t, ang), -SOFT, SOFT), g.math("MULTIPLY", up, g.math("ADD", .5, g.math("MULTIPLY", shadow, .5))))
    else:
        ev = g.n("ShaderNodeLightEvaluation", props={"mode": "DIFFUSE"})
        lit = g.step(g.math("MULTIPLY", ev.outputs["Factor"], shadow), .18 - SOFT, .18 + SOFT)
    inv = tuple(1 - c for c in shade[:3]) + (1,)
    diff_amt = g.math("ADD", lit, g.math("MULTIPLY", rim, g.math("MULTIPLY", lit, RIM)))
    diff_light = g.mix("MULTIPLY", g.mix("MULTIPLY", info.outputs["Color"], inv), (1, 1, 1, 1))
    diff_light = g.mix("MULTIPLY", diff_light, g.n("ShaderNodeCombineColor", Red=diff_amt, Green=diff_amt, Blue=diff_amt).outputs[0])
    acc_in = {"Diffuse_Light": diff_light, "Diffuse_Color": col}
    if k == "hair":
        gl = g.n("ShaderNodeLightEvaluation", props={"mode": "GLOSSY"}, Roughness=.22)
        spec = g.math("MULTIPLY", g.step(gl.outputs["Factor"], .5, .56), lit)
        acc_in["Glossy_Light"] = g.mix("MULTIPLY", info.outputs["Color"], g.n("ShaderNodeCombineColor", Red=spec, Green=spec, Blue=spec).outputs[0])
        acc_in["Glossy_Color"] = (.45, .43, .38, 1)
    acc = g.n("ShaderNodeLightAccumulation", **acc_in)
    g.finish(g.n("ShaderNodeAddShader", i0=acc.outputs[0], i1=ambient).outputs[0], alpha)


sdf = bpy.data.images.load(SDF); sdf.pack()
for m in list(bpy.data.materials):
    if m.users and m.node_tree and base_image(m) is not None and not m.name.startswith("Outline"):
        build(m, material_role(m.name), sdf)

out = bpy.data.materials.new("Outline_SUZU"); out.use_backface_culling = True; g = G(out)
g.n("ShaderNodeOutputMaterial", Surface=g.n("ShaderNodeEmission", Color=OUTLINE, Strength=1.0).outputs[0])
for ob in [o for o in bpy.data.objects if o.type == "MESH"]:
    roles = {material_role(mm.name) for mm in ob.data.materials if mm}
    width = .0010 if "face" in roles else .0016 if roles == {"hair"} else .0018
    lined = [i for i, mm in enumerate(ob.data.materials) if mm and material_role(mm.name) != "unlit"]
    if len(lined) < len(ob.data.materials):                                                 # outline skin and cloth, never eyes or lashes
        vg = ob.vertex_groups.new(name="OutlineMask")
        vg.add(sorted({v for p in ob.data.polygons if p.material_index in lined for v in p.vertices}), 1.0, "REPLACE")
    n = len(ob.data.materials); ob.data.materials.append(out)
    sm = ob.modifiers.new("Outline", "SOLIDIFY"); sm.thickness = -width; sm.offset = 1; sm.use_flip_normals = True
    sm.material_offset = n; sm.use_rim = False
    if "OutlineMask" in ob.vertex_groups: sm.vertex_group = "OutlineMask"
    ob.modifiers.move(len(ob.modifiers) - 1, len(ob.modifiers) - 1)

sc = bpy.context.scene; sc.render.engine = "BLENDER_EEVEE"; sc.view_settings.view_transform = "Standard"; sc.view_settings.look = "None"
for o in [o for o in sc.objects if o.type == "LIGHT"]: bpy.data.objects.remove(o)
def sun(name, rx, rz, energy, color):
    L = bpy.data.objects.new(name, bpy.data.lights.new(name, "SUN")); sc.collection.objects.link(L)
    L.rotation_euler = (math.radians(rx), 0, math.radians(rz)); L.data.energy = energy; L.data.color = color; L.data.angle = math.radians(2); return L
sun("Key", 45, 35, 3.0, (1.0, .97, .92))        # front, from her left, above
sun("Rim", 75, 200, 1.5, (.75, .85, 1.0))       # behind, cool
w = sc.world or bpy.data.worlds.new("World"); sc.world = w; w.use_nodes = True
wn = w.node_tree.nodes; bg = wn.get("Background"); bg.inputs[1].default_value = 1.0           # backdrop seen by the camera only:
lp = wn.new("ShaderNodeLightPath"); mx = wn.new("ShaderNodeMix"); mx.data_type = "RGBA"                 # no world light reaches either style
mx.inputs["A"].default_value = (0, 0, 0, 1); mx.inputs["B"].default_value = (.78, .82, .88, 1)
w.node_tree.links.new(lp.outputs["Is Camera Ray"], mx.inputs["Factor"]); w.node_tree.links.new(mx.outputs["Result"], bg.inputs[0])
bpy.ops.wm.save_as_mainfile(filepath=OUT); print("TOON", STYLE, "saved", OUT)
