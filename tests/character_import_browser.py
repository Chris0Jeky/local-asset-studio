"""Desktop/mobile import through real Studio commands, with a temporary canon and inert preflight.

No live Studio, ComfyUI or generation worker is used. Run explicitly, not on every unit-test discovery.
"""
import argparse
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import shutil
import threading
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
import test_character_handoff_import as fixtures
from test_server import server
import studio_use_cases


def run(out):
    out.mkdir(parents=True, exist_ok=False)
    fixture=fixtures.CharacterHandoffImportTests();fixture.setUp()
    http=worker=None;posts=[];errors=[];rows=[]
    try:
        payload=fixture.payload(fixture.plan['cases'][0])
        plan_path=fixture.root/'plan.json';plan_path.write_text(json.dumps(payload['character_plan']),encoding='utf-8')
        handoff_path=fixture.root/'handoff.json';handoff_path.write_text(json.dumps(payload['character_handoff']),encoding='utf-8')
        source=fixture.root/'reference.png';source.write_bytes(fixtures.PNG)
        Stub,_=studio_use_cases.build_handler()
        class Handler(Stub,server.Handler):
            studio=fixture.studio
            json=Stub.json
            def log_message(self,*args):pass
            def _safe_host(self):return self.headers.get('Host')=='127.0.0.1:'+str(self.server.server_port)
            def _safe_mutation(self):return self._safe_host() and self.headers.get('Origin')=='http://127.0.0.1:'+str(self.server.server_port)
            def do_GET(self):
                if urlsplit(self.path).path.startswith('/api/production'):return server.Handler.do_GET(self)
                return Stub.do_GET(self)
            def do_POST(self):
                posts.append(self.path)
                if re.search(r'^/api/jobs$|/(start|resume|run|render|generate)$',self.path):return self.json({'error':'Generation is forbidden in this fixture'},403)
                if self.path in ('/api/upload','/api/production'):return server.Handler.do_POST(self)
                return Stub.do_POST(self)
        fixture.patches[0].stop()  # Studio's inert worker stays unstarted; start our HTTP listener only.
        http=ThreadingHTTPServer(('127.0.0.1',0),Handler);worker=threading.Thread(target=http.serve_forever,daemon=True);worker.start()
        origin=f'http://127.0.0.1:{http.server_port}'
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or None,args=['--disable-gpu'])
            try:
                for width in (1440,390):
                    context=browser.new_context(viewport={'width':width,'height':980},reduced_motion='reduce')
                    page=context.new_page();page.set_default_timeout(7000);page.on('pageerror',lambda error:errors.append(str(error)))
                    page.goto(origin+'/#production',wait_until='networkidle');page.locator('#importCharacterStudy').wait_for(state='visible')
                    before=list(posts);page.locator('#importCharacterStudy').click()
                    page.locator('#characterPlanFile').set_input_files(plan_path);page.locator('#characterHandoffFile').set_input_files(handoff_path)
                    page.locator('#readCharacterCase').click();page.locator('#characterReference0').wait_for()
                    assert posts==before,'Reading the selected files caused a server mutation'
                    page.locator('#characterReference0').set_input_files(source)
                    dialog=page.locator('#characterImportDialog');box=dialog.bounding_box()
                    assert box and box['x']>=0 and box['x']+box['width']<=width+1,'Import dialog exceeds the viewport'
                    assert dialog.evaluate('(node)=>node.scrollWidth<=node.clientWidth+1'),'Import controls overflow horizontally'
                    page.locator('#importCharacterCase').focus();assert page.locator('#importCharacterCase').evaluate('(node)=>node===document.activeElement')
                    dialog.screenshot(path=str(out/f'import-{width}.png'))
                    page.locator('#importCharacterCase').press('Enter');dialog.wait_for(state='hidden')
                    page.locator('#productionMessage').filter(has_text='Nothing was started').wait_for()
                    rows.append({'width':width,'imported_or_reopened':True,'keyboard_submit':True,'horizontal_overflow':False})
                    context.close()
            finally:browser.close()
        projects=fixture.studio.production.list()
        assert len(projects)==1 and projects[0]['state']['status']=='planned'
        assert projects[0]['budget']=={'allowance':2,'reserved':0}
        assert not fixture.studio.jobs and fixture.studio.queue.empty()
        assert posts.count('/api/production')==1 and posts.count('/api/upload')==1
        assert not any(re.search(r'^/api/jobs$|/(start|resume|run|render|generate)$',p) for p in posts)
        assert not errors,errors
        result={'rows':rows,'project_count':1,'production_imports':1,'reference_uploads':1,'reserved':0,'jobs':0,'page_errors':errors,'live_runtime_used':False}
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
    finally:
        if http:http.shutdown();http.server_close()
        if worker:worker.join(5)
        fixture.doCleanups()
    assert worker is None or not worker.is_alive()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    run(parser.parse_args().out.resolve())
