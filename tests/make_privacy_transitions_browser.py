"""Native Make owners: privacy transitions, finder intent and held saved-look replies.

Disposable browser storage and synthetic records only; never ComfyUI or user media.
Saved-look POST replies are fixture-crafted; all GETs use the existing HTTP fixture.
Run: python tests/make_privacy_transitions_browser.py
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import shutil
import threading
import unittest

from playwright.sync_api import sync_playwright
from browser_ports import browser_server
import make_goals_browser as fixture

TEXT = 'Synthetic private draft: adult silver-haired traveller in a blue coat.'
DRAFT = 'studio.make.picture-draft'
BASE_LOOK = 'look-preset-pixel-lora'
OTHER_LOOK = 'look-preset-stylized-prop'
SAVED_LOOK = 'saved-browser-tune'


class MakePrivacyTransitions(unittest.TestCase):
    out = Path('.runtime/make-privacy-transitions')

    @classmethod
    def setUpClass(cls):
        cls.measurements=[]
        cls.out.mkdir(parents=True,exist_ok=True)
        cls.server=browser_server(fixture.Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.origin='http://127.0.0.1:'+str(cls.server.server_port)
        cls.pw=sync_playwright().start()
        cls.browser=cls.pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),
                                         headless=True,args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close();cls.pw.stop();cls.server.shutdown();cls.server.server_close();cls.thread.join(5)

    def setUp(self):
        self.context=self.browser.new_context(viewport={'width':1440,'height':1000},reduced_motion='reduce')
        self.page=self.context.new_page();self.page.set_default_timeout(7000);self.errors=[]
        self.page.on('pageerror',lambda error:self.errors.append(str(error)))
        self.save_receipts=[];self.requests=[]
        self.page.on('request',lambda request:self.requests.append({'method':request.method,'path':request.url.removeprefix(self.origin)}))
        self.before=len(fixture.JOBS);self.started=time.monotonic();self.actions={'clicks':0,'inputs':0,'changes':0,'searches':0}
        def action(kind,search):
            self.actions[kind]+=1
            if search:self.actions['searches']+=1
        self.page.expose_function('qaAction',action)
        self.page.add_init_script("""for(const [name,kind] of [['click','clicks'],['input','inputs'],['change','changes']])document.addEventListener(name,event=>{if(event.isTrusted)window.qaAction(kind,name==='input'&&event.target.matches('input[type=search],#studioCommandSearch'));},true);""")
        self.page.goto(self.origin+'/#make');self.ready()

    def tearDown(self):
        try:
            self.assertEqual(self.errors,[])
            self.assertEqual(len(fixture.JOBS),self.before,'Observation/navigation never submits a job')
            if self.save_receipts:
                self.assertEqual(len([r for r in self.requests if r=={'method':'POST','path':'/api/looks'}]),len(self.save_receipts))
                forbidden={'/api/jobs','/api/upload','/api/assets/reference','/api/looks/prepare'}
                self.assertFalse([r for r in self.requests if r['method']=='POST' and r['path'].split('?')[0] in forbidden],
                                 'saved-look selection and preview never prepare, stage a source or generate')
        finally:
            self.measurements.append({'case':self._testMethodName,'automated_seconds':round(time.monotonic()-self.started,3),
                                      **self.actions,'saved_look_replies':self.save_receipts})
            self.context.close()

    def ready(self):
        self.page.wait_for_function('window.StudioPrivacy && document.querySelector("#makeView").dataset.draftState === "ready"')

    def draft(self,kind):
        if kind=='picture':
            self.page.locator('[data-make-goal="edit"]').click()
            self.page.locator('[data-make-pick="asset-1"]').click()
            selector='#makeF-change'
        else:
            self.page.locator('[data-make-look]').first.click();selector='#makeScene'
        self.page.locator(selector).fill(TEXT)
        raw=self.page.evaluate('(key)=>sessionStorage.getItem(key)',DRAFT)
        self.assertIn(TEXT,raw)
        return selector,raw

    def storage_fault(self,mode):
        self.page.evaluate('''mode=>{window.originalSetItem=Storage.prototype.setItem;
          Storage.prototype.setItem=function(key,value){
            if(this===sessionStorage && key==='studio.make.picture-draft.private'){
              if(mode==='throw')throw new DOMException('Synthetic quota refusal','QuotaExceededError');
              if(mode==='drop')return;
            }
            return originalSetItem.call(this,key,value);
          };}''',mode)

    def migration(self,kind,mode):
        selector,raw=self.draft(kind);self.storage_fault(mode)
        self.page.evaluate("StudioPrivacy.setCreation('private')");self.ready()
        with self.subTest(contract='visible wording retained'):
            self.assertEqual(self.page.locator(selector).input_value(),TEXT)
        with self.subTest(contract='prior recovery retained'):
            self.assertEqual(self.page.evaluate('(key)=>sessionStorage.getItem(key)',DRAFT),raw)
        with self.subTest(contract='actionable warning'):
            warning=self.page.locator('#makeDraftWarning')
            self.assertTrue(warning.is_visible())
            self.assertIn('Keep this page open',warning.inner_text())
        with self.subTest(contract='private bytes not persistently published'):
            self.assertNotIn(TEXT,self.page.evaluate('JSON.stringify(localStorage)'))
        if kind=='picture':
            with self.subTest(contract='source retained'):
                self.assertEqual(self.page.locator('#makeComposer [data-ux-handoff]').get_attribute('data-ux-handoff'),'asset-1')
        self.page.evaluate("StudioPrivacy.setScope('all')");self.ready()
        with self.subTest(contract='scope-only transition keeps unsaved wording'):
            self.assertEqual(self.page.locator(selector).input_value(),TEXT)
        self.page.evaluate('()=>{Storage.prototype.setItem=window.originalSetItem;}')
        self.page.locator(selector).fill(TEXT+' Retried.')
        with self.subTest(contract='later successful save recovers'):
            self.assertIn(TEXT+' Retried.',self.page.evaluate('(key)=>sessionStorage.getItem(key)',DRAFT+'.private'))
            self.assertTrue(self.page.locator('#makeDraftWarning').is_hidden())
        self.page.reload();self.ready()
        with self.subTest(contract='private reload uses recovered draft'):
            self.assertEqual(self.page.locator(selector).input_value(),TEXT+' Retried.')

    def test_picture_quota_refusal_retains_draft_and_source(self):self.migration('picture','throw')
    def test_scene_quota_refusal_retains_wording_and_recovery(self):self.migration('scene','throw')
    def test_silent_storage_drop_is_not_mistaken_for_migration(self):self.migration('picture','drop')

    def test_successful_migration_retires_only_owned_regular_recovery(self):
        selector,_=self.draft('picture')
        self.page.evaluate("StudioPrivacy.setCreation('private')");self.ready()
        self.assertEqual(self.page.locator(selector).input_value(),TEXT)
        self.assertIsNone(self.page.evaluate('(key)=>sessionStorage.getItem(key)',DRAFT))
        self.assertIn(TEXT,self.page.evaluate('(key)=>sessionStorage.getItem(key)',DRAFT+'.private'))
        self.page.reload();self.ready();self.assertEqual(self.page.locator(selector).input_value(),TEXT)

    def test_selective_scene_storage_failure_keeps_the_composer(self):
        selector,_=self.draft('scene')
        self.page.evaluate("""()=>{window.sceneSetItem=Storage.prototype.setItem;
          Storage.prototype.setItem=function(key,value){
            if(this===sessionStorage&&key.startsWith('studio.make.scene.')&&key.endsWith('.private'))throw new DOMException('Synthetic scene quota','QuotaExceededError');
            return sceneSetItem.call(this,key,value);
          };}""")
        self.page.evaluate("StudioPrivacy.setCreation('private')");self.ready()
        self.assertEqual(self.page.locator(selector).input_value(),TEXT)
        self.page.locator(selector).fill(TEXT+' Still editing.')
        self.page.evaluate("StudioPrivacy.setScope('all')");self.ready()
        self.assertEqual(self.page.locator(selector).input_value(),TEXT+' Still editing.')
        self.assertIn(TEXT+' Still editing.',self.page.evaluate('(key)=>sessionStorage.getItem(key)',DRAFT+'.private'))

    def finder(self):
        self.page.locator('#studioJump').click()
        self.page.locator('#studioCommandSearch').fill('upscale')
        self.page.locator('#studioCommandResults [data-make-goal="repair"]').click()
        self.ready()
        self.page.wait_for_function('document.querySelector("[data-make-goal=repair][aria-checked=true]")')

    def test_finder_explicit_goal_wins_over_recovered_scene(self):
        self.draft('scene');self.finder()
        self.page.reload();self.ready()
        self.assertEqual(self.page.locator('[data-make-goal="repair"]').get_attribute('aria-checked'),'true')

    def test_private_finder_does_not_replace_regular_preferences(self):
        self.draft('scene')
        regular=self.page.evaluate("localStorage.getItem('studio.make')")
        self.page.evaluate("StudioPrivacy.setCreation('private')");self.ready();self.finder()
        self.assertEqual(self.page.evaluate("localStorage.getItem('studio.make')"),regular)
        self.assertNotIn(TEXT,self.page.evaluate('JSON.stringify(localStorage)'))
        self.assertEqual(self.page.evaluate('StudioPrivacy.creation()'),'private')

    def save_form(self,look=BASE_LOOK):
        self.page.locator('[data-make-goal="game"]').click()
        if self.page.locator('[data-make-change]').count():self.page.locator('[data-make-change]').click()
        self.page.locator('[data-make-look="'+look+'"]').click()
        if not self.page.locator('#makeTune').evaluate('node=>node.open'):self.page.locator('#makeTune > summary').click()
        self.page.locator('#makeSaveOpen').click()

    def hold_save(self,name,notes):
        self.held_saves=[]
        def capture(route):
            if route.request.method=='POST':self.held_saves.append(route)
            else:route.continue_()
        self.page.route(self.origin+'/api/looks',capture)
        self.page.locator('#makeSaveName').fill(name);self.page.locator('#makeSaveNotes').fill(notes)
        self.saving_button=self.page.locator('#makeSaveGo').element_handle()
        self.page.locator('#makeSaveGo').click()
        for _ in range(40):
            if self.held_saves:break
            self.page.wait_for_timeout(50)
        self.assertEqual(len(self.held_saves),1,'one actual Save press produces one held POST')
        self.assertTrue(self.page.locator('#makeSaveGo').is_disabled())
        request=self.held_saves[0].request
        self.assertEqual(request.headers.get('x-studio-creation-privacy'),'regular')
        self.assertEqual(request.post_data_json['name'],name)
        self.assertEqual(request.post_data_json['body']['notes'],notes)
        return request.post_data_json

    def release_save(self,refuse=False):
        route=self.held_saves[0];command=route.request.post_data_json
        # Acknowledgement/refusal fixtures exercise the real browser owner, not backend persistence.
        response={'error':'The original fixture save was refused'} if refuse else dict(
            id=SAVED_LOOK,kind='look',name=command['name'],body=command['body'],lineage=command['lineage'],
            origin='owner',revision=0,trashed_at=None,anchor_asset_id=None,usable=True,generation_submitted=False)
        status=409 if refuse else 201
        # Observe the original handler's finally check, even if its button was detached by a card switch.
        # Return the native value and remove the observer immediately; no production helper or timing sleep.
        self.saving_button.evaluate('''node=>{window.qaSavedLookSettled=false;
          const connected=Object.getOwnPropertyDescriptor(Node.prototype,'isConnected').get;
          Object.defineProperty(node,'isConnected',{configurable:true,get(){delete this.isConnected;
            window.qaSavedLookSettled=true;return connected.call(this);}});}''')
        with self.page.expect_request_finished(predicate=lambda request:request.url==self.origin+'/api/looks' and request.method=='POST'):
            route.fulfill(status=status,json=response)
        self.page.wait_for_function('window.qaSavedLookSettled===true')
        self.saving_button.dispose()
        self.save_receipts.append({'source':'fixture-crafted route.fulfill; GETs remain native HTTP',
                                   'request':command,'status':status,'response':response})
        self.assertEqual(len(self.held_saves),1)
        forbidden={'/api/jobs','/api/upload','/api/assets/reference','/api/looks/prepare'}
        self.assertFalse([r for r in self.requests if r['method']=='POST' and r['path'] in forbidden],
                         'saving a look never prepares, stages a source or submits generation')

    def shot(self,name,selector,width=390):
        self.page.set_viewport_size({'width':width,'height':844 if width==390 else 1000})
        self.page.locator(selector).evaluate("node=>node.scrollIntoView({block:'center',behavior:'instant'})")
        self.page.screenshot(path=str(self.out/(name+'-'+str(width)+'.png')),animations='disabled')

    def switched_save(self,refuse):
        self.save_form();self.hold_save('Original saved tune','Original notes')
        self.save_form(OTHER_LOOK)
        self.page.locator('#makeSaveName').fill('New unsaved name')
        self.page.locator('#makeSaveNotes').fill('New unsaved notes')
        message=self.page.locator('#makeSaveMsg').inner_text();status=self.page.locator('#makeStatus').inner_text()
        self.release_save(refuse)
        self.shot('save-switch-'+('refused' if refuse else 'accepted'),'#makeSaveForm')
        self.assertEqual(self.page.locator('#makeSaveName').input_value(),'New unsaved name')
        self.assertEqual(self.page.locator('#makeSaveNotes').input_value(),'New unsaved notes')
        self.assertTrue(self.page.locator('#makeSaveForm').is_visible())
        self.assertEqual(self.page.locator('#makeSaveMsg').inner_text(),message)
        self.assertEqual(self.page.locator('#makeStatus').inner_text(),status)
        self.page.locator('[data-make-change]').click()
        self.assertEqual(self.page.locator('[data-make-look="'+SAVED_LOOK+'"]').count(),0 if refuse else 1,
                         'only the acknowledged regular save enters the list; the current form is left alone')

    def test_saved_look_success_cannot_clear_a_different_cards_form(self):self.switched_save(False)
    def test_saved_look_refusal_cannot_replace_a_different_cards_status(self):self.switched_save(True)

    def test_saved_look_keeps_edits_typed_while_its_reply_is_pending(self):
        self.save_form();command=self.hold_save('First tune','First notes')
        self.page.locator('#makeSaveName').fill('Next tune');self.page.locator('#makeSaveNotes').fill('Next notes')
        self.release_save()
        self.page.wait_for_function("document.querySelector('#makeSaveMsg').textContent.includes('Saved')")
        self.shot('save-pending-edits','#makeSaveForm')
        self.assertEqual(command['name'],'First tune');self.assertEqual(command['body']['notes'],'First notes')
        self.assertEqual(self.page.locator('#makeSaveName').input_value(),'Next tune')
        self.assertEqual(self.page.locator('#makeSaveNotes').input_value(),'Next notes')
        self.assertTrue(self.page.locator('#makeSaveForm').is_visible());self.assertTrue(self.page.locator('#makeSaveGo').is_enabled())
        self.assertIn('First tune',self.page.locator('#makeSaveMsg').inner_text())
        self.assertIn('edited name and notes are still here',self.page.locator('#makeSaveMsg').inner_text())

    def preview_shots(self,name,selector):
        note=self.page.locator(selector+' .make-preview-note')
        self.assertEqual(note.inner_text(),'Base look preview; tuned settings may look different.')
        self.page.wait_for_function('(selector)=>{const img=document.querySelector(selector+" img");return img?.complete&&img.naturalWidth>0;}',arg=selector)
        for width in (1440,390):
            self.shot(name,selector,width)
            geometry=note.evaluate('''node=>{const r=node.getBoundingClientRect(),x=(r.left+r.right)/2,y=(r.top+r.bottom)/2;
              const top=Math.max(0,...[...document.querySelectorAll('.studio-globalbar,.studio-globalbar .privacy-bar')].map(n=>n.getBoundingClientRect().bottom));
              return {top:r.top,bottom:r.bottom,left:r.left,right:r.right,occupied:top,width:innerWidth,height:innerHeight,
                hit:node.contains(document.elementFromPoint(x,y)),scrollWidth:document.documentElement.scrollWidth};}''')
            (self.out/(name+'-'+str(width)+'.json')).write_text(json.dumps(geometry,indent=2)+'\n',encoding='utf-8')
            self.assertGreaterEqual(geometry['top'],geometry['occupied'],geometry)
            self.assertLessEqual(geometry['bottom'],geometry['height'],geometry)
            self.assertTrue(0<=geometry['left']<geometry['right']<=geometry['width'],geometry)
            self.assertTrue(geometry['hit'],geometry);self.assertLessEqual(geometry['scrollWidth'],geometry['width'],geometry)

    def test_saved_tune_base_preview_is_visible_but_not_a_functional_style_reference(self):
        self.save_form();base_url=self.page.locator('.make-chosen > img').get_attribute('src')
        self.assertIn('Shape and option selections start at their defaults',self.page.locator('#makeSaveHint').inner_text())
        self.assertIn('Different pictures each time',self.page.locator('#makeSaveHint').inner_text())
        status=self.page.locator('#makeStatus').inner_text()
        command=self.hold_save('A saved browser tune','Synthetic tuning notes');self.release_save()
        self.page.wait_for_function("document.querySelector('#makeSaveForm').hidden")
        self.assertEqual(self.page.locator('#makeStatus').inner_text(),status)
        self.assertTrue(self.page.locator('#makeSaveMsg').is_visible())
        self.assertIn('Game item or icon',self.page.locator('#makeSaveMsg').inner_text())
        self.assertIn('Saving a look does not generate a picture',self.page.locator('#makeSaveMsg').inner_text())
        self.shot('save-current-success','#makeSaveMsg')
        self.assertEqual(self.page.locator('#makeSaveName').input_value(),'')
        self.assertNotIn('anchor_asset_id',command)
        self.page.locator('[data-make-change]').click();card='[data-make-look="'+SAVED_LOOK+'"]'
        self.page.wait_for_function('(selector)=>{const img=document.querySelector(selector+" img");return img?.complete&&img.naturalWidth>0;}',arg=card)
        self.assertEqual(self.page.locator(card+' img').get_attribute('src'),base_url)
        self.preview_shots('saved-tune-gallery',card)
        self.page.locator(card).click();self.assertIn('A saved browser tune',self.page.locator('.make-chosen').inner_text())
        self.assertEqual(self.page.locator('.make-chosen > img').get_attribute('src'),base_url)
        self.preview_shots('saved-tune-selected','.make-chosen')
        self.page.locator('[data-make-goal="restyle"]').click();self.page.locator('[data-make-pick="asset-1"]').click()
        self.page.locator('#makeStyleLooks').wait_for()
        self.assertEqual(self.page.locator('[data-make-style="'+BASE_LOOK+'"]').count(),1)
        self.assertEqual(self.page.locator('[data-make-style="'+SAVED_LOOK+'"]').count(),0,
                         'a display-only base preview must not make the new tune a reference-image choice')
        self.assertEqual(len(self.held_saves),1)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=Path('.runtime/make-privacy-transitions'))
    args,remaining=parser.parse_known_args()
    MakePrivacyTransitions.out=args.out
    result=unittest.main(argv=[__file__,*remaining],verbosity=2,exit=False).result
    args.out.mkdir(parents=True,exist_ok=True)
    root=Path(__file__).resolve().parents[1]
    receipt={'mode':'native HTTP GETs; actual Make/privacy owners; synthetic records; held fixture-crafted saved-look POST replies','tests':result.testsRun,
             'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
             'journeys':getattr(MakePrivacyTransitions,'measurements',[]),
             'sources':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in
                        ('app/static/make.js','app/static/studio-shell.js','app/static/privacy.js','tests/make_privacy_transitions_browser.py')},
             'limits':'Automated interaction counts and timings, not human search effort or artwork acceptance; no model run.'}
    (args.out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    raise SystemExit(0 if result.wasSuccessful() else 1)
