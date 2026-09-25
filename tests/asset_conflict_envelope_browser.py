"""Malformed conflict replies around the real scoped HTTP/SQLite owner.

Default uses native Chromium. --inert explicitly substitutes browser transport
and storage; it does not establish native origin or persistence behavior.
"""
import argparse
import asyncio
import copy
import hashlib
import io
import json
import shutil
import socket
import tempfile
import threading
import uuid
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
    flags = {'bad_post': True, 'lose': False, 'bad_get': False}
    failure = None
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        store = production.AssetWorkspace(root)
        image = root / 'synthetic.png'
        Image.new('RGB', (48, 64), (100, 110, 120)).save(image)
        original = hashlib.sha256(image.read_bytes()).hexdigest()
        identifier = store.register({'id':'conflict-envelope', 'outputs':[{'filename':image.name, 'media_type':'image'}]}, 0, image)
        scope = store.snapshot()['workspace_id']

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
                    writes.append(raw.decode('utf-8')); self.rfile = io.BytesIO(raw)
                    return super().do_POST()
                return fixture.Handler.do_POST(self)

            def _json(self, status, data):
                if self.path == '/api/assets/update':
                    if data.get('code') == 'asset_revision_conflict' and flags['bad_post']:
                        flags['bad_post'] = False; data = copy.deepcopy(data)
                        data['request_id'] = uuid.uuid4().hex
                        data['current'][0]['notes'] = 'FOREIGN_CONFLICT_SENTINEL'
                    if data.get('status') == 'applied' and flags['lose']:
                        flags['lose'] = False; self.close_connection = True
                        self.connection.shutdown(socket.SHUT_RDWR)
                        return
                if self.path.startswith('/api/assets/commands/') and flags['bad_get']:
                    flags['bad_get'] = False
                    status, data = 409, dict(error='Synthetic conflict on GET', code='asset_revision_conflict',
                        request_id=json.loads(writes[-1])['request_id'], workspace_id=scope,
                        conflict_ids=[identifier], missing_ids=[], current=[store.metadata(identifier, scope)])
                return super()._json(status, data)

        http = ThreadingHTTPServer(('127.0.0.1', 8191), Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True); thread.start()
        fixture.POSTS.clear()

        def check(name, value):
            checks.append(dict(id=name, passed=bool(value))); print(name, bool(value), flush=True)
            if not value: raise AssertionError(name)

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(executable_path=shutil.which('chromium'), headless=True, args=['--no-sandbox'])
                try:
                    page = await browser.new_page(viewport={'width':1280, 'height':1000}, reduced_motion='reduce')
                    page.set_default_timeout(8000); page.on('pageerror', lambda error: errors.append(str(error)))
                    if args.inert: await inert_page(page, 8191)
                    else: await page.goto('http://127.0.0.1:8191/#assets', timeout=20000)
                    await page.wait_for_function('!!catalog && !!selected')
                    await page.evaluate("showView('assets')"); await page.wait_for_function('assetState.assets.length===1')
                    check('CONFLICT-01 boot is read-only', not writes)
                    await page.evaluate('id=>openAsset(id)', identifier)
                    store.update(dict(ids=[identifier], action='edit', notes='Saved elsewhere', workspace_id=scope,
                                      expected_revisions={identifier:0}, request_id=uuid.uuid4().hex))
                    await page.fill('#assetNotes', 'My local edit'); await page.click('#saveAssetDetails')
                    await page.wait_for_function('!assetDetailBusy')
                    check('CONFLICT-02 wrong request preserves pending bytes and avoids comparison', await page.evaluate('!!assetDetailPending && !assetDetailConflict') and await page.evaluate('assetDetailPending.body') == writes[0])
                    check('CONFLICT-03 unverified metadata is neither rendered nor retained', 'FOREIGN_CONFLICT_SENTINEL' not in await page.locator('#assetDetailConflict').inner_text() and 'FOREIGN_CONFLICT_SENTINEL' not in await page.evaluate("sessionStorage.getItem('studio.asset-recovery.v1.detail')"))
                    await page.click('[data-asset-save-check]'); await page.wait_for_function('!assetDetailBusy')
                    check('CONFLICT-04 status reads cannot retry or drop unknown evidence', len(writes) == 1 and await page.evaluate('!!assetDetailPending'))
                    await page.click('[data-asset-save-retry]'); await page.wait_for_function('!assetDetailBusy')
                    check('CONFLICT-05 valid POST conflict compares without changing retained wire intent', len(writes) == 2 and writes[0] == writes[1] and await page.evaluate('!assetDetailPending && !!assetDetailConflict'))
                    await page.click('[data-asset-rebase]')
                    check('CONFLICT-06 explicit rebase is local and preserves edits', len(writes) == 2 and await page.input_value('#assetNotes') == 'My local edit')
                    await page.click('#saveAssetDetails'); await page.wait_for_function('!assetDetailBusy')
                    check('CONFLICT-07 reviewed new command uses fresh identity and current revision', store.get(identifier)['metadata_revision'] == 2 and json.loads(writes[2])['request_id'] != json.loads(writes[0])['request_id'] and json.loads(writes[2])['expected_revisions'][identifier] == 1)
                    flags['lose'] = True
                    await page.fill('#assetNotes', 'Committed with lost reply'); await page.click('#saveAssetDetails'); await page.wait_for_function('!assetDetailBusy && !!assetDetailPending')
                    flags['bad_get'] = True; before = len(writes)
                    await page.click('[data-asset-save-check]'); await page.wait_for_function('!assetDetailBusy')
                    check('CONFLICT-08 matching GET conflict cannot release command or authorize rebase', await page.evaluate('!!assetDetailPending && !assetDetailConflict') and len(writes) == before)
                    await page.click('[data-asset-save-check]'); await page.wait_for_function('!assetDetailBusy')
                    check('CONFLICT-09 later real receipt confirms without another POST', await page.evaluate('!assetDetailPending') and len(writes) == before and store.get(identifier)['metadata_revision'] == 3)
                    check('CONFLICT-10 no page errors, generation or original-media changes', not errors and all(p['path'] in ['/api/estimate','/api/references/check'] for p in fixture.POSTS) and hashlib.sha256(image.read_bytes()).hexdigest() == original)
                finally: await browser.close()
        except Exception as error:
            failure = error
        finally:
            http.shutdown(); http.server_close(); thread.join(timeout=5)
    (args.out / 'receipt.json').write_text(json.dumps(dict(mode='inert substitutions; real HTTP/SQLite' if args.inert else 'native Chromium; real HTTP/SQLite', checks=checks, errors=errors, metadata_posts=len(writes), failure=str(failure) if failure else None), indent=2), encoding='utf-8')
    if failure: raise failure
    if len(checks) != 10: raise AssertionError('Not every browser check ran')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inert', action='store_true')
    parser.add_argument('--out', type=Path, default=Path('.runtime/asset-conflict-envelope'))
    asyncio.run(exercise(parser.parse_args()))
