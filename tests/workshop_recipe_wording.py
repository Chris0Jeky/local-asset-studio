"""#1100: switching recipes loads the new recipe's wording; your own wording gets one explicit way back.

Real frontend on the synthetic smoke fixture (no ComfyUI, no generation)."""
import os
import shutil
import threading
import unittest
from http.server import ThreadingHTTPServer

import studio_browser_smoke as smoke
from playwright.sync_api import sync_playwright

MINE = 'My own lantern keeper, painted at dusk'


class RecipeWording(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), smoke.Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.origin = f'http://127.0.0.1:{cls.server.server_port}'
        cls.playwright = sync_playwright().start()
        executable = os.environ.get('CHROMIUM_PATH') or shutil.which('chromium')
        cls.browser = cls.playwright.chromium.launch(**({'executable_path': executable} if executable else {}))

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.playwright.stop(); cls.server.shutdown(); cls.server.server_close()

    def setUp(self):
        self.page = self.browser.new_page(viewport={'width': 1440, 'height': 900})
        self.errors = []; self.page.on('pageerror', lambda e: self.errors.append(str(e))); self.page.set_default_timeout(5000)
        # Create's picker already asks before replacing edited work; the user accepts, as in the issue.
        self.confirms = []; self.page.on('dialog', lambda d: (self.confirms.append(d.message), d.accept()))
        self.page.goto(self.origin + '/#create')
        self.page.wait_for_function('!!selected && schemaAvailable && selected.id === "anima-portrait"')
        smoke.POSTS.clear()

    def tearDown(self):
        self.page.close()
        self.assertEqual(self.errors, [])
        self.assertEqual([p['path'] for p in smoke.POSTS if p['path'].startswith('/api/jobs')], [], 'nothing is generated')

    def switch(self, preset):
        # The same path as a recipe card in the picker.
        self.page.evaluate("(id)=>document.querySelector('#presetList [data-id=\"'+id+'\"]').click()", preset)
        self.page.wait_for_function('(id)=>selected.id===id', arg=preset)

    def default(self, preset):
        return self.page.evaluate("(id)=>catalog.presets.find(p=>p.id===id).defaults.positive", preset)

    def test_typed_wording_can_be_put_back_after_a_switch(self):
        self.page.fill('#positive', MINE)
        self.switch('sdxl')
        self.assertEqual(len(self.confirms), 1, 'the existing confirm still runs first')
        self.assertEqual(self.page.input_value('#positive'), self.default('sdxl'), 'the switch still loads the recipe wording')
        undo = self.page.locator('#uxWordingUndo')
        undo.wait_for(state='visible')
        self.assertIn('SDXL', undo.inner_text())
        self.page.click('#uxWordingUndoRestore')
        self.assertEqual(self.page.input_value('#positive'), MINE)
        self.assertTrue(undo.is_hidden())
        self.assertEqual(self.page.evaluate('selected.id'), 'sdxl', 'the recipe choice stands')
        self.assertTrue(self.page.locator('#positive').evaluate('(n)=>n===document.activeElement'))

    def test_keeping_the_recipe_wording_or_typing_dismisses_the_offer(self):
        self.page.fill('#positive', MINE)
        self.switch('sdxl')
        self.page.click('#uxWordingUndoDismiss')
        self.assertTrue(self.page.locator('#uxWordingUndo').is_hidden())
        self.assertEqual(self.page.input_value('#positive'), self.default('sdxl'))
        self.page.fill('#positive', MINE + ' again')
        self.switch('anima-portrait')
        self.page.locator('#uxWordingUndo').wait_for(state='visible')
        self.page.type('#positive', ' plus')
        self.assertTrue(self.page.locator('#uxWordingUndo').is_hidden(), 'typing is a decision')

    def test_untouched_example_wording_offers_nothing(self):
        self.switch('sdxl')
        self.page.wait_for_timeout(100)
        self.assertTrue(self.page.locator('#uxWordingUndo').is_hidden())
        self.page.fill('#positive', '   ')
        self.switch('anima-portrait')
        self.page.wait_for_timeout(100)
        self.assertTrue(self.page.locator('#uxWordingUndo').is_hidden(), 'blank wording is not worth restoring')

    def test_a_misclick_then_the_intended_recipe_still_offers_your_wording(self):
        self.page.fill('#positive', MINE)
        self.switch('sdxl')
        self.switch('realvis')
        undo = self.page.locator('#uxWordingUndo')
        undo.wait_for(state='visible')
        self.assertIn('Product', undo.inner_text())
        self.page.click('#uxWordingUndoRestore')
        # The SDXL example in between was never yours; your own wording is what comes back.
        self.assertEqual(self.page.input_value('#positive'), MINE)
        self.assertEqual(self.page.evaluate('selected.id'), 'realvis')

if __name__ == '__main__':
    unittest.main(verbosity=2)
