"""Fault-injected browser publication on synthetic files, without a model or network."""
from contextlib import redirect_stdout
import errno
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'app'))
import model_intake as intake
from download_contracts import InstallLease, file_identity
from model_library import ModelLibrary

spec = importlib.util.spec_from_file_location('intake_publication_cli', ROOT/'scripts/intake-downloads.py')
cli = importlib.util.module_from_spec(spec); spec.loader.exec_module(cli)


class IntakePublicationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve(); self.comfy = self.root/'comfy'
        self.downloads = self.root/'browser'; self.downloads.mkdir()
        header = json.dumps({'lora_unet_a.lora_down.weight': {}}).encode()
        self.body = len(header).to_bytes(8, 'little') + header + bytes(129)
        self.source = self.downloads/'demo.safetensors'; self.source.write_bytes(self.body)
        self.expected = intake.source_snapshot(self.source)
        self.target = self.comfy/'models/loras/demo.safetensors'
        self.state = self.root/'.runtime/downloads'
        # These tiny fixtures do not need the production 20 GiB reserve.
        reserve = patch.object(intake, 'RESERVE_BYTES', 0); reserve.start(); self.addCleanup(reserve.stop)

    def run_intake(self, **kwargs):
        return intake.import_candidate(self.root, self.comfy, kwargs.pop('source', self.source), 'loras',
                                       'demo.safetensors', kwargs.pop('identity', self.expected), 'header-hint', **kwargs)

    def journal(self):
        paths = list((self.state/'intake').glob('*.json')); self.assertEqual(len(paths), 1)
        return json.loads(paths[0].read_text())

    def assert_source(self):self.assertEqual(self.source.read_bytes(), self.body)

    def test_success_keeps_independent_source_and_observed_not_trusted_receipt(self):
        record = self.run_intake(); self.assert_source(); self.assertEqual(self.target.read_bytes(), self.body)
        self.assertFalse(os.path.samefile(self.source, self.target))
        self.assertEqual(record, self.journal()); self.assertEqual(record['status'], 'copied')
        self.assertEqual(record['sha256'], hashlib.sha256(self.body).hexdigest())
        self.assertFalse(record['verified']); self.assertIsNone(record['expected_sha256'])
        self.assertIsNone(record['runtime_compatible']); self.assertEqual(record['source_cleanup'], 'not-requested')
        self.assertEqual(record['file_identity'], file_identity(self.target))
        self.assertEqual([e['status'] for e in record['events']], ['intent', 'copying', 'prepared', 'copied'])
        self.assertFalse(Path(record['partial_path']).exists()); self.assertFalse((self.state/'install.lock').exists())

    def test_browser_changes_after_success_cannot_mutate_installed_bytes(self):
        self.run_intake(); self.source.write_bytes(b'new browser content')
        self.assertEqual(self.target.read_bytes(), self.body)

    def test_existing_destination_is_preserved_even_if_bytes_match(self):
        self.target.parent.mkdir(parents=True); self.target.write_bytes(self.body)
        with self.assertRaisesRegex(ValueError, 'already exists'):self.run_intake()
        self.assert_source(); self.assertEqual(self.target.read_bytes(), self.body)
        self.assertFalse((self.state/'intake').exists())

    def test_destination_appearing_at_publication_is_never_replaced(self):
        publish = intake.publish_verified
        def race(source, target, identity):
            target.write_bytes(b'other writer'); return publish(source, target, identity)
        with patch.object(intake, 'publish_verified', side_effect=race):
            with self.assertRaisesRegex(ValueError, 'appeared'):self.run_intake()
        self.assert_source(); self.assertEqual(self.target.read_bytes(), b'other writer')
        record = self.journal(); self.assertEqual(record['status'], 'needs_inspection')
        self.assertEqual(Path(record['partial_path']).read_bytes(), self.body)

    def test_model_root_drift_before_journal_refuses_without_side_effects(self):
        drifted = self.target.with_name('drifted.safetensors')
        with patch.object(intake.ModelLibrary, 'destination', return_value=drifted):
            with self.assertRaisesRegex(ValueError, 'Model root changed during intake'):
                self.run_intake()
        self.assert_source()
        self.assertFalse(self.target.exists())
        self.assertFalse(drifted.exists())
        self.assertFalse((self.state/'intake').exists())

    def test_destination_drift_after_publication_refuses_before_receipt(self):
        publish = intake.publish_verified

        def drift_after_publish(source, target, identity):
            result = publish(source, target, identity)
            target.write_bytes(b'post-publication writer')
            return result

        with patch.object(intake, 'publish_verified', side_effect=drift_after_publish):
            with self.assertRaisesRegex(ValueError, 'Destination changed before receipt'):
                self.run_intake()
        self.assert_source()
        self.assertEqual(self.target.read_bytes(), b'post-publication writer')
        self.assertEqual(self.journal()['status'], 'needs_inspection')

    def test_source_replacement_after_planning_refuses_before_journal(self):
        old = self.source.with_suffix('.old'); self.source.rename(old); self.source.write_bytes(self.body)
        with self.assertRaisesRegex(ValueError, 'changed since'):self.run_intake()
        self.assertEqual(old.read_bytes(), self.body); self.assert_source(); self.assertFalse(self.target.exists())
        self.assertFalse(self.state.exists())

    def test_source_mutation_after_copy_prevents_publication(self):
        copy = intake._copy
        def mutate(*args):
            digest = copy(*args); self.source.write_bytes(b'changed'); return digest
        with patch.object(intake, '_copy', side_effect=mutate):
            with self.assertRaisesRegex(ValueError, 'changed since'):self.run_intake()
        self.assertFalse(self.target.exists()); self.assertEqual(self.source.read_bytes(), b'changed')
        self.assertEqual(Path(self.journal()['partial_path']).read_bytes(), self.body)

    def test_same_size_mutation_is_detected(self):
        self.source.write_bytes(b'x'*len(self.body))
        # Restore mtime: the other identity fields must still detect the write.
        os.utime(self.source, ns=(self.expected['mtime_ns'], self.expected['mtime_ns']))
        if intake.source_snapshot(self.source) == self.expected:self.skipTest('filesystem did not expose metadata change')
        with self.assertRaisesRegex(ValueError, 'changed'):self.run_intake()
        self.assertFalse(self.target.exists())

    def test_changed_open_handle_is_refused(self):
        wrong = dict(self.expected, inode=self.expected['inode']+1)
        with patch.object(intake, '_handle_identity', return_value=wrong):
            with self.assertRaisesRegex(ValueError, 'Opened source'):self.run_intake()
        self.assert_source(); self.assertFalse(self.target.exists())

    def test_source_change_inside_copy_is_refused(self):
        with patch.object(intake, '_handle_identity', side_effect=[self.expected, dict(self.expected, size=0)]):
            with self.assertRaisesRegex(ValueError, 'during intake'):self.run_intake()
        self.assert_source(); self.assertFalse(self.target.exists())

    def test_source_change_after_prepared_journal_is_refused(self):
        save = intake._save
        def race(path, record, phase, **updates):
            save(path, record, phase, **updates)
            if phase == 'prepared':self.source.write_bytes(b'late change')
        with patch.object(intake, '_save', side_effect=race):
            with self.assertRaisesRegex(ValueError, 'changed'):self.run_intake()
        self.assertFalse(self.target.exists()); self.assertEqual(self.source.read_bytes(), b'late change')

    def test_corrupted_staged_copy_is_refused(self):
        copy = intake._copy
        def corrupt(source, stage, expected):
            digest = copy(source, stage, expected); stage.write_bytes(b'x'*expected['size']); return digest
        with patch.object(intake, '_copy', side_effect=corrupt):
            with self.assertRaisesRegex(ValueError, 'checksum'):self.run_intake()
        self.assert_source(); self.assertFalse(self.target.exists())

    def test_disk_preflight_preserves_original(self):
        usage = type('Disk', (), {'free': 0})()
        with patch.object(intake.shutil, 'disk_usage', return_value=usage):
            with self.assertRaisesRegex(ValueError, 'disk space'):self.run_intake()
        self.assert_source(); self.assertFalse(self.target.exists())
        self.assertFalse(Path(self.journal()['partial_path']).exists())

    def test_mid_copy_space_failure_preserves_partial(self):
        enough = type('Disk', (), {'free': 2**50})(); empty = type('Disk', (), {'free': 0})()
        with patch.object(intake.shutil, 'disk_usage', side_effect=[enough, empty]):
            with self.assertRaisesRegex(ValueError, 'during intake'):self.run_intake()
        self.assert_source(); self.assertFalse(self.target.exists())
        self.assertTrue(Path(self.journal()['partial_path']).exists())

    def test_copy_failure_preserves_partial_and_releases_only_own_lease(self):
        def fail(source, stage, expected):stage.write_bytes(b'part'); raise OSError('copy failed')
        with patch.object(intake, '_copy', side_effect=fail):
            with self.assertRaisesRegex(OSError, 'copy failed'):self.run_intake()
        self.assert_source(); self.assertFalse(self.target.exists())
        self.assertEqual(Path(self.journal()['partial_path']).read_bytes(), b'part')
        self.assertFalse((self.state/'install.lock').exists())

    def test_initial_receipt_failure_never_copies(self):
        with patch.object(intake, '_save', side_effect=OSError('journal full')), patch.object(intake, '_copy') as copy:
            with self.assertRaisesRegex(OSError, 'journal full') as error:self.run_intake()
        copy.assert_not_called(); self.assert_source(); self.assertFalse(self.target.exists())
        self.assertTrue(error.exception.__notes__); self.assertFalse((self.state/'install.lock').exists())

    def test_prepared_receipt_failure_never_publishes(self):
        save = intake._save
        def fail(path, record, phase, **updates):
            if phase == 'prepared':raise OSError('prepared receipt failed')
            return save(path, record, phase, **updates)
        with patch.object(intake, '_save', side_effect=fail), patch.object(intake, 'publish_verified') as publish:
            with self.assertRaisesRegex(OSError, 'prepared receipt'):self.run_intake()
        publish.assert_not_called(); self.assert_source(); self.assertFalse(self.target.exists())
        self.assertTrue(Path(self.journal()['partial_path']).exists())

    def test_final_receipt_failure_retains_copy_source_and_prepared_evidence(self):
        save = intake._save
        def fail(path, record, phase, **updates):
            if phase in ('copied', 'needs_inspection'):raise OSError('receipt unavailable')
            return save(path, record, phase, **updates)
        with patch.object(intake, '_save', side_effect=fail):
            with self.assertRaisesRegex(OSError, 'receipt unavailable'):self.run_intake()
        self.assert_source(); self.assertEqual(self.target.read_bytes(), self.body)
        self.assertEqual(self.journal()['status'], 'prepared')
        self.assertEqual(self.journal()['sha256'], hashlib.sha256(self.body).hexdigest())
        with self.assertRaisesRegex(ValueError, 'already exists'):self.run_intake()

    def test_baseexception_after_prepared_write_retains_known_intent(self):
        with patch.object(intake, 'publish_verified', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):self.run_intake()
        self.assert_source(); self.assertFalse(self.target.exists()); self.assertEqual(self.journal()['status'], 'prepared')
        self.assertTrue(Path(self.journal()['partial_path']).exists())

    def test_abrupt_process_exit_retains_lock_and_prepared_evidence(self):
        code = "import os,sys,pathlib;import model_intake as m;m.RESERVE_BYTES=0;m.publish_verified=lambda *a:os._exit(17);m.import_candidate(sys.argv[1],sys.argv[2],sys.argv[3],'loras','demo.safetensors',m.source_snapshot(sys.argv[3]),'header-hint')"
        result = subprocess.run([sys.executable, '-c', code, str(self.root), str(self.comfy), str(self.source)],
                                env=dict(os.environ, PYTHONPATH=str(ROOT/'app')), capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 17, result.stderr)
        self.assert_source(); self.assertFalse(self.target.exists()); self.assertEqual(self.journal()['status'], 'prepared')
        self.assertTrue(Path(self.journal()['partial_path']).exists()); self.assertTrue((self.state/'install.lock').exists())
        with self.assertRaisesRegex(ValueError, 'installer lock'):self.run_intake()

    def test_no_hardlink_support_has_no_rename_or_copy_overwrite_fallback(self):
        with patch('download_contracts.os.link', side_effect=OSError(errno.EPERM, 'unsupported')):
            with self.assertRaisesRegex(ValueError, 'no-clobber'):self.run_intake()
        self.assert_source(); self.assertFalse(self.target.exists())
        self.assertEqual(Path(self.journal()['partial_path']).read_bytes(), self.body)

    def test_publisher_links_only_same_directory_staging_not_browser_original(self):
        publish = intake.publish_verified
        def inspect(source, target, identity):
            self.assertEqual(source.parent, target.parent); self.assertNotEqual(source, self.source)
            self.assertFalse(os.path.samefile(source, self.source)); return publish(source, target, identity)
        with patch.object(intake, 'publish_verified', side_effect=inspect):self.run_intake()
        self.assert_source()

    def test_true_cross_device_source_when_available(self):
        other = Path('/dev/shm')
        if not other.is_dir() or other.stat().st_dev == self.root.stat().st_dev:self.skipTest('second filesystem unavailable')
        with tempfile.TemporaryDirectory(dir=other) as temp:
            source = Path(temp)/'demo.safetensors'; source.write_bytes(self.body)
            record = self.run_intake(source=source, identity=intake.source_snapshot(source))
            self.assertEqual(source.read_bytes(), self.body)
            self.assertNotEqual(source.stat().st_dev, self.target.stat().st_dev)
            self.assertEqual(record['status'], 'copied')

    def test_install_lease_conflict_has_no_copy_or_journal_and_keeps_owner_token(self):
        self.state.mkdir(parents=True); lease = InstallLease(self.state/'install.lock', 'other-owner')
        self.addCleanup(lease.release); before = (self.state/'install.lock').read_bytes()
        with self.assertRaisesRegex(ValueError, 'installer lock'):self.run_intake()
        self.assertEqual((self.state/'install.lock').read_bytes(), before); self.assert_source()
        self.assertFalse(self.target.exists()); self.assertFalse((self.state/'intake').exists())

    def test_other_process_lease_blocks_intake(self):
        self.state.mkdir(parents=True)
        code = "import pathlib,sys,time;from download_contracts import InstallLease;p=pathlib.Path(sys.argv[1]);l=InstallLease(p,'child');print('ready',flush=True);sys.stdin.readline();l.release()"
        env = dict(os.environ, PYTHONPATH=str(ROOT/'app'))
        child = subprocess.Popen([sys.executable, '-c', code, str(self.state/'install.lock')],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        try:
            self.assertEqual(child.stdout.readline().strip(), 'ready')
            with self.assertRaisesRegex(ValueError, 'installer lock'):self.run_intake()
            child.communicate('\n', timeout=5); self.assertEqual(child.returncode, 0)
        finally:
            if child.poll() is None:child.kill()
            child.communicate(timeout=5)
        self.assert_source(); self.assertFalse(self.target.exists())

    def test_active_intake_blocks_real_model_library_install(self):
        library = ModelLibrary(self.root, self.comfy)
        asset = {'id': 'test-pin', 'file': 'loras/other.safetensors', 'sha256': 'a'*64, 'bytes': 1, 'url': 'https://huggingface.co/x/y'}
        copy = intake._copy
        def observe(*args):
            with patch.object(library, '_validated_asset', return_value=asset), patch.object(library, '_install') as install:
                with self.assertRaisesRegex(ValueError, 'installer lock'):library.install('test-pin')
                install.assert_not_called()
            return copy(*args)
        with patch.object(intake, '_copy', side_effect=observe):self.run_intake()

    def test_unrelated_legacy_receipts_remain_byte_identical(self):
        self.state.mkdir(parents=True); shared = self.state/'receipts.json'; shared.write_bytes(b'[{"legacy":true}]')
        self.run_intake(); self.assertEqual(shared.read_bytes(), b'[{"legacy":true}]')
        second = self.downloads/'second.safetensors'; second.write_bytes(self.body)
        intake.import_candidate(self.root, self.comfy, second, 'loras', second.name, intake.source_snapshot(second), 'operator-selected')
        self.assertEqual(len(list((self.state/'intake').glob('*.json'))), 2)

    def link(self, target, source, directory=False):
        try:target.symlink_to(source, target_is_directory=directory)
        except (OSError, NotImplementedError):self.skipTest('symlink privilege unavailable')

    def test_symlink_source_refused(self):
        source = self.downloads/'linked.safetensors'; self.link(source, self.source)
        with self.assertRaisesRegex(ValueError, 'link'):self.run_intake(source=source)
        self.assert_source(); self.assertFalse(self.target.exists())

    def test_symlink_model_root_refused(self):
        outside = self.root/'outside'; outside.mkdir(); self.comfy.mkdir()
        self.link(self.comfy/'models', outside, True)
        with self.assertRaisesRegex(ValueError, 'link'):self.run_intake()
        self.assert_source(); self.assertEqual(list(outside.iterdir()), [])

    def test_symlink_destination_folder_refused(self):
        outside = self.root/'outside'; outside.mkdir(); self.target.parent.parent.mkdir(parents=True)
        self.link(self.target.parent, outside, True)
        with self.assertRaisesRegex(ValueError, 'link'):self.run_intake()
        self.assert_source(); self.assertEqual(list(outside.iterdir()), [])

    def test_broken_destination_symlink_refused(self):
        self.target.parent.mkdir(parents=True); self.link(self.target, self.root/'missing')
        with self.assertRaisesRegex(ValueError, 'link'):self.run_intake()
        self.assert_source(); self.assertTrue(self.target.is_symlink())

    def test_windows_junction_model_folder_refused(self):
        if os.name != 'nt':self.skipTest('Windows junction contract')
        outside = self.root/'outside'; outside.mkdir(); self.target.parent.parent.mkdir(parents=True)
        result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(self.target.parent), str(outside)], capture_output=True)
        if result.returncode:self.skipTest('junction privilege unavailable')
        try:
            with self.assertRaisesRegex(ValueError, 'junction'):self.run_intake()
            self.assertEqual(list(outside.iterdir()), []); self.assert_source()
        finally:self.target.parent.rmdir()

    def test_invalid_destination_names_and_folder_selection_refused(self):
        for name in ('../demo.safetensors', 'dir/demo.safetensors', 'NUL.safetensors', 'x.patch'):
            with self.subTest(name=name), self.assertRaises(ValueError):intake.target_path(self.comfy, 'loras', name)
        with self.assertRaises(ValueError):intake.target_path(self.comfy, 'unknown', 'x.safetensors')
        with self.assertRaisesRegex(ValueError, 'selection'):
            intake.import_candidate(self.root, self.comfy, self.source, 'loras', self.source.name, self.expected, 'unknown')
        self.assertFalse(self.target.exists())

    def test_header_inspection_change_does_not_create_a_valid_plan(self):
        read = cli.read_header
        def change(path):
            header = read(path); path.write_bytes(b'changed'); return header
        with patch.object(cli, 'read_header', side_effect=change):item = cli.plan([self.source])[0]
        self.assertIn('changed during header', item['error']); self.assertFalse(self.state.exists())

    def test_cli_copies_with_unique_receipt_and_preserves_original(self):
        output = io.StringIO()
        with patch.object(cli, 'ROOT', self.root), patch.object(cli, 'load_config', return_value={'comfy_root': str(self.comfy)}), redirect_stdout(output):
            self.assertEqual(cli.main(['--from', str(self.downloads)]), 0)
        self.assert_source(); self.assertEqual(self.target.read_bytes(), self.body)
        self.assertIn('1 copied', output.getvalue()); self.assertIn('Browser originals retained', output.getvalue())
        self.assertEqual(self.journal()['status'], 'copied'); self.assertFalse((self.state/'receipts.json').exists())

    def test_cli_dry_run_creates_no_receipt_lease_or_model_directory(self):
        with patch.object(cli, 'ROOT', self.root), patch.object(cli, 'load_config', return_value={'comfy_root': str(self.comfy)}), redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(['--from', str(self.downloads), '--dry-run']), 0)
        self.assert_source(); self.assertFalse(self.state.exists()); self.assertFalse(self.comfy.exists())


if __name__ == '__main__':unittest.main()
