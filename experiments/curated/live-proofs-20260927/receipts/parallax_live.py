# As-run script (27 Sep 2026), kept as a receipt; hardcodes local paths and is not a portable reproduction.
"""#1219/#1231 Make parallax layers, live on the real page (27 Sep 2026), on the owner-accepted anchor z2 (asset beecbff4).
Asset library -> Make parallax layers -> foreground words -> drag two far-view boxes inside the window glass (left and right
pane) on the page's picture -> Make parallax layers -> Generate (clean plate) -> Generate (isolate, loaded by the page) ->
the Studio splits the layers. The run is followed through the API."""
import json, sys, time
sys.path.insert(0, 'C:/Users/jekyt/AppData/Local/Temp/cancel-proof-0927'); import drive
from playwright.sync_api import sync_playwright
OUT = 'C:/Users/jekyt/AppData/Local/Temp/liveproofs/'
ASSET = 'beecbff4c08d5da0b7b6dcebbbab2fe5'
OBJECTS = 'the desk, the chair, the desk lamp and the computer monitor'
BOXES = [(988, 75, 1125, 425), (1172, 35, 1336, 445)]   # inside the glass of the two panes (lab route C2 polygons: 978-1133 x 62-440, 1162-1344 x 22-478)
rec = {'asset': ASSET, 'objects': OBJECTS, 'boxes_intended': BOXES, 'events': []}
def ev(k, **kw): rec['events'].append(dict(t=round(time.time(), 3), kind=k, **kw)); print(k, json.dumps(kw)[:700], flush=True)
r, p = drive.queue(); assert not r and not p
before = {j['id'] for j in drive.studio('/api/jobs')[1]}
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True); page = b.new_page(viewport={'width': 1440, 'height': 1200})
    errors, posts = [], []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('request', lambda q: posts.append((round(time.time(), 3), q.url.replace(drive.S, ''))) if q.method == 'POST' else None)
    page.on('dialog', lambda d: (ev('dialog', message=d.message), d.accept()))
    page.goto(drive.S + '/#assets', wait_until='domcontentloaded'); page.wait_for_timeout(3000)
    page.select_option('#assetSource', 'all'); page.wait_for_timeout(600)
    page.locator('#assetSearch').click(); page.keyboard.type('Z-Image Turbo', delay=15); page.wait_for_timeout(1200)
    for _ in range(30):
        if page.locator('[data-asset-open="%s"]' % ASSET).count(): break
        more = page.locator('[data-asset-more], button:has-text("Show more")')
        if not more.count(): break
        more.first.click(); page.wait_for_timeout(700)
    page.locator('[data-asset-open="%s"]' % ASSET).first.click(); page.wait_for_timeout(3000)
    g = page.locator('#assetDialog .ux-parallax')
    ev('panel', text=g.inner_text()[:400])
    g.locator('#uxParallaxObjects').fill(OBJECTS)
    g.locator('.ux-parallax-mark > summary').click(); page.wait_for_timeout(800)
    img = g.locator('.ux-parallax-pick img'); img.evaluate("e => e.scrollIntoView({block: 'center'})"); page.wait_for_timeout(500)
    bb = img.bounding_box(); ev('pick_box', box=bb)
    for x0, y0, x1, y1 in BOXES:
        sx = lambda x: bb['x'] + x / 1344 * bb['width']; sy = lambda y: bb['y'] + y / 768 * bb['height']
        page.mouse.move(sx(x0), sy(y0)); page.mouse.down(); page.mouse.move((sx(x0) + sx(x1)) / 2, (sy(y0) + sy(y1)) / 2, steps=5)
        page.mouse.move(sx(x1), sy(y1), steps=5); page.mouse.up(); page.wait_for_timeout(400)
    ev('boxes_on_page', view=g.locator('#uxParallaxView').input_value(), why=g.locator('#uxParallaxWhy').inner_text(), disabled=g.locator('[data-ux-parallax]').is_disabled())
    g.locator('.ux-parallax-mark').screenshot(path=OUT + 'parallax-boxes.png')
    g.locator('[data-ux-parallax]').click(); page.wait_for_timeout(4000)
    ev('prepared', status=page.locator('p#status').inner_text() if page.locator('p#status').count() else None, selected=page.evaluate('selected && selected.id'),
       hint=page.locator('#referenceHint').inner_text(), positive=page.evaluate('document.querySelector("#positive").value')[:400])
    for stage in ('plate', 'isolate'):
        c = drive.commit(); ev('commit_before_' + stage, **c)
        if c['pct'] >= 90: raise SystemExit('ABORT: commit before ' + stage)
        page.locator('#generate').evaluate("e => e.scrollIntoView({block: 'center'})"); page.locator('#generate').click(); page.wait_for_timeout(5000)
        ev('generated_' + stage, status=page.locator('p#status').inner_text() if page.locator('p#status').count() else None,
           positive=page.evaluate('document.querySelector("#positive").value')[:300], job_posts=[x for x in posts if x[1] == '/api/jobs'])
    b.close()
new = [j for j in drive.studio('/api/jobs')[1] if j['id'] not in before]
ev('jobs', new=[(j['id'], j['preset_id'], j['status'], (j.get('parallax') or {}).get('stage')) for j in new])
while any(drive.job(j['id'])['status'] in drive.ACTIVE for j in new): time.sleep(5)
for _ in range(60):
    js = [drive.job(j['id']) for j in new]
    if any((j.get('parallax_finish') or {}).get('job_id') or (j.get('parallax_finish') or {}).get('error') for j in js): break
    time.sleep(3)
rec['jobs'] = [{k: j.get(k) for k in ('id', 'preset_id', 'status', 'message', 'prompt_ids', 'elapsed_seconds', 'parallax', 'parallax_finish', 'outputs', 'parent_assets')} for j in js]
fin = next(((j.get('parallax_finish') or {}).get('job_id') for j in js if (j.get('parallax_finish') or {}).get('job_id')), None)
if fin:
    fj = drive.job(fin); rec['finish_job'] = {k: fj.get(k) for k in ('id', 'status', 'message', 'outputs', 'operation', 'elapsed_seconds')}
rec.update(page_errors=errors, page_posts=posts)
json.dump(rec, open(OUT + 'parallax-live.json', 'w'), indent=1)
for j in rec['jobs']: print('JOB', j['id'][:8], (j['parallax'] or {}).get('stage'), j['status'], j['prompt_ids'], round(j['elapsed_seconds'] or 0, 1), json.dumps(j.get('parallax_finish'))[:500])
print('FINISH', json.dumps(rec.get('finish_job'))[:1500])
