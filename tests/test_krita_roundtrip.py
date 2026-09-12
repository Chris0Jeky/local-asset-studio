import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("krita_roundtrip", ROOT / "scripts/krita_roundtrip.py")
roundtrip = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(roundtrip)


def png(width=4, height=3):
    header = b"\x89PNG\r\n\x1a\n" + (13).to_bytes(4, "big") + b"IHDR" + width.to_bytes(4, "big") + height.to_bytes(4, "big")
    return header + b"\x08\x06\x00\x00\x00" + b"test-bytes"


def ora(path):
    with zipfile.ZipFile(path, "x") as archive:
        archive.writestr("mimetype", b"image/openraster")
        archive.writestr("stack.xml", b'<image w="4" h="3"><stack><layer name="Top" src="data/layer000.png"/></stack></image>')
        archive.writestr("data/layer000.png", png())


def kra(path):
    with zipfile.ZipFile(path, "x") as archive:
        archive.writestr("maindoc.xml", b'<DOC><layer name="Top" nodetype="paintlayer" visible="1"/></DOC>')
        archive.writestr("mergedimage.png", png())


class KritaRoundtripTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.exe = self.root / "krita.exe"; self.exe.write_bytes(b"configured Krita")
        self.source = self.root / "input.ora"; ora(self.source)

    def tearDown(self):
        self.temp.cleanup()

    def test_preflight_and_fixed_export_argv(self):
        info = roundtrip.preflight(self.exe)
        self.assertEqual(info["fixed_argv"], ["<input>", "--export", "--export-filename", "<output>"])
        self.assertEqual(info["execution_mode"], "windows-batch-hidden")
        self.assertEqual(roundtrip.command_for(self.exe, self.source, self.root / "out.kra")[2:4], ["--export", "--export-filename"])
        with self.assertRaises(roundtrip.KritaRoundtripError):
            roundtrip.preflight(self.root / "missing.exe")

    def test_mocked_native_save_reopen_preserves_source_and_inspects_outputs(self):
        def fake_run(command, **kwargs):
            self.assertFalse(kwargs["shell"])
            self.assertNotIn("QT_QPA_PLATFORM", kwargs["env"])
            if os.name == "nt":
                self.assertIsNotNone(kwargs["startupinfo"])
                self.assertEqual(kwargs["startupinfo"].wShowWindow, 0)
            output = Path(command[-1])
            if output.suffix == ".kra": kra(output)
            else: output.write_bytes(png())
            return __import__("subprocess").CompletedProcess(command, 0, "batch complete", "")

        with mock.patch.object(roundtrip.subprocess, "run", side_effect=fake_run) as run:
            result = roundtrip.execute(self.source, self.root / "result", self.exe)
        self.assertEqual(run.call_count, 2)
        self.assertEqual(result["source"]["canvas"], [4, 3])
        self.assertEqual(result["kra"]["layers"][0]["name"], "Top")
        self.assertEqual(result["export"]["dimensions"], [4, 3])
        self.assertTrue(result["native_kra_save_reopen_proved"])
        snapshot = self.root / "result" / "source.ora"
        self.assertEqual(roundtrip.file_sha(snapshot), roundtrip.file_sha(self.source))
        self.assertTrue((self.root / "result" / "ora-to-kra.log.json").is_file())

    def test_output_must_be_new_and_invalid_ora_never_starts_krita(self):
        target = self.root / "existing"; target.mkdir()
        with mock.patch.object(roundtrip.subprocess, "run") as run:
            with self.assertRaises(FileExistsError): roundtrip.execute(self.source, target, self.exe)
            invalid = self.root / "invalid.ora"; invalid.write_bytes(b"not a zip")
            with self.assertRaises(roundtrip.KritaRoundtripError): roundtrip.execute(invalid, self.root / "invalid-output", self.exe)
        run.assert_not_called()

    def test_changed_source_never_creates_false_roundtrip_provenance(self):
        inspect=roundtrip.inspect_ora
        def change_after_inspection(path):
            original=inspect(path)
            Path(path).write_bytes(b'changed source')
            return original
        with mock.patch.object(roundtrip,'inspect_ora',side_effect=change_after_inspection), mock.patch.object(roundtrip.subprocess,'run') as run:
            with self.assertRaisesRegex(roundtrip.KritaRoundtripError,'changed'):
                roundtrip.execute(self.source,self.root/'changed',self.exe)
        run.assert_not_called()
        self.assertTrue((self.root/'changed/failure.json').is_file())
        self.assertFalse((self.root/'changed/roundtrip.json').exists())


if __name__ == "__main__":
    unittest.main()
