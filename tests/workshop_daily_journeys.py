"""Native renderer checks of production dashboard/library seams; no HTTP or generation."""
from pathlib import Path
import unittest

import workshop_entry_points as entry
from bundle_browser_smoke import HTML as BUNDLE_HTML

ROOT = Path(__file__).resolve().parents[1]


def source(name):
    return (ROOT / 'app/static' / name).read_text(encoding='utf-8')


def region(text, start, end):
    return text[text.index(start):text.index(end, text.index(start))]


class DailyJourneys(entry.EntryPoints):
    def test_home_bundle_launcher_reuses_the_explorer_without_mutations(self):
        html = BUNDLE_HTML.replace('<main>', '<main><section id="homeView"><div class="ux-home-heading">Overview</div></section>')
        html = html.replace('<link rel="stylesheet" href="/app/static/bundle-explorer.css">', '<style>'+source('bundle-explorer.css')+'</style>')
        for name in ('bundle-core.js', 'bundle-explorer.js'):
            html = html.replace('<script src="/app/static/'+name+'"></script>', entry.script(name))
        for width in (1440, 390):
            with self.subTest(width=width):
                self.page.set_viewport_size({'width': width, 'height': 900})
                self.page.goto('about:blank')
                self.page.set_content(html)
                self.assertEqual(self.page.locator('#bundleHomeLauncher').count(), 1)
                self.assertTrue(self.page.locator('#bundleHomeLauncher').is_visible())
                self.page.click('#bundleHomeLauncher')
                self.assertEqual(self.page.locator('#bundleExplorer').count(), 1)
                self.assertTrue(self.page.locator('#bundleSearch').evaluate('(n)=>n===document.activeElement'))
                self.page.fill('#bundleSearch', 'ink')
                self.page.keyboard.press('Escape')
                self.assertFalse(self.page.locator('#bundleExplorer').evaluate('(n)=>n.open'))
                self.assertTrue(self.page.locator('#bundleHomeLauncher').evaluate('(n)=>n===document.activeElement'))
                self.assertEqual(self.page.evaluate('calls'), [])

    def test_overview_launcher_mounts_when_the_host_arrives_later(self):
        html = BUNDLE_HTML
        for name in ('bundle-core.js', 'bundle-explorer.js'):
            html = html.replace('<script src="/app/static/'+name+'"></script>', entry.script(name))
        self.page.set_content(html)
        self.assertEqual(self.page.locator('#bundleLauncher').count(), 1)
        self.assertEqual(self.page.locator('#bundleHomeLauncher').count(), 0)
        self.page.evaluate("""() => {
          document.querySelector('main').insertAdjacentHTML('afterbegin',
            '<section id="homeView"><div class="ux-home-heading">Overview</div></section>');
          document.dispatchEvent(new Event('studio:setup-draft-ready'));
          document.dispatchEvent(new Event('studio:setup-draft-ready'));
        }""")
        self.assertEqual(self.page.locator('#bundleHomeLauncher').count(), 1)
        self.page.click('#bundleHomeLauncher')
        self.assertTrue(self.page.locator('#bundleExplorer').evaluate('(n)=>n.open'))
        self.page.keyboard.press('Escape')
        self.assertTrue(self.page.locator('#bundleHomeLauncher').evaluate('(n)=>n===document.activeElement'))
        self.assertEqual(self.page.evaluate('calls'), [])

    def test_empty_results_explain_generate_import_and_continue(self):
        render = region(source('app.js'), 'function renderJobs(', '\nasync function refreshJobs')
        self.page.set_content('<div id="gallery"></div><div id="jobProblemsHost"></div><script>const $=s=>document.querySelector(s);let jobs=[],jobsSignature=null;function renderCompare(){}'+render+';renderJobs();</script>')
        copy = self.page.locator('#gallery').inner_text()
        self.assertIn('Generate', copy)
        self.assertIn('import', copy)
        self.assertIn('Continue with this', copy)
        self.assertEqual(self.page.locator('#gallery a').get_attribute('href'), '/#assets')

    def test_desk_hides_put_away_jobs_and_always_counts_them(self):
        # #940: the put-away note must follow a populated desk too, not only the empty fallback.
        home = region(source('studio-workbench.js'), '  function renderHome(', "  q('#uxRefreshHome').onclick")
        self.page.set_content('''<div id="uxHomeHealth"></div><div id="uxStats"></div><div id="uxAttention"></div><div id="uxRecent"></div><script>'''
            + source('studio-core.js') + '''</script><script>
const q=s=>document.querySelector(s),U=StudioUX,escape=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function assetPreview(){return '';}
let homeErrors=[],homeUpdated=new Date(),homeSignature='',homeData={workspace:{assets:[]},plans:[{id:'plan-1',name:'Live plan',kind:'comparison',state:{status:'running'}}],
  jobs:[{id:'open-job',preset_name:'Open failure',status:'failed'},{id:'away-job',preset_name:'Old failure',status:'failed',put_away:true},{id:'stopped-job',preset_name:'Stopped uncertain',status:'uncertain',put_away:true}]};
</script><script>'''+home+'''renderHome();</script>''')
        desk = self.page.locator('#uxAttention').inner_text()
        self.assertIn('Live plan', desk); self.assertIn('Open failure', desk)
        self.assertNotIn('Old failure', desk); self.assertNotIn('Stopped uncertain', desk)
        self.assertIn('2 run(s) put away', desk)
        self.page.evaluate("homeData={...homeData,plans:[],jobs:homeData.jobs.filter(j=>j.put_away)};homeSignature='';renderHome()")
        desk = self.page.locator('#uxAttention').inner_text()
        self.assertIn('A clear desk', desk); self.assertIn('2 run(s) put away', desk)
        self.assertEqual(self.page.locator('#uxAttention a[href="/#create"]').count(), 2)

    def load_output_review(self, fail=False, missing=False):
        card = region(source('app.js'), 'function mediaCard(', 'function renderCompare(')
        render = region(source('app.js'), 'const RECENT_STEP=', 'async function refreshJobs')
        self.page.goto('about:blank')
        self.page.set_content('''<p id="status"></p><input id="elsewhere"><div id="gallery"></div><div id="jobProblemsHost"></div><script>
const $=s=>document.querySelector(s),esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let jobs=[{id:'job-1',preset_name:'Lantern',status:'completed',controls:{positive:'a lantern',seed:7},outputs:[{asset_id:'asset-"1',media_type:'image',seed:7},{media_type:'image',seed:8}]}],jobsSignature=null;
let assetState={assets:'''+("[]" if missing else "[{id:'asset-" + '"' + "1',review:'unreviewed'}]")+'''};window.edits=[];window.reads=0;window.said=[];
function renderCompare(){}function renderMixedBatch(){return '';}
function message(text,error=false){said.push([text,error]);}
window.readOk=true;window.gates=[];let assetRefreshing=false;
async function refreshAssets(){reads++;if(!assetState.assets.length)assetState.assets.push({id:'asset-"1',review:'unreviewed'});return readOk;}
async function mutateAssets(payload){if('''+('true' if fail else 'false')+''')throw Error('Resolve the earlier library update first.');if(window.slow)await new Promise(r=>gates.push(r));edits.push(payload);assetState.assets.find(a=>a.id===payload.ids[0]).review=payload.review;}
</script><script>'''+source('output-review.js')+'''</script><script>'''+card+render+'''renderJobs();</script>''')

    def test_create_output_is_reviewed_in_place_and_a_second_press_clears_it(self):
        self.load_output_review()
        self.assertEqual(self.page.locator('.output-review').count(), 1, 'an output with no asset has nothing to review')
        self.assertEqual(self.page.locator('.output-review-state').inner_text(), 'Unreviewed')
        self.page.click('[data-output-review="selected"]')
        self.page.wait_for_function('edits.length===1')
        self.assertEqual(self.page.evaluate('edits[0]'), {'action': 'edit', 'ids': ['asset-"1'], 'review': 'selected'})
        self.assertEqual(self.page.evaluate('reads'), 1, 'a fresh revision is read before the edit')
        self.assertEqual(self.page.locator('.output-review-state').inner_text(), 'Kept')
        self.assertEqual(self.page.get_attribute('[data-output-review="selected"]', 'aria-pressed'), 'true')
        self.assertIn('press it again to clear', self.page.evaluate('said.at(-1)[0]'))
        self.page.click('[data-output-review="selected"]')
        self.page.wait_for_function('edits.length===2')
        self.assertEqual(self.page.evaluate('edits[1].review'), 'unreviewed')
        self.assertEqual(self.page.locator('.output-review-state').inner_text(), 'Unreviewed')

    def test_create_output_review_keys_act_only_on_the_focused_card(self):
        self.load_output_review()
        self.page.focus('#elsewhere'); self.page.keyboard.press('k')
        self.page.focus('#gallery .imageCard .pin'); self.page.keyboard.press('Control+k')
        self.assertEqual(self.page.evaluate('edits.length'), 0, 'typing and shortcuts elsewhere never review')
        self.page.keyboard.press('w')
        self.page.wait_for_function('edits.length===1')
        self.assertEqual(self.page.evaluate('edits[0].review'), 'needs_work')
        self.page.focus('[data-output-review="rejected"]')
        self.page.evaluate("jobs=[...jobs,{id:'job-2',preset_name:'New',status:'running',message:'Generating output 1 of 1',outputs:[]}];renderJobs()")
        self.assertEqual(self.page.evaluate("document.activeElement.dataset.outputReview"), 'rejected', 'a poll re-render keeps focus on the decision')
        self.page.keyboard.press('x')
        self.page.wait_for_function('edits.length===2')
        self.assertEqual(self.page.locator('.output-review-state').inner_text(), 'Rejected')

    def test_a_brand_new_output_is_reviewed_after_the_library_read_brings_it_in(self):
        # Create never polls the library: the asset of an output made on this page arrives only with the read.
        self.load_output_review(missing=True)
        self.page.click('[data-output-review="needs_work"]')
        self.page.wait_for_function('edits.length===1')
        self.assertEqual(self.page.evaluate('edits[0].review'), 'needs_work')
        self.assertEqual(self.page.locator('.output-review-state').inner_text(), 'Needs work')

    def test_decisions_pressed_while_a_save_is_in_flight_queue_instead_of_vanishing(self):
        # Codex/Muse on #1081: a press on any card during a save was silently dropped.
        self.load_output_review()
        self.page.evaluate("""()=>{assetState.assets.push({id:'asset-2',review:'unreviewed'});
          jobs=[{id:'job-2',preset_name:'Second',status:'completed',controls:{positive:'b',seed:9},outputs:[{asset_id:'asset-2',media_type:'image',seed:9}]},...jobs];renderJobs();window.slow=true;}""")
        self.assertEqual(self.page.locator('.output-review').count(), 2)
        self.page.click('[data-asset="asset-2"][data-output-review="selected"]')
        self.page.wait_for_function('gates.length===1')
        self.page.focus('[data-output="job-1:0"] .pin'); self.page.keyboard.press('w')
        self.page.click('[data-asset="asset-2"][data-output-review="selected"]')
        self.assertIn('this one follows', self.page.evaluate('said.at(-1)[0]'))
        self.assertEqual(self.page.locator('[data-review-asset="asset-2"] .output-review-state').inner_text(), 'Saving…')
        self.assertEqual(self.page.get_attribute('[data-review-asset="asset-2"]', 'aria-busy'), '')
        for n in range(1, 4):
            self.page.wait_for_function(f'gates.length==={n}'); self.page.evaluate(f'gates[{n-1}]()')
        self.page.wait_for_function('edits.length===3')
        self.assertEqual(self.page.evaluate('edits.map(e=>[e.ids[0],e.review])'),
                         [['asset-2', 'selected'], ['asset-"1', 'needs_work'], ['asset-2', 'unreviewed']], 'every press is saved, in order; the second Keep clears')
        self.assertEqual(self.page.locator('[data-review-asset="asset-2"] .output-review-state').inner_text(), 'Unreviewed')
        self.assertIsNone(self.page.get_attribute('[data-review-asset="asset-2"]', 'aria-busy'))
        self.assertEqual(self.page.locator('[data-output="job-1:0"] .output-review-state').inner_text(), 'Needs work')

    def test_an_unreadable_library_saves_nothing_and_says_so(self):
        self.load_output_review()
        self.page.evaluate('readOk=false')
        self.page.click('[data-output-review="selected"]')
        self.page.wait_for_function('said.length===1')
        self.assertEqual(self.page.evaluate('said[0]'), ['Could not read the library, so nothing was saved. Try again.', True])
        self.assertEqual(self.page.evaluate('edits.length'), 0)
        self.assertEqual(self.page.locator('.output-review-state').inner_text(), 'Unreviewed')

    def test_holding_a_review_key_never_toggles_the_decision_back(self):
        self.load_output_review()
        self.page.focus('#gallery .imageCard .pin')
        self.page.evaluate("""()=>{const t=document.activeElement;t.dispatchEvent(new KeyboardEvent('keydown',{key:'k',bubbles:true}));}""")
        self.page.wait_for_function('edits.length===1')
        self.page.evaluate("""()=>{const t=document.activeElement;for(let i=0;i<5;i++)t.dispatchEvent(new KeyboardEvent('keydown',{key:'k',repeat:true,bubbles:true}));}""")
        self.page.wait_for_timeout(200)
        self.assertEqual(self.page.evaluate('edits.map(e=>e.review)'), ['selected'])

    def test_create_output_review_failure_is_said_and_retryable(self):
        self.load_output_review(fail=True)
        self.page.click('[data-output-review="selected"]')
        self.page.wait_for_function('said.length===1')
        self.assertEqual(self.page.evaluate('said[0]'), ['Resolve the earlier library update first.', True])
        self.assertEqual(self.page.locator('.output-review-state').inner_text(), 'Unreviewed')
        self.page.click('[data-output-review="needs_work"]')
        self.page.wait_for_function('said.length===2', timeout=2000)
    def load_desk(self, plans, jobs):
        home = region(source('studio-workbench.js'), '  function renderHome(', "  q('#uxRefreshHome').onclick")
        self.page.goto('about:blank')
        activity = region(source('production.js'), 'function planActivity(', 'function planGroups(')
        self.page.set_content('''<div id="uxHomeHealth"></div><div id="uxStats"></div><div id="uxAttention"></div><div id="uxRecent"></div><script>'''
            + source('studio-core.js') + '''</script><script>
const q=s=>document.querySelector(s),U=StudioUX,escape=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function assetPreview(){return '';}
let homeErrors=[],homeUpdated=new Date(),homeSignature='',homeData={workspace:{assets:[]},plans:'''+plans+''',jobs:'''+jobs+'''};
</script><script>'''+activity+home+'''renderHome();</script>''')
        return self.page.locator('#uxAttention').inner_text()

    def test_desk_folds_plans_untouched_for_a_week_but_keeps_live_and_undated_ones(self):
        # #940: twelve-day-old comparisons left the desk permanently full. Runs & review keeps them under Older.
        now = 'Date.now()/1000'
        desk = self.load_desk('[{id:"old-review",name:"Old review",kind:"comparison",created_at:'+now+'-12*86400,state:{status:"awaiting_review"}},'
            '{id:"old-uncertain",name:"Old uncertain",kind:"comparison",created_at:'+now+'-12*86400,state:{status:"uncertain"}},'
            '{id:"old-running",name:"Old but running",kind:"comparison",created_at:'+now+'-12*86400,state:{status:"running"}},'
            '{id:"fresh",name:"Fresh plan",kind:"comparison",created_at:'+now+'-86400,state:{status:"planned"}},'
            '{id:"touched",name:"Old but reviewed today",kind:"comparison",created_at:'+now+'-30*86400,state:{status:"awaiting_review",finished_at:'+now+'-3600}},'
            '{id:"undated",name:"Undated plan",kind:"comparison",state:{status:"planned"}}]', '[]')
        for shown in ('Old but running', 'Fresh plan', 'Old but reviewed today', 'Undated plan'): self.assertIn(shown, desk)
        for folded in ('Old review', 'Old uncertain'): self.assertNotIn(folded, desk)
        self.assertIn('2 plan(s) untouched for 7 days', desk)
        self.assertEqual(self.page.locator('#uxAttention .ux-desk-note a[href="/#production"]').count(), 1)
        desk = self.load_desk('[{id:"old",name:"Only old",kind:"comparison",created_at:Date.now()/1000-9*86400,state:{status:"planned"}}]', '[]')
        self.assertIn('A clear desk', desk); self.assertIn('1 plan(s) untouched for 7 days', desk)

    def test_desk_job_rows_say_what_each_state_needs(self):
        desk = self.load_desk('[]', '[{id:"f",preset_name:"Failed run",status:"failed"},{id:"u",preset_name:"Unknown run",status:"uncertain"},{id:"r",preset_name:"Live run",status:"running"}]')
        self.assertIn('failed · see why, then put it away', desk)
        self.assertIn('outcome unknown · inspect; do not run it again', desk)
        self.assertIn('running · in progress', desk)
        self.assertNotIn('do not repeat uncertain work', desk)

    def load_inspector(self, job):
        inspect = region(source('studio-workbench.js'), '  function inspectJob(', '  async function refreshHome(')
        self.page.goto('about:blank')
        self.page.set_content('''<button id="origin">Inspect job</button><dialog id="uxJobInspector" class="studio-dialog"></dialog><p id="said"></p><script>
const q=s=>document.querySelector(s),escape=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const U={failureDetails:()=>null};window.posts=[];window.reads=0;
let homeData={jobs:['''+job+''']},homeSignature='x';
let homeUpdated=new Date(),jobInspector=document.querySelector('#uxJobInspector');function announce(text){q('#said').textContent=text;}
async function post(path,body){posts.push({path,body});return {};}async function refreshHome(){reads++;}function refresh(){reads+=10;}
</script><script>'''+inspect+'''document.querySelector('#origin').onclick=()=>inspectJob(homeData.jobs[0].id);
document.addEventListener('click',async e=>{const b=e.target.closest('[data-ux-put-away]');if(b)await putAwayFromDesk(b);});</script>''')
        self.page.click('#origin')

    def test_desk_inspector_puts_a_problem_away_without_touching_the_job(self):
        self.load_inspector('{id:"failed-one",preset_name:"Old failure",status:"failed",message:"No memory",can_put_away:true}')
        text = self.page.locator('#uxJobInspector').inner_text()
        self.assertIn('Nothing is retried, cancelled or deleted', text)
        self.page.click('[data-ux-put-away="true"]')
        self.page.wait_for_function('!jobInspector.open')
        self.assertEqual(self.page.evaluate('posts'), [{'path': '/api/jobs/failed-one/put-away', 'body': {'put_away': True}}])
        self.assertEqual(self.page.evaluate('reads'), 11)
        self.assertIn('Show put away', self.page.locator('#said').inner_text())

    def test_desk_inspector_brings_back_and_explains_uncertain_holds(self):
        self.load_inspector('{id:"away",preset_name:"Put away",status:"failed",put_away:true,can_bring_back:true}')
        self.page.click('[data-ux-put-away="false"]')
        self.assertEqual(self.page.evaluate('posts[0].body'), {'put_away': False})
        self.load_inspector('{id:"u",preset_name:"Unknown",status:"uncertain",can_stop_tracking:true,can_put_away:false}')
        self.assertEqual(self.page.locator('[data-ux-put-away]').count(), 0)
        self.assertIn('stop tracking it first', self.page.locator('#uxJobInspector').inner_text())
        self.assertEqual(self.page.locator('#uxJobInspector a[href="/#create"]').count(), 1)

    def load_picker(self):
        production = region(source('studio-workbench.js'), '  // Pull any existing image', '  // Drafts are data only')
        self.page.set_content('''<button id="uxPullAsset">Pull from library</button><script>
const q=s=>document.querySelector(s),escape=v=>String(v);
function element(tag,cls){const n=document.createElement(tag);n.className=cls;return n;}
let selected={reference:true},referenceRecords=[],selectionEpoch=0,view='create',pickerBusy=false,pickerLoading=false,sourcePickerEpoch=0;
let assetState={assets:[{id:'old',title:'Cached old image',tags:[],media_type:'image'}]};
const takesSource=()=>!!selected.reference,NO_SOURCE_SLOT='Choose a reference recipe';
function announce(){}function after(){}function syncReady(){}function assetPreview(){return '';}
window.pending=[];function refreshAssets(){return new Promise(resolve=>pending.push(resolve));}
</script><script>'''+production+'</script>')

    def test_library_success_survives_the_production_read_scheduler(self):
        self.load_picker()
        self.page.add_script_tag(content=source('read-poller.js'))
        self.page.evaluate('''() => {
          const readAssets=refreshAssets;
          window.pickerPoller=new ReadPoller();
          pickerPoller.register('assets',{interval:15000,task:readAssets});
          refreshAssets=(...args)=>pickerPoller.refresh('assets',...args);
        }''')
        self.page.click('#uxPullAsset')
        self.page.evaluate('pending.shift()(true)')
        self.page.wait_for_function('!pickerLoading')
        self.assertEqual(self.page.locator('[data-ux-pull]').count(), 1)
        self.assertTrue(self.page.locator('#uxSourceSearch').is_enabled())
        self.page.evaluate('pickerPoller.dispose()')

    def test_library_opens_immediately_and_refuses_failed_cached_results(self):
        self.load_picker()
        self.page.click('#uxPullAsset')
        self.assertTrue(self.page.locator('#uxSourcePicker').is_visible())
        self.assertIn('Loading', self.page.locator('#uxPickerStatus').inner_text())
        self.assertEqual(self.page.locator('[data-ux-pull]').count(), 0)
        self.page.evaluate('pending.shift()(false)')
        self.page.wait_for_function('!pickerLoading')
        self.assertIn('reopen', self.page.locator('#uxPickerStatus').inner_text())
        self.assertEqual(self.page.locator('[data-ux-pull]').count(), 0)

    def test_cancelled_library_read_cannot_reopen_or_fill_a_new_picker(self):
        self.load_picker()
        self.page.click('#uxPullAsset')
        self.page.keyboard.press('Escape')
        self.page.wait_for_function('!picker.open')
        self.assertTrue(self.page.locator('#uxPullAsset').evaluate('(n)=>n===document.activeElement'))
        self.page.click('#uxPullAsset')
        self.page.evaluate('pending.shift()(true)')
        self.assertEqual(self.page.locator('[data-ux-pull]').count(), 0)
        self.page.evaluate('pending.shift()(true)')
        self.page.wait_for_selector('[data-ux-pull]')
        self.assertEqual(self.page.locator('[data-ux-pull]').count(), 1)
        self.page.keyboard.press('Escape')
        self.page.wait_for_function('!picker.open')

    def test_library_loading_keeps_one_read_and_respects_newer_focus(self):
        self.load_picker()
        self.page.click('#uxPullAsset')
        self.page.locator('#uxPullAsset').evaluate('(n)=>n.click()')
        self.assertEqual(self.page.evaluate('pending.length'), 1)
        self.page.locator('[data-ux-close="uxSourcePicker"]').focus()
        self.page.evaluate('pending.shift()(true)')
        self.page.wait_for_selector('[data-ux-pull]')
        self.assertTrue(self.page.locator('[data-ux-close="uxSourcePicker"]').evaluate('(n)=>n===document.activeElement'))
        self.page.keyboard.press('Escape')
        self.page.wait_for_function('!picker.open')
        self.assertTrue(self.page.locator('#uxPullAsset').evaluate('(n)=>n===document.activeElement'))

    def test_recipe_change_during_library_read_does_not_render_old_cards(self):
        self.load_picker()
        self.page.click('#uxPullAsset')
        self.page.evaluate('selectionEpoch++; pending.shift()(true)')
        self.page.wait_for_function('!picker.open')
        self.assertEqual(self.page.locator('[data-ux-pull]').count(), 0)
        self.assertFalse(self.page.evaluate('pickerLoading'))

    def test_failed_job_inspector_is_specific_escaped_and_read_only(self):
        inspect = region(source('studio-workbench.js'), '  function inspectJob(', '  async function refreshHome(')
        self.page.set_content('''<button id="origin">Inspect job</button><dialog id="uxJobInspector" class="studio-dialog"></dialog><script>
const q=s=>document.querySelector(s),escape=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const U={failureDetails:()=>({summary:'Memory allocation failed',action:'Try a smaller canvas',detail:'engine detail'})};
let homeData={jobs:[{id:'failed-one',preset_name:'<img src=x onerror=alert(1)>',status:'failed',message:'No memory',prompt_ids:['retained-prompt'],recipe:{controls:{positive:'original wording'}}}]};
let homeUpdated=new Date(),jobInspector=document.querySelector('#uxJobInspector');function announce(){};
</script><script>'''+inspect+'''document.querySelector('#origin').onclick=()=>inspectJob('failed-one');</script>''')
        self.page.click('#origin')
        self.assertIn('failed-one', self.page.locator('#uxJobInspector').inner_text())
        self.assertIn('retained-prompt', self.page.locator('#uxJobInspector').inner_text())
        self.assertIn('Try a smaller canvas', self.page.locator('#uxJobInspector').inner_text())
        self.assertEqual(self.page.locator('#uxJobInspector img').count(), 0)
        self.assertEqual(self.page.locator('#uxJobInspector button').count(), 1)
        self.page.keyboard.press('Escape')
        self.page.wait_for_function('!jobInspector.open')
        self.assertTrue(self.page.locator('#origin').evaluate('(n)=>n===document.activeElement'))

    def test_workspace_refresh_reports_success_failure_and_busy(self):
        refresh = region(source('workspace.js'), 'async function refreshAssets(', '// Scope, filters')
        self.page.set_content('''<script>
let assetRefreshing=false,assetState={workspace_id:'old'},assetSignature='',jobsSignature='';
const assetSelection=new Set();let assetLibraryPending=null;
function renderLibraryRecovery(){}function renderAssets(){}function renderJobs(){}function assetMessage(){};
window.pending=[];function api(){return new Promise((resolve,reject)=>pending.push({resolve,reject}));}
</script><script>'''+refresh+'</script>')
        self.page.evaluate('()=>{window.first=refreshAssets()}')
        self.assertFalse(self.page.evaluate('refreshAssets()'))
        self.page.evaluate("pending.shift().reject(Error('offline'))")
        self.assertFalse(self.page.evaluate('first'))
        self.assertEqual(self.page.evaluate('assetState.workspace_id'), 'old')
        self.page.evaluate('()=>{window.second=refreshAssets()}')
        self.page.evaluate("pending.shift().resolve({workspace_id:'new'})")
        self.assertTrue(self.page.evaluate('second'))
        self.assertEqual(self.page.evaluate('assetState.workspace_id'), 'new')


if __name__ == '__main__':
    unittest.main(verbosity=2)
