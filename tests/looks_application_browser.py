"""Opt-in shipped-UI regressions for Look application, without models or generation.

python tests/looks_application_browser.py --chromium /path/to/chromium
"""
import argparse
import copy
import os
import threading
from browser_ports import browser_server
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
    with browser_server(Handler) as server:
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
                    page.locator('#positive').fill('My existing wording.')
                    page.evaluate("getControl('seed').value='99';document.querySelector('#batch').value='3'")
                    before = page.evaluate('StudioSetupDraft.capture()')
                    page.locator('#lookPrepare').click()
                    page.wait_for_function("!document.querySelector('#lookPrepare').disabled")
                    status = page.locator('#lookStatus').inner_text()
                    assert 'could not be applied' in status and 'sampler' in status, status
                    assert 'Prepare stopped' in status and 'press Generate' not in status, status
                    assert page.evaluate('StudioSetupDraft.capture()') == before, 'Failed Prepare must restore all Create values'
                    assert 'edited shipped look' in page.locator('#lookSummary').inner_text()
                    # Switching to another recipe must roll back its wording, source and local File too.
                    page.evaluate("""selectPreset('restyle-klein');document.querySelector('#positive').value='Keep this source';
                      uploaded='retained.png';parentAssets=['asset-0'];parentByInput={reference:'asset-0'};
                      const transfer=new DataTransfer();transfer.items.add(new File(['fixture'],'local.png',{type:'image/png'}));document.querySelector('#reference').files=transfer.files;""")
                    before = page.evaluate('StudioSetupDraft.capture()')
                    page.locator('#lookPrepare').click()
                    page.wait_for_function("!document.querySelector('#lookPrepare').disabled")
                    assert page.evaluate('StudioSetupDraft.capture()') == before, 'A failed recipe switch restores the original recipe and source'
                    assert page.evaluate("document.querySelector('#reference').files[0].name") == 'local.png'
                    # Repreparing with a supported choice writes every setting.
                    CONTROLS['sampler'] = 'euler'
                    page.locator('#lookPrepare').click()
                    page.wait_for_function("document.querySelector('#lookStatus').textContent.includes('Nothing was generated; press Generate')")
                    assert page.locator('[data-key=seed]').input_value() == '37'
                    assert page.locator('#positive').input_value() == CONTROLS['positive']
                    assert page.evaluate("StudioLooks.applicationBlocker(selected.id)") == ''
                    assert 'look_application' not in page.evaluate('StudioSetupDraft.capture()')['recipe']
                    # A missing binding also restores the last prepared Create values.
                    before = page.evaluate('StudioSetupDraft.capture()')
                    CONTROLS['fps'] = 24
                    page.locator('#lookPrepare').click()
                    page.wait_for_function("document.querySelector('#lookStatus').textContent.includes('could not be applied')")
                    assert 'fps' in page.locator('#lookStatus').inner_text()
                    assert page.evaluate('StudioSetupDraft.capture()') == before
                    assert page.evaluate("StudioLooks.applicationBlocker(selected.id)") == ''
                    assert page.locator('#lookReset').is_hidden(), 'Restored Create needs no reset'
                    assert all(r['path'] in ('/api/looks/prepare', '/api/estimate', '/api/references/check') for r in fixture.POSTS), fixture.POSTS
                    assert not errors, errors
                    print('Look application: missing options/bindings refused, previous Create values restored; zero generation and page errors')
                finally:
                    browser.close()
        finally:
            server.shutdown()
            thread.join(timeout=5)


if __name__ == '__main__':
    main()
