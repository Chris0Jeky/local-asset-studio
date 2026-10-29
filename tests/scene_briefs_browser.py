"""Native shipped UI + real brief/card/asset HTTP owners with synthetic records.

No ComfyUI, model, generation, media render, or real user Workspace is opened.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import shutil
import socket
import tempfile
import threading
from types import SimpleNamespace
from urllib.parse import urlsplit

from PIL import Image
from playwright.async_api import async_playwright
from browser_ports import browser_server
import studio_browser_smoke as fixture
from test_server import server
import looks

ROOT=Path(__file__).resolve().parents[1]


async def run(out):
    out.mkdir(parents=True,exist_ok=True)
    checks=[];errors=[];requests=[];loss={'next':False};browser=None
    def check(name,value):
        checks.append({'name':name,'passed':bool(value)});print(name,bool(value),flush=True);assert value,name
    temp=tempfile.TemporaryDirectory(prefix='studio-brief-browser-');directory=Path(temp.name)
    store=server.AssetWorkspace(directory);scope=store.snapshot()['workspace_id'];images=[]
    png=directory/'synthetic.png';Image.new('RGB',(48,32),(65,105,92)).save(png)
    for index in range(16):
        images.append(store.register({'id':'brief-images','created_at':10+index,'name':'Synthetic image '+str(index),
            'outputs':[{'filename':'synthetic.png','media_type':'image'}]*16},index,png))
    private=store.register({'id':'private-canary','privacy':'private','created_at':99,
        'outputs':[{'filename':'private-canary.png','media_type':'image'}]},0,png)
    for kind,suffix in [('video','mp4'),('audio','wav'),('3d','glb')]:
        path=directory/('typed-fixture.'+suffix);path.write_bytes(b'Synthetic metadata fixture. Not media acceptance evidence.')
        store.register({'id':'brief-'+kind,'created_at':40,'outputs':[{'filename':path.name,'media_type':kind}]},0,path)
    collection=store.collection({'name':'Marsh references'})['id']
    store.collection({'name':'Empty collection'})
    preset=next(p for p in fixture.CATALOG['presets'] if p['id']=='zimage-fast')
    studio=SimpleNamespace(assets=store,root=ROOT,jobs={},catalog=lambda:fixture.CATALOG)
    look=looks.command(studio,{'action':'create','id':'look-brief-synthetic','kind':'look','name':'Synthetic brief look',
        'body':{'preset_id':preset['id'],'template':'Illustrate {scene}.','negative':'','controls':{}}})

    class Base(server.Handler):
        workspace_id=scope
        json=fixture.Handler.json
        def log_message(self,*args):pass
        def _safe_host(self):return self.headers.get('Host')=='127.0.0.1:'+str(self.server.server_port)
        def _safe_mutation(self):return self._safe_host() and self.headers.get('Origin')=='http://'+self.headers.get('Host','')
        def _json(self,status,value):
            if self.path=='/api/briefs' and status==200 and loss['next']:
                loss['next']=False;self.close_connection=True;self.connection.shutdown(socket.SHUT_RDWR);return
            return super()._json(status,value)
        def do_GET(self):
            path=urlsplit(self.path).path
            if path.startswith(('/api/briefs','/api/assets/')) or path=='/api/looks':return super().do_GET()
            if path=='/api/workspace':return self._json(200,store.snapshot(privacy=self.headers.get('X-Studio-Privacy','regular')))
            return fixture.Handler.do_GET(self)
        def do_POST(self):
            if self.path.startswith('/api/briefs'):return super().do_POST()
            if self.path in ('/api/estimate','/api/references/check'):return fixture.Handler.do_POST(self)
            return self._json(403,{'error':'This brief fixture refuses unrelated writes'})
    Base.studio=studio
    class Handler(server.extend_handler(Base)):
        def do_GET(self):requests.append(('GET',self.path));return super().do_GET()
        def do_POST(self):requests.append(('POST',self.path));return super().do_POST()
    http=browser_server(Handler);thread=threading.Thread(target=http.serve_forever,kwargs={'poll_interval':.01},daemon=True);thread.start()
    origin='http://127.0.0.1:'+str(http.server_port)
    try:
        async with async_playwright() as pw:
            browser=await pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or None,headless=True)
            context=await browser.new_context(viewport={'width':1440,'height':1080},reduced_motion='reduce')
            page=await context.new_page();page.set_default_timeout(10000);page.on('pageerror',lambda e:errors.append(str(e)));page.on('dialog',lambda d:d.accept())
            async def action(name):await page.locator('#briefsView [data-action="'+name+'"]').click()
            async def saved():await page.wait_for_function("document.querySelector('#briefSaveState')?.textContent.startsWith('Saved') && !document.querySelector('[data-action=save]').disabled")
            async def slot(key):
                await page.locator('#briefsView .brief-slots a').filter(has_text={'background':'Background','sprite':'Sprite sheet','icon':'Icon','video':'Video / scene','audio':'Audio / ambience','mesh':'3D asset'}[key]).click()
                await page.wait_for_function('key=>StudioBriefCore.route(location.hash).slot===key && !!document.querySelector("#briefIntent")',arg=key)
            await page.goto(origin+'/#briefs',timeout=25000)
            await action('new');await page.fill('#briefName','Lantern Marsh');await page.fill('#briefDirection','Quiet water, amber lanterns, cool reeds')
            await page.fill('#briefIntent','A wide marsh crossing');await page.fill('#briefCriteria','A clear path across the foreground')
            await action('save');await saved();identifier=await page.evaluate('StudioBriefCore.route(location.hash).id')
            check('Brief is a real revisioned Workspace card',store.card(identifier)['body']['direction']=='Quiet water, amber lanterns, cool reeds')
            await action('picker');await page.wait_for_selector('[data-candidate]')
            check('Picker uses a bounded real asset page and excludes private records',await page.locator('[data-candidate]').count()==12 and not await page.locator('[data-candidate="'+private+'"]').count())
            await action('next');await page.wait_for_function('!!StudioBriefCore.route(location.hash).cursor && document.querySelectorAll("[data-candidate]").length===4')
            page_two=page.url;candidate=await page.locator('[data-candidate]').first.get_attribute('data-candidate')
            await page.go_back();await page.wait_for_function('!StudioBriefCore.route(location.hash).cursor && document.querySelectorAll("[data-candidate]").length===12')
            await page.go_forward();await page.wait_for_function('document.querySelectorAll("[data-candidate]").length===4')
            check('Browser history restores the candidate page and slot words',page.url==page_two and await page.input_value('#briefIntent')=='A wide marsh crossing')
            await page.locator('[data-candidate]').first.click();await action('save');await saved()
            check('Selection stores immutable ID hash and metadata revision',store.card(identifier)['body']['slots']['background']['selected']['asset_id']==candidate)
            await action('picker');await page.wait_for_selector('[data-candidate]');await page.locator('[data-candidate]').first.click();await action('save');await saved()
            await action('restore');await page.wait_for_function("document.querySelector('#briefStatus').textContent.includes('Previous candidate restored')");await action('save');await saved()
            check('Replacement can explicitly restore the prior real candidate',store.card(identifier)['body']['slots']['background']['selected']['asset_id']==candidate)
            for key in ('sprite','icon','video','audio','mesh'):
                await slot(key);await page.fill('#briefIntent','Synthetic '+key+' role');await action('picker');await page.wait_for_selector('[data-candidate]');await page.locator('[data-candidate]').first.click()
            await action('save');await saved()
            check('All six typed slots save real records',all(s['selected'] for s in store.card(identifier)['body']['slots'].values()))
            await action('new');await page.fill('#briefName','Recoverable new brief');await page.fill('#briefDirection','Keep this unsaved new brief reachable')
            draft_id=await page.evaluate('StudioBriefCore.route(location.hash).id')
            await page.select_option('#briefSelect',identifier);await page.wait_for_function('id=>StudioBriefCore.route(location.hash).id===id && document.querySelector("#briefName")?.value==="Lantern Marsh"',arg=identifier)
            await page.select_option('#briefSelect','');await page.reload();await page.wait_for_selector('#briefSelect')
            await page.select_option('#briefSelect',draft_id);await page.wait_for_selector('#briefDirection')
            check('Unsaved new brief remains discoverable after switching and reload',await page.input_value('#briefDirection')=='Keep this unsaved new brief reachable')
            await page.select_option('#briefCollection',collection);await action('picker');await page.wait_for_function('document.querySelector(".brief-picker")?.textContent.includes("No active candidates match")')
            check('Real empty collection shows an honest empty picker',not await page.locator('[data-candidate]').count())
            await page.select_option('#briefSelect',identifier);await page.wait_for_function('document.querySelector("#briefName")?.value==="Lantern Marsh"')
            await page.screenshot(path=str(out/'brief-wide.png'),full_page=True)
            await page.fill('#briefDirection','Unsaved wording survives navigation and reload')
            await page.evaluate("document.dispatchEvent(new CustomEvent('studio:navigate',{detail:'assets'}))")
            await page.go_back();await page.wait_for_selector('#briefDirection');await page.reload();await page.wait_for_selector('#briefDirection')
            check('Unsaved wording survives native reload and app navigation',await page.input_value('#briefDirection')=='Unsaved wording survives navigation and reload')
            # A real second tab wins the revision. The first must keep its own draft.
            peer=await context.new_page();peer.on('dialog',lambda d:d.accept());await peer.goto(origin+'/#briefs?id='+identifier)
            await peer.fill('#briefDirection','Second tab wins');await peer.locator('[data-action=save]').click()
            await peer.wait_for_function("document.querySelector('#briefSaveState').textContent.startsWith('Saved')")
            await action('save');await page.wait_for_function("document.querySelector('#briefStatus').textContent.includes('changed since')")
            check('Two-tab conflict retains both winner and losing draft',store.card(identifier)['body']['direction']=='Second tab wins' and await page.input_value('#briefDirection')=='Unsaved wording survives navigation and reload')
            await action('reload');await saved();await peer.close()
            await page.fill('#briefDirection','Lost-response wording');loss['next']=True;before=len([r for r in requests if r==('POST','/api/briefs')])
            await action('save');await page.wait_for_function("document.querySelector('#briefStatus').textContent.includes('retained')")
            check('Lost response never auto-retries a committed write',len([r for r in requests if r==('POST','/api/briefs')])==before+1 and store.card(identifier)['body']['direction']=='Lost-response wording')
            await page.reload();await saved();check('Reload reconciles a committed response loss',await page.input_value('#briefDirection')=='Lost-response wording')
            await slot('background');await page.select_option('#briefLook',look['id']);await action('prepare')
            await page.wait_for_function("!document.querySelector('#createView').hidden")
            check('Image preparation uses the existing editor adapter without a job', 'Lost-response wording' in await page.input_value('#positive') and not any(p=='/api/jobs' for m,p in requests if m=='POST'))
            await page.locator('.brief-return a').click();await page.wait_for_selector('[data-candidate]')
            check('Explicit return preserves brief and slot and opens real candidates',await page.evaluate('StudioBriefCore.route(location.hash).id')==identifier and await page.evaluate('StudioBriefCore.route(location.hash).slot')=='background')
            await action('closePicker');await slot('video');await action('prepare');await page.wait_for_url('**/av.html?*')
            await page.locator('.brief-return a').wait_for(state='visible')
            check('Scene handoff reaches the existing source owner without creating a plan',await page.locator('.brief-return a').count()==1 and not any(p=='/api/av' for m,p in requests if m=='POST'))
            await page.locator('.brief-return a').click();await page.wait_for_selector('#briefIntent')
            await action('closePicker');await slot('background')
            selected=store.card(identifier)['body']['slots']['background']['selected']['asset_id']
            with store.connection() as db:db.execute('UPDATE assets SET metadata_revision=metadata_revision+1 WHERE id=?',(selected,))
            await action('reload');await page.wait_for_function("document.querySelector('.brief-candidate h3').textContent==='Saved candidate unavailable'")
            await page.fill('#briefCriteria','Retain unavailable snapshot while editing');await action('save');await saved()
            check('Stale source is explicit and does not destroy editable wording',store.card(identifier)['body']['slots']['background']['criteria']=='Retain unavailable snapshot while editing')
            await page.set_viewport_size({'width':390,'height':844});await page.screenshot(path=str(out/'brief-narrow.png'),full_page=True)
            check('Narrow layout has no horizontal overflow',await page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            await page.locator('#briefName').focus();await page.keyboard.press('Tab');check('Keyboard follows named editable fields',await page.locator('#briefDirection').evaluate('(el)=>el===document.activeElement'))
            key='studio.brief-draft.v1:'+scope+':'+identifier
            await page.evaluate('key=>sessionStorage.setItem(key,"{corrupt retained bytes")',key);await page.reload();await page.wait_for_selector('[data-action=downloadRecovery]')
            check('Corrupt recovery stays intact and blocks overwriting',await page.evaluate('key=>sessionStorage.getItem(key)',key)=='{corrupt retained bytes' and await page.locator('[data-action=save]').is_disabled())
            await action('discardRecovery');await page.wait_for_selector('#briefDirection')
            await page.evaluate("()=>{window.originalBriefSet=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(k.startsWith('studio.brief-draft'))throw new DOMException('Quota');return window.originalBriefSet.call(this,k,v)}}")
            await page.fill('#briefDirection','Memory-only draft after quota failure')
            check('Storage denial retains memory and exposes draft download',await page.input_value('#briefDirection')=='Memory-only draft after quota failure' and await page.locator('#briefStatus').inner_text()=='Browser recovery could not be stored. Keep this tab open, save to Workspace or download your draft.')
            await page.evaluate('()=>{Storage.prototype.setItem=window.originalBriefSet}')
            await page.evaluate("StudioPrivacy.setScope('private')")
            check('Private scope clears brief words from the view','Memory-only draft' not in await page.locator('#briefsView').inner_text() and not await page.locator('#briefDirection').count())
            await page.evaluate("StudioPrivacy.setScope('regular')");await page.wait_for_selector('#briefDirection')
            check('Returning to Regular preserves the regular draft',await page.input_value('#briefDirection')=='Memory-only draft after quota failure')
            check('No runtime generation render or asset review writes occurred',not any(m=='POST' and (p in ('/api/jobs','/api/av','/api/assets/update','/api/voice-baseline') or p.startswith('/api/production')) for m,p in requests))
            check('No browser JavaScript errors',not errors)
            await context.close();await browser.close();browser=None
    finally:
        if browser:await browser.close()
        http.shutdown();http.server_close();thread.join(timeout=10)
        (out/'result.json').write_text(json.dumps({'checks':checks,'browser_errors':errors,'requests':requests,
            'scope':'Synthetic real Workspace records; no runtime, generation, render, licence or art acceptance.'},indent=2),encoding='utf-8')
        temp.cleanup()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    asyncio.run(run(args.out))
