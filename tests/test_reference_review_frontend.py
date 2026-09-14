import shutil
import subprocess
import unittest
from pathlib import Path


class ReferenceReviewFrontendTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js required')
    def test_current_prompt_draft_owns_apply_and_undo(self):
        result = subprocess.run([shutil.which('node'), str(Path(__file__).with_name('reference_review_state.cjs'))],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Reference review draft guards passed', result.stdout)

    def test_raw_import_is_strict_and_preview_echoes_the_exact_base(self):
        import json
        from test_reference_review import ReferenceReviewTests
        from studio_prompt.http_extension import dispatch
        fixture = ReferenceReviewTests(); fixture.setUp()
        result = dispatch('/api/prompt/reference-review/inspect', {'analysis_json': json.dumps(fixture.report)})
        self.assertEqual(result['analysis'], fixture.report)
        duplicate = '{"analysis":' + json.dumps(fixture.report) + ',"analysis":' + json.dumps(fixture.report) + '}'
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            dispatch('/api/prompt/reference-review/inspect', {'analysis_json': duplicate})
        self.assertEqual(fixture.preview()['base_intent'], fixture.intent)

    def test_existing_tag_order_and_duplicate_entries_are_not_an_unrequested_edit(self):
        from test_reference_review import ReferenceReviewTests
        fixture = ReferenceReviewTests(); fixture.setUp()
        fixture.intent['tags'] = ['existing', 'existing']
        fixture.intent['locked'].append('tags')
        self.assertEqual(fixture.preview()['intent']['tags'], ['existing', 'existing'])

    def test_adopting_instruction_does_not_hide_an_oversized_current_field(self):
        from test_reference_review import ReferenceReviewTests
        fixture = ReferenceReviewTests(); fixture.setUp()
        fixture.intent['brief'] = ' ' * 4001; fixture.payload['adopt_brief'] = True
        with self.assertRaises(ValueError): fixture.preview()

    @unittest.skipUnless(shutil.which('node'), 'Node.js required')
    def test_panel_preserves_reselected_edits_and_serializes_validation(self):
        import json
        import tempfile
        from test_reference_review import ReferenceReviewTests
        fixture = ReferenceReviewTests(); fixture.setUp()
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / 'fixture.json'
            file.write_text(json.dumps({'report': fixture.report, 'review': fixture.review, 'images': fixture.images}))
            result = subprocess.run([shutil.which('node'), str(Path(__file__).with_name('reference_review_panel.cjs')), str(file)],
                                    capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('single-flight guards passed', result.stdout)

    def test_panel_html_read_is_independent_of_windows_default_encoding(self):
        from unittest.mock import patch
        original = Path.read_text
        def windows_default(path, *args, **kwargs):
            kwargs.setdefault('encoding', 'cp1252')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'read_text', windows_default):
            self.test_review_panel_is_loaded_with_the_existing_prompt_lab()

    def test_review_panel_is_loaded_with_the_existing_prompt_lab(self):
        root = Path(__file__).resolve().parents[1] / 'app/static'
        page = (root / 'prompt-lab.html').read_text(encoding='utf-8')
        self.assertIn('id="reference-review"', page)
        self.assertIn('src="/reference-review.js"', page)
        self.assertLess(page.index('src="/prompt-lab.js"'), page.index('src="/reference-review.js"'))


if __name__ == '__main__': unittest.main()
