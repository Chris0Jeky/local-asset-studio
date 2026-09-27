# As-run script (27 Sep 2026), kept as a receipt; hardcodes local paths and is not a portable reproduction.
"""#1202 Vary live proof (27 Sep 2026): on the real Studio page (headless Chromium), open a parent picture in the asset panel,
press Vary subtle or Vary strong, record what the page prepared, press Generate, and wait for the round. One round per call.
Usage: python vary_live.py <label> <asset_id> <search words> <subtle|strong>"""
import json, sys, time
sys.path.insert(0, 'C:/Users/jekyt/AppData/Local/Temp/cancel-proof-0927'); import drive
from playwright.sync_api import sync_playwright
OUT = 'C:/Users/jekyt/AppData/Local/Temp/liveproofs/'
label, asset, words, strength = sys.argv[1:5]
OVERRIDE = float(sys.argv[5]) if len(sys.argv) > 5 else None   # owner-approved value typed into the page's denoise field

def main():
    rec = {'label': label, 'parent_asset': asset, 'strength': strength, 'events': []}
    ev = lambda k, **kw: (rec['events'].append(dict(t=round(time.time(), 3), kind=k, **kw)), print(k, json.dumps(kw)[:300], flush=True))
    r, p = drive.queue(); assert not r and not p, 'ComfyUI queue busy'
    before = {j['id'] for j in drive.studio('/api/jobs')[1]}
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True); page = b.new_page(viewport={'width': 1440, 'height': 1000})
        errors, posts, dialogs = [], [], []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('request', lambda q: posts.append((round(time.time(), 3), q.url.replace(drive.S, ''))) if q.method == 'POST' else None)
        page.on('dialog', lambda d: (dialogs.append(d.message), d.accept()))
        page.goto(drive.S + '/#assets', wait_until='domcontentloaded'); page.wait_for_timeout(3000)
        page.select_option('#assetSource', 'all'); page.wait_for_timeout(800)   # agent-labelled runs are hidden by default ("Mine")
        page.locator('#assetSearch').click(); page.keyboard.type(words, delay=20); page.wait_for_timeout(1500)
        for _ in range(20):
            if page.locator('[data-asset-open="%s"]' % asset).count(): break
            more = page.locator('button:has-text("Show more"), button:has-text("more assets")')
            if not more.count(): break
            more.first.click(); page.wait_for_timeout(800)
        page.locator('[data-asset-open="%s"]' % asset).first.click(); page.wait_for_timeout(1500)
        btn = page.locator('#assetDialog .ux-vary [data-ux-vary="%s"]' % strength).first
        hint = page.locator('#assetDialog .ux-vary small').first.inner_text() if page.locator('#assetDialog .ux-vary small').count() else None
        ev('asset_opened', vary_buttons=page.locator('#assetDialog .ux-vary button').all_inner_texts(), hint=hint)
        btn.click(); page.wait_for_timeout(3000)
        status = page.locator('p#status').inner_text() if page.locator('p#status').count() else None
        prepared = page.evaluate("""() => ({preset: (document.querySelector('#preset')||{}).value || (window.selected && selected.id),
            batch: document.querySelector('#batch') && document.querySelector('#batch').value,
            denoise: (document.querySelector('[data-control="denoise"]')||document.querySelector('#denoise')||{}).value,
            positive: (document.querySelector('#positive')||{}).value, hash: location.hash})""")
        ev('vary_pressed', status=status, prepared=prepared, submitted_so_far=[x for x in posts if x[1].startswith('/api/jobs')])
        if OVERRIDE is not None:
            cid = page.evaluate("() => { const c = getControl('denoise'); return c && (c.id || null); }")
            before_val = page.evaluate("() => (getControl('denoise')||{}).value")
            if cid: page.locator('#' + cid).fill(str(OVERRIDE))
            else: page.evaluate("v => { const c = getControl('denoise'); c.value = v; c.dispatchEvent(new Event('input', {bubbles: true})); c.dispatchEvent(new Event('change', {bubbles: true})); }", str(OVERRIDE))
            page.wait_for_timeout(800)
            ev('denoise_override', control_id=cid, catalog_value=before_val, typed=OVERRIDE, now=page.evaluate("() => (getControl('denoise')||{}).value"),
               steps=page.evaluate("() => (getControl('steps')||{}).value"))
        page.screenshot(path=OUT + '%s-%s-prepared.png' % (label, strength))
        gen = page.locator('#generate'); ev('generate_state', disabled=gen.is_disabled(), text=gen.inner_text())
        c = drive.commit(); ev('commit_before_generate', **c)
        if c['pct'] >= 90: b.close(); raise SystemExit('ABORT before Generate: host commit %.1f %%' % c['pct'])
        gen.click(); page.wait_for_timeout(4000)
        new = [j for j in drive.studio('/api/jobs')[1] if j['id'] not in before]
        ev('generate_pressed', new_jobs=[(j['id'], j['preset_id'], j['batch_count'], j['status']) for j in new], job_posts=[x for x in posts if x[1] == '/api/jobs'])
        b.close()
    assert len(new) == 1, 'expected exactly one new job'
    jid = new[0]['id']
    while drive.job(jid)['status'] in drive.ACTIVE: time.sleep(3)
    j = drive.job(jid); st = json.load(open('C:/Users/jekyt/source/local-asset-studio/experiments/runs/%s/state.json' % jid, encoding='utf-8'))
    subs = [{k: v for k, v in s.items() if k != 'graph'} for s in st.get('submissions', [])]
    g0 = st['submissions'][0]['graph'] if st.get('submissions') else {}
    denoise = [n['inputs'].get('denoise') for n in g0.values() if isinstance(n, dict) and 'denoise' in n.get('inputs', {})]
    rec.update(job_id=jid, preset=j['preset_id'], status=j['status'], message=j['message'], batch_count=j['batch_count'], prompt_ids=j['prompt_ids'],
               outputs=[{k: o.get(k) for k in ('filename', 'subfolder', 'seed', 'prompt_id', 'asset_id')} for o in j['outputs']], submissions=subs,
               graph_denoise=denoise, parent_assets=st.get('parent_assets'), continuation=st.get('continuation'), controls=st.get('controls'),
               created_at=st['created_at'], started_at=st.get('started_at'), finished_at=st.get('finished_at'), elapsed_seconds=st.get('elapsed_seconds'),
               page_errors=errors, page_posts=posts, dialogs=dialogs)
    json.dump(rec, open(OUT + '%s-%s%s.json' % (label, strength, '-v2' if OVERRIDE is not None else ''), 'w'), indent=1)
    print('DONE', jid, j['status'], j['batch_count'], j['prompt_ids'], round(st.get('elapsed_seconds') or 0, 1), denoise[:1], st.get('parent_assets'))

main()
