# As-run script (27 Sep 2026), kept as a receipt; hardcodes local paths and is not a portable reproduction.
"""#1220 Make seamless live proof (27 Sep 2026): Asset library -> the texture -> Make seamless -> Generate on the real page,
then the tile finish (automatic, or the page's Finish tile button if the job offers it). Usage: python tile_live.py <label> <asset_id>"""
import json, sys, time
sys.path.insert(0, 'C:/Users/jekyt/AppData/Local/Temp/cancel-proof-0927'); import drive
from playwright.sync_api import sync_playwright
OUT = 'C:/Users/jekyt/AppData/Local/Temp/liveproofs/'
label, asset = sys.argv[1:3]
BAND = sys.argv[3] if len(sys.argv) > 3 else None   # seam band (px) chosen on the page's Seam band select (#1236)
rec = {'label': label, 'source_asset': asset, 'events': []}
def ev(k, **kw): rec['events'].append(dict(t=round(time.time(), 3), kind=k, **kw)); print(k, json.dumps(kw)[:600], flush=True)
r, p = drive.queue(); assert not r and not p
before = {j['id'] for j in drive.studio('/api/jobs')[1]}
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True); page = b.new_page(viewport={'width': 1440, 'height': 1100})
    errors, posts = [], []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('request', lambda q: posts.append((round(time.time(), 3), q.url.replace(drive.S, ''))) if q.method == 'POST' else None)
    page.goto(drive.S + '/#assets', wait_until='domcontentloaded'); page.wait_for_timeout(3000)
    page.select_option('#assetSource', 'all'); page.wait_for_timeout(600)
    page.locator('#assetSearch').click(); page.keyboard.type('Z-Image Turbo', delay=15); page.wait_for_timeout(1200)
    page.locator('[data-asset-open="%s"]' % asset).first.click(); page.wait_for_timeout(3000)
    ev('tile_button', text=page.locator('#assetDialog .ux-tile').inner_text() if page.locator('#assetDialog .ux-tile').count() else None,
       disabled=page.locator('#assetDialog [data-ux-tile]').is_disabled() if page.locator('#assetDialog [data-ux-tile]').count() else None)
    if BAND:
        opts = page.evaluate("() => [...document.querySelectorAll('#assetDialog [data-ux-tile-band] option')].map(o => [o.value, o.textContent, o.disabled, o.selected])")
        ev('band_options', options=opts)
        page.select_option('#assetDialog [data-ux-tile-band]', BAND); page.wait_for_timeout(500)
    page.locator('#assetDialog [data-ux-tile]').click(); page.wait_for_timeout(3000)
    ev('prepared', status=page.locator('p#status').inner_text() if page.locator('p#status').count() else None,
       positive=page.evaluate('document.querySelector("#positive").value'), hint=page.locator('#referenceHint').inner_text(), selected=page.evaluate('selected && selected.id'),
       blockers=page.evaluate("() => typeof continuationBlockerItems==='function' ? continuationBlockerItems().map(x=>x.message||x) : null"))
    pos = page.evaluate('document.querySelector("#positive").value')
    if '[' in pos:   # the texture carried no wording: describe it, as the page asks
        words = {'wall': 'front view of a dark graphite plaster wall with subtle hand-painted brush texture and faint water stains',
                 'floor': 'straight parallel dark wooden floor planks running vertically, seen exactly from above'}[label]
        s, e = pos.index('['), pos.index(']') + 1; page.locator('#positive').fill(pos[:s] + words + pos[e:]); page.wait_for_timeout(600)
        ev('wording_filled', positive=page.evaluate('document.querySelector("#positive").value'))
    c = drive.commit(); ev('commit_before_generate', **c)
    if c['pct'] >= 90: raise SystemExit('ABORT: commit')
    page.locator('#generate').click(); page.wait_for_timeout(4000)
    new = [j for j in drive.studio('/api/jobs')[1] if j['id'] not in before]
    ev('generated', new=[(j['id'], j['preset_id'], j['status']) for j in new], job_posts=[x for x in posts if x[1] == '/api/jobs'])
    assert len(new) == 1; jid = new[0]['id']
    while drive.job(jid)['status'] in drive.ACTIVE: time.sleep(3)
    for _ in range(20):
        j = drive.job(jid)
        if (j.get('outputs') and any(o.get('tile') for o in j['outputs'])) or (j.get('tile_finish') or {}).get('job_id') or (j.get('tile_finish') or {}).get('error'): break
        time.sleep(3)
    ev('after_job', status=j['status'], tile_finish=j.get('tile_finish'), outputs=[{k: o.get(k) for k in ('filename', 'subfolder', 'asset_id', 'tile')} for o in j['outputs']])
    if not any(o.get('tile') for o in j['outputs']) and not (j.get('tile_finish') or {}).get('job_id'):
        page.goto(drive.S + '/#create', wait_until='domcontentloaded'); page.wait_for_timeout(3000)
        page.locator('#workshopResults > summary').click(); page.wait_for_timeout(1500)
        btn = page.locator('.finishTile[data-job="%s"]' % jid)
        ev('finish_button', count=btn.count())
        if btn.count(): btn.first.evaluate("e => e.scrollIntoView({block: 'center'})"); btn.first.click(); page.wait_for_timeout(8000)
    b.close()
j = drive.job(jid); st = json.load(open('C:/Users/jekyt/source/local-asset-studio/experiments/runs/%s/state.json' % jid, encoding='utf-8'))
rec.update(job_id=jid, job_public={k: j.get(k) for k in ('status', 'message', 'prompt_ids', 'elapsed_seconds', 'tile', 'tile_finish', 'outputs', 'parent_assets')},
           state_tile={k: st.get(k) for k in ('tile', 'tile_finish')}, page_errors=errors, page_posts=posts)
fin = (j.get('tile_finish') or {}).get('job_id')
if fin:
    fj = drive.job(fin); rec['finish_job'] = {k: fj.get(k) for k in ('id', 'status', 'message', 'outputs', 'preset_id', 'operation', 'elapsed_seconds')}
json.dump(rec, open(OUT + 'tile-%s%s.json' % (label, '-band' + BAND if BAND else ''), 'w'), indent=1)
print('DONE', jid, j['status'], j['prompt_ids'], round(st.get('elapsed_seconds') or 0, 1), 'tile_finish', json.dumps(j.get('tile_finish'))[:400])
