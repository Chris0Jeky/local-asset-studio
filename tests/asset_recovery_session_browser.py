"""Exact editor response ownership and focus over real temporary SQLite.

Native mode uses the shipped loopback shell. --inert explicitly substitutes
browser storage/transport; it does not certify native origin persistence.
"""
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
    flags = {'lose': False, 'hold': None}
    started, release = threading.Event(), threading.Event()
    failure = None
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        a, b = production.AssetWorkspace(root / 'a'), production.AssetWorkspace(root / 'b')
        source = root / 'synthetic.png'
        Image.new('RGB', (48, 64), (100, 110, 120)).save(source)
        original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        jobs = [{'id': f'session-{i}', 'preset_name': 'Synthetic recovery QA',
                 'outputs': [{'filename': source.name, 'media_type': 'image'}]} for i in range(2)]
        ids = [a.register(job, 0, source) for job in jobs]
        assert ids == [b.register(job, 0, source) for job in jobs]
        b_before = b.snapshot()

        class Handler(production.Handler):
            studio = SimpleNamespace(assets=a)
            json = fixture.Handler.json

            def do_GET(self):
                if self.path == '/api/workspace' or self.path.startswith('/api/assets/'):
                    return super().do_GET()
                return fixture.Handler.do_GET(self)

            def do_POST(self):
                if self.path == '/api/assets/update':
                    raw = self.rfile.read(int(self.headers['Content-Length']))
                    writes.append(raw.decode('utf-8')); self.rfile = io.BytesIO(raw)
                    return super().do_POST()
                return fixture.Handler.do_POST(self)

            def _json(self, status, data):
                is_write = self.path == '/api/assets/update'
                is_receipt = self.path.startswith('/api/assets/commands/')
                if data.get('status') == 'applied' and (is_write or is_receipt):
                    if flags['lose'] and is_write:
                        flags['lose'] = False; self.close_connection = True
                        self.connection.shutdown(socket.SHUT_RDWR)
                        return
                    if flags['hold'] == self.command:
                        flags['hold'] = None; started.set()
                        if not release.wait(15):
                            return super()._json(503, {'error': 'Synthetic held-response deadline'})
                return super()._json(status, data)

        http = ThreadingHTTPServer(('127.0.0.1', 8191), Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True); thread.start()
        fixture.POSTS.clear()

        def check(name, condition):
            checks.append({'id': name, 'passed': bool(condition)})
            print(name, bool(condition), flush=True)

        async def held(kind):
            started.clear(); release.clear(); flags['hold'] = kind

        async def wait_started():
            if not await asyncio.to_thread(started.wait, 10):
                raise AssertionError('The request did not reach its real-handler gate')

        async def refreshed(page):
            await page.wait_for_function('!assetRefreshing')
            await page.evaluate('refreshAssets(true)')

        async def uncertain(page, slot='detail'):
            await page.wait_for_function('!assetDetailBusy && !!assetDetailPending' if slot == 'detail' else '!assetLibraryBusy && !!assetLibraryPending')

        async def confirmed(page, slot='detail'):
            await page.wait_for_function('!assetDetailBusy && !assetDetailPending' if slot == 'detail' else '!assetLibraryBusy && !assetLibraryPending')

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(executable_path=shutil.which('chromium'), headless=True, args=['--no-sandbox'])
                try:
                    context = await browser.new_context(viewport={'width': 1280, 'height': 1000}, reduced_motion='reduce')
                    page = await context.new_page(); page.set_default_timeout(8000)
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    if args.inert: await inert_page(page, 8191)
                    else: await page.goto('http://127.0.0.1:8191/#assets')
                    await page.wait_for_function('!!catalog && !!selected')
                    await page.evaluate("showView('assets')"); await refreshed(page)
                    check('SESSION-01 boot sends no metadata mutation', not writes)
                    await page.evaluate('id=>openAsset(id)', ids[0])
                    flags['lose'] = True
                    await page.fill('#assetNotes', 'Synthetic committed draft'); await page.click('#saveAssetDetails'); await uncertain(page)
                    before = len(writes); await held('GET')
                    await page.click('[data-asset-save-check]'); await wait_started()
                    await page.fill('#assetNotes', 'Newer typing while receipt is held'); release.set(); await confirmed(page)
                    check('SESSION-02 status never resends metadata', len(writes) == before)
                    check('SESSION-03 newer typing and its focus survive receipt', await page.input_value('#assetNotes') == 'Newer typing while receipt is held' and await page.evaluate("document.activeElement.id==='assetNotes'"))
                    flags['lose'] = True
                    await page.click('#saveAssetDetails'); await uncertain(page)
                    await page.locator('[data-asset-save-check]').focus()
                    await page.keyboard.press('Enter'); await confirmed(page)
                    check('SESSION-04 resolved status control returns keyboard focus to Save', await page.evaluate("document.activeElement.id==='saveAssetDetails'"))
                    await page.click('#closeAssetDialog'); await page.wait_for_function("!document.querySelector('#assetDialog').open")
                    await refreshed(page)
                    await page.evaluate('ids=>{assetSelection=new Set(ids);renderAssets();}', ids)
                    flags['lose'] = True; await page.click('[data-bulk="favorite"]'); await uncertain(page, 'library')
                    await page.locator('[data-asset-batch-check]').focus(); before = len(writes)
                    await page.keyboard.press('Enter'); await confirmed(page, 'library')
                    check('SESSION-05 resolved library status returns focus to Refresh', await page.evaluate("document.activeElement.id==='workspaceRefresh'") and len(writes) == before)
                    await refreshed(page); await page.evaluate('id=>openAsset(id)', ids[0])
                    baseline = await page.evaluate('activeAsset.notes')
                    await page.fill('#assetNotes', 'Committed in A, not a claim about B'); await held('POST')
                    await page.click('#saveAssetDetails'); await wait_started()
                    raw = await page.evaluate("sessionStorage.getItem('studio.asset-recovery.v1.detail')")
                    Handler.studio.assets = b; await refreshed(page); release.set()
                    await uncertain(page)
                    check('SESSION-06 late detail receipt retains exact local recovery', await page.evaluate("sessionStorage.getItem('studio.asset-recovery.v1.detail')") == raw and await page.evaluate('activeAsset.notes') == baseline)
                    check('SESSION-07 same-ID replacement Workspace is not populated from old receipt', await page.evaluate('assetState.assets.every(a=>a.notes===""&&a.metadata_revision===0)') and b.snapshot() == b_before)
                    before = len(writes); Handler.studio.assets = a; await refreshed(page)
                    await page.click('[data-asset-save-check]'); await confirmed(page)
                    check('SESSION-08 return to A requires explicit read-only confirmation', len(writes) == before and await page.evaluate('activeAsset.notes') == 'Committed in A, not a claim about B')
                    await page.click('#closeAssetDialog'); await page.wait_for_function("!document.querySelector('#assetDialog').open")
                    await refreshed(page); await page.evaluate('ids=>{assetSelection=new Set(ids);renderAssets();}', ids)
                    await held('POST'); await page.click('[data-bulk="selected"]'); await wait_started()
                    raw = await page.evaluate("sessionStorage.getItem('studio.asset-recovery.v1.library')")
                    Handler.studio.assets = b; await refreshed(page); release.set(); await uncertain(page, 'library')
                    check('SESSION-09 late bulk receipt retains every target and exact body', await page.evaluate("sessionStorage.getItem('studio.asset-recovery.v1.library')") == raw)
                    check('SESSION-10 replacement Workspace keeps its current review values', await page.evaluate('assetState.assets.every(a=>a.review==="unreviewed"&&a.metadata_revision===0)') and b.snapshot() == b_before)
                    Handler.studio.assets = a; await refreshed(page); before = len(writes)
                    await page.click('[data-asset-batch-check]'); await confirmed(page, 'library')
                    check('SESSION-11 bulk historical confirmation does not repeat mutations', len(writes) == before and all(a.get(i)['review'] == 'selected' for i in ids))
                    await page.set_viewport_size({'width': 390, 'height': 900})
                    await page.screenshot(path=str(args.out / 'recovery-390.png'))
                    check('SESSION-12 no unexpected generation or original-media change', all(p['path'] in ['/api/estimate', '/api/references/check'] for p in fixture.POSTS) and hashlib.sha256(source.read_bytes()).hexdigest() == original_hash)
                    check('SESSION-13 no page exceptions', not errors)
                finally: await browser.close()
        except Exception as error:
            failure = error
        finally:
            release.set(); http.shutdown(); http.server_close(); thread.join(timeout=5)
        (args.out / 'receipt.json').write_text(json.dumps({'mode': 'inert browser substitutions; real HTTP/SQLite' if args.inert else 'native Chromium; real HTTP/SQLite', 'checks': checks, 'errors': errors, 'metadata_posts': len(writes), 'failure': str(failure) if failure else None}, indent=2), encoding='utf-8')
        if failure: raise failure
        if len(checks) != 13 or not all(c['passed'] for c in checks): raise AssertionError('Browser recovery contract failed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inert', action='store_true')
    parser.add_argument('--out', type=Path, default=Path('.runtime/asset-recovery-session'))
    asyncio.run(exercise(parser.parse_args()))
