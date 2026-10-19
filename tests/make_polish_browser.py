"""S3 one-press Polish: StudioWorkbench.polish sends exactly one /api/jobs per press and leaves Create alone. Never a model call.

python tests/make_polish_browser.py
Fixture server from studio_browser_smoke (real frontend, synthetic API, real catalog capabilities).
"""
import json
import threading
import time
from http_test_server import ThreadingHTTPServer

from playwright.sync_api import sync_playwright
import studio_browser_smoke as fixture

LOOKS = [dict(id=id, name=name, kind='look', revision=0, body=dict(preset_id='zimage-fast', controls={}, scene_example='A quiet garden')) for id, name in [('look-wai-fantasy-portrait', 'First look'), ('look-anima-fantasy-portrait', 'Second look')]]
MAKE_JOBS = {}
RESTORE_DELAY = 0
FAILING = set()  # job ids whose GET answers 500, as a Studio that stopped answering would
READS = []  # every GET /api/jobs/make-* path, to see which runs are still polled

WAI = 'asset-1'  # its context says it was made by the WAI recipe; asset-0 stays the fixture's Anima picture


def context(asset_id):
    asset = next(a for a in fixture.ASSETS if a['id'] == asset_id)
    return {**fixture.source_context(asset), 'preset_id': 'wai'} if asset_id == WAI else fixture.source_context(asset)


class Handler(fixture.Handler):
    def do_GET(self):
        if self.path == '/api/looks': return self.json({'looks': LOOKS})
        if self.path.startswith('/api/jobs/make-'):
            if RESTORE_DELAY: time.sleep(RESTORE_DELAY)
            READS.append(self.path.split('/')[-1])
            if self.path.split('/')[-1] in FAILING: return self.json({'error': 'fixture outage'}, 500)
            if self.path.split('/')[-1] not in MAKE_JOBS: return self.json({'error': 'Unknown job'}, 404)
            return self.json(MAKE_JOBS[self.path.split('/')[-1]])
        if self.path.startswith('/api/assets/') and self.path.endswith('/context'): return self.json(context(self.path.split('/')[3]))
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith('/api/jobs/make-') and self.path.endswith(('/resume', '/stop-tracking')):
            data = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))) or b'{}'); fixture.POSTS.append({'path': self.path, 'data': data})
            job = MAKE_JOBS[self.path.split('/')[3]]
            if self.path.endswith('/resume'): job.update(status='queued', message='Queued to resume observation; no image will be resubmitted.')
            else: job.update(tracking_disposition={'status': 'stopped', 'reason': data['reason']}, can_stop_tracking=False, can_resume_tracking=True)
            return self.json(job, 202)
        if self.path == '/api/looks/prepare':
            data = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0')))); time.sleep(0.3)
            return self.json({'preset_id': 'zimage-fast', 'controls': {'positive': data['scene']}})
        if self.path not in ('/api/jobs', '/api/assets/reference'): return super().do_POST()
        data = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))))
        fixture.POSTS.append({'path': self.path, 'data': data})
        if self.path == '/api/jobs' and data.get('label', '').startswith('Make \u00b7 '):
            time.sleep(0.2); job = dict(id='make-'+str(len(MAKE_JOBS)), status='queued', created_at=1789228800, outputs=[], **data); MAKE_JOBS[job['id']] = job
            return self.json(job)
        if self.path == '/api/jobs': return self.json({'id': 'polish-'+str(len(fixture.POSTS)), 'status': 'queued', 'message': 'Queued (fixture, no model run)'})
        time.sleep(0.3)  # a second press lands while the first copy is still in flight
        return self.json({'file': 'a'*32+'_fixture.png', 'sha256': 'a'*64, 'width': 512, 'height': 768, 'parent_asset': data['id'], 'context': context(data['id'])})


def jobs():
    return [p['data'] for p in fixture.POSTS if p['path'] == '/api/jobs']


def make_checks(browser, origin):
    page = browser.new_page(); errors = []; page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(origin+'/#make'); page.wait_for_selector('[data-make-look]')
    assert page.locator('#makeRuns .make-run').count() == 0, 'agent proofs must not become Your pictures'
    page.locator('[data-make-look]').first.click()
    page.locator('#makeGenerate').click()
    assert page.locator('#makeScene').get_attribute('aria-invalid') == 'true'
    assert page.locator('#makeScene').get_attribute('aria-describedby') == 'makeStatus'
    assert page.locator('#makeScene').evaluate('(e)=>e===document.activeElement')
    # No width in the Look or prepare result: catalog dimensions still reach the exact estimate and submit.
    page.evaluate("()=>{const p=catalog.presets.find(p=>p.id==='zimage-fast');p.defaults.width=1024;p.defaults.height=1024;p.dimension_multiple=64;}")
    for shape, size in [('portrait', [832, 1280]), ('landscape', [1280, 832]), ('square', [1024, 1024])]:
        page.locator('#makeScene').fill('A quiet garden'); page.locator('#makeShape').select_option(shape)
        page.wait_for_timeout(100)
        estimate = next(p['data'] for p in reversed(fixture.POSTS) if p['path'] == '/api/estimate' and p['data'].get('preset_id') == 'zimage-fast')
        before = len(jobs())
        page.evaluate("()=>{document.querySelector('#makeGenerate').click();document.querySelector('#makeGenerate').click();document.querySelector('#makeEditor').click();}")
        page.wait_for_function("!document.querySelector('#makeGenerate').disabled")
        assert len(jobs()) == before+1, 'double press and editor share one latch'
        assert page.evaluate('!!document.querySelector("#makeStatus").closest(".make-go")'), 'the status line sits in the Generate bar'
        sent = jobs()[-1]; assert sent['label'] == 'Make \u00b7 First look', sent
        assert [sent['controls'][k] for k in ('width', 'height')] == size, sent
        assert [estimate['controls'][k] for k in ('width', 'height')] == size, estimate
        assert page.locator('#makeView').is_visible(), 'editor must not navigate during Generate'
    for setup, reason in [("workerAlive=false", 'worker has stopped'), ("workerAlive=true;online=false", 'not reachable'), ("online=true;schemaAvailable=true;missingByPreset={'zimage-fast':['missing.safetensors']}", 'model file')]:
        page.evaluate('()=>{'+setup+';StudioMake.refresh();}')
        assert page.locator('#makeGenerate').is_disabled()
        assert reason in page.locator('#makeWhy').inner_text() and page.locator('#makeWhy').get_attribute('role') == 'status'
        assert page.locator('#makeGenerate').get_attribute('aria-describedby') == 'makeWhy', 'a blocked Generate names its reason'
        before = len(jobs()); page.locator('#makeScene').fill('Blocked request'); page.locator('#makeScene').press('Control+Enter')
        assert len(jobs()) == before and reason in page.locator('#makeStatus').inner_text()
    page.evaluate("()=>{missingByPreset={};StudioMake.refresh();}")
    assert page.locator('#makeGenerate').get_attribute('aria-describedby') is None and page.locator('#makeWhy').inner_text() == '' and page.locator('#makeWhy').count() == 1, 'the status region stays, empty'
    page.locator('#makeScene').fill('Keep feedback while switching')
    before = len(jobs()); page.locator('#makeGenerate').click()
    page.locator('[data-make-change]').click(); page.locator('[data-make-look]').nth(1).click()
    assert page.locator('#makeGenerate').is_disabled() and page.locator('#makeEditor').is_disabled()
    page.wait_for_function("!document.querySelector('#makeGenerate').disabled")
    assert len(jobs()) == before+1
    assert 'Started' in page.locator('#makeStatus').inner_text()
    assert page.locator('#makeRuns').get_attribute('aria-live') == 'polite'
    assert page.locator('#makeGoals [role=radio][tabindex="0"]').count() == 1
    page.locator('#makeGoals [role=radio][tabindex="0"]').focus(); page.keyboard.press('ArrowRight')
    assert page.locator('#makeGoals [role=radio][aria-checked=true]').get_attribute('data-make-goal') == 'scene'
    page.keyboard.press('End'); assert page.locator('#makeGoals [aria-checked=true]').get_attribute('data-make-goal') == 'mesh'
    page.keyboard.press('Home'); assert page.locator('#makeGoals [aria-checked=true]').get_attribute('data-make-goal') == 'character'
    assert page.locator('#makeGoals [aria-checked=true]').evaluate('(e)=>e===document.activeElement')
    # The look gallery keeps radio selection and focus together under the arrow keys.
    page.locator('[data-make-goal="scene"]').click(); page.locator('[data-make-goal="character"]').click(); page.locator('[data-make-look]').first.click(); page.locator('[data-make-change]').click()
    page.locator('.make-looks [tabindex="0"]').focus(); page.keyboard.press('ArrowLeft')
    assert page.locator('.make-looks [aria-checked=true]').evaluate('(e)=>e===document.activeElement&&e.tabIndex===0')
    # Editor-first also owns the latch. No job can be sent while its prepare is pending.
    page.locator('[data-make-keep-look]').click(); page.locator('#makeScene').fill('Editor only')
    before = len(jobs())
    page.evaluate("()=>{document.querySelector('#makeEditor').click();document.querySelector('#makeGenerate').click();}")
    page.wait_for_selector('#createView', state='visible'); assert len(jobs()) == before
    # All six ongoing runs survive remember() while restoration is still in flight.
    global RESTORE_DELAY
    saved = [dict(id='make-restore-'+str(i), look='First look', lookId=LOOKS[0]['id'], goal='character', scene='A quiet garden') for i in range(6)]
    for r in saved: MAKE_JOBS[r['id']] = dict(id=r['id'], status='running', outputs=[], created_at=1789228800)
    RESTORE_DELAY = 0.8
    page.evaluate('(runs)=>localStorage.setItem("studio.make",JSON.stringify({goal:"character",look:null,runs}))', saved)
    page.goto(origin+'/?restore-test#make'); page.wait_for_selector('[data-make-look]'); page.locator('[data-make-goal="scene"]').click()
    assert page.evaluate('JSON.parse(localStorage.getItem("studio.make")).runs.map(r=>r.id)') == [r['id'] for r in saved]
    page.wait_for_function('document.querySelectorAll("#makeRuns .make-run").length===6'); RESTORE_DELAY = 0
    # Preserve the actual More node and focus when another card updates; restore them when its own card changes.
    page.evaluate("()=>{window.pendingPolish=[];StudioWorkbench.polishPlan=()=>new Promise(r=>pendingPolish.push(r));}")
    MAKE_JOBS[saved[0]['id']]['outputs'] = [dict(filename='Anime-Face-Mask_00001_.png', asset_id='mask', media_type='image'), dict(filename='portrait.png', asset_id=WAI, media_type='image')]
    page.wait_for_selector('#makeRuns [data-more="asset-1"]')
    assert page.locator('#makeRuns img').count() == 1
    assert page.locator('#makeRuns img').get_attribute('src').endswith('/1'), 'filter must preserve the real output index'
    summary = page.locator('[data-more="asset-1"] summary'); summary.click(); summary.focus()
    page.evaluate('()=>window.originalMore=document.querySelector("[data-more=asset-1]")')
    MAKE_JOBS[saved[1]['id']]['message'] = 'Changed other run'
    page.wait_for_timeout(2800)
    assert page.evaluate('originalMore===document.querySelector("[data-more=asset-1]")&&originalMore.open&&originalMore.contains(document.activeElement)')
    page.evaluate('()=>pendingPolish.splice(0).forEach(r=>r({ok:false,reason:"Does not apply to this picture"}))')
    page.wait_for_function('document.querySelectorAll("[data-make-polish][data-asset=asset-1]:disabled").length===4')
    assert page.locator('[data-more="asset-1"]').evaluate('(e)=>e.open&&e.contains(document.activeElement)')
    # A fix that cannot run stays, disabled, and names its reason once (aria-describedby), as the Fix or upscale goal does.
    why = page.locator('[data-make-polish=face][data-asset=asset-1]').get_attribute('aria-describedby')
    assert why and page.locator('#' + why).inner_text() == 'Does not apply to this picture' and page.locator('#' + why).is_visible()
    assert page.locator('[data-run] .make-polish-why').count() == 1, 'one line per distinct reason'
    assert all(page.locator('#makeRuns button:disabled').nth(i).get_attribute('aria-describedby') for i in range(page.locator('#makeRuns button:disabled').count())), 'no unexplained disabled button'
    MAKE_JOBS[saved[0]['id']]['status'] = 'completed'
    page.wait_for_function('document.querySelector(".make-run-state.completed")')
    assert page.locator('[data-more="asset-1"]').evaluate('(e)=>e.open&&e.contains(document.activeElement)')
    # Focus restored after a card's own redraw stays on that card, not on the first card's identical More summary.
    MAKE_JOBS[saved[2]['id']]['outputs'] = [dict(filename='second.png', asset_id='asset-second', media_type='image')]
    page.wait_for_selector('#makeRuns [data-more="asset-second"]'); page.locator('[data-more="asset-second"] summary').focus()
    MAKE_JOBS[saved[2]['id']]['status'] = 'completed'
    page.wait_for_timeout(2800)
    assert page.evaluate('document.activeElement.closest("[data-run]")?.dataset.run') == saved[2]['id'], 'focus moved to another card'
    assert 'A quiet garden' in page.locator('#makeRuns .make-run header b').first.inner_text()
    assert page.evaluate('new Date(1789228800*1000).toLocaleDateString()') in page.locator('#makeRuns .make-run header b').first.inner_text()
    page.evaluate('()=>{assetState.assets.find(a=>a.id==="asset-1").review="selected";StudioMake.refresh();}')
    assert 'Kept' in page.locator('[data-make-review="selected"][data-asset="asset-1"]').inner_text()
    assert page.locator('#experimentDialog').get_attribute('aria-labelledby') == 'experimentTitle'
    assert page.locator('#newCollection').get_attribute('aria-label') == 'Create collection'
    assert page.locator('.hero-art').get_attribute('role') == 'group'
    # A plan that cannot be read is asked once, then waits its cool-down, not once per redraw (#1438).
    page.evaluate('()=>{window.planCalls=0;StudioWorkbench.polishPlan=()=>{planCalls++;return Promise.reject(Error("fixture refusal"));};}')
    MAKE_JOBS[saved[3]['id']]['outputs'] = [dict(filename='cool.png', asset_id='asset-cool', media_type='image')]
    page.wait_for_selector('[data-run="%s"] img' % saved[3]['id']); page.wait_for_timeout(1500)
    assert page.evaluate('planCalls') == 4, page.evaluate('planCalls')  # one per finishing kind (face, details, refine, upscale)
    # A run whose reads fail keeps being checked, says so on its card, and recovers by itself.
    FAILING.add(saved[4]['id'])
    page.wait_for_function('id=>document.querySelector(`[data-run="${id}"] .make-run-state`)?.textContent.startsWith("Lost contact")', arg=saved[4]['id'], timeout=6000)
    FAILING.clear()
    page.wait_for_function('id=>!document.querySelector(`[data-run="${id}"] .make-run-state`).textContent.startsWith("Lost contact")', arg=saved[4]['id'], timeout=12000)
    # A disabled finishing action has one visible reason; unavailable actions disappear once planned.
    page.evaluate('()=>{window.finishPolish=null;StudioWorkbench.polish=()=>new Promise(r=>finishPolish=r);StudioWorkbench.polishPlan=()=>Promise.resolve({ok:true});StudioWorkbench.varyMarkup=(p,j,a)=>\'<button type="button" data-ux-vary="subtle">Vary</button><small id="varyFixture\'+a+\'">Use Prepare new seed</small>\';}')
    MAKE_JOBS[saved[1]['id']]['outputs'] = [dict(filename='forest.png', asset_id='asset-0', media_type='image')]
    page.wait_for_selector('[data-make-polish=upscale][data-asset=asset-0]')
    assert page.locator('#varyFixtureasset-0').is_visible()
    # Vary runs from the card (#1497): its hint is the plan's own, and the button is Make's, not the full editor's prepare.
    assert page.locator('#varyFixtureasset-0').inner_text() == 'Use Prepare new seed'
    vary = (page.locator('#makeRuns [data-make-vary="subtle"]').count(), page.locator('#makeRuns [data-ux-vary]').count()); assert vary[0] >= 1 and vary[1] == 0, vary
    page.locator('[data-make-polish=upscale][data-asset=asset-0]').click()
    assert page.locator('[data-make-polish=upscale][data-asset=asset-0]').is_disabled()
    assert page.locator('.make-action-reason').count() == 1 and page.locator('.make-action-reason').is_visible()
    assert 'Please wait' in page.locator('.make-action-reason').inner_text()
    page.evaluate('()=>finishPolish({id:"fixture-finish",status:"completed",outputs:[]})')
    # #1514 keeps ongoing cards beyond the six finished cards: the seventh card must not evict an active run.
    page.wait_for_function('document.querySelectorAll("#makeRuns .make-run").length===7'); page.wait_for_timeout(3000); READS.clear(); page.wait_for_timeout(3000)
    shown = page.eval_on_selector_all('#makeRuns [data-run]', 'n=>n.map(e=>e.dataset.run)')
    assert saved[5]['id'] in shown and saved[5]['id'] in READS and saved[4]['id'] in READS, (shown, READS)
    # Workspace masks carry the same filename in source; titles use prompt excerpt and date.
    assets = [dict(fixture.ASSETS[0], id='mask', filename='opaque.png', source={'filename':'Anime-Face-Mask_00001_.png'}), dict(fixture.ASSETS[1], prompt_excerpt='A moonlit garden')]
    page.route('**/api/workspace', lambda route: route.fulfill(json={'assets': assets}))
    page.locator('[data-make-goal="repair"]').click(); page.wait_for_selector('#makePictures button')
    assert page.locator('#makePictures button').count() == 1
    assert 'A moonlit garden' in page.locator('#makePictures').inner_text()
    assert 'A moonlit garden' in page.locator('#makePictures img').get_attribute('alt'), 'each picture choice names its picture'
    # A run that finishes in the background adds its picture to the open grid (#1438).
    assets.append(dict(fixture.ASSETS[1], id='asset-fresh', prompt_excerpt='A fresh lantern', created_at=1789228900))
    MAKE_JOBS[saved[4]['id']].update(status='completed', outputs=[dict(filename='fresh.png', asset_id='asset-fresh', media_type='image')])
    page.wait_for_selector('#makePictures [data-make-pick="asset-fresh"]', timeout=6000)
    recovery_checks(browser, origin)
    assert not errors, errors
    page.close()


def library_checks(browser, origin):
    # The Library's picture dialog opens Make first (audit v3 N3): Change it / Fix or upscale / Restyle / New pose open that picture goal
    # with the picture chosen; Continue with this stays as the full editor route. Unsaved details keep the dialog open. Nothing is sent.
    page = browser.new_page(viewport={'width': 1440, 'height': 900}); errors = []; page.on('pageerror', lambda e: errors.append(str(e)))
    answers = []; page.on('dialog', lambda d: d.accept() if answers and answers.pop(0) else d.dismiss())
    page.goto(origin+'/#assets'); page.wait_for_selector('#assetGrid [data-asset-open="asset-1"]'); before = len(jobs())
    page.locator('#assetGrid .asset-open[data-asset-open="asset-1"]').click(); page.wait_for_selector('#assetHandoffs [data-make-open]')
    rows = page.eval_on_selector_all('#assetHandoffs .ux-route-row', 'n=>n.map(e=>e.getAttribute("aria-label")+": "+[...e.querySelectorAll("button")].map(b=>b.textContent).join(" | "))')
    assert rows == ['Open in Make: Change it | Fix or upscale | Restyle | New pose', 'Full editor: Continue with this → | Find recipes for this image'], rows
    assert page.get_attribute('#assetHandoffs [data-make-open="edit"]', 'class') == 'primary' and page.get_attribute('#assetHandoffs [data-ux-handoff]', 'class') is None
    page.fill('#assetNotes', 'unsaved note'); answers.append(False); page.click('#assetHandoffs [data-make-open="combine"]')
    assert page.evaluate('document.querySelector("#assetDialog").open') and page.input_value('#assetNotes') == 'unsaved note', 'declining the discard keeps the dialog'
    answers.append(True); page.click('#assetHandoffs [data-make-open="combine"]'); page.wait_for_selector('[aria-labelledby=makeSlotA] img', state='attached')
    assert not page.evaluate('document.querySelector("#assetDialog").open') and page.evaluate('location.hash') == '#make' and not page.is_hidden('#makeView')
    assert page.get_attribute('#makeGoals [aria-checked=true]', 'data-make-goal') == 'combine' and page.get_attribute('[aria-labelledby=makeSlotA] img', 'src') == '/api/assets/asset-1/thumb'
    assert 'your picture is chosen' in page.inner_text('#makeStatus')
    page.goto(origin+'/#assets'); page.wait_for_selector('#assetGrid [data-asset-open="asset-0"]')
    page.locator('#assetGrid .asset-open[data-asset-open="asset-0"]').click(); page.click('#assetHandoffs [data-make-open="repair"]'); page.wait_for_selector('#makeComposer [data-make-fix]')
    assert page.get_attribute('#makeGoals [aria-checked=true]', 'data-make-goal') == 'repair' and page.get_attribute('.make-picked img', 'src') == '/api/assets/asset-0/thumb'
    assert len(jobs()) == before, 'opening Make from the Library sends nothing'
    assert not errors, errors
    page.close()


def merge_checks(browser, origin):
    # Round 5 (#1492): where Fix face and Fix hands resolve to the same recipe (Anima pictures: anime-detail-fix) Make offers one
    # "Fix face and hands" button and says what the WAI repaint can cost; a WAI picture keeps two buttons and no warning. Real plans, nothing sent.
    HINT, UP = 'Repaints with a WAI model', 'Smooths fine texture; upscale the version you chose.'
    MAKE_JOBS['make-merge'] = dict(id='make-merge', status='completed', created_at=1789228800, outputs=[dict(filename='anima.png', asset_id='asset-0', media_type='image'), dict(filename='wai.png', asset_id=WAI, media_type='image')])
    saved = [dict(id='make-merge', look='First look', lookId=LOOKS[0]['id'], goal='character', scene='Merge')]
    page = browser.new_page(viewport={'width': 1440, 'height': 900}); errors = []; page.on('pageerror', lambda e: errors.append(str(e))); before = len(jobs())
    page.goto(origin+'/#make'); page.evaluate('(runs)=>localStorage.setItem("studio.make",JSON.stringify({goal:"character",look:null,runs}))', saved)
    page.goto(origin+'/?merge#make'); page.wait_for_selector('[data-make-polish=upscale][data-asset=asset-0]'); page.wait_for_selector('[data-make-polish=upscale][data-asset=%s]' % WAI)
    page.wait_for_function('document.querySelectorAll("#makeRuns .make-polish-hint").length===5')
    kinds = lambda a: page.eval_on_selector_all('[data-make-polish][data-asset=%s]' % a, 'n=>n.map(e=>e.dataset.makePolish+":"+e.firstChild.textContent)')
    assert kinds('asset-0') == ['face:Fix face and hands', 'refine:Refine 1.5×', 'upscale:Upscale 2×'], kinds('asset-0')
    assert kinds(WAI) == ['face:Fix face', 'details:Fix hands and details', 'refine:Refine 1.5×', 'upscale:Upscale 2×'], kinds(WAI)
    hints = page.eval_on_selector_all('#makeRuns .make-polish-hint', 'n=>n.map(e=>e.textContent)')
    assert sum(h.startswith(HINT) for h in hints) == 1 and hints[0].startswith(HINT), hints
    assert hints.count(UP) == 2 and len(hints) == 5 and sum(h.startswith('Refine redraws') for h in hints) == 2, hints
    # The goal composer merges the same way.
    page.locator('[data-make-goal="repair"]').click(); page.wait_for_selector('#makePictures [data-make-pick="asset-0"]'); page.locator('#makePictures [data-make-pick="asset-0"]').click()
    page.wait_for_function('document.querySelectorAll("#makeComposer [data-make-fix]").length===3')
    assert page.eval_on_selector_all('#makeComposer [data-make-fix]', 'n=>n.map(e=>e.dataset.makeFix)') == ['face', 'refine', 'upscale'] and 'Fix face and hands' in page.locator('label:has([data-make-fix=face])').inner_text()
    assert page.is_checked('[data-make-fix=face]') and HINT in page.locator('#makeComposer').inner_text() and UP in page.locator('#makeComposer').inner_text()
    page.locator('[data-make-repick]').first.click(); page.wait_for_selector('#makePictures [data-make-pick="%s"]' % WAI); page.locator('#makePictures [data-make-pick="%s"]' % WAI).click()
    page.wait_for_function('document.querySelectorAll("#makeComposer [data-make-fix]").length===4')
    assert HINT not in page.locator('#makeComposer').inner_text() and UP in page.locator('#makeComposer').inner_text()
    assert len(jobs()) == before, 'planning and drawing hints sends nothing'
    # The merged pass is saved under the name Make showed, so the Library does not call a face-and-hands repaint face-only (Codex on #1494).
    page.goto(origin+'/?merge2#make'); page.wait_for_selector('[data-make-polish=face][data-asset=asset-0]'); page.locator('[data-make-polish=face][data-asset=asset-0]').click()
    for _ in range(50):
        if len(jobs()) > before: break
        page.wait_for_timeout(100)
    assert jobs() and jobs()[-1].get('label') == 'Make · Fix face and hands', jobs()[-1:] 
    assert not errors, errors
    page.close()


def recovery_checks(browser, origin):
    # Restore (#1438): a run whose first read fails is kept and checked again; one the Studio says is gone (404) is dropped.
    # An uncertain run offers Resume observation and Stop tracking on its own card; neither sends a picture again.
    MAKE_JOBS['make-unsure'] = dict(id='make-unsure', status='uncertain', outputs=[], created_at=1789228800, prompt_ids=['p-1'], has_pending_submission=False, can_stop_tracking=True, can_resume_tracking=False, message='Outcome unknown')
    MAKE_JOBS['make-flaky'] = dict(id='make-flaky', status='running', outputs=[], created_at=1789228800)
    FAILING.add('make-flaky')
    saved = [dict(id=i, look='First look', lookId=LOOKS[0]['id'], goal='character', scene='Recovery '+i) for i in ('make-unsure', 'make-flaky', 'make-gone')]
    page = browser.new_page(); errors = []; page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(origin+'/#make'); page.evaluate('(runs)=>localStorage.setItem("studio.make",JSON.stringify({goal:"character",look:null,runs}))', saved)
    page.goto(origin+'/?recovery#make'); page.wait_for_selector('[data-run="make-flaky"]')
    assert page.locator('[data-run="make-flaky"] .make-run-state').inner_text().startswith('Lost contact'), 'a failed first read keeps the run'
    assert page.locator('[data-run="make-gone"]').count() == 0, 'a 404 run is dropped'
    assert page.evaluate('JSON.parse(localStorage.getItem("studio.make")).runs.map(r=>r.id)') == ['make-unsure', 'make-flaky'], 'the kept run stays saved'
    FAILING.discard('make-flaky')
    page.wait_for_function('!document.querySelector(`[data-run="make-flaky"] .make-run-state`).textContent.startsWith("Lost contact")', timeout=12000)
    card = page.locator('[data-run="make-unsure"]')
    assert 'nothing was sent again' in card.locator('.make-run-state').inner_text() and 'Compare & review' not in card.inner_text()
    before = len(jobs()); card.locator('summary').click(); card.locator('[data-make-stop]').click()
    assert 'reason' in page.locator('#makeStatus').inner_text() and not any(p['path'].endswith('/stop-tracking') for p in fixture.POSTS), 'no reason, no request'
    card.locator('[data-make-resume]').click()
    page.wait_for_function('document.querySelector("#makeStatus").textContent.startsWith("Checking ComfyUI again")')
    assert any(p['path'] == '/api/jobs/make-unsure/resume' for p in fixture.POSTS) and len(jobs()) == before, 'Resume reads again; it never posts a job'
    MAKE_JOBS['make-unsure'].update(status='uncertain')
    page.wait_for_selector('[data-run="make-unsure"] [data-make-stop]', state='attached', timeout=8000)
    assert card.locator('details').evaluate('(e)=>e.open'), 'an open Stop tracking menu stays open across a redraw'
    card.locator('[data-make-stop-reason]').fill('ComfyUI was restarted'); card.locator('[data-make-stop]').click()
    page.wait_for_function('document.querySelector("#makeStatus").textContent.startsWith("Tracking stopped")')
    assert next(p for p in fixture.POSTS if p['path'] == '/api/jobs/make-unsure/stop-tracking')['data'] == {'reason': 'ComfyUI was restarted'}
    assert len(jobs()) == before and card.locator('[data-make-resume]').count() == 1, 'after stopping, Resume stays offered'
    # A Compare card's looks get the same recovery controls on their own figure (Codex review of #1462): an uncertain one is not a dead end.
    MAKE_JOBS['make-gunsure'] = dict(MAKE_JOBS['make-unsure'], id='make-gunsure', status='uncertain', prompt_ids=['p-2'], can_stop_tracking=True, tracking_disposition=None)
    MAKE_JOBS['make-gdone'] = dict(id='make-gdone', status='completed', outputs=[], created_at=1789228800)
    group = [dict(id=i, look='First look', lookId=LOOKS[0]['id'], goal='character', scene='Compare recovery', group='cmp-1') for i in ('make-gunsure', 'make-gdone')]
    page.goto(origin+'/#make'); page.evaluate('(runs)=>localStorage.setItem("studio.make",JSON.stringify({goal:"character",look:null,runs}))', group)
    page.goto(origin+'/?group#make'); page.wait_for_selector('[data-run="cmp-1"]'); card = page.locator('[data-run="cmp-1"]')
    assert card.locator('[data-make-resume]').count() == 1 and card.locator('[data-make-stop]').count() == 1, 'only the uncertain look of a Compare card offers recovery'
    assert card.locator('figure').nth(1).locator('.make-recover').count() == 0, 'the finished look offers none'
    before = len(jobs()); card.locator('[data-make-resume]').click()
    page.wait_for_function('document.querySelector("#makeStatus").textContent.startsWith("Checking ComfyUI again")')
    assert any(p['path'] == '/api/jobs/make-gunsure/resume' for p in fixture.POSTS) and len(jobs()) == before, 'Resume on a Compare look reads again; it never posts a job'
    assert not errors, errors
    page.close()


def run():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler); threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = 'http://127.0.0.1:'+str(server.server_port); errors = []
    template = {p['id']: p['continuation_capability']['template_sha256'] for p in fixture.CATALOG['presets']}
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True); page = browser.new_page(); page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(origin+'/#create'); page.wait_for_function('window.StudioWorkbench?.polish&&catalog?.presets?.length&&!!selected')
            assert not jobs(), 'nothing is submitted on load'
            page.evaluate('()=>{selectPreset("anima-portrait");document.querySelector("#positive").value="My own words, untouched"}')
            before = page.evaluate('()=>({preset:selected.id,positive:document.querySelector("#positive").value,parents:[...parentAssets],uploaded,claim:continuationState||null,view})')
            plan = page.evaluate('(id)=>StudioWorkbench.polishPlan(id,"face")', WAI)
            assert plan['ok'] and plan['preset_id'] == 'anime-face', plan
            assert page.evaluate('(id)=>StudioWorkbench.polishPlan(id,"face")', 'asset-0')['preset_id'] == 'anime-detail-fix', 'an Anima picture gets the general detail pass'
            assert not jobs(), 'a plan never submits'
            # Two presses at once: one job, one plain refusal.
            settled = page.evaluate('async(id)=>(await Promise.allSettled([StudioWorkbench.polish(id,"face"),StudioWorkbench.polish(id,"face")])).map(r=>r.status==="fulfilled"?{ok:r.value.id}:{error:r.reason.message})', WAI)
            assert sum('ok' in r for r in settled) == 1 and any('already' in r.get('error', '') for r in settled), settled
            assert len(jobs()) == 1, jobs()
            job = jobs()[0]; claim = job['continuation']; file = 'a'*32+'_fixture.png'
            assert job['preset_id'] == 'anime-face' and job['parent_assets'] == [WAI] and job['batch_count'] == 1, job
            assert claim == {'version': 1, 'intent': 'repair', 'preset_id': 'anime-face', 'reference_file': file, 'source_asset_id': WAI,
                             'source_sha256': 'a'*64, 'template_sha256': template['anime-face']}, claim
            assert job['controls']['reference'] == file and job['controls']['positive'] == context(WAI)['positive'], job['controls']
            # Upscale takes no words; a non-anime refusal names its reason and sends nothing.
            up = page.evaluate('(id)=>StudioWorkbench.polish(id,"upscale")', WAI)
            assert up['id'] and len(jobs()) == 2 and jobs()[1]['preset_id'] == 'anime-esrgan' and 'positive' not in jobs()[1]['controls'], jobs()[1]
            refused = page.evaluate('(id)=>StudioWorkbench.polish(id,"sharpen").then(()=>"",e=>e.message)', WAI)
            assert refused and len(jobs()) == 2, refused
            after = page.evaluate('()=>({preset:selected.id,positive:document.querySelector("#positive").value,parents:[...parentAssets],uploaded,claim:continuationState||null,view})')
            assert after == before, (before, after)
            make_checks(browser, origin)
            library_checks(browser, origin)
            merge_checks(browser, origin)
            browser.close()
    finally:
        server.shutdown(); server.server_close()
    assert not errors, errors
    print(json.dumps({'synthetic_jobs_posted': len(jobs()), 'real_generation_submissions': 0, 'double_press_posts': 1, 'make_checks_passed': True, 'create_unchanged': True, 'page_errors': errors}))


if __name__ == '__main__':
    run()
