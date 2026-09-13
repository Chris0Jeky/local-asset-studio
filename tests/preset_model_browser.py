"""Opt-in Chromium dependency-panel proof using real frontend files and inert APIs.

The HTTP fixture reuses studio_browser_smoke; backend behavior is covered separately
by test_preset_model_readiness's real Handler tests. No model or installer runs.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import threading
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit

import studio_browser_smoke as fixture

ROWS = [
    {'file': 'inpaint/fix.patch', 'path': 'C:/fixture/models/inpaint/fix.patch', 'present': False,
     'asset_id': 'manual-patch', 'installable': False, 'install_note': 'Pin-only patch: copy the reviewed file manually.'},
    {'file': 'loras/curated.safetensors', 'path': 'C:/fixture/models/loras/curated.safetensors', 'present': False,
     'asset_id': 'curated', 'installable': True},
    {'file': 'unknown.safetensors', 'path': None, 'present': None, 'asset_id': None, 'installable': False,
     'note': 'Model folder unknown; declare model_files.', 'install_note': 'Review the exact source and destination.'},
]


class Handler(fixture.Handler):
    def do_GET(self):
        path = urlsplit(self.path).path
        if path.startswith('/api/inspect/'):
            return self.json({'requirements': ROWS, 'nodes': [], 'graph': {}})
        if path == '/api/health':
            return self.json({'online': True, 'schema_available': True, 'missing_models': {'anima-portrait': ['inpaint/fix.patch']}, 'devices': []})
        return super().do_GET()


def run(output):
    from playwright.sync_api import sync_playwright
    output.mkdir(parents=True, exist_ok=True)
    http = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=http.serve_forever, daemon=True); worker.start()
    cases = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or None,
                                        headless=True, args=['--no-sandbox'])
            try:
                for width in (1440, 390):
                    context = browser.new_context(viewport={'width': width, 'height': 1000}, reduced_motion='reduce')
                    page = context.new_page(); errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(f'http://127.0.0.1:{http.server_port}')
                    page.wait_for_function('!!selected && schemaAvailable')
                    page.evaluate("showView('create');selectPreset('anima-portrait')")
                    page.wait_for_selector('#dependencies [data-install="curated"]', state='attached')
                    panel = page.locator('#dependencies')
                    assert panel.locator('[data-install]').count() == 1
                    assert panel.locator('[data-install="manual-patch"]').count() == 0
                    assert 'copy the reviewed file manually' in panel.text_content()
                    unknown = panel.locator('.dependency').filter(has_text='unknown.safetensors')
                    assert unknown.locator('[data-copy]').count() == 0
                    assert 'Model folder unknown' in unknown.text_content()
                    page.evaluate('health()'); page.wait_for_function("document.querySelector('#health').textContent==='Recipe needs models'")
                    assert page.locator('#generate').is_disabled()
                    # Open the real dependency disclosure, then keyboard-focus its only valid install.
                    page.evaluate("document.querySelector('#dependencies').closest('details').open=true")
                    page.locator('#dependencies [data-install="curated"]').focus()
                    assert page.locator('#dependencies [data-install="curated"]').evaluate('(el)=>document.activeElement===el')
                    page.locator('#dependencies').screenshot(path=str(output/f'dependencies-{width}.png'))
                    assert not errors, errors
                    writes = [post for post in fixture.POSTS if post['path'] not in ('/api/estimate', '/api/references/check')]
                    assert not writes, writes
                    cases.append({'width': width, 'unsupported_install_hidden': True, 'unknown_path_not_copyable': True,
                                  'readiness_blocks_generate': True, 'keyboard_focus': True, 'model_mutations': 0, 'page_errors': []})
                    context.close()
            finally: browser.close()
    finally: http.shutdown(); http.server_close(); worker.join(5)
    (output/'result.json').write_text(json.dumps({'fixture': 'real frontend with synthetic read APIs', 'cases': cases}, indent=2))
    print(json.dumps(cases, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--out', type=Path, required=True)
    run(parser.parse_args().out)
