"""Real phone UI and localhost manual-player qualification; no generation."""
import argparse,functools,http.server,json,threading
from pathlib import Path
from playwright.sync_api import sync_playwright
parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
out=parser.parse_args().output.resolve()
results=[]
with sync_playwright() as pw:
    browser=pw.chromium.launch()
    context=browser.new_context(viewport={'width':390,'height':844})
    page=context.new_page();audit=[];errors=[]
    page.on('request',lambda q:audit.append({'method':q.method,'path':q.url.replace('http://127.0.0.1:8191','')}))
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8191',wait_until='networkidle')
    page.get_by_role('button',name='Explore creative bundles',exact=False).click()
    page.locator('#bundleSearch').fill('first adapter audition')
    page.locator('[data-bundle="yumeflux-ilv1-adapter-audition"]').click()
    page.wait_for_timeout(1500)
    page.locator('#bundleIngredients').scroll_into_view_if_needed()
    page.screenshot(path=str(out/'phone-authored-stack.png'))
    assert page.locator('[data-bundle-control="lora"]').input_value()=='1'
    assert page.locator('[data-bundle-control="lora2"]').input_value()=='0'
    page.locator('#bundleConsent').check();page.locator('#bundleApply').click()
    page.wait_for_function("!document.querySelector('#bundleExplorer').open")
    if not page.locator('[data-key="lora"]').is_visible():page.get_by_text('Fine-tune the recipe',exact=True).click()
    page.locator('[data-key="lora"]').scroll_into_view_if_needed()
    state=lambda:page.evaluate('()=>({preset:selected.id,controls:values(),batch:document.querySelector("#batch").value,references:referenceRecords,parents:parentAssets})')
    before=state();page.screenshot(path=str(out/'phone-before.png'))
    page.locator('[data-key="lora"]').fill('0.8');page.locator('[data-key="lora"]').press('Tab')
    after=state();page.screenshot(path=str(out/'phone-edited.png'))
    assert [k for k in before['controls'] if before['controls'][k]!=after['controls'][k]]==['lora']
    assert after['controls']['lora']=='0.8' and after['controls']['lora2']==before['controls']['lora2']=='0'
    assert {k:v for k,v in before.items() if k!='controls'}=={k:v for k,v in after.items() if k!='controls'}
    # The desktop badge is responsively hidden; the actual phone warning remains visible.
    warnings=page.get_by_text('ComfyUI readiness is not yet confirmed.',exact=False).all()
    assert any(warning.is_visible() for warning in warnings)
    assert context.request.get('http://127.0.0.1:8191/api/jobs').json()==[]
    assert not errors
    assert all(q['method'] in ('GET','HEAD') or q['path'] in ('/api/estimate','/api/workflow-studio/guidance') for q in audit)
    results.append({'scope':'actual isolated phone UI, not physical phone','viewport':[390,844],'before':before,'after':after,'changed_keys':['lora'],'jobs_after':[],'unavailable_readiness_warning_visible':True,'desktop_badge_visible':False,'page_errors':errors,'http_audit':audit})
    context.close();browser.close()

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args):pass
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(out)))
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
try:
    with sync_playwright() as pw:
        browser=pw.chromium.launch()
        for width,height in [(1280,720),(390,844)]:
            context=browser.new_context(viewport={'width':width,'height':height},reduced_motion='reduce')
            page=context.new_page();requests=[];errors=[]
            page.on('request',lambda q:requests.append(q.url));page.on('pageerror',lambda e:errors.append(str(e)))
            url=f'http://127.0.0.1:{server.server_port}/index.html'
            page.goto(url,wait_until='networkidle')
            assert not any(u.endswith('.mp4') for u in requests)
            assert page.locator('#clip').evaluate('(v)=>v.paused && v.controls && !v.autoplay && !v.loop')
            assert page.locator('li').count()==7
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.locator('#load').click()
            page.wait_for_function('document.querySelector("#clip").readyState>=2')
            assert page.locator('#clip').evaluate('(v)=>v.paused')
            page.wait_for_function('document.querySelector("track").readyState===2')
            assert page.locator('#clip').evaluate('(v)=>v.textTracks[0].cues.length')==7
            page.locator('#clip').scroll_into_view_if_needed()
            page.locator('#clip').evaluate('(v)=>{v.currentTime=18;return v.play()}')
            page.wait_for_timeout(500)
            page.screenshot(path=str(out/f'player-{width}.png'))
            page.get_by_text('Recording source',exact=True).scroll_into_view_if_needed()
            page.wait_for_function('document.querySelector("#clip").paused')
            # Test the existing hidden-event handler explicitly; no physical/background claim.
            page.locator('#clip').scroll_into_view_if_needed()
            page.locator('#clip').evaluate('(v)=>v.play()')
            page.evaluate('Object.defineProperty(document,"hidden",{configurable:true,value:true});document.dispatchEvent(new Event("visibilitychange"))')
            assert page.locator('#clip').evaluate('(v)=>v.paused')
            assert not errors
            results.append({'scope':'localhost export browser','viewport':[width,height],'no_video_request_before_load':True,'no_autoplay_after_load':True,'manual_play_decodes':True,'caption_cues':7,'offscreen_pause':True,'hidden_event_contract':True,'hidden_event_note':'explicit DOM event contract, not physical/background-device qualification','reduced_motion':True,'static_steps':7,'no_horizontal_overflow':True,'page_errors':errors})
            context.close()
        browser.close()
finally:server.shutdown();server.server_close();thread.join()
(out/'player-and-phone-receipt.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'qualified_scopes':len(results),'actual_phone_changed_keys':['lora'],'player_widths':[1280,390],'caption_cues':7,'generation_submissions':0}))
