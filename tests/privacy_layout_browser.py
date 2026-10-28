"""Render exact privacy markup/styles without HTTP, storage or generation.

Runtime privacy semantics remain covered by private_creation_browser.py.
"""
import os
from pathlib import Path
import re
import shutil
import unittest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class PrivacyLayout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        executable = os.environ.get('STUDIO_BROWSER_EXECUTABLE') or shutil.which('chromium')
        cls.browser = cls.pw.chromium.launch(**({'executable_path': executable} if executable else {}))
        index = (ROOT / 'app/static/index.html').read_text(encoding='utf-8')
        bar = re.search(r'<section class="privacy-bar".*?</section>', index, re.S).group(0)
        # Preserve shipped siblings: the hidden hero separates the bar from main.
        between = index.split(bar, 1)[1].split('<main', 1)[0]
        styles = ''.join('<style>' + (ROOT / 'app/static' / name).read_text(encoding='utf-8') + '</style>'
                         for name in ('style.css', 'privacy.css', 'studio.css', 'workshop.css'))
        cls.html = ('<!doctype html><html lang="en"><head><meta charset="utf-8">' + styles
                    + '</head><body class="studio-shell studio-main workshop-active">' + bar
                    + between + '<main id="studioMain"><h1>Full editor</h1><textarea aria-label="Prompt"></textarea></main></body></html>')

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def setUp(self):
        self.page = self.browser.new_page(viewport={'width': 1440, 'height': 900})
        self.page.route('**/*', lambda route: route.abort())
        self.page.set_content(self.html)

    def tearDown(self):
        self.page.close()

    def test_desktop_toolbar_and_editor_keep_the_compact_budget(self):
        for text in ('This creation is regular.',
                     'This creation is private. It stays out of Regular history and Library.'):
            with self.subTest(status=text):
                self.page.locator('#privacyStatus').evaluate('(el,text)=>{el.textContent=text;}', text)
                bar = self.page.locator('.privacy-bar').bounding_box()
                self.assertLessEqual(bar['height'], 56, 'Do not spend a second toolbar row on status alone')
                self.assertEqual(self.page.locator('#studioMain').evaluate('(el)=>getComputedStyle(el).paddingTop'), '16px')
                for selector in ('#privateSession', '#creationPrivacy', '[data-privacy-scope]', '#privacyStatus', '.privacy-bar summary'):
                    for item in self.page.locator(selector).all():
                        self.assertTrue(item.is_visible(), selector)
                        box = item.bounding_box()
                        self.assertGreaterEqual(box['y'], bar['y'])
                        self.assertLessEqual(box['y'] + box['height'], bar['y'] + bar['height'])

    def test_controls_and_help_remain_keyboard_reachable_without_overflow(self):
        for width in (1440, 1100, 900, 390, 320):
            with self.subTest(width=width):
                self.page.set_viewport_size({'width': width, 'height': 900})
                self.page.set_content(self.html)
                self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), width)
                self.page.locator('#privateSession').focus()
                for selector in ('#creationPrivacy', '[data-privacy-scope="regular"]',
                                 '[data-privacy-scope="private"]', '[data-privacy-scope="all"]', '.privacy-bar summary'):
                    self.page.keyboard.press('Tab')
                    self.assertTrue(self.page.locator(selector).evaluate('(el)=>el===document.activeElement'), selector)
                self.page.keyboard.press('Space')
                self.assertTrue(self.page.locator('.privacy-bar details').evaluate('(el)=>el.open'))
                self.assertTrue(self.page.locator('.privacy-bar details p').is_visible())
                self.assertIn('not encryption', self.page.locator('.privacy-bar details p').inner_text())
                self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), width)
                self.page.keyboard.press('Space')
                self.assertFalse(self.page.locator('.privacy-bar details').evaluate('(el)=>el.open'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
