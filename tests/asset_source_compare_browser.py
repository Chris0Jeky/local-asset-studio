"""Feature-only comparison proof on the existing inert family HTTP/SQLite fixture."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tempfile
import threading
from urllib.parse import urlsplit

from PIL import Image
from playwright.sync_api import sync_playwright
from asset_family_browser import build_family_studio, build_handler, server
from browser_ports import browser_server
from creation_privacy import scope_for_handler


def picture(size, colour):
    stream = io.BytesIO()
    Image.new('RGB', size, colour).save(stream, 'PNG')
    return stream.getvalue()


def build_fixture(root):
    studio, ancestors = build_family_studio(root)
    parent = ancestors[0]
    before = studio.assets.get(parent)
    digest = hashlib.sha256(studio.assets.file(parent).read_bytes()).hexdigest()
    child = studio.import_image('Repaired picture.png', 'image/png', picture((640, 480), 'seagreen'),
                                parent=parent, note='Synthetic repair fixture')['asset']['id']
    source = Path(root) / 'synthetic.png'

    def recorded(name, parents, privacy='regular', media='image', created=100):
        job = {'id': 'compare-'+name, 'created_at': created, 'preset_name': name, 'parent_assets': parents,
               'privacy': privacy, 'outputs': [{'filename': name+'.png', 'media_type': media}]}
        identifier = studio.assets.register(job, 0, source)
        return identifier

    # The normal first page cannot supply the old parent: comparison must resolve its ID.
    for index in range(111):
        recorded('other-'+str(index), [], created=20+index)
    private = recorded('private-source', [], privacy='private')
    video = recorded('video-source', [], media='video')
    trashed = recorded('trashed-source', [])
    with studio.assets.connection() as db:
        db.execute('UPDATE assets SET trashed_at=1 WHERE id=?', (trashed,))
    cases = {'child': child, 'parent': parent, 'other': ancestors[1],
             'multiple': recorded('multiple-sources', [parent, ancestors[1]]),
             'missing': recorded('missing-source', ['0'*32]),
             'trashed': recorded('trashed-parent', [trashed]),
             'video': recorded('video-parent', [video]),
             'mixed': recorded('mixed-privacy', [private]),
             'private': recorded('private-child', [private], privacy='private'), 'private_parent': private}
    studio.assets = server.AssetWorkspace(studio.experiments)
    assert studio.assets.get(child)['review'] == 'unreviewed'
    assert studio.assets.get(parent) == before
    assert hashlib.sha256(studio.assets.file(parent).read_bytes()).hexdigest() == digest
    return studio, cases, before, digest


def comparison_handler(studio, requests, controls):
    base = build_handler(studio, [])

    class Handler(base):
        def _json(self, code, value):
            if self.path == '/api/assets/selection' and controls.get('hold'):
                controls['hold'] = False
                controls['entered'].set()
                assert controls['release'].wait(15), 'Held selection was not released'
            if self.path.startswith('/api/assets/family/') and controls.get('incomplete'):
                value = dict(value, truncated=True)
            return super()._json(code, value)

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == '/api/jobs':
                # Older sources remain in SQLite; only the newest repair is in this Recent runs fixture.
                scope = scope_for_handler(self)
                return self.json([job for job in self.studio.jobs.values() if job.get('operation') == 'asset.import'
                                  and (scope == 'all' or job.get('privacy', 'regular') == scope)])
            if path == '/api/workspace':
                return self.json(self.studio.assets.snapshot(privacy=scope_for_handler(self)))
            if path.startswith('/api/assets/') and path.endswith('/metadata'):
                return self.json(self.studio.assets.metadata(path.split('/')[3], privacy=scope_for_handler(self)))
            if path.startswith('/api/assets/') and path.endswith('/file'):
                identifier = path.split('/')[3]
                if identifier == controls.get('missing_media'):
                    return self.json({'error': 'Synthetic missing media'}, 404)
                try:
                    raw = self.studio.assets.file(identifier, privacy=scope_for_handler(self)).read_bytes()
                except (ValueError, OSError):
                    return self.json({'error': 'Picture unavailable'}, 404)
                self.send_response(200)
                self.send_header('Content-Type', 'image/png')
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            return super().do_GET()

        def do_POST(self):
            requests.append(self.path)
            if self.path == '/api/assets/update':
                assert controls.get('allow_review'), 'Comparison unexpectedly wrote metadata'
                return server.Handler.do_POST(self)
            assert self.path in ('/api/assets/selection', '/api/estimate', '/api/references/check'), self.path
            return super().do_POST()

        _body_json = server.Handler._body_json
        _read_body = server.Handler._read_body
    return Handler


def exercise(out, browser_executable=None):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    checks, errors, requests = [], [], []

    def check(condition, label):
        assert condition, label
        checks.append(label)
        print('PASS: '+label, flush=True)

    with tempfile.TemporaryDirectory() as tmp:
        studio, ids, original, digest = build_fixture(tmp)
        controls = {'entered': threading.Event(), 'release': threading.Event()}
        http = browser_server(comparison_handler(studio, requests, controls))
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        origin = 'http://127.0.0.1:'+str(http.server_port)
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True, executable_path=browser_executable)
                context = browser.new_context(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce')
                page = context.new_page()
                page.set_default_timeout(10000)
                page.on('pageerror', lambda error: errors.append(error.stack or str(error)))
                page.on('dialog', lambda dialog: dialog.dismiss())

                def ready():
                    page.wait_for_function('window.StudioSetupDraft&&backendActive==="primary"&&catalog?.presets?.some(p=>p.id==="anima-portrait")&&selected?.id&&assetPaging&&!assetRefreshing')

                def open_asset(identifier):
                    page.evaluate('(id)=>openAsset(id)', identifier)
                    page.wait_for_function('(id)=>activeAsset?.id===id&&document.querySelector("#assetDialog").open', arg=identifier)
                    page.wait_for_function('(id)=>[...document.querySelectorAll("[data-family-step]")].some(e=>e.dataset.familyStep===id)&&!document.querySelector("#assetFamilyStatus").textContent.includes("Reading")', arg=identifier)

                def compare(identifier):
                    page.locator('#assetCompareSource').click()
                    check(page.locator('#assetSourceImages img').count() == 0, 'Opening comparison chooses no source')
                    page.locator('[data-family-source="'+identifier+'"]').click()
                    page.wait_for_function('document.querySelectorAll("#assetSourceImages img").length===2&&[...document.querySelectorAll("#assetSourceImages img")].every(i=>i.complete&&i.naturalWidth)')

                def capture(name):
                    page.locator('#assetSourceTitle').focus()
                    page.screenshot(path=str(out/(name+'.png')), full_page=False, animations='disabled')

                try:
                    page.goto(origin+'/#assets', wait_until='domcontentloaded')
                    ready()
                    open_asset(ids['child'])
                    check(page.locator('#assetReview').input_value() == 'unreviewed', 'Reopened SQLite repair starts unreviewed')
                    check(page.evaluate('(id)=>!assetState.assets.some(a=>a.id===id)&&!assetResolved.has(id)', ids['parent']), 'Recorded parent starts off-page and unresolved')
                    page.locator('#assetNotes').fill('Keep these unsaved repair notes')
                    compare(ids['parent'])
                    check(page.locator('#assetNotes').input_value() == 'Keep these unsaved repair notes', 'Comparison preserves typed notes')
                    check(page.evaluate('(id)=>activeAsset.id===id', ids['child']), 'Comparison keeps the child as the active editor')
                    check(page.locator('#assetSourceStatus').inner_text().startswith('Different image dimensions.'), 'Different dimensions are disclosed without alignment claim')
                    boxes = page.locator('#assetSourceImages img').evaluate_all('(els)=>els.map(e=>({width:e.clientWidth,height:e.clientHeight,fit:getComputedStyle(e).objectFit}))')
                    check(boxes[0] == boxes[1] and boxes[0]['fit'] == 'contain', 'Wide images have equal contained display boxes')
                    capture('comparison-1440')
                    for width, zoom, name in ((390, '1', 'comparison-390'), (1440, '2', 'comparison-css200')):
                        page.set_viewport_size({'width': width, 'height': 1000})
                        page.evaluate('(zoom)=>document.documentElement.style.zoom=zoom', zoom)
                        capture(name)
                        check(page.locator('#assetDialog').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1'), name+' has no horizontal dialog overflow')
                        page.locator('[data-family-compare-close]').focus()
                        page.keyboard.press('Enter')
                        check(page.locator('#assetSourceImages img').count() == 0 and page.locator('#assetCompareSource').evaluate('(e)=>e===document.activeElement'), name+' keyboard close clears images and returns focus')
                        check(page.locator('#assetNotes').input_value() == 'Keep these unsaved repair notes', name+' close preserves unsaved notes')
                        page.keyboard.press('Enter')
                        page.locator('[data-family-source="'+ids['parent']+'"]').focus()
                        page.keyboard.press('Enter')
                        page.wait_for_function('document.querySelectorAll("#assetSourceImages img").length===2&&[...document.querySelectorAll("#assetSourceImages img")].every(i=>i.complete&&i.naturalWidth)')
                    page.evaluate('document.documentElement.style.zoom="1"')
                    page.set_viewport_size({'width': 1440, 'height': 1000})
                    page.locator('[data-family-compare-close]').click()
                    page.locator('#assetCompareSource').click()
                    controls['entered'].clear(); controls['release'].clear(); controls['hold'] = True
                    page.locator('[data-family-source]').click()
                    assert controls['entered'].wait(5), 'Comparison response did not reach the Notes hold'
                    page.locator('#assetNotes').focus()
                    controls['release'].set()
                    page.wait_for_function('document.querySelectorAll("#assetSourceImages img").length===2&&[...document.querySelectorAll("#assetSourceImages img")].every(i=>i.complete&&i.naturalWidth)')
                    check(page.locator('#assetNotes').evaluate('(e)=>e===document.activeElement'), 'Held comparison response preserves Notes focus')
                    page.keyboard.type(' kwx')
                    check(page.locator('#assetNotes').input_value().endswith(' kwx') and studio.assets.get(ids['child'])['review'] == 'unreviewed', 'K/W/X typing after a held response stays in Notes and does not review')
                    check('/api/assets/update' not in requests, 'Opening, choosing and closing comparison perform no metadata writes')
                    controls['allow_review'] = True
                    page.locator('#assetSourceTitle').focus()
                    page.keyboard.press('k')
                    page.wait_for_function('!assetDetailBusy&&activeAsset.review==="selected"')
                    check(studio.assets.get(ids['child'])['review'] == 'selected', 'Existing Keep shortcut persists the child review')
                    page.locator('#assetNotes').fill('Saved child notes after comparison')
                    page.locator('#saveAssetDetails').click()
                    page.wait_for_function('!assetDetailBusy&&!assetDetailDirty()')
                    controls['allow_review'] = False
                    check(studio.assets.get(ids['child'])['notes'] == 'Saved child notes after comparison', 'Existing Save persists only the child notes')
                    page.locator('#closeAssetDialog').click()
                    page.reload(wait_until='domcontentloaded')
                    ready()
                    open_asset(ids['child'])
                    check(page.locator('#assetReview').input_value() == 'selected' and page.locator('#assetNotes').input_value() == 'Saved child notes after comparison', 'Review and notes survive reopening')

                    open_asset(ids['multiple'])
                    compare(ids['other'])
                    check(page.locator('[data-family-source]').count() == 2 and ids['other'] in page.locator('#assetSourceImages img').nth(1).get_attribute('src'), 'Multiple direct parents require and honour explicit choice')
                    for key in ('missing', 'trashed'):
                        open_asset(ids[key])
                        page.locator('#assetCompareSource').click()
                        check(page.locator('[data-family-source]').is_disabled(), key+' source stays unavailable')
                    open_asset(ids['video'])
                    page.locator('#assetCompareSource').click()
                    page.locator('[data-family-source]').click()
                    page.wait_for_function('document.querySelector("#assetSourceStatus").textContent.includes("not an image")')
                    check(page.locator('#assetSourceImages img').count() == 0, 'Non-image source supplies no comparison media')
                    controls['incomplete'] = True
                    open_asset(ids['child'])
                    check(page.locator('#assetCompareSource').is_disabled(), 'Capped family evidence cannot start comparison')
                    controls['incomplete'] = False
                    open_asset(ids['other'])
                    open_asset(ids['child'])
                    controls['missing_media'] = ids['parent']
                    page.locator('#assetCompareSource').click()
                    page.locator('[data-family-source]').click()
                    page.wait_for_function('document.querySelector("#assetSourceStatus").textContent.includes("could not be loaded")')
                    check(page.locator('#assetSourceImages img').count() == 0, 'Missing media clears both comparison images')
                    controls.pop('missing_media')

                    for change in ('close', 'navigate', 'workspace', 'privacy'):
                        open_asset(ids['child'])
                        page.locator('#assetCompareSource').click()
                        controls['entered'].clear(); controls['release'].clear(); controls['hold'] = True
                        page.locator('[data-family-source]').click()
                        assert controls['entered'].wait(5), 'Selection response did not reach hold'
                        if change == 'close':
                            page.locator('[data-family-compare-close]').click()
                        elif change == 'navigate':
                            open_asset(ids['other'])
                        elif change == 'workspace':
                            page.evaluate('''()=>{const previous=assetState.workspace_id;assetState.workspace_id='f'.repeat(32);assetWorkspaceEpoch++;document.dispatchEvent(new Event('studio:workspace-change'));assetState.workspace_id=previous;assetWorkspaceEpoch++;document.dispatchEvent(new Event('studio:workspace-change'));}''')
                        else:
                            page.evaluate('StudioPrivacy.setScope("all");StudioPrivacy.setScope("regular")')
                        controls['release'].set()
                        page.wait_for_function('document.querySelector("#assetSourceComparison").hidden')
                        page.wait_for_timeout(150)
                        check(page.locator('#assetSourceImages img').count() == 0, 'Held reply cannot paint after '+change+' (A-B-A for scopes)')
                    page.evaluate('StudioPrivacy.setScope("all")')
                    page.wait_for_function('assetActivePrivacy==="all"&&!assetRefreshing')
                    open_asset(ids['mixed'])
                    page.locator('#assetCompareSource').click()
                    page.locator('[data-family-source]').click()
                    page.wait_for_function('document.querySelector("#assetSourceStatus").textContent.includes("same privacy")')
                    check(page.locator('#assetSourceImages img').count() == 0, 'All view never compares across privacy classifications')
                    open_asset(ids['private'])
                    compare(ids['private_parent'])
                    check(all('?privacy=private' in value for value in page.locator('#assetSourceImages img').evaluate_all('(els)=>els.map(e=>e.getAttribute("src"))')), 'Private pair retains scoped media URLs')
                    page.evaluate('StudioPrivacy.setScope("regular")')
                    page.wait_for_function('document.querySelector("#assetSourceComparison").hidden')
                    check(page.locator('#assetSourceComparison img').count() == 0, 'Leaving private view removes comparison media')
                except Exception as error:
                    (out/'failure.json').write_text(json.dumps({'error': str(error), 'checks': checks, 'page_errors': errors}, indent=2)+'\n')
                    page.screenshot(path=str(out/'failure.png'), full_page=False, timeout=5000)
                    raise
                finally:
                    controls['release'].set()
                    context.close()
                    browser.close()
        finally:
            controls['release'].set()
            http.shutdown(); http.server_close(); thread.join(5)
        check(not errors, 'No JavaScript page errors')
        check(studio.assets.get(ids['parent']) == original and hashlib.sha256(studio.assets.file(ids['parent']).read_bytes()).hexdigest() == digest, 'Parent record and bytes remain unchanged')
        check(requests.count('/api/assets/update') == 2, 'Exactly two deliberate child metadata commands; no generation or native work')
        report = {'checks': checks, 'page_errors': errors, 'post_routes': requests, 'generation_submitted': False,
                  'parent_sha256': digest, 'parent_unchanged': True, 'native_zoom_verified': False, 'screen_reader_verified': False}
        (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default='.runtime/asset-source-compare')
    parser.add_argument('--browser')
    args = parser.parse_args()
    exercise(args.out, args.browser)
