"""Run the MOSS launcher against disposable inert checkouts, never ComfyUI."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
RUNNER='''import os,runpy,sys
from pathlib import Path
from unittest.mock import patch
script,checkout,observation,fault,*extra=sys.argv[1:]
encoder=Path(checkout)/'comfy/text_encoders/moss_image.py'
original_stat=Path.stat;original_chdir=os.chdir
def observed_stat(path,*args,**kwargs):
    if fault=='encoder-stat-error' and path==encoder:raise PermissionError('injected encoder stat refusal')
    return original_stat(path,*args,**kwargs)
def observed_chdir(path):
    Path(observation).write_text(str(path))
    return original_chdir(path)
sys.argv=[script,'--comfy-root',checkout,*extra]
with patch.object(Path,'stat',observed_stat),patch.object(os,'chdir',observed_chdir):
    runpy.run_path(script,run_name='__main__')
'''


class MossLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='moss launcher ');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.repo=self.root/'repository';self.checkout=self.root/'isolated checkout'
        self.script=self.repo/'scripts/moss-launch.py';self.script.parent.mkdir(parents=True)
        shutil.copyfile(ROOT/'scripts/moss-launch.py',self.script)
        self.encoder=self.checkout/'comfy/text_encoders/moss_image.py';self.encoder.parent.mkdir(parents=True)
        self.encoder.write_bytes(b'# inert encoder presence marker\n')
        (self.checkout/'python_packages/comfy_kitchen').mkdir(parents=True)
        self.chdir_marker=self.root/'changed-directory.txt'
        (self.checkout/'main.py').write_text(
            "import json,sys\nfrom pathlib import Path\n"
            "Path('launch-observed.json').write_text(json.dumps({'argv':sys.argv,'cwd':str(Path.cwd()),'path':sys.path[:2]}))\n")
    def run_launcher(self,*extra,fault='none'):
        return subprocess.run([sys.executable,'-c',RUNNER,str(self.script),str(self.checkout),str(self.chdir_marker),fault,*extra],
                              cwd=self.repo,capture_output=True,text=True,timeout=10)
    def assert_refuses_before_directory_change_or_main(self,**kwargs):
        result=self.run_launcher(**kwargs)
        self.assertEqual(result.returncode,2,result.stdout+result.stderr)
        self.assertIn('missing or predates MOSS-Image',result.stderr)
        self.assertFalse(self.chdir_marker.exists())
        self.assertFalse((self.checkout/'input').exists())
        self.assertFalse((self.checkout/'launch-observed.json').exists())
    def test_missing_encoder_refuses_before_directory_change_or_main(self):
        self.encoder.unlink();self.assert_refuses_before_directory_change_or_main()
    def test_empty_encoder_refuses_before_directory_change_or_main(self):
        self.encoder.write_bytes(b'');self.assert_refuses_before_directory_change_or_main()
    def test_encoder_stat_error_refuses_before_directory_change_or_main(self):
        self.assert_refuses_before_directory_change_or_main(fault='encoder-stat-error')
    def test_complete_checkout_preserves_arguments_overlay_and_existing_input(self):
        inputs=self.checkout/'input';inputs.mkdir()
        existing=inputs/'existing-reference.png';existing.write_bytes(b'retained input')
        for extra,reserve in (((),'2'),(('--reserve-vram','1.25'),'1.25')):
            with self.subTest(extra=extra):
                result=self.run_launcher(*extra)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                observed=json.loads((self.checkout/'launch-observed.json').read_text())
                self.assertEqual(Path(observed['cwd']),self.checkout)
                self.assertEqual(Path(self.chdir_marker.read_text()),self.checkout)
                self.assertEqual(observed['path'],[str(self.checkout),str(self.checkout/'python_packages')])
                self.assertEqual(observed['argv'],[str(self.checkout/'main.py'),'--windows-standalone-build',
                    '--disable-auto-launch','--disable-api-nodes','--preview-method','latent2rgb','--listen','127.0.0.1',
                    '--port','8198','--reserve-vram',reserve,'--disable-pinned-memory'])
                self.assertEqual(existing.read_bytes(),b'retained input')


if __name__=='__main__':unittest.main()
