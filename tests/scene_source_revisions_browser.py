"""Real scene/brief HTTP owners, disposable media and one explicit CPU render."""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import threading
import time
from urllib.parse import urlsplit
import wave

from playwright.async_api import async_playwright
from browser_ports import browser_server, BoundPortGuard
import studio_browser_smoke as shell
from test_native_export_history import NativeExportHistoryTests, server
from test_server import rgba_png


async def run(out):
    out.mkdir(parents=True,exist_ok=False)
    checks=[];requests=[];errors=[];network=[];actions=[];context=None;http=None;thread=None
    case=NativeExportHistoryTests();case.setUp();studio=case.studio;store=studio.assets;scenes=studio.production.av
    loss={'armed':False,'observed':False};started=time.monotonic()
    def check(name,condition,detail=None):
        checks.append({'name':name,'passed':bool(condition),'detail':detail})
        print(name,bool(condition),flush=True)
        assert condition,name
    def register(path,kind):
        identifier=store.register({'id':'fixture-'+path.stem,'created_at':time.time(),
            'outputs':[{'filename':path.name,'media_type':kind}]},0,path)
        return store.get(identifier)
    def wav(name,samples):
        path=case.root/name
        with wave.open(str(path),'wb') as stream:
            stream.setparams((1,2,48000,0,'NONE',''));stream.writeframes(b'\0\0'*samples)
        return register(path,'audio')
    try:
        studio.config.update({name:shutil.which(name) for name in ('ffmpeg','ffprobe')})
        assert all(studio.config[name] for name in ('ffmpeg','ffprobe')),'Installed media tools required'
        audio=wav('original-audio.wav',96000)
        scene=scenes.create({'action':'create','name':'Synthetic opening scene','asset_ids':[case.asset['id'],audio['id']],
                            'frames_per_shot':24,'size':[160,96]})
        scene=scenes.command(scene['id'],{'action':'add','expected_revision':0,'section':'overlays','asset_key':'source0'})
        scene=scenes.command(scene['id'],{'action':'edit','expected_revision':1,'section':'audio','clip_id':'audio0',
            'changes':{'gain_db':-6,'fade_in':2400,'fade_out':2400}})
        baseline=json.loads(json.dumps(scene));identifier=scene['id'];scope=case.workspace
        later=studio.import_image('later-background.png','image/png',rgba_png(64,48))['asset']
        later_audio=wav('later-audio.wav',144000)
        clip=case.root/'later-video.mp4'
        subprocess.run([studio.config['ffmpeg'],'-v','error','-f','lavfi','-i','color=c=0x537f83:s=160x96:r=24:d=1',
            '-an','-c:v','libx264','-pix_fmt','yuv420p',str(clip)],check=True,timeout=30)
        later_video=register(clip,'video')
        slots={key:{'intent':'','criteria':'','selected':None,'previous':None}
               for key in ('background','sprite','icon','video','audio','mesh')}
        for key,asset in (('background',case.asset),('audio',audio)):
            slots[key]['selected']={name:asset[name] for name in ('sha256','metadata_revision')}
            slots[key]['selected']['asset_id']=asset['id']
        brief=store.card_command({'action':'create','id':'scene-source-journey','kind':'brief','name':'Synthetic scene brief',
            'body':{'format':'studio.scene-brief/v1','workspace_id':scope,'collection_id':None,
                    'direction':'Assemble the registered fixture media.','slots':slots}})
        for mocked in reversed(case.fixture.patches):mocked.stop()

        class Base(BoundPortGuard,server.Handler):
            json=shell.Handler.json
            def log_message(self,*_):pass
            def _body_json(self,*args,**kwargs):
                body=super()._body_json(*args,**kwargs)
                if hasattr(self,'request_record'):self.request_record['body']=body
                return body
            def _json(self,status,value):
                if hasattr(self,'request_record'):self.request_record['status']=status
                if loss['armed'] and status==200 and self.path=='/api/av/'+identifier and self.request_record.get('body',{}).get('action')=='replace_source':
                    loss.update(armed=False,observed=True);self.close_connection=True
                    self.connection.shutdown(socket.SHUT_RDWR);return
                return super()._json(status,value)
            def do_GET(self):
                path=urlsplit(self.path).path
                if path=='/api/looks':return self._json(200,{'looks':[]})
                if path.startswith(('/api/av','/api/assets/','/api/workspace','/api/briefs','/api/production')):
                    return super().do_GET()
                return shell.Handler.do_GET(self)
            def do_POST(self):
                if self.path in ('/api/av/'+identifier,'/api/assets/selection') or self.path.startswith('/api/briefs'):
                    return super().do_POST()
                return self._json(403,{'error':'This fixture permits only the named scene and brief workflow'})
        Base.studio=studio
        class Handler(server.extend_handler(Base)):
            def do_GET(self):
                self.request_record={'method':'GET','path':self.path};requests.append(self.request_record)
                return super().do_GET()
            def do_POST(self):
                self.request_record={'method':'POST','path':self.path};requests.append(self.request_record)
                return super().do_POST()
        http=browser_server(Handler);thread=threading.Thread(target=http.serve_forever,kwargs={'poll_interval':.01},daemon=True);thread.start()
        origin='http://127.0.0.1:'+str(http.server_port)
        extension=out/'zoom-extension';extension.mkdir()
        (extension/'manifest.json').write_text(json.dumps({'manifest_version':3,'name':'Synthetic scene zoom proof','version':'1.0',
            'permissions':['tabs'],'background':{'service_worker':'worker.js'}}),encoding='utf-8')
        (extension/'worker.js').write_text('chrome.runtime.onInstalled.addListener(()=>{});\nsetInterval(()=>chrome.runtime.getPlatformInfo(),20000);\n',encoding='utf-8')
        async with async_playwright() as pw:
            context=await pw.chromium.launch_persistent_context(str(out/'browser-profile'),channel='chromium',headless=True,
                executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or None,
                args=[f'--disable-extensions-except={extension}',f'--load-extension={extension}'],
                viewport={'width':1440,'height':1000},reduced_motion='reduce')
            zoom=context.service_workers[0] if context.service_workers else await context.wait_for_event('serviceworker',timeout=15000)
            await context.route('**/*',lambda route:route.continue_() if route.request.url.startswith(origin+'/') else route.abort())
            page=await context.new_page();page.set_default_timeout(10000)
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.on('requestfailed',lambda request:network.append({'url':request.url,'method':request.method,'failure':request.failure}))
            async def click(selector):
                actions.append({'action':'click','target':selector});await page.locator(selector).click()
            async def key(selector,press):
                actions.append({'action':'key','target':selector,'key':press});await page.locator(selector).press(press)
            async def saved_revision(revision):
                await page.wait_for_function('revision=>!avMutationBusy&&avDocument?.revision===revision',arg=revision)
                return scenes.inspect(identifier)
            async def choose(section,asset,clip_id=None,keyboard=False):
                selector='[data-workspace-source="'+section+'"]'+('[data-replace="'+clip_id+'"]' if clip_id else ':not([data-replace])')
                if keyboard:
                    await page.locator(selector).focus();await key(selector,'Enter')
                else:await click(selector)
                await page.wait_for_function('!avMutationBusy&&!!avSourceChoice')
                if await page.input_value('#sceneSourceKind')!=asset['media_type']:
                    await page.select_option('#sceneSourceKind',asset['media_type']);await page.wait_for_function('!avMutationBusy')
                await page.fill('#sceneSourceSearch',asset['filename']);actions.append({'action':'type','target':'#sceneSourceSearch'})
                await key('#sceneSourceSearch','Enter');await page.wait_for_function('!avMutationBusy&&avSourceItems.length>0')
                radio='#sceneSourceList input[value="'+asset['id']+'"]'
                await page.locator(radio).focus();await key(radio,'Space')
                check('Selected exact Workspace candidate',await page.locator(radio).is_checked())
            await page.goto(origin+'/#briefs?id='+brief['id']+'&slot=video')
            await page.wait_for_selector('#briefsView [data-action="prepare"]')
            await click('#briefsView [data-action="prepare"]')
            await page.wait_for_url('**/av.html?**');await saved_revision(2)
            await page.locator('.brief-return a').wait_for()
            check('Brief preparation opens existing scene without creating another',len(scenes.list()['projects'])==1 and len(await page.locator('.brief-return a').all())==1)
            before_posts=len([r for r in requests if r['method']=='POST'])
            field='[data-section="shots"][data-clip="shot0"][data-field="frames"]'
            await page.fill(field,'23')
            check('Unsaved fields block source changes',await page.locator('[data-replace="shot0"]').is_disabled())
            await click('#documentReload')
            check('Reload retains unsaved field',await page.input_value(field)=='23')
            await click('[data-discard-drafts]')
            check('Discard restores saved field without a write',await page.input_value(field)=='24' and len([r for r in requests if r['method']=='POST'])==before_posts)
            await choose('shots',later,'shot0',keyboard=True)
            await page.screenshot(path=str(out/'wide-source-picker.png'),full_page=True)
            await key('#sceneSourceApply','Enter');changed=await saved_revision(3)
            check('Replacement preserves shot timing and unrelated clips',
                {k:v for k,v in changed['project']['shots'][0].items() if k!='asset'}=={k:v for k,v in baseline['project']['shots'][0].items() if k!='asset'}
                and changed['project']['audio']==baseline['project']['audio'] and changed['project']['overlays']==baseline['project']['overlays'])
            check('Focus follows saved clip',await page.locator('[data-select-clip="shots:shot0"] h4').evaluate('(n)=>n===document.activeElement'))
            await choose('shots',later_video)
            await click('#sceneSourceApply');changed=await saved_revision(4)
            check('New video is added to the same scene',len(changed['project']['shots'])==2 and changed['timing']['frames']==48 and len(scenes.list()['projects'])==1)
            await choose('audio',later_audio,'audio0')
            await click('#sceneSourceApply');changed=await saved_revision(5)
            revision_five=json.loads(json.dumps(changed['project']))
            check('New audio preserves trim gain and fades',
                {k:v for k,v in changed['project']['audio'][0].items() if k!='asset'}=={k:v for k,v in baseline['project']['audio'][0].items() if k!='asset'})
            await page.reload();await saved_revision(5)
            check('Reload and Continue recognize the later sources',scenes.continue_observation(scope)['plan']['revision']==5)
            await page.locator('.av-history').filter(has=page.locator('summary',has_text='Revision history')).locator('summary').click()
            await click('[data-restore="2"]');restored=await saved_revision(6)
            check('Restore keeps original arrangement and later input files',restored['project']==baseline['project'] and len(list((scenes.directory(identifier)/'inputs').iterdir()))==5)
            await page.locator('.av-history').filter(has=page.locator('summary',has_text='Revision history')).locator('summary').click()
            await click('[data-restore="5"]');changed=await saved_revision(7)
            check('Later source references survive restore',changed['project']==revision_five and scenes.continue_observation(scope)['plan']['revision']==7)
            await choose('shots',later,'shot0')
            scenes.command(identifier,{'action':'edit','expected_revision':7,'section':'shots','clip_id':'shot0','changes':{'frames':23}})
            await click('#sceneSourceApply')
            await page.wait_for_function('!avMutationBusy&&avSourceUnconfirmed')
            check('Conflict retains selected candidate and performs no source edit',await page.locator('#sceneSourceList input:checked').count()==1 and scenes.inspect(identifier)['revision']==8)
            await click('#sceneSourceCancel');await click('#documentReload');await saved_revision(8)
            await choose('shots',later,'shot0');loss['armed']=True
            await click('#sceneSourceApply');await page.wait_for_function('!avMutationBusy&&avSourceUnconfirmed')
            source_posts=len([r for r in requests if r.get('body',{}).get('action') in ('add_source','replace_source')])
            check('Lost reply retains candidate and disables retry',loss['observed'] and await page.locator('#sceneSourceApply').is_disabled() and await page.locator('#sceneSourceList input:checked').count()==1)
            await page.wait_for_timeout(100)
            check('Lost reply submits once',len([r for r in requests if r.get('body',{}).get('action') in ('add_source','replace_source')])==source_posts and scenes.inspect(identifier)['revision']==9)
            await click('#sceneSourceCancel');await click('#documentReload');await saved_revision(9)
            await page.set_viewport_size({'width':390,'height':844})
            await choose('audio',later_audio,'audio0')
            check('Narrow source chooser stays within viewport',await page.locator('#sceneSourceDialog').evaluate('(n)=>n.scrollWidth<=n.clientWidth+1&&n.getBoundingClientRect().right<=innerWidth+1'))
            await page.screenshot(path=str(out/'narrow-source-picker.png'),full_page=True)
            await click('#sceneSourceCancel');await page.set_viewport_size({'width':1280,'height':1000})
            await choose('shots',later,'shot0')
            before_zoom=await page.evaluate('({width:innerWidth,dpr:devicePixelRatio,css:getComputedStyle(document.documentElement).zoom})')
            zoom_receipt=await zoom.evaluate("""async url=>{const tab=(await chrome.tabs.query({})).find(t=>t.url===url);
                if(!tab)throw Error('Fixture tab missing');await chrome.tabs.setZoomSettings(tab.id,{mode:'automatic',scope:'per-tab'});
                await chrome.tabs.setZoom(tab.id,2);return {id:tab.id,zoom:await chrome.tabs.getZoom(tab.id)};}""",page.url)
            await page.wait_for_function('dpr=>devicePixelRatio>dpr*1.9',arg=before_zoom['dpr'])
            after_zoom=await page.evaluate('({width:innerWidth,dpr:devicePixelRatio,css:getComputedStyle(document.documentElement).zoom})')
            check('Native browser 200 percent zoom',zoom_receipt['zoom']==2 and after_zoom['width']<=before_zoom['width']/2+1 and after_zoom['css']=='1',{'before':before_zoom,'after':after_zoom,'browser':zoom_receipt})
            for _ in range(35):
                if await page.locator('#sceneSourceCancel').evaluate('(n)=>n===document.activeElement'):break
                await page.keyboard.press('Tab')
            check('Cancel reachable by keyboard at 200 percent',await page.locator('#sceneSourceCancel').evaluate('(n)=>n===document.activeElement&&n.getBoundingClientRect().right<=innerWidth+1'))
            await page.screenshot(path=str(out/'browser-200-source-picker.png'),full_page=True)
            await key('#sceneSourceCancel','Enter');await zoom.evaluate('id=>chrome.tabs.setZoom(id,1)',zoom_receipt['id'])
            await page.wait_for_function('dpr=>Math.abs(devicePixelRatio-dpr)<.01',arg=before_zoom['dpr'])
            check('No render or generation was queued by source operations',studio.queue.empty() and not studio.requests)
            await click('[data-render-action="render"]')
            await page.wait_for_function('avDocument?.render?.status==="queued"&&!avMutationBusy')
            action,queued_id=studio.queue.get_nowait()
            check('Render is the explicit existing production queue action',action=='production' and queued_id==identifier)
            await asyncio.to_thread(studio.production.run,identifier)
            await page.wait_for_function('avDocument?.render?.status==="completed"',timeout=60000)
            final=scenes.inspect(identifier);attempt=final['render']['id'];job=studio.jobs[attempt]
            check('Real renderer completed revision nine',final['render']['status']=='completed' and final['render']['preview_revision']==9 and not final['render']['stale'])
            receipt=job['native_recipe']['receipt']
            decoded=next(stream['nb_read_frames'] for stream in receipt['probe']['streams'] if stream['codec_type']=='video')
            check('Decoded 47 frames and 94000 PCM samples',receipt['frames_expected']==47 and decoded=='47' and receipt['audio_qc']['samples']==94000,receipt)
            video_output=next(output for output in job['outputs'] if output['media_type']=='video')
            published=store.get(video_output['asset_id']);published_path=store.file(published['id'])
            check('Published Workspace bytes and lineage match',hashlib.sha256(published_path.read_bytes()).hexdigest()==published['sha256']
                and set(published['lineage'])=={source['asset_id'] for source in final['sources']})
            await page.screenshot(path=str(out/'wide-rendered-scene.png'),full_page=True)
            await click('.brief-return a');await page.wait_for_selector('[data-candidate="'+published['id']+'"]')
            await click('[data-candidate="'+published['id']+'"]');await click('#briefsView [data-action="save"]')
            await page.wait_for_function('document.querySelector("#briefSaveState")?.textContent.startsWith("Saved")&&!document.querySelector("[data-action=save]").disabled')
            selected=store.card(brief['id'])['body']['slots']['video']['selected']
            check('Real rendered candidate returns to the brief',selected['asset_id']==published['id'] and selected['sha256']==published['sha256'])
            check('Candidate choice is not artistic acceptance',store.get(published['id'])['review']=='unreviewed')
            check('Exactly one explicit render and no scene recreation',len([r for r in requests if r.get('body',{}).get('action')=='render'])==1 and not any(r['method']=='POST' and r['path']=='/api/av' for r in requests))
            check('No generation requests or unexpected browser errors',not studio.requests and not errors)
            unexpected=[entry for entry in network if not (entry['method']=='POST' and entry['url']==origin+'/api/av/'+identifier)
                and not (entry['method']=='GET' and entry['failure']=='net::ERR_ABORTED' and ('/sources/' in entry['url'] or '/file' in entry['url']))]
            check('Only lost acknowledgment and cancelled media reads failed on the network',bool(network) and not unexpected,network)
            await page.screenshot(path=str(out/'brief-return-candidate.png'),full_page=True)
            await context.close();context=None
    finally:
        if context:await context.close()
        if http:http.shutdown();http.server_close()
        if thread:thread.join(10)
        (out/'result.json').write_text(json.dumps({'checks':checks,'browser_errors':errors,'network_failures':network,'requests':requests,
            'actions':actions,'seconds':time.monotonic()-started,'scope':'Synthetic real HTTP/SQLite and one explicit actual CPU render; no neural generation or owner acceptance.'},indent=2),encoding='utf-8')
        shutil.copytree(case.root,out/'workspace',ignore=shutil.ignore_patterns('__pycache__'))
        case.doCleanups()
        if thread and thread.is_alive():raise AssertionError('Scene fixture HTTP thread survived')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    asyncio.run(run(parser.parse_args().out.resolve()))
