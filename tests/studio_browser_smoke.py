"""Opt-in real-browser UX contract checks. Never contacts ComfyUI or starts a model.

python tests/studio_browser_smoke.py --screenshots /tmp/studio-ux
Requires Playwright and Chromium, outside the managed model environment.
The local fixture server serves real frontend files and explicitly synthetic API data.
"""
import argparse
import hashlib
import os
import shutil
import json
import mimetypes
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
import continuation
POSTS = []
FAIL_WORKSPACE = False
WORKSPACE_DELAY = 0
ONLINE = True
CATALOG = json.loads((ROOT / 'presets/catalog.json').read_text(encoding='utf-8'))
for preset in CATALOG['presets']:
    graph = json.loads((ROOT / preset['graph']).read_text(encoding='utf-8'))
    preset['defaults'] = {k: graph[str(v[0])]['inputs'].get(str(v[1]), '') for k, v in preset.items()
                          if isinstance(v, list) and len(v) == 2 and str(v[0]) in graph and isinstance(v[1], str)}
    preset['choices'] = {'sampler': ['euler', 'dpmpp_2m'], 'scheduler': ['normal', 'karras']}
    preset['continuation_capability'] = continuation.capability(preset, graph)
    preset['continuation_capability']['template_sha256'] = hashlib.sha256((ROOT / preset['graph']).read_bytes()).hexdigest()
ASSETS = []
for i, (title, file, review) in enumerate([
    ('Lantern · material study', 'examples/references/lantern-reference.png', 'unreviewed'),
    ('Forest · atmosphere', 'examples/lanternkeeper/forest-hero.png', 'selected'),
    ('128px · lantern concept', 'examples/gallery/pixel-lora-128.png', 'needs_work'),
    ('Sculpture · silhouette', 'examples/gallery/stylized-prop.png', 'unreviewed'),
    ('Pattern · colour study', 'examples/gallery/abstract.png', 'selected'),
    ('Imported JPEG · reference', 'examples/references/atelier-style-lab-foxes.jpg', 'unreviewed'),
]):
    ASSETS.append(dict(id=f'asset-{i}', title=title, filename=Path(file).name, media_type='image', review=review,
                       url='/'+file, created_at=1789228800-i*100, bytes=1024, sha256='a'*64, source={'seed':42},
                       preset_name='Synthetic UX fixture', job_id=None, notes='', lineage=[], collections=[],
                       favorite=False, tags=['fixture'], trashed_at=None, metadata_revision=0))
JOBS = [dict(id='fixture-job',preset_name='Lantern study · synthetic fixture',preset_id='anima-portrait',status='completed',message='Completed fixture, not a model run',controls={'positive':'Explore one form, then continue with a variation.','seed':42},outputs=[{'filename':'lantern.png','asset_id':'asset-0','media_type':'image','seed':42}]),
        dict(id='allocation-failure',preset_name='Krea 2 Anime Atelier',preset_id='krea-anime-atelier',status='failed',message='Generation failed: ComfyUI reported an execution error: KSampler: bad allocation',failure={'kind':'memory_allocation','title':'Memory allocation failed','summary':'ComfyUI could not allocate memory while running the workflow. This usually indicates GPU/VRAM pressure or a backend allocation problem, not an invalid prompt.','action':'Release or restart ComfyUI memory, then retry with a smaller resolution, batch, or fewer active LoRAs. The original prompt was not retried automatically.','node_type':'KSampler','exception_type':'RuntimeError','detail':'bad allocation'},controls={},prompt_ids=['fixture-prompt'],submissions=[{'prompt_id':'fixture-prompt','status':'failed'}],outputs=[])]
PLANS = [dict(id='a'*32, name='Lantern study · choose the finish', kind='comparison', state={'status':'awaiting_review','message':'Synthetic review fixture'}, stages=[], budget={'allowance':4,'reserved':3}, axis='seed', values=[]),
         dict(id='b'*32, name='Motion study · prepared, not started', kind='comparison', state={'status':'planned','message':'Synthetic planned fixture'}, stages=[], budget={'allowance':4,'reserved':0}, axis='seed', values=[])]

def source_context(asset):
    return {'version':1, 'asset_id':asset['id'], 'sha256':asset['sha256'], 'title':asset['title'],
            'preset_id':'anima-portrait', 'preset_name':'Synthetic UX fixture', 'job_id':'fixture-job',
            'prompt_id':'fixture-prompt', 'positive':'Explore one form, then continue with a variation.',
            'negative':'blur', 'prompt_origin':'submitted-output', 'prompt_role':'description',
            'warning':'', 'width':512, 'height':768}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def json(self, value, status=200):
        data=json.dumps(value).encode(); self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)

    def do_GET(self):
        path=urlsplit(self.path).path
        if path=='/static/vendor/model-viewer/model-viewer.min.js':
            self.send_response(200);self.send_header('Content-Type','text/javascript');self.end_headers();self.wfile.write(b'/* 3D renderer excluded from no-GPU UX fixture. */');return
        if path=='/api/workspace':
            if WORKSPACE_DELAY:time.sleep(WORKSPACE_DELAY)
            if FAIL_WORKSPACE:return self.json({'error':'Fixture workspace unavailable'},503)
        data={
            '/api/catalog':CATALOG, '/api/options':{'loras':[]}, '/api/knowledge':{}, '/api/recipes':{'recipes':[]},
            '/api/identity':{'workspace':'ux-test-workspace'}, '/api/setups':[], '/api/jobs':JOBS,
            '/api/workspace':{'assets':ASSETS,'collections':[]}, '/api/production':PLANS,
            '/api/health':{'online':ONLINE,'schema_available':ONLINE,'missing_models':{},'devices':[]},
            '/api/backends':{'active':'primary','busy':False,'operation':None,'profiles':[{'id':'primary','name':'Main library','active':True,'online':ONLINE,'installed':True}]},
            '/api/library':{'storage':{'free_bytes':100000000000,'total_bytes':200000000000,'reserve_bytes':20000000000},'assets':[],'folders':[],'inventory':[],'collections':[],'model_root':'Fixture path'},
            '/api/av':{'projects':[],'capabilities':{'render_ready':False}},
            '/api/voice-baseline':{'projects':[],'capabilities':{'configured':False}},
            '/api/prompt/profiles':json.loads((ROOT/'research/prompt-studio/profiles.json').read_text(encoding='utf-8')),
        }
        if path in data:return self.json(data[path])
        if path.startswith('/api/inspect/'):return self.json({'requirements':[],'nodes':[],'graph':{}})
        if path.startswith('/api/assets/') and path.endswith('/context'):
            asset_id=path.split('/')[3]; asset=next((a for a in ASSETS if a['id']==asset_id),None)
            return self.json(source_context(asset) if asset else {'error':'Fixture asset missing'},200 if asset else 404)
        if path.startswith('/api/assets/') and path.endswith('/file'):
            asset_id=path.split('/')[3]; asset=next((a for a in ASSETS if a['id']==asset_id),None)
            if not asset:return self.json({'error':'Fixture asset missing'},404)
            path=asset['url']
        if path.startswith('/api/image/'):path='/examples/references/lantern-reference.png'
        if path.startswith('/api/uploads/'):path='/examples/references/lantern-reference.png'
        if path.startswith('/api/examples/'):path='/examples/'+path.removeprefix('/api/examples/')
        file=ROOT/'app/static/index.html' if path=='/' else ROOT/path.lstrip('/') if path.startswith('/examples/') else ROOT/'app/static'/path.removeprefix('/static/').lstrip('/')
        if not file.is_file():return self.json({'error':'Fixture route not found: '+path},404)
        raw=file.read_bytes(); self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(file)[0] or 'application/octet-stream');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)

    def do_POST(self):
        raw=self.rfile.read(int(self.headers.get('Content-Length','0')))
        data=json.loads(raw) if self.headers.get('Content-Type')=='application/json' else {}
        POSTS.append({'path':self.path,'data':data})
        if self.path=='/api/assets/reference':
            asset=next(a for a in ASSETS if a['id']==data['id'])
            return self.json({'file':'a'*32+'_fixture.png','sha256':asset['sha256'],'width':512,'height':768,
                              'parent_asset':asset['id'],'context':source_context(asset)})
        if self.path=='/api/estimate':return self.json({'available':True,'estimate_seconds':42,'range_seconds':[30,55],'confidence':'medium','sample_count':4,'matched_samples':3,'basis':['3 completed runs of this workflow','scaled for 832×1216, 15 steps, 1 active LoRA, 1 output'],'features':{'workflow':'Synthetic workflow','model':['fixture-model'],'loras':['fixture-lora'],'resolution':[832,1216],'steps':15,'frames':1,'node_count':8,'references':1,'modality':'image'}})
        if self.path=='/api/references/check':return self.json([{'file':f,'available':f!='missing.png','sha256':'a'*64} for f in data['files']])
        if self.path=='/api/prompt/compile':
            return self.json({'state':'review_required','fields':{'positive':'A lantern in a quiet forest','negative':'blur'},'profile':{'id':data['profile_id']},'intent':data['intent'],'errors':[],'diagnostics':[],'coverage':[],'profile_sha256':'a'*64})
        if self.path.startswith('/api/jobs/') and self.path.endswith('/stop-tracking'):
            return self.json({'id':self.path.split('/')[3],'tracking_disposition':{'status':'stopped','reason':data.get('reason'),'recorded_at':123.0}})
        return self.json({'error':'Unexpected mutation blocked in fixture: '+self.path},400)


def run(screenshots):
    global FAIL_WORKSPACE, ONLINE, WORKSPACE_DELAY
    from playwright.sync_api import sync_playwright
    server=ThreadingHTTPServer(('127.0.0.1',int(os.environ.get('STUDIO_UX_TEST_PORT','0'))),Handler); threading.Thread(target=server.serve_forever,daemon=True).start()
    origin=f'http://127.0.0.1:{server.server_port}'
    checks=[]
    def check(condition, label):
        assert condition,label
        checks.append(label)
        print('PASS: '+label,flush=True)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or None,headless=True,args=['--no-sandbox'])
            context=browser.new_context(viewport={'width':1536,'height':1060},device_scale_factor=1)
            page=context.new_page(); errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(origin);page.wait_for_selector('#uxRecent .ux-recent-card');page.wait_for_function('!!selected && schemaAvailable');page.wait_for_timeout(500)
            check(page.locator('#homeView').is_visible(),'overview is default')
            check(not [post for post in POSTS if post['path']=='/api/jobs'],'startup has zero generation mutations')
            check(not errors,'no browser boot exceptions: '+str(errors))
            page.evaluate("showView('create')")
            page.wait_for_selector('#timeEstimate:not([hidden])')
            check('42' in page.locator('#estimateValue').inner_text(),'interactive time estimate is shown')
            layout=page.evaluate("""() => { const box=s => { const r=document.querySelector(s).getBoundingClientRect(); return {top:r.top,left:r.left,right:r.right}; }; return {editor:box('.editor'),estimate:box('#timeEstimate'),gallery:box('.gallery-panel')}; }""")
            check(layout['gallery']['top']==layout['editor']['top'] and layout['gallery']['left']>=layout['editor']['right'] and layout['estimate']['top']>layout['editor']['top'],'recent runs stays in the right column beside the editor')
            before_estimates=len([post for post in POSTS if post['path']=='/api/estimate']);page.fill('#positive','A timing estimate interaction');page.wait_for_timeout(350)
            check(len([post for post in POSTS if post['path']=='/api/estimate'])>before_estimates,'time estimate refreshes after a control change')
            failed=page.locator('#gallery .jobStatus').filter(has_text='Memory allocation failed')
            check(failed.count()==1,'failed allocation shows a clear diagnosis panel')
            check('smaller resolution' in failed.inner_text() and 'bad allocation' in failed.inner_text(),'failure panel keeps the next action and engine detail')
            page.evaluate("""jobs.push({id:'trackable-job',preset_name:'Interrupted fixture',status:'uncertain',message:'Original uncertain outcome is retained.',controls:{},prompt_ids:['known-fixture'],submissions:[{prompt_id:'known-fixture',status:'observing'}],outputs:[],can_stop_tracking:true});renderJobs()""")
            check(page.locator('[data-stop-tracking-reason="trackable-job"]').count()==1,'uncertain known prompt exposes an explicit stop reason')
            before_posts=len(POSTS);page.click('.stopTracking');check(len(POSTS)==before_posts,'blank stop reason does not mutate')
            page.fill('[data-stop-tracking-reason="trackable-job"]','Operator retained <img src=x> uncertainty');page.click('.stopTracking');page.wait_for_timeout(100)
            check(len(POSTS)==before_posts+1 and POSTS[-1]['path']=='/api/jobs/trackable-job/stop-tracking','stop tracking sends exactly one explicit disposition request')
            page.evaluate("""jobs=jobs.filter(j=>j.id!=='trackable-job');jobs.push({id:'stopped-job',preset_name:'Stopped fixture',status:'uncertain',message:'Original uncertain outcome is retained.',controls:{},prompt_ids:['known-fixture'],submissions:[{prompt_id:'known-fixture',status:'observing'}],outputs:[],tracking_disposition:{status:'stopped',reason:'Operator retained <img src=x> uncertainty',recorded_at:123},can_stop_tracking:false,can_resume_tracking:true});renderJobs()""")
            stopped=page.locator('#gallery .jobStatus').last
            check('uncertain' in stopped.inner_text() and 'Original uncertain outcome is retained.' in stopped.inner_text(),'stopped tracking keeps the original uncertain status and message')
            check('Tracking stopped' in stopped.inner_text() and stopped.locator('img').count()==0,'stopped reason is escaped rather than rendered as markup')
            check('Resume observation of retained prompt' in stopped.locator('.resume').inner_text() and stopped.locator('.recipe').count()==1,'stopped gallery record retains Recipe and offers observation-only recovery')
            page.evaluate("""productionPlans.push({id:'tracking-project',name:'Retained stopped stage',kind:'comparison',state:{status:'uncertain',message:'Original project uncertainty retained.'},stages:[{label:'A',operation:'generate',attempt:{job_id:'stopped-job'},job:jobs.find(j=>j.id==='stopped-job')}],budget:{allowance:2,reserved:2},axis:'seed',values:[]});productionId='tracking-project';renderProduction()""")
            check(page.locator('[data-project-action="resume"]').is_disabled() and 'Resume is unavailable' in page.locator('#productionDetail').inner_text(),'production view disables direct resume for a stopped retained stage')
            page.evaluate("showView('home')")
            if screenshots:page.screenshot(path=str(screenshots/'overview-desktop.png'),full_page=True)
            page.keyboard.press('Control+k');check(page.locator('#studioCommandDialog').is_visible(),'Ctrl+K opens finder');page.fill('#studioCommandSearch','voice');check(page.locator('#studioCommandResults a').count()==1,'finder filters tools');page.keyboard.press('Escape');check(not page.locator('#studioCommandDialog').is_visible(),'Escape closes finder')
            page.click('[data-ux-intent="edit"]');page.wait_for_selector('#createView:not([hidden])');check(page.locator('#uxRecipeLabel').inner_text().startswith('Qwen'),'intent chooses compatible recipe');check(page.locator('#generate').is_disabled(),'empty required slots block generation')
            page.click('#uxPullAsset');page.wait_for_selector('[data-ux-pull="asset-0"]');page.click('[data-ux-pull="asset-0"]');page.wait_for_function('uploaded === "'+('a'*32)+'_fixture.png"');check(page.evaluate('parentAssets[0]')=='asset-0','picker preserves lineage');check(page.locator('#generate').is_enabled(),'filled required slot becomes ready');check(page.locator('#gallery .reference-output').count()==1,'output actions consolidate to one handoff');check(all(x['path']!='/api/jobs' for x in POSTS),'source picker does not generate')
            page.fill('#positive','A saved workflow draft');page.wait_for_timeout(500);check(page.evaluate('Object.keys(localStorage).some(k=>k.includes("qwen-1ref"))'),'edited draft is persisted')
            if screenshots:
                page.evaluate('window.scrollTo(0,0)');page.screenshot(path=str(screenshots/'create-desktop.png'),full_page=True)
            page.reload();page.wait_for_function('!!selected && schemaAvailable');page.wait_for_timeout(300);page.evaluate("selectPreset('qwen-1ref')");page.wait_for_selector('#uxRestoreDraft:not([hidden])');check(page.evaluate('JSON.parse(localStorage.getItem("studio-draft-v1:ux-test-workspace:qwen-1ref")).recipe.controls.positive')=='A saved workflow draft','boot does not overwrite saved draft');page.click('#uxRestoreDraft');page.wait_for_function('document.querySelector("#positive").value === "A saved workflow draft"');check(page.evaluate('parentAssets[0]')=='asset-0','restore retains source lineage')
            page.evaluate("openAsset('asset-1');jobs[0].outputs[0].asset_id=undefined;document.querySelector('#assetDialog').close()");before_posts=len(POSTS);before_parents=page.evaluate('JSON.stringify(parentAssets)');page.click('#gallery .reference-output');check(not page.locator('#uxHandoff').is_visible(),'missing gallery identity refuses handoff');check(len(POSTS)==before_posts and page.evaluate('JSON.stringify(parentAssets)')==before_parents,'missing gallery identity makes no reference or lineage write')
            page.evaluate("jobs[0].outputs[0].asset_id='asset-0'");page.click('#gallery .reference-output');check('Lantern' in page.locator('#uxHandoffSource').inner_text(),'gallery handoff uses its output identity over active asset');page.click('[data-ux-close="uxHandoff"]');page.evaluate("openAsset('asset-1')");page.click('[data-ux-handoff="asset-1"]');check('Forest' in page.locator('#uxHandoffSource').inner_text(),'asset-detail handoff retains its active asset identity');page.click('[data-ux-close="uxHandoff"]');page.evaluate("document.querySelector('#assetDialog').close()")
            page.evaluate("openAsset('asset-1');document.querySelector('#assetDialog').close();const button=document.createElement('button');button.dataset.handoff='reference';document.body.append(button)");page.click('[data-handoff="reference"]');check('Forest' in page.locator('#uxHandoffSource').inner_text(),'legacy handoff treats its value as a destination, not an asset identity');page.click('[data-ux-close="uxHandoff"]')
            ASSETS.append(dict(ASSETS[0],id='asset-late',title='Late gallery output'));page.evaluate("jobs[0].outputs[0].asset_id='asset-late'");page.click('#gallery .reference-output');page.wait_for_function("document.querySelector('#uxHandoff').open");check('Late gallery output' in page.locator('#uxHandoffSource').inner_text(),'late gallery output refreshes its exact asset identity');page.click('[data-ux-close="uxHandoff"]')
            page.evaluate("jobs[0].outputs[0].asset_id='asset-missing'");before_posts=len(POSTS);page.click('#gallery .reference-output');page.wait_for_timeout(100);check(not page.locator('#uxHandoff').is_visible() and len(POSTS)==before_posts,'missing refreshed gallery asset stays rejected without a write')
            ASSETS.append(dict(ASSETS[0],id='asset-trashed',title='Trashed gallery output',trashed_at=1));page.evaluate("jobs[0].outputs[0].asset_id='asset-trashed'");page.click('#gallery .reference-output');page.wait_for_timeout(100);check(not page.locator('#uxHandoff').is_visible(),'trashed refreshed gallery asset stays rejected')
            FAIL_WORKSPACE=True;page.evaluate("jobs[0].outputs[0].asset_id='asset-fetch-failure'");page.click('#gallery .reference-output');page.wait_for_timeout(100);check(not page.locator('#uxHandoff').is_visible(),'failed gallery refresh cannot open a handoff');FAIL_WORKSPACE=False
            WORKSPACE_DELAY=.3;page.evaluate("jobs[0].outputs[0].asset_id='asset-stale'");page.click('#gallery .reference-output');page.evaluate("jobs[0].outputs[0].asset_id='asset-0'");page.click('#gallery .reference-output');page.wait_for_function("document.querySelector('#uxHandoff').open");page.wait_for_timeout(450);check('Lantern' in page.locator('#uxHandoffSource').inner_text(),'stale gallery refresh cannot replace a newer handoff');page.click('[data-ux-close="uxHandoff"]');WORKSPACE_DELAY=0
            page.evaluate("showView('assets')");page.wait_for_selector('[data-asset-open="asset-0"]');page.locator('[data-asset-open="asset-0"]').first.click();page.fill('#assetNotes','Do not lose this edit');page.click('[data-ux-handoff="asset-0"]');check(not page.locator('#uxHandoff').is_visible(),'unsaved asset edits block handoff');check(page.locator('#assetNotes').input_value()=='Do not lose this edit','handoff preserves unsaved details');page.fill('#assetNotes','');page.click('[data-ux-handoff="asset-0"]');check(page.locator('#uxHandoff').is_visible(),'asset opens reviewed handoff');page.click('[data-ux-destination="animate"]');check('wan22-i2v' in page.locator('#uxDestination').inner_html(),'handoff filters to image-input video recipes');check('wan22-t2v' not in page.locator('#uxDestination').inner_html(),'text-only destination excluded for image handoff')
            if screenshots:page.screenshot(path=str(screenshots/'handoff-desktop.png'))
            page.click('#uxPrepareHandoff');page.wait_for_function('selected.id === "wan22-i2v"');check(page.evaluate('parentAssets[0]')=='asset-0','handoff preserves source in new recipe');check(page.locator('#uxContinuation').is_visible(),'prepared handoff keeps an explicit source-bound context panel');check(page.locator('#positive').input_value()=='','image description is not copied into a motion brief');check(page.locator('#generate').is_disabled(),'motion continuation waits for explicit motion wording');check(all(x['path']!='/api/jobs' for x in POSTS),'handoff has zero generation mutations')
            if screenshots:page.locator('#uxContinuation').screenshot(path=str(screenshots/'handoff-prepared-desktop.png'))
            page.evaluate("showView('assets')");page.check('[data-asset-check="asset-5"]');check(page.locator('#createScene').get_attribute('aria-disabled')=='true','JPEG scene selection blocked');page.click('#createScene',force=True);check(page.url.endswith('#assets'),'blocked scene handoff does not navigate');page.click('#clearAssetSelection');page.check('[data-asset-check="asset-0"]');check(page.locator('#createScene').get_attribute('aria-disabled')=='false','PNG scene selection allowed')
            page.evaluate("showView('models')");check(page.locator('.environment-panel .runtime-bar').is_visible(),'environment controls live in Models');page.go_back();page.wait_for_timeout(150);check(page.locator('#assetsView').is_visible(),'browser Back restores previous view')
            FAIL_WORKSPACE=True;page.evaluate("showView('home')");page.wait_for_function('document.querySelector("#uxHomeHealth").textContent.includes("unavailable")');check('—' in page.locator('#uxStats').inner_text(),'unavailable workspace is not reported as zero');FAIL_WORKSPACE=False
            page.goto(origin+'/prompt-lab.html');page.wait_for_selector('#profile option',state='attached');page.click('#compile');page.wait_for_selector('#studioSendPrompt:not([disabled])');page.click('#studioSendPrompt');page.wait_for_selector('#uxTransfer:not([hidden])');check('lantern' in page.locator('#uxTransferPreview').inner_text(),'Prompt Lab transfers explicit text draft');page.wait_for_function('!!selected');page.click('#uxApplyPrompt');check('lantern' in page.locator('#positive').input_value(),'text is applied only after explicit click');check(all(x['path']!='/api/jobs' for x in POSTS),'prompt transfer never generates')
            for tool in ['av.html','voice.html','review.html']:
                page.goto(origin+'/'+tool);page.wait_for_selector('.studio-sidebar');check(page.locator('#studioJump').is_visible(),tool+' has shared navigation')
            page.goto(origin+'/#home');page.wait_for_selector('#uxRecent .ux-recent-card');page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(150);check(page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'),'mobile overview has no horizontal overflow')
            if screenshots:page.screenshot(path=str(screenshots/'overview-mobile.png'),full_page=True)
            page.click('#studioNavToggle');check(page.locator('#studioNavToggle').get_attribute('aria-expanded')=='true','mobile navigation is expandable');page.click('[data-studio-route="create"]');check(page.locator('#studioNavToggle').get_attribute('aria-expanded')=='false','navigation closes after route change');check(page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'),'mobile create has no horizontal overflow')
            if screenshots:page.screenshot(path=str(screenshots/'create-mobile.png'),full_page=True)
            for route in ['assets','production','models','learn']:
                page.evaluate(f"showView('{route}')");page.wait_for_timeout(100);check(page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'),f'mobile {route} has no horizontal overflow')
            page.evaluate("showView('create');selectPreset('qwen-2ref')");page.click('#uxPullAsset');page.select_option('#uxSourceSlot','1');page.click('[data-ux-pull="asset-1"]');page.wait_for_function('referenceRecords[1].file === "'+('a'*32)+'_fixture.png"');check(page.evaluate('referenceRecords[0].file') is None,'named source picker fills only selected slot');check(page.locator('#generate').is_disabled(),'remaining required slot still blocks run')
            missing={'version':1,'updatedAt':123,'recipe':{'preset':'gentle-variation','controls':{'positive':'Restore without silently falling back','reference':'missing.png'},'batch':1,'parent_assets':['asset-0'],'references':[]}}
            page.set_input_files('#uxImportDraft',{'name':'draft.json','mimeType':'application/json','buffer':json.dumps(missing).encode()});page.wait_for_function('selected.id === "gentle-variation" && document.querySelector("#uxSourceNote").textContent.includes("unavailable")');check(page.locator('#generate').is_disabled(),'missing restored input never falls back to example');check(page.locator('#positive').input_value()=='Restore without silently falling back','draft import restores its text')
            invalid=json.loads(json.dumps(missing));invalid['recipe']['references']=[{'width':'<img onerror=alert(1)>'}]
            page.set_input_files('#uxImportDraft',{'name':'invalid.json','mimeType':'application/json','buffer':json.dumps(invalid).encode()});page.wait_for_function('document.querySelector("#uxNotice").textContent.includes("not a supported")');check(page.evaluate('selected.id')=='gentle-variation','invalid imported draft leaves active recipe intact')
            page.click('#uxPullAsset');page.click('[data-ux-pull="asset-0"]');page.wait_for_function('uploaded === "'+('a'*32)+'_fixture.png"');check(page.locator('#generate').is_enabled(),'reattachment resolves missing-input block')
            ONLINE=False;page.evaluate('health()');check(page.locator('#generate').is_disabled(),'offline runtime blocks generation');ONLINE=True;page.evaluate('health()')
            page.fill('#positive','Keep this tab draft');page.wait_for_timeout(400)
            other=context.new_page();other.goto(origin);other.wait_for_function('!!selected');other.evaluate("localStorage.setItem('studio-draft-v1:ux-test-workspace:gentle-variation',JSON.stringify({version:1,updatedAt:Date.now()+1,recipe:{preset:'gentle-variation',controls:{positive:'Other tab draft'},batch:1}}))")
            page.wait_for_function('document.querySelector("#uxDraftStatus").textContent.includes("Another tab")');page.fill('#positive','Do not overwrite the other tab');page.wait_for_timeout(400);check(page.evaluate('JSON.parse(localStorage.getItem("studio-draft-v1:ux-test-workspace:gentle-variation")).recipe.controls.positive')=='Other tab draft','cross-tab conflict pauses autosave');other.close();page.click('#uxKeepDraft');check(page.evaluate('JSON.parse(localStorage.getItem("studio-draft-v1:ux-test-workspace:gentle-variation")).recipe.controls.positive')=='Do not overwrite the other tab','explicit keep-this-tab resolves draft conflict')
            check(set(x['path'] for x in POSTS) <= {'/api/estimate','/api/assets/reference','/api/references/check','/api/prompt/compile','/api/jobs/trackable-job/stop-tracking'},'all tested navigation and handoffs avoid execution and setup mutations')
            check(not errors,'no browser exceptions through all journeys: '+str(errors))
            blocked=browser.new_context(viewport={'width':1280,'height':900});blocked.add_init_script("Object.defineProperty(window, 'localStorage', {get(){throw new DOMException('Storage disabled','SecurityError')}})")
            b=blocked.new_page();b.goto(origin+'/#create');b.wait_for_function('!!selected && schemaAvailable');check(b.locator('#createView').is_visible(),'blocked localStorage does not break startup');blocked.close();browser.close()
        print(json.dumps({'passed':len(checks),'checks':checks,'post_paths':[x['path'] for x in POSTS],'fixture_data':True},indent=2))
    finally:server.shutdown();server.server_close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--screenshots',type=Path);args=parser.parse_args()
    if args.screenshots:args.screenshots.mkdir(parents=True,exist_ok=True)
    run(args.screenshots)
