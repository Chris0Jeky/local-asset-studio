"""Actual unpatched Studio planner; deliberately stops before Prepare plan."""
from pathlib import Path
import argparse,hashlib,json,subprocess,time
from playwright.sync_api import sync_playwright
p=argparse.ArgumentParser();p.add_argument('--repo-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
repo=a.repo_root.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
assert not subprocess.check_output(['git','diff','HEAD','--','app','presets','workflows','models'],cwd=repo,text=True)
base='http://127.0.0.1:8191';audit=[];errors=[];failed=[];events=[];served=[]
with sync_playwright() as pw:
 b=pw.chromium.launch();ctx=b.new_context(viewport={'width':1280,'height':720},record_video_dir=str(out/'raw'),record_video_size={'width':1280,'height':720})
 page=ctx.new_page();origin=time.monotonic()
 page.on('request',lambda r:audit.append(dict(method=r.method,path=r.url.replace(base,''))))
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.on('requestfailed',lambda r:failed.append(dict(path=r.url.replace(base,''),failure=r.failure)))
 page.goto(base,wait_until='networkidle')
 for response_path in ['/app.js','/production.js','/studio-workbench.js','/continuation-core.js']:
  response=ctx.request.get(base+response_path);data=response.body();source=repo/'app/static'/response_path.lstrip('/')
  assert response.ok and data==source.read_bytes(),response_path
  served.append(dict(path=response_path,sha256=hashlib.sha256(data).hexdigest()))
 def state():return page.evaluate('()=>({preset:selected.id,controls:values(),batch:document.querySelector("#batch").value,refs:referenceRecords,parents:parentAssets,files:Array.from(document.querySelectorAll("input[type=file]")).map(e=>({id:e.id,count:e.files.length}))})')
 assert ctx.request.get(base+'/api/jobs').json()==[]
 assert ctx.request.get(base+'/api/production').ok
 page.locator('[data-studio-route="create"]').click()
 page.locator('#positive').fill('An original fully clothed adult cartographer in a warm ivory coat, holding a folded map in a quiet workshop. Calm daylight, clean composition.')
 page.locator('#positive').press('Tab');before=state()
 assert before['preset']=='anima-portrait' and all(x['count']==0 for x in before['files']) and not before['refs'] and not before['parents']
 start=time.monotonic()
 def mark(caption,name,seconds):
  events.append(dict(seconds=round(time.monotonic()-start,3),caption=caption,screenshot=name+'.png'))
  page.screenshot(path=str(out/(name+'.png')));page.wait_for_timeout(seconds*1000)
 page.locator('#selectedPreset').scroll_into_view_if_needed()
 mark('Start with one text-only recipe and one question. No references are attached.','01-recipe',4)
 page.locator('#planComparison').click();page.locator('#experimentDialog').wait_for(state='visible')
 options=page.locator('#experimentAxis option').evaluate_all('(es)=>es.map(e=>({value:e.value,text:e.textContent}))')
 assert any(o['value']=='cfg' for o in options),options
 page.locator('#experimentAxis').select_option('cfg')
 mark('Open Plan comparison and choose Guidance. Compare one setting at a time.','02-axis',5)
 page.locator('#experimentValues').fill('3, 4, 5');page.locator('#experimentBudget').fill('3');page.locator('#experimentMinutes').fill('10');page.locator('#experimentMinutes').press('Tab')
 mark('Enter three values. Allow three graph runs and a ten-minute between-stage limit.','03-limits',6)
 summary=page.locator('#experimentSummary').inner_text();arithmetic=page.locator('#experimentBudgetNote').inner_text();status=page.locator('#experimentStatus').inner_text()
 assert '3 graph runs' in summary and '3 values' in arithmetic and '3 reserved' in arithmetic
 page.locator('#experimentSummary').scroll_into_view_if_needed()
 mark('Read the displayed estimate and run arithmetic before preparing. This is not a completed comparison.','04-summary',4)
 page.locator('#experimentBudgetNote').scroll_into_view_if_needed()
 mark('Three values times one seed means three graph runs. The allowance is three; nothing is reserved yet.','05-arithmetic',4)
 page.locator('#cancelExperiment').click();page.wait_for_function('!document.querySelector("#experimentDialog").open')
 after=state();assert before==after
 mark('Cancel before Prepare plan. The Create draft remains unchanged; nothing was prepared or submitted.','06-cancel',5)
 duration=time.monotonic()-start
 jobs=ctx.request.get(base+'/api/jobs').json();production=ctx.request.get(base+'/api/production').json()
 assert jobs==[] and production==[],production
 forbidden=[r for r in audit if r['method']!='GET' and not r['path'].startswith(('/api/estimate','/api/guidance'))]
 assert not forbidden and not errors,(forbidden,errors)
 storage=ctx.storage_state();(out/'browser-storage.json').write_text(json.dumps(storage,indent=2)+'\n')
 raw=Path(page.video.path());ctx.close();b.close()
receipt=dict(application_revision=revision,served_source_hashes=served,server_launch_receipt='LAS-SERVER-LAUNCH.json',recipe_id=before['preset'],before=before,after=after,axis_options=options,summary=summary,arithmetic=arithmetic,status=status,events=events,duration_seconds=round(duration,3),trim_start_seconds=round(start-origin,3),raw_video=raw.relative_to(out).as_posix(),jobs_after=jobs,production_after=production,http_requests=audit,forbidden_requests=forbidden,browser_errors=errors,expected_failed_requests=failed,prepare_plan_clicked=False,generation_submitted=False)
(out/'recording-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(dict(duration=duration,summary=summary,arithmetic=arithmetic,revision=revision)))
