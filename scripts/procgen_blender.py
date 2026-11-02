"""Runs inside Blender 5.x: build a procgen Geometry Nodes group, evaluate it per LOD, split parts, measure, export.

Invoked by procgen_factory.py as `blender -b --factory-startup -P procgen_blender.py -- request.json`.
Writes measurements.json, asset_LOD{n}.glb, asset.blend (live GN modifier) and optionally contact_sheet.png.
It measures only; the factory evaluates the gates.
"""
import json
import math
from pathlib import Path
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from procgen_factory import SNAP_EPS, uv_degenerate, uv_overlap_texels  # noqa: E402

ROLES = ('wall', 'floor', 'wood', 'wood_dark', 'linen', 'fabric', 'fabric_alt', 'glass', 'paper', 'metal', 'stone',
         'vermilion', 'black', 'foliage', 'soil', 'terracotta', 'accent', 'rug')
# Flat toon-friendly base colours per palette (linear RGB): 0 day, 1 dusk, 2 sakura, 3 autumn.
PALETTES = [
    [(.86, .80, .70), (.42, .26, .15), (.62, .42, .25), (.28, .16, .09), (.92, .92, .9), (.30, .50, .80), (.90, .70, .75), (.60, .80, .92), (.96, .88, .66),
     (.25, .25, .27), (.55, .55, .53), (.80, .12, .05), (.05, .05, .06), (.20, .50, .18), (.18, .11, .06), (.70, .30, .16), (.95, .65, .15), (.45, .62, .78)],
    [(.42, .44, .60), (.22, .16, .20), (.38, .28, .30), (.14, .10, .14), (.70, .72, .82), (.20, .25, .50), (.55, .40, .65), (.40, .55, .80), (.98, .78, .45),
     (.18, .18, .22), (.40, .40, .48), (.70, .15, .20), (.04, .04, .07), (.12, .30, .25), (.10, .07, .07), (.50, .25, .22), (.95, .55, .25), (.30, .30, .55)],
    [(.95, .86, .88), (.60, .42, .38), (.80, .62, .55), (.42, .28, .26), (.98, .95, .96), (.92, .55, .68), (.98, .80, .85), (.75, .88, .95), (.99, .92, .90),
     (.35, .32, .36), (.70, .66, .68), (.90, .30, .38), (.10, .07, .09), (.45, .65, .40), (.22, .14, .12), (.80, .45, .40), (.98, .70, .78), (.85, .60, .72)],
    [(.88, .78, .62), (.48, .28, .14), (.70, .45, .22), (.34, .18, .08), (.95, .90, .82), (.62, .30, .12), (.85, .62, .30), (.70, .80, .82), (.98, .85, .60),
     (.30, .26, .22), (.58, .54, .48), (.85, .28, .06), (.08, .06, .05), (.65, .45, .10), (.20, .12, .06), (.75, .35, .15), (.90, .50, .08), (.70, .40, .20)],
]


class S:
    """A float socket with arithmetic that adds Math nodes, so generators read like plain geometry."""
    __slots__ = ('b', 's')
    def __init__(self, b, s): self.b, self.s = b, s
    def __add__(self, o): return self.b.math('ADD', self, o)
    def __radd__(self, o): return self.b.math('ADD', o, self)
    def __sub__(self, o): return self.b.math('SUBTRACT', self, o)
    def __rsub__(self, o): return self.b.math('SUBTRACT', o, self)
    def __mul__(self, o): return self.b.math('MULTIPLY', self, o)
    def __rmul__(self, o): return self.b.math('MULTIPLY', o, self)
    def __truediv__(self, o): return self.b.math('DIVIDE', self, o)
    def __rtruediv__(self, o): return self.b.math('DIVIDE', o, self)
    def __neg__(self): return self.b.math('MULTIPLY', self, -1.0)


FOLD = {'ADD': lambda a, b: a + b, 'SUBTRACT': lambda a, b: a - b, 'MULTIPLY': lambda a, b: a * b,
        'DIVIDE': lambda a, b: a / b, 'MAXIMUM': max, 'MINIMUM': min, 'CEIL': lambda a, b: math.ceil(a),
        'SINE': lambda a, b: math.sin(a), 'COSINE': lambda a, b: math.cos(a), 'FLOORED_MODULO': lambda a, b: a % b,
        'POWER': lambda a, b: a ** b, 'ARCTAN2': math.atan2, 'TANGENT': lambda a, b: math.tan(a)}


def _enabled(sockets, name=None):
    return [s for s in sockets if s.enabled and (name is None or s.name == name)]


class B:
    """Geometry Nodes builder. Every primitive stores UVMap + part_id and a material before it is placed."""
    def __init__(self, tree, materials, detail):
        self.t, self.m, self.detail = tree, materials, detail

    def set(self, socket, value):
        if isinstance(value, S): self.t.links.new(value.s, socket)
        elif isinstance(value, bpy.types.NodeSocket): self.t.links.new(value, socket)
        else: socket.default_value = value

    def node(self, kind, props=None, **inputs):
        n = self.t.nodes.new(kind)
        for key, value in (props or {}).items(): setattr(n, key, value)
        for key, value in inputs.items(): self.set(_enabled(n.inputs, key.replace('_', ' '))[0], value)
        return n

    def math(self, op, a, b=0.0):
        if not isinstance(a, S) and not isinstance(b, S): return FOLD[op](a, b)
        n = self.t.nodes.new('ShaderNodeMath'); n.operation = op
        self.set(n.inputs[0], a); self.set(n.inputs[1], b)
        return S(self, n.outputs[0])

    def max(self, a, b): return self.math('MAXIMUM', a, b)
    def ceil(self, a): return self.math('CEIL', a)
    def sin(self, a): return self.math('SINE', a)
    def cos(self, a): return self.math('COSINE', a)
    def sqrt(self, a): return self.math('POWER', a, 0.5)

    def compare(self, op, a, b):
        n = self.node('FunctionNodeCompare', {'data_type': 'FLOAT', 'operation': op})
        self.set(_enabled(n.inputs, 'A')[0], a); self.set(_enabled(n.inputs, 'B')[0], b)
        return n.outputs['Result']

    def both(self, a, b):
        n = self.node('FunctionNodeBooleanMath', {'operation': 'AND'}); self.set(n.inputs[0], a); self.set(n.inputs[1], b)
        return n.outputs[0]

    def transform(self, geo, loc=(0, 0, 0), rot_z=0.0):
        t = self.node('GeometryNodeTransform', Geometry=geo, Translation=self.vec(*loc))
        self.set(_enabled(t.inputs, 'Rotation')[0], self.vec(0.0, 0.0, rot_z))     # constant or a socket expression
        return t.outputs[0]

    def polar(self, count, radius, angle0, step, z0=0.0, dz=0.0):
        """Points i = 0..count-1 at angle0 + i*step on a circle, rising dz per point; returns (points, angle field)."""
        i = self.index(); angle = angle0 + i * step
        pos = self.vec(radius * self.cos(angle), radius * self.sin(angle), z0 + i * dz)
        return self.node('GeometryNodeSetPosition', Geometry=self.line(count, (0, 0, 0), (0, 0, 0)), Position=pos).outputs[0], angle

    def taper(self, geo, rm):
        """Scale y by (rm + x) / rm so a radial panel's width tracks the arc: ring panels meet edge to edge."""
        pos = self.node('ShaderNodeSeparateXYZ', Vector=self.node('GeometryNodeInputPosition').outputs[0]).outputs
        x, y, z = (S(self, o) for o in pos)
        return self.node('GeometryNodeSetPosition', Geometry=geo, Position=self.vec(x, y * (rm + x) / rm, z)).outputs[0]

    def instance_at(self, points, geo, rot_z, selection=None):
        """Instance geo on points rotated about z by a field (radial boxes stay radial), optional selection."""
        n = self.node('GeometryNodeInstanceOnPoints', Points=points, Instance=geo)
        self.set(_enabled(n.inputs, 'Rotation')[0], self.vec(0.0, 0.0, rot_z))
        if selection is not None: self.set(_enabled(n.inputs, 'Selection')[0], selection)
        return self.node('GeometryNodeRealizeInstances', Geometry=n.outputs[0]).outputs[0]

    def vec(self, x, y, z):
        if not any(isinstance(v, S) for v in (x, y, z)): return (x, y, z)
        return S(self, self.node('ShaderNodeCombineXYZ', X=x, Y=y, Z=z).outputs[0])

    def store(self, geo, name, data_type, domain, value):
        n = self.node('GeometryNodeStoreNamedAttribute', {'data_type': data_type, 'domain': domain}, Geometry=geo, Name=name)
        self.set(_enabled(n.inputs, 'Value')[0], value)
        return n.outputs[0]

    def place(self, n, part, role, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
        geo = self.store(n.outputs['Mesh'], 'UVMap', 'FLOAT2', 'CORNER', n.outputs['UV Map'])
        geo = self.store(geo, 'part_id', 'INT', 'FACE', part)
        geo = self.node('GeometryNodeSetMaterial', Geometry=geo, Material=self.m[role]).outputs[0]
        t = self.node('GeometryNodeTransform', Geometry=geo, Translation=self.vec(*loc), Scale=self.vec(*scale))
        _enabled(t.inputs, 'Rotation')[0].default_value = rot
        return t.outputs[0]

    def box(self, lo, hi, part, role):
        size = self.vec(*(h - l for l, h in zip(lo, hi)))
        return self.place(self.node('GeometryNodeMeshCube', Size=size), part, role, [(l + h) / 2 for l, h in zip(lo, hi)])

    def cyl(self, r, depth, base, part, role, top=None, segs=None, rot=(0, 0, 0)):
        segs = self.detail if segs is None else segs
        if top is None: n = self.node('GeometryNodeMeshCylinder', Vertices=segs, Radius=r, Depth=depth)
        else: n = self.node('GeometryNodeMeshCone', Vertices=segs, Radius_Bottom=r, Radius_Top=top, Depth=depth)
        # GN Cylinder is centred on its origin; GN Cone already spans 0..depth.
        return self.place(n, part, role, (base[0], base[1], base[2] + (depth / 2 if top is None else 0)), rot)

    def sphere(self, centre, radii, part, role):
        n = self.node('GeometryNodeMeshUVSphere', Segments=self.detail, Rings=self.max(self.detail / 2, 3.0), Radius=1.0)
        return self.place(n, part, role, centre, scale=radii)

    def grid(self, sx, sy, centre, rot, part, role):
        return self.place(self.node('GeometryNodeMeshGrid', Size_X=sx, Size_Y=sy, Vertices_X=2, Vertices_Y=2), part, role, centre, rot)

    def line(self, count, start, offset):
        return self.node('GeometryNodeMeshLine', Count=count, Start_Location=self.vec(*start), Offset=self.vec(*offset)).outputs[0]

    def instance(self, points, geo, scale=None):
        n = self.node('GeometryNodeInstanceOnPoints', Points=points, Instance=geo)
        if scale is not None: self.set(_enabled(n.inputs, 'Scale')[0], scale)
        return self.node('GeometryNodeRealizeInstances', Geometry=n.outputs[0]).outputs[0]

    def random(self, lo, hi, seed, data_type='FLOAT'):
        n = self.node('FunctionNodeRandomValue', {'data_type': data_type}, Seed=seed)
        self.set(_enabled(n.inputs, 'Min')[0], lo); self.set(_enabled(n.inputs, 'Max')[0], hi)
        return S(self, _enabled(n.outputs)[0])

    def index(self): return S(self, self.node('GeometryNodeInputIndex').outputs[0])

    def set_position(self, geo, offset):
        return self.node('GeometryNodeSetPosition', Geometry=geo, Offset=offset).outputs[0]

    def join(self, *geos):
        n = self.node('GeometryNodeJoinGeometry')
        for geo in reversed(geos): self.t.links.new(geo, n.inputs[0])
        return n.outputs[0]

    def switch(self, flag, geo):
        n = self.node('GeometryNodeSwitch', {'input_type': 'GEOMETRY'}, Switch=flag)
        self.t.links.new(geo, _enabled(n.inputs, 'True')[0])
        return n.outputs[0]

    def index_switch(self, index, geos):
        n = self.node('GeometryNodeIndexSwitch', {'data_type': 'GEOMETRY'}, Index=index)
        while len(n.index_switch_items) < len(geos): n.index_switch_items.new()
        for i, geo in enumerate(geos): self.t.links.new(geo, n.inputs[str(i)])
        return n.outputs[0]


def room_kit(b, P):
    W, D, H, T, F = P['width'], P['depth'], P['height'], P['wall_thickness'], 0.06
    # Walls stand on the floor slab: overlapping coplanar faces of two objects give ambiguous depth/ID labels.
    g = [b.box((-W / 2 - T, 0, 0), (W / 2 + T, D + T, F), 1, 'floor'),
         b.box((-W / 2 - T, 0, F), (-W / 2, D + T, H), 3, 'wall'),
         b.box((W / 2, 0, F), (W / 2 + T, D + T, H), 4, 'wall')]
    wx, ww = P['window_offset'], P['window_width']
    x0, x1 = wx - ww / 2, wx + ww / 2
    z0 = F + P['window_sill']; z1 = z0 + P['window_height']
    for lo, hi in (((-W / 2, D, F), (x0, D + T, H)), ((x1, D, F), (W / 2, D + T, H)),
                   ((x0, D, F), (x1, D + T, z0)), ((x0, D, z1), (x1, D + T, H))):
        g.append(b.box(lo, hi, 2, 'wall'))
    ft = 0.05
    for lo, hi in (((x0, D, z0), (x0 + ft, D + T, z1)), ((x1 - ft, D, z0), (x1, D + T, z1)),
                   ((x0 + ft, D, z0), (x1 - ft, D + T, z0 + ft)), ((x0 + ft, D, z1 - ft), (x1 - ft, D + T, z1)),
                   ((wx - ft / 2, D + 0.35 * T, z0 + ft), (wx + ft / 2, D + 0.65 * T, z1 - ft))):
        g.append(b.box(lo, hi, 5, 'wood'))
    g.append(b.grid(ww - 2 * ft, z1 - z0 - 2 * ft, (wx, D + T / 2, (z0 + z1) / 2), (math.pi / 2, 0, 0), 6, 'glass'))
    # Desk against the back wall on the left, lamp on its right corner.
    dx0 = -W / 2 + 0.05; dx1 = dx0 + P['desk_width']; dy1 = D - 0.02; dy0 = dy1 - P['desk_depth']; top = F + 0.74
    g.append(b.box((dx0, dy0, top - 0.04), (dx1, dy1, top), 7, 'wood'))
    for lx in (dx0 + 0.03, dx1 - 0.08):
        for ly in (dy0 + 0.03, dy1 - 0.08):
            g.append(b.box((lx, ly, F), (lx + 0.05, ly + 0.05, top - 0.04), 7, 'wood_dark'))
    lx, ly = dx1 - 0.18, dy1 - 0.18
    g += [b.cyl(0.07, 0.02, (lx, ly, top), 8, 'metal'), b.cyl(0.012, 0.3, (lx, ly, top + 0.02), 8, 'metal'),
          b.cyl(0.11, 0.12, (lx, ly, top + 0.3), 8, 'accent', top=0.05)]
    # Bed along the right wall, head at the back.
    bx1 = W / 2 - 0.02; bx0 = bx1 - P['bed_width']; by1 = D - 0.02; by0 = by1 - P['bed_length']
    g += [b.box((bx0, by0, F), (bx1, by1, F + 0.28), 9, 'wood'),
          b.box((bx0, by1 - 0.06, F + 0.28), (bx1, by1, F + 0.8), 9, 'wood'),
          b.box((bx0 + 0.03, by0 + 0.03, F + 0.28), (bx1 - 0.03, by1 - 0.06, F + 0.46), 10, 'linen'),
          b.box((bx0 + 0.02, by0 + 0.02, F + 0.46), (bx1 - 0.02, by0 + 0.62 * P['bed_length'], F + 0.5), 11, 'fabric'),
          b.sphere(((bx0 + bx1) / 2, by1 - 0.3, F + 0.52), (P['bed_width'] * 0.32, 0.17, 0.06), 12, 'fabric_alt')]
    # Bookshelf on the left wall in front of the desk; seeded book heights.
    g.append(b.transform(bookshelf(b, P['shelf_count'], P['seed'], 13, 14), (-W / 2, dy0 - 0.88, F)))
    g.append(b.cyl(P['rug_radius'], 0.01, (0, D * 0.45, F), 15, 'rug'))
    return b.join(*g)


def bookshelf(b, n, seed, shelf_part, books_part):
    """Room-kit bookshelf in local space: back against x=0, 0.3 deep (+x), 0.8 wide (y 0..0.8), standing on z=0."""
    hh = n * 0.35 + 0.02
    g = [b.box((0, 0, 0), (0.3, 0.02, hh), shelf_part, 'wood'), b.box((0, 0.78, 0), (0.3, 0.8, hh), shelf_part, 'wood'),
         b.instance(b.line(n + 1, (0.15, 0.4, 0), (0, 0, 0.35)), b.box((-0.15, -0.38, 0), (0.15, 0.38, 0.02), shelf_part, 'wood'))]
    row = b.instance(b.line(8, (0, -0.3, 0), (0, 0.085, 0)), b.box((-0.1, -0.018, 0), (0.1, 0.018, 1.0), books_part, 'accent'),
                     scale=b.vec(1.0, 1.0, b.random(0.18, 0.3, seed)))
    g.append(b.instance(b.line(n, (0.15, 0.4, 0.02), (0, 0, 0.35)), row))
    return b.join(*g)


def lighthouse_room(b, P):
    """Round lighthouse map room: ring wall of radial panels with windows, spiral steps on the wall, central map table."""
    R_, T, H, F, n = P['radius'], P['wall_thickness'], P['height'], 0.06, P['panels']
    step = 2 * math.pi / n
    # Flat panels meeting on radial planes are 2 r tan(pi/n) wide at radius r; taper() scales the width with r.
    w = 2 * (R_ + T / 2) * b.math('TANGENT', math.pi / n)
    # The floor is the wall's own outer n-gon (apothem R+T, a face centred on each panel), so no wall overhangs it at any LOD.
    g = [b.transform(b.cyl((R_ + T) / b.cos(math.pi / n), F, (0, 0, 0), 1, 'floor', segs=n), (0, 0, 0), -math.pi / 2 - math.pi / n)]
    pts, angle = b.polar(n, R_ + T / 2, -math.pi / 2, step)         # panel 0 faces the front (-y)
    i = b.index()
    window = b.compare('LESS_THAN', b.math('FLOORED_MODULO', i, P['window_every']), 0.5)
    keep = b.compare('GREATER_THAN', i, P['cutaway'] * 2.5 - 0.5)  # cutaway=1 removes panels 0..2 and n-2..n-1 at the front
    keep = b.both(keep, b.compare('LESS_THAN', i, n - P['cutaway'] * 2.5))
    solid = b.both(keep, b.compare('GREATER_THAN', b.math('FLOORED_MODULO', i, P['window_every']), 0.5))
    z0, z1 = F + P['window_sill'], F + P['window_sill'] + P['window_height']
    panel = lambda lo, hi: b.taper(b.box((-T / 2, -w / 2, lo), (T / 2, w / 2, hi), 2, 'wall'), R_ + T / 2)
    g += [b.instance_at(pts, panel(F, H), angle, solid),
          b.instance_at(pts, b.join(panel(F, z0), panel(z1, H)), angle, b.both(keep, window)),
          b.instance_at(pts, b.box((-0.02, -w / 2 + 0.03, z0), (0.02, w / 2 - 0.03, z1), 9, 'glass'), angle, b.both(keep, window))]
    # Spiral steps cantilevered from the wall on the left, rising toward a hatch.
    rise = (H - F) / (P['stair_steps'] + 1)
    # First step starts past the chart shelf's corner as seen from the centre (0.65 m off-axis at radius R - 0.9).
    start = math.pi / 2 + b.math('ARCTAN2', 0.65, R_ - 0.9) + 0.12
    spts, sangle = b.polar(P['stair_steps'], R_ - 0.4, start, 0.22, F + rise, rise)
    g.append(b.instance_at(spts, b.box((-0.4, -0.2, -0.05), (0.4, 0.2, 0.0), 3, 'wood_dark'), sangle))
    # Central map table with an unrolled chart, a stool, and a rug under them.
    tr = P['table_radius']
    g += [b.cyl(tr, 0.05, (0, 0, F + 0.72), 4, 'wood'), b.cyl(0.08, 0.72, (0, 0, F), 4, 'wood_dark'),
          b.cyl(0.35, 0.03, (0, 0, F), 4, 'wood_dark'),
          b.box((-0.6 * tr, -0.4 * tr, F + 0.77), (0.6 * tr, 0.4 * tr, F + 0.775), 5, 'paper'),
          b.cyl(0.18, 0.04, (tr + 0.35, 0, F + 0.42), 6, 'wood'), b.cyl(0.04, 0.42, (tr + 0.35, 0, F), 6, 'wood_dark'),
          b.cyl(tr + 0.55, 0.01, (0, 0, F), 8, 'rug')]
    # Room-kit bookshelf of charts at the back, turned to face the room, clear of the panel AABBs.
    back = R_ * b.cos(1.5 * step) - 0.05                           # inside every panel's axis-aligned box
    g.append(b.transform(bookshelf(b, P['shelf_count'], P['seed'], 7, 10), (-0.4, back, F), -math.pi / 2))
    return b.join(*g)


def prop(b, P):
    h, w = P['height'], P['width']
    c = 0.07 * h; body = 0.8 * h
    # The body sinks 6% into each cap so the caps grip it instead of touching at the poles.
    lantern = b.join(b.sphere((0, 0, c + body / 2), (w / 2, w / 2, 0.56 * body), 1, 'paper'),
                     b.cyl(0.3 * w, c, (0, 0, 0), 2, 'black'), b.cyl(0.3 * w, c, (0, 0, c + body), 2, 'black'),
                     b.cyl(0.06 * w, 0.06 * h, (0, 0, 2 * c + body), 3, 'metal'))
    e = 0.1 * w
    crate = [b.box((-w / 2 + e / 2, -w / 2 + e / 2, e / 2), (w / 2 - e / 2, w / 2 - e / 2, h - e / 2), 4, 'wood')]
    for z in (0, h - e, (h - e) / 2):
        for y in (-w / 2, w / 2 - e): crate.append(b.box((-w / 2, y, z), (w / 2, y + e, z + e), 5, 'wood_dark'))
        for x in (-w / 2, w / 2 - e): crate.append(b.box((x, -w / 2, z), (x + e, w / 2, z + e), 5, 'wood_dark'))
    for x in (-w / 2, w / 2 - e):
        for y in (-w / 2, w / 2 - e): crate.append(b.box((x, y, 0), (x + e, y + e, h), 5, 'wood_dark'))
    rz, pot_h = 0.17 * h, 0.38 * h
    scatter = b.set_position(b.line(5, (0, 0, 0), (0, 0, 0)),
                             b.random(b.vec(-0.2 * w, -0.2 * w, pot_h + 0.6 * rz), b.vec(0.2 * w, 0.2 * w, h - 1.2 * rz), P['seed'], 'FLOAT_VECTOR'))
    rx = b.random(0.2 * w, 0.27 * w, P['seed'] + 1)
    # The cone stops under the rim and the soil sits on the rim, so no visible faces of two parts coincide.
    plant = b.join(b.cyl(0.3 * w, pot_h - 0.05 * h, (0, 0, 0), 6, 'terracotta', top=0.4 * w),
                   b.cyl(0.43 * w, 0.05 * h, (0, 0, pot_h - 0.05 * h), 6, 'terracotta'),
                   b.cyl(0.37 * w, 0.01 * h, (0, 0, pot_h), 7, 'soil'),
                   b.sphere((0, 0, h - rz), (0.28 * w, 0.28 * w, rz), 8, 'foliage'),
                   b.instance(scatter, b.sphere((0, 0, 0), (1, 1, 1), 8, 'foliage'), scale=b.vec(rx, rx, rz)))
    return b.index_switch(P['kind'], [lantern, b.join(*crate), plant])


def shrine(b, P):
    gw, gh, pr, n, rise, run = (P[k] for k in ('gate_width', 'gate_height', 'pillar_radius', 'step_count', 'step_rise', 'step_run'))
    kasagi = 1.3 * gw + 4 * pr
    pw = b.ceil((b.max(kasagi, gw + 2 * pr) + 1.0) / 0.5 - SNAP_EPS) * 0.5
    y0, ph, pd = n * run, (n + 1) * rise, 3.0
    g = [b.box((-pw / 2, y0, 0), (pw / 2, y0 + pd, ph), 1, 'stone'),
         b.instance(b.line(n, (0, 0, 0), (0, run, 0)), b.box((-pw / 2, 0, 0), (pw / 2, run, rise), 2, 'stone'),
                    scale=b.vec(1.0, 1.0, b.index() + 1))]
    yc = y0 + pd / 2
    for sx in (-1, 1):
        g += [b.cyl(pr, 0.9 * gh, (sx * gw / 2, yc, ph), 3, 'vermilion'), b.cyl(1.35 * pr, 0.12, (sx * gw / 2, yc, ph), 5, 'black')]
    shimaki, nuki = (1.15 * gw + 2 * pr) / 2, (gw + 2 * pr + 0.4) / 2
    g += [b.box((-kasagi / 2, yc - 1.2 * pr, ph + 0.9 * gh), (kasagi / 2, yc + 1.2 * pr, ph + gh), 4, 'black'),
          b.box((-shimaki, yc - pr, ph + 0.84 * gh), (shimaki, yc + pr, ph + 0.9 * gh), 4, 'vermilion'),
          b.box((-nuki, yc - 0.6 * pr, ph + 0.68 * gh), (nuki, yc + 0.6 * pr, ph + 0.74 * gh), 4, 'vermilion'),
          b.box((-0.18, yc - 0.7 * pr, ph + 0.74 * gh), (0.18, yc + 0.7 * pr, ph + 0.84 * gh), 4, 'black')]
    pair = []
    for sx in (-1, 1):
        x, y = sx * (pw / 2 - 0.45), y0 + 0.45
        pair += [b.box((x - 0.25, y - 0.25, ph), (x + 0.25, y + 0.25, ph + 0.12), 6, 'stone'),
                 b.cyl(0.09, 0.5, (x, y, ph + 0.12), 6, 'stone'),
                 b.box((x - 0.2, y - 0.2, ph + 0.62), (x + 0.2, y + 0.2, ph + 0.68), 6, 'stone'),
                 b.box((x - 0.15, y - 0.15, ph + 0.68), (x + 0.15, y + 0.15, ph + 0.93), 6, 'paper'),
                 b.cyl(0.33, 0.15, (x, y, ph + 0.93), 6, 'stone', top=0.02, segs=4, rot=(0, 0, math.pi / 4)),
                 b.sphere((x, y, ph + 1.12), (0.04, 0.04, 0.04), 6, 'stone')]
    g.append(b.switch(P['lanterns'], b.join(*pair)))
    return b.join(*g)


GENERATORS = {'room_kit': room_kit, 'prop': prop, 'shrine': shrine, 'lighthouse_room': lighthouse_room}


def make_materials(palette):
    mats = {}
    for role, colour in zip(ROLES, PALETTES[palette]):
        mat = bpy.data.materials.new(role)
        bsdf = mat.node_tree.nodes.get('Principled BSDF')
        bsdf.inputs['Base Color'].default_value = (*colour, 1)
        bsdf.inputs['Roughness'].default_value = 1.0
        bsdf.inputs['Specular IOR Level'].default_value = 0.0
        mats[role] = mat
    return mats


def build_tree(generator, spec, materials):
    tree = bpy.data.node_groups.new('procgen_' + generator, 'GeometryNodeTree')
    tree.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    for key, rule in spec['params'].items():
        if not rule.get('gn', True): continue
        socket = tree.interface.new_socket(key, in_out='INPUT', socket_type='NodeSocketInt' if rule['type'] == 'int' else 'NodeSocketFloat')
        socket.min_value, socket.max_value, socket.default_value = rule['min'], rule['max'], rule['default']
        socket.description = rule.get('doc', '')
    gi, go = tree.nodes.new('NodeGroupInput'), tree.nodes.new('NodeGroupOutput')
    params = {s.name: s for s in gi.outputs if s.name}
    b = B(tree, materials, None)
    b.detail = S(b, params['detail'])
    tree.links.new(GENERATORS[generator](b, {k: S(b, v) for k, v in params.items()}), go.inputs['Geometry'])
    return tree


def gn_inputs(tree):
    return {i.name: i for i in tree.interface.items_tree if i.item_type == 'SOCKET' and i.in_out == 'INPUT'}


def evaluate(obj, tree, params, detail):
    for name, item in gn_inputs(tree).items():
        # Blender 5.4 moved modifier inputs from ID properties to typed structs.
        getattr(obj.modifiers['procgen'].properties.inputs, item.identifier).value = detail if name == 'detail' else params[name]
    obj.update_tag()
    dg = bpy.context.evaluated_depsgraph_get(); dg.update()
    return bpy.data.meshes.new_from_object(obj.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)


def lightmap(obj):
    me = obj.data
    me.uv_layers['UVMap'].active_render = True
    me.uv_layers.active = me.uv_layers.new(name='UVLightmap')
    with bpy.context.temp_override(active_object=obj, object=obj, selected_objects=[obj], selected_editable_objects=[obj]):
        bpy.ops.uv.lightmap_pack(PREF_CONTEXT='ALL_FACES', PREF_PACK_IN_ONE=False, PREF_NEW_UVLAYER=False, PREF_MARGIN_DIV=0.3)


def split_parts(mesh, spec, root, collection, suffix):
    if 'part_id' not in mesh.attributes or not len(mesh.polygons): raise SystemExit('generator produced no tagged geometry')
    ids = np.empty(len(mesh.polygons), dtype=np.int32)
    mesh.attributes['part_id'].data.foreach_get('value', ids)
    parts, unknown = [], sorted({int(i) for i in ids} - {int(k) for k in spec['parts']})
    for pid in sorted({int(i) for i in ids} - set(unknown)):
        name = spec['parts'][str(pid)]['name'] + suffix
        bm = bmesh.new(); bm.from_mesh(mesh)
        layer = bm.faces.layers.int['part_id']
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f[layer] != pid], context='FACES')
        me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
        for mat in mesh.materials: me.materials.append(mat)
        co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
        lo, hi = co.min(0), co.max(0)
        pivot = Vector(((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]))
        me.transform(Matrix.Translation(-pivot))
        obj = bpy.data.objects.new(name, me); obj.location = pivot; obj.parent = root
        collection.objects.link(obj)
        lightmap(obj)
        parts.append((pid, obj))
    return parts, unknown


def stats(obj):
    me = obj.data
    bm = bmesh.new(); bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    origin = obj.matrix_world.translation
    parent = list(range(len(bm.verts)))
    def find(i):
        while parent[i] != i: parent[i] = parent[parent[i]]; i = parent[i]
        return i
    for e in bm.edges:
        a, c = find(e.verts[0].index), find(e.verts[1].index)
        if a != c: parent[a] = c
    boxes = {}
    for v in bm.verts:
        p = origin + v.co; r = find(v.index)
        lo, hi = boxes.setdefault(r, ([math.inf] * 3, [-math.inf] * 3))
        for k in range(3): lo[k] = min(lo[k], p[k]); hi[k] = max(hi[k], p[k])
    result = {'triangles': sum(len(f.verts) - 2 for f in bm.faces),
              'boundary_edges': sum(1 for e in bm.edges if len(e.link_faces) == 1),
              'nonmanifold_edges': sum(1 for e in bm.edges if len(e.link_faces) not in (1, 2)),
              'inconsistent_edges': sum(1 for e in bm.edges if len(e.link_faces) == 2 and not e.is_contiguous),
              'degenerate_faces': sum(1 for f in bm.faces if f.calc_area() < 1e-10),
              'islands': [lo + hi for lo, hi in boxes.values()]}
    bm.free()
    co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3) + np.array(origin)
    result.update(bbox_min=co.min(0).tolist(), bbox_max=co.max(0).tolist(), origin=list(origin))
    uv0, uv1 = me.uv_layers.get('UVMap'), me.uv_layers.get('UVLightmap')
    def uvs(layer):
        arr = np.empty(len(me.loops) * 2); layer.uv.foreach_get('vector', arr); return arr.reshape(-1, 2)
    result['uv0_present'] = uv0 is not None
    result['uv0_finite'] = bool(uv0 is not None and np.isfinite(uvs(uv0)).all())
    result['uv1_present'] = uv1 is not None
    result['uv1_in_unit'] = bool(uv1 is not None and ((uvs(uv1) >= -1e-6) & (uvs(uv1) <= 1 + 1e-6)).all())
    result['uv1_overlap_texels'] = result['uv1_degenerate'] = -1
    if uv1 is not None:
        me.calc_loop_triangles()
        loops = np.empty(len(me.loop_triangles) * 3, dtype=np.int64); me.loop_triangles.foreach_get('loops', loops)
        tris = uvs(uv1)[loops].reshape(-1, 3, 2)
        result['uv1_overlap_texels'] = uv_overlap_texels(tris, REQUEST['uv_res'])
        result['uv1_degenerate'] = uv_degenerate(tris.tolist())
    return result


def bbox(objs):
    pts = np.concatenate([np.array([tuple(o.matrix_world @ v.co) for v in o.data.vertices]) for o in objs])
    return pts.min(0).tolist(), pts.max(0).tolist()


def collision_boxes(obj, islands, suffix, collection, root):
    """One box per disconnected solid (island), so the gaps between pillars or around a window stay open."""
    origin, verts, faces = np.array(obj.location), [], []
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    for island in islands:
        lo, hi = np.array(island[:3]) - origin, np.array(island[3:]) - origin
        base = len(verts)
        verts += [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
        faces += [tuple(base + i for i in q) for q in quads]
    me = bpy.data.meshes.new(obj.name + suffix); me.from_pydata(verts, [], faces); me.update()
    col = bpy.data.objects.new(obj.name + suffix, me); col.location = obj.location; col.parent = root
    collection.objects.link(col)
    return col


def export_glb(objs, path):
    for o in bpy.context.view_layer.objects: o.select_set(False)
    for o in objs: o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(path), export_format='GLB', use_selection=True, export_yup=True)


def contact_sheet(objs, lo, hi, out):
    import OpenImageIO as oiio
    scene = bpy.context.scene
    keep = set(objs)
    for o in scene.objects:
        if o.type == 'MESH': o.hide_render = o not in keep
    scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = 24
    scene.render.resolution_x = scene.render.resolution_y = 384
    world = bpy.data.worlds.new('sheet'); scene.world = world
    bg = world.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = (0.36, 0.42, 0.52, 1); bg.inputs['Strength'].default_value = 0.9
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sun.data.energy = 3.0
    sun.rotation_euler = (math.radians(50), 0, math.radians(-30)); scene.collection.objects.link(sun)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); scene.collection.objects.link(cam); scene.camera = cam
    centre = Vector([(a + b) / 2 for a, b in zip(lo, hi)]); radius = (Vector(hi) - Vector(lo)).length / 2
    dist = radius / math.tan(cam.data.angle / 2) * 1.05
    tiles = []
    for az, el in ((-40, 25), (40, 25), (0, 8), (0, 70)):
        a, e = math.radians(az), math.radians(el)
        cam.location = centre + dist * Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))
        cam.rotation_euler = (centre - cam.location).to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = str(out / f'view_{len(tiles)}.png')
        bpy.ops.render.render(write_still=True)
        tiles.append(oiio.ImageBuf(scene.render.filepath).get_pixels(oiio.UINT8)[:, :, :3])
    sheet = np.concatenate([np.concatenate(tiles[:2], 1), np.concatenate(tiles[2:], 1)], 0)
    buf = oiio.ImageBuf(oiio.ImageSpec(sheet.shape[1], sheet.shape[0], 3, oiio.UINT8)); buf.set_pixels(oiio.ROI(), sheet)
    buf.write(str(out / 'contact_sheet.png'))
    for i in range(4): (out / f'view_{i}.png').unlink()


def main(request):
    out, spec, params, generator = Path(request['output']), request['spec'], request['params'], request['generator']
    for o in list(bpy.data.objects): bpy.data.objects.remove(o)
    materials = make_materials(params['palette'])
    tree = build_tree(generator, spec, materials)
    gen = bpy.data.objects.new('generator', bpy.data.meshes.new('generator'))
    bpy.context.scene.collection.objects.link(gen)
    gen.modifiers.new('procgen', 'NODES').node_group = tree
    gen.hide_render = True
    measurements = {'blender': {'version': bpy.app.version_string, 'hash': bpy.app.build_hash.decode()},
                    'gn_bounds': {k: [round(i.min_value, 6), round(i.max_value, 6)] for k, i in gn_inputs(tree).items()},
                    'lods': [], 'parts': [], 'collision_objects': [], 'collision_boxes': 0, 'unknown_part_ids': []}
    lod0_objs = []
    for level, detail in enumerate(request['lod_details']):
        suffix = '' if level == 0 else f'_lod{level}'
        collection = bpy.data.collections.new(f'LOD{level}'); bpy.context.scene.collection.children.link(collection)
        root = bpy.data.objects.new(generator + suffix, None); collection.objects.link(root)
        mesh = evaluate(gen, tree, params, detail)
        parts, unknown = split_parts(mesh, spec, root, collection, suffix)
        objs = [obj for _, obj in parts]
        lo, hi = bbox(objs)
        export = list(objs) + [root]
        level_parts = [{'id': pid, 'name': obj.name, **stats(obj)} for pid, obj in parts]
        if level == 0:
            lod0_objs = objs
            measurements['unknown_part_ids'] = unknown
            measurements['parts'] = level_parts
            for (pid, obj), part in zip(parts, level_parts):
                if spec['parts'][str(pid)].get('collision', True):
                    export.append(collision_boxes(obj, part['islands'], request['collision_suffix'], collection, root))
                    measurements['collision_objects'].append(export[-1].name)
                    measurements['collision_boxes'] += len(part['islands'])
        glb = f'asset_LOD{level}.glb'
        export_glb(export, out / glb)
        measurements['lods'].append({'detail': detail, 'glb': glb, 'bbox_min': lo, 'bbox_max': hi, 'parts': level_parts if level else [],
                                     'triangles': sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs)})
    evaluate(gen, tree, params, params['detail'])
    if request['render']: contact_sheet(lod0_objs, measurements['lods'][0]['bbox_min'], measurements['lods'][0]['bbox_max'], out)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / 'asset.blend'), compress=True)
    (out / 'measurements.json').write_text(json.dumps(measurements, indent=1), encoding='utf-8')


REQUEST = json.loads(Path(sys.argv[sys.argv.index('--') + 1]).read_text(encoding='utf-8'))
main(REQUEST)
