import json, sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import splat_eval


class ScoreTest(unittest.TestCase):
    def test_psnr_over_white_and_pixel_diff(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            data, out = Path(d) / "data", Path(d) / "out"; (data / "test").mkdir(parents=True); out.mkdir()
            gt = Image.new("RGBA", (8, 8), (0, 0, 0, 0)); gt.paste((200, 0, 0, 255), (0, 0, 4, 8)); gt.save(data / "test" / "r_000.png")
            gt.save(out / "r_000.png")                                   # identical render
            pr = gt.copy(); pr.paste((0, 0, 0, 0), (0, 0, 4, 4)); pr.save(data / "test" / "r_001.png"); gt.save(out / "r_001.png")
            frames = [{"file_path": "./test/r_000"}, {"file_path": "./test/r_001"}]
            (data / "transforms_test.json").write_text(json.dumps({"frames": frames}))
            with self.assertRaises(FileNotFoundError): splat_eval.score(data, out)   # no manifest: render never finished
            (out / "rendered.json").write_text(json.dumps({"views": ["r_000.png"]}))
            with self.assertRaises(ValueError): splat_eval.score(data, out)          # partial view set
            (out / "rendered.json").write_text(json.dumps({"views": ["r_000.png", "r_001.png"], "cameras": "other dataset"}))
            with self.assertRaises(ValueError): splat_eval.score(data, out)          # renders from another dataset's cameras
            (out / "rendered.json").write_text(json.dumps({"views": ["r_000.png", "r_001.png"], "cameras": splat_eval.cameras_hash(data)}))
            splat_eval.score(data, out)
            s = json.loads((out / "score.json").read_text())
            Image.new("RGBA", (1, 1)).save(out / "r_001.png")
            with self.assertRaises(ValueError): splat_eval.score(data, out)          # size mismatch is not a perfect score
        same, off = s["views"]
        self.assertEqual((same["psnr"], same["changed_px"]), (120.0, 0))  # mse floor 1e-12 caps the identical view
        # r_001: a quarter of the image is red (200,0,0) in the render but white (transparent) in the truth:
        # mse = 0.25 * ((55/255)^2 + 1 + 1) / 3 = 0.1705 -> 7.68 dB.
        self.assertEqual(off["changed_px"], 16)
        self.assertAlmostEqual(off["psnr"], 7.68, places=2)
        self.assertEqual(s["min_psnr"], off["psnr"])


if __name__ == "__main__":
    unittest.main()
