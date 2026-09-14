"""Full-repository integration of the assistant with the existing metadata parser."""
import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image, PngImagePlugin
from studio_prompt import local_helper as h, reference_analysis as r, reference_assistant as cli


class ReferenceMetadataCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
    def inspect(self, *, metadata=None, kind='PNG', change=False):
        path = self.root / 'image'; image = Image.new('RGB', (4, 6))
        options = {}
        if metadata:
            info = PngImagePlugin.PngInfo()
            for key, value in metadata.items(): info.add_text(key, value)
            options['pnginfo'] = info
        image.save(path, format=kind, **options)
        request = r.new_request('', [{'id': 'picture-1', 'path': path.name,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'role_hint': 'auto'}])
        source = self.root / 'request.json'; source.write_text(json.dumps(request))
        if change: path.write_bytes(b'replaced')
        output = self.root / 'metadata.json'
        with patch.object(h, 'http_json') as call, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = cli.main(['inspect', '--workspace', str(self.root), '--request', str(source), '--output', str(output)])
            call.assert_not_called()
        return code, json.loads(output.read_text()) if output.exists() else None
    def test_png_claims_preserved_separately_from_visual_analysis(self):
        code, result = self.inspect(metadata={'parameters': 'blue coat, Seed: 42'})
        self.assertEqual(code, 0); inspection = result['references'][0]['inspection']
        self.assertEqual(inspection['entries'][0]['value'], 'blue coat, Seed: 42')
        self.assertEqual(inspection['entries'][0]['authority'], 'embedded_claim')
        self.assertFalse(inspection['workflow_executed']); self.assertFalse(result['generation_submitted'])
        self.assertEqual(result['references'][0]['source_sha256'], inspection['sha256'])
    def test_jpeg_missing_metadata_remains_missing(self):
        code, result = self.inspect(kind='JPEG'); self.assertEqual(code, 0)
        self.assertEqual(result['references'][0]['inspection']['status'], 'no_text_metadata')
    def test_embedded_graph_is_not_executed(self):
        graph = {'1': {'class_type': 'RunPython', 'inputs': {'code': 'raise RuntimeError("must not run")'}}}
        code, result = self.inspect(metadata={'prompt': json.dumps(graph)})
        self.assertEqual(code, 0); self.assertFalse(result['references'][0]['inspection']['workflow_executed'])
    def test_changed_source_produces_no_report(self):
        code, result = self.inspect(change=True); self.assertEqual(code, 2); self.assertIsNone(result)


if __name__ == '__main__': unittest.main()
