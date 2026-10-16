"""Regression coverage for the reference-board path in app/references.py.

Exercises compile_board()/compile_references() role/minimum/sha256/prune
behavior with a minimal preset, a fake LoadImage graph, and a real uploads
directory holding actual PNG bytes (so image_record runs for real).
"""
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
import references  # noqa: E402  (bare name, never `from app import`)


def save_png(path, colour):
    Image.new("RGB", (16, 12), colour).save(path, "PNG")


def make_preset():
    return {
        "reference_slots": [
            {"role": "style", "binding": ["1", "image"]},
            {"role": "pose", "binding": ["2", "image"]},
        ],
        "reference_board": {"min": 1},
    }


def make_graph():
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": ""}},
        "2": {"class_type": "LoadImage", "inputs": {"image": ""}},
    }


class ReferenceBoardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.uploads = Path(self.tmp.name)
        save_png(self.uploads / "ref-a.png", "teal")
        save_png(self.uploads / "ref-b.png", "maroon")

    def test_board_rejects_bad_role_and_enforces_minimum(self):
        preset = make_preset()
        with self.assertRaises(ValueError):
            references.compile_board(
                preset, make_graph(),
                [{"file": "ref-a.png", "role": "bogus"}, {}],
                self.uploads,
            )
        with self.assertRaisesRegex(ValueError, "Attach at least"):
            references.compile_board(preset, make_graph(), [], self.uploads)
        with self.assertRaisesRegex(ValueError, "Attach at least"):
            references.compile_board(preset, make_graph(), [{}, {}], self.uploads)

        graph = make_graph()
        records = references.compile_references(
            preset, graph,
            [{"file": "ref-a.png", "role": "style"},
             {"file": "ref-b.png", "role": "pose"}],
            self.uploads,
        )
        self.assertEqual(graph["1"]["inputs"]["image"], "ref-a.png")
        self.assertEqual(graph["2"]["inputs"]["image"], "ref-b.png")
        self.assertEqual(records[0]["role"], "style")
        self.assertEqual(records[1]["role"], "pose")

    def test_board_rejects_stale_sha256(self):
        preset = make_preset()
        actual = references.image_record(self.uploads, "ref-a.png")
        self.assertNotEqual(actual["sha256"], "0" * 64)
        with self.assertRaisesRegex(ValueError, "bytes changed"):
            references.compile_board(
                preset, make_graph(),
                [{"file": "ref-a.png", "role": "style", "sha256": "0" * 64}, {}],
                self.uploads,
            )

    def test_missing_slot_is_pruned_and_marked(self):
        preset = make_preset()
        graph = make_graph()
        records = references.compile_board(
            preset, graph,
            [{"file": "ref-a.png", "role": "style"}, {}],
            self.uploads,
        )
        self.assertEqual(graph["1"]["inputs"]["image"], "ref-a.png")
        self.assertNotIn("2", graph)
        self.assertEqual(records[1]["file"], None)
        self.assertTrue(records[1]["pruned"])
        self.assertEqual(records[1]["slot"], 2)


if __name__ == "__main__":
    unittest.main()
