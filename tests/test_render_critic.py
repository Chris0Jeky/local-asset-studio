import base64, http.server, json, sys, tempfile, threading, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import render_critic as rc


def row(category, verdicts, part=None, side=None):
    defects = [dict(v, type=k, evidence="") for k, v in verdicts.items() if v.get("present", True)]
    return {"id": category, "truth": {"category": category, "part": part, "side": side, "seed": 1}, "defects": defects}


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
        self.assertEqual(rc.score(rows)["detection"], {"tp": 1, "fp": 1, "fn": 0, "tn": 0, "precision": 0.5, "recall": 1.0})
        table = rc.table(rc.score(rows))
        self.assertIn("| omitted_mesh | 1 | 0 | 0 | 1.0 | 1.0 | 1/1 | 1/1 |", table)
        self.assertIn("| asymmetry | 0 | 2 | 0 | 0.0 | None | 0/0 | 0/0 |", table)
        self.assertIn("| **any defect (sample level)** | 1 | 1 | 0 | 0.5 | 1.0 |", table)

    def test_duplicate_reports_keep_the_most_confident(self):
        r = row("asymmetry", {}, part="arm.L", side="L")
        r["defects"] = [{"type": "asymmetry", "region": "left_arm", "confidence": 0.8, "evidence": ""},
                        {"type": "asymmetry", "region": "right_arm", "confidence": 0.4, "evidence": ""}]
        s = rc.score([r])["categories"]["asymmetry"]
        self.assertEqual((s["tp"], s["side_ok"], s["side_n"]), (1, 1, 1))

    def test_threshold_is_inclusive_and_can_turn_a_hit_into_a_miss(self):
        r = row("asymmetry", {"asymmetry": {"confidence": 0.5, "region": "left_arm"}}, part="arm.L", side="L")
        self.assertEqual(rc.score([r], threshold=0.5)["categories"]["asymmetry"]["tp"], 1)
        s = rc.score([r], threshold=0.6)
        self.assertEqual((s["categories"]["asymmetry"]["fn"], s["detection"]["fn"]), (1, 1))

    def test_detection_counts_quiet_samples(self):
        d = rc.score([row("clean", {}), row("omitted_mesh", {}, part="hand.L", side="L")])["detection"]
        self.assertEqual((d["tn"], d["fn"], d["tp"], d["fp"]), (1, 1, 0, 0))

    def test_wrong_side_and_wrong_region_are_misses(self):
        wrong_side = row("asymmetry", {"asymmetry": {"confidence": 0.9, "region": "left_arm"}}, part="arm.R", side="R")
        wrong_part = row("omitted_mesh", {"omitted_mesh": {"confidence": 0.9, "region": "right_leg"}}, part="hand.R", side="R")
        s = rc.score([wrong_side, wrong_part])["categories"]
        self.assertEqual((s["asymmetry"]["region_ok"], s["asymmetry"]["side_ok"], s["asymmetry"]["side_n"]), (1, 0, 1))
        self.assertEqual((s["omitted_mesh"]["region_ok"], s["omitted_mesh"]["side_ok"]), (0, 1))

    def test_missed_defect_and_errors(self):
        rows = [row("backside_hole", {}, part="torso"), {"id": "x", "error": "timeout"}]
        summary = rc.score(rows)
        self.assertEqual(summary["categories"]["backside_hole"]["fn"], 1)
        self.assertEqual(summary["categories"]["backside_hole"]["recall"], 0.0)
        self.assertEqual(summary["errors"], 1)

    def test_accepted_regions(self):
        self.assertEqual(rc.accepted_regions({"category": "omitted_mesh", "part": "eye.R"}), {"eye", "face", "head"})
        self.assertEqual(rc.region_family("right_eye"), "eye")
        self.assertIn("leg", rc.accepted_regions({"category": "white_material", "part": "pants"}))
        self.assertIn("arm", rc.accepted_regions({"category": "missing_texture", "part": "torso+arms"}))
        self.assertEqual(rc.region_family("left_hand"), "hand")
        self.assertEqual(rc.accepted_regions({"category": "omitted_mesh", "part": "shoe.L"}), {"feet"})
        self.assertEqual(rc.accepted_regions({"category": "white_material", "part": "skin"}), {"head", "face", "hand", "whole"})


class PixelGateTest(unittest.TestCase):
    def test_unchanged_candidate_never_reaches_the_model(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            ref, same, broken = (Path(d) / n for n in ("ref", "same", "broken"))
            for folder in (ref, same, broken): folder.mkdir()
            base = Image.new("RGB", (32, 32), (100, 100, 100))
            base.save(ref / "view_front.png"); base.point(lambda x: x + 3).save(same / "view_front.png")  # noise below level
            hole = base.copy(); hole.paste((255, 255, 255), (4, 4, 10, 10)); hole.save(broken / "view_front.png")
            # A dead server address proves no request is made when nothing changed or diff_only is set.
            quiet = rc.check([same / "view_front.png"], reference=[ref / "view_front.png"], server="http://127.0.0.1:9")
            diff = rc.check([broken / "view_front.png"], reference=[ref / "view_front.png"], server="http://127.0.0.1:9", diff_only=True)
        self.assertEqual((quiet["changed"], quiet["defects"], quiet["pixel_diff"]["front"]["changed_px"]), (False, [], 0))
        self.assertEqual((diff["changed"], diff["pixel_diff"]["front"]), (True, {"changed_px": 36, "bbox": (4, 4, 10, 10)}))

    def test_size_change_is_a_change(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "c").mkdir(); (Path(d) / "r").mkdir()
            Image.new("RGB", (20, 20)).save(Path(d) / "c" / "view_front.png"); Image.new("RGB", (10, 10)).save(Path(d) / "r" / "view_front.png")
            r = rc.check([Path(d) / "c" / "view_front.png"], reference=[Path(d) / "r" / "view_front.png"], server="http://127.0.0.1:9", diff_only=True)
        self.assertTrue(r["changed"]); self.assertEqual(r["pixel_diff"]["front"]["changed_px"], 400)

    def test_noise_below_the_pixel_floor_is_cleared(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            ref = Path(d) / "ref.png"; base = Image.new("RGB", (32, 32), (100, 100, 100)); base.save(ref)
            got = []
            for n in (rc.DIFF_MIN_PX - 1, rc.DIFF_MIN_PX):
                c = base.copy()
                for i in range(n): c.putpixel((i % 32, i // 32), (200, 100, 100))
                (Path(d) / "c").mkdir(exist_ok=True); c.save(Path(d) / "c" / "ref.png")
                got.append(rc.check([Path(d) / "c" / "ref.png"], reference=[ref], server="http://127.0.0.1:9", diff_only=True)["changed"])
        self.assertEqual(got, [False, True])

    def test_view_missing_from_reference_is_not_cleared(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            for name in ("view_front.png", "view_back.png"): Image.new("RGB", (8, 8)).save(Path(d) / name)
            r = rc.check([Path(d) / "view_front.png", Path(d) / "view_back.png"], reference=[Path(d) / "view_front.png"],
                         server="http://127.0.0.1:9", diff_only=True)
        self.assertTrue(r["changed"])


class RequestTest(unittest.TestCase):
    def test_schema_constrains_types_and_regions(self):
        item = rc.schema(rc.RUBRIC)["properties"]["defects"]["items"]["properties"]
        self.assertEqual(item["type"]["enum"], list(rc.RUBRIC))
        self.assertEqual(item["region"]["enum"], list(rc.REGIONS))

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


class _Canned(http.server.BaseHTTPRequestHandler):
    bodies = []
    def do_POST(self):
        _Canned.bodies.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
        answer = {"defects": [{"type": "omitted_mesh", "region": "left_hand", "confidence": 0.7, "evidence": "no hand"}]}
        data = json.dumps({"choices": [{"message": {"content": json.dumps(answer)}}], "model": "m", "timings": {"prompt_n": 5}}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(data)))
        self.end_headers(); self.wfile.write(data)
    def log_message(self, *a): pass


class ModelPathTest(unittest.TestCase):
    def setUp(self):
        self.srv = http.server.HTTPServer(("127.0.0.1", 0), _Canned); _Canned.bodies.clear()
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"
    def tearDown(self): self.srv.shutdown(); self.srv.server_close()

    def views(self, d, name, colour):
        from PIL import Image
        (Path(d) / name).mkdir()
        for v in rc.VIEWS: Image.new("RGB", (16, 16), colour).save(Path(d) / name / f"view_{v}.png")
        (Path(d) / name / "truth.json").write_text(json.dumps({"category": "clean" if name.startswith("clean") else "omitted_mesh",
                                                               "part": "hand.L", "side": "L", "seed": 1}))
        return Path(d) / name

    def test_changed_candidate_reaches_the_model_with_a_schema(self):
        with tempfile.TemporaryDirectory() as d:
            ref, cand = self.views(d, "clean-1", (0, 0, 0)), self.views(d, "omitted_mesh-1", (255, 0, 0))
            r = rc.check(rc.views(cand), reference=rc.views(ref), server=self.url)
        self.assertEqual((r["changed"], r["defects"][0]["type"], r["timings"]["prompt_n"]), (True, "omitted_mesh", 5))
        body = _Canned.bodies[-1]
        self.assertEqual((body["temperature"], body["response_format"]["type"]), (0, "json_schema"))
        texts = [c["text"] for c in body["messages"][0]["content"] if c["type"] == "text"]
        self.assertEqual(sum(t.startswith("REFERENCE") for t in texts), 4)

    def test_evaluate_resumes_retrying_errors_and_records_missing_references(self):
        with tempfile.TemporaryDirectory() as d:
            sets = Path(d) / "set"; sets.mkdir()
            for name, colour in (("clean-1", (0, 0, 0)), ("omitted_mesh-1", (9, 9, 9)), ("asymmetry-1", (9, 9, 9))):
                self.views(sets, name, colour)
            (sets / "asymmetry-1" / "view_back.png").unlink()  # incomplete sample
            out = Path(d) / "r.jsonl"
            out.write_text(json.dumps({"id": "omitted_mesh-1", "error": "timeout"}) + "\n")
            rc.evaluate(sets, out, reference_root=sets, server=self.url)
            rows = {r["id"]: r for r in rc.load_rows(out)}
            self.assertNotIn("clean-1", rows)                 # its own reference: skipped
            self.assertNotIn("error", rows["omitted_mesh-1"])  # the earlier error was retried and replaced
            self.assertIn("missing views", rows["asymmetry-1"]["error"])
            n = len(_Canned.bodies); rc.evaluate(sets, out, reference_root=sets, server=self.url)
            self.assertEqual(len(_Canned.bodies), n)          # completed rows are not re-run (the error row is retried, no request)


if __name__ == "__main__":
    unittest.main()
