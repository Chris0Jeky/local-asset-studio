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


VIEW_BOX = "document.querySelector('#workflowCanvas').getAttribute('viewBox')"
FRAMED = """() => {const svg = document.querySelector('#workflowCanvas'), [x, y, w, h] = svg.getAttribute('viewBox').split(' ').map(Number);
  return [...svg.querySelectorAll('g')].every(g => {const m = /translate\\(([-\\d.]+),([-\\d.]+)\\)/.exec(g.getAttribute('transform')), nx = +m[1], ny = +m[2];
    return nx >= x - 1 && ny >= y - 1 && nx + 245 <= x + w + 1 && ny + 82 <= y + h + 1;});}"""


def viewport_rect(page, selector):
    """Viewport-relative box, which is the frame page.mouse works in; Playwright's bounding_box() is page-relative."""
    return page.evaluate("s => {const r = document.querySelector(s).getBoundingClientRect(), top = Math.max(0, r.top), bottom = Math.min(innerHeight, r.bottom);"
                         "return {x: r.left, y: r.top, w: r.width, h: r.height, cx: r.left + r.width / 2, cy: (top + bottom) / 2, seen: bottom - top};}", selector)


def canvas_navigation(page):
    """Fit / 100% / Ctrl+wheel / background drag all move the viewBox; none of them edit the draft."""
    canvas = page.locator('#workflowCanvas'); revision = page.locator('#documentStats').inner_text()
    canvas.scroll_into_view_if_needed(); box = viewport_rect(page, '#workflowCanvas')
    assert box['seen'] > 300, ('This fixture needs most of the canvas on screen', box)
    page.locator('#canvasFit').click(); fitted = page.evaluate(VIEW_BOX)
    assert page.evaluate(FRAMED), 'Fit must frame every node: ' + fitted
    page.locator('#canvasReset').click(); reset = page.evaluate(VIEW_BOX)
    assert fitted != reset, (fitted, reset)
    assert abs(float(reset.split()[2]) - box['w']) < 2, ('100% is one world unit per CSS pixel', reset, box)
    assert page.locator('#canvasZoom').inner_text() == '100%'
    page.mouse.move(box['cx'], box['cy'])
    page.keyboard.down('Control'); page.mouse.wheel(0, -360); page.keyboard.up('Control')
    zoomed = page.evaluate(VIEW_BOX)
    assert float(zoomed.split()[2]) < float(reset.split()[2]), ('Ctrl+wheel must zoom in', reset, zoomed)
    page.keyboard.down('Control'); page.mouse.wheel(0, 6000); page.keyboard.up('Control')
    assert float(page.evaluate(VIEW_BOX).split()[2]) <= box['w'] / 0.4 + 1, 'Zoom out is clamped at 0.4x'
    page.keyboard.down('Control'); page.mouse.wheel(0, -12000); page.keyboard.up('Control')
    assert float(page.evaluate(VIEW_BOX).split()[2]) >= box['w'] / 2.5 - 1, 'Zoom in is clamped at 2.5x'
    page.locator('#canvasReset').click(); scroll = page.evaluate('scrollY')
    page.mouse.wheel(0, 240)  # A plain wheel is left to the page, so the camera does not move.
    page.wait_for_function('y => scrollY !== y', arg=scroll)
    assert page.evaluate(VIEW_BOX) == reset, 'A plain wheel must not zoom the canvas'
    canvas.scroll_into_view_if_needed(); page.locator('#canvasFit').click(); before = page.evaluate(VIEW_BOX)
    empty = page.evaluate("""() => {const svg = document.querySelector('#workflowCanvas'), r = svg.getBoundingClientRect();
      for (let py = Math.min(innerHeight, r.bottom) - 12; py > Math.max(0, r.top) + 12; py -= 12) for (let fx = r.width - 12; fx > 12; fx -= 12)
        if (document.elementFromPoint(r.left + fx, py) === svg) return [r.left + fx, py];
      return null;}""")
    assert empty, 'The fitted canvas should expose empty background to drag'
    page.mouse.move(empty[0], empty[1]); page.mouse.down(); page.mouse.move(empty[0] - 90, empty[1] - 60, steps=8); page.mouse.up()
    panned = page.evaluate(VIEW_BOX)
    assert panned != before, ('Dragging the background must pan', before, panned)
    assert panned.split()[2:] == before.split()[2:], 'Panning must not change the zoom'
    assert page.locator('#documentStats').inner_text() == revision, 'Panning must not edit the draft'
    # Dragging a node still moves the node and writes its X/Y, and must not pan the camera.
    page.locator('#canvasFit').click(); framed = page.evaluate(VIEW_BOX)
    page.locator('#workflowNodeSelect').select_option('1')
    start = page.get_by_label('X', exact=True).input_value()
    grip = page.evaluate("""() => {const g = document.querySelector('#workflowCanvas g'), r = g.getBoundingClientRect();
      const x = r.left + r.width / 2, y = r.top + 10;
      return document.elementFromPoint(x, y)?.closest('g') === g ? [x, y] : null;}""")
    assert grip, 'The fitted canvas should put node 1 under the pointer'
    page.mouse.move(grip[0], grip[1]); page.mouse.down(); page.mouse.move(grip[0] + 70, grip[1] + 30, steps=8); page.mouse.up()
    page.wait_for_function("start => document.querySelector('#nodeInspector input[type=number]').value !== start", arg=start)
    assert page.evaluate(VIEW_BOX) == framed, 'A node drag must not pan the canvas'


def text_inputs(page):
    """A multiline STRING renders as a growing textarea plus an Expand dialog that round-trips."""
    page.locator('#nodeSearch').fill('Text'); page.locator('#nodeCatalog button').first.click()
    page.wait_for_function("document.querySelector('#documentStats').textContent.includes('4 nodes')")
    area = page.locator('#nodeInspector textarea.wf-text')
    assert area.count() == 1 and area.get_attribute('aria-label') == 'text'
    page.wait_for_function("() => document.querySelector('#nodeInspector textarea.wf-text').clientHeight > 70")
    short = area.evaluate('n => n.clientHeight')
    area.fill('a line of prompt\n' * 30); area.press('Tab')
    page.wait_for_function("h => document.querySelector('#nodeInspector textarea.wf-text').clientHeight > h", arg=short)
    grown = page.locator('#nodeInspector textarea.wf-text').evaluate('n => n.clientHeight')
    assert grown <= round(page.evaluate('innerHeight') * 0.4) + 4, ('Growth is capped near 40vh', grown)
    page.locator('#nodeInspector .wf-expand-open').click()
    dialog = page.locator('dialog.wf-expand')
    assert dialog.evaluate('d => d.open') and dialog.locator('textarea').input_value().startswith('a line of prompt')
    assert dialog.locator('textarea').evaluate('n => n.clientHeight') > grown / 2
    dialog.locator('textarea').fill('expanded prompt text'); dialog.get_by_role('button', name='Apply', exact=True).click()
    page.wait_for_function("() => WorkflowStudio.snapshot().nodes['4'].inputs.text === 'expanded prompt text'")
    page.locator('#nodeInspector .wf-expand-open').click()
    dialog.locator('textarea').fill('discarded'); dialog.get_by_role('button', name='Cancel', exact=True).click()
    assert page.evaluate("WorkflowStudio.snapshot().nodes['4'].inputs.text") == 'expanded prompt text', 'Cancel must discard the edit'
    assert page.locator('#nodeInspector textarea.wf-text').input_value() == 'expanded prompt text'


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
                    raw = (ROOT / 'app/static/workflow-studio.html').read_text(encoding='utf-8')
                    raw = raw.replace('<head>', '<head><base href="http://127.0.0.1:8191/">')
                    raw = re.sub(r'<link rel="stylesheet" href="/static/([^"\n]+)">', lambda m: '<style>' + (ROOT / 'app/static' / m[1]).read_text(encoding='utf-8') + '</style>', raw)
                    raw = re.sub(r'<script src="/static/([^"\n]+)"></script>', lambda m: '<script>' + (ROOT / 'app/static' / m[1]).read_text(encoding='utf-8') + '</script>', raw)
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
                page.locator('#workflowNodeSelect').select_option('2')
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
                canvas_navigation(page)
                text_inputs(page)
                if args.screenshots:
                    page.locator('#builder').scroll_into_view_if_needed()
                    page.screenshot(path=str(args.screenshots / 'workflow-builder.png'), full_page=False)
                if not args.inert_dom:
                    # Browser draft survives a real page reload, without automatically restoring/running it.
                    page.reload(); page.locator('.wf-goal').nth(6).wait_for()
                    assert page.locator('#documentStats').inner_text() == 'No draft'
                    page.locator('#restoreWorkflow').click(); page.wait_for_function("document.querySelector('#documentStats').textContent.includes('4 nodes')")
                    assert page.evaluate("WorkflowStudio.snapshot().nodes['4'].inputs.text") == 'expanded prompt text', 'The expanded text is part of the restored draft'
                    page.goto(origin + '/workflow-studio.html?guide=workflow&step=1#builder')
                    page.locator('.studio-guide-panel').wait_for()
                    page.get_by_role('button', name='Next step', exact=True).click()
                    page.wait_for_url(re.compile(r'step=2(&|#)')); page.locator('.studio-guide-panel').wait_for()
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
                print('PASS: 7 paths; recipe import; numeric edit; undo/redo; disabled-node refusal and explicit bypass; checked export; canvas fit/100%/Ctrl+wheel zoom clamps/background pan with an unchanged draft; node drag that does not pan; growing multiline textarea and Expand dialog apply/cancel; 390px navigation/no horizontal page overflow; zero model submissions; zero page errors. Mode=' + ('inert DOM (no navigation, storage or coach proof)' if args.inert_dom else 'HTTP with reload/draft and coach next/pause'))
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__': main()
