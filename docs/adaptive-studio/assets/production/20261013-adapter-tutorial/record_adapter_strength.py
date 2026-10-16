"""Record actual owned Studio UI; no mocks, installs, model runs or generation.

Requires an already-owned full server on loopback8191. --repo-root identifies its
checkout; --output preserves raw video, complete editable states and receipts.
"""
import argparse, hashlib, importlib.util, json, shutil, subprocess, time
from pathlib import Path
from playwright.sync_api import sync_playwright

parser=argparse.ArgumentParser()
parser.add_argument('--repo-root',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();repo=args.repo_root.resolve();out=args.output.resolve()
out.mkdir(parents=True,exist_ok=True)
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
assert not subprocess.check_output(['git','diff','HEAD','--','app','presets','workflows','models/library.json'],cwd=repo,text=True)
recipe_id='yumeflux-ilv1-adapter-audition';base='http://127.0.0.1:8191'
recipe=next(r for r in json.loads((repo/'presets/recipes.json').read_text())['recipes'] if r['id']==recipe_id)
audit=[];errors=[];failed=[];events=[]
with sync_playwright() as pw:
    browser=pw.chromium.launch()
    context=browser.new_context(viewport={'width':1280,'height':720},record_video_dir=str(out/'raw'),record_video_size={'width':1280,'height':720})
    page=context.new_page();video_origin=time.monotonic()
    page.on('request',lambda r:audit.append({'method':r.method,'path':r.url.replace(base,'')}))
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('requestfailed',lambda r:failed.append({'path':r.url.replace(base,''),'failure':r.failure}))
    page.goto(base,wait_until='networkidle')
    assert context.request.get(base+'/api/jobs').json()==[]
    def state():
        return page.evaluate('''()=>({preset:selected.id,controls:values(),batch:document.querySelector('#batch').value,references:referenceRecords,parents:parentAssets})''')
    def open_recipe():
        page.locator('[data-studio-route="home"]').click()
        page.get_by_role('button',name='Explore creative bundles',exact=False).click()
        page.locator('#bundleSearch').fill('first adapter audition')
        page.locator('[data-bundle="'+recipe_id+'"]').click()
        page.wait_for_timeout(1500)
        page.locator('#bundleIngredients dd').filter(has_text='nsfw_girls.safetensors').wait_for()
    open_recipe()
    authored_fields={key:page.locator('[data-bundle-control="'+key+'"]').input_value() for key in ('lora','lora2')}
    assert float(authored_fields['lora'])==1 and float(authored_fields['lora2'])==0
    page.locator('#bundleConsent').check();page.locator('#bundleApply').click()
    page.wait_for_function("!document.querySelector('#bundleExplorer').open")
    before=state();assert before['preset']=='yumeflux-ilv1-baseline'
    assert float(before['controls']['lora'])==1 and float(before['controls']['lora2'])==0,before
    assert str(before['batch'])=='1'
    page.get_by_text('Full editor — every setting for one recipe',exact=True).scroll_into_view_if_needed()
    assert page.get_by_text('Readiness unavailable',exact=True).is_visible()
    start=time.monotonic()
    def mark(action,shot,hold):
        events.append({'seconds':round(time.monotonic()-start,3),'action':action,'screenshot':shot+'.png'})
        page.screenshot(path=str(out/(shot+'.png')))
        page.wait_for_timeout(hold*1000)
    mark('Actual isolated Studio; authored1.0/0.0; readiness unavailable','01-context',3)
    open_recipe()
    ingredient_text=page.locator('#bundleIngredients').inner_text()
    page.locator('#bundleIngredients').scroll_into_view_if_needed()
    mark('Inspect authored checkpoint and both adapter files; installed bytes not verified','02-stack',4)
    detail=page.locator('#bundleBody details').filter(has=page.get_by_text('What do the adapters do?',exact=True))
    if not detail.evaluate('(e)=>e.open'):detail.locator(':scope > summary').click()
    detail.scroll_into_view_if_needed()
    adapter_text=detail.inner_text()
    mark('Read stored slot notes; slot1 strength1.0, slot2 off','03-notes',4)
    page.locator('#bundleClose').click();page.locator('[data-studio-route="create"]').click()
    # Open only existing controls; no DOM/CSS/UI mutation or patched handlers.
    first=page.locator('[data-key="lora"]')
    if not first.is_visible():
        page.get_by_text('Fine-tune the recipe',exact=True).click()
    first.scroll_into_view_if_needed()
    assert first.is_visible()
    assert page.locator('[data-key="lora2"]').input_value() in ('0','0.0')
    mark('Return to the live editable workbench; strengths1.0 and0','04-before',4)
    first.fill('0.8');first.press('Tab')
    after=state()
    changed=[key for key in before['controls'] if before['controls'][key]!=after['controls'][key]]
    assert changed==['lora'],changed
    assert float(after['controls']['lora'])==0.8 and float(after['controls']['lora2'])==0
    assert {k:v for k,v in before.items() if k!='controls'}=={k:v for k,v in after.items() if k!='controls'}
    mark('Edit slot1 to0.8; slot2 and every other value remain unchanged','05-edited',4)
    page.locator('[data-key="lora2"]').focus()
    mark('Inspect slot2 at0; this is an editable draft, not effect evidence','06-slot-two',3)
    page.get_by_text('Full editor — every setting for one recipe',exact=True).scroll_into_view_if_needed()
    mark('Readiness remains unavailable; no generation submitted','07-no-run',3)
    duration=time.monotonic()-start
    jobs=context.request.get(base+'/api/jobs').json();assert jobs==[]
    production=context.request.get(base+'/api/production').json()
    identity=context.request.get(base+'/api/identity').json();assert identity['app']=='local-asset-studio'
    (out/'browser-storage.json').write_text(json.dumps(context.storage_state(),indent=2),encoding='utf-8')
    video=page.video;context.close();raw=Path(video.path());browser.close()

assert not errors,errors
assert all(r['method'] in ('GET','HEAD') or r['path'] in ('/api/estimate','/api/workflow-studio/guidance') for r in audit),audit
receipt={'application_revision':revision,'application_source_unchanged':True,'runtime':'owned isolated full Studio; not installed product','recipe_id':recipe_id,
 'authored_recipe_controls':recipe['controls'],'authored_bundle_fields':authored_fields,'before':before,'after':after,'changed_control_keys':changed,
 'ingredient_text':ingredient_text,'adapter_notes_text':adapter_text,'events':events,'jobs_after':jobs,'production_after':production,
 'generation_executed':False,'adapter_effect_verified':False,'art_accepted':False,'installed_product_qualification':False,
 'readiness_ui':'Readiness unavailable','psutil_available':importlib.util.find_spec('psutil') is not None,
 'backend_launched':False,'disk_free_bytes':shutil.disk_usage(repo).free,'http_requests':audit,'browser_errors':errors,'failed_requests':failed,
 'raw_video':raw.relative_to(out).as_posix(),'trim_start_seconds':round(start-video_origin,3),'duration_seconds':round(duration,3),
 'catalog_sha256':hashlib.sha256((repo/'presets/catalog.json').read_bytes()).hexdigest(),'recipes_sha256':hashlib.sha256((repo/'presets/recipes.json').read_bytes()).hexdigest()}
(out/'recording-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:receipt[k] for k in ('application_revision','changed_control_keys','duration_seconds','trim_start_seconds','jobs_after','psutil_available')}))
