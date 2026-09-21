"""Closed-tab recovery over the shipped UI and disposable real HTTP/SQLite.

Default: native localStorage, WebCrypto and Web Locks on the production loopback
origin. --inert explicitly substitutes browser storage/hash/locks/transport and
copies local data between documents; it is NOT native persistence evidence.
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

        class Handler(production.Handler):
            studio = SimpleNamespace(assets=store)
            json = fixture.Handler.json

            def do_GET(self):
                if self.path == '/api/workspace' or self.path.startswith('/api/assets/'):
                    reads.append(self.path)
                    return super().do_GET()
                return fixture.Handler.do_GET(self)

            def do_POST(self):
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

        http = ThreadingHTTPServer(('127.0.0.1', 8191), Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True); thread.start()
        fixture.POSTS.clear()

        def check(name, condition):
            checks.append({'id': name, 'passed': bool(condition)})
            print(name, bool(condition), flush=True)
            if not condition:
                raise AssertionError(name)

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(executable_path=shutil.which('chromium'), headless=True, args=['--no-sandbox'])
                context = await browser.new_context(viewport={'width': 1280, 'height': 1000}, reduced_motion='reduce', accept_downloads=True)
                retained = None

                async def page_new():
                    page = await context.new_page(); page.set_default_timeout(7000)
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    if args.inert:
                        await inert_page(page, 8191)
                        await page.expose_function('__shelfHash', lambda data: list(hashlib.sha256(bytes(data)).digest()))
                        await page.evaluate('''() => {
                          Object.defineProperty(window, 'crypto', {value:{getRandomValues: crypto.getRandomValues.bind(crypto),
                            subtle:{digest:async(name,data)=>new Uint8Array(await __shelfHash(Array.from(data))).buffer}}});
                          let tail=Promise.resolve();Object.defineProperty(navigator,'locks',{value:{request:(n,o,fn)=>{const p=tail.then(fn);tail=p.catch(()=>{});return p;}}});
                          assetShelfStore=StudioAssetRecoveryShelf.create({storage:()=>localStorage,locks:()=>navigator.locks,crypto});
                          assetShelfSession=StudioAssetRecoveryShelfSession.create({journal:assetRecovery,store:assetShelfStore,crypto,onStatus:assetShelfStatus});
                        }''')
                        if retained is not None:
                            await page.evaluate('raw=>localStorage.setItem(StudioAssetRecoveryShelf.KEY,raw)', retained)
                    else:
                        await page.goto('http://127.0.0.1:8191/#assets')
                    await page.wait_for_function('!!catalog && !!selected')
                    await page.evaluate("showView('assets')")
                    await page.wait_for_function('assetState.assets.length===2')
                    return page

                async def close_page(page):
                    nonlocal retained
                    await page.evaluate('assetShelfSession.flush()')
                    if args.inert:
                        retained = await page.evaluate('localStorage.getItem(StudioAssetRecoveryShelf.KEY)')
                    await page.close()

                async def shelf(page, details=False):
                    await page.click('#openAssetRecoveryShelfDetails' if details else '#openAssetRecoveryShelf')
                    await page.wait_for_function('!assetShelfReading')

                async def restore_pending(page, identifier):
                    await shelf(page)
                    record_id = await page.evaluate('''async id => (await assetShelfStore.list()).find(r=>r.payload.operation&&r.payload.id===id).id''', identifier)
                    await page.click(f'[data-shelf-restore="{record_id}"]')
                    await page.wait_for_function('!document.querySelector("#assetRecoveryShelfDialog").open')
                    await page.click('[data-asset-recover-open]')

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
                await restore_pending(page, ids[1]); await page.click('[data-asset-save-check]'); await unknown(page)
                check('SHELF-09 unknown receipt never triggers retry', len(writes) == before and store.get(ids[1])['metadata_revision'] == 0)
                await page.click('[data-asset-save-retry]'); await page.wait_for_function('!assetDetailBusy && !assetDetailPending')
                check('SHELF-10 explicit retry preserves exact body and commits once', writes[-1] == retry_wire and store.get(ids[1])['metadata_revision'] == 1)
                await shelf(page, True)
                async with page.expect_download() as download_info:
                    await page.click('#assetShelfExport')
                download = await download_info.value; exported = Path(await download.path()).read_bytes()
                before = len(writes)
                await page.evaluate('''() => {localStorage.removeItem(StudioAssetRecoveryShelf.KEY);sessionStorage.removeItem('studio.asset-recovery.v1.detail');}''')
                await page.set_input_files('#assetShelfImport', {'name': 'synthetic-recovery.json', 'mimeType': 'application/json', 'buffer': exported})
                await page.wait_for_function('assetShelfImported!==null')
                check('SHELF-11 import inspection does not persist or mutate', len(writes) == before and await page.evaluate('localStorage.getItem(StudioAssetRecoveryShelf.KEY)') is None)
                await page.click('#assetShelfImportConfirm'); await page.wait_for_function('assetShelfImported===null')
                check('SHELF-12 explicit import is local only and preserves pending identities', len(writes) == before and len(await page.evaluate('assetShelfStore.list()')) >= 2)
                # Foreign evidence is valid for inspection/export, never restoration.
                foreign = await page.evaluate('''async()=>{const [r]=await assetShelfStore.list(),p=structuredClone(r.payload),w='2'.repeat(32);p.workspace_id=w;p.metadata.workspace_id=w;
                  if(p.operation){p.operation.command.workspace_id=w;p.operation.body=JSON.stringify(p.operation.command);}
                  if(p.conflict){p.conflict.workspace_id=w;p.conflict.current.forEach(m=>m.workspace_id=w);}
                  return StudioAssetRecoveryShelf.seal(r.slot,p,{id:'f'.repeat(32),generation:1,created_at:1,updated_at:1},crypto);}''')
                await page.evaluate('r=>assetShelfStore.importRecords([r])', foreign)
                await page.click('#assetShelfRefresh'); await page.wait_for_function('!assetShelfReading')
                check('SHELF-13 foreign Workspace is inspection-only', await page.locator('[data-shelf-restore="' + foreign['id'] + '"]').is_disabled() and len(writes) == before)
                await page.click('[data-shelf-inspect="' + foreign['id'] + '"]')
                await page.set_viewport_size({'width': 390, 'height': 1000})
                await page.evaluate("document.documentElement.style.zoom='2'")
                check('SHELF-14 390px CSS 200% layout has no horizontal dialog overflow', await page.evaluate("(()=>{const d=document.querySelector('#assetRecoveryShelfDialog');return d.scrollWidth<=d.clientWidth+1&&d.getBoundingClientRect().right<=innerWidth+1;})()"))
                await page.screenshot(path=str(args.out / 'shelf-390-css200.png'))
                await page.evaluate("document.documentElement.style.zoom='1'")
                await page.set_viewport_size({'width': 1280, 'height': 1000})
                if not args.inert:
                    # Two actual pages race the same expected digest. Neither may
                    # replace an unobserved revision from the other page.
                    other = await page_new()
                    base = (await page.evaluate('assetShelfStore.list()'))[0]
                    update = """async data=>{const r=data.record,p=structuredClone(r.payload);p.draft.notes=data.note;
                      const next=await StudioAssetRecoveryShelf.seal(r.slot,p,{id:r.id,generation:r.generation+1,created_at:r.created_at,updated_at:r.updated_at+1},crypto);
                      try{await assetShelfStore.put(next,r.sha256);return true;}catch(error){if(!error.message.includes('changed'))throw error;return false;}}"""
                    results = await asyncio.gather(page.evaluate(update, {'record': base, 'note': 'Tab A viewpoint'}),
                                                   other.evaluate(update, {'record': base, 'note': 'Tab B viewpoint'}))
                    check('SHELF-NATIVE-01 two-tab expected-digest CAS admits exactly one writer', results.count(True) == 1)
                    await other.evaluate("""() => {window.__shelfHeld=false;navigator.locks.request(StudioAssetRecoveryShelf.LOCK,()=>new Promise(resolve=>{window.__releaseShelfLock=resolve;window.__shelfHeld=true;}));}""")
                    await other.wait_for_function('__shelfHeld')
                    outcome = await page.evaluate("""async()=>{const r=(await assetShelfStore.list())[0];try{await assetShelfStore.remove(r.id,r.sha256);return 'unexpected';}catch(error){return error.name;}}""")
                    check('SHELF-NATIVE-02 held lock times out without unlocked fallback', outcome == 'AbortError')
                    await other.evaluate('__releaseShelfLock()'); await other.close()
                    await page.click('#assetShelfRefresh'); await page.wait_for_function('!assetShelfReading')
                # Explicit discard is local, including an unresolved identity.
                async def accept(dialog):
                    await dialog.accept()
                page.on('dialog', accept)
                await page.click('[data-shelf-discard="' + foreign['id'] + '"]')
                await page.wait_for_function('!assetShelfReading')
                check('SHELF-15 discard changes neither SQLite nor original media', len(writes) == before and hashlib.sha256(source.read_bytes()).hexdigest() == original_hash)
                await page.press('#assetShelfRefresh', 'Escape')
                await enable(page)
                await page.evaluate('''() => {const proto=Object.getPrototypeOf(localStorage),set=proto.setItem;window.__restoreShelfStorage=()=>{proto.setItem=set;};proto.setItem=function(k,v){if(k===StudioAssetRecoveryShelf.KEY)throw new DOMException('Synthetic quota','QuotaExceededError');return set.call(this,k,v);};}''')
                before = len(writes); await page.fill('#assetNotes', 'Draft during a shelf quota failure')
                await page.click('#saveAssetDetails'); await unknown(page)
                check('SHELF-16 quota refusal sends zero POST and retains exact pending command', len(writes) == before and await page.input_value('#assetNotes') == 'Draft during a shelf quota failure')
                await page.evaluate('__restoreShelfStorage()')
                check('SHELF-17 only existing read-only estimate POSTs accompany page boot', all(p['path'] == '/api/estimate' for p in fixture.POSTS))
                check('SHELF-18 no JavaScript exceptions', not errors)
                await browser.close()
        except Exception as error:
            failure = error
        finally:
            http.shutdown(); http.server_close(); thread.join(timeout=5)
        (args.out / 'receipt.json').write_text(json.dumps({'mode': 'inert substitutions; NOT native storage/locks/crypto proof' if args.inert else 'native Chromium HTTP/SQLite/localStorage/Web Locks/WebCrypto', 'checks': checks, 'errors': errors, 'failure': str(failure) if failure else None, 'metadata_posts': len(writes)}, indent=2), encoding='utf-8')
        if failure:
            raise failure


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--inert', action='store_true')
    parser.add_argument('--out', type=Path, default=Path('.runtime/asset-recovery-shelf'))
    asyncio.run(exercise(parser.parse_args()))
