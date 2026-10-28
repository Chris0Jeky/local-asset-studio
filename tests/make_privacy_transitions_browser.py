"""Native Make + real privacy owner: persistence failures and explicit finder intent.

Disposable browser storage and synthetic records only; never ComfyUI or user media.
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


class MakePrivacyTransitions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.measurements=[]
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
        finally:
            self.measurements.append({'case':self._testMethodName,'automated_seconds':round(time.monotonic()-self.started,3),**self.actions})
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
        self.page.select_option('#creationPrivacy','private');self.ready()
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
        self.page.locator('[data-privacy-scope=all]').click();self.ready()
        with self.subTest(contract='scope-only transition keeps unsaved wording'):
            self.assertEqual(self.page.locator(selector).input_value(),TEXT)
        self.page.evaluate('Storage.prototype.setItem=window.originalSetItem')
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
        self.page.select_option('#creationPrivacy','private');self.ready()
        self.assertEqual(self.page.locator(selector).input_value(),TEXT)
        self.assertIsNone(self.page.evaluate('(key)=>sessionStorage.getItem(key)',DRAFT))
        self.assertIn(TEXT,self.page.evaluate('(key)=>sessionStorage.getItem(key)',DRAFT+'.private'))
        self.page.reload();self.ready();self.assertEqual(self.page.locator(selector).input_value(),TEXT)

    def test_selective_scene_storage_failure_keeps_the_composer(self):
        selector,_=self.draft('scene')
        self.page.evaluate("""window.sceneSetItem=Storage.prototype.setItem;
          Storage.prototype.setItem=function(key,value){
            if(this===sessionStorage&&key.startsWith('studio.make.scene.')&&key.endsWith('.private'))throw new DOMException('Synthetic scene quota','QuotaExceededError');
            return sceneSetItem.call(this,key,value);
          };""")
        self.page.select_option('#creationPrivacy','private');self.ready()
        self.assertEqual(self.page.locator(selector).input_value(),TEXT)
        self.page.locator(selector).fill(TEXT+' Still editing.')
        self.page.locator('[data-privacy-scope=all]').click();self.ready()
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
        self.page.select_option('#creationPrivacy','private');self.ready();self.finder()
        self.assertEqual(self.page.evaluate("localStorage.getItem('studio.make')"),regular)
        self.assertNotIn(TEXT,self.page.evaluate('JSON.stringify(localStorage)'))
        self.assertEqual(self.page.evaluate('StudioPrivacy.creation()'),'private')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=Path('.runtime/make-privacy-transitions'))
    args,remaining=parser.parse_known_args()
    result=unittest.main(argv=[__file__,*remaining],verbosity=2,exit=False).result
    args.out.mkdir(parents=True,exist_ok=True)
    root=Path(__file__).resolve().parents[1]
    receipt={'mode':'native HTTP; actual Make/privacy owners; synthetic records','tests':result.testsRun,
             'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
             'journeys':getattr(MakePrivacyTransitions,'measurements',[]),
             'sources':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in
                        ('app/static/make.js','app/static/studio-shell.js','app/static/privacy.js')},
             'limits':'Automated interaction counts and timings, not human search effort or artwork acceptance; no model run.'}
    (args.out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    raise SystemExit(0 if result.wasSuccessful() else 1)
