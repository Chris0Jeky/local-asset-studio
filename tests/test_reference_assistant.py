"""Executable CLI commands use real files and never implicitly run a generator."""
import contextlib
import copy
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from studio_prompt import reference_assistant as cli, reference_analysis as r, local_helper as h


class ReferenceAssistantTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); Image.new('RGB', (3, 5)).save(self.root / 'image.png')
        self.request = r.new_request('', [{'id': 'picture-1', 'path': 'image.png',
            'sha256': hashlib.sha256((self.root / 'image.png').read_bytes()).hexdigest(), 'role_hint': 'auto'}])
        answer = {'summary': 'A soft ink illustration', 'assumptions': [], 'questions': [], 'images': [
            {'reference_id': 'picture-1', 'suggested_role': 'style', 'description': 'A painted figure',
             'tags': ['ink'], 'facets': {'style': 'soft ink'}, 'uncertain_facets': [], 'unknowns': []}]}
        self.report = r.make_report(self.request, answer, [{'reference_id': 'picture-1',
            'source_sha256': self.request['references'][0]['sha256'], 'analysis_sha256': 'a' * 64, 'analysis_size': [3, 5]}])
        self.reqpath = self.root / 'request.json'; self.reqpath.write_text(json.dumps(self.request))
        self.reportpath = self.root / 'analysis.json'; self.reportpath.write_text(json.dumps({'analysis': self.report}))
    def invoke(self, *args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return cli.main(list(map(str, args)))
    def test_init_can_use_empty_brief_and_auto_roles(self):
        out = self.root / 'new-request.json'
        with patch.object(h, 'http_json') as call:
            self.assertEqual(self.invoke('init', '--workspace', self.root, '--image', 'image.png', '--output', out), 0)
            call.assert_not_called()
        self.assertEqual(json.loads(out.read_text()), self.request)
    def test_role_count_and_unsafe_image_rejected(self):
        for arguments in (['--role', 'style', '--role', 'pose'], ['--image', '../other.png']):
            out = self.root / 'bad.json'
            self.assertEqual(self.invoke('init', '--workspace', self.root, '--image', 'image.png', *arguments, '--output', out), 2)
            self.assertFalse(out.exists())
    def test_explicit_roles_and_original_words_retained(self):
        out = self.root / 'explicit.json'
        self.assertEqual(self.invoke('init', '--workspace', self.root, '--image', 'image.png', '--role', 'pose',
                                    '--brief', '  like this, please  ', '--output', out), 0)
        result = json.loads(out.read_text()); self.assertEqual(result['brief'], '  like this, please  ')
        self.assertEqual(result['references'][0]['role_hint'], 'pose')
    def test_review_then_edit_then_new_draft(self):
        review_path = self.root / 'review.json'; out = self.root / 'draft.json'
        with patch.object(h, 'http_json') as call:
            self.assertEqual(self.invoke('review', '--analysis', self.reportpath, '--output', review_path), 0)
            review = json.loads(review_path.read_text()); review['selections'][0]['overrides']['style'] = 'bold ink'
            review_path.write_text(json.dumps(review))
            self.assertEqual(self.invoke('draft', '--workspace', self.root, '--analysis', self.reportpath,
                                        '--review', review_path, '--output', out), 0)
            call.assert_not_called()
        result = json.loads(out.read_text()); self.assertIn('bold ink', result['intent']['facets']['style'])
        self.assertEqual(result['transfers'][0]['origin'], 'user_edit'); self.assertFalse(result['generation_submitted'])
    def test_existing_output_refused_before_analysis(self):
        out = self.root / 'existing.json'; out.write_text('KEEP')
        with patch.object(h, 'run_local') as call:
            self.assertEqual(self.invoke('analyze', '--workspace', self.root, '--request', self.reqpath,
                '--model', 'local-vlm', '--idle-confirmed', '--output', out), 2)
            call.assert_not_called()
        self.assertEqual(out.read_text(), 'KEEP')
    def test_analyze_is_explicit_and_uses_existing_helper_operation(self):
        out = self.root / 'result.json'
        with patch.object(h, 'run_local', return_value={'analysis': self.report}) as call:
            self.assertEqual(self.invoke('analyze', '--workspace', self.root, '--request', self.reqpath,
                '--model', 'local-vlm', '--idle-confirmed', '--output', out), 0)
        self.assertEqual(call.call_args.kwargs['operation'], 'references')
        self.assertIs(call.call_args.kwargs['include_images'], True); self.assertIs(call.call_args.kwargs['cache'], True)
    def test_missing_idle_confirmation_prevents_helper(self):
        with patch.object(h, 'run_local') as call:
            self.assertEqual(self.invoke('analyze', '--workspace', self.root, '--request', self.reqpath,
                '--model', 'local-vlm', '--output', self.root / 'no.json'), 2)
            call.assert_not_called()
    def test_changed_original_refuses_draft_and_preserves_analysis(self):
        before = self.reportpath.read_bytes(); review_path = self.root / 'review.json'
        review_path.write_text(json.dumps(r.review_template(self.report))); (self.root / 'image.png').write_bytes(b'changed')
        self.assertEqual(self.invoke('draft', '--workspace', self.root, '--analysis', self.reportpath,
                                    '--review', review_path, '--output', self.root / 'bad-draft.json'), 2)
        self.assertEqual(self.reportpath.read_bytes(), before)
    def test_subprocess_module_entrypoint(self):
        out = self.root / 'subprocess.json'
        result = subprocess.run([sys.executable, '-m', 'studio_prompt.reference_assistant', 'init', '--workspace', str(self.root),
            '--image', 'image.png', '--output', str(out)], cwd=Path(__file__).resolve().parents[1],
            capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr); self.assertEqual(json.loads(out.read_text()), self.request)


if __name__ == '__main__': unittest.main()
