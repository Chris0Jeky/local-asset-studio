"""Unsent Make picture drafts survive reload, scoped to this tab and creation privacy.

Native HTTP/Chromium with real frontend and synthetic records. No ComfyUI or private media.
python tests/make_draft_browser.py --out .runtime/make-drafts
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import threading
import time
import traceback

from playwright.sync_api import sync_playwright
from browser_ports import browser_server, evidence_screenshot
import make_goals_browser as fixture

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_TEXT = 'Private synthetic brief: adult elf in a blue travelling coat.'
PUBLIC_TEXT = 'Adult elf in a green travelling coat, silver hair, amber eyes.'
PRIVACY = """(() => {
  let creation=sessionStorage.getItem('qa.creation')||'regular',scope=sessionStorage.getItem('qa.scope')||'regular',revision=0;
  window.StudioPrivacy={creation:()=>creation,scope:()=>scope,storageKey:(key,p=creation)=>p==='private'?key+'.private':key,
    capture:()=>({privacy:creation,scope,revision}),setCreation:p=>window.qaPrivacy(p,scope),
    allows:(record,s=scope)=>s==='all'||(record?.privacy||'regular')===s,
    mediaUrl:(path,record)=>record?.privacy==='private'?path+(path.includes('?')?'&':'?')+'privacy=private':path,
    fetch:(path,options={})=>{const headers=new Headers(options.headers||{});if(!headers.has('X-Studio-Privacy'))headers.set('X-Studio-Privacy',scope);
      if((options.method||'GET')!=='GET'&&!headers.has('X-Studio-Creation-Privacy'))headers.set('X-Studio-Creation-Privacy',creation);return fetch(path,{...options,headers});},submitted:()=>{}};
  window.qaPrivacy=(next,nextScope=next)=>{const previousCreation=creation,previousScope=scope;creation=next;scope=nextScope;revision++;
    sessionStorage.setItem('qa.creation',creation);sessionStorage.setItem('qa.scope',scope);
    document.dispatchEvent(new CustomEvent('studio:privacy-change',{detail:{creation,scope,previousCreation,previousScope}}));};
})();"""


def synthetic_privacy(context):
    """This focused Make gate owns an explicit contract stub; the composed gate uses the real module."""
    context.add_init_script(PRIVACY)
    context.route('**/static/privacy.js',lambda route:route.fulfill(content_type='text/javascript',body='/* Explicit synthetic privacy owner from make_draft_browser. */'))


def snapshot(page):
    return page.evaluate("""() => ({source:document.querySelector('#makeComposer [data-ux-handoff]')?.dataset.uxHandoff||null,
      fields:Object.fromEntries([...document.querySelectorAll('[data-make-field]')].map(e=>[e.dataset.makeField,e.value])),
      pose:document.querySelector('[data-make-pose-change]')?.previousElementSibling?.textContent||null,
      route:document.querySelector('[data-make-pose-route]:checked')?.dataset.makePoseRoute||null,
      style:document.querySelector('[data-make-style]:checked')?.dataset.makeStyle||null})""")


def run(output, baseline=False):
    output.mkdir(parents=True, exist_ok=True)
    server_errors, errors, rows, requests, disconnects = [], [], [], [], []
    class Handler(fixture.Handler):
        def do_POST(self):
            requests.append({'path':self.path,'privacy':self.headers.get('X-Studio-Creation-Privacy'),'scope':self.headers.get('X-Studio-Privacy')})
            return super().do_POST()
    server=browser_server(Handler)
    def server_error(request,address):
        error=sys.exc_info()[1]
        if isinstance(error,(BrokenPipeError,ConnectionResetError,ConnectionAbortedError)):disconnects.append(type(error).__name__)
        else:server_errors.append(traceback.format_exc())
    server.handle_error=server_error
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    origin='http://127.0.0.1:'+str(server.server_port)
    def check(name, ok, detail=None): rows.append({'name':name,'passed':bool(ok),'detail':detail})
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or None)
            for width,height in ((1440,900),(390,844)):
                for goal in ('edit','combine','restyle'):
                    context=browser.new_context(viewport={'width':width,'height':height},reduced_motion='reduce');synthetic_privacy(context)
                    page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
                    page.goto(origin+'/#make');page.wait_for_selector('[data-make-look]')
                    page.locator('[data-make-goal="'+goal+'"]').click();page.locator('[data-make-pick="asset-1"]').click()
                    if goal=='edit':page.locator('#makeF-change').fill(PUBLIC_TEXT)
                    elif goal=='combine':
                        page.locator('[data-make-pose-pick="asset-0"]').click()
                        for key,text in [('who',PUBLIC_TEXT),('clothes','Green coat, brass buttons, brown boots'),('pose','Looking over her left shoulder')]:page.locator('#makeF-'+key).fill(text)
                    else:
                        page.locator('label:has([data-make-style="look-preset-realvis"])').click();page.locator('#makeF-colours').fill('Keep the green coat and silver hair.')
                    before=snapshot(page);start=time.perf_counter();page.reload();page.wait_for_function('!!catalog?.presets?.length&&!!window.StudioWorkbench')
                    page.wait_for_selector('#makeComposer,#makePictures')
                    # Restoration reads the selected identities before presenting them. Wait for a visible settled outcome.
                    page.wait_for_function('document.querySelector("#makeComposer")||document.querySelector("[data-make-pick]")||document.querySelector("#makeDraftStatus")')
                    after=snapshot(page)
                    check(goal+' reload '+str(width),before==after,{'before':before,'after':after,'automated_reload_ms':round((time.perf_counter()-start)*1000,2)})
                    evidence_screenshot(page,path=str(output/(goal+'-'+str(width)+'.png')))
                    context.close()
            context=browser.new_context(viewport={'width':1440,'height':900});synthetic_privacy(context)
            page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(origin+'/#make');page.wait_for_selector('[data-make-look]')
            page.locator('[data-make-goal="edit"]').click();page.locator('[data-make-pick="asset-1"]').click();page.locator('#makeF-change').fill(PRIVATE_TEXT)
            before=snapshot(page);page.evaluate("qaPrivacy('private')")
            check('make current draft private keeps the form',snapshot(page)==before)
            stores=page.evaluate('({local:{...localStorage},session:{...sessionStorage}})')
            regular_session='\n'.join(v for k,v in stores['session'].items() if not k.endswith('.private'))
            check('private draft never enters localStorage',PRIVATE_TEXT not in json.dumps(stores['local']))
            check('moved draft leaves no regular session copy',PRIVATE_TEXT not in regular_session,{'session_keys':list(stores['session'])})
            check('private draft is held in private session namespace',any(PRIVATE_TEXT in v for k,v in stores['session'].items() if k.endswith('.private')))
            page.reload();page.wait_for_selector('#makeComposer,#makePictures');page.wait_for_function('document.querySelector("#makeComposer")||document.querySelector("[data-make-pick]")')
            check('private draft reload stays private',snapshot(page)==before and page.evaluate('StudioPrivacy.creation()')=='private')
            page.evaluate("qaPrivacy('regular')")
            check('returning regular hides private draft',PRIVATE_TEXT not in page.locator('#makeView').inner_text() and PRIVATE_TEXT not in page.locator('#makeView').evaluate('(e)=>[...e.querySelectorAll("input,textarea")].map(x=>x.value).join(" ")'))
            page.evaluate("qaPrivacy('private')")
            page.wait_for_selector('#makeComposer,#makePictures')
            check('private draft can be resumed explicitly',snapshot(page)==before)
            context.close()
            context=browser.new_context(viewport={'width':1440,'height':900});synthetic_privacy(context)
            page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(origin+'/#make');page.wait_for_selector('[data-make-look]')
            page.locator('[data-make-goal="edit"]').click();page.locator('[data-make-pick="asset-1"]').click();page.locator('#makeF-change').fill(PUBLIC_TEXT)
            source=next(a for a in fixture.fixture.ASSETS if a['id']=='asset-1');source['trashed_at']=1789229900
            try:
                page.reload();page.wait_for_function('document.querySelector("#makeView").dataset.draftState==="ready"')
                check('unavailable source preserves wording and blocks Generate',page.input_value('#makeF-change')==PUBLIC_TEXT and page.is_disabled('#makeGenerate') and 'unavailable' in page.locator('#makeWhy').inner_text())
            finally:source['trashed_at']=None
            Handler.workspace_id='2'*32
            try:
                page.reload();page.wait_for_function('document.querySelector("#makeView").dataset.draftState==="ready"')
                check('different Workspace cannot adopt the draft source',page.input_value('#makeF-change')==PUBLIC_TEXT and page.is_disabled('#makeGenerate') and 'another library' in page.locator('#makeWhy').inner_text())
            finally:Handler.workspace_id='1'*32
            page.evaluate("const d=JSON.parse(sessionStorage.getItem('studio.make.picture-draft'));d.source.workspace_id=null;sessionStorage.setItem('studio.make.picture-draft',JSON.stringify(d))")
            page.reload();page.wait_for_function('document.querySelector("#makeView").dataset.draftState==="ready"')
            check('unbound saved source keeps wording and requires a fresh choice',page.input_value('#makeF-change')==PUBLIC_TEXT and page.is_disabled('#makeGenerate') and 'verified library identity' in page.locator('#makeWhy').inner_text())
            page.evaluate("sessionStorage.setItem('studio.make.picture-draft','{invalid json')")
            page.reload();page.wait_for_selector('[data-make-pick]')
            check('malformed stored draft is ignored without submitting',page.locator('#makeF-change').count()==0)
            context.close();browser.close()
    except Exception as error:
        check('driver completed',False,type(error).__name__+': '+str(error))
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
    check('zero generation submissions',not fixture.jobs(),{'jobs':len(fixture.jobs())})
    check('zero page errors',not errors,errors);check('zero HTTP request-thread errors',not server_errors,server_errors)
    receipt={'mode':'native-http-synthetic-api','baseline':baseline,'rows':rows,'requests':requests,'client_disconnects':disconnects,'source_sha256':{path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in ['app/static/make.js','tests/make_draft_browser.py']},
             'limits':'No model run, GPU, user media, creative acceptance or human completion-time measurement. Synthetic privacy owner exercises the browser contract; integrated privacy owner requires a separate composed check.'}
    (output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    for row in rows:print(('PASS ' if row['passed'] else 'FAIL ')+row['name'])
    print(str(sum(r['passed'] for r in rows))+'/'+str(len(rows)))
    return 0 if all(row['passed'] for row in rows) else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,default=ROOT/'.runtime/make-drafts');parser.add_argument('--baseline',action='store_true');args=parser.parse_args()
    raise SystemExit(run(args.out,args.baseline))
