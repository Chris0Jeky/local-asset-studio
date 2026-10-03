"""Opt-in shipped-UI regressions for Look application, without models or generation.

python tests/looks_application_browser.py --chromium /path/to/chromium
"""
import argparse
import copy
import os
import threading
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit

import studio_browser_smoke as fixture

CONTROLS = {'positive': 'A quiet room in a saved look.', 'negative': '', 'seed': 37,
            'width': 768, 'height': 960, 'sampler': 'retired_sampler'}
LOOK = {'id': 'look-application-fixture', 'name': 'Application fixture', 'origin': 'seed',
        'revision': 1, 'usable': True, 'trashed_at': None, 'preset_name': 'Fixture recipe',
        'body': {'preset_id': 'zimage-fast', 'template': 'A {scene}.', 'controls': {}}, 'lineage': []}


class Handler(fixture.Handler):
    def do_GET(self):
        if urlsplit(self.path).path == '/api/looks':
            return self.json({'looks': [LOOK], 'seed_errors': [], 'generation_submitted': False})
        return super().do_GET()

    def do_POST(self):
        if self.path == '/api/looks/prepare':
            self.rfile.read(int(self.headers.get('Content-Length', 0)))
            fixture.POSTS.append({'path': self.path})
            return self.json({'preset_id': 'zimage-fast', 'preset_name': 'Fixture recipe',
                              'look': {'id': LOOK['id'], 'name': LOOK['name']}, 'controls': copy.deepcopy(CONTROLS)})
        return super().do_POST()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chromium', default=os.environ.get('CHROMIUM_PATH'))
    args = parser.parse_args()
    from playwright.sync_api import sync_playwright
    # Deterministic API fixture: the real UI must render a select with only supported choices.
    preset = next(p for p in fixture.CATALOG['presets'] if p['id'] == 'zimage-fast')
    preset['sampler'] = ['fixture-node', 'sampler_name']
    preset['defaults']['sampler'] = 'euler'
    errors = []
    with ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, executable_path=args.chromium, args=['--no-sandbox'])
                try:
                    page = browser.new_page(viewport={'width': 1536, 'height': 1060})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.on('dialog', lambda dialog: dialog.accept())
                    page.goto(f'http://127.0.0.1:{server.server_port}/')
                    page.wait_for_function("typeof catalog !== 'undefined' && catalog?.presets?.length && document.querySelector('#lookSelect option[value=\"look-application-fixture\"]')")
                    page.evaluate("showView('create');selectPreset('zimage-fast')")
                    page.locator('#lookBlock').evaluate('(el) => el.open = true')
                    page.locator('#lookSelect').select_option(LOOK['id'])
                    page.locator('#lookScene').fill('quiet room')
                    page.locator('#lookPrepare').click()
                    page.wait_for_function("!document.querySelector('#lookPrepare').disabled")
                    status = page.locator('#lookStatus').inner_text()
                    assert 'could not be applied' in status, status
                    assert 'sampler' in status and 'press Generate' not in status, status
                    assert page.locator('#generate').is_disabled(), 'A failed Look must hold Generate'
                    assert page.locator('[data-key=sampler]').input_value() == 'euler', 'No partial control writes'
                    assert page.locator('[data-key=seed]').input_value() != '37', 'No partial control writes'
                    assert 'edited shipped look' in page.locator('#lookSummary').inner_text()
                    # The hold survives browser-draft normalization and restoration.
                    draft = page.evaluate('StudioSetupDraft.capture()')
                    assert draft['recipe']['look_application']['controls'] == ['sampler'], draft
                    page.evaluate('(d) => applySaved(d.recipe)', draft)
                    assert page.locator('#generate').is_disabled(), 'Restoring a draft must retain the hold'
                    # A named setup must not freeze an unapplied look as if it succeeded.
                    reason = page.evaluate("(() => { try { checkedSetupControls(); return ''; } catch(e) { return e.message; } })()")
                    assert 'Look' in reason and 'sampler' in reason, reason
                    # Repreparing with a supported choice clears the hold and writes every setting.
                    CONTROLS['sampler'] = 'euler'
                    page.locator('#lookPrepare').click()
                    page.wait_for_function("document.querySelector('#lookStatus').textContent.includes('Nothing was generated; press Generate')")
                    assert page.locator('[data-key=seed]').input_value() == '37'
                    assert page.locator('#positive').input_value() == CONTROLS['positive']
                    assert page.evaluate("StudioLooks.applicationBlocker(selected.id)") == ''
                    assert 'look_application' not in page.evaluate('StudioSetupDraft.capture()')['recipe']
                    # A missing binding, not only an unknown select option, also holds the request.
                    CONTROLS['fps'] = 24
                    page.locator('#lookPrepare').click()
                    page.wait_for_function("document.querySelector('#lookStatus').textContent.includes('could not be applied')")
                    assert 'fps' in page.locator('#lookStatus').inner_text()
                    assert page.locator('#generate').is_disabled()
                    page.locator('#lookReset').click()
                    assert page.evaluate("StudioLooks.applicationBlocker(selected.id)") == ''
                    assert 'without the look' in page.locator('#lookStatus').inner_text()
                    assert all(r['path'] in ('/api/looks/prepare', '/api/estimate', '/api/references/check') for r in fixture.POSTS), fixture.POSTS
                    assert not errors, errors
                    print('Look application: missing options/bindings held, atomic writes, draft recovery, explicit reset; zero generation and page errors')
                finally:
                    browser.close()
        finally:
            server.shutdown()
            thread.join(timeout=5)


if __name__ == '__main__':
    main()
