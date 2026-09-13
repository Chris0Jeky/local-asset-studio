"""Opt-in browser proof of Wan mode admission; synthetic APIs, no GPU calls."""
import argparse
import hashlib
import json
import os
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import studio_browser_smoke as fixture


def run(output):
    from playwright.sync_api import sync_playwright
    output.mkdir(parents=True, exist_ok=True)
    fixture.POSTS.clear()
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
                    # Manual controls must change the verdict even though the mode label stays put.
                    page.locator('#i2vMode').select_option('balanced')
                    page.locator('[data-key="frames"]').fill('81')
                    page.wait_for_function("document.querySelector('#generate').disabled")
                    assert '81 frames' in page.locator('#uxBlockers').text_content()
                    page.locator('#i2vMode').select_option('quality')
                    for key, value in (('width', '512'), ('height', '768'), ('frames', '33')):
                        page.locator(f'[data-key="{key}"]').fill(value)
                    page.wait_for_function("!document.querySelector('#generate').disabled")
                    assert 'Held:' not in page.locator('#i2vModeNote').text_content()
                    page.locator('#batch').select_option('3')
                    assert page.locator('#generate').is_enabled()  # Serial outputs are not latent batches.
                    page.locator('[data-key="frames"]').fill('')
                    page.wait_for_function("document.querySelector('#generate').disabled")  # Empty falls back to the long mode.
                    page.evaluate("selectPreset('wan22-t2v')")
                    page.wait_for_function("document.querySelector('#generate').disabled")
                    assert '81 frames' in page.locator('#uxBlockers').text_content()
                    page.screenshot(path=str(output / f't2v-default-{width}.png'))
                    page.locator('#variants').get_by_role('button', name='Short motion study', exact=True).click()
                    page.wait_for_function("!document.querySelector('#generate').disabled")
                    page.locator('#variants').get_by_role('button', name='3.4-second shot', exact=True).click()
                    page.wait_for_function("document.querySelector('#generate').disabled")
                    page.evaluate("applySaved({preset:'wan22-t2v', controls:{frames:33}})")
                    page.wait_for_function("!document.querySelector('#generate').disabled")
                    page.evaluate("applyRecipe({preset_id:'wan22-t2v', name:'Long recipe', controls:{frames:81}})")
                    page.wait_for_function("document.querySelector('#generate').disabled")
                    assert not errors, errors
                    writes = [entry for entry in fixture.POSTS if entry['path'] not in ('/api/estimate', '/api/references/check')]
                    assert not writes, writes
                    cases.append({'width': width, 'quick_and_balanced_enabled': True, 'long_modes_disabled': True,
                                  'mode_switch_restores_generate': True, 'manual_overrides': True, 't2v_default_and_variants': True,
                                  'saved_and_named_overrides': True, 'generation_mutations': 0, 'page_errors': errors})
                    context.close()
            finally:
                browser.close()
    finally:
        http.shutdown()
        http.server_close()
        worker.join(5)
    receipt = {'mode': 'native-http-synthetic-api', 'cases': cases,
               'source_sha256': {name: hashlib.sha256((fixture.ROOT/name).read_bytes()).hexdigest() for name in
                                 ('app/static/app.js', 'app/wan_capacity.py', 'tests/wan_capacity_browser.py')}}
    (output / 'result.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(cases, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    run(parser.parse_args().out)
