"""Actual Studio HTTP/SQLite/Library flow in Chromium with synthetic native outputs.

No --base-url and no native executables: this owns its temporary fixture. Screenshots
prove page behavior, never Blender compatibility, geometry quality or art acceptance.
"""
import json
from pathlib import Path
import tempfile
import threading
from unittest.mock import patch
from urllib.parse import urlsplit

from browser_ports import BoundPortGuard, browser_server, evidence_screenshot
from test_procedural_studio import configured_studio, fake_build, procedural, server
import studio_browser_smoke as fixture

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.runtime/procedural-browser'


def settle_layout(page, width):
    page.wait_for_function('width=>innerWidth===width',arg=width,timeout=5000)
    page.evaluate('''() => new Promise((resolve,reject) => {
        const deadline=setTimeout(()=>reject(Error('Viewport layout did not settle')),5000);
        requestAnimationFrame(()=>requestAnimationFrame(()=>{clearTimeout(deadline);resolve();}));
    })''')


def capture_full_page(page, name):
    page.evaluate('scrollTo(0,0)')
    page.wait_for_function('scrollY===0',timeout=5000)
    settle_layout(page,page.viewport_size['width'])
    evidence_screenshot(page,path=str(OUT/name),full_page=True)


def main():
    from playwright.sync_api import sync_playwright
    OUT.mkdir(parents=True,exist_ok=True)
    report={'kind':'synthetic native fixture, not native runtime proof','checks':[],'page_errors':[],'posts':[]}
    def check(condition,message):
        report['checks'].append({'passed':bool(condition),'message':message})
        if not condition:raise AssertionError(message)
    with tempfile.TemporaryDirectory() as temporary:
        studio,validator=configured_studio(Path(temporary));configured=dict(studio.config)
        studio.config={}
        actual=server.extend_handler(server.Handler)
        class Handler(BoundPortGuard,actual):
            def log_message(self,*args):pass
            def json(self,value,status=200):return self._json(status,value)
            def do_GET(self):
                path=urlsplit(self.path).path
                if path.startswith(('/api/procedural','/api/production','/api/assets','/api/image','/api/workspace','/api/collections','/api/jobs','/api/identity')):
                    return super().do_GET()
                return fixture.Handler.do_GET(self)
            def do_POST(self):
                report['posts'].append(self.path)
                if self.path.startswith(('/api/procedural','/api/production','/api/assets')):return super().do_POST()
                if self.path=='/api/estimate':return fixture.Handler.do_POST(self)
                self._drain_refused_body();return self._json(400,{'error':'Unexpected fixture mutation'})
        Handler.studio=studio
        http=browser_server(Handler);thread=threading.Thread(target=http.serve_forever,kwargs={'poll_interval':.01},daemon=True);thread.start()
        origin=f'http://127.0.0.1:{http.server_port}'
        try:
            with patch.object(procedural,'VALIDATOR_DIR',validator),patch.object(procedural.factory,'build',side_effect=fake_build) as build,sync_playwright() as playwright:
                browser=playwright.chromium.launch(headless=True)
                try:
                    context=browser.new_context(viewport={'width':1440,'height':1050})
                    page=context.new_page();page.on('pageerror',lambda error:report['page_errors'].append(str(error)))
                    page.goto(origin+'/procedural.html');page.wait_for_function('document.querySelectorAll("#proceduralGenerator option").length===8')
                    check(page.locator('#studioPageTitle').inner_text()=='Procedural assets','Shared shell identifies the page')
                    check(page.locator('#proceduralPrepare').is_disabled(),'Missing runtime disables preparation')
                    check('Blender 5.4' in page.locator('#proceduralRuntime').inner_text(),'Required runtime and readiness limits are visible')
                    check(build.call_count==0 and not report['posts'],'Opening the page does not prepare or execute anything')
                    capture_full_page(page,'missing-runtime-desktop.png')
                    page.locator('#proceduralName').fill('Fixture crate')
                    for generator,spec in procedural.catalog(studio)['generators'].items():
                        page.locator('#proceduralGenerator').select_option(generator)
                        check(page.locator('#proceduralParams input').count()==len(spec['params']),'Fields follow the '+generator+' schema')
                    page.locator('#proceduralGenerator').select_option('room_kit')
                    page.locator('#proceduralParam-width').fill('2.4');page.locator('#proceduralParam-window_width').fill('2.4')
                    page.locator('#proceduralCheck').click();page.wait_for_function('document.querySelector("#proceduralStatus").classList.contains("error")')
                    check(not studio.production.list(),'Invalid fit creates no project')
                    page.locator('#proceduralGenerator').select_option('prop');page.locator('#proceduralParam-kind').fill('1')
                    page.locator('#proceduralCheck').click();page.wait_for_function('document.querySelector("#proceduralStatus").textContent.includes("Settings are valid")')
                    check(build.call_count==0,'Parameter validation does not execute the factory')
                    page.set_viewport_size({'width':390,'height':844})
                    settle_layout(page,390)
                    check(page.evaluate('document.documentElement.scrollWidth<=innerWidth'),'Form fits a 390 px viewport')
                    capture_full_page(page,'settings-mobile.png')
                    evidence_screenshot(page,path=str(OUT/'settings-mobile-viewport.png'))
                    studio.config=configured
                    page.locator('#proceduralRefresh').click();page.wait_for_function('!document.querySelector("#proceduralPrepare").disabled')
                    check(page.locator('#proceduralParam-kind').input_value()=='1','Setup refresh preserves the typed draft')
                    page.locator('#proceduralPrepare').click();page.wait_for_selector('#proceduralPrepared a.primary')
                    project=studio.production.list()[0];identifier=project['id']
                    check(project['state']['status']=='planned' and studio.queue.empty() and build.call_count==0,'Preparing materializes one plan without execution')
                    capture_full_page(page,'prepared-mobile.png')
                    page.set_viewport_size({'width':1440,'height':1050});page.locator('#proceduralPrepared a.primary').click()
                    page.wait_for_selector('[data-project-action="start"]')
                    check(page.locator('[data-project-action="start"]').inner_text()=='Start build','The linked coordinator names the explicit action')
                    capture_full_page(page,'plan-desktop.png')
                    page.locator('[data-project-action="start"]').click();page.wait_for_function('document.querySelector("#productionDetail").textContent.includes("queued")')
                    check(studio.queue.get_nowait()==('production',identifier),'Start uses the existing Production queue')
                    studio.production.run(identifier) # Deterministic fixture worker tick; factory remains patched.
                    page.evaluate('refreshProduction(true)');page.wait_for_selector('[data-candidate-open]')
                    check(build.call_count==1,'Exactly one explicitly started factory invocation')
                    check('Godot import was not checked' in page.locator('#productionDetail').inner_text(),'Successful software flow still shows incomplete engine verification')
                    check(page.locator('.native-model').get_attribute('autoplay') is None,'Static procedural asset is not presented as an animated chest')
                    capture_full_page(page,'completed-fixture-desktop.png')
                    page.locator('[data-candidate-open]').click();page.wait_for_selector('#assetDialog[open]')
                    check(page.locator('#assetTitle').input_value().startswith('Fixture crate'),'Completed model opens its real Library record')
                    check(len(studio.assets.snapshot()['assets'])==4,'Three LODs and the inspection sheet are registered')
                    check(not studio.requests,'No ComfyUI request was made')
                    check(not report['page_errors'],'No browser page exceptions')
                    check(report['posts'].count('/api/procedural')==1,'One prepare request')
                    check(report['posts'].count('/api/production/'+identifier+'/start')==1,'One explicit Start request')
                    check(not any(p.startswith('/api/jobs') for p in report['posts']),'No image generation route was used')
                finally:browser.close()
        finally:
            http.shutdown();http.server_close();thread.join(3)
            (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('Procedural browser fixture passed: '+str(len(report['checks']))+' checks. Native runtime proof remains outstanding.')


if __name__=='__main__':main()
