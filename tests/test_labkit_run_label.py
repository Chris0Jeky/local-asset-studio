"""Studio run labels for lab submissions (issue #963): payload and edge cases.

No network request or generation is made: every seam behind `labkit.run_studio`
(lease guard, backends, sampler, polling sleeps, HTTP) is faked, and assertions
run against the captured outgoing payload. `app/workspace.py:clean_run_label`
is the independent oracle: it is the exact rule `POST /api/jobs` enforces, so a
payload label it accepts cannot turn a valid lab submission into REJECTED.
"""
import copy
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve()
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "experiments" / "curated" / "overnight-20260923"))
sys.path.insert(0, str(REPO / "app"))

import labkit  # noqa: E402
from workspace import RUN_LABEL_MAX, clean_run_label  # noqa: E402  -- server rule oracle

# Result keys used by the current overnight-lab call sites; all must stay recognizable.
CALL_SITE_LABELS = (
    "anime-masked-repair-proof",
    "zimage-fast-proof",
    "depth-fullbody-2026092301",
    "d025-2026092301",
    "standing-p09-5",
    "wai",
    "cstati-v3-baseline-retry",
)


class FakeSampler:
    def __init__(self, pid):
        self.pid = pid
        self.stop = threading.Event()
    def start(self):
        return self
    def finish(self):
        return {}


class StudioFake:
    """Capture POST /api/jobs bodies; answer every poll as instantly completed."""
    def __init__(self):
        self.posts = []
    def __call__(self, url, body=None, timeout=60, origin=None):
        if url == labkit.STUDIO + "/api/jobs":
            self.posts.append({"body": copy.deepcopy(body), "origin": origin})
            return {"id": "job-test-1"}
        if url == labkit.STUDIO + "/api/jobs/job-test-1/recipe":
            return {}
        if url == labkit.STUDIO + "/api/jobs/job-test-1":
            return {"status": "completed", "prompt_ids": ["prompt-test-1"],
                    "outputs": [], "elapsed_seconds": 1.0}
        raise AssertionError("unexpected URL " + url)


def server_accepts(value):
    """The Studio rule: returns the trimmed label instead of raising."""
    return clean_run_label(value) == value


class RunLabelTests(unittest.TestCase):
    def run_lab(self, fake, intent, label, **kwargs):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        results = labkit.Results(Path(tmp.name))
        with (patch.object(labkit, "http", fake),
              patch.object(labkit, "guard", lambda: None),
              patch.object(labkit, "comfy_pid", lambda: None),
              patch.object(labkit, "commit_pct", lambda: (None, 1.0)),
              patch.object(labkit, "runtime_identity", lambda: {}),
              patch.object(labkit, "Sampler", FakeSampler),
              patch("time.sleep", lambda *args, **kwargs: None)):
            record = labkit.run_studio(intent, label, results, **kwargs)
        return record, results

    def base_intent(self):
        return {"preset_id": "zimage-fast", "controls": {}, "batch_count": 1,
                "references": [], "parent_assets": []}

    def test_call_site_labels_pass_through_recognizably(self):
        for label in CALL_SITE_LABELS:
            with self.subTest(label=label):
                self.assertEqual(labkit.studio_run_label(label), label)
                self.assertTrue(server_accepts(label))

    def test_helper_never_emits_a_server_reject(self):
        corpus = ["", "   ", "\t \n ", "\x00\x07", "ab\x00cd\nef",
                  "  padded label  ", "a  b\tc", "x" * 200,
                  "zimage-fast-proof-" + "y" * 200, "élève-1 gündoğumu",
                  None, 123]
        for raw in corpus:
            with self.subTest(raw=raw):
                out = labkit.studio_run_label(raw)
                self.assertIsInstance(out, str)
                self.assertTrue(1 <= len(out) <= RUN_LABEL_MAX, out)
                self.assertTrue(server_accepts(out), out)

    def test_controls_dropped_whitespace_falls_back_overlong_truncated(self):
        self.assertEqual(labkit.studio_run_label("ab\x00cd"), "abcd")
        self.assertEqual(labkit.studio_run_label("foo\nbar"), "foobar")
        self.assertEqual(labkit.studio_run_label("   "), labkit.RUN_LABEL_FALLBACK)
        self.assertEqual(labkit.studio_run_label("  padded label  "), "padded label")
        long_label = "zimage-fast-proof-" + "y" * 200
        out = labkit.studio_run_label(long_label)
        self.assertEqual(len(out), RUN_LABEL_MAX)
        self.assertTrue(long_label.startswith(out))
        self.assertTrue(server_accepts(out))

    def test_payload_posts_a_copied_intent_with_the_label(self):
        fake, intent, label = StudioFake(), self.base_intent(), "zimage-fast-proof"
        snapshot = copy.deepcopy(intent)
        record, _ = self.run_lab(fake, intent, label)
        self.assertEqual(len(fake.posts), 1)
        body = fake.posts[0]["body"]
        self.assertEqual(fake.posts[0]["origin"], labkit.STUDIO)
        self.assertEqual(body["label"], label)
        self.assertEqual(body["preset_id"], "zimage-fast")
        self.assertIsNot(body, intent)
        self.assertEqual(intent, snapshot)  # caller-owned intent never mutated
        self.assertNotIn("label", intent)
        self.assertEqual(record["label"], label)
        self.assertEqual(record["submitted_label"], label)
        self.assertEqual(record["job_id"], "job-test-1")
        self.assertEqual(record["status"], "completed")

    def test_payload_overrides_a_stale_intent_label(self):
        fake = StudioFake()
        intent = self.base_intent()
        intent["label"] = "  stale\tlabel\n"
        record, _ = self.run_lab(fake, intent, "zimage-fast-proof")
        self.assertEqual(fake.posts[0]["body"]["label"], "zimage-fast-proof")
        self.assertEqual(intent["label"], "  stale\tlabel\n")  # untouched
        self.assertEqual(record["submitted_label"], "zimage-fast-proof")

    def test_edge_label_posts_valid_payload_but_keeps_result_key(self):
        # Overlong here is 100 chars (extreme lengths are covered at helper level);
        # the full run writes result files keyed by the original label, so the name
        # must stay comfortably under filesystem path limits.
        for label in ("   ", "zimage-fast-proof-" + "q" * 81):
            with self.subTest(label=label[:20] + "…"):
                fake = StudioFake()
                record, results = self.run_lab(fake, self.base_intent(), label)
                body = fake.posts[0]["body"]
                self.assertTrue(server_accepts(body["label"]), body["label"])
                self.assertEqual(body["label"], labkit.studio_run_label(label))
                self.assertEqual(record["label"], label)
                self.assertIs(results.find(label), record)
                self.assertEqual(record["submitted_label"], body["label"])
                self.assertTrue(record["recipe_file"].endswith(label + ".recipe.json"))

    def test_skip_existing_posts_nothing(self):
        fake = StudioFake()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        results = labkit.Results(Path(tmp.name))
        prior = results.add({"label": "zimage-fast-proof", "status": "completed"})
        with (patch.object(labkit, "http", fake),
              patch.object(labkit, "guard", lambda: None)):
            record = labkit.run_studio(self.base_intent(), "zimage-fast-proof", results)
        self.assertIs(record, prior)
        self.assertEqual(fake.posts, [])


if __name__ == "__main__":
    unittest.main()
