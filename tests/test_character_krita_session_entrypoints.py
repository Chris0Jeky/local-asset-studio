"""Focused entrypoint contracts; native GUI execution is proved separately."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts import character_krita as saved
from scripts import character_krita_session as entrypoints
from scripts.character_edit_demo import create
from scripts.character_study import file_sha, read_json
from integrations.krita.studio_session import plugin


class RequestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name) / "workspace"; create(self.workspace)
        # Reuse the existing protected compositor fixture to make a real native package.
        from PIL import Image
        import io, zipfile
        source = Image.open(self.workspace / "source.png").convert("RGBA")
        native = self.workspace / "native-source.kra"
        preview = io.BytesIO(); source.save(preview, format="PNG")
        with zipfile.ZipFile(native, "w") as archive:
            archive.writestr("maindoc.xml", '<image width="%d" height="%d"><layer name="Source" nodetype="paintlayer" visible="1" compositeop="normal" /></image>' % source.size)
            archive.writestr("preview.png", preview.getvalue())
        saved.prepare(self.workspace, "plan.json", "prepared", "revision-2/result.json", "document.json", "native-source.kra", "native-package")
        self.package = self.workspace / "native-package"
        self.capture = Path(self.temp.name) / "capture"; self.capture.mkdir()
        source_bytes = (self.package / "source.bgra").read_bytes()
        kra_bytes = (self.package / "native-source.kra").read_bytes()
        snapshot = {"schema_version": 1, "kind": "krita_document_snapshot", "session_id": "fixture",
                    "document": {"projection_sha256": entrypoints.native_edit.digest(source_bytes)},
                    "files": {"source.kra": {"sha256": entrypoints.native_edit.digest(kra_bytes)}}}
        (self.capture / "snapshot.json").write_text(json.dumps(snapshot), encoding="utf-8")

    def test_request_revalidates_plan_and_pins_absolute_dependencies(self):
        output = self.capture / "request.json"
        value = entrypoints.request(self.workspace, self.capture / "snapshot.json", "native-package", output)
        self.assertTrue(output.is_file())
        self.assertEqual(value, read_json(output))
        self.assertTrue(value["dependencies"])
        self.assertTrue(all(Path(item["path"]).is_absolute() for item in value["dependencies"]))
        self.assertLessEqual(len(value["dependencies"]), 256)

    def test_request_rejects_tampered_package_and_stale_source(self):
        plan = self.package / "native-plan.json"
        changed = read_json(plan); changed["changed_pixels"] += 1
        plan.write_text(json.dumps(changed), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Native plan changed"):
            entrypoints.request(self.workspace, self.capture / "snapshot.json", "native-package", self.capture / "tampered.json")

        saved.prepare(self.workspace, "plan.json", "prepared", "revision-2/result.json", "document.json", "native-source.kra", "native-package-2")
        from PIL import Image
        with Image.open(self.workspace / "source.png") as original:
            altered = original.convert("RGBA")
        altered.putpixel((0, 0), (1, 2, 3, 255)); altered.save(self.workspace / "source.png", format="PNG")
        with self.assertRaisesRegex(ValueError, "Changed or empty"):
            entrypoints.request(self.workspace, self.capture / "snapshot.json", "native-package-2", self.capture / "stale.json")


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runner = self.root / "kritarunner.exe"; self.runner.write_bytes(b"runner")
        self.krita = self.root / "krita.exe"; self.krita.write_bytes(b"krita")
        self.config = {"kritarunner": str(self.runner), "kritarunner_scripts": str(self.root / "runner-scripts"),
                       "krita": str(self.krita), "krita_scripts": str(self.root / "gui-scripts")}

    def test_install_is_hash_named_immutable_and_does_not_launch(self):
        with mock.patch("subprocess.run") as run:
            first = entrypoints.install(self.config, "runner")
        run.assert_not_called()
        self.assertNotIn(".desktop", " ".join(first["outputs"]))
        self.assertEqual(first, entrypoints.install(self.config, "runner"))
        module = Path(next(iter(first["outputs"].values()))["path"]).parent
        (module / "plugin.py").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "differs"):
            entrypoints.install(self.config, "runner")

    def test_install_accepts_only_normal_python_bytecode_cache(self):
        first = entrypoints.install(self.config, "runner")
        module = Path(next(iter(first["outputs"].values()))["path"]).parent
        cache = module / "__pycache__"; cache.mkdir()
        (cache / "plugin.cpython-311.pyc").write_bytes(b"cache")
        self.assertEqual(first, entrypoints.install(self.config, "runner"))
        (cache / "unrelated.pyc").write_bytes(b"cache")
        with self.assertRaisesRegex(ValueError, "cache"):
            entrypoints.install(self.config, "runner")

    def test_gui_install_writes_matching_desktop_and_runner_proof_is_opt_in(self):
        gui = entrypoints.install(self.config, "gui")
        desktop = [item for name, item in gui["outputs"].items() if name.endswith(".desktop")]
        self.assertEqual(1, len(desktop))
        self.assertIn(gui["module"], Path(desktop[0]["path"]).read_text(encoding="utf-8"))
        with self.assertRaisesRegex(ValueError, "proof module"):
            entrypoints.install(self.config, "runner", include_proof=True)
        with self.assertRaisesRegex(ValueError, "runner-only"):
            entrypoints.install(self.config, "gui", include_proof=True)


class PluginTests(unittest.TestCase):
    def test_startup_is_inert_and_native_document_identity_never_retargets(self):
        class Root:
            def __init__(self, value): self.value = value
            def uniqueId(self): return self.value
        class Document:
            def __init__(self, value, native): self.root, self.native = Root(value), native
            def rootNode(self): return self.root
            def __eq__(self, other): return isinstance(other, Document) and self.native == other.native
        class Application:
            def __init__(self, document): self.document, self.calls = document, 0
            def activeDocument(self): self.calls += 1; return self.document
        app = Application(Document("one", "native-a")); notices = []
        controller = plugin.Controller(app, lambda: "C:/capture", lambda: "C:/request.json", lambda *value: notices.append(value))
        self.assertIsNone(controller.session)
        self.assertEqual(0, app.calls)
        fake = mock.Mock(document=app.document); fake.capture.return_value = {"captured": True}
        with mock.patch.object(plugin, "Session", return_value=fake):
            self.assertEqual({"captured": True}, controller.capture())
        app.document = Document("one", "native-a")
        fake.show_source.return_value = {"source": True}
        self.assertEqual({"source": True}, controller.show_source())
        app.document = Document("one", "native-b")
        with self.assertRaisesRegex(ValueError, "differs"):
            controller.show_source()

    def test_import_reports_the_pinned_native_package_path(self):
        class Root:
            def uniqueId(self): return "root"
        class Document:
            def rootNode(self): return Root()
            def __eq__(self, other): return isinstance(other, Document)
        class Application:
            def activeDocument(self): return document
        document = Document(); notices = []
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); request = root / "request.json"; package = root / "package"; package.mkdir()
            native = package / "native-plan.json"; native.write_text("{}", encoding="utf-8")
            request.write_text(json.dumps({"native_plan": {"path": str(native)}}), encoding="utf-8")
            controller = plugin.Controller(Application(), lambda: None, lambda: str(request), lambda *value: notices.append(value))
            controller.session = mock.Mock(document=document); controller.identity = "root"
            controller.import_request()
        self.assertIn("/package/live-result.json", notices[-1][1].replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()
