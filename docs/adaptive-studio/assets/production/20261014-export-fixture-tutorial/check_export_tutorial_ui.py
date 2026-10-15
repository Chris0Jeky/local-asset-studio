from pathlib import Path
import argparse, hashlib, json, zipfile
from playwright.sync_api import sync_playwright
p=argparse.ArgumentParser();p.add_argument('--tutorial-folder',type=Path,required=True);a=p.parse_args();out=a.tutorial_folder.resolve();receipt=json.loads((out/'recording-receipt.json').read_text());base='http://127.0.0.1:8191';checks=[]
with zipfile.ZipFile(out/'downloaded-native-source-pack.zip') as archive:atlas=json.loads(archive.read('atlas/manifest.json'));atlas_dimensions=atlas['dimensions']
with sync_playwright() as pw:
    browser=pw.chromium.launch()
    for width in [390,1440]:
        ctx=browser.new_context(viewport={'width':width,'height':1000},accept_downloads=True);page=ctx.new_page();errors=[];requests=[]
        page.on('pageerror',lambda error:errors.append(str(error)));page.on('request',lambda request:requests.append(dict(method=request.method,path=request.url.replace(base,''))))
        before_jobs=ctx.request.get(base+'/api/jobs').json();before_plans=ctx.request.get(base+'/api/production').json()
        def guard(route):
            request=route.request
            assert request.method=='GET' or request.url.startswith((base+'/api/estimate',base+'/api/guidance'))
            route.continue_()
        page.route(base+'/**',guard)
        page.goto(base+'/#production',wait_until='networkidle');page.locator('#planStatus').select_option('all')
        page.locator('[data-project="'+receipt['blocked_plan']['id']+'"]').click();page.locator('#productionDetail').scroll_into_view_if_needed()
        assert 'They are preserved' in page.locator('#productionDetail').inner_text();assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(out/f'actual-collision-{width}.png'),full_page=True)
        page.locator('[data-project="'+receipt['completed_plan']['id']+'"]').click();page.locator('#productionDetail').scroll_into_view_if_needed()
        assert 'Native export complete' in page.locator('#productionDetail').inner_text()
        image=page.get_by_alt_text('Sprite atlas',exact=True);image.scroll_into_view_if_needed();image.wait_for(state='visible');page.wait_for_function("dimensions=>{const image=document.querySelector('img[alt=\"Sprite atlas\"]');return image.complete&&image.naturalWidth===dimensions[0]&&image.naturalHeight===dimensions[1]}",arg=atlas_dimensions)
        page.screenshot(path=str(out/f'actual-completed-{width}.png'),full_page=True);image.screenshot(path=str(out/f'actual-atlas-{width}.png'))
        link=page.get_by_role('link',name='Download native source pack',exact=True);link.scroll_into_view_if_needed()
        with page.expect_download() as event:link.click()
        pack=out/f'phone-desktop-pack-{width}.zip';event.value.save_as(pack)
        assert hashlib.sha256(pack.read_bytes()).hexdigest()==receipt['downloaded_pack_sha256']
        assert before_jobs==ctx.request.get(base+'/api/jobs').json() and before_plans==ctx.request.get(base+'/api/production').json()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth') and not errors
        forbidden=[row for row in requests if row['method']!='GET' and not row['path'].startswith(('/api/estimate','/api/guidance'))];assert not forbidden
        checks.append(dict(width=width,actual_unpatched_app=True,collision_message_visible=True,atlas_dimensions=atlas_dimensions,logical_canvas=atlas['logical_canvas'],downloaded_pack_exact=True,jobs_and_plans_unchanged=True,no_overflow=True,browser_errors=errors,forbidden_requests=forbidden,physical_device=False));ctx.close()
    browser.close()
(out/'ACTUAL-UI-CHECKS.json').write_text(json.dumps(checks,indent=2)+'\n');print(json.dumps(checks))
