"""Real headless JSON transport must preserve Unicode on legacy Windows pipes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from studio_prompt.compiler import compile_brief
from studio_prompt.schema import new_brief

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT/'scripts/studio_prompt.py'


class PromptCLIUnicodeTests(unittest.TestCase):
    def run_cli(self, args, encoding):
        # Byte capture avoids decoding the child's output with the parent's locale.
        return subprocess.run([sys.executable, str(CLI), *map(str, args)], cwd=ROOT,
                              env={**os.environ, 'PYTHONIOENCODING': encoding + ':strict'},
                              capture_output=True, timeout=15)

    def test_compile_preserves_unicode_intent_and_hashes_in_ascii_compatible_pipes(self):
        brief = new_brief('成人の旅人, lumină, 漫画. A lantern labelled 星. 🐈')
        brief['tags'] = ['成人', 'lantern', 'ルーン']
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'brief.json'
            raw = json.dumps(brief, ensure_ascii=False).encode('utf-8'); path.write_bytes(raw)
            for encoding in ('ascii', 'cp1252'):
                for profile in ('sdxl-prose-v1', 'animagine4-tags-v1'):
                    with self.subTest(encoding=encoding, profile=profile):
                        result = self.run_cli(['compile', path, '--profile', profile], encoding)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        compiled = json.loads(result.stdout.decode('ascii'))
                        self.assertEqual(compiled, compile_brief(brief, profile))
                        self.assertEqual(compiled['intent'], brief)
                        self.assertFalse(compiled['generation_submitted'])
                        self.assertEqual(path.read_bytes(), raw)

    def test_utf8_output_file_and_pipe_have_identical_decoded_artifacts(self):
        brief = new_brief('A lantern engraved with 星, pădure and café.')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); path = root/'brief.json'; out = root/'compiled.json'
            path.write_bytes(json.dumps(brief, ensure_ascii=False).encode('utf-8'))
            piped = self.run_cli(['compile', path, '--profile', 'sdxl-prose-v1'], 'ascii')
            self.assertEqual(piped.returncode, 0, piped.stderr)
            written = self.run_cli(['compile', path, '--profile', 'sdxl-prose-v1', '--out', out], 'ascii')
            self.assertEqual(written.returncode, 0, written.stderr)
            self.assertEqual(written.stdout, b'')
            self.assertEqual(json.loads(piped.stdout.decode('ascii')), json.loads(out.read_text(encoding='utf-8')))
            before = out.read_bytes()
            refused = self.run_cli(['compile', path, '--profile', 'sdxl-prose-v1', '--out', out], 'ascii')
            self.assertEqual(refused.returncode, 2)
            self.assertFalse(json.loads(refused.stderr.decode('ascii'))['generation_submitted'])
            self.assertEqual(out.read_bytes(), before)

    def test_unicode_error_remains_one_json_diagnostic_not_stdout_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_cli(['compile', Path(tmp)/'不存在.json', '--profile', 'sdxl-prose-v1'], 'ascii')
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, b'')
            diagnostic = json.loads(result.stderr.decode('ascii'))
            self.assertFalse(diagnostic['generation_submitted'])
            self.assertIn('不存在.json', diagnostic['error'])


if __name__ == '__main__': unittest.main()
