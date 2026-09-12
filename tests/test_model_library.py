import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]/'app'))
import model_library as models


class Reply(io.BytesIO):
    status=200
    headers={}


class ModelLibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        (self.root/'models').mkdir();(self.root/'home/Downloads').mkdir(parents=True)
        self.body=b'small inert model fixture'
        self.asset={'id':'demo','file':'loras/demo.safetensors','bytes':len(self.body),'sha256':hashlib.sha256(self.body).hexdigest(),'url':'https://huggingface.co/example/pinned/demo.safetensors'}
        (self.root/'models/library.json').write_text(json.dumps({'assets':[self.asset]}))
        self.lib=models.ModelLibrary(self.root,self.root/'comfy')
        self.home=patch.object(Path,'home',return_value=self.root/'home');self.home.start()
        self.reserve=patch.object(models,'RESERVE_BYTES',0);self.reserve.start()
    def tearDown(self):
        self.home.stop();self.reserve.stop();self.temp.cleanup()
    def test_verified_download_then_inventory(self):
        with patch.object(models,'urlopen',return_value=Reply(self.body)) as request:
            receipt=self.lib.install('demo')
        self.assertEqual(receipt['status'],'installed');request.assert_called_once()
        self.assertEqual(self.lib.destination(self.asset).read_bytes(),self.body)
        self.assertTrue(self.lib.snapshot()['assets'][0]['verified'])
        self.assertFalse((self.lib.state/'install.lock').exists())
    def test_hash_failure_keeps_partial_and_existing_file_is_preserved(self):
        with patch.object(models,'urlopen',return_value=Reply(b'x'*len(self.body))):
            with self.assertRaisesRegex(ValueError,'checksum'):self.lib.install('demo')
        target=self.lib.destination(self.asset)
        self.assertFalse(target.exists());self.assertTrue(self.lib.partial_path(target).exists())
        target.write_bytes(b'user experiment')
        with self.assertRaisesRegex(ValueError,'preserved'):self.lib.install('demo')
        self.assertEqual(target.read_bytes(),b'user experiment')
    def test_resume_must_be_honored_and_preserves_partial(self):
        target=self.lib.destination(self.asset);target.parent.mkdir(parents=True)
        part=self.lib.partial_path(target);part.write_bytes(self.body[:5])
        with patch.object(models,'urlopen',return_value=Reply(self.body)):
            with self.assertRaisesRegex(ValueError,'honor resume'):self.lib.install('demo')
        self.assertEqual(part.read_bytes(),self.body[:5]);self.assertFalse(target.exists())
        response=Reply(self.body[5:]);response.status=206;response.headers={'Content-Range':f'bytes 5-{len(self.body)-1}/{len(self.body)}'}
        with patch.object(models,'urlopen',return_value=response):self.lib.install('demo')
        self.assertEqual(target.read_bytes(),self.body)
    def test_paths_space_and_concurrent_installer(self):
        for file in ('../outside.safetensors','loras/../../outside.safetensors','loras/file.exe'):
            with self.assertRaises(ValueError):self.lib.destination(dict(self.asset,file=file))
        with self.assertRaises(ValueError):self.lib.folder('../../outside')
        with patch.object(models,'RESERVE_BYTES',10**18),patch.object(models,'urlopen') as request:
            with self.assertRaisesRegex(ValueError,'disk space'):self.lib.install('demo')
            request.assert_not_called()
        (self.lib.state/'install.lock').write_text('123')
        with self.assertRaisesRegex(ValueError,'Another installer'):self.lib.start_install('demo')
        self.assertEqual((self.lib.state/'install.lock').read_text(),'123')
    def test_existing_browser_download_reuse_and_race_does_not_overwrite(self):
        local=self.root/'home/Downloads/demo.safetensors';local.write_bytes(self.body)
        target=self.lib.destination(self.asset)
        def appeared(*args):
            target.write_bytes(b'someone else')
            raise FileExistsError()
        with patch.object(models.os,'link',side_effect=appeared),patch.object(models,'urlopen') as request:
            with self.assertRaisesRegex(ValueError,'preserved'):self.lib.install('demo')
            request.assert_not_called()
        self.assertEqual(target.read_bytes(),b'someone else');self.assertEqual(local.read_bytes(),self.body)


class PinOnlyFolderTests(unittest.TestCase):
    """Detectors, GGUF backbones and .pth heads are pinned for verification, never auto-installed."""
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        (self.root/'models').mkdir()
        self.body=b'inert detector fixture'
        self.detector={'id':'detector','name':'hand detector','file':'ultralytics/bbox/hand.pt','bytes':len(self.body),
                       'sha256':hashlib.sha256(self.body).hexdigest(),'url':'','source':'','license':'apache-2.0',
                       'family':'Ultralytics detectors','trigger':'','terms':'pinned from the installed file'}
        self.adapter={'id':'adapter','name':'identity adapter','file':'ipadapter/plus.safetensors','bytes':len(self.body),
                      'sha256':hashlib.sha256(self.body).hexdigest(),'url':'https://huggingface.co/example/a/plus.safetensors',
                      'source':'https://huggingface.co/example/a','license':'apache-2.0','family':'IP-Adapter SDXL','trigger':''}
        self.unsourced={'id':'unsourced','name':'latent previewer','file':'vae_approx/taesd_decoder.safetensors',
                        'bytes':len(self.body),'sha256':hashlib.sha256(self.body).hexdigest(),'url':'','source':'',
                        'license':'','family':'Latent previews','trigger':'','terms':'provenance not recorded'}
        (self.root/'models/library.json').write_text(json.dumps({'assets':[self.detector,self.adapter,self.unsourced]}))
        self.lib=models.ModelLibrary(self.root,self.root/'comfy')
        self.home=patch.object(Path,'home',return_value=self.root/'home');self.home.start()
    def tearDown(self):self.home.stop();self.temp.cleanup()
    def test_new_folders_are_supported_and_stay_inside_the_model_root(self):
        for key in ('ipadapter','ultralytics','inpaint','vae_approx'):
            with self.subTest(folder=key):
                self.assertIn(key,models.FOLDERS)
                self.assertTrue(self.lib.folder(key).is_relative_to(self.lib.models))
        listed={f['id'] for f in self.lib.snapshot()['folders']}
        self.assertTrue({'ipadapter','ultralytics','inpaint','vae_approx'}<=listed)
    def test_detector_snapshot_reports_pin_only_and_installer_refuses_it(self):
        missing=self.lib.snapshot()['assets'][0]
        self.assertEqual((missing['installable'],missing['present'],missing['verification']),(False,False,'missing'))
        self.assertIn('safetensors',missing['install_note'])
        path=self.lib.locate(self.detector);path.parent.mkdir(parents=True);path.write_bytes(self.body)
        present=self.lib.snapshot()['assets'][0]
        self.assertEqual(present['path'],str(path))
        self.assertEqual((present['present'],present['size_matches'],present['verified']),(True,True,False))
        self.assertEqual(present['verification'],'pin-only-manual-verification')
        for start in (self.lib.start_install,self.lib.install):
            with self.assertRaisesRegex(ValueError,'safetensors'):start('detector')
        # A refusal must not leave an installer gate, a receipt or a partial behind.
        self.assertFalse((self.lib.state/'install.lock').exists())
        self.assertFalse((self.lib.state/'detector.json').exists())
        self.assertFalse(path.with_suffix('.pt.part').exists())
        self.assertEqual(path.read_bytes(),self.body)
    def test_safetensors_in_a_new_folder_stays_installable(self):
        item=self.lib.snapshot()['assets'][1]
        self.assertEqual((item['installable'],item['install_note']),(True,None))
        self.assertEqual(self.lib.destination(self.adapter),self.lib.locate(self.adapter))
    def test_missing_unsourced_pin_is_refused_before_any_download_state(self):
        item=self.lib.snapshot()['assets'][2]
        self.assertEqual((item['installable'],item['present']),(False,False))
        self.assertIn('curated source',item['install_note'])
        with patch.object(models,'urlopen') as request:
            for start in (self.lib.start_install,self.lib.install):
                with self.assertRaisesRegex(ValueError,'copy this file in by hand'):start('unsourced')
            request.assert_not_called()
        self.assertFalse((self.lib.state/'install.lock').exists())
        self.assertFalse((self.lib.state/'unsourced.json').exists())
        self.assertFalse(self.lib.locate(self.unsourced).parent.exists())
    def test_installed_unsourced_pin_still_verifies_without_a_url(self):
        """Pinning an unrecorded file is worth nothing if its hash can never be re-checked."""
        path=self.lib.locate(self.unsourced);path.parent.mkdir(parents=True);path.write_bytes(self.body)
        item=self.lib.snapshot()['assets'][2]
        self.assertEqual((item['installable'],item['install_note']),(True,None))
        with patch.object(models,'urlopen') as request:
            self.assertEqual(self.lib.install('unsourced')['status'],'installed')
            request.assert_not_called()
        self.assertTrue(self.lib.snapshot()['assets'][2]['verified'])
    def test_pinned_library_never_breaks_the_models_view(self):
        """Every shipped pin must resolve; one bad folder would make the whole snapshot raise."""
        library=json.loads((Path(__file__).parents[1]/'models/library.json').read_text(encoding='utf-8'))
        for asset in library['assets']:
            with self.subTest(asset=asset['id']):
                self.assertTrue(self.lib.locate(asset).is_relative_to(self.lib.models))


if __name__=='__main__':unittest.main()
