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
from http.server import BaseHTTPRequestHandler
from browser_ports import browser_server
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app')); sys.path.insert(0, str(ROOT))  # app/ modules import studio_workflow from the repo root
import continuation
import looks
import wan_capacity
POSTS = []
FAIL_WORKSPACE = False
WORKSPACE_DELAY = 0
ONLINE = True
CATALOG = json.loads((ROOT / 'presets/catalog.json').read_text(encoding='utf-8'))
for preset in CATALOG['presets']:
    graph = json.loads((ROOT / preset['graph']).read_text(encoding='utf-8'))
    capacity = wan_capacity.projection(preset, graph)
    if capacity is not None: preset['wan_decode_capacity'] = capacity
    preset['defaults'] = {k: graph[str(v[0])]['inputs'].get(str(v[1]), '') for k, v in preset.items()
                          if isinstance(v, list) and len(v) == 2 and str(v[0]) in graph and isinstance(v[1], str)}
    preset['choices'] = {'sampler': ['euler', 'dpmpp_2m'], 'scheduler': ['normal', 'karras']}
    preset['model'] = looks.model_of(graph)
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
                       workspace_id='1'*32, favorite=False, tags=['fixture'], trashed_at=None, metadata_revision=0))
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
            '/api/identity':{'workspace':'ux-test-workspace'}, '/api/setups':[], '/api/looks':{'looks':[],'seed_errors':[],'generation_submitted':False}, '/api/characters':{'characters':[],'generation_submitted':False}, '/api/jobs':JOBS,
            '/api/workspace':{'workspace_id':'1'*32,'assets':ASSETS,'collections':[]}, '/api/production':PLANS,
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
        raw=file.read_bytes(); self.send_response(200);self.send_header('Content-Type','text/javascript' if file.suffix=='.js' else mimetypes.guess_type(file)[0] or 'application/octet-stream');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)

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
    server=browser_server(Handler, port=int(os.environ.get('STUDIO_UX_TEST_PORT', '0'))); threading.Thread(target=server.serve_forever,daemon=True).start()
    origin=f'http://127.0.0.1:{server.server_port}'
    checks=[]
    def check(condition, label):
        assert condition,label
        checks.append(label)
        print('PASS: '+label,flush=True)
    # The debounced time estimate and a restored draft's availability check are read-only POSTs that can land
    # inside any window under load (#1124, measured); "no write" means none of the other routes.
    READ_ONLY={'/api/estimate','/api/references/check'}
    def writes(start): return [post['path'] for post in POSTS[start:] if post['path'] not in READ_ONLY]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or None,headless=True,args=['--no-sandbox'])
            context=browser.new_context(viewport={'width':1536,'height':1060},device_scale_factor=1)
            page=context.new_page(); errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(origin);page.wait_for_selector('#makeGoals [data-make-goal]')
            check(page.locator('#makeView').is_visible() and not page.locator('#homeView').is_visible(),'Make is the default view')
            check(page.locator('#studioSidebar nav > a').all_text_contents()==['✦Make','▦Library','◇Models & setup'],'Workspace has exactly the three primary destinations')
            check(page.locator('#studioSidebar [data-studio-route="home"]').count()==0,'Overview is absent from the sidebar')
            for section in ['Advanced','More tools']:
                group=page.locator(f'[data-nav-group="{section}"]');summary=group.locator('summary')
                check(not group.evaluate('(el)=>el.open'),section+' starts collapsed')
                summary.focus();page.keyboard.press('Enter');page.wait_for_function('(section)=>localStorage.getItem("studio.nav."+section)==="true"',arg=section)
                page.reload();page.wait_for_selector('#makeGoals [data-make-goal]');check(group.evaluate('(el)=>el.open'),section+' remembers keyboard expansion across reload')
                summary.focus();page.keyboard.press('Space');page.wait_for_function('(section)=>localStorage.getItem("studio.nav."+section)==="false"',arg=section)
                page.reload();page.wait_for_selector('#makeGoals [data-make-goal]');check(not group.evaluate('(el)=>el.open'),section+' remembers keyboard collapse across reload')
            for route,section in [('create','Advanced'),('learn','More tools')]:
                page.goto(origin+'/#'+route);page.wait_for_selector(f'[data-studio-route="{route}"][aria-current="page"]')
                check(page.locator(f'[data-nav-group="{section}"]').evaluate('(el)=>el.open'),section+' opens for its bookmarked route')
                page.evaluate("showView('make')");page.locator(f'[data-nav-group="{section}"] summary').click()
            page.wait_for_function('!!selected && schemaAvailable')
            check(page.locator('#createView h1').inner_text()=='Full editor — every setting for one recipe','Full editor heading explains its purpose')
            check(page.locator('#positive').input_value()=='','Full editor starts with an empty prompt')
            check(page.locator('#positive').get_attribute('placeholder')=='Describe the picture','Full editor has a neutral prompt placeholder')
            for query,label,href,goal in [('anime','Anime character','/#make','character'),('upscale','Fix or upscale','/#make','repair'),('download','Models & setup','/#models',None),('pose','Character in a new pose','/#make','combine')]:
                page.keyboard.press('Control+k');page.fill('#studioCommandSearch',query)
                result=page.locator('#studioCommandResults a').filter(has=page.locator('b',has_text=label)).first
                check(result.get_attribute('href')==href,'finder: '+query+' has the right destination')
                if goal:
                    check(result.get_attribute('data-make-goal')==goal,'finder: '+query+' selects the right Make goal')
                    result.focus();page.keyboard.press('Enter');page.wait_for_selector('#makeGoals [data-make-goal="'+goal+'"][aria-checked="true"]')
                    check(page.evaluate('JSON.parse(localStorage.getItem("studio.make")).goal')==goal,'finder: '+query+' survives the Make reload')
                else:
                    page.fill('#studioCommandSearch',query);page.keyboard.press('ArrowDown');page.keyboard.press('Enter');page.wait_for_selector('#modelsView',state='visible')
            page.keyboard.press('Control+k');page.fill('#studioCommandSearch','no-such-place')
            check('Try anime, upscale, pose' in page.locator('#studioCommandResults').inner_text(),'empty finder suggests real queries');page.keyboard.press('Escape')
            finder=browser.new_page();finder.route('**/api/looks',lambda route:route.fulfill(json=json.loads((ROOT/'presets/looks.json').read_text(encoding='utf-8'))))
            finder.goto(origin+'/#make');finder.wait_for_selector('#makeGoals [data-make-goal]')
            for query,goal in [('fix face','repair'),('fix hands','repair'),('3d','mesh'),('video','animate'),('style','restyle')]:
                finder.keyboard.press('Control+k');finder.fill('#studioCommandSearch',query)
                check(finder.locator('#studioCommandResults a').first.get_attribute('data-make-goal')==goal,'finder synonym: '+query);finder.keyboard.press('Escape')
            for query,href in [('pictures','/#assets'),('keepers','/#assets'),('compare','/#production'),('seed','/#create')]:
                finder.keyboard.press('Control+k');finder.fill('#studioCommandSearch',query)
                check(finder.locator('#studioCommandResults a').first.get_attribute('href')==href,'finder keyword: '+query);finder.keyboard.press('Escape')
            for query in ['wai','krea','noob','anima']:
                finder.keyboard.press('Control+k');finder.fill('#studioCommandSearch',query)
                finder.wait_for_selector('#studioCommandResults [data-make-look]')
                check(finder.locator('#studioCommandResults [data-make-look]').count()>0,'model search lists a Make look: '+query)
                if query=='wai':check(finder.locator('#studioCommandResults [data-make-look="look-wai-fantasy-portrait"]').count()==1,'wai lists the WAI portrait look')
                finder.keyboard.press('Escape')
            for query in ['pony','flux','qwen']:
                finder.keyboard.press('Control+k');finder.fill('#studioCommandSearch',query)
                check(finder.locator('#studioCommandResults a[href="/#models"]').count()==1,'model without an authored look leads to Models & setup: '+query)
                finder.keyboard.press('Escape')
            for query in ['lora','adapter','tune']:
                finder.keyboard.press('Control+k');finder.fill('#studioCommandSearch',query)
                result=finder.locator('#studioCommandResults a').first
                check(result.get_attribute('href')=='/#make' and 'Open Model, LoRAs and settings under the words in Make' in result.inner_text(),'Tune hint leads to Make: '+query)
                finder.keyboard.press('Escape')
            finder.keyboard.press('Control+k');finder.fill('#studioCommandSearch','pixel');finder.wait_for_selector('#studioCommandResults [data-make-look="look-preset-pixel-lora"]')
            check(finder.locator('#studioCommandResults a').first.get_attribute('data-make-look')=='look-preset-pixel-lora','pixel search leads to the pixel-art look')
            finder.keyboard.press('ArrowDown');finder.keyboard.press('ArrowDown');finder.keyboard.press('ArrowUp');finder.keyboard.press('Enter')
            finder.wait_for_selector('.make-chosen');check(finder.evaluate('JSON.parse(localStorage.getItem("studio.make")).look')=='look-preset-pixel-lora','look selection reloads Make with the chosen pixel look')
            finder.keyboard.press('Control+k');finder.fill('#studioCommandSearch',next(l['name'] for l in json.loads((ROOT/'presets/looks.json').read_text(encoding='utf-8'))['looks'] if l['id']=='look-wai-fantasy-portrait'));finder.wait_for_selector('#studioCommandResults [data-make-look="look-wai-fantasy-portrait"]')
            check(finder.locator('#studioCommandResults [data-make-look="look-wai-fantasy-portrait"]').get_attribute('data-make-goal')=='character','look names resolve to their Make goal');finder.close()
            page.evaluate("localStorage.removeItem('studio.make')");page.reload();page.wait_for_selector('#makeGoals [data-make-goal]')
            page.keyboard.press('Control+k');page.fill('#studioCommandSearch','Overview');check(page.locator('#studioCommandResults a').count()==0,'Overview is no longer offered in the command palette (#18)');page.keyboard.press('Escape')
            page.goto(origin+'/#home');page.wait_for_selector('#makeView',state='visible');check(page.url.endswith('#make') and page.locator('#homeView').is_hidden(),'#home lands on Make, not the retired Overview (#18)')
            page.evaluate("showView('make')");page.wait_for_function('!!selected && schemaAvailable');page.wait_for_timeout(500)
            check(not [post for post in POSTS if post['path']=='/api/jobs'],'startup has zero generation mutations')
            check(not errors,'no browser boot exceptions: '+str(errors))
            page.evaluate("showView('create')")
            page.wait_for_function('document.querySelector("#workshopEta")?.textContent.includes("42")')
            check('42' in page.locator('#workshopEta').inner_text(),'interactive time estimate is shown in the run dock')
            check(page.locator('#createView').get_attribute('data-workshop-layout')=='focus','Focus is the default presentation')
            check(not page.locator('#workshopResults').evaluate('(el)=>el.open'),'recent runs are secondary in Focus')
            page.click('#workshopResults > summary')
            before_estimates=len([post for post in POSTS if post['path']=='/api/estimate']);page.fill('#positive','A timing estimate interaction');page.wait_for_timeout(350)
            check(len([post for post in POSTS if post['path']=='/api/estimate'])>before_estimates,'time estimate refreshes after a control change')
            failed=page.locator('#jobProblemsHost .jobStatus').filter(has_text='Memory allocation failed')
            check(failed.count()==1,'failed allocation shows a clear diagnosis panel')
            check(not page.locator('#jobProblems').evaluate('(el)=>el.open'),'old failures are collapsed outside the experiment flow')
            page.click('#jobProblems > summary')
            check('smaller resolution' in failed.inner_text() and 'bad allocation' in failed.inner_text(),'failure panel keeps the next action and engine detail')
            page.evaluate("""jobs.push({id:'trackable-job',preset_name:'Interrupted fixture',status:'uncertain',message:'Original uncertain outcome is retained.',controls:{},prompt_ids:['known-fixture'],submissions:[{prompt_id:'known-fixture',status:'observing'}],outputs:[],can_stop_tracking:true});renderJobs()""")
            check(page.locator('[data-stop-tracking-reason="trackable-job"]').count()==1,'uncertain known prompt exposes an explicit stop reason')
            before_posts=len(POSTS);page.click('.stopTracking');check(writes(before_posts)==[],'blank stop reason does not mutate')
            page.fill('[data-stop-tracking-reason="trackable-job"]','Operator retained <img src=x> uncertainty');page.click('.stopTracking');page.wait_for_timeout(100)
            check(writes(before_posts)==['/api/jobs/trackable-job/stop-tracking'],'stop tracking sends exactly one explicit disposition request')
            page.evaluate("""jobs=jobs.filter(j=>j.id!=='trackable-job');jobs.push({id:'stopped-job',preset_name:'Stopped fixture',status:'uncertain',message:'Original uncertain outcome is retained.',controls:{},prompt_ids:['known-fixture'],submissions:[{prompt_id:'known-fixture',status:'observing'}],outputs:[],tracking_disposition:{status:'stopped',reason:'Operator retained <img src=x> uncertainty',recorded_at:123},can_stop_tracking:false,can_resume_tracking:true});renderJobs()""")
            stopped=page.locator('#jobProblemsHost .jobStatus').last
            check('uncertain' in stopped.inner_text() and 'Original uncertain outcome is retained.' in stopped.inner_text(),'stopped tracking keeps the original uncertain status and message')
            check('Tracking stopped' in stopped.inner_text() and stopped.locator('img').count()==0,'stopped reason is escaped rather than rendered as markup')
            check('Resume observation of retained prompt' in stopped.locator('.resume').inner_text() and stopped.locator('.recipe').count()==1,'stopped Problems record retains Recipe and offers observation-only recovery')
            page.evaluate("""jobs.push({id:'unreadable-job',preset_name:'Unreadable run record',status:'uncertain',message:'The run record could not be read (state.json: x). Nothing was resubmitted.',controls:{},outputs:[],record_error:'state.json: x',run_path:'x'});renderJobs()""")
            check(page.locator('[data-problem="unreadable-job"]').count()==1 and page.locator('[data-problem="unreadable-job"] .recipe').count()==0,'an unreadable run record stays visible but offers no Recipe export (it has no recipe)')
            page.evaluate("jobs=jobs.filter(j=>j.id!=='unreadable-job');renderJobs()")
            page.evaluate("""productionPlans.push({id:'tracking-project',name:'Retained stopped stage',kind:'comparison',state:{status:'uncertain',message:'Original project uncertainty retained.'},stages:[{label:'A',operation:'generate',attempt:{job_id:'stopped-job'},job:jobs.find(j=>j.id==='stopped-job')}],budget:{allowance:2,reserved:2},axis:'seed',values:[]});productionId='tracking-project';renderProduction()""")
            check(page.locator('[data-project-action="resume"]').is_disabled() and 'Resume is unavailable' in page.locator('#productionDetail').inner_text(),'production view disables direct resume for a stopped retained stage')
            page.evaluate("showView('home')")
            if screenshots:page.screenshot(path=str(screenshots/'overview-desktop.png'),full_page=True)
            page.keyboard.press('Control+k');check(page.locator('#studioCommandDialog').is_visible(),'Ctrl+K opens finder');page.fill('#studioCommandSearch','voice');check(page.locator('#studioCommandResults a').count()==1,'finder filters tools');page.keyboard.press('Escape');check(not page.locator('#studioCommandDialog').is_visible(),'Escape closes finder')
            # #18: the Overview intent picker left the navigation with the Overview; Full editor opens by its own route and the later steps pick recipes explicitly.
            page.evaluate("showView('create')");page.wait_for_selector('#createView:not([hidden])');page.wait_for_function('!!selected');check(page.locator('#homeView').is_hidden(),'Full editor opens without the retired Overview view')
            page.evaluate("selectPreset('qwen-1ref')");check(page.locator('#generate').is_disabled(),'empty required slots block generation')
            page.click('#uxPullAsset');page.wait_for_selector('[data-ux-pull="asset-0"]');page.click('[data-ux-pull="asset-0"]');page.wait_for_function('uploaded === "'+('a'*32)+'_fixture.png"');check(page.evaluate('parentAssets[0]')=='asset-0','picker preserves lineage');check(page.locator('#generate').is_enabled(),'filled required slot becomes ready');check(page.locator('#gallery .reference-output').count()==1,'output actions consolidate to one handoff');check(all(x['path']!='/api/jobs' for x in POSTS),'source picker does not generate')
            page.fill('#positive','A saved workflow draft');page.wait_for_timeout(500);check(page.evaluate('Object.keys(localStorage).some(k=>k.includes("qwen-1ref"))'),'edited draft is persisted')
            if screenshots:
                page.evaluate('window.scrollTo(0,0)');page.screenshot(path=str(screenshots/'create-desktop.png'),full_page=True)
            page.reload();page.wait_for_function('!!selected && schemaAvailable');page.wait_for_timeout(300);page.evaluate("selectPreset('qwen-1ref')");page.wait_for_selector('#uxRestoreDraft:not([hidden])');check(page.evaluate('JSON.parse(localStorage.getItem("studio-draft-v1:ux-test-workspace:qwen-1ref")).recipe.controls.positive')=='A saved workflow draft','boot does not overwrite saved draft');page.click('#uxRestoreDraft');page.wait_for_function('document.querySelector("#positive").value === "A saved workflow draft"');check(page.evaluate('parentAssets[0]')=='asset-0','restore retains source lineage')
            page.evaluate("openAsset('asset-1');jobs[0].outputs[0].asset_id=undefined;document.querySelector('#assetDialog').close()");before_posts=len(POSTS);before_parents=page.evaluate('JSON.stringify(parentAssets)');page.click('#workshopResults > summary');page.click('#gallery .reference-output');check(not page.locator('#uxHandoff').is_visible(),'missing gallery identity refuses handoff');check(writes(before_posts)==[] and page.evaluate('JSON.stringify(parentAssets)')==before_parents,'missing gallery identity makes no reference or lineage write')
            page.evaluate("jobs[0].outputs[0].asset_id='asset-0'");page.click('#gallery .reference-output');check('Lantern' in page.locator('#uxHandoffSource').inner_text(),'gallery handoff uses its output identity over active asset');page.click('[data-ux-close="uxHandoff"]');page.evaluate("openAsset('asset-1')");page.click('[data-ux-handoff="asset-1"]');check('Forest' in page.locator('#uxHandoffSource').inner_text(),'asset-detail handoff retains its active asset identity');page.click('[data-ux-close="uxHandoff"]');page.evaluate("document.querySelector('#assetDialog').close()")
            page.evaluate("openAsset('asset-1');document.querySelector('#assetDialog').close();const button=document.createElement('button');button.dataset.handoff='reference';document.body.append(button)");page.click('[data-handoff="reference"]');check('Forest' in page.locator('#uxHandoffSource').inner_text(),'legacy handoff treats its value as a destination, not an asset identity');page.click('[data-ux-close="uxHandoff"]')
            ASSETS.append(dict(ASSETS[0],id='asset-late',title='Late gallery output'));page.evaluate("jobs[0].outputs[0].asset_id='asset-late'");page.click('#gallery .reference-output');page.wait_for_function("document.querySelector('#uxHandoff').open");check('Late gallery output' in page.locator('#uxHandoffSource').inner_text(),'late gallery output refreshes its exact asset identity');page.click('[data-ux-close="uxHandoff"]')
            page.evaluate("jobs[0].outputs[0].asset_id='asset-missing'");before_posts=len(POSTS);page.click('#gallery .reference-output');page.wait_for_timeout(100);check(not page.locator('#uxHandoff').is_visible() and writes(before_posts)==[],'missing refreshed gallery asset stays rejected without a write')
            ASSETS.append(dict(ASSETS[0],id='asset-trashed',title='Trashed gallery output',trashed_at=1));page.evaluate("jobs[0].outputs[0].asset_id='asset-trashed'");page.click('#gallery .reference-output');page.wait_for_timeout(100);check(not page.locator('#uxHandoff').is_visible(),'trashed refreshed gallery asset stays rejected')
            FAIL_WORKSPACE=True;page.evaluate("jobs[0].outputs[0].asset_id='asset-fetch-failure'");page.click('#gallery .reference-output');page.wait_for_timeout(100);check(not page.locator('#uxHandoff').is_visible(),'failed gallery refresh cannot open a handoff');FAIL_WORKSPACE=False
            WORKSPACE_DELAY=.3;page.evaluate("jobs[0].outputs[0].asset_id='asset-stale'");page.click('#gallery .reference-output');page.evaluate("jobs[0].outputs[0].asset_id='asset-0'");page.click('#gallery .reference-output');page.wait_for_function("document.querySelector('#uxHandoff').open");page.wait_for_timeout(450);check('Lantern' in page.locator('#uxHandoffSource').inner_text(),'stale gallery refresh cannot replace a newer handoff');page.click('[data-ux-close="uxHandoff"]');WORKSPACE_DELAY=0
            page.evaluate("showView('assets')");page.wait_for_selector('[data-asset-open="asset-0"]');page.locator('[data-asset-open="asset-0"]').first.click();page.fill('#assetNotes','Do not lose this edit');page.click('[data-ux-handoff="asset-0"]');check(not page.locator('#uxHandoff').is_visible(),'unsaved asset edits block handoff');check(page.locator('#assetNotes').input_value()=='Do not lose this edit','handoff preserves unsaved details');page.fill('#assetNotes','');page.click('[data-ux-handoff="asset-0"]');check(page.locator('#uxHandoff').is_visible(),'asset opens reviewed handoff');page.click('[data-ux-destination="animate"]');check('wan22-i2v' in page.locator('#uxDestination').inner_html(),'handoff filters to image-input video recipes');check('wan22-t2v' not in page.locator('#uxDestination').inner_html(),'text-only destination excluded for image handoff')
            if screenshots:page.screenshot(path=str(screenshots/'handoff-desktop.png'))
            page.click('#uxPrepareHandoff');page.wait_for_function('selected.id === "wan22-i2v"');check(page.evaluate('parentAssets[0]')=='asset-0','handoff preserves source in new recipe');check(page.locator('#uxContinuation').is_visible(),'prepared handoff keeps an explicit source-bound context panel');check(page.locator('#positive').input_value()=='','image description is not copied into a motion brief');check(page.locator('#generate').is_disabled(),'motion continuation waits for explicit motion wording');check(all(x['path']!='/api/jobs' for x in POSTS),'handoff has zero generation mutations')
            if screenshots:page.locator('#uxContinuation').screenshot(path=str(screenshots/'handoff-prepared-desktop.png'))
            page.evaluate("showView('assets')");page.check('[data-asset-check="asset-5"]');check(page.locator('#createScene').get_attribute('aria-disabled')=='true','JPEG scene selection blocked');page.click('#createScene',force=True);check(page.url.endswith('#assets'),'blocked scene handoff does not navigate');page.click('#clearAssetSelection');page.check('[data-asset-check="asset-0"]');check(page.locator('#createScene').get_attribute('aria-disabled')=='false','PNG scene selection allowed')
            page.evaluate("showView('models')");check(not page.locator('.environment-panel .runtime-bar').is_visible() and not page.evaluate("document.querySelector('.environment-panel').open"),'environment switcher is folded when Models opens');page.locator('.environment-panel > summary').click();check(page.locator('.environment-panel .runtime-bar').is_visible(),'environment controls live in Models behind a disclosure');page.go_back();page.wait_for_timeout(150);check(page.locator('#assetsView').is_visible(),'browser Back restores previous view')
            # S5: real routing and cards over synthetic model state; no setup or generation presses.
            models=context.new_page();models.on('pageerror',lambda error:errors.append(str(error)))
            rows=[dict(id=key,name=name,family=family,file='checkpoints/'+key+'.safetensors',path='C:/models/checkpoints/'+key+'.safetensors',bytes=8,present=present,verified=verified,installable=True,source='https://example.com/model',license='Fixture',download={}) for key,name,family,present,verified in [('required','Required model','Anime',False,False),('other','Other model','Photo',False,False),('pending','Pending model','Anime',True,False),('mismatch','Mismatch model','Photo',True,False),('installed','Installed model','Anime',True,True)]]
            rows[3]['verification']='mismatch'
            model_library=dict(storage=dict(free_bytes=100,total_bytes=200,reserve_bytes=20),model_root='C:/models',assets=rows,folders=[],inventory=[],collections=[])
            models.route('**/api/library',lambda route:route.fulfill(json=model_library))
            models.route('**/api/health',lambda route:route.fulfill(json=dict(online=True,schema_available=True,missing_models={'wai':['checkpoints/required.safetensors','checkpoints/installed.safetensors']})))
            looks=json.loads((ROOT/'presets/looks.json').read_text(encoding='utf-8'))
            models.route('**/api/looks',lambda route:route.fulfill(json=looks))
            wai_look=next(l['name'] for l in looks['looks'] if l['id']=='look-wai-fantasy-portrait')
            models.route('**/api/inspect/wai',lambda route:route.fulfill(json=dict(requirements=[dict(file='checkpoints/required.safetensors',asset_id='required',present=False),dict(file='checkpoints/installed.safetensors',asset_id='installed',present=True)],nodes=[],graph={})))
            models.route('**/api/inspect/*',lambda route:route.fulfill(json=dict(requirements=[],nodes=[],graph={})) if not route.request.url.endswith('/wai') else route.fallback())
            models.goto(origin+'/#models?need=wai');models.wait_for_function('document.querySelectorAll("#modelCards .model-card").length===1')
            check(models.locator('#modelsView').is_visible() and models.url.endswith('#models?need=wai'),'need deep link preserves Models route and parameter')
            check(models.locator('#curatedModelTitle').inner_text()=='Files needed for '+next(p['name'] for p in CATALOG['presets'] if p['id']=='wai'),'need filter names the preset')
            check(models.locator('#modelCards .model-card h3').all_text_contents()==['Required model'],'need filter shows only missing required files')
            models.locator('[data-models-all]').click();models.wait_for_function('document.querySelectorAll("#modelCards .model-card").length===5')
            # A missing file no look or recipe uses folds under Optional once every inspection has answered (audit v3 N8).
            models.wait_for_function('document.querySelector("#modelCards .model-group > summary")?.textContent.startsWith("Optional")')
            check(models.locator('#modelCards h3').all_text_contents().count('Missing (1)')==1 and 'Needs a check (2)' in models.locator('#modelCards').inner_text(),'curated models group missing and pending or mismatched files with counts')
            check(models.locator('#modelCards .model-group > summary').all_inner_texts()==['Optional · not used by any look or recipe (1)','Needs a check (2)','Installed (1)'] and not any(models.locator('#modelCards .model-group').evaluate_all('(els)=>els.map(el=>el.open)')),'checked and unchecked groups have counts and start collapsed')
            # Shop structure: looks ready or needing a file, per-file acquisition block, install only where eligible, search at the top that filters everything.
            models.wait_for_function('document.querySelector("#modelLooks .model-look")')
            check(models.locator('#modelLooks').is_visible() and 'needs a download' in models.locator('#modelLooks').inner_text().lower() and models.locator('#modelLooks .model-look.needs').inner_text().startswith(wai_look),'looks list names which look needs a download')
            check(models.locator('#modelLooks .model-look.needs a').get_attribute('href')=='/#models?need=wai' and models.locator('#modelLooks .model-look.ready').count()>=1,'blocked look links to its files; other looks are ready')
            required=models.locator('#modelCards .model-card').filter(has_text='Required model')
            check(('Used by: '+wai_look) in required.inner_text(),'card says which look uses the file')
            check(required.locator('.model-get a').get_attribute('href')=='https://example.com/model' and 'C:/models/checkpoints' in required.locator('.model-get code').inner_text() and required.locator('[data-copy]').count()==2,'missing file shows its source, its folder and a copy button')
            check(required.locator('[data-install]').is_enabled() and required.locator('[data-install]').inner_text().startswith('Install'),'installable missing file offers its install action')
            check(models.locator('#modelCards .model-card').filter(has_text='Pending model').locator('.model-get').count()==0 and models.locator('#modelCards .model-card').filter(has_text='Pending model').locator('[data-install]').text_content()=='Verify','a present file has no acquisition block and a quiet Verify')
            check(models.locator('.models-toolbar').evaluate('(el)=>getComputedStyle(el).position')=='sticky','the search stays at the top while scrolling')
            models.fill('#curatedModelSearch','glowing fantasy');check(models.locator('#modelCards .model-card h3').all_text_contents()==['Required model','Installed model'] and models.locator('#modelLooks .model-look').count()==1,'top search filters looks and the files they use')
            models.fill('#curatedModelSearch','');models.wait_for_function('document.querySelectorAll("#modelCards .model-card").length===5')
            for query,expected in [('required',['Required model']),('photo',['Other model','Mismatch model']),('pending.safetensors',['Pending model'])]:
                models.fill('#curatedModelSearch',query);check(models.locator('#modelCards .model-card h3').all_text_contents()==expected,'curated search filters '+query)
            models.fill('#curatedModelSearch','');models.evaluate("location.hash='models?need=wai'");models.wait_for_function('document.querySelectorAll("#modelCards .model-card").length===1')
            check(models.locator('#modelsView').is_visible(),'same-view need hash change redraws Models')
            models.reload();models.wait_for_function('document.querySelectorAll("#modelCards .model-card").length===1')
            check(models.locator('#modelsView').is_visible(),'need filter survives reload')
            models.goto(origin+'/?need=wai#models');models.wait_for_function('document.querySelectorAll("#modelCards .model-card").length===1')
            check(models.locator('#modelsView').is_visible(),'query need parameter also filters Models')
            models.locator('[data-models-all]').click();models.wait_for_function('document.querySelectorAll("#modelCards .model-card").length>1 && !location.search.includes("need")')
            check(models.locator('#modelsView').is_visible(),'Show everything clears a query need filter too')
            models.goto(origin+'/#make');models.wait_for_selector('[data-make-look="look-wai-fantasy-portrait"]');models.locator('[data-make-look="look-wai-fantasy-portrait"]').click()
            check(models.locator('#makeWhy a').get_attribute('href')=='/#models?need=wai','composer blocker links to the preset files')
            models.locator('[data-make-change]').click()  # choosing a look folds the gallery (S1); open it again to see the cards
            card_link=models.locator('.make-look').filter(has=models.locator('[data-make-look="look-wai-fantasy-portrait"]')).locator('a')
            check(card_link.get_attribute('href')=='/#models?need=wai' and card_link.locator('xpath=ancestor::button').count()==0,'look blocker is a real link outside its select button')
            card_link.click();models.wait_for_function('document.querySelectorAll("#modelCards .model-card").length===1')
            check(models.locator('#modelsView').is_visible(),'Make blocker opens only the needed file')
            check(all(x['path'] not in ['/api/jobs','/api/models/install'] for x in POSTS),'model navigation and filtering never submit or install')
            models.close()
            # #18: the Overview stats left the navigation with the Overview itself, so the unavailable-workspace check no longer has a surface here.
            page.goto(origin+'/prompt-lab.html');page.wait_for_selector('#profile option',state='attached');page.click('#compile');page.wait_for_selector('#studioSendPrompt:not([disabled])');page.click('#studioSendPrompt');page.wait_for_selector('#uxTransfer:not([hidden])');check('lantern' in page.locator('#uxTransferPreview').inner_text(),'Prompt Lab transfers explicit text draft');page.wait_for_function('!!selected');page.click('#uxApplyPrompt');check('lantern' in page.locator('#positive').input_value(),'text is applied only after explicit click');check(all(x['path']!='/api/jobs' for x in POSTS),'prompt transfer never generates')
            for tool in ['av.html','voice.html','review.html']:
                page.goto(origin+'/'+tool);page.wait_for_selector('.studio-sidebar');check(page.locator('#studioJump').is_visible(),tool+' has shared navigation')
            page.goto(origin+'/#home');page.wait_for_selector('#makeView',state='visible');page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(150);check(page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'),'mobile landing (#home resolves to Make) has no horizontal overflow')
            check(page.locator('#studioQuickCreate').get_attribute('href')=='/#make' and page.locator('#studioQuickCreate').inner_text()=='Make','mobile header points at Make')
            check(page.locator('#studioQuickCreate').get_attribute('aria-current')=='page','mobile Make is the landing view')
            page.click('#studioQuickCreate');page.wait_for_selector('#makeView',state='visible')
            check(page.locator('#studioQuickCreate').get_attribute('aria-current')=='page','mobile Make is highlighted only on Make');page.evaluate("showView('home')")
            if screenshots:page.screenshot(path=str(screenshots/'overview-mobile.png'),full_page=True)
            page.locator('[data-nav-group="Advanced"]').evaluate('(el)=>el.open=false')
            page.click('#studioNavToggle');check(page.locator('#studioNavToggle').get_attribute('aria-expanded')=='true','mobile navigation is expandable');page.click('[data-nav-group="Advanced"] summary');page.click('[data-studio-route="create"]');check(page.locator('#studioNavToggle').get_attribute('aria-expanded')=='false','navigation closes after route change');check(page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'),'mobile create has no horizontal overflow')
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
            # Handoff 03: dialog actions sat below the fold (Plan comparison at 1440x900, asset details at 900 px tall).
            reachable="([s,d])=>{const r=document.querySelector(s).getBoundingClientRect(),b=document.querySelector(d).getBoundingClientRect(),x=r.left+r.width/2,y=r.top+r.height/2;return r.height>0&&r.top>=Math.max(0,b.top)&&r.bottom<=Math.min(innerHeight,b.bottom)&&document.querySelector(s).contains(document.elementFromPoint(x,y))}"
            hit="sel=>[...document.querySelectorAll(sel)].filter(el=>el.getClientRects().length).map(el=>{const r=el.getBoundingClientRect();return {name:(el.innerText||'').replace(/[^ -~]/g,'').replace(/\\s+/g,' ').trim(),w:r.width,h:r.height}})"
            for width,height in ((1440,900),(390,844)):
                v=browser.new_page(viewport={'width':width,'height':height});v.goto(origin+'/#home');v.wait_for_selector('#makeView',state='visible')
                v.goto(origin+'/#create');v.wait_for_function('!!selected && schemaAvailable')
                looks=v.evaluate(hit,'details.ux-looks > summary')
                if not looks:print(f'NOTE: details.ux-looks > summary is not in the DOM at {width}x{height}',flush=True)
                for box in looks:check(box['w']>=24 and box['h']>=24,f"{box['name']} pointer target is {box['w']:.1f}x{box['h']:.1f} at {width}x{height}")
                # On phones Plan a comparison lives in the run dock's Run tools disclosure (#1495).
                if not v.locator('#planComparison').is_visible():v.click('#workshopRunTools > summary')
                v.click('#planComparison');v.wait_for_selector('#experimentDialog[open]')
                for control in ('#prepareExperiment','#cancelExperiment'):check(v.evaluate(reachable,[control,'#experimentDialog']),f'{control} is on screen when Plan a comparison opens at {width}x{height}')
                v.keyboard.press('Escape');v.evaluate("showView('assets');openAsset('asset-1')");v.wait_for_selector('#assetDialog[open]');v.wait_for_timeout(200)
                for control in ('#saveAssetDetails','#assetTrash'):check(v.evaluate(reachable,[control,'#assetDialog']),f'{control} is on screen when asset details open at {width}x{height}')
                v.close()
            blocked=browser.new_context(viewport={'width':1280,'height':900});blocked.add_init_script("Object.defineProperty(window, 'localStorage', {get(){throw new DOMException('Storage disabled','SecurityError')}})")
            b=blocked.new_page();b.goto(origin+'/#create');b.wait_for_function('!!selected && schemaAvailable');check(b.locator('#createView').is_visible(),'blocked localStorage does not break startup');blocked.close();browser.close()
        print(json.dumps({'passed':len(checks),'checks':checks,'post_paths':[x['path'] for x in POSTS],'fixture_data':True},indent=2))
    finally:server.shutdown();server.server_close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--screenshots',type=Path);args=parser.parse_args()
    if args.screenshots:args.screenshots.mkdir(parents=True,exist_ok=True)
    run(args.screenshots)
