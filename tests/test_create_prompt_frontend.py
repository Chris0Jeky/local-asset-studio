"""Shared Create readiness and explicit-submission contracts, without generation."""
from html.parser import HTMLParser
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class HeadingText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inside = False
        self.text = ''

    def handle_starttag(self, tag, attrs):
        if tag == 'h1':
            self.inside = True

    def handle_endtag(self, tag):
        if tag == 'h1':
            self.inside = False

    def handle_data(self, data):
        if self.inside:
            self.text += data


class CreatePromptTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node required for frontend contracts')
    def test_shared_readiness_and_submission(self):
        result = subprocess.run(['node', '--test', 'tests/create_prompt_contracts.cjs'],
                                cwd=ROOT, capture_output=True, text=True, timeout=20)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_hero_sentences_have_a_text_boundary_without_relying_on_visual_line_breaks(self):
        heading = HeadingText()
        heading.feed((ROOT / 'app/static/index.html').read_text(encoding='utf-8'))
        self.assertIn('Follow the idea. Make something yours.', ' '.join(heading.text.split()))
