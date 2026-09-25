"""Library refresh continuity in the actual shell and temporary Workspace.

Native HTTP by default; --inert labels substituted storage/transport. All server
changes are fixture-side setup (another client), never generation or user files.
"""
import argparse
import asyncio
import hashlib
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
    checks, errors, failure = [], [], None
    def check(identifier, expectation, value):
        checks.append({'id': identifier, 'expectation': expectation, 'passed': bool(value)})
        print(identifier, bool(value), flush=True)
        if not value and not args.baseline:
            raise AssertionError(expectation)
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder); store = production.AssetWorkspace(root)
        ids = []
        for i in range(3):
            source = root / f'original-{i}.png'
            Image.new('RGB', (48, 64), (90 + 40 * i, 110, 140)).save(source)
            ids.append(store.register({'id': f'grid-{i}', 'created_at': 10-i, 'preset_name': 'Grid QA',
                                      'outputs': [{'filename': source.name, 'media_type': 'image'}]}, 0, source))
        def edit(identifier, **values):
            store.update({'ids': [identifier], 'action': 'edit', 'request_id': uuid.uuid4().hex,
                          'expected_revisions': {identifier: store.metadata(identifier)['metadata_revision']}, **values})
        for i, identifier in enumerate(ids): edit(identifier, title=f'Study {i}')
        class Handler(production.Handler):
            studio = SimpleNamespace(assets=store)
            json = fixture.Handler.json
            def _safe_host(self):
                return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'
            def do_GET(self):
                if self.path == '/api/workspace' or self.path.startswith('/api/assets/'):
                    return super().do_GET()
                return fixture.Handler.do_GET(self)
            def do_POST(self):
                # Not a mutation harness. All page writes are recorded inert fixture calls.
                return fixture.Handler.do_POST(self)
        http = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True); thread.start()
        fixture.POSTS.clear()
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(executable_path=shutil.which('chromium'), headless=True, args=['--no-sandbox'])
                page = await browser.new_page(viewport={'width': 1440, 'height': 1100}, reduced_motion='reduce')
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.set_default_timeout(6000)
                if args.inert: await inert_page(page, http.server_port)
                else: await page.goto(f'http://127.0.0.1:{http.server_port}/#assets')
                await page.wait_for_function('!!catalog && !!selected && !!assetState.workspace_id')
                await page.evaluate("showView('assets');if(window.studioReadPoller)studioReadPoller.pause?.();")
                await page.wait_for_selector(f'[data-asset-check="{ids[0]}"]')
                await page.evaluate("""ids=>{
                    window.gridIds=ids;
                    window.card=id=>document.querySelector('[data-asset-check="'+id+'"]')?.closest('.asset-card');
                    window.remember=id=>{window.keptCard=card(id);window.keptImage=keptCard?.querySelector('img');window.keptCheck=keptCard?.querySelector('input');window.keptStar=keptCard?.querySelector('.asset-star');};
                }""", ids)
                async def refresh():
                    await page.wait_for_function('!assetRefreshing')
                    await page.evaluate('refreshAssets(true)')
                    await page.wait_for_function('!assetRefreshing')
                async def remember(identifier=ids[0]): await page.evaluate('remember', identifier)
                await remember();await page.locator(f'[data-asset-check="{ids[0]}"]').focus();await refresh()
                check('GRID-01', 'An unchanged forced refresh reuses the card', await page.evaluate('card(gridIds[0])===keptCard'))
                check('GRID-02', 'An unchanged forced refresh reuses the image', await page.evaluate('card(gridIds[0]).querySelector("img")===keptImage'))
                check('GRID-03', 'A focused checkbox survives the refresh', await page.evaluate('document.activeElement===keptCheck'))
                await page.select_option('#assetGroup', 'run')
                check('GRID-32', 'Grouping and Review next retain the current view counts', await page.evaluate('document.querySelectorAll("#assetGrid .asset-group").length===3 && document.querySelectorAll("#assetGrid .asset-card").length===3 && document.querySelector("#reviewNext").textContent.includes("3 unreviewed") && !document.querySelector("#reviewNext").disabled'))
                await page.locator(f'[data-asset-check="{ids[0]}"]').focus();await refresh()
                check('GRID-33', 'Grouped refresh retains card, image and focused control', await page.evaluate('card(gridIds[0])===keptCard && keptImage.isConnected && document.activeElement===keptCheck'))
                await page.evaluate('window.groupMutations=[];window.groupObserver=new MutationObserver(items=>groupMutations.push(...items));groupObserver.observe(document.querySelector("#assetGrid"),{subtree:true,childList:true,attributes:true,characterData:true});')
                await refresh()
                check('GRID-34', 'An unchanged grouped refresh makes no grid mutations', await page.evaluate('groupMutations.length===0'))
                await page.evaluate('groupObserver.disconnect();document.querySelector("#assetSort").value="oldest";renderAssets();')
                check('GRID-35', 'Group reorder preserves identity, focus and selected reading order', await page.evaluate('card(gridIds[0])===keptCard && keptImage.isConnected && document.activeElement===keptCheck && JSON.stringify([...document.querySelectorAll("#assetGrid [data-asset-check]")].map(n=>n.dataset.assetCheck))===JSON.stringify(visibleAssets().map(a=>a.id))'))
                await page.evaluate('id=>{assetState.assets.find(a=>a.id===id).job_id="moved-run";renderAssets();}', ids[0])
                check('GRID-36', 'Moving an asset into a new group retains its source and focus', await page.evaluate('card(gridIds[0])===keptCard && keptImage.isConnected && document.activeElement===keptCheck && keptCard.closest(".asset-group")?.querySelector("h4").textContent.includes("moved-run") && document.querySelectorAll("#assetGrid .asset-group").length===3'))
                await page.evaluate('id=>{assetState.assets.find(a=>a.id===id).review="selected";updateAssetCard(id);}', ids[0])
                check('GRID-37', 'A saved-record repaint keeps the cached card and updates Review next', await page.evaluate('card(gridIds[0])===keptCard && keptImage.isConnected && document.activeElement===keptCheck && keptCard.querySelector(".asset-card-meta").textContent.includes("keeper") && document.querySelector("#reviewNext").textContent.includes("2 unreviewed")'))
                await refresh()
                await page.select_option('#assetGroup', 'recipe')
                await page.locator(f'[data-asset-check="{ids[0]}"]').focus()
                await page.evaluate('document.querySelector("#assetSort").value="newest";renderAssets();')
                check('GRID-39', 'Several cards share a retained group and reorder without losing focus', await page.evaluate('document.querySelectorAll("#assetGrid .asset-group").length===1 && document.querySelector("#assetGrid .asset-group h4 small").textContent==="3" && card(gridIds[0])===keptCard && keptImage.isConnected && document.activeElement===keptCheck && JSON.stringify([...document.querySelectorAll("#assetGrid [data-asset-check]")].map(n=>n.dataset.assetCheck))===JSON.stringify(visibleAssets().map(a=>a.id))'))
                check('GRID-40', 'A group offers three keyboard triage buttons naming its unreviewed count', await page.evaluate('document.querySelectorAll("#assetGrid .asset-group-actions [data-group-review]").length===3 && document.querySelector("#assetGrid .asset-group-actions").textContent.startsWith("Mark 3 unreviewed as") && !document.querySelector("#assetGrid .asset-group-actions").hidden'))
                await page.evaluate('window.groupPrompts=[];window.savedConfirm=window.confirm;window.confirm=m=>{groupPrompts.push(m);return false;};void 0')
                await page.locator('#assetGrid [data-group-review="rejected"]').focus();await page.keyboard.press('Enter')
                await page.wait_for_function('groupPrompts.length===1 && !assetBulkReviewBusy')
                check('GRID-41', 'Enter on a group action asks with count and decision; declining sends nothing', await page.evaluate('groupPrompts[0].startsWith("Mark 3 unreviewed pictures in \'Grid QA\' as Rejected?") && groupPrompts[0].includes("changed back individually")') and not any(p['path']=='/api/assets/update' for p in fixture.POSTS))
                await page.evaluate('window.confirm=savedConfirm;assetState.assets.forEach(a=>{a.review="rejected";});renderAssets();')
                check('GRID-42', 'A focused group action that disappears hands focus to its group heading', await page.evaluate('document.querySelector("#assetGrid .asset-group-actions").hidden && document.activeElement===document.querySelector("#assetGrid .asset-group h4")'))
                await refresh()
                # Group writes are answered in the page (never the fixture server): a conflict, then a receipt.
                replies=['conflict','applied']
                async def group_reply(route):
                    command=json.loads(route.request.post_data);kind=replies.pop(0)
                    if kind=='conflict':
                        body={'error':'Selected asset metadata changed or no longer exists; nothing changed in this batch','code':'asset_revision_conflict','request_id':command['request_id'],'workspace_id':command['workspace_id'],'conflict_ids':command['ids'][:1],'missing_ids':[],'current':[]}
                        return await route.fulfill(status=409,content_type='application/json',body=json.dumps(body))
                    body={'status':'applied','workspace_id':command['workspace_id'],'request_id':command['request_id'],'updated':command['ids'],'action':'edit','revisions':{i:command['expected_revisions'][i]+1 for i in command['ids']},'applied':{'review':command['review']},'current':[]}
                    await route.fulfill(status=200,content_type='application/json',body=json.dumps(body))
                await page.route('**/api/assets/update',group_reply)
                await page.evaluate('window.savedConfirm=window.confirm;window.confirm=()=>true;void 0')
                await page.locator('#assetGrid [data-group-review="rejected"]').focus();await page.keyboard.press('Enter')
                await page.wait_for_function('!assetBulkReviewBusy && document.querySelector("#assetMessage").textContent.includes("Stopped")')
                check('GRID-43', 'A stopped group mark leaves keyboard focus on its enabled group action', await page.evaluate('document.activeElement?.dataset?.groupReview==="rejected" && !document.activeElement.disabled && document.querySelector("#assetGrid").contains(document.activeElement)'))
                await page.keyboard.press('Enter')
                await page.wait_for_function('!assetBulkReviewBusy && document.querySelector("#assetMessage").textContent.startsWith("Marked 3 of 3")')
                check('GRID-44', 'A completed group mark hands keyboard focus to the group heading, not the page body', await page.evaluate('document.querySelector("#assetGrid .asset-group-actions").hidden && document.activeElement===document.querySelector("#assetGrid .asset-group h4")'))
                await page.unroute('**/api/assets/update');await page.evaluate('window.confirm=savedConfirm;void 0')
                await refresh()
                await page.select_option('#assetGroup', 'none')
                check('GRID-38', 'Ungrouping retains source nodes and removes old group containers', await page.evaluate('card(gridIds[0])===keptCard && keptImage.isConnected && !document.querySelector("#assetGrid .asset-group") && keptCard.parentElement.id==="assetGrid"'))
                await page.select_option('#assetSort', 'newest')
                await remember();await page.locator(f'[data-asset-check="{ids[0]}"]').focus()
                edit(ids[1], title='Another client renamed Study 1');await refresh()
                check('GRID-04', 'Another asset changing leaves this card and focus intact', await page.evaluate('card(gridIds[0])===keptCard && document.activeElement===keptCheck'))
                edit(ids[0], title='<b>Renamed study</b>', tags=['portrait','<script>text</script>'], favorite=True, review='selected');await refresh()
                check('GRID-05', 'Metadata updates do not replace the unchanged source image', await page.evaluate('card(gridIds[0]).querySelector("img")===keptImage'))
                check('GRID-06', 'Labels, tags and saved review update as text', await page.evaluate('''()=>{const c=card(gridIds[0]);return c.querySelector('img').alt==='<b>Renamed study</b>' && c.querySelector('.asset-card-title').textContent==='<b>Renamed study</b>' && !c.querySelector('.asset-tags script') && c.querySelector('.asset-tags').textContent.includes('<script>text</script>') && c.querySelector('.asset-card-meta').textContent.includes('keeper') && c.querySelector('.asset-star').getAttribute('aria-label').startsWith('Unfavorite');}'''))
                check('GRID-07', 'Metadata updates retain the original favorite control', await page.evaluate('card(gridIds[0]).querySelector(".asset-star")===keptStar'))
                await page.locator(f'[data-asset-check="{ids[0]}"]').check();await remember();await refresh()
                check('GRID-08', 'Checkbox and selected styling match the owned selection', await page.evaluate('keptCheck.isConnected && keptCheck.checked && keptCard.classList.contains("is-selected") && assetSelection.has(gridIds[0])'))
                await page.locator(f'[data-asset-check="{ids[0]}"]').focus()
                source = root / 'new.png';Image.new('RGB',(48,64),(160,150,130)).save(source)
                new_id=store.register({'id':'new-first','created_at':20,'outputs':[{'filename':source.name,'media_type':'image'}]},0,source)
                await refresh()
                check('GRID-09', 'Insertions preserve existing card, image and focused control', await page.evaluate('card(gridIds[0])===keptCard && keptImage.isConnected && document.activeElement===keptCheck'))
                check('GRID-10', 'Rendered order follows the current library order', await page.evaluate('JSON.stringify([...document.querySelectorAll("#assetGrid [data-asset-check]")].map(n=>n.dataset.assetCheck))===JSON.stringify(visibleAssets().map(a=>a.id))'))
                # Use real user sorting, then a direct render with a focused card to test the move fallback.
                await page.select_option('#assetSort','title');await remember();await page.locator(f'[data-asset-check="{ids[0]}"]').focus()
                edit(ids[0],title='ZZZ last in title order');await refresh()
                check('GRID-11', 'Reordering preserves node identity and keyboard focus', await page.evaluate('card(gridIds[0])===keptCard && keptImage.isConnected && document.activeElement===keptCheck'))
                check('GRID-12', 'Reordering still matches the selected sort', await page.evaluate('JSON.stringify([...document.querySelectorAll("#assetGrid [data-asset-check]")].map(n=>n.dataset.assetCheck))===JSON.stringify(visibleAssets().map(a=>a.id))'))
                # Test filtered cleanup and deterministic focus fallback without a search action owning focus.
                await page.evaluate("document.querySelector('#assetSort').value='oldest';renderAssets();")
                order = await page.evaluate('visibleAssets().map(a=>a.id)')
                removed = order[1];successor = order[2]
                await page.locator(f'[data-asset-check="{removed}"]').focus()
                revision=store.metadata(removed)['metadata_revision']
                store.update({'ids':[removed],'action':'trash','request_id':uuid.uuid4().hex,'expected_revisions':{removed:revision}})
                await refresh()
                check('GRID-13', 'A removed focused card moves focus to the next surviving checkbox', await page.evaluate('id=>document.activeElement.dataset.assetCheck===id',successor))
                check('GRID-14', 'A removed card leaves no stale grid node', await page.locator(f'[data-asset-check="{removed}"]').count()==0)
                await page.fill('#assetSearch','no such title')
                await page.locator('[data-asset-clear-filters]').focus()
                await page.evaluate("window.keptEmpty=document.querySelector('[data-asset-clear-filters]')")
                await refresh()
                check('GRID-15', 'Unchanged empty view retains its focused recovery action', await page.evaluate('keptEmpty.isConnected && document.activeElement===keptEmpty'))
                await page.fill('#assetSearch','')
                active=await page.evaluate('visibleAssets()[0].id')
                await page.locator(f'[data-asset-check="{active}"]').focus()
                await page.evaluate("document.querySelector('#assetSearch').value='no such title';renderAssets();")
                check('GRID-16', 'No surviving cards returns grid focus to Search', await page.evaluate('document.activeElement.id==="assetSearch"'))
                await page.fill('#assetSearch','');await page.focus('#assetSearch');await refresh()
                check('GRID-17', 'A refresh does not steal focus from another control', await page.evaluate('document.activeElement.id==="assetSearch"'))
                # Source identity and Workspace identity are independent from mutable labels.
                active=await page.evaluate('visibleAssets()[0].id');await remember(active)
                await page.evaluate('id=>{assetState.assets.find(a=>a.id===id).url+="?changed-source";renderAssets();}',active)
                check('GRID-18', 'A changed source replaces only the preview, not card controls', await page.evaluate('id=>card(id)===keptCard && card(id).querySelector("img")!==keptImage && keptCheck.isConnected',active))
                await refresh();await remember(active)
                await page.evaluate('assetState.workspace_id="f".repeat(32);renderAssets()')
                check('GRID-19', 'A different Workspace never reuses coincident card identities', await page.evaluate('id=>card(id)!==keptCard && !keptImage.isConnected',active))
                await refresh()
                # Deliberately synthetic, non-decodable video: this proves DOM resource release, not codec savings.
                await page.evaluate('id=>{const a=assetState.assets.find(a=>a.id===id);a.media_type="video";renderAssets();const v=card(id).querySelector("video");window.gridVideo=v;window.releaseCalls=[];v.pause=()=>releaseCalls.push("pause");v.load=()=>releaseCalls.push("load");}',active)
                await page.fill('#assetSearch','no such title')
                # The current search handler debounces its projection; wait for the filtered result.
                await page.wait_for_function('!gridVideo.isConnected')
                check('GRID-20', 'A removed video is paused and detached from its source', await page.evaluate('!gridVideo.isConnected && !gridVideo.hasAttribute("src") && releaseCalls.includes("pause") && releaseCalls.includes("load")'))
                await page.fill('#assetSearch','');await refresh()
                # Modal ownership: library refresh must not interfere with an active review draft.
                await page.evaluate('id=>openAsset(id)',active);await page.fill('#assetNotes','Keep my unsaved review');await refresh()
                check('GRID-21', 'Refreshing beneath a dialog preserves focused unsaved notes', await page.evaluate('document.activeElement.id==="assetNotes" && document.querySelector("#assetNotes").value==="Keep my unsaved review"'))
                # Close by explicit consent, then verify retained control still drives the real delegated handler.
                page.on('dialog',lambda dialog:dialog.accept())
                await page.click('#closeAssetDialog');await page.wait_for_function('!document.querySelector("#assetDialog").open')
                await page.evaluate('assetSelection.clear();renderAssets()');await remember(active);await refresh()
                await page.locator(f'[data-asset-check="{active}"]').check()
                check('GRID-22', 'Reused controls retain their delegated selection behavior', await page.evaluate('id=>assetSelection.has(id) && card(id).classList.contains("is-selected")',active))
                # Selection events mutate checkbox state without a full grid render.
                await page.click('#clearAssetSelection')
                check('GRID-27', 'Clear selection immediately after a checkbox click clears its visual state', await page.evaluate('id=>!assetSelection.size && !card(id).querySelector("input").checked && !card(id).classList.contains("is-selected")', active))
                await page.focus('#assetSearch')
                await page.evaluate('window.gridMutations=[];window.gridObserver=new MutationObserver(items=>gridMutations.push(...items));gridObserver.observe(document.querySelector("#assetGrid"),{subtree:true,childList:true,attributes:true,characterData:true});')
                await refresh()
                check('GRID-28', 'An unchanged refresh makes no grid DOM mutations', await page.evaluate('gridMutations.length===0'))
                await page.evaluate('gridObserver.disconnect()')
                # Exercise the standards-based insertion fallback even in moveBefore-capable Chromium.
                await page.evaluate('window.gridMoveBefore=document.querySelector("#assetGrid").moveBefore;document.querySelector("#assetGrid").moveBefore=undefined;')
                await page.select_option('#assetSort','newest');await remember(active)
                await page.locator(f'[data-asset-check="{active}"]').focus()
                await page.evaluate('document.querySelector("#assetSort").value="oldest";renderAssets()')
                check('GRID-29', 'The insertBefore fallback retains the focused control on reorder', await page.evaluate('keptCheck.isConnected && document.activeElement===keptCheck'))
                check('GRID-30', 'The fallback preserves source element identity on reorder', await page.evaluate('keptImage.isConnected'))
                await page.evaluate('()=>{document.querySelector("#assetGrid").moveBefore=gridMoveBefore;}')
                await remember(active)
                await page.evaluate('id=>{assetState.assets.find(a=>a.id===id).sha256="e".repeat(64);renderAssets();}',active)
                check('GRID-31', 'Changed source hash at the same URL invalidates only its media', await page.evaluate('id=>card(id)===keptCard && card(id).querySelector("img")!==keptImage && !keptImage.hasAttribute("src")',active))
                await refresh()
                for width in [1440,390]:
                    await page.set_viewport_size({'width':width,'height':1100})
                    check('GRID-23' if width==1440 else 'GRID-24', f'{width}px layout remains within the viewport',await page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
                    await page.screenshot(path=str(args.out/f'grid-{width}.png'))
                    await page.locator(f'[data-asset-check="{active}"]').focus()
                    await page.locator('#assetGrid').screenshot(path=str(args.out/f'focused-grid-{width}.png'))
                check('GRID-25', 'Browsing and refresh make no mutation or generation request',all(p['path'] in {'/api/estimate','/api/references/check'} for p in fixture.POSTS))
                check('GRID-26', 'Complete shell has no JavaScript exceptions',not errors)
                await browser.close()
        except Exception as error:
            failure=f'{type(error).__name__}: {error}'
        finally:
            http.shutdown();http.server_close();thread.join(timeout=5)
    receipt={'mode':'inert browser storage/transport' if args.inert else 'native HTTP/browser',
             'scope':'Actual shell, production Workspace reads and temporary SQLite; synthetic images. Video case proves DOM release only, not decoding/performance.',
             'checks':checks,'errors':errors,'execution_error':failure,'pass':sum(c['passed'] for c in checks),'fail':sum(not c['passed'] for c in checks),
             'posts':fixture.POSTS,'source_sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in ['app/static/workspace.js','app/static/asset-grid.js'] if (ROOT/f).is_file()}}
    (args.out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:receipt[k] for k in ['mode','pass','fail','errors','execution_error']},indent=2))
    if failure or errors or len(checks)!=44 or (receipt['fail'] and not args.baseline):raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);parser.add_argument('--inert',action='store_true');parser.add_argument('--baseline',action='store_true')
    asyncio.run(exercise(parser.parse_args()))
