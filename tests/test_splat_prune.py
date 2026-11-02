import math, struct, sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import splat_prune

NAMES = ["f_dc_0", "f_dc_1", "f_dc_2", "f_rest_0", "f_rest_1", "opacity", "scale_0", "scale_1", "scale_2", "x", "y", "z"]


def ply(path, rows):
    head = "ply\nformat binary_little_endian 1.0\ncomment Exported from Brush\nelement vertex %d\n" % len(rows)
    head += "".join(f"property float {n}\n" for n in NAMES) + "end_header\n"
    Path(path).write_bytes(head.encode() + b"".join(struct.pack("<%df" % len(NAMES), *r) for r in rows))


def logit(p): return math.log(p / (1 - p))


class PruneTest(unittest.TestCase):
    def test_opacity_needle_and_dc_only(self):
        disc = [0.1, 0.2, 0.3, 0.5, 0.6, logit(0.9), math.log(0.02), math.log(0.02), math.log(1e-6), 0, 0, 0]
        faint = disc[:]; faint[5] = logit(0.05)
        needle = disc[:]; needle[6] = math.log(2.0)  # longest axis 100x the middle one
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "in.ply"; ply(src, [disc, faint, needle])
            self.assertEqual(splat_prune.prune(src, Path(d) / "a.ply", min_opacity=0.1), {"in": 3, "out": 2})
            self.assertEqual(splat_prune.prune(src, Path(d) / "b.ply", min_opacity=0.1, max_needle=50), {"in": 3, "out": 1})
            splat_prune.prune(src, Path(d) / "c.ply", dc_only=True)
            head, names, n, data = splat_prune.read(Path(d) / "c.ply")
            self.assertEqual(n, 3); self.assertEqual(names, NAMES)
            self.assertEqual([round(data[i], 6) for i in (0, 3, 4)], [0.1, 0.0, 0.0])  # DC kept, higher bands zeroed
            self.assertIn("comment Exported from Brush", head)  # the rest of the header survives
            tiny = disc[:]; tiny[6:9] = [-25.0, -30.0, -30.0]; tiny[5] = -1000.0  # e^5 needle, extreme logit
            ply(src, [disc, tiny]); self.assertEqual(splat_prune.prune(src, Path(d) / "e.ply", max_needle=50), {"in": 2, "out": 1})
            self.assertEqual(splat_prune.prune(src, Path(d) / "f.ply", min_opacity=0.1), {"in": 2, "out": 1})
            Path(src).write_bytes(Path(src).read_bytes()[:-4])  # truncated payload
            with self.assertRaises(ValueError): splat_prune.prune(src, Path(d) / "g.ply")
            Path(src).write_bytes(Path(src).read_bytes().replace(b"end_header", b"element face 0\nend_header"))
            with self.assertRaises(ValueError): splat_prune.read(src)  # a second element is refused


if __name__ == "__main__":
    unittest.main()
