"""Native privacy recovery controls with synthetic SQLite observations and media.

python tests/private_recovery_browser.py --out .runtime/private-recovery-browser
--app-root serves a composed checkout read-only, including its matched fixture.
No running Studio, ComfyUI, model execution or personal media is used.
"""
import argparse
import hashlib
import importlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import threading
import traceback
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from browser_ports import browser_server, evidence_screenshot

ROOT = Path(__file__).resolve().parents[1]
REGULAR = 'REGULAR RECOVERY CANARY: synthetic lantern'
PRIVATE = 'PRIVATE RECOVERY CANARY: synthetic lantern'
ALL = 'ALL RECOVERY CANARY: private synthetic lantern'
COLLECTION = 'PRIVATE COLLECTION RECOVERY CANARY'


def run(output, app_root):
    output.mkdir(parents=True, exist_ok=True)
    app_root = app_root.resolve()
    sys.path.insert(0, str(app_root / 'tests'))
    fixture = importlib.import_module('make_goals_browser')
    fixture.fixture.ROOT = app_root
    fixture.fixture.ASSETS = [dict(a, privacy='regular') for a in fixture.fixture.ASSETS]
    fixture.fixture.ASSETS.append(dict(fixture.fixture.ASSETS[0], id='asset-private',
        privacy='private', title='Synthetic private lantern', job_id='private-fixture-job'))
    sources = ['app/static/'+name+'.js' for name in (
        'privacy', 'workspace', 'asset-recovery', 'asset-recovery-shelf',
        'asset-recovery-shelf-session', 'asset-recovery-shelf-ui',
        'asset-recovery-lifecycle', 'collection-editor', 'collection-recovery')]
    sources += ['app/static/index.html', 'tests/studio_browser_smoke.py', 'tests/make_goals_browser.py']
    hashes = {path: hashlib.sha256((app_root/path).read_bytes()).hexdigest() for path in sources}
    rows, errors, server_errors, disconnects, requests = [], [], [], [], []

    def allows(record, scope): return scope == 'all' or record.get('privacy', 'regular') == scope

    class Handler(fixture.Handler):
        def scope(self): return self.headers.get('X-Studio-Privacy', 'regular')
        def do_GET(self):
            path = urlsplit(self.path).path
            requests.append({'method':'GET', 'path':path, 'scope':self.scope()})
            if path == '/api/assets/page':
                query = fixture.fixture.asset_page_query(self.path)
                query['filters']['privacy'] = self.scope()
                return fixture.fixture.observe_fixture(self, lambda workspace: workspace.asset_page(**query))
            if path == '/api/collections':
                query = fixture.fixture.collection_page_query(self.path)
                return fixture.fixture.observe_fixture(self, lambda workspace: workspace.collection_page(**query, privacy=self.scope()))
            if path == '/api/workspace':
                return self.json({'workspace_id':self.workspace_id,
                    'assets':[a for a in fixture.fixture.ASSETS if allows(a, self.scope())], 'collections':[]})
            if path == '/api/jobs':
                return self.json([j for j in fixture.fixture.JOBS if allows(j, self.scope())])
            if path.startswith('/api/assets/') and path.endswith('/thumb'):
                self.path = path[:-6]+'/file'
            return super().do_GET()
        def do_POST(self):
            path = urlsplit(self.path).path
            item = {'method':'POST', 'path':path, 'scope':self.scope(),
                    'privacy':self.headers.get('X-Studio-Creation-Privacy', 'regular')}
            requests.append(item)
            if path in ('/api/assets/selection', '/api/collections'):
                data = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))))
                item['body'] = data
                if path == '/api/assets/selection':
                    return fixture.fixture.observe_fixture(self, lambda workspace: workspace.asset_selection(
                        data['ids'], workspace_id=data['workspace_id'], details=data.get('details', False), privacy=self.scope()))
                privacy = item['privacy'] if data.get('action') == 'create' else self.scope()
                return fixture.fixture.observe_fixture(self, lambda workspace: workspace.collection(data, privacy=privacy))
            if path in ('/api/jobs', '/api/assets/update'):
                self.rfile.read(int(self.headers.get('Content-Length', '0')))
                return self.json({'error':'This recovery-only fixture refuses generation and asset mutations'}, 400)
            return super().do_POST()

    server = browser_server(Handler)
    def server_error(request, address):
        error = sys.exc_info()[1]
        if isinstance(error, (BrokenPipeError, ConnectionResetError)): disconnects.append(type(error).__name__)
        else: server_errors.append(traceback.format_exc())
    server.handle_error = server_error
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    origin = 'http://127.0.0.1:'+str(server.server_port)
    def check(name, condition, detail=None):
        rows.append({'name':name, 'passed':bool(condition), 'detail':detail})
        print(('PASS ' if condition else 'FAIL ')+name, flush=True)
    def stores(page): return page.evaluate('({local:{...localStorage},session:{...sessionStorage}})')
    def ready(page): page.wait_for_function('!!window.StudioPrivacy&&!!window.StudioAssetRecoveryShelf&&!!assetState.workspace_id&&document.querySelectorAll("#assetGrid [data-asset-open]").length>0')
    def set_scope(page, scope):
        page.locator('[data-privacy-scope="'+scope+'"]').click()
        expected = 'asset-private' if scope == 'private' else 'asset-0'
        page.wait_for_selector('#assetGrid [data-asset-open="'+expected+'"]')
    def open_shelf(page, detail=False):
        if not detail: page.locator('#assetRecoveryDisclosure').evaluate('(node)=>node.open=true')
        page.locator('#openAssetRecoveryShelfDetails' if detail else '#openAssetRecoveryShelf').click()
        page.wait_for_function('document.querySelector("#assetRecoveryShelfDialog").open&&!assetShelfReading')
    def close_shelf(page): page.locator('#closeAssetRecoveryShelf').click()
    def checkpoint(page, asset_id, text):
        page.locator('#assetGrid .asset-open[data-asset-open="'+asset_id+'"]').click()
        page.locator('#assetTitle').fill(text)
        page.locator('#assetNotes').fill(text+' notes')
        open_shelf(page, detail=True)
        page.locator('#assetShelfEnabled').check()
        page.wait_for_function('document.querySelector("#assetShelfStatus").textContent.toLowerCase().includes("checkpoint verified")')
        page.locator('#assetShelfRefresh').click()
        page.wait_for_function('(text)=>!assetShelfReading&&document.querySelector("#assetShelfRecords").textContent.includes(text)', arg=text)
        close_shelf(page); page.locator('#closeAssetDialog').click()
    def device_owner(page):
        return page.evaluate("""async()=>{
          const db=await new Promise((resolve,reject)=>{const r=indexedDB.open('studio.asset-recovery.shelf.v2');r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});
          try{return await new Promise((resolve,reject)=>{const r=db.transaction('shelf','readonly').objectStore('shelf').get('current');r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});}
          finally{db.close();}
        }""")
    browser_version = None
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or None)
            browser_version = browser.version
            context = browser.new_context(viewport={'width':1440, 'height':950}, reduced_motion='reduce', accept_downloads=True)
            page = context.new_page(); page.set_default_timeout(8000)
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('dialog', lambda dialog: dialog.accept())
            page.goto(origin+'/#assets'); ready(page)
            checkpoint(page, 'asset-0', REGULAR)
            regular_owner = device_owner(page)
            check('Regular checkpoint uses the real IndexedDB shelf', REGULAR in json.dumps(regular_owner))
            set_scope(page, 'private'); checkpoint(page, 'asset-private', PRIVATE)
            state = stores(page)
            check('Private checkpoint is retained in tab storage', PRIVATE in state['session'].get('studio.asset-recovery.tab-shelf.v1.private', ''))
            check('Private recovery never enters localStorage or IndexedDB', PRIVATE not in json.dumps(state['local']) and device_owner(page) == regular_owner)
            open_shelf(page)
            check('Private shelf hides the Regular checkpoint', PRIVATE in page.locator('#assetShelfRecords').inner_text() and REGULAR not in page.locator('#assetShelfRecords').inner_text())
            check('Private retention explains the tab lifetime', 'Closing the tab' in page.locator('#assetShelfStorageDescription').inner_text())
            page.locator('#assetShelfRecords [data-shelf-inspect]').first.click()
            check('Private inspect displays retained notes explicitly', PRIVATE in page.locator('#assetShelfInspection pre').inner_text())
            # A second surface may change the controller while a modal is open.
            # Exercise its public event owner, not a replacement privacy module.
            page.evaluate("StudioPrivacy.setScope('regular')")
            check('Scope switch synchronously closes and clears private recovery inspection',
                not page.locator('#assetRecoveryShelfDialog').evaluate('(node)=>node.open') and
                PRIVATE not in page.locator('#assetShelfInspection').inner_text() and
                PRIVATE not in page.locator('#assetCommandRecovery').inner_text() and
                not page.input_value('#assetNotes'))
            page.wait_for_selector('#assetGrid [data-asset-open="asset-0"]')
            open_shelf(page)
            check('Regular shelf still has only regular evidence', REGULAR in page.locator('#assetShelfRecords').inner_text() and PRIVATE not in page.locator('#assetShelfRecords').inner_text())
            close_shelf(page); set_scope(page, 'all'); checkpoint(page, 'asset-private', ALL)
            state = stores(page)
            check('All checkpoint uses its own tab store', ALL in state['session'].get('studio.asset-recovery.tab-shelf.v1.all', ''))
            check('Private and All leave the exact device owner unchanged', device_owner(page) == regular_owner and PRIVATE not in json.dumps(state['local']) and ALL not in json.dumps(state['local']))
            open_shelf(page)
            content = page.locator('#assetShelfRecords').inner_text()
            check('All deliberately lists all three recovery scopes', all(text in content for text in (REGULAR, PRIVATE, ALL)))
            check('All offers matching-view navigation for private restore', page.locator('[data-shelf-view="private"]').count() == 1 and page.locator('[data-shelf-view="regular"]').count() == 1)
            record = page.locator('#assetShelfRecords article').filter(has_text=PRIVATE)
            check('All cannot restore a Private checkpoint into its own journal', record.locator('[data-shelf-restore]').is_disabled())
            evidence_screenshot(page, path=str(output/'all-recovery-shelf.png'))
            close_shelf(page)
            # Collection text has a separate typed journal and must follow its target.
            page.locator('#creationPrivacy').select_option('private')
            page.locator('#newCollection').click()
            page.locator('#collectionName').fill(COLLECTION)
            page.locator('#collectionDescription').fill(COLLECTION+' description')
            page.evaluate("StudioPrivacy.setScope('regular')")
            check('Scope switch closes and clears a private collection editor', not page.locator('#collectionDialog').evaluate('(node)=>node.open') and not page.input_value('#collectionDescription'))
            state = stores(page)
            check('Private collection draft uses only its private tab journal', COLLECTION in state['session'].get('studio.collection-recovery/v1/private/'+'1'*32, '') and COLLECTION not in state['session'].get('studio.collection-recovery/v1/'+'1'*32, '') and COLLECTION not in json.dumps(state['local']))
            set_scope(page, 'private'); page.locator('#recoverCollections').click(); page.locator('#restoreCollectionDraft').click()
            check('Private collection wording restores through its explicit recovery action', page.input_value('#collectionDescription') == COLLECTION+' description')
            page.locator('#saveCollection').click()
            page.wait_for_function('document.querySelector("#collectionStatus").textContent.includes("Collection saved")')
            writes = [r for r in requests if r['method']=='POST' and r['path']=='/api/collections']
            check('Native collection save freezes private read and creation headers', len(writes)==1 and writes[0]['scope']=='private' and writes[0]['privacy']=='private')
            page.locator('#cancelCollection').click(); set_scope(page, 'regular')
            page.reload(); ready(page); open_shelf(page)
            check('Reload in Regular exposes only the device checkpoint', REGULAR in page.locator('#assetShelfRecords').inner_text() and PRIVATE not in page.locator('#assetShelfRecords').inner_text())
            close_shelf(page); set_scope(page, 'private'); open_shelf(page)
            check('Private tab checkpoint survives same-tab reload', PRIVATE in page.locator('#assetShelfRecords').inner_text())
            close_shelf(page); set_scope(page, 'all'); open_shelf(page)
            check('All tab checkpoint survives same-tab reload', ALL in page.locator('#assetShelfRecords').inner_text())
            with page.expect_download() as download: page.locator('#assetShelfExport').click()
            exported = output/'all-view-recovery.json'; download.value.save_as(exported)
            bundle = json.loads(exported.read_text(encoding='utf-8'))
            check('Explicit All export preserves its scope and complete note text', ALL in json.dumps(bundle) and '"privacy": "all"' in json.dumps(bundle))
            close_shelf(page)
            fresh = context.new_page(); fresh.set_default_timeout(8000); fresh.on('pageerror',lambda error:errors.append(str(error)))
            fresh.goto(origin+'/#assets'); ready(fresh)
            check('Independent tab starts Regular without private session recovery', fresh.evaluate('StudioPrivacy.scope()==="regular"') and PRIVATE not in json.dumps(stores(fresh)['session']) and ALL not in json.dumps(stores(fresh)['session']))
            open_shelf(fresh)
            check('Independent tab can read the regular device checkpoint', REGULAR in fresh.locator('#assetShelfRecords').inner_text())
            close_shelf(fresh); set_scope(fresh, 'private'); open_shelf(fresh)
            check('Independent tab has no private shelf records', fresh.locator('#assetShelfRecords article').count()==0)
            context.close(); browser.close()
    except Exception as error:
        check('driver completed', False, type(error).__name__+': '+str(error)); traceback.print_exc()
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)
        fixture.fixture.close_fixture_observations()
    check('zero page errors', not errors, errors)
    check('zero HTTP request-thread errors', not server_errors, server_errors)
    check('zero generation or asset metadata submissions', not any(r['method']=='POST' and r['path'] in ('/api/jobs','/api/assets/update') for r in requests))
    unchanged = all(hashlib.sha256((app_root/path).read_bytes()).hexdigest() == digest for path,digest in hashes.items())
    check('served source remained unchanged during the run', unchanged)
    receipt = {'mode':'native-http-real-privacy-and-recovery-owners-synthetic-api', 'rows':rows,
        'requests':requests, 'client_disconnects':disconnects,
        'provenance':{'app_root':str(app_root), 'python':platform.python_version(),
            'playwright':version('playwright'), 'chromium':browser_version, 'source_sha256':hashes},
        'limits':'Real browser IndexedDB/sessionStorage and production recovery controls over temporary synthetic SQLite records. No running Studio, personal workspace, model, artistic acceptance or human task-time measurement.'}
    (output/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    print(str(sum(row['passed'] for row in rows))+'/'+str(len(rows)), flush=True)
    return 0 if all(row['passed'] for row in rows) else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT/'.runtime/private-recovery-browser')
    parser.add_argument('--app-root', type=Path, default=ROOT)
    args = parser.parse_args(); raise SystemExit(run(args.out, args.app_root))
