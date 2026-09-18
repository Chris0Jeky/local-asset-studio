"""Failed reference observation -> named setup -> reload -> replace, without inference.

Real Studio shell and SQLite setup persistence, synthetic references/other services.
Native: python tests/setup_lineage_browser.py --out .runtime/setup-lineage
Use --inert only where native navigation is policy-blocked (storage/API bridge doubles).
"""
import argparse
import asyncio
import hashlib
import json
import shutil
import tempfile
import threading
from pathlib import Path

from playwright.async_api import async_playwright
import studio_browser_smoke as fixture
from asset_detail_browser import inert_page
from workspace import AssetWorkspace

ROOT = Path(__file__).resolve().parents[1]


class Handler(fixture.Handler):
    store = None
    fail_check = True
    checks = 0

    def do_GET(self):
        if self.path == '/api/setups':
            return self.json(self.store.setups())
        super().do_GET()

    def do_POST(self):
        if self.path not in ('/api/setups', '/api/references/check'):
            return super().do_POST()
        data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        fixture.POSTS.append({'path': self.path, 'data': data})
        if self.path == '/api/setups':
            return self.json(self.store.save_setup(data))
        type(self).checks += 1
        if self.fail_check:
            return self.json({'error': 'Synthetic availability outage'}, 503)
        return self.json([{'file': file, 'available': file != 'missing.png', 'sha256': 'a'*64}
                          for file in data['files']])


def draft(preset='gentle-variation', two=False, file='source.png'):
    return {'version': 1, 'updatedAt': 1234, 'templateHash': None, 'pendingInputs': [],
            'recipe': {'preset': preset, 'batch': 1, 'references': [],
                       'controls': {'positive': 'Retain the original costume and setting', 'reference': file,
                                    **({'last_reference': 'last.png'} if two else {})},
                       'parent_assets': ['asset-0', 'asset-1'] if two else ['asset-0'],
                       'parent_by_input': {'reference': 'asset-0', **({'lastReference': 'asset-1'} if two else {})}}}


async def run(args):
    args.out.mkdir(parents=True, exist_ok=True)
    temporary = tempfile.TemporaryDirectory()
    Handler.store = AssetWorkspace(temporary.name)
    Handler.fail_check = True; Handler.checks = 0; fixture.POSTS.clear()
    server = fixture.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    checks = []; errors = []
    def check(identifier, expectation, actual):
        checks.append({'id': identifier, 'expectation': expectation, 'passed': bool(actual)})
        print(identifier, bool(actual), flush=True)
        if not actual and not args.baseline:
            raise AssertionError(expectation)
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(executable_path=args.chromium or shutil.which('chromium'),
                                                headless=True, args=['--no-sandbox'])
            async def new_page():
                page = await browser.new_page(viewport={'width': 1440, 'height': 1100}, reduced_motion='reduce')
                page.set_default_timeout(5000)
                page.on('pageerror', lambda error: errors.append(str(error)))
                if args.inert:
                    await inert_page(page, server.server_port)
                    await page.add_style_tag(content=(ROOT/'app/static/workshop.css').read_text())
                    await page.add_script_tag(content=(ROOT/'app/static/workshop.js').read_text())
                else: await page.goto(f'http://127.0.0.1:{server.server_port}/#create')
                await page.wait_for_function('!!catalog && !!selected && schemaAvailable')
                await page.evaluate("showView('create')")
                return page
            async def restore(page, value):
                await page.set_input_files('#uxImportDraft', {'name': 'draft.json', 'mimeType': 'application/json',
                                                             'buffer': json.dumps(value).encode()})
                await page.wait_for_function("document.querySelector('#uxNotice').textContent.includes('availability could not be checked') || document.querySelector('#uxNotice').textContent.includes('Draft restored')")
            async def open_saved(page):
                await page.wait_for_selector('#workshopSaved', state='attached')
                if not await page.locator('#workshopSaved').evaluate('n=>n.open'):
                    await page.click('#workshopSaved > summary')
            async def save(page, name):
                await open_saved(page)
                await page.fill('#saveName', name)
                await page.click('#save')
                await page.wait_for_function("document.querySelector('#status').textContent.includes('Setup not saved:') || document.querySelector('#status').textContent.includes('Setup saved in')")
            async def pull(page, asset, slot='reference'):
                await page.click('#uxPullAsset')
                await page.wait_for_selector('#uxSourcePicker[open]')
                await page.select_option('#uxSourceSlot', slot)
                await page.click(f'[data-ux-pull="{asset}"]')
                await page.wait_for_selector('#uxSourcePicker[open]', state='hidden')

            page = await new_page()
            await restore(page, draft())
            check('SETUP-01', 'Failed check clears the attachment but retains its uncertain source claim',
                  await page.evaluate("uploaded===null && parentByInput.reference==='asset-0' && parentAssets[0]==='asset-0'"))
            before = len(Handler.store.setups()); count = Handler.checks
            await save(page, 'Recoverable source setup')
            check('SETUP-02', 'Save after failed observation creates no durable setup', len(Handler.store.setups()) == before)
            check('SETUP-03', 'Recovery instruction identifies the reference input and reattachment',
                  'reattach Reference / first frame' in await page.inner_text('#status'))
            check('SETUP-17', 'Save error is also exposed beside Save in a polite status region',
                  await page.locator('#setupStatus').count() == 1 and
                  'reattach' in await page.inner_text('#setupStatus') and
                  await page.locator('#setupStatus').get_attribute('role') == 'status')
            check('SETUP-04', 'Blocked save preserves wording, name and in-memory lineage',
                  await page.input_value('#saveName') == 'Recoverable source setup' and
                  await page.input_value('#positive') == draft()['recipe']['controls']['positive'] and
                  await page.evaluate("parentByInput.reference==='asset-0' && parentAssets[0]==='asset-0'"))
            check('SETUP-05', 'Save does not silently retry the availability request', Handler.checks == count)
            await page.locator('#status').scroll_into_view_if_needed()
            await page.screenshot(path=str(args.out / 'blocked-save-desktop.png'))
            await page.set_viewport_size({'width': 390, 'height': 1100})
            await page.locator('#status').scroll_into_view_if_needed()
            check('SETUP-06', '390px recovery feedback remains within the page width',
                  await page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            await page.screenshot(path=str(args.out / 'blocked-save-390.png'))
            await page.set_viewport_size({'width': 1440, 'height': 1100})
            await pull(page, 'asset-0'); await save(page, 'Recovered setup')
            saved = Handler.store.setups()[0]['recipe']
            check('SETUP-07', 'Explicit reattachment saves the actual file with attributable lineage',
                  saved['controls'].get('reference') == 'a'*32+'_fixture.png' and
                  saved['parent_assets'] == ['asset-0'] and saved['parent_by_input'] == {'reference': 'asset-0'})
            second = await new_page()
            await open_saved(second)
            await second.wait_for_selector('#savedList [data-load="0"]')
            await second.locator('#savedList [data-load="0"]').evaluate("n=>n.scrollIntoView({block:'center'})")
            await second.screenshot(path=str(args.out / 'saved-setup-target.png'))
            hit = await second.locator('#savedList [data-load="0"]').evaluate('(el)=>{const r=el.getBoundingClientRect();return el.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2));}')
            check('SETUP-16', 'Saved setup button is not covered by the sticky recipe panel', hit)
            await second.click('#savedList [data-load="0"]')
            await pull(second, 'asset-1')
            check('SETUP-08', 'Fresh page reload followed by source replacement releases the old parent',
                  await second.evaluate("parentAssets.length===1 && parentAssets[0]==='asset-1' && parentByInput.reference==='asset-1'"))
            await second.close()
            # Two-input shape: one restored input must not hide the other unresolved claim.
            await restore(page, draft('h3-first-last', two=True))
            await save(page, 'Two frames')
            check('SETUP-09', 'Two unresolved inputs are both named',
                  'Reference / first frame and Last frame' in await page.inner_text('#status'))
            await pull(page, 'asset-0'); before = len(Handler.store.setups())
            await save(page, 'Still missing last frame')
            check('SETUP-10', 'Reattaching the first frame alone cannot save a stale last-frame claim',
                  len(Handler.store.setups()) == before and 'reattach Last frame' in await page.inner_text('#status'))
            await pull(page, 'asset-1', 'lastReference'); await save(page, 'Both restored')
            record = next(s for s in Handler.store.setups() if s['name'] == 'Both restored')['recipe']
            check('SETUP-11', 'Reattaching both inputs preserves their independent lineage mapping',
                  record['parent_by_input'] == {'reference': 'asset-0', 'lastReference': 'asset-1'})
            # A real file-input selection releases lineage but has no durable upload yet.
            for index, (input_id, key, source, other) in enumerate([
                    ('reference', 'reference', 'asset-0', 'asset-1'),
                    ('lastReference', 'last_reference', 'asset-1', 'asset-0')]):
                before = len(Handler.store.setups()); post_count = len(fixture.POSTS)
                await page.set_input_files('#'+input_id, str(ROOT/'examples/references/lantern-reference.png'))
                await save(page, 'Selected only '+input_id)
                check('SETUP-'+str(18+index*2), 'A local '+input_id+' selection cannot be silently omitted from a saved setup',
                      len(Handler.store.setups()) == before and
                      not any(p['path'] in {'/api/setups', '/api/upload'} for p in fixture.POSTS[post_count:]) and
                      'not uploaded' in await page.inner_text('#setupStatus') and
                      'Pull from library' in await page.inner_text('#setupStatus') and
                      await page.input_value('#saveName') == 'Selected only '+input_id and
                      await page.locator('#'+input_id).evaluate('(el)=>el.files.length===1') and
                      await page.evaluate('parentAssets') == [other])
                await pull(page, source, input_id); await save(page, 'Library recovery '+input_id)
                recovered = next(s for s in Handler.store.setups() if s['name']=='Library recovery '+input_id)['recipe']
                check('SETUP-'+str(19+index*2), 'Library reattachment recovers the '+input_id+' save with a staged file',
                      bool(recovered['controls'].get(key)) and recovered['parent_by_input'].get(input_id) == source)
            Handler.fail_check = False
            await restore(page, draft(file='missing.png'))
            check('SETUP-12', 'A confirmed missing file follows the existing claim-release path',
                  await page.evaluate('uploaded===null && parentAssets.length===0 && Object.keys(parentByInput).length===0'))
            await save(page, 'No source claimed')
            check('SETUP-13', 'A source-free setup remains savable without inventing lineage',
                  next(s for s in Handler.store.setups() if s['name'] == 'No source claimed')['recipe']['parent_assets'] == [])
            check('SETUP-14', 'No generation, backend switch, installation or other unexpected mutation',
                  all(p['path'] in {'/api/estimate', '/api/references/check', '/api/setups', '/api/assets/reference'}
                      for p in fixture.POSTS))
            check('SETUP-15', 'No JavaScript errors in the full Studio shell', not errors)
            await browser.close()
    finally:
        server.shutdown(); server.server_close(); temporary.cleanup()
        receipt = {'base_commit': '06bd93aed2f019cb978eb5795e9f116cfb7ff749',
                   'mode': 'inert: injected browser storage/API transport' if args.inert else 'native browser HTTP',
                   'scope': 'Actual Studio shell and SQLite setup storage; synthetic references and unrelated services; no inference.',
                   'app_js_sha256': hashlib.sha256((ROOT/'app/static/app.js').read_bytes()).hexdigest(),
                   'checks': checks, 'errors': errors, 'posts': fixture.POSTS,
                   'pass': sum(c['passed'] for c in checks), 'fail': sum(not c['passed'] for c in checks)}
        (args.out/'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    if any(not c['passed'] for c in checks) and not args.baseline: raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--inert', action='store_true')
    parser.add_argument('--baseline', action='store_true')
    parser.add_argument('--chromium')
    asyncio.run(run(parser.parse_args()))
