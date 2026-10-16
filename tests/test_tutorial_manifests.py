"""Repository tutorial manifests describe Git bytes, not Windows checkout newlines."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = ROOT / 'docs/adaptive-studio/assets/production'


def file_bytes(path):
    try:
        return subprocess.check_output(
            ['git', 'show', 'HEAD:' + path.relative_to(ROOT).as_posix()], cwd=ROOT,
            stderr=subprocess.PIPE)
    except FileNotFoundError:
        data = path.read_bytes()
        try:
            data.decode('utf-8')
        except UnicodeDecodeError:
            return data
        return data.replace(b'\r\n', b'\n')


class TutorialManifestTests(unittest.TestCase):
    def test_repository_manifests(self):
        manifests = list(PRODUCTION.rglob('FILES.json'))
        self.assertTrue(manifests)
        for manifest in manifests:
            for name, expected in json.loads(manifest.read_text(encoding='utf-8')).items():
                with self.subTest(manifest=manifest.relative_to(ROOT).as_posix(), file=name):
                    data = file_bytes(manifest.parent / name)
                    self.assertEqual(expected, {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})

    def test_git_unavailable_normalizes_text_only(self):
        with patch('subprocess.check_output', side_effect=FileNotFoundError):
            for source, expected in ((b'a\r\nb\r\n', b'a\nb\n'), (b'\x89PNG\r\n\x1a\n', b'\x89PNG\r\n\x1a\n')):
                with self.subTest(source=source), patch.object(Path, 'read_bytes', return_value=source):
                    self.assertEqual(file_bytes(ROOT / 'example'), expected)

    def test_git_errors_are_not_silently_ignored(self):
        with patch('subprocess.check_output', side_effect=subprocess.CalledProcessError(128, 'git')):
            with self.assertRaises(subprocess.CalledProcessError):
                file_bytes(ROOT / 'missing')

    def test_recorder_requires_matching_workspace_before_page_creation(self):
        source = (PRODUCTION / '20261013-adapter-tutorial/record_adapter_strength.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'require_workspace')
        namespace = {'Path': Path}
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<workspace guard>', 'exec'), namespace)
        require = namespace['require_workspace']
        require({'app': 'local-asset-studio', 'workspace': str(ROOT / 'app/..')}, ROOT)
        for identity in ({'app': 'local-asset-studio', 'workspace': str(ROOT / 'other')}, {'app': 'local-asset-studio'}, {'app': 'other', 'workspace': str(ROOT)}):
            with self.subTest(identity=identity), self.assertRaisesRegex(ValueError, 'does not match --repo-root.*refusing to record'):
                require(identity, ROOT)
        self.assertLess(source.index('require_workspace(identity_response.json(),repo)'), source.index('page=context.new_page()'))
        self.assertIn('Full editor — every setting for one recipe', source)


if __name__ == '__main__':
    unittest.main()
