"""Record actual imports and native exports; the collision is explicitly controlled."""
from pathlib import Path
import argparse, hashlib, json, re, subprocess, time, zipfile
from playwright.sync_api import sync_playwright

p=argparse.ArgumentParser();p.add_argument('--repo-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
repo=a.repo_root.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
parent=out.parent;inputs=parent/'public-inputs';preflight=json.loads((parent/'PREFLIGHT.json').read_text());base='http://127.0.0.1:8191'
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
assert not subprocess.check_output(['git','diff','HEAD','--','app','presets','workflows','models'],cwd=repo,text=True)
config=json.loads((repo/'config/local.json').read_text(encoding='utf-8-sig'));projects=(Path(config['experiments_root'])/'projects').resolve();assert projects.is_relative_to(repo)
audit=[];errors=[];events=[];allowed_plans=set();responses=[]
with sync_playwright() as pw:
    browser=pw.chromium.launch();ctx=browser.new_context(viewport={'width':1280,'height':720},record_video_dir=str(out/'raw'),record_video_size={'width':1280,'height':720},accept_downloads=True)
    page=ctx.new_page();page.set_default_timeout(15000);origin=time.monotonic()
    page.on('request',lambda request:audit.append(dict(method=request.method,path=request.url.replace(base,''),body=request.post_data if request.method=='POST' and request.headers.get('content-type','').startswith('application/json') else None)))
    page.on('pageerror',lambda error:errors.append(str(error)))
    def permitted(request):
        path=request.url.replace(base,'')
        if request.method=='GET':return True
        if path.startswith(('/api/estimate','/api/guidance')):return True
        if path in ('/api/assets/import','/api/production-export'):return True
        match=re.fullmatch(r'/api/production/([0-9a-f]{32})/start',path)
        return bool(match and match[1] in allowed_plans)
    def guard(route):
        assert permitted(route.request),'Forbidden operation: '+route.request.url
        route.continue_()
    page.route(base+'/**',guard)
    page.goto(base+'/#assets',wait_until='networkidle')
    before_jobs=ctx.request.get(base+'/api/jobs').json();before_plans=ctx.request.get(base+'/api/production').json();assert before_jobs==[] and before_plans==[]
    start=time.monotonic()
    def mark(caption,name,seconds=5):
        events.append(dict(seconds=round(time.monotonic()-start,3),caption=caption,screenshot=name+'.png'));page.screenshot(path=str(out/(name+'.png')));page.wait_for_timeout(seconds*1000)
    mark('CONTROLLED PUBLIC FIXTURE: import existing Alibi paintings. No image generation or native-editor launch.','01-public-inputs')
    page.locator('#importAssets').set_input_files([str(inputs/row['imported_filename']) for row in preflight['inputs']])
    page.wait_for_function("document.querySelector('#assetMessage').textContent.startsWith('Imported 2 originals')")
    imported_jobs=ctx.request.get(base+'/api/jobs').json();assets=ctx.request.get(base+'/api/workspace').json()['assets']
    assert len(imported_jobs)==2 and all(job['preset_id']=='imported-image' and job['status']=='completed' and not job['prompt_ids'] and not job['submissions'] for job in imported_jobs)
    assert {asset['sha256'] for asset in assets}=={row['sha256'] for row in preflight['inputs']}
    imported_state=json.loads(json.dumps(imported_jobs))
    mark('Two public originals are genuinely imported and selected. Their hashes match the existing source derivatives.','02-imported')
    def prepare(clip):
        page.locator('#nativeExport').click();page.locator('#nativeKind').select_option('atlas');page.locator('#nativeClip').fill(clip)
        with page.expect_response(lambda response:response.url==base+'/api/production-export' and response.request.method=='POST') as response_event:
            page.locator('#prepareNative').click()
        response=response_event.value;assert response.status==201;summary=response.json();full_response=ctx.request.get(base+'/api/production/'+summary['id']+'/files/plan.json');assert full_response.ok;plan={**full_response.json(),'id':summary['id'],'state':summary['state']};assert plan['kind']=='native' and plan['export_kind']=='atlas' and plan['source_assets']
        assert not plan['verify_engine'] and not plan['verify_krita'];allowed_plans.add(plan['id']);responses.append(dict(path='/api/production-export',status=response.status,plan=plan))
        page.locator('#productionView').wait_for(state='visible');page.locator('#productionDetail [data-project-action="start"]').wait_for(state='visible');page.locator('#productionDetail').scroll_into_view_if_needed()
        return plan
    blocked=prepare('controlled-public-collision-fixture');blocked_id=blocked['id'];assert re.fullmatch('[0-9a-f]{32}',blocked_id)
    mark('Prepare a sprite-atlas export. Start is separate, and the plan pins these imported source files.','03-prepare')
    destination=projects/blocked_id/'native';assert not destination.exists();destination.mkdir();sentinel=destination/'CONTROLLED-PREEXISTING-FILE.txt'
    sentinel.write_text('CONTROLLED COLLISION FIXTURE\nExisting run-owned bytes must survive. No earlier export actually failed here.\n')
    sentinel_before=hashlib.sha256(sentinel.read_bytes()).hexdigest()
    page.goto(sentinel.as_uri(),wait_until='load');assert 'CONTROLLED COLLISION FIXTURE' in page.locator('body').inner_text()
    mark('Preview the actual file already in this run-owned export destination. It is a deliberately seeded collision fixture.','04-owned-destination',6)
    page.goto(base+'/#production',wait_until='networkidle');page.locator(f'[data-project="{blocked_id}"]').click()
    with page.expect_response(lambda response:response.url==base+'/api/production/'+blocked_id+'/start') as response_event:
        page.locator('#productionDetail [data-project-action="start"]').click()
    assert response_event.value.status==202
    page.wait_for_function("id=>productionPlans.some(p=>p.id===id&&p.state.status==='interrupted')",arg=blocked_id)
    blocked_after=ctx.request.get(base+'/api/production/'+blocked_id).json();assert blocked_after['state']['status']=='interrupted' and not blocked_after['state']['attempts'] and blocked_after['state']['artifacts']==[]
    assert sentinel_before==hashlib.sha256(sentinel.read_bytes()).hexdigest() and [path.name for path in destination.iterdir()]==[sentinel.name]
    assert 'They are preserved' in page.locator('#productionDetail').inner_text()
    mark('Start refuses the existing destination and preserves its bytes. This is the real app response to the controlled fixture.','05-collision-preserved',6)
    page.locator('[data-studio-route="assets"]').click();page.locator('#selectVisibleAssets').click() if page.locator('#selectVisibleAssets').count() else None
    # On a page reload selection is empty; select only these two existing imported originals.
    if not page.locator('#nativeExport').is_visible():
        page.get_by_role('button',name='Select visible',exact=True).click()
    fresh=prepare('controlled-public-fresh-export');fresh_id=fresh['id'];fresh_destination=projects/fresh_id/'native';assert not fresh_destination.exists()
    mark('Keep the blocked plan intact. Prepare a fresh export in a new run-owned directory; no cleanup or overwrite is needed.','06-fresh-plan',6)
    with page.expect_response(lambda response:response.url==base+'/api/production/'+fresh_id+'/start') as response_event:
        page.locator('#productionDetail [data-project-action="start"]').click()
    assert response_event.value.status==202
    page.wait_for_function("id=>productionPlans.some(p=>p.id===id&&p.state.status==='completed')",arg=fresh_id,timeout=30000)
    completed=ctx.request.get(base+'/api/production/'+fresh_id).json();assert completed['state']['status']=='completed'
    assert completed['state']['measurements']['image_count']==2 and completed['state']['measurements']['canvas']==[320,292]
    assert not completed['state'].get('engine') and not completed['state'].get('krita')
    mark('The fresh native export completes: two 320 × 292 originals are packed without resizing or generation.','07-completed',6)
    with page.expect_download() as download_event:page.get_by_role('link',name='Download native source pack',exact=True).click()
    pack=out/'downloaded-native-source-pack.zip';download_event.value.save_as(pack)
    assert pack.read_bytes()==(projects/fresh_id/'export.zip').read_bytes()
    with zipfile.ZipFile(pack) as archive:
        assert archive.testzip() is None
        files=archive.namelist();assert 'studio-plan.json' in files and 'atlas/atlas.png' in files
        source_hashes={hashlib.sha256(archive.read(name)).hexdigest() for name in files if name.startswith('sources/')}
        assert source_hashes=={row['sha256'] for row in preflight['inputs']}
    page.locator('#productionDetail').get_by_text('Files & provenance',exact=False).click()
    mark('Download and inspect the real pack and its file paths. Original hashes and the collision sentinel remain unchanged.','08-download',6)
    duration=time.monotonic()-start;after_jobs=ctx.request.get(base+'/api/jobs').json();assert after_jobs==imported_state and sentinel_before==hashlib.sha256(sentinel.read_bytes()).hexdigest()
    forbidden=[row for row in audit if row['method']!='GET' and not (row['path'].startswith(('/api/estimate','/api/guidance')) or row['path'] in ('/api/assets/import','/api/production-export') or re.fullmatch(r'/api/production/('+ '|'.join(allowed_plans)+')/start',row['path']))]
    assert not forbidden and not errors
    raw=Path(page.video.path());ctx.close();browser.close()
receipt=dict(application_revision=revision,application_source_unpatched=True,fixture_classification='CONTROLLED PUBLIC IMPORT AND DESTINATION-COLLISION FIXTURE; no generated output or actual prior failed export',input_provenance=preflight['inputs'],before_jobs=before_jobs,imported_jobs=imported_state,after_jobs=after_jobs,before_plans=before_plans,blocked_plan=blocked_after,completed_plan=completed,collision_destination=str(destination),fresh_destination=str(fresh_destination),collision_sentinel_sha256=sentinel_before,collision_sentinel_unchanged=True,downloaded_pack_sha256=hashlib.sha256(pack.read_bytes()).hexdigest(),downloaded_pack_bytes=pack.stat().st_size,downloaded_pack_members=files,events=events,duration_seconds=round(duration,3),trim_start_seconds=round(start-origin,3),raw_video=raw.relative_to(out).as_posix(),http_requests=audit,forbidden_requests=forbidden,browser_errors=errors,generation_submitted=False,native_editor_launched=False,accepted_art_unchanged=True)
(out/'recording-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(dict(duration=duration,revision=revision,blocked_plan=blocked_id,completed_plan=fresh_id,mutations=len([row for row in audit if row['method']!='GET']))))
