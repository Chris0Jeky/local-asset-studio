"""Selection/filter journeys over shipped UI and temporary production SQLite.

Native HTTP by default. --inert explicitly replaces browser storage/transport;
--baseline records missing expectations but never ignores JavaScript exceptions.
"""
import argparse
import asyncio
import hashlib
import io
import json
import shutil
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


async def exercise(args):
    args.out.mkdir(parents=True, exist_ok=True)
    checks, errors, writes, dialogs = [], [], [], []
    outcome = {'accept': False}
    failure = None
    mutation_gate = threading.Event(); mutation_gate.set()
    def check(case, expected, condition):
        checks.append({'id': case, 'expectation': expected, 'passed': bool(condition)})
        print(case, bool(condition), flush=True)
        if not condition and not args.baseline:
            raise AssertionError(expected)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        store = production.AssetWorkspace(root / 'workspace')
        ids = []
        for i in range(3):
            source = root / f'study-{i}.png'
            Image.new('RGB', (48, 64), (80 + i * 30, 110, 120)).save(source)
            identifier = store.register({'id': f'library-{i}', 'preset_name': 'Library QA', 'outputs': [{'filename': source.name, 'media_type': 'image'}]}, 0, source)
            ids.append(identifier)
            store.update({'ids': [identifier], 'action': 'edit', 'title': f'Study {i}', 'expected_revisions': {identifier: 0}, 'request_id': uuid.uuid4().hex})
        scope = store.snapshot()['workspace_id']
        empty = store.collection({'name': 'Empty project'})

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
                    writes.append(json.loads(raw)); self.rfile = io.BytesIO(raw)
                    if not mutation_gate.wait(10):
                        return self._json(503, {'error': 'Fixture mutation gate timed out'})
                    return super().do_POST()
                # Any export/generation request is evidence of an unexpected action, not authorized work.
                return fixture.Handler.do_POST(self)

        http = ThreadingHTTPServer(('127.0.0.1', 8191), Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True); thread.start()
        fixture.POSTS.clear()
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(executable_path=shutil.which('chromium'), headless=True, args=['--no-sandbox'])
                context = await browser.new_context(viewport={'width': 1440, 'height': 1100}, reduced_motion='reduce')
                page = await context.new_page(); page.set_default_timeout(6000)
                page.on('pageerror', lambda error: errors.append(str(error)))
                async def confirm(dialog):
                    dialogs.append(dialog.message)
                    await (dialog.accept() if outcome['accept'] else dialog.dismiss())
                page.on('dialog', confirm)
                if args.inert:
                    await inert_page(page, 8191)
                else:
                    await page.goto('http://127.0.0.1:8191/#assets', timeout=20000)
                await page.wait_for_function('!!catalog && !!selected && !!assetState.workspace_id')
                await page.evaluate("showView('assets')")
                await page.wait_for_selector(f'[data-asset-check="{ids[0]}"]')
                async def text(selector):
                    node = page.locator(selector)
                    return await node.inner_text() if await node.count() else ''
                async def search(value):
                    # Typing is debounced in the product; wait for the pending repaint, never a fixed sleep.
                    await page.fill('#assetSearch', value)
                    await page.wait_for_function('!assetSearchTimer')
                async def select_two():
                    await search('')
                    await page.evaluate("setAssetScope('all')")
                    for identifier in ids[:2]:
                        await page.locator(f'[data-asset-check="{identifier}"]').check()
                    await search('Study 0')
                await select_two()
                check('LIB-01', 'Filtering preserves both selected IDs', await page.evaluate('assetSelection.size') == 2)
                check('LIB-02', 'Matching and total counts are separate', '1 of 3' in await text('#assetVisibleCount'))
                check('LIB-03', 'Hidden selection is explicit beside the actions', '1 visible' in await text('#assetSelectionSummary') and '1 outside' in await text('#assetSelectionSummary'))
                details = page.locator('.asset-selection-context summary')
                if await details.count():
                    await details.click()
                check('LIB-04', 'Selection review lists the hidden asset by title', 'Study 1' in await text('#assetSelectedList'))
                boxes = [await page.locator(selector).bounding_box() for selector in ['#assetSearch', '#assetType', '#assetSort']]
                check('LIB-31', 'Desktop search and filter controls share one compact row', max(box['y'] for box in boxes) - min(box['y'] for box in boxes) < 10)
                await page.screenshot(path=str(args.out / 'selection-desktop.png'))
                before = len(writes)
                await page.click('[data-bulk="favorite"]')
                await page.wait_for_function('!assetLibraryBusy')
                check('LIB-05', 'Cancel hidden-item Favorite causes no metadata POST', len(writes) == before)
                check('LIB-06', 'Cancel leaves the entire selection in place', await page.evaluate('assetSelection.size') == 2)
                await select_two(); outcome['accept'] = True
                before = len(writes)
                await page.click('[data-bulk="favorite"]')
                await page.wait_for_function('!assetLibraryBusy && !assetLibraryPending')
                check('LIB-07', 'Consent sends one command with exactly the selected IDs', len(writes) == before + 1 and set(writes[-1]['ids']) == set(ids[:2]))
                check('LIB-08', 'The ordinary Workspace revision/request/scope contract remains', writes[-1].get('workspace_id') == scope and set(writes[-1]['expected_revisions']) == set(ids[:2]) and bool(writes[-1].get('request_id')))
                outcome['accept'] = False
                await select_two()
                before = len(fixture.POSTS)
                await page.click('[data-bulk="export"]')
                check('LIB-09', 'Cancel hidden-item export sends no pack request', len(fixture.POSTS) == before)
                await page.click('#nativeExport')
                check('LIB-10', 'Cancel hidden-item native handoff does not open export setup', not await page.locator('#nativeDialog').is_visible())
                if await page.locator('#nativeDialog').is_visible():
                    await page.click('#cancelNative')
                # Inspect trusted activation without allowing the fixture to leave the tested page.
                await page.evaluate("window.librarySceneEscaped=false;document.querySelector('#createScene').addEventListener('click',e=>{window.librarySceneEscaped=true;e.preventDefault();})")
                await page.click('#createScene')
                check('LIB-11', 'Cancel hidden-item scene handoff stops activation before the link', not await page.evaluate('window.librarySceneEscaped'))
                keep = page.locator('#keepVisibleSelection')
                if await keep.count():
                    await keep.click()
                check('LIB-12', 'Keep only visible prunes local selection to the one matching asset', await page.evaluate('ids=>JSON.stringify([...assetSelection])===JSON.stringify([ids[0]])', ids))
                check('LIB-13', 'Pruning returns keyboard focus to search', await keep.count() > 0 and await page.evaluate("document.activeElement.id==='assetSearch'"))
                await page.select_option('#assetSort', 'title')
                clear = page.locator('#clearAssetFilters')
                if await clear.count():
                    await clear.focus(); await page.keyboard.press('Enter')
                check('LIB-14', 'Keyboard filter reset keeps sort and selection', await page.input_value('#assetSearch') == '' and await page.input_value('#assetSort') == 'title' and await page.evaluate('assetSelection.size') == 1)
                # Real persisted Trash plus a filter miss, not a fake metadata response.
                metadata = store.metadata(ids[2])
                store.update({'ids': [ids[2]], 'action': 'trash', 'expected_revisions': {ids[2]: metadata['metadata_revision']}, 'request_id': uuid.uuid4().hex})
                await page.evaluate('refreshAssets(true)')
                await page.wait_for_function('id=>assetState.assets.some(a=>a.id===id&&a.trashed_at)', arg=ids[2])
                await page.click('#assetScopes [data-scope="trash"]')
                await search('absent query')
                check('LIB-15', 'Populated Trash with no matches is described as filtered', 'No matching assets' in await text('#assetGrid') and 'Trash is empty' not in await text('#assetGrid'))
                reset = page.locator('[data-asset-clear-filters]')
                if await reset.count():
                    await reset.click()
                check('LIB-16', 'Empty-state reset preserves Trash scope and reveals its asset', await page.evaluate('assetScope') == 'trash' and await page.locator('#assetGrid .asset-card').count() == 1)
                await page.evaluate("document.querySelector('#assetSearch').value='';setAssetScope('collection:'+" + json.dumps(empty['id']) + ')')
                check('LIB-17', 'An empty collection has a specific next step', 'This collection has no assets' in await text('#assetGrid'))
                await page.click('#assetScopes [data-scope="selected"]')
                check('LIB-18', 'Keepers means saved review state, not checkbox selection', await text('#assetScopeTitle') == 'Keepers' and 'No keepers yet' in await text('#assetGrid'))
                await page.evaluate("document.querySelector('#assetSearch').value='';setAssetScope('all')")
                await page.locator(f'[data-asset-check="{ids[0]}"]').check()
                mutation_gate.clear()
                await page.click('[data-bulk="selected"]')
                await page.wait_for_function('assetLibraryBusy')
                await page.locator(f'[data-asset-check="{ids[1]}"]').check()
                mutation_gate.set()
                await page.wait_for_function('!assetLibraryBusy && !assetLibraryPending')
                check('LIB-29', 'A late bulk success does not erase a selection changed while waiting', await page.evaluate('assetSelection.size') == 2)
                await page.click('#assetScopes [data-scope="unreviewed"]')
                await search('Study 0')
                check('LIB-30', 'Awaiting review counts only its own unreviewed active assets', '0 of 1' in await text('#assetVisibleCount'))
                await search('')
                # Organisation and bulk review over the same real records.
                await page.evaluate("setAssetScope('all')")
                await page.select_option('#assetGroup', 'run')
                check('LIB-32', 'Group by run gives each job its own section without losing a card', await page.locator('#assetGrid .asset-group').count() == 2 and await page.locator('#assetGrid .asset-card').count() == 2)
                check('LIB-33', 'Review next counts only unreviewed assets in this view', '(1 unreviewed)' in await text('#reviewNext'))
                await page.select_option('#assetGroup', 'none')
                check('LIB-34', 'Ungrouping restores the flat grid', await page.locator('#assetGrid .asset-group').count() == 0 and await page.locator('#assetGrid .asset-card').count() == 2)
                before = len(writes)
                await page.evaluate('ids=>{assetSelection=new Set(ids);renderAssets();}', ids[:2])
                # ids[0] is a keeper since LIB-29, so bulk review first names the saved review it replaces (#939).
                outcome['accept'] = True; asked = len(dialogs)
                await page.click('[data-review-bulk="needs_work"]')
                await page.wait_for_function('!assetBulkReviewBusy')
                outcome['accept'] = False
                check('LIB-37', 'Bulk review asks before replacing a saved keeper', len(dialogs) == asked + 1 and dialogs[-1].startswith('Replace 1 saved review? 1 keeper will change to Needs work.'))
                sent = writes[before:]
                check('LIB-35', 'Bulk review sends one ordinary single-asset command per selection', len(sent) == 2 and all(len(w['ids']) == 1 and w['action'] == 'edit' and w['review'] == 'needs_work' and w['expected_revisions'] for w in sent) and {w['ids'][0] for w in sent} == set(ids[:2]))
                saved = {a['id']: a['review'] for a in store.snapshot()['assets']}
                check('LIB-36', 'Bulk review reports its outcome and the stored reviews agree', 'Marked 2 of 2' in await text('#assetBulkReviewStatus') and all(saved[identifier] == 'needs_work' for identifier in ids[:2]))
                await page.evaluate('assetSelection.clear();renderAssets()')
                # Oversized gallery is a UI fixture only: no writes or large real-media claim.
                await page.evaluate("refreshAssets=async()=>{};setAssetScope('all');assetState.assets=Array.from({length:205},(_,i)=>({...assetState.assets[0],id:'large-'+i,title:'Large '+i,trashed_at:null,collections:[]}));renderAssets();")
                check('LIB-19', 'Select visible discloses the bounded batch size first', '200 of 205' in await text('#selectVisible'))
                await page.click('#selectVisible')
                check('LIB-20', 'Select visible selects 200 and explains the remaining matches', await page.evaluate('assetSelection.size') == 200 and '200 of 205' in await text('#assetMessage'))
                remaining = await page.evaluate('assetState.assets.find(a=>!assetSelection.has(a.id)).id')
                # click, not check(): refusing the 201st check is the required behavior.
                await page.locator(f'[data-asset-check="{remaining}"]').click()
                check('LIB-21', 'Manual 201st selection is refused without losing the first 200', await page.evaluate('assetSelection.size') == 200 and not await page.locator(f'[data-asset-check="{remaining}"]').is_checked())
                await page.evaluate("assetSelection=new Set(['large-0','missing-record']);renderAssets()")
                before = len(writes); await page.click('[data-bulk="trash"]')
                check('LIB-22', 'Unavailable selected IDs prevent bulk mutation without silent removal', len(writes) == before and await page.evaluate('assetSelection.size') == 2)
                if await details.count() and not await details.locator('..').evaluate('(e)=>e.open'):
                    await details.click()
                check('LIB-23', 'Unavailable records remain visible in selection review', 'Unavailable' in await text('#assetSelectedList'))
                for width in (390, 720):
                    await page.set_viewport_size({'width': width, 'height': 1100})
                    await page.locator('#assetBulk').scroll_into_view_if_needed()
                    check('LIB-24' if width == 390 else 'LIB-25', f'{width}px selection review fits without horizontal overflow', await page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
                    await page.screenshot(path=str(args.out / f'selection-{width}.png'))
                check('LIB-26', 'Selection feedback has polite status semantics', await page.locator('#assetSelectionSummary').count() > 0 and await page.locator('#assetSelectionSummary').get_attribute('aria-live') == 'polite')
                check('LIB-27', 'No generation, native preparation or backend mutation is sent', all(post['path'] in {'/api/estimate', '/api/references/check'} for post in fixture.POSTS))
                check('LIB-28', 'No JavaScript errors', not errors)
                await browser.close()
        except Exception as error:
            failure = repr(error)
        finally:
            mutation_gate.set()
            http.shutdown(); http.server_close(); thread.join(timeout=5)
            receipt = {
                'mode': 'inert storage/transport; actual metadata HTTP/SQLite' if args.inert else 'native HTTP/browser; actual metadata SQLite',
                'base': '28cfe3b54e221ce0f18b5dd8615dfc82dd6b49d3', 'checks': checks,
                'passed': sum(c['passed'] for c in checks), 'failed': sum(not c['passed'] for c in checks),
                'errors': errors, 'execution_error': failure, 'metadata_writes': writes, 'other_posts': fixture.POSTS, 'dialogs': dialogs,
                'source_sha256': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in ['app/static/workspace.js', 'app/static/index.html', 'app/static/style.css']},
                'limits': 'Synthetic UI/media; 205-row case is in-memory only. Not inference, native editor, actual zoom, screen-reader or large-library performance evidence.',
            }
            (args.out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
            print(json.dumps({k: receipt[k] for k in ['mode', 'passed', 'failed', 'errors', 'execution_error']}, indent=2))
    if failure or errors or (not args.baseline and any(not c['passed'] for c in checks)):
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--inert', action='store_true')
    parser.add_argument('--baseline', action='store_true')
    asyncio.run(exercise(parser.parse_args()))
