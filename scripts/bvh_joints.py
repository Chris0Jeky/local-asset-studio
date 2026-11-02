"""BVH -> per-frame joint world positions for a runtime direction-matching retarget.
  python scripts/bvh_joints.py IN.bvh OUT.json [scale] [--positions=auto|absolute|relative]

Positions come out in metres (scale default 0.01 for centimetre BVH), Y up, the figure turned about Y so that at frame 0
its left side (UpperLeg_L - UpperLeg_R) points to +X and it faces +Z (Godot glTF convention, matching a VRM import).
Rotation channels are applied in the order they are listed (intrinsic), e.g. "Zrotation Xrotation Yrotation" -> Rz Rx Ry."""
import json, math, sys
from pathlib import Path


def mat_mul(a, b): return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def rot(axis, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    if axis == "X": return [[1, 0, 0, 0], [0, c, -s, 0], [0, s, c, 0], [0, 0, 0, 1]]
    if axis == "Y": return [[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1]]
    return [[c, -s, 0, 0], [s, c, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]


def parse(path):
    tok = Path(path).read_text(encoding="utf-8").split(); i = 0; joints = []; stack = []
    while tok[i] != "MOTION":
        t = tok[i]
        if t in ("ROOT", "JOINT"):
            joints.append({"name": tok[i + 1], "parent": stack[-1] if stack else None, "offset": None, "channels": []}); i += 2
        elif t == "End":
            joints.append({"name": None, "parent": stack[-1], "offset": None, "channels": []}); i += 2
        elif t == "{": stack.append(len(joints) - 1); i += 1
        elif t == "}": stack.pop(); i += 1
        elif t == "OFFSET": joints[stack[-1]]["offset"] = [float(x) for x in tok[i + 1:i + 4]]; i += 4
        elif t == "CHANNELS":
            n = int(tok[i + 1]); joints[stack[-1]]["channels"] = tok[i + 2:i + 2 + n]; i += 2 + n
        else: i += 1
    frames = int(tok[i + 2]); dt = float(tok[i + 5]); i += 6
    nch = sum(len(j["channels"]) for j in joints); data = [[float(x) for x in tok[i + f * nch:i + (f + 1) * nch]] for f in range(frames)]
    return joints, data, dt


def absolute_positions(joints, data, mode="auto"):
    """Per joint: True when its position channels carry the whole local translation (Bandai Namco and many exporters),
    False when they are relative to OFFSET (added to it). mode absolute/relative forces it; auto decides on the offset's
    dominant axis using the channel's median over all frames (absolute when it sits nearer the offset than zero) and
    prints each decision, because a clip that crouches or jumps throughout can still fool it. A zero offset makes both
    conventions identical."""
    out = []; k = 0
    for j in joints:
        idx = {ch[0]: k + i for i, ch in enumerate(j["channels"]) if ch.endswith("position")}; k += len(j["channels"])
        off = j["offset"]; a = max(range(3), key=lambda i: abs(off[i])); axis = "XYZ"[a]
        if not idx or abs(off[a]) <= 1e-6: out.append(False); continue
        if mode != "auto": out.append(mode == "absolute"); continue
        vals = sorted(r[idx[axis]] for r in data) if axis in idx else [0.0]; med = vals[len(vals) // 2]
        absolute = abs(med - off[a]) < 0.5 * abs(off[a]); out.append(absolute)
        print(f"positions {j['name']}: {'absolute' if absolute else 'relative'} (median {axis} {med:g} vs offset {off[a]:g}; override with --positions=)")
    return out


def world_positions(joints, row, absolute):
    mats = []; k = 0
    for n, j in enumerate(joints):
        t = list(j["offset"]); r = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
        for ch in j["channels"]:
            v = row[k]; k += 1
            if ch.endswith("position"): t["XYZ".index(ch[0])] = v if absolute[n] else j["offset"]["XYZ".index(ch[0])] + v
            else: r = mat_mul(r, rot(ch[0], v))
        m = mat_mul([[1, 0, 0, t[0]], [0, 1, 0, t[1]], [0, 0, 1, t[2]], [0, 0, 0, 1]], r)
        mats.append(m if j["parent"] is None else mat_mul(mats[j["parent"]], m))
    return {j["name"]: [mats[n][0][3], mats[n][1][3], mats[n][2][3]] for n, j in enumerate(joints) if j["name"]}


def main(src, out, scale=0.01, positions="auto"):
    joints, data, dt = parse(src); absolute = absolute_positions(joints, data, positions)
    frames = [world_positions(joints, r, absolute) for r in data]
    l, r = frames[0]["UpperLeg_L"], frames[0]["UpperLeg_R"]
    yaw = math.atan2(l[2] - r[2], l[0] - r[0])                                  # turn left->right onto +X
    c, s = math.cos(yaw), math.sin(yaw)
    def fix(p): return [round((c * p[0] + s * p[2]) * scale, 5), round(p[1] * scale, 5), round((-s * p[0] + c * p[2]) * scale, 5)]
    frames = [{n: fix(p) for n, p in f.items()} for f in frames]
    a, b = frames[0]["Hips"], frames[-1]["Hips"]; dx, dz = b[0] - a[0], b[2] - a[2]
    if math.hypot(dx, dz) > 0.3:                                              # travelling clip: put its path on +Z, no drift
        t = math.atan2(dx, dz); c2, s2 = math.cos(t), math.sin(t)
        frames = [{n: [round(c2 * p[0] - s2 * p[2], 5), p[1], round(s2 * p[0] + c2 * p[2], 5)] for n, p in f.items()} for f in frames]
    Path(out).write_text(json.dumps({"source": src.replace("\\", "/").split("/")[-1], "fps": round(1 / dt, 3), "frames": frames}), encoding="utf-8")
    xs = [f["Hips"] for f in frames]
    print(f"{len(frames)} frames @ {1 / dt:.1f} fps, hips travel {[round(xs[-1][i] - xs[0][i], 3) for i in range(3)]} m, hips height {xs[0][1]:.3f} m")


if __name__ == "__main__":
    flags = [a for a in sys.argv[1:] if a.startswith("--")]; args = [a for a in sys.argv[1:] if not a.startswith("--")]
    mode = next((f.split("=", 1)[1] for f in flags if f.startswith("--positions=")), "auto")
    if mode not in ("auto", "absolute", "relative") or len(args) < 2: raise SystemExit(__doc__)
    main(args[0], args[1], float(args[2]) if len(args) > 2 else 0.01, mode)
