"""Closed-tab recovery over the shipped UI and disposable real HTTP/SQLite.

Default: native IndexedDB, WebCrypto and Web Locks on the production loopback
origin. --inert explicitly substitutes browser storage/hash/locks/transport and
copies local data between documents; it is NOT native persistence evidence.
"""
from browser_ports import evidence_screenshot
import argparse
import asyncio
import hashlib
import io
import json
import shutil
import socket
import tempfile
import threading
from browser_ports import browser_server
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
from playwright.async_api import async_playwright
import studio_browser_smoke as fixture
from asset_detail_browser import inert_page
from browser_shelf_owner import inert_shelf_owner, replace_shelf_raw, clear_shelf_storage, refuse_shelf_writes, read_shelf_entry
import server as production


async def exercise(args):
    args.out.mkdir(parents=True, exist_ok=True)
    checks, errors, writes, reads = [], [], [], []
    flags = {'lose': False, 'fail': False}
    failure = None
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        store = production.AssetWorkspace(root)
        source = root / 'synthetic.png'
        Image.new('RGB', (48, 64), (100, 110, 120)).save(source)
        original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        ids = [store.register({'id': f'shelf-{i}', 'preset_name': 'Synthetic shelf QA',
                'outputs': [{'filename': source.name, 'media_type': 'image'}]}, 0, source) for i in range(2)]

        class Handler(production.extend_handler(production.Handler)):
            studio = SimpleNamespace(assets=store, jobs={})
            json = fixture.Handler.json

            # This fixture uses its own loopback origin, even while the owner's
            # Studio is listening on 8191. Production host checks have their own tests.
            def _safe_host(self):
                return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')

            def _safe_mutation(self):
                return self._safe_host() and self.headers.get('Origin') in (f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}')

            def do_GET(self):
                if self.path == '/api/workspace' or self.path.startswith('/api/assets/') or self.path.startswith('/api/collections'):
                    reads.append(self.path)
                    return super().do_GET()
                return fixture.Handler.do_GET(self)

            def do_POST(self):
                if self.path=='/api/assets/selection':return super().do_POST()  # read-only Workspace observation, served by the real store
                if self.path == '/api/assets/update':
                    raw = self.rfile.read(int(self.headers['Content-Length']))
                    writes.append(raw.decode('utf-8')); self.rfile = io.BytesIO(raw)
                    if flags['fail']:
                        flags['fail'] = False
                        return self._json(503, {'error': 'Synthetic pre-commit interruption'})
                    return super().do_POST()
                return fixture.Handler.do_POST(self)

            def _json(self, status, data):
                if flags['lose'] and self.path == '/api/assets/update' and data.get('status') == 'applied':
                    flags['lose'] = False; self.close_connection = True
                    self.connection.shutdown(socket.SHUT_RDWR)
                    return
                return super()._json(status, data)

        http = browser_server(Handler)
        port = http.server_port
        thread = threading.Thread(target=http.serve_forever, daemon=True); thread.start()
        fixture.POSTS.clear()

        def check(name, condition, detail=None):
            checks.append({'id': name, 'passed': bool(condition), **({'detail': detail} if detail is not None else {})})
            print(name, bool(condition), flush=True)
            if not condition:
                raise AssertionError(name)

        try:
            async with async_playwright() as pw:
                if args.inert:
                    browser = await pw.chromium.launch(executable_path=shutil.which('chromium'), headless=True, args=['--no-sandbox'])
                    context = await browser.new_context(viewport={'width': 1280, 'height': 1000}, reduced_motion='reduce', accept_downloads=True)
                    zoom_worker = None
                else:
                    # A disposable extension calls the browser's own tab-zoom API.
                    # It never injects CSS, patches Studio, or leaves this profile.
                    extension = root / 'zoom-extension'; extension.mkdir()
                    (extension / 'manifest.json').write_text(json.dumps({'manifest_version': 3,
                        'name': 'Synthetic recovery zoom qualification', 'version': '1.0',
                        'permissions': ['tabs'], 'background': {'service_worker': 'worker.js'}}), encoding='utf-8')
                    (extension / 'worker.js').write_text('chrome.runtime.onInstalled.addListener(()=>{});\n'
                        'setInterval(()=>chrome.runtime.getPlatformInfo(),20000);\n', encoding='utf-8')
                    context = await pw.chromium.launch_persistent_context(str(root / 'browser-profile'),
                        channel='chromium', headless=True, args=['--no-sandbox',
                            f'--disable-extensions-except={extension}', f'--load-extension={extension}'],
                        viewport={'width': 1280, 'height': 1000}, reduced_motion='reduce', accept_downloads=True)
                    browser = context.browser
                    zoom_worker = context.service_workers[0] if context.service_workers else await context.wait_for_event('serviceworker')
                retained = None

                async def tab_to(page, selector):
                    # Native sequential keyboard navigation, not element.focus().
                    last = []
                    for _ in range(100):
                        if await page.evaluate('selector=>document.activeElement.matches(selector)', selector):
                            return
                        last.append(await page.evaluate('document.activeElement.outerHTML.slice(0,200)'))
                        await page.keyboard.press('Tab')
                    state = await page.evaluate('''selector=>({matches:document.querySelectorAll(selector).length,
                      editor:document.getElementById('assetDialog').open,shelf:document.getElementById('assetRecoveryShelfDialog').open,
                      pending:assetDetailPending?.command?.request_id,retained:assetRetainedDetail?.operation?.command?.request_id})''', selector)
                    raise AssertionError('Keyboard could not reach ' + selector + ': ' + json.dumps({'state': state, 'last_focus': last[-12:]}))

                async def activate(page, selector):
                    await tab_to(page, selector); await page.keyboard.press('Enter')

                async def import_inspect(page, content, name='synthetic-recovery.json'):
                    await page.set_input_files('#assetShelfImport', {'name': name, 'mimeType': 'application/json', 'buffer': content})
                    await page.wait_for_function('!assetShelfChanging')

                async def import_refused(page, name, content, message):
                    raw = await page.evaluate('assetShelfStore.raw()')
                    journal = await page.evaluate('JSON.stringify({...sessionStorage})')
                    before_posts, before_receipts = len(writes), sum('/api/assets/commands/' in r for r in reads)
                    await tab_to(page, '#assetShelfImport')
                    await import_inspect(page, content, name + '.json')
                    check(name, await page.evaluate('''message=>assetShelfImported===null &&
                          document.getElementById('assetShelfImportPreview').hidden &&
                          document.getElementById('assetShelfStatus').textContent.includes(message)''', message) and
                          await page.evaluate('assetShelfStore.raw()') == raw and
                          await page.evaluate('JSON.stringify({...sessionStorage})') == journal and len(writes) == before_posts and
                          sum('/api/assets/commands/' in r for r in reads) == before_receipts and
                          await page.evaluate("document.activeElement.id==='assetShelfImport'"))

                async def ready(page):
                    await page.wait_for_function('!!catalog && !!selected')
                    # The shell removes the legacy nav; the workbench then replaces
                    # showView with the current navigation adapter in one script turn.
                    await page.wait_for_function('!!window.StudioShell && !!document.getElementById("homeView")')
                    await page.evaluate("showView('assets')")
                    await page.wait_for_function('assetState.assets.length===2')
                    return page

                async def page_new():
                    page = await context.new_page(); page.set_default_timeout(7000)
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    if args.inert:
                        await inert_page(page, port)
                        await page.expose_function('__shelfHash', lambda data: list(hashlib.sha256(bytes(data)).digest()))
                        await page.evaluate('''() => {
                          Object.defineProperty(window, 'crypto', {value:{getRandomValues: crypto.getRandomValues.bind(crypto),
                            subtle:{digest:async(name,data)=>new Uint8Array(await __shelfHash(Array.from(data))).buffer}}});
                          let tail=Promise.resolve();Object.defineProperty(navigator,'locks',{value:{request:(n,o,fn)=>{const p=tail.then(fn);tail=p.catch(()=>{});return p;}}});
                        }''')
                        await inert_shelf_owner(page)
                        if retained is not None:
                            await page.evaluate('raw=>localStorage.setItem(StudioAssetRecoveryShelf.KEY,raw)', retained)
                    else:
                        await page.goto(f'http://127.0.0.1:{port}/#assets')
                    return await ready(page)

                async def close_page(page):
                    nonlocal retained
                    await page.evaluate('assetShelfSession.flush()')
                    if args.inert:
                        retained = await page.evaluate('assetShelfStore.raw()')
                    await page.close()

                async def shelf(page, details=False):
                    # S6: the library launcher sits in the Recovery disclosure; open it the way a person would.
                    if not details and not await page.evaluate("document.getElementById('assetRecoveryDisclosure')?.open ?? true"): await page.click('#assetRecoveryDisclosure > summary')
                    await page.click('#openAssetRecoveryShelfDetails' if details else '#openAssetRecoveryShelf')
                    await page.wait_for_function('!assetShelfReading')

                async def restore_record(page, record_id):
                    # Closing is queued by <dialog>; wait for its focus handoff
                    # before the next keyboard activation starts another dialog.
                    await page.evaluate('''() => {window.__restoredShelfClosed=false;
                      document.getElementById('assetRecoveryShelfDialog').addEventListener('close',()=>{window.__restoredShelfClosed=true;},{once:true});}''')
                    await activate(page, f'[data-shelf-restore="{record_id}"]')
                    await page.wait_for_function('__restoredShelfClosed && !document.querySelector("#assetRecoveryShelfDialog").open')
                    await activate(page, '[data-asset-recover-open]')
                    await page.wait_for_function('document.getElementById("assetDialog").open && !!assetDetailPending')

                async def restore_pending(page, identifier, request_id=None):
                    await shelf(page)
                    record_id = await page.evaluate('''async ([id,request]) => (await assetShelfStore.list()).find(r=>r.payload.operation&&r.payload.id===id&&(!request||r.payload.operation.command.request_id===request)).id''', [identifier, request_id])
                    await restore_record(page, record_id)

                async def enable(page):
                    await shelf(page, True)
                    await page.check('#assetShelfEnabled')
                    await page.wait_for_function('!assetShelfChanging')
                    await page.press('#assetShelfEnabled', 'Escape')

                async def unknown(page):
                    await page.wait_for_function('!assetDetailBusy && !!assetDetailPending')

                page = await page_new()
                check('SHELF-01 page load is read-only and shelf is opt-in', not writes and not await page.evaluate('assetShelfSession.enabled'))
                await page.evaluate('id=>openAsset(id)', ids[0])
                await page.fill('#assetNotes', 'Draft retained after a closed tab — synthetic only')
                await enable(page)
                check('SHELF-02 device opt-in preserves current draft without POST', not writes and (await page.evaluate('assetShelfStore.list()'))[0]['payload']['draft']['notes'].startswith('Draft retained'))
                check('SHELF-03 Escape returns focus to its detail launcher', await page.evaluate("document.activeElement.id==='openAssetRecoveryShelfDetails'"))
                await close_page(page); before = len(writes); page = await page_new()
                await shelf(page)
                first = (await page.evaluate('assetShelfStore.list()'))[0]['id']
                await page.click(f'[data-shelf-inspect="{first}"]')
                check('SHELF-04 closed-tab shelf inspect is inert', len(writes) == before and 'synthetic only' in await page.locator('#assetShelfInspection').inner_text())
                await page.click(f'[data-shelf-restore="{first}"]'); await page.click('[data-asset-recover-open]')
                check('SHELF-05 explicit restore recovers the closed-tab draft', 'synthetic only' in await page.input_value('#assetNotes') and len(writes) == before)
                await enable(page); flags['lose'] = True
                await page.fill('#assetNotes', 'Committed snapshot; response deliberately lost')
                await page.click('#saveAssetDetails'); await unknown(page)
                wire = writes[-1]; request = json.loads(wire)['request_id']
                await page.fill('#assetNotes', 'Newer local typing after the committed snapshot')
                await close_page(page); before = len(writes); page = await page_new()
                check('SHELF-06 new tab never replays a lost response', len(writes) == before and store.get(ids[0])['metadata_revision'] == 1)
                await restore_pending(page, ids[0])
                check('SHELF-07 pending bytes and newer draft survive closure independently', await page.evaluate('assetDetailPending.body') == wire and await page.input_value('#assetNotes') == 'Newer local typing after the committed snapshot')
                await page.click('[data-asset-save-check]'); await page.wait_for_function('!assetDetailBusy && !assetDetailPending')
                check('SHELF-08 GET observes historical commit without resending or replacing newer typing', len(writes) == before and await page.input_value('#assetNotes') == 'Newer local typing after the committed snapshot' and any(request in r for r in reads))
                # Fixture setup leaves this completed editor; the next operation owns a new asset.
                await page.evaluate('''() => new Promise(resolve=>{const d=document.querySelector('#assetDialog');d.addEventListener('close',resolve,{once:true});d.close();})''')
                await page.evaluate('id=>openAsset(id)', ids[1]); await enable(page); flags['fail'] = True
                await page.fill('#assetNotes', 'Exact retry after pre-commit failure')
                await page.click('#saveAssetDetails'); await unknown(page); retry_wire = writes[-1]
                await close_page(page); page = await page_new(); before = len(writes)
                await restore_pending(page, ids[1]); await activate(page, '[data-asset-save-check]'); await unknown(page)
                check('SHELF-09 unknown receipt never triggers retry', len(writes) == before and store.get(ids[1])['metadata_revision'] == 0)
                await activate(page, '[data-asset-save-retry]'); await page.wait_for_function('!assetDetailBusy && !assetDetailPending')
                check('SHELF-10 explicit retry preserves exact body and commits once', writes[-1] == retry_wire and store.get(ids[1])['metadata_revision'] == 1)
                # Export an actually unresolved command, independently of newer typing.
                await enable(page)
                flags['lose'] = True
                await page.fill('#assetNotes', 'Exported committed snapshot; response lost')
                await page.click('#saveAssetDetails'); await unknown(page)
                export_wire = writes[-1]; export_request = json.loads(export_wire)['request_id']
                await page.fill('#assetNotes', 'Newer draft retained in the exported pending record')
                await page.evaluate('assetShelfSession.flush()')
                await shelf(page, True)
                malformed = await page.evaluate('''async()=>{const r=(await assetShelfStore.list()).find(record=>record.slot==='detail'),p=structuredClone(r.payload);
                  p.draft.notes='Malformed UTF-8 marker \uFFFD';
                  const sealed=await StudioAssetRecoveryShelf.seal(r.slot,p,{id:'e'.repeat(32),generation:1,created_at:1,updated_at:1},crypto);
                  return StudioAssetRecoveryShelf.encode([sealed]);}''')
                malformed_bytes = malformed.encode('utf-8')
                if b'\xef\xbf\xbd' not in malformed_bytes:
                    raise AssertionError('Synthetic bundle did not contain the replacement-character UTF-8 bytes')
                malformed_bytes = malformed_bytes.replace(b'\xef\xbf\xbd', b'\x80', 1)
                invalid_import_before = await page.evaluate('assetShelfStore.raw()')
                invalid_import_writes = len(writes)
                await page.set_input_files('#assetShelfImport', {
                    'name': 'malformed-utf8-recovery.json', 'mimeType': 'application/json',
                    'buffer': malformed_bytes})
                await page.wait_for_function('!assetShelfChanging')
                check('SHELF-UTF8-01 malformed UTF-8 is refused before replacement decoding',
                      await page.evaluate('''() => assetShelfImported===null &&
                        document.querySelector('#assetShelfImportPreview').hidden &&
                        document.querySelector('#assetShelfStatus').textContent.includes('valid UTF-8')''') and
                      await page.evaluate('assetShelfStore.raw()') == invalid_import_before and
                      len(writes) == invalid_import_writes)
                async with page.expect_download() as download_info:
                    await activate(page, '#assetShelfExport')
                download = await download_info.value; exported = Path(await download.path()).read_bytes()
                before = len(writes); before_receipts = sum(export_request in r for r in reads)
                await clear_shelf_storage(page, args.inert)
                # Do not flush the closed tab back into the deliberately cleared storage.
                await page.close(); retained = None; page = await page_new()
                check('SHELF-EXPORT-01 fresh tab starts without a shelf or session recovery',
                      not await page.evaluate('assetShelfSession.enabled') and
                      await page.evaluate('assetRecovery.read("detail")') is None and
                      await page.evaluate('assetRecovery.read("library")') is None and
                      await page.evaluate('assetShelfStore.list()') == [] and len(writes) == before)
                await activate(page, '#assetRecoveryDisclosure > summary')
                await activate(page, '#openAssetRecoveryShelf'); await page.wait_for_function('!assetShelfReading')
                await tab_to(page, '#assetShelfImport')
                await import_inspect(page, exported)
                await page.wait_for_function('assetShelfImported!==null')
                check('SHELF-11 fresh-tab import inspection does not persist, query receipts or mutate', len(writes) == before and
                      sum(export_request in r for r in reads) == before_receipts and
                      await page.evaluate('assetShelfStore.raw()') is None)
                await activate(page, '#assetShelfImportConfirm'); await page.wait_for_function('assetShelfImported===null && !assetShelfChanging')
                imported_records = await page.evaluate('assetShelfStore.list()')
                imported_pending = next(r for r in imported_records if (r['payload'].get('operation') or {}).get('command', {}).get('request_id') == export_request)
                imported_id = imported_pending['id']
                check('SHELF-12 explicit import is local only and preserves exact pending bytes', len(writes) == before and
                      sum(export_request in r for r in reads) == before_receipts and imported_pending['payload']['operation']['body'] == export_wire)
                check('SHELF-KEYBOARD-01 hidden import confirmation moves focus into imported records',
                      await page.evaluate('document.activeElement.matches("[data-shelf-inspect]")'))
                await restore_record(page, imported_id)
                check('SHELF-EXPORT-02 imported pending command and newer draft restore independently',
                      await page.evaluate('assetDetailPending.body') == export_wire and
                      await page.input_value('#assetNotes') == 'Newer draft retained in the exported pending record' and len(writes) == before)
                await activate(page, '[data-asset-save-check]'); await page.wait_for_function('!assetDetailBusy && !assetDetailPending')
                check('SHELF-EXPORT-03 fresh-tab recovery reads one historical result without replay', len(writes) == before and
                      sum(export_request in r for r in reads) == before_receipts + 1 and store.get(ids[1])['metadata_revision'] == 2 and
                      await page.input_value('#assetNotes') == 'Newer draft retained in the exported pending record')
                check('SHELF-KEYBOARD-02 confirmed pending controls return focus to the reviewed save',
                      await page.evaluate("document.activeElement.id==='saveAssetDetails'"))
                # A distinct occupied session viewpoint cannot be overwritten by import restoration.
                await page.fill('#assetNotes', 'A different local viewpoint must survive imported recovery')
                if args.inert:
                    local_recovery = await page.evaluate('sessionStorage.getItem("studio.asset-recovery.v1.detail")')
                    await close_page(page); page = await page_new()
                    await page.evaluate('raw=>{sessionStorage.setItem("studio.asset-recovery.v1.detail",raw);assetRetainedDetail=assetRecovery.read("detail");renderLibraryRecovery();}', local_recovery)
                else:
                    await page.reload(); await ready(page)
                await shelf(page)
                local_view = await page.evaluate('JSON.stringify(assetRecovery.read("detail"))')
                shelf_view = await page.evaluate('assetShelfStore.raw()')
                await activate(page, f'[data-shelf-restore="{imported_id}"]'); await page.wait_for_function('!assetShelfChanging')
                conflict_observation = {'journal_unchanged': await page.evaluate('JSON.stringify(assetRecovery.read("detail"))') == local_view,
                    'shelf_unchanged': await page.evaluate('assetShelfStore.raw()') == shelf_view,
                    'status': await page.locator('#assetShelfStatus').inner_text(), 'posts_before': before, 'posts_after': len(writes),
                    'editor_open': await page.locator('#assetDialog').evaluate('(element)=>element.open')}
                check('SHELF-CONFLICT-01 occupied session and imported viewpoint both survive refusal',
                      conflict_observation['journal_unchanged'] and conflict_observation['shelf_unchanged'] and
                      'different local viewpoint' in conflict_observation['status'] and len(writes) == before, conflict_observation)
                await page.keyboard.press('Escape'); await activate(page, '[data-asset-recover-open]'); await shelf(page, True)
                # Exercise the file-input refusal UI over native storage, not only codec helpers.
                valid = json.loads(exported)
                corrupt = json.loads(exported); corrupt['records'][0]['sha256'] = '0' * 64
                duplicate = json.loads(exported); duplicate['records'].append(duplicate['records'][0])
                same_request = await page.evaluate('''async record=>{const copy=await StudioAssetRecoveryShelf.seal(record.slot,record.payload,
                  {id:'c'.repeat(32),generation:1,created_at:1,updated_at:1},crypto);return JSON.stringify({version:1,records:[record,copy]});}''', imported_pending)
                for name, content, message in [
                    ('SHELF-IMPORT-01 malformed JSON', b'{"version":1,"records":[', 'Incomplete JSON'),
                    ('SHELF-IMPORT-02 corrupt digest', json.dumps(corrupt).encode(), 'digest mismatch'),
                    ('SHELF-IMPORT-03 oversized file', b' ' * (2 * 1024 * 1024 + 1), 'exceeds 2 MiB'),
                    ('SHELF-IMPORT-04 future bundle version', json.dumps({'version': 99, 'records': valid['records']}).encode(), 'Unsupported recovery bundle'),
                    ('SHELF-IMPORT-05 duplicate record identity', json.dumps(duplicate).encode(), 'Duplicate recovery record identity'),
                    ('SHELF-IMPORT-06 duplicate pending identity', same_request.encode(), 'Duplicate pending request identity'),
                    ('SHELF-IMPORT-07 duplicate JSON key', b'{"version":1,"version":1,"records":[]}', 'Duplicate JSON key'),
                    ('SHELF-IMPORT-08 JSON depth', ('[' * 18 + '0' + ']' * 18).encode(), 'depth limit'),
                ]:
                    await import_refused(page, name, content, message)
                for cancelled_kind, cancelled_bytes in [('valid', exported), ('malformed', b'{')]:
                    cancelled_storage = await page.evaluate('assetShelfStore.raw()')
                    await page.evaluate('''() => {const original=File.prototype.arrayBuffer;
                      window.__importReadHeld=false;File.prototype.arrayBuffer=function(){const file=this;File.prototype.arrayBuffer=original;
                        return new Promise((resolve,reject)=>{window.__releaseImportRead=()=>original.call(file).then(resolve,reject);window.__importReadHeld=true;});};}''')
                    await page.set_input_files('#assetShelfImport', {'name': 'cancelled-inspection.json', 'mimeType': 'application/json', 'buffer': cancelled_bytes})
                    await page.wait_for_function('__importReadHeld'); await page.keyboard.press('Escape')
                    check('SHELF-KEYBOARD-05 closing pending inspection returns focus to its launcher (' + cancelled_kind + ')',
                          await page.evaluate("document.activeElement.id==='openAssetRecoveryShelfDetails'"))
                    await page.keyboard.press('Enter'); await page.wait_for_function('!assetShelfReading')
                    await tab_to(page, '#assetShelfImport')
                    current_status = await page.locator('#assetShelfStatus').inner_text()
                    await page.evaluate('__releaseImportRead()'); await page.wait_for_function('!assetShelfChanging')
                    cancelled_observation = await page.evaluate('''async()=>({imported:assetShelfImported!==null,
                      hidden:document.getElementById('assetShelfImportPreview').hidden,focus:document.activeElement.id,
                      dialog:document.getElementById('assetRecoveryShelfDialog').open,epoch:assetShelfImportEpoch})''')
                    check('SHELF-KEYBOARD-06 cancelled inspection cannot replace a reopened dialog (' + cancelled_kind + ')',
                          not cancelled_observation['imported'] and cancelled_observation['hidden'] and cancelled_observation['focus'] == 'assetShelfImport' and
                          await page.locator('#assetShelfStatus').inner_text() == current_status and
                          await page.evaluate('assetShelfStore.raw()') == cancelled_storage and len(writes) == before, cancelled_observation)
                # Foreign evidence is valid for inspection/export, never restoration.
                foreign_reads = [r for r in reads if '/api/assets/commands/' in r or '/api/assets/recovery-observation' in r]
                foreign = await page.evaluate('''async()=>{const [r]=await assetShelfStore.list(),p=structuredClone(r.payload),w='2'.repeat(32);p.workspace_id=w;p.metadata.workspace_id=w;
                  p.draft.title='<img src=x onerror="window.__shelfMarkupRan=true">';p.draft.notes='Literal imported text: <script>window.__shelfMarkupRan=true</script>';
                  if(p.operation){p.operation.command.workspace_id=w;p.operation.body=JSON.stringify(p.operation.command);}
                  if(p.conflict){p.conflict.workspace_id=w;p.conflict.current.forEach(m=>m.workspace_id=w);}
                  return StudioAssetRecoveryShelf.seal(r.slot,p,{id:'f'.repeat(32),generation:1,created_at:1,updated_at:1},crypto);}''')
                foreign_bundle = await page.evaluate('r=>StudioAssetRecoveryShelf.encode([r])', foreign)
                rejected_record = await page.evaluate('''async record=>{const p=structuredClone(record.payload);p.operation=null;p.conflict=null;
                  return StudioAssetRecoveryShelf.seal(record.slot,p,{id:'e'.repeat(32),generation:1,created_at:1,updated_at:1},crypto);}''', foreign)
                rejected_bundle = await page.evaluate('r=>StudioAssetRecoveryShelf.encode([r])', rejected_record)
                for rejected_context in ['active', 'reopened', 'committed-reopened']:
                    await import_inspect(page, rejected_bundle.encode())
                    rejected_raw = await page.evaluate('assetShelfStore.raw()')
                    await page.evaluate('''commitFirst => {const original=assetShelfStore.importRecords.bind(assetShelfStore);
                      window.__rejectedImportHeld=false;assetShelfStore.importRecords=async records=>{
                        await new Promise(resolve=>{window.__releaseRejectedImport=resolve;window.__rejectedImportHeld=true;});
                        assetShelfStore.importRecords=original;if(commitFirst)await original(records);
                        throw Error('Synthetic local import rejection');};}''', rejected_context == 'committed-reopened')
                    await activate(page, '#assetShelfImportConfirm'); await page.wait_for_function('__rejectedImportHeld')
                    if rejected_context != 'active':
                        await page.keyboard.press('Escape'); await page.keyboard.press('Enter')
                        await page.wait_for_function('document.getElementById("assetRecoveryShelfDialog").open && !assetShelfReading')
                        await tab_to(page, '#assetShelfImport')
                    rejected_status = await page.locator('#assetShelfStatus').inner_text()
                    await page.evaluate('__releaseRejectedImport()'); await page.wait_for_function('!assetShelfChanging')
                    rejected_observation = await page.evaluate('''async()=>({status:document.getElementById('assetShelfStatus').textContent,
                      imported:assetShelfImported!==null,hidden:document.getElementById('assetShelfImportPreview').hidden,
                      focus:document.activeElement.id,raw:await assetShelfStore.raw()})''')
                    if rejected_context == 'active':
                        expected_ui = 'Synthetic local import rejection' in rejected_observation['status'] and rejected_observation['imported'] and not rejected_observation['hidden'] and rejected_observation['focus'] == 'assetShelfImportConfirm'
                    else:
                        expected_ui = rejected_observation['status'] == rejected_status and not rejected_observation['imported'] and rejected_observation['hidden'] and rejected_observation['focus'] == 'assetShelfImport'
                    expected_storage = rejected_observation['raw'] == rejected_raw if rejected_context != 'committed-reopened' else rejected_record in await page.evaluate('assetShelfStore.list()') and rejected_observation['raw'] != rejected_raw
                    check('SHELF-IMPORT-11 import failure owns only its dialog context (' + rejected_context + ')',
                          expected_ui and expected_storage and len(writes) == before and
                          [r for r in reads if '/api/assets/commands/' in r or '/api/assets/recovery-observation' in r] == foreign_reads,
                          {k: v for k, v in rejected_observation.items() if k != 'raw'})
                await import_inspect(page, foreign_bundle.encode())
                await page.evaluate('''() => {const original=assetShelfStore.importRecords.bind(assetShelfStore);
                  window.__shelfImportHeld=false;assetShelfStore.importRecords=async records=>{
                    await new Promise(resolve=>{window.__releaseShelfImport=resolve;window.__shelfImportHeld=true;});
                    assetShelfStore.importRecords=original;return original(records);};}''')
                await activate(page, '#assetShelfImportConfirm'); await page.wait_for_function('__shelfImportHeld')
                await page.keyboard.press('Shift+Tab')
                check('SHELF-KEYBOARD-03 pending import allows navigation back to the file input',
                      await page.evaluate("document.activeElement.id==='assetShelfImport'"))
                await page.evaluate('__releaseShelfImport()'); await page.wait_for_function('assetShelfImported===null && !assetShelfChanging')
                check('SHELF-KEYBOARD-04 late import completion does not take newer focus',
                      await page.evaluate("document.activeElement.id==='assetShelfImport'"))
                check('SHELF-13 foreign Workspace is inspection-only', await page.locator('[data-shelf-restore="' + foreign['id'] + '"]').is_disabled() and len(writes) == before and
                      [r for r in reads if '/api/assets/commands/' in r or '/api/assets/recovery-observation' in r] == foreign_reads)
                await page.click('[data-shelf-inspect="' + foreign['id'] + '"]')
                check('SHELF-IMPORT-09 imported markup remains literal review text',
                      not await page.evaluate('!!window.__shelfMarkupRan') and await page.locator('#assetShelfRecords img').count() == 0 and
                      '<script>window.__shelfMarkupRan=true</script>' in await page.locator('#assetShelfInspection').inner_text())
                unknown_record = await page.evaluate('''async record=>{const p=structuredClone(record.payload);p.version=1;delete p.workspace_id;delete p.metadata.workspace_id;
                  if(p.operation){delete p.operation.command.workspace_id;p.operation.body=JSON.stringify(p.operation.command);}
                  if(p.conflict){p.conflict.workspace_id=null;p.conflict.current.forEach(m=>delete m.workspace_id);}
                  return StudioAssetRecoveryShelf.seal(record.slot,p,{id:'d'.repeat(32),generation:1,created_at:1,updated_at:1},crypto);}''', foreign)
                unknown_bundle = await page.evaluate('r=>StudioAssetRecoveryShelf.encode([r])', unknown_record)
                await import_inspect(page, unknown_bundle.encode()); await activate(page, '#assetShelfImportConfirm')
                await page.wait_for_function('assetShelfImported===null && !assetShelfChanging')
                check('SHELF-IMPORT-10 unknown Workspace stays inspection-only after native import',
                      await page.locator('[data-shelf-restore="' + unknown_record['id'] + '"]').is_disabled() and
                      await page.locator('[data-shelf-observe="' + unknown_record['id'] + '"]').is_disabled() and len(writes) == before and
                      [r for r in reads if '/api/assets/commands/' in r or '/api/assets/recovery-observation' in r] == foreign_reads)
                await page.set_viewport_size({'width': 390, 'height': 1000})
                await page.evaluate("document.documentElement.style.zoom='2'")
                check('SHELF-14 390px CSS 200% layout has no horizontal dialog overflow', await page.evaluate("(()=>{const d=document.querySelector('#assetRecoveryShelfDialog');return d.scrollWidth<=d.clientWidth+1&&d.getBoundingClientRect().right<=innerWidth+1;})()"))
                await evidence_screenshot(page, path=str(args.out / 'shelf-390-css200.png'))
                await page.evaluate("document.documentElement.style.zoom='1'")
                if zoom_worker is not None:
                    baseline_zoom = await page.evaluate('({width:innerWidth,dpr:devicePixelRatio,css:getComputedStyle(document.documentElement).zoom})')
                    zoom_receipt = await zoom_worker.evaluate('''async url=>{const tabs=await chrome.tabs.query({});const tab=tabs.find(t=>t.url===url);
                      if(!tab)throw Error('Synthetic tab not found');await chrome.tabs.setZoomSettings(tab.id,{mode:'automatic',scope:'per-tab'});
                      await chrome.tabs.setZoom(tab.id,2);return {tab:tab.id,zoom:await chrome.tabs.getZoom(tab.id),settings:await chrome.tabs.getZoomSettings(tab.id)};}''', page.url)
                    await page.wait_for_function('dpr=>devicePixelRatio>dpr*1.9', arg=baseline_zoom['dpr'])
                    measured_zoom = await page.evaluate('({width:innerWidth,dpr:devicePixelRatio,css:getComputedStyle(document.documentElement).zoom})')
                    check('SHELF-ZOOM-01 Chromium owns the 200-percent zoom without CSS scaling',
                          zoom_receipt['zoom'] == 2 and zoom_receipt['settings']['mode'] == 'automatic' and
                          measured_zoom['dpr'] > baseline_zoom['dpr'] * 1.9 and measured_zoom['width'] <= baseline_zoom['width'] / 2 + 1 and
                          measured_zoom['css'] == '1', {'browser': zoom_receipt, 'before': baseline_zoom, 'after': measured_zoom})
                    await tab_to(page, '#assetShelfExport')
                    check('SHELF-ZOOM-02 keyboard actions remain reachable at native 200-percent zoom',
                          await page.evaluate("(()=>{const d=document.querySelector('#assetRecoveryShelfDialog'),b=document.activeElement,r=b.getBoundingClientRect();return b.id==='assetShelfExport'&&r.left>=0&&r.right<=innerWidth+1&&d.scrollWidth<=d.clientWidth+1&&d.getBoundingClientRect().right<=innerWidth+1;})()"))
                    await evidence_screenshot(page, path=str(args.out / 'shelf-390-browser200.png'))
                    await zoom_worker.evaluate('id=>chrome.tabs.setZoom(id,1)', zoom_receipt['tab'])
                    await page.wait_for_function('dpr=>Math.abs(devicePixelRatio-dpr)<.01', arg=baseline_zoom['dpr'])
                await page.set_viewport_size({'width': 1280, 'height': 1000})
                if not args.inert:
                    # Two actual pages race the same expected digest. Neither may
                    # replace an unobserved revision from the other page.
                    other = await page_new()
                    records = await page.evaluate('assetShelfStore.list()'); base = records[0]
                    update = """async data=>{const r=data.record,p=structuredClone(r.payload);p.draft.notes=data.note;
                      const next=await StudioAssetRecoveryShelf.seal(r.slot,p,{id:r.id,generation:r.generation+1,created_at:r.created_at,updated_at:r.updated_at+1},crypto);
                      try{await assetShelfStore.put(next,r.sha256);return {written:true,refusal:null,sha256:next.sha256,note:data.note};}catch(error){if(!error.message.includes('changed'))throw error;return {written:false,refusal:error.message,sha256:next.sha256,note:data.note};}}"""
                    results = await asyncio.gather(page.evaluate(update, {'record': base, 'note': 'Tab A viewpoint'}),
                                                   other.evaluate(update, {'record': base, 'note': 'Tab B viewpoint'}))
                    # Synthetic fixture values only: retain both writer outcomes and the record's
                    # generation/digest before and after, so zero writers and two are distinguishable (#825).
                    after = await page.evaluate('assetShelfStore.list()'); final = next((r for r in after if r['id'] == base['id']), None)
                    race = {'writers': [dict(tab=tab, **outcome) for tab, outcome in zip(('A', 'B'), results)],
                            'record_id': base['id'], 'records_before': len(records), 'records_after': len(after),
                            'before': {'generation': base['generation'], 'sha256': base['sha256']},
                            'after': None if final is None else {'generation': final['generation'], 'sha256': final['sha256'],
                                                                 'notes': ((final.get('payload') or {}).get('draft') or {}).get('notes')}}
                    winners = [r for r in results if r['written']]
                    check('SHELF-NATIVE-01 two-tab expected-digest CAS admits exactly one writer', len(winners) == 1 and final is not None and
                          final['generation'] == base['generation'] + 1 and final['sha256'] == winners[0]['sha256'] and
                          final['payload']['draft']['notes'] == winners[0]['note'], race)
                    await other.evaluate("""() => {window.__shelfHeld=false;navigator.locks.request(StudioAssetRecoveryShelf.LOCK,()=>new Promise(resolve=>{window.__releaseShelfLock=resolve;window.__shelfHeld=true;}));}""")
                    await other.wait_for_function('__shelfHeld')
                    outcome = await page.evaluate("""async()=>{const r=(await assetShelfStore.list())[0];try{await assetShelfStore.remove(r.id,r.sha256);return 'unexpected';}catch(error){return error.name;}}""")
                    check('SHELF-NATIVE-02 held lock times out without unlocked fallback', outcome == 'AbortError')
                    await other.evaluate('__releaseShelfLock()')
                    await page.click('#assetShelfRefresh'); await page.wait_for_function('!assetShelfReading')
                    # A genuinely separate tab writes only the preserved older
                    # store. It cannot replace the current transactional owner.
                    current_entry = (await read_shelf_entry(page))[0]
                    older = await page.evaluate('''async record=>{const p=structuredClone(record.payload);p.draft.notes='Older version viewpoint';
                      return StudioAssetRecoveryShelf.encode([await StudioAssetRecoveryShelf.seal(record.slot,p,
                        {id:record.id,generation:record.generation+1,created_at:record.created_at,updated_at:record.updated_at+1},crypto)]);}''', final)
                    await other.evaluate('raw=>localStorage.setItem(StudioAssetRecoveryShelf.KEY,raw)', older)
                    await page.wait_for_function('raw=>localStorage.getItem(StudioAssetRecoveryShelf.KEY)===raw', arg=older)
                    await page.click('#assetShelfRefresh'); await page.wait_for_function('!assetShelfReading && !!assetShelfLegacyReview')
                    downloads = []
                    for selector in ['#assetShelfRawExport', '#assetShelfLegacyExport']:
                        async with page.expect_download() as info: await activate(page, selector)
                        downloads.append(Path(await (await info.value).path()).read_bytes())
                    check('SHELF-OWNER-01 quarantine exports preserve both exact bundles',
                          downloads == [current_entry['raw'].encode(), older.encode()] and (await read_shelf_entry(page))[0] == current_entry and len(writes) == before)
                    await page.set_viewport_size({'width': 390, 'height': 1000})
                    reachable = []
                    for selector in ['#assetShelfRawExport', '#assetShelfLegacyExport', '#assetShelfAcceptLegacy']:
                        await tab_to(page, selector)
                        reachable.append(await page.evaluate('''()=>{const b=document.activeElement,r=b.getBoundingClientRect(),d=document.getElementById('assetRecoveryShelfDialog');
                          return !b.hidden&&r.left>=0&&r.right<=innerWidth+1&&d.scrollWidth<=d.clientWidth+1;}'''))
                    check('SHELF-OWNER-02 quarantine actions remain reachable at 390px', all(reachable))
                    await evidence_screenshot(page, path=str(args.out / 'shelf-quarantine-390.png'))
                    acknowledgement_prompts = []
                    async def acknowledge(dialog):
                        acknowledgement_prompts.append(dialog.message); await dialog.accept()
                    page.on('dialog', acknowledge)
                    await activate(page, '#assetShelfAcceptLegacy'); await page.wait_for_function('!assetShelfChanging && !assetShelfReading && assetShelfLegacyReview===null')
                    acknowledged = (await read_shelf_entry(page))[0]
                    check('SHELF-OWNER-03 confirmed acknowledgement changes only compatibility metadata',
                          acknowledged['raw'] == current_entry['raw'] and acknowledged['version'] == current_entry['version'] and
                          acknowledged['legacy_digest'] == hashlib.sha256(older.encode()).hexdigest() and
                          await page.evaluate('assetShelfStore.legacyRaw()') == older and
                          len(acknowledgement_prompts) == 1 and 'Nothing will be merged or deleted.' in acknowledgement_prompts[0] and
                          await page.evaluate("document.activeElement.id==='assetShelfRefresh'") and len(writes) == before)
                    later_older = older + ' '
                    await other.evaluate('raw=>localStorage.setItem(StudioAssetRecoveryShelf.KEY,raw)', later_older)
                    await page.wait_for_function('raw=>localStorage.getItem(StudioAssetRecoveryShelf.KEY)===raw', arg=later_older)
                    await page.click('#assetShelfRefresh'); await page.wait_for_function('!assetShelfReading && !!assetShelfLegacyReview')
                    check('SHELF-OWNER-04 later legacy writes quarantine again without replacing current data',
                          (await read_shelf_entry(page))[0] == acknowledged and await page.evaluate('assetShelfStore.raw()') == current_entry['raw'] and
                          await page.evaluate('assetShelfStore.legacyRaw()') == later_older and len(writes) == before)
                    # Deliberate fixture acknowledgement keeps the next independent
                    # quota/capacity cases on their previously inspected current data.
                    await activate(page, '#assetShelfAcceptLegacy'); await page.wait_for_function('!assetShelfChanging && !assetShelfReading && assetShelfLegacyReview===null')
                    page.remove_listener('dialog', acknowledge); await other.close()
                    await page.set_viewport_size({'width': 1280, 'height': 1000})
                # Explicit discard is local, including an unresolved identity.
                discard_prompts = []
                async def accept(dialog):
                    discard_prompts.append(dialog.message)
                    await dialog.accept()
                page.on('dialog', accept)
                await page.click('[data-shelf-discard="' + foreign['id'] + '"]')
                await page.wait_for_function('!assetShelfReading')
                check('SHELF-15 discard changes neither SQLite nor original media', len(writes) == before and hashlib.sha256(source.read_bytes()).hexdigest() == original_hash)
                # A full shelf of distinct unresolved identities refuses through the real UI.
                retained_fixture = await page.evaluate('assetShelfStore.raw()')
                full_shelf = await page.evaluate('''async record=>{const records=[];for(let i=1;i<=StudioAssetRecoveryShelf.LIMITS.records;i++){
                  const p=structuredClone(record.payload);p.operation.command.request_id='capacity-request-'+i.toString().padStart(4,'0');
                  p.operation.body=JSON.stringify(p.operation.command);
                  records.push(await StudioAssetRecoveryShelf.seal(record.slot,p,{id:i.toString(16).padStart(32,'0'),generation:1,created_at:1,updated_at:1},crypto));}
                  return StudioAssetRecoveryShelf.encode(records);}''', imported_pending)
                await replace_shelf_raw(page, full_shelf, args.inert)
                await page.close(); retained = full_shelf if args.inert else None; page = await page_new()
                await page.evaluate('id=>openAsset(id)', ids[1])
                await page.fill('#assetNotes', 'Visible draft while twenty unresolved identities fill the shelf')
                await enable(page)
                await page.click('#saveAssetDetails'); await unknown(page)
                capacity_wire = await page.evaluate('assetDetailPending.body')
                capacity_status_before = await page.locator('#assetShelfDetailStatus').inner_text()
                # The editor's finally path retains its newer draft once more.
                # Wait for that real checkpoint result, including expected refusal,
                # before asserting the final persistence/status observation.
                capacity_error = await page.evaluate('assetShelfSession.flush().then(()=>null,error=>error.message)')
                capacity_status = await page.locator('#assetShelfDetailStatus').inner_text()
                check('SHELF-CAPACITY-01 full unresolved shelf refuses dependent save without eviction',
                      len(writes) == before and await page.evaluate('assetShelfStore.raw()') == full_shelf and
                      len(await page.evaluate('assetShelfStore.list()')) == 20 and
                      await page.input_value('#assetNotes') == 'Visible draft while twenty unresolved identities fill the shelf' and
                      capacity_error is not None and 'capacity' in capacity_error and 'capacity' in capacity_status,
                      {'status_before_final_checkpoint': capacity_status_before, 'status_after_final_checkpoint': capacity_status, 'checkpoint_error': capacity_error})
                await shelf(page, True); page.on('dialog', accept)
                await activate(page, '[data-shelf-discard="' + '1'.zfill(32) + '"]')
                await page.wait_for_function('!assetShelfChanging && !assetShelfReading')
                check('SHELF-CAPACITY-02 explicit local discard preserves the pending save and other identities',
                      len(writes) == before and await page.evaluate('assetShelfStore.list()') == json.loads(full_shelf)['records'][1:] and
                      await page.evaluate('assetDetailPending.body') == capacity_wire and
                      'may already have committed' in discard_prompts[-1] and 'does not cancel or undo server work' in discard_prompts[-1])
                # Restore synthetic fixture data between independent refusal scenarios.
                await page.evaluate('assetShelfSession.disable()')
                await replace_shelf_raw(page, retained_fixture, args.inert)
                await page.close(); retained = retained_fixture if args.inert else None; page = await page_new()
                await page.evaluate('id=>openAsset(id)', ids[1]); await shelf(page, True)
                await page.press('#assetShelfRefresh', 'Escape')
                await enable(page)
                await refuse_shelf_writes(page, args.inert)
                before = len(writes); await page.fill('#assetNotes', 'Draft during a shelf quota failure')
                await page.click('#saveAssetDetails'); await unknown(page)
                check('SHELF-16 quota refusal sends zero POST and retains exact pending command', len(writes) == before and await page.input_value('#assetNotes') == 'Draft during a shelf quota failure')
                await page.evaluate('__restoreShelfStorage()')
                check('SHELF-17 only existing read-only estimate POSTs accompany page boot', all(p['path'] == '/api/estimate' for p in fixture.POSTS))
                check('SHELF-18 no JavaScript exceptions', not errors)
                await context.close()
                if browser is not None:
                    await browser.close()
        except Exception as error:
            failure = error
        finally:
            http.shutdown(); http.server_close(); thread.join(timeout=5)
        (args.out / 'receipt.json').write_text(json.dumps({'mode': 'inert substitutions; NOT native storage/locks/crypto proof' if args.inert else 'native Chromium HTTP/SQLite/IndexedDB/Web Locks/WebCrypto', 'checks': checks, 'errors': errors, 'failure': str(failure) if failure else None, 'metadata_posts': len(writes)}, indent=2), encoding='utf-8')
        if failure:
            raise failure


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--inert', action='store_true')
    parser.add_argument('--out', type=Path, default=Path('.runtime/asset-recovery-shelf'))
    asyncio.run(exercise(parser.parse_args()))
