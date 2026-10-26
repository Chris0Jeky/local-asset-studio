"""Opt-in real-frontend recovery proof with inert model receipts and no installation.

python tests/model_download_recovery_browser.py --out /tmp/model-recovery-proof
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import threading
from urllib.parse import urlsplit

from browser_ports import browser_server, evidence_screenshot
import studio_browser_smoke as fixture

RETAINED = 'C:\\model  library\\' + 'long folder\\' * 32 + '.model-<img src=x onerror=bad()>&".unverified'
CLEANUP = 'Do not load this file. Close any reader, then inspect it manually. <script>bad()</script> is text.'
ROWS = [
    {'id': 'failed', 'name': 'Unverified download', 'present': False,
     'download': {'status': 'failed', 'message': CLEANUP + ' Published file failed verification.',
                  'unverified_path': RETAINED, 'cleanup': CLEANUP}},
    {'id': 'other', 'name': 'Other failed publication', 'present': True,
     'download': {'status': 'failed', 'message': 'Other failure',
                  'unverified_path': 'C:\\other.unverified', 'cleanup': 'Inspect the other retained file manually.'}},
    {'id': 'installed', 'name': 'Installed model', 'present': True, 'verified': True,
     'download': {'status': 'installed', 'unverified_path': 'STALE-PATH', 'cleanup': 'STALE-CLEANUP'}},
    {'id': 'active', 'name': 'Active download', 'present': False,
     'download': {'status': 'downloading', 'unverified_path': 'STALE-PATH', 'cleanup': 'STALE-CLEANUP'}},
]
ROWS = [dict(family='Synthetic fixture', file=row['id'] + '.safetensors', bytes=8,
             installable=True, license='Inert browser fixture', **row) for row in ROWS]


class Handler(fixture.Handler):
    def do_GET(self):
        if urlsplit(self.path).path == '/api/library':
            return self.json({'assets': ROWS, 'storage': {'free_bytes': 100, 'total_bytes': 200, 'reserve_bytes': 20},
                              'model_root': 'C:/fixture/models', 'folders': [], 'inventory': [], 'collections': []})
        return super().do_GET()


def run(output):
    from playwright.sync_api import sync_playwright
    output.mkdir(parents=True, exist_ok=True)
    http = browser_server(Handler)
    worker = threading.Thread(target=http.serve_forever, daemon=True); worker.start()
    origin = f'http://127.0.0.1:{http.server_port}'
    cases = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or None,
                                                  headless=True, args=['--no-sandbox'])
            try:
                for width in (1440, 390, 320):
                    context = browser.new_context(viewport={'width': width, 'height': 1000}, reduced_motion='reduce')
                    external = []; errors = []
                    def local_only(route):
                        if route.request.url.startswith(origin + '/'):
                            return route.continue_()
                        external.append(route.request.url); route.abort()
                    context.route('**/*', local_only)
                    page = context.new_page(); page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(origin + '/#models')
                    page.wait_for_function('document.querySelectorAll("#modelCards .model-card").length===4')
                    for key in ('installed', 'active'):
                        card = page.locator('.model-card').filter(has=page.locator(f'[data-install="{key}"]'))
                        assert card.locator('.model-recovery').count() == 0
                        assert 'STALE-' not in card.text_content()
                    other = page.locator('.model-card').filter(has=page.locator('[data-install="other"]'))
                    assert other.locator('.model-recovery code').text_content() == 'C:\\other.unverified'
                    page.fill('#curatedModelSearch', 'Unverified download')
                    card = page.locator('#modelCards .model-card'); recovery = card.locator('.model-recovery')
                    assert card.count() == 1
                    assert recovery.locator('code').text_content() == RETAINED
                    assert recovery.locator('p').last.text_content() == CLEANUP
                    assert card.text_content().count(CLEANUP) == 1
                    assert card.locator('img,script').count() == 0
                    bounds = recovery.evaluate('(el)=>({width:el.clientWidth,scroll:el.scrollWidth,whiteSpace:getComputedStyle(el.querySelector("code")).whiteSpace})')
                    assert bounds['scroll'] <= bounds['width'] + 1, bounds
                    assert bounds['whiteSpace'] == 'pre-wrap', bounds
                    assert card.evaluate('(el)=>el.scrollWidth<=el.clientWidth+1')
                    card.evaluate('(el)=>window.scrollBy(0,el.getBoundingClientRect().top-document.querySelector(".models-toolbar").getBoundingClientRect().bottom-16)')
                    evidence_screenshot(card, path=str(output / f'recovery-card-{width}.png'))
                    assert not errors, errors
                    assert not external, external
                    mutations = [post for post in fixture.POSTS if post['path'] not in ('/api/estimate', '/api/references/check')]
                    assert not mutations, mutations
                    cases.append({'viewport': width, 'path_characters': len(RETAINED), 'recovery_width': bounds['width'],
                                  'complete_path': True, 'cleanup_once': True, 'hostile_text_escaped': True,
                                  'failed_receipt_only': True, 'card_overflow': False, 'mutations': 0, 'page_errors': []})
                    context.close()
            finally: browser.close()
    finally: http.shutdown(); http.server_close(); worker.join(5)
    result = {'fixture': 'Real frontend with synthetic recovery receipts; no model/provider traffic', 'cases': cases}
    (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--out', type=Path, required=True)
    run(parser.parse_args().out)
