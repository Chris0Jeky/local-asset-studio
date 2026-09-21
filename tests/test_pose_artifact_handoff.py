"""Durable editable pose artifacts paired with rendered guide pixels."""
import hashlib
import json
import sys
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "tests"))

import pose_guide  # noqa: E402
from studio_workflow import pose_artifact  # noqa: E402
import test_pose_guide as baseline  # noqa: E402


class PoseArtifactHandoffTests(unittest.TestCase):
    def setUp(self):
        self.fixture = baseline.PoseGuideTests("test_a_drawn_pose_is_stored_exactly_like_an_uploaded_picture")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.studio = self.fixture.studio

    def test_render_publishes_a_retrievable_validated_editable_artifact(self):
        result = pose_guide.render(self.studio, baseline.payload(unknown={16}))
        descriptor = result["artifact"]
        self.assertEqual(descriptor, {
            "id": result["artifact_id"],
            "schema": pose_artifact.SCHEMA,
            "file": result["artifact_id"] + ".pose.json",
            "sha256": descriptor["sha256"],
            "bytes": descriptor["bytes"],
            "url": "/api/pose/artifacts/" + result["artifact_id"],
            "authority": "none",
            "review": "unreviewed",
        })
        self.assertRegex(descriptor["sha256"], r"^[0-9a-f]{64}$")
        raw = pose_guide.read_artifact(self.studio, descriptor["id"])
        self.assertEqual(len(raw), descriptor["bytes"])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), descriptor["sha256"])
        restored = pose_artifact.validate(pose_artifact.loads(raw))
        self.assertEqual(restored["id"], descriptor["id"])
        self.assertIsNone(restored["joints"]["right_ear"])
        placed = [joint for joint in restored["joints"].values() if joint]
        self.assertEqual({joint["origin"] for joint in placed}, {"manual"})
        self.assertEqual({joint["confidence"] for joint in placed}, {None})
        self.assertFalse(result["generation_submitted"])
        self.assertEqual(self.studio.requests, [])

    def test_identical_poses_deduplicate_and_a_changed_existing_artifact_fails_before_another_upload(self):
        first = pose_guide.render(self.studio, baseline.payload())
        second = pose_guide.render(self.studio, baseline.payload())
        self.assertEqual(first["artifact"], second["artifact"])
        folder = self.studio.experiments / pose_guide.ARTIFACT_DIRECTORY
        self.assertEqual([path.name for path in folder.iterdir()], [first["artifact"]["file"]])
        upload_count = len(self.fixture.uploads())
        (folder / first["artifact"]["file"]).write_bytes(b"{}\n")
        with self.assertRaisesRegex(ValueError, "changed"):
            pose_guide.render(self.studio, baseline.payload())
        self.assertEqual(len(self.fixture.uploads()), upload_count,
                         "artifact integrity is checked before another guide upload")
        self.assertEqual(self.studio.requests, [])

    def test_artifact_lookup_rejects_unknown_or_ambiguous_identifiers(self):
        for identifier in ("", "../escape", "A" * 64, "f" * 63, "f" * 65):
            with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                pose_guide.read_artifact(self.studio, identifier)
        with self.assertRaisesRegex(ValueError, "unavailable"):
            pose_guide.read_artifact(self.studio, "f" * 64)


class PoseArtifactHandoffRouteTests(unittest.TestCase):
    def setUp(self):
        self.fixture = baseline.PoseGuideTests("test_a_drawn_pose_is_stored_exactly_like_an_uploaded_picture")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.http = baseline.server.create_server(
            self.fixture.root, port=0, studio_factory=lambda _: self.fixture.studio)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.thread.join, 5)
        self.addCleanup(self.http.server_close)
        self.addCleanup(self.http.shutdown)

    def call(self, method, path, body=None):
        connection = HTTPConnection("127.0.0.1", self.http.server_port, timeout=5)
        try:
            headers = {
                "Host": "127.0.0.1:8191",
                "Origin": "http://127.0.0.1:8191",
                "Content-Type": "application/json",
            }
            encoded = None if body is None else json.dumps(body)
            connection.request(method, path, encoded, headers=headers)
            reply = connection.getresponse()
            return reply.status, reply.getheader("Content-Type"), reply.read()
        finally:
            connection.close()

    def test_render_receipt_links_to_the_exact_editable_artifact(self):
        status, _, raw = self.call("POST", "/api/pose/render", baseline.payload(unknown={3}))
        self.assertEqual(status, 201, raw)
        result = json.loads(raw)
        descriptor = result["artifact"]
        served, content_type, artifact_raw = self.call("GET", descriptor["url"])
        self.assertEqual(served, 200, artifact_raw)
        self.assertEqual(content_type, "application/json")
        self.assertEqual(hashlib.sha256(artifact_raw).hexdigest(), descriptor["sha256"])
        restored = pose_artifact.validate(pose_artifact.loads(artifact_raw))
        self.assertEqual(restored["id"], descriptor["id"])
        self.assertIsNone(restored["joints"]["right_elbow"])
        self.assertFalse(self.fixture.studio.jobs)
        self.assertEqual(self.fixture.studio.requests, [])

    def test_artifact_route_rejects_bad_and_missing_ids_without_leaving_the_store(self):
        for identifier in ("../uploads", "not-a-hash", "F" * 64, "f" * 64):
            with self.subTest(identifier=identifier):
                status, _, raw = self.call("GET", "/api/pose/artifacts/" + identifier)
                self.assertEqual(status, 400, raw)
        self.assertFalse((self.fixture.root / "escape").exists())
        self.assertEqual(self.fixture.studio.requests, [])


if __name__ == "__main__":
    unittest.main()
