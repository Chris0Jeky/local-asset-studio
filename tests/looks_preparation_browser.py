"""Opt-in native-browser response-ownership checks with the shipped UI and inert API."""
import argparse
import copy
import os
import threading
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit

import studio_browser_smoke as fixture

STARTED = threading.Event()
RELEASE = threading.Event()
LOOK = {'id': 'look-ownership-fixture', 'name': 'Ownership fixture', 'origin': 'owner',
        'revision': 1, 'usable': True, 'trashed_at': None, 'preset_name': 'Fixture recipe',
        'body': {'preset_id': 'zimage-fast', 'template': 'A {scene}.', 'controls': {}}, 'lineage': []}
CONTROLS = {'positive': 'Delayed prepared wording.', 'negative': '', 'seed': 37}


class Handler(fixture.Handler):
    def do_GET(self):
        if urlsplit(self.path).path == '/api/looks':
            return self.json({'looks': [LOOK], 'seed_errors': []})
        return super().do_GET()

    def do_POST(self):
        if self.path == '/api/looks/prepare':
            self.rfile.read(int(self.headers.get('Content-Length', 0)))
            fixture.POSTS.append({'path': self.path})
            STARTED.set()
            if not RELEASE.wait(timeout=20):
                return self.json({'error': 'Test did not release the prepared response'}, status=500)
            return self.json({'preset_id': 'zimage-fast', 'preset_name': 'Fixture recipe',
                              'look': {'id': LOOK['id'], 'name': LOOK['name']}, 'controls': copy.deepcopy(CONTROLS)})
        return super().do_POST()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chromium', default=os.environ.get('CHROMIUM_PATH'))
    args = parser.parse_args()
    from playwright.sync_api import sync_playwright
    errors = []
    with ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, executable_path=args.chromium, args=['--no-sandbox'])
                try:
                    for viewport in ({'width': 1536, 'height': 1060}, {'width': 430, 'height': 932}):
                        page = browser.new_page(viewport=viewport)
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        page.on('dialog', lambda dialog: dialog.accept())
                        try:
                            page.goto(f'http://127.0.0.1:{server.server_port}/')
                            page.wait_for_function("typeof StudioSetupDraft !== 'undefined' && document.querySelector('#lookSelect option[value=\"look-ownership-fixture\"]')")
                            page.evaluate("showView('create');selectPreset('zimage-fast')")
                            page.locator('#lookBlock').evaluate('(el) => el.open = true')
                            page.locator('#lookSelect').select_option(LOOK['id'])
                            page.locator('#lookScene').fill('quiet room')
                            for change in ('wording', 'scene', 'recipe', 'unchanged'):
                                STARTED.clear()
                                RELEASE.clear()
                                page.locator('#lookPrepare').click()
                                assert STARTED.wait(timeout=5), 'Fixture must observe the request'
                                assert page.locator('#generate').is_disabled(), 'Pending Look must hold Generate'
                                assert page.evaluate("continuationBlockerItems()[0].code") == 'look'
                                reason = page.evaluate("(() => {try {checkedSetupControls(); return '';} catch(e) {return e.message;}})()")
                                assert 'being prepared' in reason, reason
                                old = page.locator('#positive').input_value()
                                if change == 'wording':
                                    page.locator('#positive').fill('New wording owned by the editor.')
                                    old = 'New wording owned by the editor.'
                                elif change == 'scene':
                                    page.locator('#lookScene').fill('a different scene')
                                elif change == 'recipe':
                                    page.evaluate("selectPreset('zimage-fast')")
                                    old = page.locator('#positive').input_value()
                                RELEASE.set()
                                page.wait_for_function("!document.querySelector('#lookPrepare').disabled")
                                if change == 'unchanged':
                                    assert page.locator('#positive').input_value() == CONTROLS['positive']
                                    assert 'Nothing was generated; press Generate' in page.locator('#lookStatus').inner_text()
                                else:
                                    assert page.locator('#positive').input_value() == old
                                    assert 'not applied' in page.locator('#lookStatus').inner_text()
                                assert page.evaluate("StudioLooks.applicationBlocker(selected.id)") == ''
                        finally:
                            RELEASE.set()
                            page.close()
                    assert all(row['path'] in ('/api/looks/prepare', '/api/estimate', '/api/references/check') for row in fixture.POSTS), fixture.POSTS
                    assert not errors, errors
                    print('Desktop/mobile: pending admission held, stale wording/scene/recipe refused, current response applied; zero generation and page errors')
                finally:
                    browser.close()
        finally:
            RELEASE.set()
            server.shutdown()
            thread.join(timeout=5)


if __name__ == '__main__':
    main()
