"""Toon material compiler: Blender 5.4 Material Lighting graphs -> Godot 4.7 spatial shaders + VRM MToon parameters.

Pure Python (stdlib). The graph comes from `toon_compile_bpy.py`, which dumps materials as a JSON IR; see
docs/TOON-COMPILER.md for the IR, the light convention and the parity proof.

  python scripts/toon_compile.py IR.json OUT_DIR       writes OUT_DIR/shaders/*.gdshader, report.json, mtoon.json, lights.json
  python scripts/toon_compile.py parity REF_DIR CAND_DIR OUT_DIR ["[r, g, b]"]   per-view difference inside the subject

How a graph maps: every node downstream of Light Evaluation, Light Info or Shadow Raycast is evaluated per light,
exactly like Godot's light(); the rest runs once in fragment() and reaches light() through varyings. Light
Accumulation becomes DIFFUSE_LIGHT/SPECULAR_LIGHT (ALBEDO = 1), Emission becomes EMISSION, Transparent BSDF becomes
ALPHA, and world light is off (`ambient_light_disabled`), as in Blender where world light never enters the loop.
All vectors stay in Blender world axes inside the shader; Godot built-ins are converted where they are read.
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

LIGHT_SOURCES = {"LIGHT_EVALUATION", "LIGHT_INFO", "SHADOW_RAYCAST"}
LUMA = "vec3(0.2126, 0.7152, 0.0722)"  # Blender's scene-linear Rec.709 luminance (colour -> float, RGB to BW)

# GLSL helpers, written in a subset the tests can also evaluate in Python (no ternaries, no bools).
HELPERS = {
    "b_world": "vec3 b_world(vec3 v) {\n\treturn vec3(v.x, -v.z, v.y);\n}",  # Godot world (Y up) -> Blender world (Z up)
    "g_world": "vec3 g_world(vec3 v) {\n\treturn vec3(v.x, v.z, -v.y);\n}",
    "safe_div": "float safe_div(float a, float b) {\n\tfloat z = 1.0 - step(1e-30, abs(b));\n\treturn a * (1.0 - z) / (b + z);\n}",
    # Light convention: Godot light_color = Blender colour, light_energy = Blender Light Info Power. Power is the brightest
    # channel of LIGHT_COLOR / PI and Color the rest: exact when the colour's brightest channel is 1, products always.
    "light_rgb": "vec3 light_rgb(vec3 c) {\n\treturn c / max(max(c.x, max(c.y, c.z)), 1e-8);\n}",
    "light_power": "float light_power(vec3 c) {\n\treturn max(c.x, max(c.y, c.z));\n}",
    # Blender safe power: a negative base keeps its sign for an odd integer exponent, 0 for a non-integer one.
    "safe_pow": ("float safe_pow(float a, float b) {\n\tfloat r = pow(abs(a), b);\n\tfloat e = floor(b + 0.5);\n"
                 "\tfloat isint = 1.0 - step(1e-6, abs(b - e));\n\tfloat odd = e - 2.0 * floor(e * 0.5);\n"
                 "\treturn mix(r, r * isint * (1.0 - 2.0 * odd), 1.0 - step(0.0, a));\n}"),
    "lin01": "float lin01(float v, float a, float b) {\n\treturn clamp(safe_div(v - a, b - a), 0.0, 1.0);\n}",
    "fresnel_cos": ("float fresnel_cos(float cosi, float eta) {\n\tfloat c = abs(cosi);\n\tfloat g = eta * eta - 1.0 + c * c;\n"
                    "\tfloat ok = step(1e-30, g);\n\tg = sqrt(max(g, 1e-30));\n\tfloat a = (g - c) / (g + c);\n"
                    "\tfloat b = (c * (g + c) - 1.0) / (c * (g - c) + 1.0);\n\treturn mix(1.0, 0.5 * a * a * (1.0 + b * b), ok);\n}"),
    # Light Evaluation (Glossy) Factor, fitted to Blender 5.4 (docs/TOON-COMPILER.md, Measured): GGX D (alpha = rough^2)
    # times N.L, no geometry or 1/(4 N.V) term.
    "ggx_factor": ("float ggx_factor(vec3 n, vec3 l, vec3 v, float rough) {\n\tvec3 h = normalize(l + v);\n"
                   "\tfloat a2 = max(rough * rough * rough * rough, 1e-7);\n\tfloat nh = max(dot(n, h), 0.0);\n"
                   "\tfloat d = nh * nh * (a2 - 1.0) + 1.0;\n"
                   "\treturn a2 / (3.14159265 * d * d) * max(dot(n, l), 0.0);\n}"),
}
HELPER_DEPS = {"lin01": ["safe_div"]}

MATH = {  # Blender Math node -> GLSL; a, b, c are the three inputs. Blender's "safe" variants are kept.
    "ADD": "{a} + {b}", "SUBTRACT": "{a} - {b}", "MULTIPLY": "{a} * {b}", "DIVIDE": "safe_div({a}, {b})",
    "MULTIPLY_ADD": "{a} * {b} + {c}", "POWER": "safe_pow({a}, {b})", "LOGARITHM": "safe_div(log(max({a}, 1e-30)), log(max({b}, 1e-30)))",
    "SQRT": "sqrt(max({a}, 0.0))", "INVERSE_SQRT": "inversesqrt(max({a}, 1e-30))", "ABSOLUTE": "abs({a})",
    "EXPONENT": "exp({a})", "MINIMUM": "min({a}, {b})", "MAXIMUM": "max({a}, {b})",
    "LESS_THAN": "1.0 - step({b}, {a})", "GREATER_THAN": "1.0 - step({a}, {b})", "SIGN": "sign({a})",
    "COMPARE": "step(abs({a} - {b}), max({c}, 1e-5))", "ROUND": "floor({a} + 0.5)", "FLOOR": "floor({a})",
    "CEIL": "ceil({a})", "TRUNC": "trunc({a})", "FRACT": "{a} - floor({a})",
    "MODULO": "{a} - {b} * trunc(safe_div({a}, {b}))", "FLOORED_MODULO": "{a} - {b} * floor(safe_div({a}, {b}))",
    "SINE": "sin({a})", "COSINE": "cos({a})", "TANGENT": "tan({a})", "ARCSINE": "asin(clamp({a}, -1.0, 1.0))",
    "ARCCOSINE": "acos(clamp({a}, -1.0, 1.0))", "ARCTANGENT": "atan({a})", "ARCTAN2": "atan({a}, {b})",
    "RADIANS": "{a} * 0.0174532925", "DEGREES": "{a} * 57.2957795",
}
VMATH = {  # output name -> (GLSL, type)
    "ADD": ("{a} + {b}", "VECTOR"), "SUBTRACT": ("{a} - {b}", "VECTOR"), "MULTIPLY": ("{a} * {b}", "VECTOR"),
    "DIVIDE": ("vec3(safe_div({a}.x, {b}.x), safe_div({a}.y, {b}.y), safe_div({a}.z, {b}.z))", "VECTOR"),
    "SCALE": ("{a} * {s}", "VECTOR"), "CROSS_PRODUCT": ("cross({a}, {b})", "VECTOR"),
    "NORMALIZE": ("normalize({a})", "VECTOR"), "ABSOLUTE": ("abs({a})", "VECTOR"),
    "MINIMUM": ("min({a}, {b})", "VECTOR"), "MAXIMUM": ("max({a}, {b})", "VECTOR"),
    "DOT_PRODUCT": ("dot({a}, {b})", "VALUE"), "LENGTH": ("length({a})", "VALUE"), "DISTANCE": ("distance({a}, {b})", "VALUE"),
}
BLEND = {  # Mix node blend type -> GLSL over a, b and factor f (Blender's ramp_blend formulas)
    "MIX": "mix({a}, {b}, {f})", "ADD": "{a} + {b} * {f}", "MULTIPLY": "mix({a}, {a} * {b}, {f})",
    "SUBTRACT": "{a} - {b} * {f}", "DIFFERENCE": "mix({a}, abs({a} - {b}), {f})", "DARKEN": "mix({a}, min({a}, {b}), {f})",
    "LIGHTEN": "mix({a}, max({a}, {b}), {f})", "SCREEN": "vec3(1.0) - (vec3(1.0 - {f}) + {f} * (vec3(1.0) - {b})) * (vec3(1.0) - {a})",
}
SUPPORTED_SHADER_NODES = {"EMISSION", "ADD_SHADER", "MIX_SHADER", "BSDF_TRANSPARENT", "LIGHT_ACCUMULATION"}
GLSL_TYPE = {"VALUE": "float", "INT": "float", "BOOLEAN": "float", "VECTOR": "vec3", "RGBA": "vec3"}


class Unsupported(Exception):
    pass


def fmt(x) -> str:
    if isinstance(x, (list, tuple)):
        v = [fmt(c) for c in list(x)[:3]] + ["0.0"] * (3 - min(3, len(x)))
        return f"vec3({', '.join(v)})"
    s = repr(float(x))
    return s if ("." in s or "e" in s or "inf" in s or "nan" in s) else s + ".0"


def convert(code: str, src: str, dst: str) -> str:
    """Blender's implicit socket conversions: colour -> float is luminance, vector -> float the component average."""
    s, d = GLSL_TYPE.get(src, "float"), GLSL_TYPE.get(dst, "float")
    if s == d:
        return code
    if s == "float":
        return f"vec3({code})"
    return f"dot({code}, {LUMA})" if src == "RGBA" else f"dot({code}, vec3(1.0 / 3.0))"


def safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", name).strip("_") or "m"


class Graph:
    """A material's node tree with groups inlined, reroutes and muted nodes resolved."""

    def __init__(self, mat: dict, groups: dict):
        self.nodes = {}
        self._add(mat["nodes"], groups, "", 0)

    def _add(self, nodes, groups, prefix, depth):
        if depth > 16:
            raise Unsupported("node groups nested deeper than 16")
        for name, n in nodes.items():
            n = dict(n, name=prefix + name, prefix=prefix)
            self.nodes[prefix + name] = n
            if n["type"] == "GROUP":
                if n.get("tree") not in groups:
                    raise Unsupported(f"group {n.get('tree')!r} missing from the IR")
                self._add(groups[n["tree"]]["nodes"], groups, prefix + name + "/", depth + 1)

    def node(self, prefix, name):
        return self.nodes[prefix + name]

    def source(self, node: dict, key: str):
        """Follow an input to its producer: ("link", node, output_id, socket types crossed) or ("const", value, type)."""
        sock = find_socket(node["inputs"], key)
        if sock is None:
            raise Unsupported(f"{node['name']}: no input {key!r}")
        hops = [sock["type"]]
        for _ in range(256):
            link = sock.get("link")
            if not link:
                return ("const", sock.get("default", 0.0), sock["type"], hops)
            src = self.node(node["prefix"], link[0])
            out = link[1]
            t = src["type"]
            if t == "REROUTE":
                node, sock = src, next(iter(src["inputs"].values()))
            elif src.get("mute"):
                inner = {o: i for i, o in src.get("internal_links") or []}.get(out)
                if inner is None:
                    return ("const", 0.0, src["outputs"][out]["type"], hops)
                node, sock = src, src["inputs"][inner]
            elif t == "GROUP":
                gout = next((n for k, n in self.nodes.items() if k.startswith(src["name"] + "/") and n["type"] == "GROUP_OUTPUT"
                             and n["prefix"] == src["name"] + "/" and n.get("active", True)), None)
                if gout is None or out not in gout["inputs"]:
                    return ("const", 0.0, src["outputs"][out]["type"], hops)
                node, sock = gout, gout["inputs"][out]
            elif t == "GROUP_INPUT":
                outer = self.nodes[src["prefix"].rstrip("/")]
                if out not in outer["inputs"]:
                    return ("const", 0.0, src["outputs"][out]["type"], hops)
                node, sock = outer, outer["inputs"][out]
            else:
                return ("link", src, out, hops)
            hops.append(sock["type"])
        raise Unsupported(f"{node['name']}: link chain does not end")


def find_socket(socks: dict, key: str):
    if key in socks:
        return socks[key]
    return next((s for s in socks.values() if s.get("name") == key), None)


class Compiler:
    def __init__(self, name: str, mat: dict, groups: dict, images: dict):
        self.name, self.mat, self.images = name, mat, images
        self.g = Graph(mat, groups)
        self.lines = {"fragment": [], "light": []}
        self.memo, self.light_dep, self.varyings, self.uniforms = {}, {}, {}, {}
        self.helpers, self.warnings, self.unsupported = set(), [], []
        self.n = 0

    # ---- values ----
    def emit(self, stage, typ, code):
        self.n += 1
        var = f"v{self.n}"
        self.lines[stage].append(f"{GLSL_TYPE[typ]} {var} = {code};")
        return var

    def helper(self, name):
        for dep in HELPER_DEPS.get(name, []):
            self.helper(dep)
        self.helpers.add(name)
        return name

    def is_light(self, node) -> bool:
        key = node["name"]
        if key not in self.light_dep:
            self.light_dep[key] = False  # cycle guard
            dep = node["type"] in LIGHT_SOURCES
            for k in node["inputs"]:
                src = self.g.source(node, k)
                if src[0] == "link" and self.is_light(src[1]):
                    dep = True
            self.light_dep[key] = dep
        return self.light_dep[key]

    def input(self, node, key, stage, want=None):
        """An input's value as GLSL in `stage`, converted to the input's own socket type (or `want`)."""
        sock = find_socket(node["inputs"], key)
        src = self.g.source(node, key)
        if src[0] == "const":
            code, typ = fmt(src[1]), src[2]
        else:
            code, typ = self.value(src[1], src[2], stage)
        for hop in reversed(src[3][1:]):  # group sockets crossed on the way, outermost last
            code, typ = convert(code, typ, hop), hop
        dst = want or sock["type"]
        return convert(code, typ, dst)

    def linked(self, node, key):
        sock = find_socket(node["inputs"], key)
        return sock is not None and bool(sock.get("link"))

    def value(self, node, out, stage):
        key = (node["name"], out, stage)
        if key in self.memo:
            return self.memo[key]
        light = self.is_light(node)
        otype = node["outputs"][out]["type"]
        if stage == "light" and not light:  # computed once in fragment(), carried to light() by a varying
            code, typ = self.value(node, out, "fragment")
            var = f"vy_{len(self.varyings)}"
            self.varyings[var] = (GLSL_TYPE[typ], code)
            res = (var, typ)
        elif stage == "fragment" and node["type"] in LIGHT_SOURCES:  # ordinary nodes downstream still compute
            res = (self.outside_loop(node, out), otype)
        else:
            res = (self.emit(stage, otype, self.node_code(node, node["outputs"][out]["name"], stage)), otype)
        self.memo[key] = res
        return res

    def outside_loop(self, node, out):
        """Blender evaluates per-light nodes outside the light path with defaults (measured: Factor 1, Power 0)."""
        name = node["outputs"][out]["name"]
        defaults = {"Factor": "1.0", "Mask": "1.0", "Power": "0.0", "Color": "vec3(1.0)" if node["type"] == "SHADOW_RAYCAST" else None}
        if defaults.get(name) is None:
            raise Unsupported(f"{node['name']}.{name} used outside Light Accumulation (no Godot equivalent)")
        self.warnings.append(f"{node['name']}.{name} is used outside Light Accumulation; Blender returns its default there")
        return defaults[name]

    # ---- nodes ----
    def node_code(self, n, out, stage):
        t, p = n["type"], n.get("props", {})
        I = lambda k, want=None: self.input(n, k, stage, want)  # noqa: E731
        if t in ("VALUE", "RGB"):
            return fmt(next(iter(n["outputs"].values())).get("default", 0.0))
        if t == "MATH":
            op = p.get("operation", "ADD")
            if op not in MATH:
                raise Unsupported(f"{n['name']}: Math {op}")
            ins = [k for k in n["inputs"]]
            a, b, c = (I(ins[i]) if i < len(ins) else "0.0" for i in range(3))
            for h in ("safe_div", "safe_pow"):
                if h in MATH[op]:
                    self.helper(h)
            code = MATH[op].format(a=a, b=b, c=c)
            return f"clamp({code}, 0.0, 1.0)" if p.get("use_clamp") else code
        if t == "VECT_MATH":
            op = p.get("operation", "ADD")
            if op not in VMATH:
                raise Unsupported(f"{n['name']}: Vector Math {op}")
            ins = [k for k in n["inputs"]]
            code, rtype = VMATH[op]
            if "safe_div" in code:
                self.helper("safe_div")
            vecs = [k for k in ins if n["inputs"][k]["type"] == "VECTOR"]
            a = I(vecs[0]) if vecs else "vec3(0.0)"
            b = I(vecs[1]) if len(vecs) > 1 else "vec3(0.0)"
            s = I("Scale", "VALUE") if find_socket(n["inputs"], "Scale") else "1.0"
            expr = code.format(a=a, b=b, s=s)
            if rtype == "VALUE" and out != "Value":
                return f"vec3({expr})"
            if rtype == "VECTOR" and out == "Value":
                return "0.0"
            return expr
        if t == "MAP_RANGE":
            if p.get("data_type", "FLOAT") != "FLOAT":
                raise Unsupported(f"{n['name']}: vector Map Range")
            v, a, b, c, d = (I(k) for k in ("Value", "From Min", "From Max", "To Min", "To Max"))
            mode = p.get("interpolation_type", "LINEAR")
            self.helper("safe_div")
            if mode in ("SMOOTHSTEP", "SMOOTHERSTEP"):
                f = f"lin01({v}, {a}, {b})"
                self.helper("lin01")
                f = self.emit(stage, "VALUE", f)
                f = (f"{f} * {f} * (3.0 - 2.0 * {f})" if mode == "SMOOTHSTEP"
                     else f"{f} * {f} * {f} * ({f} * ({f} * 6.0 - 15.0) + 10.0)")
            elif mode in ("LINEAR", "STEPPED"):
                f = f"safe_div({v} - {a}, {b} - {a})"
                if mode == "STEPPED":
                    steps = I("Steps")
                    f = f"safe_div(floor({f} * ({steps} + 1.0)), {steps})"
            else:
                raise Unsupported(f"{n['name']}: Map Range {mode}")
            res = f"{c} + ({f}) * ({d} - {c})"
            if p.get("clamp", True) and mode in ("LINEAR", "STEPPED"):
                res = f"clamp({res}, min({c}, {d}), max({c}, {d}))"
            return res
        if t in ("MIX", "MIX_RGB"):
            dtype = p.get("data_type", "RGBA") if t == "MIX" else "RGBA"
            blend = p.get("blend_type", "MIX")
            fkey = "Factor" if t == "MIX" else "Fac"
            akey, bkey = ("A", "B") if t == "MIX" else ("Color1", "Color2")
            if dtype == "FLOAT":
                f, a, b = I(fkey, "VALUE"), I(akey, "VALUE"), I(bkey, "VALUE")
                if p.get("clamp_factor", True):
                    f = f"clamp({f}, 0.0, 1.0)"
                return f"mix({a}, {b}, {f})"
            if dtype == "VECTOR" and p.get("factor_mode", "UNIFORM") != "UNIFORM":
                raise Unsupported(f"{n['name']}: non-uniform vector Mix")
            if blend not in BLEND:
                raise Unsupported(f"{n['name']}: Mix blend {blend}")
            want = "VECTOR" if dtype == "VECTOR" else "RGBA"
            f, a, b = I(fkey, "VALUE"), I(akey, want), I(bkey, want)
            if p.get("clamp_factor", True) or t == "MIX_RGB":
                f = f"clamp({f}, 0.0, 1.0)"
            f = self.emit(stage, "VALUE", f)
            res = BLEND[blend if dtype == "RGBA" else "MIX"].format(a=a, b=b, f=f)
            if p.get("clamp_result") or p.get("use_clamp"):
                res = f"clamp({res}, vec3(0.0), vec3(1.0))"
            return res
        if t == "RGBTOBW":
            return f"dot({I('Color', 'RGBA')}, {LUMA})"
        if t in ("SEPXYZ", "SEPARATE_COLOR", "SEPRGB"):
            if t == "SEPARATE_COLOR" and p.get("mode", "RGB") != "RGB":
                raise Unsupported(f"{n['name']}: Separate Color {p.get('mode')}")
            v = I(next(iter(n["inputs"])))
            comp = {"X": "x", "Y": "y", "Z": "z", "Red": "x", "Green": "y", "Blue": "z", "R": "x", "G": "y", "B": "z"}[out]
            return f"{v}.{comp}"
        if t in ("COMBXYZ", "COMBINE_COLOR", "COMBRGB"):
            if t == "COMBINE_COLOR" and p.get("mode", "RGB") != "RGB":
                raise Unsupported(f"{n['name']}: Combine Color {p.get('mode')}")
            ks = list(n["inputs"])[:3]
            return f"vec3({', '.join(I(k, 'VALUE') for k in ks)})"
        if t == "CLAMP":
            v, lo, hi = I("Value"), I("Min"), I("Max")
            if p.get("clamp_type", "MINMAX") == "RANGE":
                return f"clamp({v}, min({lo}, {hi}), max({lo}, {hi}))"
            return f"min(max({v}, {lo}), {hi})"
        if t == "INVERT":
            return f"mix({I('Color', 'RGBA')}, vec3(1.0) - {I('Color', 'RGBA')}, {I('Fac', 'VALUE')})"
        if t == "VALTORGB":
            return self.color_ramp(n, out, I("Fac", "VALUE"), stage)
        if t == "LAYER_WEIGHT":
            nrm = I("Normal") if self.linked(n, "Normal") else self.normal(stage)
            blend = I("Blend")
            nv = self.emit(stage, "VALUE", f"dot(normalize({nrm}), {self.view(stage)})")
            if out == "Fresnel":
                self.helper("fresnel_cos")
                eta = self.emit(stage, "VALUE", f"max(1.0 - {blend}, 0.00001)")
                return f"fresnel_cos({nv}, mix({eta}, 1.0 / {eta}, {self.front(stage)}))"
            bl = self.emit(stage, "VALUE", f"clamp({blend}, 0.0, 0.99999)")
            expo = f"mix(0.5 / (1.0 - {bl}), 2.0 * {bl}, 1.0 - step(0.5, {bl}))"
            return f"1.0 - pow(abs({nv}), {expo})"
        if t == "FRESNEL":
            nrm = I("Normal") if self.linked(n, "Normal") else self.normal(stage)
            self.helper("fresnel_cos")
            ior = I("IOR")
            return f"fresnel_cos(dot(normalize({nrm}), {self.view(stage)}), mix(1.0 / max({ior}, 1e-5), max({ior}, 1e-5), {self.front(stage)}))"
        if t == "NEW_GEOMETRY":
            if out in ("Normal", "True Normal"):
                return self.normal(stage)
            if out == "Incoming":
                return self.view(stage)
            if out == "Backfacing":
                return f"1.0 - {self.front(stage)}"
            if out == "Position" and stage == "fragment":
                self.helper("b_world")
                return "b_world((INV_VIEW_MATRIX * vec4(VERTEX, 1.0)).xyz)"
            raise Unsupported(f"{n['name']}: Geometry {out}")
        if t in ("TEX_COORD", "UVMAP"):
            if (t == "TEX_COORD" and out != "UV") or (t == "UVMAP" and p.get("uv_map") not in (None, "", p.get("render_uv"))):
                raise Unsupported(f"{n['name']}: texture coordinate {out if t == 'TEX_COORD' else p.get('uv_map')}")
            return "vec3(UV.x, 1.0 - UV.y, 0.0)"  # Blender UVs have V up; glTF and Godot flip V
        if t == "TEX_IMAGE":
            return self.texture(n, out, stage)
        if t == "VECT_TRANSFORM":
            return self.vector_transform(n, I("Vector"), stage)
        if t == "LIGHT_EVALUATION":
            nrm = I("Normal") if self.linked(n, "Normal") else self.normal(stage)
            lw = self.light_dir()
            if out == "Factor":
                if p.get("mode", "DIFFUSE") == "GLOSSY":
                    self.helper("ggx_factor")
                    rough = I("Roughness") if find_socket(n["inputs"], "Roughness") else "0.5"
                    return f"ggx_factor(normalize({nrm}), {lw}, {self.view(stage)}, clamp({rough}, 0.0, 1.0))"
                if p.get("mode", "DIFFUSE") != "DIFFUSE":
                    raise Unsupported(f"{n['name']}: Light Evaluation mode {p.get('mode')}")
                return f"clamp(dot(normalize({nrm}), {lw}), 0.0, 1.0)"
            if out == "Mask":
                return "1.0"
            if out == "Direction":
                return lw
            if out == "Distance":
                self.warnings.append(f"{n['name']}.Distance read as 1.0 (exact for suns; Godot light() has no light position)")
                return "1.0"
            raise Unsupported(f"{n['name']}: Light Evaluation {out}")
        if t == "LIGHT_INFO":
            if out in ("Color", "Power"):
                return f"{self.helper('light_rgb' if out == 'Color' else 'light_power')}(LIGHT_COLOR / PI)"
            raise Unsupported(f"{n['name']}: Light Info {out} (Godot light() has no light position)")
        if t == "SHADOW_RAYCAST":
            if out == "Color":
                return "vec3(ATTENUATION)"
            raise Unsupported(f"{n['name']}: Shadow Raycast {out}")
        raise Unsupported(f"{n['name']}: node {t}")

    def normal(self, stage):
        self.helper("b_world")
        return "b_world(normalize(mat3(INV_VIEW_MATRIX) * NORMAL))"

    def view(self, stage):
        self.helper("b_world")
        return "b_world(normalize(mat3(INV_VIEW_MATRIX) * VIEW))"

    def front(self, stage):
        if stage == "fragment":
            return "(FRONT_FACING ? 1.0 : 0.0)"
        raise Unsupported("backfacing test inside the light loop")

    def light_dir(self):
        self.helper("b_world")
        return "b_world(normalize(mat3(INV_VIEW_MATRIX) * LIGHT))"

    def vector_transform(self, n, v, stage):
        p = n.get("props", {})
        src, dst, kind = p.get("convert_from", "WORLD"), p.get("convert_to", "OBJECT"), p.get("vector_type", "VECTOR")
        self.helper("b_world")
        self.helper("g_world")
        m3 = "mat3(MODEL_MATRIX)"
        if (src, dst) == ("WORLD", "OBJECT"):
            if kind == "POINT":
                return f"b_world((inverse(MODEL_MATRIX) * vec4(g_world({v}), 1.0)).xyz)"
            mat = f"inverse({m3})" if kind == "VECTOR" else f"transpose({m3})"
        elif (src, dst) == ("OBJECT", "WORLD"):
            if kind == "POINT":
                return f"b_world((MODEL_MATRIX * vec4(g_world({v}), 1.0)).xyz)"
            mat = m3 if kind == "VECTOR" else f"transpose(inverse({m3}))"
        elif src == dst:
            return v
        else:
            raise Unsupported(f"{n['name']}: Vector Transform {src} -> {dst}")
        res = f"b_world({mat} * g_world({v}))"
        return f"normalize({res})" if kind == "NORMAL" else res

    def texture(self, n, out, stage):
        img = n.get("props", {}).get("image")
        if not img or img not in self.images:
            return "vec3(1.0, 0.0, 1.0)" if out == "Color" else "1.0"  # Blender's missing-texture magenta
        info = self.images[img]
        uni = self.uniforms.setdefault(img, f"tex_{safe_name(img)}_{len(self.uniforms)}")
        uv = self.input(n, "Vector", stage, "VECTOR") if self.linked(n, "Vector") else "vec3(UV.x, 1.0 - UV.y, 0.0)"
        key = ("tex", img, uv, stage)
        if key not in self.memo:
            self.memo[key] = self.emit_vec4(stage, f"texture({uni}, vec2(({uv}).x, 1.0 - ({uv}).y))")
        s = self.memo[key]
        if out == "Alpha":
            return f"{s}.a"
        return f"{s}.rgb"

    def emit_vec4(self, stage, code):
        self.n += 1
        var = f"v{self.n}"
        self.lines[stage].append(f"vec4 {var} = {code};")
        return var

    def color_ramp(self, n, out, f, stage):
        ramp = n.get("props", {}).get("ramp") or {}
        els = sorted(ramp.get("elements", []), key=lambda e: e["position"])
        mode = ramp.get("interpolation", "LINEAR")
        if not els or mode not in ("LINEAR", "CONSTANT"):
            raise Unsupported(f"{n['name']}: Color Ramp {mode}")
        f = self.emit(stage, "VALUE", f)
        idx = 3 if out == "Alpha" else None
        val = (lambda e: fmt(e["color"][3])) if idx else (lambda e: fmt(e["color"]))
        typ = "VALUE" if idx else "RGBA"
        acc = val(els[0])
        for prev, e in zip(els, els[1:]):
            if mode == "CONSTANT":
                t = f"step({fmt(e['position'])}, {f})"
            else:
                self.helper("lin01")
                t = f"lin01({f}, {fmt(prev['position'])}, {fmt(e['position'])})"
            acc = self.emit(stage, typ, f"mix({acc}, {val(e)}, {t})")
        return acc

    # ---- closures ----
    def closures(self):
        out = self.g.nodes.get(self.mat["output"])
        if out is None:
            raise Unsupported("no active Material Output")
        terms = {"emission": [], "diffuse": [], "specular": [], "transparent": [], "opaque": []}
        src = self.g.source(out, "Surface")
        if src[0] == "link":
            self.closure(src[1], None, terms)
        return terms

    def closure(self, n, w, terms):
        t = n["type"]
        mul = (lambda c: c) if w is None else (lambda c: f"({c}) * {w}")  # noqa: E731
        if t not in SUPPORTED_SHADER_NODES:
            raise Unsupported(f"{n['name']}: shader node {t}")
        if t == "EMISSION":
            terms["emission"].append(mul(f"{self.input(n, 'Color', 'fragment', 'RGBA')} * {self.input(n, 'Strength', 'fragment')}"))
            terms["opaque"].append(w or "1.0")
        elif t == "BSDF_TRANSPARENT":
            terms["transparent"].append(mul(f"dot({self.input(n, 'Color', 'fragment', 'RGBA')}, vec3(1.0 / 3.0))"))
        elif t in ("ADD_SHADER", "MIX_SHADER"):
            shaders = [k for k, s in n["inputs"].items() if s["type"] == "SHADER"]
            if t == "MIX_SHADER":
                fac = self.emit("fragment", "VALUE", f"clamp({self.input(n, next(iter(n['inputs'])), 'fragment', 'VALUE')}, 0.0, 1.0)")
                ws = [f"(1.0 - {fac})" if w is None else f"(1.0 - {fac}) * {w}", fac if w is None else f"{fac} * {w}"]
            else:
                ws = [w, w]
            for k, wk in zip(shaders, ws):
                src = self.g.source(n, k)
                if src[0] == "link":
                    if wk is not None and t == "MIX_SHADER":
                        wk = self.emit("fragment", "VALUE", wk)
                    self.closure(src[1], wk, terms)
        elif t == "LIGHT_ACCUMULATION":
            wl = None
            if w is not None:
                wl = f"vy_{len(self.varyings)}"
                self.varyings[wl] = ("float", w)
            lmul = (lambda c: c) if wl is None else (lambda c: f"({c}) * {wl}")  # noqa: E731
            for kind, light, color in (("diffuse", "Diffuse Light", "Diffuse Color"), ("specular", "Glossy Light", "Glossy Color")):
                sock = find_socket(n["inputs"], light)
                if sock is None or (not self.linked(n, light) and not any(sock.get("default", [0.0])[:3])):
                    continue  # an unlinked constant still adds itself once per light; only black adds nothing
                terms[kind].append(lmul(f"{self.input(n, light, 'light', 'RGBA')} * {self.input(n, color, 'light', 'RGBA')}"))
            if self.linked(n, "Transmission Light"):
                self.unsupported.append(f"{n['name']}: Transmission Light")
            terms["opaque"].append(w or "1.0")

    # ---- shader text ----
    def compile(self) -> dict:
        try:
            terms = self.closures()
        except Unsupported as e:
            self.unsupported.append(str(e))
            return {"status": "unsupported", "unsupported": self.unsupported, "warnings": self.warnings}
        lit = bool(terms["diffuse"] or terms["specular"])
        modes = ["cull_back" if self.mat.get("backface_culling") else "cull_disabled"]
        modes += ["ambient_light_disabled"] if lit else ["unshaded"]
        if terms["transparent"] and self.mat.get("blend") == "BLENDED":
            modes.append("depth_prepass_alpha")
        emission = " + ".join(terms["emission"]) or "vec3(0.0)"
        frag = list(self.lines["fragment"])
        for var, (typ, code) in self.varyings.items():
            frag.append(f"{var} = {code};")
        frag += ["ALBEDO = vec3(1.0);", f"EMISSION = {emission};"] if lit else [f"ALBEDO = {emission};"]
        if terms["transparent"]:
            frag.append(f"ALPHA = clamp(1.0 - ({' + '.join(terms['transparent'])}), 0.0, 1.0);")
            if self.mat.get("blend") != "BLENDED":
                frag.append("ALPHA_SCISSOR_THRESHOLD = 0.5;")  # Blender's dithered surfaces read as a hard cut-out
        out = [f"// Compiled by scripts/toon_compile.py from Blender material {self.name!r}. Do not edit; recompile.",
               "shader_type spatial;", f"render_mode {', '.join(modes)};", ""]
        for img, uni in self.uniforms.items():
            info = self.images[img]
            hints = ["source_color"] if info.get("colorspace", "sRGB") not in ("Non-Color", "Linear Rec.709", "Raw") else []
            hints.append("filter_nearest_mipmap" if info.get("interpolation") == "Closest" else "filter_linear_mipmap")
            hints.append("repeat_enable" if info.get("extension", "REPEAT") == "REPEAT" else "repeat_disable")
            out.append(f"uniform sampler2D {uni} : {', '.join(hints)};")
        out += [f"varying {typ} {var};" for var, (typ, _) in self.varyings.items()]
        out += [""] + [HELPERS[h] + "\n" for h in HELPERS if h in self.helpers]
        out += ["void fragment() {"] + ["\t" + s for s in frag] + ["}"]
        if lit:
            body = list(self.lines["light"])
            if terms["diffuse"]:
                body.append(f"DIFFUSE_LIGHT += {' + '.join(terms['diffuse'])};")
            if terms["specular"]:
                body.append(f"SPECULAR_LIGHT += {' + '.join(terms['specular'])};")
            out += ["", "void light() {"] + ["\t" + s for s in body] + ["}"]
        status = "partial" if self.unsupported else "ok"
        return {"status": status, "shader": "\n".join(out) + "\n", "uniforms": {u: i for i, u in self.uniforms.items()},
                "lit": lit, "varyings": len(self.varyings), "warnings": self.warnings, "unsupported": self.unsupported}


# ---- VRM MToon (approximate, pattern-matched) ----
def mtoon(name: str, mat: dict, groups: dict) -> dict:
    """VRMC_materials_mtoon 1.0 parameters read from the graph's recognisable parts. Every value says where it came
    from; anything MToon cannot express (SDF face shadow, glossy steps, per-light colour) is listed under dropped."""
    g = Graph(mat, groups)
    nodes = list(g.nodes.values())
    ext = {"specVersion": "1.0"}
    sources, dropped = {}, []

    def ancestors(n, seen=None):
        seen = set() if seen is None else seen
        for k in n["inputs"]:
            s = g.source(n, k)
            if s[0] == "link" and s[1]["name"] not in seen:
                seen.add(s[1]["name"])
                ancestors(s[1], seen)
        return seen

    def const(n, k):
        s = g.source(n, k)
        return s[1] if s[0] == "const" else None

    for n in nodes:
        if n["type"] != "MAP_RANGE":
            continue
        up = {g.nodes[a]["type"] + ":" + g.nodes[a].get("props", {}).get("mode", "") for a in ancestors(n)}
        lo, hi = const(n, "From Min"), const(n, "From Max")
        if lo is None or hi is None:
            continue
        if "LIGHT_EVALUATION:DIFFUSE" in up and "shadingShiftFactor" not in ext and not any(u.startswith("TEX_IMAGE") for u in up):
            c, w = (lo + hi) / 2, abs(hi - lo)
            ext["shadingShiftFactor"] = round(-c, 4)
            ext["shadingToonyFactor"] = round(min(1.0, max(0.0, 1 - w / 2)), 4)
            sources["shading"] = f"{n['name']}: {n.get('props', {}).get('interpolation_type', 'LINEAR').lower()} step {lo}..{hi} of N.L"
        elif any(u.startswith("LAYER_WEIGHT") for u in up) and "parametricRimLiftFactor" not in ext:
            lift = 1 - hi  # rim = pow(saturate(1 - N.V + lift), power): reaches 1 where facing = hi
            ext["parametricRimLiftFactor"] = round(lift, 4)
            ext["parametricRimFresnelPowerFactor"] = round(math.log(0.05) / math.log(max(1e-4, min(0.9999, lo + lift))), 3)
            ext["rimLightingMixFactor"] = 1.0
            sources["rim"] = f"{n['name']}: facing step {lo}..{hi} (power puts 5 % at the low edge)"
        elif "LIGHT_EVALUATION:GLOSSY" in up:
            dropped.append(f"{n['name']}: glossy step highlight (MToon has no specular; use a matcap)")
    for n in nodes:
        if n["type"] == "EMISSION":
            s = g.source(n, "Color")
            if s[0] == "link" and s[1]["type"] in ("MIX", "MIX_RGB") and s[1].get("props", {}).get("blend_type") == "MULTIPLY":
                m = s[1]
                a, b = g.source(m, "A" if m["type"] == "MIX" else "Color1"), g.source(m, "B" if m["type"] == "MIX" else "Color2")
                tex, col = (a, b) if a[0] == "link" else (b, a)
                if col[0] == "const" and tex[0] == "link" and tex[1]["type"] == "TEX_IMAGE":
                    ext["shadeColorFactor"] = [round(float(c), 4) for c in list(col[1])[:3]]
                    ext["shadeMultiplyTexture"] = {"image": tex[1].get("props", {}).get("image")}
                    sources["shade"] = f"{m['name']}: base texture x constant shade colour"
        if n["type"] == "LIGHT_ACCUMULATION":
            s = g.source(n, "Diffuse Color")
            if s[0] == "link" and s[1]["type"] == "TEX_IMAGE":
                ext["baseColorTexture"] = {"image": s[1].get("props", {}).get("image")}
        if n["type"] == "TEX_IMAGE" and any(g.nodes[a]["type"] == "LIGHT_EVALUATION" for a in ancestors(n)):
            dropped.append(f"{n['name']}: light-direction texture lookup (SDF face shadow); MToon shades by N.L")
        if n["type"] == "SHADOW_RAYCAST":
            sources.setdefault("shadow", f"{n['name']}: cast shadows -> MToon multiplies shading by attenuation")
    if any(n["type"] == "LIGHT_INFO" for n in nodes):
        sources["light"] = "Light Info colour -> MToon lights by light colour; intensity follows the engine light"
    return {"VRMC_materials_mtoon": ext, "sources": sources, "dropped": sorted(set(dropped)),
            "note": "approximate: MToon uses a linear step on N.L + shift; the toon graph's smoothstep is matched by centre and width"}


# ---- scene conversion (Blender Z up -> Godot Y up) ----
def g_vec(v):
    return [v[0], v[2], -v[1]]


def godot_transform(m):
    """A Blender 4x4 world matrix (row-major list) -> Godot Transform3D columns [x, y, z, origin], axes converted."""
    cols = [[m[r][c] for r in range(3)] for c in range(4)]
    return [g_vec(c) for c in cols]


def look_at(target, yaw, pitch, dist):
    """Blender camera matrix orbiting `target` (yaw about Z from -Y, pitch up), looking at it with Z up."""
    a, b = math.radians(yaw), math.radians(pitch)
    eye = [target[0] + math.sin(a) * math.cos(b) * dist, target[1] - math.cos(a) * math.cos(b) * dist, target[2] + math.sin(b) * dist]
    f = [target[i] - eye[i] for i in range(3)]
    fl = math.sqrt(sum(c * c for c in f))
    f = [c / fl for c in f]
    up = [0.0, 0.0, 1.0] if abs(f[2]) < 0.999 else [0.0, 1.0, 0.0]  # straight down or up: no Z-up reference
    r = [f[1] * up[2] - f[2] * up[1], f[2] * up[0] - f[0] * up[2], f[0] * up[1] - f[1] * up[0]]
    rl = math.sqrt(sum(c * c for c in r))
    r = [c / rl for c in r]
    u = [r[1] * f[2] - r[2] * f[1], r[2] * f[0] - r[0] * f[2], r[0] * f[1] - r[1] * f[0]]
    z = [-c for c in f]  # cameras look down their local -Z in both programs
    return [[r[0], u[0], z[0], eye[0]], [r[1], u[1], z[1], eye[1]], [r[2], u[2], z[2], eye[2]], [0, 0, 0, 1]]


def cameras(spec: list) -> list:
    out = []
    for c in spec:
        m = look_at(c["target"], c.get("yaw", 0), c.get("pitch", 0), c["dist"])
        w, h = c["res"]
        cam = {"name": c["name"], "res": [w, h], "matrix": m, "transform": godot_transform(m), "near": c.get("near", .05), "far": c.get("far", 100)}
        if "ortho" in c:
            cam["ortho"] = c["ortho"]
            cam["godot_size"] = c["ortho"] * min(1.0, h / w)  # Blender's scale spans the wider side, Godot's the height
        else:
            cam["fov"] = c["fov"]  # Blender angle across the wider side, degrees
            cam["godot_fov"] = math.degrees(2 * math.atan(math.tan(math.radians(c["fov"]) / 2) * min(1.0, h / w)))
        out.append(cam)
    return out


def lights(ir_lights: list) -> list:
    """Godot light rig under the compiler's convention: the Blender colour, and as energy the value Blender's Light Info
    reports as Power (measured: strength / pi for suns, power / (4 pi^2) for points), so LIGHT_COLOR / PI = colour x Power."""
    out = []
    for L in ir_lights:
        if L["type"] not in ("SUN", "POINT"):
            out.append({"name": L["name"], "skipped": f"{L['type']} light: no measured Light Info Power convention"})
            continue
        out.append({"name": L["name"], "type": "directional" if L["type"] == "SUN" else "omni", "transform": godot_transform(L["matrix"]),
                    "color": L["color"][:3], "energy": L.get("energy", 1.0) / (math.pi if L["type"] == "SUN" else 4 * math.pi ** 2), "shadow": L.get("shadow", True),
                    "angular_distance": math.degrees(L.get("angle", 0.0)), "blender_energy": L.get("energy")})
    return out


def compile_ir(ir: dict, out_dir: Path) -> dict:
    out_dir = Path(out_dir)
    (out_dir / "shaders").mkdir(parents=True, exist_ok=True)
    report, mt, files = {}, {}, set()
    groups, images = ir.get("groups", {}), ir.get("images", {})
    for name, mat in ir["materials"].items():
        try:
            r = Compiler(name, mat, groups, images).compile()
        except Unsupported as e:
            r = {"status": "unsupported", "unsupported": [str(e)], "warnings": []}
        if "shader" in r:
            stem = safe_name(name)
            fn = next(f"{stem}{'' if i == 0 else f'_{i}'}.gdshader" for i in range(len(files) + 1)
                      if f"{stem}{'' if i == 0 else f'_{i}'}.gdshader" not in files)  # names that sanitise alike
            files.add(fn)
            (out_dir / "shaders" / fn).write_text(r.pop("shader"), encoding="utf-8")
            r["file"] = f"shaders/{fn}"
        report[name] = r
        try:
            mt[name] = mtoon(name, mat, groups)
        except Unsupported as e:
            mt[name] = {"error": str(e)}
    summary = {s: sum(1 for r in report.values() if r["status"] == s) for s in ("ok", "partial", "unsupported")}
    doc = {"summary": summary, "materials": report, "images": images, "light_convention": "Godot light_color = Blender colour, light_energy = Blender Light Info Power"}
    (out_dir / "report.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
    (out_dir / "mtoon.json").write_text(json.dumps(mt, indent=1), encoding="utf-8")
    (out_dir / "lights.json").write_text(json.dumps(lights(ir.get("lights", [])), indent=1), encoding="utf-8")
    if ir.get("cameras"):
        (out_dir / "cameras.json").write_text(json.dumps(cameras(ir["cameras"]), indent=1), encoding="utf-8")
    return doc


def parity(ref_dir: Path, cand_dir: Path, out_dir: Path, background) -> dict:
    """Per view: inside the subject (pixels that differ from the background in either image), the mean absolute
    difference (0-255, largest channel) and the share over 8 and over 24 levels; writes a x4 heatmap per view."""
    from PIL import Image, ImageChops
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    bg = tuple(round(255 * (12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055)) for c in background)
    res = {}
    for ref in sorted(Path(ref_dir).glob("*.png")):
        cand = Path(cand_dir) / ref.name
        if not cand.is_file():
            res[ref.stem] = {"missing": str(cand)}
            continue
        with Image.open(ref) as a, Image.open(cand) as b:
            a, b = a.convert("RGB"), b.convert("RGB")
            if a.size != b.size:
                res[ref.stem] = {"size_mismatch": [a.size, b.size]}
                continue
            plate = Image.new("RGB", a.size, bg)
            subj = [max(px) > 6 for px in zip(*(ch.tobytes() for ch in ImageChops.difference(a, plate).split()))]
            subj = [s or max(px) > 6 for s, px in zip(subj, zip(*(ch.tobytes() for ch in ImageChops.difference(b, plate).split())))]
            d = [max(px) for px in zip(*(ch.tobytes() for ch in ImageChops.difference(a, b).split()))]
        inside = [v for v, s in zip(d, subj) if s]
        n = max(1, len(inside))
        res[ref.stem] = {"subject_px": len(inside), "mean_abs": round(sum(inside) / n, 2),
                         "over8": round(sum(v > 8 for v in inside) / n, 4), "over24": round(sum(v > 24 for v in inside) / n, 4)}
        heat = Image.new("L", a.size)
        heat.putdata([min(255, v * 4) for v in d])
        heat.save(out_dir / f"{ref.stem}-diff.png")
    (out_dir / "parity.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    return res


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["parity"] and len(argv) in (4, 5):
        bg = json.loads(argv[4]) if len(argv) == 5 else [0.0, 0.0, 0.0]
        print(json.dumps(parity(Path(argv[1]), Path(argv[2]), Path(argv[3]), bg), indent=1))
        return
    if len(argv) != 2:
        raise SystemExit(__doc__)
    doc = compile_ir(json.loads(Path(argv[0]).read_text(encoding="utf-8")), Path(argv[1]))
    print(json.dumps(doc["summary"]))
    for name, r in doc["materials"].items():
        if r["status"] != "ok":
            print(f"{r['status']}: {name}: {'; '.join(r['unsupported'])}")


if __name__ == "__main__":
    main()
