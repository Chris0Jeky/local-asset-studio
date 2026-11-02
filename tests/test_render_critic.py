import base64, sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import render_critic as rc


def row(category, verdicts, part=None, side=None):
    full = {k: {"present": False, "confidence": 0.9, "region": "none", "evidence": ""} for k in rc.RUBRIC}
    full.update(verdicts)
    return {"id": category, "truth": {"category": category, "part": part, "side": side, "seed": 1}, "verdicts": full}


class ScoreTest(unittest.TestCase):
    def test_cross_category_false_alarm_counts_against_precision(self):
        rows = [row("omitted_mesh", {"omitted_mesh": {"present": True, "confidence": 0.9, "region": "left_hand"},
                                     "asymmetry": {"present": True, "confidence": 0.8, "region": "left_hand"}},
                    part="hand.L", side="L"),
                row("clean", {"asymmetry": {"present": True, "confidence": 0.3, "region": "right_arm"}})]
        s = rc.score(rows)["categories"]
        self.assertEqual((s["omitted_mesh"]["tp"], s["omitted_mesh"]["fp"]), (1, 0))
        self.assertEqual((s["asymmetry"]["tp"], s["asymmetry"]["fp"], s["asymmetry"]["precision"]), (0, 2, 0.0))
        self.assertEqual((s["omitted_mesh"]["region_ok"], s["omitted_mesh"]["side_ok"], s["omitted_mesh"]["side_n"]), (1, 1, 1))
        # A confidence threshold drops the low-confidence clean false alarm only.
        self.assertEqual(rc.score(rows, threshold=0.5)["categories"]["asymmetry"]["fp"], 1)

    def test_missed_defect_and_errors(self):
        rows = [row("backside_hole", {}, part="torso"), {"id": "x", "error": "timeout"}]
        summary = rc.score(rows)
        self.assertEqual(summary["categories"]["backside_hole"]["fn"], 1)
        self.assertEqual(summary["categories"]["backside_hole"]["recall"], 0.0)
        self.assertEqual(summary["errors"], 1)

    def test_accepted_regions(self):
        self.assertEqual(rc.accepted_regions({"category": "omitted_mesh", "part": "eye.R"}), {"face", "head"})
        self.assertIn("leg", rc.accepted_regions({"category": "white_material", "part": "pants"}))
        self.assertIn("arm", rc.accepted_regions({"category": "missing_texture", "part": "torso+arms"}))
        self.assertEqual(rc.region_family("left_hand"), "hand")


class RequestTest(unittest.TestCase):
    def test_schema_requires_every_category(self):
        s = rc.schema(rc.RUBRIC)
        self.assertEqual(set(s["required"]), set(rc.RUBRIC))
        self.assertEqual(s["properties"]["asymmetry"]["properties"]["region"]["enum"], list(rc.REGIONS))

    def test_messages_label_reference_and_candidate_views(self):
        with tempfile.TemporaryDirectory() as d:
            paths = []
            for name in ("view_front.png", "view_back.png"):
                p = Path(d) / name; p.write_bytes(b"png"); paths.append(p)
            m = rc.messages(paths[:1], rc.RUBRIC, reference=paths[1:])[0]["content"]
            texts = [c["text"] for c in m if c["type"] == "text"]
            self.assertEqual(texts[:2], ["REFERENCE back view:", "CANDIDATE front view:"])
            self.assertIn("not in the REFERENCE", texts[-1])
            self.assertEqual(m[1]["image_url"]["url"], "data:image/png;base64," + base64.b64encode(b"png").decode())


if __name__ == "__main__":
    unittest.main()
