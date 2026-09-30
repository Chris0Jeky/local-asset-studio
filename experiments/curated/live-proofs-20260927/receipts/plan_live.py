# As-run script (27 Sep 2026), kept as a receipt; hardcodes local paths and is not a portable reproduction.
"""#1163 multi-engine Combine plan + #1203 review checks, live on the real page (27 Sep 2026).
Character (image kept): fantasy-pack portrait asset 021731c0 (Studio/Anima-v1-Baseline_00004_.png).
Pose picture (board): fantasy-pack full-body asset 025678ca (Studio/Anima-v1-Baseline_00005_.png). Both SFW, clothed adult.
Phase 'prepare': Continue with this -> Combine -> Prepare -> pull the pose picture -> three fills -> tick recipes -> seed ->
Prepare plan (records the estimate). Phase 'start' (same page session): waits for an idle ComfyUI queue, checks commit < 90 %,
presses Start plan once, then leaves the page; the run is followed through the API."""
import json, sys, time
sys.path.insert(0, 'C:/Users/jekyt/AppData/Local/Temp/cancel-proof-0927'); import drive
from playwright.sync_api import sync_playwright
OUT = 'C:/Users/jekyt/AppData/Local/Temp/liveproofs/'
CHAR, POSE = '021731c057d955b4a2487395a37fadf6', '025678cadf5750bf9a3bfa8ed62e6590'
ENGINES = sys.argv[1].split(',') if len(sys.argv) > 1 else ['combine-klein', 'combine-klein-9b-copypose']
SEED = '2026092795'
ANSWERS = (('who', 'the adult traveller with long dark hair, a centre part, brown eyes and gold earrings'),
           ('pose', 'standing upright, holding a lantern at her side'),
           ('cloth', 'a navy double-breasted coat with brass buttons, a teal scarf, dark trousers and brown lace-up boots'))
rec = {'engines_requested': ENGINES, 'seed': SEED, 'events': []}
def ev(k, **kw): rec['events'].append(dict(t=round(time.time(), 3), kind=k, **kw)); print(k, json.dumps(kw)[:400], flush=True)
def save(): json.dump(rec, open(OUT + 'plan-live.json', 'w'), indent=1)

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True); page = b.new_page(viewport={'width': 1440, 'height': 1100})
    errors, posts = [], []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('request', lambda q: posts.append((round(time.time(), 3), q.url.replace(drive.S, ''))) if q.method == 'POST' else None)
    page.on('dialog', lambda d: (ev('dialog', message=d.message), d.accept()))
    page.goto(drive.S + '/#assets', wait_until='domcontentloaded'); page.wait_for_timeout(3000)
    page.select_option('#assetSource', 'all'); page.wait_for_timeout(600)
    page.locator('#assetSearch').click(); page.keyboard.type('modular illustration', delay=15); page.wait_for_timeout(1200)
    page.locator('[data-asset-open="%s"]' % CHAR).first.click(); page.wait_for_timeout(1200)
    page.locator('#assetDialog [data-ux-handoff]').first.click(); page.wait_for_timeout(2000)
    page.locator('#uxHandoffIntents [data-ux-destination="combine"]').click(); page.wait_for_timeout(1200)
    ev('handoff', destination=page.evaluate("() => (document.querySelector('#uxDestination')||{}).value"),
       options=page.evaluate("() => [...(document.querySelector('#uxDestination')||{options:[]}).options].map(o=>o.value)"))
    if page.locator('#uxDestination').count() and ENGINES[0] in page.evaluate("() => [...document.querySelector('#uxDestination').options].map(o=>o.value)"):
        page.select_option('#uxDestination', ENGINES[0]); page.wait_for_timeout(800)
    page.locator('#uxPrepareHandoff').click(); page.wait_for_timeout(3000)
    ev('prepared_handoff', selected=page.evaluate("() => selected && selected.id"), blockers=page.locator('#uxBlockers').inner_text() if page.locator('#uxBlockers').count() else None)
    page.locator('#uxPullAsset').click(); page.wait_for_timeout(1500)
    if page.locator('#uxSourceSlot').count():
        try: page.select_option('#uxSourceSlot', '0', timeout=3000)
        except Exception as e: ev('slot_select_failed', error=str(e)[:200])
    pull = page.locator('[data-ux-pull="%s"]' % POSE)
    if not pull.count():
        s = page.locator('#uxSourceSearch')
        if s.count(): s.first.fill('modular illustration'); page.wait_for_timeout(1200)
    ev('picker', pull_buttons=page.locator('[data-ux-pull]').count(), pose_present=page.locator('[data-ux-pull="%s"]' % POSE).count())
    page.locator('[data-ux-pull="%s"]' % POSE).first.click(); page.wait_for_timeout(3000)
    if page.locator('#uxSourcePicker[open]').count():
        try: page.click('[data-ux-close="uxSourcePicker"]', timeout=2000)
        except Exception: pass
    fields = page.evaluate('[...document.querySelectorAll("#uxFills:not([hidden]) [data-ux-fill]")].map(i => i.dataset.uxFill)')
    for f in fields:
        words = next((w for k, w in ANSWERS if k in f.lower()), ANSWERS[0][1])
        page.locator('[data-ux-fill="%s"]' % f.replace('"', '\\"')).fill(words)
    page.wait_for_timeout(800)
    ev('filled', fields=fields, positive=page.evaluate('document.querySelector("#positive").value')[:600],
       board=page.evaluate('typeof referenceRecords!=="undefined" ? referenceRecords.filter(r=>r.file).map(r=>r.file) : null'))
    page.locator('#uxEnginePlan > summary').click(); page.wait_for_timeout(800)
    ev('plan_options', options=page.evaluate("() => [...document.querySelectorAll('[data-ux-plan-engine]')].map(i=>[i.dataset.uxPlanEngine,i.checked,i.disabled,i.title])"))
    for e in ENGINES:
        box = page.locator('[data-ux-plan-engine="%s"]' % e)
        if box.count() and box.is_enabled() and not box.is_checked(): box.check()
    for box in page.locator('[data-ux-plan-engine]').all():
        if box.is_checked() and box.get_attribute('data-ux-plan-engine') not in ENGINES: box.uncheck()
    page.locator('#uxPlanSeeds').fill(SEED); page.wait_for_timeout(800)
    ev('plan_summary', summary=page.locator('#uxPlanSummary').inner_text(),
       ticked=page.evaluate("() => [...document.querySelectorAll('[data-ux-plan-engine]')].filter(i=>i.checked).map(i=>i.dataset.uxPlanEngine)"))
    page.screenshot(path=OUT + 'plan-before-prepare.png', full_page=False)
    page.locator('#uxPlanPrepare').evaluate("e => e.scrollIntoView({block: 'center'})"); page.wait_for_timeout(500)
    ev('prepare_button', disabled=page.locator('#uxPlanPrepare').is_disabled(), status_before=page.locator('#uxPlanStatus').inner_text())
    t_prep = time.time(); page.locator('#uxPlanPrepare').click()
    page.wait_for_function('!document.querySelector("#uxPlanStart").hidden || (document.querySelector("#uxPlanStatus").textContent.length > 0 && !/Checking every recipe/.test(document.querySelector("#uxPlanStatus").textContent))', timeout=300000)
    ev('plan_prepared', status=page.locator('#uxPlanStatus').inner_text(), start_visible=page.locator('#uxPlanStart').is_visible(), took=round(time.time() - t_prep, 1))
    prod = [p for p in posts if p[1] == '/api/production']; ev('production_posts', posts=prod)
    save()
    if not page.locator('#uxPlanStart').is_visible(): raise SystemExit('plan not prepared')
    # wait for an idle ComfyUI and Studio before starting
    while True:
        r, p = drive.queue(); active = [j for j in drive.studio('/api/jobs')[1] if j['status'] in drive.ACTIVE]
        if not r and not p and not active: break
        time.sleep(10)
    c = drive.commit(); ev('commit_before_start', **c)
    if c['pct'] >= 90: save(); raise SystemExit('ABORT before Start: commit %.1f %%' % c['pct'])
    rec['log_before'] = drive.log_counts(); before = {j['id'] for j in drive.studio('/api/jobs')[1]}
    t_start = time.time(); page.locator('#uxPlanStart').click(); page.wait_for_timeout(4000)
    ev('plan_started', status=page.locator('#uxPlanStatus').inner_text(), start_posts=[p for p in posts if p[1].endswith('/start')])
    rec.update(t_start=t_start, jobs_before=sorted(before), page_errors=errors, page_posts=posts); save()
    b.close()
