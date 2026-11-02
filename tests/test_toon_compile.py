"""Toon material compiler: graphs are built here, compiled to Godot shader text, and the shader is then executed by a
small GLSL-subset interpreter, so the tests check values (the kit's analytic cel formula), not just text."""
import math
from pathlib import Path
import re
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import toon_compile as tc


# ---- a GLSL-subset interpreter (vec2/3/4, mat3, the built-ins the compiler emits) ----
class V(tuple):
    def __new__(cls, *c):
        return tuple.__new__(cls, [float(x) for x in c])

    def _op(self, o, f):
        o = o if isinstance(o, V) else V(*([o] * len(self)))
        return V(*(f(a, b) for a, b in zip(self, o)))

    __add__ = lambda s, o: s._op(o, lambda a, b: a + b)
    __radd__ = __add__
    __sub__ = lambda s, o: s._op(o, lambda a, b: a - b)
    __rsub__ = lambda s, o: V(*([o] * len(s)))._op(s, lambda a, b: a - b)
    __mul__ = lambda s, o: s._op(o, lambda a, b: a * b)
    __rmul__ = __mul__
    __truediv__ = lambda s, o: s._op(o, lambda a, b: a / b)
    __neg__ = lambda s: V(*(-a for a in s))

    def __getattr__(self, k):
        idx = {"x": 0, "y": 1, "z": 2, "w": 3, "r": 0, "g": 1, "b": 2, "a": 3}
        vals = [self[idx[c]] for c in k]
        return vals[0] if len(vals) == 1 else V(*vals)


class M:
    def __init__(self, rows):
        self.r = rows

    def __mul__(self, v):
        return V(*(sum(a * b for a, b in zip(row, v)) for row in self.r[:len(v)]))


def _vec(n):
    def make(*a):
        flat = [c for x in a for c in (x if isinstance(x, V) else [x])]
        return V(*(flat * n if len(flat) == 1 else flat))
    return make


def _cw(f):
    return lambda *a: V(*(f(*c) for c in zip(*[x if isinstance(x, V) else [x] * len(next(y for y in a if isinstance(y, V))) for x in a]))) \
        if any(isinstance(x, V) for x in a) else f(*a)


def _mix(a, b, t):
    return a * (1 - t) + b * t if not isinstance(t, V) else _cw(lambda x, y, z: x * (1 - z) + y * z)(a, b, t)


ENV = dict(vec2=_vec(2), vec3=_vec(3), vec4=_vec(4), mat3=lambda m: m, transpose=lambda m: M([list(c) for c in zip(*m.r)]),
           inverse=lambda m: M([list(c) for c in zip(*m.r)]),  # tests only use rotation matrices
           dot=lambda a, b: sum(x * y for x, y in zip(a, b)), length=lambda a: math.sqrt(sum(x * x for x in a)),
           normalize=lambda a: a / math.sqrt(sum(x * x for x in a)), cross=lambda a, b: V(a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]),
           distance=lambda a, b: math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b))), mix=_mix,
           clamp=_cw(lambda x, a, b: min(max(x, a), b)), step=_cw(lambda e, x: 0.0 if x < e else 1.0), pow=_cw(math.pow),
           abs=_cw(abs), sqrt=_cw(math.sqrt), max=_cw(max), min=_cw(min), floor=_cw(math.floor), ceil=_cw(math.ceil),
           trunc=_cw(math.trunc), exp=_cw(math.exp), log=_cw(math.log), sign=_cw(lambda x: (x > 0) - (x < 0)),
           sin=math.sin, cos=math.cos, tan=math.tan, asin=math.asin, acos=math.acos, atan=math.atan2 if False else (lambda y, x=None: math.atan(y) if x is None else math.atan2(y, x)),
           inversesqrt=lambda x: 1 / math.sqrt(x), PI=math.pi)


def py_lines(lines):
    out = []
    for s in lines:
        s = s.strip().rstrip(";")
        s = re.sub(r"\((\w+) \? ([^:()]+) : ([^()]+)\)", r"(\2 if \1 else \3)", s)
        s = re.sub(r"^(float|vec2|vec3|vec4) ", "", s)
        s = re.sub(r"(\d)\.(\d+)e", r"\1.\2e", s)
        out.append(s)
    return out


def load_shader(text):
    """Python callables for the shader's helpers, fragment() and light()."""
    env = dict(ENV)
    env.update({u: u for u in re.findall(r"^uniform sampler2D (\w+)", text, re.M)})
    for m in re.finditer(r"^(?:float|vec3) (\w+)\(([^)]*)\) \{\n(.*?)\n\}", text, re.S | re.M):
        args = ", ".join(a.split()[-1] for a in m.group(2).split(","))
        body = py_lines(m.group(3).split("\n"))
        body = [("return " + b[len("return "):]) if b.startswith("return ") else b for b in body]
        exec(f"def {m.group(1)}({args}):\n" + "\n".join("    " + b for b in body), env)

    def stage(name):
        m = re.search(r"^void " + name + r"\(\) \{\n(.*?)\n\}", text, re.S | re.M)
        return py_lines(m.group(1).split("\n")) if m else []
    return env, stage("fragment"), stage("light")


I3 = M([[1, 0, 0], [0, 1, 0], [0, 0, 1]])


def g(v):  # Blender world -> Godot world (the camera is the identity, so view space is Godot world)
    return V(v[0], v[2], -v[1])


def run(text, normal, lights, view=(0, -1, 0), uv=(0.25, 0.5), tex=None, front=True):
    """Execute fragment() then light() once per light; returns (final colour, alpha). Vectors are Blender world."""
    env, frag, light = load_shader(text)
    st = dict(env, NORMAL=g(normal), VIEW=g(view), UV=V(*uv), INV_VIEW_MATRIX=I3, MODEL_MATRIX=I3, FRONT_FACING=front,
              ALBEDO=V(0, 0, 0), EMISSION=V(0, 0, 0), ALPHA=1.0, VERTEX=V(0, 0, 0))
    st["texture"] = lambda s, p: (tex or (lambda u: V(.8, .6, .4, 1)))(p)
    for line in frag:
        exec(line, st)
    diffuse, spec = V(0, 0, 0), V(0, 0, 0)
    for L, color, atten in lights:
        ls = dict(st, LIGHT=g(L), LIGHT_COLOR=V(*color) * math.pi, ATTENUATION=atten, DIFFUSE_LIGHT=V(0, 0, 0), SPECULAR_LIGHT=V(0, 0, 0))
        for line in light:
            exec(line, ls)
        diffuse, spec = diffuse + ls["DIFFUSE_LIGHT"], spec + ls["SPECULAR_LIGHT"]
    final = st["ALBEDO"] if "unshaded" in text else st["EMISSION"] + st["ALBEDO"] * diffuse + spec
    return final, st.get("ALPHA", 1.0)


# ---- a tiny IR builder, shaped like the kit's G helper ----
class B:
    def __init__(self):
        self.nodes, self.n = {}, 0

    def node(self, t, ins=None, outs=None, **props):
        self.n += 1
        name = f"{t}.{self.n}"
        inputs = {}
        for k, v in (ins or {}).items():
            typ, val = v if isinstance(v, tuple) and len(v) == 2 and isinstance(v[0], str) else (None, v)
            if isinstance(val, Out):
                inputs[k] = {"name": k.split("#")[0], "type": typ or val.type, "link": [val.node, val.key]}
            else:
                inputs[k] = {"name": k.split("#")[0], "type": typ or ("RGBA" if isinstance(val, (list, tuple)) else "VALUE"), "default": val, "link": None}
        self.nodes[name] = {"type": t, "props": props, "inputs": inputs,
                            "outputs": {k: {"name": k, "type": ty} for k, ty in (outs or {}).items()}}
        return name

    def out(self, name, key):
        return Out(name, key, self.nodes[name]["outputs"][key]["type"])

    def mat(self, surface, **kw):
        o = self.node("OUTPUT_MATERIAL", {"Surface": ("SHADER", surface)})
        return dict({"nodes": self.nodes, "output": o}, **kw)


class Out:
    def __init__(self, node, key, typ):
        self.node, self.key, self.type = node, key, typ


def math_(b, op, a, c=0.0, clamp=False):
    sock = lambda v: ("VALUE", v) if isinstance(v, Out) else v  # noqa: E731  Math sockets are floats; links convert
    return b.out(b.node("MATH", {"Value": sock(a), "Value_001": sock(c)}, {"Value": "VALUE"}, operation=op, use_clamp=clamp), "Value")


def mix(b, op, a, c, f=1.0):
    return b.out(b.node("MIX", {"Factor": f, "A": ("RGBA", a), "B": ("RGBA", c)}, {"Result": "RGBA"}, data_type="RGBA", blend_type=op), "Result")


def smooth(b, v, lo, hi):
    return b.out(b.node("MAP_RANGE", {"Value": v, "From Min": lo, "From Max": hi, "To Min": 0.0, "To Max": 1.0}, {"Result": "VALUE"},
                        interpolation_type="SMOOTHSTEP"), "Result")


SHADE, RIM = (0.62, 0.62, 0.78), 0.35
IMAGES = {"base.png": {"file": "textures/base.png", "colorspace": "sRGB"}}


def kit_cloth(b):
    """The kit's `ml` cloth graph (scripts/vrm_toon_bpy.py), node for node."""
    tex = b.node("TEX_IMAGE", {"Vector": ("VECTOR", [0, 0, 0])}, {"Color": "RGBA", "Alpha": "VALUE"}, image="base.png")
    col, alpha = b.out(tex, "Color"), b.out(tex, "Alpha")
    amb = b.out(b.node("EMISSION", {"Color": ("RGBA", mix(b, "MULTIPLY", col, list(SHADE) + [1])), "Strength": 1.0}, {"Emission": "SHADER"}), "Emission")
    facing = b.out(b.node("LAYER_WEIGHT", {"Blend": 0.5, "Normal": ("VECTOR", [0, 0, 0])}, {"Fresnel": "VALUE", "Facing": "VALUE"}), "Facing")
    rim = smooth(b, facing, .62, .70)
    info = b.node("LIGHT_INFO", {}, {"Color": "RGBA", "Power": "VALUE"})
    shadow = b.out(b.node("RGBTOBW", {"Color": ("RGBA", b.out(b.node("SHADOW_RAYCAST", {"Softness": .15}, {"Color": "RGBA"}), "Color"))}, {"Val": "VALUE"}), "Val")
    ev = b.node("LIGHT_EVALUATION", {"Normal": ("VECTOR", [0, 0, 0])}, {"Factor": "VALUE", "Mask": "VALUE", "Direction": "VECTOR", "Distance": "VALUE"}, mode="DIFFUSE")
    lit = smooth(b, math_(b, "MULTIPLY", b.out(ev, "Factor"), shadow), .15, .21)
    amt = math_(b, "ADD", lit, math_(b, "MULTIPLY", rim, math_(b, "MULTIPLY", lit, RIM)))
    dl = mix(b, "MULTIPLY", mix(b, "MULTIPLY", b.out(info, "Color"), [1 - c for c in SHADE] + [1]), [1, 1, 1, 1])
    dl = mix(b, "MULTIPLY", dl, b.out(b.node("COMBINE_COLOR", {"Red": amt, "Green": amt, "Blue": amt}, {"Color": "RGBA"}), "Color"))
    acc = b.out(b.node("LIGHT_ACCUMULATION", {"Diffuse Light": ("RGBA", dl), "Diffuse Color": ("RGBA", col)}, {"BSDF": "SHADER"}), "BSDF")
    add = b.out(b.node("ADD_SHADER", {"Shader": ("SHADER", acc), "Shader_001": ("SHADER", amb)}, {"Shader": "SHADER"}), "Shader")
    tr = b.out(b.node("BSDF_TRANSPARENT", {"Color": [1, 1, 1, 1]}, {"BSDF": "SHADER"}), "BSDF")
    mx = b.out(b.node("MIX_SHADER", {"Fac": alpha, "Shader": ("SHADER", tr), "Shader_001": ("SHADER", add)}, {"Shader": "SHADER"}), "Shader")
    return b.mat(mx, blend="DITHERED")


def smoothstep(lo, hi, x):
    t = min(max((x - lo) / (hi - lo), 0), 1)
    return t * t * (3 - 2 * t)


def kit_expected(base, normal, view, lights):
    """The kit's cel formula, written independently: base x shade + sum over lights of base x colour x (1 - shade) x amount."""
    n = ENV["normalize"](V(*normal))
    v = ENV["normalize"](V(*view))
    facing = 1 - abs(ENV["dot"](n, v))
    rim = smoothstep(.62, .70, facing)
    out = V(*base) * V(*SHADE)
    for L, color, atten in lights:
        lit = smoothstep(.15, .21, max(0.0, min(1.0, ENV["dot"](n, ENV["normalize"](V(*L))))) * atten)
        out = out + V(*base) * V(*color) * (V(1, 1, 1) - V(*SHADE)) * (lit + rim * lit * RIM)
    return out


def compile_one(mat, images=IMAGES, groups=None):
    return tc.Compiler("m", mat, groups or {}, images).compile()


def close(a, b, tol=1e-5):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


class KitGraph(unittest.TestCase):
    def setUp(self):
        self.r = compile_one(kit_cloth(B()))

    def test_compiles_with_the_loop_split(self):
        self.assertEqual(self.r["status"], "ok")
        sh = self.r["shader"]
        light = sh.split("void light()")[1]
        frag = sh.split("void fragment()")[1].split("void light()")[0]
        self.assertIn("ATTENUATION", light)
        self.assertNotIn("texture(", light)        # textures are sampled once, in fragment()
        self.assertNotIn("LIGHT", frag.replace("ALPHA", ""))
        self.assertIn("ambient_light_disabled", sh)
        self.assertIn("ALPHA_SCISSOR_THRESHOLD = 0.5", sh)

    def test_matches_the_kit_formula(self):
        base = (.8, .6, .4)
        cases = [((0, -1, 0), [((0.3, -1, 0.6), (1, .97, .92), 1.0)]),
                 ((0.9, -0.3, 0.1), [((0.3, -1, 0.6), (1, .97, .92), 1.0), ((-0.5, 0.8, 0.4), (.75, .85, 1.0), 1.0)]),
                 ((0.2, -0.6, 0.77), [((0.0, -0.2, 1.0), (1, 1, 1), 0.4)]),     # partly shadowed
                 ((-1, 0.05, 0), [((1, -0.2, 0.3), (1, 1, 1), 1.0)])]         # light behind the surface
        for normal, lights in cases:
            got, alpha = run(self.r["shader"], normal, lights)
            want = kit_expected(base, normal, (0, -1, 0), lights)
            self.assertTrue(close(got, want), f"{normal}: {got} != {want}")
            self.assertEqual(alpha, 1.0)

    def test_alpha_from_the_texture(self):
        _, alpha = run(self.r["shader"], (0, -1, 0), [], tex=lambda uv: V(.8, .6, .4, 0.25))
        self.assertAlmostEqual(alpha, 0.25)


class Nodes(unittest.TestCase):
    def emit(self, b, value):
        """A material that shows `value` (a colour output) unshaded."""
        return b.mat(b.out(b.node("EMISSION", {"Color": ("RGBA", value), "Strength": 1.0}, {"Emission": "SHADER"}), "Emission"))

    def eval(self, mat, normal=(0, -1, 0), view=(0, -1, 0)):
        r = compile_one(mat)
        self.assertEqual(r["status"], "ok", r.get("unsupported"))
        return run(r["shader"], normal, [], view=view)[0]

    def test_unshaded_without_light_accumulation(self):
        b = B()
        r = compile_one(self.emit(b, [.2, .3, .4, 1]))
        self.assertIn("unshaded", r["shader"])
        self.assertNotIn("void light()", r["shader"])

    def test_implicit_conversions(self):
        # colour -> float is luminance; vector -> float is the average; float -> colour broadcasts
        for kind, value, want in (("RGB", [1, 0, 0, 1], 0.2126), ("VECTOR", [3, 6, 0], 3.0)):
            b = B()
            src = b.node("RGB", {}, {"Color": kind if kind == "VECTOR" else "RGBA"})
            b.nodes[src]["outputs"]["Color"]["default"] = value
            self.assertTrue(close(self.eval(self.emit(b, math_(b, "ADD", b.out(src, "Color"), 0.0))), [want] * 3), kind)

    def test_mix_blends(self):
        a, c = [.2, .4, .6, 1], [.5, .5, .5, 1]
        want = {"MULTIPLY": [.15, .3, .45], "ADD": [.45, .65, .85], "SUBTRACT": [-.05, .15, .35], "MIX": [.35, .45, .55],
                "SCREEN": [.4, .55, .7], "LIGHTEN": [.35, .45, .6], "DARKEN": [.2, .4, .55]}
        for op, w in want.items():
            b = B()
            got = self.eval(self.emit(b, mix(b, op, a, c, 0.5)))
            self.assertTrue(close(got, w), f"{op}: {got} != {w}")

    def test_map_range_modes(self):
        for mode, v, want in (("LINEAR", 0.75, 0.5), ("LINEAR", 2.0, 1.0), ("SMOOTHSTEP", 0.75, 0.5), ("SMOOTHSTEP", 0.6, .104)):
            b = B()
            r = b.out(b.node("MAP_RANGE", {"Value": v, "From Min": 0.5, "From Max": 1.0, "To Min": 0.0, "To Max": 1.0}, {"Result": "VALUE"},
                             interpolation_type=mode, clamp=True), "Result")
            self.assertAlmostEqual(self.eval(self.emit(b, r))[0], want, 3, mode)
        b = B()  # an inverted range counts down, as in Blender
        r = b.out(b.node("MAP_RANGE", {"Value": 0.6, "From Min": 1.0, "From Max": 0.5, "To Min": 0.0, "To Max": 1.0}, {"Result": "VALUE"},
                         interpolation_type="SMOOTHSTEP"), "Result")
        self.assertAlmostEqual(self.eval(self.emit(b, r))[0], 1 - .104, 3)

    def test_math_is_blender_safe(self):
        for op, a, c, want in (("DIVIDE", 1.0, 0.0, 0.0), ("SQRT", -4.0, 0, 0.0), ("ARCCOSINE", 2.0, 0, 0.0),
                               ("GREATER_THAN", 2.0, 1.0, 1.0), ("GREATER_THAN", 1.0, 1.0, 0.0), ("LESS_THAN", 0.5, 1.0, 1.0),
                               ("MODULO", -3.0, 2.0, -1.0), ("FLOORED_MODULO", -3.0, 2.0, 1.0)):
            b = B()
            self.assertAlmostEqual(self.eval(self.emit(b, math_(b, op, a, c)))[0], want, 5, op)

    def test_layer_weight_matches_blender(self):
        for blend, nv in ((0.5, 0.6), (0.3, 0.6), (0.8, 0.9)):
            b = B()
            f = b.out(b.node("LAYER_WEIGHT", {"Blend": blend, "Normal": ("VECTOR", [0, 0, 0])}, {"Fresnel": "VALUE", "Facing": "VALUE"}), "Facing")
            normal = (math.sqrt(1 - nv * nv), -nv, 0)
            e = 2 * blend if blend < 0.5 else 0.5 / (1 - blend)
            self.assertAlmostEqual(self.eval(self.emit(b, f), normal=normal)[0], 1 - nv ** e, 5)

    def test_color_ramp(self):
        ramp = {"interpolation": "CONSTANT", "elements": [{"position": 0.0, "color": [0, 0, 0, 1]}, {"position": 0.5, "color": [1, 1, 1, 1]}]}
        for mode, fac, want in (("CONSTANT", 0.49, 0.0), ("CONSTANT", 0.5, 1.0), ("LINEAR", 0.25, 0.5)):
            b = B()
            r = b.out(b.node("VALTORGB", {"Fac": fac}, {"Color": "RGBA", "Alpha": "VALUE"}, ramp=dict(ramp, interpolation=mode)), "Color")
            self.assertAlmostEqual(self.eval(self.emit(b, r))[0], want, 5, mode)

    def test_groups_reroutes_and_mutes_resolve(self):
        inner = B()
        gi = inner.node("GROUP_INPUT", {}, {"Socket_0": "VALUE"})
        m = math_(inner, "MULTIPLY", inner.out(gi, "Socket_0"), 2.0)
        inner.node("GROUP_OUTPUT", {"Socket_1": ("VALUE", m)}, {}, )
        b = B()
        rr = b.node("REROUTE", {"Input": 0.25}, {"Output": "VALUE"})
        muted = b.node("MATH", {"Value": b.out(rr, "Output"), "Value_001": 100.0}, {"Value": "VALUE"}, operation="ADD")
        b.nodes[muted].update(mute=True, internal_links=[["Value", "Value"]])
        grp = b.node("GROUP", {"Socket_0": b.out(muted, "Value")}, {"Socket_1": "VALUE"})
        b.nodes[grp]["tree"] = "Double"
        mat = self.emit(b, b.out(grp, "Socket_1"))
        r = tc.Compiler("m", mat, {"Double": {"nodes": inner.nodes}}, IMAGES).compile()
        self.assertEqual(r["status"], "ok", r.get("unsupported"))
        self.assertTrue(close(run(r["shader"], (0, -1, 0), [])[0], [0.5] * 3))

    def test_light_nodes_outside_the_loop(self):
        b = B()
        ev = b.node("LIGHT_EVALUATION", {}, {"Factor": "VALUE"}, mode="DIFFUSE")
        r = compile_one(self.emit(b, b.out(ev, "Factor")))
        self.assertEqual(r["status"], "ok")
        self.assertTrue(r["warnings"])                                      # Blender's default (1.0), flagged
        self.assertTrue(close(run(r["shader"], (0, -1, 0), [])[0], [1.0] * 3))
        b = B()
        info = b.node("LIGHT_INFO", {}, {"Color": "RGBA"})
        self.assertEqual(compile_one(self.emit(b, b.out(info, "Color")))["status"], "unsupported")

    def test_unsupported_nodes_are_reported(self):
        b = B()
        p = b.out(b.node("BSDF_PRINCIPLED", {}, {"BSDF": "SHADER"}), "BSDF")
        r = compile_one(b.mat(p))
        self.assertEqual(r["status"], "unsupported")
        self.assertNotIn("shader", r)
        b = B()
        info = b.node("LIGHT_INFO", {}, {"Position": "VECTOR"})
        acc = b.out(b.node("LIGHT_ACCUMULATION", {"Diffuse Light": ("RGBA", b.out(info, "Position")), "Diffuse Color": [1, 1, 1, 1]}, {"BSDF": "SHADER"}), "BSDF")
        self.assertIn("Position", compile_one(b.mat(acc))["unsupported"][0])

    def test_light_info_split(self):
        # Godot sees colour x Power; Power is its brightest channel, Color the normalised rest; their product is exact.
        for out, want in (("Power", [2.0] * 3), ("Color", [1.0, 0.5, 0.25])):
            b = B()
            info = b.node("LIGHT_INFO", {}, {"Color": "RGBA", "Power": "VALUE"})
            acc = b.out(b.node("LIGHT_ACCUMULATION", {"Diffuse Light": ("RGBA", b.out(info, out)), "Diffuse Color": [1, 1, 1, 1]}, {"BSDF": "SHADER"}), "BSDF")
            r = compile_one(b.mat(acc))
            got = run(r["shader"], (0, -1, 0), [((0, -1, 0), (2.0, 1.0, 0.5), 1.0)])[0]
            self.assertTrue(close(got, want), f"{out}: {got}")

    def test_glossy_factor(self):
        # Fitted to Blender 5.4: GGX D (alpha = rough^2) x N.L. Normal on the half vector: D = 1 / (pi alpha^2).
        b = B()
        ev = b.node("LIGHT_EVALUATION", {"Roughness": 0.5}, {"Factor": "VALUE"}, mode="GLOSSY")
        acc = b.out(b.node("LIGHT_ACCUMULATION", {"Diffuse Light": ("RGBA", b.out(ev, "Factor")), "Diffuse Color": [1, 1, 1, 1]}, {"BSDF": "SHADER"}), "BSDF")
        r = compile_one(b.mat(acc))
        th = math.radians(60)
        got = run(r["shader"], (math.sin(th / 2), -math.cos(th / 2), 0), [((math.sin(th), -math.cos(th), 0), (1.0, 1.0, 1.0), 1.0)])[0]
        want = 1 / (math.pi * 0.0625) * math.cos(th / 2)
        self.assertTrue(close(got, [want] * 3, 1e-3), got)

    def test_object_space_vector(self):
        # Godot MODEL_MATRIX rotated 90 degrees about Godot Y (= Blender Z): a world +X light is object -Y in Blender axes.
        b = B()
        ev = b.node("LIGHT_EVALUATION", {}, {"Direction": "VECTOR"}, mode="DIFFUSE")
        vt = b.out(b.node("VECT_TRANSFORM", {"Vector": ("VECTOR", b.out(ev, "Direction"))}, {"Vector": "VECTOR"},
                          vector_type="VECTOR", convert_from="WORLD", convert_to="OBJECT"), "Vector")
        sep = b.out(b.node("SEPXYZ", {"Vector": ("VECTOR", vt)}, {"X": "VALUE", "Y": "VALUE", "Z": "VALUE"}), "Y")
        acc = b.out(b.node("LIGHT_ACCUMULATION", {"Diffuse Light": ("RGBA", sep), "Diffuse Color": [1, 1, 1, 1]}, {"BSDF": "SHADER"}), "BSDF")
        r = compile_one(b.mat(acc))
        env, frag, light = load_shader(r["shader"])
        rot = M([[0, 0, 1], [0, 1, 0], [-1, 0, 0]])  # Godot basis: object +X -> world -Z
        st = dict(env, NORMAL=g((0, -1, 0)), VIEW=g((0, -1, 0)), UV=V(0, 0), INV_VIEW_MATRIX=I3, MODEL_MATRIX=rot, FRONT_FACING=True,
                  ALBEDO=V(0, 0, 0), EMISSION=V(0, 0, 0), LIGHT=g((1, 0, 0)), LIGHT_COLOR=V(1, 1, 1), ATTENUATION=1.0, DIFFUSE_LIGHT=V(0, 0, 0))
        for line in frag + light:
            exec(line, st)
        self.assertAlmostEqual(st["DIFFUSE_LIGHT"][0], -1.0, 5)


class Scene(unittest.TestCase):
    def test_transforms_convert_axes(self):
        m = [[1, 0, 0, 1], [0, 1, 0, 2], [0, 0, 1, 3], [0, 0, 0, 1]]
        self.assertEqual(tc.godot_transform(m)[3], [1, 3, -2])
        cam = tc.look_at([0, 0, 1], 0, 0, 5)                       # in front of the character (-Y), looking at +Y
        self.assertTrue(close([cam[r][3] for r in range(3)], [0, -5, 1]))
        self.assertTrue(close([-cam[r][2] for r in range(3)], [0, 1, 0]))
        self.assertTrue(close(tc.godot_transform(cam)[2], [0, 0, 1]))  # Godot camera's +Z points back at the viewer side

    def test_top_down_camera(self):
        cam = tc.look_at([0, 0, 1], 0, 90, 5)
        self.assertTrue(close([-cam[r][2] for r in range(3)], [0, 0, -1]))
        self.assertFalse(any(math.isnan(c) for row in cam for c in row))

    def test_camera_sizes_follow_the_wider_side(self):
        c = tc.cameras([{"name": "a", "res": [600, 800], "target": [0, 0, 1], "dist": 5, "ortho": 2.0},
                        {"name": "b", "res": [800, 400], "target": [0, 0, 1], "dist": 5, "fov": 60}])
        self.assertAlmostEqual(c[0]["godot_size"], 2.0)
        self.assertAlmostEqual(c[1]["godot_fov"], math.degrees(2 * math.atan(math.tan(math.radians(30)) / 2)))

    def test_lights_carry_blender_power(self):
        out = tc.lights([{"name": "Key", "type": "SUN", "color": [1, .9, .8], "energy": 3.0, "angle": math.radians(2),
                          "matrix": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]}, {"name": "A", "type": "AREA", "color": [1, 1, 1], "matrix": []}])
        self.assertEqual(len(out), 2)
        self.assertIn("skipped", out[1])
        self.assertEqual((out[0]["type"], out[0]["blender_energy"]), ("directional", 3.0))
        self.assertAlmostEqual(out[0]["energy"], 3.0 / math.pi)        # Light Info Power of a 3 W/m2 sun
        self.assertAlmostEqual(out[0]["angular_distance"], 2.0)


class MToon(unittest.TestCase):
    def test_kit_parameters(self):
        mt = tc.mtoon("m", kit_cloth(B()), {})["VRMC_materials_mtoon"]
        self.assertAlmostEqual(mt["shadingShiftFactor"], -0.18)
        self.assertAlmostEqual(mt["shadingToonyFactor"], 0.97)
        self.assertEqual(mt["shadeColorFactor"], list(SHADE))
        self.assertEqual(mt["shadeMultiplyTexture"], {"image": "base.png"})
        self.assertAlmostEqual(mt["parametricRimLiftFactor"], 0.3)
        # the MToon rim reaches 1 at the graph's upper edge and is about 5 % at its lower edge
        p, lift = mt["parametricRimFresnelPowerFactor"], mt["parametricRimLiftFactor"]
        self.assertAlmostEqual(min(1.0, 0.70 + lift) ** p, 1.0)
        self.assertAlmostEqual((0.62 + lift) ** p, 0.05, 3)


class Files(unittest.TestCase):
    def test_compile_ir_writes_everything(self):
        ir = {"materials": {"Cloth": kit_cloth(B()), "Bad/Name": B().mat(None), "Bad Name": B().mat(None)}, "images": IMAGES,
              "lights": [], "cameras": [{"name": "front", "res": [64, 64], "target": [0, 0, 1], "dist": 3, "fov": 40}]}
        with tempfile.TemporaryDirectory() as d:
            doc = tc.compile_ir(ir, Path(d))
            self.assertEqual(doc["summary"]["ok"], 3)
            self.assertEqual(doc["materials"]["Bad Name"]["file"], "shaders/Bad_Name_1.gdshader")
            self.assertTrue((Path(d) / "shaders" / "Cloth.gdshader").is_file())
            self.assertEqual(doc["materials"]["Bad/Name"]["file"], "shaders/Bad_Name.gdshader")
            for f in ("report.json", "mtoon.json", "lights.json", "cameras.json"):
                self.assertTrue((Path(d) / f).is_file(), f)


class Parity(unittest.TestCase):
    def test_measures_inside_the_subject_only(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "ref").mkdir()
            (d / "cand").mkdir()
            ref = Image.new("RGB", (10, 10), (0, 0, 0))
            ref.paste((100, 100, 100), (0, 0, 5, 10))         # subject: left half
            cand = ref.copy()
            cand.paste((130, 100, 100), (0, 0, 5, 5))         # a quarter of the image differs by 30
            ref.save(d / "ref" / "v.png")
            cand.save(d / "cand" / "v.png")
            Image.new("RGB", (4, 4)).save(d / "ref" / "w.png")
            r = tc.parity(d / "ref", d / "cand", d / "out", [0, 0, 0])
            self.assertEqual(r["v"]["subject_px"], 50)
            self.assertAlmostEqual(r["v"]["mean_abs"], 15.0)
            self.assertEqual((r["v"]["over8"], r["v"]["over24"]), (0.5, 0.5))
            self.assertIn("missing", r["w"])
            self.assertTrue((d / "out" / "v-diff.png").is_file())


if __name__ == "__main__":
    unittest.main()
