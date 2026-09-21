// Regression contracts for failed and superseded settings-planner requests (#601).
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
const esc = value => String(value ?? '').replace(/[&<>'\"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','\"':'&quot;'}[c]));
const ctx = vm.createContext({$, esc, safeUrl:()=> '#', setInterval(){}, showView(){}, api:async()=>[],
  document:{querySelector:$, querySelectorAll:()=>[], createElement:()=>({})},
  post:(url, body) => new Promise((resolve, reject) => requests.push({url, body, resolve, reject}))});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../app/static/production.js'), 'utf8'), ctx);
const run = script => vm.runInContext(script, ctx);
const saved = [{label:'Owner draft', controls:{seed:7}, rationale:'Retained', sources:[]}];
const offer = {mode:'grid', variants:saved, axes_available:[{id:'seed', control:'seed', values:[7,8]}],
  axes_withheld:[], notice:'', generation_submitted:false, reservation_created:false};
function setup(axisIds=['stale-axis']){
  $('#experimentDialog').open = true;
  $('#experimentAxis').value = 'seed'; $('#experimentValues').value = '7'; $('#experimentBudget').value = '9';
  run(`comparisonRecipe={preset_id:'fixture', controls:{seed:7}};plannedVariants=${JSON.stringify(saved)};plannerAxes=[];plannerAxisIds=${JSON.stringify(axisIds)};plannerWithheld=[];plannerNotice='';plannerBlock();`);
}
(async()=>{
  setup();
  let wait = run('requestPlan("inspect")'), request = requests.shift();
  request.reject(new Error('Inspection unavailable')); await wait;
  assert.deepEqual(JSON.parse(run('JSON.stringify(plannerAxisIds)')), [], 'A failed read must clear stale axis identities with the vanished list');

  setup([]);
  wait = run('requestPlan("grid")'); request = requests.shift();
  assert.match($('#experimentStatus').textContent, /Reading the documented settings/);
  $('#plannedVariants').onclick({target:{closest:()=>({dataset:{dropVariant:'0'}})}});
  assert.doesNotMatch($('#experimentStatus').textContent, /Reading the documented settings/,
    'Removing a candidate must finish the superseded request status');
  request.resolve(offer); await wait;
  assert.equal(run('plannedVariants'), null, 'The removed candidate must not return from the superseded reply');

  setup([]);
  wait = run('requestPlan("grid")'); request = requests.shift();
  assert.match($('#experimentStatus').textContent, /Reading the documented settings/);
  $('#clearPlanned').onclick();
  assert.doesNotMatch($('#experimentStatus').textContent, /Reading the documented settings/,
    'Clearing the local plan must finish the superseded request status');
  request.resolve(offer); await wait;
  assert.equal(run('plannedVariants'), null, 'A cleared plan must not return from the superseded reply');
  console.log('Planner integrity: stale axes and superseded status regressions passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
