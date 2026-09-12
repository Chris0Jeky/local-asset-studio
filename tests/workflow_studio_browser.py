"""Opt-in Chromium smoke: python tests/workflow_studio_browser.py [--screenshots DIR].

Uses the real new page, scripts, styles, HTTP extension and compiler with an inert
synthetic Comfy schema. This is NOT the configured Windows/GPU runtime.
Requires separately available playwright + Chromium; not a runtime dependency.
"""
import argparse
from http.server import ThreadingHTTPServer
import json
import mimetypes
import re
from pathlib import Path
import sys
import tempfile
import threading
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from test_workflow_studio import FakeStudio, LocalHandler
from studio_workflow.http_extension import extend_handler, get, post


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--screenshots', type=Path); parser.add_argument('--browser-executable'); parser.add_argument('--inert-dom', action='store_true', help='Render inline assets with an in-memory API fixture; no browser network access'); args = parser.parse_args()
    from playwright.sync_api import sync_playwright
    with tempfile.TemporaryDirectory() as temp:
        studio = FakeStudio(temp); requests = []
        class StaticHandler(LocalHandler):
            def do_GET(self):
                path = urlparse(self.path).path
                if path == '/api/catalog': return self._json(200, {'presets': [studio.recipe]})
                file = ROOT / 'app' / 'static' / path.removeprefix('/static/').lstrip('/')
                if not file.is_file(): return self._json(404, {'error': 'Not found'})
                raw = file.read_bytes(); self.send_response(200); self.send_header('Content-Type', mimetypes.guess_type(str(file))[0] or 'application/octet-stream'); self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
            def do_POST(self):
                requests.append(self.path); return super().do_POST()
        Wrapped = extend_handler(StaticHandler)
        class TrackingHandler(Wrapped):
            def do_POST(self): requests.append(self.path); return super().do_POST()
        TrackingHandler.studio = studio
        server = ThreadingHTTPServer(('127.0.0.1', 0), TrackingHandler)
        server.expected_host = '127.0.0.1:' + str(server.server_port)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        origin = 'http://' + server.expected_host
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, executable_path=args.browser_executable, args=['--no-sandbox'])
                page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                page.set_default_timeout(5000)
                errors = []; page.on('pageerror', lambda e: errors.append(str(e)))
                if args.inert_dom:
                    # No browser navigation/network: render only authored local files.
                    page.route('**/*', lambda route: route.abort())
                    def fixture(path, body=None):
                        if body is not None: requests.append(path)
                        try:
                            value = {'presets': [studio.recipe]} if path == '/api/catalog' else (get(path, studio) if body is None else post(path, body, studio))
                            return {'ok': True, 'value': value}
                        except ValueError as exc: return {'ok': False, 'value': {'error': str(exc)}}
                    page.expose_function('fixtureRequest', fixture)
                    raw = (ROOT / 'app/static/workflow-studio.html').read_text()
                    raw = raw.replace('<head>', '<head><base href="http://127.0.0.1:8191/">')
                    raw = re.sub(r'<link rel="stylesheet" href="/static/([^"\n]+)">', lambda m: '<style>' + (ROOT / 'app/static' / m[1]).read_text() + '</style>', raw)
                    raw = re.sub(r'<script src="/static/([^"\n]+)"></script>', lambda m: '<script>' + (ROOT / 'app/static' / m[1]).read_text() + '</script>', raw)
                    stub = "<script>window.fetch=async(path,options={})=>{const r=await window.fixtureRequest(path,options.body?JSON.parse(options.body):null);return{ok:r.ok,json:async()=>r.value};};</script>"
                    raw = raw.replace('<body class="workflow-page">', '<body class="workflow-page">' + stub)
                    page.set_content(raw)
                    page.evaluate("StudioShell.setView('workflows')")
                else:
                    page.goto(origin + '/workflow-studio.html')
                page.locator('.wf-goal').nth(6).wait_for()
                assert page.locator('.wf-goal').count() == 7
                assert page.locator('[data-studio-route="workflows"]').get_attribute('aria-current') == 'page'
                assert studio.calls == 0
                if args.screenshots:
                    args.screenshots.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(args.screenshots / 'workflow-guides.png'), full_page=False)
                page.locator('#loadNodes').click(); page.wait_for_function("document.querySelector('#nodeCount').textContent.includes('5 installed')")
                page.locator('#presetChoice').select_option('example'); page.locator('#loadPreset').click()
                page.wait_for_function("document.querySelector('#documentStats').textContent.includes('3 nodes')")
                page.locator('#compileWorkflow').click(); page.wait_for_function("!document.querySelector('#exportGraph').disabled")
                page.locator('#loadNodes').click(); page.wait_for_function("document.querySelector('#exportGraph').disabled")
                page.locator('#compileWorkflow').click(); page.wait_for_function("!document.querySelector('#exportGraph').disabled")
                page.locator('#workflowNodes button').nth(1).click()
                page.get_by_label('factor', exact=True).fill('3.5'); page.get_by_label('factor', exact=True).press('Tab')
                assert page.locator('#exportGraph').is_disabled()
                page.locator('#undoWorkflow').click(); assert page.get_by_label('factor', exact=True).input_value() == '2'
                page.locator('#redoWorkflow').click(); assert page.get_by_label('factor', exact=True).input_value() == '3.5'
                page.get_by_label('Enabled', exact=True).uncheck(); page.locator('#compileWorkflow').click()
                page.wait_for_function("document.querySelector('#workflowStatus').textContent.includes('issue(s)')")
                assert page.locator('#exportGraph').is_disabled()
                page.locator('#nodeInspector summary').click()
                page.get_by_label('Bypass output 0', exact=True).select_option('source')
                page.locator('#compileWorkflow').click(); page.wait_for_function("!document.querySelector('#exportGraph').disabled")
                with page.expect_download() as download:
                    page.locator('#exportGraph').click()
                graph = json.loads(Path(download.value.path()).read_text())
                assert '2' not in graph and graph['3']['inputs']['number'] == ['1', 0]
                page.get_by_label('Enabled', exact=True).check(); page.locator('#compileWorkflow').click()
                page.wait_for_function("!document.querySelector('#exportGraph').disabled")
                if args.screenshots:
                    page.locator('#builder').scroll_into_view_if_needed()
                    page.screenshot(path=str(args.screenshots / 'workflow-builder.png'), full_page=False)
                if not args.inert_dom:
                    # Browser draft survives a real page reload, without automatically restoring/running it.
                    page.reload(); page.locator('.wf-goal').nth(6).wait_for()
                    assert page.locator('#documentStats').inner_text() == 'No draft'
                    page.locator('#restoreWorkflow').click(); page.wait_for_function("document.querySelector('#documentStats').textContent.includes('3 nodes')")
                    page.goto(origin + '/workflow-studio.html?guide=workflow&step=1#builder')
                    page.locator('.studio-guide-panel').wait_for()
                    page.get_by_role('button', name='Next step', exact=True).click()
                    page.wait_for_url('**step=2#builder'); page.locator('.studio-guide-panel').wait_for()
                    page.get_by_role('button', name='Pause guide', exact=True).click()
                    assert page.locator('.studio-guide-panel').count() == 0
                    page.set_viewport_size({'width': 390, 'height': 844}); page.goto(origin + '/workflow-studio.html')
                    page.locator('.wf-goal').nth(6).wait_for()
                else:
                    page.set_viewport_size({'width': 390, 'height': 844})
                    page.evaluate('window.scrollTo(0,0)')
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                page.locator('#studioNavToggle').click(); assert page.locator('#studioNavToggle').get_attribute('aria-expanded') == 'true'
                page.keyboard.press('Escape'); assert page.locator('#studioNavToggle').get_attribute('aria-expanded') == 'false'
                if args.screenshots: page.screenshot(path=str(args.screenshots / 'workflow-mobile.png'))
                assert not errors, errors
                assert studio.calls == 0
                assert all(path not in ('/prompt', '/api/jobs', '/api/workflow-studio/run') for path in requests), requests
                browser.close()
                print('PASS: 7 paths; recipe import; numeric edit; undo/redo; disabled-node refusal and explicit bypass; checked export; 390px navigation/no horizontal page overflow; zero model submissions; zero page errors. Mode=' + ('inert DOM (no navigation, storage or coach proof)' if args.inert_dom else 'HTTP with reload/draft and coach next/pause'))
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__': main()
