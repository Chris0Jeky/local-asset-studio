"""Transfer/publication faults on tiny inert bytes; no real model download."""
import errno
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).parents[1]/'app'))
import model_library as models
import download_contracts as contracts


class Reply(io.BytesIO):
    def __init__(self,body,status=200,headers=None):
        super().__init__(body);self.status=status;self.headers=headers or {}


class InstallSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        (self.root/'models').mkdir();(self.root/'home/Downloads').mkdir(parents=True)
        self.body=b'0123456789 inert pinned model fixture'
        self.asset={'id':'demo','file':'loras/demo.safetensors','bytes':len(self.body),
                    'sha256':hashlib.sha256(self.body).hexdigest(),'url':'https://huggingface.co/example/pinned/demo.safetensors'}
        self.manifest=self.root/'models/library.json';self.manifest.write_text(json.dumps({'assets':[self.asset]}))
        self.lib=models.ModelLibrary(self.root,self.root/'comfy');self.target=self.lib.destination(self.asset)
        self.target.parent.mkdir(parents=True);self.part=self.lib.partial_path(self.target)
        self.home=patch.object(Path,'home',return_value=self.root/'home');self.home.start()
        self.reserve=patch.object(models,'RESERVE_BYTES',0);self.reserve.start()
    def tearDown(self):self.home.stop();self.reserve.stop();self.temp.cleanup()
    def receipt(self):return json.loads((self.lib.state/'demo.json').read_text())
    def install(self):
        with patch.object(models,'urlopen',return_value=Reply(self.body)):return self.lib.install('demo')
    def assert_released(self):
        self.assertFalse(self.lib.lock.locked());self.assertFalse((self.lib.state/'install.lock').exists())

    def test_download_publication_race_keeps_competing_file_and_verified_stage(self):
        link=os.link
        def race(source,target):
            self.target.write_bytes(b'another writer');return link(source,target)
        with patch.object(models,'urlopen',return_value=Reply(self.body)),patch.object(contracts.os,'link',side_effect=race):
            with self.assertRaisesRegex(ValueError,'both files preserved'):self.lib.install('demo')
        self.assertEqual(self.target.read_bytes(),b'another writer');self.assertEqual(self.part.read_bytes(),self.body)
        self.assertEqual(self.receipt()['status'],'failed');self.assert_released()

    def test_unsupported_atomic_publication_preserves_complete_stage(self):
        with patch.object(models,'urlopen',return_value=Reply(self.body)),patch.object(contracts,'os',wraps=os) as platform:
            platform.name='posix';platform.link.side_effect=OSError(errno.ENOTSUP,'no links')
            with self.assertRaisesRegex(ValueError,'explicit recovery'):self.lib.install('demo')
        self.assertFalse(self.target.exists());self.assertEqual(self.part.read_bytes(),self.body);self.assert_released()

    @unittest.skipUnless(os.name=='nt','Requires Windows no-clobber rename')
    def test_publish_verified_link_failure_on_nt_uses_rename(self):
        self.part.write_bytes(self.body);identity=contracts.file_identity(self.part)
        with patch.object(contracts.os,'name','nt'),patch.object(contracts.os,'link',side_effect=OSError('no links')):
            published=contracts.publish_verified(self.part,self.target,identity,self.asset['sha256'])
        self.assertEqual(self.target.read_bytes(),self.body);self.assertFalse(self.part.exists())
        self.assertEqual(published,contracts.file_identity(self.target))
        self.assertEqual(published['size'],identity['size']);self.assertEqual(published['mtime_ns'],identity['mtime_ns'])

    @unittest.skipUnless(os.name=='nt','Requires Windows no-clobber rename')
    def test_publish_verified_rename_race_preserves_both_files(self):
        self.part.write_bytes(self.body);identity=contracts.file_identity(self.part)
        rename=os.rename
        def race(source,target):
            self.target.write_bytes(b'another writer');return rename(source,target)
        with patch.object(contracts.os,'name','nt'),patch.object(contracts.os,'link',side_effect=OSError('no links')),patch.object(contracts.os,'rename',side_effect=race):
            with self.assertRaisesRegex(ValueError,'Destination appeared during publication; both files preserved'):
                contracts.publish_verified(self.part,self.target,identity,self.asset['sha256'])
        self.assertEqual(self.part.read_bytes(),self.body);self.assertEqual(self.target.read_bytes(),b'another writer')

    def test_rename_rejects_same_size_same_mtime_replacement(self):
        self.part.write_bytes(self.body);identity=contracts.file_identity(self.part);rename=os.rename
        saved=self.part.with_name('original-stage');replacement=b'x'*len(self.body)
        calls=[]
        def swap(source,target):
            calls.append((source,target))
            if len(calls)>1:return rename(source,target)
            rename(source,saved);source.write_bytes(replacement)
            os.utime(source,ns=(identity['mtime_ns'],identity['mtime_ns']))
            return rename(source,target)
        with patch.object(contracts.os,'name','nt'),patch.object(contracts.os,'link',side_effect=OSError('no links')),patch.object(contracts.os,'rename',side_effect=swap):
            with self.assertRaisesRegex(ValueError,'Published file does not match the verified digest') as caught:
                contracts.publish_verified(self.part,self.target,identity,self.asset['sha256'])
        # Unverified bytes never stay at the model's name: they go back to the staging name; the original is untouched.
        self.assertFalse(self.target.exists());self.assertEqual(self.part.read_bytes(),replacement);self.assertEqual(saved.read_bytes(),self.body)
        self.assertEqual(getattr(caught.exception,'unverified_path',None),self.part)

    def test_rename_rejects_a_write_during_the_digest(self):
        # A writer that changes the published file while it is being hashed must not leave a verified receipt behind.
        self.part.write_bytes(self.body);identity=contracts.file_identity(self.part);real=contracts.sha256
        def hash_then_write(path):
            digest=real(path);path.write_bytes(b'y'*len(self.body));return digest
        with patch.object(contracts.os,'name','nt'),patch.object(contracts.os,'link',side_effect=OSError('no links')),patch.object(contracts,'sha256',side_effect=hash_then_write):
            with self.assertRaisesRegex(ValueError,'Published file does not match the verified digest'):
                contracts.publish_verified(self.part,self.target,identity,self.asset['sha256'])
        self.assertFalse(self.target.exists());self.assertEqual(self.part.read_bytes(),b'y'*len(self.body))

    def failed_rollback(self,refused):
        # One refused rename models a transient/name conflict; persistent Windows share-delete denial refuses both.
        self.part.write_bytes(self.body);identity=contracts.file_identity(self.part);rename=os.rename;calls=[]
        def flaky(source,target):
            calls.append(target)
            if 1<len(calls)<=1+refused:raise PermissionError(13,'file in use')
            return rename(source,target)
        with patch.object(contracts.os,'name','nt'),patch.object(contracts.os,'link',side_effect=OSError('no links')),patch.object(contracts.os,'rename',side_effect=flaky),patch.object(contracts,'sha256',return_value='0'*64):
            with self.assertRaises(ValueError) as caught:contracts.publish_verified(self.part,self.target,identity,self.asset['sha256'])
        return caught.exception,calls

    def test_failed_move_back_quarantines_unverified_bytes(self):
        error,calls=self.failed_rollback(1)
        self.assertIn(str(calls[-1]),str(error))
        self.assertFalse(self.target.exists());self.assertFalse(self.part.exists())
        self.assertTrue(calls[-1].name.endswith('.unverified'));self.assertEqual(calls[-1].read_bytes(),self.body)
        self.lib._failed(self.asset,error)
        receipt=self.receipt()
        self.assertEqual(receipt.get('unverified_path'),str(calls[-1]))
        self.assertIn('manually',receipt.get('cleanup',''))
        self.assertIn(receipt['cleanup'],receipt['message'])
        self.assertEqual(calls[-1].read_bytes(),self.body)  # Reporting never deletes the retained bytes.

    def test_unmovable_unverified_bytes_fail_naming_the_published_path(self):
        error,calls=self.failed_rollback(2)
        self.assertIn('unverified bytes remain at '+str(self.target),str(error));self.assertEqual(len(calls),3)
        self.lib._failed(self.asset,error)
        receipt=self.receipt()
        self.assertEqual(receipt.get('unverified_path'),str(self.target))
        self.assertIn('Do not load',receipt['message']);self.assertIn('Close',receipt.get('cleanup',''))
        self.assertEqual(self.target.read_bytes(),self.body);self.assertFalse(self.part.exists())

    def test_long_unverified_path_and_cleanup_survive_failure_receipt_and_reload(self):
        # Paths can exceed the UI message budget. The receipt must keep the complete path separately.
        path=self.target.parent.joinpath(*(['deep-model-folder']*24),'demo.safetensors')
        cleanup='Do not load this model. Close any reader, then inspect and move or remove the unverified file manually before retrying.'
        error=ValueError('Unverified bytes remain at '+str(path)+'. '+cleanup)
        error.unverified_path=path;error.cleanup=cleanup
        self.lib._failed(self.asset,error)
        restored=models.ModelLibrary(self.root,self.root/'comfy').snapshot()['assets'][0]['download']
        self.assertEqual(restored.get('unverified_path'),str(path))
        self.assertEqual(restored.get('cleanup'),cleanup)
        self.assertIn(cleanup,restored['message']);self.assertLessEqual(len(restored['message']),300)

    def test_quarantine_preserves_a_competing_staging_file(self):
        self.part.write_bytes(self.body);identity=contracts.file_identity(self.part);rename=os.rename
        competing=b'another writer owns the staging name';calls=[]
        def conflicted(source,target):
            calls.append(target)
            if len(calls)==1:
                rename(source,target);source.write_bytes(competing);return
            if target==self.part:raise FileExistsError('staging name occupied')
            return rename(source,target)
        with patch.object(contracts.os,'name','nt'),patch.object(contracts.os,'link',side_effect=OSError('no links')),patch.object(contracts.os,'rename',side_effect=conflicted),patch.object(contracts,'sha256',return_value='0'*64):
            with self.assertRaises(ValueError) as caught:contracts.publish_verified(self.part,self.target,identity,self.asset['sha256'])
        self.lib._failed(self.asset,caught.exception)
        self.assertEqual(self.part.read_bytes(),competing);self.assertEqual(calls[-1].read_bytes(),self.body)
        self.assertEqual(self.receipt().get('unverified_path'),str(calls[-1]));self.assertFalse(self.target.exists())

    def test_rename_requires_digest_before_moving_stage(self):
        self.part.write_bytes(self.body);identity=contracts.file_identity(self.part)
        with patch.object(contracts.os,'name','nt'),patch.object(contracts.os,'link',side_effect=OSError('no links')):
            with self.assertRaisesRegex(ValueError,'digest'):
                contracts.publish_verified(self.part,self.target,identity)
        self.assertEqual(self.part.read_bytes(),self.body);self.assertFalse(self.target.exists())

    def test_browser_copy_failure_records_temp_and_retry_does_not_accumulate(self):
        local=self.root/'home/Downloads/demo.safetensors';local.write_bytes(self.body)
        self.part.write_bytes(b'stale partial');before=contracts.file_identity(self.part)
        for failure in ('copy','verification','publication'):
            with self.subTest(failure=failure):
                for attempt in range(2):
                    free=Mock(side_effect=[SimpleNamespace(free=10**9),SimpleNamespace(free=0)]) if failure=='copy' else Mock(return_value=SimpleNamespace(free=10**9))
                    verify=self.lib._verify
                    def check(path,asset):
                        if path!=local and failure=='verification':raise ValueError('verification failed')
                        return verify(path,asset)
                    with patch.object(models.os,'link',side_effect=OSError('no links')),patch.object(models.shutil,'disk_usage',free),patch.object(self.lib,'_verify',side_effect=check),patch.object(models,'publish_verified',side_effect=ValueError('publication failed')):
                        with self.assertRaises(ValueError):self.lib.install('demo')
                    temps=list(self.target.parent.glob(self.part.name+'.*.tmp'))
                    self.assertEqual(len(temps),1)
                    receipt=self.receipt();self.assertEqual(receipt['partial_path'],str(temps[0]))
                    self.assertEqual(receipt['bytes_done'],temps[0].stat().st_size);self.assertEqual(receipt['status'],'failed')
                    self.assertEqual(contracts.file_identity(self.part),before);self.assert_released()
        link=os.link
        def cross_device(source,target):
            if source==local:raise OSError(errno.EXDEV,'cross device')
            return link(source,target)
        with patch.object(models.os,'link',side_effect=cross_device):
            self.assertEqual(self.lib.install('demo')['status'],'installed')
        self.assertEqual(self.target.read_bytes(),self.body);self.assertEqual(self.part.read_bytes(),b'stale partial')
        self.assertEqual(list(self.target.parent.glob(self.part.name+'.*.tmp')),[])

    def test_retry_preserves_unrelated_temps_and_refuses_shared_temp(self):
        local=self.root/'home/Downloads/demo.safetensors';local.write_bytes(self.body);self.part.write_bytes(b'stale')
        unrelated=self.part.with_name(self.part.name+'.notes.tmp');unrelated.write_bytes(b'user notes')
        other=self.root/'other';other.write_bytes(b'user data')
        shared=self.part.with_name(self.part.name+'.'+'a'*32+'.tmp');os.link(other,shared)
        with patch.object(models.os,'link',side_effect=OSError('no links')):
            with self.assertRaisesRegex(ValueError,'unshared regular file'):self.lib.install('demo')
        self.assertEqual(shared.read_bytes(),b'user data');self.assertEqual(unrelated.read_bytes(),b'user notes')
        self.assertEqual(self.part.read_bytes(),b'stale');self.assertFalse(self.target.exists());self.assert_released()

    def test_publish_verified_link_failure_on_posix_refuses(self):
        self.part.write_bytes(self.body);identity=contracts.file_identity(self.part)
        with patch.object(contracts.os,'name','posix'),patch.object(contracts.os,'link',side_effect=OSError('no links')),patch.object(contracts.os,'rename') as rename:
            with self.assertRaisesRegex(ValueError,'explicit recovery'):contracts.publish_verified(self.part,self.target,identity)
        rename.assert_not_called();self.assertEqual(self.part.read_bytes(),self.body);self.assertFalse(self.target.exists())

    def test_every_resume_header_mismatch_preserves_original_partial(self):
        n=len(self.body);self.part.write_bytes(self.body[:5])
        replies=[(200,{}),(416,{}),(206,{}),(206,{'Content-Range':f'bytes 4-{n-1}/{n}'}),
                 (206,{'Content-Range':f'bytes 5-{n-2}/{n}'}),(206,{'Content-Range':f'bytes 5-{n-1}/{n+1}'}),
                 (206,{'Content-Range':f'bytes 5-{n-1}/*'}),
                 (206,{'Content-Range':f'bytes 5-{n-1}/{n}','Content-Length':'99'}),
                 (206,{'Content-Range':f'bytes 5-{n-1}/{n}','Content-Encoding':'gzip'})]
        for status,headers in replies:
            with self.subTest(status=status,headers=headers),patch.object(models,'urlopen',return_value=Reply(self.body[5:],status,headers)):
                with self.assertRaises(ValueError):self.lib.install('demo')
            self.assertEqual(self.part.read_bytes(),self.body[:5]);self.assertFalse(self.target.exists());self.assert_released()

    def test_bad_full_response_is_rejected_before_creating_partial(self):
        for status,headers in ((204,{}),(200,{'Content-Range':'bytes 0-1/2'}),(200,{'Content-Length':'bad'}),
                               (200,{'Content-Length':'0'}),(200,{'Content-Encoding':'br'})):
            with self.subTest(status=status,headers=headers),patch.object(models,'urlopen',return_value=Reply(self.body,status,headers)):
                with self.assertRaises(ValueError):self.lib.install('demo')
            self.assertFalse(self.part.exists());self.assertFalse(self.target.exists())

    def test_empty_partial_resumes_and_records_path_bound_verification(self):
        self.part.touch();receipt=self.install()
        self.assertEqual(self.target.read_bytes(),self.body);self.assertFalse(self.part.exists())
        self.assertEqual(receipt['version'],2);self.assertEqual(receipt['path'],str(self.target))
        self.assertEqual(receipt['file_identity'],contracts.file_identity(self.target))
        self.assertTrue(self.lib.snapshot()['assets'][0]['verified'])

    def test_exact_resume_requests_identity_and_remaining_range(self):
        self.part.write_bytes(self.body[:5]);n=len(self.body)
        with patch.object(models,'urlopen',return_value=Reply(self.body[5:],206,{'Content-Range':f'bytes 5-{n-1}/{n}','Content-Length':str(n-5)})) as request:
            self.lib.install('demo')
        self.assertEqual(request.call_args.args[0].get_header('Range'),'bytes=5-')
        self.assertEqual(request.call_args.args[0].get_header('Accept-encoding'),'identity')
        self.assertEqual(self.target.read_bytes(),self.body)

    def test_short_response_retains_exact_restart_offset(self):
        with patch.object(models,'urlopen',return_value=Reply(self.body[:5])):
            with self.assertRaisesRegex(ValueError,'checksum'):self.lib.install('demo')
        self.assertEqual(self.receipt()['bytes_done'],5);self.assertEqual(self.part.read_bytes(),self.body[:5])
        replacement=models.ModelLibrary(self.root,self.root/'comfy');n=len(self.body)
        with patch.object(models,'urlopen',return_value=Reply(self.body[5:],206,{'Content-Range':f'bytes 5-{n-1}/{n}'})):
            replacement.install('demo')
        self.assertEqual(self.target.read_bytes(),self.body)

    def test_oversized_chunk_is_not_appended(self):
        self.part.write_bytes(self.body[:5]);n=len(self.body)
        with patch.object(models,'urlopen',return_value=Reply(self.body[5:]+b'excess',206,{'Content-Range':f'bytes 5-{n-1}/{n}'})):
            with self.assertRaisesRegex(ValueError,'exceeds pinned'):self.lib.install('demo')
        self.assertEqual(self.part.read_bytes(),self.body[:5]);self.assertFalse(self.target.exists())

    def test_complete_partial_is_verified_without_network(self):
        self.part.write_bytes(self.body)
        with patch.object(models,'urlopen') as request:self.lib.install('demo')
        request.assert_not_called();self.assertEqual(self.target.read_bytes(),self.body)

    def test_corrupt_complete_partial_is_not_deleted_or_redownloaded(self):
        self.part.write_bytes(b'x'*len(self.body))
        with patch.object(models,'urlopen') as request:
            with self.assertRaisesRegex(ValueError,'checksum'):self.lib.install('demo')
        request.assert_not_called();self.assertEqual(self.part.read_bytes(),b'x'*len(self.body));self.assertFalse(self.target.exists())

    def test_disk_drop_during_transfer_preserves_stage_and_failure(self):
        with patch.object(models.shutil,'disk_usage',side_effect=[SimpleNamespace(free=10**9),SimpleNamespace(free=0)]),patch.object(models,'urlopen',return_value=Reply(self.body)):
            with self.assertRaisesRegex(ValueError,'during transfer'):self.lib.install('demo')
        self.assertFalse(self.target.exists());self.assertEqual(self.part.read_bytes(),b'');self.assertEqual(self.receipt()['bytes_done'],0);self.assert_released()

    def test_replaced_same_size_same_mtime_file_invalidates_receipt(self):
        self.install();before=self.target.stat();replacement=self.target.with_suffix('.replacement')
        replacement.write_bytes(b'x'*len(self.body));os.utime(replacement,ns=(before.st_atime_ns,before.st_mtime_ns));os.replace(replacement,self.target)
        self.assertFalse(self.lib.snapshot()['assets'][0]['verified'])
        self.assertEqual(self.lib.snapshot()['assets'][0]['verification'],'explicit-reverification-required')

    def test_other_backend_root_cannot_reuse_receipt(self):
        self.install();other=models.ModelLibrary(self.root,self.root/'other-comfy');target=other.destination(self.asset)
        target.parent.mkdir(parents=True);os.link(self.target,target)
        self.assertFalse(other.snapshot()['assets'][0]['verified'])

    def test_legacy_receipt_requires_explicit_rehash_without_download(self):
        self.target.write_bytes(self.body)
        self.lib._record('demo',status='installed',sha256=self.asset['sha256'],mtime_ns=self.target.stat().st_mtime_ns)
        self.assertFalse(self.lib.snapshot()['assets'][0]['verified'])
        with patch.object(models,'urlopen') as request:self.lib.install('demo')
        request.assert_not_called();self.assertTrue(self.lib.snapshot()['assets'][0]['verified'])

    def test_browser_hardlink_reuse_and_later_shared_write(self):
        local=self.root/'home/Downloads/demo.safetensors';local.write_bytes(self.body)
        with patch.object(models,'urlopen') as request:self.lib.install('demo')
        request.assert_not_called();self.assertTrue(os.path.samefile(local,self.target))
        local.write_bytes(b'x'*len(self.body));os.utime(local,ns=(1,2))
        self.assertFalse(self.lib.snapshot()['assets'][0]['verified'])

    def test_cross_device_browser_copy_uses_verified_noclobber_publication(self):
        local=self.root/'home/Downloads/demo.safetensors';local.write_bytes(self.body);link=os.link
        def cross_device(source,target):
            if Path(source)==local:raise OSError(errno.EXDEV,'cross device')
            return link(source,target)
        with patch.object(models.os,'link',side_effect=cross_device),patch.object(models,'urlopen') as request:self.lib.install('demo')
        request.assert_not_called();self.assertEqual(local.read_bytes(),self.body);self.assertEqual(self.target.read_bytes(),self.body)
        self.assertFalse(os.path.samefile(local,self.target));self.assertFalse(self.part.exists())

    def test_cross_device_copy_race_preserves_both_sources(self):
        local=self.root/'home/Downloads/demo.safetensors';local.write_bytes(self.body);link=os.link
        def cross_device(source,target):
            if Path(source)==local:raise OSError(errno.EXDEV,'cross device')
            self.target.write_bytes(b'another writer');return link(source,target)
        with patch.object(models.os,'link',side_effect=cross_device):
            with self.assertRaisesRegex(ValueError,'both files preserved'):self.lib.install('demo')
        self.assertEqual(local.read_bytes(),self.body);self.assertEqual(self.part.read_bytes(),self.body);self.assertEqual(self.target.read_bytes(),b'another writer')

    @unittest.skipUnless(os.name=='nt','Requires Windows no-clobber rename')
    def test_browser_copy_with_stale_part_uses_temp_and_preserves_partial(self):
        local=self.root/'home/Downloads/demo.safetensors';local.write_bytes(self.body)
        self.part.write_bytes(b'stale partial');before=contracts.file_identity(self.part)
        with patch.object(models.os,'link',side_effect=OSError('no links')),patch.object(models,'urlopen') as request:
            receipt=self.lib.install('demo')
        request.assert_not_called();self.assertEqual(receipt['status'],'installed')
        self.assertEqual(local.read_bytes(),self.body);self.assertEqual(self.target.read_bytes(),self.body)
        self.assertEqual(self.part.read_bytes(),b'stale partial');self.assertEqual(contracts.file_identity(self.part),before)
        self.assertEqual(set(self.target.parent.iterdir()),{self.target,self.part})
        self.assertTrue(self.lib.snapshot()['assets'][0]['verified']);self.assert_released()

    def test_change_while_hashing_is_not_verified(self):
        self.target.write_bytes(self.body)
        def changed(path):
            path.write_bytes(b'x'*len(self.body));os.utime(path,ns=(1,2));return self.asset['sha256']
        with patch.object(models,'sha256',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'changed while hashing'):self.lib.install('demo')
        self.assertEqual(self.receipt()['status'],'failed');self.assert_released()

    def test_invalid_identifiers_pins_and_portable_paths(self):
        for value in ('../demo','/tmp/demo','demo.json','',None):
            with self.subTest(value=value),self.assertRaises(ValueError):self.lib.start_install(value)
        for size in (True,0,-1,1.5,'20'):
            with self.subTest(size=size),self.assertRaises(ValueError):contracts.validate_pins(dict(self.asset,bytes=size))
        for value in ('../x.safetensors','loras/../x.safetensors','C:/x.safetensors','loras\\x.safetensors',
                      '/loras/x.safetensors','loras//x.safetensors','loras/NUL.safetensors','loras/x:stream.safetensors','loras./x.safetensors'):
            with self.subTest(value=value),self.assertRaises(ValueError):self.lib.destination(dict(self.asset,file=value))
        self.assert_released()

    def test_partial_hardlink_cannot_modify_another_file(self):
        other=self.root/'owned-by-user';other.write_bytes(self.body[:5]);os.link(other,self.part)
        with patch.object(models,'urlopen') as request:
            with self.assertRaisesRegex(ValueError,'unshared'):self.lib.install('demo')
        request.assert_not_called();self.assertEqual(other.read_bytes(),self.body[:5]);self.assertTrue(self.part.exists());self.assert_released()

    def test_partial_symlink_is_preserved(self):
        other=self.root/'owned-by-user';other.write_bytes(self.body[:5])
        try:self.part.symlink_to(other)
        except OSError as exc:self.skipTest('Symlink creation unavailable: '+str(exc))
        with patch.object(models,'urlopen') as request:
            with self.assertRaisesRegex(ValueError,'link'):self.lib.install('demo')
        request.assert_not_called();self.assertTrue(self.part.is_symlink());self.assertEqual(other.read_bytes(),self.body[:5]);self.assert_released()

    def test_thread_start_failure_releases_both_gates(self):
        with patch.object(models.threading.Thread,'start',side_effect=RuntimeError('no worker')):
            with self.assertRaisesRegex(RuntimeError,'no worker'):self.lib.start_install('demo')
        self.assert_released();self.assertEqual(self.receipt()['status'],'failed')

    def test_receipt_write_failure_does_not_mask_error_or_wedge_gate(self):
        with patch.object(self.lib,'_record',side_effect=OSError('disk full')),patch.object(models.threading.Thread,'start') as thread:
            with self.assertRaisesRegex(OSError,'disk full'):self.lib.start_install('demo')
        thread.assert_not_called();self.assert_released()

    def test_two_instances_cannot_clobber_active_receipt(self):
        other=models.ModelLibrary(self.root,self.root/'comfy')
        with patch.object(models.threading,'Thread') as thread:
            queued=self.lib.start_install('demo');before=(self.lib.state/'demo.json').read_bytes()
            with self.assertRaisesRegex(ValueError,'Another installer'):other.start_install('demo')
            self.assertEqual((self.lib.state/'demo.json').read_bytes(),before);self.assertFalse(other.lock.locked())
            with patch.object(models,'urlopen',return_value=Reply(self.body)):thread.call_args.kwargs['target']()
        self.assertEqual(queued['status'],'queued');self.assert_released();self.assertEqual(self.receipt()['status'],'installed')

    def test_async_worker_uses_reserved_manifest_snapshot(self):
        with patch.object(models.threading,'Thread') as thread:
            self.lib.start_install('demo')
            self.manifest.write_text(json.dumps({'assets':[dict(self.asset,file='loras/changed.safetensors')]}))
            with patch.object(models,'urlopen',return_value=Reply(self.body)):thread.call_args.kwargs['target']()
        self.assertEqual(self.target.read_bytes(),self.body);self.assertFalse((self.target.parent/'changed.safetensors').exists());self.assert_released()

    def test_worker_failure_keeps_progress_and_releases_gates(self):
        with patch.object(models.threading,'Thread') as thread:
            self.lib.start_install('demo')
            with patch.object(models,'urlopen',return_value=Reply(self.body[:5])):thread.call_args.kwargs['target']()
        self.assertEqual(self.receipt()['status'],'failed');self.assertEqual(self.receipt()['bytes_done'],5);self.assert_released()

    def test_replaced_lease_and_corrupt_locks_are_not_deleted(self):
        path=self.lib.state/'install.lock';lease=contracts.InstallLease(path,'demo')
        path.write_text(json.dumps({'token':'another owner'}));self.assertFalse(lease.release());self.assertTrue(path.exists())
        path.write_text('interrupted write')
        with self.assertRaisesRegex(ValueError,'Another installer'):self.lib.start_install('demo')
        self.assertEqual(path.read_text(),'interrupted write');self.assertFalse(self.lib.lock.locked())

    def test_snapshot_performs_no_network_or_hashing(self):
        self.install()
        with patch.object(models,'sha256') as digest,patch.object(models,'urlopen') as request:self.lib.snapshot()
        digest.assert_not_called();request.assert_not_called()


if __name__=='__main__':unittest.main()
