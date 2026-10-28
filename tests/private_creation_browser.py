"""Real privacy controls with Make, Full editor and Library; synthetic HTTP only.

python tests/private_creation_browser.py --out .runtime/private-creation-browser
--app-root serves another checkout's frontend and matched fixture read-only for composed local verification.
No privacy-module injection, ComfyUI connection, model or owner media is used.
"""
import argparse
import hashlib
import importlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import threading
import time
import traceback
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from browser_ports import browser_server, evidence_screenshot

ROOT = Path(__file__).resolve().parents[1]
EDITOR = 'PRIVATE EDITOR CANARY: adult elf in a blue travelling coat.'
MAKE = 'PRIVATE MAKE CANARY: adult elf with silver hair in a green coat.'
PRIVATE_ASSET = 'PRIVATE LIBRARY CANARY: synthetic lantern'
PRIVATE_JOB = 'PRIVATE HISTORY CANARY: synthetic lantern study'


def run(output, app_root):
    output.mkdir(parents=True, exist_ok=True)
    app_root = app_root.resolve()
    sys.path.insert(0,str(app_root/'tests'))
    fixture=importlib.import_module('make_goals_browser')
    sources = ('app/static/privacy.js', 'app/static/make.js', 'app/static/app.js',
               'app/static/workspace.js', 'app/static/studio-workbench.js', 'app/static/index.html',
               'tests/studio_browser_smoke.py', 'tests/make_goals_browser.py')
    hashes = {path: hashlib.sha256((app_root/path).read_bytes()).hexdigest() for path in sources}
    # Only the served frontend path changes. Fixture records remain synthetic and process-local.
    fixture.fixture.ROOT = app_root
    fixture.fixture.ASSETS = [dict(a, privacy='regular') for a in fixture.fixture.ASSETS]
    private_asset = dict(fixture.fixture.ASSETS[0], id='asset-private', title=PRIVATE_ASSET,
                         privacy='private', job_id='private-fixture-job', prompt_excerpt=PRIVATE_JOB)
    fixture.fixture.ASSETS.append(private_asset)
    fixture.fixture.JOBS = [dict(j, privacy='regular') for j in fixture.fixture.JOBS]
    fixture.fixture.JOBS.append(dict(fixture.fixture.JOBS[0], id='private-fixture-job', privacy='private',
                                    preset_name=PRIVATE_JOB, controls={'positive': PRIVATE_JOB, 'seed':42},
                                    outputs=[{'filename':'private-synthetic.png','asset_id':'asset-private','media_type':'image'}]))
    rows, errors, server_errors, disconnects, requests, sent = [], [], [], [], [], []
    layout={}
    held, release = threading.Event(), threading.Event()
    hold = {'path': None, 'scope': None}

    def classification(value): return value.get('privacy', 'regular')
    def allows(value, scope): return scope == 'all' or classification(value) == scope
    def source(asset):
        result = fixture.fixture.source_context(asset)
        result['privacy'] = classification(asset)
        if classification(asset) == 'private': result.update(positive=PRIVATE_JOB, job_id='private-fixture-job')
        return result

    class Handler(fixture.Handler):
        def scope(self): return self.headers.get('X-Studio-Privacy', 'regular')
        def json(self, value, status=200):
            scope = self.scope()
            if isinstance(value, dict) and isinstance(value.get('assets'), list):
                value = dict(value, assets=[a for a in value['assets'] if allows(a, scope)])
            if isinstance(value, dict) and isinstance(value.get('items'), list):
                value = dict(value, items=[item if not item.get('asset') or allows(item['asset'], scope)
                                          else {'id':item['id'], 'state':'missing', 'asset':None} for item in value['items']])
            return super().json(value, status)
        def do_GET(self):
            path = urlsplit(self.path).path
            requests.append({'method':'GET', 'path':path, 'scope':self.scope()})
            if path == hold['path'] and self.scope() == hold['scope']:
                held.set(); release.wait(10)
            if path == '/api/assets/page':
                query=fixture.fixture.asset_page_query(self.path);query['filters']['privacy']=self.scope()
                return fixture.fixture.observe_fixture(self,lambda workspace:workspace.asset_page(**query))
            if path == '/api/collections':
                query=fixture.fixture.collection_page_query(self.path)
                return fixture.fixture.observe_fixture(self,lambda workspace:workspace.collection_page(**query,privacy=self.scope()))
            if path == '/api/jobs': return self.json([j for j in fixture.fixture.JOBS + sent if allows(j, self.scope())])
            if path.startswith('/api/jobs/'):
                job = next((j for j in fixture.fixture.JOBS + sent if j['id'] == path.rsplit('/',1)[-1]), None)
                if job: return self.json(job if allows(job, self.scope()) else {'error':'Fixture scope excludes this job'}, 200 if allows(job, self.scope()) else 404)
            if path.startswith('/api/assets/') and path.endswith('/context'):
                asset = next((a for a in fixture.fixture.ASSETS if a['id'] == path.split('/')[3]), None)
                return self.json(source(asset) if asset and allows(asset,self.scope()) else {'error':'Fixture scope excludes this asset'},
                                 200 if asset and allows(asset,self.scope()) else 404)
            # Media has an explicit query classification in production. The fixture serves inert repository bytes.
            if path.startswith('/api/assets/') and path.endswith('/thumb'):
                self.path = path[:-6]+'/file'
            return super().do_GET()
        def do_POST(self):
            path = urlsplit(self.path).path
            item = {'method':'POST','path':path,'scope':self.scope(),'privacy':self.headers.get('X-Studio-Creation-Privacy','regular')}
            requests.append(item)
            if path == '/api/assets/selection':
                data=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))));item['body']=data
                if not data.get('workspace_id'):return self.json({'error':'Selection inspection requires workspace_id'},400)
                return fixture.fixture.observe_fixture(self,lambda workspace:workspace.asset_selection(data['ids'],workspace_id=data['workspace_id'],details=data.get('details',False),privacy=self.scope()))
            if path == '/api/jobs':
                data = json.loads(self.rfile.read(int(self.headers.get('Content-Length','0')))); item['body'] = data
                n = len(sent); asset_id = 'synthetic-created-'+str(n)
                asset = dict(fixture.fixture.ASSETS[0], id=asset_id, privacy=item['privacy'], title=data.get('label','Synthetic creation'),
                             prompt_excerpt=data.get('controls',{}).get('positive',''), job_id='created-'+str(n), created_at=time.time(), run_label=data.get('label',''))
                fixture.fixture.ASSETS.append(asset)
                job = dict(data, id='created-'+str(n), privacy=item['privacy'], status='completed', created_at=time.time(),
                           preset_name='Synthetic acknowledged creation', outputs=[{'filename':'synthetic.png','asset_id':asset_id,'media_type':'image'}])
                sent.append(job); return self.json(job, 201)
            if path == '/api/assets/reference':
                data = json.loads(self.rfile.read(int(self.headers.get('Content-Length','0')))); item['body'] = data
                asset = next((a for a in fixture.fixture.ASSETS if a['id']==data['id']), None)
                if not asset or not allows(asset,self.scope()): return self.json({'error':'Fixture source scope refused'},404)
                return self.json(dict(fixture.fixture.source_reference(asset), context=source(asset), privacy=item['privacy']))
            return super().do_POST()

    server = browser_server(Handler)
    def server_error(request,address):
        error=sys.exc_info()[1]
        if isinstance(error,(BrokenPipeError,ConnectionResetError,ConnectionAbortedError)):disconnects.append(type(error).__name__)
        else:server_errors.append(traceback.format_exc())
    server.handle_error = server_error
    thread = threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    origin = 'http://127.0.0.1:'+str(server.server_port)
    def check(name, condition, detail=None):
        rows.append({'name':name,'passed':bool(condition),'detail':detail}); print(('PASS ' if condition else 'FAIL ')+name, flush=True)
    def stores(page): return page.evaluate('({local:{...localStorage},session:{...sessionStorage}})')
    def ready(page): page.wait_for_function('!!catalog?.presets?.length&&!!selected&&!!StudioWorkbench&&!!StudioPrivacy')
    def settled_make(page): page.wait_for_function('document.querySelector("#makeView").dataset.draftState==="ready"')
    def measure_layout(page,name):
        layout[name]=page.evaluate('({width:innerWidth,height:innerHeight,privacy_bar_height:document.querySelector(".privacy-bar").getBoundingClientRect().height,horizontal_overflow:document.documentElement.scrollWidth>innerWidth})')
        check(name+' privacy controls do not cause horizontal overflow',not layout[name]['horizontal_overflow'],layout[name])
    def choose_recipe(page, preset):
        name=page.evaluate('(id)=>catalog.presets.find(p=>p.id===id).name',preset)
        page.locator('#workshopRecipeChange').click(); page.locator('#presetSearch').fill(name)
        page.locator('#presetList [data-id="'+preset+'"]').click(); page.wait_for_function('(id)=>selected.id===id', arg=preset)
    browser_version = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or None)
            browser_version = browser.version
            context = browser.new_context(viewport={'width':1440,'height':900},reduced_motion='reduce',accept_downloads=True)
            page = context.new_page(); page.set_default_timeout(8000); page.on('pageerror',lambda e:errors.append(str(e))); page.on('dialog',lambda dialog:dialog.accept())
            page.goto(origin+'/#create'); ready(page)
            check('real privacy module starts regular',page.evaluate('StudioPrivacy.creation()==="regular"&&StudioPrivacy.scope()==="regular"&&typeof StudioPrivacy.capture==="function"'))
            choose_recipe(page,'wai'); page.locator('#positive').fill(EDITOR)
            page.wait_for_function('(s)=>Object.values(localStorage).some(x=>x.includes(s))',arg=EDITOR)
            page.locator('#privateSession').check()
            check('private session conversion keeps editor wording immediately',page.input_value('#positive')==EDITOR)
            st=stores(page)
            check('converted editor wording leaves localStorage',EDITOR not in json.dumps(st['local']),{'local_keys':list(st['local'])})
            drafts=[json.loads(v) for k,v in st['session'].items() if k.startswith('studio-draft-v1:') and k.endswith('.private')]
            check('converted editor draft is private in tab storage',any(d.get('recipe',{}).get('privacy')=='private' and d['recipe'].get('controls',{}).get('positive')==EDITOR for d in drafts))
            with page.expect_download() as downloaded: page.locator('#uxExportDraft').click()
            export=output/'private-editor-draft.json'; downloaded.value.save_as(export); draft=json.loads(export.read_text(encoding='utf-8'))
            check('exported editor draft carries private classification',draft['recipe'].get('privacy')=='private' and draft['recipe']['controls']['positive']==EDITOR)
            for scope in ('regular','private','all'):
                page.locator('[data-privacy-scope="'+scope+'"]').click()
                check('editor draft independent of '+scope+' read scope',page.evaluate('StudioPrivacy.creation()')=='private' and page.input_value('#positive')==EDITOR)
            page.locator('#privateSession').uncheck()
            check('regular editor clears the private form immediately',EDITOR not in page.input_value('#positive') and EDITOR not in page.locator('#createView').inner_text())
            check('leaving private retains its session draft',EDITOR in json.dumps(stores(page)['session']) and EDITOR not in json.dumps(stores(page)['local']))
            # Import is an explicit user action and must adopt the file's classification before applying its words.
            page.set_input_files('#uxImportDraft',str(export)); page.wait_for_function('(s)=>document.querySelector("#positive").value===s',arg=EDITOR)
            check('imported private draft changes creation privacy before adoption',page.evaluate('StudioPrivacy.creation()')=='private' and EDITOR not in json.dumps(stores(page)['local']))
            check('imported private editor draft is retained for reload',EDITOR in stores(page)['session'].get('studio-draft-v1:ux-test-workspace:wai.private',''),
                  {'saved':stores(page)['session'].get('studio-draft-v1:ux-test-workspace:wai.private')})
            page.reload(); ready(page); choose_recipe(page,'wai'); page.wait_for_selector('#uxRestoreDraft:not([hidden])'); page.locator('#uxRestoreDraft').click()
            page.wait_for_timeout(100)
            check('private editor draft restores after same-tab reload',page.input_value('#positive')==EDITOR and page.evaluate('StudioPrivacy.creation()')=='private' and EDITOR not in json.dumps(stores(page)['local']),
                  {'restored_positive':page.input_value('#positive')})
            measure_layout(page,'desktop')
            evidence_screenshot(page,path=str(output/'private-editor.png'))
            # Another tab owns the newer regular bytes. Converting this tab's unsent form must not replace them.
            page.locator('#creationPrivacy').select_option('regular');page.locator('#positive').fill('REGULAR TAB A CANARY')
            page.wait_for_function('localStorage.getItem("studio-draft-v1:ux-test-workspace:wai")?.includes("REGULAR TAB A CANARY")')
            other=context.new_page();other.set_default_timeout(8000);other.on('pageerror',lambda e:errors.append(str(e)));other.on('dialog',lambda dialog:dialog.accept())
            other.goto(origin+'/#create');ready(other);choose_recipe(other,'wai');other.locator('#positive').fill('REGULAR TAB B CANARY')
            other.wait_for_function('localStorage.getItem("studio-draft-v1:ux-test-workspace:wai")?.includes("REGULAR TAB B CANARY")')
            newer=other.evaluate('localStorage.getItem("studio-draft-v1:ux-test-workspace:wai")')
            page.locator('#creationPrivacy').select_option('private')
            check('private conversion preserves another tab exact regular draft',page.evaluate('localStorage.getItem("studio-draft-v1:ux-test-workspace:wai")')==newer)
            check('private conversion keeps this tab competing wording separately',page.input_value('#positive')=='REGULAR TAB A CANARY' and 'REGULAR TAB A CANARY' in stores(page)['session'].get('studio-draft-v1:ux-test-workspace:wai.private',''))
            other.close()
            # A private source-list response arrives after a real scope change. Invoke the public controller while
            # the modal is open; ordinary topbar controls are deliberately unavailable behind a modal dialog.
            choose_recipe(page,'qwen-1ref'); page.locator('[data-privacy-scope="private"]').click()
            hold.update(path='/api/assets/page',scope='private'); held.clear(); release.clear()
            page.locator('#uxPullAsset').click(); assert held.wait(3),'source list request was not reached'
            page.evaluate("StudioPrivacy.setScope('regular')")
            check('scope change closes and clears pending source picker immediately',not page.locator('#uxSourcePicker').evaluate('(e)=>e.open') and not page.locator('#uxSourceAssets').inner_text().strip())
            release.set(); hold['path']=None; page.wait_for_timeout(250)
            check('late private source list cannot repaint regular picker',PRIVATE_ASSET not in page.locator('#uxSourceAssets').inner_text() and not page.locator('#uxSourcePicker').evaluate('(e)=>e.open'))
            check('all editor operations submitted no generation',not sent)
            context.close()

            context=browser.new_context(viewport={'width':390,'height':844},reduced_motion='reduce')
            page=context.new_page();page.set_default_timeout(8000);page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(origin+'/#make');page.wait_for_selector('[data-make-look]');settled_make(page)
            page.locator('[data-make-goal="edit"]').click();page.locator('[data-make-pick="asset-1"]').click();page.locator('#makeF-change').fill('REGULAR EDIT RECOVERY CANARY')
            page.reload();settled_make(page)
            check('Make picture recovery uses Workspace-bound selection contract',page.locator('#makeF-change').count()>0 and page.input_value('#makeF-change')=='REGULAR EDIT RECOVERY CANARY' and page.is_enabled('#makeGenerate'),
                  {'blocker':page.locator('#makeWhy').inner_text() if page.locator('#makeWhy').count() else None})
            page.locator('[data-make-goal="character"]').click()
            page.locator('[data-make-look="look-wai-fantasy-portrait"]').click();page.locator('#makeScene').fill(MAKE)
            page.locator('#creationPrivacy').select_option('private');settled_make(page)
            check('per-creation Private keeps Make wording',page.input_value('#makeScene')==MAKE and page.evaluate('StudioPrivacy.scope()')=='regular')
            measure_layout(page,'mobile')
            page.locator('#makeGenerate').click();page.wait_for_function('StudioPrivacy.creation()==="regular"')
            check('Make submits exactly one private job through real owner',len(sent)==1 and sent[0]['privacy']=='private' and MAKE in json.dumps(sent[0]['controls']))
            check('acknowledged override resets without reusing private wording',MAKE not in page.input_value('#makeScene') and MAKE not in page.locator('#makeRuns').inner_text())
            check('private Make run and tune stay out of localStorage',MAKE not in json.dumps(stores(page)['local']))
            page.locator('[data-privacy-scope="private"]').click();settled_make(page);page.wait_for_selector('#makeRuns [data-run="created-0"]')
            check('private filter restores acknowledged Make run',MAKE in page.locator('#makeRuns').inner_text())
            page.locator('[data-privacy-scope="all"]').click();settled_make(page);page.wait_for_selector('#makeRuns [data-make-rerun="created-0"]')
            page.locator('[data-make-rerun="created-0"]').click()
            check('All view cannot copy private rerun into regular creation',MAKE not in page.input_value('#makeScene') and 'Choose Private' in page.locator('#makeStatus').inner_text())
            page.locator('#creationPrivacy').select_option('private');settled_make(page)
            page.locator('[data-make-rerun="created-0"]').click();page.locator('[data-privacy-scope="regular"]').click();settled_make(page)
            check('scope-only Regular keeps private Make draft but hides private results',page.input_value('#makeScene')==MAKE and MAKE not in page.locator('#makeRuns').inner_text())
            page.goto(origin+'/#assets');page.wait_for_selector('#assetGrid [data-asset-open]')
            check('regular Library excludes private synthetic asset',page.locator('[data-asset-open="asset-private"]').count()==0)
            page.locator('[data-privacy-scope="private"]').click();page.wait_for_selector('[data-asset-open="asset-private"]')
            check('private Library shows only private assets',page.locator('[data-asset-open="asset-0"]').count()==0)
            page.locator('[data-privacy-scope="all"]').click();page.wait_for_selector('[data-asset-open="asset-0"]')
            check('All Library deliberately includes both classifications',page.locator('[data-asset-open="asset-private"]').count()>0)
            evidence_screenshot(page,path=str(output/'all-library-mobile.png'))
            page.locator('[data-privacy-scope="regular"]').click()
            check('Regular Library clears private DOM immediately',PRIVATE_ASSET not in page.locator('#assetGrid').inner_text())
            fresh=context.new_page();fresh.set_default_timeout(8000);fresh.on('pageerror',lambda e:errors.append(str(e)));fresh.goto(origin+'/#make');settled_make(fresh)
            check('new independent tab starts regular without private text',fresh.evaluate('StudioPrivacy.creation()==="regular"&&StudioPrivacy.scope()==="regular"') and MAKE not in fresh.locator('#makeView').evaluate('(e)=>e.textContent+" "+[...e.querySelectorAll("input,textarea")].map(x=>x.value).join(" ")'))
            fresh.close();context.close();browser.close()
    except Exception as error:
        check('driver completed',False,type(error).__name__+': '+str(error)); traceback.print_exc()
    finally:
        release.set();server.shutdown();server.server_close();thread.join(timeout=5)
    check('zero page errors',not errors,errors);check('zero HTTP request-thread errors',not server_errors,server_errors)
    unchanged=all(hashlib.sha256((app_root/path).read_bytes()).hexdigest()==value for path,value in hashes.items())
    check('served source remained unchanged during the run',unchanged)
    receipt={'mode':'native-http-real-privacy-owner-synthetic-api','rows':rows,'requests':requests,'inert_jobs':len(sent),'client_disconnects':disconnects,'layout':layout,
             'provenance':{'app_root':str(app_root),'python':platform.python_version(),'playwright':version('playwright'),
                           'chromium':browser_version,'source_sha256':hashes,'driver_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
             'limits':'Production privacy controller/frontend and production read contracts over temporary synthetic SQLite data. No running Studio instance, user workspace, model execution, owner media, artistic acceptance or human task-time claim.'}
    (output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(str(sum(r['passed'] for r in rows))+'/'+str(len(rows)),flush=True)
    return 0 if all(row['passed'] for row in rows) else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,default=ROOT/'.runtime/private-creation-browser')
    parser.add_argument('--app-root',type=Path,default=ROOT);args=parser.parse_args();raise SystemExit(run(args.out,args.app_root))
