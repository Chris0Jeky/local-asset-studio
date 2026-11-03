"""Exercise the shipped privacy bar and shell with disposable browser storage."""
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
        styles = ''.join('<style>' + (ROOT / 'app/static' / name).read_text(encoding='utf-8') + '</style>'
                         for name in ('style.css', 'privacy.css', 'studio.css', 'workshop.css', 'studio-navigation.css'))
        scripts = ''.join('<script>' + (ROOT / 'app/static' / name).read_text(encoding='utf-8') + '</script>'
                          for name in ('studio-core.js', 'studio-shell.js', 'privacy.js'))
        views = ''.join('<section id="' + name + 'View"' + (' hidden' if name != 'create' else '')
                        + '><div class="view-heading"><h1>' + name + '</h1></div><textarea aria-label="Prompt"></textarea></section>'
                        for name in ('create', 'make', 'assets', 'production', 'models', 'learn', 'briefs', 'home'))
        cls.html = ('<!doctype html><html lang="en"><head><meta charset="utf-8">' + styles
                    + '</head><body class="studio-shell studio-main workshop-active">' + bar
                    + '<div id="health" class="pill">ComfyUI connected</div><main id="studioMain">'
                    + views + '</main>' + scripts + '</body></html>')

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def setUp(self):
        self.page = self.browser.new_page(viewport={'width': 1440, 'height': 900})
        self.page.route('**/*', lambda route: route.fulfill(body=self.html, content_type='text/html')
                        if route.request.is_navigation_request() else route.abort())
        self.page.goto('http://privacy.test/#create')

    def view(self, name):
        self.page.evaluate('name=>{document.querySelectorAll("main>section").forEach(el=>el.hidden=el.id!==name+"View");StudioShell.setView(name);}', name)

    def tearDown(self):
        self.page.close()

    def test_header_has_one_setting_with_session_status_in_tooltip(self):
        self.assertEqual(self.page.locator('.studio-globalbar #privateSession').count(), 1)
        self.assertEqual(self.page.locator('#creationPrivacy, #privacyStatus').count(), 0)
        self.assertEqual(self.page.locator('.privacy-session').inner_text(), 'Private')
        self.assertEqual(self.page.locator('.privacy-session').get_attribute('title'), 'New creations are regular')
        self.page.locator('#privateSession').check()
        self.assertEqual(self.page.locator('.privacy-session').get_attribute('title'), 'New creations are private')
        self.page.evaluate("StudioPrivacy.setCreation('regular')")
        self.assertEqual(self.page.evaluate('StudioPrivacy.creation()'), 'regular')
        # The toggle shows what the next creation is, never a session setting a regular override has silently beaten.
        self.assertFalse(self.page.locator('#privateSession').is_checked())
        self.assertEqual(self.page.locator('.privacy-session').get_attribute('title'), 'New creations are regular')
        bar = self.page.locator('.privacy-bar').bounding_box()
        header = self.page.locator('.studio-globalbar').bounding_box()
        self.assertGreaterEqual(bar['y'], header['y'])
        self.assertLessEqual(bar['y'] + bar['height'], header['y'] + header['height'])

    def test_history_filter_only_on_listing_views_without_changing_scope(self):
        views = ('assets', 'make', 'production', 'models', 'create', 'learn', 'briefs', 'home')
        for name in views:
            with self.subTest(view=name, scope='regular'):
                self.view(name)
                self.assertEqual(self.page.locator('.privacy-views').is_visible(), name in ('assets', 'production'))
        # A scope other than the session's own stays visible everywhere, so a hidden filter never hides a private list or job.
        self.page.evaluate("StudioPrivacy.setScope('all')")
        saved = self.page.evaluate("sessionStorage.getItem('studio.privacy.session.v1')")
        for name in views:
            with self.subTest(view=name, scope='all'):
                self.view(name)
                self.assertTrue(self.page.locator('.privacy-views').is_visible())
                if name in ('assets', 'production'):
                    self.assertEqual(self.page.locator('#' + name + 'View .privacy-views').count(), 1)
                    self.assertEqual(self.page.locator('#' + name + 'View .view-heading + .privacy-views').count(), 1)
                self.assertEqual(self.page.evaluate('StudioPrivacy.scope()'), 'all')
                self.assertEqual(self.page.evaluate("sessionStorage.getItem('studio.privacy.session.v1')"), saved)
        self.view('assets')
        self.page.locator('[data-privacy-scope="private"]').click()
        self.assertEqual(self.page.evaluate('StudioPrivacy.scope()'), 'private')
        self.page.reload()
        self.view('production')
        self.assertEqual(self.page.locator('[data-privacy-scope="private"]').get_attribute('aria-pressed'), 'true')
        self.assertEqual(self.page.evaluate('StudioPrivacy.creation()'), 'regular')

    def test_controls_and_help_remain_keyboard_reachable_without_overflow(self):
        for width in (1440, 1100, 900, 390, 320):
            with self.subTest(width=width):
                self.page.set_viewport_size({'width': width, 'height': 900})
                self.page.reload()
                self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), width)
                self.page.locator('#privateSession').focus()
                self.page.keyboard.press('Tab')
                self.assertTrue(self.page.locator('.privacy-bar summary').evaluate('(el)=>el===document.activeElement'))
                self.page.keyboard.press('Space')
                self.assertTrue(self.page.locator('.privacy-bar details').evaluate('(el)=>el.open'))
                self.assertTrue(self.page.locator('.privacy-bar details p').is_visible())
                self.assertIn('not encryption', self.page.locator('.privacy-bar details p').inner_text())
                self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), width)
                self.page.keyboard.press('Space')
                self.assertFalse(self.page.locator('.privacy-bar details').evaluate('(el)=>el.open'))
                self.view('assets')
                for button in self.page.locator('[data-privacy-scope]').all():
                    self.assertTrue(button.is_visible())
                self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), width)


if __name__ == '__main__':
    unittest.main(verbosity=2)
