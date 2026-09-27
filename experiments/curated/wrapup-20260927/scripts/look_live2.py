# As-run script (27 Sep 2026), kept as a receipt; hardcodes local paths and is not a portable reproduction.
"""#1221 look templates live proof (27 Sep 2026): Create -> Use a saved look -> Night Shift (retro anime) -> a new scene ->
Prepare with this look -> Variations 2 -> Generate, on the real page. The run is followed through the API."""
import json, sys, time
sys.path.insert(0, 'C:/Users/jekyt/AppData/Local/Temp/cancel-proof-0927'); import drive
from playwright.sync_api import sync_playwright
OUT = 'C:/Users/jekyt/AppData/Local/Temp/liveproofs/'
SCENE = 'a rain-soaked arcade entrance on a narrow street at night; at the right edge a glowing vending machine beside the entrance'
QUIET = sys.argv[1] == 'on'; BATCH = sys.argv[2]   # the look's optional 'Keep the quiet wall for UI backgrounds' line (#1236), and Variations
rec = {'scene': SCENE, 'events': []}
def ev(k, **kw): rec['events'].append(dict(t=round(time.time(), 3), kind=k, **kw)); print(k, json.dumps(kw)[:900], flush=True)
r, p = drive.queue(); assert not r and not p
before = {j['id'] for j in drive.studio('/api/jobs')[1]}
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True); page = b.new_page(viewport={'width': 1440, 'height': 1100})
    errors, posts, dialogs = [], [], []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('request', lambda q: posts.append((round(time.time(), 3), q.url.replace(drive.S, ''))) if q.method == 'POST' else None)
    page.on('dialog', lambda d: (dialogs.append(d.message), d.accept()))
    page.goto(drive.S + '/#create', wait_until='domcontentloaded'); page.wait_for_timeout(4000)
    page.locator('#lookBlock > summary').click(); page.wait_for_timeout(800)
    opts = page.evaluate("() => [...document.querySelectorAll('#lookSelect option')].map(o => [o.value, o.textContent])"); ev('looks', options=opts)
    look = next(v for v, t in opts if 'Night Shift' in t)
    page.select_option('#lookSelect', look); page.wait_for_timeout(500)
    page.locator('#lookScene').fill(SCENE); page.wait_for_timeout(500)
    box = page.locator('[data-look-option="quiet_wall"]')
    ev('option', present=box.count(), default_checked=box.is_checked() if box.count() else None)
    if box.count() and box.is_checked() != QUIET: box.click(); page.wait_for_timeout(300)
    ev('before_prepare', summary=page.locator('#lookSummary').inner_text(), reason=page.locator('#lookReason').inner_text(), placeholder=page.locator('#lookScene').get_attribute('placeholder'))
    page.locator('#lookPrepare').click(); page.wait_for_timeout(3000)
    ev('prepared', status=page.locator('#lookStatus').inner_text(), selected=page.evaluate('selected && selected.id'),
       positive=page.evaluate('document.querySelector("#positive").value'), seed=page.evaluate("() => (getControl('seed')||{}).value"),
       size=page.evaluate("() => [(getControl('width')||{}).value, (getControl('height')||{}).value]"))
    page.select_option('#batch', BATCH); page.wait_for_timeout(800)
    page.screenshot(path=OUT + 'look-prepared-v2-%s.png' % ('on' if QUIET else 'off'))
    c = drive.commit(); ev('commit_before_generate', **c)
    if c['pct'] >= 90: raise SystemExit('ABORT: commit')
    page.locator('#generate').click(); page.wait_for_timeout(4000)
    new = [j for j in drive.studio('/api/jobs')[1] if j['id'] not in before]
    ev('generated', new=[(j['id'], j['preset_id'], j['batch_count'], j['status']) for j in new], job_posts=[x for x in posts if x[1] == '/api/jobs'], dialogs=dialogs)
    b.close()
assert len(new) == 1; jid = new[0]['id']
while drive.job(jid)['status'] in drive.ACTIVE: time.sleep(3)
j = drive.job(jid); st = json.load(open('C:/Users/jekyt/source/local-asset-studio/experiments/runs/%s/state.json' % jid, encoding='utf-8'))
rec.update(job_id=jid, preset=j['preset_id'], status=j['status'], prompt_ids=j['prompt_ids'], elapsed_seconds=st.get('elapsed_seconds'), controls=st.get('controls'),
           outputs=[{k: o.get(k) for k in ('filename', 'subfolder', 'seed', 'asset_id')} for o in j['outputs']], page_errors=errors, page_posts=posts)
json.dump(rec, open(OUT + 'look-live-v2-quiet-%s.json' % ('on' if QUIET else 'off'), 'w'), indent=1)
print('DONE', jid, j['preset_id'], j['status'], j['prompt_ids'], round(st.get('elapsed_seconds') or 0, 1))
