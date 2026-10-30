"""Real Review desk HTTP/SQLite browser proof with synthetic retained images.

Uses the production Handler, serializers, review store and preview file route.
The asset index and jobs are inert fixtures. No Studio worker or model is started.
"""
import argparse
import asyncio
import copy
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import uuid
from types import MethodType
from urllib.parse import urlsplit

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from browser_ports import browser_server
from review_fixture import FixtureStudio, seed, seed_matrix, seed_comparison
from production import fingerprint
from test_server import server


def expected_stale_save_only(errors, console_errors, page_failures, review_url):
    return (not errors and len(console_errors)<=1
            and all(error.get('url')==review_url and error['text'].startswith('Failed to load resource: the server responded with a status of 400 ') for error in console_errors)
            and page_failures==[{'url':review_url,'status':400}])


def extra_output(studio, identifier):
    project=studio.production._get(identifier)
    first=studio.jobs[project['state']['attempts']['0']['job_id']]
    last=studio.jobs[project['state']['attempts'][str(len(project['plan']['stages'])-1)]['job_id']]
    original=last['outputs'][0]['asset_id'];identifier_asset=uuid.uuid4().hex
    studio.assets.paths[identifier_asset]=studio.assets.paths[original]
    studio.assets.records[identifier_asset]={**studio.assets.records[original], 'id':identifier_asset,
        'job_id':first['id'], 'output_index':1, 'filename':'second-retained-output.png'}
    first['outputs'].append({'asset_id':identifier_asset,'media_type':'image'})


async def run(out):
    from playwright.async_api import async_playwright, expect
    out.mkdir(parents=True,exist_ok=True)
    checks=[];errors=[];console_errors=[];page_failures=[];requests=[];commands=[];layout={};browser=None
    def check(name,value):
        checks.append({'name':name,'passed':bool(value)});print(name,bool(value),flush=True);assert value,name
    with tempfile.TemporaryDirectory() as temporary:
        studio=FixtureStudio(Path(temporary)/'one');identifier=seed_matrix(studio);extra_output(studio,identifier)
        legacy=seed(studio);outcomes=seed_matrix(studio)
        legacy_plan=studio.production._get(legacy)['plan'];legacy_plan.pop('axis')
        legacy_plan['sha256']=fingerprint({k:v for k,v in legacy_plan.items() if k!='sha256'})
        with studio.production.connect() as db:db.execute('UPDATE projects SET plan=? WHERE id=?',(json.dumps(legacy_plan),legacy))
        (studio.production.root/legacy/'plan.json').write_text(json.dumps(legacy_plan))
        wordings=[{'label':'Wording A','controls':{'positive':'A lantern in rain <img src=x>'}},
                  {'label':'Wording B','controls':{'positive':'Rain glows around a lantern'}}]
        ordinary={
            'wording':seed_comparison(studio,'variants',wordings),
            'guidance':seed_comparison(studio,'cfg',[1,3,5]),
            'seed':seed_comparison(studio,'seed',[9223372036854775805,9223372036854775806,9223372036854775807]),
        }
        extra_output(studio,ordinary['wording'])
        project=studio.production._get(outcomes)
        for index,status in ((0,'failed'),(1,'cancelled'),(2,'completed')):
            studio.jobs[project['state']['attempts'][str(index)]['job_id']].update(status=status,outputs=[])
        del project['state']['attempts']['3'];project['state']['status']='failed';studio.production._state(outcomes,project['state'])
        other=FixtureStudio(Path(temporary)/'two')
        for job in studio.jobs.values():
            graph=job['fixture_recipe']['graph']
            job.update(preset_id='inert-qa',controls={'seed':graph['1']['inputs']['seed']},batch_count=1,
                       created_at=1,graph=graph,submissions=[],references=[],parent_assets=[])
        studio.public=MethodType(server.Studio.public,studio);studio.export_recipe=MethodType(server.Studio.export_recipe,studio)
        before_jobs=copy.deepcopy(studio.jobs)
        project_ids=(identifier,legacy,outcomes,*ordinary.values())
        budgets={key:studio.production.get(key)['budget'] for key in project_ids}
        plans={key:copy.deepcopy(studio.production._get(key)['plan']) for key in project_ids}
        plan_bytes={key:(studio.production.root/key/'plan.json').read_bytes() for key in project_ids}

        class Base(server.Handler):
            def log_message(self,*args):pass
            def _safe_host(self):return self.headers.get('Host')=='127.0.0.1:'+str(self.server.server_port)
            def _safe_mutation(self):return self._safe_host() and self.headers.get('Origin')=='http://'+self.headers.get('Host','')
            def _body_json(self):
                payload=super()._body_json();commands.append(copy.deepcopy(payload));return payload
            def do_GET(self):
                if urlsplit(self.path).path=='/favicon.ico':self.send_response(204);self.end_headers();return
                return super().do_GET()
            def do_POST(self):
                if self.path.startswith('/api/production/') and self.path.endswith('/review'):return super().do_POST()
                self._drain_refused_body();return self._json(403,{'error':'The fixture refuses generation and unrelated writes'})
        class Handler(server.extend_handler(Base)):
            def do_GET(self):requests.append(('GET',self.path));return super().do_GET()
            def do_POST(self):requests.append(('POST',self.path));return super().do_POST()
        Handler.studio=studio
        http=browser_server(Handler);worker=threading.Thread(target=http.serve_forever,kwargs={'poll_interval':.01},daemon=True);worker.start()
        origin='http://127.0.0.1:'+str(http.server_port)
        try:
            async with async_playwright() as pw:
                browser=await pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or None,headless=True)
                context=await browser.new_context(viewport={'width':1440,'height':900},reduced_motion='reduce',accept_downloads=True)
                page=await context.new_page();page.set_default_timeout(10000)
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.on('console',lambda event:console_errors.append({'text':event.text,**event.location}) if event.type=='error' else None)
                page.on('response',lambda response:page_failures.append({'url':response.url,'status':response.status}) if response.status>=400 else None)
                page.on('dialog',lambda dialog:dialog.accept())
                async def idle():await expect(page.locator('#desk')).to_have_attribute('aria-busy','false')
                async def open_review(key):
                    await page.goto(origin+'/review.html?project='+key,timeout=25000)
                    await expect(page.locator('#open')).to_be_enabled();await page.locator('#open').click();await idle()
                    await expect(page.locator('#phase')).to_have_text('Blind review')
                async def grid():await page.locator('#presentationGrid').click();await expect(page.locator('#gridPanel')).to_be_visible()
                async def post(payload,headers=None):
                    return await context.request.post(origin+f'/api/production/{identifier}/review',data=payload,
                                                      headers={'Origin':origin,**(headers or {})})
                await open_review(identifier);check('Page load inspects and explicit Prepare opens one review',[c['action'] for c in commands]==['inspect','open'])
                await grid();blind=studio.production.reviews.inspect(identifier);topology=copy.deepcopy(blind['grid'])
                await expect(page.locator('[data-grid-candidate]')).to_have_count(7)
                await page.wait_for_function("[...document.querySelectorAll('[data-grid-candidate] canvas')].every(c=>{const p=c.getContext('2d').getImageData(192,192,1,1).data;return p[0]!==32||p[1]!==35||p[2]!==43;})")
                check('Recorded 3x2 matrix shows all seven retained outputs',len(topology['rows'])==3 and len(topology['columns'])==2 and len(topology['cells'])==6)
                content=await page.content()
                check('Blind DOM and accessible labels contain no recorded identities',not any(v in content for v in ('engine-copper','engine-indigo','engine-jade','712031','915047','original-','PRIVATE-SEED')))
                multiple=next(c for c in topology['cells'] if len(c['candidates'])==2);chosen=multiple['candidates'][1]
                target=page.locator('[data-grid-candidate="'+chosen+'"]');await target.click()
                check('Either output of a multi-output cell selects existing assessment and crop',await page.input_value('#candidate')==chosen and await page.input_value('#left')==chosen)
                await page.locator('#notes').fill('Synthetic detail: retain both outputs; this is not art acceptance.')
                await target.focus();await page.keyboard.press('w');await idle()
                check('W saves the focused assessment through the revisioned command',commands[-1]['action']=='rate' and commands[-1]['alias']==chosen and commands[-1]['expected_revision']==0 and commands[-1]['assessment']['verdict']=='needs_work')
                check('A saved shortcut retains keyboard focus',await target.evaluate('(node)=>document.activeElement===node'))
                await page.locator('[data-crop="centre"]').click();await page.locator('#saveCrop').click();await idle()
                check('Shared crop is saved once for grid and pair',studio.production.reviews.inspect(identifier)['crop']==[2500,2500,7500,7500])
                pixels=await page.evaluate("(()=>{const grid=document.querySelector('[data-grid-candidate][aria-pressed=true] canvas'),pair=document.querySelector('#leftCanvas');return [grid,pair].map(c=>Array.from(c.getContext('2d').getImageData(c.width/2,c.height/2,1,1).data));})()")
                check('Grid and selected pair render the same cropped source centre',pixels[0]==pixels[1])
                await page.locator('#notes').fill('Unsaved grid note <literal>')
                alternate=next(c['alias'] for c in blind['candidates'] if c['alias']!=chosen)
                await page.locator('[data-grid-candidate="'+alternate+'"]').click();await target.click()
                await page.locator('#presentationPair').click();await page.locator('#presentationGrid').click()
                check('Candidate and view changes retain unsaved assessment and selection',await page.input_value('#notes')=='Unsaved grid note <literal>' and await page.input_value('#candidate')==chosen)
                current=studio.production.reviews.inspect(identifier)
                studio.production.review(identifier,{'action':'view','expected_revision':current['revision'],'crop':[0,0,10000,10000],'background':'dark','reviewer':'local-agent'})
                await page.locator('#saveAssessment').click();await idle();await expect(page.locator('#message')).to_contain_text('conflict')
                check('Stale save refuses overwrite and keeps draft',await page.input_value('#notes')=='Unsaved grid note <literal>' and await page.input_value('#candidate')==chosen)
                async with page.expect_download() as pending:await page.locator('#saveDraft').click()
                await (await pending.value).save_as(out/'unsaved-review-notes.json')
                check('Downloaded recovery notes contain the exact unsaved candidate draft',json.loads((out/'unsaved-review-notes.json').read_text())['assessments'][chosen]['notes']=='Unsaved grid note <literal>')
                await page.locator('#reload').click();await idle();await expect(page.locator('#message')).to_contain_text('Saved review loaded')
                count=len(commands);await page.locator('#notes').focus();await page.keyboard.type(' K W X')
                check('Typing shortcut letters in notes never submits an assessment',len(commands)==count)
                await page.locator('#saveAssessment').click();await idle()
                await page.locator('#gridTable').evaluate("node=>node.scrollIntoView({block:'center'})")
                layout['wide']=await page.locator('#gridTable').evaluate("node=>({table:node.getBoundingClientRect().toJSON(),cells:[...node.querySelectorAll('td')].map(c=>c.getBoundingClientRect().toJSON()),headerBottom:document.querySelector('.studio-globalbar').getBoundingClientRect().bottom,viewport:{width:innerWidth,height:innerHeight}})")
                await page.screenshot(path=str(out/'grid-wide.png'))
                check('All three grid rows are visible together below the desktop toolbar',layout['wide']['table']['top']>=layout['wide']['headerBottom'] and layout['wide']['table']['bottom']<=900)
                check('Desktop matrix uses equal cell widths and heights',all(abs(c['width']-layout['wide']['cells'][0]['width'])<1 and abs(c['height']-layout['wide']['cells'][0]['height'])<1 for c in layout['wide']['cells']))
                await page.locator('#reveal').click();await idle();await expect(page.locator('#phase')).to_have_text('Settings revealed')
                revealed=studio.production.reviews.inspect(identifier)
                revealed_text=await page.locator('#gridTable').inner_text()
                check('Explicit recorded Reveal names engines and seeds without regrouping',[(c['row'],c['column'],c['candidates']) for c in revealed['grid']['cells']]==[(c['row'],c['column'],c['candidates']) for c in topology['cells']] and all(v in revealed_text for v in ('engine-copper','engine-indigo','engine-jade','712031','915047')))
                await page.reload();await idle();await expect(page.locator('#gridPanel')).to_be_visible();await expect(page.locator('#reveal')).to_be_disabled()
                check('Reload retains Reveal and saved assessments',studio.production.reviews.inspect(identifier)==revealed)
                await page.set_viewport_size({'width':390,'height':844});await page.locator('#gridPanel').scroll_into_view_if_needed()
                check('390px layout has no page overflow',await page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
                await page.locator('#presentationGrid').focus();await page.keyboard.press('Tab')
                focused=await page.evaluate('document.activeElement?.dataset.gridCandidate')
                check('Tab reaches a named grid output at 390px',focused in [c['alias'] for c in blind['candidates']])
                await page.keyboard.press('Enter');check('Narrow Enter selects an output for assessment',await page.input_value('#candidate')==focused)
                await page.keyboard.press('ArrowDown');moved=await page.evaluate('document.activeElement?.dataset.gridCandidate')
                check('Arrow navigation reaches another matrix row',moved and moved!=focused)
                check('Narrow multi-output images keep readable card widths',await page.locator('[data-grid-candidate]').evaluate_all('nodes=>nodes.every(node=>node.getBoundingClientRect().width>=88)'))
                await page.locator('#gridPanel').scroll_into_view_if_needed();await page.screenshot(path=str(out/'grid-narrow.png'))
                await target.locator('xpath=ancestor::td').scroll_into_view_if_needed();await page.screenshot(path=str(out/'grid-narrow-multiple.png'))
                for kind,key in ordinary.items():
                    await page.set_viewport_size({'width':1440,'height':900});await open_review(key);await grid()
                    saved=studio.production.reviews.inspect(key);shape=(len(saved['grid']['rows']),len(saved['grid']['columns']))
                    check(kind+' uses its saved topology',shape==({'wording':(2,1),'guidance':(3,1),'seed':(1,3)}[kind]))
                    content=await page.content()
                    check(kind+' hides wording settings and seed identities before Reveal',not any(token in content for token in ('Wording A','Wording B','lantern in rain','Guidance 1','Guidance 3','Guidance 5','9223372036854775805','9223372036854775806','9223372036854775807')))
                    await page.reload();await idle();await expect(page.locator('#gridPanel')).to_be_visible()
                    check(kind+' keeps anonymous coordinates across reload',studio.production.reviews.inspect(key)['grid']==saved['grid'])
                    retained=next(cell for cell in saved['grid']['cells'] if cell['candidates'])
                    alias=retained['candidates'][-1];button=page.locator('[data-grid-candidate="'+alias+'"]')
                    await button.click();await page.locator('#notes').fill('Retained '+kind+' review note')
                    await page.locator('#presentationPair').click();await grid()
                    check(kind+' preserves its draft through Pair and Grid',await page.input_value('#notes')=='Retained '+kind+' review note')
                    shortcut,verdict={'wording':('k','keep'),'guidance':('w','needs_work'),'seed':('x','reject')}[kind]
                    await button.focus();await page.keyboard.press(shortcut);await idle()
                    check(kind+' saves '+shortcut.upper()+' through the existing assessment',commands[-1]['action']=='rate' and commands[-1]['alias']==alias and commands[-1]['assessment']['verdict']==verdict and commands[-1]['assessment']['notes']=='Retained '+kind+' review note')
                    await page.locator('#gridTable').evaluate("node=>node.scrollIntoView({block:'center'})")
                    await page.screenshot(path=str(out/(kind+'-blind-wide.png')))
                    if kind=='wording':check('Wording grid retains all outputs in its two planned cells',len(saved['candidates'])==3 and sorted(len(cell['candidates']) for cell in saved['grid']['cells'])==[1,2])
                    await page.locator('#reveal').click();await idle();actual=studio.production.reviews.inspect(key)
                    check(kind+' Reveal preserves grouping',actual['grid']['cells']==saved['grid']['cells'])
                    for details in await page.locator('.grid-settings summary').all():await details.click()
                    text=await page.locator('#gridTable').inner_text()
                    expected={'wording':['Wording A','Wording B',wordings[0]['controls']['positive'],wordings[1]['controls']['positive'],'9223372036854775807'],
                              'guidance':['Guidance 1','Guidance 3','Guidance 5','9223372036854775807'],
                              'seed':['Shared settings','9223372036854775805','9223372036854775806','9223372036854775807']}[kind]
                    check(kind+' Reveal displays the exact recorded labels and values',all(value in text for value in expected) and await page.locator('#gridTable img').count()==0)
                    await page.locator('#gridTable').evaluate("node=>node.scrollIntoView({block:'center'})")
                    await page.screenshot(path=str(out/(kind+'-revealed-wide.png')))
                    await page.set_viewport_size({'width':390,'height':844});await page.locator('#gridPanel').scroll_into_view_if_needed()
                    check(kind+' fits the phone page while keeping images selectable',await page.evaluate('document.documentElement.scrollWidth<=innerWidth') and await page.locator('[data-grid-candidate]').count()==len(saved['candidates']))
                    await page.screenshot(path=str(out/(kind+'-revealed-narrow.png')))
                    (out/(kind+'-blind.json')).write_text(json.dumps(saved,indent=2),encoding='utf-8')
                    (out/(kind+'-revealed.json')).write_text(json.dumps(actual,indent=2),encoding='utf-8')
                await open_review(legacy);check('Unknown topology retains Pair with a concise explanation',await page.locator('#presentationGrid').is_disabled() and 'unambiguous saved settings and seeds' in await page.locator('#gridHint').inner_text())
                await open_review(outcomes);await grid();text=await page.locator('#gridTable').inner_text()
                check('Failed cancelled unstarted and empty completed positions remain visible',all(word in text for word in ('Failed','Cancelled','Not started','Completed','No retained images')))

                revision=studio.production.reviews.inspect(identifier)['revision']
                payload={'action':'rate','expected_revision':revision,'alias':chosen,'assessment':{'verdict':'keep'}}
                response=await post(payload,{'X-Studio-Creation-Privacy':'private'})
                check('Private creation scope cannot mutate a Regular review',response.status==400 and (await response.json())['code']=='private_workflow_unsupported')
                Handler.studio=other;response=await post(payload);Handler.studio=studio
                check('The same URL in another Workspace store cannot mutate the original review',response.status==400 and studio.production.reviews.inspect(identifier)['revision']==revision)
                with studio.production.connect() as db:document=studio.production.reviews._read(db,identifier)
                candidate=next(c for c in document['candidates'] if c['alias']==chosen)
                studio.assets.records[candidate['asset_id']]['trashed_at']=1;response=await post(payload);studio.assets.records[candidate['asset_id']]['trashed_at']=None
                check('Revoked source refuses assessment without changing its revision',response.status==400 and studio.production.reviews.inspect(identifier)['revision']==revision)
                preview=studio.production.root/identifier/candidate['preview_path'];raw=preview.read_bytes();preview.write_bytes(b'changed synthetic preview')
                response=await context.request.get(origin+f'/api/production/{identifier}/files/'+candidate['preview_path']);preview.write_bytes(raw)
                check('Modified preview bytes are refused by the real file route',response.status==400)
                check('No generation or unrelated write was submitted',all(path.endswith('/review') for method,path in requests if method=='POST') and studio.network_calls==0 and studio.queue.empty())
                check('Review interactions preserve jobs and generation budgets',studio.jobs==before_jobs and all(studio.production.get(key)['budget']==budget for key,budget in budgets.items()))
                check('Review interactions leave every historical plan and saved plan file unchanged',all(studio.production._get(key)['plan']==plan and (studio.production.root/key/'plan.json').read_bytes()==plan_bytes[key] for key,plan in plans.items()))
                # The deliberately stale save returns HTTP 400 through page fetch.
                # Retain its browser diagnostic; any other failure remains an error.
                expected_url=origin+f'/api/production/{identifier}/review'
                print('Browser diagnostics: '+json.dumps({'page_errors':errors,'console_errors':console_errors,'page_failures':page_failures}),flush=True)
                check('No unexpected console or JavaScript errors',expected_stale_save_only(errors,console_errors,page_failures,expected_url))
                (out/'blind-review.json').write_text(json.dumps(blind,indent=2),encoding='utf-8')
                (out/'revealed-review.json').write_text(json.dumps(revealed,indent=2),encoding='utf-8')
                (out/'frozen-plans.json').write_text(json.dumps(plans,indent=2),encoding='utf-8')
                await context.close();await browser.close();browser=None
        finally:
            Handler.studio=studio
            if browser and browser.is_connected():await browser.close()
            http.shutdown();http.server_close();worker.join(2)
            (out/'result.json').write_text(json.dumps({'scope':'Synthetic assets and jobs; real production HTTP/serializers/ReviewDesk/SQLite/previews; not generation, art acceptance or assistive technology',
                'checks':checks,'layout':layout,'page_errors':errors,'console_errors':console_errors,'page_failures':page_failures,'commands':commands,'requests':requests},indent=2),encoding='utf-8')
    return checks


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    asyncio.run(run(args.out))
