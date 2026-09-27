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

    def test_locked_mixed_batch_recovery_says_why_beside_each_button(self):
        batch = region(source('app.js'), 'function renderMixedBatch(', 'async function mixedBatchAction(')
        self.page.goto('about:blank')
        self.page.set_content("""<div id="out"></div><script>const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));</script><script>"""+batch+"""
const base={revision:'r',known:[],unknown_index:1,never_submitted_count:0,message:'m'};
window.show=(status,b)=>{document.querySelector('#out').innerHTML=renderMixedBatch({id:'j',status,mixed_batch:{...base,...b}});return [...document.querySelectorAll('.disabledReason')].map(n=>n.textContent);};</script>""")
        self.assertEqual(self.page.evaluate("show('running',{can_observe:false,can_dispose:false})"),
                         ['Available once this job stops being running.'] * 2)
        self.assertEqual(self.page.evaluate("show('uncertain',{can_observe:false,can_dispose:true})"),
                         ['The check limit for this batch is used up; its evidence is kept.'])
        self.assertEqual(self.page.evaluate("show('uncertain',{can_observe:true,can_dispose:true})"), [])

    def test_combine_seed_buttons_say_why_they_are_locked(self):
        combine = region(source('studio-workbench.js'), '  function syncCombineResults(', '  resultPanel.onclick=')
        self.page.goto('about:blank')
        self.page.set_content("""<div id="panel"></div><script>"""+source('continuation-core.js')+"""</script><script>const escape=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const StudioContinuation={...globalThis.StudioContinuation,combineKind:()=>'depth',sameCombinePair:()=>true};let selected={},catalog={presets:[]},referenceRecords=[],lastUploaded=null,resultMarkup='',pairActionBusy=false,busy=false;
const resultPanel=document.querySelector('#panel');function currentPair(){return {};}function combineBusy(){return busy||dirty;}let submitting=false,poseBusy=false,dirty=false;function posePositionDirty(){return dirty;}function durationLabel(s){return s+' s';}
let assetState={assets:[]},jobs=[{id:'done',status:'completed',preset_name:'P',outputs:[{seed:1}]},{id:'half',status:'partial',preset_name:'P',outputs:[{seed:2}]}];
</script><script>"""+combine+'</script>')
        titles = lambda: self.page.evaluate("syncCombineResults();[...document.querySelectorAll('[data-ux-rerun]')].map(b=>[b.dataset.job,b.disabled,b.title])")
        # #422: a partial run is folded under "needs attention" with no seed control at all, only a way to Problems.
        self.assertEqual(titles(), [['done', False, ''], ['done', False, '']])
        self.assertEqual(self.page.evaluate("[...document.querySelectorAll('.ux-run-attention [data-ux-problem]')].map(b=>b.dataset.uxProblem)"), ['half'])
        self.page.evaluate('busy=true;resultMarkup=""')
        self.assertEqual(titles()[0], ['done', True, 'Wait for the current Combine action to finish.'])
        self.page.evaluate('busy=false;dirty=true;resultMarkup=""')
        self.assertEqual(titles()[0], ['done', True, 'Set or reset the typed joint position first.'], 'waiting never clears an unapplied joint edit')

    def test_restore_source_wording_says_why_and_keeps_its_lock_rule(self):
        sync = region(source('studio-workbench.js'), '  function syncContinuation(', '  async function readSource(')
        ids = ['uxContinuationImage','uxContinuationTitle','uxContinuationOrigin','uxContinuationGuidance','uxContinuationPrompt','uxContinuationRecord','uxChangeRoute','uxLeaveContinuation','generate']
        self.page.goto('about:blank')
        self.page.set_content('<div id="ctx"></div><textarea id="positive"></textarea><button id="uxRestoreSourcePrompt"></button><small id="uxRestoreSourceReason"></small>'
            + ''.join(f'<div id="{i}"></div>' if i != 'uxContinuationImage' else f'<img id="{i}">' for i in ids)
            + '''<script>const q=s=>document.querySelector(s),escape=v=>String(v??''),contextPanel=q('#ctx');
const StudioContinuation={guidance:()=>[]};let submitting=false,sourceReadError='',continuationState={source_asset_id:'a1'},continuationSource=null,selected={continuation_capability:{prompt_role:'description'}};
window.state=()=>{syncContinuation();return [q('#uxRestoreSourcePrompt').disabled,q('#uxRestoreSourceReason').textContent];};</script><script>'''+sync+'</script>')
        self.assertEqual(self.page.evaluate('state()'), [True, 'Restore source wording: Still reading the source.'])
        self.page.evaluate("sourceReadError='Could not verify source metadata: offline'")
        self.assertEqual(self.page.evaluate('state()'), [True, 'Restore source wording: Could not verify source metadata: offline'])
        self.page.evaluate("continuationSource={prompt_origin:'submitted-output',prompt_role:'description',positive:'a lantern'}")
        self.assertEqual(self.page.evaluate('state()'), [False, ''])
        self.page.evaluate("selected={continuation_capability:{prompt_role:'instruction'}}")
        self.assertEqual(self.page.evaluate('state()'), [True, 'Restore source wording: This recipe takes an instruction, not the source description.'])
        self.page.evaluate("selected={continuation_capability:{prompt_role:'description'}};continuationSource={prompt_origin:'imported',prompt_role:'description',positive:'x'}")
        self.assertEqual(self.page.evaluate('state()'), [True, 'Restore source wording: The source has no submitted description to restore.'])
        self.page.evaluate("continuationSource={prompt_origin:'submitted-output',prompt_role:'description',positive:'a'};submitting=true")
        self.assertEqual(self.page.evaluate('state()'), [True, ''], 'a transient submit lock shows no reason line')

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

    def load_outcome(self):
        self.page.goto('about:blank')
        self.page.set_content("""<p id="status" role="status"></p><button id="generate">Generate</button>
<details id="workshopResults"><summary>Recent runs</summary><div id="gallery"><article class="imageCard" data-output="done-1:0"><img alt=""><div class="card-actions"><button class="pin">Compare</button></div></article></div></details>
<div id="jobProblemsHost"><details id="jobProblems"><summary>Problems</summary><article class="jobStatus failed" data-problem="bad-1"><b>Krea · failed</b><button class="recipe">Recipe</button></article></details></div>
<script>let jobs=[];window.said=[];function message(text,error=false){said.push([text,error]);document.querySelector('#status').textContent=text;}
function durationLabel(s){return Math.round(s)+' s';}</script><script>"""+source('run-outcome.js')+'</script>')

    def settle(self, job):
        self.page.evaluate('job=>document.dispatchEvent(new CustomEvent("studio:job-settled",{detail:job}))', job)

    def test_a_finished_run_says_what_happened_and_shows_its_result(self):
        self.load_outcome()
        self.settle({'id': 'done-1', 'status': 'completed', 'elapsed_seconds': 72, 'outputs': [{}, {}], 'batch_count': 2})
        self.assertEqual(self.page.locator('#status').inner_text(), 'Done in 72 s · 2 outputs. Review it while it is fresh.')
        self.page.click('[data-run-outcome="show"]')
        self.assertTrue(self.page.evaluate("document.querySelector('#workshopResults').open"))
        self.assertEqual(self.page.evaluate('document.activeElement.className'), 'pin', 'focus lands on the result so K/W/X can review it')
        self.page.click('#generate')
        self.assertTrue(self.page.locator('#runOutcome').is_hidden(), 'a new Generate clears the old summary')

    def test_a_failed_or_uncertain_run_points_at_its_problem_and_never_offers_a_rerun(self):
        self.load_outcome()
        self.settle({'id': 'bad-1', 'status': 'failed', 'failure': {'title': 'Memory allocation failed'}, 'message': 'Generation failed: bad allocation. More detail.'})
        self.assertEqual(self.page.evaluate('said.at(-1)'), ['Failed: Memory allocation failed', True])
        self.assertEqual(self.page.locator('[data-run-outcome="show"]').inner_text(), 'See why →')
        self.page.click('[data-run-outcome="show"]')
        self.assertTrue(self.page.evaluate("document.querySelector('#jobProblems').open"))
        self.assertEqual(self.page.evaluate('document.activeElement.dataset.problem'), 'bad-1', 'focus lands on the record, reason first, not on an action')
        self.settle({'id': 'lost', 'status': 'uncertain', 'message': 'Submission outcome is uncertain.'})
        # The exact sentence: it must promise no re-run and invite none.
        self.assertEqual(self.page.locator('#status').inner_text(), 'Outcome unknown. It will not be run again; inspect it before starting new work.')
        self.assertEqual(self.page.evaluate("[...document.querySelectorAll('#runOutcome button')].map(b=>b.textContent)"), ['Inspect →', 'Dismiss'])
        self.page.click('[data-run-outcome="show"]')
        self.assertIn('not shown here yet', self.page.evaluate('said.at(-1)[0]'))
        self.settle({'id': 'half', 'status': 'partial', 'outputs': [{}], 'batch_count': 3})
        self.assertEqual(self.page.locator('#status').inner_text(), 'Partly done: 1 output saved. The rest will not be run again automatically.')
        self.page.click('[data-run-outcome="dismiss"]')
        self.assertTrue(self.page.locator('#runOutcome').is_hidden())
        self.assertEqual(self.page.locator('#status').inner_text(), '')
        self.settle({'id': 'done-1', 'status': 'completed', 'outputs': [{}]})
        self.page.evaluate("message('A newer, unrelated message')")
        self.page.click('[data-run-outcome="dismiss"]')
        self.assertEqual(self.page.locator('#status').inner_text(), 'A newer, unrelated message', 'Dismiss never wipes a newer message')

    def test_a_run_that_never_started_says_nothing_was_submitted(self):
        self.load_outcome()
        self.settle({'id': 'ns', 'status': 'not_submitted', 'message': 'ComfyUI queue unavailable. Nothing was submitted. No retry was queued.'})
        self.assertEqual(self.page.evaluate('said.at(-1)'), ['Not started: ComfyUI queue unavailable. Nothing was submitted.', True])
        self.assertEqual(self.page.locator('[data-run-outcome="show"]').inner_text(), 'See why →')

    def test_show_result_uses_any_shown_output_of_the_run(self):
        self.load_outcome()
        self.page.evaluate("document.querySelector('[data-output]').dataset.output='done-1:2'")
        self.settle({'id': 'done-1', 'status': 'completed', 'outputs': [{}, {}, {}]})
        self.page.click('[data-run-outcome="show"]')
        self.assertEqual(self.page.evaluate('document.activeElement.className'), 'pin', 'output 0 in Trash still leads to the run')

    def test_refresh_jobs_announces_the_started_run_once_when_it_settles(self):
        refresh = region(source('app.js'), 'async function refreshJobs(', 'function refresh(')
        self.page.goto('about:blank')
        self.page.set_content("""<p id="status"></p><script>let jobs=[],jobsEtag=null,jobsDataSignature='',estimateKey='',estimateResultKey='',activeJobId='mine';window.events=[];
function renderJobs(){}function scheduleTimeEstimate(){}function message(){}
window.reply=[{id:'mine',status:'running',preset_name:'P',message:'Generating'}];window.fetch=async()=>({ok:true,status:200,headers:{get:()=>null},json:async()=>reply});
document.addEventListener('studio:job-settled',e=>events.push(e.detail.id));</script><script>"""+refresh+'</script>')
        self.page.evaluate("startedJobIds.add('mine')"); self.page.evaluate('refreshJobs()')
        self.assertEqual(self.page.evaluate('events'), [])
        self.page.evaluate("reply=[{id:'mine',status:'completed',preset_name:'P',message:'Complete',outputs:[{}]}]")
        self.page.evaluate('refreshJobs()'); self.page.evaluate('refreshJobs()')
        self.assertEqual(self.page.evaluate('events'), ['mine'])

    def test_a_run_already_settled_before_a_304_is_still_announced(self):
        # Review of #1085: a fast failure seen by an earlier poll, then a 304 after the POST set activeJobId.
        refresh = region(source('app.js'), 'async function refreshJobs(', 'function refresh(')
        self.page.goto('about:blank')
        self.page.set_content("""<p id="status"></p><script>let jobs=[{id:'mine',status:'failed',preset_name:'P',message:'Rejected'}],jobsEtag='"e1"',jobsDataSignature='x',estimateKey='',estimateResultKey='',activeJobId='mine';window.events=[];
function renderJobs(){}function scheduleTimeEstimate(){}function message(){}
window.fetch=async()=>({ok:false,status:304,headers:{get:()=>'"e1"'},json:async()=>{throw Error('no body');}});
document.addEventListener('studio:job-settled',e=>events.push(e.detail.id));</script><script>"""+refresh+'</script>')
        self.page.evaluate("startedJobIds.add('mine')"); self.page.evaluate('refreshJobs()'); self.page.evaluate('refreshJobs()')
        self.assertEqual(self.page.evaluate('events'), ['mine'])


    def test_an_earlier_run_is_announced_after_a_newer_generate_took_the_status_line(self):
        # Codex on #1085: activeJobId is overwritten when a second run is queued before the first settles.
        refresh = region(source('app.js'), 'async function refreshJobs(', 'function refresh(')
        self.page.goto('about:blank')
        self.page.set_content("""<p id="status"></p><script>let jobs=[],jobsEtag=null,jobsDataSignature='',estimateKey='',estimateResultKey='',activeJobId='second';window.events=[];
function renderJobs(){}function scheduleTimeEstimate(){}function message(){}
window.reply=[{id:'first',status:'not_submitted',preset_name:'P',message:'Queue unavailable. Nothing was submitted.'},{id:'second',status:'running',preset_name:'P',message:'Generating'}];
window.fetch=async()=>({ok:true,status:200,headers:{get:()=>null},json:async()=>reply});
document.addEventListener('studio:job-settled',e=>events.push([e.detail.id,e.detail.status]));</script><script>"""+refresh+'</script>')
        self.page.evaluate("startedJobIds.add('first');startedJobIds.add('second')")
        self.page.evaluate('refreshJobs()'); self.page.evaluate('refreshJobs()')
        self.assertEqual(self.page.evaluate('events'), [['first', 'not_submitted']], 'the earlier run settles once; the running one waits')
        self.assertEqual(self.page.evaluate('activeJobId'), 'second')


    def test_running_cards_show_truthful_elapsed_time_not_progress(self):
        """Handoff 03: a running card had no elapsed time. Only started_at is observed, so no progress bar is drawn (K13)."""
        html = entry.workshop_html().replace('</body>', """<script>
var jobs=[{id:'run-1',status:'running',started_at:Date.now()/1000-75,message:'Generating output 1 of 1'},
  {id:'wait-1',status:'waiting',started_at:Date.now()/1000-5,message:'Waiting for existing ComfyUI work'},
  {id:'queued-1',status:'queued',message:'Queued'},{id:'done-1',status:'completed',started_at:Date.now()/1000-300,message:'Complete'}];
document.getElementById('gallery').innerHTML=jobs.map(j=>'<article class="jobStatus '+j.status+'" data-problem="'+j.id+'"><b>Fixture · '+j.status+'</b><p>'+j.message+'</p></article>').join('');
</script></body>""")
        self.page.set_content(html)
        self.page.wait_for_selector('#workshopRecipeChange')
        self.page.locator('#workshopResults').evaluate('(n)=>n.open=true')  # Generate opens Recent runs
        self.page.wait_for_selector('[data-problem="run-1"] .job-elapsed')
        running = self.page.locator('[data-problem="run-1"] .job-elapsed').inner_text()
        self.assertRegex(running, r'^Started \d{1,2}:\d{2}.* · 1 min 1[5-7] s so far$')
        self.assertIn('Generating output 1 of 1', self.page.locator('[data-problem="run-1"]').inner_text(), 'the job message stays')
        self.assertRegex(self.page.locator('[data-problem="wait-1"] .job-elapsed').inner_text(), r' · [5-7] s so far$')
        self.assertEqual(self.page.locator('[data-problem="queued-1"] .job-elapsed').count(), 0, 'not started, so no clock')
        self.assertEqual(self.page.locator('[data-problem="done-1"] .job-elapsed').count(), 0)
        self.assertEqual(self.page.locator('#gallery progress, #gallery [role=progressbar]').count(), 0)
        self.page.wait_for_function("!document.querySelector('[data-problem=\"run-1\"] .job-elapsed').textContent.includes('"+running.split('·')[-1].strip()+"')")
        # Codex P2 on #1139: the ticking clock is not an execution change, so the presentation context stays put.
        stamp = self.page.evaluate("document.querySelector('#createView').__workshop.presentationView().contextStamp")
        self.assertTrue(stamp)
        self.page.wait_for_timeout(2200)
        self.assertEqual(self.page.evaluate("document.querySelector('#createView').__workshop.presentationView().contextStamp"), stamp)
        # A real card change is still an execution change: the stamp advances (the filter ignores only the clock line).
        self.page.evaluate("document.getElementById('gallery').insertAdjacentHTML('beforeend','<article class=\"jobStatus queued\" data-problem=\"queued-2\"><b>Fixture · queued</b><p>Queued</p></article>')")
        self.page.wait_for_function("(s)=>document.querySelector('#createView').__workshop.presentationView().contextStamp!==s", arg=stamp)
        # A settled job loses its clock on the next tick.
        self.page.evaluate("jobs[0].status='completed'")
        self.page.wait_for_selector('[data-problem="run-1"] .job-elapsed', state='detached')
        self.assertEqual(self.page.evaluate('submitted'), 0)

if __name__ == '__main__':
    unittest.main(verbosity=2)
