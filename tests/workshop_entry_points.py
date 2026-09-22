"""Native keyboard/layout tests over exact presentation scripts; no HTTP or generation.

Run: python tests/workshop_entry_points.py
Full application integration remains in workshop_application.py / GitHub Actions.
"""
import os
from pathlib import Path
import re
import shutil
import unittest

from playwright.sync_api import sync_playwright
from workshop_browser_core import immersive_css

ROOT = Path(__file__).resolve().parents[1]


def script(name):
    return '<script>' + (ROOT / 'app/static' / name).read_text(encoding='utf-8').replace('</script', '<\\/script') + '</script>'


def workshop_html():
    html = (ROOT / 'tests/workshop_fixture.html').read_text(encoding='utf-8')
    html = re.sub(r'<script src="[^"]+"></script>', '', html)
    styles = '<style id="workshopStyles">' + (ROOT / 'app/static/workshop.css').read_text(encoding='utf-8') + '</style>'
    styles += '<style id="workshopImmersiveStyles">' + immersive_css() + '</style>'
    styles += navigation_css()
    html = html.replace('</style>', '</style>' + styles, 1)
    return html.replace('</body>', ''.join(script(name) for name in ('reference-model.js', 'presentation-context.js', 'workshop.js')) + '</body>')


def navigation_css():
    return '<style id="studioNavigationStyles">' + (ROOT / 'app/static/studio-navigation.css').read_text(encoding='utf-8') + '</style>'


def shell_html(workflow=False):
    css = (ROOT / 'app/static' / ('workflow-studio.css' if workflow else 'studio.css')).read_text(encoding='utf-8')
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><style>' + css + '</style>'
             + navigation_css() + '<body class="' + ('workflow-page' if workflow else '') + '"><main id="toolMain"><button>Inside the tool</button></main>'
            + script('studio-shell.js') + '</body></html>')


class EntryPoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        executable = os.environ.get('STUDIO_BROWSER_EXECUTABLE') or shutil.which('chromium')
        cls.browser = cls.playwright.chromium.launch(**({'executable_path': executable} if executable else {}))

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.page = self.browser.new_page(viewport={'width': 1440, 'height': 900})
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.set_default_timeout(3000)

    def tearDown(self):
        self.page.close()
        self.assertEqual(self.errors, [])

    def load_workshop(self):
        self.page.set_content(workshop_html())
        self.page.wait_for_selector('#workshopRecipeChange')

    def test_closed_picker_has_explicit_accessibility_state(self):
        self.load_workshop()
        for layout in ('focus', 'studio', 'immersive'):
            with self.subTest(layout=layout):
                self.page.select_option('#workshopLayout', layout)
                self.assertEqual(self.page.locator('#workshopRecipeChange').get_attribute('aria-expanded'), 'false')
                self.assertTrue(self.page.locator('.ux-recipe-drawer').evaluate('(n)=>n.inert'))
                self.assertEqual(self.page.locator('.ux-recipe-drawer').get_attribute('aria-hidden'), 'true')
                # .tabIndex == 0 alone is NOT proof of a tab stop in a closed native dialog.
                self.page.focus('#workshopRecipeChange')
                self.page.locator('#presetList button').first.evaluate('(n)=>n.focus()')
                self.assertTrue(self.page.locator('#workshopRecipeChange').evaluate('(n)=>n===document.activeElement'))
                self.page.keyboard.press('Tab')
                self.assertFalse(self.page.evaluate("!!document.activeElement.closest('#workshopRecipeDialog')"))

    def test_recipe_labels_follow_empty_and_active_state(self):
        self.load_workshop()
        for layout in ('focus', 'studio', 'immersive'):
            with self.subTest(layout=layout):
                self.page.select_option('#workshopLayout', layout)
                self.page.evaluate("selected=null;document.querySelector('#createView').__workshop.sync()")
                self.assertEqual(self.page.locator('#workshopRecipeChange').inner_text(), 'Choose recipe')
                self.page.evaluate("selectPreset('ink');document.querySelector('#createView').__workshop.sync()")
                self.assertEqual(self.page.locator('#workshopRecipeChange').inner_text(), 'Change: Ink illustration')
                self.assertIn('Ink illustration', self.page.locator('#workshopRecipeChange').get_attribute('aria-label'))

    def test_long_recipe_names_do_not_collapse_or_overflow_the_rail(self):
        self.load_workshop()
        for width in (1440, 390, 320):
            self.page.set_viewport_size({'width': width, 'height': 900})
            for layout in ('focus', 'studio', 'immersive'):
                with self.subTest(width=width, layout=layout):
                    self.page.select_option('#workshopLayout', layout)
                    self.page.evaluate("selected.name='Combine • FLUX.2 Klein 9B — Copy pose and preserve identity';document.querySelector('#createView').__workshop.sync()")
                    chip = self.page.locator('.wk-recipe').bounding_box()
                    change = self.page.locator('#workshopRecipeChange').bounding_box()
                    self.assertLessEqual(chip['height'], 150)
                    self.assertGreater(change['width'], 120)
                    self.assertLessEqual(change['x'] + change['width'], width)
                    if width >= 390:
                        self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), width)
                    self.assertIn('Copy pose and preserve identity', self.page.locator('#workshopRecipeChange').inner_text())

    def test_native_modal_focus_escape_and_cancel_preserve_draft(self):
        self.load_workshop()
        self.page.fill('#positive', 'Keep my edited draft')
        for layout in ('focus', 'studio', 'immersive'):
            with self.subTest(layout=layout):
                self.page.select_option('#workshopLayout', layout)
                self.page.click('#workshopRecipeChange')
                self.assertFalse(self.page.locator('.ux-recipe-drawer').evaluate('(n)=>n.inert'))
                self.assertTrue(self.page.locator('#presetSearch').evaluate('(n)=>n===document.activeElement'))
                self.page.focus('#positive')
                self.assertTrue(self.page.evaluate("!!document.activeElement.closest('#workshopRecipeDialog')"))
                self.page.once('dialog', lambda dialog: dialog.dismiss())
                self.page.locator('#presetList [data-id="refine"]').click()
                self.assertEqual(self.page.locator('#positive').input_value(), 'Keep my edited draft')
                self.page.keyboard.press('Escape')
                self.page.wait_for_function("!document.querySelector('#workshopRecipeDialog').open")
                self.assertTrue(self.page.locator('#workshopRecipeChange').evaluate('(n)=>n===document.activeElement'))
                self.assertEqual(self.page.evaluate('submitted'), 0)

    def test_existing_skip_link_is_first_and_focuses_main(self):
        for workflow in (False, True):
            with self.subTest(workflow=workflow):
                self.page.set_content(shell_html(workflow))
                self.page.keyboard.press('Tab')
                self.assertTrue(self.page.locator('.studio-skip').evaluate('(n)=>n===document.activeElement'))
                self.page.keyboard.press('Enter')
                self.assertTrue(self.page.locator('main').evaluate('(n)=>n===document.activeElement'))

    def test_mobile_create_and_sidebar_focus_for_each_shell(self):
        self.page.set_viewport_size({'width': 390, 'height': 844})
        for workflow in (False, True):
            with self.subTest(workflow=workflow):
                self.page.set_content(shell_html(workflow))
                self.assertEqual(self.page.locator('#studioQuickCreate').count(), 1)
                self.assertTrue(self.page.locator('#studioQuickCreate').is_visible())
                self.assertEqual(self.page.locator('#studioQuickCreate').get_attribute('href'), '/#create')
                self.assertTrue(self.page.locator('#studioSidebar').evaluate('(n)=>n.inert'))
                self.page.click('#studioNavToggle')
                self.assertTrue(self.page.evaluate("!!document.activeElement.closest('#studioSidebar')"))
                self.assertFalse(self.page.locator('#studioSidebar').evaluate('(n)=>n.inert'))
                self.page.keyboard.press('Escape')
                self.assertTrue(self.page.locator('#studioNavToggle').evaluate('(n)=>n===document.activeElement'))
                self.assertTrue(self.page.locator('#studioSidebar').evaluate('(n)=>n.inert'))
                self.page.set_viewport_size({'width': 1440, 'height': 900})
                self.page.wait_for_function("!document.querySelector('#studioSidebar').inert")
                self.page.set_viewport_size({'width': 390, 'height': 844})


if __name__ == '__main__':
    unittest.main(verbosity=2)
