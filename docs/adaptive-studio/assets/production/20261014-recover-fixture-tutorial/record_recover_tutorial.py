"""Actual unpatched app with clearly labelled public retained-state fixture."""
from pathlib import Path
import argparse,hashlib,json,subprocess,time
from playwright.sync_api import sync_playwright
p=argparse.ArgumentParser();p.add_argument('--repo-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
repo=a.repo_root.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);base='http://127.0.0.1:8191';identifier='controlled-recover-tutorial-20261014'
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip();assert not subprocess.check_output(['git','diff','HEAD','--','app','presets','workflows','models'],cwd=repo,text=True)
audit=[];errors=[];failed=[];events=[];served=[]
with sync_playwright() as pw:
 b=pw.chromium.launch();ctx=b.new_context(viewport={'width':1280,'height':720},record_video_dir=str(out/'raw'),record_video_size={'width':1280,'height':720},accept_downloads=True)
 page=ctx.new_page();origin=time.monotonic()
 page.on('request',lambda r:audit.append(dict(method=r.method,path=r.url.replace(base,''))));page.on('pageerror',lambda e:errors.append(str(e)));page.on('requestfailed',lambda r:failed.append(dict(path=r.url.replace(base,''),failure=r.failure)))
 def guard(route):
  r=route.request
  if r.method!='GET' and not r.url.startswith((base+'/api/estimate',base+'/api/guidance')):route.abort();raise AssertionError('Forbidden mutation '+r.url)
  route.continue_()
 page.route(base+'/**',guard)
 page.goto(base+'/#create',wait_until='networkidle')
 for path in ['/app.js','/production.js','/studio-workbench.js','/continuation-core.js']:
  response=ctx.request.get(base+path);data=response.body();assert response.ok and data==(repo/'app/static'/path.lstrip('/')).read_bytes();served.append(dict(path=path,sha256=hashlib.sha256(data).hexdigest()))
 before=ctx.request.get(base+'/api/jobs').json();assert len(before)==1
 job=before[0];assert job['id']==identifier and job['status']=='uncertain' and job['has_pending_submission'] and not job['prompt_ids'] and not job['submissions'] and not job['outputs']
 assert 'CONTROLLED FIXTURE' in job['preset_name'] and 'no request was sent' in job['controls']['positive']
 assert ctx.request.get(base+'/api/production').json()==[]
 page.locator('#jobProblems > summary').click();card=page.locator(f'[data-problem="{identifier}"]');card.wait_for(state='visible')
 page.mouse.wheel(0,card.bounding_box()['y']-96);page.wait_for_timeout(300)
 assert card.locator('.resume').count()==0 and card.locator('.stopTracking').count()==0 and card.locator('.cancelJob').count()==0
 start=time.monotonic()
 def mark(caption,name,seconds):
  events.append(dict(seconds=round(time.monotonic()-start,3),caption=caption,screenshot=name+'.png'));page.screenshot(path=str(out/(name+'.png')));page.wait_for_timeout(seconds*1000)
 mark('CONTROLLED FIXTURE: no remote request was sent. This is a simulated retained unknown-request record.','01-fixture',6)
 mark('Read the uncertain status. The real app preserves uncertainty and says it was not resubmitted.','02-uncertain',5)
 assert not card.locator('[data-abandon-ack]').is_checked() and card.locator('[data-abandon-reason]').input_value()==''
 mark('No prompt ID is known, so Resume observation is absent. Leave Abandon and its acknowledgement untouched.','03-no-replay',6)
 with page.expect_download() as download_event:card.get_by_role('button',name='Recipe',exact=True).click()
 download=download_event.value;recipe_file=out/'asset-studio-recipe.json';download.save_as(recipe_file)
 recipe=json.loads(recipe_file.read_text());actual=ctx.request.get(base+'/api/jobs/'+identifier+'/recipe').json();assert recipe==actual and recipe['controls']==job['controls'] and recipe['submissions']==[] and recipe['outputs']==[]
 mark('Click Recipe to download the retained recipe. This is a read-only request, not a replay.','04-recipe-download',4)
 page.goto(recipe_file.as_uri(),wait_until='load')
 assert 'CONTROLLED FIXTURE' in page.locator('body').inner_text() and 'no request was sent' in page.locator('body').inner_text()
 mark('Inspect the downloaded JSON: the public fixture label, original controls and workflow are retained.','05-inspect-json',6)
 page.goto(base+'/#create',wait_until='networkidle');page.locator('#jobProblems > summary').click();card=page.locator(f'[data-problem="{identifier}"]');page.mouse.wheel(0,card.bounding_box()['y']-96);page.wait_for_timeout(300)
 after=ctx.request.get(base+'/api/jobs').json();assert before==after
 mark('Return to the unchanged uncertain record. Stop here: no Resume, Abandon, replay or generation.','06-preserve',5)
 duration=time.monotonic()-start;production=ctx.request.get(base+'/api/production').json();assert production==[]
 forbidden=[r for r in audit if r['method']!='GET' and not r['path'].startswith(('/api/estimate','/api/guidance'))];assert not forbidden and not errors,(forbidden,errors)
 (out/'browser-storage.json').write_text(json.dumps(ctx.storage_state(),indent=2)+'\n');raw=Path(page.video.path());ctx.close();b.close()
 receipt=dict(application_revision=revision,application_source_unpatched=True,served_source_hashes=served,server_launch_receipt='RECOVER-SERVER-LAUNCH.json',fixture_classification='CONTROLLED PUBLIC RETAINED-STATE FIXTURE; no real request/lost response/output',fixture_job_id=identifier,before=before,after=after,production_after=production,events=events,duration_seconds=round(duration,3),trim_start_seconds=round(start-origin,3),raw_video=raw.relative_to(out).as_posix(),downloaded_recipe_file=recipe_file.name,downloaded_recipe_sha256=hashlib.sha256(recipe_file.read_bytes()).hexdigest(),recipe_download_is_read_only=True,no_observation_replay_or_abandon_clicked=True,http_requests=audit,forbidden_requests=forbidden,browser_errors=errors,expected_failed_requests=failed,generation_submitted=False)
 (out/'recording-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(dict(duration=duration,revision=revision,fixture=identifier,mutations=forbidden)))
