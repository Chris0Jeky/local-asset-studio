"""#308 first step: a run refused by the pre-submit memory check says why in plain words, on the card and in the dock.

Real frontend on the synthetic smoke fixture; no generation request is made (the refused job is served by the fixture, the dock refusal is injected)."""
import os
import shutil
import threading
import unittest
from http.server import ThreadingHTTPServer

import studio_browser_smoke as smoke
from playwright.sync_api import sync_playwright

REFUSAL = 'Host commit headroom 20.0 GiB is below the required 32 GiB for this Qwen/FLUX.2 submission'


class FailureWords(unittest.TestCase):
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
        self.page.goto(self.origin + '/#create')
        self.page.wait_for_function('!!selected && schemaAvailable')
        smoke.POSTS.clear()

    def tearDown(self):
        self.page.close()
        self.assertEqual(self.errors, [])
        self.assertEqual([p['path'] for p in smoke.POSTS if p['path'].startswith('/api/jobs')], [], 'nothing is generated')

    def test_refused_job_card_explains_the_memory_check(self):
        # The record is served by the fixture, not pushed into `jobs`: the page's own jobs read (its first load can still be
        # in flight) replaces the client list with the server's, which dropped an injected record about 1 run in 6.
        job = dict(id='headroom-job', preset_name='Qwen Atelier - 1 Reference', status='failed', message=REFUSAL + '. No prompt was submitted for output 1.',
                   prompt_ids=[], outputs=[], controls={}, can_put_away=True)
        smoke.JOBS.insert(0, job); self.addCleanup(smoke.JOBS.remove, job)
        self.page.evaluate("async()=>{await refresh();document.querySelector('#jobProblems').open=true}")
        card = self.page.locator('#jobProblemsHost [data-problem="headroom-job"]')
        card.wait_for()
        text = card.inner_text()
        self.assertIn('Held: not enough memory headroom', text)
        self.assertIn('RAM plus the page file', text)
        self.assertIn('Nothing was sent to ComfyUI', text)
        self.assertIn('press Generate again', text)
        self.assertIn(REFUSAL, text, 'the server wording stays visible as the detail')
        self.assertNotIn('Memory allocation failed', text, 'not confused with a GPU allocation failure')

    def test_refused_generate_says_why_in_the_dock(self):
        self.page.evaluate('(m)=>message(m,true)', REFUSAL)
        status = self.page.locator('#status').inner_text()
        self.assertTrue(status.startswith('Held: not enough memory headroom.'), status)
        self.assertNotIn('sent', status.split('(')[0], 'the bare refusal proves nothing about sending')
        self.assertIn('(' + REFUSAL + ')', status)
        self.page.evaluate("message('Recipe loaded.',false)")
        self.assertEqual(self.page.locator('#status').inner_text(), 'Recipe loaded.', 'other messages are untouched')


if __name__ == '__main__':
    unittest.main(verbosity=2)
