"""Repaired PNG import through the shipped page and real HTTP/SQLite, never generation."""
import argparse
import hashlib
import io
import json
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import patch

from PIL import Image
from playwright.sync_api import sync_playwright

from asset_family_browser import build_family_studio, build_handler
from browser_ports import browser_server, evidence_screenshot
from creation_privacy import scope_for_handler
from test_server import server


def picture(colour='seagreen'):
    stream = io.BytesIO()
    Image.new('RGB', (96, 128), colour).save(stream, 'PNG')
    return stream.getvalue()


def storage(studio):
    files = {str(path.relative_to(studio.root)): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in studio.root.rglob('*') if path.is_file() and 'assets.sqlite3' not in path.name}
    return files, sorted(studio.jobs), sorted(asset['id'] for asset in studio.assets.snapshot(privacy='all')['assets'])


def import_handler(studio, requests, controls):
    base = build_handler(studio, [])

    class Handler(base):
        _body_json = server.Handler._body_json
        _asset_query_scope = server.Handler._asset_query_scope

        def _read_body(self, limit):
            raw = server.Handler._read_body(self, limit)
            identity = controls.pop('change_after_read', None) if urlsplit(self.path).path == '/api/assets/import' else None
            if identity:
                with self.studio.assets.connection() as db:
                    db.execute('UPDATE workspace_identity SET id=? WHERE singleton=1', (identity,))
            return raw

        def _json(self, code, value):
            if self.path == '/api/assets/selection' and controls.get('hold'):
                controls['hold'] = False; controls['entered'].set()
                assert controls['release'].wait(15), 'Held parent confirmation was not released'
            return super()._json(code, value)

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == controls.get('startup_path'):
                controls['startup_entered'].set()
                assert controls['startup_release'].wait(15), 'Held Create initialization was not released'
            if path.startswith('/api/assets/recall/'):
                controls.setdefault('recall_reads', []).append(self.path)
            if path == '/api/jobs': return self.json([])  # The retained Library is independent of Recent runs.
            if path == '/api/workspace': return self.json(self.studio.assets.snapshot(privacy=scope_for_handler(self)))
            if path.startswith('/api/assets/') and path.endswith('/metadata'):
                return server.Handler.do_GET(self)
            if path.startswith('/api/assets/') and path.endswith('/file'):
                try: raw = self.studio.assets.file(path.split('/')[3], privacy=scope_for_handler(self)).read_bytes()
                except (ValueError, OSError): return self.json({'error': 'Picture unavailable'}, 404)
                self.send_response(200); self.send_header('Content-Type', 'image/png')
                self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw); return
            return super().do_GET()

        def do_POST(self):
            requests.append(self.path)
            if urlsplit(self.path).path == '/api/assets/import': return server.Handler.do_POST(self)
            assert self.path in ('/api/assets/selection', '/api/estimate', '/api/references/check'), self.path
            return super().do_POST()
    return Handler


def exercise(out, browser_executable=None):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    checks, errors, requests, children = [], [], [], []
    controls = {'hold': False, 'entered': threading.Event(), 'release': threading.Event(),
                'startup_entered': threading.Event(), 'startup_release': threading.Event(), 'recall_reads': []}

    def check(condition, label):
        if not condition: raise AssertionError(label)
        checks.append(label); print('PASS: '+label, flush=True)

    def page_error(error):
        details = error.stack or str(error); errors.append(details)
        print('PAGE ERROR: '+details, flush=True)

    with tempfile.TemporaryDirectory() as tmp:
        studio, ids = build_family_studio(tmp)
        private = studio.import_image('private-parent.png', 'image/png', picture('purple'), privacy='private')['asset']['id']
        parents = {'regular': ids[0], 'private': private}
        originals = {scope: studio.assets.get(identifier, privacy=scope) for scope, identifier in parents.items()}
        hashes = {scope: hashlib.sha256(studio.assets.file(identifier, privacy=scope).read_bytes()).hexdigest()
                  for scope, identifier in parents.items()}
        identity = studio.assets.snapshot()['workspace_id']
        handler = import_handler(studio, requests, controls)
        http = browser_server(handler); thread = threading.Thread(target=http.serve_forever, daemon=True); thread.start()
        origin = 'http://127.0.0.1:'+str(http.server_port)
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True, executable_path=browser_executable)
                try:
                    context = browser.new_context(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce')
                    try:
                        page = context.new_page(); page.set_default_timeout(10000); page.on('pageerror', page_error)

                        def ready(scope):
                            # The ordinary import journey waits for the full page; startup cases hold it below.
                            page.wait_for_function('(scope)=>window.StudioSetupDraft&&backendActive==="primary"&&catalog?.presets?.some(p=>p.id==="anima-portrait")&&selected?.id&&assetActivePrivacy===scope&&!!assetState.workspace_id&&assetPaging&&!assetRefreshing', arg=scope)

                        before_startup = storage(studio)
                        for label, endpoint in (('catalog', '/api/catalog'), ('Atelier', '/api/options')):
                            controls['startup_path'] = endpoint
                            controls['startup_entered'].clear(); controls['startup_release'].clear()
                            try:
                                if label == 'catalog': page.goto(origin+'/#assets', wait_until='domcontentloaded')
                                else: page.reload(wait_until='domcontentloaded')
                                check(controls['startup_entered'].wait(5), 'Create initialization is held at '+label)
                                page.wait_for_function('!!assetState.workspace_id&&assetPaging&&!assetRefreshing')
                                check(page.evaluate('!selected'), 'The Library is ready before a Create recipe: '+label)
                                page.locator('#assetGrid .asset-open[data-asset-open="'+ids[0]+'"]').click()
                                page.wait_for_function('(id)=>activeAsset?.id===id&&document.querySelectorAll("#assetFamily [data-family-step]").length===1', arg=ids[0])
                                check(page.locator('#assetFamily [data-family-step]').get_attribute('data-family-step') == ids[0],
                                      'A visible Library card opens its recorded family while Create loads: '+label)
                                page.locator('[data-family-children]').click()
                                page.wait_for_function('(id)=>[...document.querySelectorAll("#assetFamilyChildren [data-family-open]")].some(e=>e.dataset.familyOpen===id)', arg=ids[1])
                                check(not errors, 'Early family and child reads have no JavaScript page errors: '+label)
                                for selector in ('[data-family-recall="new"]', '[data-family-reference]'):
                                    page.locator(selector).click()
                                    page.wait_for_function('document.querySelector("#assetFamilyStatus").textContent.includes("Create setup is still loading")')
                                check(not controls['recall_reads'] and storage(studio) == before_startup,
                                      'Incomplete Create actions refuse before recall or storage mutation: '+label)
                                page.locator('#assetFamily').scroll_into_view_if_needed()
                                evidence_screenshot(page, path=str(out/('startup-'+label.lower()+'.png')), full_page=False)
                            finally:
                                controls['startup_path'] = None; controls['startup_release'].set()
                            ready('regular')
                            check(page.evaluate('!!StudioSetupDraft.capture()?.recipe?.preset&&typeof StudioSetupDraft.stamp()==="string"'),
                                  'The real Create owner becomes available after '+label+' finishes')
                            check(page.locator('#assetFamily [data-family-step]').get_attribute('data-family-step') == ids[0],
                                  'Initialization preserves the opened family: '+label)
                            page.locator('#closeAssetDialog').click()

                        def open_parent(identifier):
                            if page.locator('#assetDialog').evaluate('(el)=>el.open'):
                                page.locator('#closeAssetDialog').click()
                                page.wait_for_function('!document.querySelector("#assetDialog").open')
                            page.evaluate('(id)=>openAsset(id)', identifier)
                            page.wait_for_function('(id)=>activeAsset?.id===id&&!assetDetailBusy&&!assetRefreshing', arg=identifier)
                            page.locator('#assetRepair').evaluate('(el)=>{el.open=true;}')
                            page.locator('#assetRepairFile').set_input_files({'name': 'repaired.png', 'mimeType': 'image/png', 'buffer': picture()})
                            page.locator('#assetRepairNote').fill('Synthetic edited PNG')
                            page.evaluate('message("");document.querySelector("#assetRepairStatus").textContent=""')

                        before = storage(studio)
                        for query, status in (('', 400), ('?workspace_id=', 400),
                                              ('?workspace_id='+identity+'&workspace_id='+identity, 400),
                                              ('?workspace_id='+'0'*32, 409)):
                            response = page.request.post(origin+'/api/assets/import'+query, data=picture(),
                                headers={'Content-Type': 'image/png', 'X-Filename': 'refused.png', 'X-Parent-Asset': ids[0]})
                            check(response.status == status, 'HTTP refuses invalid repair Workspace: '+(query or 'missing'))
                            check(storage(studio) == before, 'Refused HTTP repair writes no files, jobs or assets')

                        for change in ('workspace', 'privacy', 'navigate', 'close', 'hash'):
                            page.wait_for_function('assetActivePrivacy==="regular"&&!assetRefreshing')
                            open_parent(ids[0]); count = sum(urlsplit(path).path == '/api/assets/import' for path in requests)
                            controls['entered'].clear(); controls['release'].clear(); controls['hold'] = True
                            page.locator('#assetRepairImport').click()
                            check(controls['entered'].wait(5), 'Import waits for a current parent confirmation: '+change)
                            if change == 'workspace':
                                page.evaluate('''()=>{const previous=assetState.workspace_id;assetState.workspace_id='f'.repeat(32);observeAssetWorkspaceIdentity();assetState.workspace_id=previous;observeAssetWorkspaceIdentity();}''')
                            elif change == 'privacy':
                                page.evaluate('StudioPrivacy.setScope("all");StudioPrivacy.setScope("regular")')
                            elif change == 'navigate': page.evaluate('(id)=>openAsset(id)', ids[1])
                            elif change == 'close': page.locator('#closeAssetDialog').click()
                            else: page.evaluate('activeAsset.sha256="e".repeat(64)')
                            controls['release'].set()
                            page.wait_for_function('document.querySelector("#status").textContent.includes("changed")||document.querySelector("#assetRepairStatus").textContent.includes("changed")')
                            check(sum(urlsplit(path).path == '/api/assets/import' for path in requests) == count,
                                  'Held confirmation cannot import after '+change+' (A-B-A for scopes)')
                            check(storage(studio) == before, 'Discarded confirmation preserves storage: '+change)

                        open_parent(ids[0]); controls['change_after_read'] = 'f'*32
                        page.locator('#assetRepairImport').click()
                        page.wait_for_function('document.querySelector("#assetRepairStatus").textContent.includes("different Workspace")')
                        check(storage(studio) == before, 'Workspace replacement during HTTP body reading refuses before writes')
                        with studio.assets.connection() as db:
                            db.execute('UPDATE workspace_identity SET id=? WHERE singleton=1', (identity,))

                        for scope, width in (('regular', 1440), ('private', 390)):
                            page.set_viewport_size({'width': width, 'height': 1000})
                            if scope == 'private': page.evaluate('StudioPrivacy.setScope("private")')
                            page.wait_for_function('(scope)=>assetActivePrivacy===scope&&!assetRefreshing', arg=scope)
                            open_parent(parents[scope]); page.locator('#assetRepairImport').click()
                            page.wait_for_function('!document.querySelector("#assetRepairOpen").hidden')
                            identifier = page.locator('#assetRepairOpen').get_attribute('data-id'); children.append(identifier)
                            child = studio.assets.get(identifier, privacy=scope)
                            check((child['privacy'], child['lineage'], child['review']) == (scope, [parents[scope]], 'unreviewed'),
                                  'Current '+scope+' repair keeps its parent and remains unreviewed')
                            check(child['source']['editor_note'] == 'Synthetic edited PNG', 'Editor note survives the scoped import')
                            check(child['sha256'] != hashes[scope], 'The repair has changed pixels: '+scope)
                            check([path for path in requests if urlsplit(path).path == '/api/assets/import'][-1] == '/api/assets/import?workspace_id='+identity,
                                  'The import request carries its captured Workspace identity')
                            check(studio.assets.get(parents[scope], privacy=scope) == originals[scope], 'Parent record is unchanged: '+scope)
                            check(hashlib.sha256(studio.assets.file(parents[scope], privacy=scope).read_bytes()).hexdigest() == hashes[scope],
                                  'Parent bytes are unchanged: '+scope)
                            evidence_screenshot(page, path=str(out/('repair-import-'+str(width)+'.png')), full_page=True)
                            page.locator('#assetRepairOpen').click()
                            page.wait_for_function('(id)=>activeAsset?.id===id&&document.querySelectorAll("#assetFamily [data-family-step]").length===2', arg=identifier)
                            check(page.locator('#assetFamily [data-family-step]').evaluate_all('(els)=>els.map(e=>e.dataset.familyStep)') == [parents[scope], identifier],
                                  'Open repaired version shows its recorded family: '+scope)

                        with patch.object(threading.Thread, 'start', lambda *_: None):
                            studio = server.Studio(Path(tmp))
                        studio._request = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('Model request forbidden'))
                        handler.studio = studio
                        page.reload(wait_until='domcontentloaded')
                        ready('private')
                        page.evaluate('(id)=>openAsset(id)', children[-1])
                        page.wait_for_function('document.querySelectorAll("#assetFamily [data-family-step]").length===2')
                        check(page.locator('#assetFamily [data-family-step]').evaluate_all('(els)=>els.map(e=>e.dataset.familyStep)') == [private, children[-1]],
                              'Repair linkage survives reopening Studio and reloading the page')
                        check(not errors, 'No JavaScript page errors')
                    finally: context.close()
                finally: browser.close()
            check(all(studio.assets.get(identifier, privacy=scope) == originals[scope] and
                      hashlib.sha256(studio.assets.file(identifier, privacy=scope).read_bytes()).hexdigest() == hashes[scope]
                      for scope, identifier in parents.items()), 'Both original records and byte hashes remain unchanged after restart')
            report = {'checks': checks, 'page_errors': errors, 'post_routes': requests, 'recall_reads': controls['recall_reads'], 'children': children,
                      'parent_unchanged': True, 'generation_submitted': False}
            (out/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
        except BaseException as error:
            (out/'failure.json').write_text(json.dumps({'error': str(error), 'checks': checks, 'page_errors': errors,
                                                       'post_routes': requests, 'recall_reads': controls['recall_reads']}, indent=2)+'\n', encoding='utf-8')
            raise
        finally:
            controls['release'].set(); controls['startup_release'].set(); http.shutdown(); http.server_close(); thread.join(timeout=2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--out', default='.runtime/asset-family/repair-import')
    parser.add_argument('--browser-executable'); args = parser.parse_args()
    exercise(args.out, args.browser_executable)
