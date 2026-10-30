"""The owner's Keep / Not this record per look (#1699): GET /api/looks/record counts the marks on pictures made with each look."""
import importlib.util
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("asset_server", ROOT / "app/server.py")
server = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(server)

GRAPH = {"1": {"inputs": {"text": "authored", "seed": 1}}}
TEXT = {"id": "text-only", "name": "Text only", "modality": "image", "graph": "workflows/api/demo-api.json", "positive": ["1", "text"], "seed": ["1", "seed"]}


class LookRecordTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        (self.root / "presets").mkdir(); (self.root / "workflows/api").mkdir(parents=True); (self.root / "config").mkdir()
        (self.root / "fake-comfy/input").mkdir(parents=True)
        (self.root / "config/local.json").write_text(json.dumps({"comfy_root": str(self.root / "fake-comfy")}))
        (self.root / "presets/catalog.json").write_text(json.dumps({"presets": [TEXT]}))
        (self.root / "workflows/api/demo-api.json").write_text(json.dumps(GRAPH))
        self.start = patch.object(threading.Thread, "start", lambda *_: None); self.start.start()
        self.addCleanup(self.start.stop); self.addCleanup(self.tmp.cleanup)
        self.studio = server.Studio(self.root); self.n = 0

    def make(self, look, review="unreviewed", privacy="regular", trashed=False):
        """One finished job with one registered picture; `look` None makes a job without a look."""
        self.n += 1; source = self.root / f"out{self.n}.png"; source.write_bytes(b"png" + bytes([self.n]))
        job = {"id": f"job{self.n}", "status": "completed", "created_at": float(self.n), "preset_id": "text-only", "preset_name": "Text only",
               "outputs": [{"filename": source.name, "media_type": "image"}], **({"look": {"id": look, "name": look, "revision": 1}} if look else {}),
               **({"privacy": "private"} if privacy == "private" else {})}
        self.studio.jobs[job["id"]] = job
        asset_id = self.studio.assets.register(job, 0, source)
        with self.studio.assets.connection() as db:
            db.execute("UPDATE assets SET review=?,trashed_at=? WHERE id=?", (review, 1.0 if trashed else None, asset_id))
        return asset_id

    def get(self, path="/api/looks/record"):
        handler = server.Handler.__new__(server.Handler); handler.studio = self.studio; handler.path = path
        handler._safe_host = lambda: True; sent = []; handler._json = lambda status, obj: sent.append((status, obj))
        handler.do_GET(); return sent[0]

    def test_counts_marks_per_look_and_ignores_pictures_without_a_look(self):
        for review in ("selected", "selected", "rejected", "needs_work", "unreviewed"): self.make("look-a", review)
        self.make("look-b", "selected"); self.make(None, "selected")
        status, body = self.get()
        self.assertEqual(status, 200)
        self.assertEqual(body["looks"], {"look-a": {"pictures": 5, "kept": 2, "not_this": 1, "needs_work": 1}, "look-b": {"pictures": 1, "kept": 1, "not_this": 0, "needs_work": 0}})

    def test_a_trashed_picture_is_not_counted(self):
        self.make("look-a", "selected"); self.make("look-a", "selected", trashed=True); self.make("look-c", "rejected", trashed=True)
        self.assertEqual(self.get()[1]["looks"], {"look-a": {"pictures": 1, "kept": 1, "not_this": 0, "needs_work": 0}})

    def test_private_runs_stay_out_of_the_regular_scope(self):
        self.make("look-a", "selected"); self.make("look-a", "selected", privacy="private"); self.make("look-p", "rejected", privacy="private")
        self.assertEqual(self.get()[1]["looks"], {"look-a": {"pictures": 1, "kept": 1, "not_this": 0, "needs_work": 0}})
        self.assertEqual(self.get("/api/looks/record?privacy=private")[1]["looks"],
                         {"look-a": {"pictures": 1, "kept": 1, "not_this": 0, "needs_work": 0}, "look-p": {"pictures": 1, "kept": 0, "not_this": 1, "needs_work": 0}})
        self.assertEqual(self.get("/api/looks/record?privacy=all")[1]["looks"]["look-a"]["pictures"], 2)


if __name__ == "__main__":
    unittest.main()
