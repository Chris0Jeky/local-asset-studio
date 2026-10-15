from pathlib import Path
import argparse,json
from playwright.sync_api import sync_playwright
R=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path,default=R/'evidence/follow-on-20261014');p.add_argument('--tutorial-folder',type=Path);a=p.parse_args();E=a.evidence.resolve();E.mkdir(parents=True,exist_ok=True);tutorial=a.tutorial_folder.resolve() if a.tutorial_folder else E/'tutorial-recover';base='http://127.0.0.1:8191';identifier='controlled-recover-tutorial-20261014'
with sync_playwright() as pw:
 b=pw.chromium.launch();page=b.new_page(viewport={'width':390,'height':1000},accept_downloads=True);errors=[];requests=[]
 page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:requests.append(dict(method=r.method,path=r.url.replace(base,''))))
 before=page.request.get(base+'/api/jobs').json();page.goto(base+'/#create',wait_until='networkidle');page.locator('#jobProblems > summary').click();card=page.locator(f'[data-problem="{identifier}"]');page.mouse.wheel(0,card.bounding_box()['y']-85);page.wait_for_timeout(300)
 assert 'CONTROLLED FIXTURE' in card.inner_text() and card.locator('.resume').count()==0 and card.locator('.stopTracking').count()==0
 assert not card.locator('[data-abandon-ack]').is_checked();assert page.locator('#generate').is_disabled();assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 page.screenshot(path=str(E/'recover-actual-ui-390.png'),full_page=True)
 card.get_by_role('button',name='Recipe',exact=True).scroll_into_view_if_needed()
 with page.expect_download() as event:card.get_by_role('button',name='Recipe',exact=True).click()
 path=E/'recover-phone-recipe.json';event.value.save_as(path)
 assert json.loads(path.read_text())==json.loads((tutorial/'asset-studio-recipe.json').read_text())
 assert before==page.request.get(base+'/api/jobs').json() and page.request.get(base+'/api/production').json()==[]
 forbidden=[r for r in requests if r['method']!='GET' and not r['path'].startswith(('/api/estimate','/api/guidance'))];assert not forbidden and not errors
 result=dict(width=390,actual_unpatched_app=True,clearly_labelled_fixture=True,recipe_download_exact=True,jobs_unchanged=True,production_empty=True,no_resume_or_tracking_controls=True,generate_disabled=True,no_overflow=True,page_errors=errors,forbidden_requests=forbidden,physical_phone=False)
 (E/'RECOVER-PHONE-CHECKS.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));b.close()
