"""Refused retries over actual HTTP/SQLite; --inert is not native-origin proof."""
import argparse
import asyncio
import hashlib
import io
import json
import shutil
import socket
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
from playwright.async_api import async_playwright
import studio_browser_smoke as fixture
from asset_detail_browser import inert_page
import server as production


async def exercise(args):
    args.out.mkdir(parents=True, exist_ok=True)
    checks, errors, writes = [], [], []
    flags = {'lose': False, 'refuse': False}
    with tempfile.TemporaryDirectory() as tmp:
        store = production.AssetWorkspace(tmp)
        source = Path(tmp) / 'synthetic.png'
        Image.new('RGB', (32, 32)).save(source)
        original = hashlib.sha256(source.read_bytes()).hexdigest()
        ids = [store.register({'id': f'refusal-{i}', 'outputs': [{'filename': source.name, 'media_type': 'image'}]}, 0, source) for i in range(2)]

        class Handler(production.Handler):
            studio = SimpleNamespace(assets=store)
            json = fixture.Handler.json

            def do_GET(self):
                if self.path == '/api/workspace' or self.path.startswith('/api/assets/'):
                    return super().do_GET()
                return fixture.Handler.do_GET(self)

            def do_POST(self):
                if self.path == '/api/assets/update':
                    raw = self.rfile.read(int(self.headers['Content-Length']))
                    writes.append(raw.decode()); self.rfile = io.BytesIO(raw)
                    if flags['refuse']:
                        flags['refuse'] = False
                        return self._json(403, {'error': 'Synthetic transport refusal'})
                    return super().do_POST()
                return fixture.Handler.do_POST(self)

            def _json(self, status, value):
                if self.path == '/api/assets/update' and value.get('status') == 'applied' and flags['lose']:
                    flags['lose'] = False; self.close_connection = True
                    self.connection.shutdown(socket.SHUT_RDWR)
                    return
                return super()._json(status, value)

        http = ThreadingHTTPServer(('127.0.0.1', 8191), Handler)
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
                    for slot in ['detail', 'library']:
                        context = await browser.new_context(viewport={'width': 390, 'height': 950}, reduced_motion='reduce')
                        page = await context.new_page(); page.set_default_timeout(8000)
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        if args.inert: await inert_page(page, 8191)
                        else: await page.goto('http://127.0.0.1:8191/#assets', timeout=20000)
                        await page.wait_for_function('!!catalog && !!selected && assetState.assets.length===2')
                        await page.evaluate("showView('assets')")
                        done = '!assetDetailBusy && !!assetDetailPending' if slot == 'detail' else '!assetLibraryBusy && !!assetLibraryPending'
                        settled = '!assetDetailBusy && !assetDetailPending' if slot == 'detail' else '!assetLibraryBusy && !assetLibraryPending'
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
                        before = await page.evaluate('k=>sessionStorage.getItem(k)', key)
                        body = writes[-1]; flags['refuse'] = True
                        await page.click('[data-asset-save-retry]' if slot == 'detail' else '[data-asset-batch-retry]')
                        await page.wait_for_function(done)
                        check(slot+'-01 retained exact recovery after 403', before == await page.evaluate('k=>sessionStorage.getItem(k)', key))
                        check(slot+'-02 exact retry body unchanged', writes[-1] == body)
                        saved = json.loads(before)
                        check(slot+'-03 all targets retained', saved['operation']['command']['ids'] == ([ids[0]] if slot == 'detail' else ids))
                        count = len(writes)
                        await page.click('[data-asset-save-check]' if slot == 'detail' else '[data-asset-batch-check]')
                        await page.wait_for_function(settled)
                        check(slot+'-04 historical confirmation is GET only', len(writes) == count)
                        check(slot+'-05 newer draft or complete selection survives', await page.input_value('#assetNotes') == 'Newer unsaved text' if slot == 'detail' else await page.evaluate('assetSelection.size') == 2)
                        await page.screenshot(path=str(args.out / (slot+'-390.png')))
                        await context.close()
                    check('original bytes unchanged', hashlib.sha256(source.read_bytes()).hexdigest() == original)
                    check('no JavaScript exceptions', not errors)
                finally: await browser.close()
        except Exception as error: failure = error
        finally:
            http.shutdown(); http.server_close(); worker.join(timeout=5)
        (args.out / 'receipt.json').write_text(json.dumps({'mode': 'inert substitutions; real HTTP/SQLite' if args.inert else 'native Chromium HTTP/SQLite', 'checks': checks, 'errors': errors, 'failure': str(failure) if failure else None}, indent=2), encoding='utf-8')
        if failure: raise failure
        if len(checks) != 12: raise AssertionError('Incomplete browser checks')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inert', action='store_true')
    parser.add_argument('--out', type=Path, default=Path('.runtime/asset-recovery-refusal'))
    asyncio.run(exercise(parser.parse_args()))
