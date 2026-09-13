"""Opt-in Chromium: shipped Gallery, real recovery commands/files, synthetic Comfy."""
import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import threading
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit

import studio_browser_smoke as ui
import test_mixed_batch as recovery


def run(output):
    from playwright.sync_api import sync_playwright
    output.mkdir(parents=True,exist_ok=True)
    case=recovery.MixedBatchTests();case.setUp();case.fixture.patches[0].stop()
    case.unresolved();case.studio.replies=iter([recovery.completed()])
    identifier=case.owning_project();ui.POSTS.clear();mutations=[]
    initial=case.files();pending=copy.deepcopy(case.job['pending_submission']);budget=case.studio.production.get(identifier)['budget']
    class Handler(ui.Handler,recovery.server.Handler):
        def do_GET(self):
            path=urlsplit(self.path).path
            if path=='/api/jobs':return self.json([case.studio.public(case.job)])
            if path=='/api/production':return self.json(case.studio.production.list())
            if path=='/api/production/'+identifier:return self.json(case.studio.production.get(identifier))
            return super().do_GET()
        def do_POST(self):
            path=urlsplit(self.path).path
            prefix='/api/jobs/'+case.job['id']
            if path in (prefix+'/observe-known',prefix+'/dispose-mixed','/api/production/'+identifier+'/resume'):
                payload=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
                mutations.append({'path':path,'payload':payload})
                try:
                    if path.endswith('/resume'):value=case.studio.production.resume(identifier)
                    else:
                        action='observe' if path.endswith('/observe-known') else 'dispose'
                        value=case.command(action,payload)
                        if action=='observe':case.consume();value=case.studio.public(case.job)
                    return self.json(value)
                except ValueError as exc:return self.json({'error':str(exc)},400)
            return super().do_POST()
    target=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=target.serve_forever,daemon=True);thread.start()
    result={'passed':False,'fixture':'Shipped UI, real recovery command/Production/files; inert catalog and synthetic Comfy; shared queue consumed deterministically'}
    try:
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or None,headless=True)
            try:
                page=browser.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda exc:errors.append(str(exc)))
                page.goto(f'http://127.0.0.1:{target.server_port}');page.wait_for_function('!!selected')
                page.evaluate("showView('create')")
                box=page.locator('.mixedBatchControls');box.locator('summary').click()
                assert not mutations
                assert 'unknown submission outcome' in box.inner_text()
                button=box.locator('[data-mixed-action="observe"]');button.focus();button.press('Enter')
                page.wait_for_function("document.querySelector('.mixedBatchControls')?.textContent.includes('Output 1: completed')")
                assert len(mutations)==1 and mutations[0]['path'].endswith('/observe-known')
                box=page.locator('.mixedBatchControls');assert box.evaluate('(element)=>element.open')
                dispose=box.locator('[data-mixed-action="dispose"]');dispose.scroll_into_view_if_needed()
                pointer=dispose.evaluate("""element=>{const r=element.getBoundingClientRect(),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return {reachable:element===hit||element.contains(hit),hit:hit?.outerHTML,button:{x:r.x,y:r.y,width:r.width,height:r.height}};}""")
                result['pointer_target']=pointer
                page.screenshot(path=str(output/'mixed-pointer-target.png'),full_page=True)
                assert pointer['reachable'],'A preceding panel intercepts the recovery button: '+str(pointer)
                dispose.click();assert len(mutations)==1
                box.locator('[data-mixed-reason]').fill('Retain the unknown tail; no retry.')
                dispose.click();assert len(mutations)==1
                box.locator('[data-mixed-ack]').check()
                # An unrelated Gallery rerender must not erase this same-revision draft.
                page.evaluate("renderJobs('unrelated-fixture-refresh')")
                assert box.locator('[data-mixed-reason]').input_value()=='Retain the unknown tail; no retry.'
                assert box.locator('[data-mixed-ack]').is_checked()
                for width in (1440,390):
                    page.set_viewport_size({'width':width,'height':1000})
                    box.scroll_into_view_if_needed();page.screenshot(path=str(output/f'mixed-{width}.png'),full_page=True)
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),'Horizontal overflow'
                box.locator('[data-mixed-action="dispose"]').focus();box.locator('[data-mixed-action="dispose"]').press('Enter')
                page.wait_for_function("document.querySelector('#gallery')?.textContent.includes('Batch abandoned locally')")
                assert len(mutations)==2 and mutations[1]['payload']['acknowledge_unknown'] is True
                assert page.locator('[data-mixed-action]').count()==0
                page.evaluate("showView('production');productionId='"+identifier+"';renderProduction()")
                page.wait_for_selector('[data-project-action="resume"]')
                button=page.locator('[data-project-action="resume"]');assert button.inner_text()=='Reconcile outcome only'
                button.focus();button.press('Enter')
                page.wait_for_function("!document.querySelector('[data-project-action=resume]')")
                assert len(mutations)==3 and mutations[-1]['path'].endswith('/resume')
                assert case.studio.production.get(identifier)['state']['status']=='failed'
                assert case.studio.production.get(identifier)['budget']==budget
                assert case.job['pending_submission']==pending
                for name in ('recipe.json','workflow.json'):assert case.files()[name]==initial[name]
                case.no_posts_since(2);assert case.studio.queue.empty();assert len(case.studio.jobs)==1
                unintended=[p for p in ui.POSTS if p['path'] not in ('/api/estimate','/api/references/check')]
                assert not unintended,unintended
                assert not errors,errors
                result.update(passed=True,browser=browser.version,page_errors=errors,mutations=mutations,
                              recovered_known_status=case.job['submissions'][0]['status'],local_status=case.job['status'],
                              new_prompt_posts=0,known_history_gets=1,later_jobs=0,keyboard=True,draft_preserved=True,budget=budget)
            finally:browser.close()
    except Exception as exc:result['error']=str(exc);raise
    finally:
        target.shutdown();target.server_close();thread.join(5);case.doCleanups()
        (output/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    run(parser.parse_args().out)
