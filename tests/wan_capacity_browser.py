"""Opt-in browser proof of Wan mode admission; synthetic APIs, no GPU calls."""
import argparse
import json
import os
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import studio_browser_smoke as fixture


def run(output):
    from playwright.sync_api import sync_playwright
    output.mkdir(parents=True, exist_ok=True)
    http = ThreadingHTTPServer(('127.0.0.1', 0), fixture.Handler)
    worker = threading.Thread(target=http.serve_forever, daemon=True)
    worker.start()
    cases = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or None, headless=True)
            try:
                for width in (1440, 390):
                    context = browser.new_context(viewport={'width': width, 'height': 1000})
                    page = context.new_page()
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(f'http://127.0.0.1:{http.server_port}')
                    page.wait_for_function('!!selected && schemaAvailable')
                    page.evaluate("showView('create'); selectPreset('wan22-i2v')")
                    page.wait_for_function("document.querySelector('#i2vMode')?.value === 'quick-diagnostic'")
                    assert page.locator('#generate').is_enabled()
                    if not page.locator('#i2vMode').is_visible():
                        page.locator('#i2vMode').locator('xpath=ancestor::details[1]/summary').click()
                    for mode in ('quality', 'canonical-upstream'):
                        page.locator('#i2vMode').select_option(mode)
                        assert page.locator('#generate').is_disabled()
                        assert 'Held:' in page.locator('#i2vModeNote').text_content()
                        page.locator('#i2vModeNote').scroll_into_view_if_needed()
                        page.screenshot(path=str(output / f'{mode}-{width}.png'))
                    page.locator('#i2vMode').select_option('balanced')
                    assert page.locator('#generate').is_enabled()
                    assert 'Held:' not in page.locator('#i2vModeNote').text_content()
                    page.locator('#i2vMode').focus()
                    page.keyboard.press('Home')
                    page.keyboard.press('Tab')
                    assert page.locator('#generate').is_enabled()
                    assert not errors, errors
                    writes = [entry for entry in fixture.POSTS if entry['path'] not in ('/api/estimate', '/api/references/check')]
                    assert not writes, writes
                    cases.append({'width': width, 'quick_and_balanced_enabled': True, 'long_modes_disabled': True,
                                  'mode_switch_restores_generate': True, 'generation_mutations': 0, 'page_errors': errors})
                    context.close()
            finally:
                browser.close()
    finally:
        http.shutdown()
        http.server_close()
        worker.join(5)
    (output / 'result.json').write_text(json.dumps(cases, indent=2), encoding='utf-8')
    print(json.dumps(cases, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    run(parser.parse_args().out)
