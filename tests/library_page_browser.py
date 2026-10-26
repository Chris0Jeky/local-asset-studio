"""Native Library page ownership, unavailable details and same-run browsing.

The real HTTP/SQLite owners operate only on a temporary 205-asset Workspace.
Two explicit Favorite actions write fixture metadata; no generation is accepted.
"""
import argparse
import asyncio
import hashlib
import json
import shutil
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from PIL import Image
from playwright.async_api import async_playwright
import studio_browser_smoke as fixture
import server as production
from browser_ports import BoundPortGuard, evidence_screenshot

ROOT = Path(__file__).resolve().parents[1]


async def exercise(args):
    args.out.mkdir(parents=True, exist_ok=True)
    checks, errors, reads, writes = [], [], [], []
    failure = None
    diagnostics = {}

    def check(identifier, condition):
        checks.append({'id': identifier, 'passed': bool(condition)})
        print(identifier, bool(condition), flush=True)
        if not condition:
            raise AssertionError(identifier)

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        store = production.AssetWorkspace(root / 'workspace')
        source = root / 'fixture.png'
        Image.new('RGB', (48, 64), (80, 110, 120)).save(source)
        output = {'filename': source.name, 'media_type': 'image'}
        ids = [store.register({'id': 'shared-run' if i < 25 else f'other-{i}',
                               'created_at': i, 'preset_name': 'Library page fixture',
                               'outputs': [output] * 25 if i < 25 else [output]},
                              i if i < 25 else 0, source) for i in range(205)]
        with store.connection() as db:
            db.execute('UPDATE assets SET notes=? WHERE id=?', ('x' * 100_000, ids[202]))
        original_hash = hashlib.sha256(source.read_bytes()).hexdigest()

        class Handler(BoundPortGuard, production.extend_handler(production.Handler)):
            studio = SimpleNamespace(assets=store, jobs={})
            json = fixture.Handler.json

            def do_GET(self):
                if self.path.startswith(('/api/assets/page?', '/api/collections?')):
                    reads.append(self.path)
                if self.path == '/api/workspace' or self.path.startswith(('/api/assets/', '/api/collections')):
                    return super().do_GET()
                return fixture.Handler.do_GET(self)

            def do_POST(self):
                if self.path == '/api/assets/update':
                    writes.append(self.path)
                    return super().do_POST()
                if self.path == '/api/assets/selection':
                    return super().do_POST()
                if self.path in ('/api/generate', '/api/run', '/api/jobs'):
                    raise AssertionError('Generation is forbidden in this fixture')
                return fixture.Handler.do_POST(self)

        http = production.StudioHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        fixture.POSTS.clear()
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(executable_path=shutil.which('chromium'), headless=True, args=['--no-sandbox'])
                page = await browser.new_page(viewport={'width': 1440, 'height': 1100}, reduced_motion='reduce')
                page.set_default_timeout(8000)
                page.on('pageerror', lambda error: errors.append(str(error)))
                await page.goto(f'http://127.0.0.1:{http.server_port}/#assets', timeout=20000)

                async def settle():
                    await page.wait_for_function('!!assetPaging&&!assetRefreshing&&assetPaging.query===assetPageQuery()')

                await settle()
                await page.evaluate('if(window.studioReadPoller)studioReadPoller.pause?.()')
                check('PAGE-01 one oversized record leaves 99 complete records and an honest 100-row page',
                      await page.locator('#assetVisibleCount').inner_text() == '99 available of 100 observed assets on this page'
                      and await page.evaluate('assetState.assets.length') == 99
                      and ids[202] in await page.locator('#assetPaging').text_content()
                      and await page.locator('[data-asset-page="next"]').is_enabled())
                first = await page.evaluate('assetState.assets[0].id')
                await page.locator(f'[data-asset-check="{first}"]').check()
                await page.click('[data-asset-page="next"]')
                await settle()
                second = await page.evaluate('assetState.assets[0].id')
                await page.locator(f'[data-asset-check="{second}"]').check()
                await page.locator('#assetBulk details summary').click()
                await page.click('[data-asset-resolve-selection]')
                await page.wait_for_function('assetSelectionInfo().unresolved===0')
                before = await page.evaluate('assetState.assets.map(a=>a.id)')
                await page.locator(f'[data-asset-favorite="{second}"]').click()
                await page.wait_for_function('!assetLibraryBusy&&!assetRefreshing&&assetPaging.history.length===1&&assetSelectionInfo().unresolved===0')
                check('PAGE-02 a confirmed star reanchors page two and preserves fresh cross-page selection',
                      await page.evaluate('assetState.assets.map(a=>a.id)') == before
                      and set(await page.evaluate('[...assetSelection]')) == {first, second}
                      and await page.evaluate('id=>assetRecord(id).favorite', second)
                      and await page.locator('#assetPaging span').inner_text() == 'Page 2')
                page.once('dialog', lambda dialog: dialog.accept())
                await page.click('[data-bulk="favorite"]')
                await page.wait_for_function('!assetLibraryBusy&&!assetRefreshing&&assetSelection.size===0')
                check('PAGE-03 the bulk Favorite command also keeps page two',
                      await page.evaluate('assetState.assets.map(a=>a.id)') == before
                      and await page.locator('#assetPaging span').inner_text() == 'Page 2'
                      and store.metadata(first)['favorite'] and store.metadata(second)['favorite'])
                await page.click('[data-asset-page="next"]')
                await settle()
                page_three = await page.evaluate('assetState.assets.map(a=>a.id)')
                check('PAGE-04 explicit Next follows the new strict cursor and observes only five remaining rows',
                      len(page_three) == 5 and await page.locator('#assetPaging span').inner_text() == 'Page 3'
                      and await page.locator('[data-asset-page="next"]').is_disabled())
                await page.locator(f'#assetGrid [data-asset-open="{page_three[0]}"]').first.click()
                check('PAGE-05 the same-run preview does not claim its five loaded rows are the whole run',
                      'Loaded outputs: 5.' in await page.locator('#assetSameRun').inner_text()
                      and await page.locator('[data-asset-siblings="load"]').is_enabled())
                await page.click('[data-asset-siblings="load"]')
                await page.wait_for_function('assetSiblingPage?.loaded&&!assetSiblingRequest')
                check('PAGE-06 one explicit run read observes twenty outputs without changing the Library page',
                      await page.locator('#assetSameRun [data-asset-open]').count() == 20
                      and '20 available outputs on this page.' in await page.locator('#assetSameRun').inner_text()
                      and await page.evaluate('assetState.assets.map(a=>a.id)') == page_three)
                await page.click('[data-asset-siblings="next"]')
                await page.wait_for_function('assetSiblingPage?.history.length===1&&!assetSiblingRequest')
                check('PAGE-07 explicit run Next observes the final five and disables continuation',
                      await page.locator('#assetSameRun [data-asset-open]').count() == 5
                      and await page.locator('[data-asset-siblings="next"]').is_disabled())
                await page.click('[data-asset-siblings="previous"]')
                await page.wait_for_function('assetSiblingPage?.history.length===0&&!assetSiblingRequest')
                target = ids[10]
                await page.fill('#assetNotes', 'Retained draft')
                page.once('dialog', lambda dialog: dialog.dismiss())
                await page.locator(f'#assetSameRun [data-asset-open="{target}"]').click()
                check('PAGE-08 an off-page sibling obeys the existing draft guard',
                      await page.evaluate('activeAsset.id') == page_three[0]
                      and await page.input_value('#assetNotes') == 'Retained draft')
                page.once('dialog', lambda dialog: dialog.accept())
                await page.locator(f'#assetSameRun [data-asset-open="{target}"]').click()
                check('PAGE-09 explicit discard opens the exact resolved sibling with its complete saved metadata',
                      await page.evaluate('activeAsset.id') == target and await page.input_value('#assetNotes') == '')
                await page.set_viewport_size({'width': 390, 'height': 1100})
                await page.locator('#assetSameRun').scroll_into_view_if_needed()
                check('PAGE-10 run controls and sibling strip fit at 390px',
                      await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                      and await page.locator('[data-asset-siblings="next"]').is_visible())
                await evidence_screenshot(page, path=str(args.out / 'same-run-390.png'))
                await page.click('#closeAssetDialog')
                await page.click('[data-asset-page="previous"]')
                await settle()
                await page.click('[data-asset-page="previous"]')
                await settle()
                check('PAGE-11 explicit Previous reanchors historical page one after the confirmed edits',
                      await page.locator('#assetPaging span').inner_text() == 'Page 1'
                      and await page.locator('#assetVisibleCount').inner_text() == '99 available of 100 observed assets on this page')
                await page.locator('#assetPaging details summary').click()
                await page.locator('#assetPaging').scroll_into_view_if_needed()
                diagnostics = await page.evaluate('''() => ({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,
                  message:document.querySelector('#assetMessage')?.textContent,
                  overflowing:[...document.querySelectorAll('body *')].filter(el=>el.getBoundingClientRect().right>innerWidth+1).slice(-12).map(el=>({tag:el.tagName,id:el.id,cls:el.className,text:el.textContent.slice(0,150),right:el.getBoundingClientRect().right}))})''')
                await evidence_screenshot(page, path=str(args.out / 'unavailable-page-390.png'))
                check('PAGE-12 unavailable details remain readable at 390px',
                      await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                      and ids[202] in await page.locator('#assetPaging details').inner_text())
                queries = [parse_qs(urlsplit(url).query) for url in reads if url.startswith('/api/assets/page?')]
                check('PAGE-13 observations stay bounded and collection reads are atomic',
                      all(query.get('include_collections') == ['true'] for query in queries if 'job_id' not in query)
                      and all(query.get('limit') == ['20'] and query.get('job_id') == ['shared-run'] for query in queries if 'job_id' in query)
                      and not any(url.startswith('/api/collections?') for url in reads))
                check('PAGE-14 only two explicit metadata commands ran and the original media stayed untouched',
                      len(writes) == 2 and hashlib.sha256(source.read_bytes()).hexdigest() == original_hash
                      and all(post['path'] in {'/api/estimate', '/api/references/check'} for post in fixture.POSTS))
                check('PAGE-15 no JavaScript exceptions', not errors)
                await browser.close()
        except Exception as error:
            failure = repr(error)
        finally:
            http.shutdown()
            http.server_close()
            thread.join(5)
            receipt = {'mode': 'native Chromium HTTP and production SQLite', 'checks': checks, 'errors': errors,
                       'execution_error': failure, 'diagnostics': diagnostics, 'metadata_writes': writes, 'reads': reads, 'other_posts': fixture.POSTS,
                       'fixture_assets': 205, 'same_run_outputs': 25, 'unavailable_rows': 1,
                       'source_sha256': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                                         for path in ('app/static/workspace.js', 'studio_workflow/asset_reads.py')},
                       'limits': 'Synthetic media and temporary Workspace; no installed runtime or generation.'}
            (args.out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    if failure or errors or len(checks) != 15:
        raise AssertionError(failure or 'Library page fixture did not complete')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    asyncio.run(exercise(parser.parse_args()))
