# As-run script (27 Sep 2026), kept as a receipt; hardcodes local paths and is not a portable reproduction.
"""#1163 results panel + #1203 review checks, live on the real page (27 Sep 2026).
Rebuilds the same Combine pair as plan_live.py (no plan, no generation), reads "Runs for these pictures" (the plan's three
runs must be there, tagged "from a plan"), taps review-check chips on the plan's tiles, reads the per-run (per-engine) tallies,
reloads the page and reads them again. Then it cycles every tapped chip back to "not checked" (only the owner's answers should
remain) and confirms that the cleared state also persists. Nothing is generated."""
import json, sys, time
sys.path.insert(0, 'C:/Users/jekyt/AppData/Local/Temp/cancel-proof-0927'); import drive
from playwright.sync_api import sync_playwright
OUT = 'C:/Users/jekyt/AppData/Local/Temp/liveproofs/'
CHAR, POSE = '021731c057d955b4a2487395a37fadf6', '025678cadf5750bf9a3bfa8ed62e6590'
PLAN_JOBS = {'combine-klein': 'c13dbf5c', 'combine-klein-9b-depth': '6e66575c', 'combine-klein-9b-copypose': '227a9fe3'}
TAPS = [('combine-klein', 'pose', 1), ('combine-klein-9b-depth', 'pose', 2), ('combine-klein-9b-copypose', 'face', 1)]   # 1 tap = yes, 2 = no
rec = {'events': []}
def ev(k, **kw): rec['events'].append(dict(t=round(time.time(), 3), kind=k, **kw)); print(k, json.dumps(kw)[:700], flush=True)

def build_pair(page):
    page.goto(drive.S + '/#assets', wait_until='domcontentloaded'); page.wait_for_timeout(3000)
    page.select_option('#assetSource', 'all'); page.wait_for_timeout(600)
    page.locator('#assetSearch').click(); page.keyboard.type('modular illustration', delay=15); page.wait_for_timeout(1200)
    page.locator('[data-asset-open="%s"]' % CHAR).first.click(); page.wait_for_timeout(1200)
    page.locator('#assetDialog [data-ux-handoff]').first.click(); page.wait_for_timeout(2000)
    page.locator('#uxHandoffIntents [data-ux-destination="combine"]').click(); page.wait_for_timeout(1000)
    page.select_option('#uxDestination', 'combine-klein-9b-copypose'); page.wait_for_timeout(600)
    page.locator('#uxPrepareHandoff').click(); page.wait_for_timeout(3000)
    page.locator('#uxPullAsset').click(); page.wait_for_timeout(1500)
    page.locator('[data-ux-pull="%s"]' % POSE).first.click(); page.wait_for_timeout(3000)
    if page.locator('#uxSourcePicker[open]').count():
        try: page.click('[data-ux-close="uxSourcePicker"]', timeout=2000)
        except Exception: pass
    page.wait_for_timeout(2000)

def groups(page):
    return page.evaluate("""() => [...document.querySelectorAll('.ux-run-group')].map(g => ({
        head: (g.querySelector('.ux-run-head b')||{}).innerText, facts: (g.querySelector('.ux-run-head small')||{}).innerText,
        checks: (g.querySelector('.ux-run-checks')||{}).innerText || '',
        job: (g.querySelector('[data-ux-result-recipe]')||{dataset:{}}).dataset.uxResultRecipe,
        chips: [...g.querySelectorAll('[data-ux-check]')].map(c => c.dataset.uxCheck + ':' + c.className.replace('review-check','').trim()) }))""")

def plan_groups(page):
    return [g for g in groups(page) if any((g.get('job') or '').startswith(v) for v in PLAN_JOBS.values())]

def tap(page, engine, check, times):
    for _ in range(times):
        grp = page.locator('.ux-run-group:has([data-ux-result-recipe^="%s"])' % PLAN_JOBS[engine])
        chip = grp.locator('[data-ux-check="%s"]' % check).first
        chip.evaluate("e => e.scrollIntoView({block: 'center'})"); chip.click(); page.wait_for_timeout(2500)

def fresh(pw):
    b = pw.chromium.launch(headless=True); page = b.new_page(viewport={'width': 1440, 'height': 1100})
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('request', lambda q: posts.append((round(time.time(), 3), q.method, q.url.replace(drive.S, ''))) if q.method in ('POST', 'PATCH', 'PUT') else None)
    build_pair(page); return b, page

errors, posts = [], []
job_assets = {j['id'][:8]: [o.get('asset_id') for o in j['outputs']] for j in drive.studio('/api/jobs')[1] if j.get('project_id') == 'cd3c581291914ccf806483ee38763656'}
def server_tags():
    ws = drive.studio('/api/workspace')[1]['assets']; return {k: [a['tags'] for a in ws if a['id'] in v] for k, v in job_assets.items()}
with sync_playwright() as pw:
    # Attempt 1 (review-live-attempt1.json) tapped pose=yes on Klein 4B, pose=no on 9B depth, face=yes on 9B Copy Pose, then
    # crashed while rebuilding the pair after an in-context reload. A fresh browser session is the stricter persistence test.
    b, page = fresh(pw)
    ev('fresh_session_reads_attempt1_taps', plan_groups=plan_groups(page), server_tags=server_tags())
    page.locator('h3:has-text("Runs for these pictures")').first.evaluate("e => e.scrollIntoView({block: 'start'})"); page.wait_for_timeout(500)
    page.screenshot(path=OUT + 'runs-panel-fresh-session.png')
    for engine, check, times in [('combine-klein', 'pose', 2), ('combine-klein-9b-depth', 'pose', 1), ('combine-klein-9b-copypose', 'face', 2)]:
        tap(page, engine, check, times)
    ev('after_clear', plan_groups=plan_groups(page))
    b.close()
    b, page = fresh(pw)
    ev('fresh_session_after_clear', plan_groups=plan_groups(page), server_tags=server_tags())
    b.close()
rec.update(page_errors=errors, page_writes=posts)
json.dump(rec, open(OUT + 'review-live.json', 'w'), indent=1)
print('errors', errors); print('writes', [p for p in posts if not p[2].startswith('/api/estimate')])
