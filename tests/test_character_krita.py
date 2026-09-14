import io
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from PIL import Image

from integrations.krita import native_edit
from scripts import character_krita as ck
from scripts.character_edit_demo import create
from scripts.character_study import file_sha, read_json, sha, write_json


ROOT = Path(__file__).resolve().parents[1]


def write_kra(path, image, layer_names=("Source",)):
    """Write the smallest structurally inspectable KRA fixture."""
    preview = io.BytesIO()
    image.save(preview, format="PNG")
    layers = "".join(
        f'<layer name="{name}" nodetype="paintlayer" visible="1" compositeop="normal" />'
        for name in layer_names
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "maindoc.xml",
            f'<image width="{image.width}" height="{image.height}">{layers}</image>',
        )
        archive.writestr("preview.png", preview.getvalue())


class NativeNode:
    def __init__(self, document, name, pixels, faulty=False):
        self.document = document
        self._name = name
        self.pixels = pixels
        self.faulty = faulty
        self._visible = True

    def name(self): return self._name
    def type(self): return "paintlayer"
    def childNodes(self): return []
    def animated(self): return False
    def colorModel(self): return "RGBA"
    def colorDepth(self): return "U8"
    def colorProfile(self): return native_edit.PROFILE
    def blendingMode(self): return "normal"
    def pixelData(self, x, y, width, height): return self.pixels
    def visible(self): return self._visible
    def setVisible(self, value): self._visible = value
    def opacity(self): return 255
    def locked(self): return False
    def setPixelData(self, pixels, x, y, width, height):
        if not self.faulty:
            self.pixels = bytes(pixels)
        return None


class NativeRoot:
    def __init__(self, document): self.document = document
    def addChildNode(self, node, sibling):
        self.document.nodes.append(node)
        return True


class NativeDocument:
    def __init__(self, source, overlay, result, edited=False, faulty=False):
        self.source = source
        self.overlay = overlay
        self.result = result
        self.width_value = 2
        self.height_value = 2
        self.nodes = [NativeNode(self, "Source", source)]
        if edited:
            self.nodes.append(NativeNode(self, "Proposed edit", overlay))
        self.faulty = faulty
        self.closed = False
        self.modified = False

    def width(self): return self.width_value
    def height(self): return self.height_value
    def colorModel(self): return "RGBA"
    def colorDepth(self): return "U8"
    def colorProfile(self): return native_edit.PROFILE
    def setBatchmode(self, value): pass
    def waitForDone(self): pass
    def refreshProjection(self): pass
    def topLevelNodes(self): return self.nodes
    def rootNode(self): return NativeRoot(self)
    def createNode(self, name, node_type):
        pixels = b"\x00" * len(self.overlay) if self.faulty else self.overlay
        return NativeNode(self, name, pixels, self.faulty)
    def pixelData(self, x, y, width, height):
        if len(self.nodes) == 1 or not self.nodes[-1].visible(): return self.source
        return self.result
    def saveAs(self, path):
        image = Image.frombytes("RGBA", (self.width_value, self.height_value), self.result, "raw", "BGRA")
        write_kra(Path(path), image, ("Source", "Proposed edit"))
        return True
    def exportImage(self, path, info):
        image = Image.frombytes("RGBA", (self.width_value, self.height_value), self.result, "raw", "BGRA")
        image.save(path, format="PNG")
        return True
    def setModified(self, value): self.modified = value
    def close(self): self.closed = True


class NativeApp:
    def __init__(self, root, source, overlay, result, faulty=False):
        self.root = Path(root)
        self.source, self.overlay, self.result = source, overlay, result
        self.faulty = faulty
        self.documents = []

    def openDocument(self, path):
        edited = Path(path).name == "edited.kra"
        document = NativeDocument(self.source, self.overlay, self.result, edited=edited, faulty=self.faulty)
        self.documents.append(document)
        return document

    def version(self): return "synthetic-krita"


class CharacterKrita(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "job"
        create(self.root)
        self.original_document = read_json(self.root / "document.json")
        with Image.open(self.root / "source.png") as image:
            write_kra(self.root / "native-source.kra", image)
        self.package = self.root / "native-package"
        ck.prepare(
            self.root, "plan.json", "prepared", "revision-2/result.json",
            "document.json", "native-source.kra", "native-package",
        )
        self.native_plan = self.package / "native-plan.json"

    def _ref(self, name):
        return {"path": name, "sha256": file_sha(self.root / name)}

    def _config(self):
        runner = self.root / "kritarunner.exe"
        runner.write_bytes(b"synthetic runner")
        scripts = self.root / "runner-scripts"
        return {"kritarunner": str(runner), "kritarunner_scripts": str(scripts)}

    def _native_result(self, **changes):
        plan = read_json(self.native_plan)
        result_pixels = (self.package / "result.bgra").read_bytes()
        edited = self.package / "edited.kra"
        image = Image.frombytes("RGBA", tuple(plan["canvas"]), result_pixels, "raw", "BGRA")
        write_kra(edited, image, ("Source", "Proposed edit"))
        reopened = self.package / "reopened.png"
        image.save(reopened, format="PNG")
        original = {"name": "Source", "type": "paintlayer", "visible": True,
                    "opacity": 255, "locked": False,
                    "pixels_sha256": native_edit.digest((self.package / "source.bgra").read_bytes())}
        edit = {"name": "Proposed edit", "type": "paintlayer", "visible": True,
                "opacity": 255, "locked": False,
                "pixels_sha256": native_edit.digest((self.package / "overlay.bgra").read_bytes())}
        payload = {
            "schema_version": 1, "operation": plan["operation"],
            "edit_plan_sha256": plan["edit_plan_sha256"],
            "native_plan_sha256": native_edit.digest(self.native_plan.read_bytes()),
            "krita_version": "synthetic-krita", "canvas": plan["canvas"],
            "profile": plan["profile"], "original_layers": [original],
            "result_layers": [original, edit], "native_save_reopen_verified": True,
            "native_projection_exact": True, "hide_restores_source": True,
            "neural_inference": False, "semantic_approval": False,
            "review_state": "unreviewed",
            "outputs": {
                "edited.kra": {"sha256": file_sha(edited), "bytes": edited.stat().st_size},
                "reopened.png": {"sha256": file_sha(reopened), "bytes": reopened.stat().st_size},
            },
        }
        payload.update(changes)
        write_json(self.package / "native-result.json", payload)
        return payload

    def test_prepare_refuses_stale_document_and_native_source(self):
        document = read_json(self.root / "document.json")
        document["revision"] = 2
        (self.root / "document.json").unlink()
        write_json(self.root / "document.json", document)
        with self.assertRaisesRegex(ValueError, "Current exported document is stale"):
            ck.prepare(self.root, "plan.json", "prepared", "revision-2/result.json",
                       "document.json", "native-source.kra", "another-package")

        (self.root / "document.json").unlink()
        write_json(self.root / "document.json", self.original_document)
        with Image.open(self.root / "source.png") as source:
            write_kra(self.root / "native-source.kra", source, ("Changed",))
        with self.assertRaisesRegex(ValueError, "Changed or empty artifact: native-source.kra"):
            ck.execute(self.root, "native-package", {})

    def test_prepare_refuses_rehashed_altered_result(self):
        result_path = self.root / "revision-2/result.json"
        receipt = read_json(result_path)
        output = self.root / receipt["output"]["path"]
        with Image.open(output) as image:
            altered = image.convert("RGBA")
        altered.putpixel((0, 0), (1, 2, 3, 255))
        altered.save(output, format="PNG")
        receipt["output"]["sha256"] = file_sha(output)
        receipt["receipt_sha256"] = sha({k: v for k, v in receipt.items() if k != "receipt_sha256"})
        result_path.unlink()
        write_json(result_path, receipt)
        with self.assertRaisesRegex(ValueError, "Published edit pixels differ"):
            ck.prepare(self.root, "plan.json", "prepared", "revision-2/result.json",
                       "document.json", "native-source.kra", "altered-result-package")

    def test_prepare_refuses_rehashed_stale_candidate(self):
        result_path = self.root / "revision-2/result.json"
        receipt = read_json(result_path)
        candidate = self.root / receipt["candidate"]["path"]
        with Image.open(candidate) as image:
            altered = image.convert("RGBA")
        altered.putpixel((20, 20), (8, 9, 10, 255))
        altered.save(candidate, format="PNG")
        receipt["candidate"]["sha256"] = file_sha(candidate)
        receipt["receipt_sha256"] = sha({k: v for k, v in receipt.items() if k != "receipt_sha256"})
        result_path.unlink()
        write_json(result_path, receipt)
        with self.assertRaisesRegex(ValueError, "Published edit pixels differ"):
            ck.prepare(self.root, "plan.json", "prepared", "revision-2/result.json",
                       "document.json", "native-source.kra", "stale-candidate-package")

    def test_native_plan_rejects_modified_buffers_and_unsupported_overlay(self):
        overlay = self.package / "overlay.bgra"
        overlay.write_bytes(overlay.read_bytes()[:-4] + b"\x01\x02\x03\x7f")
        with self.assertRaisesRegex(ValueError, "Native input hash changed"):
            native_edit.read_plan(self.native_plan)

        plan = read_json(self.native_plan)
        plan["files"]["overlay.bgra"]["sha256"] = native_edit.digest(overlay.read_bytes())
        plan["files"]["overlay.bgra"]["bytes"] = overlay.stat().st_size
        self.native_plan.unlink()
        write_json(self.native_plan, plan)
        with self.assertRaisesRegex(ValueError, "binary coverage"):
            native_edit.read_plan(self.native_plan)

    def test_status_rejects_rehashed_wrong_reopened_pixels_and_missing_check(self):
        self._native_result()
        self.assertEqual("completed", ck.status(self.root, "native-package")["state"])
        with self.assertRaisesRegex(ValueError, "already recorded"):
            ck.execute(self.root, "native-package", {})
        reopened = self.package / "reopened.png"
        with Image.open(reopened) as image:
            altered = image.convert("RGBA")
        altered.putpixel((0, 0), (4, 5, 6, 255))
        altered.save(reopened, format="PNG")
        result = read_json(self.package / "native-result.json")
        result["outputs"]["reopened.png"] = {"sha256": file_sha(reopened), "bytes": reopened.stat().st_size}
        self.package.joinpath("native-result.json").unlink()
        write_json(self.package / "native-result.json", result)
        with self.assertRaisesRegex(ValueError, "Reopened PNG differs"):
            ck.status(self.root, "native-package")

        result["native_projection_exact"] = False
        self.package.joinpath("native-result.json").unlink()
        write_json(self.package / "native-result.json", result)
        with self.assertRaisesRegex(ValueError, "required checks"):
            ck.status(self.root, "native-package")

    def test_status_refuses_repeats_after_failure_and_uncertain_intent(self):
        write_json(self.package / "native-failure.json", {"error": "synthetic failure"})
        self.assertEqual("failed", ck.status(self.root, "native-package")["state"])
        with self.assertRaisesRegex(ValueError, "already recorded"):
            ck.execute(self.root, "native-package", {})

        (self.package / "native-failure.json").unlink()
        write_json(self.package / "native-intent.json", {"argv": ["synthetic"]})
        self.assertEqual("uncertain", ck.status(self.root, "native-package")["state"])
        with self.assertRaisesRegex(ValueError, "already recorded"):
            ck.execute(self.root, "native-package", {})

    def test_install_is_immutable_and_hash_named(self):
        config = self._config()
        installed = ck.install(config)
        target = Path(installed["installed_path"])
        self.assertEqual("studio_native_edit_" + installed["module_sha256"], target.stem)
        self.assertEqual(installed, ck.install(config))
        target.write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "differs from its pinned source"):
            ck.install(config)

    def test_execute_uses_fixed_hidden_command_and_retains_exit_zero_without_result(self):
        config = self._config()
        completed = subprocess.CompletedProcess([], 0, stdout="ok", stderr="")
        with mock.patch.object(ck.subprocess, "run", return_value=completed) as run:
            with self.assertRaisesRegex(ValueError, "exit code alone"):
                ck.execute(self.root, "native-package", config)
        command = run.call_args.args[0]
        self.assertEqual(6, len(command))
        self.assertEqual([config["kritarunner"], "-s", "studio_native_edit_" + ck.native_edit.digest(ck.MODULE.read_bytes()),
                          "-f", "run"], command[:5])
        self.assertTrue(Path(command[5]).samefile(self.native_plan))
        kwargs = run.call_args.kwargs
        self.assertFalse(kwargs["shell"])
        self.assertEqual(ck.TIMEOUT, kwargs["timeout"])
        self.assertFalse(kwargs["check"])
        self.assertEqual(getattr(subprocess, "CREATE_NO_WINDOW", 0), kwargs["creationflags"])
        if os.name == "nt":
            self.assertIsNotNone(kwargs["startupinfo"])
        self.assertTrue((self.package / "native-intent.json").is_file())
        self.assertTrue((self.package / "runner-log.json").is_file())

    def test_execute_timeout_retains_error_and_attempt(self):
        config = self._config()
        timeout = subprocess.TimeoutExpired(["synthetic"], ck.TIMEOUT, output="out", stderr="err")
        with mock.patch.object(ck.subprocess, "run", side_effect=timeout):
            with self.assertRaisesRegex(ValueError, "did not complete"):
                ck.execute(self.root, "native-package", config)
        self.assertTrue((self.package / "native-intent.json").is_file())
        self.assertTrue((self.package / "runner-error.json").is_file())
        with self.assertRaisesRegex(ValueError, "already recorded"):
            ck.execute(self.root, "native-package", config)

    def _small_native_plan(self):
        package = self.root / "small-package"
        package.mkdir()
        source = bytes([10, 20, 30, 255] * 4)
        overlay = bytes([90, 80, 70, 255, 0, 0, 0, 0, 0, 0, 0, 0, 90, 80, 70, 255])
        result = bytes([90, 80, 70, 255, 10, 20, 30, 255, 10, 20, 30, 255, 90, 80, 70, 255])
        image = Image.frombytes("RGBA", (2, 2), source, "raw", "BGRA")
        write_kra(package / "native-source.kra", image)
        files = {"native-source.kra": (package / "native-source.kra").read_bytes(),
                 "source.bgra": source, "overlay.bgra": overlay, "result.bgra": result}
        for name, raw in files.items(): (package / name).write_bytes(raw)
        plan = {"schema_version": 1, "operation": "character.krita-layer.v1", "workspace": str(self.root),
                "edit_plan_sha256": "e" * 64, "canvas": [2, 2], "profile": native_edit.PROFILE,
                "files": {name: {"bytes": len(raw), "sha256": native_edit.digest(raw)} for name, raw in files.items()},
                "neural_inference": False, "semantic_approval": False, "review_state": "unreviewed"}
        write_json(package / "native-plan.json", plan)
        return package, source, overlay, result

    def test_native_set_pixel_none_is_verified_by_readback(self):
        package, source, overlay, result = self._small_native_plan()
        app = NativeApp(package, source, overlay, result)
        krita = SimpleNamespace(InfoObject=lambda: object())
        with mock.patch.dict(sys.modules, {"krita": krita}):
            output = native_edit.execute(package / "native-plan.json", app)
        self.assertTrue(output["native_save_reopen_verified"])
        self.assertTrue(all(document.closed for document in app.documents))

    def test_native_faulty_readback_fails_and_closes_owned_documents(self):
        package, source, overlay, result = self._small_native_plan()
        app = NativeApp(package, source, overlay, result, faulty=True)
        with self.assertRaisesRegex(ValueError, "exact edit pixels"):
            native_edit.execute(package / "native-plan.json", app)
        self.assertTrue((package / "native-failure.json").is_file())
        self.assertFalse((package / "native-result.json").exists())
        self.assertTrue(all(document.closed for document in app.documents))


if __name__ == "__main__":
    unittest.main()
