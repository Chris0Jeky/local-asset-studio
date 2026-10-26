"""Refused retries over actual HTTP/SQLite; --inert is not native-origin proof."""
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
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
from playwright.async_api import async_playwright
import studio_browser_smoke as fixture
from asset_detail_browser import inert_page
import server as production
from browser_ports import BoundPortGuard
from browser_shelf_owner import clear_shelf_storage


async def exercise(args):
    args.out.mkdir(parents=True, exist_ok=True)
    checks, errors, writes, reads = [], [], [], []
    flags = {'lose': False, 'refuse': False}
    refusal_started, release_refusal = threading.Event(), threading.Event()
    refusal_text = 'Synthetic transport refusal <img src=x onerror="window.__refusalMarkupRan=true"> ' + 'bounded-reason-' * 20
    with tempfile.TemporaryDirectory() as tmp:
        store = production.AssetWorkspace(tmp)
        source = Path(tmp) / 'synthetic.png'
        Image.new('RGB', (32, 32)).save(source)
        original = hashlib.sha256(source.read_bytes()).hexdigest()
        ids = [store.register({'id': f'refusal-{i}', 'outputs': [{'filename': source.name, 'media_type': 'image'}]}, 0, source) for i in range(2)]

        class Handler(BoundPortGuard, production.extend_handler(production.Handler)):
            studio = SimpleNamespace(assets=store, jobs={})
            json = fixture.Handler.json

            def do_GET(self):
                reads.append(self.path)
                if self.path == '/api/workspace' or self.path.startswith('/api/assets/') or self.path.startswith('/api/collections'):
                    return super().do_GET()
                return fixture.Handler.do_GET(self)

            def do_POST(self):
                if self.path=='/api/assets/selection':return super().do_POST()  # read-only Workspace observation, served by the real store
                if self.path == '/api/assets/update':
                    raw = self.rfile.read(int(self.headers['Content-Length']))
                    writes.append(raw.decode()); self.rfile = io.BytesIO(raw)
                    if flags['refuse']:
                        flags['refuse'] = False
                        refusal_started.set(); release_refusal.wait(timeout=8)
                        return self._json(403, {'error': refusal_text})
                    return super().do_POST()
                return fixture.Handler.do_POST(self)

            def _json(self, status, value):
                if self.path == '/api/assets/update' and value.get('status') == 'applied' and flags['lose']:
                    flags['lose'] = False; self.close_connection = True
                    self.connection.shutdown(socket.SHUT_RDWR)
                    return
                return super()._json(status, value)

        http = production.StudioHTTPServer(('127.0.0.1', args.port), Handler)
        worker = threading.Thread(target=http.serve_forever, daemon=True); worker.start()
        failure = None
        def check(name, value):
            checks.append({'id': name, 'passed': bool(value)})
            print(name, bool(value), flush=True)
            if not value: raise AssertionError(name)
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(executable_path=shutil.which('chromium'), headless=True, args=['--no-sandbox'])
                try:
                    async def ready(page):
                        await page.wait_for_function('!!catalog && !!selected && !!window.StudioShell && !!document.getElementById("homeView")')
                        await page.evaluate("showView('assets')")
                        await page.wait_for_function('assetState.assets.length===2')

                    async def accept(dialog):
                        await dialog.accept()

                    async def new_page(context):
                        page = await context.new_page(); page.set_default_timeout(8000)
                        page.on('pageerror', lambda error: errors.append(str(error))); page.on('dialog', accept)
                        if args.inert: await inert_page(page, http.server_port)
                        else: await page.goto(f'http://127.0.0.1:{http.server_port}/#assets', timeout=20000)
                        await ready(page); return page

                    async def shelf(page, detail=False):
                        if not detail and not await page.locator('#assetRecoveryDisclosure').evaluate('(node)=>node.open'):
                            await page.click('#assetRecoveryDisclosure > summary')
                        await page.click('#openAssetRecoveryShelfDetails' if detail else '#openAssetRecoveryShelf')
                        await page.wait_for_function('!assetShelfReading')

                    for slot in ['detail', 'library']:
                        context = await browser.new_context(viewport={'width': 390, 'height': 950}, reduced_motion='reduce', accept_downloads=True)
                        page = await new_page(context)
                        done = '!assetDetailBusy && !!assetDetailPending' if slot == 'detail' else '!assetLibraryBusy && !!assetLibraryPending'
                        settled = '!assetDetailBusy && !assetDetailPending' if slot == 'detail' else '!assetLibraryBusy && !assetLibraryPending'
                        panel = '#assetDetailRecovery' if slot == 'detail' else '#assetCommandRecovery'
                        if not args.inert:
                            await shelf(page); await page.check('#assetShelfEnabled')
                            await page.wait_for_function('assetShelfSession.enabled && !assetShelfChanging')
                            await page.keyboard.press('Escape')
                        flags['lose'] = True
                        if slot == 'detail':
                            await page.evaluate('id=>openAsset(id)', ids[0])
                            await page.fill('#assetNotes', 'Committed text, then a lost response')
                            await page.click('#saveAssetDetails')
                        else:
                            await page.evaluate('ids=>{assetSelection=new Set(ids);renderAssets();}', ids)
                            await page.click('[data-bulk="favorite"]')
                        await page.wait_for_function(done)
                        if slot == 'detail': await page.fill('#assetNotes', 'Newer unsaved text')
                        key = 'studio.asset-recovery.v1.' + slot
                        body = writes[-1]; flags['refuse'] = True; refusal_started.clear(); release_refusal.clear()
                        await page.click('[data-asset-save-retry]' if slot == 'detail' else '[data-asset-batch-retry]')
                        if not await asyncio.to_thread(refusal_started.wait, 4): raise AssertionError('Synthetic refusal did not reach the held boundary')
                        focus = 'assetNotes' if slot == 'detail' else 'assetSearch'
                        if slot == 'detail': await page.fill('#assetNotes', 'Newer typing while the refused attempt was pending')
                        else: await page.focus('#assetSearch')
                        before = json.loads(await page.evaluate('k=>sessionStorage.getItem(k)', key)); release_refusal.set()
                        await page.wait_for_function(done)
                        saved = json.loads(await page.evaluate('k=>sessionStorage.getItem(k)', key))
                        check(slot+'-01 retained exact recovery after 403', {k: v for k, v in saved.items() if k != 'last_refusal'} == before)
                        check(slot+'-02 exact retry body unchanged', writes[-1] == body)
                        check(slot+'-03 all targets retained', saved['operation']['command']['ids'] == ([ids[0]] if slot == 'detail' else ids))
                        explanation = saved.get('last_refusal', {})
                        check(slot+'-04 refusal is retained and rendered literally', explanation.get('message') == refusal_text and
                              explanation.get('status') == 403 and explanation.get('request_id') == saved['operation']['command']['request_id'] and
                              explanation.get('workspace_id') == saved['workspace_id'] and refusal_text in await page.locator(panel).inner_text() and
                              'Last recorded refusal' in await page.locator(panel).inner_text() and
                              await page.locator(panel + ' img').count() == 0 and not await page.evaluate('!!window.__refusalMarkupRan'))
                        check(slot+'-05 refusal completion preserves newer focus', await page.evaluate('document.activeElement.id') == focus)
                        attempts = len(writes); flags['lose'] = True
                        await page.click('[data-asset-save-retry]' if slot == 'detail' else '[data-asset-batch-retry]')
                        await page.wait_for_function(done)
                        history_text = await page.locator(panel).inner_text()
                        status_text = await page.locator('#assetDetailStatus' if slot == 'detail' else '#assetMessage').inner_text()
                        check(slot+'-05b later lost response keeps the refusal historical', len(writes) == attempts + 1 and writes[-1] == body and
                              json.loads(await page.evaluate('k=>sessionStorage.getItem(k)', key)) == saved and
                              'Last recorded refusal' in history_text and 'Last attempt refused' not in history_text and
                              'not confirmed' in status_text)
                        count = len(writes); request_id = saved['operation']['command']['request_id']
                        receipt_reads = sum('/api/assets/commands/' + request_id in path for path in reads)
                        if slot == 'detail':
                            await page.click('#closeAssetDialog'); await page.wait_for_function('!document.getElementById("assetDialog").open')
                            await page.click('[data-asset-recover-open]')
                        else:
                            await page.evaluate("showView('create');showView('assets')")
                        check(slot+'-06 returning to recovery preserves its explanation', refusal_text in await page.locator(panel).inner_text() and
                              json.loads(await page.evaluate('k=>sessionStorage.getItem(k)', key))['last_refusal'] == explanation and len(writes) == count)
                        if not args.inert:
                            await page.evaluate('assetShelfSession.flush()')
                            await page.reload(); await ready(page)
                            if slot == 'detail': await page.click('[data-asset-recover-open]')
                            check(slot+'-07 reload preserves explanation without automatic status or retry',
                                  json.loads(await page.evaluate('k=>sessionStorage.getItem(k)', key))['last_refusal'] == explanation and
                                  refusal_text in await page.locator(panel).inner_text() and len(writes) == count and
                                  sum('/api/assets/commands/' + request_id in path for path in reads) == receipt_reads)
                            await page.evaluate('assetShelfSession.flush()')
                            record = await page.evaluate('''async request=>(await assetShelfStore.list()).find(r=>r.payload.operation?.command.request_id===request)''', request_id)
                            check(slot+'-08 native checkpoint keeps refusal beside exact pending bytes', record['payload']['operation']['body'] == body and record['payload']['last_refusal'] == explanation)
                            await shelf(page, slot == 'detail')
                            async with page.expect_download() as download_info: await page.click('#assetShelfExport')
                            download = await download_info.value; exported = Path(await download.path()).read_bytes()
                            await clear_shelf_storage(page); await page.close(); page = await new_page(context)
                            await shelf(page)
                            await page.set_input_files('#assetShelfImport', {'name': 'synthetic-refusal.json', 'mimeType': 'application/json', 'buffer': exported})
                            await page.wait_for_function('assetShelfImported!==null && !assetShelfChanging')
                            check(slot+'-09 fresh-tab inspection is local and read-only', await page.evaluate('assetShelfStore.list()') == [] and
                                  await page.evaluate('k=>sessionStorage.getItem(k)', key) is None and len(writes) == count and
                                  sum('/api/assets/commands/' + request_id in path for path in reads) == receipt_reads)
                            await page.click('#assetShelfImportConfirm'); await page.wait_for_function('assetShelfImported===null && !assetShelfChanging')
                            await page.click('[data-shelf-restore="' + record['id'] + '"]')
                            await page.wait_for_function('!document.getElementById("assetRecoveryShelfDialog").open && !assetShelfChanging')
                            if slot == 'detail': await page.click('[data-asset-recover-open]')
                            restored = json.loads(await page.evaluate('k=>sessionStorage.getItem(k)', key))
                            check(slot+'-10 imported restoration preserves literal refusal and pending identity',
                                  restored['last_refusal'] == explanation and restored['operation']['body'] == body and
                                  refusal_text in await page.locator(panel).inner_text() and len(writes) == count and
                                  sum('/api/assets/commands/' + request_id in path for path in reads) == receipt_reads)
                        await page.locator(panel).scroll_into_view_if_needed()
                        await evidence_screenshot(page, path=str(args.out / (slot+'-retained-390.png')))
                        await page.click('[data-asset-save-check]' if slot == 'detail' else '[data-asset-batch-check]')
                        await page.wait_for_function(settled)
                        check(slot+'-11 historical confirmation is GET only', len(writes) == count and sum('/api/assets/commands/' + request_id in path for path in reads) == receipt_reads + 1)
                        check(slot+'-12 newer draft or complete selection survives', await page.input_value('#assetNotes') == 'Newer typing while the refused attempt was pending' if slot == 'detail' else await page.evaluate('assetSelection.size') == 2)
                        current = json.loads(await page.evaluate('k=>sessionStorage.getItem(k)', key) or 'null')
                        check(slot+'-13 confirmation clears current refusal presentation', not (current or {}).get('last_refusal') and 'Last recorded refusal' not in await page.locator(panel).inner_text())
                        if not args.inert:
                            history = await page.evaluate('assetShelfStore.list()')
                            check(slot+'-14 confirmation preserves historical shelf evidence until explicit discard', any(r['id'] == record['id'] and r['payload'].get('last_refusal') == explanation for r in history))
                        await evidence_screenshot(page, path=str(args.out / (slot+'-390.png')))
                        await context.close()
                    check('original bytes unchanged', hashlib.sha256(source.read_bytes()).hexdigest() == original)
                    check('no JavaScript exceptions', not errors)
                finally: await browser.close()
        except Exception as error: failure = error
        finally:
            release_refusal.set()
            http.shutdown(); http.server_close(); worker.join(timeout=5)
        (args.out / 'receipt.json').write_text(json.dumps({'mode': 'inert substitutions; real HTTP/SQLite' if args.inert else 'native Chromium HTTP/SQLite', 'checks': checks, 'errors': errors, 'failure': str(failure) if failure else None}, indent=2), encoding='utf-8')
        if failure: raise failure
        if len(checks) != (22 if args.inert else 32): raise AssertionError('Incomplete browser checks')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inert', action='store_true')
    parser.add_argument('--port', type=int, default=0, help='Fixed loopback port; 0 binds a free one')
    parser.add_argument('--out', type=Path, default=Path('.runtime/asset-recovery-refusal'))
    asyncio.run(exercise(parser.parse_args()))
