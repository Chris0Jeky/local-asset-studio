"""Accessibility regressions against an owned ephemeral fixture, without generation."""
import os
import shutil
import threading
import unittest
from playwright.sync_api import sync_playwright
from browser_ports import browser_server
import studio_use_cases as ux


class AccessibilityControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        handler, cls.fixture = ux.build_handler()
        cls.server = browser_server(handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True); cls.thread.start()
        cls.playwright = sync_playwright().start()
        executable = os.environ.get('CHROMIUM_PATH') or shutil.which('chromium')
        cls.browser = cls.playwright.chromium.launch(headless=True, **({'executable_path': executable} if executable else {}))

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.playwright.stop(); cls.server.shutdown(); cls.server.server_close(); cls.thread.join()

    def test_native_import_prompt_and_wording_status(self):
        page = self.browser.new_page()
        try:
            page.goto('http://127.0.0.1:'+str(self.server.server_port)+'/#assets')
            page.locator('#importAssetsButton').wait_for()
            self.assertEqual(page.locator('#importAssetsButton').evaluate('n=>n.tagName'), 'BUTTON')
            for key in ('Enter', 'Space'):
                page.locator('#importAssetsButton').focus()
                with page.expect_file_chooser(): page.keyboard.press(key)
            self.assertEqual(page.locator('#positiveLabel').evaluate('n=>n.control.id'), 'positive')
            self.assertEqual(page.locator('#nsfwIntel').evaluate('n=>n.closest("label")'), None)
            self.assertIsNone(page.locator('#uxWordingUndo').get_attribute('role'))
            self.assertEqual(page.locator('#uxWordingUndo > span').get_attribute('role'), 'status')
            self.assertEqual(page.locator('#uxWordingUndo [role="status"] button').count(), 0)
        finally: page.close()

    def test_backend_focus_survives_disabled_and_hidden_controls(self):
        page = self.browser.new_page()
        try:
            page.goto('http://127.0.0.1:'+str(self.server.server_port)+'/#models')
            page.wait_for_function("typeof backendActive!=='undefined' && backendActive!==null")
            page.locator('.environment-panel').evaluate('n=>n.open=true')
            state = page.evaluate("api('/api/backends')")
            state.update(busy=True, operation=None)
            page.route('**/api/backends', lambda route: route.fulfill(json=state))
            page.locator('#backendChoice').focus()
            page.evaluate('refreshBackends()')
            self.assertTrue(page.locator('#backendStatus').evaluate('n=>n===document.activeElement'))
            page.evaluate("renderRecovery({enabled:true,status:'breaker-open'});document.querySelector('#retryRecovery').focus();renderRecovery({enabled:false})")
            self.assertTrue(page.locator('#recoveryStatus').evaluate('n=>n===document.activeElement'))
            self.assertTrue(page.locator('#retryRecovery').is_hidden())
            page.route('**/api/backends/switch', lambda route: route.fulfill(json={}))
            page.evaluate("document.querySelector('#switchBackend').disabled=false")
            page.locator('#switchBackend').focus(); page.keyboard.press('Enter')
            page.wait_for_function("document.activeElement===document.querySelector('#backendStatus')")
        finally: page.close()


if __name__ == '__main__': unittest.main(verbosity=2)
