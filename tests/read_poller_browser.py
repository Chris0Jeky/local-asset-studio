"""Opt-in Chromium proof with real Studio scripts and inert APIs; no model runtime.

Browser visibility is simulated and intervals shortened to exercise the actual
handlers without relying on an OS window manager or spending minutes per case.
"""
import argparse
import json
import os
import shutil
import threading
import time
from collections import Counter
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import studio_browser_smoke as fixture

COUNTS = Counter()
JOBS_IN_FLIGHT = 0
JOBS_PEAK = 0
JOBS_DELAY = 0
LOCK = threading.Lock()


class Handler(fixture.Handler):
    def do_GET(self):
        global JOBS_IN_FLIGHT, JOBS_PEAK
        path = urlsplit(self.path).path
        with LOCK:
            if path.startswith('/api/'): COUNTS[path] += 1
            if path == '/api/jobs':
                JOBS_IN_FLIGHT += 1; JOBS_PEAK = max(JOBS_PEAK, JOBS_IN_FLIGHT)
        try:
            if path == '/api/jobs' and JOBS_DELAY: time.sleep(JOBS_DELAY)
            return super().do_GET()
        finally:
            if path == '/api/jobs':
                with LOCK: JOBS_IN_FLIGHT -= 1


def run(output):
    global JOBS_DELAY, JOBS_PEAK
    from playwright.sync_api import sync_playwright
    output.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
    evidence = {'fixture': 'real frontend; inert APIs; simulated visibility; shortened intervals', 'cases': []}
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or None, headless=True)
            try:
                page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                errors = []; page.on('pageerror', lambda error: errors.append(str(error)))
                page.add_init_script("""window.testHidden=false;
                  Object.defineProperty(document,'hidden',{configurable:true,get:()=>window.testHidden});
                  window.testVisibility=hidden=>{window.testHidden=hidden;document.dispatchEvent(new Event('visibilitychange'));};
                  window.addEventListener('pageshow',event=>window.lastPageshowPersisted=event.persisted);""")
                origin = f'http://127.0.0.1:{server.server_port}'
                page.goto(origin)
                page.wait_for_function('!!window.StudioReadPoller?.started && !!selected')
                page.evaluate("for(const lane of window.StudioReadPoller.lanes.values())lane.interval=300; window.StudioReadPoller.wake()")
                page.wait_for_timeout(400)
                page.evaluate('testVisibility(true)'); page.wait_for_timeout(150)
                before = dict(COUNTS); page.wait_for_timeout(700)
                assert dict(COUNTS) == before, (before, dict(COUNTS))
                page.evaluate('testVisibility(false)'); page.wait_for_timeout(150)
                assert COUNTS['/api/jobs'] > before['/api/jobs']
                evidence['cases'].append({'hidden_automatic_gets': 0, 'visible_resume_reads': True})

                page.locator('[data-studio-route="create"]').click(); page.wait_for_timeout(750)
                production_before = COUNTS['/api/production']; page.wait_for_timeout(400)
                assert COUNTS['/api/production'] == production_before
                page.locator('[data-studio-route="home"]').click(); page.wait_for_timeout(800)
                assert COUNTS['/api/production'] >= production_before + 2
                evidence['cases'].append({'overview_resumes_after_inactive_interval': True})

                page.locator('[data-studio-route="create"]').click(); page.wait_for_timeout(450)
                JOBS_PEAK = 0; JOBS_DELAY = 0.35
                page.evaluate('Promise.all([refresh(),refresh(),refresh()])')
                page.wait_for_timeout(750)
                assert JOBS_PEAK == 1, JOBS_PEAK
                evidence['cases'].append({'slow_jobs_max_concurrent_in_create': JOBS_PEAK})
                JOBS_DELAY = 0
                page.goto('about:blank'); page.go_back()
                page.wait_for_function('!!window.StudioReadPoller?.started && !!selected')
                before = COUNTS['/api/jobs']; page.evaluate('refresh()')
                assert COUNTS['/api/jobs'] > before
                evidence['cases'].append({'browser_back_refresh_works': True, 'bfcache_used': page.evaluate('!!window.lastPageshowPersisted')})
                for width in (1440, 390):
                    page.set_viewport_size({'width': width, 'height': 1000})
                    page.screenshot(path=str(output / f'polling-{width}.png'), full_page=False)
                assert not errors, errors
                writes = [post['path'] for post in fixture.POSTS if post['path'] not in ('/api/estimate', '/api/references/check')]
                assert not writes, writes
                evidence.update(page_errors=errors, mutating_requests=writes, get_counts=dict(COUNTS))
            finally: browser.close()
    finally:
        server.shutdown(); server.server_close(); worker.join(5)
    (output / 'result.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--out', type=Path, required=True)
    run(parser.parse_args().out)
