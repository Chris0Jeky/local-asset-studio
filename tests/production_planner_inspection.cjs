// Execute shipped planner handlers; only transport and DOM are deterministic fixtures.
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const elements = new Map(), requests = [];
let mounted = null;
const $ = selector => {
  if(selector === '#plannerBlock') return mounted;
  if(!elements.has(selector)) elements.set(selector, {innerHTML:'', textContent:'', value:'', open:true,
    disabled:false, hidden:false, classList:{toggle(){}}, querySelectorAll:()=>[],
    before(element){mounted = element;}, close(){this.open = false;}});
  return elements.get(selector);
};
const esc = value => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const ctx = vm.createContext({$, esc, safeUrl:()=> '#', setInterval(){}, showView(){}, api:async()=>[],
  document:{querySelector:$, querySelectorAll:()=>[], createElement:()=>({})},
  post:(url, body) => new Promise((resolve, reject) => requests.push({url, body, resolve, reject}))});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../app/static/production.js'), 'utf8'), ctx);
const run = script => vm.runInContext(script, ctx);
const saved = [{label:'Owner draft', controls:{seed:7}, rationale:'Retained', sources:[]}];
function setup(){
  $('#experimentDialog').open = true;
  $('#experimentAxis').value = 'seed'; $('#experimentValues').value = '7'; $('#experimentBudget').value = '9';
  run(`comparisonRecipe={preset_id:'fixture', controls:{seed:7}};plannedVariants=${JSON.stringify(saved)};plannerAxisIds=[];plannerBlock();`);
}
const inspect = {mode:'inspect', variants:[], axes_available:[], axes_withheld:[
  {id:'<img src=x>', control:'steps', code:'accelerator_schedule', accelerator_slots:['lora'], message:'<script>not executable</script>'}],
  notice:'Known roles, not installed-byte attestation.', generation_submitted:false, reservation_created:false};
(async()=>{
  assert.equal(requests.length, 0, 'Loading the module must not inspect or plan');
  setup();
  assert.match(mounted.innerHTML, /id="inspectSettings"/, 'Inspection must be reachable without a failed plan');
  $('#experimentBudget').value = '0'; // A read must not repair the owner's invalid draft.
  const pending = $('#inspectSettings').onclick();
  assert.equal(requests.length, 1); assert.equal(requests[0].url, '/api/experiments/plan');
  assert.equal(requests[0].body.mode, 'inspect'); assert.equal(requests[0].body.axes, undefined);
  requests.shift().resolve(inspect); await pending;
  assert.equal(run('JSON.stringify(plannedVariants)'), JSON.stringify(saved), 'Inspection preserves the proposed variants');
  assert.equal($('#experimentBudget').value, '0', 'Inspection cannot resize an existing budget');
  assert.match($('#plannerLimits').innerHTML, /&lt;script&gt;/);
  assert.doesNotMatch($('#plannerLimits').innerHTML, /<script>|<img /, 'Imported labels and reasons are text');
  assert.match($('#experimentStatus').textContent, /Existing variants are unchanged/);
  // The latest explicit action wins even when older requests resolve last.
  const old = run('requestPlan("grid")');
  const newest = run('requestPlan("inspect")');
  const first = requests.shift(), second = requests.shift();
  second.resolve(inspect); await newest;
  first.resolve({...inspect, mode:'grid', variants:[{label:'Late old plan', controls:{seed:99}}]}); await old;
  assert.equal(run('JSON.stringify(plannedVariants)'), JSON.stringify(saved));
  // Closing or replacing a dialog context refuses stale success and failure alike.
  let wait = run('requestPlan("inspect")'); const closed = requests.shift();
  $('#cancelExperiment').onclick(); const status = $('#experimentStatus').textContent;
  closed.resolve({...inspect, notice:'late closed'}); await wait;
  assert.equal($('#experimentStatus').textContent, status);
  setup(); wait = run('requestPlan("grid")'); const replaced = requests.shift();
  run('comparisonRecipe={preset_id:"fixture",controls:{seed:7}}');
  replaced.reject(new Error('old context failure')); await wait;
  assert.equal(run('JSON.stringify(plannedVariants)'), JSON.stringify(saved));
  // Dropping a variant is also a newer local choice than an outstanding plan.
  wait = run('requestPlan("grid")'); const dropped = requests.shift();
  $('#plannedVariants').onclick({target:{closest:()=>({dataset:{dropVariant:'0'}})}});
  dropped.resolve({...inspect, mode:'grid', variants:saved}); await wait;
  assert.equal(run('plannedVariants'), null, 'A removed candidate must not reappear from an old plan');
  setup();
  // An unavailable inspection leaves the local plan intact, but clears hidden axis IDs.
  run("plannerAxisIds=['stale-axis']");
  wait = run('requestPlan("inspect")'); requests.shift().reject(new Error('Inspection unavailable')); await wait;
  assert.equal(run('JSON.stringify(plannedVariants)'), JSON.stringify(saved));
  assert.equal(run('JSON.stringify(plannerAxisIds)'), '[]', 'Failed inspection cannot retain invisible axis selection');
  assert.equal($('#experimentStatus').textContent, 'Inspection unavailable');
  assert.doesNotMatch($('#plannerLimits').innerHTML, /&lt;script&gt;/, 'Stale reasons must not survive a failed read');

  // Clearing while a plan is in flight supersedes it and replaces the transient reading status.
  setup();
  wait = run('requestPlan("grid")'); const cleared = requests.shift();
  assert.match($('#experimentStatus').textContent, /Reading/);
  $('#clearPlanned').onclick();
  const clearedStatus = $('#experimentStatus').textContent;
  assert.equal(clearedStatus, 'Planned variants cleared. Nothing was reserved or submitted.');
  cleared.resolve({...inspect, mode:'grid', variants:saved}); await wait;
  assert.equal(run('plannedVariants'), null);
  assert.equal($('#experimentStatus').textContent, clearedStatus, 'Stale reply cannot restore a reading status');

  // Removing one candidate has the same latest-action status ownership.
  setup();
  run(`plannedVariants=${JSON.stringify([saved[0],{label:'Second',controls:{seed:8},rationale:'Retained',sources:[]}])};renderPlanner()`);
  wait = run('requestPlan("grid")'); const removed = requests.shift();
  $('#plannedVariants').onclick({target:{closest:()=>({dataset:{dropVariant:'0'}})}});
  const removedStatus = $('#experimentStatus').textContent;
  assert.equal(removedStatus, '1 planned variant remains. Nothing was reserved or submitted.');
  removed.resolve({...inspect, mode:'grid', variants:saved}); await wait;
  assert.equal(run('plannedVariants.length'), 1);
  assert.equal($('#experimentStatus').textContent, removedStatus);
  console.log('Planner inspection: explicit read, retained variants, escaped reasons, latest-action/context/status guards passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
