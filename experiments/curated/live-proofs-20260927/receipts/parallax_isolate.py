# As-run script (27 Sep 2026), kept as a receipt; hardcodes local paths and is not a portable reproduction.
"""Second try of the isolate stage through the page (27 Sep 2026): the first isolate job (37b9c16b) was refused by the Studio's
32 GiB host-commit gate with nothing sent. Create -> Recent runs -> the plate job's card -> its 'load the isolate edit' button ->
Generate. Then wait for the split."""
import json, sys, time
sys.path.insert(0, 'C:/Users/jekyt/AppData/Local/Temp/cancel-proof-0927'); import drive
from playwright.sync_api import sync_playwright
OUT = 'C:/Users/jekyt/AppData/Local/Temp/liveproofs/'
PLATE = '7fb68111-0025-43b8-a0b8-6c8ca6bd9b2b'
rec = json.load(open(OUT + 'parallax-live.json')); ev_list = rec.setdefault('isolate_retry', [])
def ev(k, **kw): ev_list.append(dict(t=round(time.time(), 3), kind=k, **kw)); print(k, json.dumps(kw)[:700], flush=True)
before = {j['id'] for j in drive.studio('/api/jobs')[1]}
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True); page = b.new_page(viewport={'width': 1440, 'height': 1200})
    errors, posts = [], []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('request', lambda q: posts.append((round(time.time(), 3), q.url.replace(drive.S, ''))) if q.method == 'POST' else None)
    page.goto(drive.S + '/#create', wait_until='domcontentloaded'); page.wait_for_timeout(4000)
    page.locator('#workshopResults > summary').click(); page.wait_for_timeout(2000)
    btn = page.locator('.parallaxStage[data-job="%s"]' % PLATE)
    ev('stage_button', count=btn.count(), notes=page.locator('.imageCard:has([data-job="%s"]) .disabledReason' % PLATE).all_inner_texts()[:2])
    btn.first.evaluate("e => e.scrollIntoView({block: 'center'})"); btn.first.click(); page.wait_for_timeout(3000)
    ev('loaded', status=page.locator('p#status').inner_text() if page.locator('p#status').count() else None, hint=page.locator('#referenceHint').inner_text(),
       positive=page.evaluate('document.querySelector("#positive").value')[:300])
    c = drive.commit(); ev('commit_before_isolate', **c)
    if c['pct'] >= 90: raise SystemExit('ABORT: commit')
    page.locator('#generate').evaluate("e => e.scrollIntoView({block: 'center'})"); page.locator('#generate').click(); page.wait_for_timeout(5000)
    ev('generated', job_posts=[x for x in posts if x[1] == '/api/jobs'], errors=errors)
    b.close()
new = [j for j in drive.studio('/api/jobs')[1] if j['id'] not in before]
ev('jobs', new=[(j['id'], j['preset_id'], j['status'], (j.get('parallax') or {}).get('stage')) for j in new])
while any(drive.job(j['id'])['status'] in drive.ACTIVE for j in new): time.sleep(5)
for _ in range(60):
    js = [drive.job(j['id']) for j in new] + [drive.job(PLATE)]
    if any((j.get('parallax_finish') or {}).get('job_id') or (j.get('parallax_finish') or {}).get('error') for j in js): break
    time.sleep(3)
rec['jobs_retry'] = [{k: j.get(k) for k in ('id', 'preset_id', 'status', 'message', 'prompt_ids', 'elapsed_seconds', 'parallax', 'parallax_finish', 'outputs')} for j in js]
fin = next(((j.get('parallax_finish') or {}).get('job_id') for j in js if (j.get('parallax_finish') or {}).get('job_id')), None)
if fin:
    fj = drive.job(fin); rec['finish_job'] = {k: fj.get(k) for k in ('id', 'status', 'message', 'outputs', 'operation', 'elapsed_seconds')}
json.dump(rec, open(OUT + 'parallax-live.json', 'w'), indent=1)
for j in rec['jobs_retry']: print('JOB', j['id'][:8], (j['parallax'] or {}).get('stage'), j['status'], j['prompt_ids'], round(j['elapsed_seconds'] or 0, 1), json.dumps(j.get('parallax_finish'))[:600])
print('FINISH', json.dumps(rec.get('finish_job'))[:1500])
