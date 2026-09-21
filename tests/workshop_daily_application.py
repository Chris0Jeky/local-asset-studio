"""Full Studio entry-point journeys on the existing synthetic HTTP fixture, never ComfyUI."""
import argparse
import json
import os
from pathlib import Path
import shutil
import threading
from http.server import ThreadingHTTPServer

from playwright.sync_api import sync_playwright
import studio_browser_smoke as fixture

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / '.runtime/workshop-daily')
    output = parser.parse_args().output
    output.mkdir(parents=True, exist_ok=True)
    fixture.POSTS.clear()
    server = ThreadingHTTPServer(('127.0.0.1', 0), fixture.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    checks, errors = [], []
    try:
        with sync_playwright() as p:
            executable = os.environ.get('STUDIO_BROWSER_EXECUTABLE') or shutil.which('chromium')
            browser = p.chromium.launch(**({'executable_path': executable} if executable else {}))
            try:
                for width in (1440, 390):
                    page = browser.new_page(viewport={'width': width, 'height': 900})
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(origin+'/#home')
                    page.wait_for_function('!!selected && schemaAvailable && !!window.StudioReadPoller')
                    page.wait_for_selector('[data-ux-inspect-job="allocation-failure"]')
                    original = page.evaluate('JSON.stringify([selected.id,values(),parentAssets])')
                    page.click('#bundleHomeLauncher')
                    page.wait_for_selector('#bundleSearch')
                    page.fill('#bundleSearch', 'ink')
                    page.keyboard.press('Escape')
                    page.wait_for_function('!document.querySelector("#bundleExplorer").open')
                    assert page.locator('#bundleHomeLauncher').evaluate('(n)=>n===document.activeElement')
                    page.click('[data-ux-inspect-job="allocation-failure"]')
                    content = page.locator('#uxJobInspector').inner_text()
                    failed_job = next(job for job in fixture.JOBS if job['id'] == 'allocation-failure')
                    assert failed_job['id'] in content and failed_job['prompt_ids'][0] in content, content
                    assert failed_job['failure']['summary'] in content, content
                    assert failed_job['failure']['action'] in content, content
                    page.screenshot(path=str(output/f'job-inspector-{width}.png'))
                    page.keyboard.press('Escape')
                    page.wait_for_function('!document.querySelector("#uxJobInspector").open')
                    assert page.evaluate('JSON.stringify([selected.id,values(),parentAssets])') == original
                    assert page.locator('[data-ux-inspect-job="allocation-failure"]').evaluate('(n)=>n===document.activeElement')
                    page.screenshot(path=str(output/f'overview-{width}.png'), full_page=True)
                    checks.append(f'Overview bundles and exact job inspection at {width}px preserve current work')
                    page.evaluate("showView('create');selectPreset('anima-portrait')")
                    page.wait_for_function('schemaAvailable')
                    assert page.locator('#uxPullAsset').is_disabled()
                    assert 'takes no reference' in page.locator('#uxSourceNote').inner_text()
                    page.evaluate("selectPreset('flux-edit')")
                    page.wait_for_function('schemaAvailable && !assetRefreshing')
                    fixture.WORKSPACE_DELAY = .4
                    page.click('#uxPullAsset')
                    assert page.locator('#uxSourcePicker').is_visible()
                    assert 'Loading' in page.locator('#uxPickerStatus').inner_text()
                    page.wait_for_selector('[data-ux-pull="asset-0"]')
                    page.screenshot(path=str(output/f'library-picker-{width}.png'))
                    page.click('[data-ux-close="uxSourcePicker"]')
                    page.wait_for_function('!document.querySelector("#uxSourcePicker").open')
                    assert page.locator('#uxPullAsset').evaluate('(n)=>n===document.activeElement')
                    fixture.WORKSPACE_DELAY = 0
                    fixture.FAIL_WORKSPACE = True
                    page.click('#uxPullAsset')
                    page.wait_for_function('document.querySelector("#uxPickerStatus").textContent.includes("reopen")')
                    assert page.locator('[data-ux-pull]').count() == 0
                    page.click('[data-ux-close="uxSourcePicker"]')
                    fixture.FAIL_WORKSPACE = False
                    # Exercise real gallery rendering with an empty snapshot, without writing a job.
                    page.evaluate("jobs=[];renderJobs('daily-empty')")
                    page.locator('#workshopResults').evaluate('(n)=>n.open=true')
                    assert 'Continue with this' in page.locator('#gallery').inner_text()
                    page.click('#gallery a[href="/#assets"]')
                    page.wait_for_function("view==='assets'")
                    checks.append(f'Library loading/failure and empty-result import route at {width}px')
                    page.close()
                assert not errors, errors
                writes = [post for post in fixture.POSTS if post['path'] != '/api/estimate']
                assert not writes, writes
            finally:
                browser.close()
    finally:
        fixture.WORKSPACE_DELAY = 0
        fixture.FAIL_WORKSPACE = False
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        (output/'checks.json').write_text(json.dumps({'checks':checks,'page_errors':errors,'posts':fixture.POSTS}, indent=2), encoding='utf-8')
    print(json.dumps({'passed':True,'checks':checks,'generation_submissions':0}, indent=2))


if __name__ == '__main__':
    main()
