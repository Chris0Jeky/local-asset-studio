"""Opt-in native-browser response-ownership checks with the shipped UI and inert API."""
import argparse
import copy
import os
import threading
from browser_ports import browser_server
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
                              'look': {'id': LOOK['id'], 'name': LOOK['name'], 'revision': LOOK['revision']}, 'controls': copy.deepcopy(CONTROLS)})
        return super().do_POST()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chromium', default=os.environ.get('CHROMIUM_PATH'))
    args = parser.parse_args()
    from playwright.sync_api import sync_playwright
    errors = []
    with browser_server(Handler) as server:
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
                                    assert page.evaluate('StudioSetupDraft.capture()')['recipe']['look'] == {key: LOOK[key] for key in ('id', 'name', 'revision')}
                                else:
                                    assert page.locator('#positive').input_value() == old
                                    assert 'not applied' in page.locator('#lookStatus').inner_text()
                                assert page.evaluate("StudioLooks.applicationBlocker(selected.id)") == ''
                            attempts = []
                            def block_generation(route):
                                attempts.append(route.request.post_data_json)
                                route.fulfill(status=400, content_type='application/json', body='{"error":"Generation blocked by browser test"}')
                            page.route('**/api/jobs', block_generation)
                            page.locator('#lookScene').fill('new shortcut scene')
                            count = len(fixture.POSTS)
                            page.locator('#lookScene').press('Control+Enter')
                            page.wait_for_function("document.querySelector('#lookStatus').textContent.includes('Prepared. Press Ctrl+Enter again (or Generate) to run it.') && !document.querySelector('#lookPrepare').disabled")
                            assert any(row['path'] == '/api/looks/prepare' for row in fixture.POSTS[count:])
                            assert attempts == [], 'First shortcut only prepares'
                            page.locator('#lookScene').evaluate("el=>el.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',ctrlKey:true,repeat:true,bubbles:true,cancelable:true}))")
                            assert attempts == [], 'Held keys never generate'
                            page.locator('#lookScene').press('Control+Enter')
                            page.wait_for_function("!submitting")
                            assert len(attempts) == 1, 'Second unchanged shortcut uses Generate'
                            assert attempts[0]['controls']['positive'] == CONTROLS['positive']
                            for change in ('scene', 'wording', 'recipe'):
                                if change == 'scene': page.locator('#lookScene').fill('another scene')
                                elif change == 'wording': page.locator('#positive').fill('My new words')
                                else: page.evaluate("selectPreset('zimage-fast')")
                                count = sum(row['path'] == '/api/looks/prepare' for row in fixture.POSTS)
                                page.locator('#lookScene').press('Control+Enter')
                                page.wait_for_function("!document.querySelector('#lookPrepare').disabled && document.querySelector('#lookStatus').textContent.includes('Prepared. Press Ctrl+Enter again')")
                                assert sum(row['path'] == '/api/looks/prepare' for row in fixture.POSTS) == count + 1, change
                                assert len(attempts) == 1, 'Changed preparation cannot generate: ' + change
                        finally:
                            RELEASE.set()
                            page.close()
                    assert all(row['path'] in ('/api/looks/prepare', '/api/estimate', '/api/references/check') for row in fixture.POSTS), fixture.POSTS
                    assert not errors, errors
                    print('Desktop/mobile: pending admission held, stale wording/scene/recipe refused, current response applied, scene shortcut prepares then runs only unchanged wording; zero generation and page errors')
                finally:
                    browser.close()
        finally:
            RELEASE.set()
            server.shutdown()
            thread.join(timeout=5)


if __name__ == '__main__':
    main()
