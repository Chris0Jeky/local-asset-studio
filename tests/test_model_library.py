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


if __name__=='__main__':unittest.main()
