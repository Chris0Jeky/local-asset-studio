"""Clean a 3DGS PLY (binary little-endian, all-float properties, e.g. a Brush export). Stdlib only.

  python scripts/splat_prune.py <in.ply> <out.ply> [--min-opacity 0.1] [--max-needle 0] [--dc-only]

--min-opacity drops splats whose sigmoid(opacity) is below the value; 0.1 was the best measured cut on 2 Nov
(docs/research/BLENDER-54-SPLATS-AND-LAB-MCP-2026-11-02.md). --max-needle drops splats whose longest axis exceeds that
many times the middle one (splats are flat discs, so the shortest axis says nothing). --dc-only zeroes the higher SH
bands (view-dependent colour).
"""
import argparse, json, math, struct, sys
from array import array


def read(path):
    raw = open(path, "rb").read(); end = raw.index(b"end_header\n") + len(b"end_header\n"); head = raw[:end].decode()
    lines = head.splitlines()
    if "format binary_little_endian 1.0" not in lines: raise ValueError("only binary little-endian PLY is supported")
    n = int(next(l.split()[2] for l in lines if l.startswith("element vertex")))
    props = [l.split() for l in lines if l.startswith("property")]
    if any(p[1] != "float" for p in props): raise ValueError("only all-float vertex properties are supported")
    data = array("f"); data.frombytes(raw[end:end + n * 4 * len(props)])
    if sys.byteorder != "little": data.byteswap()
    return head, [p[2] for p in props], n, data


def write(path, head, rows, width):
    lines = [l if not l.startswith("element vertex") else f"element vertex {len(rows) // width}" for l in head.splitlines()]
    out = array("f", rows)
    if sys.byteorder != "little": out.byteswap()
    open(path, "wb").write(("\n".join(lines) + "\n").encode() + out.tobytes())


def prune(src, dst, min_opacity=0.0, max_needle=0.0, dc_only=False):
    head, names, n, d = read(src); w = len(names); col = {k: i for i, k in enumerate(names)}
    rest = [i for k, i in col.items() if k.startswith("f_rest_")]; kept = array("f")
    for r in range(n):
        row = d[r * w:(r + 1) * w]
        if 1 / (1 + math.exp(-row[col["opacity"]])) < min_opacity: continue
        if max_needle:
            axes = sorted(math.exp(row[col[k]]) for k in ("scale_0", "scale_1", "scale_2"))
            if axes[2] > max_needle * max(axes[1], 1e-12): continue
        if dc_only:
            for i in rest: row[i] = 0.0
        kept.extend(row)
    write(dst, head, kept, w)
    return {"in": n, "out": len(kept) // w}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0]); ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--min-opacity", type=float, default=0.0); ap.add_argument("--max-needle", type=float, default=0.0)
    ap.add_argument("--dc-only", action="store_true"); a = ap.parse_args()
    print(json.dumps(prune(a.src, a.dst, a.min_opacity, a.max_needle, a.dc_only)))


if __name__ == "__main__":
    main()
