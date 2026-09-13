"""Workspace-scoped recovery: actual HTTP/SQLite and shipped UI, no inference.

Default uses native sessionStorage/page.reload. --inert substitutes browser storage
and transport only and recreates the document, so is not native reload evidence.
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
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
from playwright.async_api import async_playwright
import studio_browser_smoke as fixture
from asset_detail_browser import inert_page
import server as production

ROOT = Path(__file__).resolve().parents[1]
KEY = 'studio.asset-recovery.v1.detail'
LIBRARY_KEY = 'studio.asset-recovery.v1.library'


async def exercise(args):
    args.out.mkdir(parents=True, exist_ok=True)
    checks, errors, writes, reads = [], [], [], []
    flags = {'lose': False, 'fail': False}
    failure = None
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        a, b = production.AssetWorkspace(root / 'a'), production.AssetWorkspace(root / 'b')
        source = root / 'source.png'; Image.new('RGB', (48, 64), (100, 110, 120)).save(source)
        job = {'id': 'scope-fixture', 'preset_name': 'Workspace identity QA', 'outputs': [{'filename': 'source.png', 'media_type': 'image'}]}
        identifier = a.register(job, 0, source)
        assert b.register(job, 0, source) == identifier
        scope_a, scope_b = a.snapshot()['workspace_id'], b.snapshot()['workspace_id']

        class Handler(production.Handler):
            studio = SimpleNamespace(assets=a)
            json = fixture.Handler.json
            def do_GET(self):
                if self.path == '/api/workspace' or self.path.startswith('/api/assets/'):
                    reads.append(self.path)
                    return super().do_GET()
                return fixture.Handler.do_GET(self)
            def do_POST(self):
                if self.path == '/api/assets/update':
                    raw = self.rfile.read(int(self.headers['Content-Length'])); writes.append(raw.decode('utf-8')); self.rfile = io.BytesIO(raw)
                    if flags['fail']:
                        flags['fail'] = False
                        return self._json(503, {'error': 'Injected pre-commit interruption'})
                    return super().do_POST()
                return fixture.Handler.do_POST(self)
            def _json(self, status, data):
                if flags['lose'] and self.path == '/api/assets/update' and data.get('status') == 'applied':
                    flags['lose'] = False; self.close_connection = True
                    self.connection.shutdown(socket.SHUT_RDWR)
                    return
                return super()._json(status, data)

        # Refuse an occupied production-allowed loopback port; never attach to an existing Studio.
        http = ThreadingHTTPServer(('127.0.0.1', 8191), Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True); thread.start(); fixture.POSTS.clear()
        def check(case, expectation, condition):
            checks.append({'id': case, 'expectation': expectation, 'passed': bool(condition)})
            print(case, bool(condition), flush=True)
            if not condition: raise AssertionError(expectation)
        async def ready(page):
            await page.wait_for_function('!!catalog && !!selected && !!assetState.workspace_id')
            await page.evaluate("showView('assets')")
        async def pending(page): await page.wait_for_function('!assetDetailBusy && !!assetDetailPending')
        async def clean(page): await page.wait_for_function('!assetDetailBusy && !assetDetailPending && !assetDetailConflict')
        async def open_asset(page):
            await page.click(f'[data-asset-open="{identifier}"]', strict=False)
            await page.wait_for_selector('#assetDialog[open]')
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(executable_path=shutil.which('chromium'), headless=True, args=['--no-sandbox'])
                context = await browser.new_context(viewport={'width': 1440, 'height': 1100}, reduced_motion='reduce')
                async def new_page(session=None):
                    page = await context.new_page(); page.set_default_timeout(6000)
                    page.on('pageerror', lambda e: errors.append(str(e)))
                    if args.inert: await inert_page(page, 8191, session)
                    else: await page.goto('http://127.0.0.1:8191/#assets')
                    await ready(page)
                    return page
                async def reload(page):
                    if args.inert:
                        session = await page.evaluate('keys=>Object.fromEntries(keys.map(k=>[k,sessionStorage.getItem(k)]).filter(([,v])=>v!==null))', [KEY, LIBRARY_KEY])
                        await page.close(); return await new_page(session)
                    await page.reload(); await ready(page); return page
                async def refresh(page, expected):
                    await page.evaluate('refreshAssets(true)')
                    await page.wait_for_function('id=>assetState.workspace_id===id', arg=expected)
                page = await new_page(); await open_asset(page)
                await page.fill('#assetNotes', 'Committed N; response intentionally lost')
                flags['lose'] = True; await page.click('#saveAssetDetails'); await pending(page)
                first_body = writes[-1]; first = json.loads(first_body)
                check('SCOPE-01', 'The actual submitted command binds the original Workspace', first['workspace_id'] == scope_a)
                check('SCOPE-02', 'Lost response retains exact request bytes before reload', await page.evaluate('key=>JSON.parse(sessionStorage.getItem(key)).operation.body', KEY) == first_body)
                await page.fill('#assetNotes', 'My newer unsaved review notes')
                other = await new_page()
                check('SCOPE-03', 'A second tab does not inherit the first tab draft', await other.evaluate('key=>sessionStorage.getItem(key)', KEY) is None)
                await open_asset(other); await other.fill('#assetNotes', 'Saved N+1 from the second tab'); await other.click('#saveAssetDetails'); await clean(other)
                await other.close()
                # Reopen SQLite; the receipt and Workspace identity are durable server state.
                Handler.studio.assets = production.AssetWorkspace(root / 'a')
                before, receipt_reads = len(writes), sum('/commands/' in x for x in reads)
                page = await reload(page)
                check('SCOPE-04', 'Reload does not submit or automatically check an earlier save', len(writes) == before and sum('/commands/' in x for x in reads) == receipt_reads)
                await page.click('[data-asset-recover-open]')
                check('SCOPE-05', 'Explicit recovery retains newer typing and opened revision', await page.input_value('#assetNotes') == 'My newer unsaved review notes' and await page.evaluate('activeAsset.metadata_revision') == 0)
                await page.click('[data-asset-save-check]'); await page.wait_for_function('!assetDetailBusy && !!assetDetailConflict')
                check('SCOPE-06', 'Receipt lookup is a Workspace-bound GET without another POST', len(writes) == before and any('/commands/' in x and 'workspace_id=' + scope_a in x for x in reads))
                check('SCOPE-07', 'Historical success exposes newer saved metadata as a conflict', 'Saved N+1 from the second tab' in await page.inner_text('#assetDetailConflict'))
                check('SCOPE-08', 'Conflict distinguishes a confirmed old save from a rejected save', 'earlier save is confirmed' in (await page.inner_text('#assetDetailConflict')).lower() and 'Nothing in your save was applied' not in await page.inner_text('#assetDetailConflict'))
                check('SCOPE-09', 'Current conflict never replaces newer local typing', await page.input_value('#assetNotes') == 'My newer unsaved review notes')
                await page.set_viewport_size({'width': 390, 'height': 1100}); await page.locator('#assetDetailConflict').scroll_into_view_if_needed()
                check('SCOPE-10', '390px conflict fits the dialog', await page.evaluate("document.querySelector('#assetDialog').scrollWidth<=document.querySelector('#assetDialog').clientWidth"))
                await page.screenshot(path=str(args.out / 'historical-receipt-conflict-390.png'))
                await page.click('[data-asset-rebase]')
                check('SCOPE-11', 'Rebase preserves unsaved notes without writing', len(writes) == before and await page.input_value('#assetNotes') == 'My newer unsaved review notes')
                await page.click('#saveAssetDetails'); await clean(page)
                check('SCOPE-12', 'Reviewed save uses a new request at the observed revision', json.loads(writes[-1])['expected_revisions'][identifier] == 2 and json.loads(writes[-1])['request_id'] != first['request_id'] and a.get(identifier)['metadata_revision'] == 3)
                # A different DB at the same URL and with the same asset ID must not accept A's edit.
                await page.fill('#assetNotes', 'Workspace A draft, not for B')
                Handler.studio.assets = b; await page.click('#saveAssetDetails'); await pending(page)
                wrong_body = writes[-1]
                check('SCOPE-13', 'Actual wrong-Workspace POST changes no B metadata', b.get(identifier)['metadata_revision'] == 0 and b.get(identifier)['notes'] == '')
                check('SCOPE-14', 'Wrong-Workspace rejection retains the original request identity', await page.evaluate('key=>JSON.parse(sessionStorage.getItem(key)).operation.body', KEY) == wrong_body)
                page = await reload(page); before = len(writes)
                await page.click('[data-asset-recover-open]')
                check('SCOPE-15', 'Same asset ID in a different Workspace cannot open A recovery', not await page.locator('#assetDialog').is_visible() and len(writes) == before and 'different workspace' in (await page.inner_text('#assetCommandRecovery')).lower())
                await page.set_viewport_size({'width':390,'height':1100}); await page.locator('#assetCommandRecovery').scroll_into_view_if_needed(); await page.screenshot(path=str(args.out / 'wrong-workspace-390.png'))
                outcome = await page.evaluate("""async ({id,scope})=>{try{await api('/api/assets/'+id+'/metadata?workspace_id='+scope);return {unexpected:true};}catch(e){return {status:e.status,...e.data};}}""", {'id': identifier, 'scope': scope_a})
                check('SCOPE-16', 'Metadata observation itself rejects a switched Workspace', outcome.get('status') == 409 and outcome.get('code') == 'asset_workspace_conflict' and 'current' not in outcome)
                Handler.studio.assets = a; await refresh(page, scope_a); await page.click('[data-asset-recover-open]')
                before = len(writes); await page.click('[data-asset-save-check]'); await pending(page)
                check('SCOPE-17', 'An unapplied original request remains unknown after return to A', len(writes) == before and 'No receipt' in await page.inner_text('#assetDetailStatus'))
                await page.click('[data-asset-save-retry]'); await clean(page)
                check('SCOPE-18', 'Explicit retry applies exact original bytes only in A', writes[-1] == wrong_body and a.get(identifier)['notes'] == 'Workspace A draft, not for B' and b.get(identifier)['metadata_revision'] == 0)
                # Pre-commit failure -> reload -> unknown GET -> exact retry once.
                await page.fill('#assetNotes', 'Interrupted before commit'); flags['fail'] = True
                revision = a.get(identifier)['metadata_revision']; await page.click('#saveAssetDetails'); await pending(page)
                interrupted = writes[-1]; page = await reload(page); await page.click('[data-asset-recover-open]')
                await page.click('[data-asset-save-check]'); await pending(page)
                check('SCOPE-19', 'Pre-commit failure never invents a receipt', a.get(identifier)['metadata_revision'] == revision and 'No receipt' in await page.inner_text('#assetDetailStatus'))
                await page.click('[data-asset-save-retry]'); await clean(page)
                check('SCOPE-20', 'Recovered pre-commit exact retry has one effect', writes[-1] == interrupted and a.get(identifier)['metadata_revision'] == revision + 1)
                await page.fill('#assetNotes', 'Legacy draft remains inspectable')
                await page.evaluate("""key=>{const r=JSON.parse(sessionStorage.getItem(key));r.version=1;delete r.workspace_id;delete r.metadata.workspace_id;sessionStorage.setItem(key,JSON.stringify(r));}""", KEY)
                page = await reload(page); before = len(writes); await page.click('[data-asset-recover-open]')
                await page.locator('#assetCommandRecovery details summary').click()
                check('SCOPE-21', 'Unscoped legacy draft is not rebound to the current Workspace', not await page.locator('#assetDialog').is_visible() and len(writes) == before and 'Legacy draft remains inspectable' in await page.inner_text('#assetCommandRecovery'))
                page.once('dialog', lambda d: d.accept()); await page.click('[data-asset-recovery-discard="detail"]')
                check('SCOPE-22', 'Explicit local discard clears only the journal', await page.evaluate('key=>sessionStorage.getItem(key)', KEY) is None and len(writes) == before)
                await open_asset(page)
                await page.evaluate("""()=>{const p=Object.getPrototypeOf(sessionStorage);window.__savedSet=p.setItem;p.setItem=function(){throw Error('Injected quota');};}""")
                await page.fill('#assetNotes', 'Keep in memory after quota failure'); before = len(writes); await page.click('#saveAssetDetails')
                check('SCOPE-23', 'Storage refusal prevents a new metadata POST', len(writes) == before and await page.input_value('#assetNotes') == 'Keep in memory after quota failure' and 'retain' in await page.inner_text('#assetDetailStatus'))
                await page.evaluate('()=>{Object.getPrototypeOf(sessionStorage).setItem=window.__savedSet;}')
                check('SCOPE-24', 'No generation or backend mutations occur', all(p['path'] in ['/api/estimate', '/api/references/check'] for p in fixture.POSTS))
                check('SCOPE-25', 'No JavaScript exceptions', not errors)
                await browser.close()
        except BaseException as error:
            failure = repr(error)
            raise
        finally:
            http.shutdown(); http.server_close(); thread.join(2)
            receipt = {'mode': 'inert storage/transport and document recreation' if args.inert else 'native HTTP, sessionStorage and page.reload',
                       'scope': 'Shipped Studio UI, production metadata routes, two temporary real SQLite Workspaces; no Studio/model process.',
                       'base_commit': '22ec26dc549a4648a6e94f80f5d3c870f03c6520',
                       'source_sha256': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in ['app/workspace.py', 'app/static/workspace.js', 'app/static/asset-recovery.js']},
                       'checks': checks, 'errors': errors, 'failure': failure, 'writes': writes, 'reads': reads,
                       'pass': sum(c['passed'] for c in checks), 'fail': sum(not c['passed'] for c in checks)}
            (args.out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    assert len(checks) == 25 and not errors, 'Incomplete or erroneous browser run'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--inert', action='store_true')
    asyncio.run(exercise(parser.parse_args()))
