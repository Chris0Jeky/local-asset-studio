"""Offline faults for the hosted runtime bootstrap; no native tools or network calls."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import runpy
import sys
import tarfile
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('ci_blender_runtime', ROOT / 'scripts/ci_blender_runtime.py')
runtime = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(runtime)
DESCRIPTOR = ROOT / 'research/procgen/blender-shading-runtime.json'
SELECTION = json.loads(DESCRIPTOR.read_text())
NAME = runtime.validate_selection(SELECTION)


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def archive(self, extra=None):
        path = self.root / NAME
        with tarfile.open(path, 'w:xz') as bundle:
            binary = tarfile.TarInfo(NAME.removesuffix('.tar.xz') + '/blender')
            binary.mode = 0o755; binary.size = 4
            bundle.addfile(binary, io.BytesIO(b'test'))
            if extra is not None: bundle.addfile(extra, io.BytesIO(b'x' * extra.size) if extra.isfile() else None)
        return path

    def test_committed_selection_and_official_archive_pair(self):
        self.assertEqual(SELECTION['build_hash'], '6f4fc760c138')
        self.assertEqual(runtime.validate_selection(SELECTION), NAME)
        for field, value in [('version', [5, 3, 0]), ('release_cycle', 'release'), ('build_hash', 'main'),
                             ('architecture', 'arm64'), ('platform', 'windows')]:
            selected = dict(SELECTION, **{field: value})
            with self.subTest(field=field), self.assertRaises(ValueError): runtime.validate_selection(selected)
        selected = dict(SELECTION, checksum_url=SELECTION['archive_url'])
        with self.assertRaises(ValueError): runtime.validate_selection(selected)

    def test_rejects_nonofficial_or_ambiguous_urls_before_opening(self):
        invalid = [SELECTION['archive_url'].replace('https:', 'http:'),
                   SELECTION['archive_url'].replace('cdn.builder.blender.org', 'cdn.builder.blender.org.evil.test'),
                   SELECTION['archive_url'].replace('https://', 'https://user@'),
                   SELECTION['archive_url'].replace('blender.org/', 'blender.org:443/'),
                   SELECTION['archive_url'] + '?download=1', SELECTION['archive_url'] + '#fragment',
                   SELECTION['archive_url'].replace('/daily/', '/daily/../'),
                   SELECTION['archive_url'].replace('6f4fc760c138', '000000000000')]
        with patch.object(runtime, 'build_opener') as opener:
            for url in invalid:
                with self.subTest(url=url), self.assertRaises(ValueError):
                    runtime.download(url, self.root / 'out', NAME, 100, time.monotonic() + 5)
            opener.assert_not_called()

    def test_redirect_is_validated_before_following(self):
        redirects = runtime.OfficialRedirects(NAME)
        with self.assertRaises(ValueError):
            redirects.redirect_request(None, None, 302, '', {}, 'https://example.org/' + NAME)
        with self.assertRaises(ValueError):
            redirects.redirect_request(None, None, 302, '', {}, SELECTION['archive_url'] + '.sha256')

    def test_checksum_requires_matching_single_entry_and_actual_bytes(self):
        archive = self.archive(); digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        checksum = self.root / 'official.sha256'
        for text in (digest, digest + '  ' + NAME, digest.upper() + ' *' + NAME):
            checksum.write_text(text + '\n')
            self.assertEqual(runtime.verify_checksum(archive, checksum, NAME), digest)
        for text in (digest + '  another.tar.xz', digest + '\n' + digest, 'not a digest'):
            with self.subTest(text=text), self.assertRaises(ValueError): runtime.checksum_digest(text.encode(), NAME)
        checksum.write_text('0' * 64)
        with self.assertRaisesRegex(ValueError, 'mismatch'): runtime.verify_checksum(archive, checksum, NAME)

    def test_download_bounds_size_and_deadline_without_network(self):
        class Response(io.BytesIO):
            def geturl(self): return SELECTION['archive_url']
        for data, limit, deadline in [(b'four', 3, time.monotonic() + 5), (b'four', 10, 0), (b'', 10, time.monotonic() + 5)]:
            opener = SimpleNamespace(open=lambda *args, **kwargs: Response(data))
            destination = self.root / str(limit)
            destination.unlink(missing_ok=True)
            with patch.object(runtime, 'build_opener', return_value=opener), self.assertRaises(ValueError):
                runtime.download(SELECTION['archive_url'], destination, NAME, limit, deadline)

    def test_valid_archive_extracts_only_expected_executable(self):
        binary = runtime.extract_runtime(self.archive(), self.root / 'runtime', NAME)
        self.assertEqual(binary.read_bytes(), b'test')
        self.assertTrue(binary.is_relative_to(self.root / 'runtime'))

    def test_rejects_archive_escape_and_unsafe_member_types(self):
        prefix = NAME.removesuffix('.tar.xz')
        members = [tarfile.TarInfo('../outside'), tarfile.TarInfo('/outside'), tarfile.TarInfo('wrong/blender'),
                   tarfile.TarInfo(prefix + '/../../outside'), tarfile.TarInfo(prefix + '/back\\slash')]
        link = tarfile.TarInfo(prefix + '/escape'); link.type = tarfile.SYMTYPE; link.linkname = '../../outside'
        device = tarfile.TarInfo(prefix + '/device'); device.type = tarfile.CHRTYPE
        members += [link, device]
        for index, member in enumerate(members):
            with self.subTest(member=member.name), self.assertRaises((ValueError, tarfile.FilterError)):
                runtime.extract_runtime(self.archive(member), self.root / f'runtime{index}', NAME)
        self.assertFalse((self.root / 'outside').exists())

    def test_checksum_failure_retains_original_and_never_extracts(self):
        def download(url, destination, filename, limit, deadline):
            destination.write_bytes(b'0' * 64 if filename.endswith('.sha256') else b'corrupt')
            return {'url': url}
        evidence = self.root / 'evidence'
        with patch.object(runtime, 'download', side_effect=download), patch.object(runtime, 'extract_runtime') as extract:
            with self.assertRaisesRegex(ValueError, 'mismatch'):
                runtime.bootstrap(DESCRIPTOR, self.root / 'work', evidence)
            extract.assert_not_called()
        receipt = json.loads((evidence / 'bootstrap.json').read_text())
        self.assertEqual(receipt['state'], 'failed')
        self.assertIn('mismatch', receipt['error'])
        self.assertEqual((evidence / (NAME + '.sha256')).read_bytes(), b'0' * 64)


class RuntimeIdentityTests(unittest.TestCase):
    def test_runtime_mismatch_fails_before_export_but_retains_observed_identity(self):
        self.check_identity('000000000000', False)

    def test_selected_runtime_records_bundled_numpy_and_exporter_sources(self):
        self.check_identity(SELECTION['build_hash'], True)

    def check_identity(self, build_hash, expected_pass):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); output = root / 'runtime.json'
            module = root / '__init__.py'; module.write_text('# exporter fixture\n')
            app = SimpleNamespace(version=(5, 4, 0), version_string='5.4.0 Alpha', build_hash=build_hash.encode(),
                                  build_date=b'2026-11-05', build_time=b'02:41', build_platform=b'Linux', binary_path='/fixture/blender')
            operator = SimpleNamespace(get_rna_type=lambda: SimpleNamespace(properties={'export_normals': SimpleNamespace(default=True)}))
            modules = {'bpy': SimpleNamespace(app=app, ops=SimpleNamespace(export_scene=SimpleNamespace(gltf=operator))),
                       'numpy': SimpleNamespace(__version__='fixture', __file__='/fixture/numpy.py'),
                       'io_scene_gltf2': SimpleNamespace(__file__=str(module), bl_info={'version': (5, 4, 0)})}
            with patch.dict(sys.modules, modules), patch.object(sys, 'argv', ['blender', '--', str(DESCRIPTOR), str(output)]):
                if expected_pass: runpy.run_path(str(ROOT / 'scripts/ci_blender_identity.py'), run_name='__main__')
                else:
                    with self.assertRaisesRegex(RuntimeError, 'identity'):
                        runpy.run_path(str(ROOT / 'scripts/ci_blender_identity.py'), run_name='__main__')
            receipt = json.loads(output.read_text())
            self.assertEqual(receipt['state'], 'passed' if expected_pass else 'failed')
            self.assertEqual(receipt['build_hash'], build_hash)
            if expected_pass:
                self.assertEqual(receipt['numpy']['version'], 'fixture')
                self.assertEqual(receipt['gltf_exporter']['source_sha256']['__init__.py'], hashlib.sha256(module.read_bytes()).hexdigest())


if __name__ == '__main__': unittest.main()
