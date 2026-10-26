"""Run the real Qwen launcher against disposable inert checkouts, never ComfyUI."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class Qwen21LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='qwen launcher ');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.repo=self.root/'repository';self.checkout=self.root/'isolated checkout'
        self.script=self.repo/'scripts/qwen21-launch.py';self.script.parent.mkdir(parents=True)
        shutil.copyfile(ROOT/'scripts/qwen21-launch.py',self.script)
        self.references=self.repo/'examples/references';self.references.mkdir(parents=True)
        (self.references/'new-reference.png').write_bytes(b'inert new reference')
        (self.references/'existing-reference.png').write_bytes(b'example must not replace existing input')
        self.encoder=self.checkout/'comfy/text_encoders/qwen_image21.py';self.encoder.parent.mkdir(parents=True)
        self.encoder.write_bytes(b'# inert encoder presence marker\n')
        (self.checkout/'python_packages/comfy_kitchen').mkdir(parents=True)
        (self.checkout/'main.py').write_text(
            "import json,sys\nfrom pathlib import Path\n"
            "Path('launch-observed.json').write_text(json.dumps({'argv':sys.argv,'cwd':str(Path.cwd())}))\n")
    def run_launcher(self):
        return subprocess.run([sys.executable,str(self.script),'--comfy-root',str(self.checkout)],
                              cwd=self.repo,capture_output=True,text=True,timeout=10)
    def assert_refuses_before_staging_or_main(self):
        result=self.run_launcher()
        self.assertEqual(result.returncode,2,result.stdout+result.stderr)
        self.assertIn('missing or predates Qwen-Image-2.1',result.stderr)
        self.assertFalse((self.checkout/'input').exists())
        self.assertFalse((self.checkout/'launch-observed.json').exists())
    def test_missing_encoder_refuses_before_input_staging_or_main(self):
        self.encoder.unlink();self.assert_refuses_before_staging_or_main()
    def test_empty_encoder_refuses_before_input_staging_or_main(self):
        self.encoder.write_bytes(b'');self.assert_refuses_before_staging_or_main()
    def test_complete_checkout_preserves_launch_arguments_and_existing_input(self):
        inputs=self.checkout/'input';inputs.mkdir()
        existing=inputs/'existing-reference.png';existing.write_bytes(b'retained input')
        result=self.run_launcher()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        observed=json.loads((self.checkout/'launch-observed.json').read_text())
        self.assertEqual(Path(observed['cwd']),self.checkout)
        self.assertEqual(observed['argv'],[str(self.checkout/'main.py'),'--windows-standalone-build',
            '--disable-auto-launch','--disable-api-nodes','--preview-method','latent2rgb','--listen','127.0.0.1',
            '--port','8196','--reserve-vram','3','--disable-fast-disk','--disable-pinned-memory'])
        self.assertEqual(existing.read_bytes(),b'retained input')
        self.assertEqual((inputs/'new-reference.png').read_bytes(),b'inert new reference')


if __name__=='__main__':unittest.main()
