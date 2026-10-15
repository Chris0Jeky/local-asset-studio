"""Record real UI actions against an owned full Studio; no routes, handlers or state are mocked.

Requires an already running owned server at 127.0.0.1:8191. No generation is submitted.
Run with --output DIRECTORY. Keep the raw recording alongside the edited MP4.
"""
import argparse, hashlib, json, subprocess, time
from pathlib import Path
from playwright.sync_api import sync_playwright

parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
repo=Path(__file__).resolve().parents[5]
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
recipe_id='yumeflux-ilv1-base'
initial_prompt='An original brass lantern on a quiet workshop desk.'
audit=[];errors=[];events=[];screens=[]
with sync_playwright() as p:
    browser=p.chromium.launch()
    context=browser.new_context(viewport={'width':1280,'height':720},record_video_dir=str(out/'raw'),record_video_size={'width':1280,'height':720})
    page=context.new_page();video_origin=time.monotonic()
    page.on('request',lambda r:audit.append({'method':r.method,'path':r.url.replace('http://127.0.0.1:8191','')}))
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8191',wait_until='networkidle')
    page.locator('[data-studio-route="create"]').click()
    page.locator('#positive').fill(initial_prompt)
    page.locator('#positive').press('Tab')
    page.locator('#positive').scroll_into_view_if_needed()
    def state():
        return page.evaluate('''()=>({preset:selected.id,controls:values(),batch:document.querySelector('#batch').value,references:referenceRecords,parents:parentAssets})''')
    initial=state();start=time.monotonic()
    def mark(label,shot=None,hold=0):
        events.append({'seconds':round(time.monotonic()-start,3),'action':label})
        if shot:
            page.screenshot(path=str(out/(shot+'.png')));screens.append(shot+'.png')
        if hold:page.wait_for_timeout(hold*1000)
    def open_review():
        page.locator('[data-studio-route="home"]').click()
        page.get_by_role('button',name='Explore creative bundles',exact=False).click()
        page.locator('#bundleSearch').fill('uncluttered baseline')
        page.locator('[data-bundle="'+recipe_id+'"]').click()
        page.wait_for_timeout(1500)  # Real async resource inspection redraws the review.
        page.locator('#bundleDiff details').first.wait_for()
        diff=page.locator('#bundleDiff details').first
        if not diff.evaluate('(el)=>el.open'):diff.locator('summary').click()
        diff.scroll_into_view_if_needed()
    mark('Initial editable draft; readiness unavailable; no generation', '01-initial',4)
    open_review();mark('Review authored replacement and workbench differences','02-review',5)
    page.locator('#bundleClose').click()
    page.locator('[data-studio-route="create"]').click()
    cancelled=state();assert cancelled==initial,'Cancel changed the active draft'
    page.locator('#positive').scroll_into_view_if_needed()
    mark('Cancel preserves the complete active draft','03-cancel-preserved',4)
    open_review();mark('Reopen the same replacement for a fresh review','04-review-again',4)
    page.locator('#bundleConsent').scroll_into_view_if_needed()
    page.locator('#bundleConsent').check()
    page.locator('#bundleApply').focus()
    mark('Explicit replacement consent; Apply focused','05-consent',3)
    page.locator('#bundleApply').press('Enter')
    page.wait_for_function("!document.querySelector('#bundleExplorer').open")
    applied=state();assert applied['preset']=='yumeflux-ilv1-baseline'
    assert applied['controls']['positive']!=initial_prompt
    assert str(applied['batch'])=='1'
    mark('Replacement applied as editable setup; Generate remains separate','06-applied',5)
    finish=time.monotonic()
    jobs=context.request.get('http://127.0.0.1:8191/api/jobs').json();assert jobs==[]
    identity=context.request.get('http://127.0.0.1:8191/api/identity').json()
    # Preserve browser draft source explicitly, rather than claiming a saved workspace setup.
    storage=context.storage_state();(out/'browser-storage.json').write_text(json.dumps(storage,indent=2),encoding='utf-8')
    video=page.video
    context.close();raw=Path(video.path());browser.close()
    browser=p.chromium.launch();phone=browser.new_page(viewport={'width':390,'height':844})
    phone.goto('http://127.0.0.1:8191/#create',wait_until='networkidle')
    phone.locator('#positive').fill(initial_prompt)
    phone.screenshot(path=str(out/'phone-real-create.png'))
    browser.close()
(out/'http-audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
assert not [r for r in audit if r['method'] not in ('GET','HEAD') and r['path'] not in ('/api/estimate','/api/workflow-studio/guidance')],'Unexpected execution or mutation request'
receipt={'application_revision':revision,'runtime':'owned isolated full application; not installed product',
         'generation_executed':False,'art_accepted':False,'models_available':False,
         'health_limitation':'Python 3.13 lacks psutil; /api/health closes response; UI says Readiness unavailable',
         'recipe_id':recipe_id,'initial':initial,'after_cancel':cancelled,'after_apply':applied,
         'jobs_after':jobs,'identity_app':identity['app'],'browser_errors':errors,
         'http_requests':audit,'events':events,'screenshots':screens+['phone-real-create.png'],
         'raw_video':str(raw.relative_to(out)).replace('\\','/'),
         'trim_start_seconds':round(start-video_origin,3),'duration_seconds':round(finish-start,3),
         'catalog_sha256':hashlib.sha256((repo/'presets/catalog.json').read_bytes()).hexdigest(),
         'recipes_sha256':hashlib.sha256((repo/'presets/recipes.json').read_bytes()).hexdigest()}
(out/'recording-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps({k:receipt[k] for k in ('application_revision','duration_seconds','trim_start_seconds','raw_video','jobs_after')}))
