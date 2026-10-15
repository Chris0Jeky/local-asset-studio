"""Actual imported-original character + picture-compatible Copy Pose preparation. Never Generate."""
from pathlib import Path
import argparse,hashlib,json,subprocess,time
from playwright.sync_api import sync_playwright
p=argparse.ArgumentParser();p.add_argument('--repo-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();repo=a.repo_root.resolve();O=a.output.resolve();O.mkdir(parents=True,exist_ok=False);E=Path(__file__).resolve().parents[1]/'evidence/continuation-20261014'
source=json.loads((E/'POSE-IMPORT-RECEIPT.json').read_text(encoding='utf-8-sig'))['asset'];inputs=json.loads((E/'public-inputs/PROVENANCE.json').read_text());revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip();base='http://127.0.0.1:8191';requests=[];errors=[];failed=[];events=[]
assert source['preset_id']=='imported-image' and source['sha256']==inputs[0]['sha256']
with sync_playwright() as pw:
 b=pw.chromium.launch();ctx=b.new_context(viewport={'width':1280,'height':720},record_video_dir=str(O/'raw'),record_video_size={'width':1280,'height':720});page=ctx.new_page();origin=time.monotonic()
 page.on('request',lambda r:requests.append(dict(method=r.method,path=r.url.replace(base,''))))
 page.on('pageerror',lambda e:errors.append(str(e)));page.on('requestfailed',lambda r:failed.append(dict(path=r.url.replace(base,''),failure=r.failure)))
 page.goto(base,wait_until='networkidle');jobs_before=ctx.request.get(base+'/api/jobs').json();assert len(jobs_before)==1 and jobs_before[0]['preset_id']=='imported-image' and not jobs_before[0]['prompt_ids']
 def state():return page.evaluate('()=>({preset:selected.id,controls:values(),batch:document.querySelector("#batch").value,refs:referenceRecords,uploaded,lastUploaded,parents:parentAssets,continuation:continuationState})')
 before=state();page.locator('[data-studio-route="assets"]').click();page.locator('[data-asset-open="'+source['id']+'"]').first.click();page.locator('#assetDialog').wait_for(state='visible')
 start=time.monotonic()
 def mark(caption,name,hold):
  events.append(dict(seconds=round(time.monotonic()-start,3),caption=caption,screenshot=name+'.png'));page.screenshot(path=str(O/(name+'.png')));page.wait_for_timeout(hold*1000)
 mark('Choose the original teaching character in Asset library. It is an imported diagram, not a generated output.','01-source',4)
 page.locator('[data-ux-handoff="'+source['id']+'"]').click();page.locator('#uxHandoff').wait_for(state='visible');page.locator('[data-ux-destination="combine"]').click();page.locator('#uxDestination').select_option('combine-klein-9b-copypose');page.wait_for_function('!document.querySelector("#uxPrepareHandoff").disabled')
 guidance=page.locator('#uxHandoffDetails').inner_text();assert 'image 1' in guidance and 'image 2' in guidance and 'real picture' in guidance
 page.locator('#uxDestination').scroll_into_view_if_needed();mark('Choose Combine and the picture-compatible Copy Pose recipe. No skeleton or depth-map route is used.','02-route',4)
 page.locator('#uxHandoffDetails').scroll_into_view_if_needed();mark('Read the actual roles: keep the character as image 1; the pose-board picture becomes image 2.','03-guidance',5)
 page.locator('#uxPrepareHandoff').click();page.wait_for_function('!document.querySelector("#uxHandoff").open');assert page.evaluate('selected.id')=='combine-klein-9b-copypose'
 page.locator('[data-ref-file="0"]').set_input_files(str(E/'public-inputs/tutorial-pose.png'));page.wait_for_function('(sha)=>referenceRecords[0]?.sha256===sha',arg=inputs[1]['sha256'])
 page.locator('#referenceCards').scroll_into_view_if_needed();mark('Attach the original pose diagram to the pose board. The character stays in Picture to keep.','04-pose',5)
 fills=page.locator('#uxFills [data-ux-fill]');assert fills.count()==3
 answers=['an original adult cartographer with short dark hair and round glasses','a long sage coat with brass trim, dark petrol trousers and dark shoes','knees bent, right arm raised above the head, left arm bent outward, front camera, full body']
 for field,value in zip(fills.all(),answers):field.fill(value)
 fills.last.press('Tab');page.locator('#uxFills').evaluate('(e)=>e.scrollIntoView({block:"center"})');mark('Describe who to keep, their clothes and colours, and the target pose. These fields write an editable instruction.','05-wording',5)
 page.locator('#lastReferenceWrap').evaluate('(e)=>e.scrollIntoView({block:"center"})');mark('Review the board count and Picture to keep. These inputs only prepare a pair; no pose-transfer quality is proved.','06-pair',4)
 page.get_by_role('button',name='Review checks',exact=True).click();page.get_by_text('ComfyUI readiness is not yet confirmed.',exact=False).first.wait_for(state='visible');mark('Read the actual readiness warning. Stop without Generate; the backend remains unavailable.','07-readiness',4)
 after=state();assert after['preset']=='combine-klein-9b-copypose' and after['parents']==[source['id']] and after['continuation']['source_sha256']==source['sha256']
 assert after['refs'][0]['sha256']==inputs[1]['sha256'] and after['refs'][0]['role']=='pose'
 assert all(answer in after['controls']['positive'] for answer in answers)
 assert page.locator('#generate').is_disabled()
 assert page.get_by_role('button',name='Combine pictures',exact=False).is_disabled()
 jobs_after=ctx.request.get(base+'/api/jobs').json();assert jobs_before==jobs_after
 production=ctx.request.get(base+'/api/production').json();assert production==[]
 allowed=['/api/estimate','/api/guidance','/api/assets/reference','/api/upload'];forbidden=[r for r in requests if r['method']!='GET' and not any(r['path'].startswith(s) for s in allowed)]
 assert not forbidden and not errors
 ready=page.get_by_text('ComfyUI readiness is not yet confirmed.',exact=False).first.inner_text();blockers=page.locator('.dependencies').inner_text();assert ready and 'ComfyUI' in ready;storage=ctx.storage_state();raw=Path(page.video.path());duration=time.monotonic()-start
 (O/'browser-storage.json').write_text(json.dumps(storage,indent=2)+'\n');ctx.close();b.close()
receipt=dict(application_revision=revision,recipe_id=after['preset'],source_import=source,input_provenance=inputs,guidance=guidance,before=before,after=after,readiness=ready,blockers=blockers,events=events,duration_seconds=round(duration,3),trim_start_seconds=round(start-origin,3),raw_video=raw.relative_to(O).as_posix(),http_requests=requests,forbidden_requests=forbidden,browser_errors=errors,expected_failed_requests=failed,jobs_before=jobs_before,jobs_after=jobs_after,production_after=production,generation_submitted=False,import_is_generated=False)
(O/'recording-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(dict(duration=duration,recipe=after['preset'],readiness=ready,generation_submitted=False)))
