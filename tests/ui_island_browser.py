"""#907 spike: the committed Vue guidance island in the real Studio frontend, on studio_browser_smoke's synthetic API.

Flag off: no island request, no island DOM, legacy guidance untouched. Flag on: the island mounts after the workshop,
mirrors the workshop's projection, dispatches only reveal/navigation intents, preserves the prompt field's identity
across unmount/remount, survives storage denial and an unreadable recipe list, follows reduced motion, and the page
makes no request outside the local origin. Never contacts ComfyUI; the fixture blocks unexpected mutations.

Also measures normal/opt-in/candidate-default loads and checks 200%-equivalent reflow (#1207).
The candidate is a test-only loader response override, never a production default change.

    python tests/ui_island_browser.py [--output .runtime/ui-island]
"""
from browser_ports import evidence_screenshot
import argparse
import gzip
import hashlib
import json
import os
import shutil
import sys
import threading
from datetime import datetime, timezone
from browser_ports import browser_server
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
import studio_browser_smoke as fixture  # noqa: E402  (sets up app/ and repo-root imports)

RECIPES = json.loads((ROOT / 'presets/recipes.json').read_text(encoding='utf-8'))
STATE = {'fail_recipes': False}


class Handler(fixture.Handler):
    def do_GET(self):
        if urlsplit(self.path).path == '/api/recipes':
            if STATE['fail_recipes']: return self.json({'error': 'Fixture recipe list unavailable'}, 503)
            return self.json({'version': 1, 'available': True, 'source': 'fixture',
                              'recipes': [dict(r, available=None, missing=[]) for r in RECIPES['recipes']]})
        return super().do_GET()


def install_candidate_default(context, origin):
    """Fixture-only response override; production files and ordinary URLs stay unchanged."""
    shell = (ROOT / 'app/static/studio-shell.js').read_text(encoding='utf-8')
    guard = "new URLSearchParams(location.search).get('ui')!=='island'||"
    assert shell.count(guard) == 1, 'Update the candidate fixture for the current island loader'
    shell = shell.replace(guard, '')
    context.route(origin + '/static/studio-shell.js', lambda route: route.fulfill(
        status=200, content_type='text/javascript', body=shell))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / '.runtime/ui-island')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright
    server = browser_server(Handler)
    server.handle_error = lambda *_: None  # a closed browser context aborting an in-flight fixture response is not a finding
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = f'http://127.0.0.1:{server.server_port}'
    checks, external, measurements = [], [], []

    def check(condition, label):
        assert condition, label
        checks.append(label); print('PASS: ' + label, flush=True)

    def new_page(browser, candidate=False, viewport=None, **options):
        context = browser.new_context(viewport=viewport or {'width': 1440, 'height': 900}, **options)
        # Network denial: everything outside the local Studio origin is aborted and recorded.
        def guard(route):
            if route.request.url.startswith(origin + '/'): return route.continue_()
            external.append(route.request.url); return route.abort()
        context.route('**/*', guard)
        if candidate: install_candidate_default(context, origin)
        page = context.new_page(); errors, requests = [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: requests.append(request.url))
        return context, page, errors, requests

    def open_create(page, query=''):
        page.goto(origin + '/' + query + '#create')
        page.wait_for_function("!!document.querySelector('#createView')?.__workshop && !!selected")

    try:
        with sync_playwright() as p:
            executable = os.environ.get('STUDIO_BROWSER_EXECUTABLE') or os.environ.get('CHROMIUM_PATH') or shutil.which('chromium')
            browser = p.chromium.launch(headless=True, **({'executable_path': executable} if executable else {}))

            # Flag off: the page is the legacy page.
            context, page, errors, requests = new_page(browser)
            open_create(page); page.wait_for_timeout(400)
            check(not [u for u in requests if '/ui-dist/' in u], 'flag off: no island asset is requested')
            check(page.locator('#uiIsland').count() == 0, 'flag off: no island root')
            check(page.evaluate('document.body.dataset.uiIsland') is None, 'flag off: no island page flag')
            check(page.locator('#workshopGuidance').count() == 1, 'flag off: legacy guidance present')
            check(not errors, 'flag off: no page errors ' + str(errors))
            context.close()

            # Candidate default: the ordinary URL must mount without an opt-in query.
            context, page, errors, requests = new_page(browser, candidate=True)
            open_create(page)
            page.wait_for_selector('#uiIsland[data-state=mounted] #uiIslandPrimary', timeout=5000)
            check(page.url.endswith('/#create'), 'candidate default uses the ordinary Create URL')
            check(page.locator('#uiIslandPrimary').is_visible(), 'candidate default shows Next step without opting in')
            check(page.locator('#uiIsland [data-recipe-card]').count() > 0, 'candidate default shows authored setups')
            check(not errors, 'candidate default: no page errors')
            context.close()

            # 200% browser-zoom equivalent: half the CSS viewport, doubled pixel density.
            context, page, errors, _ = new_page(browser, candidate=True,
                viewport={'width': 720, 'height': 450}, device_scale_factor=2)
            open_create(page)
            page.wait_for_selector('#uiIsland [data-recipe-card]')
            for layout in ('focus', 'studio', 'immersive'):
                page.select_option('#workshopLayout', layout, force=True)
                page.locator('#uiIslandPrimary').scroll_into_view_if_needed()
                check(page.locator('#uiIsland').evaluate('el => el.scrollWidth <= el.clientWidth + 1'),
                      '200% equivalent: island has no horizontal overflow in ' + layout)
                page.locator('#uiIsland .ui-island__why summary').focus()
                page.keyboard.press('Enter')
                check(page.locator('#uiIsland .ui-island__why').evaluate('el => el.open'),
                      '200% equivalent: Why this opens by keyboard in ' + layout)
                page.keyboard.press('Enter')
                page.locator('#uiIslandToggle').click()
                check(page.locator('#uiIslandToggle').get_attribute('aria-expanded') == 'false',
                      '200% equivalent: authored setups collapse in ' + layout)
                page.locator('#uiIslandToggle').click()
                check(page.locator('#uiIsland [data-recipe-card]').first.is_visible(),
                      '200% equivalent: authored setups reopen in ' + layout)
            check(not errors, '200% equivalent: no page errors')
            context.close()

            # Flag on.
            context, page, errors, requests = new_page(browser)
            posts_before = len(fixture.POSTS)
            open_create(page, '?ui=island')
            page.wait_for_selector('#uiIsland[data-state=mounted] #uiIslandPrimary')
            page.wait_for_selector('#uiIsland [data-recipe-card], #uiIsland .ui-island__unavailable')
            check(page.evaluate('document.body.dataset.uiIsland') == 'active', 'flag on: island mounted and active')
            check([u for u in requests if u.endswith('/static/ui-dist/island.js')] and [u for u in requests if u.endswith('/static/ui-dist/island.css')],
                  'flag on: island JS and CSS come from the Python origin')
            check(page.locator('#workshopGuidance').count() == 1, 'flag on: legacy guidance node retained (hidden by CSS only)')
            legacy = page.locator('#workshopGuidanceAction').evaluate('el => el.dataset.intent')
            check(page.locator('#uiIslandPrimary').get_attribute('data-intent') == legacy, 'island shows the workshop projection: ' + str(legacy))
            check(page.locator('#uiIsland [data-recipe-card]').count() >= 1, 'recipe discovery summaries rendered')
            check(not [p for p in fixture.POSTS[posts_before:] if p['path'] == '/api/jobs'], 'mount submits nothing')

            # Keyboard: the primary action is a native button reachable by focus + Enter, and dispatches a reveal.
            prompt = page.locator('#positive'); prompt.fill('Island keeps this draft text')
            page.evaluate("window.__prompt = document.querySelector('#positive')")
            page.wait_for_timeout(300)
            posts_before = len(fixture.POSTS)
            page.focus('#uiIslandPrimary'); page.keyboard.press('Enter'); page.wait_for_timeout(200)
            focused = page.evaluate('document.activeElement?.id || document.activeElement?.tagName')
            check(focused != 'uiIslandPrimary', 'Enter on the island action moves focus to the existing owner: ' + str(focused))
            cards = page.locator('#uiIsland [data-recipe-card]')
            if cards.count() > 1:
                cards.nth(0).focus(); page.keyboard.press('ArrowDown')
                check(page.evaluate("document.activeElement === document.querySelectorAll('#uiIsland [data-recipe-card]')[1]"), 'ArrowDown moves between recipe cards')
            cards.nth(0).focus(); page.keyboard.press('Enter')
            page.wait_for_selector('#bundleExplorer[open]')
            check(True, 'Inspect opens the existing bundle explorer')
            page.keyboard.press('Escape'); page.wait_for_function("!document.querySelector('#bundleExplorer').open")
            check(not [p for p in fixture.POSTS[posts_before:] if p['path'] != '/api/estimate'], 'island actions made no mutation: ' + str(fixture.POSTS[posts_before:]))

            # Unmount/remount: prompt identity and value survive; one root, one listener set.
            state = page.evaluate('StudioUiIsland.unmount(), StudioUiIsland.state()')
            check(state == 'unmounted' and page.evaluate('document.body.dataset.uiIsland') is None, 'unmount restores the legacy guidance flag')
            page.select_option('#workshopLayout', 'immersive', force=True); page.wait_for_timeout(200)
            check(page.locator('#workshopGuidance').is_visible(), 'rollback: Immersive shows the legacy guidance again once the island is gone')
            for _ in range(3): page.evaluate('StudioUiIsland.remount()')
            check(page.locator('#uiIsland').count() == 1 and page.locator('#uiIslandPrimary').count() == 1, 'remount leaves one root and one action')
            check(page.evaluate("window.__prompt === document.querySelector('#positive') && window.__prompt.value") == 'Island keeps this draft text',
                  'prompt field identity and value preserved across unmount/remount')
            check(page.locator('#workshopGuidance').evaluate('el => getComputedStyle(el).display') == 'none' and page.locator('#uiIsland').is_visible(),
                  'Immersive: island takes the guidance slot; legacy aside hidden only while active')
            evidence_screenshot(page, path=str(args.output / 'flag-on.png'), full_page=False) if os.environ.get('UI_ISLAND_SCREENSHOT') else None
            check(not errors, 'flag on: no page errors ' + str(errors))
            context.close()

            # Storage denial and reduced motion together.
            context, page, errors, _ = new_page(browser, reduced_motion='reduce')
            context.add_init_script("Object.defineProperty(window, 'localStorage', {get() { throw new DOMException('denied', 'SecurityError'); }})")
            open_create(page, '?ui=island')
            page.wait_for_selector('#uiIsland[data-state=mounted] .ui-island__note')
            check('this tab only' in page.locator('#uiIsland .ui-island__note').inner_text(), 'storage denial: island works in tab-only mode')
            check(page.locator('#uiIsland .ui-island__frame').get_attribute('data-motion') == 'reduced', 'reduced motion observed')
            page.click('#uiIslandToggle')
            check(page.locator('#uiIslandToggle').get_attribute('aria-expanded') == 'false', 'storage denial: disclosure still works')
            context.close()

            # Unreadable recipe list: contained, guidance still usable.
            STATE['fail_recipes'] = True
            context, page, errors, _ = new_page(browser)
            open_create(page, '?ui=island')
            page.wait_for_selector('#uiIsland .ui-island__unavailable')
            check(page.locator('#uiIslandPrimary').is_visible() and page.evaluate('StudioUiIsland.state()') == 'mounted', 'recipe failure is contained')
            check(not errors, 'recipe failure: no page errors ' + str(errors))
            context.close()
            STATE['fail_recipes'] = False

            # Alternating arms, six cold browser contexts per arm, same fixture and viewport.
            for _ in range(6):
                for arm in ('normal', 'opt-in', 'candidate-default'):
                    context, page, errors, requests = new_page(browser, candidate=arm == 'candidate-default')
                    open_create(page, '?ui=island' if arm == 'opt-in' else '')
                    workshop_ms = page.evaluate('performance.now()')
                    island_ms = None
                    if arm != 'normal':
                        page.wait_for_selector('#uiIsland [data-recipe-card]')
                        island_ms = page.evaluate('performance.now()')
                    load_ms = page.evaluate("performance.getEntriesByType('navigation')[0].loadEventEnd")
                    page.wait_for_timeout(300)  # settle lazy requests; not included in ready timings
                    measurements.append({'arm': arm, 'workshop_ms': round(workshop_ms, 1),
                        'island_ms': round(island_ms, 1) if island_ms is not None else None,
                        'load_ms': round(load_ms, 1), 'requests': len(requests)})
                    check(not errors, 'measurement ' + str(len(measurements)) + ': no page errors')
                    context.close()
            browser.close()
        check(not external, 'no request left the local origin: ' + str(external[:5]))
    finally:
        server.shutdown(); server.server_close()
    payload = {}
    for name in ('island.js', 'island.css'):
        raw = (ROOT / 'app/static/ui-dist' / name).read_bytes()
        payload[name] = {'bytes': len(raw), 'gzip_bytes': len(gzip.compress(raw, compresslevel=9, mtime=0)),
                         'sha256': hashlib.sha256(raw).hexdigest()}
    (args.output / 'result.json').write_text(json.dumps({'checks': checks, 'measurements': measurements,
        'payload': payload, 'measured_at': datetime.now(timezone.utc).isoformat()}, indent=2), encoding='utf-8')
    print(f'{len(checks)} checks passed')


if __name__ == '__main__':
    main()
